#!/usr/bin/env python3
"""
tools/test_c281_mutations.py:
Verification runner for 40 accessibility, contrast, contract, and fail-closed mutants (M1-M40)
targeting Card 281:
  - apps/web/src/features/editor/MonacoWorkspaceEditor.tsx (M1-M40)

Requirements:
- Each mutant MUST compile cleanly under TypeScript (npx tsc -b).
- Each mutant MUST be killed by vitest run tests/acc09-contrast-tokens.test.tsx with timeout=120s.
- If timeout, record as TIMEOUT (do not count as killed).
- Restore original code after each mutant using binary read_bytes/write_bytes and verify git status byte-clean.
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
RESULTS_FILE = WORKTREE_ROOT / "tools" / ".c281_mutation_results.json"

TARGET_FILES = {
    "monaco": APPS_WEB / "src" / "features" / "editor" / "MonacoWorkspaceEditor.tsx",
}

MUTANTS = [
    # M1-M14: WORKSPACE_TERMINAL_STATUS_CONFIG
    {
        "id": "M1",
        "file": "monaco",
        "desc": "connected color subtle collision: colorVar: 'var(--color-bg-subtle)'",
        "target": "  connected: {\n    label: 'CONNECTED',\n    bgVar: 'var(--color-diff-added-bg)',\n    colorVar: 'var(--color-status-online)',",
        "replacement": "  connected: {\n    label: 'CONNECTED',\n    bgVar: 'var(--color-diff-added-bg)',\n    colorVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M2",
        "file": "monaco",
        "desc": "connected color literal regression: colorVar: '#3fb950'",
        "target": "  connected: {\n    label: 'CONNECTED',\n    bgVar: 'var(--color-diff-added-bg)',\n    colorVar: 'var(--color-status-online)',",
        "replacement": "  connected: {\n    label: 'CONNECTED',\n    bgVar: 'var(--color-diff-added-bg)',\n    colorVar: '#3fb950',",
    },
    {
        "id": "M3",
        "file": "monaco",
        "desc": "connected bg literal regression: bgVar: 'rgba(46, 160, 67, 0.2)'",
        "target": "  connected: {\n    label: 'CONNECTED',\n    bgVar: 'var(--color-diff-added-bg)',",
        "replacement": "  connected: {\n    label: 'CONNECTED',\n    bgVar: 'rgba(46, 160, 67, 0.2)',",
    },
    {
        "id": "M4",
        "file": "monaco",
        "desc": "connected border literal regression: borderVar: '#2ea043'",
        "target": "    colorVar: 'var(--color-status-online)',\n    borderVar: 'var(--color-diff-added-border)',",
        "replacement": "    colorVar: 'var(--color-status-online)',\n    borderVar: '#2ea043',",
    },
    {
        "id": "M5",
        "file": "monaco",
        "desc": "recovered color subtle collision: colorVar: 'var(--color-bg-subtle)'",
        "target": "  recovered: {\n    label: 'RECOVERED',\n    bgVar: 'var(--color-brand-subtle)',\n    colorVar: 'var(--color-brand-hover)',",
        "replacement": "  recovered: {\n    label: 'RECOVERED',\n    bgVar: 'var(--color-brand-subtle)',\n    colorVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M6",
        "file": "monaco",
        "desc": "recovered color literal regression: colorVar: '#58a6ff'",
        "target": "  recovered: {\n    label: 'RECOVERED',\n    bgVar: 'var(--color-brand-subtle)',\n    colorVar: 'var(--color-brand-hover)',",
        "replacement": "  recovered: {\n    label: 'RECOVERED',\n    bgVar: 'var(--color-brand-subtle)',\n    colorVar: '#58a6ff',",
    },
    {
        "id": "M7",
        "file": "monaco",
        "desc": "recovered bg literal regression: bgVar: 'rgba(56, 139, 253, 0.2)'",
        "target": "  recovered: {\n    label: 'RECOVERED',\n    bgVar: 'var(--color-brand-subtle)',",
        "replacement": "  recovered: {\n    label: 'RECOVERED',\n    bgVar: 'rgba(56, 139, 253, 0.2)',",
    },
    {
        "id": "M8",
        "file": "monaco",
        "desc": "reconnecting color subtle collision: colorVar: 'var(--color-bg-subtle)'",
        "target": "  reconnecting: {\n    label: 'RECONNECTING',\n    bgVar: 'var(--color-bg-subtle)',\n    colorVar: 'var(--color-status-degraded)',",
        "replacement": "  reconnecting: {\n    label: 'RECONNECTING',\n    bgVar: 'var(--color-bg-subtle)',\n    colorVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M9",
        "file": "monaco",
        "desc": "reconnecting color literal regression: colorVar: '#e3b341'",
        "target": "  reconnecting: {\n    label: 'RECONNECTING',\n    bgVar: 'var(--color-bg-subtle)',\n    colorVar: 'var(--color-status-degraded)',",
        "replacement": "  reconnecting: {\n    label: 'RECONNECTING',\n    bgVar: 'var(--color-bg-subtle)',\n    colorVar: '#e3b341',",
    },
    {
        "id": "M10",
        "file": "monaco",
        "desc": "disconnected color subtle collision: colorVar: 'var(--color-bg-subtle)'",
        "target": "  disconnected: {\n    label: 'DISCONNECTED',\n    bgVar: 'var(--color-risk-l3-bg)',\n    colorVar: 'var(--color-status-offline)',",
        "replacement": "  disconnected: {\n    label: 'DISCONNECTED',\n    bgVar: 'var(--color-risk-l3-bg)',\n    colorVar: 'var(--color-bg-subtle)',",
    },
    {
        "id": "M11",
        "file": "monaco",
        "desc": "disconnected color literal regression: colorVar: '#f85149'",
        "target": "  disconnected: {\n    label: 'DISCONNECTED',\n    bgVar: 'var(--color-risk-l3-bg)',\n    colorVar: 'var(--color-status-offline)',",
        "replacement": "  disconnected: {\n    label: 'DISCONNECTED',\n    bgVar: 'var(--color-risk-l3-bg)',\n    colorVar: '#f85149',",
    },
    {
        "id": "M12",
        "file": "monaco",
        "desc": "disconnected bg literal regression: bgVar: 'rgba(248, 81, 73, 0.2)'",
        "target": "  disconnected: {\n    label: 'DISCONNECTED',\n    bgVar: 'var(--color-risk-l3-bg)',",
        "replacement": "  disconnected: {\n    label: 'DISCONNECTED',\n    bgVar: 'rgba(248, 81, 73, 0.2)',",
    },
    {
        "id": "M13",
        "file": "monaco",
        "desc": "getWorkspaceTerminalStatusStyle prototype key vulnerability",
        "target": "  if (typeof rawStatus === 'string' && Object.hasOwn(WORKSPACE_TERMINAL_STATUS_CONFIG, rawStatus)) {",
        "replacement": "  if (typeof rawStatus === 'string' && (rawStatus in WORKSPACE_TERMINAL_STATUS_CONFIG)) {",
    },
    {
        "id": "M14",
        "file": "monaco",
        "desc": "getWorkspaceTerminalStatusStyle fallback changed to normal text",
        "target": "export const UNKNOWN_TERMINAL_STATUS_STYLE: WorkspaceTerminalStatusConfig = {\n  label: 'UNKNOWN',\n  bgVar: 'var(--color-bg-subtle)',\n  colorVar: 'var(--color-status-unknown)',",
        "replacement": "export const UNKNOWN_TERMINAL_STATUS_STYLE: WorkspaceTerminalStatusConfig = {\n  label: 'UNKNOWN',\n  bgVar: 'var(--color-bg-subtle)',\n  colorVar: 'var(--color-text-primary)',",
    },

    # M15-M26: Explorer & Root Container & Notice Banners
    {
        "id": "M15",
        "file": "monaco",
        "desc": "Root container background literal regression: backgroundColor: '#0d1117'",
        "target": "    <div\n      style={{\n        display: 'flex',\n        flexDirection: 'column',\n        height: 'calc(100vh - 120px)',\n        backgroundColor: 'var(--color-bg-canvas)',",
        "replacement": "    <div\n      style={{\n        display: 'flex',\n        flexDirection: 'column',\n        height: 'calc(100vh - 120px)',\n        backgroundColor: '#0d1117',",
    },
    {
        "id": "M16",
        "file": "monaco",
        "desc": "Root container border subtle collision: border: '1px solid var(--color-bg-canvas)'",
        "target": "        color: 'var(--color-text-primary)',\n        border: '1px solid var(--color-border-subtle)',",
        "replacement": "        color: 'var(--color-text-primary)',\n        border: '1px solid var(--color-bg-canvas)',",
    },
    {
        "id": "M17",
        "file": "monaco",
        "desc": "Unexposed notice connected background literal regression",
        "target": "backgroundColor: projectId && runId && checkoutId ? 'var(--color-diff-added-bg)' : 'var(--color-brand-subtle)',",
        "replacement": "backgroundColor: projectId && runId && checkoutId ? 'rgba(46, 160, 67, 0.12)' : 'var(--color-brand-subtle)',",
    },
    {
        "id": "M18",
        "file": "monaco",
        "desc": "Unexposed notice unconnected background literal regression",
        "target": "backgroundColor: projectId && runId && checkoutId ? 'var(--color-diff-added-bg)' : 'var(--color-brand-subtle)',",
        "replacement": "backgroundColor: projectId && runId && checkoutId ? 'var(--color-diff-added-bg)' : 'rgba(56, 139, 253, 0.12)',",
    },
    {
        "id": "M19",
        "file": "monaco",
        "desc": "Unexposed notice connected text literal regression",
        "target": "color: projectId && runId && checkoutId ? 'var(--color-status-online)' : 'var(--color-brand-hover)',",
        "replacement": "color: projectId && runId && checkoutId ? '#3fb950' : 'var(--color-brand-hover)',",
    },
    {
        "id": "M20",
        "file": "monaco",
        "desc": "Unexposed notice unconnected text literal regression",
        "target": "color: projectId && runId && checkoutId ? 'var(--color-status-online)' : 'var(--color-brand-hover)',",
        "replacement": "color: projectId && runId && checkoutId ? 'var(--color-status-online)' : '#58a6ff',",
    },
    {
        "id": "M21",
        "file": "monaco",
        "desc": "Save error banner background literal regression",
        "target": "          data-testid=\"editor-save-error-banner\"\n          style={{\n            padding: '8px 16px',\n            backgroundColor: 'var(--color-risk-l3-bg)',",
        "replacement": "          data-testid=\"editor-save-error-banner\"\n          style={{\n            padding: '8px 16px',\n            backgroundColor: 'rgba(248, 81, 73, 0.15)',",
    },
    {
        "id": "M22",
        "file": "monaco",
        "desc": "Save warning banner background literal regression",
        "target": "          data-testid=\"editor-context-notice\"\n          style={{\n            padding: '8px 16px',\n            backgroundColor: 'var(--color-bg-subtle)',\n            borderBottom: '1px solid var(--color-status-degraded)',",
        "replacement": "          data-testid=\"editor-context-notice\"\n          style={{\n            padding: '8px 16px',\n            backgroundColor: 'rgba(227, 179, 65, 0.15)',\n            borderBottom: '1px solid var(--color-status-degraded)',",
    },
    {
        "id": "M23",
        "file": "monaco",
        "desc": "Save success banner background literal regression",
        "target": "          data-testid=\"editor-save-success-notice\"\n          style={{\n            padding: '8px 16px',\n            backgroundColor: 'var(--color-diff-added-bg)',",
        "replacement": "          data-testid=\"editor-save-success-notice\"\n          style={{\n            padding: '8px 16px',\n            backgroundColor: 'rgba(46, 160, 67, 0.15)',",
    },
    {
        "id": "M24",
        "file": "monaco",
        "desc": "Explorer sidebar background literal regression",
        "target": "        <div\n          style={{\n            width: '240px',\n            backgroundColor: 'var(--color-bg-canvas)',",
        "replacement": "        <div\n          style={{\n            width: '240px',\n            backgroundColor: '#0d1117',",
    },
    {
        "id": "M25",
        "file": "monaco",
        "desc": "Explorer active file background literal regression",
        "target": "                  backgroundColor: file.path === activeFilePath ? 'var(--color-brand-subtle)' : 'transparent',",
        "replacement": "                  backgroundColor: file.path === activeFilePath ? '#1f242c' : 'transparent',",
    },
    {
        "id": "M26",
        "file": "monaco",
        "desc": "Explorer active file text literal regression",
        "target": "                  color: file.path === activeFilePath ? 'var(--color-brand-hover)' : 'var(--color-text-primary)',",
        "replacement": "                  color: file.path === activeFilePath ? '#58a6ff' : 'var(--color-text-primary)',",
    },

    # M27-M34: Editor Toolbar, Tabs, Gutters, Code Textareas
    {
        "id": "M27",
        "file": "monaco",
        "desc": "Top toolbar background literal regression",
        "target": "      {/* Top Main Toolbar */}\n      <div\n        style={{\n          display: 'flex',\n          justifyContent: 'space-between',\n          alignItems: 'center',\n          padding: '8px 16px',\n          backgroundColor: 'var(--color-bg-surface)',",
        "replacement": "      {/* Top Main Toolbar */}\n      <div\n        style={{\n          display: 'flex',\n          justifyContent: 'space-between',\n          alignItems: 'center',\n          padding: '8px 16px',\n          backgroundColor: '#161b22',",
    },
    {
        "id": "M28",
        "file": "monaco",
        "desc": "Top toolbar workspace text literal regression",
        "target": "          <span style={{ fontWeight: 600, color: 'var(--color-text-primary)', fontSize: '14px' }}>",
        "replacement": "          <span style={{ fontWeight: 600, color: '#f0f6fc', fontSize: '14px' }}>",
    },
    {
        "id": "M29",
        "file": "monaco",
        "desc": "Editor tab bar background literal regression",
        "target": "                {/* Editor Tab Bar */}\n                <div\n                  style={{\n                    display: 'flex',\n                    alignItems: 'center',\n                    justifyContent: 'space-between',\n                    padding: '6px 16px',\n                    backgroundColor: 'var(--color-bg-surface)',\n                    borderBottom: '1px solid var(--color-border-subtle)',\n                    fontSize: '12px',\n                  }}\n                >\n                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>\n                    <span style={{ fontFamily: 'var(--font-mono, monospace)', color: 'var(--color-text-primary)' }}>\n                      {activeFile.path}\n                    </span>\n                    {activeFile.isDirty && <span style={{ color: 'var(--color-status-degraded)' }}>(modified)</span>}",
        "replacement": "                {/* Editor Tab Bar */}\n                <div\n                  style={{\n                    display: 'flex',\n                    alignItems: 'center',\n                    justifyContent: 'space-between',\n                    padding: '6px 16px',\n                    backgroundColor: '#161b22',\n                    borderBottom: '1px solid var(--color-border-subtle)',\n                    fontSize: '12px',\n                  }}\n                >\n                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>\n                    <span style={{ fontFamily: 'var(--font-mono, monospace)', color: 'var(--color-text-primary)' }}>\n                      {activeFile.path}\n                    </span>\n                    {activeFile.isDirty && <span style={{ color: 'var(--color-status-degraded)' }}>(modified)</span>}",
    },
    {
        "id": "M30",
        "file": "monaco",
        "desc": "Normal editor gutter background literal regression",
        "target": "                {/* Editor Textarea with Line Numbers */}\n                <div style={{ flex: 1, display: 'flex', backgroundColor: 'var(--color-bg-canvas)', overflow: 'hidden' }}>\n                  {/* Line Numbers Gutter */}\n                  <div\n                    style={{\n                      width: '44px',\n                      padding: '12px 6px',\n                      backgroundColor: 'var(--color-bg-subtle)',",
        "replacement": "                {/* Editor Textarea with Line Numbers */}\n                <div style={{ flex: 1, display: 'flex', backgroundColor: 'var(--color-bg-canvas)', overflow: 'hidden' }}>\n                  {/* Line Numbers Gutter */}\n                  <div\n                    style={{\n                      width: '44px',\n                      padding: '12px 6px',\n                      backgroundColor: '#090d13',",
    },
    {
        "id": "M31",
        "file": "monaco",
        "desc": "Normal editor gutter border literal regression",
        "target": "                {/* Editor Textarea with Line Numbers */}\n                <div style={{ flex: 1, display: 'flex', backgroundColor: 'var(--color-bg-canvas)', overflow: 'hidden' }}>\n                  {/* Line Numbers Gutter */}\n                  <div\n                    style={{\n                      width: '44px',\n                      padding: '12px 6px',\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      borderRight: '1px solid var(--color-border-subtle)',",
        "replacement": "                {/* Editor Textarea with Line Numbers */}\n                <div style={{ flex: 1, display: 'flex', backgroundColor: 'var(--color-bg-canvas)', overflow: 'hidden' }}>\n                  {/* Line Numbers Gutter */}\n                  <div\n                    style={{\n                      width: '44px',\n                      padding: '12px 6px',\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      borderRight: '1px solid #21262d',",
    },
    {
        "id": "M32",
        "file": "monaco",
        "desc": "Normal editor gutter text literal regression",
        "target": "                {/* Editor Textarea with Line Numbers */}\n                <div style={{ flex: 1, display: 'flex', backgroundColor: 'var(--color-bg-canvas)', overflow: 'hidden' }}>\n                  {/* Line Numbers Gutter */}\n                  <div\n                    style={{\n                      width: '44px',\n                      padding: '12px 6px',\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      borderRight: '1px solid var(--color-border-subtle)',\n                      color: 'var(--color-text-muted)',",
        "replacement": "                {/* Editor Textarea with Line Numbers */}\n                <div style={{ flex: 1, display: 'flex', backgroundColor: 'var(--color-bg-canvas)', overflow: 'hidden' }}>\n                  {/* Line Numbers Gutter */}\n                  <div\n                    style={{\n                      width: '44px',\n                      padding: '12px 6px',\n                      backgroundColor: 'var(--color-bg-subtle)',\n                      borderRight: '1px solid var(--color-border-subtle)',\n                      color: '#484f58',",
    },
    {
        "id": "M33",
        "file": "monaco",
        "desc": "Frozen snapshot gutter background literal regression",
        "target": "                {/* Frozen Code Area */}\n                <div style={{ flex: 1, display: 'flex', backgroundColor: 'var(--color-bg-canvas)', overflow: 'hidden' }}>\n                  {/* Line Numbers Gutter */}\n                  <div\n                    style={{\n                      width: '44px',\n                      padding: '12px 6px',\n                      backgroundColor: 'var(--color-bg-subtle)',",
        "replacement": "                {/* Frozen Code Area */}\n                <div style={{ flex: 1, display: 'flex', backgroundColor: 'var(--color-bg-canvas)', overflow: 'hidden' }}>\n                  {/* Line Numbers Gutter */}\n                  <div\n                    style={{\n                      width: '44px',\n                      padding: '12px 6px',\n                      backgroundColor: '#070a0e',",
    },
    {
        "id": "M34",
        "file": "monaco",
        "desc": "Frozen snapshot read-only badge background literal regression",
        "target": "                        padding: '1px 6px',\n                        borderRadius: '4px',\n                        fontSize: '11px',\n                        fontWeight: 600,\n                        backgroundColor: 'var(--color-bg-subtle)',\n                        color: 'var(--color-status-degraded)',",
        "replacement": "                        padding: '1px 6px',\n                        borderRadius: '4px',\n                        fontSize: '11px',\n                        fontWeight: 600,\n                        backgroundColor: 'rgba(210, 153, 34, 0.2)',\n                        color: 'var(--color-status-degraded)',",
    },

    # M35-M40: Embedded Terminal & PTY Area
    {
        "id": "M35",
        "file": "monaco",
        "desc": "Terminal container background literal regression",
        "target": "          <div\n            style={{\n              height: '240px',\n              borderTop: '1px solid var(--color-border-subtle)',\n              backgroundColor: 'var(--color-bg-canvas)',",
        "replacement": "          <div\n            style={{\n              height: '240px',\n              borderTop: '1px solid var(--color-border-subtle)',\n              backgroundColor: '#090d13',",
    },
    {
        "id": "M36",
        "file": "monaco",
        "desc": "Terminal title bar background literal regression",
        "target": "            {/* Terminal Title / Recovery Bar */}\n            <div\n              style={{\n                display: 'flex',\n                justifyContent: 'space-between',\n                alignItems: 'center',\n                padding: '6px 14px',\n                backgroundColor: 'var(--color-bg-surface)',",
        "replacement": "            {/* Terminal Title / Recovery Bar */}\n            <div\n              style={{\n                display: 'flex',\n                justifyContent: 'space-between',\n                alignItems: 'center',\n                padding: '6px 14px',\n                backgroundColor: '#161b22',",
    },
    {
        "id": "M37",
        "file": "monaco",
        "desc": "Terminal mock notice background literal regression",
        "target": "                  data-testid=\"editor-terminal-mock-notice\"\n                  role=\"status\"\n                  aria-live=\"polite\"\n                  style={{\n                    fontSize: '11px',\n                    color: 'var(--color-status-degraded)',\n                    padding: '1px 6px',\n                    borderRadius: '4px',\n                    backgroundColor: 'var(--color-bg-subtle)',",
        "replacement": "                  data-testid=\"editor-terminal-mock-notice\"\n                  role=\"status\"\n                  aria-live=\"polite\"\n                  style={{\n                    fontSize: '11px',\n                    color: 'var(--color-status-degraded)',\n                    padding: '1px 6px',\n                    borderRadius: '4px',\n                    backgroundColor: 'rgba(227, 179, 65, 0.15)',",
    },
    {
        "id": "M38",
        "file": "monaco",
        "desc": "Terminal prompt output text literal regression",
        "target": "                  <span style={{ color: 'var(--color-brand-primary)' }}>saintvision@wsp:~$ {cmd.command}</span>",
        "replacement": "                  <span style={{ color: '#58a6ff' }}>saintvision@wsp:~$ {cmd.command}</span>",
    },
    {
        "id": "M39",
        "file": "monaco",
        "desc": "Terminal resume report background literal regression",
        "target": "                  style={{\n                    margin: '6px 0',\n                    padding: '6px 10px',\n                    backgroundColor: 'var(--color-brand-subtle)',",
        "replacement": "                  style={{\n                    margin: '6px 0',\n                    padding: '6px 10px',\n                    backgroundColor: 'rgba(56, 139, 253, 0.1)',",
    },
    {
        "id": "M40",
        "file": "monaco",
        "desc": "Terminal command form prompt $ text literal regression",
        "target": "              <span style={{ color: 'var(--color-status-online)', fontFamily: 'var(--font-mono, monospace)', fontSize: '13px', marginRight: '6px' }}>\n                $",
        "replacement": "              <span style={{ color: '#3fb950', fontFamily: 'var(--font-mono, monospace)', fontSize: '13px', marginRight: '6px' }}>\n                $",
    },
]


def get_clean_status():
    res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=WORKTREE_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return res.stdout.strip()


def run_single_mutant(mutant, originals):
    mid = mutant["id"]
    target_path = TARGET_FILES[mutant["file"]]
    target_str = mutant["target"]
    replacement_str = mutant["replacement"]

    content = target_path.read_text(encoding="utf-8")
    if target_str not in content:
        return {
            "id": mid,
            "desc": mutant["desc"],
            "status": "target_not_found",
            "error": f"Target string not found in {target_path}",
        }

    # Apply mutation
    mutated_content = content.replace(target_str, replacement_str, 1)
    target_path.write_text(mutated_content, encoding="utf-8")

    tsc_ok = False
    killed = False
    error_msg = ""

    try:
        # 1. TypeScript compilation check: MUST succeed
        tsc_cmd = ["cmd", "/c", "npx", "tsc", "-b"] if os.name == "nt" else ["npx", "tsc", "-b"]
        tsc_res = subprocess.run(
            tsc_cmd,
            cwd=APPS_WEB,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if tsc_res.returncode != 0:
            return {
                "id": mid,
                "desc": mutant["desc"],
                "status": "tsc_failed",
                "error": f"TypeScript compilation failed:\n{tsc_res.stderr or tsc_res.stdout}",
            }
        tsc_ok = True

        # 2. Vitest: MUST fail (be killed)
        vitest_cmd = [
            "cmd", "/c", "npx", "vitest", "run", "tests/acc09-contrast-tokens.test.tsx"
        ] if os.name == "nt" else [
            "npx", "vitest", "run", "tests/acc09-contrast-tokens.test.tsx"
        ]

        vitest_res = subprocess.run(
            vitest_cmd,
            cwd=APPS_WEB,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )

        if vitest_res.returncode != 0:
            killed = True
            error_msg = f"Killed successfully (exit {vitest_res.returncode})"
        else:
            killed = False
            error_msg = "SURVIVED: test suite unexpectedly passed with mutant!"

    except subprocess.TimeoutExpired:
        return {
            "id": mid,
            "desc": mutant["desc"],
            "status": "timeout",
            "error": "Test run timed out (>120s)",
        }
    finally:
        # CRITICAL: Always restore byte-clean using original bytes
        target_path.write_bytes(originals[mutant["file"]])
        status = get_clean_status()
        if status:
            print(f"FATAL: Working tree dirty after restoring {mid}: {status}", file=sys.stderr)
            sys.exit(1)

    return {
        "id": mid,
        "desc": mutant["desc"],
        "status": "killed" if killed else "survived",
        "tsc_ok": tsc_ok,
        "detail": error_msg,
    }


def main():
    parser = argparse.ArgumentParser(description="Card 281 Mutation Verification Runner")
    parser.add_argument("--mutant", help="Run a specific mutant by ID (e.g. M1)")
    parser.add_argument("--all", action="store_true", help="Run all 40 mutants sequentially")
    parser.add_argument("--list", action="store_true", help="List all available mutants")
    args = parser.parse_args()

    if args.list:
        print(f"Total Mutants: {len(MUTANTS)}")
        for m in MUTANTS:
            print(f"  [{m['id']}] ({m['file']}) {m['desc']}")
        return

    # Check clean working tree before starting
    init_status = get_clean_status()
    if init_status:
        print(f"Error: Git working tree must be clean before running mutants!\n{init_status}", file=sys.stderr)
        sys.exit(1)

    # Read original bytes for all target files
    originals = {fkey: path.read_bytes() for fkey, path in TARGET_FILES.items()}

    to_run = MUTANTS
    if args.mutant:
        to_run = [m for m in MUTANTS if m["id"] == args.mutant]
        if not to_run:
            print(f"Error: Mutant ID {args.mutant} not found!", file=sys.stderr)
            sys.exit(1)
    elif not args.all:
        print("Please specify --all or --mutant <id> (use --list to view all)")
        return

    # Record commit SHA before running
    head_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=WORKTREE_ROOT, text=True, encoding="utf-8", errors="replace"
    ).strip()

    start_time = datetime.now(timezone.utc)
    results = []

    print(f"Starting execution of {len(to_run)} mutants at {start_time.isoformat()}...")
    print(f"Head SHA: {head_sha}")
    print("-" * 70)

    for i, m in enumerate(to_run, 1):
        print(f"[{i}/{len(to_run)}] Running {m['id']}: {m['desc']} ...", end=" ", flush=True)
        res = run_single_mutant(m, originals)
        print(f"{res['status'].upper()}")
        results.append(res)
        if res["status"] != "killed":
            print(f"   --> {res.get('error') or res.get('detail')}")

    end_time = datetime.now(timezone.utc)
    duration_s = (end_time - start_time).total_seconds()

    killed_count = sum(1 for r in results if r["status"] == "killed")
    survived_count = sum(1 for r in results if r["status"] == "survived")
    timeout_count = sum(1 for r in results if r["status"] == "timeout")
    tsc_fail_count = sum(1 for r in results if r["status"] == "tsc_failed")

    summary = {
        "timestamp": end_time.isoformat(),
        "sourceHeadSha": head_sha,
        "totalMutants": len(to_run),
        "killed": killed_count,
        "survived": survived_count,
        "timeouts": timeout_count,
        "tsc_fails": tsc_fail_count,
        "durationSeconds": round(duration_s, 2),
        "killRate": f"{(killed_count / len(to_run) * 100):.1f}%",
        "mutants": results,
    }

    # Save to receipt file only when running --all
    if args.all and len(to_run) == len(MUTANTS):
        RESULTS_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Saved mutation receipt to {RESULTS_FILE}")

    print("=" * 70)
    print(f"SUMMARY: Kill Rate: {killed_count}/{len(to_run)} ({summary['killRate']}) in {duration_s:.1f}s")
    print(f"  killed: {killed_count}, survived: {survived_count}, timeouts: {timeout_count}, tsc_fails: {tsc_fail_count}")

    if killed_count != len(to_run):
        sys.exit(1)


if __name__ == "__main__":
    main()
