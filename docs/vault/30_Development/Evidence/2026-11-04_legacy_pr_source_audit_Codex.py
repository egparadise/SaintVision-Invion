"""Read-only Git audit recorder. No product, Git ref, PR, or live state mutation."""
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path.cwd()
EVIDENCE = ROOT / 'docs/vault/30_Development/Evidence/2026-11-04_legacy_pr_source_audit_Codex.json'
KST = datetime.timezone(datetime.timedelta(hours=9))


def record(audit, args):
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    audit['commands'].append({'argv': args, 'exitCode': result.returncode,
                              'stdout': result.stdout, 'stderr': result.stderr,
                              'atKst': datetime.datetime.now(KST).isoformat()})
    return result


if __name__ == '__main__':
    if '--verdicts' in sys.argv:
        audit = json.loads(EVIDENCE.read_text(encoding='utf-8'))
        definitions = {
            390: ('superseded', 'Historical two-option recovery plan is overtaken by Card295 offline recovery and Card296 isolated bootstrap; do not execute its old live commands.', None, ['tools/lan_pilot.py::_validate_expired_historical_leaf', 'tools/lan_pilot.py::_load_offline_authorization', 'deploy/lan/worker_leaf_rotation.py', 'deploy/lan/prepare-pilot-database.sh', 'tests/test_lan_leaf_rotation.py']),
            306: ('superseded', 'The nine caller questions are answered in the later internal caller, authenticated receipts, isolation/epoch checks, atomic completion and product worker composition; physical builder acceptance remains separate.', None, ['services/control-plane/src/inv/build_execution.py::BuildExecutionService', 'services/control-plane/src/inv/build_product_runtime.py::configured_tenant_product_runtime', 'services/control-plane/src/inv/worker.py::consume_builds', 'tests/core/test_build_product_runtime.py', 'tests/integration/test_build_product_runtime_real_pg.py']),
            265: ('superseded', 'Original design-only files are absent; later strict BuildRequest/Plan/Receipt, BuildKit governance and measured single-GPU allocation implement its direction. This is not a claim that every proposed design feature or hardware acceptance is complete.', None, ['contracts/v1alpha1/core.schema.json', 'services/control-plane/src/inv/build_governance.py', 'services/control-plane/src/inv/build_adapter.py', 'services/control-plane/src/inv/gpu.py::current_single_gpu_allocation', 'tests/core/test_single_gpu_contract.py', 'tests/core/test_build_governance.py']),
            194: ('superseded', 'Canonical denials call the shared recorder exactly once; the later shared denial_recorder also serves the kernel. audit_action and its tests are identical blobs; focused current tests pass.', None, ['src/saintvision/api/app.py::_record_denial', 'src/saintvision/api/problem.py::install_canonical_problem_handler', 'src/saintvision/api/denial_recorder.py::record_denial', 'services/control-plane/src/inv/app.py', 'tests/core/test_canonical_denial_audit.py', 'tests/integration/test_canonical_denial_audit_real_pg.py']),
            148: ('conflicts-with-later-architecture', 'Card46 historical result and later clean-base legacy staircase are preserved; inherited semaphore lifecycle and hosted-wave candidate arm were explicitly excluded by Card47. Do not merge the stack.', None, ['docs/vault/30_Development/S05 bounded admission 후속 결정 제안.md::sections 6-7', 'tools/run_s05_legacy_staircase.py', 'tests/test_s05_legacy_staircase.py', '.github/workflows/s05-legacy-staircase.yml']),
            145: ('conflicts-with-later-architecture', 'Decision prose is preserved and revised in the later canonical S05 decision; its inherited semaphore and candidate-wave stack was explicitly excluded by Card47.', None, ['docs/vault/30_Development/S05 bounded admission 후속 결정 제안.md::sections 6-7', 'tools/run_s05_legacy_staircase.py']),
            141: ('conflicts-with-later-architecture', 'Hosted candidate-wave implementation depends on the rejected semaphore tree; later clean-base legacy-only staircase replaces the accepted measurement need.', None, ['docs/vault/30_Development/S05 bounded admission 후속 결정 제안.md::sections 6-7', 'tools/run_s05_legacy_staircase.py', 'tests/test_s05_legacy_staircase.py']),
            140: ('superseded', 'Later ObjectStore SPI, shared S3Client, immutable provider/locator migration, verified provider-byte reads and provider-bound checkpoint tests implement the design; historical design-only files need not be restored.', None, ['services/control-plane/src/inv/object_store.py::ObjectStore', 'services/control-plane/src/inv/s3_object_store.py::S3Objects', 'services/control-plane/src/inv/s3_client.py', 'tools/verify_storage_roundtrip.py::S3Client', 'migrations/versions/0048_object_store_locator.py', 'services/control-plane/src/inv/result_view.py', 'tests/core/test_s3_object_store.py', 'tests/core/test_object_store_provider_binding.py', 'tests/integration/test_s3_object_store_postgres.py']),
            119: ('still-needed-source-delta', 'S07 five-node read-only dry-run adapter is genuinely absent. Current spec is proposed-review and explicitly says this CLI is not implemented; this is a pending feature/harness delta, not a regression or physical acceptance.', {'ownerRecommendation': 'Codex; Claude independent review', 'scope': ['tools/measure_s07_recovery.py', 'tools/five_node_lab_preflight.py', 'tests/core/test_s07_recovery_measurement.py', 'tests/integration/test_five_node_lab_preflight.py'], 'minimalAction': 'Forward-port the read-only adapter from 4d322156, retain current synthetic path and shared strict inventory; no disruption, live DB mutation or acceptance promotion.', 'reproduction': 'Recorded parser-only invocation exits 2; required synthetic knobs are still mandatory and --adapter/--inventory/--dry-run are unsupported.'}, ['tools/measure_s07_recovery.py::parser', 'tools/five_node_lab_preflight.py::write_registration_mtls_preflight', 'docs/vault/30_Development/S07 5노드 실 Node adapter 사양.md::section 1']),
            118: ('still-needed-source-delta', 'All three source/test files for the unified HTTP+PG approval/outbox runner are absent. Later operational collectors and individual regressions do not replace this four-case executable report.', {'ownerRecommendation': 'Codex; Claude independent review', 'scope': ['tools/run_s04_db_evidence.py', 'tests/core/test_s04_db_runner.py', 'tests/integration/s04_db_runner_case.py'], 'minimalAction': 'Port only these three files after adapting to current fixture and schema; use a fresh disposable PostgreSQL instance and rerun the four cases. Do not import old green JSON/XML as current evidence.', 'reproduction': 'git cat-file -e <candidate>:<each of the three files> exits 128; the branch versions exist and identify the four cases.'}, ['tests/integration/test_approvals.py', 'tests/integration/test_control_api.py', 'services/control-plane/src/inv/outbox.py', 'tools/collect_s04_kernel_approval_evidence.py', 'tools/collect_s04_s08_operational_evidence.py']),
            115: ('conflicts-with-later-architecture', 'The process-local project semaphore and root-transaction permit lifecycle were deliberately not merged after the no-degrade-through-50 decision. Their absence is intentional.', None, ['docs/vault/30_Development/S05 bounded admission 후속 결정 제안.md::sections 6-7', 'services/control-plane/src/inv/db.py', 'services/control-plane/src/inv/placement.py']),
            35: ('superseded', 'Envelope/WorkloadSpec rejection tests, requirements, gate instructions and several integration tests are identical blobs. Provisioning refusal and catalogue behavior persist with later narrower exception handling and integrated UI.', None, ['tests/core/test_evidence_envelope_serving.py', 'tests/core/test_workload_spec_input_anchors.py', 'tests/core/test_serving_anchors.py', 'tools/provision_credentials.py::validate_manifest', 'tests/core/test_credential_provision_cli.py', 'apps/web/src/features/desktop/InvFileExplorer.tsx', 'tests/integration/test_desktop_browser.py', 'tests/integration/test_studio_browser.py']),
            14: ('conflicts-with-later-architecture', 'Eval executor/tests and numerous kernel modules are identical blobs, and the all-error gate fix persists. Experimental handoff/gateway, automatic epoch seeding and renumbered migration graph conflict with ADR050-052/064-065; later explicit binding/current-authority routes replace them.', None, ['src/saintvision/services/eval_execution.py', 'tests/test_eval_execution.py', 'src/saintvision/services/evaluation.py::gate_passed', 'tools/node_dependent_tests.py', 'services/control-plane/src/inv/business_handoff.py', 'services/control-plane/src/inv/workspace_api.py', 'migrations/versions/0021_business_kernel.py', 'docs/vault/30_Development/Codex 업무 binding과 실행 커널 연결 계약.md::ADR-051', 'docs/vault/40_Governance/설계 충돌 정정 및 ADR.md::ADR-050-052,064-065']),
        }
        compact = {key: audit[key] for key in ('schemaVersion', 'taskId', 'dispatchId', 'runId', 'observedAt', 'sourceSha', 'candidateSha', 'worktree', 'branch', 'snapshotSha256', 'executor', 'reviewer', 'productFilesChanged', 'environment')}
        compact.update({'meaning': 'Exact-head source disposition only. No ancestry, local test, old CI or design document is operational acceptance. No PR state changed.', 'excludedPrNumbers': [401, 402, 406], 'counts': {'reviewed': 13, 'exactHeadsInIntegration': 0, 'exactHeadsInCandidate': 0, 'wholeCommitPatchEquivalent': 0, 'superseded': 6, 'conflictsWithLaterArchitecture': 5, 'stillNeededSourceDelta': 2}, 'rawEvidence': EVIDENCE.name, 'pullRequests': []})
        compact['validation'] = [{'argv': command['argv'], 'exitCode': command['exitCode'], 'atKst': command['atKst']} for command in audit['commands'] if any(name in command['argv'] for name in ('pytest', 'tools/check_docs.py', 'tools/check_ontology.py', 'tools/sync_obsidian.py'))]
        compact['localTests'] = {'directSourceSha': audit['sourceSha'], 'passed': 68, 'skipped': 13, 'failed': 0, 'errors': 0, 'deselected': 0, 'skipReason': 'INV_TEST_ADMIN_DSN absent for 13 eval-execution PostgreSQL cases'}
        compact['ci'] = {'newReportCi': 'not-run', 'historicalCiCountsAsCurrentCandidateEvidence': False}
        compact['operationalAcceptance'] = 'not-run'
        for pr in audit['pullRequests']:
            verdict, reason, delta, paths = definitions[pr['number']]
            row = {key: pr[key] for key in ('number', 'title', 'headRefName', 'headRefOid', 'verifiedRemoteHead', 'baseRefName', 'mergeBase')}
            row.update({'inIntegration': pr['inIntegration'] == 0, 'inCandidate': pr['inCandidate'] == 0, 'wholeCommitPatchEquivalent': False, 'uniqueNonMergeCommits': pr['uniqueCommits'].splitlines(), 'verdict': verdict, 'reason': reason, 'missingDelta': delta, 'sourceEvidence': [{'sha': audit['candidateSha'], 'pathAndSymbol': path} for path in paths], 'blobComparisonCounts': {state: sum(p['state'] == state for p in pr['pathComparisons']) for state in ('same-blob', 'different-blob', 'absent-from-candidate')}})
            compact['pullRequests'].append(row)
        path = EVIDENCE.with_name(EVIDENCE.stem + '.inventory.json')
        path.write_text(json.dumps(compact, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(path)
        sys.exit(0)
    if '--semantic' in sys.argv:
        audit = json.loads(EVIDENCE.read_text(encoding='utf-8'))
        c = audit['candidateSha']
        commands = [
            ['git', 'status', '--porcelain'],
            ['git', 'diff', '--name-only', audit['sourceSha'], c],
            ['git', 'show', '--format=', 'c5d03f4a', '--', 'src/saintvision/api/app.py', 'src/saintvision/api/problem.py'],
            ['git', 'diff', '39d8c238', c, '--', 'tools/provision_credentials.py', 'tests/core/test_credential_provision_cli.py', 'tests/core/test_serving_anchors.py'],
            ['git', 'grep', '-n', '-E', 'def _record_denial|denial_recorder.record_denial|install_canonical_problem_handler|def is_audited_denial|on_denial\(', c, '--', 'src/saintvision/api/app.py', 'src/saintvision/api/problem.py', 'src/saintvision/api/denial_recorder.py', 'services/control-plane/src/inv/app.py'],
            ['git', 'grep', '-n', '-E', 'BuildExecutionAdapter\(|build_runtime|PRODUCT_ENABLE_SETTING|CI_REFERENCE_ISOLATION|COMPLETED_EVENT|_require_epoch_agreement|WRITER_KIND', c, '--', 'services/control-plane/src/inv/build_execution.py', 'services/control-plane/src/inv/build_product_runtime.py', 'services/control-plane/src/inv/worker.py'],
            ['git', 'grep', '-n', '-E', 'class ObjectStore|class S3Objects|S3Client|require_object_provider|files.get|X-Content-SHA256', c, '--', 'services/control-plane/src/inv/object_store.py', 'services/control-plane/src/inv/s3_object_store.py', 'services/control-plane/src/inv/result_view.py', 'services/control-plane/src/inv/results.py', 'services/control-plane/src/inv/app.py', 'tools/verify_storage_roundtrip.py'],
            ['git', 'grep', '-n', '-E', 'gpuCount|def current_single_gpu_allocation|GPUAllocation|GPU_FRESHNESS_SECONDS', c, '--', 'services/control-plane/src/inv/gpu.py', 'tests/core/test_single_gpu_contract.py'],
            ['git', 'grep', '-n', '-E', 'NO_DEGRADE_THROUGH_50|mayReplaceCanonicalDecision|semaphoreProductCodeExpected', c, '--', 'tools/run_s05_legacy_staircase.py', 'tests/test_s05_legacy_staircase.py'],
            ['git', 'grep', '-n', '-E', 'fabricObservation|api.locations|api.resolve|api.replicas|signal.aborted', c, '--', 'apps/web/src/features/desktop/InvFileExplorer.tsx'],
            ['git', 'grep', '-n', '-E', 'def gate_passed|total_cases > 0|passed == total_cases|gate_passed\(', c, '--', 'src/saintvision/services/evaluation.py'],
            ['git', 'grep', '-n', '-E', 'def _validate_expired_historical_leaf|def _load_offline_authorization|def prepare_fully_expired|fully-expired-offline|prepare-fully-expired', c, '--', 'tools/lan_pilot.py', 'deploy/lan/worker_leaf_rotation.py'],
            ['git', 'show', c + ':docs/vault/30_Development/Codex 업무 binding과 실행 커널 연결 계약.md'],
            ['git', 'show', c + ':docs/vault/30_Development/S05 bounded admission 후속 결정 제안.md'],
            ['git', 'show', 'c149f8df:tools/run_s04_db_evidence.py'],
            ['git', 'show', 'c149f8df:tests/integration/s04_db_runner_case.py'],
            ['git', 'show', '--format=', '4d322156', '--', 'tools/measure_s07_recovery.py', 'tools/five_node_lab_preflight.py'],
            ['git', 'cat-file', '-e', c + ':tools/run_s04_db_evidence.py'],
            ['git', 'cat-file', '-e', c + ':tests/core/test_s04_db_runner.py'],
            ['git', 'cat-file', '-e', c + ':tests/integration/s04_db_runner_case.py'],
            [sys.executable, '-c', "import runpy; p=runpy.run_path('tools/measure_s07_recovery.py')['parser'](); print(p.format_help()); p.parse_args(['--adapter','five-node-lab','--inventory','synthetic.json','--dry-run','--json-out','unused.json'])"],
        ]
        for args in commands:
            result = record(audit, args)
            print('EXIT', result.returncode, subprocess.list2cmdline(args))
        audit['environment'] = {'os': 'Windows / PowerShell', 'testPython': 'D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe', 'testPythonVersion': '3.14.7', 'inventoryPythonVersion': sys.version, 'testPytestVersion': '9.1.1', 'postgresDsnPresent': False, 'liveNodesUsed': False, 'containersCreated': 0, 'externalMessages': 'Orca coordinator only', 'testEnvironment': {'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1', 'PYTHONPATH': str(ROOT / 'src') + ';' + str(ROOT / 'services/control-plane/src') + ';' + str(ROOT)}}
        EVIDENCE.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        sys.exit(0)
    if '--capture' in sys.argv:
        audit = json.loads(EVIDENCE.read_text(encoding='utf-8'))
        result = record(audit, sys.argv[2:])
        EVIDENCE.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        print('DIRECT EXIT:', result.returncode)
        sys.exit(result.returncode)
    if '--compare' in sys.argv:
        audit = json.loads(EVIDENCE.read_text(encoding='utf-8'))
        for pr in audit['pullRequests']:
            pr['pathComparisons'] = []
            paths = record(audit, ['git', '-c', 'core.quotePath=false', 'diff', '--name-only', audit['candidateSha'] + '...' + pr['headRefOid']]).stdout.splitlines()
            for path in paths:
                old = record(audit, ['git', 'rev-parse', pr['headRefOid'] + ':' + path])
                new = record(audit, ['git', 'rev-parse', audit['candidateSha'] + ':' + path])
                state = 'same-blob' if old.returncode == new.returncode == 0 and old.stdout == new.stdout else 'absent-from-candidate' if new.returncode else 'different-blob'
                pr['pathComparisons'].append({'path': path, 'state': state, 'headBlob': old.stdout.strip() if old.returncode == 0 else None, 'candidateBlob': new.stdout.strip() if new.returncode == 0 else None})
            print(pr['number'], [(p['path'], p['state']) for p in pr['pathComparisons'] if not p['path'].startswith(('docs/', 'ontology/'))])
        EVIDENCE.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        sys.exit(0)
    snapshot = pathlib.Path('D:/Project/SaintVisionI-Invion/supervision-integration-20261104/.work/current-open-pr-inventory.json').read_bytes()
    prs = json.loads(snapshot.decode('utf-16' if snapshot.startswith(b'\xff\xfe') else 'utf-8-sig'))
    audit = {'schemaVersion': 1, 'taskId': 'task_fc87fbcb38e0', 'dispatchId': 'ctx_7cf31e3d629b',
             'runId': 'run_e57ecd84a7bc', 'observedAt': datetime.datetime.now(KST).isoformat(),
             'sourceSha': '03e17c31cf535008d39534aaa80d3ae274bd75cc',
             'candidateSha': 'fe69e300121edefe198a8a495ebc9abb08588667',
             'worktree': str(ROOT), 'branch': 'agent/codex/legacy-pr-audit-20261104',
             'snapshotSha256': hashlib.sha256(snapshot).hexdigest(), 'executor': 'Codex dispatched worker',
             'reviewer': 'coordinator pending', 'productFilesChanged': False, 'commands': [], 'pullRequests': []}
    ids = [390, 306, 265, 194, 148, 145, 141, 140, 119, 118, 115, 35, 14]
    refs = ['refs/heads/' + next(pr for pr in prs if pr['number'] == number)['headRefName'] for number in ids]
    remote = record(audit, ['git', 'ls-remote', '--heads', 'origin', *refs])
    assert remote.returncode == 0, remote.stderr
    heads = {ref: sha for sha, ref in (line.split() for line in remote.stdout.splitlines())}
    for number in ids:
        pr = dict(next(pr for pr in prs if pr['number'] == number))
        head = pr['headRefOid']
        pr['verifiedRemoteHead'] = heads['refs/heads/' + pr['headRefName']]
        assert pr['verifiedRemoteHead'] == head
        for name, args in [
            ('inIntegration', ['merge-base', '--is-ancestor', head, audit['sourceSha']]),
            ('inCandidate', ['merge-base', '--is-ancestor', head, audit['candidateSha']]),
            ('mergeBase', ['merge-base', audit['candidateSha'], head]),
            ('uniqueCommits', ['log', '--no-merges', '--format=%H %s', audit['candidateSha'] + '..' + head]),
            ('cherry', ['cherry', audit['candidateSha'], head]),
            ('uniqueDiffPaths', ['diff', '--name-status', audit['candidateSha'] + '...' + head]),
        ]:
            result = record(audit, ['git', *args])
            pr[name] = result.returncode if name.startswith('in') else result.stdout.strip()
        audit['pullRequests'].append(pr)
        print(number, 'BASE', pr['mergeBase'], '\n', pr['uniqueDiffPaths'], '\nCHERRY', pr['cherry'])
    EVIDENCE.parent.mkdir(exist_ok=True)
    EVIDENCE.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
