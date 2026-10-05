#!/usr/bin/env python3
"""
tools/test_c275_mutations.py:
Verification runner for 40 accessibility, contrast, contract, and fail-closed mutants (W1-W40)
targeting Card 275 EvidenceViewer component:
  - apps/web/src/features/evidence/EvidenceViewer.tsx (W1-W40)

Requirements:
- Each mutant MUST compile cleanly under TypeScript (npx tsc -b).
- Each mutant MUST be killed by vitest run tests/acc09-contrast-tokens.test.tsx with timeout=120s.
- If timeout, record as TIMEOUT (do not count as killed).
- Restore original code after each mutant and verify byte equality + git diff 0.
- Sequential execution only (under 1GB memory).
- 100% kill rate (40/40) required.
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parent.parent
APPS_WEB = WORKTREE_ROOT / "apps" / "web"
RESULTS_FILE = WORKTREE_ROOT / "tools" / ".c275_mutation_results.json"

TARGET_FILES = {
    "EvidenceViewer": APPS_WEB / "src" / "features" / "evidence" / "EvidenceViewer.tsx",
}

MUTANTS = [
    # Batch 1 (W1-W15): EVIDENCE_INTEGRITY_CONFIG tokens, contrast, and outline
    {
        "id": "W1",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: PASS colorVar==bgVar 1:1 collision (colorVar: var(--color-bg-subtle))",
        "target": "  PASS: {\n    label: '출력 무결성 검증 통과 (PASS)',\n    icon: '✓',\n    colorVar: 'var(--color-brand-success)',\n    bgVar: 'var(--color-bg-subtle)',",
        "replacement": "  PASS: {\n    label: '출력 무결성 검증 통과 (PASS)',\n    icon: '✓',\n    colorVar: 'var(--color-bg-subtle)',\n    bgVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W2",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: PASS colorVar low-contrast text mutation (colorVar: var(--color-text-inverse))",
        "target": "  PASS: {\n    label: '출력 무결성 검증 통과 (PASS)',\n    icon: '✓',\n    colorVar: 'var(--color-brand-success)',\n    bgVar: 'var(--color-bg-subtle)',",
        "replacement": "  PASS: {\n    label: '출력 무결성 검증 통과 (PASS)',\n    icon: '✓',\n    colorVar: 'var(--color-text-inverse)',\n    bgVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W3",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: PASS borderVar==bgVar collision (borderVar: var(--color-bg-subtle))",
        "target": "  PASS: {\n    label: '출력 무결성 검증 통과 (PASS)',\n    icon: '✓',\n    colorVar: 'var(--color-brand-success)',\n    bgVar: 'var(--color-bg-subtle)',\n    borderVar: 'var(--color-brand-success)',",
        "replacement": "  PASS: {\n    label: '출력 무결성 검증 통과 (PASS)',\n    icon: '✓',\n    colorVar: 'var(--color-brand-success)',\n    bgVar: 'var(--color-bg-subtle)',\n    borderVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W4",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: PASS borderVar degraded to border-subtle (borderVar: var(--color-border-subtle))",
        "target": "  PASS: {\n    label: '출력 무결성 검증 통과 (PASS)',\n    icon: '✓',\n    colorVar: 'var(--color-brand-success)',\n    bgVar: 'var(--color-bg-subtle)',\n    borderVar: 'var(--color-brand-success)',",
        "replacement": "  PASS: {\n    label: '출력 무결성 검증 통과 (PASS)',\n    icon: '✓',\n    colorVar: 'var(--color-brand-success)',\n    bgVar: 'var(--color-bg-subtle)',\n    borderVar: 'var(--color-border-subtle)',",
    },
    {
        "id": "W5",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: FAIL colorVar==bgVar 1:1 collision (colorVar: var(--color-bg-subtle))",
        "target": "  FAIL: {\n    label: '출력 무결성 검증 실패 (FAIL)',\n    icon: '✗',\n    colorVar: 'var(--color-brand-danger)',\n    bgVar: 'var(--color-bg-subtle)',",
        "replacement": "  FAIL: {\n    label: '출력 무결성 검증 실패 (FAIL)',\n    icon: '✗',\n    colorVar: 'var(--color-bg-subtle)',\n    bgVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W6",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: FAIL colorVar low-contrast text mutation (colorVar: var(--color-text-inverse))",
        "target": "  FAIL: {\n    label: '출력 무결성 검증 실패 (FAIL)',\n    icon: '✗',\n    colorVar: 'var(--color-brand-danger)',\n    bgVar: 'var(--color-bg-subtle)',",
        "replacement": "  FAIL: {\n    label: '출력 무결성 검증 실패 (FAIL)',\n    icon: '✗',\n    colorVar: 'var(--color-text-inverse)',\n    bgVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W7",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: FAIL borderVar==bgVar collision (borderVar: var(--color-bg-subtle))",
        "target": "  FAIL: {\n    label: '출력 무결성 검증 실패 (FAIL)',\n    icon: '✗',\n    colorVar: 'var(--color-brand-danger)',\n    bgVar: 'var(--color-bg-subtle)',\n    borderVar: 'var(--color-brand-danger)',",
        "replacement": "  FAIL: {\n    label: '출력 무결성 검증 실패 (FAIL)',\n    icon: '✗',\n    colorVar: 'var(--color-brand-danger)',\n    bgVar: 'var(--color-bg-subtle)',\n    borderVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W8",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: RUN_FAILED colorVar==bgVar 1:1 collision (colorVar: var(--color-bg-subtle))",
        "target": "  RUN_FAILED: {\n    label: '실행 실패 · 출력 부재 (RUN_FAILED)',\n    icon: '✗',\n    colorVar: 'var(--color-brand-danger)',\n    bgVar: 'var(--color-bg-subtle)',",
        "replacement": "  RUN_FAILED: {\n    label: '실행 실패 · 출력 부재 (RUN_FAILED)',\n    icon: '✗',\n    colorVar: 'var(--color-bg-subtle)',\n    bgVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W9",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: RUN_FAILED colorVar low-contrast text mutation (colorVar: var(--color-text-inverse))",
        "target": "  RUN_FAILED: {\n    label: '실행 실패 · 출력 부재 (RUN_FAILED)',\n    icon: '✗',\n    colorVar: 'var(--color-brand-danger)',\n    bgVar: 'var(--color-bg-subtle)',",
        "replacement": "  RUN_FAILED: {\n    label: '실행 실패 · 출력 부재 (RUN_FAILED)',\n    icon: '✗',\n    colorVar: 'var(--color-text-inverse)',\n    bgVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W10",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: RUN_FAILED borderVar==bgVar collision (borderVar: var(--color-bg-subtle))",
        "target": "  RUN_FAILED: {\n    label: '실행 실패 · 출력 부재 (RUN_FAILED)',\n    icon: '✗',\n    colorVar: 'var(--color-brand-danger)',\n    bgVar: 'var(--color-bg-subtle)',\n    borderVar: 'var(--color-brand-danger)',",
        "replacement": "  RUN_FAILED: {\n    label: '실행 실패 · 출력 부재 (RUN_FAILED)',\n    icon: '✗',\n    colorVar: 'var(--color-brand-danger)',\n    bgVar: 'var(--color-bg-subtle)',\n    borderVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W11",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: UNVERIFIED colorVar==bgVar 1:1 collision (colorVar: var(--color-bg-subtle))",
        "target": "  UNVERIFIED: {\n    label: '출력 무결성 미검증 (UNVERIFIED)',\n    icon: '⚠️',\n    colorVar: 'var(--color-status-unknown)',\n    bgVar: 'var(--color-bg-subtle)',",
        "replacement": "  UNVERIFIED: {\n    label: '출력 무결성 미검증 (UNVERIFIED)',\n    icon: '⚠️',\n    colorVar: 'var(--color-bg-subtle)',\n    bgVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W12",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: UNVERIFIED colorVar low-contrast text mutation (colorVar: var(--color-text-inverse))",
        "target": "  UNVERIFIED: {\n    label: '출력 무결성 미검증 (UNVERIFIED)',\n    icon: '⚠️',\n    colorVar: 'var(--color-status-unknown)',\n    bgVar: 'var(--color-bg-subtle)',",
        "replacement": "  UNVERIFIED: {\n    label: '출력 무결성 미검증 (UNVERIFIED)',\n    icon: '⚠️',\n    colorVar: 'var(--color-text-inverse)',\n    bgVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W13",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: UNVERIFIED borderVar==bgVar collision (borderVar: var(--color-bg-subtle))",
        "target": "  UNVERIFIED: {\n    label: '출력 무결성 미검증 (UNVERIFIED)',\n    icon: '⚠️',\n    colorVar: 'var(--color-status-unknown)',\n    bgVar: 'var(--color-bg-subtle)',\n    borderVar: 'var(--color-status-unknown)',",
        "replacement": "  UNVERIFIED: {\n    label: '출력 무결성 미검증 (UNVERIFIED)',\n    icon: '⚠️',\n    colorVar: 'var(--color-status-unknown)',\n    bgVar: 'var(--color-bg-subtle)',\n    borderVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W14",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: UNVERIFIED borderVar degraded to border-subtle (borderVar: var(--color-border-subtle))",
        "target": "  UNVERIFIED: {\n    label: '출력 무결성 미검증 (UNVERIFIED)',\n    icon: '⚠️',\n    colorVar: 'var(--color-status-unknown)',\n    bgVar: 'var(--color-bg-subtle)',\n    borderVar: 'var(--color-status-unknown)',",
        "replacement": "  UNVERIFIED: {\n    label: '출력 무결성 미검증 (UNVERIFIED)',\n    icon: '⚠️',\n    colorVar: 'var(--color-status-unknown)',\n    bgVar: 'var(--color-bg-subtle)',\n    borderVar: 'var(--color-border-subtle)',",
    },
    {
        "id": "W15",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: Error alert banner outline:none focus ring suppression mutant",
        "target": "        <div\n          role=\"alert\"\n          data-testid=\"evidence-error-alert\"\n          style={{\n            padding: '16px 20px',",
        "replacement": "        <div\n          role=\"alert\"\n          data-testid=\"evidence-error-alert\"\n          style={{\n            outline: 'none',\n            padding: '16px 20px',",
    },

    # Batch 2 (W16-W25): getEvidenceIntegrityConfig fallback, prototype guard, and sealed badge
    {
        "id": "W16",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: Object.hasOwn replaced by `status in EVIDENCE_INTEGRITY_CONFIG` (prototype pollution vulnerability)",
        "target": "  if (typeof status === 'string' && Object.hasOwn(EVIDENCE_INTEGRITY_CONFIG, status)) {",
        "replacement": "  if (typeof status === 'string' && status in EVIDENCE_INTEGRITY_CONFIG) {",
    },
    {
        "id": "W17",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: UNKNOWN fallback colorVar==bgVar 1:1 collision",
        "target": "  return {\n    label: raw ? `미확인 무결성 상태 (UNKNOWN: ${raw})` : '미확인 무결성 상태 (UNKNOWN)',\n    icon: '❓',\n    colorVar: 'var(--color-status-unknown)',\n    bgVar: 'var(--color-bg-subtle)',",
        "replacement": "  return {\n    label: raw ? `미확인 무결성 상태 (UNKNOWN: ${raw})` : '미확인 무결성 상태 (UNKNOWN)',\n    icon: '❓',\n    colorVar: 'var(--color-bg-subtle)',\n    bgVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W18",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: UNKNOWN fallback colorVar low-contrast text mutation (colorVar: var(--color-text-inverse))",
        "target": "  return {\n    label: raw ? `미확인 무결성 상태 (UNKNOWN: ${raw})` : '미확인 무결성 상태 (UNKNOWN)',\n    icon: '❓',\n    colorVar: 'var(--color-status-unknown)',\n    bgVar: 'var(--color-bg-subtle)',",
        "replacement": "  return {\n    label: raw ? `미확인 무결성 상태 (UNKNOWN: ${raw})` : '미확인 무결성 상태 (UNKNOWN)',\n    icon: '❓',\n    colorVar: 'var(--color-text-inverse)',\n    bgVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W19",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: UNKNOWN fallback borderVar==bgVar collision (borderVar: var(--color-bg-subtle))",
        "target": "  return {\n    label: raw ? `미확인 무결성 상태 (UNKNOWN: ${raw})` : '미확인 무결성 상태 (UNKNOWN)',\n    icon: '❓',\n    colorVar: 'var(--color-status-unknown)',\n    bgVar: 'var(--color-bg-subtle)',\n    borderVar: 'var(--color-status-unknown)',",
        "replacement": "  return {\n    label: raw ? `미확인 무결성 상태 (UNKNOWN: ${raw})` : '미확인 무결성 상태 (UNKNOWN)',\n    icon: '❓',\n    colorVar: 'var(--color-status-unknown)',\n    bgVar: 'var(--color-bg-subtle)',\n    borderVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W20",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: Sealed badge outline:none focus ring suppression mutant",
        "target": "              {evidenceData.immutable && (\n                <span\n                  data-testid=\"evidence-status-sealed\"\n                  style={{\n                    padding: '4px 10px',",
        "replacement": "              {evidenceData.immutable && (\n                <span\n                  data-testid=\"evidence-status-sealed\"\n                  style={{\n                    outline: 'none',\n                    padding: '4px 10px',",
    },
    {
        "id": "W21",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: Dynamic status badge unknown fallback testId bypassed to evidence-status-pass",
        "target": "                const testId = (typeof evidenceData.integrityVerification === 'string' && Object.hasOwn(testIdMap, evidenceData.integrityVerification))\n                  ? testIdMap[evidenceData.integrityVerification as IntegrityVerificationStatus]\n                  : 'evidence-status-unknown';",
        "replacement": "                const testId = (typeof evidenceData.integrityVerification === 'string' && Object.hasOwn(testIdMap, evidenceData.integrityVerification))\n                  ? testIdMap[evidenceData.integrityVerification as IntegrityVerificationStatus]\n                  : 'evidence-status-pass';",
    },
    {
        "id": "W22",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: Sealed badge backgroundColor reverted to former rgba literal rgba(56, 139, 253, 0.15)",
        "target": "              {evidenceData.immutable && (\n                <span\n                  data-testid=\"evidence-status-sealed\"\n                  style={{\n                    padding: '4px 10px',\n                    borderRadius: 'var(--radius-sm)',\n                    fontSize: '0.75rem',\n                    fontWeight: 600,\n                    backgroundColor: 'var(--color-bg-subtle)',",
        "replacement": "              {evidenceData.immutable && (\n                <span\n                  data-testid=\"evidence-status-sealed\"\n                  style={{\n                    padding: '4px 10px',\n                    borderRadius: 'var(--radius-sm)',\n                    fontSize: '0.75rem',\n                    fontWeight: 600,\n                    backgroundColor: 'rgba(56, 139, 253, 0.15)',",
    },
    {
        "id": "W23",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: Sealed badge color==backgroundColor 1:1 collision",
        "target": "              {evidenceData.immutable && (\n                <span\n                  data-testid=\"evidence-status-sealed\"\n                  style={{\n                    padding: '4px 10px',\n                    borderRadius: 'var(--radius-sm)',\n                    fontSize: '0.75rem',\n                    fontWeight: 600,\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    color: 'var(--color-brand-primary)',",
        "replacement": "              {evidenceData.immutable && (\n                <span\n                  data-testid=\"evidence-status-sealed\"\n                  style={{\n                    padding: '4px 10px',\n                    borderRadius: 'var(--radius-sm)',\n                    fontSize: '0.75rem',\n                    fontWeight: 600,\n                    backgroundColor: 'var(--color-bg-subtle)',\n                    color: 'var(--color-bg-subtle)',",
    },
    {
        "id": "W24",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: Sealed badge border==backgroundColor collision",
        "target": "                    backgroundColor: 'var(--color-bg-subtle)',\n                    color: 'var(--color-brand-primary)',\n                    border: '1px solid var(--color-brand-primary)',",
        "replacement": "                    backgroundColor: 'var(--color-bg-subtle)',\n                    color: 'var(--color-brand-primary)',\n                    border: '1px solid var(--color-bg-subtle)',",
    },
    {
        "id": "W25",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: Sealed badge color mutated to low-contrast var(--color-text-inverse)",
        "target": "                    backgroundColor: 'var(--color-bg-subtle)',\n                    color: 'var(--color-brand-primary)',\n                    border: '1px solid var(--color-brand-primary)',",
        "replacement": "                    backgroundColor: 'var(--color-bg-subtle)',\n                    color: 'var(--color-text-inverse)',\n                    border: '1px solid var(--color-brand-primary)',",
    },

    # Batch 3 (W26-W32): Copy success indicator and error alert banner
    {
        "id": "W26",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: Copy success indicator color reverted to former #10b981 literal",
        "target": "              {copySuccess && (\n                <span role=\"status\" data-testid=\"copy-evidence-success\" style={{ fontSize: '0.75rem', color: 'var(--color-brand-success)' }}>\n                  ✓ 클립보드에 복사되었습니다\n                </span>\n              )}",
        "replacement": "              {copySuccess && (\n                <span role=\"status\" data-testid=\"copy-evidence-success\" style={{ fontSize: '0.75rem', color: '#10b981' }}>\n                  ✓ 클립보드에 복사되었습니다\n                </span>\n              )}",
    },
    {
        "id": "W27",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: Copy success indicator color mutated to low-contrast var(--color-text-inverse)",
        "target": "              {copySuccess && (\n                <span role=\"status\" data-testid=\"copy-evidence-success\" style={{ fontSize: '0.75rem', color: 'var(--color-brand-success)' }}>\n                  ✓ 클립보드에 복사되었습니다\n                </span>\n              )}",
        "replacement": "              {copySuccess && (\n                <span role=\"status\" data-testid=\"copy-evidence-success\" style={{ fontSize: '0.75rem', color: 'var(--color-text-inverse)' }}>\n                  ✓ 클립보드에 복사되었습니다\n                </span>\n              )}",
    },
    {
        "id": "W28",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: Copy success indicator color==surface bg 1:1 collision",
        "target": "              {copySuccess && (\n                <span role=\"status\" data-testid=\"copy-evidence-success\" style={{ fontSize: '0.75rem', color: 'var(--color-brand-success)' }}>\n                  ✓ 클립보드에 복사되었습니다\n                </span>\n              )}",
        "replacement": "              {copySuccess && (\n                <span role=\"status\" data-testid=\"copy-evidence-success\" style={{ fontSize: '0.75rem', color: 'var(--color-bg-surface)' }}>\n                  ✓ 클립보드에 복사되었습니다\n                </span>\n              )}",
    },
    {
        "id": "W29",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: Error alert banner backgroundColor reverted to former rgba literal rgba(248, 81, 73, 0.1)",
        "target": "      {errorMessage && (\n        <div\n          role=\"alert\"\n          data-testid=\"evidence-error-alert\"\n          style={{\n            padding: '16px 20px',\n            marginBottom: '20px',\n            backgroundColor: 'var(--color-risk-l3-bg)',\n            border: '1px solid var(--color-risk-l3-border)',",
        "replacement": "      {errorMessage && (\n        <div\n          role=\"alert\"\n          data-testid=\"evidence-error-alert\"\n          style={{\n            padding: '16px 20px',\n            marginBottom: '20px',\n            backgroundColor: 'rgba(248, 81, 73, 0.1)',\n            border: '1px solid var(--color-risk-l3-border)',",
    },
    {
        "id": "W30",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: Error alert banner border reverted to former rgba literal rgba(248, 81, 73, 0.3)",
        "target": "            padding: '16px 20px',\n            marginBottom: '20px',\n            backgroundColor: 'var(--color-risk-l3-bg)',\n            border: '1px solid var(--color-risk-l3-border)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-risk-l3-text)',",
        "replacement": "            padding: '16px 20px',\n            marginBottom: '20px',\n            backgroundColor: 'var(--color-risk-l3-bg)',\n            border: '1px solid rgba(248, 81, 73, 0.3)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-risk-l3-text)',",
    },
    {
        "id": "W31",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: Error alert banner text color reverted to former #f87171 literal",
        "target": "            padding: '16px 20px',\n            marginBottom: '20px',\n            backgroundColor: 'var(--color-risk-l3-bg)',\n            border: '1px solid var(--color-risk-l3-border)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-risk-l3-text)',",
        "replacement": "            padding: '16px 20px',\n            marginBottom: '20px',\n            backgroundColor: 'var(--color-risk-l3-bg)',\n            border: '1px solid var(--color-risk-l3-border)',\n            borderRadius: 'var(--radius-md)',\n            color: '#f87171',",
    },
    {
        "id": "W32",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: Error alert banner color==backgroundColor 1:1 collision",
        "target": "            padding: '16px 20px',\n            marginBottom: '20px',\n            backgroundColor: 'var(--color-risk-l3-bg)',\n            border: '1px solid var(--color-risk-l3-border)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-risk-l3-text)',",
        "replacement": "            padding: '16px 20px',\n            marginBottom: '20px',\n            backgroundColor: 'var(--color-risk-l3-bg)',\n            border: '1px solid var(--color-risk-l3-border)',\n            borderRadius: 'var(--radius-md)',\n            color: 'var(--color-risk-l3-bg)',",
    },

    # Batch 4 (W33-W40): Notice banners (RUN_FAILED, FAIL, UNVERIFIED)
    {
        "id": "W33",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: RUN_FAILED notice banner backgroundColor reverted to former rgba literal rgba(248, 81, 73, 0.08)",
        "target": "          {evidenceData.integrityVerification === 'RUN_FAILED' && (\n            <div\n              role=\"status\"\n              data-testid=\"evidence-run-failed-notice\"\n              style={{\n                marginBottom: '16px',\n                padding: '10px 14px',\n                backgroundColor: 'var(--color-risk-l3-bg)',\n                borderRadius: 'var(--radius-sm)',\n                border: '1px solid var(--color-risk-l3-border)',\n                fontSize: '0.8125rem',\n                color: 'var(--color-risk-l3-text)',\n              }}",
        "replacement": "          {evidenceData.integrityVerification === 'RUN_FAILED' && (\n            <div\n              role=\"status\"\n              data-testid=\"evidence-run-failed-notice\"\n              style={{\n                marginBottom: '16px',\n                padding: '10px 14px',\n                backgroundColor: 'rgba(248, 81, 73, 0.08)',\n                borderRadius: 'var(--radius-sm)',\n                border: '1px solid var(--color-risk-l3-border)',\n                fontSize: '0.8125rem',\n                color: 'var(--color-risk-l3-text)',\n              }}",
    },
    {
        "id": "W34",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: RUN_FAILED notice banner border reverted to former rgba literal rgba(248, 81, 73, 0.3)",
        "target": "          {evidenceData.integrityVerification === 'RUN_FAILED' && (\n            <div\n              role=\"status\"\n              data-testid=\"evidence-run-failed-notice\"\n              style={{\n                marginBottom: '16px',\n                padding: '10px 14px',\n                backgroundColor: 'var(--color-risk-l3-bg)',\n                borderRadius: 'var(--radius-sm)',\n                border: '1px solid var(--color-risk-l3-border)',\n                fontSize: '0.8125rem',\n                color: 'var(--color-risk-l3-text)',\n              }}",
        "replacement": "          {evidenceData.integrityVerification === 'RUN_FAILED' && (\n            <div\n              role=\"status\"\n              data-testid=\"evidence-run-failed-notice\"\n              style={{\n                marginBottom: '16px',\n                padding: '10px 14px',\n                backgroundColor: 'var(--color-risk-l3-bg)',\n                borderRadius: 'var(--radius-sm)',\n                border: '1px solid rgba(248, 81, 73, 0.3)',\n                fontSize: '0.8125rem',\n                color: 'var(--color-risk-l3-text)',\n              }}",
    },
    {
        "id": "W35",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: RUN_FAILED notice banner text color reverted to former #f87171 literal",
        "target": "          {evidenceData.integrityVerification === 'RUN_FAILED' && (\n            <div\n              role=\"status\"\n              data-testid=\"evidence-run-failed-notice\"\n              style={{\n                marginBottom: '16px',\n                padding: '10px 14px',\n                backgroundColor: 'var(--color-risk-l3-bg)',\n                borderRadius: 'var(--radius-sm)',\n                border: '1px solid var(--color-risk-l3-border)',\n                fontSize: '0.8125rem',\n                color: 'var(--color-risk-l3-text)',\n              }}",
        "replacement": "          {evidenceData.integrityVerification === 'RUN_FAILED' && (\n            <div\n              role=\"status\"\n              data-testid=\"evidence-run-failed-notice\"\n              style={{\n                marginBottom: '16px',\n                padding: '10px 14px',\n                backgroundColor: 'var(--color-risk-l3-bg)',\n                borderRadius: 'var(--radius-sm)',\n                border: '1px solid var(--color-risk-l3-border)',\n                fontSize: '0.8125rem',\n                color: '#f87171',\n              }}",
    },
    {
        "id": "W36",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: FAIL notice banner backgroundColor reverted to former rgba literal rgba(248, 81, 73, 0.1)",
        "target": "          {evidenceData.integrityVerification === 'FAIL' && (\n            <div\n              role=\"alert\"\n              data-testid=\"evidence-failed-notice\"\n              style={{\n                marginBottom: '16px',\n                padding: '10px 14px',\n                backgroundColor: 'var(--color-risk-l3-bg)',\n                borderRadius: 'var(--radius-sm)',\n                border: '1px solid var(--color-risk-l3-border)',\n                fontSize: '0.8125rem',\n                color: 'var(--color-risk-l3-text)',\n              }}",
        "replacement": "          {evidenceData.integrityVerification === 'FAIL' && (\n            <div\n              role=\"alert\"\n              data-testid=\"evidence-failed-notice\"\n              style={{\n                marginBottom: '16px',\n                padding: '10px 14px',\n                backgroundColor: 'rgba(248, 81, 73, 0.1)',\n                borderRadius: 'var(--radius-sm)',\n                border: '1px solid var(--color-risk-l3-border)',\n                fontSize: '0.8125rem',\n                color: 'var(--color-risk-l3-text)',\n              }}",
    },
    {
        "id": "W37",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: FAIL notice banner text color mutated to low-contrast var(--color-text-inverse)",
        "target": "          {evidenceData.integrityVerification === 'FAIL' && (\n            <div\n              role=\"alert\"\n              data-testid=\"evidence-failed-notice\"\n              style={{\n                marginBottom: '16px',\n                padding: '10px 14px',\n                backgroundColor: 'var(--color-risk-l3-bg)',\n                borderRadius: 'var(--radius-sm)',\n                border: '1px solid var(--color-risk-l3-border)',\n                fontSize: '0.8125rem',\n                color: 'var(--color-risk-l3-text)',\n              }}",
        "replacement": "          {evidenceData.integrityVerification === 'FAIL' && (\n            <div\n              role=\"alert\"\n              data-testid=\"evidence-failed-notice\"\n              style={{\n                marginBottom: '16px',\n                padding: '10px 14px',\n                backgroundColor: 'var(--color-risk-l3-bg)',\n                borderRadius: 'var(--radius-sm)',\n                border: '1px solid var(--color-risk-l3-border)',\n                fontSize: '0.8125rem',\n                color: 'var(--color-text-inverse)',\n              }}",
    },
    {
        "id": "W38",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: UNVERIFIED notice banner backgroundColor reverted to former rgba literal rgba(234, 179, 8, 0.08)",
        "target": "          {evidenceData.integrityVerification === 'UNVERIFIED' && (\n            <div\n              data-testid=\"evidence-unverified-notice\"\n              style={{\n                marginBottom: '16px',\n                padding: '10px 14px',\n                backgroundColor: 'var(--color-bg-subtle)',\n                borderRadius: 'var(--radius-sm)',\n                border: '1px solid var(--color-status-unknown)',\n                fontSize: '0.8125rem',\n                color: 'var(--color-status-unknown)',\n              }}",
        "replacement": "          {evidenceData.integrityVerification === 'UNVERIFIED' && (\n            <div\n              data-testid=\"evidence-unverified-notice\"\n              style={{\n                marginBottom: '16px',\n                padding: '10px 14px',\n                backgroundColor: 'rgba(234, 179, 8, 0.08)',\n                borderRadius: 'var(--radius-sm)',\n                border: '1px solid var(--color-status-unknown)',\n                fontSize: '0.8125rem',\n                color: 'var(--color-status-unknown)',\n              }}",
    },
    {
        "id": "W39",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: UNVERIFIED notice banner border reverted to former rgba literal rgba(234, 179, 8, 0.3)",
        "target": "          {evidenceData.integrityVerification === 'UNVERIFIED' && (\n            <div\n              data-testid=\"evidence-unverified-notice\"\n              style={{\n                marginBottom: '16px',\n                padding: '10px 14px',\n                backgroundColor: 'var(--color-bg-subtle)',\n                borderRadius: 'var(--radius-sm)',\n                border: '1px solid var(--color-status-unknown)',\n                fontSize: '0.8125rem',\n                color: 'var(--color-status-unknown)',\n              }}",
        "replacement": "          {evidenceData.integrityVerification === 'UNVERIFIED' && (\n            <div\n              data-testid=\"evidence-unverified-notice\"\n              style={{\n                marginBottom: '16px',\n                padding: '10px 14px',\n                backgroundColor: 'var(--color-bg-subtle)',\n                borderRadius: 'var(--radius-sm)',\n                border: '1px solid rgba(234, 179, 8, 0.3)',\n                fontSize: '0.8125rem',\n                color: 'var(--color-status-unknown)',\n              }}",
    },
    {
        "id": "W40",
        "file": "EvidenceViewer",
        "desc": "EvidenceViewer: UNVERIFIED notice banner text color reverted to former #d97706 literal",
        "target": "          {evidenceData.integrityVerification === 'UNVERIFIED' && (\n            <div\n              data-testid=\"evidence-unverified-notice\"\n              style={{\n                marginBottom: '16px',\n                padding: '10px 14px',\n                backgroundColor: 'var(--color-bg-subtle)',\n                borderRadius: 'var(--radius-sm)',\n                border: '1px solid var(--color-status-unknown)',\n                fontSize: '0.8125rem',\n                color: 'var(--color-status-unknown)',\n              }}",
        "replacement": "          {evidenceData.integrityVerification === 'UNVERIFIED' && (\n            <div\n              data-testid=\"evidence-unverified-notice\"\n              style={{\n                marginBottom: '16px',\n                padding: '10px 14px',\n                backgroundColor: 'var(--color-bg-subtle)',\n                borderRadius: 'var(--radius-sm)',\n                border: '1px solid var(--color-status-unknown)',\n                fontSize: '0.8125rem',\n                color: '#d97706',\n              }}",
    },
]


def apply_mutation(mutant):
    """Apply mutation to the target file."""
    path = TARGET_FILES[mutant["file"]]
    content = path.read_text(encoding="utf-8")
    if mutant["target"] not in content:
        raise ValueError(f"Target pattern not found in {mutant['file']} for {mutant['id']}")
    new_content = content.replace(mutant["target"], mutant["replacement"], 1)
    path.write_text(new_content, encoding="utf-8")


def restore_file(file_key, original_bytes):
    """Restore file from original bytes and verify byte equality."""
    path = TARGET_FILES[file_key]
    path.write_bytes(original_bytes)
    current = path.read_bytes()
    assert current == original_bytes, f"Byte mismatch after restoring {file_key}"


def run_tsc_check():
    """Verify that mutated file compiles cleanly under TypeScript."""
    cmd = [
        "npx.cmd" if os.name == "nt" else "npx",
        "tsc",
        "-b",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(APPS_WEB),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        return proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")
    except Exception as e:
        return False, str(e)


def run_vitest_acc09(timeout=120):
    """Run vitest on acc09-contrast-tokens.test.tsx."""
    cmd = [
        "npx.cmd" if os.name == "nt" else "npx",
        "vitest",
        "run",
        "tests/acc09-contrast-tokens.test.tsx",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(APPS_WEB),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or "", False
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        return -1, stdout, stderr, True


def test_mutant(mutant, original_bytes_map, timeout=120, head_sha=""):
    mutant_id = mutant["id"]
    file_key = mutant["file"]
    desc = mutant["desc"]
    observed_time = datetime.now(timezone.utc).isoformat()

    print(f"\n--- Testing Mutant {mutant_id} [{file_key}]: {desc} ---")
    try:
        apply_mutation(mutant)
    except Exception as e:
        print(f"  [ERROR] Failed to apply mutation: {e}")
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "ERROR",
            "reason": str(e),
            "killed": False,
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
        }

    # Verify compilation
    compiled_ok, tsc_out = run_tsc_check()
    if not compiled_ok:
        print(f"  [TSC_FAIL] Mutant failed TypeScript compilation:\n{tsc_out[:300]}")
        restore_file(file_key, original_bytes_map[file_key])
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "TSC_FAIL",
            "reason": tsc_out,
            "killed": False,
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
        }

    # Run test
    retcode, stdout, stderr, is_timeout = run_vitest_acc09(timeout=timeout)

    # Restore file immediately
    restore_file(file_key, original_bytes_map[file_key])

    if is_timeout:
        print(f"  [TIMEOUT] Vitest timed out after {timeout}s!")
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "TIMEOUT",
            "killed": False,
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
        }

    if retcode != 0:
        failed_test = "acc09-contrast-tokens.test.tsx"
        for line in (stdout + stderr).splitlines():
            if "FAIL" in line or "AssertionError" in line:
                failed_test = line.strip()
                break
        print(f"  [KILLED] Retcode {retcode}, caught by: {failed_test}")
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "KILLED",
            "killed": True,
            "killer": failed_test,
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
        }
    else:
        print(f"  [SURVIVED] Vitest passed! Mutant was NOT killed!")
        return {
            "id": mutant_id,
            "desc": desc,
            "status": "SURVIVED",
            "killed": False,
            "sourceHeadSha": head_sha,
            "observedAt": observed_time,
        }


def main():
    parser = argparse.ArgumentParser(description="Test Card 275 mutations across EvidenceViewer component")
    parser.add_argument("--batch", type=int, choices=[1, 2, 3, 4], help="Run specific batch (1: Config tokens, 2: Fallback/Sealed, 3: Copy/Alert, 4: Notice banners)")
    parser.add_argument("--mutant", type=str, help="Run single mutant by ID (e.g. W1)")
    parser.add_argument("--all", action="store_true", help="Run all 40 mutants sequentially")
    parser.add_argument("--verify-targets", action="store_true", help="Verify all targets exist in files")
    parser.add_argument("--timeout", type=int, default=120, help="Per-mutant vitest timeout in seconds")
    args = parser.parse_args()

    original_bytes_map = {k: v.read_bytes() for k, v in TARGET_FILES.items()}

    if args.verify_targets:
        print("Verifying mutant targets...")
        missing = 0
        for m in MUTANTS:
            content = TARGET_FILES[m["file"]].read_text(encoding="utf-8")
            if m["target"] not in content:
                print(f"  [MISSING] {m['id']} in {m['file']}: target not found!")
                missing += 1
            else:
                print(f"  [FOUND] {m['id']} in {m['file']}")
        if missing == 0:
            print(f"All {len(MUTANTS)} mutant targets verified!")
            return 0
        else:
            print(f"ERROR: {missing} mutant targets missing!")
            return 1

    try:
        head_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(WORKTREE_ROOT), text=True).strip()
    except Exception:
        head_sha = "unknown"

    selected_mutants = []
    if args.mutant:
        selected_mutants = [m for m in MUTANTS if m["id"] == args.mutant]
        if not selected_mutants:
            print(f"Unknown mutant: {args.mutant}")
            return 1
    elif args.batch:
        if args.batch == 1:
            selected_mutants = MUTANTS[0:15]
        elif args.batch == 2:
            selected_mutants = MUTANTS[15:25]
        elif args.batch == 3:
            selected_mutants = MUTANTS[25:32]
        elif args.batch == 4:
            selected_mutants = MUTANTS[32:40]
    elif args.all:
        selected_mutants = MUTANTS
    else:
        print("Please specify --mutant, --batch, --all, or --verify-targets")
        return 1

    print(f"Starting mutation testing for {len(selected_mutants)} mutant(s) (head SHA: {head_sha})")

    results = []
    for m in selected_mutants:
        res = test_mutant(m, original_bytes_map, timeout=args.timeout, head_sha=head_sha)
        results.append(res)

    # If updating full results
    if args.all:
        killed_count = sum(1 for r in results if r["killed"])
        summary = {
            "sourceHeadSha": head_sha,
            "observedAt": datetime.now(timezone.utc).isoformat(),
            "totalTested": len(results),
            "totalMutants": len(MUTANTS),
            "killed": killed_count,
            "survived": sum(1 for r in results if r.get("status") == "SURVIVED"),
            "timeouts": sum(1 for r in results if r.get("status") == "TIMEOUT"),
            "tsc_fails": sum(1 for r in results if r.get("status") == "TSC_FAIL"),
            "mutations": results,
        }
        RESULTS_FILE.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nSaved complete mutation results to {RESULTS_FILE}")
        print(f"Kill Rate: {killed_count}/{len(results)} ({killed_count/len(results)*100:.1f}%)")
        return 0 if killed_count == len(results) else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
