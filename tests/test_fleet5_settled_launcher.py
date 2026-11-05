"""Default-dispatch framing units; actual installed crypto is proved in Backend CI."""
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

from test_lan_leaf_rotation import _plain_unit_transport, _fixture
from test_fleet5_plain_reentry import finish, snapshot
import worker_plain_rotation as plain


ROOT=Path(__file__).resolve().parents[1]


def test_ci_pinned_fixture_refuses_non_ci_execution_before_writes(tmp_path,monkeypatch):
    path=ROOT/'tests/proofs/fleet5_settled_pinned_fixture.py'
    spec=importlib.util.spec_from_file_location('owned_pinned_ci_fixture',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.delenv('GITHUB_ACTIONS',raising=False)
    with pytest.raises(ValueError,match='restricted to isolated Linux CI'):
        module.prove_default_settled(tmp_path,tmp_path/'missing-runtime',tmp_path/'worker',tmp_path/'daemon',{},tmp_path/'result.json')
    assert list(tmp_path.iterdir())==[]


@pytest.mark.parametrize('fault',['valid','missing-launcher','missing-entry','exit','timeout','empty','oversize','duplicate','unknown','unverified'])
def test_default_settled_dispatch_has_fixed_pinned_paths_and_fails_closed(tmp_path,monkeypatch,fault):
    f=_fixture(tmp_path/'fixture');finish(f,tmp_path)
    token=plain.verify_settled(f.worker,now=f.now)
    installer=tmp_path/'installer';installer.mkdir()
    for name in ('worker_config.py','leaf_rotation_standalone_runtime.py','worker_leaf_rotation.py'):
        if (fault,name) in {('missing-launcher','leaf_rotation_standalone_runtime.py'),('missing-entry','worker_leaf_rotation.py')}:
            continue
        (installer/name).write_bytes((ROOT/'deploy/lan'/name).read_bytes())
    spec=importlib.util.spec_from_file_location('owned_default_settled_fixture',installer/'worker_config.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert module._settled_verifier is None  # Exercise the default subprocess branch.
    home=tmp_path/'owned-home';home.mkdir()
    monkeypatch.setattr(module.Path,'home',classmethod(lambda cls:home))
    expected=[module.sys.executable,'-I','-B',str(installer/'leaf_rotation_standalone_runtime.py'),'run',
              '--runtime-dir',str(home/'.local/share/saintvision/leaf-rotation-runtime'),
              '--worker-script',str(installer/'worker_leaf_rotation.py'),'--','verify-settled','--worker-root',str(f.worker)]
    calls=[]
    def invoke(command,**kwargs):
        calls.append(command)
        assert command==expected and kwargs==dict(capture_output=True,check=True,timeout=30)
        if fault=='exit':raise subprocess.CalledProcessError(1,command,stderr=b'fixture pinned verification failure')
        if fault=='timeout':raise subprocess.TimeoutExpired(command,30)
        value=dict(token)
        if fault=='unknown':value['extra']=True
        if fault=='unverified':value['verified']=False
        raw=json.dumps(value).encode()
        if fault=='empty':raw=b''
        if fault=='oversize':raw=b' '*65537+raw  # valid JSON; only the byte bound rejects it
        if fault=='duplicate':raw=raw[:-1]+b',"verified":true}'  # otherwise exact valid token
        if fault in ('oversize','duplicate'):assert json.loads(raw)==value
        return subprocess.CompletedProcess(command,0,stdout=raw,stderr=b'')
    monkeypatch.setattr(module.subprocess,'run',invoke)
    before=snapshot(f.worker)
    if fault=='valid':
        with module.rotation_mutation_guard(f.worker,action='idempotent') as verified:
            assert verified==token
        assert len(calls)==2
    else:
        with pytest.raises((ValueError,subprocess.CalledProcessError,subprocess.TimeoutExpired)):
            with module.rotation_mutation_guard(f.worker,action='idempotent'):
                pytest.fail('Invalid default verifier dispatch admitted an operation')
        assert len(calls)==(0 if fault in ('missing-launcher','missing-entry') else 1)
    assert snapshot(f.worker)==before
    assert not (f.worker/'leaf-rotation.lock').exists()
