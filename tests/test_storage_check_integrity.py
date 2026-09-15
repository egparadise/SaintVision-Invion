"""Real PostgreSQL and local files; a local sample cannot attest a Node."""

import datetime as dt
import hashlib
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import text, event
from sqlalchemy.engine import Engine

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError
from saintvision.ids import new_id
from saintvision.services import pilot as service
from test_pilot import pilot, NOW
from test_verification_readroot import directory_link

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import storage_check as tool


@pytest.fixture
def folder(owner_engine, pilot, tmp_path):
    root = tmp_path / "authorized"
    root.mkdir()
    (root / "data.bin").write_bytes(b"catalogued bytes")
    location = new_id("data_location")
    with owner_engine.begin() as c:
        c.execute(
            text(
                "UPDATE storage_contributions SET normalized_path=:root, declared_path=:root "
                "WHERE contribution_id=:id"
            ),
            {"root": str(root), "id": pilot["contribution_id"]},
        )
        c.execute(
            text(
                "INSERT INTO data_locations (tenant_id,location_id,contribution_id,uri,kind,"
                "relative_path,byte_size,checksum_sha256,ready) "
                "VALUES (:t,:id,:c,:uri,'dataset','data.bin',16,:digest,false)"
            ),
            {
                "t": pilot["tenant_a"],
                "id": location,
                "c": pilot["contribution_id"],
                "uri": "inv://datasets/test@1/" + location,
                "digest": hashlib.sha256(b"catalogued bytes").hexdigest(),
            },
        )
    args = SimpleNamespace(
        dsn=owner_engine.url.render_as_string(hide_password=False),
        tenant=str(pilot["tenant_a"]),
        node=pilot["node_id"],
        contribution=pilot["contribution_id"],
        root=str(root),
        sample=32,
    )
    return args, location


def count_checks(engine, tenant):
    with engine.connect() as c:
        return c.scalar(
            text("SELECT count(*) FROM storage_checks WHERE tenant_id=:t"), {"t": tenant}
        )


def test_intact_local_sample_is_read_only_and_not_node_attestation(folder, owner_engine, pilot):
    args, _ = folder
    checked = []

    def inspect_connection(conn, cursor, statement, parameters, context, executemany):
        if "FROM data_locations" in statement:
            cursor.execute("SHOW transaction_read_only")
            checked.append(cursor.fetchone()[0])

    before = count_checks(owner_engine, pilot["tenant_a"])
    event.listen(Engine, "before_cursor_execute", inspect_connection)
    try:
        result = tool.run(args)
    finally:
        event.remove(Engine, "before_cursor_execute", inspect_connection)
    assert checked and set(checked) == {"on"}
    assert result["sampleHealthy"] is True
    assert result["nodeBindingVerified"] is False and result["recorded"] is False
    assert result["operationalAcceptanceAssessed"] is False
    assert count_checks(owner_engine, pilot["tenant_a"]) == before


@pytest.mark.parametrize("change", ["corrupt", "missing", "size", "checksum"])
def test_unverified_bytes_never_pass(folder, owner_engine, change):
    args, location = folder
    path = Path(args.root) / "data.bin"
    if change == "corrupt":
        path.write_bytes(b"different bytes!")
    elif change == "missing":
        path.unlink()
    else:
        sql = (
            "UPDATE data_locations SET byte_size=17 WHERE location_id=:id"
            if change == "size"
            else "UPDATE data_locations SET checksum_sha256=NULL WHERE location_id=:id"
        )
        with owner_engine.begin() as c:
            c.execute(text(sql), {"id": location})
    result = tool.run(args)
    assert result["sampleHealthy"] is False and result["recorded"] is False


@pytest.mark.parametrize("scope", ["tenant", "node", "root"])
def test_scope_mismatch_refused_before_read(folder, pilot, monkeypatch, tmp_path, scope):
    args, _ = folder
    if scope == "tenant":
        args.tenant = str(pilot["tenant_b"])
    elif scope == "node":
        args.node = new_id("node")
    else:
        args.root = str(tmp_path)
    reads = []
    monkeypatch.setattr(tool, "hash_file", lambda *a, **kw: reads.append(True))
    with pytest.raises(ValueError):
        tool.run(args)
    assert reads == []


def test_root_junction_cannot_be_authorized(folder, tmp_path, owner_engine):
    args, _ = folder
    link = tmp_path / "junction"
    directory_link(link, Path(args.root))
    args.root = str(link)
    with owner_engine.begin() as c:
        c.execute(
            text("UPDATE storage_contributions SET normalized_path=:p WHERE contribution_id=:id"),
            {"p": str(link), "id": args.contribution},
        )
    try:
        with pytest.raises(OSError):
            tool.run(args)
    finally:
        import os

        os.rmdir(link) if sys.platform == "win32" else link.unlink()


@pytest.mark.parametrize("limit", [0, -1, True, 1001])
def test_invalid_limit_refused_before_database(limit):
    with pytest.raises(ValueError):
        tool.run(SimpleNamespace(sample=limit))


def test_legacy_zero_sample_healthy_row_still_needs_attention(
    owner_engine, app_sessionmaker, pilot
):
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO storage_checks(check_id,tenant_id,contribution_id,reachable,"
                "sampled_count,mismatch_count,healthy,checked_at,detail) "
                "VALUES(:id,:t,:c,true,0,0,true,:now,'{}')"
            ),
            {
                "id": new_id("storage_check"),
                "t": pilot["tenant_a"],
                "c": pilot["contribution_id"],
                "now": NOW,
            },
        )
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, pilot["tenant_a"]):
        assert service.contributions_needing_attention(s, tenant_id=pilot["tenant_a"], now=NOW)


@pytest.mark.parametrize(
    "sampled,detail", [(0, {}), (1, {"unverifiable": [{"reason": "no checksum"}]})]
)
def test_no_verified_evidence_is_not_healthy(app_sessionmaker, pilot, sampled, detail):
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, pilot["tenant_a"]):
        row = service.record_storage_check(
            s,
            tenant_id=pilot["tenant_a"],
            contribution_id=pilot["contribution_id"],
            now=NOW,
            reachable=True,
            sampled_count=sampled,
            detail=detail,
        )
        assert row.healthy is False
        assert service.contributions_needing_attention(s, tenant_id=pilot["tenant_a"], now=NOW)


@pytest.mark.parametrize("count", [-1, True, 1.5])
def test_invalid_counts_fail_before_promotion(app_sessionmaker, pilot, count):
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, pilot["tenant_a"]):
        with pytest.raises(InvError):
            service.record_storage_check(
                s,
                tenant_id=pilot["tenant_a"],
                contribution_id=pilot["contribution_id"],
                now=NOW,
                reachable=True,
                sampled_count=count,
            )


def test_tied_failed_sample_cannot_be_hidden(app_sessionmaker, pilot):
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, pilot["tenant_a"]):
        for mismatches in (0, 1):
            service.record_storage_check(
                s,
                tenant_id=pilot["tenant_a"],
                contribution_id=pilot["contribution_id"],
                now=NOW,
                reachable=True,
                sampled_count=1,
                mismatch_count=mismatches,
            )
        assert service.contributions_needing_attention(s, tenant_id=pilot["tenant_a"], now=NOW)


def test_future_observation_does_not_clear_attention(app_sessionmaker, pilot):
    with app_sessionmaker() as s, s.begin(), tenant_scope(s, pilot["tenant_a"]):
        service.record_storage_check(
            s,
            tenant_id=pilot["tenant_a"],
            contribution_id=pilot["contribution_id"],
            now=NOW + dt.timedelta(days=1),
            reachable=True,
            sampled_count=1,
        )
        result = service.contributions_needing_attention(s, tenant_id=pilot["tenant_a"], now=NOW)
        assert result[0]["reason"] == "future observation"


def test_cli_rejects_dsn_and_apply_without_echoing_secrets():
    secret = "synthetic-private-password"
    result = subprocess.run(
        [sys.executable, str(Path(tool.__file__)), "--dsn", secret, "--apply"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert secret not in result.stdout + result.stderr


@pytest.mark.parametrize("json_output", [True, False])
def test_actual_cli_reads_sample_without_recording(folder, owner_engine, pilot, json_output):
    import os
    import json

    args, _ = folder
    env = dict(os.environ, INV_STORAGE_CHECK_DSN=args.dsn)
    command = [
        sys.executable,
        str(Path(tool.__file__)),
        "--tenant",
        args.tenant,
        "--node",
        args.node,
        "--contribution",
        args.contribution,
        "--root",
        args.root,
    ]
    if json_output:
        command.append("--json")
    before = count_checks(owner_engine, pilot["tenant_a"])
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert result.returncode == 0, "local sample CLI failed (private diagnostic)"
    if json_output:
        output = json.loads(result.stdout)
        assert (
            output["sampleHealthy"] and not output["nodeBindingVerified"] and not output["recorded"]
        )
    else:
        assert "Node identity unverified" in result.stdout
    assert count_checks(owner_engine, pilot["tenant_a"]) == before


def test_sampling_reports_unexamined_files(folder, owner_engine, monkeypatch):
    args, _ = folder
    identifier = new_id("data_location")
    with owner_engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO data_locations(tenant_id,location_id,contribution_id,uri,kind,"
                "relative_path,byte_size,checksum_sha256,ready) "
                "SELECT tenant_id,:id,contribution_id,:uri,kind,relative_path,byte_size,"
                "checksum_sha256,false FROM data_locations WHERE contribution_id=:c"
            ),
            {
                "id": identifier,
                "uri": "inv://datasets/test@1/" + identifier,
                "c": args.contribution,
            },
        )
    args.sample = 1
    calls = []
    original = tool.hash_file

    def track(*a, **kw):
        calls.append(True)
        return original(*a, **kw)

    monkeypatch.setattr(tool, "hash_file", track)
    result = tool.run(args)
    assert result["catalogued"] == 2 and result["examined"] == 1 and result["unsampled"] == 1
    assert calls == [True] and result["recorded"] is False
