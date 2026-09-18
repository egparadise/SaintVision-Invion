"""Whether a PostgreSQL is configured for point-in-time recovery -- honestly.

VF-CL-04 (operations). The backup *media* and retention are operator decisions;
this assesses whether the cluster can do PITR at all, which is a configuration
fact this tool can read and must not paper over.

The three verdicts are kept distinct, because collapsing them is exactly how "no
PITR" gets mistaken for "recovery is fine":

``possible``
    ``archive_mode`` is on and an ``archive_command`` is set and ``wal_level`` is
    at least ``replica``. WAL is being shipped somewhere a base backup can be
    replayed against.
``absent``
    One of those is missing. There is no point-in-time recovery, whatever a
    nightly ``pg_dump`` might suggest -- a dump restores to the dump's instant,
    not to an arbitrary point.
``inconclusive``
    A setting could not be read. Never reported as ``absent`` (which would read
    as a checked "no"): an unread setting is an open question, and the tool exits
    non-zero for it just as it does for ``absent``.

Usage:
    python tools/pitr_readiness.py --dsn postgresql://.../db
    python tools/pitr_readiness.py --dsn ... --require-pitr   # exit 1 unless possible
"""

from __future__ import annotations

import argparse
import json
import sys

#: The settings that decide it, and what each must be.
REQUIRED = ("archive_mode", "archive_command", "wal_level")
_WAL_ORDER = ("minimal", "replica", "logical")


def assess(settings: dict[str, str | None]) -> dict:
    """Pure verdict over a settings snapshot -- no database, so it is testable.

    ``settings`` maps each name in :data:`REQUIRED` to its value, or ``None`` if
    it could not be read.
    """
    missing_reads = [name for name in REQUIRED if settings.get(name) is None]
    if missing_reads:
        return {
            "verdict": "inconclusive",
            "reasons": [f"{name} could not be read" for name in missing_reads],
            "settings": settings,
        }

    reasons: list[str] = []
    archive_mode = (settings["archive_mode"] or "").lower()
    if archive_mode not in ("on", "always"):
        reasons.append(f"archive_mode is {archive_mode!r}, not on/always")

    command = (settings["archive_command"] or "").strip()
    # A disabled or empty command ships nothing. PostgreSQL reports the literal
    # string; an empty or clearly-disabled one is not archiving.
    if not command or command.lower() in ("(disabled)", "off"):
        reasons.append("archive_command is empty/disabled, so no WAL is shipped")

    wal_level = (settings["wal_level"] or "").lower()
    if wal_level not in _WAL_ORDER or _WAL_ORDER.index(wal_level) < _WAL_ORDER.index("replica"):
        reasons.append(f"wal_level is {wal_level!r}, below 'replica'")

    if reasons:
        return {"verdict": "absent", "reasons": reasons, "settings": settings}
    return {"verdict": "possible", "reasons": [], "settings": settings}


def read_settings(dsn: str) -> dict[str, str | None]:
    """Read the deciding settings from a live cluster, each independently.

    A read that errors yields ``None`` for that setting -- an inconclusive, not a
    false "off".
    """
    import psycopg

    out: dict[str, str | None] = {}
    with psycopg.connect(dsn, connect_timeout=10) as conn:
        for name in REQUIRED:
            try:
                row = conn.execute("SELECT current_setting(%s, true)", (name,)).fetchone()
                out[name] = row[0] if row else None
            except Exception:  # noqa: BLE001 - an unread setting is None, not a guess
                out[name] = None
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True, help="libpq DSN of the cluster to assess")
    parser.add_argument(
        "--require-pitr",
        action="store_true",
        help="exit non-zero unless the verdict is 'possible' (a deployment gate)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        settings = read_settings(args.dsn)
    except Exception as error:  # noqa: BLE001
        report = {
            "verdict": "inconclusive",
            "reasons": [f"could not connect: {type(error).__name__}"],
            "settings": {},
        }
    else:
        report = assess(settings)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"PITR: {report['verdict']}")
        for name, value in report["settings"].items():
            print(f"  {name} = {value!r}")
        for reason in report["reasons"]:
            print(f"  - {reason}")
        if report["verdict"] == "absent":
            print(
                "\nNo point-in-time recovery. A logical dump restores to the dump's "
                "instant, not to an arbitrary point; do not record this as PITR."
            )
        elif report["verdict"] == "inconclusive":
            print("\nNOT established. An unread setting is an open question, not a 'no'.")

    # 'possible' -> 0. 'absent'/'inconclusive' -> non-zero when a gate is requested;
    # without the gate the tool still reports and exits 0 for 'possible', 2 otherwise
    # so a caller can branch without --require-pitr.
    if report["verdict"] == "possible":
        return 0
    if args.require_pitr:
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
