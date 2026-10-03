#!/usr/bin/env python3
"""
tools/test_c266_mutations.py:
Verification runner for the card 266 guards -- the three-phase collect surface,
the authority order around replay, the project boundary, and the project binding
in replica_repair.

Why this is in the tree (Codex r1 F5): a "10/10 killed" line in a PR body that a
reader cannot re-run is a claim, not evidence. This runner and the JSON it writes
are the evidence, and either can be re-run at any head.

Rules, the same ones this lane has used since card 202:
- one mutant at a time, applied by exact anchor; an anchor that does not match
  exactly once is NOT APPLIED rather than silently skipped;
- only pytest exit code 1 counts as KILLED. Exit 0 is a survivor and anything
  else is an error to look at, never a pass;
- the file is restored from the original text after every mutant and the restore
  is verified, so a crash cannot leave a mutant behind;
- PostgreSQL is required: these guards are about rows, grants and locks.

Usage:
    INV_TEST_ADMIN_DSN=<admin dsn> python tools/test_c266_mutations.py [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS = ROOT / "docs/vault/30_Development/Evidence/c266-mutation-results.json"

COLLECT = ROOT / "services/control-plane/src/inv/storage_check_collect.py"
COMMIT = ROOT / "services/control-plane/src/inv/storage_commit.py"
KERNEL_APP = ROOT / "services/control-plane/src/inv/app.py"
REPAIR = ROOT / "src/saintvision/services/replica_repair.py"

SERVICE_TESTS = ["tests/integration/test_storage_check_collect.py"]
HTTP_TESTS = ["tests/integration/test_storage_check_collect_http.py"]
STARTUP_TESTS = ["tests/integration/test_storage_check_collect_startup.py"]
REPAIR_TESTS = [
    "tests/test_replica_repair.py",
    "tests/integration/test_replica_repair_plan_route_real_pg.py",
]

MUTANTS = [
    {
        "id": "M1",
        "what": "phase one replays before authority is re-read",
        "file": COLLECT,
        "from": """            self._authority(conn, principal, project, contribution)
            # Locks first, boundary second, decision third""",
        "to": """            # Locks first, boundary second, decision third""",
        "tests": SERVICE_TESTS,
    },
    {
        "id": "M2",
        "what": "phase three replays before authority is re-read",
        "file": COLLECT,
        "from": """            self._authority(conn, principal, project, contribution)
            # The idempotency row is locked""",
        "to": """            # The idempotency row is locked""",
        "tests": SERVICE_TESTS,
        # Declared equivalent, with the reason measured rather than assumed: in
        # phase three the call this removes is followed by ``_locked_boundary``,
        # whose ``_scope`` re-checks the same grant and the same folder ownership
        # -- ``storage_commit.py:48-49`` calls ``_grant`` and
        # ``permission(..., linked=True)`` -- and does so **under the lock**, which
        # is strictly later than the removed call. So no behaviour changes and no
        # test can tell the two apart. Left in the set rather than deleted, because
        # the next person to move that line deserves to see this note.
        "equivalent": (
            "_locked_boundary -> _scope re-checks grant and ownership under the lock "
            "(storage_commit.py:48-49), so removing the earlier call changes nothing"
        ),
    },
    {
        "id": "M3",
        "what": "the ledger response is not stored with the writes",
        "file": COLLECT,
        "from": "            self.auth._save(conn, project, OPERATION, key, response)\n",
        "to": "",
        "tests": SERVICE_TESTS,
    },
    {
        "id": "M4",
        "what": "phase three ignores a response a concurrent request already stored",
        "file": COLLECT,
        "from": """            if prior is not None:
                # A concurrent request already won. Its answer is the answer; the
                # envelope this call just received is dropped rather than recorded.
                return prior, True""",
        "to": """            if False:
                return prior, True""",
        "tests": SERVICE_TESTS,
    },
    {
        "id": "M5",
        "what": "the request id is minted instead of derived",
        "file": COLLECT,
        "from": "    return str(uuid.uuid5(REQUEST_NAMESPACE, name))",
        "to": "    return str(uuid.uuid4())",
        "tests": SERVICE_TESTS,
    },
    {
        "id": "M6",
        "what": "the derivation drops its separator",
        "file": COLLECT,
        "from": '    name = SEPARATOR.join(\n        (str(tenant_id).lower(), str(project_id), str(run_id), OPERATION, key)\n    )',
        "to": '    name = "".join(\n        (str(tenant_id).lower(), str(project_id), str(run_id), OPERATION, key)\n    )',
        "tests": SERVICE_TESTS,
    },
    {
        "id": "M7",
        "what": "the contribution's current owner is not compared",
        "file": COLLECT,
        "from": '            or row["registered_by_user_id"] != granted["userId"]',
        "to": "            or False",
        "tests": SERVICE_TESTS,
    },
    {
        "id": "M8",
        "what": "the project boundary is not checked at all",
        "file": COLLECT,
        "from": "        self._project_boundary(principal, project, contribution)\n",
        "to": "",
        "tests": SERVICE_TESTS,
    },
    {
        "id": "M9",
        "what": "the boundary tolerates a folder straddling two projects",
        "file": COLLECT,
        "from": 'return row["inside"] > 0 and row["outside"] == 0',
        "to": 'return row["inside"] > 0',
        "tests": SERVICE_TESTS,
    },
    {
        "id": "M10",
        "what": "the boundary stops counting a NULL project as outside",
        "file": COLLECT,
        "from": '"count(*) FILTER (WHERE project_id IS NULL OR project_id <> :project)"',
        "to": '"count(*) FILTER (WHERE project_id IS NOT NULL AND project_id <> :project)"',
        "tests": SERVICE_TESTS,
    },
    {
        "id": "M11",
        "what": "the business link is not required, so a kernel-only project 500s",
        "file": COLLECT,
        "from": '''        granted = business_permission(
            conn, project, principal.subject_id, "can_request", linked=True
        )''',
        "to": '''        granted = business_permission(
            conn, project, principal.subject_id, "can_request"
        )''',
        "tests": SERVICE_TESTS,
    },
    {
        "id": "M12",
        "what": "the pre-I/O phase issues on its own transaction again",
        "file": COLLECT,
        "from": """            challenge = self.samples.locked_issue(
                conn, principal, project, run_id, contribution,
                request_id=request_id, sample=sample,
            )""",
        "to": """            challenge = self.samples.issue(
                principal, project, run_id, contribution,
                request_id=request_id, sample=sample,
            )""",
        "tests": SERVICE_TESTS,
    },
    {
        "id": "M13",
        "what": "the verified identity is not pinned, so a denial is anonymous",
        "file": KERNEL_APP,
        "from": '        request.state.actor_type = "user"\n',
        "to": "",
        "tests": HTTP_TESTS,
    },
    {
        "id": "M14",
        "what": "the audited target loses the path's project",
        "file": KERNEL_APP,
        "from": '    @api.post("/v1/projects/{project_id}/runs/{run_id}/storage-samples", status_code=201)\n    async def collect_storage_sample(\n        request: Request, project_id: str, run_id: str, identity=Depends(authenticated)\n    ):',
        "to": '    @api.post("/v1/projects/{project}/runs/{run_id}/storage-samples", status_code=201)\n    async def collect_storage_sample(\n        request: Request, project: str, run_id: str, identity=Depends(authenticated)\n    ):\n        project_id = project',
        "tests": HTTP_TESTS,
    },
    {
        "id": "M15",
        "what": "a configured collector no longer requires the business surface",
        "file": COLLECT,
        "from": """    if catalogue_engine is None:""",
        "to": """    if False:""",
        "tests": HTTP_TESTS,
    },
    {
        "id": "M19",
        "what": "the boundary is asked before the Run and folder are locked",
        "file": COLLECT,
        "from": (
            "        self.samples._scope(conn, principal, project, run_id, contribution)\n"
            "        self._project_boundary(principal, project, contribution)"
        ),
        "to": (
            "        self._project_boundary(principal, project, contribution)\n"
            "        self.samples._scope(conn, principal, project, run_id, contribution)"
        ),
        "tests": SERVICE_TESTS,
    },
    {
        "id": "M20",
        "what": "the final phase decides replay before re-asking the boundary",
        "file": COLLECT,
        "from": (
            "            self._locked_boundary(conn, principal, project, run_id, contribution)\n"
            "            if prior is not None:\n"
            "                # A concurrent request already won."
        ),
        "to": (
            "            if prior is not None:\n"
            "                # A concurrent request already won."
        ),
        "tests": SERVICE_TESTS,
    },
    {
        "id": "M21",
        "what": "an audit write failure degrades to the unavailable 503",
        "file": KERNEL_APP,
        "from": '                    raise DomainError("SYS-0001", "Internal error", 500) from None',
        "to": '                    raise DomainError("SYS-0001", "Internal error", 503) from None',
        "tests": HTTP_TESTS,
    },
    {
        "id": "M22",
        "what": "storageSample leaves the strict allow-list again",
        "file": KERNEL_APP,
        "from": '                "storageSample",\n',
        "to": "",
        "tests": STARTUP_TESTS,
    },
    {
        "id": "M16",
        "what": "the repair list drops its project condition",
        "file": REPAIR,
        "from": """            .where(
                DataLocation.tenant_id == tenant_id,
                DataLocation.project_id == project_id,
            )
            .order_by(DataLocation.location_id)""",
        "to": """            .where(DataLocation.tenant_id == tenant_id)
            .order_by(DataLocation.location_id)""",
        "tests": REPAIR_TESTS,
    },
    {
        "id": "M17",
        "what": "a NULL legacy project is treated as this project",
        "file": REPAIR,
        "from": """        or location.project_id is None
        or location.project_id != project_id""",
        "to": """        or (location.project_id is not None and location.project_id != project_id)""",
        "tests": REPAIR_TESTS,
    },
    {
        "id": "M18",
        "what": "the fleet summary drops its project condition",
        "file": REPAIR,
        "from": """            select(DataLocation.location_id).where(
                DataLocation.tenant_id == tenant_id,
                DataLocation.project_id == project_id,
            )""",
        "to": """            select(DataLocation.location_id).where(DataLocation.tenant_id == tenant_id)""",
        "tests": REPAIR_TESTS,
    },
]


def run(tests: list[str]) -> subprocess.CompletedProcess:
    env = dict(os.environ, PYTHONUTF8="1")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:randomly", *tests],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="write the results file")
    arguments = parser.parse_args()
    if not os.environ.get("INV_TEST_ADMIN_DSN"):
        print("INV_TEST_ADMIN_DSN is required: these guards are about rows and grants")
        return 2

    baseline = run(SERVICE_TESTS + HTTP_TESTS + STARTUP_TESTS + REPAIR_TESTS)
    summary = (baseline.stdout.strip().splitlines() or [""])[-1]
    print(f"unmutated suite -> exit {baseline.returncode}: {summary}")
    if baseline.returncode != 0:
        print("the unmutated suite must pass before a mutant means anything")
        return 2

    results = []
    for mutant in MUTANTS:
        path = mutant["file"]
        original = path.read_text(encoding="utf-8")
        occurrences = original.count(mutant["from"])
        if occurrences != 1:
            verdict = f"NOT APPLIED (anchor matched {occurrences})"
            print(f"{verdict:<28} {mutant['id']} {mutant['what']}")
            results.append({**{k: v for k, v in mutant.items() if k not in ("file", "tests")},
                            "file": str(path.relative_to(ROOT)), "verdict": "NOT_APPLIED"})
            continue
        path.write_text(original.replace(mutant["from"], mutant["to"], 1),
                        encoding="utf-8", newline="")
        try:
            done = run(mutant["tests"])
        finally:
            path.write_text(original, encoding="utf-8", newline="")
            assert path.read_text(encoding="utf-8") == original, path
        if done.returncode == 1:
            verdict = "KILLED"
        elif mutant.get("equivalent") and done.returncode == 0:
            # An equivalent mutant is not a gap: the behaviour is unchanged, and the
            # reason is recorded beside it so the claim can be checked rather than
            # taken. It is never counted as a kill.
            verdict = "EQUIVALENT"
        else:
            verdict = "SURVIVED"
        shown = verdict if verdict != "SURVIVED" else f"SURVIVED (exit {done.returncode})"
        print(f"{shown:<28} {mutant['id']} {mutant['what']}")
        row = {
            "id": mutant["id"], "what": mutant["what"],
            "file": str(path.relative_to(ROOT)),
            "verdict": verdict,
            "exitCode": done.returncode,
        }
        if mutant.get("equivalent"):
            row["equivalentBecause"] = mutant["equivalent"]
        results.append(row)

    killed = sum(1 for row in results if row["verdict"] == "KILLED")
    equivalent = sum(1 for row in results if row["verdict"] == "EQUIVALENT")
    print(f"\n{killed}/{len(results)} killed, {equivalent} equivalent")
    if arguments.json:
        RESULTS.write_text(
            json.dumps(
                {
                    "card": 266,
                    "scope": "storage-check-collect-and-replica-repair-project-binding",
                    "note": (
                        "Only pytest exit code 1 counts as KILLED. The runner restores "
                        "each file and verifies the restore, so a survivor is a test gap "
                        "rather than a leftover mutant."
                    ),
                    "killed": killed,
                    "equivalent": equivalent,
                    "total": len(results),
                    "mutants": results,
                },
                ensure_ascii=False, indent=2,
            ) + "\n",
            encoding="utf-8", newline="",
        )
        print("wrote", RESULTS.relative_to(ROOT))
    return 0 if killed + equivalent == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
