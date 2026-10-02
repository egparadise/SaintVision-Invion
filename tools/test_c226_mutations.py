#!/usr/bin/env python3
"""
tools/test_c226_mutations.py

Card 226 (ACC-09) Model Studio screen (ModelStudioView.tsx) Mutation Testing Suite.
Verifies that 23 distinct regressions/mutations (M1-M23) across
color contrast, border collisions, status semantics, testid binding,
fail-closed unknown handling, and token inventory are strictly caught and killed
by the test suite (ACC-09 Test 9l, Test 9j-2, and Test 10).

Usage:
    python tools/test_c226_mutations.py
"""

import sys
import os
import atexit
import subprocess
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MS_FILE = os.path.join(REPO_ROOT, 'apps', 'web', 'src', 'features', 'desktop', 'ModelStudioView.tsx')

original_ms = None

if os.path.exists(MS_FILE):
    with open(MS_FILE, 'r', encoding='utf-8') as f:
        original_ms = f.read()

def cleanup():
    if original_ms is not None and os.path.exists(MS_FILE):
        with open(MS_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(original_ms)

atexit.register(cleanup)

MUTANTS = [
    {
        'id': 'M1 (A1)',
        'name': 'ModelStudioView: root section color -> bg-canvas (fg==bg 1:1 collision)',
        'target': "        backgroundColor: 'var(--color-bg-canvas)',\n        color: 'var(--color-text-primary)',",
        'replacement': "        backgroundColor: 'var(--color-bg-canvas)',\n        color: 'var(--color-bg-canvas)',",
        'expected_guard': 'Test 9j-2 (AST guard: 1:1 collision) & Test 9l (DOM check)',
    },
    {
        'id': 'M2 (A2)',
        'name': 'ModelStudioView: REPLICA_STATUS_CONFIG.healthy.bg -> status-online (fg==bg collision)',
        'target': "  healthy: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',",
        'replacement': "  healthy: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-status-online)',",
        'expected_guard': 'Test 9j-2 (AST guard: 1:1 collision) & Test 9l (DOM contrast check)',
    },
    {
        'id': 'M3 (A3)',
        'name': 'ModelStudioView: PLAN_FEASIBILITY_CONFIG.feasible.bg -> text-secondary (text token as bg)',
        'target': "  feasible: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',",
        'replacement': "  feasible: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-text-secondary)',",
        'expected_guard': 'Test 9j-2 (AST guard: text token background)',
    },
    {
        'id': 'M4 (A4)',
        'name': 'ModelStudioView: model-manifest-article border -> bg-surface (border==bg collision)',
        'target': "            backgroundColor: 'var(--color-bg-surface)',\n            borderRadius: '8px',\n            border: '1px solid var(--color-border-subtle)',",
        'replacement': "            backgroundColor: 'var(--color-bg-surface)',\n            borderRadius: '8px',\n            border: '1px solid var(--color-bg-surface)',",
        'expected_guard': 'Test 9j-2 (border==bg collision) & Test 9l',
    },
    {
        'id': 'M5 (B1)',
        'name': 'ModelStudioView: query-model-btn outline ring suppressed with outline: none',
        'target': "            padding: '6px 14px',\n            backgroundColor: 'var(--color-brand-primary-bg)',",
        'replacement': "            outline: 'none',\n            padding: '6px 14px',\n            backgroundColor: 'var(--color-brand-primary-bg)',",
        'expected_guard': 'Test 9l (focus ring suppression assertion)',
    },
    {
        'id': 'M6 (C1)',
        'name': 'ModelStudioView: shard-degradation-badge opacity degraded to 0.4',
        'target': "                              style={{\n                                padding: '2px 6px',",
        'replacement': "                              style={{\n                                opacity: 0.4,\n                                padding: '2px 6px',",
        'expected_guard': 'Test 9l (opacity degradation assertion)',
    },
    {
        'id': 'M7 (D1)',
        'name': 'ModelStudioView: REPLICA_STATUS_CONFIG.healthy.color reverted to legacy literal #10b981',
        'target': "  healthy: {\n    color: 'var(--color-status-online)',",
        'replacement': "  healthy: {\n    color: '#10b981',",
        'expected_guard': 'Test 10 (COLOR_LITERAL_MULTISET_BASELINE ratchet)',
    },
    {
        'id': 'M8 (D2)',
        'name': 'ModelStudioView: PLAN_FEASIBILITY_CONFIG.infeasible.color reverted to legacy literal #ef4444',
        'target': "  infeasible: {\n    color: 'var(--color-status-offline)',",
        'replacement': "  infeasible: {\n    color: '#ef4444',",
        'expected_guard': 'Test 10 (COLOR_LITERAL_MULTISET_BASELINE ratchet)',
    },
    {
        'id': 'M9 (F-R1 replica out-of-contract enum)',
        'name': 'ModelStudioView: REPLICA_STATUS_CONFIG injects out-of-contract enum unhealthy',
        'target': "  repairing: {\n    color: 'var(--color-status-degraded)',",
        'replacement': "  unhealthy: {\n    color: 'var(--color-status-offline)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-offline)',\n    label: '이상',\n  },\n  repairing: {\n    color: 'var(--color-status-degraded)',",
        'expected_guard': 'Test 9l (exact wire contract enum keys assertion for REPLICA_STATUS_CONFIG)',
    },
    {
        'id': 'M10 (F2)',
        'name': 'ModelStudioView: plan infeasible color collapsed to status-online (feasible collision)',
        'target': "  infeasible: {\n    color: 'var(--color-status-offline)',",
        'replacement': "  infeasible: {\n    color: 'var(--color-status-online)',",
        'expected_guard': 'Test 9l (plan state token uniqueness assertion)',
    },
    {
        'id': 'M11 (G1)',
        'name': 'ModelStudioView: shard-degradation-badge text label removed',
        'target': "                              저하 ({healthyReplicas}/2)\n                            </span>",
        'replacement': "                              \n                            </span>",
        'expected_guard': 'Test 9l (degradation badge non-empty text assertion)',
    },
    {
        'id': 'M12 (G2)',
        'name': 'ModelStudioView: plan-feasible-badge text label removed',
        'target': "                  {executionPlan.isFeasible\n                    ? `${planCfg.label} · 점수 ${executionPlan.localityScore}점`\n                    : planCfg.label}",
        'replacement': "                  {''}",
        'expected_guard': 'Test 9l (plan feasible badge non-empty text assertion)',
    },
    {
        'id': 'M13 (E1)',
        'name': 'ModelStudioView: shard-repair-error border swapped to status-online',
        'target': "                border: '1px solid var(--color-status-offline)',",
        'replacement': "                border: '1px solid var(--color-status-online)',",
        'expected_guard': 'Test 9l (repair error alert border token assertion)',
    },
    {
        'id': 'M14 (E2)',
        'name': 'ModelStudioView: unobserved-shards-notice color swapped to bg-surface (invisible text)',
        'target': "            color: 'var(--color-text-secondary)',\n            fontSize: '0.8125rem',",
        'replacement': "            color: 'var(--color-bg-surface)',\n            fontSize: '0.8125rem',",
        'expected_guard': 'Test 9j-2 (1:1 collision between fg and bg)',
    },
    {
        'id': 'M15 (H1)',
        'name': 'ModelStudioView: getReplicaStatusConfig unknown fallback returns healthy config (fail-closed bypass)',
        'target': "  return {\n    color: 'var(--color-status-unknown)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-unknown)',\n    label: `알 수 없음 (${status || 'UNKNOWN'})`,\n  };",
        'replacement': "  return REPLICA_STATUS_CONFIG.healthy;",
        'expected_guard': 'Test 9l (unknown status fail-closed token & label assertion)',
    },
    {
        'id': 'M16 (H2)',
        'name': 'ModelStudioView: query-model-btn inject named color lightgray',
        'target': "            color: 'var(--color-brand-primary-fg)',\n            border: 'none',",
        'replacement': "            color: 'lightgray',\n            border: 'none',",
        'expected_guard': 'Test 9j-2 (named color literal violation) & Test 10',
    },
    {
        'id': 'M17 (Codex F1)',
        'name': 'ModelStudioView: getReplicaStatusConfig uses status in REPLICA_STATUS_CONFIG bypassing prototype keys',
        'target': "export function getReplicaStatusConfig(status?: string | null) {\n  if (status && Object.hasOwn(REPLICA_STATUS_CONFIG, status)) {",
        'replacement': "export function getReplicaStatusConfig(status?: string | null) {\n  if (status && status in REPLICA_STATUS_CONFIG) {",
        'expected_guard': 'Test 9l (prototype key fail-closed own-key defense assertion)',
    },
    {
        'id': 'M18 (Claude Low)',
        'name': 'ModelStudioView: query-model-btn outline ring suppressed with outline: 0',
        'target': "            padding: '6px 14px',\n            backgroundColor: 'var(--color-brand-primary-bg)',",
        'replacement': "            outline: '0',\n            padding: '6px 14px',\n            backgroundColor: 'var(--color-brand-primary-bg)',",
        'expected_guard': 'Test 9l (computed outline-width 0 assertion)',
    },
    {
        'id': 'M19 (F-R1 availability out-of-contract enum)',
        'name': 'ModelStudioView: MODEL_AVAILABILITY_CONFIG injects out-of-contract enum observed',
        'target': "export const MODEL_AVAILABILITY_CONFIG = {\n  unknown: {",
        'replacement': "export const MODEL_AVAILABILITY_CONFIG = {\n  observed: {\n    color: 'var(--color-status-active)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-active)',\n    label: '관측됨',\n  },\n  unknown: {",
        'expected_guard': 'Test 9l (exact wire contract enum keys assertion for MODEL_AVAILABILITY_CONFIG)',
    },
    {
        'id': 'M20 (M1 own-key)',
        'name': 'ModelStudioView: getModelAvailabilityConfig uses availability in MODEL_AVAILABILITY_CONFIG bypassing prototype keys',
        'target': "export function getModelAvailabilityConfig(availability?: string | null) {\n  if (availability && Object.hasOwn(MODEL_AVAILABILITY_CONFIG, availability)) {",
        'replacement': "export function getModelAvailabilityConfig(availability?: string | null) {\n  if (availability && availability in MODEL_AVAILABILITY_CONFIG) {",
        'expected_guard': 'Test 9l (availability prototype key defense assertion)',
    },
    {
        'id': 'M21 (H2 repairing collapse)',
        'name': 'ModelStudioView: replica repairing color collapsed to status-online (healthy collision)',
        'target': "  repairing: {\n    color: 'var(--color-status-degraded)',",
        'replacement': "  repairing: {\n    color: 'var(--color-status-online)',",
        'expected_guard': 'Test 9l (replica repairing uniqueness assertion)',
    },
    {
        'id': 'M22 (H2 missing collapse)',
        'name': 'ModelStudioView: replica missing color collapsed to status-online (healthy collision)',
        'target': "  missing: {\n    color: 'var(--color-status-offline)',",
        'replacement': "  missing: {\n    color: 'var(--color-status-online)',",
        'expected_guard': 'Test 9l (replica missing uniqueness assertion)',
    },
    {
        'id': 'M23 (F-R2 repair outline)',
        'name': 'ModelStudioView: shard repair button outline ring suppressed with outline: none',
        'target': "                                padding: '4px 8px',\n                                fontSize: '0.75rem',",
        'replacement': "                                outline: 'none',\n                                padding: '4px 8px',\n                                fontSize: '0.75rem',",
        'expected_guard': 'Test 9j-2 (AST outline guard) & Test 9l (repair button focus ring assertion)',
    },
]

def run_test_suite():
    cmd = [
        'npx.cmd' if os.name == 'nt' else 'npx',
        'vitest',
        'run',
        'tests/acc09-contrast-tokens.test.tsx',
    ]
    env = os.environ.copy()
    res = subprocess.run(
        cmd,
        cwd=os.path.join(REPO_ROOT, 'apps', 'web'),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace',
        env=env,
        timeout=180,
    )
    return res.returncode, res.stdout, res.stderr

def main():
    print('=' * 80)
    print(' Card 226 (ACC-09): Reproducible Mutant Test Suite (23 Mutants: M1-M23)')
    print(' Target: ModelStudioView.tsx')
    print('=' * 80)

    print('\n[Baseline Check] Testing unmutated code...')
    rc, stdout, stderr = run_test_suite()
    if rc != 0:
        print('[Baseline Check] FAILED! Tests must pass on clean code before mutation testing.')
        print(stdout[-1500:])
        print(stderr[-1500:])
        return 1
    print('[Baseline Check] Clean pass (exit code 0).\n')

    killed_count = 0
    total_mutants = len(MUTANTS)
    results = []

    for i, m in enumerate(MUTANTS, 1):
        mid = m['id']
        mname = m['name']
        target = m['target']
        replacement = m['replacement']

        if target not in original_ms:
            print(f'[{i:02d}/{total_mutants}] {mid}: ERROR - Target snippet not found in ModelStudioView.tsx!')
            results.append((mid, mname, 'ERROR_TARGET_NOT_FOUND', 'Target snippet not found'))
            continue

        mutated_code = original_ms.replace(target, replacement, 1)
        with open(MS_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(mutated_code)

        start_time = time.time()
        test_rc, test_out, test_err = run_test_suite()
        elapsed = time.time() - start_time

        # Restore immediately
        with open(MS_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(original_ms)

        if test_rc != 0:
            killed_count += 1
            reason = 'Unknown failure'
            for line in (test_out + test_err).splitlines():
                if 'AssertionError' in line or 'Error:' in line or 'expected' in line:
                    reason = line.strip()[:100]
                    break
            print(f'[{i:02d}/{total_mutants}] {mid}: KILLED in {elapsed:.1f}s -- {mname}')
            print(f'         Reason: {reason}')
            results.append((mid, mname, 'KILLED', reason))
        else:
            print(f'[{i:02d}/{total_mutants}] {mid}: SURVIVED (MUTANT ESCAPED!) in {elapsed:.1f}s -- {mname}')
            print(f'         Expected to be caught by: {m["expected_guard"]}')
            results.append((mid, mname, 'SURVIVED', 'Test suite returned 0 (did not fail)'))

    print('\n' + '=' * 80)
    print(f' Summary: {killed_count}/{total_mutants} mutants killed ({killed_count/total_mutants*100:.1f}%)')
    print('=' * 80)

    for mid, mname, status, reason in results:
        status_str = '[PASS] ' + status if status == 'KILLED' else '[FAIL] ' + status
        print(f' {status_str:16} | {mname} ({reason})')

    if killed_count == total_mutants:
        print('\nSUCCESS: 100% mutant kill rate achieved. All accessibility invariants strictly hold.')
        return 0
    else:
        print(f'\nFAILURE: {total_mutants - killed_count} mutants survived.')
        return 1

if __name__ == '__main__':
    sys.exit(main())
