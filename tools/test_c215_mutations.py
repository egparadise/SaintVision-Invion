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
        'id': 'M1',
        'name': 'RunList: status succeeded badge token swapped to brand-hover (semantic regression)',
        'target': "  succeeded: {\n    label: '성공',\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-online)',\n  },",
        'replacement': "  succeeded: {\n    label: '성공',\n    color: 'var(--color-brand-hover)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-brand-hover)',\n  },",
        'expected_guard': 'Test 9i (DOM assertion: badgeSucceeded.style.color must be var(--color-status-online))',
    },
    {
        'id': 'M2',
        'name': 'RunList: status running badge token swapped to online (semantic regression)',
        'target': "  running: {\n    label: '실행 중',\n    color: 'var(--color-brand-hover)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-brand-hover)',\n  },",
        'replacement': "  running: {\n    label: '실행 중',\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-online)',\n  },",
        'expected_guard': 'Test 9i (DOM assertion: Succeeded and running must not have identical tokens)',
    },
    {
        'id': 'M3',
        'name': 'RunList: status recovering badge token swapped to online (semantic regression)',
        'target': "  recovering: {\n    label: '복구 중',\n    color: 'var(--color-status-active)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-active)',\n  },",
        'replacement': "  recovering: {\n    label: '복구 중',\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-online)',\n  },",
        'expected_guard': 'Test 9i (DOM assertion: Recovering and succeeded must not have identical tokens)',
    },
    {
        'id': 'M4',
        'name': 'RunList: status failed badge token swapped to online (semantic regression)',
        'target': "  failed: {\n    label: '실패',\n    color: 'var(--color-status-offline)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-offline)',\n  },",
        'replacement': "  failed: {\n    label: '실패',\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-online)',\n  },",
        'expected_guard': 'Test 9i (DOM assertion: Succeeded and failed must not have identical tokens)',
    },
    {
        'id': 'M5',
        'name': 'RunList: status cancelled badge token swapped to offline (semantic regression)',
        'target': "  cancelled: {\n    label: '취소됨',\n    color: 'var(--color-status-neutral)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-border-strong)',\n  },",
        'replacement': "  cancelled: {\n    label: '취소됨',\n    color: 'var(--color-status-offline)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-offline)',\n  },",
        'expected_guard': 'Test 9i (DOM assertion: Failed and cancelled must not have identical tokens)',
    },
    {
        'id': 'M6',
        'name': 'RunList: re-injects raw hex literal (fail-closed multiset inventory breach)',
        'target': 'export const RunList: React.FC<RunListProps> = ({',
        'replacement': "const _decoyRunList = '#ef4444';\nexport const RunList: React.FC<RunListProps> = ({",
        'expected_guard': 'Test 10 (Fail-Closed Multiset Inventory: RunList multiset must be empty)',
    },
    {
        'id': 'M7',
        'name': 'RunList: missing testid regression (removes run-status-badge)',
        'target': "                      <span\n                        data-testid={`run-status-badge-${run.id}`}\n                        style={{",
        'replacement': "                      <span\n                        style={{",
        'expected_guard': 'Test 9i (DOM assertion: badgeSucceeded must render: expected null not to be null)',
    },
    {
        'id': 'M8',
        'name': 'RunList: 1:1 border collision on table container',
        'target': "        style={{\n          backgroundColor: 'var(--color-bg-surface)',\n          borderRadius: 'var(--radius-lg)',\n          border: '1px solid var(--color-border-subtle)',",
        'replacement': "        style={{\n          backgroundColor: 'var(--color-bg-surface)',\n          borderRadius: 'var(--radius-lg)',\n          border: '1px solid var(--color-bg-surface)',",
        'expected_guard': 'Test 9i-2 (AST guard: Identical border-background token collision detected)',
    },
    {
        'id': 'M9',
        'name': 'RunList: completedAt failed branch swapped to online (semantic collapse)',
        'target': "                    {run.completedAt ? (\n                      <div data-testid={`run-completed-at-${run.id}`} style={{ fontSize: '0.75rem', color: run.state === 'succeeded' ? 'var(--color-status-online)' : 'var(--color-status-offline)', marginTop: '2px' }}>",
        'replacement': "                    {run.completedAt ? (\n                      <div data-testid={`run-completed-at-${run.id}`} style={{ fontSize: '0.75rem', color: run.state === 'succeeded' ? 'var(--color-status-online)' : 'var(--color-status-online)', marginTop: '2px' }}>",
        'expected_guard': 'Test 9i (DOM assertion: Succeeded and failed completedAt must have distinct status tokens)',
    },
    {
        'id': 'M10',
        'name': 'RunList: resource release pending badge swapped to online (semantic violation)',
        'target': "                        <span\n                          data-testid={`run-resource-release-badge-${run.id}`}\n                          style={{\n                            display: 'inline-block',\n                            padding: '1px 6px',\n                            borderRadius: 'var(--radius-sm)',\n                            fontSize: '0.6875rem',\n                            fontWeight: 600,\n                            color: 'var(--color-status-degraded)',\n                            backgroundColor: 'var(--color-bg-subtle)',\n                            border: '1px solid var(--color-status-degraded)',\n                          }}",
        'replacement': "                        <span\n                          data-testid={`run-resource-release-badge-${run.id}`}\n                          style={{\n                            display: 'inline-block',\n                            padding: '1px 6px',\n                            borderRadius: 'var(--radius-sm)',\n                            fontSize: '0.6875rem',\n                            fontWeight: 600,\n                            color: 'var(--color-status-online)',\n                            backgroundColor: 'var(--color-bg-subtle)',\n                            border: '1px solid var(--color-status-online)',\n                          }}",
        'expected_guard': 'Test 9i (DOM assertion: releaseBadge.style.color must be var(--color-status-degraded))',
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
            output_lines = (stdout + '\n' + stderr).splitlines()
            err_snips = [line.strip() for line in output_lines if not line.strip().startswith('↓') and ('AssertionError' in line or 'violations' in line or 'FAIL' in line or 'Expected' in line or '1:1' in line or 'exceeded' in line or 'not registered' in line)]
            snippet = err_snips[0] if err_snips else 'Exit code 1 (Vitest test assertion failure)'
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
