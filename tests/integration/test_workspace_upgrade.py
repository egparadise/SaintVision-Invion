"""Real Docker installer upgrade/rollback against synthetic, owned Node state."""
import hashlib
import json
import os
from pathlib import Path
import sys
from uuid import uuid4
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from inv.ids import new_id
from inv.node_channels import node_uri
from inv.tooling import NodePrincipal
from pki_support import authority, issue, credentials

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'deploy/lan'))
import worker_workspace as worker
import worker_peer_floor
import peer_policy_phase

pytestmark = pytest.mark.skipif(sys.platform != 'linux' or not os.getenv('INV_UPGRADE_AGENT_IMAGE'),reason='Opt-in Linux Docker installer acceptance')


@pytest.fixture
def installation(tmp_path,monkeypatch):
    node,tenant,epoch = new_id('nod'),str(uuid4()),str(uuid4())
    name = 'saintvision-'+node.lower()
    folder,state = tmp_path/'bundle',tmp_path/'private'
    folder.mkdir(); state.mkdir(mode=0o700)
    ca = authority()
    cert = issue(ca,node_uri(NodePrincipal(tenant,node),epoch),server=True)
    control = issue(ca,f'spiffe://saintvision.ai/tenant/{tenant}/control-plane/epoch/{epoch}')
    files = credentials(state,ca,cert,prefix='node')
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    for target,source in [('node-cert.pem','certificate_file'),('node-key.pem','key_file'),('ca.pem','ca_file')]:
        (state/target).write_bytes(Path(files[source]).read_bytes())
    (state/'signer.pub').write_bytes(public)
    from datetime import datetime,timedelta,timezone
    policy = dict(version=1,tenantId=tenant,nodeId=node,recoveryEpoch=epoch,
                  expiresAt=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),clientFingerprints=[control.fingerprint])
    (state/'peer-policy.json').write_text(json.dumps(policy))
    for f in state.iterdir(): f.chmod(0o600)
    for f in ('ca.pem','signer.pub','peer-policy.json'): (folder/f).write_bytes((state/f).read_bytes())
    agent = os.environ['INV_UPGRADE_AGENT_IMAGE']
    workload = os.environ['INV_PYTHON_NODE_IMAGE']
    args = ['--serve','--listen','0.0.0.0:18443','--node',node,'--tenant',tenant,'--epoch',epoch,
            '--profile','lan-observe-v1','--image',agent,'--executable','/inv-node','--state','/state/journal',
            '--public-key','/state/signer.pub','--tls-cert','/state/node-cert.pem','--tls-key','/state/node-key.pem',
            '--client-ca','/state/ca.pem','--peer-policy','/state/peer-policy.json']
    worker.docker('volume','create','--label','ai.saintvision.node='+node,name+'-state')
    try:
        worker.docker('create','--name',name,'--label','ai.saintvision.node='+node,'--read-only',
                      '--restart','unless-stopped','--publish','127.0.0.1::18443',
                      '--mount','type=volume,source='+name+'-state,target=/state',agent,*args)
        worker.install_files(name,state)
        worker.docker('start',name)
        worker.check_running(name)
        original = worker.inspect(name)
        port = original['NetworkSettings']['Ports']['18443/tcp'][0]['HostPort']
        manifest = dict(scope='workspace-node-acceptance',profile=worker.PROFILE,nodeId=node,tenantId=tenant,epoch=epoch,
                        nodeIP='127.0.0.1',nodePort=int(port),serverIP='127.0.0.2',imageCodeSHA='test-only',
                        certificateSHA256=hashlib.sha256((state/'node-cert.pem').read_bytes()).hexdigest(),
                        agent={'agentImage':agent},workload={'agentImage':workload})
        for p in (state,folder): (p/'manifest.json').write_text(json.dumps(manifest))
        # Archive byte/config verification has separate tests and package evidence.
        # This integration boundary exercises actual Docker lifecycle and PKI copies.
        monkeypatch.setattr(worker,'load_image',lambda folder,spec,archive: spec['agentImage'])
        original_journal = worker.docker('cp',name+':/state/journal/identity.json','-')
        yield dict(node=node,name=name,state=state,folder=folder,original=original,journal=original_journal,manifest=manifest)
    finally:
        ids = worker.docker('ps','-aq','--filter','label=ai.saintvision.node='+node).decode().split()
        for identifier in ids:
            value = worker.inspect(identifier)
            assert value['Config']['Labels']['ai.saintvision.node'] == node
            worker.docker('rm','-f',identifier)
        label = json.loads(worker.docker('volume','inspect',name+'-state'))[0]['Labels']['ai.saintvision.node']
        assert label == node
        worker.docker('volume','rm',name+'-state')


def test_real_upgrade_preserves_credentials_journal_and_replays(installation):
    a = installation
    scope = dict(nodeId=a['node'],tenantId=a['manifest']['tenantId'],recoveryEpoch=a['manifest']['epoch'])
    public = {'node-cert.pem':(a['state']/'node-cert.pem').read_bytes()}
    before_floor = worker_peer_floor.observe(a['state'],scope,public)
    assert before_floor['peerPolicyVersion'] == 1 and before_floor['servingPID'] == 1
    assert before_floor['peerPolicySHA256'] == hashlib.sha256((a['state']/'peer-policy.json').read_bytes()).hexdigest()
    before_context = worker_peer_floor.context(a['state'])
    keys = {p.name:p.read_bytes() for p in a['state'].iterdir() if p.name.endswith('.pem')}
    result = worker.install(a['folder'],a['state'])
    current = worker.inspect(a['name'])
    assert current['Id'] != a['original']['Id'] and current['State']['Running']
    assert result['profile'] == worker.PROFILE and result['identityPreserved']
    assert worker.docker('cp',a['name']+':/state/journal/identity.json','-') == a['journal']
    assert {p.name:p.read_bytes() for p in a['state'].iterdir() if p.name in keys} == keys
    assert worker.install(a['folder'],a['state']) == result
    assert worker.inspect(a['name'])['Id'] == current['Id']
    backup = json.loads((a['state']/'workspace-upgrade.json').read_text())['backup']
    assert not worker.inspect(backup)['State']['Running']
    after_floor = worker_peer_floor.observe(a['state'],scope,public)
    after_context = worker_peer_floor.context(a['state'])
    assert after_floor['peerPolicyVersion'] == before_floor['peerPolicyVersion']
    for field in ('peerPolicySHA256','floorSHA256','journalIdentitySHA256','journalUID','certificateDER_SHA256'):
        assert after_floor[field] == before_floor[field]
    assert after_context['containerId'] != before_context['containerId']
    assert after_context['volumeSHA256'] == before_context['volumeSHA256']
    assert len(after_context['consumers']) == 2
    evidence = os.getenv('INV_TEST_EVIDENCE_DIR')
    if evidence:
        Path(evidence,'p0-owned-docker-floor.json').write_text(json.dumps(dict(
            scope='isolated-linux-docker-fixture',actualGoObserver=True,actualDockerOwnership=True,
            before=before_floor,after=after_floor,beforeContext=before_context,afterContext=after_context,
            storageCoexistenceAssessed=False,physicalAcceptanceAssessed=False),indent=2)+'\n')


def test_real_failed_start_restores_prior_container_and_journal(installation,monkeypatch):
    a = installation
    original_check = worker.check_running
    count = 0
    def fail_new_once(name):
        nonlocal count
        count += 1
        if count == 1: raise ValueError('injected startup health failure')
        return original_check(name)
    monkeypatch.setattr(worker,'check_running',fail_new_once)
    with pytest.raises(ValueError,match='injected'): worker.install(a['folder'],a['state'])
    assert worker.inspect(a['name'])['Id'] == a['original']['Id']
    assert worker.inspect(a['name'])['State']['Running']
    assert worker.docker('cp',a['name']+':/state/journal/identity.json','-') == a['journal']
    assert json.loads((a['state']/'workspace-upgrade.json').read_text())['phase'] == 'rolled-back'


def test_real_trust_mismatch_does_not_stop_node(installation):
    a = installation
    (a['folder']/'signer.pub').write_bytes(b'x'*32)
    with pytest.raises(ValueError,match='trust material'): worker.install(a['folder'],a['state'])
    assert worker.inspect(a['name'])['Id'] == a['original']['Id']
    assert worker.inspect(a['name'])['State']['Running']
    assert not (a['state']/'workspace-upgrade.json').exists()


@pytest.fixture
def plain_rotation_installation(tmp_path):
    """Actual Docker/Go with synthetic owned PKI; no runtime acknowledgement mock."""
    from datetime import datetime,timezone
    from test_lan_leaf_rotation import _legacy_fixture
    import worker_leaf_rotation as leaf
    import worker_plain_rotation as plain
    import worker_config
    import lan_pilot
    f=_legacy_fixture(tmp_path/'rotation',now=datetime.now(timezone.utc).replace(microsecond=0))
    f.worker.chmod(0o700)
    name='saintvision-'+f.manifest['nodeId'].lower();agent=os.environ['INV_UPGRADE_AGENT_IMAGE']
    metadata=dict(nodeId=f.manifest['nodeId'],tenantId=f.manifest['tenantId'],epoch=f.manifest['recoveryEpoch'],serverIP='127.0.0.2',nodeIP=f.manifest['nodeIP'],nodePort=18443)
    (f.worker/'manifest.json').write_bytes(peer_policy_phase.canonical(metadata))
    args=['--serve','--listen','0.0.0.0:18443','--tenant',metadata['tenantId'],'--node',metadata['nodeId'],'--epoch',metadata['epoch'],
          '--profile','lan-observe-v1','--image',agent,'--executable','/inv-node','--state','/state/journal','--public-key','/state/signer.pub',
          '--tls-cert','/state/node-cert.pem','--tls-key','/state/node-key.pem','--client-ca','/state/ca.pem','--peer-policy','/state/peer-policy.json']
    worker.docker('volume','create','--label','ai.saintvision.node='+metadata['nodeId'],name+'-state')
    try:
        worker.docker('create','--name',name,'--label','ai.saintvision.node='+metadata['nodeId'],'--read-only',
                      '--restart','unless-stopped','--mount','type=volume,source='+name+'-state,target=/state',agent,*args)
        worker_config.install_files(name,f.worker);worker.docker('start',name);worker.check_running(name)
        original=worker.inspect(name)
        observed=worker_peer_floor.observe(f.worker,dict(nodeId=metadata['nodeId'],tenantId=metadata['tenantId'],recoveryEpoch=metadata['epoch']),{'node-cert.pem':(f.worker/'node-cert.pem').read_bytes()})
        bundle=tmp_path/'actual-proposal'
        raw,manifest,files=lan_pilot._write_rotation_public_material(bundle,state={'tenantId':metadata['tenantId'],'epoch':metadata['epoch']},node={'nodeId':metadata['nodeId'],'nodeIP':metadata['nodeIP']},
            current_node=f.current_node,current_control=f.current_control,control_key=f.control_key,public_key=f.node_key.public_key(),ca_key=f.issuer_key,intermediate=f.issuer,
            chain_raw=f.chain,revocations=set(),now=datetime.now(timezone.utc),current_version=7,overlap_seconds=3600,leaf_valid_seconds=21600,rotation_id='c'*32,
            peer_floor_observation=observed,peer_floor_nonce=observed['nonce'],current_policy_raw=(f.worker/'peer-policy.json').read_bytes(),current_node_raw=(f.worker/'node-cert.pem').read_bytes())
        body=peer_policy_phase.commit_body(manifest,raw);commit=tmp_path/'commit.json'
        commit.write_bytes(peer_policy_phase.canonical({**body,'controlSignature':f.control_key.sign(leaf._canonical(body)).hex()}))
        yield dict(f=f,name=name,cid=original['Id'],bundle=bundle,manifest=manifest,commit=commit,leaf=leaf,plain=plain,config=worker_config)
    finally:
        current=worker.inspect(name)
        if current:
            assert current['Config']['Labels']['ai.saintvision.node']==metadata['nodeId']
            worker.docker('rm','-f',current['Id'])
        volume=json.loads(worker.docker('volume','inspect',name+'-state'))[0]
        assert volume['Labels']['ai.saintvision.node']==metadata['nodeId']
        worker.docker('volume','rm',name+'-state')


@pytest.mark.parametrize('point',['after-stop','after-copy'])
def test_real_stopped_publication_reentry_starts_only_frozen_phase(plain_rotation_installation,monkeypatch,point):
    a=plain_rotation_installation;f=a['f'];leaf=a['leaf'];plain=a['plain'];config=a['config']
    def crash(root):
        worker.docker('stop',a['cid'])
        if point=='after-copy':config.install_files(a['cid'],root,rotation_publication=True)
        raise RuntimeError('owned publication crash')
    with pytest.raises(RuntimeError,match='publication crash'):leaf.install(a['bundle'],f.worker,restart=crash)
    assert not worker.inspect(a['name'])['State']['Running']
    before=(f.worker/'leaf-rotation.json').read_bytes()
    if point=='after-stop':
        with pytest.raises(ValueError,match='frozen active tuple'):
            plain.resume_publication(a['bundle'],f.worker)
        assert not worker.inspect(a['name'])['State']['Running']
        assert (f.worker/'leaf-rotation.json').read_bytes()==before
        return
    value=plain.resume_publication(a['bundle'],f.worker)
    assert value['startAttempted'] is True and value['actualPeerFloor']['peerPolicyVersion']==8
    assert worker.inspect(a['name'])['Id']==a['cid'] and (f.worker/'leaf-rotation.json').read_bytes()==before
    again=plain.resume_publication(a['bundle'],f.worker)
    assert again['startAttempted'] is False
    leaf.install(a['bundle'],f.worker,restart=leaf.docker_restart)
    leaf.finalize(a['bundle'],f.worker,a['commit'],restart=leaf.docker_restart)
    original={p.name:p.read_bytes() for p in (f.worker/'leaf-rotation-finalized').iterdir()}
    monkeypatch.setattr(config,'_settled_verifier',plain.verify_settled)
    with config.rotation_mutation_guard(f.worker,action='idempotent') as proof:
        assert proof['actualFinalPeerFloor']['peerPolicyVersion']==9
    config.install_files(a['cid'],f.worker)
    assert worker.inspect(a['name'])['Id']==a['cid']
    assert {p.name:p.read_bytes() for p in (f.worker/'leaf-rotation-finalized').iterdir()}==original
    # A finalized stopped Node still needs its exact signed CP commitment.
    worker.docker('stop',a['cid'])
    with pytest.raises(ValueError,match='signed CP commitment'):plain.resume_publication(a['bundle'],f.worker)
    resumed=plain.resume_publication(a['bundle'],f.worker,commit_receipt=a['commit'])
    assert resumed['actualPeerFloor']['peerPolicyVersion']==9
    evidence=os.getenv('INV_TEST_EVIDENCE_DIR')
    if evidence:
        Path(evidence,'p0-real-stopped-reentry-settled.json').write_text(json.dumps(dict(
            scope='owned-disposable-linux-docker',actualGo=True,actualDocker=True,phaseFloors=[8,9],
            sameContainerPreserved=True,originalArchivePreserved=True,reentry=value,final=resumed,
            physicalAcceptanceAssessed=False,bootstrapConsumerClassImplemented=False),indent=2)+'\n')
