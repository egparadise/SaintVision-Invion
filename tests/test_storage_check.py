"""Re-hashing a contributed folder, and the ways that must fail.

``record_storage_check`` had no caller, so every active folder was reported as
"never checked" — accurately. These tests pin the collector that changes that,
and in particular the safeguard it is built around: a folder is identified by its
node, and checking a same-named local path under another node's identity would
manufacture evidence that somebody had looked.
"""

from __future__ import annotations

import hashlib
import random
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.postgres

TOOL = Path(__file__).resolve().parents[1] / "tools" / "storage_check.py"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _id(prefix: str) -> str:
    return prefix + "_" + "".join(random.choice(CROCKFORD) for _ in range(26))


@pytest.fixture
def folder(migrated, database_url, tmp_path):
    """A contributed folder on this machine with one catalogued file in it."""
    import psycopg

    dsn = database_url.replace("postgresql+psycopg://", "postgresql://")
    ids = {
        "dsn": dsn,
        "tenant": str(uuid.uuid4()),
        "user": _id("usr"),
        "node": _id("nod"),
        "otherNode": _id("nod"),
        "contribution": _id("stc"),
        "otherContribution": _id("stc"),
        "location": _id("dlc"),
        "root": tmp_path / "contributed",
    }
    ids["root"].mkdir()
    payload = b"a catalogued dataset file\n"
    (ids["root"] / "data.bin").write_bytes(payload)
    ids["digest"] = hashlib.sha256(payload).hexdigest()

    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'sc')",
            (ids["tenant"], uuid.uuid4().hex[:12]),
        )
        conn.execute(
            "INSERT INTO public.users(tenant_id,user_id,external_subject,display_name,status) "
            "VALUES(%s,%s,%s,'u','active')",
            (ids["tenant"], ids["user"], "oidc:" + uuid.uuid4().hex),
        )
        for node in (ids["node"], ids["otherNode"]):
            conn.execute(
                "INSERT INTO public.nodes"
                "(tenant_id,node_id,hostname,os_type,os_version,agent_version,status) "
                "VALUES(%s,%s,%s,'linux','1','1','active')",
                (ids["tenant"], node, "host-" + node[-4:]),
            )
        conn.execute(
            "INSERT INTO public.storage_contributions"
            "(tenant_id,contribution_id,node_id,declared_path,normalized_path,"
            "mode,status,registered_by_user_id) "
            "VALUES(%s,%s,%s,%s,%s,'read_write','active',%s)",
            (
                ids["tenant"],
                ids["contribution"],
                ids["node"],
                str(ids["root"]),
                str(ids["root"]),
                ids["user"],
            ),
        )
        # A folder on a different machine, with a root that exists right here.
        conn.execute(
            "INSERT INTO public.storage_contributions"
            "(tenant_id,contribution_id,node_id,declared_path,normalized_path,"
            "mode,status,registered_by_user_id) "
            "VALUES(%s,%s,%s,%s,%s,'read_write','active',%s)",
            (
                ids["tenant"],
                ids["otherContribution"],
                ids["otherNode"],
                str(ids["root"]),
                str(ids["root"]),
                ids["user"],
            ),
        )
        conn.execute(
            "INSERT INTO public.data_locations"
            "(tenant_id,location_id,contribution_id,uri,kind,relative_path,"
            "byte_size,checksum_sha256,verified_at,ready) "
            "VALUES(%s,%s,%s,%s,'dataset','data.bin',%s,%s,now(),true)",
            (
                ids["tenant"],
                ids["location"],
                ids["contribution"],
                f"inv://datasets/sc@1/{ids['location']}",
                len(payload),
                ids["digest"],
            ),
        )
    return ids


def _run(ids, node: str | None = None) -> tuple[dict, int]:
    import json

    completed = subprocess.run(
        [
            sys.executable, str(TOOL),
            "--dsn", ids["dsn"],
            "--tenant", ids["tenant"],
            "--node", node or ids["node"],
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert completed.stdout, completed.stderr
    return json.loads(completed.stdout), completed.returncode


def _checks(ids) -> list[tuple]:
    import psycopg

    with psycopg.connect(ids["dsn"]) as conn:
        return conn.execute(
            "SELECT contribution_id, reachable, sampled_count, mismatch_count, healthy "
            "FROM public.storage_checks WHERE tenant_id=%s ORDER BY checked_at",
            (ids["tenant"],),
        ).fetchall()


def test_an_intact_folder_is_checked_and_recorded(folder) -> None:
    report, code = _run(folder)
    (entry,) = report["checked"]
    assert entry["healthy"] is True
    assert (entry["sampled"], entry["mismatches"]) == (1, 0)
    assert _checks(folder) == [(folder["contribution"], True, 1, 0, True)]
    assert code == 0


def test_a_changed_byte_makes_the_folder_unhealthy(folder) -> None:
    """Presence is not health. This is the whole reason the check re-hashes."""
    (folder["root"] / "data.bin").write_bytes(b"a catalogued dataset file!\n")
    report, code = _run(folder)
    (entry,) = report["checked"]
    assert entry["healthy"] is False
    assert entry["mismatches"] == 1
    assert entry["detail"]["mismatchDetail"][0]["reason"] == "checksum differs"
    assert code == 1


def test_a_missing_catalogued_file_is_a_mismatch_not_a_skip(folder) -> None:
    (folder["root"] / "data.bin").unlink()
    report, code = _run(folder)
    (entry,) = report["checked"]
    assert entry["detail"]["mismatchDetail"][0]["reason"] == "catalogued file is absent"
    assert entry["healthy"] is False
    assert code == 1


def test_an_unreachable_root_is_recorded_as_unreachable(folder) -> None:
    import shutil

    shutil.rmtree(folder["root"])
    report, code = _run(folder)
    (entry,) = report["checked"]
    assert entry["reachable"] is False
    assert entry["healthy"] is False
    assert _checks(folder)[0][1:] == (False, 0, 0, False)
    assert code == 1


def test_another_nodes_folder_is_refused_not_checked_locally(folder) -> None:
    """The safeguard. Both contributions point at a root that exists here.

    Checking the second one would file a health record about this machine's
    directory under the identity of a folder on another machine -- evidence that
    somebody looked at something nobody looked at.
    """
    report, _ = _run(folder)
    assert [c["contributionId"] for c in report["checked"]] == [folder["contribution"]]
    (skipped,) = report["refused"]
    assert skipped["contributionId"] == folder["otherContribution"]
    assert "another node" in skipped["reason"]
    # And nothing was filed for it.
    assert [row[0] for row in _checks(folder)] == [folder["contribution"]]


def test_a_location_without_a_checksum_is_not_counted_as_intact(folder) -> None:
    """Nothing to compare against is not the same as compared and fine."""
    import psycopg

    with psycopg.connect(folder["dsn"], autocommit=True) as conn:
        conn.execute(
            "UPDATE public.data_locations SET ready=false, checksum_sha256=NULL, "
            "verified_at=NULL WHERE location_id=%s",
            (folder["location"],),
        )
    report, _ = _run(folder)
    (entry,) = report["checked"]
    assert entry["sampled"] == 0
    assert entry["detail"]["unverifiable"][0]["reason"] == "no recorded checksum"
    # Reachable with nothing verifiable is still "healthy" by the model's rule
    # -- no mismatch was found -- so the sample count is what tells the reader
    # that nothing was actually compared.
    assert entry["detail"]["catalogued"] == 1


def test_the_folder_check_clears_the_acceptance_blocker(folder) -> None:
    """What this collector is for: AC-12 counted every folder as unchecked."""
    import datetime as dt

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from saintvision.db.session import tenant_scope
    from saintvision.services import pilot as pilot_service

    url = "postgresql+psycopg://" + folder["dsn"][len("postgresql://") :]
    engine = create_engine(url, future=True)
    factory = sessionmaker(engine, future=True, expire_on_commit=False)
    tenant = uuid.UUID(folder["tenant"])
    try:
        with factory() as session, session.begin(), tenant_scope(session, tenant):
            before = pilot_service.contributions_needing_attention(
                session, tenant_id=tenant, now=dt.datetime.now(dt.timezone.utc)
            )
        assert len(before) == 2, "both folders start out never checked"

        _run(folder)

        with factory() as session, session.begin(), tenant_scope(session, tenant):
            after = pilot_service.contributions_needing_attention(
                session, tenant_id=tenant, now=dt.datetime.now(dt.timezone.utc)
            )
        # The one on this node is now checked; the one on the other node is
        # still unchecked, because nobody has been to that machine.
        assert [c["contributionId"] for c in after] == [folder["otherContribution"]]
    finally:
        engine.dispose()
