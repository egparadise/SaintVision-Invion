#!/usr/bin/env python3
"""
tools/test_c206_mutations.py

Card 206 (ACC-09) DeveloperStudio Mutation Testing Suite.
Verifies that 10 distinct regressions/mutations (M1-M10) across
color contrast, opacity, border collisions, status semantics, testid binding,
and fail-closed multiset inventory are strictly caught and killed by the test suite
(ACC-09 Test 2, Test 9g, Test 9g-2, and Test 10).

Usage:
    python tools/test_c206_mutations.py
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
TARGET_FILE = os.path.join(REPO_ROOT, 'apps', 'web', 'src', 'features', 'studio', 'DeveloperStudio.tsx')
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
        'id': 'M1',
        'name': 'status running token swapped to text-muted (grey)',
        'target': ": currentRun?.state === 'running'\n                          ? 'var(--color-brand-hover)'",
        'replacement': ": currentRun?.state === 'running'\n                          ? 'var(--color-text-muted)'",
        'expected_guard': 'Test 9g (DOM assertion fails: Running status text must bind to var(--color-brand-hover))',
    },
    {
        'id': 'M2',
        'name': 'status succeeded border swapped to text-primary',
        'target': "border: `1px solid ${\n                        currentRun?.state === 'succeeded'\n                          ? 'var(--color-status-online)'",
        'replacement': "border: `1px solid ${\n                        currentRun?.state === 'succeeded'\n                          ? 'var(--color-text-primary)'",
        'expected_guard': 'Test 9g (DOM assertion fails: Succeeded status border must bind to var(--color-status-online))',
    },
    {
        'id': 'M3',
        'name': 'non-schedulable node card re-injects opacity 0.75 (contrast failure)',
        'target': "style={{\n                    padding: '20px',\n                    borderRadius: 'var(--radius-lg)',\n                    border: `2px solid ${isWinner ? 'var(--color-status-online)' : isSelected ? 'var(--color-brand-primary)' : 'var(--color-border-subtle)'}`,\n                    backgroundColor: 'var(--color-bg-surface)',",
        'replacement': "style={{\n                    padding: '20px',\n                    borderRadius: 'var(--radius-lg)',\n                    border: `2px solid ${isWinner ? 'var(--color-status-online)' : isSelected ? 'var(--color-brand-primary)' : 'var(--color-border-subtle)'}`,\n                    backgroundColor: 'var(--color-bg-surface)',\n                    opacity: isNodeSchedulable ? 1 : 0.75,",
        'expected_guard': 'Test 9g-2 (Light/Dark text contrast < 4.5:1 with opacity 0.75 on surface)',
    },
    {
        'id': 'M4',
        'name': 'active tab borderBottom 1:1 collision with surface background',
        'target': "borderBottom: isCurrent ? '1px solid transparent' : '1px solid var(--color-border-subtle)',",
        'replacement': "borderBottom: isCurrent ? '1px solid var(--color-bg-surface)' : '1px solid var(--color-border-subtle)',",
        'expected_guard': 'Test 9g-2 (1:1 border-background collision detected: --color-bg-surface on --color-bg-surface)',
    },
    {
        'id': 'M5',
        'name': 'stepper active border swapped to subtle border',
        'target': "border: `2px solid ${isActive ? 'var(--color-brand-primary)' : isPassed ? 'var(--color-status-online)' : 'var(--color-border-subtle)'}`,",
        'replacement': "border: `2px solid ${isActive ? 'var(--color-border-subtle)' : isPassed ? 'var(--color-status-online)' : 'var(--color-border-subtle)'}`,",
        'expected_guard': 'Test 9g (DOM assertion fails: Step 1 active border must bind to var(--color-brand-primary))',
    },
    {
        'id': 'M6',
        'name': 'node chip background swapped to surface (fails subtle bg assertion)',
        'target': 'data-testid="studio-node-chip"\n                style={{\n                  padding: \'4px 10px\',\n                  backgroundColor: \'var(--color-bg-subtle)\',',
        'replacement': 'data-testid="studio-node-chip"\n                style={{\n                  padding: \'4px 10px\',\n                  backgroundColor: \'var(--color-bg-surface)\',',
        'expected_guard': 'Test 9g (DOM assertion fails: Node chip bg must bind to var(--color-bg-subtle))',
    },
    {
        'id': 'M7',
        'name': 'multiset decoy literal reintroduced (fail-closed multiset inventory breach)',
        'target': "export const DeveloperStudio: React.FC<DeveloperStudioProps> = ({",
        'replacement': "const _decoyColor = '#abcdef';\nexport const DeveloperStudio: React.FC<DeveloperStudioProps> = ({",
        'expected_guard': 'Test 10 (Fail-Closed Multiset Inventory: DeveloperStudio multiset must be empty)',
    },
    {
        'id': 'M8',
        'name': 'missing testid regression (removes studio-execution-status-badge testid)',
        'target': 'data-testid="studio-execution-status-badge"\n                    style={{',
        'replacement': 'style={{',
        'expected_guard': 'Test 9g (DOM assertion fails: Status badge (running) must render: expected null not to be null)',
    },
    {
        'id': 'M9',
        'name': 'status failed swapped to degraded token (status semantic violation)',
        'target': "                          : 'var(--color-status-offline)',\n                    }}",
        'replacement': "                          : 'var(--color-status-degraded)',\n                    }}",
        'expected_guard': 'Test 9g (DOM assertion fails: Failed status text must bind to var(--color-status-offline))',
    },
    {
        'id': 'M10',
        'name': 'stepper inactive circle background swapped to primary (Test 2 assertion)',
        'target': ": 'var(--color-border-strong)',\n                      color: isActive ? 'var(--color-brand-primary-fg)' : 'var(--color-text-inverse)',",
        'replacement': ": 'var(--color-brand-primary)',\n                      color: isActive ? 'var(--color-brand-primary-fg)' : 'var(--color-text-inverse)',",
        'expected_guard': 'Test 2 (DOM assertion fails: DeveloperStudio inactive step circle background must bind to var(--color-border-strong))',
    },
]

def run_test():
    web_dir = os.path.join(REPO_ROOT, 'apps', 'web')
    cmd = ['npx.cmd' if sys.platform == 'win32' else 'npx', 'vitest', 'run', 'tests/acc09-contrast-tokens.test.tsx', '-t', 'Card 206|Multiset Inventory|DeveloperStudio bind to var']
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
    print(' Card 206 (ACC-09): Reproducible Mutant Test Suite (10 Mutants: M1-M10)')
    print(' Target: apps/web/src/features/studio/DeveloperStudio.tsx')
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
            print(f'[{i:02d}/{total_count}] {mid}: ERROR - Target string not found in source file!')
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
            err_snips = [line.strip() for line in output_lines if 'AssertionError' in line or 'violations' in line or 'FAIL' in line or 'Expected' in line or '1:1' in line or 'exceeded' in line or 'not registered' in line]
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
