"""Hosted-only S11-ST MinIO/PostgreSQL fault-matrix evidence runner."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
import pytest

from tools import run_s11_storage_failure_hosted as runner


_OPT_IN_REASON = "run only through S11 Storage Failure Hosted Reference opt-in lane"
pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif("INV_S11_STORAGE_REPORT" not in os.environ, reason=_OPT_IN_REASON),
]


def test_hosted_storage_failure_reference_matrix(env):
    if "INV_S11_STORAGE_REPORT" not in os.environ:
        pytest.skip(_OPT_IN_REASON)
    report_path = Path(os.environ["INV_S11_STORAGE_REPORT"])
    junit_path = Path(os.environ["INV_S11_STORAGE_JUNIT"])
    source_run_id = os.environ["INV_S11_SOURCE_RUN_ID"]
    archive_image = os.environ["INV_TEST_ARCHIVER_IMAGE"]
    minio_digest = os.environ["INV_S11_MINIO_IMAGE_DIGEST"]
    archive_digest = os.environ["INV_S11_ARCHIVE_IMAGE_DIGEST"]

    source = runner.git_value("rev-parse", "HEAD")
    expected_source = os.environ.get("INV_EVIDENCE_CODE_SHA", source)
    assert source == expected_source, "hosted lane did not checkout the exact requested head"
    tree = runner.git_value("rev-parse", "HEAD^{tree}")
    assert not runner.git_value("status", "--porcelain"), "hosted evidence checkout is dirty"
    with psycopg.connect(env.owner) as connection:
        postgres_version = connection.execute("SHOW server_version").fetchone()[0]
        # Exercise the real composite-key upsert twice.  A SQL-text-only test
        # does not prove that the hosted migrated schema accepts the statement.
        runner._set_budget(connection, env.tenant, env.project, 4096)
        runner._set_budget(connection, env.tenant, env.project, 8192)
        budget = connection.execute(
            "SELECT quota_bytes FROM inv.storage_budgets "
            "WHERE tenant_id=%s AND project_id=%s",
            (env.tenant, env.project),
        ).fetchall()
        assert budget == [(8192,)]

    started = runner.utc_now()
    report = runner.build_report(
        lambda identity: runner.execute_case(
            identity,
            env,
            archive_image=archive_image,
            owner=source_run_id,
        ),
        source_run_id=source_run_id,
        source_head_sha=source,
        checkout_tree_sha=tree,
        clean_checkout=True,
        producer_blob=runner.git_value("rev-parse", f"HEAD:{runner.PRODUCER_PATH}"),
        recovery_probe_blob=runner.git_value("rev-parse", f"HEAD:{runner.RECOVERY_PROBE_PATH}"),
        harness_blob=runner.git_value("rev-parse", f"HEAD:{runner.HARNESS_PATH}"),
        started_at=started,
        environment=runner.hosted_environment(
            postgres_version=postgres_version,
            minio_digest=minio_digest,
            archive_digest=archive_digest,
        ),
    )
    runner.write_outputs(report, report_path, junit_path)

    assert tuple(case["caseIdentity"] for case in report["cases"]) == runner.HOSTED_CASES
    assert report["caseCount"] == 10
    assert report["cleanup"] == {"performed": True, "residueCount": 0}
