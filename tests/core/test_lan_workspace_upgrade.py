"""Reject unsafe software substitution and active work before Node mutation."""
from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import pytest

LAN = Path(__file__).resolve().parents[2]/'deploy/lan'
sys.path.insert(0, str(LAN))
spec = spec_from_file_location('workspace_upgrade', LAN/'worker_workspace.py')
worker = module_from_spec(spec)
spec.loader.exec_module(worker)


def target():
    m = dict(nodeId='nod_ASSIGNED', tenantId='tenant', epoch='epoch')
    name = 'saintvision-nod_assigned'
    args = ['--node',m['nodeId'],'--tenant',m['tenantId'],'--epoch',m['epoch'],
            '--state','/state/journal','--public-key','/state/signer.pub',
            '--tls-key','/state/node-key.pem','--tls-cert','/state/node-cert.pem',
            '--client-ca','/state/ca.pem','--peer-policy','/state/peer-policy.json',
            '--profile','lan-observe-v1','--image','sha256:'+'a'*64,'--executable','/inv-node']
    c = dict(Name='/'+name, Config=dict(User='',Labels={'ai.saintvision.node':m['nodeId']},Cmd=args),
             State=dict(Running=True,Restarting=False,Status='running'),
             Mounts=[dict(Destination='/state',Type='volume',Name=name+'-state',RW=True)])
    return m,c


@pytest.mark.parametrize('fault',['identity','volume','private-path','duplicate-profile','unknown-profile','absent'])
def test_upgrade_rejects_unowned_or_ambiguous_target_without_mutation(fault):
    m,c = target()
    before = deepcopy(c)
    if fault == 'identity': m['epoch'] = 'wrong'
    elif fault == 'volume': c['Mounts'][0]['Name'] = 'unrelated'
    elif fault == 'private-path': c['Config']['Cmd'][7] = '/state/unrelated'
    elif fault == 'duplicate-profile': c['Config']['Cmd'] += ['--profile','lan-test-v1']
    elif fault == 'unknown-profile': c['Config']['Cmd'][-5] = 'production-profile'
    else: c = None
    with pytest.raises(ValueError): worker.validate_target(m,c)
    assert before['State']['Running'] is True


def test_configuration_check_does_not_change_live_inspection():
    m,c = target()
    before = deepcopy(c)
    assert worker.validate_target(m,c) == c['Config']['Cmd']
    assert c == before


def test_owned_workload_blocks_upgrade_even_if_stopped(monkeypatch):
    calls = []
    def docker(*args):
        calls.append(args)
        return b'owned-pending-output\n'
    monkeypatch.setattr(worker,'docker',docker)
    with pytest.raises(ValueError,match='owned workload'): worker.idle('node')
    assert calls == [('ps','-aq','--filter','label=ai.saintvision.node=node','--filter','label=ai.saintvision.command')]


def test_completed_upgrade_refuses_automatic_downgrade(tmp_path,monkeypatch):
    monkeypatch.setattr(worker,'docker',lambda *a: pytest.fail('must not change Docker'))
    with pytest.raises(ValueError,match='new work'):
        worker.rollback({'nodeId':'node'},tmp_path,{'phase':'ready'})


def test_archive_corruption_rejected_before_load(tmp_path,monkeypatch):
    (tmp_path/'image.tar').write_bytes(b'changed archive')
    monkeypatch.setattr(worker,'docker',lambda *a,**k: pytest.fail('must not load unverified archive'))
    with pytest.raises(ValueError,match='checksum'):
        worker.load_image(tmp_path,{'archiveSHA256':'a'*64},'image.tar')
