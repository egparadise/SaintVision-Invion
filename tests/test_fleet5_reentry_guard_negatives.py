"""T1/T2 protocol negatives use owned synthetic signed Python fixtures only."""
import hashlib

import pytest

from test_lan_leaf_rotation import _plain_unit_transport, _fixture, rotation
from test_fleet5_plain_reentry import stopped_fixture, finish, snapshot
import peer_policy_phase as phase
import worker_plain_rotation as plain
import worker_peer_floor as transport
import worker_config as config


@pytest.mark.parametrize('fault',['phase','hash','executable'])
def test_rs1_rejects_fresh_correctly_signed_wrong_post_start_ack(tmp_path,monkeypatch,fault):
    f,commit,entries,state,calls,_=stopped_fixture(tmp_path,monkeypatch)
    original=rotation.observe_actual_floor
    acknowledged=[]
    def wrong_ack(root,manifest,files):
        value=original(root,manifest,files)
        if fault=='phase':
            value['peerPolicyVersion']=manifest['finalPeerPolicyVersion']
            value['peerPolicySHA256']=manifest['finalPeerPolicySHA256']
        elif fault=='hash':value['peerPolicySHA256']='e'*64
        else:value['servingExecutableSHA256']=hashlib.sha256(b'OTHER SYNTHETIC EXECUTABLE').hexdigest()
        body={key:item for key,item in value.items() if key!='nodeSignature'}
        value['nodeSignature']=f.node_key.sign(phase.DOMAIN+phase.floor_canonical(body)).hex()
        phase.verify_floor(value,files['node-cert.pem'],manifest,now=f.now)
        acknowledged.append(value)
        return value
    monkeypatch.setattr(rotation,'observe_actual_floor',wrong_ack)
    before=snapshot(f.worker)
    durable=entries['journal/.peer-policy']
    with pytest.raises(ValueError,match='phase|executable'):
        plain.resume_publication(f.bundle,f.worker,now=f.now)
    assert len(acknowledged)==1 and calls==[('start',plain._record(f.worker)['targetContext']['containerId'])]
    assert state['Running'] is True  # no old restore or unauthorized stop after a rejected ack
    assert snapshot(f.worker)==before and entries['journal/.peer-policy']==durable


@pytest.mark.parametrize('fault',['volume','context'])
def test_rs1_rechecks_stopped_volume_and_context_before_any_start(tmp_path,monkeypatch,fault):
    f,commit,entries,state,calls,archive=stopped_fixture(tmp_path,monkeypatch)
    context=plain._record(f.worker)['targetContext']
    reads=[]
    def raced_archive(root):
        reads.append(root)
        if len(reads)==2 and fault=='volume':entries['signer.pub']=b'R'*32
        return archive(root)
    def raced_context(root):
        return {**context,'image':'sha256:'+'f'*64} if len(reads)>=2 and fault=='context' else context
    monkeypatch.setattr(transport,'_stopped_archive',raced_archive)
    monkeypatch.setattr(transport,'context',raced_context)
    before=snapshot(f.worker);durable=entries['journal/.peer-policy']
    with pytest.raises(ValueError,match='changed|ownership'):
        plain.resume_publication(f.bundle,f.worker,now=f.now)
    assert len(reads)==2 and not calls and state['Running'] is False
    assert snapshot(f.worker)==before and entries['journal/.peer-policy']==durable


@pytest.mark.parametrize('floor_phase',['current','overlap','final'])
def test_rs1_finalizing_accepts_only_overlap_or_final_durable_floor(tmp_path,monkeypatch,floor_phase):
    f,commit,entries,state,calls,_=stopped_fixture(tmp_path,monkeypatch,'finalizing')
    entries['journal/.peer-policy']=phase.canonical(dict(Version=f.manifest[floor_phase+'PeerPolicyVersion'],Hash=f.manifest[floor_phase+'PeerPolicySHA256']))
    before=snapshot(f.worker);durable=entries['journal/.peer-policy']
    if floor_phase=='current':
        with pytest.raises(ValueError,match='outside the frozen tuples'):
            plain.resume_publication(f.bundle,f.worker,commit_receipt=commit,now=f.now)
        assert not calls and state['Running'] is False
    else:
        value=plain.resume_publication(f.bundle,f.worker,commit_receipt=commit,now=f.now)
        assert value['actualPeerFloor']['peerPolicyVersion']==f.manifest['finalPeerPolicyVersion']
        assert len(calls)==1 and state['Running'] is True
    assert snapshot(f.worker)==before and entries['journal/.peer-policy']==durable


def test_generic_guard_rechecks_settled_state_after_operation_and_never_restores(tmp_path,monkeypatch):
    f=_fixture(tmp_path);finish(f,tmp_path)
    monkeypatch.setattr(config,'_settled_verifier',plain.verify_settled)
    before=snapshot(f.worker)
    with pytest.raises(ValueError,match='changed settled identity, history or ownership'):
        with config.rotation_mutation_guard(f.worker,action='idempotent') as token:
            assert token['verified'] is True
            (f.worker/'signer.pub').write_bytes(b'R'*32)
    assert snapshot(f.worker)=={**before,'signer.pub':b'R'*32}
    assert not (f.worker/'leaf-rotation.lock').exists()


@pytest.mark.parametrize('malformed',['g'*64,'a'*63,'A'*64,'a'*65])
def test_signed_malformed_executable_digest_is_rejected_independently(tmp_path,malformed):
    f=_fixture(tmp_path)
    valid=phase.strict((f.bundle/'peer-floor-observation.json').read_bytes())
    certificate=(f.bundle/'previous-node-cert.pem').read_bytes()
    phase.verify_floor(valid,certificate,f.manifest,now=f.now)
    invalid={**valid,'servingExecutableSHA256':malformed}
    body={key:value for key,value in invalid.items() if key!='nodeSignature'}
    invalid['nodeSignature']=f.node_key.sign(phase.DOMAIN+phase.floor_canonical(body)).hex()
    f.node_key.public_key().verify(bytes.fromhex(invalid['nodeSignature']),phase.DOMAIN+phase.floor_canonical(body))
    assert all(invalid[key]==valid[key] for key in valid if key not in {'servingExecutableSHA256','nodeSignature'})
    with pytest.raises(ValueError,match='digest differs'):
        phase.verify_floor(invalid,certificate,f.manifest,now=f.now)
