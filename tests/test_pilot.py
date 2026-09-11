"""S12 pilot operations against a real PostgreSQL.

Every test here is about the same thing: a record must not claim more than
happened. A drill cannot pass without measurements, a database drill cannot
pass without the fencing check, a conditional acceptance cannot have an empty
limitation list, and a healthy folder cannot have a checksum mismatch.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from saintvision.db.models import TARGET_RPO_SECONDS, TARGET_RTO_SECONDS
from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.services import pilot as pilot_service

pytestmark = pytest.mark.postgres

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 9, 9, 7, 0, 0, tzinfo=UTC)


@pytest.fixture
def pilot(owner_engine, two_tenants):
    tenant_a, tenant_b = two_tenants
    ids = {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "user_id": new_id("user"),
        "project_id": new_id("project"),
        "node_id": new_id("node"),
        "contribution_id": new_id("storage_contribution"),
    }
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO users (user_id, tenant_id, external_subject, display_name, "
                "status, created_at, updated_at, version) "
                "VALUES (:u, :t, 'sub', 'Operator', 'active', now(), now(), 1)"
            ),
            {"u": ids["user_id"], "t": tenant_a},
        )
        c.execute(
            text(
                "INSERT INTO projects (project_id, tenant_id, code, display_name, status, "
                "created_at, version) VALUES (:p, :t, 'a', 'A', 'active', now(), 1)"
            ),
            {"p": ids["project_id"], "t": tenant_a},
        )
        c.execute(
            text(
                "INSERT INTO nodes (node_id, tenant_id, hostname, os_type, os_version, "
                "agent_version, status, enrolled_at, heartbeat_sequence, version) "
                "VALUES (:n, :t, 'lab-01', 'linux', '22.04', '0.1', 'active', now(), 0, 1)"
            ),
            {"n": ids["node_id"], "t": tenant_a},
        )
        c.execute(
            text(
                "INSERT INTO storage_contributions (contribution_id, tenant_id, node_id, "
                "declared_path, normalized_path, mode, status, registered_by_user_id, "
                "registered_at, version) VALUES (:c, :t, :n, '/srv/inv', '/srv/inv', "
                "'read_only', 'active', :u, now(), 1)"
            ),
            {"c": ids["contribution_id"], "t": tenant_a, "n": ids["node_id"], "u": ids["user_id"]},
        )
    return ids


def _components():
    return [
        pilot_service.ReleaseComponent("control-plane", "service", "a" * 64),
        pilot_service.ReleaseComponent("node-agent", "service", "b" * 64),
        pilot_service.ReleaseComponent("web", "frontend", "c" * 64),
    ]


def _measurement(rpo=600, rto=1800):
    return pilot_service.DrillMeasurement(rpo_seconds=rpo, rto_seconds=rto)


# --------------------------------------------------------------------------
# Recovery drills
# --------------------------------------------------------------------------


def test_a_passing_drill_needs_measurements(app_sessionmaker, pilot):
    """"It worked" is not evidence for a quantitative target."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                with pytest.raises(InvError, match="measured RPO and RTO"):
                    pilot_service.record_recovery_drill(
                        session, tenant_id=pilot["tenant_a"], scope="workspace",
                        outcome="passed", performed_by_user_id=pilot["user_id"], now=NOW,
                        integrity_verified=True,
                    )


def test_a_passing_drill_needs_checksum_verification(app_sessionmaker, pilot):
    """Data being present is not data being correct."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                with pytest.raises(InvError, match="integrity"):
                    pilot_service.record_recovery_drill(
                        session, tenant_id=pilot["tenant_a"], scope="workspace",
                        outcome="passed", performed_by_user_id=pilot["user_id"], now=NOW,
                        measurement=_measurement(),
                    )


def test_a_database_drill_cannot_pass_without_the_fencing_check(app_sessionmaker, pilot):
    """ERR-DESIGN-006, enforced rather than filed.

    A PITR restore rewinds the fencing sequence while the Node Agents holding
    tokens do not rewind with it. A restore that verified the data came back
    and stopped there has not shown the system is safe to run.
    """
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                with pytest.raises(InvError, match="ERR-DESIGN-006"):
                    pilot_service.record_recovery_drill(
                        session, tenant_id=pilot["tenant_a"], scope="database",
                        outcome="passed", performed_by_user_id=pilot["user_id"], now=NOW,
                        measurement=_measurement(), integrity_verified=True,
                    )


def test_a_database_drill_passes_once_fencing_is_verified(app_sessionmaker, pilot):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                drill = pilot_service.record_recovery_drill(
                    session, tenant_id=pilot["tenant_a"], scope="database",
                    outcome="passed", performed_by_user_id=pilot["user_id"], now=NOW,
                    measurement=_measurement(), integrity_verified=True,
                    fencing_verified=True,
                    fencing_note="setval advanced past the pre-restore maximum plus margin",
                )
    assert drill.outcome == "passed"
    assert drill.met_targets is True


def test_a_workspace_drill_does_not_need_the_fencing_check(app_sessionmaker, pilot):
    """The fencing problem is specific to restoring the sequence's own database."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                drill = pilot_service.record_recovery_drill(
                    session, tenant_id=pilot["tenant_a"], scope="workspace",
                    outcome="passed", performed_by_user_id=pilot["user_id"], now=NOW,
                    measurement=_measurement(), integrity_verified=True,
                )
    assert drill.outcome == "passed"


def test_a_drill_that_missed_the_target_still_records_the_pass(app_sessionmaker, pilot):
    """Both facts are kept: the restore worked, and it took too long.

    Rewriting the target to match the measurement is how a pilot reports a
    success it did not have.
    """
    slow = _measurement(rpo=TARGET_RPO_SECONDS + 60, rto=TARGET_RTO_SECONDS + 600)
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                drill = pilot_service.record_recovery_drill(
                    session, tenant_id=pilot["tenant_a"], scope="database",
                    outcome="passed", performed_by_user_id=pilot["user_id"], now=NOW,
                    measurement=slow, integrity_verified=True, fencing_verified=True,
                )
    assert drill.outcome == "passed"
    assert drill.met_targets is False
    assert drill.measured_rpo_seconds > drill.target_rpo_seconds


def test_the_database_refuses_met_targets_that_contradict_the_numbers(
    app_sessionmaker, pilot
):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                drill = pilot_service.record_recovery_drill(
                    session, tenant_id=pilot["tenant_a"], scope="database",
                    outcome="passed", performed_by_user_id=pilot["user_id"], now=NOW,
                    measurement=_measurement(rpo=TARGET_RPO_SECONDS + 1),
                    integrity_verified=True, fencing_verified=True,
                )
                drill_id = drill.drill_id
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, pilot["tenant_a"]):
                    session.execute(
                        text("UPDATE recovery_drills SET met_targets = true WHERE drill_id = :d"),
                        {"d": drill_id},
                    )


def test_the_database_refuses_a_database_pass_without_fencing(app_sessionmaker, pilot):
    """The constraint, checked by going around the service."""
    with app_sessionmaker() as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, pilot["tenant_a"]):
                    session.execute(
                        text(
                            "INSERT INTO recovery_drills (drill_id, tenant_id, scope, outcome, "
                            "measured_rpo_seconds, measured_rto_seconds, target_rpo_seconds, "
                            "target_rto_seconds, met_targets, fencing_verified, "
                            "integrity_verified, performed_by_user_id, performed_at, notes) "
                            "VALUES (:d, :t, 'database', 'passed', 60, 60, 900, 3600, false, "
                            "false, true, :u, now(), '{}')"
                        ),
                        {"d": new_id("drill"), "t": pilot["tenant_a"], "u": pilot["user_id"]},
                    )


def test_a_failed_drill_records_without_measurements(app_sessionmaker, pilot):
    """A failure is a result and must be recordable."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                drill = pilot_service.record_recovery_drill(
                    session, tenant_id=pilot["tenant_a"], scope="database",
                    outcome="failed", performed_by_user_id=pilot["user_id"], now=NOW,
                    notes={"reason": "WAL segment missing"},
                )
    assert drill.outcome == "failed"
    assert drill.met_targets is False


# --------------------------------------------------------------------------
# Backups
# --------------------------------------------------------------------------


def test_a_backup_is_not_verified_without_a_checksum(app_sessionmaker, pilot):
    with app_sessionmaker() as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, pilot["tenant_a"]):
                    session.execute(
                        text(
                            "INSERT INTO backup_records (backup_id, tenant_id, kind, "
                            "location_ref, off_site, byte_size, verified, started_at) "
                            "VALUES (:b, :t, 'base', 'vol://x', true, 1, true, now())"
                        ),
                        {"b": new_id("backup"), "t": pilot["tenant_a"]},
                    )


def test_verifying_a_backup_requires_a_real_digest(app_sessionmaker, pilot):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                backup = pilot_service.record_backup(
                    session, tenant_id=pilot["tenant_a"], kind="base",
                    location_ref="vol://offsite/2026-09-09", now=NOW, off_site=True,
                )
                with pytest.raises(InvError):
                    pilot_service.verify_backup(
                        session, tenant_id=pilot["tenant_a"],
                        backup_id=backup.backup_id, checksum_sha256="nope", now=NOW,
                    )
                verified = pilot_service.verify_backup(
                    session, tenant_id=pilot["tenant_a"],
                    backup_id=backup.backup_id, checksum_sha256="e" * 64, now=NOW,
                )
    assert verified.verified is True
    assert verified.off_site is True


def test_off_site_is_recorded_not_inferred(app_sessionmaker, pilot):
    """ADR-018 separates local durability from surviving the failure domain."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                local = pilot_service.record_backup(
                    session, tenant_id=pilot["tenant_a"], kind="base",
                    location_ref="/var/lib/postgresql/backups", now=NOW,
                )
    assert local.off_site is False


# --------------------------------------------------------------------------
# Storage checks
# --------------------------------------------------------------------------


def test_one_mismatch_makes_a_folder_unhealthy(app_sessionmaker, pilot):
    """A corrupted byte is not outvoted by intact ones."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                check = pilot_service.record_storage_check(
                    session, tenant_id=pilot["tenant_a"],
                    contribution_id=pilot["contribution_id"], now=NOW,
                    reachable=True, sampled_count=500, mismatch_count=1,
                )
    assert check.healthy is False


def test_an_unreachable_folder_is_unhealthy(app_sessionmaker, pilot):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                check = pilot_service.record_storage_check(
                    session, tenant_id=pilot["tenant_a"],
                    contribution_id=pilot["contribution_id"], now=NOW,
                    reachable=False, sampled_count=0, mismatch_count=0,
                )
    assert check.healthy is False


def test_the_database_refuses_healthy_with_a_mismatch(app_sessionmaker, pilot):
    with app_sessionmaker() as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, pilot["tenant_a"]):
                    session.execute(
                        text(
                            "INSERT INTO storage_checks (check_id, tenant_id, contribution_id, "
                            "reachable, sampled_count, mismatch_count, healthy, checked_at, detail) "
                            "VALUES (:c, :t, :n, true, 10, 3, true, now(), '{}')"
                        ),
                        {"c": new_id("storage_check"), "t": pilot["tenant_a"],
                         "n": pilot["contribution_id"]},
                    )


def test_a_never_checked_folder_needs_attention(app_sessionmaker, pilot):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                needing = pilot_service.contributions_needing_attention(
                    session, tenant_id=pilot["tenant_a"], now=NOW
                )
    assert [n["reason"] for n in needing] == ["never checked"]


def test_a_stale_check_needs_attention(app_sessionmaker, pilot):
    """Healthy a month ago and unlooked-at since means the same thing as failed:
    nobody currently knows."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                pilot_service.record_storage_check(
                    session, tenant_id=pilot["tenant_a"],
                    contribution_id=pilot["contribution_id"],
                    now=NOW - dt.timedelta(days=30), reachable=True,
                    sampled_count=10, mismatch_count=0,
                )
                needing = pilot_service.contributions_needing_attention(
                    session, tenant_id=pilot["tenant_a"], now=NOW
                )
    assert [n["reason"] for n in needing] == ["stale"]


def test_a_recent_healthy_check_needs_no_attention(app_sessionmaker, pilot):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                pilot_service.record_storage_check(
                    session, tenant_id=pilot["tenant_a"],
                    contribution_id=pilot["contribution_id"], now=NOW,
                    reachable=True, sampled_count=10, mismatch_count=0,
                )
                needing = pilot_service.contributions_needing_attention(
                    session, tenant_id=pilot["tenant_a"], now=NOW
                )
    assert needing == []


# --------------------------------------------------------------------------
# Release and acceptance
# --------------------------------------------------------------------------


def test_a_component_without_a_digest_is_refused(app_sessionmaker, pilot):
    """A manifest whose components carry no digest is unverifiable."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                with pytest.raises(InvError, match="digest"):
                    pilot_service.create_release_manifest(
                        session, tenant_id=pilot["tenant_a"], version="R4",
                        components=[pilot_service.ReleaseComponent("web", "frontend", "")],
                        created_by_user_id=pilot["user_id"], now=NOW,
                    )


def test_the_manifest_hash_is_order_independent(app_sessionmaker, pilot):
    """Two manifests with the same components are the same release."""
    forward = _components()
    backward = list(reversed(_components()))
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                first = pilot_service.create_release_manifest(
                    session, tenant_id=pilot["tenant_a"], version="R4",
                    components=forward, created_by_user_id=pilot["user_id"], now=NOW,
                )
                second = pilot_service.create_release_manifest(
                    session, tenant_id=pilot["tenant_a"], version="R4-rebuild",
                    components=backward, created_by_user_id=pilot["user_id"], now=NOW,
                )
    assert first.manifest_sha256 == second.manifest_sha256


def test_a_conditional_acceptance_must_say_what_it_is_conditional_on(
    app_sessionmaker, pilot
):
    """Otherwise it is a plain acceptance wearing a hedge."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                release = pilot_service.create_release_manifest(
                    session, tenant_id=pilot["tenant_a"], version="R4",
                    components=_components(), created_by_user_id=pilot["user_id"], now=NOW,
                )
                with pytest.raises(InvError, match="conditional"):
                    pilot_service.record_acceptance(
                        session, tenant_id=pilot["tenant_a"], release_id=release.release_id,
                        acceptance_criterion="AC-12", outcome="conditional",
                        accepted_by_user_id=pilot["user_id"], now=NOW,
                    )


def test_the_database_refuses_a_conditional_acceptance_with_no_limitations(
    app_sessionmaker, pilot
):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                release = pilot_service.create_release_manifest(
                    session, tenant_id=pilot["tenant_a"], version="R4",
                    components=_components(), created_by_user_id=pilot["user_id"], now=NOW,
                )
                release_id, digest = release.release_id, release.manifest_sha256
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, pilot["tenant_a"]):
                    session.execute(
                        text(
                            "INSERT INTO acceptance_records (acceptance_id, tenant_id, "
                            "release_id, acceptance_id_ref, outcome, accepted_manifest_sha256, "
                            "known_limitations, accepted_by_user_id, decided_at) "
                            "VALUES (:a, :t, :r, 'AC-12', 'conditional', :d, '[]', :u, now())"
                        ),
                        {"a": new_id("acceptance"), "t": pilot["tenant_a"], "r": release_id,
                         "d": digest, "u": pilot["user_id"]},
                    )


def test_acceptance_must_be_by_a_real_user(app_sessionmaker, pilot):
    """The system cannot sign its own acceptance."""
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                release = pilot_service.create_release_manifest(
                    session, tenant_id=pilot["tenant_a"], version="R4",
                    components=_components(), created_by_user_id=pilot["user_id"], now=NOW,
                )
                release_id, digest = release.release_id, release.manifest_sha256
        with pytest.raises(IntegrityError):
            with session.begin():
                with tenant_scope(session, pilot["tenant_a"]):
                    session.execute(
                        text(
                            "INSERT INTO acceptance_records (acceptance_id, tenant_id, "
                            "release_id, acceptance_id_ref, outcome, accepted_manifest_sha256, "
                            "known_limitations, accepted_by_user_id, decided_at) "
                            "VALUES (:a, :t, :r, 'AC-12', 'accepted', :d, '[]', :u, now())"
                        ),
                        {"a": new_id("acceptance"), "t": pilot["tenant_a"], "r": release_id,
                         "d": digest, "u": new_id("user")},
                    )


def test_acceptance_pins_the_manifest_it_saw(app_sessionmaker, pilot):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                release = pilot_service.create_release_manifest(
                    session, tenant_id=pilot["tenant_a"], version="R4",
                    components=_components(), created_by_user_id=pilot["user_id"], now=NOW,
                )
                record = pilot_service.record_acceptance(
                    session, tenant_id=pilot["tenant_a"], release_id=release.release_id,
                    acceptance_criterion="AC-12", outcome="conditional",
                    accepted_by_user_id=pilot["user_id"], now=NOW,
                    known_limitations=["single control plane, no HA"],
                )
    assert record.accepted_manifest_sha256 == release.manifest_sha256
    assert record.known_limitations == ["single control plane, no HA"]


# --------------------------------------------------------------------------
# Readiness reporting
# --------------------------------------------------------------------------


def test_readiness_lists_every_missing_piece(app_sessionmaker, pilot):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                release = pilot_service.create_release_manifest(
                    session, tenant_id=pilot["tenant_a"], version="R4",
                    components=_components(), created_by_user_id=pilot["user_id"], now=NOW,
                )
                report = pilot_service.pilot_readiness(
                    session, tenant_id=pilot["tenant_a"],
                    release_id=release.release_id, now=NOW,
                )
    assert not report["evidenceComplete"]
    blockers = " | ".join(report["blockers"])
    for expected in (
        "no acceptance record",
        "no passing database recovery drill",
        "no verified backup",
        "no verified off-site backup",
        "need attention",
    ):
        assert expected in blockers, expected


def test_readiness_is_complete_once_the_evidence_exists(app_sessionmaker, pilot):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                tenant = pilot["tenant_a"]
                backup = pilot_service.record_backup(
                    session, tenant_id=tenant, kind="base",
                    location_ref="vol://offsite", now=NOW, off_site=True,
                )
                pilot_service.verify_backup(
                    session, tenant_id=tenant, backup_id=backup.backup_id,
                    checksum_sha256="f" * 64, now=NOW,
                )
                pilot_service.record_recovery_drill(
                    session, tenant_id=tenant, scope="database", outcome="passed",
                    performed_by_user_id=pilot["user_id"], now=NOW,
                    measurement=_measurement(), integrity_verified=True,
                    fencing_verified=True, backup_id=backup.backup_id,
                )
                pilot_service.record_storage_check(
                    session, tenant_id=tenant, contribution_id=pilot["contribution_id"],
                    now=NOW, reachable=True, sampled_count=20, mismatch_count=0,
                )
                release = pilot_service.create_release_manifest(
                    session, tenant_id=tenant, version="R4", components=_components(),
                    created_by_user_id=pilot["user_id"], now=NOW,
                )
                pilot_service.record_acceptance(
                    session, tenant_id=tenant, release_id=release.release_id,
                    acceptance_criterion="AC-12", outcome="conditional",
                    accepted_by_user_id=pilot["user_id"], now=NOW,
                    known_limitations=["single control plane; 99.5% is measured, not HA"],
                )
                report = pilot_service.pilot_readiness(
                    session, tenant_id=tenant, release_id=release.release_id, now=NOW
                )
    assert report["evidenceComplete"], report["blockers"]
    # Complete evidence is not the same as no limitations, and the report keeps
    # the limitations visible rather than absorbing them into a green flag.
    assert report["knownLimitations"] == [
        "single control plane; 99.5% is measured, not HA"
    ]


def test_readiness_reports_a_drill_that_passed_but_missed_the_target(
    app_sessionmaker, pilot
):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                pilot_service.record_recovery_drill(
                    session, tenant_id=pilot["tenant_a"], scope="database", outcome="passed",
                    performed_by_user_id=pilot["user_id"], now=NOW,
                    measurement=_measurement(rto=TARGET_RTO_SECONDS + 1),
                    integrity_verified=True, fencing_verified=True,
                )
                release = pilot_service.create_release_manifest(
                    session, tenant_id=pilot["tenant_a"], version="R4",
                    components=_components(), created_by_user_id=pilot["user_id"], now=NOW,
                )
                report = pilot_service.pilot_readiness(
                    session, tenant_id=pilot["tenant_a"],
                    release_id=release.release_id, now=NOW,
                )
    assert len(report["drillsMissingTargets"]) == 1
    assert report["drillsMissingTargets"][0]["measuredRtoSeconds"] > TARGET_RTO_SECONDS


def test_a_rejected_acceptance_blocks_readiness(app_sessionmaker, pilot):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                release = pilot_service.create_release_manifest(
                    session, tenant_id=pilot["tenant_a"], version="R4",
                    components=_components(), created_by_user_id=pilot["user_id"], now=NOW,
                )
                pilot_service.record_acceptance(
                    session, tenant_id=pilot["tenant_a"], release_id=release.release_id,
                    acceptance_criterion="AC-12", outcome="rejected",
                    accepted_by_user_id=pilot["user_id"], now=NOW,
                )
                report = pilot_service.pilot_readiness(
                    session, tenant_id=pilot["tenant_a"],
                    release_id=release.release_id, now=NOW,
                )
    assert "a rejected acceptance stands against this release" in report["blockers"]


# --------------------------------------------------------------------------
# Permissions and isolation
# --------------------------------------------------------------------------


def test_a_permission_snapshot_is_hashed_order_independently(app_sessionmaker, pilot):
    grants = [{"table": "runs", "privilege": "SELECT"}, {"table": "nodes", "privilege": "INSERT"}]
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                first = pilot_service.take_permission_snapshot(
                    session, tenant_id=pilot["tenant_a"], subject_type="app_role",
                    subject_id="inv_app", grants=grants, now=NOW,
                )
                second = pilot_service.take_permission_snapshot(
                    session, tenant_id=pilot["tenant_a"], subject_type="app_role",
                    subject_id="inv_app", grants=list(reversed(grants)), now=NOW,
                )
    assert first.digest_sha256 == second.digest_sha256


def test_pilot_records_are_tenant_isolated(app_sessionmaker, pilot):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                pilot_service.record_backup(
                    session, tenant_id=pilot["tenant_a"], kind="base",
                    location_ref="vol://x", now=NOW,
                )
                pilot_service.create_release_manifest(
                    session, tenant_id=pilot["tenant_a"], version="R4",
                    components=_components(), created_by_user_id=pilot["user_id"], now=NOW,
                )
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_b"]):
                for table in ("backup_records", "release_manifests", "recovery_drills"):
                    assert (
                        session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
                    ), table


@pytest.mark.parametrize("outcome", ["failed", "aborted"])
def test_failed_or_aborted_drill_keeps_measurements_without_claiming_targets(app_sessionmaker, pilot, outcome):
    with app_sessionmaker() as session:
        with session.begin():
            with tenant_scope(session, pilot["tenant_a"]):
                drill = pilot_service.record_recovery_drill(
                    session, tenant_id=pilot["tenant_a"], scope="database",
                    outcome=outcome, performed_by_user_id=pilot["user_id"], now=NOW,
                    measurement=_measurement(), integrity_verified=True, fencing_verified=True,
                )
                drill_id = drill.drill_id
    assert drill.measured_rpo_seconds is not None
    assert drill.met_targets is False
    with app_sessionmaker() as session:
        with pytest.raises((IntegrityError, DBAPIError)):
            with session.begin():
                with tenant_scope(session, pilot["tenant_a"]):
                    session.execute(text("UPDATE recovery_drills SET met_targets=true WHERE drill_id=:d"), {"d":drill_id})
