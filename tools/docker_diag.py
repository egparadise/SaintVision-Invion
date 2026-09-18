"""Tell a docker/daemon error apart from a host process-creation failure.

VF-CL-R-001 root cause: intermittent docker-command failures on this Windows host
were STATUS_DLL_INIT_FAILED (exit 0xC0000142) -- the OS could not start docker.exe
under handle/RAM pressure -- not a docker daemon fault. The daemon was healthy
throughout (docker version fine; 10/10 re-runs of the failing inspect succeeded).

A Windows NTSTATUS error-severity exit code is not docker semantics, so reporting
it as its own category makes a failure falsifiable (host vs daemon vs product), and
a short retry is safe because a process that failed to initialise never ran.
"""

from __future__ import annotations

import re
import subprocess
import time

_CREDENTIAL = re.compile(r'(://[^:@/\s]+:)[^@/\s]+(@)')


def is_host_process_init_failure(returncode) -> bool:
    """True for a Windows NTSTATUS error-severity exit (top two status bits set),
    e.g. 0xC0000142 STATUS_DLL_INIT_FAILED. The process could not start or
    initialise: host resource/handle pressure, not a docker or daemon error.
    Normal docker exit codes (0-255) are far below this range."""
    return (int(returncode) & 0xFFFFFFFF) >= 0xC0000000


def masked_stderr(stderr) -> str:
    """Bounded docker stderr with credential values (user:password@ in a DSN) masked."""
    text = stderr.decode('utf-8', 'replace') if isinstance(stderr, (bytes, bytearray)) else str(stderr or '')
    return _CREDENTIAL.sub(r'\1***\2', text).strip()[:400] or '(no stderr)'


def describe_failure(returncode, stderr=b'') -> str:
    """One falsifiable line: a host-init failure names its NTSTATUS; a docker error
    keeps its (credential-masked) stderr. Neither is guessed at."""
    rc = int(returncode) & 0xFFFFFFFF
    if is_host_process_init_failure(returncode):
        return (f'host process-creation failed (NTSTATUS 0x{rc:08X}); the OS could not start '
                f'the process -- host resource/handle pressure, not a docker/daemon error')
    return f'docker exit {returncode}: {masked_stderr(stderr)}'


def run(args, *, retries: int = 2, timeout: int = 60, **kwargs) -> subprocess.CompletedProcess:
    """subprocess.run over a docker command, retrying ONLY a host-init failure.

    A docker error (the command ran and returned a docker exit code) is returned
    as-is on the first attempt -- retrying a real docker failure would just repeat
    it. Only a Windows host process-creation failure is retried, because that
    process never ran (idempotent) and the failure is intermittent.
    """
    argv = [str(v) for v in args]
    result = subprocess.run(argv, capture_output=True, timeout=timeout, **kwargs)
    for attempt in range(retries):
        if result.returncode == 0 or not is_host_process_init_failure(result.returncode):
            return result
        time.sleep(0.4 * (attempt + 1))
        result = subprocess.run(argv, capture_output=True, timeout=timeout, **kwargs)
    return result
