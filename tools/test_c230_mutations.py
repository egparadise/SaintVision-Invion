#!/usr/bin/env python3
"""
tools/test_c230_mutations.py

Card 230 (ACC-09) Desktop Shell screen (DesktopShell.tsx) Mutation Testing Suite.
Verifies that 37 distinct regressions/mutations (Y1-Y37) across
color contrast, border collisions, status semantics, wire contract enum purity,
fail-closed unknown handling, prototype key defense, outline suppression, and token inventory
are strictly caught and killed by the test suite (ACC-09 Test 9n, Test 9j-2, and Test 10).

Usage:
    python tools/test_c230_mutations.py
"""

import sys
import os
import atexit
import subprocess
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SHELL_FILE = os.path.join(REPO_ROOT, 'apps', 'web', 'src', 'features', 'desktop', 'DesktopShell.tsx')

original_shell = None

if os.path.exists(SHELL_FILE):
    with open(SHELL_FILE, 'r', encoding='utf-8') as f:
        original_shell = f.read()

def cleanup():
    if original_shell is not None and os.path.exists(SHELL_FILE):
        with open(SHELL_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(original_shell)

atexit.register(cleanup)

MUTANTS = [
    # 1. fg == bg (1:1 collision)
    {
        'id': 'Y1',
        'name': 'DesktopShell: error notification config bg -> status-offline (fg==bg collision)',
        'target': "  error: {\n    color: 'var(--color-status-offline)',\n    bg: 'var(--color-bg-subtle)',",
        'replacement': "  error: {\n    color: 'var(--color-status-offline)',\n    bg: 'var(--color-status-offline)',",
        'expected_guard': 'Test 9j-2 (1:1 collision) & Test 9n',
    },
    {
        'id': 'Y2',
        'name': 'DesktopShell: success notification config bg -> status-online (fg==bg collision)',
        'target': "  success: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',",
        'replacement': "  success: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-status-online)',",
        'expected_guard': 'Test 9j-2 (1:1 collision) & Test 9n',
    },
    {
        'id': 'Y3',
        'name': 'DesktopShell: info notification config bg -> brand-hover (fg==bg collision)',
        'target': "  info: {\n    color: 'var(--color-brand-hover)',\n    bg: 'var(--color-bg-subtle)',",
        'replacement': "  info: {\n    color: 'var(--color-brand-hover)',\n    bg: 'var(--color-brand-hover)',",
        'expected_guard': 'Test 9j-2 (1:1 collision) & Test 9n',
    },
    {
        'id': 'Y4',
        'name': 'DesktopShell: warning notification config bg -> status-degraded (fg==bg collision)',
        'target': "  warning: {\n    color: 'var(--color-status-degraded)',\n    bg: 'var(--color-bg-subtle)',",
        'replacement': "  warning: {\n    color: 'var(--color-status-degraded)',\n    bg: 'var(--color-status-degraded)',",
        'expected_guard': 'Test 9j-2 (1:1 collision) & Test 9n',
    },
    {
        'id': 'Y5',
        'name': 'DesktopShell: notification badge color -> notifCfg.bg (fg==bg collision in badge DOM)',
        'target': "                      backgroundColor: notifCfg.bg,\n                      color: notifCfg.color,",
        'replacement': "                      backgroundColor: notifCfg.bg,\n                      color: notifCfg.bg,",
        'expected_guard': 'Test 9n (DOM badge fg/bg match)',
    },
    {
        'id': 'Y6',
        'name': 'DesktopShell: unknown fallback color -> bg-subtle (fg==bg collision on fallback)',
        'target': "    color: 'var(--color-status-unknown)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-unknown)',",
        'replacement': "    color: 'var(--color-bg-subtle)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-unknown)',",
        'expected_guard': 'Test 9n (unknown level contrast check)',
    },

    # 2. border == bg (border collision)
    {
        'id': 'Y7',
        'name': 'DesktopShell: error notification border -> bg-subtle (border==bg collision)',
        'target': "  error: {\n    color: 'var(--color-status-offline)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-offline)',",
        'replacement': "  error: {\n    color: 'var(--color-status-offline)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-bg-subtle)',",
        'expected_guard': 'Test 9j-2 (border collision) & Test 9n',
    },
    {
        'id': 'Y8',
        'name': 'DesktopShell: success notification border -> bg-subtle (border==bg collision)',
        'target': "  success: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-online)',",
        'replacement': "  success: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-bg-subtle)',",
        'expected_guard': 'Test 9j-2 (border collision) & Test 9n',
    },
    {
        'id': 'Y9',
        'name': 'DesktopShell: notification badge border -> notifCfg.bg (border==bg collision in badge DOM)',
        'target': "                      color: notifCfg.color,\n                      border: `1px solid ${notifCfg.border}`,",
        'replacement': "                      color: notifCfg.color,\n                      border: `1px solid ${notifCfg.bg}`,",
        'expected_guard': 'Test 9n (DOM badge border match)',
    },
    {
        'id': 'Y10',
        'name': 'DesktopShell: dock tile inactive border -> bg-subtle (border==bg collision in dock tile)',
        'target': "border: isActive ? '1.5px solid var(--color-brand-hover)' : '1px solid var(--color-border-subtle)',",
        'replacement': "border: isActive ? '1.5px solid var(--color-brand-hover)' : '1px solid var(--color-bg-subtle)',",
        'expected_guard': 'Test 9j-2 (border collision in conditional style)',
    },

    # 3. Text token as background
    {
        'id': 'Y11',
        'name': 'DesktopShell: notification item background -> text-secondary (text token as bg)',
        'target': "                  backgroundColor: 'var(--color-bg-subtle)',\n                  border: '1px solid var(--color-border-subtle)',",
        'replacement': "                  backgroundColor: 'var(--color-text-secondary)',\n                  border: '1px solid var(--color-border-subtle)',",
        'expected_guard': 'Test 9j-2 (illegitimate background token derived from text token)',
    },
    {
        'id': 'Y12',
        'name': 'DesktopShell: header background -> text-primary (text token as bg)',
        'target': "          backgroundColor: 'var(--color-bg-surface)',\n          backdropFilter: 'blur(16px)',",
        'replacement': "          backgroundColor: 'var(--color-text-primary)',\n          backdropFilter: 'blur(16px)',",
        'expected_guard': 'Test 9j-2 (illegitimate background token derived from text token)',
    },

    # 4. Degraded opacity
    {
        'id': 'Y13',
        'name': 'DesktopShell: notification badge opacity degraded to 0.4',
        'target': "                      color: notifCfg.color,\n                      border: `1px solid ${notifCfg.border}`,",
        'replacement': "                      color: notifCfg.color,\n                      opacity: 0.4,\n                      border: `1px solid ${notifCfg.border}`,",
        'expected_guard': 'Test 9n (badge opacity assertion)',
    },
    {
        'id': 'Y14',
        'name': 'DesktopShell: mode switcher button opacity degraded to 0.45',
        'target': "              color: 'var(--color-brand-hover)',\n              cursor: 'pointer',",
        'replacement': "              color: 'var(--color-brand-hover)',\n              opacity: 0.45,\n              cursor: 'pointer',",
        'expected_guard': 'Test 9n (mode switcher opacity assertion)',
    },

    # 5. Comment decoys
    {
        'id': 'Y15',
        'name': 'DesktopShell: success color with comment decoy literal',
        'target': "  success: {\n    color: 'var(--color-status-online)',",
        'replacement': "  success: {\n    color: 'var(--color-status-online) /* #3fb950 */',",
        'expected_guard': 'Test 9n (strict token equality) & Test 9j-2',
    },
    {
        'id': 'Y16',
        'name': 'DesktopShell: unknown fallback border with comment decoy literal',
        'target': "    border: 'var(--color-status-unknown)',\n    label: level ? `UNKNOWN (${level})` : 'UNKNOWN',",
        'replacement': "    border: 'var(--color-status-unknown) /* #8b949e */',\n    label: level ? `UNKNOWN (${level})` : 'UNKNOWN',",
        'expected_guard': 'Test 9n (strict token equality)',
    },

    # 6. Token reverts
    {
        'id': 'Y17',
        'name': 'DesktopShell: mode switcher button color reverted to legacy literal #60a5fa',
        'target': "              color: 'var(--color-brand-hover)',\n              cursor: 'pointer',",
        'replacement': "              color: '#60a5fa',\n              cursor: 'pointer',",
        'expected_guard': 'Test 10 (multiset baseline violation) & Test 9j-2',
    },
    {
        'id': 'Y18',
        'name': 'DesktopShell: notification unread dot backgroundColor reverted to legacy literal #ef4444',
        'target': "                  backgroundColor: 'var(--color-status-offline)',\n                }}",
        'replacement': "                  backgroundColor: '#ef4444',\n                }}",
        'expected_guard': 'Test 10 (multiset baseline violation) & Test 9j-2',
    },
    {
        'id': 'Y19',
        'name': 'DesktopShell: start menu trigger color reverted to legacy literal #38bdf8',
        'target': "              color: 'var(--color-brand-hover)',\n              background: 'none',",
        'replacement': "              color: '#38bdf8',\n              background: 'none',",
        'expected_guard': 'Test 10 (multiset baseline violation) & Test 9j-2',
    },

    # 7. State collapse
    {
        'id': 'Y20',
        'name': 'DesktopShell: warning notification color collapsed to status-online',
        'target': "  warning: {\n    color: 'var(--color-status-degraded)',",
        'replacement': "  warning: {\n    color: 'var(--color-status-online)',",
        'expected_guard': 'Test 9n (warning badge color assertion)',
    },
    {
        'id': 'Y21',
        'name': 'DesktopShell: error notification color collapsed to status-online',
        'target': "  error: {\n    color: 'var(--color-status-offline)',",
        'replacement': "  error: {\n    color: 'var(--color-status-online)',",
        'expected_guard': 'Test 9n (error badge color assertion)',
    },
    {
        'id': 'Y22',
        'name': 'DesktopShell: info notification color collapsed to status-offline',
        'target': "  info: {\n    color: 'var(--color-brand-hover)',",
        'replacement': "  info: {\n    color: 'var(--color-status-offline)',",
        'expected_guard': 'Test 9n (info badge color assertion)',
    },

    # 8. Label / Non-color preservation
    {
        'id': 'Y23',
        'name': 'DesktopShell: notification badge SUCCESS label changed to OK',
        'target': "  success: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-online)',\n    label: 'SUCCESS',",
        'replacement': "  success: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-online)',\n    label: 'OK',",
        'expected_guard': 'Test 9n (SUCCESS label exact equality)',
    },
    {
        'id': 'Y24',
        'name': 'DesktopShell: notification badge ERROR label changed to FAIL',
        'target': "  error: {\n    color: 'var(--color-status-offline)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-offline)',\n    label: 'ERROR',",
        'replacement': "  error: {\n    color: 'var(--color-status-offline)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-offline)',\n    label: 'FAIL',",
        'expected_guard': 'Test 9n (ERROR label exact equality)',
    },
    {
        'id': 'Y25',
        'name': 'DesktopShell: notification badge INFO label changed to 안내',
        'target': "  info: {\n    color: 'var(--color-brand-hover)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-brand-hover)',\n    label: 'INFO',",
        'replacement': "  info: {\n    color: 'var(--color-brand-hover)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-brand-hover)',\n    label: '안내',",
        'expected_guard': 'Test 9n (INFO label exact equality)',
    },
    {
        'id': 'Y26',
        'name': 'DesktopShell: notification badge DOM altered with extra exclamation suffix',
        'target': "{notifCfg.label}\n                  </span>",
        'replacement': "{notifCfg.label + '!'}\n                  </span>",
        'expected_guard': 'Test 9n (badge label exact text)',
    },

    # 9. Outline suppression
    {
        'id': 'Y27',
        'name': 'DesktopShell: mode switcher button outline suppressed with outline: none',
        'target': "              color: 'var(--color-brand-hover)',\n              cursor: 'pointer',",
        'replacement': "              color: 'var(--color-brand-hover)',\n              outline: 'none',\n              cursor: 'pointer',",
        'expected_guard': 'Test 9j-2 (outline suppression guard) & Test 9n',
    },
    {
        'id': 'Y28',
        'name': 'DesktopShell: mode switcher button outline suppressed with outlineWidth: 0px',
        'target': "              color: 'var(--color-brand-hover)',\n              cursor: 'pointer',",
        'replacement': "              color: 'var(--color-brand-hover)',\n              outlineWidth: '0px',\n              cursor: 'pointer',",
        'expected_guard': 'Test 9j-2 (outlineWidth: 0 guard) & Test 9n',
    },
    {
        'id': 'Y29',
        'name': 'DesktopShell: start menu trigger outline suppressed with outline: none as const',
        'target': "              color: 'var(--color-brand-hover)',\n              background: 'none',",
        'replacement': "              color: 'var(--color-brand-hover)',\n              outline: 'none' as const,\n              background: 'none',",
        'expected_guard': 'Test 9j-2 (AsExpression unwrap outline guard) & Test 9n',
    },
    {
        'id': 'Y30',
        'name': 'DesktopShell: dock button outline suppressed with outline: 0',
        'target': "                  padding: '4px',\n                  borderRadius: '10px',",
        'replacement': "                  padding: '4px',\n                  outline: '0',\n                  borderRadius: '10px',",
        'expected_guard': 'Test 9j-2 (outline: 0 suppression guard)',
    },

    # 10. Fail-closed unknown handling
    {
        'id': 'Y31',
        'name': 'DesktopShell: getNotificationLevelConfig null/empty returns info (fail-open fallback bypass)',
        'target': "export function getNotificationLevelConfig(level?: string | null): NotificationLevelStyle {\n  if (level && Object.hasOwn(NOTIFICATION_LEVEL_CONFIG, level)) {",
        'replacement': "export function getNotificationLevelConfig(level?: string | null): NotificationLevelStyle {\n  if (!level) return NOTIFICATION_LEVEL_CONFIG.info;\n  if (level && Object.hasOwn(NOTIFICATION_LEVEL_CONFIG, level)) {",
        'expected_guard': 'Test 9n (null fallback assertion)',
    },
    {
        'id': 'Y32',
        'name': 'DesktopShell: getNotificationLevelConfig unknown fallback returns info config',
        'target': "  return {\n    color: 'var(--color-status-unknown)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-unknown)',\n    label: level ? `UNKNOWN (${level})` : 'UNKNOWN',\n  };",
        'replacement': "  return NOTIFICATION_LEVEL_CONFIG.info;",
        'expected_guard': 'Test 9n (unknown fallback assertion)',
    },
    {
        'id': 'Y33',
        'name': 'DesktopShell: getNotificationLevelConfig uses in operator instead of Object.hasOwn',
        'target': "  if (level && Object.hasOwn(NOTIFICATION_LEVEL_CONFIG, level)) {",
        'replacement': "  if (level && level in NOTIFICATION_LEVEL_CONFIG) {",
        'expected_guard': 'Test 9n (prototype key toString/constructor hijack defense)',
    },

    # 11. Wire contract enum purity
    {
        'id': 'Y34',
        'name': 'DesktopShell: out-of-contract level (critical) added to NOTIFICATION_LEVEL_CONFIG',
        'target': "export const NOTIFICATION_LEVEL_CONFIG = {",
        'replacement': "export const NOTIFICATION_LEVEL_CONFIG = {\n  critical: { color: 'var(--color-status-offline)', bg: 'var(--color-bg-subtle)', border: 'var(--color-status-offline)', label: 'CRITICAL' },",
        'expected_guard': 'Test 9n (key set equality assertion)',
    },
    {
        'id': 'Y35',
        'name': 'DesktopShell: contract level (error) bypassed in getNotificationLevelConfig (treated as unknown)',
        'target': "export function getNotificationLevelConfig(level?: string | null): NotificationLevelStyle {\n  if (level && Object.hasOwn(NOTIFICATION_LEVEL_CONFIG, level)) {",
        'replacement': "export function getNotificationLevelConfig(level?: string | null): NotificationLevelStyle {\n  if (level && level !== 'error' && Object.hasOwn(NOTIFICATION_LEVEL_CONFIG, level)) {",
        'expected_guard': 'Test 9n (ERROR badge exact token and label)',
    },

    # 12. Named colors injection
    {
        'id': 'Y36',
        'name': 'DesktopShell: success config border injected with named color green',
        'target': "  success: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-online)',",
        'replacement': "  success: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'green',",
        'expected_guard': 'Test 9j-2 (named color guard)',
    },
    {
        'id': 'Y37',
        'name': 'DesktopShell: header text color injected with named color white',
        'target': "          color: 'var(--color-text-primary)',\n          fontSize: '0.8125rem',",
        'replacement': "          color: 'white',\n          fontSize: '0.8125rem',",
        'expected_guard': 'Test 9j-2 (named color guard)',
    },

    # 13. Label formatting & Case sensitivity (Codex r1 & Claude r1 verification)
    {
        'id': 'Y38',
        'name': 'DesktopShell: getNotificationLevelConfig fallback label drops UNKNOWN prefix (raw level)',
        'target': "    label: level ? `UNKNOWN (${level})` : 'UNKNOWN',",
        'replacement': "    label: level ? level : 'UNKNOWN',",
        'expected_guard': 'Test 9n (UNKNOWN prefix guard on out-of-contract levels)',
    },
    {
        'id': 'Y39',
        'name': 'DesktopShell: getNotificationLevelConfig fallback label converts raw level to uppercase',
        'target': "    label: level ? `UNKNOWN (${level})` : 'UNKNOWN',",
        'replacement': "    label: (level || 'UNKNOWN').toUpperCase(),",
        'expected_guard': 'Test 9n (casing preservation and UNKNOWN wrapper guard)',
    },
    {
        'id': 'Y40',
        'name': 'DesktopShell: getNotificationLevelConfig normalizes case with toLowerCase() (case-insensitive bypass)',
        'target': "  if (level && Object.hasOwn(NOTIFICATION_LEVEL_CONFIG, level)) {",
        'replacement': "  if (level && Object.hasOwn(NOTIFICATION_LEVEL_CONFIG, level.toLowerCase())) {",
        'expected_guard': 'Test 9n (case-insensitive lookup defense for non-canonical keys)',
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
    print(' Card 230 (ACC-09): Reproducible Mutant Test Suite (37 Mutants: Y1-Y37)')
    print(' Target: DesktopShell.tsx')
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

        if target not in original_shell:
            print(f'[{i:02d}/{total_mutants}] {mid}: ERROR - Target snippet not found in DesktopShell.tsx!')
            results.append((mid, mname, 'ERROR_TARGET_NOT_FOUND', 'Target snippet not found'))
            continue

        mutated_code = original_shell.replace(target, replacement, 1)
        with open(SHELL_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(mutated_code)

        start_time = time.time()
        test_rc, test_out, test_err = run_test_suite()
        elapsed = time.time() - start_time

        # Restore immediately
        with open(SHELL_FILE, 'w', encoding='utf-8', newline='\n') as f:
            f.write(original_shell)

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
