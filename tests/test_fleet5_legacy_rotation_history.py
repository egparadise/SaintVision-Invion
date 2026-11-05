"""Legacy :1/:2 remain historical readers, never live normal-renewal fallbacks.

Fixtures build signed historical bytes directly. No historical Python lifecycle
success here is claimed to be Go acceptance; the old Go rejection is preserved.
"""
from datetime import timedelta, timezone
import json

import pytest
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from test_lan_leaf_rotation import _plain_unit_transport, _legacy_fixture, rotation, lan_pilot, fingerprint, issue, pem
import peer_policy_phase as phase


def historical_final(tmp_path):
    f=_legacy_fixture(tmp_path,now=lan_pilot.datetime.now(timezone.utc).replace(microsecond=0))
    raw=(f.bundle/'rotation.json').read_bytes()
    body=dict(schemaVersion=rotation.SCHEMA,rotationId=f.manifest['rotationId'],proposalDigest=phase.digest(raw),targetChannelVersion=8,
              nodeId=f.manifest['nodeId'],installedNodeCertificateSHA256=f.manifest['nextNodeCertificateSHA256'],installedAt=f.manifest['createdAt'],restartObserved=True)
    receipt={**body,'nodeSignature':f.node_key.sign(rotation._canonical(body)).hex()}
    commit_body=dict(schemaVersion=rotation.SCHEMA,rotationId=f.manifest['rotationId'],proposalDigest=phase.digest(raw),nodeId=f.manifest['nodeId'],
                     channelVersion=8,certificateSHA256=f.manifest['nextNodeCertificateSHA256'],committed=True)
    commit=rotation._canonical({**commit_body,'controlSignature':f.control_key.sign(rotation._canonical(commit_body)).hex()})
    (f.worker/'node-cert.pem').write_bytes((f.bundle/'node-cert.pem').read_bytes())
    (f.worker/'peer-policy.json').write_bytes((f.bundle/'peer-policy-final.json').read_bytes())
    record=dict(rotationId=f.manifest['rotationId'],proposalDigest=phase.digest(raw),targetChannelVersion=8,phase='finalized',restartRequired=False,receipt=receipt)
    original=json.dumps(record,indent=4).encode()+b'\n\n'
    (f.worker/'leaf-rotation.json').write_bytes(original)
    validated=rotation.validate_bundle(f.bundle,f.worker,now=f.now,installed=True,finalized=True)
    directory=f.worker/'leaf-rotation-finalized';directory.mkdir(mode=0o700)
    archive=directory/(f.manifest['rotationId']+'.json')
    archive.write_bytes(rotation._finalized_evidence(validated,raw,commit,record,original))
    commit_path=tmp_path/'legacy-commit.json';commit_path.write_bytes(commit)
    return f,archive,commit_path,original


def test_original_legacy_finalized_bytes_are_verified_without_restart_or_redump(tmp_path):
    f,archive,commit,original=historical_final(tmp_path)
    before=archive.read_bytes()
    rotation.finalize(f.bundle,f.worker,commit,now=f.now,restart=lambda _:pytest.fail('historical replay restarted'))
    assert archive.read_bytes()==before and (f.worker/'leaf-rotation.json').read_bytes()==original
    assert phase.strict(before)['journalRaw'].encode()==original
    with pytest.raises(ValueError,match='Legacy'):
        rotation.install(f.bundle,f.worker,now=f.now,restart=lambda _:pytest.fail('legacy install'))


def test_explicit_legacy_to_normal3_successor_preserves_original_archive(tmp_path):
    f,archive,commit,original=historical_final(tmp_path)
    before=archive.read_bytes()
    scope=f.manifest
    actual=rotation.observe_actual_floor(f.worker,scope,{})  # explicitly synthetic unit adapter
    bundle=tmp_path/'normal3'
    lan_pilot._write_rotation_public_material(bundle,state={'tenantId':scope['tenantId'],'epoch':scope['recoveryEpoch']},node={'nodeId':scope['nodeId'],'nodeIP':scope['nodeIP']},
        current_node=f.next_node,current_control=f.next_control,control_key=f.control_key,public_key=f.node_key.public_key(),ca_key=f.issuer_key,intermediate=f.issuer,
        chain_raw=f.chain,revocations=set(),now=lan_pilot.datetime.now(timezone.utc),current_version=8,overlap_seconds=3600,leaf_valid_seconds=21600,rotation_id='b'*32,
        peer_floor_observation=actual,peer_floor_nonce=actual['nonce'],current_policy_raw=(f.worker/'peer-policy.json').read_bytes(),current_node_raw=(f.worker/'node-cert.pem').read_bytes())
    value=rotation.install(bundle,f.worker,restart=lambda _:None)
    assert value['currentPeerPolicyVersion']==8 and value['overlapPeerPolicyVersion']==9 and value['finalPeerPolicyVersion']==10
    assert archive.read_bytes()==before and phase.strict(before)['journalRaw'].encode()==original


def offline_history(tmp_path):
    f=_legacy_fixture(tmp_path,now=lan_pilot.datetime.now(timezone.utc).replace(microsecond=0)-timedelta(minutes=10))
    now=lan_pilot.datetime.now(timezone.utc).replace(microsecond=0)
    node=issue(f.issuer_key,f.issuer,f.node_key.public_key(),f'spiffe://saintvision.ai/tenant/{f.manifest["tenantId"]}/node/{f.manifest["nodeId"]}/epoch/{f.manifest["recoveryEpoch"]}',address=f.manifest['nodeIP'],now=now,valid_for=timedelta(hours=1))
    control=issue(f.issuer_key,f.issuer,f.control_key.public_key(),f'spiffe://saintvision.ai/tenant/{f.manifest["tenantId"]}/control-plane/epoch/{f.manifest["recoveryEpoch"]}',now=now,valid_for=timedelta(hours=1))
    manifest=dict(f.manifest,schemaVersion=rotation.OFFLINE_SCHEMA,recoveryMode=rotation.OFFLINE_RECOVERY_MODE,offlineAuthorizationSHA256='a'*64,
                  currentPeerPolicySHA256=phase.digest((f.worker/'peer-policy.json').read_bytes()),supersededRotationId=None,supersededProposalDigest=None,
                  nextNodeCertificateSHA256=fingerprint(node),nextControlCertificateSHA256=fingerprint(control),createdAt=now.isoformat().replace('+00:00','Z'),
                  overlapExpiresAt=(now+timedelta(minutes=30)).isoformat().replace('+00:00','Z'),certificateNotAfter=node.not_valid_after_utc.isoformat().replace('+00:00','Z'))
    for name,raw in {'node-cert.pem':pem(node),'control-cert.pem':pem(control)}.items():(f.bundle/name).write_bytes(raw)
    policy=dict(version=8,tenantId=manifest['tenantId'],nodeId=manifest['nodeId'],recoveryEpoch=manifest['recoveryEpoch'],clientFingerprints=[fingerprint(control)])
    for name,expires in [('peer-policy-overlap.json',manifest['overlapExpiresAt']),('peer-policy-final.json',manifest['certificateNotAfter'])]:
        (f.bundle/name).write_bytes(phase.canonical({**policy,'expiresAt':expires}))
    manifest['files']={name:phase.digest((f.bundle/name).read_bytes()) for name in rotation.FILE_NAMES}
    (f.bundle/'rotation.json').write_bytes(rotation._canonical(manifest));f.manifest=manifest
    return f,now


def test_offline2_historical_reader_accepts_original_scope_but_live_install_stays_blocked(tmp_path):
    f,now=offline_history(tmp_path)
    before={p.name:p.read_bytes() for p in f.worker.iterdir()}
    rotation.validate_bundle(f.bundle,f.worker,now=now)
    with pytest.raises(ValueError,match='Legacy'):rotation.install(f.bundle,f.worker,now=now,restart=lambda _:pytest.fail('offline2 live start'))
    assert {p.name:p.read_bytes() for p in f.worker.iterdir()}==before


@pytest.mark.parametrize('fault',['duplicate','unknown-field','wrong-node','wrong-epoch','wrong-chain','policy-extra','policy-fingerprint','policy-version','current-hash','next-key','expired'])
def test_offline2_historical_negative_assertions_remain_read_only(tmp_path,fault):
    f,now=offline_history(tmp_path);manifest=phase.strict((f.bundle/'rotation.json').read_bytes())
    if fault=='duplicate':
        raw=(f.bundle/'rotation.json').read_bytes();(f.bundle/'rotation.json').write_bytes(b'{"schemaVersion":"duplicate",'+raw.lstrip()[1:])
    else:
        if fault=='unknown-field':manifest['unknown']=True
        elif fault=='wrong-node':manifest['nodeId']='nod_'+'0'*26
        elif fault=='wrong-epoch':manifest['recoveryEpoch']='33333333-3333-4333-8333-333333333333'
        elif fault=='wrong-chain':manifest['caBundleSHA256']='f'*64
        elif fault=='current-hash':manifest['currentPeerPolicySHA256']='f'*64
        elif fault=='expired':now+=timedelta(hours=2)
        elif fault=='next-key':
            wrong=issue(f.issuer_key,f.issuer,Ed25519PrivateKey.generate().public_key(),f'spiffe://saintvision.ai/tenant/{manifest["tenantId"]}/node/{manifest["nodeId"]}/epoch/{manifest["recoveryEpoch"]}',address=manifest['nodeIP'],now=now,valid_for=timedelta(hours=1))
            (f.bundle/'node-cert.pem').write_bytes(pem(wrong));manifest['nextNodeCertificateSHA256']=fingerprint(wrong)
        else:
            policy=phase.strict((f.bundle/'peer-policy-overlap.json').read_bytes())
            if fault=='policy-extra':policy['extra']=True
            elif fault=='policy-fingerprint':policy['clientFingerprints']=['f'*64]
            else:policy['version']=7
            (f.bundle/'peer-policy-overlap.json').write_bytes(phase.canonical(policy))
        manifest['files']={name:phase.digest((f.bundle/name).read_bytes()) for name in rotation.FILE_NAMES}
        (f.bundle/'rotation.json').write_bytes(rotation._canonical(manifest))
    before={p.name:p.read_bytes() for p in f.worker.iterdir()}
    with pytest.raises(ValueError):rotation.validate_bundle(f.bundle,f.worker,now=now)
    assert {p.name:p.read_bytes() for p in f.worker.iterdir()}==before
