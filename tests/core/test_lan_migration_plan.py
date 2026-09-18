from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from migration_graph import Revision
from plan_lan_migration import gap_plan


@pytest.fixture
def graph(tmp_path):
    rows = []
    for name, parents in [("a", None), ("b", "a"), ("c", "a"), ("d", ("b", "c"))]:
        p = tmp_path / (name + ".py")
        p.write_text(name)
        rows.append(Revision(name, parents, p, True, "forward fix"))
    return rows


@pytest.mark.parametrize("heads,pending", [(["a"], ["b", "c", "d"]), (["b"], ["c", "d"]), (["b", "c"], ["d"]), (["d"], [])])
def test_pending_includes_unapplied_merge_branch(graph, heads, pending):
    result = gap_plan(heads, graph)
    assert [r["revision"] for r in result["pending"]] == pending
    assert result["migrationAuthorized"] is False
    assert result["schemaIntegrityAssessed"] is False
    assert all(len(r["sha256"]) == 64 for r in result["pending"])


@pytest.mark.parametrize("heads", [[], ["unknown"], ["b", "b"], ["a", "b"]])
def test_inconsistent_metadata_refused(graph, heads):
    with pytest.raises(ValueError):
        gap_plan(heads, graph)


@pytest.mark.parametrize("failure,expected,code", [
    ("db", "migration_metadata_database_error", 2),
    ("shape", "migration_metadata_internal_error", 3),
])
def test_cli_separates_database_and_internal_failures(monkeypatch, capsys, tmp_path, failure, expected, code):
    import plan_lan_migration as subject
    if failure == "db":
        monkeypatch.setattr(subject, "inspect", lambda path: (_ for _ in ()).throw(subject.MigrationPlanDatabaseError("08001")))
    else:
        monkeypatch.setattr(subject, "inspect", lambda path: (_ for _ in ()).throw(TypeError("dsn-value")))
    monkeypatch.setattr(subject.sys, "argv", ["plan_lan_migration.py", "--state", "state.json", "--output", str(tmp_path / "out.json")])
    assert subject.main() == code
    output = capsys.readouterr()
    assert expected in output.err and "dsn-value" not in output.out + output.err


@pytest.mark.postgres
def test_real_postgres_column_grants(migrated, owner_engine):
    from psycopg.rows import dict_row
    from check_lan_storage_readiness import relation_access

    with owner_engine.connect() as outer:
        conn = outer.connection.driver_connection
        old_factory = conn.row_factory
        try:
            conn.row_factory = dict_row
            conn.execute("SET LOCAL ROLE inv_kernel")
            for name in ("public.storage_contributions", "public.data_locations"):
                result = relation_access(conn, name)
                assert result["tableSelectAllowed"] is False
                assert result["selectAllowed"] is True
                assert result["missingColumns"] == []
            conn.execute("SET LOCAL ROLE inv_app")
            result = relation_access(conn, "inv.storage_sample_requests")
            assert result["present"] is True
            assert result["selectAllowed"] is False
            assert relation_access(conn, "inv.nonexistent_relation")["present"] is False
        finally:
            conn.rollback()
            conn.row_factory = old_factory
