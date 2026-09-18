"""Opt-in local Linux kernel integration; never connects to an existing database.

Build a source copy, pinned Python/Node image, isolated network and disposable DB.
No production identity/PKI or user Workspace is mounted. Keep private logs for
debugging and emit only bounded public case results. Requires a local Docker CLI.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from uuid import uuid4
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TESTS = ['tests/integration/' + name + '.py' for name in (
    'test_node_runtime', 'test_node_delivery', 'test_output_ingestion',
    'test_workspace_resume', 'test_workspace_api', 'test_developer_workloads', 'test_workspace_start', 'test_business_handoff', 'test_shard_recovery', 'test_containment')]


#: user:password@ inside a DSN/URL. The kernel DSN carries a synthetic password,
#: which is why diagnostics were dropped; masking the value keeps the error kind.
_CREDENTIAL = re.compile(r'(://[^:@/\s]+:)[^@/\s]+(@)')


def _masked(stderr):
    """The docker error kind, with credential values masked (VF-CL-R-001).

    Suppressing the whole message made a daemon timeout indistinguishable from a
    resource-exhaustion or a product failure, so a failure could only be guessed
    at. Keeping a bounded, credential-masked stderr makes the classification
    falsifiable without leaking the synthetic DSN password.
    """
    text = stderr.decode('utf-8', errors='replace') if isinstance(stderr, (bytes, bytearray)) else str(stderr or '')
    return _CREDENTIAL.sub(r'\1***\2', text).strip()[:400] or '(no stderr)'


def run(args, **kwargs):
    return subprocess.run([str(v) for v in args], capture_output=True,
                          timeout=kwargs.pop('timeout', 60), **kwargs)


def checked(args, **kwargs):
    result = run(args, **kwargs)
    if result.returncode:
        raise RuntimeError(
            f'{Path(str(args[0])).name} exit {result.returncode}: {_masked(result.stderr)}')
    return result.stdout.decode('utf-8', errors='replace').strip()


def prune_stale_kernel_test_residue():
    """Remove *exited* kernel-test containers and empty networks from prior runs.

    The per-invocation finally deliberately preserves this run's stopped
    containers for post-mortem logs, but nothing bounded that: weeks of runs
    accumulated (VF-CL-R-001 -- ~130 exited ai.saintvision.kernel-test containers
    exhausted an 8 GB host and timed out a separate image lane). Pruning only
    *non-running* kernel-test-labelled residue at the start of a run bounds the
    accumulation to the current invocation, while a failed run's artifacts still
    survive until the next run starts. Running containers are never touched, and
    this is best-effort -- a prune failure must not abort the run it precedes.
    """
    stale = run(['docker', 'ps', '-aq', '--filter', 'label=ai.saintvision.kernel-test',
                 '--filter', 'status=exited', '--filter', 'status=created',
                 '--filter', 'status=dead']).stdout.decode('utf-8', 'replace').split()
    for container in stale:
        run(['docker', 'rm', '-f', container])
    for network in run(['docker', 'network', 'ls', '--filter', 'label=ai.saintvision.kernel-test',
                        '--format', '{{.ID}}']).stdout.decode('utf-8', 'replace').split():
        run(['docker', 'network', 'rm', network])  # refuses while still in use; ignored


def image_id(reference):
    return json.loads(checked(['docker', 'image', 'inspect', reference]))[0]['Id']


def source_files():
    paths = checked(['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT).splitlines()
    exact = {'pyproject.toml', 'alembic.ini', 'requirements-core.txt', 'requirements-test.txt', 'requirements-backend.txt',
             'tools/storage_check.py', 'tools/provision_credentials.py', 'tools/operational_readiness.py', 'tools/check_subject_tenant.py', 'tools/check_definer_functions.py', 'tools/definer-policy.json', 'tools/recovery_drill.py', 'tools/provision_account.py', 'tools/prepare_git_probe.py', 'tools/kernel_test_entry.py', 'tools/studio_templates.py', 'tools/check_kernel_docker.py', 'tools/migration_graph.py', 'tools/check_migration_upgrade.py', 'deploy/testing/Dockerfile.kernel', 'deploy/testing/Dockerfile.python-node'}
    return sorted(set(p for p in paths if p in exact or p.startswith(('src/', 'services/control-plane/src/', 'services/node-agent/', 'packages/contracts-go/', 'tests/', 'contracts/', 'migrations/'))))


def prepare(args):
    name = 'sv-kernel-' + uuid4().hex[:12]
    work = ROOT / '.work' / name
    work.mkdir(parents=True)
    if os.name == 'nt':
        sid = checked(['powershell.exe', '-NoProfile', '-Command', '[Security.Principal.WindowsIdentity]::GetCurrent().User.Value'])
        checked(['icacls.exe', work, '/inheritance:r', '/grant:r', '*'+sid+':(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'])
    else:
        work.chmod(0o700)
    context = work / 'context'
    context.mkdir()
    hashes = {}
    for relative in source_files():
        source = ROOT / relative
        if source.is_symlink() or not source.resolve().is_relative_to(ROOT):
            raise ValueError('Source symlink refused')
        target = context / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        hashes[relative] = hashlib.sha256(target.read_bytes()).hexdigest()
    binaries = context / 'binaries'
    binaries.mkdir()
    env = dict(os.environ, GOOS='linux', GOARCH='amd64', CGO_ENABLED='0', GOMAXPROCS='2')
    for binary, package in [('inv-node','./cmd/inv-node'), ('inv-discover','./cmd/inv-discover'),
                            ('inv-supervisor','./cmd/inv-supervisor'), ('probe','./tests/probe')]:
        checked([args.go, 'build', '-p', '1', '-trimpath', '-o', binaries/binary, package],
                cwd=ROOT/'services/node-agent', env=env, timeout=180)
    python_image = image_id(args.python_image)
    # Use an explicit local tag to avoid Docker treating a bare image ID in FROM
    # as a remote repository. Record the resolved content ID for evidence.
    python_tag = 'saintvision-kernel-base:' + python_image.split(':')[1]
    checked(['docker','tag',python_image,python_tag])
    shutil.copyfile(ROOT/'deploy/testing/Dockerfile.kernel', context/'Dockerfile')
    result = run(['docker','build','--pull=false','--build-arg','PYTHON_IMAGE='+python_tag,'-t',name,context], timeout=600)
    (work/'build.log').write_bytes(result.stdout+result.stderr)
    if result.returncode: raise RuntimeError(f'Kernel image build failed; private log: {work / "build.log"}')
    kernel_image = image_id(name)
    probe = work/'node-image'
    probe.mkdir()
    for binary in ('probe','inv-supervisor'): shutil.copyfile(binaries/binary,probe/binary)
    shutil.copyfile(ROOT/'deploy/testing/Dockerfile.python-node',probe/'Dockerfile')
    result = run(['docker','build','--pull=false','--build-arg','PYTHON_IMAGE='+python_tag,
                  '-t',name+'-node',probe],timeout=300)
    (work/'node-build.log').write_bytes(result.stdout+result.stderr)
    if result.returncode: raise RuntimeError(f'Node image build failed; private log: {work / "node-build.log"}')
    value = dict(name=name,work=str(work),codeSHA=checked(['git','rev-parse','HEAD'],cwd=ROOT),
                 dirty=bool(checked(['git','status','--porcelain'],cwd=ROOT)),
                 pythonImage=python_image,kernelImage=kernel_image,nodeImage=image_id(name+'-node'),
                 postgresImage=image_id(args.postgres_image),sourceHashes=hashes,
                 binaryHashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in binaries.iterdir()})
    (work/'prepared.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
    print(json.dumps({'prepared':str(work/'prepared.json'),'codeSHA':value['codeSHA'],
                      'nodeImage':value['nodeImage'],'scope':'isolated-test-environment'}),flush=True)
    return value


def owned(name, label):
    result=run(['docker','inspect',name])
    if result.returncode: return None
    value=json.loads(result.stdout)[0]
    if value['Config'].get('Labels',{}).get('ai.saintvision.kernel-test') != label:
        raise ValueError('Test container ownership differs; preserved')
    return value


def release_network(network, label):
    """Release this invocation's empty network, preserving containers and logs."""
    result = run(['docker', 'network', 'inspect', network])
    if result.returncode:
        diagnostic = result.stderr.lower()
        if b'not found' in diagnostic or b'no such network' in diagnostic:
            return True
        raise RuntimeError('Test network inspection failed; network preserved')
    value = json.loads(result.stdout)[0]
    if (value['Name'] != network or value.get('Driver') != 'bridge'
            or not value.get('Internal')
            or value.get('Labels', {}).get('ai.saintvision.kernel-test') != label
            or value.get('Containers')):
        raise ValueError('Test network ownership or empty state differs; preserved')
    for suffix in ('-runner', '-db'):
        container = owned(label + suffix, label)
        if container and (container['State']['Running'] or container['State']['Pid']):
            raise ValueError('Test container still running; network preserved')
    checked(['docker', 'network', 'rm', value['Id']])
    return not checked(['docker', 'network', 'ls', '--filter', 'id=' + value['Id'], '--format', '{{.ID}}'])


def execute(prepared, tests):
    if set(source_files()) != set(prepared['sourceHashes']):
        raise ValueError('Prepared source file set differs; rebuild before running')
    for relative, expected in prepared['sourceHashes'].items():
        if hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=expected:
            raise ValueError('Prepared source differs; rebuild before running')
    if not tests or any(t not in prepared['sourceHashes'] or not t.startswith(('tests/integration/test_', 'tests/test_')) for t in tests):
        raise ValueError('Tests must be present in the prepared source copy')
    work=Path(prepared['work'])/'runs'/uuid4().hex[:12]
    work.mkdir(parents=True)
    name=prepared['name']+'-'+work.name
    network=name+'-net'; database=name+'-db'; runner=name+'-runner'
    password=uuid4().hex
    (work/'postgres.env').write_text('POSTGRES_PASSWORD='+password+'\n',encoding='ascii')
    config=dict(adminDSN=f'postgresql://postgres:{password}@{database}:5432/postgres',nodeImage=prepared['nodeImage'],tests=tests)
    (work/'config.json').write_text(json.dumps(config),encoding='utf-8')
    exit_code=None
    # Bound residue from prior runs before creating this run's containers, so a
    # host that has accumulated weeks of stopped test containers does not time out
    # this run (VF-CL-R-001). This run's own resources are created after the prune.
    prune_stale_kernel_test_residue()
    try:
        checked(['docker','network','create','--internal','--label','ai.saintvision.kernel-test='+name,network])
        checked(['docker','run','-d','--name',database,'--label','ai.saintvision.kernel-test='+name,
                 '--network',network,'--cpus','0.5','--memory','256m','--pids-limit','128',
                 '--env-file',work/'postgres.env','--tmpfs','/var/lib/postgresql/data:rw,size=268435456',prepared['postgresImage']])
        for _ in range(30):
            if run(['docker','exec',database,'pg_isready','-U','postgres'],timeout=5).returncode==0: break
            time.sleep(0.5)
        else: raise RuntimeError('Isolated database startup timed out')
        checked(['docker','create','--name',runner,'--label','ai.saintvision.kernel-test='+name,
                 '--network',network,'--cpus','1','--memory','512m','--pids-limit','256',
                 '--cap-drop','ALL','--security-opt','no-new-privileges',
                 '--mount','type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock',
                 prepared['kernelImage']])
        # No host workspace bind. docker cp targets only the new owned runner.
        checked(['docker','cp',work/'config.json',runner+':/run/test/config.json'])
        checked(['docker','start',runner])
        deadline=time.monotonic()+960
        while time.monotonic()<deadline:
            current=owned(runner,name)
            if not current['State']['Running']:
                exit_code=current['State']['ExitCode'];break
            time.sleep(1)
        else: raise RuntimeError('Kernel test deadline exceeded')
        checked(['docker','cp',runner+':/evidence/.',str(work)])
        rows=[]
        xml=ET.parse(work/'tests.xml')
        for case in xml.findall('.//testcase'):
            status=next((tag for tag in ('failure','error','skipped') if case.find(tag) is not None),'passed')
            rows.append(dict(name=case.attrib['name'],suite=case.attrib.get('classname'),status=status))
        cleanup = {}
        for target in (runner,database):
            current = owned(target,name)
            if current is None: raise RuntimeError('Test cleanup identity unavailable')
            if current['State']['Running']: checked(['docker','stop','--time','10',target],timeout=30)
            final = owned(target,name)
            cleanup[target] = bool(final and not final['State']['Running'] and final['State']['Pid']==0)
        cleanup[network] = release_network(network, name)
        workloads = [json.loads(p.read_text()) for p in sorted(work.glob('developer-*.json'))]
        first_workloads = [json.loads(p.read_text()) for p in sorted(work.glob('first-*.json'))]
        model_workloads = [json.loads(p.read_text()) for p in sorted(work.glob('model-*.json'))]
        models_complete = ('tests/integration/test_model_node.py' not in tests or
                           {row['case'] for row in model_workloads} == {'single','output-recovery','cancel','stale','node-loss','replacement-node'})
        records_complete = ('tests/integration/test_developer_workloads.py' not in tests or
                            {row['case'] for row in workloads} == {'python','ai','ai-output-recovery','python-failure'})
        first_complete = ('tests/integration/test_workspace_start.py' not in tests or
                          {row['case'] for row in first_workloads} == {'python','ai','output-recovery','failure'})
        result=dict(at=datetime.now(timezone.utc).isoformat(),codeSHA=prepared['codeSHA'],dirty=prepared['dirty'],
                    sourceHashes=prepared['sourceHashes'],binaryHashes=prepared['binaryHashes'],
                    nodeImage=prepared['nodeImage'],kernelImage=prepared['kernelImage'],postgresImage=prepared['postgresImage'],
                    scope='local-kernel-tests-synthetic-identity-not-two-physical-pcs',exitCode=exit_code,
                    passed=exit_code==0 and bool(rows) and all(r['status']=='passed' for r in rows) and all(cleanup.values()) and records_complete and first_complete and models_complete,cases=rows,
                    cleanup=cleanup,developerWorkloads=workloads,firstWorkloads=first_workloads,modelWorkloads=model_workloads,
                    privateLogSHA256=hashlib.sha256((work/'pytest.log').read_bytes()).hexdigest())
        (work/'evidence.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:result[k] for k in ('at','codeSHA','dirty','scope','exitCode','passed')} | {'cases':len(rows),'evidence':str(work/'evidence.json')}),flush=True)
        return result['passed']
    finally:
        # Stop only containers created and labelled for this invocation. Preserve
        # stopped containers/private logs on failures; no broad name-prefix delete.
        # Best-effort (VF-CL-R-001): cleanup runs through the non-raising helper and
        # is wrapped, so a stop or network-release failure under load cannot mask the
        # original error or skip the remaining cleanup. Residue this leaves stopped
        # is bounded by the next run's start-of-run prune.
        for target in (runner,database):
            try:
                value=owned(target,name)
                if value and value['State']['Running']:
                    run(['docker','stop','--time','10',target],timeout=30)
            except Exception:
                pass
        try:
            release_network(network, name)
        except Exception:
            pass


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--go')
    parser.add_argument('--python-image',default='python:3.12-slim')
    parser.add_argument('--postgres-image',default='pgvector/pgvector:pg16')
    parser.add_argument('--prepared',type=Path)
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--tests',nargs='+',default=DEFAULT_TESTS)
    args=parser.parse_args()
    if not args.prepared and not args.go: parser.error('--go required for preparation')
    prepared=json.loads(args.prepared.read_text()) if args.prepared else prepare(args)
    if not args.prepare_only and not execute(prepared,args.tests): raise SystemExit(1)


if __name__=='__main__': main()
