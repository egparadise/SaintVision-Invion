#!/usr/bin/env python3
"""
tools/test_c213_mutations.py

Card 213 (ACC-09) Runs execution record screens (SealRecordPanel & RunDetail) Mutation Testing Suite.
Verifies that 13 distinct regressions/mutations (M1-M13) across
color contrast, border collisions, status semantics, testid binding,
and fail-closed multiset inventory are strictly caught and killed by the test suite
(ACC-09 Test 9h, Test 9h-2, and Test 10).

Usage:
    python tools/test_c213_mutations.py
"""

import sys
import os
import atexit
import subprocess
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SEAL_FILE = os.path.join(REPO_ROOT, 'apps', 'web', 'src', 'features', 'runs', 'SealRecordPanel.tsx')
RUN_FILE = os.path.join(REPO_ROOT, 'apps', 'web', 'src', 'features', 'runs', 'RunDetail.tsx')

original_seal = None
original_run = None

if os.path.exists(SEAL_FILE):
    with open(SEAL_FILE, 'r', encoding='utf-8') as f:
        original_seal = f.read()

if os.path.exists(RUN_FILE):
    with open(RUN_FILE, 'r', encoding='utf-8') as f:
        original_run = f.read()

def cleanup():
    if original_seal is not None and os.path.exists(SEAL_FILE):
        with open(SEAL_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(original_seal)
    if original_run is not None and os.path.exists(RUN_FILE):
        with open(RUN_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(original_run)

atexit.register(cleanup)

MUTANTS = [
    {
        'id': 'M1',
        'file': 'seal',
        'name': 'SealRecordPanel: seal badge status token swapped to degraded (semantic violation)',
        'target': "color: 'var(--color-status-online)',\n                  border: '1px solid var(--color-status-online)',",
        'replacement': "color: 'var(--color-status-degraded)',\n                  border: '1px solid var(--color-status-degraded)',",
        'expected_guard': 'Test 9h (DOM assertion fails: Seal badge color must bind to var(--color-status-online))',
    },
    {
        'id': 'M2',
        'file': 'seal',
        'name': 'SealRecordPanel: seal record ID color swapped to muted (contrast/token regression)',
        'target': 'data-testid="seal-record-id" style={{ fontFamily: \'monospace\', fontWeight: 600, color: \'var(--color-text-primary)\', marginTop: \'2px\' }}',
        'replacement': 'data-testid="seal-record-id" style={{ fontFamily: \'monospace\', fontWeight: 600, color: \'var(--color-text-muted)\', marginTop: \'2px\' }}',
        'expected_guard': 'Test 9h (DOM assertion fails: Seal record ID text must bind to var(--color-text-primary))',
    },
    {
        'id': 'M3',
        'file': 'seal',
        'name': 'SealRecordPanel: re-injects raw hex literal (fail-closed multiset inventory breach)',
        'target': 'export const SealRecordPanel: React.FC<SealRecordPanelProps> = ({',
        'replacement': "const _decoySeal = '#abcdef';\nexport const SealRecordPanel: React.FC<SealRecordPanelProps> = ({",
        'expected_guard': 'Test 10 (Fail-Closed Multiset Inventory: SealRecordPanel multiset must be empty)',
    },
    {
        'id': 'M4',
        'file': 'seal',
        'name': 'SealRecordPanel: missing testid regression (removes seal-status-badge)',
        'target': 'data-testid="seal-status-badge"\n                style={{\n                  fontSize: \'0.75rem\',\n                  fontWeight: 600,\n                  padding: \'2px 8px\',\n                  borderRadius: \'12px\',\n                  backgroundColor: \'var(--color-bg-subtle)\',\n                  color: \'var(--color-status-online)\',',
        'replacement': 'style={{\n                  fontSize: \'0.75rem\',\n                  fontWeight: 600,\n                  padding: \'2px 8px\',\n                  borderRadius: \'12px\',\n                  backgroundColor: \'var(--color-bg-subtle)\',\n                  color: \'var(--color-status-online)\',',
        'expected_guard': 'Test 9h (DOM assertion fails: Seal status badge must render: expected null not to be null)',
    },
    {
        'id': 'M5',
        'file': 'seal',
        'name': 'SealRecordPanel: 1:1 border collision on record ledger card',
        'target': "padding: '8px 12px', backgroundColor: 'var(--color-bg-surface)', border: '1px solid var(--color-border-subtle)', borderRadius: '4px'",
        'replacement': "padding: '8px 12px', backgroundColor: 'var(--color-bg-surface)', border: '1px solid var(--color-bg-surface)', borderRadius: '4px'",
        'expected_guard': 'Test 9h-2 (1:1 border-background collision detected: --color-bg-surface on --color-bg-surface)',
    },
    {
        'id': 'M6',
        'file': 'run',
        'name': 'RunDetail: status succeeded badge color swapped to brand-hover (semantic regression)',
        'target': "run.state === 'succeeded'\n                      ? 'var(--color-status-online)'\n                      : run.state === 'running'",
        'replacement': "run.state === 'succeeded'\n                      ? 'var(--color-brand-hover)'\n                      : run.state === 'running'",
        'expected_guard': 'Test 9h (DOM assertion fails: Succeeded text must bind to var(--color-status-online))',
    },
    {
        'id': 'M7',
        'file': 'run',
        'name': 'RunDetail: status cancelled badge color swapped to offline (semantic violation)',
        'target': "run.state === 'cancelled'\n                      ? 'var(--color-status-neutral)'",
        'replacement': "run.state === 'cancelled'\n                      ? 'var(--color-status-offline)'",
        'expected_guard': 'Test 9h (DOM assertion fails: Cancelled text must bind to var(--color-status-neutral))',
    },
    {
        'id': 'M8',
        'file': 'run',
        'name': 'RunDetail: re-injects raw hex literal (fail-closed multiset inventory breach)',
        'target': 'export const RunDetail: React.FC<RunDetailProps> = ({',
        'replacement': "const _decoyRun = '#abcdef';\nexport const RunDetail: React.FC<RunDetailProps> = ({",
        'expected_guard': 'Test 10 (Fail-Closed Multiset Inventory: RunDetail multiset must be empty)',
    },
    {
        'id': 'M9',
        'file': 'run',
        'name': 'RunDetail: missing testid regression (removes run-detail-status-badge)',
        'target': 'data-testid="run-detail-status-badge"\n                style={{\n                  fontSize: \'0.75rem\',',
        'replacement': 'style={{\n                  fontSize: \'0.75rem\',',
        'expected_guard': 'Test 9h (DOM assertion fails: RunDetail status badge must render: expected null not to be null)',
    },
    {
        'id': 'M10',
        'file': 'run',
        'name': 'RunDetail: 1:1 border collision on cancel modal dialog container',
        'target': "border: '1px solid var(--color-border-subtle)',\n              padding: '24px',\n              maxWidth: '440px',\n              width: '100%',\n              boxShadow: 'var(--shadow-md)',\n            }}\n          >\n            <h3 id=\"run-cancel-modal-title\"",
        'replacement': "border: '1px solid var(--color-bg-surface)',\n              padding: '24px',\n              maxWidth: '440px',\n              width: '100%',\n              boxShadow: 'var(--shadow-md)',\n            }}\n          >\n            <h3 id=\"run-cancel-modal-title\"",
        'expected_guard': 'Test 9h-2 (1:1 border-background collision detected: --color-bg-surface on --color-bg-surface)',
    },
    {
        'id': 'M11',
        'file': 'seal',
        'name': 'SealRecordPanel: unsealed badge status token swapped to online (semantic violation)',
        'target': "color: 'var(--color-status-degraded)',\n                  border: '1px solid var(--color-status-degraded)',",
        'replacement': "color: 'var(--color-status-online)',\n                  border: '1px solid var(--color-status-online)',",
        'expected_guard': 'Test 9h (DOM assertion fails: Unsealed badge color must bind to var(--color-status-degraded))',
    },
    {
        'id': 'M12',
        'file': 'run',
        'name': 'RunDetail: completedAt failed branch status token swapped to online (semantic violation)',
        'target': "color: run.state === 'succeeded' ? 'var(--color-status-online)' : 'var(--color-status-offline)'",
        'replacement': "color: run.state === 'succeeded' ? 'var(--color-status-online)' : 'var(--color-status-online)'",
        'expected_guard': 'Test 9h (DOM assertion fails: Succeeded and failed completedAt must have distinct status tokens)',
    },
    {
        'id': 'M13',
        'file': 'run',
        'name': 'RunDetail: attempt exitCode != 0 status token swapped to online (semantic violation)',
        'target': "style={{ color: att.exitCode === 0 ? 'var(--color-status-online)' : 'var(--color-status-offline)' }}",
        'replacement': "style={{ color: att.exitCode === 0 ? 'var(--color-status-online)' : 'var(--color-status-online)' }}",
        'expected_guard': 'Test 9h (DOM assertion fails: ExitCode 0 and non-zero must have distinct status tokens)',
    },
]

def run_test():
    web_dir = os.path.join(REPO_ROOT, 'apps', 'web')
    cmd = ['npx.cmd' if sys.platform == 'win32' else 'npx', 'vitest', 'run', 'tests/acc09-contrast-tokens.test.tsx', '-t', 'Card 213|Multiset Inventory']
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
    print(' Card 213 (ACC-09): Reproducible Mutant Test Suite (13 Mutants: M1-M13)')
    print(' Targets: SealRecordPanel.tsx & RunDetail.tsx')
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
        file_key = m['file']

        target_file = SEAL_FILE if file_key == 'seal' else RUN_FILE
        orig = original_seal if file_key == 'seal' else original_run

        if target not in orig:
            print(f'[{i:02d}/{total_count}] {mid}: ERROR - Target string not found in {os.path.basename(target_file)}!')
            results.append((mid, name, 'ERROR (target not found)', ''))
            continue

        mutated_content = orig.replace(target, replacement, 1)
        with open(target_file, 'w', encoding='utf-8', newline='\n') as f:
            f.write(mutated_content)

        t0 = time.time()
        rc, stdout, stderr = run_test()
        elapsed = time.time() - t0

        # Restore immediately
        with open(target_file, 'w', encoding='utf-8', newline='\n') as f:
            f.write(orig)

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
