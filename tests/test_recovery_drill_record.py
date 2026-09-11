"""The drill's recording step, which had never run.

``tools/recovery_drill.py`` promises three things in its own docstring, and the
third is that it writes the row. That path only executes when ``--tenant`` and
``--user`` are supplied, and it carried three separate faults at once: SQLAlchemy
resolving a bare ``postgresql://`` to psycopg2, which this project does not
install; ``DrillMeasurement`` called with keyword names it does not have; and a
backup filed under a kind the ledger does not allow. Every drill run without
those flags exited 0 and wrote nothing, so none of it ever surfaced.

These tests exercise the recording path against a real database, because that is
where all three faults lived — in the wiring between this tool and services it
calls, not in any logic either side owns.
"""

from __future__ import annotations

import datetime as dt
import random
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

pytestmark = pytest.mark.postgres

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _id(prefix: str) -> str:
    return prefix + "_" + "".join(random.choice(CROCKFORD) for _ in range(26))


class _Args:
    """Only the fields ``record`` reads, so the test states its dependencies."""

    def __init__(self, dsn: str, tenant: str, user: str) -> None:
        self.record_dsn = dsn
        self.source = dsn
        self.tenant = tenant
        self.user = user
        self.off_site = False


@pytest.fixture
def recorded(migrated, database_url):
    """A tenant and user the ledger rows can belong to."""
    import psycopg

    dsn = database_url.replace("postgresql+psycopg://", "postgresql://")
    tenant, user = str(uuid.uuid4()), _id("usr")
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'drill')",
            (tenant, uuid.uuid4().hex[:12]),
        )
        conn.execute(
            "INSERT INTO public.users(tenant_id,user_id,external_subject,display_name,status) "
            "VALUES(%s,%s,%s,'u','active')",
            (tenant, user, "oidc:" + uuid.uuid4().hex),
        )
    return {"dsn": dsn, "tenant": tenant, "user": user}


def _report(**overrides):
    report = {
        "measuredRpoSeconds": 6,
        "measuredRtoSeconds": 6,
        "fencingVerified": True,
        "fencingNote": "the restored sequence is at or above every issued token",
        "integrityVerified": True,
        "backupSha256": "a" * 64,
        "backupBytes": 1024,
        "tablesWithDifferentCounts": [],
        "tablesWithDifferentContent": [],
        "fencingAdvanceRequired": 0,
        "recoveryCapability": {"operationalRpoBoundSeconds": None},
    }
    report.update(overrides)
    return report


def _rows(dsn: str, sql: str, params: tuple = ()):
    import psycopg

    with psycopg.connect(dsn) as conn:
        return conn.execute(sql, params).fetchall()


def test_a_passing_drill_writes_its_row(recorded) -> None:
    """The claim the docstring makes, checked against the database."""
    from recovery_drill import record

    drill_id = record(_report(), _Args(**recorded))
    assert drill_id and drill_id.startswith("drl_")
    rows = _rows(
        recorded["dsn"],
        "SELECT scope, outcome, measured_rpo_seconds, measured_rto_seconds, "
        "fencing_verified FROM public.recovery_drills WHERE tenant_id=%s",
        (recorded["tenant"],),
    )
    assert rows == [("database", "passed", 6, 6, True)]


def test_a_saved_backup_is_filed_and_verified_and_linked(recorded) -> None:
    """A saved dump is a backup, and the ledger existed with no caller.

    Verified from the digest of the file on disk, and linked to the drill, so a
    later reader can tell which backup the rehearsal actually restored.
    """
    from recovery_drill import record

    digest = "b" * 64
    record(
        _report(
            backupSource="/backups/drill.dump",
            savedBackupSha256=digest,
            savedBackupBytes=2048,
            savedBackupIntact=True,
        ),
        _Args(**recorded),
    )
    (backup,) = _rows(
        recorded["dsn"],
        "SELECT kind, location_ref, off_site, byte_size, verified, checksum_sha256 "
        "FROM public.backup_records WHERE tenant_id=%s",
        (recorded["tenant"],),
    )
    # logical, because pg_dump --format=custom is not a base backup: this
    # platform produces no base backup and archives no WAL.
    assert backup[:5] == ("logical", "/backups/drill.dump", False, 2048, True)
    assert backup[5] == digest
    (linked,) = _rows(
        recorded["dsn"],
        "SELECT backup_id IS NOT NULL FROM public.recovery_drills WHERE tenant_id=%s",
        (recorded["tenant"],),
    )
    assert linked == (True,)


def test_a_backup_whose_file_does_not_match_is_filed_unverified(recorded) -> None:
    """Filed, not verified. The row is the evidence that a bad backup exists.

    Dropping it would lose the only record that a backup was taken and came out
    wrong, which is the thing somebody needs to see before restoring from it.
    """
    from recovery_drill import record

    record(
        _report(
            backupSource="/backups/truncated.dump",
            savedBackupSha256="c" * 64,
            savedBackupBytes=17,
            savedBackupIntact=False,
        ),
        _Args(**recorded),
    )
    (backup,) = _rows(
        recorded["dsn"],
        "SELECT verified, checksum_sha256 FROM public.backup_records WHERE tenant_id=%s",
        (recorded["tenant"],),
    )
    assert backup == (False, None)


def test_a_failed_drill_is_recorded_without_measurements(recorded) -> None:
    """A drill that did not pass has no numbers to offer, and says so.

    The service refuses a pass without measurements; recording a failure with
    them would be claiming the restore met a target it never reached.
    """
    from recovery_drill import record

    record(_report(integrityVerified=False), _Args(**recorded))
    (row,) = _rows(
        recorded["dsn"],
        "SELECT outcome, measured_rpo_seconds, measured_rto_seconds "
        "FROM public.recovery_drills WHERE tenant_id=%s",
        (recorded["tenant"],),
    )
    assert row == ("failed", None, None)


def test_off_site_is_the_operators_assertion_not_the_tools(recorded) -> None:
    """ADR-018 separates a durable write from surviving the failure domain.

    This tool cannot tell whether a path is off-site, so it records what it was
    told and defaults to the claim that asserts less.
    """
    from recovery_drill import record

    args = _Args(**recorded)
    args.off_site = True
    record(
        _report(
            backupSource="//nas/offsite/drill.dump",
            savedBackupSha256="d" * 64,
            savedBackupBytes=64,
            savedBackupIntact=True,
        ),
        args,
    )
    (row,) = _rows(
        recorded["dsn"],
        "SELECT off_site FROM public.backup_records WHERE tenant_id=%s",
        (recorded["tenant"],),
    )
    assert row == (True,)
