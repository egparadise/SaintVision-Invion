"""Card 253: the project-scoped catalogue contract, its enum and its refusals.

PG-free. The real-PostgreSQL side (locks, idempotency, the revoke race and the
denial audit) is ``tests/integration/test_storage_project_scope_real_pg.py``.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest
from pydantic import ValidationError

from saintvision.api import schemas
from saintvision.api.problem import RES_NOT_FOUND, GRAPH_PRECONDITION, AUTH_PROJECT, SYS_UNMAPPED
from saintvision.api.v1 import storage_project
from saintvision.db.models.storage import LOCATION_KINDS
from saintvision.db.models import storage as storage_model
from saintvision.errors import (
    AUTH_PROJECT_SCOPE,
    GRAPH_IDEMPOTENCY_CONFLICT,
    RES_ARTIFACT_NOT_FOUND,
    RES_CONTRIBUTION_NOT_FOUND,
    RES_NODE_NOT_FOUND,
    VAL_PATH_UNSAFE,
    VAL_SCHEMA,
    InvError,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"


def contract(name: str) -> dict:
    return json.loads((CONTRACTS / f"{name}.schema.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- T1 ----------
def test_t1_the_three_generated_contracts_have_the_shape_the_design_fixed():
    request = contract("project-data-location-request")
    assert request["additionalProperties"] is False
    assert request["required"] == ["contributionId", "kind", "relativePath", "byteSize"]
    # The project comes from the path. A body field would let a caller name a
    # project the server never judged, so there is none to send.
    assert "projectId" not in request["properties"]

    response = contract("project-data-location-response")
    base = contract("data-location-response")
    assert response["additionalProperties"] is False
    assert set(response["required"]) == set(base["required"]) | {"projectId"}
    assert set(response["properties"]) == set(base["properties"]) | {"projectId"}

    page = contract("project-data-location-page-response")
    assert page["additionalProperties"] is False
    assert set(page["required"]) == {"items", "nextCursor"}


def test_t1_the_request_body_cannot_smuggle_a_project():
    with pytest.raises(ValidationError):
        schemas.ProjectDataLocationRequest(
            contributionId="stc_x", kind="workspace", relativePath="a", byteSize=0,
            workspaceId="wsp_01ARZ3NDEKTSV4RRFFQ69G5FAV", projectId="prj_other",
        )


# ---------------------------------------------------------------- T2 ----------
def test_t2_the_kind_enum_is_the_same_set_in_the_contract_the_model_and_the_check():
    """Three places say which kinds exist; a drift in any of them fails here."""
    from_contract = set(contract("project-data-location-request")["properties"]["kind"]["enum"])
    from_constant = set(LOCATION_KINDS)
    source = pathlib.Path(storage_model.__file__).read_text(encoding="utf-8")
    match = re.search(r"kind IN \(([^)]+)\)", source)
    from_check = {value.strip().strip("'") for value in match.group(1).split(",")}
    assert from_contract == from_constant == from_check
    assert from_contract == {"artifact", "dataset", "model", "workspace"}


# --------------------------------------------------------------- T17 ----------
@pytest.mark.parametrize(
    "payload",
    [
        # dataset and model are addressed by name@version, so an artifact or a
        # workspace identifier cannot belong to them.
        {"kind": "dataset", "name": "d", "version": "1", "runId": "run_1"},
        {"kind": "model", "name": "m", "version": "1", "workspaceId": "wsp_1"},
        {"kind": "dataset", "name": "d"},
        {"kind": "model", "version": "1"},
        # artifacts are addressed by run and artifact id.
        {"kind": "artifact", "runId": "run_1"},
        {"kind": "artifact", "runId": "run_1", "artifactId": "art_1", "name": "n"},
        # a workspace by its own id.
        {"kind": "workspace", "name": "n", "version": "1"},
    ],
)
def test_t17_the_identifiers_a_kind_may_carry_are_fixed(payload):
    with pytest.raises(ValidationError):
        schemas.ProjectDataLocationRequest(
            contributionId="stc_x", relativePath="a/b.bin", byteSize=1, **payload
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "dataset", "name": "d", "version": "1"},
        {"kind": "model", "name": "m", "version": "2"},
        {"kind": "artifact", "runId": "run_1", "artifactId": "art_1"},
        {"kind": "workspace", "workspaceId": "wsp_1"},
    ],
)
def test_t17_each_kind_accepts_exactly_its_own_identifiers(payload):
    request = schemas.ProjectDataLocationRequest(
        contributionId="stc_x", relativePath="a/b.bin", byteSize=1, **payload
    )
    assert request.kind == payload["kind"]


def test_t17_the_oneof_branches_say_the_same_thing_as_the_validator():
    """The schema and the check read one table, so they cannot disagree."""
    branches = {branch["properties"]["kind"]["const"]: branch for branch in
                contract("project-data-location-request")["oneOf"]}
    assert set(branches) == set(schemas.LOCATION_IDENTITY_RULES)
    for kind, (required, forbidden) in schemas.LOCATION_IDENTITY_RULES.items():
        branch = branches[kind]
        assert set(branch["required"]) == {"kind", *required}
        assert {name for name, rule in branch["properties"].items() if rule == {"not": {}}} == set(forbidden)


# --------------------------------------------------------------- T19 ----------
def test_t19_the_translation_table_covers_every_code_this_route_can_raise():
    """An uncovered code becomes SYS-0002 500, which tells the caller nothing."""
    reachable = {
        VAL_SCHEMA,            # inactive contribution, unbuildable URI, bad URI
        VAL_PATH_UNSAFE,       # relative path refused by pathsafe
        AUTH_PROJECT_SCOPE,    # membership, archived project, suspended user
        GRAPH_IDEMPOTENCY_CONFLICT,
        RES_CONTRIBUTION_NOT_FOUND,
        RES_ARTIFACT_NOT_FOUND,
        RES_NODE_NOT_FOUND,
    }
    assert reachable <= set(storage_project.TRANSLATION)
    assert storage_project.TRANSLATION[GRAPH_IDEMPOTENCY_CONFLICT] == (GRAPH_PRECONDITION, 409, False)
    assert storage_project.TRANSLATION[AUTH_PROJECT_SCOPE] == (AUTH_PROJECT, 403, False)
    assert storage_project.TRANSLATION[RES_CONTRIBUTION_NOT_FOUND] == (RES_NOT_FOUND, 404, False)
    assert SYS_UNMAPPED not in {code for code, _status, _retry in storage_project.TRANSLATION.values()}


# --------------------------------------------------------------- T12 ----------
def test_t12_absence_is_one_canonical_body_and_it_is_audited():
    """The internal code is not canonical, and must not be: it would be an oracle."""
    missing = storage_project._absent(InvError(RES_CONTRIBUTION_NOT_FOUND, "storage contribution not found"))
    not_owned = storage_project._absent(InvError(RES_CONTRIBUTION_NOT_FOUND, "someone else's folder"))
    for problem in (missing, not_owned):
        assert (problem.code, problem.status, problem.retryable) == (RES_NOT_FOUND, 404, False)
        assert problem.detail == "No such resource."
        assert problem.audit_action == storage_project.AUDIT_ACTION
    # Byte for byte the same refusal: nothing in it says which cause it was.
    assert (missing.code, missing.status, missing.detail) == (not_owned.code, not_owned.status, not_owned.detail)


# --------------------------------------------------------------- T11 ----------
def test_t11_the_bounded_action_and_endpoint_carry_no_identifier():
    for value in (storage_project.ENDPOINT, storage_project.AUDIT_ACTION):
        assert "{project_id}" in value
        assert not re.search(r"(prj|stc|usr|run)_[0-9A-HJKMNP-TV-Z]{26}", value)


def test_t11_the_kernel_has_no_catalogue_route():
    """The surface lives in the app that records denials (card 250 §3-0)."""
    kernel = (ROOT / "services/control-plane/src/inv/app.py").read_text(encoding="utf-8")
    assert "storage/locations" not in kernel


# ----------------------------------------------------------- 0062 shape -------
def test_the_migration_adds_a_column_and_leaves_every_policy_alone():
    """Phase 1 is reversible because it never touches a policy (card 250 §3-4-1)."""
    source = (ROOT / "migrations/versions/0062_data_location_project_scope.py").read_text(encoding="utf-8")
    # 0062 sits directly on 0061 (#343): two revisions with the same parent would
    # be two migration heads, which alembic refuses to upgrade.
    assert 'down_revision = "0061_build_preparations"' in source
    for forbidden in ("CREATE POLICY", "DROP POLICY", "ENABLE ROW LEVEL", "FORCE ROW LEVEL", "GRANT "):
        assert forbidden not in source, forbidden
    upgrade, downgrade = source.split("def downgrade()")
    assert "add_column" in upgrade and "create_foreign_key" in upgrade
    assert "drop_column" in downgrade and "drop_constraint" in downgrade
    # The drop is guarded: bound rows refuse it before any DDL (0053's rule).
    assert "RuntimeError" in downgrade and "reviewed data fix" in downgrade
    assert downgrade.index("RuntimeError") < downgrade.index("drop_index")
