"""Real PostgreSQL evidence for the S04-DB C1-K collector."""

from __future__ import annotations

import json

import psycopg
from psycopg import sql
import pytest
from inv.dispatch import DeliveryQueue

from tools import collect_s04_kernel_approval_evidence as collector
from test_approvals import approval
from test_dispatch_queue import queued
from test_tool_admission import gateway


pytestmark = pytest.mark.postgres


@pytest.fixture(autouse=True)
def clean_kernel_evidence_tables(postgres):
    """Give this database-wide collector an explicit empty kernel boundary."""
    with psycopg.connect(postgres.owner) as conn:
        names = [
            row[0]
            for row in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='inv' ORDER BY tablename"
            ).fetchall()
        ]
        required = {
            "approval_dispatches",
            "approval_requests",
            "execution_attempts",
            "execution_deliveries",
            "outbox",
            "run_attempts",
            "tool_claims",
        }
        assert required <= set(names)
        conn.execute(
            sql.SQL("TRUNCATE {} CASCADE").format(
                sql.SQL(", ").join(sql.Identifier("inv", name) for name in names)
            )
        )


def test_real_product_approval_claim_delivery_and_attempt_chain_is_observed(gateway):
    a = gateway
    queued(a)
    attempt = DeliveryQueue(a.e.db).acquire(a.e.tenant, command_id=a.command["commandId"])
    assert attempt is not None and attempt.operation == "execute"

    measured = collector.collect_database(a.e.owner)
    evidence = collector.build_evidence(
        database=measured,
        provenance={
            "commit_sha": "1" * 40,
            "branch": "hosted-core",
            "working_tree_clean_status": True,
            "content_clean_diff": True,
            "executor": "pytest-real-pg",
        },
        source_env="INV_TEST_ADMIN_DSN",
    )

    assert [evidence["observations"][key]["status"] for key in ("K1", "K2", "K3")] == [
        "MEASURED_PASS",
        "MEASURED_PASS",
        "MEASURED_PASS",
    ]
    assert evidence["observations"]["K1"]["metrics"]["claimCount"] == 1
    assert evidence["observations"]["K2"]["metrics"]["deliveryCount"] == 1
    assert evidence["observations"]["K3"]["metrics"]["executionAttemptCount"] == 1
    assert evidence["observations"]["K4"]["status"] == "NOT_REGISTERED"
    assert evidence["verdict"] == "NOT_OBSERVED"
    assert evidence["acceptanceClaim"] is False

    rendered = json.dumps(evidence, ensure_ascii=False)
    for identifier in (
        a.e.tenant,
        a.e.project,
        a.e.node,
        a.run["runId"],
        a.row["approvalId"],
        a.command["commandId"],
    ):
        assert identifier not in rendered
