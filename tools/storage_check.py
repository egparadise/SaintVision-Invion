"""Re-hash what a contributed folder actually holds, and file the result.

``StorageCheck`` has existed since S12 and ``record_storage_check`` has never
been called, so ``contributions_needing_attention`` reports every active folder
as "never checked" — correctly, because none ever was. This is the collector.

**Presence is not health.** A check that counted files would pass over a folder
whose bytes had rotted, so this re-hashes catalogued locations and compares
against the checksum recorded when they were catalogued. Any mismatch makes the
folder unhealthy however many files were intact; a corrupted byte is not
outvoted by its neighbours.

**A folder is identified by its node, not by its path.** A contributed folder
lives on a particular machine, and this tool can only reach what is reachable
from wherever it is run. ``D:/inv-share`` on the control plane is not
``D:/inv-share`` on pc-225, and filing a health record about the first under the
identity of the second would be worse than filing none — it would be an
operator's evidence that a folder is fine when nobody has looked at it. So the
node is required, contributions belonging to any other node are refused, and
running this for a remote node means running it *on* that node.

**A sample is not the folder.** Checking every file in a large contribution is
not something to do on a schedule, so a bounded sample is taken and its size is
recorded and printed. Nothing here licenses a claim about the files not sampled.

Usage:
    python tools/storage_check.py --dsn DSN --tenant UUID --node nod_...
        [--sample 32] [--json]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import uuid as _uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

#: How many catalogued locations to re-hash per contribution by default. Large
#: enough to catch rot that has spread, small enough to run often; the number is
#: reported so nobody mistakes it for the whole folder.
DEFAULT_SAMPLE = 32

#: Read in chunks so a large file does not have to fit in memory.
CHUNK = 1024 * 1024


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _check_one(contribution, locations, sample: int) -> dict[str, Any]:
    """Re-hash up to ``sample`` catalogued files under one contribution root."""
    from saintvision.storage.pathsafe import UnsafePath, resolve_within

    root = Path(contribution.normalized_path)
    if not root.is_dir():
        return {
            "reachable": False,
            "sampled": 0,
            "mismatches": 0,
            "freeBytes": None,
            "detail": {
                "reason": "the contribution root is not a directory on this machine",
                "root": str(root),
            },
        }

    try:
        free_bytes = shutil.disk_usage(root).free
    except OSError:
        free_bytes = None

    os_type = "windows" if os.name == "nt" else "linux"
    sampled = 0
    mismatches: list[dict[str, str]] = []
    unverifiable: list[dict[str, str]] = []

    for location in locations[:sample]:
        if not location.checksum_sha256:
            # Never counted as intact. A location catalogued without a checksum
            # has nothing to compare against, and folding it into the healthy
            # count would turn "not checkable" into "checked and fine".
            unverifiable.append(
                {"locationId": location.location_id, "reason": "no recorded checksum"}
            )
            continue
        try:
            resolved = resolve_within(root, location.relative_path, os_type=os_type)
        except (UnsafePath, ValueError) as error:
            # A catalogued path that escapes its root is a finding in its own
            # right, not a file to go and read.
            mismatches.append(
                {
                    "locationId": location.location_id,
                    "reason": f"unsafe relative path: {type(error).__name__}",
                }
            )
            sampled += 1
            continue
        if not resolved.is_file():
            mismatches.append(
                {"locationId": location.location_id, "reason": "catalogued file is absent"}
            )
            sampled += 1
            continue
        sampled += 1
        if _digest(resolved) != location.checksum_sha256:
            mismatches.append(
                {"locationId": location.location_id, "reason": "checksum differs"}
            )

    return {
        "reachable": True,
        "sampled": sampled,
        "mismatches": len(mismatches),
        "freeBytes": free_bytes,
        "detail": {
            "root": str(root),
            "catalogued": len(locations),
            "sampleLimit": sample,
            # Named individually: "three files differ" is not actionable,
            # "these three" is.
            "mismatchDetail": mismatches,
            "unverifiable": unverifiable,
        },
    }


def run(args) -> dict[str, Any]:
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker

    from saintvision.db.models import DataLocation, StorageContribution
    from saintvision.db.session import tenant_scope
    from saintvision.services import pilot as pilot_service

    url = args.dsn
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    engine = create_engine(url, future=True)
    factory = sessionmaker(engine, future=True, expire_on_commit=False)
    tenant = _uuid.UUID(args.tenant)
    now = dt.datetime.now(dt.timezone.utc)
    results: list[dict[str, Any]] = []
    refused: list[dict[str, str]] = []

    try:
        with factory() as session:
            with session.begin():
                with tenant_scope(session, tenant):
                    contributions = list(
                        session.scalars(
                            select(StorageContribution).where(
                                StorageContribution.tenant_id == tenant,
                                StorageContribution.status == "active",
                            )
                        ).all()
                    )
                    for contribution in contributions:
                        if contribution.node_id != args.node:
                            # The safeguard this tool exists around. Checking a
                            # same-named local path and filing it under another
                            # node's folder would manufacture evidence.
                            refused.append(
                                {
                                    "contributionId": contribution.contribution_id,
                                    "nodeId": contribution.node_id,
                                    "reason": (
                                        "belongs to another node; run this tool on "
                                        "that machine"
                                    ),
                                }
                            )
                            continue
                        locations = list(
                            session.scalars(
                                select(DataLocation)
                                .where(
                                    DataLocation.tenant_id == tenant,
                                    DataLocation.contribution_id
                                    == contribution.contribution_id,
                                )
                                .order_by(DataLocation.location_id)
                            ).all()
                        )
                        outcome = _check_one(contribution, locations, args.sample)
                        row = pilot_service.record_storage_check(
                            session,
                            tenant_id=tenant,
                            contribution_id=contribution.contribution_id,
                            now=now,
                            reachable=outcome["reachable"],
                            sampled_count=outcome["sampled"],
                            mismatch_count=outcome["mismatches"],
                            free_bytes=outcome["freeBytes"],
                            detail=outcome["detail"],
                        )
                        results.append(
                            {
                                "contributionId": contribution.contribution_id,
                                "checkId": row.check_id,
                                "declaredPath": contribution.declared_path,
                                "healthy": row.healthy,
                                **outcome,
                            }
                        )
    finally:
        engine.dispose()

    return {"node": args.node, "checked": results, "refused": refused}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True, help="schema owner DSN")
    parser.add_argument("--tenant", required=True)
    parser.add_argument(
        "--node",
        required=True,
        help=(
            "the node this machine is. Contributions belonging to any other "
            "node are refused rather than checked against a local path that "
            "happens to share the name"
        ),
    )
    parser.add_argument("--sample", type=int, default=DEFAULT_SAMPLE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.sample < 1:
        parser.error("--sample must be at least 1")

    report = run(args)
    unhealthy = [c for c in report["checked"] if not c["healthy"]]

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 1 if unhealthy or not report["checked"] else 0

    print(f"node {report['node']}\n")
    if not report["checked"]:
        print("  no active contributed folder belongs to this node")
    for entry in report["checked"]:
        mark = "healthy  " if entry["healthy"] else "UNHEALTHY"
        print(f"  {mark} {entry['declaredPath']}  ({entry['checkId']})")
        if not entry["reachable"]:
            print(f"            {entry['detail']['reason']}: {entry['detail']['root']}")
            continue
        print(
            f"            re-hashed {entry['sampled']} of "
            f"{entry['detail']['catalogued']} catalogued file(s); "
            f"{entry['mismatches']} differ"
        )
        for bad in entry["detail"]["mismatchDetail"]:
            print(f"            {bad['locationId']}: {bad['reason']}")
        for skipped in entry["detail"]["unverifiable"]:
            print(f"            {skipped['locationId']}: {skipped['reason']}")
        if entry["sampled"] < entry["detail"]["catalogued"]:
            print(
                "            a sample was checked; the files not sampled have "
                "not been shown to be intact"
            )
    for entry in report["refused"]:
        print(f"  skipped   {entry['contributionId']} — {entry['reason']}")

    return 1 if unhealthy or not report["checked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
