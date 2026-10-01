#!/usr/bin/env python3
"""
tools/test_c202_mutations.py

Card 202 (ACC-09) IntranetDeploymentView Mutation Testing Suite.
Verifies that 10 distinct regressions/mutations (B1-B5, M6-M10) across
color contrast, opacity, border collisions, status semantics, and multiset inventory
are strictly caught and killed by the test suite (ACC-09 Test 9f, 9f-2, and Test 10).

Usage:
    python tools/test_c202_mutations.py
"""

import sys
import os
import atexit
import shutil
import subprocess
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TARGET_FILE = os.path.join(REPO_ROOT, 'apps', 'web', 'src', 'features', 'deployment', 'IntranetDeploymentView.tsx')
BACKUP_FILE = TARGET_FILE + '.mutant_bak'

# Ensure backup and restore safety
original_content = None
if os.path.exists(TARGET_FILE):
    with open(TARGET_FILE, 'r', encoding='utf-8') as f:
        original_content = f.read()

def cleanup():
    if original_content is not None and os.path.exists(TARGET_FILE):
        with open(TARGET_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(original_content)
    if os.path.exists(BACKUP_FILE):
        try:
            os.remove(BACKUP_FILE)
        except OSError:
            pass

atexit.register(cleanup)

MUTANTS = [
    {
        'id': 'B1',
        'name': 'server detail grid bg -> status-degraded',
        'target': "backgroundColor: 'var(--color-bg-subtle)',\n            padding: '16px',\n            borderRadius: '6px',\n            border: '1px solid var(--color-border-subtle)',",
        'replacement': "backgroundColor: 'var(--color-status-degraded)',\n            padding: '16px',\n            borderRadius: '6px',\n            border: '1px solid var(--color-border-subtle)',",
        'expected_guard': 'Test 9f-2 (contrast failure against degraded status background)',
    },
    {
        'id': 'B2',
        'name': 'server detail grid border -> bg-subtle (1:1 border collision)',
        'target': "border: '1px solid var(--color-border-subtle)',\n            fontSize: '12px',",
        'replacement': "border: '1px solid var(--color-bg-subtle)',\n            fontSize: '12px',",
        'expected_guard': 'Test 9f-2 (1:1 border-background collision detected: --color-bg-subtle on --color-bg-subtle)',
    },
    {
        'id': 'B3',
        'name': 'unsigned mark -> text-secondary (#281 semantic degradation)',
        'target': "<span style={{ color: 'var(--color-status-degraded)', fontWeight: 600 }}>\n                    미서명 (operatorSignOff: false)\n                  </span>",
        'replacement': "<span style={{ color: 'var(--color-text-secondary)', fontWeight: 600 }}>\n                    미서명 (operatorSignOff: false)\n                  </span>",
        'expected_guard': 'Test 9f (DOM assertion fails: signoff badge must bind to var(--color-status-degraded))',
    },
    {
        'id': 'B4',
        'name': 'color literal decoy insertion (fail-closed multiset inventory breach)',
        'target': "export const IntranetDeploymentView: React.FC<IntranetDeploymentViewProps> = ({",
        'replacement': "const _decoyColor = '#abcdef';\nexport const IntranetDeploymentView: React.FC<IntranetDeploymentViewProps> = ({",
        'expected_guard': 'Test 10 (Fail-Closed Multiset Inventory: IntranetDeploymentView multiset must be empty)',
    },
    {
        'id': 'B5',
        'name': 'line 889 error detail opacity: 0.9 -> 0.5 (contrast degradation)',
        'target': "<div style={{ fontSize: '12px', opacity: 0.9 }}>",
        'replacement': "<div style={{ fontSize: '12px', opacity: 0.5 }}>",
        'expected_guard': 'Test 9f-2 (Light/Dark text contrast < 4.5:1 with opacity 0.50 on subtle background)',
    },
    {
        'id': 'M6',
        'name': 'operator input border re-injects opacity 0.8 (border contrast < 3.0:1)',
        'target': "color: 'var(--color-text-primary)',\n              }}\n            />",
        'replacement': "color: 'var(--color-text-primary)',\n                opacity: currentUser ? 0.8 : 1,\n              }}\n            />",
        'expected_guard': 'Test 9f-2 (Light/Dark border contrast < 3.0:1 on input with opacity 0.80)',
    },
    {
        'id': 'M7',
        'name': 'unexposed notice text -> text-secondary (contrast / semantic breach)',
        'target': "color: 'var(--color-brand-hover)',\n          fontSize: '12px',",
        'replacement': "color: 'var(--color-text-secondary)',\n          fontSize: '12px',",
        'expected_guard': 'Test 9f (DOM assertion fails: notice text must bind to var(--color-brand-hover))',
    },
    {
        'id': 'M8',
        'name': 'server banner border -> bg-subtle (1:1 border collision)',
        'target': "border: '1px solid var(--color-brand-hover)',\n              color: 'var(--color-brand-hover)',",
        'replacement': "border: '1px solid var(--color-bg-subtle)',\n              color: 'var(--color-brand-hover)',",
        'expected_guard': 'Test 9f-2 (1:1 border collision) and Test 9f (DOM border assertion)',
    },
    {
        'id': 'M9',
        'name': 'auth notice border -> border-subtle (offline semantic breach)',
        'target': "border: '1px solid var(--color-status-offline)',\n            borderRadius: '6px',\n            color: 'var(--color-status-offline)',",
        'replacement': "border: '1px solid var(--color-border-subtle)',\n            borderRadius: '6px',\n            color: 'var(--color-status-offline)',",
        'expected_guard': 'Test 9f (DOM assertion fails: auth notice border must bind to var(--color-status-offline))',
    },
    {
        'id': 'M10',
        'name': 'server banner bg -> text-primary (illegitimate text token as background)',
        'target': "backgroundColor: 'var(--color-bg-subtle)',\n              borderRadius: '6px',",
        'replacement': "backgroundColor: 'var(--color-text-primary)',\n              borderRadius: '6px',",
        'expected_guard': 'Test 9f-2 (Illegitimate background token derived from text token: --color-text-primary)',
    },
]

def run_test():
    web_dir = os.path.join(REPO_ROOT, 'apps', 'web')
    cmd = ['npx.cmd' if sys.platform == 'win32' else 'npx', 'vitest', 'run', 'tests/acc09-contrast-tokens.test.tsx', '-t', 'Card 202|Multiset Inventory']
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
    print(' Card 202 (ACC-09): Reproducible Mutant Test Suite (10 Mutants: B1-B5, M6-M10)')
    print(' Target: apps/web/src/features/deployment/IntranetDeploymentView.tsx')
    print('================================================================================\n')

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

        if target not in original_content:
            print(f'[{i}/{total_count}] {mid}: ERROR - Target string not found in source file!')
            results.append((mid, name, 'ERROR (target not found)', ''))
            continue

        mutated_content = original_content.replace(target, replacement, 1)
        with open(TARGET_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(mutated_content)

        t0 = time.time()
        rc, stdout, stderr = run_test()
        elapsed = time.time() - t0

        # Restore immediately
        with open(TARGET_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(original_content)

        if rc != 0:
            killed_count += 1
            # Extract failure line
            output_lines = (stdout + '\n' + stderr).splitlines()
            err_snips = [line.strip() for line in output_lines if 'AssertionError' in line or 'violations' in line or 'FAIL' in line or 'Expected' in line or '1:1' in line]
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
