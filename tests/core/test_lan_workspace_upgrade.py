"""Reject unsafe software substitution and active work before Node mutation."""
from copy import deepcopy
from contextlib import nullcontext
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
from types import SimpleNamespace
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


@pytest.fixture
def installation(tmp_path, monkeypatch):
    """Exercise install/rollback with inspected containers, never a real daemon."""
    manifest, current = target()
    node = 'nod_'+'0'*26
    name = 'saintvision-'+node
    manifest.update(nodeId=node, serverIP='192.0.2.1', nodeIP='192.0.2.2', nodePort=18443,
                    scope='workspace-node-acceptance', profile=worker.PROFILE,
                    agent={}, workload={}, imageCodeSHA='59f0a3c2ff41ba1ae99a38515a2cdc65b2144067')
    current['Name'] = '/'+name
    current['Config']['Labels']['ai.saintvision.node'] = node
    current['Config']['Cmd'][1] = node
    current['Mounts'][0]['Name'] = name+'-state'
    socket = dict(Destination='/var/run/docker.sock', Type='bind',
                  Source='/var/run/docker.sock', RW=True, Propagation='rprivate')
    current['Mounts'].append(socket)
    current.update(Id='original-container', Image='sha256:'+'b'*64)
    folder, state = tmp_path/'bundle', tmp_path/'private'
    folder.mkdir()
    state.mkdir()
    for directory in (folder, state):
        (directory/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    for filename in ('journal', 'node-key.pem', 'storage-policy.json', 'workspace-ready.json'):
        (state/filename).write_bytes(('preserve '+filename).encode())
    (state/'workspace-upgrade.json').write_text(json.dumps({'phase':'rolled-back'}), encoding='utf-8')
    calls, containers = [], {name:current}
    agent, workload = 'sha256:'+'c'*64, 'sha256:'+'d'*64

    def inspect(container):
        calls.append(('inspect', container))
        return deepcopy(containers.get(container))

    def docker(*args, **kwargs):
        calls.append(('docker', *args))
        if args[0] == 'ps':
            return b''
        if args[:2] == ('volume', 'inspect'):
            return json.dumps([{'Labels':{'ai.saintvision.node':node}}]).encode()
        if args[0] == 'stop':
            containers[args[1]]['State'] = dict(Status='exited', Running=False, Restarting=False)
        elif args[0] == 'rename':
            containers[args[2]] = containers.pop(args[1])
            containers[args[2]]['Name'] = '/'+args[2]
        elif args[0] == 'create':
            image_index = args.index(agent)
            created = deepcopy(current)
            created.update(Id='new-container', Image=agent, Name='/'+name,
                           State=dict(Status='created', Running=False, Restarting=False))
            created['Config']['Cmd'] = list(args[image_index+1:])
            created['Config']['Labels']['ai.saintvision.upgrade'] = args[args.index('--label', 4)+1].split('=',1)[1]
            created['Mounts'] = [dict(Destination='/state', Type='volume', Name=name+'-state', RW=True), deepcopy(socket)]
            containers[name] = created
        elif args[0] == 'start':
            containers[args[1]]['State'] = dict(Status='running', Running=True, Restarting=False)
        elif args[0] != 'update':
            pytest.fail('Unexpected simulated Docker operation: '+repr(args))
        return b''

    def load_image(folder, spec, archive):
        calls.append(('load-image', archive))
        return agent if archive == 'node-agent.tar' else workload

    def check_running(container):
        calls.append(('check-running', container))
        assert containers[container]['State']['Running']

    # Only the Unix lock and external credential/image operations are simulated.
    # Production identity/mount/profile validation, state writes and rollback run.
    monkeypatch.setattr(worker, 'exclusive_lock', lambda path: nullcontext())
    monkeypatch.setattr(worker, 'inspect', inspect)
    monkeypatch.setattr(worker, 'docker', docker)
    monkeypatch.setattr(worker, 'load_image', load_image)
    monkeypatch.setattr(worker, 'verify_credentials', lambda *a: calls.append(('verify-credentials',)))
    monkeypatch.setattr(worker, 'install_files', lambda *a: calls.append(('install-files',)))
    monkeypatch.setattr(worker, 'check_running', check_running)
    return SimpleNamespace(manifest=manifest, current=current, name=name, folder=folder,
                           state=state, calls=calls, containers=containers, agent=agent)


@pytest.mark.parametrize('configuration', [
    'storage', 'policy-only', 'policy-equals', 'policy-single-dash', 'policy-single-dash-equals',
    'policy-empty', 'contribution-only', 'nested-contribution', 'other-bind', 'other-volume',
    'socket-source', 'socket-type', 'socket-readonly', 'socket-propagation', 'duplicate-socket',
])
def test_install_rejects_unpreserved_storage_before_any_docker_mutation(installation, configuration):
    p = installation
    args, mounts = p.current['Config']['Cmd'], p.current['Mounts']
    if configuration in ('storage', 'policy-only'):
        args += ['--storage-policy', '/state/storage-policy.json']
    elif configuration == 'policy-equals':
        args += ['--storage-policy=/state/storage-policy.json']
    elif configuration == 'policy-single-dash':
        args += ['-storage-policy', '/state/storage-policy.json']
    elif configuration == 'policy-single-dash-equals':
        args += ['-storage-policy=/state/storage-policy.json']
    elif configuration == 'policy-empty':
        args += ['--storage-policy=']
    if configuration in ('storage', 'contribution-only', 'nested-contribution', 'other-bind'):
        destination = {'nested-contribution':'/contribution/files', 'other-bind':'/objects'}.get(configuration, '/contribution')
        mounts.append(dict(Destination=destination, Type='bind', Source='/approved-data', RW=False, Propagation='rprivate'))
    elif configuration == 'other-volume':
        mounts.append(dict(Destination='/cache', Type='volume', Name='other-data', RW=True))
    elif configuration.startswith('socket-'):
        key, value = {'socket-source':('Source','/other/docker.sock'), 'socket-type':('Type','volume'),
                      'socket-readonly':('RW',False), 'socket-propagation':('Propagation','rshared')}[configuration]
        mounts[1][key] = value
    elif configuration == 'duplicate-socket':
        mounts.append(deepcopy(mounts[1]))
    before = deepcopy(p.current)
    private = {path.name:path.read_bytes() for path in p.state.iterdir()}
    error = None
    try:
        worker.install(p.folder, p.state)
    except ValueError as caught:
        error = str(caught)
    assert p.calls == [('inspect',p.name)], 'Preflight must precede image loads and every Docker mutation'
    assert error and 'separate' in error and 'Node' in error
    assert p.containers == {p.name:before}
    assert p.current == before and p.current['State']['Running']
    assert {path.name:path.read_bytes() for path in p.state.iterdir()} == private


@pytest.mark.parametrize('profile', ['lan-observe-v1', 'lan-test-v1', worker.PROFILE])
def test_supported_plain_upgrade_preserves_identity_journal_and_recreated_mounts(installation, profile):
    p = installation
    args = p.current['Config']['Cmd']
    args[args.index('--profile')+1] = profile
    original_args = list(args)
    key, journal = (p.state/'node-key.pem').read_bytes(), (p.state/'journal').read_bytes()
    result = worker.install(p.folder, p.state)
    assert result['status'] == 'awaiting-server-mtls-verification'
    record = json.loads((p.state/'workspace-upgrade.json').read_text('utf-8'))
    assert record['phase'] == 'ready'
    assert p.containers[record['backup']]['Id'] == 'original-container'
    assert not p.containers[record['backup']]['State']['Running']
    replacement = p.containers[p.name]
    assert replacement['State']['Running'] and replacement['Image'] == p.agent
    expected_args = list(original_args)
    for flag,value in {'--profile':worker.PROFILE, '--image':'sha256:'+'d'*64, '--executable':worker.EXECUTABLE}.items():
        expected_args[expected_args.index(flag)+1] = value
    assert replacement['Config']['Cmd'] == expected_args
    create = next(call for call in p.calls if call[:2] == ('docker','create'))
    assert [create[i+1] for i,value in enumerate(create) if value == '--mount'] == [
        'type=volume,source='+p.name+'-state,target=/state',
        'type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock',
    ]
    assert (p.state/'node-key.pem').read_bytes() == key
    assert (p.state/'journal').read_bytes() == journal


@pytest.mark.parametrize('storage_backup', [False, True])
def test_install_rollback_restores_recorded_backup_including_storage(installation, storage_backup):
    p = installation
    backup_name = p.name+'-pre-workspace-recorded'
    backup = deepcopy(p.current)
    backup['Name'] = '/'+backup_name
    backup['State'] = dict(Status='exited', Running=False, Restarting=False)
    if storage_backup:
        backup['Config']['Cmd'] += ['--storage-policy', '/state/storage-policy.json']
        backup['Mounts'].append(dict(Destination='/contribution', Type='bind',
                                   Source='/approved-data', RW=False, Propagation='rprivate'))
    p.containers[backup_name] = backup
    expected_backup = deepcopy(backup)
    p.current.update(Id='new-container', Image=p.agent)
    p.current['Config']['Labels']['ai.saintvision.upgrade'] = 'recorded-upgrade'
    record = dict(phase='created', previousId=backup['Id'], backup=backup_name,
                  agentImage=p.agent, upgradeId='recorded-upgrade')
    (p.state/'workspace-upgrade.json').write_text(json.dumps(record), encoding='utf-8')
    private = {path.name:path.read_bytes() for path in p.state.iterdir() if path.name != 'workspace-upgrade.json'}
    assert worker.install(p.folder, p.state, undo=True)['status'] == 'rolled-back'
    restored = deepcopy(p.containers[p.name])
    restored['Name'], restored['State'] = expected_backup['Name'], expected_backup['State']
    assert restored == expected_backup
    assert p.containers[p.name]['State']['Running']
    assert json.loads((p.state/'workspace-upgrade.json').read_text('utf-8'))['phase'] == 'rolled-back'
    assert not any(call[0] == 'load-image' or call[:2] == ('docker','create') for call in p.calls)
    assert {path.name:path.read_bytes() for path in p.state.iterdir() if path.name != 'workspace-upgrade.json'} == private
