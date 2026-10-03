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
import re
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
                "present": True, "superuser": False, "bypassrls": False, "login": False,
                "inherit": True, "member_of": [], "granted_to": [],
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


GOOD_KEY = {
    "method": "owner-verified-key", "columns": ["tenant_id", "event_id"],
    "ownerDistinctness": {"rows": 2, "distinct": 2, "nullRows": 0},
    "owner_a": {"rows": 2, "fp": "aa"}, "role_a": {"rows": 2, "fp": "aa"}, "match": True,
}


def _bridge_observation(identity: dict) -> dict:
    """An observation whose **registered** pair carries ``identity``.

    ``OWNER_VERIFIED_KEY_SCOPE`` lists exactly (inv_cancel_bridge_owner, public.audit_events,
    (tenant_id, event_id)), so a test about the readable-key method has to use that pair: on
    any other pair the method is refused by design (#322 r2 F-R2), which the unregistered-pair
    test below measures.
    """

    observation = deepcopy(_observation())
    observation["ground_truth"]["public.audit_events"] = {
        "total": {"rows": 4}, "tenant_a": {"rows": 2}, "other_tenants": {"rows": 2},
    }
    observation["roles"]["inv_cancel_bridge_owner"] = {
        "present": True, "superuser": False, "bypassrls": False, "login": False,
        "inherit": False, "member_of": [], "granted_to": [],
        "tables": {
            "public.audit_events": {
                "tenant_scoped": True, "rls_enabled": True, "rls_forced": True,
                "privileges": {"select": "column", "insert": "column",
                               "update": None, "delete": None},
                "policies": [{"name": "cancel_bridge_audit_read", "cmd": "SELECT",
                              "permissive": "PERMISSIVE", "roles": ["inv_cancel_bridge_owner"],
                              "using": True, "with_check": False}],
                "visible": {"guc_unset": {"rows": 0}, "guc_tenant_a": {"rows": 2},
                            "guc_tenant_a_foreign_rows": {"rows": 0},
                            "guc_unknown_tenant": {"rows": 0}, "guc_not_uuid": {"denied": "22P02"},
                            "identity": deepcopy(identity)},
            },
        },
        "functions": {},
    }
    return observation


def test_e4_identity_can_be_a_readable_key_the_owner_measured_unique():
    """Card 225: a partitioned, column-granted table has an identity after all.

    ``public.audit_events`` is RANGE partitioned by ``occurred_at``, so PostgreSQL puts that
    column in the primary key, and ``inv_cancel_bridge_owner`` is granted
    ``SELECT (tenant_id, event_id)`` -- the reviewed grant, which this card may not widen.  The
    full key is therefore unreadable and ``ctid`` is denied, which used to end in
    "identity unverifiable".  What closes it is a measurement, not a wider grant: the owner
    counts rows and distinct ``(tenant_id, event_id)`` tuples over the compared rows in the same
    snapshot, and when those are equal -- over at least one row, with no NULL -- the tuple *is*
    a row identity for this comparison.
    """

    observation = _bridge_observation({**GOOD_KEY, "role_a": {"rows": 2, "fp": "bb"},
                                       "match": False})
    violations = tool.evaluate(observation)
    assert [v["rule"] for v in violations] == ["E4"]
    assert "owner-verified-key" in violations[0]["detail"]
    assert tool.unverified_identities(observation) == []

    passing = _bridge_observation(GOOD_KEY)
    assert tool.evaluate(passing) == []
    assert tool.verdict([], tool.unverified_identities(passing)) == "PASS"


@pytest.mark.parametrize(
    ("identity", "expected"),
    [
        pytest.param(
            {**GOOD_KEY, "ownerDistinctness": {"rows": 0, "distinct": 0, "nullRows": 0},
             "owner_a": {"rows": 0, "fp": "d4"}, "role_a": {"rows": 0, "fp": "d4"}},
            "compared over 0 rows",
            id="vacuous-zero-rows",
        ),
        pytest.param(
            {**GOOD_KEY, "ownerDistinctness": {"rows": 2, "distinct": 2, "nullRows": 1}},
            "are NULL in 1 of 2 rows",
            id="null-bearing-key",
        ),
        pytest.param(
            {**GOOD_KEY, "ownerDistinctness": {"rows": 2, "distinct": 1, "nullRows": 0}},
            "not unique",
            id="repeated-key",
        ),
        pytest.param(
            {**GOOD_KEY, "columns": ["tenant_id"]},
            "not registered",
            id="unregistered-columns",
        ),
        pytest.param(
            {k: v for k, v in GOOD_KEY.items() if k != "ownerDistinctness"},
            "records no measured distinctness",
            id="no-distinctness-recorded",
        ),
    ],
)
def test_a_readable_key_is_only_an_identity_while_the_measurement_says_so(identity, expected):
    """Each way the measurement falls short keeps the pair UNMEASURED, never PASS.

    ``match: true`` is present in every case here, so nothing but these checks stands between a
    forged or vacuous key and a PASS verdict.  Zero rows is the one the hosted run actually hit
    (#322 r2 F-R1): over an empty set every projection is injective and every fingerprint
    matches, which says nothing about a populated table.
    """

    observation = _bridge_observation(identity)
    assert tool.evaluate(observation) == []
    unmeasured = tool.unverified_identities(observation)
    assert [(u["rule"], u["role"], u["table"]) for u in unmeasured] == [
        ("E4", "inv_cancel_bridge_owner", "public.audit_events")
    ]
    assert expected in unmeasured[0]["detail"]
    assert tool.verdict([], unmeasured) == "UNMEASURED"


def test_the_readable_key_method_cannot_spread_to_an_unregistered_pair():
    """The same well-formed key on a pair the reviewed scope does not list is refused.

    Without this the fallback would be generic: a later grant or schema change could make some
    other unmeasured (role, table) eligible and promote it to PASS with no review (#322 r2).
    """

    observation = deepcopy(_observation())
    observation["roles"]["inv_app"]["tables"]["public.projects"]["visible"]["identity"] = deepcopy(
        GOOD_KEY
    )
    unmeasured = tool.unverified_identities(observation)
    assert [(u["role"], u["table"]) for u in unmeasured] == [("inv_app", "public.projects")]
    assert "not registered" in unmeasured[0]["detail"]
    assert tool.verdict(tool.evaluate(observation), unmeasured) == "UNMEASURED"


def test_a_readable_key_that_is_not_unique_stays_unmeasured():
    """The method is only an identity while the owner's own count says it is.

    If the readable tuple repeats over the compared rows, two different rows could share it and
    a swap would survive the fingerprint -- so the collector reports the pair as unverifiable
    with the two numbers, and the verdict stays UNMEASURED rather than PASS.
    """

    observation = deepcopy(_observation())
    vis = observation["roles"]["inv_app"]["tables"]["public.projects"]["visible"]
    vis["identity"] = {
        "method": "unverifiable",
        "reason": "ctid denied 42501; the readable identity columns ['tenant_id'] are not "
                  "unique over the owner's tenant-A rows (2 rows / 1 distinct)",
    }
    assert tool.evaluate(observation) == []
    unmeasured = tool.unverified_identities(observation)
    assert [(u["rule"], u["role"], u["table"]) for u in unmeasured] == [
        ("E4", "inv_app", "public.projects")
    ]
    assert "not unique" in unmeasured[0]["detail"]
    assert tool.verdict([], unmeasured) == "UNMEASURED"


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


AUDIT_SEED = (
    "INSERT INTO public.audit_events"
    "(event_id,occurred_at,tenant_id,actor_type,action,outcome,detail)"
    " VALUES (%s,now(),%s,'system','rls.evidence.seed','allow','{}'::jsonb)"
)


def seed_audit_rows(dsn: str, tenant_a: str, other: str) -> list[str]:
    """Two audit rows per tenant, inserted by this test and removed by it.

    They do **not** belong in ``disposable_database``: measured on this tree, seeding that
    shared fixture makes ``inv_audit_reader``'s accepted E3/E4/E5 rows appear.  The reviewed
    AC-11 allowlist now accepts that real privileged visibility only while the role's measured
    login/membership/grant boundary remains exact; this helper is for the isolated collector test,
    not a second producer for that reviewed security evidence.
    """

    import psycopg

    ids = []
    with psycopg.connect(dsn, autocommit=True) as conn:
        for tenant in (tenant_a, tenant_a, other, other):
            event_id = "aud_" + uuid4().hex[:26].upper()
            conn.execute(AUDIT_SEED, (event_id, tenant))
            ids.append(event_id)
    return ids


def drop_audit_rows(dsn: str, ids: list[str]) -> None:
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("DELETE FROM public.audit_events WHERE event_id = ANY(%s::text[])", (ids,))


@pytest.mark.postgres
def test_real_pg_boundary_passes_and_records_kernel_denial(rls_db, tmp_path):
    observation = tool.collect(
        rls_db["owner"],
        (
            "inv_app",
            "inv_kernel",
            "inv_runtime_dev",
            "inv_audit_writer",
            "inv_audit_reader",
            "inv_cancel_bridge_owner",
        ),
        rls_db["tenant_a"],
    )
    violations, accepted = tool.apply_baseline(tool.evaluate(observation), tool.load_baseline())
    # The audit_events gap that was pinned at head 0046 is closed by
    # 0047_audit_events_isolation: inv_app has no SELECT on the table and RLS is
    # enabled and forced, so no expectation applies to it for that role.
    assert [(v["rule"], v["role"], v["table"]) for v in violations] == []
    assert accepted == []
    tenant_registry = observation["roles"]["inv_app"]["tables"]["public.tenants"]
    assert tenant_registry["privileges"] == {
        "select": None, "insert": None, "update": None, "delete": None,
    }
    audit = observation["roles"]["inv_app"]["tables"]["public.audit_events"]
    assert audit["rls_enabled"] and audit["rls_forced"]
    assert audit["privileges"] == {"select": None, "insert": "table", "update": None, "delete": None}
    reader = observation["roles"]["inv_audit_reader"]
    assert reader["present"] and not reader["superuser"] and not reader["bypassrls"]
    assert not reader["login"] and not reader["inherit"]
    assert reader["member_of"] == [] and reader["granted_to"] == []
    reader_audit = reader["tables"]["public.audit_events"]
    assert reader_audit["privileges"] == {
        "select": "table", "insert": None, "update": None, "delete": None,
    }
    assert reader_audit["policies"] == [{
        "name": "audit_events_audit_read", "cmd": "SELECT", "permissive": "PERMISSIVE",
        "roles": ["inv_audit_reader"], "using": True, "with_check": False,
    }]
    writer_audit = observation["roles"]["inv_audit_writer"]["tables"]["public.audit_events"]
    assert writer_audit["privileges"] == {"select": None, "insert": "table", "update": None, "delete": None}
    bridge = observation["roles"]["inv_cancel_bridge_owner"]
    assert bridge["present"] and not bridge["superuser"] and not bridge["bypassrls"]
    assert not bridge["login"] and not bridge["inherit"]
    assert bridge["member_of"] == [] and bridge["granted_to"] == []
    bridge_audit = bridge["tables"]["public.audit_events"]
    assert bridge_audit["privileges"] == {
        "select": "column", "insert": "column", "update": None, "delete": None
    }
    assert [p["cmd"] for p in bridge_audit["policies"]] == ["INSERT", "SELECT"]
    bridge_function = [
        k for k in observation["definer_functions"]
        if k.startswith("public.record_kernel_run_cancel(")
    ]
    assert len(bridge_function) == 1
    assert observation["definer_functions"][bridge_function[0]]["owner"] == (
        "inv_cancel_bridge_owner"
    )
    assert observation["definer_functions"][bridge_function[0]]["execute_grants"] == [
        "inv_kernel"
    ]
    denial = [k for k in observation["definer_functions"] if k.startswith("public.record_auth_denial(")]
    assert len(denial) == 1
    assert observation["definer_functions"][denial[0]]["owner"] == "inv_audit_writer"
    assert observation["definer_functions"][denial[0]]["execute_grants"] == ["inv_app"]
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
    assert [v["table"] for v in after] == []


@pytest.mark.postgres
def test_real_pg_an_empty_audit_table_stays_unmeasured_not_a_vacuous_pass(rls_db):
    """Zero compared rows is not a measurement, so the pair stays UNMEASURED (#322 r2 F-R1).

    The AC-11 producer measures an empty ``public.audit_events`` (the disposable fixture seeds
    tenants and projects, not audit rows).  Over an empty set every projection is injective and
    every fingerprint matches, so an earlier version of this collector reported
    ``owner-verified-key`` / ``match: true`` there and the hosted run turned that into PASS.
    Nothing about a populated table was observed, so the honest verdict is UNMEASURED and the
    reason says why.
    """

    observation = tool.collect(rls_db["owner"], tool.DEFAULT_ROLES, rls_db["tenant_a"])
    identity = (
        observation["roles"]["inv_cancel_bridge_owner"]["tables"]["public.audit_events"]
        ["visible"]["identity"]
    )
    assert identity["method"] == "unverifiable"
    assert "compared over 0 rows" in identity["reason"]
    unmeasured, _ = tool.apply_baseline(
        tool.unverified_identities(observation), tool.load_baseline()
    )
    assert ("E4", "inv_cancel_bridge_owner", "public.audit_events") in [
        (row["rule"], row["role"], row["table"]) for row in unmeasured
    ]
    violations, _accepted = tool.apply_baseline(tool.evaluate(observation), tool.load_baseline())
    assert tool.verdict(violations, unmeasured) == "UNMEASURED"


@pytest.mark.postgres
def test_real_pg_a_key_cannot_be_forged_by_a_separator_and_a_null_is_fail_closed(rls_db):
    """Two different tuples must not render as one string, and a NULL key stays unmeasured.

    ``concat_ws('\x1f', ...)`` rendered ``('a\x1fb', 'c')`` and ``('a', 'b\x1fc')``
    identically, so a row swap between those two rows would have survived the owner's
    fingerprint, and it dropped NULLs silently (#322 r2 F-R2).  ``jsonb_build_array`` escapes
    both.  Measured on real PostgreSQL because this is a property of the server's rendering.
    """

    import psycopg
    from psycopg import sql

    name = "rls_key_probe_" + uuid4().hex[:12]
    ident = sql.Identifier("public", name)
    tenant = str(uuid4())
    with psycopg.connect(rls_db["owner"], autocommit=True) as conn:
        conn.execute(
            sql.SQL("CREATE TABLE {}(tenant_id uuid, a text, b text)").format(ident)
        )
        try:
            empty = tool._distinct_fingerprint(
                conn, "public", name, ["a", "b"], "tenant_id = %s", (tenant,)
            )
            assert empty["rows"] == 0 and empty["distinct"] == 0
            assert empty["unique"] is False, "zero rows is not a measured uniqueness"
            conn.execute(
                sql.SQL("INSERT INTO {} VALUES (%s,%s,%s),(%s,%s,%s)").format(ident),
                (tenant, "a\x1fb", "c", tenant, "a", "b\x1fc"),
            )
            measured = tool._distinct_fingerprint(
                conn, "public", name, ["a", "b"], "tenant_id = %s", (tenant,)
            )
            assert measured["rows"] == 2
            assert measured["distinct"] == 2, "a separator inside a value forged the other tuple"
            assert measured["nullRows"] == 0 and measured["unique"] is True
            conn.execute(
                sql.SQL("INSERT INTO {} VALUES (%s,%s,NULL)").format(ident), (tenant, "d")
            )
            with_null = tool._distinct_fingerprint(
                conn, "public", name, ["a", "b"], "tenant_id = %s", (tenant,)
            )
            assert with_null["rows"] == 3 and with_null["nullRows"] == 1
            assert with_null["unique"] is False, "a NULL in the key must be fail-closed"
        finally:
            conn.execute(sql.SQL("DROP TABLE {}").format(ident))


@pytest.mark.postgres
def test_real_pg_the_readable_key_is_refused_for_an_unregistered_pair(rls_db, monkeypatch):
    """Take the pair out of the reviewed scope and the live probe refuses it.

    Same database, same seeded rows, same grant: with an empty
    ``OWNER_VERIFIED_KEY_SCOPE`` the collector reports the pair as unverifiable instead of
    measuring it anyway, so a later grant or schema change cannot promote another pair to PASS
    through this method (#322 r2 F-R2).
    """

    ids = seed_audit_rows(rls_db["owner"], rls_db["tenant_a"], str(uuid4()))
    try:
        monkeypatch.setattr(tool, "OWNER_VERIFIED_KEY_SCOPE", frozenset())
        observation = tool.collect(rls_db["owner"], tool.DEFAULT_ROLES, rls_db["tenant_a"])
    finally:
        drop_audit_rows(rls_db["owner"], ids)
    identity = (
        observation["roles"]["inv_cancel_bridge_owner"]["tables"]["public.audit_events"]
        ["visible"]["identity"]
    )
    assert identity["method"] == "unverifiable"
    assert "not registered" in identity["reason"]
    assert ("E4", "inv_cancel_bridge_owner", "public.audit_events") in [
        (row["rule"], row["role"], row["table"])
        for row in tool.unverified_identities(observation)
    ]


@pytest.mark.postgres
def test_real_pg_cancel_bridge_audit_identity_is_measured_not_unmeasured(rls_db):
    """Card 225: the row AC-11 reported as unmeasured is measured now, and it passes.

    Measured before this card: ``inv_cancel_bridge_owner`` / ``public.audit_events`` / E4 came
    back "row identity unverifiable: ctid denied 42501; identity columns not readable:
    ['occurred_at']" and made the whole SEC-RLS-001 report UNMEASURED.  Nothing about the grant
    changed -- the role still reads two columns and the role population is still the
    collector's own eight -- what changed is that the owner now measures whether those two
    columns identify the rows being compared.
    """

    ids = seed_audit_rows(rls_db["owner"], rls_db["tenant_a"], str(uuid4()))
    try:
        observation = tool.collect(rls_db["owner"], tool.DEFAULT_ROLES, rls_db["tenant_a"])
    finally:
        drop_audit_rows(rls_db["owner"], ids)
    bridge = observation["roles"]["inv_cancel_bridge_owner"]["tables"]["public.audit_events"]
    assert bridge["privileges"]["select"] == "column"
    identity = bridge["visible"]["identity"]
    assert identity["method"] == "owner-verified-key"
    assert identity["columns"] == ["tenant_id", "event_id"]
    # Non-vacuous: rows exist for both tenants, so an empty set is not being compared with an
    # empty set -- which is the whole difference between "measured" and "trivially equal".
    assert identity["ownerDistinctness"] == {"rows": 2, "distinct": 2, "nullRows": 0}
    assert identity["role_a"]["rows"] == identity["owner_a"]["rows"] == 2
    assert identity["match"] is True
    # The shape the canonical evaluator recomputes from (#322 r2 F-R3): the owner observation
    # is the one the distinctness was measured on, both fingerprints are digests, and ``match``
    # is exactly what comparing them says.  Written here because this is the real producer.
    assert identity["owner_a"]["rows"] == identity["ownerDistinctness"]["rows"]
    assert all(
        re.fullmatch(r"[0-9a-f]{32}", identity[side]["fp"]) for side in ("owner_a", "role_a")
    )
    assert identity["match"] is (identity["owner_a"]["fp"] == identity["role_a"]["fp"])
    truth = observation["ground_truth"]["public.audit_events"]
    assert truth["tenant_a"]["rows"] == 2 and truth["other_tenants"]["rows"] == 2
    assert bridge["visible"]["guc_unset"] == {"rows": 0}
    assert bridge["visible"]["guc_tenant_a_foreign_rows"] == {"rows": 0}

    violations = [
        v for v in tool.evaluate(observation)
        if (v.get("role"), v.get("table")) == ("inv_cancel_bridge_owner", "public.audit_events")
    ]
    unmeasured = tool.unverified_identities(observation)
    assert violations == []
    assert [(u["role"], u["table"]) for u in unmeasured] == []


@pytest.mark.postgres
def test_real_pg_negative_control_a_swapped_audit_row_set_is_e4_fail(rls_db):
    """Plant a policy violation and the measurement has to say FAIL.

    The planted policy shows the bridge role one of tenant A's audit rows and one row of another
    tenant: the same count as the owner's tenant-A set, a different set.  Counts alone cannot
    see that; the identity fingerprint can, and the foreign-row probe sees the leak as well --
    two independent observations of one policy violation, which is what should happen.
    """

    import psycopg

    canonical = (
        "CREATE POLICY cancel_bridge_audit_read ON public.audit_events"
        " FOR SELECT TO inv_cancel_bridge_owner"
        " USING (tenant_id = NULLIF(pg_catalog.current_setting('inv.tenant_id',true),'')::uuid)"
    )
    ids = seed_audit_rows(rls_db["owner"], rls_db["tenant_a"], str(uuid4()))
    with psycopg.connect(rls_db["owner"], autocommit=True) as conn:
        rows = conn.execute(
            "SELECT event_id, tenant_id::text FROM public.audit_events"
            " WHERE event_id = ANY(%s::text[]) ORDER BY event_id",
            (ids,),
        ).fetchall()
        mine = [r[0] for r in rows if r[1] == rls_db["tenant_a"]]
        theirs = [r[0] for r in rows if r[1] != rls_db["tenant_a"]]
        assert len(mine) == 2 and len(theirs) == 2
        try:
            conn.execute("DROP POLICY cancel_bridge_audit_read ON public.audit_events")
            # DDL takes no bind parameters, so the two ids are composed as quoted literals.
            from psycopg import sql

            conn.execute(
                sql.SQL(
                    "CREATE POLICY cancel_bridge_audit_read ON public.audit_events"
                    " FOR SELECT TO inv_cancel_bridge_owner USING (event_id IN ({}))"
                ).format(sql.SQL(", ").join(sql.Literal(i) for i in (mine[0], theirs[0])))
            )
            leaked = tool.collect(rls_db["owner"], tool.DEFAULT_ROLES, rls_db["tenant_a"])
        finally:
            conn.execute("DROP POLICY IF EXISTS cancel_bridge_audit_read ON public.audit_events")
            conn.execute(canonical)

    bridge = leaked["roles"]["inv_cancel_bridge_owner"]["tables"]["public.audit_events"]
    identity = bridge["visible"]["identity"]
    assert identity["method"] == "owner-verified-key"
    assert identity["match"] is False, "a swapped row set must not look like the owner's"
    assert identity["role_a"]["rows"] == identity["owner_a"]["rows"], (
        "this plant keeps the count equal on purpose -- only identity exposes it"
    )
    violations = tool.evaluate(leaked)
    e4 = [
        v for v in violations
        if v["rule"] == "E4" and v["role"] == "inv_cancel_bridge_owner"
        and v["table"] == "public.audit_events"
    ]
    assert e4, violations
    assert tool.verdict(violations, tool.unverified_identities(leaked)) == "VIOLATIONS"

    # And the canonical policy is back: the same measurement passes again.
    try:
        restored = tool.collect(rls_db["owner"], tool.DEFAULT_ROLES, rls_db["tenant_a"])
    finally:
        drop_audit_rows(rls_db["owner"], ids)
    restored_identity = (
        restored["roles"]["inv_cancel_bridge_owner"]["tables"]["public.audit_events"]["visible"]
    )
    assert restored_identity["identity"]["match"] is True
    assert [
        v for v in tool.evaluate(restored)
        if (v.get("role"), v.get("table")) == ("inv_cancel_bridge_owner", "public.audit_events")
    ] == []


@pytest.mark.postgres
def test_real_pg_cli_exit_codes(rls_db, tmp_path):
    env = {**os.environ, "INV_AUDIT_DSN": rls_db["owner"], "PYTHONUTF8": "1"}
    result = subprocess.run([sys.executable, str(ROOT / "tools/collect_rls_evidence.py"), "--out-dir", str(tmp_path),
                             "--label", "cli", "--roles", "inv_app,inv_kernel"], cwd=ROOT, env=env,
                            capture_output=True, text=True)
    # exit 0 since 0047 closed the audit_events gap; the CLI still writes both files
    assert result.returncode == 0, result.stdout[-500:]
    assert result.stdout.startswith("PASS: roles=2") and "unmeasured=" in result.stdout
    assert "audit_events" not in result.stdout
    assert (tmp_path / "cli.json").exists() and (tmp_path / "cli.md").exists()
    assert rls_db["owner"] not in (tmp_path / "cli.json").read_text(encoding="utf-8")
    bad = subprocess.run([sys.executable, str(ROOT / "tools/collect_rls_evidence.py"), "--dsn",
                          "postgresql://nobody:nothing@127.0.0.1:1/none?connect_timeout=2", "--out-dir", str(tmp_path)],
                         cwd=ROOT, capture_output=True, text=True)
    assert bad.returncode == 2 and "nothing" not in bad.stderr
