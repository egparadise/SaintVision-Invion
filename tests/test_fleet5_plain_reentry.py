"""RS1/SF1 protocol units use synthetic signed observations and fake transport.

Actual Go/Docker acceptance is required separately in the provisioned Linux lane.
"""
from datetime import datetime, timezone
from pathlib import Path
import io
import json
import tarfile

import pytest
from cryptography.exceptions import InvalidSignature

from test_lan_leaf_rotation import _plain_unit_transport, _fixture, rotation
import peer_policy_phase as phase
import worker_plain_rotation as plain
import worker_peer_floor as transport
import worker_config as config


def finish(f, tmp_path):
    receipt = rotation.install(f.bundle,f.worker,now=f.now,restart=lambda _:None)
    body = phase.commit_body(f.manifest,(f.bundle/'rotation.json').read_bytes())
    commit = {**body,'controlSignature':f.control_key.sign(rotation._canonical(body)).hex()}
    path = tmp_path/'commit.json';path.write_bytes(phase.canonical(commit))
    rotation.finalize(f.bundle,f.worker,path,now=f.now,restart=lambda _:None)
    return path


def snapshot(root):
    return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}


def stopped_fixture(tmp_path,monkeypatch,phase_name='overlap'):
    f = _fixture(tmp_path)
    commit = finish(f,tmp_path) if phase_name=='final' else None
    if phase_name=='finalizing':
        rotation.install(f.bundle,f.worker,now=f.now,restart=lambda _:None)
        body=phase.commit_body(f.manifest,(f.bundle/'rotation.json').read_bytes())
        commit=tmp_path/'commit.json'
        commit.write_bytes(phase.canonical({**body,'controlSignature':f.control_key.sign(rotation._canonical(body)).hex()}))
        def interrupted(_):
            raise RuntimeError('fixture crash before final start')
        with pytest.raises(RuntimeError,match='fixture crash before final start'):
            rotation.finalize(f.bundle,f.worker,commit,now=f.now,restart=interrupted)
        assert plain._record(f.worker)['phase']=='finalizing'
    if phase_name=='overlap':
        rotation.install(f.bundle,f.worker,now=f.now,restart=lambda _:None)
        record = phase.strict((f.worker/'leaf-rotation.json').read_bytes())
        record.pop('receipt');record['phase']='installed';record['restartRequired']=True
        (f.worker/'leaf-rotation.json').write_bytes(phase.canonical(record))
    record = plain._record(f.worker)
    context = record['targetContext']
    state = {'Running':False,'Restarting':False,'Status':'exited'}
    container = {'Id':context['containerId'],'State':state}
    monkeypatch.setattr(transport,'target',lambda _:({},'',container,[],{},context['consumers']))
    monkeypatch.setattr(transport,'context',lambda _:context)
    entries = {name:(f.worker/name).read_bytes() for name in config.CREDENTIAL_FILES}
    entries['journal/identity.json'] = phase.canonical(dict(Tenant=f.manifest['tenantId'],Node=f.manifest['nodeId'],Epoch=f.manifest['recoveryEpoch']))
    floor_phase='final' if phase_name=='finalizing' else phase_name
    entries['journal/.peer-policy'] = phase.canonical(dict(Version=f.manifest[floor_phase+'PeerPolicyVersion'],Hash=f.manifest[floor_phase+'PeerPolicySHA256']))
    calls=[]
    def docker(*args):
        calls.append(args)
        assert args == ('start',context['containerId'])
        state.update(Running=True,Status='running')
        return b''
    monkeypatch.setattr(transport,'docker',docker)
    def archive(*_args):
        data=io.BytesIO()
        with tarfile.open(fileobj=data,mode='w') as out:
            for name,body in entries.items():
                item=tarfile.TarInfo('state/'+name);item.mode=0o600;item.size=len(body)
                out.addfile(item,io.BytesIO(body))
            item=tarfile.TarInfo('state/journal/.lock');item.mode=0o600;item.size=0
            out.addfile(item,io.BytesIO(b''))
        return data.getvalue()
    monkeypatch.setattr(transport,'_stopped_archive',archive)
    return f,commit,entries,state,calls,archive


@pytest.mark.parametrize('name',['overlap','final'])
def test_rs1_same_cid_start_requires_fresh_expected_ack_and_running_retry_does_not_start(tmp_path,monkeypatch,name):
    f,commit,entries,state,calls,_ = stopped_fixture(tmp_path,monkeypatch,name)
    before=snapshot(f.worker)
    value=plain.resume_publication(f.bundle,f.worker,commit_receipt=commit,now=f.now)
    assert value['startAttempted'] is True and value['acceptanceAssessed'] is False
    assert value['actualPeerFloor']['peerPolicyVersion']==f.manifest[name+'PeerPolicyVersion']
    assert snapshot(f.worker)==before and len(calls)==1
    value=plain.resume_publication(f.bundle,f.worker,commit_receipt=commit,now=f.now)
    assert value['startAttempted'] is False and len(calls)==1


@pytest.mark.parametrize('fault',['old-active','foreign-floor','boolean-version','wrong-identity','missing-floor','migration','stale-lock','bad-pre-signature'])
def test_rs1_unknown_or_old_state_never_starts_or_edits_journal(tmp_path,monkeypatch,fault):
    f,commit,entries,state,calls,_ = stopped_fixture(tmp_path,monkeypatch)
    if fault=='old-active':entries['peer-policy.json']=(f.bundle/'previous-peer-policy.json').read_bytes()
    elif fault=='foreign-floor':entries['journal/.peer-policy']=phase.canonical(dict(Version=99,Hash='f'*64))
    elif fault=='boolean-version':entries['journal/.peer-policy']=phase.canonical(dict(Version=True,Hash=f.manifest['overlapPeerPolicySHA256']))
    elif fault=='wrong-identity':entries['journal/identity.json']=phase.canonical(dict(Tenant='wrong',Node=f.manifest['nodeId'],Epoch=f.manifest['recoveryEpoch']))
    elif fault=='missing-floor':entries.pop('journal/.peer-policy')
    elif fault=='migration':(f.worker/'agent-binary-migration.json').write_bytes(b'{}')
    elif fault=='stale-lock':(f.worker/'leaf-rotation.lock').write_bytes(b'prior unknown owner')
    else:
        record=plain._record(f.worker);record['prePeerFloor']['nodeSignature']='0'*128
        (f.worker/'leaf-rotation.json').write_bytes(phase.canonical(record))
    before=snapshot(f.worker)
    with pytest.raises((ValueError,InvalidSignature)):plain.resume_publication(f.bundle,f.worker,now=f.now)
    assert not calls and snapshot(f.worker)==before and state['Running'] is False


@pytest.mark.parametrize('kind',['symlink','hardlink','duplicate','uid','mode','compressed'])
def test_rs1_actual_tar_rejects_links_duplicates_owner_mode_and_compression(tmp_path,monkeypatch,kind):
    f,_commit,_entries,state,calls,good=stopped_fixture(tmp_path,monkeypatch)
    original=good()
    if kind=='compressed':
        import gzip
        bad=gzip.compress(original)
    else:
        data=io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(original),mode='r:') as source,tarfile.open(fileobj=data,mode='w') as out:
            for item in source:
                body=source.extractfile(item).read()
                if item.name=='state/peer-policy.json':
                    if kind=='symlink':item.type=tarfile.SYMTYPE;item.linkname='/outside';item.size=0
                    elif kind=='hardlink':item.type=tarfile.LNKTYPE;item.linkname='state/other';item.size=0
                    elif kind=='uid':item.uid=1
                    elif kind=='mode':item.mode=0o644
                    elif kind=='duplicate':out.addfile(item,io.BytesIO(body))
                out.addfile(item,io.BytesIO(body) if item.isfile() else None)
        bad=data.getvalue()
    monkeypatch.setattr(transport,'_stopped_archive',lambda _:bad)
    before=snapshot(f.worker)
    with pytest.raises((ValueError,tarfile.TarError)):plain.resume_publication(f.bundle,f.worker,now=f.now)
    assert not calls and snapshot(f.worker)==before


def test_sf1_read_only_verifier_and_idempotent_guard_preserve_original_archive(tmp_path,monkeypatch):
    f=_fixture(tmp_path);finish(f,tmp_path)
    monkeypatch.setattr(config,'_settled_verifier',plain.verify_settled)
    before=snapshot(f.worker)
    assert plain.verify_settled(f.worker,now=f.now)['verified'] is True
    with config.rotation_mutation_guard(f.worker,action='idempotent') as proof:
        assert proof['actualFinalPeerFloor']['peerPolicyVersion']==9
    assert snapshot(f.worker)==before
    with pytest.raises(ValueError,match='forward-only'):
        with config.rotation_mutation_guard(f.worker):pytest.fail('migration inherited settlement')
    assert snapshot(f.worker)==before


def test_sf1_refuses_even_equal_staging_residue_without_deleting_it(tmp_path,monkeypatch):
    f=_fixture(tmp_path);finish(f,tmp_path)
    archive=f.worker/'leaf-rotation-finalized'/(f.manifest['rotationId']+'.json')
    pending=archive.with_name(archive.name+'.next');pending.write_bytes(archive.read_bytes())
    before=snapshot(f.worker)
    with pytest.raises(ValueError,match='unsettled'):plain.verify_settled(f.worker,now=f.now)
    assert snapshot(f.worker)==before


def test_sf1_owning_verifier_refuses_current_peer_policy_byte_drift(tmp_path,monkeypatch):
    f=_fixture(tmp_path);finish(f,tmp_path)
    settled=plain.verify_settled(f.worker,now=f.now)
    assert settled['verified'] is True
    # Hold the fixture-only transport observation at its valid signed final
    # value so a second policy-hash check cannot mask this owning SF1 guard.
    # plain._floor still verifies the signature, freshness and manifest scope.
    final_floor=dict(settled['actualFinalPeerFloor'])
    def observe(root,manifest,files):
        assert Path(root).resolve()==f.worker.resolve()
        assert manifest['rotationId']==f.manifest['rotationId']
        return dict(final_floor)
    monkeypatch.setattr(rotation,'observe_actual_floor',observe)
    before=snapshot(f.worker)
    assert plain.verify_settled(f.worker,now=f.now)['verified'] is True
    assert snapshot(f.worker)==before

    policy=f.worker/'peer-policy.json'
    original=policy.read_bytes()
    policy.write_bytes(original+b'\n')  # Same valid policy object, different bytes.
    assert phase.strict(policy.read_bytes())==phase.strict(original)
    tampered=snapshot(f.worker)
    with pytest.raises(ValueError,match='SF1 current credentials differ from the settled final bytes'):
        plain.verify_settled(f.worker,now=f.now)
    assert snapshot(f.worker)==tampered
