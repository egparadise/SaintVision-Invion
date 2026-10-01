"""Hold a CI-derived S12 acceptance bundle to its shape, never to its verdict.

``tools/collect_s12_acceptance_evidence.py`` sorts the AC-12 items into PASS / FAIL /
NOT_OBSERVED / BLOCKED_EXTERNAL. Until the external waits clear, the honest verdict is
``FAIL`` or ``PASS_MEASURED_PARTIAL`` -- so a gate that demanded a good verdict would be
red forever and would be deleted, and a gate that demanded nothing would pass on a bundle
with items missing. This one asserts what must be true of any bundle whatever the answer:

* the schema is the one this checker understands;
* ``acceptanceClaim`` is ``false`` -- the bundle feeds a review and never closes AC-12;
* **every expected item is present with a recognised status.** This is the assertion that
  matters. A dropped item removes a FAIL from the scope lists, which reads as progress; the
  verdict improving because an item disappeared is the one failure mode a reader cannot see;
* no connection string reached the file.

It judges nothing about *which* status an item has. That is the measurement, and the point
of running the collector in CI is that CI derives it rather than a person typing it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA = "s12-db-acceptance-evidence:1"
STATUSES = frozenset({"PASS", "FAIL", "NOT_OBSERVED", "BLOCKED_EXTERNAL"})

#: The seventeen AC-12 items the collector sorts. Written out rather than counted so a
#: removal fails here instead of changing a number nobody reads. Measured at 8d5a7d9b.
EXPECTED_ITEMS = (
    "admission-gates-observed-open",
    "authenticated-browser-acceptance-on-physical-node",
    "contributed-folders-checked",
    "database-recovery-drill-passed-with-targets",
    "five-node-full-journey",
    "known-limitations-recorded",
    "offer-agreement",
    "operational-inputs-present",
    "operational-rpo-rto-measured",
    "pitr-configuration-possible",
    "pitr-rehearsal-dry-run-observed",
    "real-pitr-target-time-recovery",
    "release-manifest-recorded",
    "user-acceptance-record-ac12",
    "verified-backup-in-retention",
    "verified-off-site-backup",
    "web-smoke-journeys",
)

#: The two observations the VF-CL registry recorded as "produced by hand; CI never
#: re-derives them". They are in EXPECTED_ITEMS as well; naming them separately is what
#: makes this checker the evidence for that specific claim rather than a general shape test.
CI_DERIVED_CLAIM = ("pitr-configuration-possible", "pitr-rehearsal-dry-run-observed")

#: A libpq DSN or a bare password in a URL. The collector redacts before serialising and
#: re-checks its own text; this is the independent re-read of the file that shipped.
SECRET = re.compile(
    r"postgres(?:ql)?://[^\s\"\\]*:[^\s\"\\@]+@|password=[^\s\"\\&]+",
    re.IGNORECASE,
)


class ShapeRefused(SystemExit):
    """The bundle cannot be accepted as a bundle. Not a judgement on its verdict."""

    def __init__(self, message: str) -> None:
        super().__init__(f"REFUSED: {message}")


def check(document: dict, raw: str) -> dict:
    if document.get("schemaVersion") != SCHEMA:
        raise ShapeRefused(f"schemaVersion is {document.get('schemaVersion')!r}, expected {SCHEMA!r}")
    if document.get("acceptanceClaim") is not False:
        raise ShapeRefused(
            "acceptanceClaim must be exactly false; this bundle feeds a review and does not "
            f"close AC-12 (saw {document.get('acceptanceClaim')!r})"
        )
    items = document.get("items")
    if not isinstance(items, dict):
        raise ShapeRefused("items must be an object keyed by item id")
    missing = [name for name in EXPECTED_ITEMS if name not in items]
    if missing:
        raise ShapeRefused(
            "these AC-12 items are absent, which removes them from the scope lists and reads "
            f"as progress: {sorted(missing)}"
        )
    unknown = sorted(set(items) - set(EXPECTED_ITEMS))
    if unknown:
        raise ShapeRefused(
            f"these items are not in the expected set, so the checker cannot say the scope is "
            f"complete: {unknown}"
        )
    unrecognised = sorted(
        name for name, item in items.items()
        if not isinstance(item, dict) or item.get("status") not in STATUSES
    )
    if unrecognised:
        raise ShapeRefused(f"these items carry no recognised status: {unrecognised}")
    for name in CI_DERIVED_CLAIM:
        if items[name].get("source") in (None, ""):
            raise ShapeRefused(
                f"{name} names no source tool, so nothing says CI derived it rather than a "
                f"person typing the answer"
            )
    leak = SECRET.search(raw)
    if leak:
        raise ShapeRefused("a connection string or password reached the evidence file")
    counted = {name: item["status"] for name, item in items.items()}
    return {
        "schemaVersion": SCHEMA,
        "codeSha": document.get("codeSha"),
        "verdict": document.get("verdict"),
        "acceptanceClaim": document.get("acceptanceClaim"),
        "items": len(items),
        "byStatus": {
            status: sorted(name for name, value in counted.items() if value == status)
            for status in sorted(STATUSES)
        },
        "ciDerived": {name: counted[name] for name in CI_DERIVED_CLAIM},
        "status": "shape accepted; the verdict is the measurement and is not judged here",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("evidence", type=Path, help="the collector's JSON bundle")
    args = parser.parse_args(argv)
    raw = args.evidence.read_text(encoding="utf-8")
    print(json.dumps(check(json.loads(raw), raw), ensure_ascii=False, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
