"""Public Git/CI/docs/state metadata only; never imports renewal/product code."""
from datetime import datetime, timezone, timedelta
import hashlib
import base64
import json
import os
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = Path.cwd()
REPO = 'egparadise/SaintVision-Invion'
BASE = 'a3c6984fa25c6cf179827e15e4259000e7bd294e'
BRANCH = 'agent/codex/fleet5-current-three-node-renewal-plan-r2-20261108'
SYNC = Path('D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json')


def command(argv):
    result = subprocess.run(argv, capture_output=True)
    assert result.returncode == 0, (argv[:4], result.returncode, result.stderr.decode('utf8', errors='replace')[:500])
    return result.stdout


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=True) + '\n', encoding='utf8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


sha = command(['git', 'rev-parse', 'HEAD']).decode().strip()
assert command(['git', 'branch', '--show-current']).decode().strip() == BRANCH
assert command(['git', 'ls-remote', 'origin', 'refs/heads/' + BRANCH]).decode().split()[0] == sha
assert not command(['git', 'diff', '--name-only'])
assert not command(['git', 'diff', '--cached', '--name-only'])
dispatch = json.loads((HERE / f'ci-dispatch-{sha[:12]}.json').read_text('utf8'))
assert len(dispatch) == 1 and dispatch[0]['workflow'] == 'docs'
entry = dispatch[0]
run = json.loads(command(['gh', 'api', f'repos/{REPO}/actions/runs/{entry["runID"]}']))
jobs = json.loads(command(['gh', 'api', f'repos/{REPO}/actions/runs/{run["id"]}/jobs']))
artifacts = json.loads(command(['gh', 'api', f'repos/{REPO}/actions/runs/{run["id"]}/artifacts']))
assert run['head_sha'] == sha and run['head_branch'] == BRANCH
assert run['event'] == 'workflow_dispatch' and run['run_attempt'] == 1
assert run['display_title'] == entry['correlation'] and run['conclusion'] == 'success'
assert len(jobs['jobs']) == 1 and len(jobs['jobs'][0]['steps']) == 19
assert all(job['conclusion'] == 'success' for job in jobs['jobs'])
assert all(step['conclusion'] == 'success' for job in jobs['jobs'] for step in job['steps'])
write(f'ci-{sha[:12]}-docs-run.json', run)
write(f'ci-{sha[:12]}-docs-jobs.json', jobs)
write(f'ci-{sha[:12]}-docs-artifacts.json', artifacts)
log_pins = []
for job in jobs['jobs']:
    raw = command(['gh', 'api', f'repos/{REPO}/actions/jobs/{job["id"]}/logs', '--allow-escape-sequences'])
    name = f'ci-{sha[:12]}-job-{job["id"]}-raw-base64.json'
    write(name, dict(jobID=job['id'], bytes=len(raw), SHA256=digest(raw), encoding='base64', data=base64.b64encode(raw).decode('ascii')))
    clean = re.sub(r'\x1b\[[0-9;]*m', '', raw.decode('utf8', errors='replace'))
    log_pins.append(dict(path=name, bytes=len(raw), SHA256=digest(raw),
        source='Official exact-head Docs job log',
        consoleResultLines=[line for line in clean.splitlines() if ' passed' in line or 'PASS:' in line]))
for artifact in artifacts['artifacts']:
    assert not artifact['expired'] and artifact.get('digest', '').startswith('sha256:')
    artifact['digestSource'] = 'Official GitHub artifact API'
    if artifact['name'] == 'route-coverage-report':
        raw = command(['gh', 'api', f'repos/{REPO}/actions/artifacts/{artifact["id"]}/zip'])
        assert artifact['digest'] == 'sha256:' + digest(raw)
        name = f'ci-{sha[:12]}-route-coverage-report.zip'
        (HERE / name).write_bytes(raw)
        artifact['downloadedZIP'] = name
        artifact['downloadedZIPVerifiedSHA256'] = digest(raw)
protected = json.loads((HERE / 'protected-trees.json').read_text('utf8'))
for path, pin in protected['paths'].items():
    current = command(['git', 'rev-parse', sha + ':' + path]).decode().strip()
    assert current == pin['baseGitObject'] and not command(['git', 'diff', BASE, sha, '--', path]), path
    pin['candidateGitObject'] = current
inputs = json.loads((HERE / 'new-input-pins.json').read_text('utf8'))
for pin in inputs:
    raw = command(['git', 'show', pin['source'] + ':' + pin['path']])
    assert digest(raw) == pin['SHA256']
    assert raw == command(['git', 'show', sha + ':' + (HERE / pin['copy']).relative_to(ROOT).as_posix()])
sources = json.loads((HERE / 'source-contract-map.json').read_text('utf8'))
for pin in sources:
    raw = command(['git', 'show', pin['source'] + ':' + pin['path']])
    assert digest(raw) == pin['SHA256']
    if pin['source'] == '03f6ea0a2c6cf83074cfa71850892ba4a1873ae5':
        assert any(item['source'] == pin['source'] and item['path'] == pin['path'] for item in inputs)
    else:
        assert raw == command(['git', 'show', sha + ':' + pin['path']])
manifest = json.loads((HERE / 'operation-manifest.json').read_text('utf8'))
assert manifest['status'] == 'HOLD_MIGRATION_NORMAL_AND_EXPIRED_CONTRACTS_NOT_IMPLEMENTED' and manifest['executable'] is False
assert all(value is None for value in manifest['privateHandlesToBeBoundOnlyByRootLater'].values())
assert all(node['currentChannelGeneration'] is None and node['currentSignedPeerGeneration'] is None and node['operationResult'] == 'NOT_RUN' for node in manifest['nodes'])
at = datetime.now(timezone(timedelta(hours=9))).isoformat()
argv = ['D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe', '-B', 'tools/sync_obsidian.py', '--check']
check = subprocess.run(argv, capture_output=True, env={**os.environ, 'PYTHONUTF8': '1'})
sync = dict(atKST=at, argv=argv, exit=check.returncode, stdout=check.stdout.decode('utf8'), stderr=check.stderr.decode('utf8'))
write('postCI-sync-check.json', sync)
assert check.returncode == 0
before = (HERE / 'sync-state-before.json').read_bytes()
after = SYNC.read_bytes()
assert before == (HERE / 'sync-state-after.json').read_bytes() == after
assert len(before) == 587290 and digest(before) == 'a59e836f1e826231ddfee3a3be5bb247dd4a9b018c24a9d809104e9ef2c5b5e4'
(HERE / 'sync-state-postCI-after.json').write_bytes(after)
changed = command(['git', 'diff', '--name-only', '-z', BASE, sha]).decode('utf8').strip('\0').split('\0')
assert all(path.startswith('docs/vault/30_Development/') for path in changed)
patch = command(['git', 'diff', '--binary', BASE, sha])
(HERE / f'plan-diff-{sha[:12]}.patch').write_bytes(patch)
gates = json.loads((HERE / 'local-gates.json').read_text('utf8'))
assert len(gates) == 6 and all(gate['exit'] == 0 for gate in gates)
report = dict(taskID='task_3e413989dcaa', dispatchID='ctx_80dec9e2eb1e', owner='Actual Orca Codex',
    atKST=datetime.now(timezone(timedelta(hours=9))).isoformat(), planSHA=sha, base=BASE, branch=BRANCH,
    planOnly=True, productImplementation=False, rotationOrCryptoExecution=False, remoteExecution=False,
    currentGenerationsUnknown=True, sourceAcceptance=False, independentReview='One actual Claude required later; not yet performed',
    exactDocs=dict(run=run, jobs=jobs['jobs'], artifacts=artifacts['artifacts'], dispatch=entry, all19StepsSuccess=True, logs=log_pins),
    localMetadataGates=gates, postCISyncCHECK=sync,
    canonicalState=dict(startBytes=len(before), endBytes=len(before), postCIBytes=len(after),
        startSHA256=digest(before), endSHA256=digest(before), postCISHA256=digest(after), fullBytesEqual=True, APPLY=False),
    changedPaths=changed, patchSHA256=digest(patch), protectedTrees=protected, rootInputPins=inputs,
    sourcePins=sources, manifestSHA256=digest((HERE / 'operation-manifest.json').read_bytes()),
    operatingConclusion='R2 PLAN ONLY: budgets/cutoffs/releases unknown HOLD; required serving migration, normal adapter, distinct expired recovery and CA terminal branches remain unimplemented',
    nextImplementation='Root selects required migration/normal code or distinct expired-current-authority contract by real time, proved budgets and authority after actual R2 delta review',
    earliestDefault48hLeafWindow='2026-11-07T07:15:30Z', earliestKnownDeadlineKST='2026-11-08T16:15:30+09:00', earliestAuthorizedActualStart=None,
    nextOwner='Root: verify/publish R2 delta and obtain actual Claude delta review, then assign required implementation branch appropriate to time/budget/authority',
    noFreshProductCIClaim='Docs only; product/crypto/rotation/5PC acceptance NOT_RUN, inherited runtime1efea/API96/UIabb707 remain distinct',
    holds=manifest['holds'], wholeProgramComplete=False,
    commit=dict(SHA=sha, atKST=command(['git', 'show', '-s', '--format=%cI', sha]).decode().strip(), commitExit=0, pushExit=0, hooksDisabled=True),
    receiptPublication='Published tracked plan/docs source at planSHA; exact-head postCI receipt/artifacts remain Root-ready untracked to avoid self-reference')
report['authorFindingDispositions'] = json.loads((HERE / 'finding-dispositions.json').read_text('utf8'))
report['citationCoverage'] = json.loads((HERE / 'citation-coverage.json').read_text('utf8'))
report['requiredMigrationAndDeadlineFork'] = manifest['deadlineFork']
report['futureTaskDAG'] = manifest['taskDependencies']
report['fiveContextSites'] = manifest['clientContexts']
report['newPublicCPClientValidity'] = manifest['publicCPClientValidity']
report['R1EvidenceTreeUnchanged'] = True
report['allProposedNewRuntimeOutputsUnbound'] = True
report['rawCILogScope'] = 'Official exact Docs job bytes base64 encoded with size/SHA; no raw whitespace log Git addition'
write('delivery.json', report)
print(json.dumps(dict(planSHA=sha, Docs=run['id'], jobs=[j['id'] for j in jobs['jobs']], all19Success=True,
    artifacts=[dict(id=a['id'],name=a['name'],digest=a['digest']) for a in artifacts['artifacts']],
    canonical=report['canonicalState'], deliverySHA256=digest((HERE / 'delivery.json').read_bytes()))))
