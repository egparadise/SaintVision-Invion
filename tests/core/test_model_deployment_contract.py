"""Card 261: the deployment surface's contract, order and refusals (PG-free).

What a real database must say -- the two row locks, the approval's project chain,
the re-check between locking and writing, the ledger's binding -- is
``tests/integration/test_model_deployment_real_pg.py``. This file holds the parts
that are true of the code itself.
"""

from __future__ import annotations

import inspect
import json
import pathlib
from typing import get_args

import pytest
from pydantic import ValidationError

from saintvision.api import schemas
from saintvision.api.problem import (
    AUTH_PROJECT,
    GRAPH_PRECONDITION,
    RES_NOT_FOUND,
    SYS_UNMAPPED,
)
from saintvision.api.v1 import model_deployments, model_versions
from saintvision.errors import (
    AUTH_APPROVAL_DIGEST_MISMATCH,
    AUTH_PROJECT_SCOPE,
    GRAPH_IDEMPOTENCY_CONFLICT,
    RES_ARTIFACT_NOT_FOUND,
    VAL_SCHEMA,
)
from saintvision.services import lineage as lineage_service

ROOT = pathlib.Path(__file__).resolve().parents[2]


def contract(name: str) -> dict:
    return json.loads((ROOT / "contracts" / f"{name}.schema.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ contracts --
def test_the_request_carries_two_fields_and_the_absences_are_the_point():
    request = contract("model-deployment-request")
    assert request["additionalProperties"] is False
    assert set(request["required"]) == {"environment", "approvalId"}
    assert set(request["properties"]) == {"environment", "approvalId"}
    # The three a caller must not be able to say.
    for forbidden in ("deployedDigest", "imageId", "notes"):
        assert forbidden not in request["properties"], forbidden
    assert set(request["properties"]["environment"]["enum"]) == {"lab", "pilot", "staging"}


def test_the_response_returns_the_server_derived_digest():
    response = contract("model-deployment-response")
    assert response["additionalProperties"] is False
    assert "deployedDigest" in response["properties"]
    assert {"deploymentId", "modelVersionId", "environment", "status", "deployedDigest",
            "approvalId", "deployedAt"} <= set(response["required"])


@pytest.mark.parametrize(
    "payload",
    [
        {"environment": "lab", "approvalId": "apr_1", "deployedDigest": "a" * 64},
        {"environment": "lab", "approvalId": "apr_1", "imageId": "img_1"},
        {"environment": "lab", "approvalId": "apr_1", "notes": {}},
        {"environment": "prod", "approvalId": "apr_1"},
        {"environment": "lab"},
        {"approvalId": "apr_1"},
    ],
)
def test_the_request_refuses_what_the_server_will_not_take_from_a_caller(payload):
    with pytest.raises(ValidationError):
        schemas.ModelDeploymentRequest(**payload)


# ----------------------------------------------------------- the asserted kinds
def test_a_caller_may_assert_only_the_kinds_whose_project_can_be_proven():
    """Three of the service's five. ``code_commit`` and ``container_image`` carry no
    project anywhere in the schema, so the contract is where they stop."""
    register = contract("model-version-register-request")
    edge = register["$defs"]["ProvableLineageEdge"]
    assert edge["additionalProperties"] is False
    asserted = set(edge["properties"]["kind"]["enum"])
    # The field itself is nullable and bounded, and it points at that one shape.
    array = next(part for part in register["properties"]["lineage"]["anyOf"] if part.get("type") == "array")
    assert array["items"]["$ref"].endswith("/ProvableLineageEdge") and array["maxItems"] == 64
    assert asserted == {"approval", "dataset_version", "eval_run"}
    # And the live model, not only the generated file: widening the Literal without
    # regenerating would otherwise be caught by ``export_schemas --check`` alone.
    assert set(get_args(schemas.ProvableLineageKind)) == asserted
    assert asserted < set(lineage_service.SUBJECT_TABLES)
    assert set(lineage_service.SUBJECT_TABLES) - asserted == {"code_commit", "container_image"}


def test_every_kind_the_service_knows_has_a_subject_table_and_an_id_column():
    from saintvision.db.base import Base

    for kind, (entity, column) in lineage_service.SUBJECT_TABLES.items():
        assert hasattr(entity, column), kind
        assert hasattr(entity, "tenant_id"), kind
        assert entity.__tablename__ in Base.metadata.tables, kind


# --------------------------------------------------------------- the write order
def test_the_write_order_is_the_contract_card_250_fixed():
    """Six steps, and the order is what makes them worth anything. A re-check that
    moves above the locks stops being a re-check."""
    source = inspect.getsource(model_deployments.record_model_deployment)
    steps = [
        "_require_idempotency_key(",
        "_authorised(",                  # [1]
        "serialise_idempotent_write(",
        "_authorised(",                  # [3] before the replay decision
        "replay_or_reserve(",
        "_version_in_project(",
        "locked_deployment_authority(",
        "_authorised(",                  # [6] before the write
        "apply_deployment(",
    ]
    index = 0
    for step in steps:
        index = source.index(step, index) + 1
    assert source.count("_authorised(") == 3
    # The audit and the ledger come after the write, inside the same transaction.
    assert source.index("apply_deployment(") < source.index("record_event(")
    assert source.index("record_event(") < source.index("store_idempotent_response(")


def test_the_ledger_body_carries_the_paths_model_and_version():
    """Without it the same key on another version replays the first one's answer."""
    source = inspect.getsource(model_deployments.record_model_deployment)
    assert '"modelId": model_id' in source and '"version": version' in source
    assert "payload=ledger_payload" in source


def test_the_bounded_action_and_endpoint_carry_no_identifier():
    """The ledger's endpoint is the template verbatim; the audit action cannot be,
    because the column is bounded at 64 and this template is 79. The fallback is
    ``METHOD <name>#<digest of the template>`` -- still no identifier in it."""
    from saintvision.api.audit_action import AUDIT_ACTION_LIMIT, long_template_action

    assert "{project_id}" in model_deployments.ENDPOINT
    assert "{model_id}" in model_deployments.ENDPOINT
    assert "{version}" in model_deployments.ENDPOINT
    assert len(model_deployments.ENDPOINT) > AUDIT_ACTION_LIMIT
    assert model_deployments.AUDIT_ACTION == long_template_action(
        "POST",
        "/v1/projects/{project_id}/models/{model_id}/versions/{version}/deployments",
        "record_model_deployment",
    )
    assert len(model_deployments.AUDIT_ACTION) <= AUDIT_ACTION_LIMIT
    import re

    assert not re.search(r"(prj|mdl|apr|usr)_[0-9A-HJKMNP-TV-Z]{26}", model_deployments.AUDIT_ACTION)


def test_the_grade_is_canApprove_and_it_is_read_not_inferred():
    source = inspect.getsource(model_deployments._authorised)
    # Read the code, not the prose: the docstring names the other grade to explain
    # why it is not enough, and an assertion over the whole source would catch
    # that explanation rather than a decision.
    code = [
        line for line in source.splitlines()
        if line.strip().startswith(("if ", "raise", "permission", "return", "project_service"))
        or "permission.get(" in line
    ]
    assert any('permission.get("canApprove")' in line for line in code)
    assert not any("canRequest" in line for line in code)


# ------------------------------------------------------------- the refusal table
def test_the_translation_table_covers_every_code_this_route_can_raise():
    reachable = {
        AUTH_APPROVAL_DIGEST_MISMATCH,   # six approval failures, one answer
        VAL_SCHEMA,                      # unknown environment, unreleased stage
        AUTH_PROJECT_SCOPE,
        GRAPH_IDEMPOTENCY_CONFLICT,
        RES_ARTIFACT_NOT_FOUND,
    }
    assert reachable <= set(model_deployments.TRANSLATION)
    assert SYS_UNMAPPED not in {code for code, _s, _r in model_deployments.TRANSLATION.values()}


def test_the_six_approval_failures_share_one_public_code():
    """An approval id must not become an existence oracle: absent, foreign-tenant,
    foreign-project, not-approved, expired and digest-mismatch are one answer."""
    assert model_deployments.TRANSLATION[AUTH_APPROVAL_DIGEST_MISMATCH] == (
        GRAPH_PRECONDITION, 409, False
    )
    source = inspect.getsource(lineage_service.locked_deployment_authority)
    # Five raise sites, one per approval failure the function can see; the sixth
    # (another tenant's) is the same site as "absent", by construction of the query.
    raises = [
        line for line in source.splitlines()
        if "AUTH_APPROVAL_DIGEST_MISMATCH" in line and not line.strip().startswith("#")
        and "``" not in line
    ]
    assert len(raises) == 5, raises
    assert "approval_project(" in source


def test_the_project_scope_refusal_is_a_403_and_absence_is_a_404():
    assert model_deployments.TRANSLATION[AUTH_PROJECT_SCOPE] == (AUTH_PROJECT, 403, False)
    assert model_deployments.TRANSLATION[RES_ARTIFACT_NOT_FOUND] == (RES_NOT_FOUND, 404, False)


# ------------------------------------------------------------- the service split
def test_the_authority_step_writes_nothing_and_the_apply_step_validates_nothing():
    """The split is what makes a re-check before the insert possible at all."""
    authority = inspect.getsource(lineage_service.locked_deployment_authority)
    apply_step = inspect.getsource(lineage_service.apply_deployment)
    for writing in ("session.add(", "update(Deployment)", "enqueue_mirror("):
        assert writing not in authority, writing
    assert "with_for_update()" in authority and "with_for_update(read=True)" in authority
    for judging in ("AUTH_APPROVAL_DIGEST_MISMATCH", "approval.decision", "subject_sha256"):
        assert judging not in apply_step, judging
    assert "session.add(" in apply_step and "update(Deployment)" in apply_step


def test_the_legacy_entry_point_still_exists_for_its_existing_callers():
    signature = inspect.signature(lineage_service.record_deployment)
    assert {"tenant_id", "model_version_id", "environment", "approval_id",
            "deployed_by_user_id", "now"} <= set(signature.parameters)
    assert signature.parameters["project_id"].default is None


# ------------------------------------------------------------------ 0064 shape --
def test_the_migration_adds_one_key_and_measures_before_it():
    source = (ROOT / "migrations/versions/0064_model_version_run_fk.py").read_text(encoding="utf-8")
    assert 'revision = "0064_model_version_run_fk"' in source
    assert len("0064_model_version_run_fk") <= 32          # alembic_version is varchar(32)
    assert 'down_revision = "0063_build_policy_budgets"' in source
    assert "add_column" not in source and "drop_column" not in source
    for forbidden in ("CREATE POLICY", "DROP POLICY", "ENABLE ROW LEVEL", "GRANT "):
        assert forbidden not in source, forbidden
    upgrade, downgrade = source.split("def downgrade()")
    # The measurement comes before the key, and it refuses instead of repairing.
    assert upgrade.index("DANGLING") < upgrade.index("create_foreign_key")
    assert "RuntimeError" in upgrade and "reviewed data fix" in upgrade
    assert "UPDATE" not in upgrade and "DELETE" not in upgrade
    # The downgrade drops the key only, so it has nothing to guard.
    assert "drop_constraint" in downgrade and "RuntimeError" not in downgrade


def test_the_dangling_query_pairs_tenant_and_run():
    """A value naming another tenant's run must also come out as dangling."""
    from importlib import util

    spec = util.spec_from_file_location(
        "m0064", ROOT / "migrations/versions/0064_model_version_run_fk.py"
    )
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    query = " ".join(module.DANGLING.split())
    assert "r.tenant_id = mv.tenant_id AND r.run_id = mv.produced_by_run_id" in query
    assert "IS NOT NULL" in query and "r.run_id IS NULL" in query and "LIMIT 10" in query
