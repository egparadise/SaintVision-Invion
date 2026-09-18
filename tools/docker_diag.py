"""Tell a docker/daemon error apart from a host process-creation failure or a timeout.

VF-CL-R-001 root cause: intermittent docker-command failures on this Windows host
were STATUS_DLL_INIT_FAILED (exit 0xC0000142) -- the OS could not start docker.exe
under handle/RAM pressure -- not a docker daemon fault. The daemon was healthy
throughout (docker version fine; 10/10 re-runs of the failing inspect succeeded).

A Windows NTSTATUS error-severity exit code is not docker semantics, so reporting
it as its own category makes a failure falsifiable (host vs daemon vs product). A
timeout is a third category: the docker CLI was started but did not return in time,
again a host-pressure symptom rather than a product assertion result. All three are
distinguished so an unverifiable run is recorded as *unverified*, never as a product
failure and never as a suppressed blank.

Retry note (image-lane finding, 2026-09-18): retrying a host-init failure only helps
a *transient* blip. Under *sustained* host pressure a retry cannot clear the
condition, and each extra attempt is one more process-creation that adds to the very
pressure it is fighting (an 8-case image lane went 3->2 passed as the suite's own
load grew). So the retry here is a single, minimal transient cushion, deliberately
not escalating and with no growing backoff; the honest recovery for sustained
pressure is classification -- the caller records the outcome as unverified (a pre-run
host check or a pytest.skip), not more retries. ``is_infrastructure_failure`` is the
predicate the callers use to make that unverified-vs-failed decision.
"""

from __future__ import annotations

import re
import subprocess
import time

_CREDENTIAL = re.compile(r'(://[^:@/\s]+:)[^@/\s]+(@)')

#: Synthetic returncode for a docker CLI call that did not return within its timeout.
#: 124 is the conventional timeout exit code and is not a docker exit code; the
#: CompletedProcess ``run`` returns also carries ``.timed_out = True`` so nothing has
#: to classify a timeout from the number alone.
TIMEOUT_RETURNCODE = 124


def is_host_process_init_failure(returncode) -> bool:
    """True for a Windows NTSTATUS error-severity exit (top two status bits set),
    e.g. 0xC0000142 STATUS_DLL_INIT_FAILED. The process could not start or
    initialise: host resource/handle pressure, not a docker or daemon error.
    Normal docker exit codes (0-255) are far below this range."""
    return (int(returncode) & 0xFFFFFFFF) >= 0xC0000000


def timed_out(result) -> bool:
    """True if ``run`` synthesised this result from a subprocess timeout."""
    return bool(getattr(result, 'timed_out', False))


def is_infrastructure_failure(result) -> bool:
    """True when a non-zero result is a *host condition* -- a process-creation failure
    or a timeout -- rather than a docker/daemon/product error.

    The caller uses this to record the outcome as *unverified* (a pytest.skip or a
    pre-run host-check abort) instead of a failure: the product assertion was never
    actually reached, so calling it a failure would be a false product defect, and
    letting the exception escape would be the same masked hole this module removes.
    A real docker error (the command ran and returned a docker exit code) is not an
    infrastructure failure and must still fail loudly."""
    return getattr(result, 'returncode', 0) != 0 and (
        timed_out(result) or is_host_process_init_failure(result.returncode))


def masked_stderr(stderr) -> str:
    """Bounded docker stderr with credential values (user:password@ in a DSN) masked."""
    text = stderr.decode('utf-8', 'replace') if isinstance(stderr, (bytes, bytearray)) else str(stderr or '')
    return _CREDENTIAL.sub(r'\1***\2', text).strip()[:400] or '(no stderr)'


def describe_failure(returncode, stderr=b'', is_timeout=False) -> str:
    """One falsifiable line naming the failure category. A timeout and a host-init
    failure are named as host conditions; a docker error keeps its (credential-masked)
    stderr. Nothing is guessed at."""
    rc = int(returncode) & 0xFFFFFFFF
    if is_timeout:
        return (f'docker operation timed out ({masked_stderr(stderr)}); the CLI was started '
                f'but did not return -- host resource pressure or a hung operation, not a '
                f'product assertion result')
    if is_host_process_init_failure(returncode):
        return (f'host process-creation failed (NTSTATUS 0x{rc:08X}); the OS could not start '
                f'the process -- host resource/handle pressure, not a docker/daemon error')
    return f'docker exit {returncode}: {masked_stderr(stderr)}'


def describe(result) -> str:
    """``describe_failure`` for a CompletedProcess, honouring a synthesised timeout."""
    return describe_failure(result.returncode, getattr(result, 'stderr', b''),
                            is_timeout=timed_out(result))


def _timeout_result(argv, exc, timeout) -> subprocess.CompletedProcess:
    """A classified CompletedProcess standing in for a ``TimeoutExpired`` so a timeout
    is surfaced as a category, never raised out as an unclassified hole."""
    note = f'timed out after {timeout}s'
    stderr = getattr(exc, 'stderr', None)
    if isinstance(stderr, (bytes, bytearray)):
        stderr = stderr.decode('utf-8', 'replace').strip() or note
    elif isinstance(stderr, str):
        stderr = stderr.strip() or note
    else:
        stderr = note
    result = subprocess.CompletedProcess(argv, TIMEOUT_RETURNCODE,
                                         stdout=getattr(exc, 'stdout', None) or '', stderr=stderr)
    result.timed_out = True
    return result


def run(args, *, retries: int = 1, timeout: int = 60, **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run over a docker command, classifying the two host conditions that
    are not docker errors: a host process-creation failure and a timeout.

    A docker error (the command ran and returned a docker exit code) is returned
    as-is -- retrying a real docker failure would just repeat it. A timeout is caught
    and returned as a classified result (never raised): an escaping ``TimeoutExpired``
    is exactly the kind of unclassified hole this module removes, and a timeout is not
    retried here -- it already spent the full timeout, and a re-run under the same
    pressure would only spend it again. Only a host process-creation failure is
    retried, once by default, because that process never ran (idempotent) and a
    transient blip can clear; retry is deliberately minimal, because under sustained
    pressure it cannot help and each attempt adds load, so the caller (not more
    retries) records a persistent failure as unverified.
    """
    argv = [str(v) for v in args]

    def _once():
        try:
            return subprocess.run(argv, capture_output=True, timeout=timeout, **kwargs)
        except subprocess.TimeoutExpired as exc:
            return _timeout_result(argv, exc, timeout)

    result = _once()
    for attempt in range(retries):
        # Return anything that is not a host-init failure: success, a real docker
        # error, and a timeout (returncode 124) all fall through here unretried.
        if result.returncode == 0 or not is_host_process_init_failure(result.returncode):
            return result
        time.sleep(0.4 * (attempt + 1))
        result = _once()
    return result
