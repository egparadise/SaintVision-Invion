"""PG-free LAN pilot multi-Node state and artifact boundary tests."""
from argparse import Namespace
import json
from pathlib import Path
import sys
import zipfile

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import NameOID
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import lan_pilot


def node(node_id, node_ip, *, provisioned=True, colocated=False):
    return dict(nodeId=node_id, nodeIP=node_ip, nodePort=18443,
                provisioned=provisioned,
                coLocatedWithControlPlane=colocated)


def state(nodes):
    primary = nodes[0]
    return dict(
        epoch='epoch-test', tenantId='tenant-test', nodes=nodes,
        nodeId=primary['nodeId'], nodeIP=primary['nodeIP'], nodePort=18443,
        serverIP='192.168.45.74', downloadPort=18081, baseSHA='a' * 40,
        serverNodeColocationAllowed=any(
            current['nodeIP'] == '192.168.45.74' for current in nodes),
        agentImage='sha256:' + 'b' * 64, initialized=True,
    )


def csr(node_id):
    key = Ed25519PrivateKey.generate()
    request = (x509.CertificateSigningRequestBuilder()
               .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, node_id)]))
               .sign(key, None))
    return request.public_bytes(serialization.Encoding.PEM)


def test_legacy_single_node_state_normalizes_and_addition_preserves_identity():
    legacy = dict(epoch='epoch-test', tenantId='tenant-test', nodeId='nod_primary',
                  serverIP='192.168.45.74', nodeIP='192.168.45.81', nodePort=18443,
                  initialized=True)

    normalized = lan_pilot.normalized_state(legacy)
    expanded, added = lan_pilot.add_requested_nodes(
        normalized, ['192.168.45.81', '192.168.45.82'])

    assert expanded['nodeId'] == 'nod_primary'
    assert expanded['nodeIP'] == '192.168.45.81'
    assert expanded['nodes'][0] == node('nod_primary', '192.168.45.81')
    assert len(added) == 1
    assert added[0]['nodeIP'] == '192.168.45.82'
    assert added[0]['nodeId'].startswith('nod_')
    assert added[0]['provisioned'] is False


def test_node_addresses_are_private_unique_and_distinct_from_server():
    lan_pilot.validate_node_ips('192.168.45.74', ['192.168.45.81', '192.168.45.82'])
    with pytest.raises(ValueError, match='specified once'):
        lan_pilot.validate_node_ips('192.168.45.74', ['192.168.45.81', '192.168.45.81'])
    with pytest.raises(ValueError, match='allow-server-node-colocation'):
        lan_pilot.validate_node_ips('192.168.45.74', ['192.168.45.74'])
    lan_pilot.validate_node_ips(
        '192.168.45.74', ['192.168.45.74'],
        allow_server_node_colocation=True)
    with pytest.raises(ValueError, match='private LAN'):
        lan_pilot.validate_node_ips('192.168.45.74', ['8.8.8.8'])


def test_colocated_node_metadata_is_derived_and_cannot_be_forged():
    configured = state([
        node('nod_01HZZZZZZZZZZZZZZZZZZZZZZZ', '192.168.45.81'),
        node('nod_01J00000000000000000000000', '192.168.45.74', colocated=True),
    ])

    assert lan_pilot.configured_nodes(configured)[1]['coLocatedWithControlPlane'] is True
    configured['nodes'][1]['coLocatedWithControlPlane'] = False
    with pytest.raises(ValueError, match='co-location metadata differs'):
        lan_pilot.configured_nodes(configured)

    configured['nodes'][1]['coLocatedWithControlPlane'] = True
    configured['serverNodeColocationAllowed'] = False
    with pytest.raises(ValueError, match='not authorized'):
        lan_pilot.configured_nodes(configured)


def test_colocated_node_addition_requires_persisted_opt_in():
    configured = state([
        node('nod_01HZZZZZZZZZZZZZZZZZZZZZZZ', '192.168.45.81'),
    ])
    with pytest.raises(ValueError, match='not authorized'):
        lan_pilot.add_requested_nodes(configured, ['192.168.45.74'])

    configured['serverNodeColocationAllowed'] = True
    expanded, added = lan_pilot.add_requested_nodes(
        configured, ['192.168.45.74'])
    assert added[0]['nodeIP'] == '192.168.45.74'
    assert expanded['nodes'][1]['coLocatedWithControlPlane'] is True


def test_colocated_manifest_is_excluded_from_adr100_measurements():
    configured = state([
        node('nod_01HZZZZZZZZZZZZZZZZZZZZZZZ', '192.168.45.81'),
        node('nod_01J00000000000000000000000', '192.168.45.74', colocated=True),
    ])
    manifest = lan_pilot.manifest_for_node(
        configured, configured['nodes'][1],
        {'RootFS': {'Layers': []}, 'Config': {}}, 'test:tag')

    assert manifest['schemaVersion'] == 3
    assert manifest['coLocatedWithControlPlane'] is True
    assert manifest['measurementEligible'] == {'s05': False, 's07': False}
    assert manifest['exclusionReason'] == 'cp-host-colocation'


def test_csr_common_name_selects_exact_configured_node():
    configured = state([
        node('nod_01HZZZZZZZZZZZZZZZZZZZZZZZ', '192.168.45.81'),
        node('nod_01J00000000000000000000000', '192.168.45.82'),
    ])

    selected = lan_pilot.node_from_csr(
        configured, csr('nod_01J00000000000000000000000'))

    assert selected['nodeIP'] == '192.168.45.82'
    with pytest.raises(ValueError, match='not configured'):
        lan_pilot.node_from_csr(
            configured, csr('nod_01J11111111111111111111111'))


def test_legacy_single_node_public_paths_remain_downloadable(tmp_path):
    legacy = dict(epoch='epoch-test', tenantId='tenant-test', nodeId='nod_primary',
                  serverIP='192.168.45.74', nodeIP='192.168.45.81', nodePort=18443,
                  initialized=True)
    public = tmp_path / 'public'
    public.mkdir()
    (public / 'worker.zip').write_bytes(b'legacy-worker')
    (public / 'node-cert.pem').write_bytes(b'legacy-certificate')

    assert lan_pilot.artifact_for_client(
        legacy, public, '192.168.45.81', '/worker.zip') == public / 'worker.zip'
    assert lan_pilot.artifact_for_client(
        legacy, public, '192.168.45.81', '/node-cert.pem') == public / 'node-cert.pem'


def test_secondary_node_never_falls_back_to_primary_legacy_artifacts(tmp_path):
    configured = state([
        node('nod_01HZZZZZZZZZZZZZZZZZZZZZZZ', '192.168.45.81'),
        node('nod_01J00000000000000000000000', '192.168.45.82'),
    ])
    public = tmp_path / 'public'
    public.mkdir()
    (public / 'worker.zip').write_bytes(b'primary-worker-only')
    (public / 'node-cert.pem').write_bytes(b'primary-certificate-only')

    assert lan_pilot.artifact_for_client(
        configured, public, '192.168.45.82', '/worker.zip') is None
    assert lan_pilot.artifact_for_client(
        configured, public, '192.168.45.82', '/node-cert.pem') is None


@pytest.mark.parametrize('field', ['nodeId', 'recoveryEpoch', 'clientFingerprints'])
def test_existing_peer_policy_mismatch_is_rejected_without_replacement(tmp_path, field):
    configured = state([
        node('nod_01HZZZZZZZZZZZZZZZZZZZZZZZ', '192.168.45.81'),
    ])
    ca_key, ca_cert = lan_pilot.ca_pair()
    control_key = Ed25519PrivateKey.generate()
    control = lan_pilot.issue(
        ca_key, ca_cert, control_key.public_key(),
        'spiffe://saintvision.ai/tenant/tenant-test/control-plane/epoch/epoch-test')
    (tmp_path / 'control-cert.pem').write_bytes(lan_pilot.pem(control))
    policy = dict(
        version=1, tenantId=configured['tenantId'],
        nodeId=configured['nodeId'], recoveryEpoch=configured['epoch'],
        expiresAt='2099-01-01T00:00:00+00:00',
        clientFingerprints=[lan_pilot.fingerprint(control)],
    )
    if field == 'nodeId':
        policy[field] = 'nod_DIFFERENT'
    elif field == 'recoveryEpoch':
        policy[field] = 'different-epoch'
    else:
        policy[field] = ['0' * 64]
    target = tmp_path / 'peer-policy.json'
    target.write_text(json.dumps(policy, indent=2), encoding='utf-8')
    before = target.read_bytes()

    with pytest.raises(ValueError, match='Existing peer policy identity differs'):
        lan_pilot.ensure_node_policy(tmp_path, configured, configured['nodes'][0])

    assert target.read_bytes() == before


def test_bundle_emits_distinct_node_archives_and_ip_scoped_downloads(tmp_path, monkeypatch, capsys):
    nodes = [
        node('nod_01HZZZZZZZZZZZZZZZZZZZZZZZ', '192.168.45.81'),
        node('nod_01J00000000000000000000000', '192.168.45.82'),
    ]
    configured = state(nodes)
    lan_pilot.save(tmp_path, configured)
    (tmp_path / 'ca.pem').write_bytes(b'public-ca')
    (tmp_path / 'signer.pub').write_bytes(b'public-signer')
    for current in nodes:
        policy_path = lan_pilot.node_policy_path(tmp_path, configured, current)
        policy_path.write_text(json.dumps(dict(
            version=1, tenantId=configured['tenantId'], nodeId=current['nodeId'],
            recoveryEpoch=configured['epoch'], expiresAt='2099-01-01T00:00:00Z',
            clientFingerprints=['f' * 64])), encoding='utf-8')

    def fake_run(command, **_kwargs):
        command = [str(value) for value in command]
        if command[:3] == ['docker', 'image', 'inspect'] and '--format' in command:
            return configured['agentImage']
        if command[:2] == ['docker', 'save']:
            Path(command[3]).write_bytes(b'node-image')
            return ''
        if command[:3] == ['docker', 'image', 'inspect']:
            return json.dumps([{'RootFS': {'Layers': ['sha256:' + 'c' * 64]},
                                'Config': {'Entrypoint': ['/inv-node']}}])
        raise AssertionError(command)

    monkeypatch.setattr(lan_pilot, 'run', fake_run)
    lan_pilot.bundle(Namespace(state=tmp_path, go=None, reuse_image=True))
    output = json.loads(capsys.readouterr().out)

    assert len(output['nodes']) == 2
    assert output['nodes'][0]['sha256'] != output['nodes'][1]['sha256']
    for current, artifact in zip(nodes, output['nodes'], strict=True):
        archive_path = Path(artifact['archive'])
        with zipfile.ZipFile(archive_path) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            policy = json.loads(archive.read('peer-policy.json'))
        assert (manifest['nodeId'], manifest['nodeIP']) == (current['nodeId'], current['nodeIP'])
        assert policy['nodeId'] == current['nodeId']

    public = tmp_path / 'public'
    first = lan_pilot.artifact_for_client(configured, public, '192.168.45.81', '/worker.zip')
    second = lan_pilot.artifact_for_client(configured, public, '192.168.45.82', '/worker.zip')
    assert first == Path(output['nodes'][0]['archive'])
    assert second == Path(output['nodes'][1]['archive'])
    assert first != second
    assert lan_pilot.artifact_for_client(
        configured, public, '192.168.45.81', '/worker.sha256') is None
    with pytest.raises(PermissionError, match='not an allowed Node'):
        lan_pilot.artifact_for_client(configured, public, '192.168.45.99', '/worker.zip')


def test_status_rows_keep_partial_nodes_visible(monkeypatch):
    nodes = [
        node('nod_01HZZZZZZZZZZZZZZZZZZZZZZZ', '192.168.45.81'),
        node('nod_01J00000000000000000000000', '192.168.45.82'),
    ]
    configured = state(nodes)

    class Result:
        def __init__(self, value):
            self.value = value

        def fetchone(self):
            return self.value

    class Connection:
        def execute(self, query, params):
            node_id = params[0]
            if 'FROM inv.nodes' in query:
                if node_id == nodes[0]['nodeId']:
                    return Result(dict(node_id=node_id, status='online', heartbeat_at='now'))
                return Result(None)
            if node_id == nodes[0]['nodeId']:
                return Result(dict(received_at='now', snapshot={'cpu': 4}))
            return Result(None)

    class Transaction:
        def __enter__(self):
            return Connection()

        def __exit__(self, *_args):
            return False

    class Runtime:
        def transaction(self, tenant_id):
            assert tenant_id == configured['tenantId']
            return Transaction()

    monkeypatch.setattr(lan_pilot, 'runtime', lambda _state: Runtime())
    rows = lan_pilot.node_status_rows(configured)

    assert [(row['nodeId'], row['nodeIP']) for row in rows] == [
        (nodes[0]['nodeId'], '192.168.45.81'),
        (nodes[1]['nodeId'], '192.168.45.82'),
    ]
    assert rows[0]['observed'] is True
    assert rows[1]['node'] is None
    assert rows[1]['observed'] is False
