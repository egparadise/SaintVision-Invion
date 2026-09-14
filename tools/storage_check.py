"""Read-only local sample of a declared contribution (Claude 71cf2c0 reviewed).

An operator-supplied --node is a claim, not proof of the machine executing this
process. This command never records StorageCheck or clears operational gates.
Use --dsn-env for a protected database credential and --root for the separately
authorized local folder. No root is inferred from database/job paths.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from saintvision.errors import InvError
from saintvision.services.verification import hash_file
from saintvision.storage.readroot import ReadRoot

DEFAULT_SAMPLE = 32


def _check_one(contribution, locations, sample, *, allowed_root):
    from saintvision.storage.sampling import check_sample

    result = check_sample(
        contribution, locations, sample, allowed_root=allowed_root, hash_reader=hash_file
    )
    # Preserve the public local CLI report; raw observations belong to the
    # separately signed internal protocol, not a Node identity claim here.
    result.pop("observations")
    return result


def run(args):
    from sqlalchemy import create_engine, select, func
    from sqlalchemy.orm import Session
    from saintvision.db.models import DataLocation, StorageContribution
    from saintvision.db.session import tenant_scope

    if type(args.sample) is not int or not 1 <= args.sample <= 1000:
        raise ValueError("invalid sample limit")
    tenant = uuid.UUID(args.tenant)
    url = args.dsn
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    if not url.startswith("postgresql+psycopg://"):
        raise ValueError("PostgreSQL required")
    engine = create_engine(url).execution_options(
        isolation_level="REPEATABLE READ",
        postgresql_readonly=True,
    )
    try:
        with Session(engine) as session, session.begin(), tenant_scope(session, tenant):
            contribution = session.scalars(
                select(StorageContribution).where(
                    StorageContribution.tenant_id == tenant,
                    StorageContribution.contribution_id == args.contribution,
                    StorageContribution.node_id == args.node,
                    StorageContribution.status == "active",
                )
            ).first()
            if contribution is None:
                raise ValueError("contribution unavailable in declared scope")
            root = ReadRoot(args.root)  # Explicit operator argument, never DB-derived.
            selector = (
                DataLocation.tenant_id == tenant,
                DataLocation.contribution_id == contribution.contribution_id,
            )
            catalogued = session.scalar(
                select(func.count()).select_from(DataLocation).where(*selector)
            )
            locations = session.scalars(
                select(DataLocation)
                .where(*selector)
                .order_by(DataLocation.location_id)
                .limit(args.sample)
            ).all()
            outcome = _check_one(contribution, locations, args.sample, allowed_root=root)
            return {
                "scope": "local-storage-sample-v1",
                "declaredNode": args.node,
                "contributionId": contribution.contribution_id,
                "nodeBindingVerified": False,
                "recorded": False,
                "operationalAcceptanceAssessed": False,
                "catalogued": catalogued,
                "examined": len(locations),
                "unsampled": catalogued - len(locations),
                **outcome,
            }
    finally:
        engine.dispose()


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse otherwise echoes unknown command-line tokens (possibly DSNs).
        self.exit(2, "Invalid storage check arguments; use --help.\n")


def main():
    parser = SafeParser(description=__doc__)
    parser.add_argument("--dsn-env", default="INV_STORAGE_CHECK_DSN")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--node", required=True, help="Declared node; not attested")
    parser.add_argument("--contribution", required=True)
    parser.add_argument("--root", required=True, help="Operator-authorized local root")
    parser.add_argument("--sample", type=int, default=DEFAULT_SAMPLE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.dsn_env):
        parser.error("invalid environment reference")
    args.dsn = os.environ.get(args.dsn_env)
    if not args.dsn:
        parser.error("missing database credential")
    try:
        report = run(args)
    except Exception:
        print("Storage sample unavailable; no operational record was written.", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report))
    else:
        print("Local sample only; Node identity unverified; no operational record written.")
        print(
            f"Sample match: {report['sampleHealthy']}; sampled {report['sampled']}; "
            f"mismatches {report['mismatches']}; unsampled {report['unsampled']}."
        )
    return 0 if report["sampleHealthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
