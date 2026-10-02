#!/usr/bin/env python3
"""
tools/test_c215_mutations.py

Card 215 (ACC-09) Runs execution list screen (RunList.tsx) Mutation Testing Suite.
Verifies that 10 distinct regressions/mutations (M1-M10) across
color contrast, border collisions, status semantics, testid binding,
and fail-closed multiset inventory are strictly caught and killed by the test suite
(ACC-09 Test 9i, Test 9i-2, and Test 10).

Usage:
    python tools/test_c215_mutations.py
"""

import sys
import os
import atexit
import subprocess
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RUNLIST_FILE = os.path.join(REPO_ROOT, 'apps', 'web', 'src', 'features', 'runs', 'RunList.tsx')

original_runlist = None

if os.path.exists(RUNLIST_FILE):
    with open(RUNLIST_FILE, 'r', encoding='utf-8') as f:
        original_runlist = f.read()

def cleanup():
    if original_runlist is not None and os.path.exists(RUNLIST_FILE):
        with open(RUNLIST_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(original_runlist)

atexit.register(cleanup)

MUTANTS = [
    {
        'id': 'M1 (A1)',
        'name': 'RunList: stale warning banner bg -> status-offline (fg==bg collision)',
        'target': "          style={{\n            padding: '12px 16px',\n            marginBottom: '16px',\n            backgroundColor: 'var(--color-bg-subtle)',\n            border: '1px solid var(--color-status-offline)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',",
        'replacement': "          style={{\n            padding: '12px 16px',\n            marginBottom: '16px',\n            backgroundColor: 'var(--color-status-offline)',\n            border: '1px solid var(--color-status-offline)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',",
        'expected_guard': 'Test 9i-2 / Test 9i (1:1 collision between bg and fg)',
    },
    {
        'id': 'M2 (A2)',
        'name': 'RunList: RUN_STATE_CONFIG.validated.bg -> text-secondary (fg==bg collision)',
        'target': "  validated: {\n    label: '검증됨',\n    color: 'var(--color-text-secondary)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-border-subtle)',\n  },",
        'replacement': "  validated: {\n    label: '검증됨',\n    color: 'var(--color-text-secondary)',\n    bg: 'var(--color-text-secondary)',\n    border: 'var(--color-border-subtle)',\n  },",
        'expected_guard': 'Test 9i-2 (AST guard: 1:1 collision) & Test 9i (DOM bg & contrast check)',
    },
    {
        'id': 'M3 (A3)',
        'name': 'RunList: RUN_STATE_CONFIG.draft.bg -> text-muted (illegitimate text token as background)',
        'target': "  draft: {\n    label: '초안',\n    color: 'var(--color-text-secondary)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-border-subtle)',\n  },",
        'replacement': "  draft: {\n    label: '초안',\n    color: 'var(--color-text-secondary)',\n    bg: 'var(--color-text-muted)',\n    border: 'var(--color-border-subtle)',\n  },",
        'expected_guard': 'Test 9i-2 (AST guard: text token background) & Test 9i (DOM bg & contrast check)',
    },
    {
        'id': 'M4 (A4)',
        'name': 'RunList: table header tr bg -> text-secondary (JSX text token as background)',
        'target': "            <tr style={{ backgroundColor: 'var(--color-bg-subtle)', borderBottom: '1px solid var(--color-border-subtle)' }}>",
        'replacement': "            <tr style={{ backgroundColor: 'var(--color-text-secondary)', borderBottom: '1px solid var(--color-border-subtle)' }}>",
        'expected_guard': 'Test 9i-2 (AST guard: Illegitimate background token derived from text token)',
    },
    {
        'id': 'M5 (B1)',
        'name': 'RunList: RUN_STATE_CONFIG.draft.border -> bg-subtle (border==bg collision)',
        'target': "  draft: {\n    label: '초안',\n    color: 'var(--color-text-secondary)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-border-subtle)',\n  },",
        'replacement': "  draft: {\n    label: '초안',\n    color: 'var(--color-text-secondary)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-bg-subtle)',\n  },",
        'expected_guard': 'Test 9i-2 (AST guard: Identical border-background token collision) & Test 9i (DOM)',
    },
    {
        'id': 'M6 (B2)',
        'name': 'RunList: ALL pill selected border -> brand-primary-bg (border==bg collision)',
        'target': "            border: selectedFilter === 'ALL' ? '1px solid var(--color-brand-primary-fg)' : '1px solid var(--color-border-subtle)',\n            backgroundColor: selectedFilter === 'ALL' ? 'var(--color-brand-primary-bg)' : 'var(--color-bg-subtle)',",
        'replacement': "            border: selectedFilter === 'ALL' ? '1px solid var(--color-brand-primary-bg)' : '1px solid var(--color-border-subtle)',\n            backgroundColor: selectedFilter === 'ALL' ? 'var(--color-brand-primary-bg)' : 'var(--color-bg-subtle)',",
        'expected_guard': 'Test 9i-2 (AST guard: border-bg collision) / Test 9i',
    },
    {
        'id': 'M7 (C1)',
        'name': 'RunList: status badge opacity degraded to 0.4',
        'target': "                      <span\n                        data-testid={`run-status-badge-${run.id}`}\n                        style={{\n                          display: 'inline-block',\n                          padding: '2px 8px',\n                          borderRadius: 'var(--radius-sm)',\n                          fontSize: '0.75rem',\n                          fontWeight: 600,\n                          color: cfg.color,\n                          backgroundColor: cfg.bg,\n                          border: `1px solid ${cfg.border}`,\n                        }}",
        'replacement': "                      <span\n                        data-testid={`run-status-badge-${run.id}`}\n                        style={{\n                          display: 'inline-block',\n                          padding: '2px 8px',\n                          borderRadius: 'var(--radius-sm)',\n                          fontSize: '0.75rem',\n                          fontWeight: 600,\n                          opacity: 0.4,\n                          color: cfg.color,\n                          backgroundColor: cfg.bg,\n                          border: `1px solid ${cfg.border}`,\n                        }}",
        'expected_guard': 'Test 9i (DOM assertion: Badge must not have degraded opacity)',
    },
    {
        'id': 'M8 (C2)',
        'name': 'RunList: stale warning banner opacity degraded to 0.5',
        'target': "          style={{\n            padding: '12px 16px',\n            marginBottom: '16px',\n            backgroundColor: 'var(--color-bg-subtle)',\n            border: '1px solid var(--color-status-offline)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',\n            fontSize: '0.8125rem',\n          }}",
        'replacement': "          style={{\n            padding: '12px 16px',\n            marginBottom: '16px',\n            backgroundColor: 'var(--color-bg-subtle)',\n            border: '1px solid var(--color-status-offline)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-status-offline)',\n            fontSize: '0.8125rem',\n            opacity: 0.5,\n          }}",
        'expected_guard': 'Test 9i-2 (AST guard: Light/Dark text contrast < 4.5:1 with opacity)',
    },
    {
        'id': 'M9 (D1)',
        'name': 'RunList: decoy comment with legacy hex literal',
        'target': "                    <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--color-status-offline)', marginBottom: '6px' }}>",
        'replacement': "                    <div style={{ fontSize: '1rem', fontWeight: 600, color: '#fca5a5' /* var(--color-status-offline) */, marginBottom: '6px' }}>",
        'expected_guard': 'Test 10 (Fail-Closed Multiset Inventory: unexpected raw hex literal)',
    },
    {
        'id': 'M10 (E1)',
        'name': 'RunList: recovering color reverted to legacy literal #f97316',
        'target': "  recovering: {\n    label: '복구 중',\n    color: 'var(--color-status-active)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-active)',\n  },",
        'replacement': "  recovering: {\n    label: '복구 중',\n    color: '#f97316',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-active)',\n  },",
        'expected_guard': 'Test 10 (Fail-Closed Multiset Inventory: #f97316 unexpected literal)',
    },
    {
        'id': 'M11 (E2)',
        'name': 'RunList: retry button bg reverted to legacy literal #ef4444',
        'target': "                          backgroundColor: 'var(--color-status-offline-bg)',",
        'replacement': "                          backgroundColor: '#ef4444',",
        'expected_guard': 'Test 10 (Fail-Closed Multiset Inventory: #ef4444 unexpected literal)',
    },
    {
        'id': 'M12 (F1)',
        'name': 'RunList: recovering token collapsed to running token',
        'target': "  recovering: {\n    label: '복구 중',\n    color: 'var(--color-status-active)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-active)',\n  },",
        'replacement': "  recovering: {\n    label: '복구 중',\n    color: 'var(--color-brand-hover)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-brand-hover)',\n  },",
        'expected_guard': 'Test 9i (DOM assertion: badgeRecovering.style.color must be var(--color-status-active))',
    },
    {
        'id': 'M13 (F2)',
        'name': 'RunList: failed token collapsed to cancelled token',
        'target': "  failed: {\n    label: '실패',\n    color: 'var(--color-status-offline)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-offline)',\n  },",
        'replacement': "  failed: {\n    label: '실패',\n    color: 'var(--color-status-neutral)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-border-strong)',\n  },",
        'expected_guard': 'Test 9i (DOM assertion: Failed and cancelled must not have identical tokens)',
    },
    {
        'id': 'M14 (G1)',
        'name': 'RunList: badge text label {cfg.label} removed',
        'target': "                        {cfg.label}\n                      </span>",
        'replacement': "                        {/* label removed */}\n                      </span>",
        'expected_guard': 'Test 9i (DOM assertion: badgeDraft.textContent must be 초안)',
    },
    {
        'id': 'M15 (G2)',
        'name': 'RunList: ⏳ icon removed from resourceReleasePending badge',
        'target': "                          ⏳ 자원 반환 대기 (ADR-040)\n                        </span>",
        'replacement': "                          자원 반환 대기 (ADR-040)\n                        </span>",
        'expected_guard': 'Test 9i (DOM assertion: releaseBadge.textContent must contain ⏳)',
    },
    {
        'id': 'M16 (F2 Collide)',
        'name': 'RunList: planned state token collapsed back to recovering (status-active)',
        'target': "  planned: {\n    label: '계획 수립',\n    color: 'var(--color-text-secondary)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-border-subtle)',\n  },",
        'replacement': "  planned: {\n    label: '계획 수립',\n    color: 'var(--color-status-active)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-active)',\n  },",
        'expected_guard': 'Test 9i (DOM assertion: recovering must not collide with planned)',
    },
]

def run_test():
    web_dir = os.path.join(REPO_ROOT, 'apps', 'web')
    cmd = ['npx.cmd' if sys.platform == 'win32' else 'npx', 'vitest', 'run', 'tests/acc09-contrast-tokens.test.tsx', '-t', 'Card 215|Multiset Inventory']
    res = subprocess.run(
        cmd,
        cwd=web_dir,
        capture_output=True,
        encoding='utf-8',
        errors='replace'
    )
    return res.returncode, res.stdout, res.stderr

def extract_failure_reason(stdout, stderr):
    import re
    ansi_escape = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
    clean = ansi_escape.sub('', stdout + '\n' + stderr)
    output_lines = clean.splitlines()
    failed_block = False
    for line in output_lines:
        line_s = line.strip()
        if 'Failed Tests' in line_s:
            failed_block = True
            continue
        if failed_block:
            if 'AssertionError' in line_s or 'violations' in line_s or 'Expected' in line_s or '1:1' in line_s or 'Illegitimate' in line_s or 'expected' in line_s or 'collide' in line_s:
                return line_s
    for line in output_lines:
        line_s = line.strip()
        if not line_s or line_s.startswith('↓') or line_s.startswith('✓') or line_s.startswith('RUN') or line_s.startswith('Test Files') or line_s.startswith('Tests'):
            continue
        if 'AssertionError' in line_s or 'violations' in line_s or '1:1' in line_s or 'Illegitimate' in line_s or 'exceeded' in line_s:
            return line_s
    return 'Exit code 1 (Vitest test assertion failure)'

def main():
    print('================================================================================')
    print(' Card 215 (ACC-09): Reproducible Mutant Test Suite (10 Mutants: M1-M10)')
    print(' Target: RunList.tsx')
    print('================================================================================\\n')

    # Step 0: Verify clean baseline
    print('[Baseline Check] Testing unmutated code...')
    rc, stdout, stderr = run_test()
    if rc != 0:
        print('FAILED: Baseline test failed unexpectedly!')
        print(stdout)
        print(stderr)
        sys.exit(1)
    print('[Baseline Check] Clean pass (exit code 0).\n')

    killed_count = 0
    total_count = len(MUTANTS)
    results = []

    for i, m in enumerate(MUTANTS, 1):
        mid = m['id']
        name = m['name']
        target = m['target']
        replacement = m['replacement']

        if target not in original_runlist:
            print(f'[{i:02d}/{total_count}] {mid}: ERROR - Target string not found in RunList.tsx!')
            results.append((mid, name, 'ERROR (target not found)', ''))
            continue

        mutated_content = original_runlist.replace(target, replacement, 1)
        with open(RUNLIST_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(mutated_content)

        t0 = time.time()
        rc, stdout, stderr = run_test()
        elapsed = time.time() - t0

        # Restore immediately
        with open(RUNLIST_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(original_runlist)

        if rc != 0:
            killed_count += 1
            snippet = extract_failure_reason(stdout, stderr)
            print(f'[{i:02d}/{total_count}] {mid}: KILLED in {elapsed:.1f}s -- {name}')
            print(f'         Reason: {snippet[:100]}')
            results.append((mid, name, 'KILLED', snippet[:100]))
        else:
            print(f'[{i:02d}/{total_count}] {mid}: SURVIVED in {elapsed:.1f}s -- {name}')
            results.append((mid, name, 'SURVIVED', 'Test passed unexpectedly'))

    print('\n================================================================================')
    print(f' Summary: {killed_count}/{total_count} mutants killed ({(killed_count/total_count)*100:.1f}%)')
    print('================================================================================')
    for mid, name, status, snip in results:
        marker = '[PASS]' if status == 'KILLED' else '[FAIL]'
        print(f' {marker} {mid:4s}: {status:8s} | {name} ({snip})')

    if killed_count == total_count:
        print('\nSUCCESS: 100% mutant kill rate achieved. All accessibility invariants strictly hold.')
        sys.exit(0)
    else:
        print(f'\nFAILURE: Only {killed_count}/{total_count} mutants killed.')
        sys.exit(1)

if __name__ == '__main__':
    main()
