"""The rules that decide whether a SECURITY DEFINER function is safe.

These run without a database because each case here is a definition that the
previous version of the rule judged wrongly. A definer function bypasses row
level security, and this judgement now gates the restore drill's verdict, so a
rule that can only say "safe" would be worse than no rule at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from _definer_rules import (  # noqa: E402
    binds_tenant_scope,
    filters_tenant_from_argument,
    judge,
    search_path_of,
    temp_schema_misplaced,
)

BOUND = "SELECT v FROM inv.t WHERE tenant_id = current_setting('inv.tenant_id')::uuid"


def test_a_real_call_binds_the_scope() -> None:
    assert binds_tenant_scope(BOUND)


def test_a_comment_promising_the_binding_does_not_bind() -> None:
    body = (
        "-- must match current_setting('inv.tenant_id')\n"
        "SELECT v FROM inv.t WHERE tenant_id = p_tenant"
    )
    assert not binds_tenant_scope(body)


def test_a_block_comment_promising_the_binding_does_not_bind() -> None:
    body = (
        "/* bound to current_setting('inv.tenant_id') by the caller */ "
        "SELECT v FROM inv.t WHERE tenant_id = p_tenant"
    )
    assert not binds_tenant_scope(body)


def test_a_string_literal_quoting_the_binding_does_not_bind() -> None:
    body = "SELECT 'current_setting(''inv.tenant_id'')' FROM inv.t WHERE tenant_id = $1"
    assert not binds_tenant_scope(body)


def test_a_different_setting_is_not_the_tenant_binding() -> None:
    assert not binds_tenant_scope("SELECT current_setting('inv.project_id')")


def test_the_tenant_argument_need_not_be_called_tenant() -> None:
    body = "SELECT v FROM inv.t WHERE tenant_id = org"
    assert filters_tenant_from_argument(body, "org uuid")


def test_a_positional_parameter_counts_as_caller_supplied() -> None:
    assert filters_tenant_from_argument("SELECT v FROM inv.t WHERE tenant_id = $1", "")


def test_a_cast_between_column_and_parameter_still_counts() -> None:
    body = "SELECT v FROM inv.t WHERE tenant_id::text = p_org"
    assert filters_tenant_from_argument(body, "p_org text")


def test_a_tenant_id_mentioned_only_in_a_literal_is_not_a_filter() -> None:
    body = "SELECT 'tenant_id = org' FROM inv.t"
    assert not filters_tenant_from_argument(body, "org uuid")


def test_search_path_values_may_contain_spaces() -> None:
    # proconfig is an array; joining it and splitting on whitespace read this
    # as "pg_temp," and dropped the rest, hiding the ordering below.
    assert search_path_of(["search_path=pg_temp, inv"]) == "pg_temp, inv"


def test_search_path_is_none_when_unpinned() -> None:
    assert search_path_of([]) is None
    assert search_path_of(None) is None


def test_pg_temp_before_the_functions_own_schemas_is_a_finding() -> None:
    assert temp_schema_misplaced("pg_temp, inv")
    assert not temp_schema_misplaced("inv, pg_temp")
    assert not temp_schema_misplaced("inv, public")


def test_a_correct_function_is_judged_safe() -> None:
    verdict = judge(
        BOUND + " AND tenant_id = p_tenant",
        "p_tenant uuid",
        ["search_path=inv, pg_temp"],
    )
    assert verdict["bindsTenant"]
    assert verdict["pinsSearchPath"]
    assert not verdict["tempSchemaMisplaced"]


def test_the_2024_leak_shape_is_judged_unsafe() -> None:
    # What 0024's project_kernel_link did: take a tenant id and trust it.
    verdict = judge(
        "SELECT p.project_id FROM public.projects p WHERE p.tenant_id = p_tenant",
        "p_tenant uuid, p_project text",
        ["search_path=public, pg_temp"],
    )
    assert verdict["takesTenant"]
    assert not verdict["bindsTenant"]
