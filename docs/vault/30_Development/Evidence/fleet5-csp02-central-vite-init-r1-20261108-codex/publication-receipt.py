"""Post-CI public metadata/data receipt only; no product execution on Main."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = 'egparadise/SaintVision-Invion'
BASE = 'cc6076254d5b8f54804081a8b1994d76d86cf81a'
BACKEND = '96afd799d49717fd40e4ddabd538d82accbe1958'
SYNC = Path('D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json')


def command(argv):
    result = subprocess.run(argv, capture_output=True)
    assert result.returncode == 0, (argv[:3], result.stderr.decode('utf8', errors='replace')[:1000])
    return result.stdout


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=True) + '\n', encoding='utf8')


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


sha = command(['git', 'rev-parse', 'HEAD']).decode().strip()
branch = command(['git', 'branch', '--show-current']).decode().strip()
assert command(['git', 'ls-remote', 'origin', 'refs/heads/' + branch]).decode().split()[0] == sha
assert not command(['git', 'diff', '--name-only'])
dispatch = json.loads((HERE / f'ci-dispatch-{sha[:12]}.json').read_text('utf8'))
lanes = []
for entry in dispatch:
    prefix = f'ci-{sha[:12]}-{entry["workflow"]}'
    run = json.loads(command(['gh', 'api', f'repos/{REPO}/actions/runs/{entry["runID"]}']))
    jobs = json.loads(command(['gh', 'api', '-X', 'GET', f'repos/{REPO}/actions/runs/{run["id"]}/jobs', '-f', 'per_page=100']))
    artifacts = json.loads(command(['gh', 'api', f'repos/{REPO}/actions/runs/{run["id"]}/artifacts']))
    assert run['head_sha'] == sha and run['head_branch'] == branch
    assert run['event'] == 'workflow_dispatch' and run['run_attempt'] == 1
    assert run['display_title'] == entry['correlation'] and run['conclusion'] == 'success'
    assert all(j['conclusion'] == 'success' for j in jobs['jobs'])
    assert all(s['conclusion'] == 'success' for j in jobs['jobs'] for s in j['steps'])
    if entry['workflow'] == 'docs':
        assert len(jobs['jobs']) == 1 and len(jobs['jobs'][0]['steps']) == 19
    if entry['workflow'] == 'frontend':
        job = next(job for job in jobs['jobs'] if job['name'] == 'frontend')
        steps = {step['name']: step['number'] for step in job['steps']}
        direct = steps['Boot clean direct vite.js main config in real browser']
        assert steps['Install dependencies'] < direct < min(steps[name] for name in
            ['Run ESLint', 'Run Vitest Unit Tests', 'TypeScript Check & Production Build'])
    write(prefix + '-run.json', run)
    write(prefix + '-jobs.json', jobs)
    write(prefix + '-artifacts.json', artifacts)
    lane = dict(workflow=entry['workflow'], runID=run['id'], sourceSHA=sha, ref=branch,
                correlation=entry['correlation'], event=run['event'], attempt=run['run_attempt'],
                conclusion=run['conclusion'], url=run['html_url'],
                jobs=[dict(id=j['id'], name=j['name'], conclusion=j['conclusion'],
                           steps=j['steps']) for j in jobs['jobs']], artifacts=artifacts['artifacts'])
    for job in jobs['jobs']:
        log_path = HERE / f'ci-{sha[:12]}-job-{job["id"]}.log'
        with log_path.open('wb') as handle:
            result = subprocess.run(['gh', 'api', f'repos/{REPO}/actions/jobs/{job["id"]}/logs', '--allow-escape-sequences'], stdout=handle, stderr=subprocess.PIPE)
        assert result.returncode == 0
        text = re.sub(r'\x1b\[[0-9;]*m', '', log_path.read_text('utf8'))
        if job['name'] == 'frontend':
            summaries = [line for line in text.splitlines() if re.search(r'\b(?:Test Files|Tests)\s+\d+ passed', line)]
            assert len(summaries) == 2, summaries
            counts = [re.search(r'(\d+) passed\s+\((\d+)\)', line) for line in summaries]
            assert all(m and m[1] == m[2] for m in counts), summaries
            lane['vitest'] = dict(filesPassed=int(counts[0][1]), passed=int(counts[1][1]),
                                  failed=0, errors=0, skipped=0, deselected=0,
                                  rawSummaryLines=summaries, source='official job console summary; all collected tests passed')
        if job['name'] == 'accessibility-e2e':
            summaries = [json.loads(line[line.index('{'):]) for line in text.splitlines()
                         if '"exitCode":' in line and '"tests":' in line]
            assert len(summaries) == 1 and summaries[0]['exitCode'] == 0, summaries
            assert summaries[0]['tests'] == {'failure': 0, 'error': 0, 'skipped': 0, 'passed': 6}, summaries
            lane['actualBrowserCaseCounts'] = summaries[0]
        if job['name'].startswith('Portal Container'):
            lane['hardenedRuntimeSmokeExecuted'] = True
            lane['imageIdentityConsole'] = [line for line in text.splitlines()
                                            if 'Built Image ID (lane-internal' in line or re.search(r'"(?:codeSha|imageId|tarSha256|buildRunId)"', line)]
            lane['portalRelease'] = {
                key: re.findall(pattern, text)[-1] for key, pattern in {
                    'codeSha': r'"codeSha": "([0-9a-f]{40})"',
                    'imageId': r'"imageId": "(sha256:[0-9a-f]{64})"',
                    'tarSha256': r'"tarSha256": "([0-9a-f]{64})"',
                    'buildRunId': r'"buildRunId": "(\d+)"',
                }.items()
            }
            assert lane['portalRelease']['codeSha'] == sha
            assert lane['portalRelease']['buildRunId'] == str(run['id'])
    for artifact in artifacts['artifacts']:
        if artifact['name'] not in {'saintvision-portal-strict-csp-evidence', 'saintvision-web-dist', 'route-coverage-report', 'saintvision-direct-vite-startup-evidence'} and not artifact['name'].startswith('s11-ac11-accessibility-'):
            continue
        archive = HERE / f'ci-{sha[:12]}-{artifact["name"]}.zip'
        with archive.open('wb') as handle:
            result = subprocess.run(['gh', 'api', f'repos/{REPO}/actions/artifacts/{artifact["id"]}/zip'], stdout=handle, stderr=subprocess.PIPE)
        assert result.returncode == 0
        assert 'sha256:' + file_hash(archive) == artifact['digest']
        artifact['downloadedZIPVerifiedSHA256'] = file_hash(archive)
        with zipfile.ZipFile(archive) as zipped:
            if artifact['name'] == 'saintvision-portal-strict-csp-evidence':
                report = json.loads(zipped.read('artifacts/portal-strict-csp/result.json'))
                assert report['bootPassed'] and report['sandbox'] and report['rootChildren'] > 0
                assert not report['pageErrors'] and not report['requestFailures'] and not report['cspErrors']
                assert not report['bundledAjvCompilerModules']
                assert report['negativeControl'] == {'functionBlocked': True, 'evalBlocked': True}
                assert set(report['requestMethods']) == {'GET'}
                manifest = json.loads(zipped.read('apps/web/src/contracts/node-certificate-validator.manifest.json'))
                code = zipped.read('apps/web/src/contracts/node-certificate-validator.mjs')
                assert hashlib.sha256(code).hexdigest() == manifest['validatorSHA256']
                assert file_hash(Path('contracts/v1alpha1/core.schema.json')) == manifest['schemaSHA256']
                assert file_hash(Path('apps/web/package-lock.json')) == manifest['lockSHA256']
                assert file_hash(Path('apps/web/scripts/node-certificate-validator.mjs')) == manifest['generatorSHA256']
                lock = json.loads(Path('apps/web/package-lock.json').read_text('utf8'))
                assert manifest['esbuild'] == lock['packages']['node_modules/esbuild']['version']
                assert manifest['format'] == 'esm' and manifest['selfContained'] is True
                assert all('/ajv/dist/' not in row['path'] or '/ajv/dist/runtime/' in row['path']
                           for row in manifest['runtimeInputs'])
                write(f'ci-{sha[:12]}-strict-csp-result.json', report)
                write(f'ci-{sha[:12]}-validator-manifest.json', manifest)
                lane['strictCSPBrowser'] = report
                lane['standaloneValidatorManifest'] = manifest
            elif artifact['name'] == 'saintvision-web-dist':
                lane['distFilesSHA256'] = {name: hashlib.sha256(zipped.read(name)).hexdigest()
                                          for name in zipped.namelist() if not name.endswith('/')}
            elif artifact['name'].startswith('s11-ac11-accessibility-'):
                report = json.loads(zipped.read('s11-ac11-accessibility-e2e.json'))
                assert report['sourceHeadSha'] == sha and report['sourceRunId'] == str(run['id'])
                assert report['cleanCheckout'] is True and report['acceptanceClaim'] is False
                assert report['environment']['credentialsRequired'] is False
                assert report['environment']['physicalFiveNodeComparable'] is False
                assert report['environment']['frontendTransport'] == 'vite-dev-server-with-browser-node-fixture'
                assert len(report['payload']['journeyIds']) == 5
                assert report['payload']['browserPhysicalCaseCount'] == 6
                assert len(report['payload']['invariantIds']) == 9
                rows = {row['metric']: row for row in report['payload']['observations']}
                assert set(rows) == {'canonicalJourneyFailureCount', 'desktopInvariantFailureCount',
                                     'contrastFailureCount', 'keyboardFailureCount', 'manualAcceptanceMissingCount'}
                assert all(row['failureCount'] == (1 if key == 'manualAcceptanceMissingCount' else 0)
                           and row['skipCount'] == 0 for key, row in rows.items()), rows
                # Unchanged fail-closed normalizer keeps the actual human-device gate.
                assert report['verdict'] == 'MEASURED_FAIL'
                xml = ET.fromstring(zipped.read('s11-ac11-accessibility-e2e.xml'))
                assert xml.attrib['tests'] == '5' and xml.attrib['failures'] == '1'
                assert xml.attrib['errors'] == '0' and xml.attrib['skipped'] == '0'
                lane['redactedAC11Report'] = report
                lane['normalizedCriterionCounts'] = dict(tests=5, passed=4, failures=1, errors=0, skipped=0,
                    reason='Only manualAcceptanceMissingCount remains1; all automated measurements pass; no real-device acceptance claim')
                write(f'ci-{sha[:12]}-ac11-redacted-report.json', report)
            elif artifact['name'] == 'saintvision-direct-vite-startup-evidence':
                report = json.loads(zipped.read('result.json'))
                assert report['sourceSHA'] == sha and report['mainConfig'] == 'apps/web/vite.config.ts'
                assert report['mainConfigSHA256'] == file_hash(Path('apps/web/vite.config.ts'))
                assert report['npmLifecycleUsed'] is False and report['deletedFiles'] == []
                assert report['missingBefore'] and all(report['missingBefore'].values())
                assert report['bootPassed'] and report['sandbox'] and report['rootChildren'] > 0
                assert not report['pageErrors'] and not report['requestFailures']
                assert set(report['requestMethods']) == {'GET'}
                assert report['validatorModuleResponses'] and all(row['status'] == 200 for row in report['validatorModuleResponses'])
                assert report['command'][1:4] == ['node_modules/vite/bin/vite.js', '--config', 'vite.config.ts']
                assert 'npm' not in report['command'] and report['ownedChildExitCode'] is not None
                lane['cleanDirectMainConfigBrowser'] = report
                lane['directProofBeforeNpmGenerationHooks'] = True
                write(f'ci-{sha[:12]}-clean-direct-result.json', report)
    lanes.append(lane)

frontend = next(lane for lane in lanes if lane['workflow'] == 'frontend')
ac11 = next(lane for lane in lanes if lane['workflow'] == 'ac11-accessibility-e2e')
assert ac11['actualBrowserCaseCounts']['tests']['passed'] == 6
assert 'redactedAC11Report' in ac11
assert frontend['distFilesSHA256'] == frontend['strictCSPBrowser']['distSHA256']
assert frontend['cleanDirectMainConfigBrowser']['manifest'] == frontend['standaloneValidatorManifest']
assert frontend['cleanDirectMainConfigBrowser']['generatedAfter']['apps/web/src/contracts/node-certificate-validator.mjs'] == frontend['standaloneValidatorManifest']['validatorSHA256']
protected = json.loads((HERE / 'protected-components.json').read_text('utf8'))
for path, pin in protected['paths'].items():
    assert command(['git', 'rev-parse', sha + ':' + path]).decode().strip() == pin['baseObject']
    assert not command(['git', 'diff', BASE, sha, '--', path])
old = command(['git', 'show', BASE + ':apps/web/src/shared/api/nodeCertificateObservation.ts'])
new = command(['git', 'show', sha + ':apps/web/src/shared/api/nodeCertificateObservation.ts'])
assert old[old.index(b'const renewalWindowMillis'):] == new[new.index(b'const renewalWindowMillis'):]
backend_semantics = command(['git', 'show', BACKEND + ':apps/web/src/shared/api/nodeCertificateObservation.ts'])
assert backend_semantics[backend_semantics.index(b'const renewalWindowMillis'):] == new[new.index(b'const renewalWindowMillis'):]
sql = Path('services/control-plane/src/inv/migrations/0068_first_workspace_intent.sql')
assert file_hash(sql) == '8b79f55289661d7590dbe24e60d60d319360e7fcaf35454fe21c722fe11905d3'
patch = command(['git', 'diff', '--binary', BASE, sha])
(HERE / f'source-diff-{sha[:12]}.patch').write_bytes(patch)
listing = command(['git', 'ls-tree', '-r', sha, '--', 'src', 'services', 'migrations', 'contracts', 'packages', 'deploy', 'tests', 'apps/studio', '.github/workflows/ac11-accessibility-e2e.yml', 'tools/collect_ac11_accessibility_e2e.py', 'tools/run_real_browser_acceptance.py'])
before = (HERE / 'sync-state-before.json').read_bytes()
after = SYNC.read_bytes()
assert before == after == (HERE / 'sync-state-final-after.json').read_bytes()
gates = json.loads((HERE / f'local-gates-final-{sha[:12]}.json').read_text('utf8'))
assert len(gates) == 8 and all(gate['exit'] == 0 for gate in gates)
report = dict(task='CR-CSP-02 central main-config initialization', owner='Codex', atKST=datetime.now(timezone(timedelta(hours=9))).isoformat(),
              sourceSHA=sha, branch=branch, deliveryBase=BASE, backendSource=BACKEND,
              remoteMatches=True, trackedClean=True, freshWorkflows=lanes,
              changedPaths=command(['git', 'diff', '--name-only', BASE, sha]).decode('utf8').splitlines(),
              patchSHA256=hashlib.sha256(patch).hexdigest(),
              protectedRecursiveListingSHA256=hashlib.sha256(listing).hexdigest(),
              protectedComponents=protected['paths'], SQL0068SHA256=file_hash(sql),
              semanticValidatorTailByteIdentical=True, inheritedOnly={'backendCoreSource': BACKEND,
                  'frontend905': '42368189302 is historical evidence only, not a new-head run',
                  'backendOrCoreRerun': False},
              canonicalState=dict(bytes=len(before), SHA256=hashlib.sha256(before).hexdigest(),
                                  fullBytesEqual=True, checkOnly=True, apply=False),
              localGates=gates,
              mainProductExecution=False, actualPC3BrowserAcceptance=False, actualUsersVotesRuns=False,
              independentReview='Pending one actual Claude started by Root after this worker settles/exits/releases',
              nextOwner='Root: verify exact artifacts, actual Claude review, then controlled same-CSP PC3 deployment/browser/API check',
              remainingGates=['actual PC3 strict-CSP browser/login/no-blink/resource verification',
                              'two real distinct nonrequester approvers', 'requester enqueue and genuine Run/output',
                              'all5/GPU/storage/renewal/reconnect/reboot'],
              holds='Original19HOLD/discharges0/runtimeB0/A1-A16/H1-H7/H3EA/RDNULL_HOLD/raw7UNREGISTERED/A01-A40NOT_RUN',
              receiptPublication='Post-CI data is untracked and Root-ready; tracked source/docs are published at sourceSHA; no self-referential final-SHA commit claim')
report['baselineCC607DirectFailure'] = json.loads((HERE / 'baseline-public-repro-receipt.json').read_text('utf8'))
report['priorActualFailures'] = []
for pin in json.loads((HERE / 'inherited-failure-pins.json').read_text('utf8')):
    data = command(['git', 'show', pin['source'] + ':' + pin['path']])
    assert hashlib.sha256(data).hexdigest() == pin['SHA256']
    report['priorActualFailures'].append(dict(pin=pin, receipt=json.loads(data)))
report['inheritedSoundR1'] = dict(source='63f3eeb661c565d864e14c2395f68c6715d109c0',
    verdict=json.loads((HERE / 'r2-review.json').read_text('utf8'))['verdict'],
    productionCorrectionSoundInherited=True, newReview='Root-owned pending actual bounded delta review')
report['newRegression'] = dict(priorCasesRetained=15, newHostedCleanDirectMainConfigBrowserCase=1,
    SourceTextModuleActualESM=True, stringsAndWasmGenerationDisabled=True,
    directViteBrowserFixtureGeneratesSameCanonicalESM=True, AC11WorkflowNormalizerAssertionsTimeoutUnchanged=True)
report['dispatchReceipts'] = dispatch
report['semanticTailComparisonBases'] = [BASE, BACKEND]
report['gitCommits'] = [dict(sourceSHA=commit,
    KST=command(['git', 'show', '-s', '--format=%cI', commit]).decode().strip(),
    subject=command(['git', 'show', '-s', '--format=%s', commit]).decode().strip(), commitExit=0, pushExit=0,
    setupHooksDisabled=True) for commit in command(['git', 'rev-list', '--reverse', BASE + '..' + sha]).decode().splitlines()]
report['inheritedOnly']['backendCoreRuns'] = []
for run_id in [42378656486, 42374998823]:
    inherited = json.loads(command(['gh', 'api', f'repos/{REPO}/actions/runs/{run_id}']))
    assert inherited['head_sha'] == BACKEND and inherited['conclusion'] == 'success'
    report['inheritedOnly']['backendCoreRuns'].append({key: inherited[key] for key in
        ['id', 'head_sha', 'head_branch', 'event', 'run_attempt', 'conclusion', 'html_url']})
report['publicInputPins'] = json.loads((HERE / 'public-input-pins.json').read_text('utf8'))
for pin in report['publicInputPins']:
    for key, hash_key in [('path', 'SHA256')] + ([('rawPath', 'rawSHA256')] if 'rawPath' in pin else []):
        assert hashlib.sha256(command(['git', 'show', sha + ':' + str((HERE / pin[key]).relative_to(Path.cwd())).replace('\\', '/')])).hexdigest() == pin[hash_key]
write('delivery.json', report)
print(json.dumps(dict(sourceSHA=sha, workflows=[dict(workflow=x['workflow'], runID=x['runID'],
                     jobs=[j['id'] for j in x['jobs']], artifacts=[a['id'] for a in x['artifacts']]) for x in lanes],
                     tests=frontend['vitest'], canonicalState=report['canonicalState'], report=str(HERE / 'delivery.json'))))
