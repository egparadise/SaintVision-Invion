"""Self-tests for tools/collect_rls_evidence.py (S02-DB evidence collector).

Pure tests pin the expectation evaluator, the Markdown renderer and the secret
guard.  Real-PostgreSQL tests (``INV_TEST_ADMIN_DSN``) run the collector against
a disposable migrated database and include a negative control: an unscoped
table granted to ``inv_app`` must be reported (E2/E4) and drive exit 1, and must
disappear from the report once dropped.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import collect_rls_evidence as tool  # noqa: E402


def _observation(**overrides) -> dict:
    base = {
        "collector": "tools/collect_rls_evidence.py", "collected_at": "2026-09-22T13:00:00+00:00", "git_sha": "abc1234",
        "database": {"name": "db", "server_version": "16.3", "migration_head": "0046",
                     "observer": {"role": "invowner", "superuser": True, "bypassrls": False}},
        "tenant_guc": {"name": "inv.tenant_id", "unset_value": None, "tenant_a": "t-a", "known_tenants": 2, "random_tenant": "r"},
        "schemas": ["public", "inv"],
        "ground_truth": {"public.projects": {"total": {"rows": 2}, "tenant_a": {"rows": 1}, "other_tenants": {"rows": 1}}},
        "roles": {
            "inv_app": {
                "present": True, "superuser": False, "bypassrls": False, "login": False, "inherit": True, "member_of": [],
                "tables": {
                    "public.projects": {
                        "tenant_scoped": True, "rls_enabled": True, "rls_forced": True,
                        "privileges": {"select": "table", "insert": "table", "update": "table", "delete": "table"},
                        "policies": [{"name": "projects_tenant_isolation", "cmd": "ALL", "permissive": "PERMISSIVE",
                                      "roles": ["inv_app"], "using": True, "with_check": True}],
                        "visible": {"guc_unset": {"rows": 0}, "guc_tenant_a": {"rows": 1},
                                    "guc_tenant_a_foreign_rows": {"rows": 0}, "guc_unknown_tenant": {"rows": 0},
                                    "guc_not_uuid": {"denied": "22P02"},
                                    "identity": {"method": "ctid", "owner_a": {"rows": 1, "fp": "aa"}, "role_a": {"rows": 1, "fp": "aa"}, "match": True}},
                    },
                    "inv.model_manifests": {
                        "tenant_scoped": True, "rls_enabled": False, "rls_forced": False,
                        "privileges": {"select": None, "insert": None, "update": None, "delete": None}, "policies": [],
                    },
                },
                "functions": {"public.model_location_readiness(uuid, text[])": {"execute": False}},
            },
            "inv_runtime_dev": {"present": False},
        },
        "definer_functions": {"public.model_location_readiness(uuid, text[])": {
            "owner": "invowner", "config": ["search_path=pg_catalog"], "execute_grants": ["inv_kernel"]}},
    }
    base.update(overrides)
    return base


def test_clean_observation_has_no_violations():
    assert tool.evaluate(_observation()) == []


@pytest.mark.parametrize("mutate, rule", [
    (lambda o: o["roles"]["inv_app"].__setitem__("bypassrls", True), "E1"),
    (lambda o: o["roles"]["inv_app"]["tables"]["public.projects"].__setitem__("rls_forced", False), "E2"),
    (lambda o: o["roles"]["inv_app"]["tables"]["public.projects"]["visible"].__setitem__("guc_unset", {"rows": 3}), "E3"),
    (lambda o: o["roles"]["inv_app"]["tables"]["public.projects"]["visible"].__setitem__("guc_tenant_a_foreign_rows", {"rows": 1}), "E4"),
    (lambda o: o["roles"]["inv_app"]["tables"]["public.projects"]["visible"].__setitem__("guc_unknown_tenant", {"rows": 1}), "E5"),
    (lambda o: o["definer_functions"]["public.model_location_readiness(uuid, text[])"].__setitem__("execute_grants", ["PUBLIC"]), "E6"),
])
def test_each_expectation_is_enforced(mutate, rule):
    observation = deepcopy(_observation())
    mutate(observation)
    rules = [v["rule"] for v in tool.evaluate(observation)]
    assert rules == [rule]


def test_unreadable_or_unscoped_tables_are_not_judged():
    """A table the role cannot read (kernel table for inv_app) is never a violation even without RLS."""
    observation = _observation()
    observation["roles"]["inv_app"]["tables"]["inv.model_manifests"]["rls_enabled"] = False
    assert tool.evaluate(observation) == []


def test_baseline_accepts_only_listed_role_table_rules():
    violations = [{"rule": "E2", "role": "inv_app", "table": "public.tenants", "detail": "x"},
                  {"rule": "E2", "role": "inv_app", "table": "public.audit_events", "detail": "y"},
                  {"rule": "E1", "role": "inv_app", "detail": "z"}]
    baseline = {"accepted": [{"role": "inv_app", "table": "public.tenants", "rules": ["E2"], "reason": "registry"}]}
    remaining, accepted = tool.apply_baseline(violations, baseline)
    assert [v["table"] for v in remaining if "table" in v] == ["public.audit_events"] and remaining[-1]["rule"] == "E1"
    assert accepted == [{**violations[0], "reason": "registry", "since": None}]
    shipped = tool.load_baseline()
    assert all({"role", "table", "rules", "reason"} <= set(e) for e in shipped["accepted"])


def test_compact_drops_untouched_tables_and_keeps_note():
    observation = _observation()
    observation["note"] = "concurrent load lane"
    compact = tool._compact(observation)
    assert "inv.model_manifests" not in compact["roles"]["inv_app"]["tables"]
    assert "public.projects" in compact["roles"]["inv_app"]["tables"]
    assert "condition: concurrent load lane" in tool.render_markdown(observation, [], [])


def test_denied_probe_counts_as_zero_rows():
    observation = deepcopy(_observation())
    observation["roles"]["inv_app"]["tables"]["public.projects"]["visible"]["guc_unset"] = {"denied": "42501"}
    assert tool.evaluate(observation) == []


def test_e4_catches_same_count_row_swap_by_identity():
    """Codex finding 3/4 (PR #68): a foreign row replacing an equal number of tenant-A rows keeps
    every count equal; only row identity (ctid or tenant_id + full PK) exposes it."""
    observation = deepcopy(_observation())
    vis = observation["roles"]["inv_app"]["tables"]["public.projects"]["visible"]
    vis["guc_tenant_a_foreign_rows"] = {"denied": "42501"}
    vis["identity"] = {"method": "pk", "columns": ["tenant_id", "project_id"], "owner_a": {"rows": 1, "fp": "aa"}, "role_a": {"rows": 1, "fp": "bb"}, "match": False}
    violations = tool.evaluate(observation)
    assert [v["rule"] for v in violations] == ["E4"] and "differs from the owner" in violations[0]["detail"]
    vis["identity"] = {"method": "ctid", "owner_a": {"rows": 1, "fp": "aa"}, "role_a": {"rows": 1, "fp": "aa"}, "match": True}
    assert tool.evaluate(observation) == []


def test_unverifiable_identity_is_unmeasured_never_pass():
    """Codex finding 4: a non-unique projection could let a swap through; the collector no longer
    fingerprints values at all -- when identity is unreadable the table is UNMEASURED, not PASS."""
    observation = deepcopy(_observation())
    vis = observation["roles"]["inv_app"]["tables"]["public.projects"]["visible"]
    vis["identity"] = {"method": "unverifiable", "reason": "ctid denied 42501; identity columns not readable: ['project_id']"}
    assert tool.evaluate(observation) == []  # not a violation ...
    unmeasured = tool.unverified_identities(observation)
    assert [(u["rule"], u["role"], u["table"]) for u in unmeasured] == [("E4", "inv_app", "public.projects")]
    assert tool.verdict([], unmeasured) == "UNMEASURED" and tool.verdict([], []) == "PASS"
    assert tool.verdict([{"rule": "E1"}], unmeasured) == "VIOLATIONS"
    # the baseline may accept a specific unverifiable pair with a reason
    remaining, accepted = tool.apply_baseline(unmeasured, {"accepted": [{"role": "inv_app", "table": "public.projects", "rules": ["E4"], "reason": "r"}]})
    assert remaining == [] and len(accepted) == 1
    assert '"method": "projection"' not in open(tool.__file__, encoding="utf-8").read()  # value projection method is gone
    md = tool.render_markdown(observation, [], [], unmeasured)
    assert "**UNMEASURED**" in md and "Unverifiable row identities" in md


def test_e4_uses_owner_truth_when_foreign_probe_is_denied():
    """Codex finding 1 (PR #68): a column-privilege role cannot run ``tenant_id <> A``; the
    denied probe must not read as zero foreign rows when the role sees more than tenant A owns."""
    observation = deepcopy(_observation())
    vis = observation["roles"]["inv_app"]["tables"]["public.projects"]["visible"]
    vis.pop("identity")  # older observation without identity: count comparison is the fallback
    vis["guc_tenant_a"] = {"rows": 2}
    vis["guc_tenant_a_foreign_rows"] = {"denied": "42501"}
    violations = tool.evaluate(observation)
    assert [v["rule"] for v in violations] == ["E4"]
    assert "owner counts 1" in violations[0]["detail"] and "42501" in violations[0]["detail"]
    # a denied probe with a visible count that matches the owner's tenant-A count is not a violation
    vis["guc_tenant_a"] = {"rows": 1}
    assert tool.evaluate(observation) == []


def test_provenance_records_content_hashes_and_head():
    prov = tool.provenance()
    assert prov["collector_sha256"] and len(prov["collector_sha256"]) == 64
    assert prov["baseline_sha256"] and len(prov["baseline_sha256"]) == 64
    assert isinstance(prov["uncommitted_sources"], list)
    md = tool.render_markdown({**_observation(), "provenance": prov}, [])
    assert prov["collector_sha256"] in md


def test_markdown_lists_absent_roles_and_verdict():
    md = tool.render_markdown(_observation(), [])
    assert "**PASS**" in md and "absent in pg_roles" in md and "`public.projects`" in md
    md2 = tool.render_markdown(_observation(), [{"rule": "E3", "role": "inv_app", "table": "public.projects", "detail": "3 rows"}])
    assert "1 violation(s)" in md2 and "| E3 | inv_app | public.projects | 3 rows |" in md2


def test_secret_guard_rejects_dsn_and_password(tmp_path):
    dsn = "postgresql://u:s3cretpw@127.0.0.1:5432/db"
    with pytest.raises(ValueError):
        tool.assert_no_secrets("dsn=" + dsn, dsn)
    with pytest.raises(ValueError):
        tool.assert_no_secrets("password s3cretpw leaked", dsn)
    tool.assert_no_secrets("clean text", dsn)
    json_path, md_path = tool.write_evidence(_observation(), [], tmp_path, "x", dsn)
    assert "s3cretpw" not in json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    assert json.loads(json_path.read_text(encoding="utf-8"))["verdict"] == "PASS"


# ---------------------------------------------------------------------------
# real PostgreSQL
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rls_db():
    admin = os.getenv("INV_TEST_ADMIN_DSN")
    if not admin:
        if os.getenv("CI"):
            pytest.fail("CI requires INV_TEST_ADMIN_DSN; DB tests must not be skipped")
        pytest.skip("Set INV_TEST_ADMIN_DSN to a disposable PostgreSQL 16+ test server")
    class Redacted(dict):  # pytest prints fixture values on failure: never show the DSN
        def __repr__(self):
            return "<rls_db dsn=redacted>"

    with tool.disposable_database(admin) as (owner, tenant_a):
        yield Redacted(owner=owner, tenant_a=tenant_a)


@pytest.mark.postgres
def test_real_pg_boundary_passes_and_records_kernel_denial(rls_db, tmp_path):
    observation = tool.collect(rls_db["owner"], ("inv_app", "inv_kernel", "inv_runtime_dev"), rls_db["tenant_a"])
    violations, accepted = tool.apply_baseline(tool.evaluate(observation), tool.load_baseline())
    # Pinned gap at migration head 0046: public.audit_events is readable by inv_app without RLS.
    # This assertion flips to [] once a migration scopes audit_events (Codex security review).
    assert [(v["rule"], v["role"], v["table"]) for v in violations] == [("E2", "inv_app", "public.audit_events")]
    assert {(a["role"], a["table"]) for a in accepted} == {("inv_app", "public.tenants")}
    app = observation["roles"]["inv_app"]
    assert app["present"] and not app["superuser"] and not app["bypassrls"]
    projects = app["tables"]["public.projects"]
    assert projects["rls_enabled"] and projects["rls_forced"] and projects["privileges"]["select"] == "table"
    assert observation["ground_truth"]["public.projects"] == {"total": {"rows": 2}, "tenant_a": {"rows": 1}, "other_tenants": {"rows": 1}}
    assert projects["visible"]["guc_unset"] == {"rows": 0}
    assert projects["visible"]["guc_tenant_a"] == {"rows": 1}
    assert projects["visible"]["guc_tenant_a_foreign_rows"] == {"rows": 0}
    assert projects["visible"]["guc_unknown_tenant"] == {"rows": 0}
    assert projects["visible"]["guc_not_uuid"] == {"denied": "22P02"}
    # kernel tables are not readable by the business role at all
    manifests = app["tables"]["inv.model_manifests"]
    assert manifests["privileges"]["select"] is None and "visible" not in manifests
    # the SECURITY DEFINER readiness function is executable by inv_kernel only
    readiness = [k for k in observation["definer_functions"] if k.startswith("public.model_location_readiness(")]
    assert len(readiness) == 1
    assert observation["definer_functions"][readiness[0]]["execute_grants"] == ["inv_kernel"]
    assert app["functions"][readiness[0]]["execute"] is False
    assert observation["roles"]["inv_kernel"]["functions"][readiness[0]]["execute"] is True
    runtime_dev = observation["roles"]["inv_runtime_dev"]  # cluster-level role: may or may not exist on this server
    assert runtime_dev["present"] in (True, False)
    if runtime_dev["present"]:
        assert not runtime_dev["superuser"] and not runtime_dev["bypassrls"]
    json_path, md_path = tool.write_evidence(observation, violations, tmp_path, "probe", rls_db["owner"])
    text = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    assert "password" not in text.lower() or "password" in json.dumps(observation)  # DSN never embedded
    assert rls_db["owner"] not in text


@pytest.mark.postgres
def test_real_pg_negative_control_unscoped_table_is_reported_then_clears(rls_db):
    """A table with tenant rows granted to inv_app but without RLS must trip E2 and E4."""
    import psycopg
    other = str(uuid4())
    with psycopg.connect(rls_db["owner"]) as conn:
        conn.execute("INSERT INTO inv.tenants VALUES (%s,'rls-evidence-c') ON CONFLICT DO NOTHING", (other,))
        conn.execute("CREATE TABLE public.rls_probe_unscoped(tenant_id uuid NOT NULL, note text)")
        conn.execute("GRANT SELECT ON public.rls_probe_unscoped TO inv_app")
        conn.execute("INSERT INTO public.rls_probe_unscoped VALUES (%s,'a'),(%s,'other')", (rls_db["tenant_a"], other))
    with psycopg.connect(rls_db["owner"]) as conn:
        # Codex finding 1: a role with column-level SELECT that excludes tenant_id cannot run the
        # ``tenant_id <> A`` probe; E4 must still trip through the owner-side count.
        conn.execute("CREATE TABLE public.rls_probe_colpriv(tenant_id uuid NOT NULL, note text)")
        conn.execute("GRANT SELECT(note) ON public.rls_probe_colpriv TO inv_app")
        conn.execute("INSERT INTO public.rls_probe_colpriv VALUES (%s,'a'),(%s,'other')", (rls_db["tenant_a"], other))
        # Codex finding 3: same-count row swap.  An inverted policy shows the role exactly one
        # row under GUC=A -- but it is tenant B's row.  Every count matches (owner A=1, role A=1)
        # and the column-only role cannot run the foreign probe; only row identity exposes it.
        # identity readable through tenant_id + PK; the swapped rows carry the SAME note value so a
        # value projection would collide (Codex finding 4) -- only the key set exposes the swap
        conn.execute("CREATE TABLE public.rls_probe_swap(id int PRIMARY KEY, tenant_id uuid NOT NULL, note text)")
        conn.execute("ALTER TABLE public.rls_probe_swap ENABLE ROW LEVEL SECURITY")
        conn.execute("ALTER TABLE public.rls_probe_swap FORCE ROW LEVEL SECURITY")
        conn.execute("CREATE POLICY swapped ON public.rls_probe_swap FOR SELECT TO inv_app "
                     "USING (tenant_id <> nullif(current_setting('inv.tenant_id', true), '')::uuid)")
        conn.execute("GRANT SELECT(id, tenant_id, note) ON public.rls_probe_swap TO inv_app")
        conn.execute("INSERT INTO public.rls_probe_swap VALUES (1,%s,'same'),(2,%s,'same')", (rls_db["tenant_a"], other))
    try:
        observation = tool.collect(rls_db["owner"], ("inv_app",), rls_db["tenant_a"])
        remaining, _ = tool.apply_baseline(tool.evaluate(observation), tool.load_baseline())
        rules = sorted({(v["rule"], v.get("table")) for v in remaining if v.get("table") == "public.rls_probe_unscoped"})
        assert rules == [("E2", "public.rls_probe_unscoped"), ("E3", "public.rls_probe_unscoped"),
                         ("E4", "public.rls_probe_unscoped"), ("E5", "public.rls_probe_unscoped")]
        vis = observation["roles"]["inv_app"]["tables"]["public.rls_probe_unscoped"]["visible"]
        assert vis["guc_unset"] == {"rows": 2} and vis["guc_tenant_a_foreign_rows"] == {"rows": 1}
        colpriv = observation["roles"]["inv_app"]["tables"]["public.rls_probe_colpriv"]
        assert colpriv["privileges"]["select"] == "column"
        assert colpriv["visible"]["guc_tenant_a_foreign_rows"] == {"denied": "42501"}
        # note-only privilege on a table without a PK: identity is unverifiable -> UNMEASURED, not a pass
        assert colpriv["visible"]["identity"]["method"] == "unverifiable", colpriv["visible"]["identity"]
        unmeasured, _ = tool.apply_baseline(tool.unverified_identities(observation), tool.load_baseline())
        assert [(u["role"], u["table"]) for u in unmeasured] == [("inv_app", "public.rls_probe_colpriv")]
        assert not [v for v in remaining if v.get("table") == "public.rls_probe_colpriv" and v["rule"] == "E4"]
        swap = observation["roles"]["inv_app"]["tables"]["public.rls_probe_swap"]
        assert swap["visible"]["guc_tenant_a"] == {"rows": 1}  # count-swap: same cardinality as the owner's A set
        assert swap["visible"]["guc_tenant_a_foreign_rows"] == {"rows": 1}  # tenant_id readable here: direct probe also fires
        assert swap["visible"]["identity"]["method"] in ("ctid", "pk") and swap["visible"]["identity"]["match"] is False, swap["visible"]["identity"]
        e4_swap = [v for v in remaining if v["rule"] == "E4" and v.get("table") == "public.rls_probe_swap"]
        assert len(e4_swap) == 1, remaining
        # the inverted policy legitimately also trips E5 (an unknown tenant sees both rows); E2/E3 stay clean
        assert not [v for v in remaining if v["rule"] in ("E2", "E3") and v.get("table") == "public.rls_probe_swap"]
    finally:
        with psycopg.connect(rls_db["owner"]) as conn:
            conn.execute("DROP TABLE public.rls_probe_unscoped")
            conn.execute("DROP TABLE public.rls_probe_colpriv")
            conn.execute("DROP TABLE public.rls_probe_swap")
    after, _ = tool.apply_baseline(tool.evaluate(tool.collect(rls_db["owner"], ("inv_app",), rls_db["tenant_a"])), tool.load_baseline())
    assert [v["table"] for v in after] == ["public.audit_events"]


@pytest.mark.postgres
def test_real_pg_cli_exit_codes(rls_db, tmp_path):
    env = {**os.environ, "INV_AUDIT_DSN": rls_db["owner"], "PYTHONUTF8": "1"}
    result = subprocess.run([sys.executable, str(ROOT / "tools/collect_rls_evidence.py"), "--out-dir", str(tmp_path),
                             "--label", "cli", "--roles", "inv_app,inv_kernel"], cwd=ROOT, env=env,
                            capture_output=True, text=True)
    # exit 1 while the audit_events gap is open at head; the CLI must still write both files
    assert result.returncode == 1, result.stdout[-500:]
    assert result.stdout.startswith("VIOLATIONS 1: roles=2") and "unmeasured=" in result.stdout
    assert "E2 inv_app public.audit_events" in result.stdout
    assert (tmp_path / "cli.json").exists() and (tmp_path / "cli.md").exists()
    assert rls_db["owner"] not in (tmp_path / "cli.json").read_text(encoding="utf-8")
    bad = subprocess.run([sys.executable, str(ROOT / "tools/collect_rls_evidence.py"), "--dsn",
                          "postgresql://nobody:nothing@127.0.0.1:1/none?connect_timeout=2", "--out-dir", str(tmp_path)],
                         cwd=ROOT, capture_output=True, text=True)
    assert bad.returncode == 2 and "nothing" not in bad.stderr
