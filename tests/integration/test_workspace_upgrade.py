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
