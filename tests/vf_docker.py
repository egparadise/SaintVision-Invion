"""Result-based docker cleanup shared by container tests (VF-CL-R5-01).

Kept out of the heavy integration test module so its one security-critical property
-- that cleanup never raises a pytest outcome that could replace a test's real
failure -- can be regression-tested on its own, without a live database or docker.
"""
from __future__ import annotations

import sys
from pathlib import Path
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import docker_diag  # noqa: E402


_ABSENT = re.compile(r"\bNo such (?:object|volume|network):", re.IGNORECASE)


def _confirmed_absent(result):
    """Docker inspect's narrow, idempotent absence result (not a daemon error)."""
    return result.returncode == 1 and bool(
        _ABSENT.search(docker_diag.masked_stderr(getattr(result, "stderr", "")))
    )


def cleanup_owned(name, resources):
    """Best-effort, RESULT-BASED cleanup of this run's own resources.

    It must NOT reuse the verification ``docker()`` helper: that helper raises
    ``pytest.skip`` on an infrastructure failure, and ``Skipped`` is a
    ``BaseException`` (not ``Exception``), so it would escape the caller's ``finally``
    and *replace the test's real failure with an unverified outcome* -- the exact
    inverse of the VF-CL-R-001 masking -- while also skipping the remaining removals.
    So cleanup inspects returncodes directly and never raises a pytest outcome.
    Ownership is still checked (never remove another run's resource). Every resource is
    attempted; one that cannot be confirmed removed is recorded and returned. Only
    ``Exception`` (e.g. OSError) is swallowed per resource -- never ``BaseException``,
    so KeyboardInterrupt/SystemExit still propagate.

    ``resources`` is a sequence of ``(label, inspect_args, remove_args)``. Returns a
    list of ``(label, reason)`` for resources left un-removed.
    """
    incomplete = []
    for label, inspect_args, remove_args in resources:
        try:
            inspected = docker_diag.run(["docker", *inspect_args], timeout=90, text=True)
            if inspected.returncode != 0:
                if _confirmed_absent(inspected):
                    continue  # already gone: the cleanup postcondition holds
                incomplete.append((label, "ownership uncheckable, preserved: " + docker_diag.describe(inspected)))
                continue
            if inspected.stdout.strip() != name:
                continue  # not this run's resource -- leave it
            removed = docker_diag.run(["docker", *remove_args], timeout=90, text=True)
            if removed.returncode != 0:
                incomplete.append((label, docker_diag.describe(removed)))
                continue
            # A successful rm command is not proof of removal (the daemon may
            # have returned before the object disappeared). Confirm absence
            # through the same ownership-scoped inspect command.
            confirmed = docker_diag.run(["docker", *inspect_args], timeout=90, text=True)
            if confirmed.returncode == 0:
                incomplete.append((label, "removal not confirmed; resource preserved"))
            elif confirmed.returncode != 1:
                incomplete.append((label, "removal query failed: " + docker_diag.describe(confirmed)))
        except Exception as exc:  # OSError etc.; never BaseException (skip/interrupt propagate)
            incomplete.append((label, "cleanup error: " + docker_diag.masked_stderr(str(exc))))
    return incomplete
