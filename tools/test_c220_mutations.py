#!/usr/bin/env python3
"""
tools/test_c220_mutations.py

Card 220 (ACC-09) Release Candidate screen (ReleaseCandidateView.tsx) Mutation Testing Suite.
Verifies that 16 distinct regressions/mutations (M1-M16) across
color contrast, border collisions, status semantics, testid binding,
and fail-closed multiset inventory are strictly caught and killed by the test suite
(ACC-09 Test 9k, Test 9j-2 / Test 9k-2, and Test 10).

Usage:
    python tools/test_c220_mutations.py
"""

import sys
import os
import atexit
import subprocess
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RC_FILE = os.path.join(REPO_ROOT, 'apps', 'web', 'src', 'features', 'release', 'ReleaseCandidateView.tsx')

original_rc = None

if os.path.exists(RC_FILE):
    with open(RC_FILE, 'r', encoding='utf-8') as f:
        original_rc = f.read()

def cleanup():
    if original_rc is not None and os.path.exists(RC_FILE):
        with open(RC_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(original_rc)

atexit.register(cleanup)

MUTANTS = [
    {
        'id': 'M1 (A1)',
        'name': 'ReleaseCandidateView: notice banner bg -> text-secondary (fg==bg collision)',
        'target': "        style={{\n          padding: '8px 16px',\n          backgroundColor: 'var(--color-bg-subtle)',\n          border: '1px solid var(--color-border-subtle)',\n          borderRadius: '6px',\n          color: 'var(--color-text-secondary)',",
        'replacement': "        style={{\n          padding: '8px 16px',\n          backgroundColor: 'var(--color-text-secondary)',\n          border: '1px solid var(--color-border-subtle)',\n          borderRadius: '6px',\n          color: 'var(--color-text-secondary)',",
        'expected_guard': 'Test 9k / Test 9j-2 (1:1 collision between bg and fg)',
    },
    {
        'id': 'M2 (A2)',
        'name': 'ReleaseCandidateView: SLO_STATUS_CONFIG.met.bg -> status-online (fg==bg collision)',
        'target': "  met: {\n    color: 'var(--color-status-online)',\n    border: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',",
        'replacement': "  met: {\n    color: 'var(--color-status-online)',\n    border: 'var(--color-status-online)',\n    bg: 'var(--color-status-online)',",
        'expected_guard': 'Test 9j-2 (AST guard: 1:1 collision) & Test 9k (DOM contrast check)',
    },
    {
        'id': 'M3 (A3)',
        'name': 'ReleaseCandidateView: CANDIDATE_STATUS_CONFIG.waiting.bg -> text-secondary (text token as bg)',
        'target': "  waiting: {\n    color: 'var(--color-text-secondary)',\n    border: 'var(--color-border-subtle)',\n    bg: 'var(--color-bg-subtle)',",
        'replacement': "  waiting: {\n    color: 'var(--color-text-secondary)',\n    border: 'var(--color-border-subtle)',\n    bg: 'var(--color-text-secondary)',",
        'expected_guard': 'Test 9j-2 (AST guard: text token background)',
    },
    {
        'id': 'M4 (A4)',
        'name': 'ReleaseCandidateView: rollback card border -> bg-surface (border==bg collision)',
        'target': "      {/* Release Candidate Management & Rollback Verification Panel (AC-11) */}\n      <div\n        data-testid=\"rollback-management-card\"\n        style={{\n          backgroundColor: 'var(--color-bg-surface)',\n          border: '1px solid var(--color-border-subtle)',",
        'replacement': "      {/* Release Candidate Management & Rollback Verification Panel (AC-11) */}\n      <div\n        data-testid=\"rollback-management-card\"\n        style={{\n          backgroundColor: 'var(--color-bg-surface)',\n          border: '1px solid var(--color-bg-surface)',",
        'expected_guard': 'Test 9j-2 (border==bg collision)',
    },
    {
        'id': 'M5 (B1)',
        'name': 'ReleaseCandidateView: active candidate card outline ring removed',
        'target': "        <div\n          data-testid=\"active-candidate-card\"\n          style={{\n            backgroundColor: 'var(--color-bg-surface)',\n            border: '1px solid var(--color-border-subtle)',\n            borderRadius: '8px',\n            padding: '16px 20px',\n            outline: '2px solid var(--color-brand-primary)',\n            outlineOffset: '2px',\n          }}",
        'replacement': "        <div\n          data-testid=\"active-candidate-card\"\n          style={{\n            backgroundColor: 'var(--color-bg-surface)',\n            border: '1px solid var(--color-border-subtle)',\n            borderRadius: '8px',\n            padding: '16px 20px',\n            outline: 'none',\n            outlineOffset: '2px',\n          }}",
        'expected_guard': 'Test 9k (active candidate outline ring assertion)',
    },
    {
        'id': 'M6 (C1)',
        'name': 'ReleaseCandidateView: SLO status badge opacity degraded to 0.4',
        'target': "                        <span\n                          data-testid={`slo-status-badge-${slo.name}`}\n                          style={{\n                            padding: '2px 8px',",
        'replacement': "                        <span\n                          data-testid={`slo-status-badge-${slo.name}`}\n                          style={{\n                            opacity: 0.4,\n                            padding: '2px 8px',",
        'expected_guard': 'Test 9k (opacity 0.4 degradation assertion)',
    },
    {
        'id': 'M7 (D1)',
        'name': 'ReleaseCandidateView: SLO_STATUS_CONFIG.met.color reverted to legacy literal #3fb950',
        'target': "  met: {\n    color: 'var(--color-status-online)',",
        'replacement': "  met: {\n    color: '#3fb950',",
        'expected_guard': 'Test 10 (COLOR_LITERAL_MULTISET_BASELINE ratchet)',
    },
    {
        'id': 'M8 (D2)',
        'name': 'ReleaseCandidateView: CANDIDATE_STATUS_CONFIG.active.color reverted to legacy literal #58a6ff',
        'target': "  active: {\n    color: 'var(--color-brand-hover)',",
        'replacement': "  active: {\n    color: '#58a6ff',",
        'expected_guard': 'Test 10 (COLOR_LITERAL_MULTISET_BASELINE ratchet)',
    },
    {
        'id': 'M9 (F1)',
        'name': 'ReleaseCandidateView: candidate active color collapsed to text-secondary (waiting collision)',
        'target': "export const CANDIDATE_STATUS_CONFIG: Record<CandidateActiveStatus, CandidateStatusStyle> = {\n  active: {\n    color: 'var(--color-brand-hover)',",
        'replacement': "export const CANDIDATE_STATUS_CONFIG: Record<CandidateActiveStatus, CandidateStatusStyle> = {\n  active: {\n    color: 'var(--color-text-secondary)',",
        'expected_guard': 'Test 9k (candidate state token uniqueness assertion)',
    },
    {
        'id': 'M10 (F2)',
        'name': 'ReleaseCandidateView: SLO breached color collapsed to status-online (met collision)',
        'target': "  breached: {\n    color: 'var(--color-status-offline)',",
        'replacement': "  breached: {\n    color: 'var(--color-status-online)',",
        'expected_guard': 'Test 9k (SLO state token uniqueness assertion)',
    },
    {
        'id': 'M11 (G1)',
        'name': 'ReleaseCandidateView: SLO status badge text label {statusCfg.label} removed',
        'target': "                          {statusCfg.label}\n                        </span>",
        'replacement': "                          \n                        </span>",
        'expected_guard': 'Test 9k (SLO badge text label textContent non-empty assertion)',
    },
    {
        'id': 'M12 (G2)',
        'name': 'ReleaseCandidateView: candidate status badge text label {rcCfg.label} removed',
        'target': "                        {rcCfg.label}\n                      </span>",
        'replacement': "                        \n                      </span>",
        'expected_guard': 'Test 9k (candidate badge text label assertion)',
    },
    {
        'id': 'M13 (E1)',
        'name': 'ReleaseCandidateView: action notice error border swapped to status-online',
        'target': "border: `1px solid ${actionNotice.type === 'error' ? 'var(--color-status-offline)' : 'var(--color-status-online)'}`",
        'replacement': "border: `1px solid ${actionNotice.type === 'error' ? 'var(--color-status-online)' : 'var(--color-status-online)'}`",
        'expected_guard': 'Test 9k (action notice error border token assertion)',
    },
    {
        'id': 'M14 (E2)',
        'name': 'ReleaseCandidateView: KPI vulns title color swapped to bg-surface (invisible text)',
        'target': "          <div style={{ fontSize: '12px', color: 'var(--color-text-muted)', fontWeight: 600 }}>Critical / High 미완화 결함 (AC-11)</div>",
        'replacement': "          <div style={{ fontSize: '12px', color: 'var(--color-bg-surface)', fontWeight: 600 }}>Critical / High 미완화 결함 (AC-11)</div>",
        'expected_guard': 'Test 9j-2 (1:1 collision between fg and bg)',
    },
    {
        'id': 'M15 (E3)',
        'name': 'ReleaseCandidateView: WCAG audit fail badge color swapped to status-online',
        'target': "  fail: {\n    color: 'var(--color-status-offline)',",
        'replacement': "  fail: {\n    color: 'var(--color-status-online)',",
        'expected_guard': 'Test 9k (audit fail status color token assertion)',
    },
    {
        'id': 'M16 (F3)',
        'name': 'ReleaseCandidateView: candidate active border token reverted from brand-hover to border-subtle',
        'target': "  active: {\n    color: 'var(--color-brand-hover)',\n    border: 'var(--color-brand-hover)',",
        'replacement': "  active: {\n    color: 'var(--color-brand-hover)',\n    border: 'var(--color-border-subtle)',",
        'expected_guard': 'Test 9k (candidate active border token assertion)',
    },
]

def run_test_suite():
    cmd = [
        'npx.cmd' if os.name == 'nt' else 'npx',
        'vitest',
        'run',
        'tests/acc09-contrast-tokens.test.tsx',
        '--test-timeout=30000',
    ]
    env = os.environ.copy()
    env['NODE_OPTIONS'] = '--max-old-space-size=4096'
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
    print(' Card 220 (ACC-09): Reproducible Mutant Test Suite (16 Mutants: M1-M16)')
    print(' Target: ReleaseCandidateView.tsx')
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

        if target not in original_rc:
            print(f'[{i:02d}/{total_mutants}] {mid}: ERROR - Target snippet not found in ReleaseCandidateView.tsx!')
            results.append((mid, mname, 'ERROR_TARGET_NOT_FOUND', 'Target snippet not found'))
            continue

        mutated_code = original_rc.replace(target, replacement, 1)
        with open(RC_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(mutated_code)

        start_time = time.time()
        test_rc, test_out, test_err = run_test_suite()
        elapsed = time.time() - start_time

        # Restore immediately
        with open(RC_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(original_rc)

        if test_rc != 0:
            killed_count += 1
            reason = 'Unknown failure'
            for line in (test_out + test_err).splitlines():
                if 'AssertionError' in line or 'Error:' in line or 'expected' in line:
                    reason = line.strip()[:100]
                    break
            print(f'[{i:02d}/{total_mutants}] {mid}: KILLED in {elapsed:.1f}s -- {mname}', flush=True)
            print(f'         Reason: {reason}', flush=True)
            results.append((mid, mname, 'KILLED', reason))
        else:
            print(f'[{i:02d}/{total_mutants}] {mid}: SURVIVED (MUTANT ESCAPED!) in {elapsed:.1f}s -- {mname}', flush=True)
            print(f'         Expected to be caught by: {m["expected_guard"]}', flush=True)
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
