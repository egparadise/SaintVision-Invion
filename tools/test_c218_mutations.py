#!/usr/bin/env python3
"""
tools/test_c218_mutations.py

Card 218 (ACC-09) Distributed Recovery screen (DistributedRecoveryView.tsx) Mutation Testing Suite.
Verifies that 18 distinct regressions/mutations (M1-M18) across
color contrast, border collisions, status semantics, testid binding,
outline focus ring preservation, non-color label distinctness,
and fail-closed multiset inventory are strictly caught and killed by the test suite
(ACC-09 Test 9j, Test 9j-2, and Test 10).

Usage:
    python tools/test_c218_mutations.py
"""

import sys
import os
import atexit
import subprocess
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RECOVERY_FILE = os.path.join(REPO_ROOT, 'apps', 'web', 'src', 'features', 'recovery', 'DistributedRecoveryView.tsx')

original_recovery = None

if os.path.exists(RECOVERY_FILE):
    with open(RECOVERY_FILE, 'r', encoding='utf-8') as f:
        original_recovery = f.read()

def cleanup():
    if original_recovery is not None and os.path.exists(RECOVERY_FILE):
        with open(RECOVERY_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(original_recovery)

atexit.register(cleanup)

MUTANTS = [
    {
        'id': 'M1 (A1)',
        'name': 'DistributedRecoveryView: notice banner bg -> brand-hover (fg==bg collision)',
        'target': "        style={{\n          padding: '12px 16px',\n          backgroundColor: 'var(--color-bg-subtle)',\n          border: '1px solid var(--color-brand-hover)',\n          borderRadius: 'var(--radius-md)',\n          color: 'var(--color-brand-hover)',",
        'replacement': "        style={{\n          padding: '12px 16px',\n          backgroundColor: 'var(--color-brand-hover)',\n          border: '1px solid var(--color-brand-hover)',\n          borderRadius: 'var(--radius-md)',\n          color: 'var(--color-brand-hover)',",
        'expected_guard': 'Test 9j-2 / Test 9j (1:1 collision between bg and fg)',
    },
    {
        'id': 'M2 (A2)',
        'name': 'DistributedRecoveryView: NODE_HEALTH_CONFIG.online.bg -> status-online (fg==bg collision)',
        'target': "  online: {\n    label: 'ONLINE',\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-online)',\n  },",
        'replacement': "  online: {\n    label: 'ONLINE',\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-status-online)',\n    border: 'var(--color-status-online)',\n  },",
        'expected_guard': 'Test 9j-2 (AST guard: 1:1 collision) & Test 9j (DOM contrast check)',
    },
    {
        'id': 'M3 (A3)',
        'name': 'DistributedRecoveryView: NODE_HEALTH_CONFIG.fenced.bg -> text-secondary (text token as bg)',
        'target': "  fenced: {\n    label: 'FENCED',\n    color: 'var(--color-status-neutral)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-border-strong)',\n  },",
        'replacement': "  fenced: {\n    label: 'FENCED',\n    color: 'var(--color-status-neutral)',\n    bg: 'var(--color-text-secondary)',\n    border: 'var(--color-border-strong)',\n  },",
        'expected_guard': 'Test 9j-2 (AST guard: text token background)',
    },
    {
        'id': 'M4 (A4)',
        'name': 'DistributedRecoveryView: node card unselected border -> bg-surface (border==bg collision)',
        'target': "                      border: isSelected ? '2px solid var(--color-brand-hover)' : '1px solid var(--color-border-subtle)',",
        'replacement': "                      border: isSelected ? '2px solid var(--color-brand-hover)' : '1px solid var(--color-bg-surface)',",
        'expected_guard': 'Test 9j-2 (AST guard: border-background collision) & Test 9j',
    },
    {
        'id': 'M5 (B1)',
        'name': 'DistributedRecoveryView: unselected node card given inline outline: "none" (destroying :focus-visible keyboard focus ring)',
        'target': "                      border: isSelected ? '2px solid var(--color-brand-hover)' : '1px solid var(--color-border-subtle)',",
        'replacement': "                      border: isSelected ? '2px solid var(--color-brand-hover)' : '1px solid var(--color-border-subtle)',\n                      outline: 'none',",
        'expected_guard': 'Test 9j (DOM assertion: nodeCard2 outline must be empty string to preserve :focus-visible)',
    },
    {
        'id': 'M6 (C1)',
        'name': 'DistributedRecoveryView: status badge opacity degraded to 0.4',
        'target': "                        <span\n                          data-testid={`node-sim-status-${node.nodeId}`}\n                          style={{\n                            padding: '2px 8px',\n                            borderRadius: 'var(--radius-sm)',\n                            fontSize: '11px',\n                            fontWeight: 700,\n                            backgroundColor: healthCfg.bg,\n                            color: healthCfg.color,\n                            border: `1px solid ${healthCfg.border}`,\n                          }}",
        'replacement': "                        <span\n                          data-testid={`node-sim-status-${node.nodeId}`}\n                          style={{\n                            padding: '2px 8px',\n                            borderRadius: 'var(--radius-sm)',\n                            fontSize: '11px',\n                            fontWeight: 700,\n                            opacity: 0.4,\n                            backgroundColor: healthCfg.bg,\n                            color: healthCfg.color,\n                            border: `1px solid ${healthCfg.border}`,\n                          }}",
        'expected_guard': 'Test 9j (DOM assertion: Badge opacity must not be degraded)',
    },
    {
        'id': 'M7 (D1)',
        'name': 'DistributedRecoveryView: NODE_HEALTH_CONFIG.online.color reverted to legacy literal #3fb950',
        'target': "  online: {\n    label: 'ONLINE',\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-online)',\n  },",
        'replacement': "  online: {\n    label: 'ONLINE',\n    color: '#3fb950',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-online)',\n  },",
        'expected_guard': 'Test 10 (Fail-closed multiset inventory: unregistered literal #3fb950)',
    },
    {
        'id': 'M8 (D2)',
        'name': 'DistributedRecoveryView: recovering color reverted to legacy literal #58a6ff',
        'target': "  recovering: {\n    label: 'RECOVERING',\n    color: 'var(--color-status-active)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-active)',\n  },",
        'replacement': "  recovering: {\n    label: 'RECOVERING',\n    color: '#58a6ff',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-active)',\n  },",
        'expected_guard': 'Test 10 (Fail-closed multiset inventory: unregistered literal #58a6ff) & Test 9j',
    },
    {
        'id': 'M9 (F1)',
        'name': 'DistributedRecoveryView: recovering color collapsed to status-neutral (fenced collision)',
        'target': "  recovering: {\n    label: 'RECOVERING',\n    color: 'var(--color-status-active)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-active)',\n  },",
        'replacement': "  recovering: {\n    label: 'RECOVERING',\n    color: 'var(--color-status-neutral)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-active)',\n  },",
        'expected_guard': 'Test 9j (DOM assertion: uniqueColors.size must be 5 & recovering color must match active token)',
    },
    {
        'id': 'M10 (F2)',
        'name': 'DistributedRecoveryView: recovering color collapsed to status-online (online collision)',
        'target': "  recovering: {\n    label: 'RECOVERING',\n    color: 'var(--color-status-active)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-active)',\n  },",
        'replacement': "  recovering: {\n    label: 'RECOVERING',\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-active)',\n  },",
        'expected_guard': 'Test 9j (DOM assertion: uniqueColors.size must be 5 & recovering color must match active token)',
    },
    {
        'id': 'M11 (G1)',
        'name': 'DistributedRecoveryView: status badge text label {healthCfg.label} removed',
        'target': "                          시뮬레이션: {healthCfg.label}\n                        </span>",
        'replacement': "                          시뮬레이션: {/* label removed */}\n                        </span>",
        'expected_guard': 'Test 9j (DOM assertion: simBadgeOnline textContent must be 시뮬레이션: ONLINE)',
    },
    {
        'id': 'M12 (E1)',
        'name': 'DistributedRecoveryView: action notice error border swapped to status-online',
        'target': "            border: `1px solid ${\n              actionNotice.type === 'error'\n                ? 'var(--color-status-offline)'\n                : actionNotice.type === 'success'\n                ? 'var(--color-status-online)'\n                : 'var(--color-brand-hover)'\n            }`,",
        'replacement': "            border: `1px solid ${\n              actionNotice.type === 'error'\n                ? 'var(--color-status-online)'\n                : actionNotice.type === 'success'\n                ? 'var(--color-status-online)'\n                : 'var(--color-brand-hover)'\n            }`,",
        'expected_guard': 'Test 9j (DOM assertion: Action notice error border must be status-offline)',
    },
    {
        'id': 'M13 (E2)',
        'name': 'DistributedRecoveryView: KPI zombie writes color swapped to text-secondary',
        'target': "          <div\n            data-testid=\"kpi-zombie-writes\"\n            style={{ fontSize: '20px', fontWeight: 700, color: 'var(--color-status-online)', marginTop: '4px' }}\n          >",
        'replacement': "          <div\n            data-testid=\"kpi-zombie-writes\"\n            style={{ fontSize: '20px', fontWeight: 700, color: 'var(--color-text-secondary)', marginTop: '4px' }}\n          >",
        'expected_guard': 'Test 9j (DOM assertion: zombieCount color must be status-online)',
    },
    {
        'id': 'M14 (E3)',
        'name': 'DistributedRecoveryView: rejection item border swapped to border-subtle',
        'target': "                      data-testid={`rejection-item-${rej.requestId}`}\n                      style={{\n                        backgroundColor: 'var(--color-bg-subtle)',\n                        border: '1px solid var(--color-status-offline)',\n                        borderRadius: 'var(--radius-md)',\n                        padding: '8px 12px',\n                        fontSize: '12px',\n                      }}",
        'replacement': "                      data-testid={`rejection-item-${rej.requestId}`}\n                      style={{\n                        backgroundColor: 'var(--color-bg-subtle)',\n                        border: '1px solid var(--color-border-subtle)',\n                        borderRadius: 'var(--radius-md)',\n                        padding: '8px 12px',\n                        fontSize: '12px',\n                      }}",
        'expected_guard': 'Test 9j (DOM assertion: rejItem border must be status-offline)',
    },
    {
        'id': 'M15 (E4)',
        'name': 'DistributedRecoveryView: empty screen border swapped to bg-surface (border==bg collision)',
        'target': "          data-testid=\"recovery-empty-nodes-screen\"\n          style={{\n            padding: '48px 24px',\n            textAlign: 'center',\n            backgroundColor: 'var(--color-bg-surface)',\n            border: '1px solid var(--color-border-subtle)',\n            borderRadius: 'var(--radius-lg)',\n            display: 'flex',\n            flexDirection: 'column',\n            alignItems: 'center',\n            gap: '12px',\n          }}",
        'replacement': "          data-testid=\"recovery-empty-nodes-screen\"\n          style={{\n            padding: '48px 24px',\n            textAlign: 'center',\n            backgroundColor: 'var(--color-bg-surface)',\n            border: '1px solid var(--color-bg-surface)',\n            borderRadius: 'var(--radius-lg)',\n            display: 'flex',\n            flexDirection: 'column',\n            alignItems: 'center',\n            gap: '12px',\n          }}",
        'expected_guard': 'Test 9j-2 (AST guard: border-bg collision) & Test 9j',
    },
    {
        'id': 'M16 (F3)',
        'name': 'DistributedRecoveryView: fenced border token reverted from border-strong to border-subtle',
        'target': "  fenced: {\n    label: 'FENCED',\n    color: 'var(--color-status-neutral)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-border-strong)',\n  },",
        'replacement': "  fenced: {\n    label: 'FENCED',\n    color: 'var(--color-status-neutral)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-border-subtle)',\n  },",
        'expected_guard': 'Test 9j (DOM assertion: fenced border must match border-strong token)',
    },
    {
        'id': 'M17 (G2)',
        'name': 'DistributedRecoveryView: recovering label set to empty string (M8a non-color a11y)',
        'target': "  recovering: {\n    label: 'RECOVERING',\n    color: 'var(--color-status-active)',",
        'replacement': "  recovering: {\n    label: '',\n    color: 'var(--color-status-active)',",
        'expected_guard': 'Test 9j (DOM / Config assertion: all health labels must be non-empty and recovering label must be RECOVERING)',
    },
    {
        'id': 'M18 (G3)',
        'name': 'DistributedRecoveryView: recovering label collapsed to ONLINE (M8d non-color state collapse)',
        'target': "  recovering: {\n    label: 'RECOVERING',\n    color: 'var(--color-status-active)',",
        'replacement': "  recovering: {\n    label: 'ONLINE',\n    color: 'var(--color-status-active)',",
        'expected_guard': 'Test 9j (DOM / Config assertion: all 5 labels must be distinct and recovering label must be RECOVERING)',
    },
]

def run_test():
    web_dir = os.path.join(REPO_ROOT, 'apps', 'web')
    cmd = ['npx.cmd' if sys.platform == 'win32' else 'npx', 'vitest', 'run', 'tests/acc09-contrast-tokens.test.tsx', '-t', 'Card 218|Multiset Inventory']
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
    print(' Card 218 (ACC-09): Reproducible Mutant Test Suite (18 Mutants: M1-M18)')
    print(' Target: DistributedRecoveryView.tsx')
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

        if target not in original_recovery:
            print(f'[{i:02d}/{total_count}] {mid}: ERROR - Target string not found in DistributedRecoveryView.tsx!')
            results.append((mid, name, 'ERROR (target not found)', ''))
            continue

        mutated_content = original_recovery.replace(target, replacement, 1)
        with open(RECOVERY_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(mutated_content)

        t0 = time.time()
        rc, stdout, stderr = run_test()
        elapsed = time.time() - t0

        # Restore immediately
        with open(RECOVERY_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(original_recovery)

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
