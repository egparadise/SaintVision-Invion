#!/usr/bin/env python3
"""
tools/test_c228_mutations.py

Card 228 (ACC-09) Natural Language Run screen (NaturalLanguageRunView.tsx) Mutation Testing Suite.
Verifies that 18 distinct regressions/mutations (M1-M18) across
color contrast, border collisions, status semantics, testid binding,
fail-closed unknown handling, prototype key defense, outline suppression, and token inventory
are strictly caught and killed by the test suite (ACC-09 Test 9m, Test 9j-2, and Test 10).

Usage:
    python tools/test_c228_mutations.py
"""

import sys
import os
import atexit
import subprocess
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
NL_FILE = os.path.join(REPO_ROOT, 'apps', 'web', 'src', 'features', 'agent', 'NaturalLanguageRunView.tsx')

original_nl = None

if os.path.exists(NL_FILE):
    with open(NL_FILE, 'r', encoding='utf-8') as f:
        original_nl = f.read()

def cleanup():
    if original_nl is not None and os.path.exists(NL_FILE):
        with open(NL_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(original_nl)

atexit.register(cleanup)

MUTANTS = [
    {
        'id': 'M1 (A1)',
        'name': 'NaturalLanguageRunView: unexposed-notice text color -> bg-surface (fg==bg 1:1 collision)',
        'target': "          backgroundColor: 'var(--color-bg-surface)',\n          border: '1px solid var(--color-border-subtle)',\n          borderRadius: '8px',\n          color: 'var(--color-text-primary)',",
        'replacement': "          backgroundColor: 'var(--color-bg-surface)',\n          border: '1px solid var(--color-border-subtle)',\n          borderRadius: '8px',\n          color: 'var(--color-bg-surface)',",
        'expected_guard': 'Test 9j-2 (AST guard: 1:1 collision) & Test 9m',
    },
    {
        'id': 'M2 (A2)',
        'name': 'NaturalLanguageRunView: AGENT_RUN_STATUS_CONFIG.completed.bg -> status-online (fg==bg collision)',
        'target': "  completed: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',",
        'replacement': "  completed: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-status-online)',",
        'expected_guard': 'Test 9j-2 (AST guard: 1:1 collision) & Test 9m',
    },
    {
        'id': 'M3 (A3)',
        'name': 'NaturalLanguageRunView: form textarea background -> text-primary (text token as bg)',
        'target': "                  backgroundColor: 'var(--color-bg-subtle)',\n                  border: '1px solid var(--color-border-subtle)',\n                  borderRadius: '6px',\n                  color: 'var(--color-text-primary)',",
        'replacement': "                  backgroundColor: 'var(--color-text-primary)',\n                  border: '1px solid var(--color-border-subtle)',\n                  borderRadius: '6px',\n                  color: 'var(--color-text-primary)',",
        'expected_guard': 'Test 9j-2 (AST guard: text token background)',
    },
    {
        'id': 'M4 (A4)',
        'name': 'NaturalLanguageRunView: KPI 1 container border -> bg-surface (border==bg collision)',
        'target': "<div style={{ backgroundColor: 'var(--color-bg-surface)', border: '1px solid var(--color-border-subtle)', borderRadius: '8px', padding: '16px 20px' }}>\n          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', fontWeight: 600 }}>Prompt 100건 유효율 (AC-09 픽스처)</div>",
        'replacement': "<div style={{ backgroundColor: 'var(--color-bg-surface)', border: '1px solid var(--color-bg-surface)', borderRadius: '8px', padding: '16px 20px' }}>\n          <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', fontWeight: 600 }}>Prompt 100건 유효율 (AC-09 픽스처)</div>",
        'expected_guard': 'Test 9j-2 (border==bg collision)',
    },
    {
        'id': 'M5 (B1)',
        'name': 'NaturalLanguageRunView: refine button outline ring suppressed with outline: none',
        'target': '<Button size="sm" variant="secondary" onClick={handleRequestRefinement} data-testid="agent-refine-btn">',
        'replacement': '<Button size="sm" variant="secondary" onClick={handleRequestRefinement} data-testid="agent-refine-btn" style={{ outline: \'none\' }}>',
        'expected_guard': 'Test 9m (focus ring suppression assertion) & Test 9j-2',
    },
    {
        'id': 'M6 (B2)',
        'name': 'NaturalLanguageRunView: refine button outline ring suppressed with outline: 0 (Claude Low 1)',
        'target': '<Button size="sm" variant="secondary" onClick={handleRequestRefinement} data-testid="agent-refine-btn">',
        'replacement': '<Button size="sm" variant="secondary" onClick={handleRequestRefinement} data-testid="agent-refine-btn" style={{ outline: \'0\' }}>',
        'expected_guard': 'Test 9m (focus ring suppression assertion) & Test 9j-2',
    },
    {
        'id': 'M7 (C1)',
        'name': 'NaturalLanguageRunView: status badge opacity degraded to 0.4',
        'target': "                    fontSize: '11px',\n                    fontWeight: 700,\n                    backgroundColor: statusCfg.bg,",
        'replacement': "                    fontSize: '11px',\n                    opacity: 0.4,\n                    fontWeight: 700,\n                    backgroundColor: statusCfg.bg,",
        'expected_guard': 'Test 9m (opacity degradation assertion)',
    },
    {
        'id': 'M8 (D1)',
        'name': 'NaturalLanguageRunView: KPI 1 valid rate color reverted to legacy literal #3fb950',
        'target': "fontSize: '24px', fontWeight: 700, color: 'var(--color-status-online)', marginTop: '4px'",
        'replacement': "fontSize: '24px', fontWeight: 700, color: '#3fb950', marginTop: '4px'",
        'expected_guard': 'Test 10 (COLOR_LITERAL_MULTISET_BASELINE ratchet)',
    },
    {
        'id': 'M9 (D2)',
        'name': 'NaturalLanguageRunView: action notice error border reverted to legacy literal #f85149',
        'target': "actionNotice.type === 'error'\n                    ? 'var(--color-status-offline)'",
        'replacement': "actionNotice.type === 'error'\n                    ? '#f85149'",
        'expected_guard': 'Test 10 (COLOR_LITERAL_MULTISET_BASELINE ratchet)',
    },
    {
        'id': 'M10 (D3)',
        'name': 'NaturalLanguageRunView: token/cost preview border reverted to legacy literal #30363d',
        'target': "border: '1px solid var(--color-border-subtle)',\n                borderRadius: '6px',\n                padding: '12px 16px',\n                display: 'flex',\n                justifyContent: 'space-between',\n                alignItems: 'center',\n                fontSize: '12px',",
        'replacement': "border: '1px solid #30363d',\n                borderRadius: '6px',\n                padding: '12px 16px',\n                display: 'flex',\n                justifyContent: 'space-between',\n                alignItems: 'center',\n                fontSize: '12px',",
        'expected_guard': 'Test 10 (COLOR_LITERAL_MULTISET_BASELINE ratchet)',
    },
    {
        'id': 'M11 (F1)',
        'name': 'NaturalLanguageRunView: ready status color collapsed to rejected status-offline',
        'target': "  ready: {\n    color: 'var(--color-brand-hover)',",
        'replacement': "  ready: {\n    color: 'var(--color-status-offline)',",
        'expected_guard': 'Test 9m (status token uniqueness assertion)',
    },
    {
        'id': 'M12 (F2)',
        'name': 'NaturalLanguageRunView: completed status color collapsed to rejected status-offline',
        'target': "  completed: {\n    color: 'var(--color-status-online)',",
        'replacement': "  completed: {\n    color: 'var(--color-status-offline)',",
        'expected_guard': 'Test 9m (status token uniqueness assertion)',
    },
    {
        'id': 'M13 (G1)',
        'name': 'NaturalLanguageRunView: status badge icon element removed from DOM',
        'target': '<span data-testid="agent-status-icon" aria-hidden="true">{statusCfg.icon}</span>',
        'replacement': '{null}',
        'expected_guard': 'Test 9m (status badge icon presence assertion)',
    },
    {
        'id': 'M14 (G2)',
        'name': 'NaturalLanguageRunView: status badge label element removed from DOM',
        'target': '<span data-testid="agent-status-label">{statusCfg.label}</span>',
        'replacement': '{null}',
        'expected_guard': 'Test 9m (status badge label presence assertion)',
    },
    {
        'id': 'M15 (H1)',
        'name': 'NaturalLanguageRunView: getAgentRunStatusConfig unknown fallback returns completed config (fail-closed bypass)',
        'target': "  return {\n    color: 'var(--color-status-unknown)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-unknown)',\n    label: `UNKNOWN (${status || 'UNKNOWN'})`,\n    icon: '❓',\n  };",
        'replacement': '  return AGENT_RUN_STATUS_CONFIG.completed;',
        'expected_guard': 'Test 9m (unknown status fail-closed token & label assertion)',
    },
    {
        'id': 'M16 (H2)',
        'name': 'NaturalLanguageRunView: getAgentRunStatusConfig uses prototype-inclusive in operator (Codex F1)',
        'target': 'if (status && Object.hasOwn(AGENT_RUN_STATUS_CONFIG, status)) {',
        'replacement': 'if (status && status in AGENT_RUN_STATUS_CONFIG) {',
        'expected_guard': 'Test 9m (prototype key fail-closed own-key defense assertion)',
    },
    {
        'id': 'M17 (I1)',
        'name': 'NaturalLanguageRunView: preset 1 button color injected with named color lightgray',
        'target': "border: '1px solid var(--color-border-subtle)',\n                backgroundColor: 'var(--color-bg-subtle)',\n                color: 'var(--color-brand-hover)',",
        'replacement': "border: '1px solid var(--color-border-subtle)',\n                backgroundColor: 'var(--color-bg-subtle)',\n                color: 'lightgray',",
        'expected_guard': 'Test 9j-2 (named color literal violation) & Test 10',
    },
    {
        'id': 'M18 (I2)',
        'name': 'NaturalLanguageRunView: unexposed notice title injected with comment decoy and literal',
        'target': "fontWeight: 600, fontSize: '0.875rem', color: 'var(--color-brand-hover)', display: 'flex'",
        'replacement': "fontWeight: 600, fontSize: '0.875rem', color: '#93c5fd' /* var(--color-brand-hover) */, display: 'flex'",
        'expected_guard': 'Test 10 (COLOR_LITERAL_MULTISET_BASELINE ratchet)',
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
    print(' Card 228 (ACC-09): Reproducible Mutant Test Suite (18 Mutants: M1-M18)')
    print(' Target: NaturalLanguageRunView.tsx')
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

        if target not in original_nl:
            print(f'[{i:02d}/{total_mutants}] {mid}: ERROR - Target snippet not found in NaturalLanguageRunView.tsx!')
            results.append((mid, mname, 'ERROR_TARGET_NOT_FOUND', 'Target snippet not found'))
            continue

        mutated_code = original_nl.replace(target, replacement, 1)
        with open(NL_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(mutated_code)

        start_time = time.time()
        test_rc, test_out, test_err = run_test_suite()
        elapsed = time.time() - start_time

        # Restore immediately
        with open(NL_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(original_nl)

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
