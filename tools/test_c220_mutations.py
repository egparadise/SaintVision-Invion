#!/usr/bin/env python3
"""
tools/test_c220_mutations.py

Card 220 (ACC-09) Release Candidate screen (ReleaseCandidateView.tsx) Mutation Testing Suite.
Verifies that 22 distinct regressions/mutations (M1-M22) across
color contrast, border collisions, status semantics, testid binding,
fail-closed unknown handling, and non-color accessibility are strictly caught
and killed by the test suite (ACC-09 Test 9k, Test 9j-2, and Test 10).

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
        'target': "padding: '8px 16px',\n          backgroundColor: 'var(--color-bg-subtle)',\n          border: '1px solid var(--color-border-subtle)',\n          borderRadius: '6px',\n          color: 'var(--color-text-secondary)',",
        'replacement': "padding: '8px 16px',\n          backgroundColor: 'var(--color-text-secondary)',\n          border: '1px solid var(--color-border-subtle)',\n          borderRadius: '6px',\n          color: 'var(--color-text-secondary)',",
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
        'name': 'ReleaseCandidateView: rollback button injects inline outline: none suppressing focus ring',
        'target': "<Button\n                          size=\"sm\"\n                          variant=\"secondary\"\n                          aria-label={`이 버전(${rc.tag})으로 롤백 실행 (AC-11)`}",
        'replacement': "<Button\n                          size=\"sm\"\n                          variant=\"secondary\"\n                          style={{ outline: 'none' }}\n                          aria-label={`이 버전(${rc.tag})으로 롤백 실행 (AC-11)`}",
        'expected_guard': 'Test 9k (rollback button outline ring suppression assertion) & Test 9j-2',
    },
    {
        'id': 'M6 (C1)',
        'name': 'ReleaseCandidateView: SLO status badge opacity degraded to 0.4',
        'target': "<span\n                          data-testid={`slo-status-badge-${slo.name}`}\n                          style={{\n                            padding: '2px 8px',",
        'replacement': "<span\n                          data-testid={`slo-status-badge-${slo.name}`}\n                          style={{\n                            opacity: 0.4,\n                            padding: '2px 8px',",
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
        'target': "<div style={{ fontSize: '12px', color: 'var(--color-text-muted)', fontWeight: 600 }}>Critical / High 미완화 결함 (AC-11)</div>",
        'replacement': "<div style={{ fontSize: '12px', color: 'var(--color-bg-surface)', fontWeight: 600 }}>Critical / High 미완화 결함 (AC-11)</div>",
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
    {
        'id': 'M17 (H2-1)',
        'name': 'ReleaseCandidateView: SLO status badge color set to statusCfg.bg (rendered fg==bg collision)',
        'target': "backgroundColor: statusCfg.bg,\n                            border: `1px solid ${statusCfg.border}`,\n                            color: statusCfg.color,",
        'replacement': "backgroundColor: statusCfg.bg,\n                            border: `1px solid ${statusCfg.border}`,\n                            color: statusCfg.bg,",
        'expected_guard': 'Test 9k (rendered badge color matches config color assertion)',
    },
    {
        'id': 'M18 (H2-2)',
        'name': 'ReleaseCandidateView: Audit status badge border set to auditCfg.bg (rendered border==bg collision)',
        'target': "backgroundColor: auditCfg.bg,\n                      border: `1px solid ${auditCfg.border}`,\n                      color: auditCfg.color,",
        'replacement': "backgroundColor: auditCfg.bg,\n                      border: `1px solid ${auditCfg.bg}`,\n                      color: auditCfg.color,",
        'expected_guard': 'Test 9k (rendered badge border matches config border assertion)',
    },
    {
        'id': 'M19 (H2-3)',
        'name': 'ReleaseCandidateView: Audit status badge opacity degraded to 0.4',
        'target': "<span\n                    data-testid={`audit-status-badge-${audit.ruleId}`}\n                    style={{\n                      padding: '2px 8px',",
        'replacement': "<span\n                    data-testid={`audit-status-badge-${audit.ruleId}`}\n                    style={{\n                      opacity: 0.4,\n                      padding: '2px 8px',",
        'expected_guard': 'Test 9k (rendered audit badge opacity 1 assertion)',
    },
    {
        'id': 'M20 (H1)',
        'name': 'ReleaseCandidateView: getSloStatusConfig unknown fallback changed to met (fail-closed bypass)',
        'target': "export function getSloStatusConfig(status?: string | null): SloStatusStyle {\n  if (status && Object.hasOwn(SLO_STATUS_CONFIG, status)) {\n    return SLO_STATUS_CONFIG[status as SloRecordStatus];\n  }\n  return {\n    color: 'var(--color-status-unknown)',\n    border: 'var(--color-status-unknown)',\n    bg: 'var(--color-bg-subtle)',\n    label: `UNKNOWN (${status || 'UNKNOWN'})`,\n  };\n}",
        'replacement': "export function getSloStatusConfig(status?: string | null): SloStatusStyle {\n  if (status && Object.hasOwn(SLO_STATUS_CONFIG, status)) {\n    return SLO_STATUS_CONFIG[status as SloRecordStatus];\n  }\n  return SLO_STATUS_CONFIG.met;\n}",
        'expected_guard': 'Test 9k (rendered unknown status fail-closed token & label assertion)',
    },
    {
        'id': 'M21 (Codex F1)',
        'name': 'ReleaseCandidateView: getSloStatusConfig uses status in SLO_STATUS_CONFIG bypassing prototype keys',
        'target': "export function getSloStatusConfig(status?: string | null): SloStatusStyle {\n  if (status && Object.hasOwn(SLO_STATUS_CONFIG, status)) {\n    return SLO_STATUS_CONFIG[status as SloRecordStatus];\n  }\n  return {\n    color: 'var(--color-status-unknown)',\n    border: 'var(--color-status-unknown)',\n    bg: 'var(--color-bg-subtle)',\n    label: `UNKNOWN (${status || 'UNKNOWN'})`,\n  };\n}",
        'replacement': "export function getSloStatusConfig(status?: string | null): SloStatusStyle {\n  if (status && status in SLO_STATUS_CONFIG) {\n    return SLO_STATUS_CONFIG[status as SloRecordStatus];\n  }\n  return {\n    color: 'var(--color-status-unknown)',\n    border: 'var(--color-status-unknown)',\n    bg: 'var(--color-bg-subtle)',\n    label: `UNKNOWN (${status || 'UNKNOWN'})`,\n  };\n}",
        'expected_guard': 'Test 9k (prototype key fail-closed own-key defense assertion)',
    },
    {
        'id': 'M22 (Claude Low)',
        'name': 'ReleaseCandidateView: rollback button injects style={{ outline: 0 }} suppressing focus ring',
        'target': "<Button\n                          size=\"sm\"\n                          variant=\"secondary\"\n                          aria-label={`이 버전(${rc.tag})으로 롤백 실행 (AC-11)`}",
        'replacement': "<Button\n                          size=\"sm\"\n                          variant=\"secondary\"\n                          style={{ outline: 0 }}\n                          aria-label={`이 버전(${rc.tag})으로 롤백 실행 (AC-11)`}",
        'expected_guard': 'Test 9k (computed outline-width/style and inline outline non-zero assertion) & Test 9j-2',
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
    print(' Card 220 (ACC-09): Reproducible Mutant Test Suite (22 Mutants: M1-M22)')
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
