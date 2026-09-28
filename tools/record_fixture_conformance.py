"""Operator command: run the conformance suite against the fixture adapter and record it.

G-03 stage two (design #218 v1.2 §3-1, option B). This is the **only** producer
of ``adapter_conformance_records`` in this revision, and it is a command, not a
request handler: the read routes never run the suite.

What it measures is the product's in-process ``ReferenceAdapter`` -- not the
CLI installed on this host, which the platform has no credential for and must
not ``install``. Each record says so (``subject = fixture-adapter``,
``provenance = in-server``); a screen reading these rows must not call the
result "the installed CLI conforms".

Configuration: ``INV_DATABASE_URL`` (the application role) and
``INV_CONTROL_PLANE_HOST_ID`` (a canonical UUID; anything else refuses to
start, and the value is never printed). The clock is the process's UTC now.

The write is one transaction under ``bounded_lock_wait`` (G-04 card 84): a
lock wait past ``INV_BUSINESS_LOCK_TIMEOUT_MS`` or a broken deadlock ends the
command with exit code 3 and the helper's fixed sentence, nothing written; any
other database failure propagates as the defect it is.

    python tools/record_fixture_conformance.py            # every tool
    python tools/record_fixture_conformance.py --adapter codex-cli
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
for entry in (ROOT / "src", ROOT / "services" / "control-plane" / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))


def main(argv: list[str] | None = None) -> int:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from saintvision.adapters import agents
    from saintvision.api.lock_wait import bounded_lock_wait
    from saintvision.api.problem import CanonicalProblem
    from saintvision.config import Settings
    from saintvision.services.conformance_records import record_fixture_conformance

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--adapter",
        action="append",
        choices=[tool.name for tool in agents.TOOLS],
        help="record for this tool only (repeatable); default: every tool",
    )
    args = parser.parse_args(argv)

    try:
        settings = Settings.from_env()
    except ValueError as error:
        # The message names the setting and the rule, never the value.
        print(f"refusing to start: {error}", file=sys.stderr)
        return 2
    if settings.control_plane_host_id is None:
        print("refusing to start: INV_CONTROL_PLANE_HOST_ID is not set", file=sys.stderr)
        return 2

    adapters = args.adapter or [tool.name for tool in agents.TOOLS]
    engine = create_engine(settings.database_url, future=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    now = dt.datetime.now(dt.timezone.utc)
    lines: list[str] = []
    try:
        with factory() as session:
            with session.begin():
                with bounded_lock_wait(session, timeout_ms=settings.business_lock_timeout_ms):
                    for adapter in adapters:
                        row = record_fixture_conformance(
                            session,
                            adapter=adapter,
                            host_id=settings.control_plane_host_id,
                            now=now,
                        )
                        lines.append(
                            f"{row.record_id} {adapter} subject={row.subject} "
                            f"total={row.total} passed={row.passed} failed={row.failed} "
                            f"skipped={row.skipped}"
                        )
    except CanonicalProblem as problem:
        # A lock wait past the budget or a broken deadlock: nothing was
        # committed, and the sentence carries nothing from the database.
        print(f"not recorded: {problem.detail}", file=sys.stderr)
        return 3
    finally:
        engine.dispose()
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
