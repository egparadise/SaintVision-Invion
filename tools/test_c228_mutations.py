#!/usr/bin/env python3
"""
tools/test_c228_mutations.py

Card 228 (ACC-09) Natural Language Run screen (NaturalLanguageRunView.tsx) Mutation Testing Suite.
Verifies that 34 distinct regressions/mutations (X1-X34) across
color contrast, border collisions, status semantics, wire contract enum purity,
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
    # 1. fg == bg (1:1 collision)
    {
        'id': 'X1',
        'name': 'NaturalLanguageRunView: repairing status config bg -> status-degraded (fg==bg collision)',
        'target': "  repairing: {\n    color: 'var(--color-status-degraded)',\n    bg: 'var(--color-bg-subtle)',",
        'replacement': "  repairing: {\n    color: 'var(--color-status-degraded)',\n    bg: 'var(--color-status-degraded)',",
        'expected_guard': 'Test 9j-2 (1:1 collision) & Test 9m',
    },
    {
        'id': 'X2',
        'name': 'NaturalLanguageRunView: status badge color -> statusCfg.bg (fg==bg collision)',
        'target': "                    backgroundColor: statusCfg.bg,\n                    border: `1px solid ${statusCfg.border}`,\n                    color: statusCfg.color,",
        'replacement': "                    backgroundColor: statusCfg.bg,\n                    border: `1px solid ${statusCfg.border}`,\n                    color: statusCfg.bg,",
        'expected_guard': 'Test 9m (DOM badge fg/bg match)',
    },
    {
        'id': 'X3',
        'name': 'NaturalLanguageRunView: action notice success color -> bg-subtle (fg==bg collision on notice)',
        'target': "actionNotice.type === 'error'\n                    ? 'var(--color-status-offline)'\n                    : actionNotice.type === 'success'\n                    ? 'var(--color-status-online)'\n                    : 'var(--color-brand-hover)'",
        'replacement': "actionNotice.type === 'error'\n                    ? 'var(--color-status-offline)'\n                    : actionNotice.type === 'success'\n                    ? 'var(--color-bg-subtle)'\n                    : 'var(--color-brand-hover)'",
        'expected_guard': 'Test 9j-2 (1:1 collision in conditional style) & Test 9m',
    },
    {
        'id': 'X4',
        'name': 'NaturalLanguageRunView: unknown fallback color -> bg-subtle (fg==bg collision on fallback)',
        'target': "    color: 'var(--color-status-unknown)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-unknown)',",
        'replacement': "    color: 'var(--color-bg-subtle)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-unknown)',",
        'expected_guard': 'Test 9m (unknown status contrast check)',
    },

    # 2. border == bg (1:1 border collision)
    {
        'id': 'X5',
        'name': 'NaturalLanguageRunView: draft status border -> bg-subtle (border==bg collision)',
        'target': "  draft: {\n    color: 'var(--color-text-secondary)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-border-subtle)',",
        'replacement': "  draft: {\n    color: 'var(--color-text-secondary)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-bg-subtle)',",
        'expected_guard': 'Test 9j-2 (1:1 border collision)',
    },
    {
        'id': 'X6',
        'name': 'NaturalLanguageRunView: status badge border -> statusCfg.bg (border==bg collision)',
        'target': "border: `1px solid ${statusCfg.border}`,",
        'replacement': "border: `1px solid ${statusCfg.bg}`,",
        'expected_guard': 'Test 9m (DOM badge border)',
    },
    {
        'id': 'X7',
        'name': 'NaturalLanguageRunView: action notice success border -> bg-subtle (border==bg collision on notice)',
        'target': "border: `1px solid ${\n                  actionNotice.type === 'error'\n                    ? 'var(--color-status-offline)'\n                    : actionNotice.type === 'success'\n                    ? 'var(--color-status-online)'\n                    : 'var(--color-brand-hover)'\n                }`,",
        'replacement': "border: `1px solid ${\n                  actionNotice.type === 'error'\n                    ? 'var(--color-status-offline)'\n                    : actionNotice.type === 'success'\n                    ? 'var(--color-bg-subtle)'\n                    : 'var(--color-brand-hover)'\n                }`,",
        'expected_guard': 'Test 9j-2 (border==bg collision in conditional style)',
    },

    # 3. text token as background
    {
        'id': 'X8',
        'name': 'NaturalLanguageRunView: form textarea background -> text-inverse (text token as bg)',
        'target': "                  backgroundColor: 'var(--color-bg-subtle)',\n                  border: '1px solid var(--color-border-subtle)',\n                  borderRadius: '6px',\n                  color: 'var(--color-text-primary)',",
        'replacement': "                  backgroundColor: 'var(--color-text-inverse)',\n                  border: '1px solid var(--color-border-subtle)',\n                  borderRadius: '6px',\n                  color: 'var(--color-text-primary)',",
        'expected_guard': 'Test 9j-2 (text token background guard)',
    },
    {
        'id': 'X9',
        'name': 'NaturalLanguageRunView: draft config bg -> text-secondary (text token as bg)',
        'target': "  draft: {\n    color: 'var(--color-text-secondary)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-border-subtle)',\n    label: 'DRAFT',",
        'replacement': "  draft: {\n    color: 'var(--color-text-secondary)',\n    bg: 'var(--color-text-secondary)',\n    border: 'var(--color-border-subtle)',\n    label: 'DRAFT',",
        'expected_guard': 'Test 9j-2 (1:1 collision / text token as bg)',
    },

    # 4. opacity degradation
    {
        'id': 'X10',
        'name': 'NaturalLanguageRunView: action notice opacity degraded to 0.45',
        'target': "                padding: '12px 18px',\n                borderRadius: '6px',",
        'replacement': "                padding: '12px 18px',\n                opacity: 0.45,\n                borderRadius: '6px',",
        'expected_guard': 'Test 9j-2 (opacity contrast reduction) & Test 9m',
    },
    {
        'id': 'X11',
        'name': 'NaturalLanguageRunView: status badge opacity degraded to 0.4',
        'target': "                    fontSize: '11px',\n                    fontWeight: 700,\n                    backgroundColor: statusCfg.bg,",
        'replacement': "                    fontSize: '11px',\n                    opacity: 0.4,\n                    fontWeight: 700,\n                    backgroundColor: statusCfg.bg,",
        'expected_guard': 'Test 9m (badge opacity degradation assertion)',
    },

    # 5. comment decoy
    {
        'id': 'X12',
        'name': 'NaturalLanguageRunView: completed color with comment decoy literal',
        'target': "  completed: {\n    color: 'var(--color-status-online)',",
        'replacement': "  completed: {\n    color: '#3fb950' /* var(--color-status-online) */,",
        'expected_guard': 'Test 10 (COLOR_LITERAL_MULTISET_BASELINE ratchet)',
    },
    {
        'id': 'X13',
        'name': 'NaturalLanguageRunView: unknown fallback border with comment decoy literal',
        'target': "    border: 'var(--color-status-unknown)',\n    label: (status || 'UNKNOWN').toUpperCase(),",
        'replacement': "    border: '#8b949e' /* var(--color-status-unknown) */,\n    label: (status || 'UNKNOWN').toUpperCase(),",
        'expected_guard': 'Test 10 (COLOR_LITERAL_MULTISET_BASELINE ratchet)',
    },

    # 6. legacy token revert
    {
        'id': 'X14',
        'name': 'NaturalLanguageRunView: rejected config color reverted to legacy literal #ff7b72',
        'target': "  rejected: {\n    color: 'var(--color-status-offline)',",
        'replacement': "  rejected: {\n    color: '#ff7b72',",
        'expected_guard': 'Test 10 (COLOR_LITERAL_MULTISET_BASELINE ratchet)',
    },
    {
        'id': 'X15',
        'name': 'NaturalLanguageRunView: diff code view color reverted to legacy literal #c9d1d9',
        'target': "              fontSize: '12px',\n              lineHeight: '18px',\n              color: 'var(--color-text-primary)',",
        'replacement': "              fontSize: '12px',\n              lineHeight: '18px',\n              color: '#c9d1d9',",
        'expected_guard': 'Test 10 (COLOR_LITERAL_MULTISET_BASELINE ratchet)',
    },

    # 7. state collapse
    {
        'id': 'X16',
        'name': 'NaturalLanguageRunView: evaluating status color collapsed to status-online',
        'target': "  evaluating: {\n    color: 'var(--color-brand-hover)',",
        'replacement': "  evaluating: {\n    color: 'var(--color-status-online)',",
        'expected_guard': 'Test 9m (state token uniqueness assertion: evaluating != completed)',
    },
    {
        'id': 'X17',
        'name': 'NaturalLanguageRunView: repairing status color collapsed to status-online',
        'target': "  repairing: {\n    color: 'var(--color-status-degraded)',",
        'replacement': "  repairing: {\n    color: 'var(--color-status-online)',",
        'expected_guard': 'Test 9m (state token uniqueness assertion: repairing != completed)',
    },
    {
        'id': 'X18',
        'name': 'NaturalLanguageRunView: draft status color collapsed to brand-hover',
        'target': "  draft: {\n    color: 'var(--color-text-secondary)',",
        'replacement': "  draft: {\n    color: 'var(--color-brand-hover)',",
        'expected_guard': 'Test 9m (state token uniqueness assertion: draft != ready)',
    },

    # 8. label alteration / non-exact string (F-R2)
    {
        'id': 'X19',
        'name': 'NaturalLanguageRunView: completed label changed to DONE',
        'target': "  completed: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-online)',\n    label: 'COMPLETED',",
        'replacement': "  completed: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-online)',\n    label: 'DONE',",
        'expected_guard': 'Test 9m (label uppercase equality assertion)',
    },
    {
        'id': 'X20',
        'name': 'NaturalLanguageRunView: rejected label changed to BLOCKED',
        'target': "  rejected: {\n    color: 'var(--color-status-offline)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-offline)',\n    label: 'REJECTED',",
        'replacement': "  rejected: {\n    color: 'var(--color-status-offline)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-offline)',\n    label: 'BLOCKED',",
        'expected_guard': 'Test 9m (label uppercase equality assertion)',
    },
    {
        'id': 'X21',
        'name': 'NaturalLanguageRunView: draft label changed to 초안',
        'target': "  draft: {\n    color: 'var(--color-text-secondary)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-border-subtle)',\n    label: 'DRAFT',",
        'replacement': "  draft: {\n    color: 'var(--color-text-secondary)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-border-subtle)',\n    label: '초안',",
        'expected_guard': 'Test 9m (label uppercase equality assertion)',
    },
    {
        'id': 'X22',
        'name': 'NaturalLanguageRunView: status badge DOM altered with extra exclamation suffix',
        'target': "                  {statusCfg.label}\n                </span>",
        'replacement': "                  {statusCfg.label + '!'}\n                </span>",
        'expected_guard': 'Test 9m (status badge exact string assertion)',
    },

    # 9. outline suppression
    {
        'id': 'X23',
        'name': 'NaturalLanguageRunView: preset 1 button outline suppressed with outline: none',
        'target': "                backgroundColor: 'var(--color-bg-subtle)',\n                color: 'var(--color-brand-hover)',\n                cursor: 'pointer',",
        'replacement': "                backgroundColor: 'var(--color-bg-subtle)',\n                color: 'var(--color-brand-hover)',\n                cursor: 'pointer',\n                outline: 'none',",
        'expected_guard': 'Test 9j-2 (inline outline: none suppression)',
    },
    {
        'id': 'X24',
        'name': 'NaturalLanguageRunView: preset 1 button outline suppressed with outlineWidth: 0px',
        'target': "                backgroundColor: 'var(--color-bg-subtle)',\n                color: 'var(--color-brand-hover)',\n                cursor: 'pointer',",
        'replacement': "                backgroundColor: 'var(--color-bg-subtle)',\n                color: 'var(--color-brand-hover)',\n                cursor: 'pointer',\n                outlineWidth: '0px',",
        'expected_guard': 'Test 9j-2 (inline outlineWidth: 0px suppression)',
    },
    {
        'id': 'X25',
        'name': 'NaturalLanguageRunView: apply-diff Button outline suppressed with outline: none as const (F10)',
        'target': '<Button size="sm" variant="primary" onClick={handleApplyDiff} data-testid="agent-apply-diff-btn">',
        'replacement': '<Button size="sm" variant="primary" onClick={handleApplyDiff} data-testid="agent-apply-diff-btn" style={{ outline: \'none\' as const }}>',
        'expected_guard': 'Test 9j-2 (outline unwraps AsExpression and catches none)',
    },
    {
        'id': 'X26',
        'name': 'NaturalLanguageRunView: context tag outline suppressed with outline: 0',
        'target': "                        backgroundColor: 'var(--color-bg-subtle)',\n                        color: isSelected ? 'var(--color-brand-hover)' : 'var(--color-text-secondary)',",
        'replacement': "                        backgroundColor: 'var(--color-bg-subtle)',\n                        color: isSelected ? 'var(--color-brand-hover)' : 'var(--color-text-secondary)',\n                        outline: '0',",
        'expected_guard': 'Test 9j-2 (inline outline: 0 suppression)',
    },

    # 10. unknown fallback handling
    {
        'id': 'X27',
        'name': 'NaturalLanguageRunView: getAgentRunStatusConfig null/empty returns draft (fail-open fallback bypass)',
        'target': "export function getAgentRunStatusConfig(status?: string | null): AgentRunStatusStyle {\n  if (status && Object.hasOwn(AGENT_RUN_STATUS_CONFIG, status)) {",
        'replacement': "export function getAgentRunStatusConfig(status?: string | null): AgentRunStatusStyle {\n  if (!status) return AGENT_RUN_STATUS_CONFIG.draft;\n  if (status && Object.hasOwn(AGENT_RUN_STATUS_CONFIG, status)) {",
        'expected_guard': 'Test 9m (null / empty string UNKNOWN assertion)',
    },
    {
        'id': 'X28',
        'name': 'NaturalLanguageRunView: getAgentRunStatusConfig unknown fallback returns ready config',
        'target': "  return {\n    color: 'var(--color-status-unknown)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-unknown)',\n    label: (status || 'UNKNOWN').toUpperCase(),\n  };",
        'replacement': "  return AGENT_RUN_STATUS_CONFIG.ready;",
        'expected_guard': 'Test 9m (unknown status fail-closed token assertion)',
    },

    # 11. prototype key defense (Codex F1)
    {
        'id': 'X29',
        'name': 'NaturalLanguageRunView: getAgentRunStatusConfig uses in operator instead of Object.hasOwn',
        'target': 'if (status && Object.hasOwn(AGENT_RUN_STATUS_CONFIG, status)) {',
        'replacement': 'if (status && status in AGENT_RUN_STATUS_CONFIG) {',
        'expected_guard': 'Test 9m (prototype key fail-closed own-key defense assertion)',
    },

    # 12. wire contract enum purity (Codex F-R1)
    {
        'id': 'X30b',
        'name': 'NaturalLanguageRunView: out-of-contract status (planning) added to AGENT_RUN_STATUS_CONFIG',
        'target': "  draft: {\n    color: 'var(--color-text-secondary)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-border-subtle)',\n    label: 'DRAFT',\n  },",
        'replacement': "  draft: {\n    color: 'var(--color-text-secondary)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-border-subtle)',\n    label: 'DRAFT',\n  },\n  planning: {\n    color: 'var(--color-brand-hover)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-brand-hover)',\n    label: 'PLANNING',\n  } as any,",
        'expected_guard': 'Test 9m (exact wire contract key set equality assertion)',
    },
    {
        'id': 'X31b',
        'name': 'NaturalLanguageRunView: contract status (completed) removed from AGENT_RUN_STATUS_CONFIG',
        'target': "  completed: {\n    color: 'var(--color-status-online)',\n    bg: 'var(--color-bg-subtle)',\n    border: 'var(--color-status-online)',\n    label: 'COMPLETED',\n  },",
        'replacement': "",
        'expected_guard': 'Test 9m (exact wire contract key set equality assertion)',
    },

    # 13. named color literals
    {
        'id': 'X32',
        'name': 'NaturalLanguageRunView: action notice success border injected with named color green',
        'target': "actionNotice.type === 'error'\n                    ? 'var(--color-status-offline)'\n                    : actionNotice.type === 'success'\n                    ? 'var(--color-status-online)'\n                    : 'var(--color-brand-hover)'",
        'replacement': "actionNotice.type === 'error'\n                    ? 'var(--color-status-offline)'\n                    : actionNotice.type === 'success'\n                    ? 'green'\n                    : 'var(--color-brand-hover)'",
        'expected_guard': 'Test 9j-2 (named color literal violation) & Test 10',
    },
    {
        'id': 'X33',
        'name': 'NaturalLanguageRunView: draft config color injected with named color green',
        'target': "  draft: {\n    color: 'var(--color-text-secondary)',",
        'replacement': "  draft: {\n    color: 'green',",
        'expected_guard': 'Test 9j-2 (named color literal violation) & Test 10',
    },
    {
        'id': 'X34',
        'name': 'NaturalLanguageRunView: KPI 1 label injected with named color dimgray',
        'target': "<div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', fontWeight: 600 }}>Prompt 100건 유효율 (AC-09 픽스처)</div>",
        'replacement': "<div style={{ fontSize: '12px', color: 'dimgray', fontWeight: 600 }}>Prompt 100건 유효율 (AC-09 픽스처)</div>",
        'expected_guard': 'Test 9j-2 (named color literal violation) & Test 10',
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
    print(' Card 228 (ACC-09): Reproducible Mutant Test Suite (34 Mutants: X1-X34)')
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
