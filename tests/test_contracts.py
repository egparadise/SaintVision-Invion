"""ID, error and pagination contracts.

These are the shapes every other component depends on, so they are pinned here
rather than asserted incidentally inside API tests.
"""

from __future__ import annotations

import uuid

import pytest

from saintvision import errors
from saintvision.errors import ErrorCategory, InvError, category_of
from saintvision.ids import (
    is_id,
    is_span_id,
    is_trace_id,
    new_id,
    new_span_id,
    new_tenant_id,
    new_trace_id,
    new_ulid,
    parse_id,
    ulid_timestamp_ms,
)
from saintvision.services.pagination import build_page, clamp_limit, validate_cursor


class _Row:
    def __init__(self, node_id: str) -> None:
        self.node_id = node_id


def test_id_is_prefix_and_ulid():
    value = new_id("node")
    prefix, ulid = parse_id(value)
    assert prefix == "nod"
    assert len(ulid) == 26
    assert is_id(value, "node")
    assert not is_id(value, "user")


def test_id_column_width_matches_the_schema():
    # db.base pins InvId to CHAR(30); a longer prefix would silently truncate.
    for kind in ("node", "user", "project", "data_location", "idempotency"):
        assert len(new_id(kind)) == 30


def test_unknown_entity_kind_is_refused():
    with pytest.raises(ValueError):
        new_id("dragon")


@pytest.mark.parametrize(
    "value",
    ["", "nod", "nod_", "nodx_01ARZ3NDEKTSV4RRFFQ69G5FAV", "nod_short", "NOD_01ARZ3NDEKTSV4RRFFQ69G5FAV"],
)
def test_malformed_ids_are_rejected(value):
    assert not is_id(value)


def test_ulids_sort_by_creation_time():
    # Cursor pagination orders on the ID, so this property is load-bearing.
    earlier = new_ulid(now_ms=1_700_000_000_000)
    later = new_ulid(now_ms=1_700_000_001_000)
    assert earlier < later
    assert ulid_timestamp_ms(earlier) == 1_700_000_000_000


def test_ulid_body_uses_crockford_alphabet_only():
    # I, L, O and U are excluded so a transcribed ID cannot be misread.
    body = new_ulid()
    assert not (set(body) & set("ILOU"))


def test_trace_and_span_ids_are_hex_and_never_zero():
    trace = new_trace_id()
    span = new_span_id()
    assert is_trace_id(trace) and trace != "0" * 32
    assert is_span_id(span) and span != "0" * 16
    assert not is_trace_id(trace.upper())


def test_tenant_id_is_a_uuid():
    assert isinstance(new_tenant_id(), uuid.UUID)


@pytest.mark.parametrize(
    "code,category",
    [
        (errors.VAL_SCHEMA, ErrorCategory.VALIDATION),
        (errors.AUTH_BOOTSTRAP_TOKEN_CONSUMED, ErrorCategory.AUTH),
        (errors.RES_NODE_NOT_FOUND, ErrorCategory.RESOURCE),
        (errors.SEC_TENANT_SCOPE_UNSET, ErrorCategory.SECURITY),
        (errors.GRAPH_IDEMPOTENCY_CONFLICT, ErrorCategory.GRAPH),
    ],
)
def test_category_is_derived_from_the_code(code, category):
    assert category_of(code) == category
    assert InvError(code, "x").category == category


def test_unknown_code_family_is_refused():
    with pytest.raises(ValueError):
        InvError("WAT-SOMETHING", "x")


def test_problem_carries_every_required_field():
    trace = new_trace_id()
    problem = InvError(
        errors.RES_HEARTBEAT_STALE, "stale", cause_ref="nod_x", evidence_id="evd_y"
    ).to_problem(trace_id=trace, instance="/v1/nodes")
    for field in ("type", "title", "status", "code", "category", "retryable", "traceId"):
        assert field in problem, field
    assert problem["causeRef"] == "nod_x"
    assert problem["evidenceId"] == "evd_y"
    assert problem["traceId"] == trace
    assert problem["instance"] == "/v1/nodes"


def test_internal_message_is_withheld_when_not_public():
    problem = InvError(
        errors.AUTH_INVALID_CREDENTIAL, "token abc123 rejected", public=False
    ).to_problem(trace_id=new_trace_id())
    assert "detail" not in problem
    assert "abc123" not in repr(problem)


def test_retryability_follows_the_category_table():
    assert InvError("NET-TIMEOUT", "x").retryable
    assert not InvError(errors.VAL_SCHEMA, "x").retryable
    assert not InvError(errors.SEC_TENANT_SCOPE_UNSET, "x").retryable
    assert InvError(errors.RES_NODE_NOT_FOUND, "x").retryable


def test_limit_defaults_and_clamps():
    assert clamp_limit(None) == 50
    assert clamp_limit(10) == 10
    assert clamp_limit(1000) == 200
    assert clamp_limit(1000, maximum=25) == 25


def test_limit_below_one_is_rejected():
    with pytest.raises(InvError):
        clamp_limit(0)


def test_cursor_must_be_an_identifier():
    assert validate_cursor(None) is None
    good = new_id("node")
    assert validate_cursor(good) == good
    with pytest.raises(InvError):
        validate_cursor("'; DROP TABLE nodes; --")


def test_page_reports_a_cursor_only_when_more_rows_exist():
    rows = [_Row(new_id("node")) for _ in range(4)]
    rows.sort(key=lambda r: r.node_id)

    exact = build_page(rows[:3], limit=3, id_attr="node_id")
    assert exact.next_cursor is None
    assert len(exact.items) == 3

    more = build_page(rows, limit=3, id_attr="node_id")
    assert len(more.items) == 3
    assert more.next_cursor == more.items[-1].node_id
