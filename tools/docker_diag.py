"""Tell a docker/daemon error apart from a host process-creation failure or a timeout.

VF-CL-R-001 root cause: intermittent docker-command failures on this Windows host
were STATUS_DLL_INIT_FAILED (exit 0xC0000142) -- the OS could not start docker.exe
under handle/RAM pressure -- not a docker daemon fault. The daemon was healthy
throughout (docker version fine; 10/10 re-runs of the failing inspect succeeded).

A Windows NTSTATUS error-severity exit code is not docker semantics, so reporting
it as its own category makes a failure falsifiable (host vs daemon vs product). A
timeout is a third category: the docker CLI was started but did not return in time,
again a host-pressure symptom rather than a product assertion result. All are
distinguished so an unverifiable run is recorded as *unverified*, never as a product
failure and never as a suppressed blank.

Retry safety (Codex R3-01, 2026-09-18): a retry is only safe when the process
provably *never ran*, because a mutating docker command (``volume create``, ``run``)
that already took effect would create a duplicate on re-run. "Any error-severity
NTSTATUS" is too broad: 0xC0000142 STATUS_DLL_INIT_FAILED and 0xC0000135
STATUS_DLL_NOT_FOUND are *loader-stage* failures before the entry point (safe to
retry), but 0xC0000005 (access violation) is a crash *after* the process started, and
a negative POSIX returncode is a signal (e.g. -9 SIGKILL) -- both ran, so neither is
retried. The classifier is therefore an explicit allowlist, and it is platform-gated:
an NTSTATUS is only meaningful on Windows, so a negative code on POSIX is never read
as one.

Retry breadth (image-lane finding): even a genuine loader failure is retried at most
once, as a transient-blip cushion. Under *sustained* host pressure a retry cannot
clear the condition and each attempt adds one more process-creation to the pressure,
so the honest recovery is classification -- the caller records the outcome as
unverified (a pre-run host check or a pytest.skip), not more retries.
``is_infrastructure_failure`` is the predicate the callers use for that decision.
"""

from __future__ import annotations

import re
import subprocess
import sys
import time

# URL form: ``scheme://user:password@host`` (e.g. an SQLAlchemy-rendered DSN).
_URL_CREDENTIAL = re.compile(r'(://[^:@/\s]+:)[^@/\s]+(@)')
# libpq keyword form: ``password=secret`` / ``password='quoted secret'`` / "double".
# Only the value is masked; the ``password=`` marker and every other keyword stay so
# the error kind is preserved.
_LIBPQ_PASSWORD = re.compile(
    r"(?i)(password\s*=\s*)('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|\S+)")

#: NTSTATUS codes that mean the image failed to load / initialise *before* reaching
#: its entry point -- the process never ran, so a mutating command is safe to retry.
#: A running-process crash (0xC0000005 access violation, 0xC00000FD stack overflow, …)
#: is deliberately absent: it ran, and may already have taken effect.
_INIT_FAILURE_NTSTATUS = frozenset({
    0xC0000142,  # STATUS_DLL_INIT_FAILED -- a DLL's init failed at load (our observed code)
    0xC0000135,  # STATUS_DLL_NOT_FOUND   -- a required DLL was missing at load
})

#: Synthetic returncode for a docker CLI call that did not return within its timeout.
#: 124 is the conventional timeout exit code and is not a docker exit code; the
#: CompletedProcess ``run`` returns also carries ``.timed_out = True`` so nothing has
#: to classify a timeout from the number alone.
TIMEOUT_RETURNCODE = 124


def _on_windows() -> bool:
    return sys.platform == 'win32'


def is_host_process_init_failure(returncode, *, windows=None) -> bool:
    """True only for a Windows *loader-stage* failure whose process never reached its
    entry point (STATUS_DLL_INIT_FAILED / STATUS_DLL_NOT_FOUND), so a mutating command
    is safe to retry.

    NOT true for a running-process crash (e.g. 0xC0000005 access violation) or a POSIX
    signal (a negative returncode such as -9 SIGKILL): those ran, or may have, and a
    re-run could duplicate a resource. The platform is honoured -- an NTSTATUS is only
    meaningful on Windows -- so ``windows`` defaults to the current platform and is
    injectable for tests. Normal docker exit codes (0-255) are never in the allowlist.
    """
    if windows is None:
        windows = _on_windows()
    if not windows:
        return False
    return (int(returncode) & 0xFFFFFFFF) in _INIT_FAILURE_NTSTATUS


def timed_out(result) -> bool:
    """True if ``run`` synthesised this result from a subprocess timeout."""
    return bool(getattr(result, 'timed_out', False))


def is_infrastructure_failure(result) -> bool:
    """True when a non-zero result is a *host condition* -- a loader-stage
    process-creation failure or a timeout -- rather than a docker/daemon/product
    error.

    The caller uses this to record the outcome as *unverified* (a pytest.skip or a
    pre-run host-check abort) instead of a failure: the product assertion was never
    reached, so calling it a failure would be a false product defect, and letting the
    exception escape would be the same masked hole this module removes. A real docker
    error, and a running-process *crash* (which may indicate a real problem and is
    unsafe to treat as "never happened"), are not infrastructure failures and still
    fail loudly."""
    return getattr(result, 'returncode', 0) != 0 and (
        timed_out(result) or is_host_process_init_failure(result.returncode))


def masked_stderr(stderr) -> str:
    """Bounded docker stderr with credential *values* masked in every form that can
    appear in a DSN -- a URL ``user:password@``, and a libpq/query ``password=`` value
    whether bare, single- or double-quoted -- while the error kind and non-secret
    keywords are preserved."""
    text = stderr.decode('utf-8', 'replace') if isinstance(stderr, (bytes, bytearray)) else str(stderr or '')
    text = _URL_CREDENTIAL.sub(r'\1***\2', text)
    text = _LIBPQ_PASSWORD.sub(r'\1***', text)
    return text.strip()[:400] or '(no stderr)'


def describe_failure(returncode, stderr=b'', is_timeout=False, windows=None) -> str:
    """One falsifiable line naming the failure *category*: a timeout, a loader-stage
    host process-creation failure, a running-process crash/signal (named apart because
    it ran and is not retried), or a plain docker error keeping its masked stderr.
    Nothing is guessed at, and no secret value is emitted."""
    if windows is None:
        windows = _on_windows()
    rc = int(returncode) & 0xFFFFFFFF
    if is_timeout:
        return (f'docker operation timed out ({masked_stderr(stderr)}); the CLI was started '
                f'but did not return -- host resource pressure or a hung operation, not a '
                f'product assertion result')
    if is_host_process_init_failure(returncode, windows=windows):
        return (f'host process-creation failed (NTSTATUS 0x{rc:08X}); the OS could not start '
                f'the process -- host resource/handle pressure, not a docker/daemon error')
    if windows and rc >= 0xC0000000:
        return (f'process crashed after starting (NTSTATUS 0x{rc:08X}); it ran, so a mutating '
                f'command is not retried -- {masked_stderr(stderr)}')
    if not windows and int(returncode) < 0:
        return (f'killed by signal {-int(returncode)}; the process ran, so a mutating command '
                f'is not retried -- {masked_stderr(stderr)}')
    return f'docker exit {returncode}: {masked_stderr(stderr)}'


def describe(result) -> str:
    """``describe_failure`` for a CompletedProcess, honouring a synthesised timeout."""
    return describe_failure(result.returncode, getattr(result, 'stderr', b''),
                            is_timeout=timed_out(result))


def _text_mode(kwargs) -> bool:
    """True when subprocess.run would decode stdout/stderr to ``str`` for this call
    (``text=``/``universal_newlines=``, or an explicit ``encoding``/``errors``)."""
    return bool(kwargs.get('text') or kwargs.get('universal_newlines')
                or kwargs.get('encoding') is not None or kwargs.get('errors') is not None)


def _timeout_result(argv, exc, timeout, *, text_mode) -> subprocess.CompletedProcess:
    """A classified CompletedProcess standing in for a ``TimeoutExpired`` so a timeout
    is surfaced as a category, never raised out as an unclassified hole -- carrying
    stdout/stderr in the SAME type ``subprocess.run`` would have returned for this call
    (bytes unless the call is in text mode).

    The type must match the call: a bytes-mode caller ``.decode()``s the result and a
    text-mode caller ``.strip()``s it. A mismatch here (str on a bytes call) made a
    timed-out prune raise ``AttributeError: 'str' has no attribute 'decode'`` under the
    very host pressure this module exists to handle, and the best-effort wrapper then
    swallowed it -- reintroducing the leak R2-01 fixed while hiding that it happened.
    That is the VF-CL-R-001 masking recurring one layer down, so the type is pinned."""
    note = f'timed out after {timeout}s'

    def coerce(value, default):
        if value is None or value == b'' or value == '':
            value = default
        if text_mode:
            return value.decode('utf-8', 'replace') if isinstance(value, (bytes, bytearray)) else str(value)
        return bytes(value) if isinstance(value, (bytes, bytearray)) else str(value).encode('utf-8', 'replace')

    result = subprocess.CompletedProcess(
        argv, TIMEOUT_RETURNCODE,
        stdout=coerce(getattr(exc, 'stdout', None), ''),
        stderr=coerce(getattr(exc, 'stderr', None), note),
    )
    result.timed_out = True
    return result


def run(args, *, retries: int = 1, timeout: int = 60, **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run over a docker command, classifying the host conditions that are
    not docker errors and retrying only the one that is provably safe to retry.

    A docker error (the command ran and returned a docker exit code) is returned
    as-is -- retrying a real docker failure would just repeat it. A timeout is caught
    and returned as a classified result (never raised) whose stdout/stderr type matches
    the call (bytes unless text mode), so every caller's ``.decode()`` or ``.strip()``
    keeps working; a timeout is not retried (it already spent the full timeout). Only a
    *loader-stage* host process-creation failure is retried -- and only once by default
    -- because that process never ran (idempotent, so a mutating command cannot
    duplicate) and a transient blip can clear. A running-process crash or a POSIX
    signal is NOT retried: it ran, so a re-run could take a second, duplicating effect.
    """
    argv = [str(v) for v in args]
    text_mode = _text_mode(kwargs)

    def _once():
        try:
            return subprocess.run(argv, capture_output=True, timeout=timeout, **kwargs)
        except subprocess.TimeoutExpired as exc:
            return _timeout_result(argv, exc, timeout, text_mode=text_mode)

    result = _once()
    for attempt in range(retries):
        # Retry only a loader-stage process-creation failure (safe: the process never
        # ran). Success, a timeout (rc 124), a real docker error, a running-process
        # crash, and a signal all fall through here unretried.
        if result.returncode == 0 or not is_host_process_init_failure(result.returncode):
            return result
        time.sleep(0.4 * (attempt + 1))
        result = _once()
    return result
