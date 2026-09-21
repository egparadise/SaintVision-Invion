"""Emit the verification provenance header, so a "check passed" report can prove
*where and how* it ran. A recommendation nobody runs is worth nothing; this makes the
header mechanical -- paste the output, or wrap a check so it self-identifies.

Usage:
  python tools/provenance.py                 # print the header (text)
  python tools/provenance.py --json          # print it as JSON
  python tools/provenance.py --executor NAME # stamp who ran it
  python tools/provenance.py -- <cmd...>     # print header, run <cmd> WITHOUT a pipe
                                             # (so the exit code is never masked), then
                                             # print the command, exit code and output tail;
                                             # exits with the command's own code.

Design notes tied to today's failures (2026-09-21):
- interpreter is sys.executable -- the *actual* running interpreter, so a bare `python`
  (system) vs `.venv` interpreter can never be silently confused again.
- working-tree-clean is reported by BOTH `git status --porcelain` (byte-level; flags CRLF)
  and `git diff --quiet HEAD` (content-level; EOL-normalized). When the first is dirty but
  the second is clean, the difference is an EOL/untracked artifact, not real drift -- exactly
  the models.py CRLF case. EOL-drift gates must be judged by `git diff --exit-code`.
- exit codes are captured directly (subprocess return code), never through `| tail`, which
  masks the pipeline's exit.
"""
import argparse
import datetime
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git(*args, cwd=None):
    try:
        out = subprocess.run(['git', *args], capture_output=True, text=True,
                             cwd=cwd or os.getcwd())
        return out.returncode, out.stdout.strip(), out.stderr.strip()
    except FileNotFoundError:
        return 127, '', 'git not found'


def _tool_version(name, *ver_args):
    path = shutil.which(name)
    if not path:
        return None, None
    try:
        out = subprocess.run([name, *ver_args], capture_output=True, text=True)
        return path, out.stdout.strip() or out.stderr.strip()
    except OSError:
        return path, None


def collect(executor=None):
    rc, sha, _ = _git('rev-parse', 'HEAD')
    _, branch, _ = _git('rev-parse', '--abbrev-ref', 'HEAD')
    _, toplevel, _ = _git('rev-parse', '--show-toplevel')
    _, porcelain, _ = _git('status', '--porcelain')
    status_clean = (porcelain == '')
    diff_rc, _, _ = _git('diff', '--quiet', 'HEAD')      # 0 == content clean (EOL-normalized)
    content_clean = (diff_rc == 0)
    modified = [ln[3:] for ln in porcelain.splitlines() if not ln.startswith('??')]
    untracked = [ln[3:] for ln in porcelain.splitlines() if ln.startswith('??')]
    if branch == 'HEAD':
        branch = f'(detached@{sha[:12]})'

    node_path, node_ver = _tool_version('node', '--version')
    go_path, go_ver = _tool_version('go', 'version')
    kst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(tz=kst)

    return {
        # --- required ---
        'commit_sha': sha,
        'branch': branch,
        'worktree_path': toplevel,
        'working_tree_clean_status': status_clean,          # git status --porcelain empty
        'content_clean_diff': content_clean,                # git diff --quiet HEAD
        'eol_or_untracked_only': (not status_clean) and content_clean,
        'modified_paths': modified,
        'untracked_paths': untracked,
        'interpreter': sys.executable,                      # the ACTUAL running interpreter
        'runtime_python': platform.python_version(),
        'timestamp_kst': now.isoformat(timespec='seconds'),
        'executor': executor or os.environ.get('USERNAME') or os.environ.get('USER') or 'unspecified',
        # --- optional / environment fingerprint (grounds "what was NOT run and why") ---
        'os_platform': platform.platform(),
        'runtime_node': node_ver,
        'runtime_go': go_ver,
        'gate_postgres_dsn': 'set' if os.environ.get('INV_TEST_ADMIN_DSN') else 'absent',
        'gate_docker': 'present' if shutil.which('docker') else 'absent',
        'gate_go': 'present' if go_path else 'absent',
        'gate_node': 'present' if node_path else 'absent',
        'cwd': os.getcwd(),
    }


def render_text(p):
    lines = ['=== verification provenance ===']
    clean = 'YES' if p['working_tree_clean_status'] else 'NO'
    lines += [
        f"commit_sha:          {p['commit_sha']}",
        f"branch:              {p['branch']}",
        f"worktree_path:       {p['worktree_path']}",
        f"working_tree_clean:  {clean}   (git status --porcelain)",
    ]
    if not p['working_tree_clean_status']:
        lines.append(f"  content_clean:     {'YES' if p['content_clean_diff'] else 'NO'}   (git diff --quiet HEAD; EOL-normalized)")
        if p['eol_or_untracked_only']:
            lines.append("  note:              status-dirty but content-clean -> EOL/untracked artifact, not real drift (judge EOL gates by `git diff --exit-code`)")
        if p['modified_paths']:
            lines.append(f"  modified:          {', '.join(p['modified_paths'][:20])}")
        if p['untracked_paths']:
            lines.append(f"  untracked:         {', '.join(p['untracked_paths'][:20])}")
    lines += [
        f"interpreter:         {p['interpreter']}",
        f"runtime_python:      {p['runtime_python']}",
        f"runtime_node:        {p['runtime_node'] or '(absent)'}",
        f"timestamp_kst:       {p['timestamp_kst']}",
        f"executor:            {p['executor']}   (reviewer must be a different person for independent verification)",
        f"os_platform:         {p['os_platform']}",
        f"env_gates:           postgres_dsn={p['gate_postgres_dsn']}; docker={p['gate_docker']}; go={p['gate_go']}; node={p['gate_node']}",
        f"cwd:                 {p['cwd']}",
    ]
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='emit JSON')
    parser.add_argument('--executor', help='who ran this (stamped into the header)')
    parser.add_argument('command', nargs=argparse.REMAINDER,
                        help='after `--`, a command to run WITHOUT a pipe and self-identify')
    args = parser.parse_args()

    prov = collect(executor=args.executor)
    cmd = args.command[1:] if args.command and args.command[0] == '--' else args.command

    if cmd:
        # Wrap mode: run the check directly, capture its exit without pipe-masking.
        result = subprocess.run(cmd, capture_output=True, text=True)
        tail = '\n'.join((result.stdout + result.stderr).splitlines()[-5:])
        if args.json:
            prov.update({'command': cmd, 'command_cwd': os.getcwd(),
                         'exit_code': result.returncode, 'output_tail': tail})
            print(json.dumps(prov, indent=2))
        else:
            print(render_text(prov))
            print(f"command:             {' '.join(cmd)}")
            print(f"command_cwd:         {os.getcwd()}")
            print(f"exit_code:           {result.returncode}")
            print("output_tail:")
            print('\n'.join('  ' + ln for ln in tail.splitlines()))
        return result.returncode

    print(json.dumps(prov, indent=2) if args.json else render_text(prov))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
