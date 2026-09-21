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


def _env_gates():
    """The environment gates AT THE MOMENT THIS IS CALLED. env_gates is a signal, and today's
    whole lesson is that a signal must say *what time* it is about -- so callers stamp the moment:
    bare mode = report time; wrap mode = the check's own invocation (same process as the check)."""
    return {
        'gate_postgres_dsn': 'set' if os.environ.get('INV_TEST_ADMIN_DSN') else 'absent',
        'gate_docker': 'present' if shutil.which('docker') else 'absent',
        'gate_go': 'present' if shutil.which('go') else 'absent',
        'gate_node': 'present' if shutil.which('node') else 'absent',
    }


def _resolve_executable(name):
    """Make wrap mode robust on Windows. CreateProcess (subprocess with shell=False) does not
    find a RELATIVE path that uses forward slashes -- e.g. .venv/Scripts/python.exe -- so the
    label's own advice (`provenance.py -- <cmd>`) died with WinError 2. Resolve cmd[0] to an
    absolute path when it names a file, or via PATH (PATHEXT-aware) when it's a bare name; an
    absolute path with forward slashes is already tolerated by Windows."""
    has_sep = (os.sep in name) or (os.altsep is not None and os.altsep in name)
    if has_sep:
        cand = os.path.abspath(name)
        if os.path.isfile(cand):
            return cand
        if os.name == 'nt' and os.path.isfile(cand + '.exe'):
            return cand + '.exe'
        return cand  # not found; let subprocess raise, caught and reported cleanly below
    return shutil.which(name) or name


def _integration_distance(ref, do_fetch):
    """How far THIS tree is from the integration tip -- the gap that stayed invisible all of
    2026-09-21 because the main checkout sat ~12 commits behind and nobody printed it. Measured
    LOCALLY against the last-fetched ref by default (no network); `--fetch` refreshes first."""
    mode = 'local (last fetch)'
    if do_fetch:
        frc, _, _ = _git('fetch', 'origin', '--quiet')
        mode = 'fetched' if frc == 0 else 'local (fetch failed)'
    rc, isha, _ = _git('rev-parse', ref)
    if rc != 0:
        return {'integration_ref': ref, 'integration_sha': None, 'integration_check_mode': mode,
                'in_sync': None, 'behind': None, 'ahead': None}
    _, behind, _ = _git('rev-list', '--count', f'HEAD..{ref}')
    _, ahead, _ = _git('rev-list', '--count', f'{ref}..HEAD')
    behind, ahead = int(behind or 0), int(ahead or 0)
    return {'integration_ref': ref, 'integration_sha': isha, 'integration_check_mode': mode,
            'in_sync': (behind == 0 and ahead == 0), 'behind': behind, 'ahead': ahead}


def collect(executor=None, integration_ref='origin/integration/all-agents-unified', do_fetch=False):
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
    integ = _integration_distance(integration_ref, do_fetch)

    return {
        # --- required ---
        'commit_sha': sha,
        'branch': branch,
        'worktree_path': toplevel,
        # --- distance to the integration tip (the gap that hid all day) ---
        **integ,
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
        **_env_gates(),
        # env_gates default to the report-time snapshot; wrap mode overrides this to the check's
        # own invocation so a torn-down PG (or a DSN set only in the check's shell) cannot be
        # misread as the environment the check actually ran in.
        'env_context': 'report-time snapshot -- NOT necessarily a check runtime; run `provenance.py -- <cmd>` for a check\'s own environment',
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
    if p.get('integration_sha') is None:
        lines.append(f"integration_sync:    UNKNOWN   (ref {p['integration_ref']} not found locally; pass --fetch or --integration-ref)")
    elif p['in_sync']:
        lines.append(f"integration_sync:    IN SYNC   (== {p['integration_ref']} @{p['integration_sha'][:12]}; {p['integration_check_mode']})")
    else:
        state = []
        if p['behind']:
            state.append(f"BEHIND {p['behind']}")
        if p['ahead']:
            state.append(f"AHEAD {p['ahead']}")
        lines.append(f"integration_sync:    {' '.join(state)}   (vs {p['integration_ref']} @{p['integration_sha'][:12]}; {p['integration_check_mode']}) -- results from this tree may NOT reflect integration")
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
        f"  as-of:             {p.get('env_context', 'report-time snapshot')}",
    ]
    if p.get('env_changed'):
        lines.append(f"  WARNING env changed during check: {p['env_changed']} -- the check ran under the 'at check start' values above")
    lines.append(f"cwd:                 {p['cwd']}")
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='emit JSON')
    parser.add_argument('--executor', help='who ran this (stamped into the header)')
    parser.add_argument('--integration-ref', default='origin/integration/all-agents-unified',
                        help='ref to measure distance to (default: origin/integration/all-agents-unified)')
    parser.add_argument('--fetch', action='store_true',
                        help='refresh the integration ref over the network before measuring (default: local last-fetch)')
    parser.add_argument('command', nargs=argparse.REMAINDER,
                        help='after `--`, a command to run WITHOUT a pipe and self-identify')
    args = parser.parse_args()

    prov = collect(executor=args.executor, integration_ref=args.integration_ref, do_fetch=args.fetch)
    cmd = args.command[1:] if args.command and args.command[0] == '--' else args.command

    if cmd:
        # Wrap mode: env_gates in `prov` were captured just now, in THIS process, immediately
        # before the check runs -- i.e. the check's own invocation environment, not a later
        # report-time snapshot. Stamp that, run the check without a pipe, then re-read the gates
        # and warn if they changed while the check ran (a divergence is itself worth knowing).
        prov['env_context'] = 'at check invocation (same process/shell as the check)'
        pre = {k: prov[k] for k in ('gate_postgres_dsn', 'gate_docker', 'gate_go', 'gate_node')}
        cmd = [_resolve_executable(cmd[0])] + cmd[1:]      # relative/venv/forward-slash safe
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except (FileNotFoundError, OSError) as exc:
            # The wrapped command could not be launched. Report it cleanly instead of a raw
            # traceback, so the alternative the label points at fails loudly, not silently.
            print(render_text(prov))
            print(f"command:             {' '.join(cmd)}")
            print(f"command_cwd:         {os.getcwd()}")
            print("exit_code:           127")
            print(f"error:               could not launch command -- {type(exc).__name__}: {exc}. "
                  "Pass an absolute path or a PATH-resolvable name.")
            return 127
        post = _env_gates()
        diffs = [f"{k.replace('gate_', '')}: {pre[k]}->{post[k]}" for k in pre if pre[k] != post[k]]
        if diffs:
            prov['env_changed'] = '; '.join(diffs)
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
