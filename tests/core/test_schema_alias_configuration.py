"""Every aliased response model stays buildable by its Python field name.

This file exists because of a merge, not because of a feature.

``Strict`` gives every model ``extra="forbid"`` but **not**
``populate_by_name``. Models that declare wire aliases therefore add
``model_config = ConfigDict(extra="forbid", populate_by_name=True)`` after their
fields. That line is the *last* line of the class body, and two independent
merges have now silently moved it to a class that was inserted immediately
after: git sees an identical trailing line in both parents, treats it as common
context, and keeps one copy -- which then belongs to the new class.

Nothing caught it. The file still parses, the line count is unchanged, the class
names are a clean union, and the only product caller builds the model by alias.
So the checks that a reviewer naturally reaches for -- class-name sets, line
survival, "does the suite pass" -- are all blind to it by construction.

What is not blind to it is asking every model the question directly.
"""

from __future__ import annotations

import pytest

from saintvision.api import schemas

#: Aliased models that legitimately do not accept field-name population.
#: This is a ratchet: a name may leave, but a new name may not appear without a
#: reviewer deciding that the model really is alias-only.
PRE_EXISTING_EXEMPTIONS = frozenset({"ReplicaObservationResponse"})


def _strict_models() -> list[type[schemas.Strict]]:
    return [
        value
        for value in vars(schemas).values()
        if isinstance(value, type)
        and issubclass(value, schemas.Strict)
        and value is not schemas.Strict
    ]


def _aliased_models() -> list[type[schemas.Strict]]:
    return [
        model
        for model in _strict_models()
        if any(field.alias for field in model.model_fields.values())
    ]


def test_every_aliased_model_can_be_populated_by_field_name():
    """The invariant itself, stated over every model rather than a sample."""
    offenders = sorted(
        model.__name__
        for model in _aliased_models()
        if not model.model_config.get("populate_by_name")
        and model.__name__ not in PRE_EXISTING_EXEMPTIONS
    )
    assert offenders == [], (
        "these aliased models lost populate_by_name -- most likely a merge "
        "attached their trailing model_config to a class inserted after them: "
        f"{offenders}"
    )


def test_the_exemption_list_is_not_stale():
    """An exemption that no longer applies must be deleted, not carried."""
    aliased = {model.__name__ for model in _aliased_models()}
    unknown = sorted(PRE_EXISTING_EXEMPTIONS - aliased)
    assert unknown == [], f"exempted names that are no longer aliased models: {unknown}"
    still_needed = sorted(
        name
        for name in PRE_EXISTING_EXEMPTIONS
        if getattr(schemas, name).model_config.get("populate_by_name")
    )
    assert still_needed == [], (
        f"these names now accept field-name population; drop the exemption: {still_needed}"
    )


@pytest.mark.parametrize(
    "name",
    ["LineageDatasetVersion", "ModelVersionByDatasetDigestPageResponse"],
)
def test_the_two_classes_this_merge_dropped_keep_their_configuration(name):
    """Named regression for the exact loss Codex found in merge ``54fc69bc``.

    Deleting either restored ``model_config`` line fails this test, which is the
    point: the general ratchet above would also fail, but a reader looking at
    the merge wants to see the two classes by name.
    """
    model = getattr(schemas, name)
    assert model.model_config.get("populate_by_name") is True
    assert model.model_config.get("extra") == "forbid"


def test_lineage_dataset_version_builds_by_field_name_and_by_alias():
    by_alias = schemas.LineageDatasetVersion(
        datasetVersionId="dsv_1",
        version="1",
        content_sha256="0" * 64,
        uri="inv://dataset/x@1",
    )
    by_field_name = schemas.LineageDatasetVersion(
        dataset_version_id="dsv_1",
        version="1",
        content_sha256="0" * 64,
        uri="inv://dataset/x@1",
    )
    assert by_field_name == by_alias
    with pytest.raises(ValueError):
        schemas.LineageDatasetVersion(
            datasetVersionId="dsv_1",
            version="1",
            content_sha256="0" * 64,
            uri="inv://dataset/x@1",
            unexpected="x",
        )


def test_digest_page_response_builds_by_field_name_and_by_alias():
    common = {
        "items": [],
        "truncated": {},
        "complete": True,
    }
    by_alias = schemas.ModelVersionByDatasetDigestPageResponse(
        contentSha256="0" * 64,
        datasetVersionIds=["dsv_1"],
        nextCursor=None,
        unresolvedModelVersions=0,
        **common,
    )
    by_field_name = schemas.ModelVersionByDatasetDigestPageResponse(
        content_sha256="0" * 64,
        dataset_version_ids=["dsv_1"],
        next_cursor=None,
        unresolved_model_versions=0,
        **common,
    )
    assert by_field_name == by_alias
    with pytest.raises(ValueError):
        schemas.ModelVersionByDatasetDigestPageResponse(
            contentSha256="0" * 64,
            datasetVersionIds=["dsv_1"],
            nextCursor=None,
            unresolvedModelVersions=0,
            unexpected="x",
            **common,
        )


def test_the_conformance_models_added_by_this_branch_keep_their_own_configuration():
    """The two new classes are not the ones to fix by deleting their config."""
    for model in (schemas.ConformanceCheckDescriptor, schemas.ConformanceStatusResponse):
        assert model.model_config.get("populate_by_name") is True
        assert model.model_config.get("extra") == "forbid"


# ---------------------------------------------------------------------------
# From the #205 side of this merge. Both branches added this file with the same
# general ratchet above but different named regressions, and the two sets do not
# overlap: #205 pinned the classes its own merge had combined, #200 pinned the two
# whose configuration git's auto-merge moved. Keeping only one set would drop a
# guarantee that a merge had already been needed to establish once.
# ---------------------------------------------------------------------------


def _aliased(model) -> list[str]:
    return [field for field, info in model.model_fields.items() if info.alias]


@pytest.mark.parametrize(
    "name",
    [
        # The two classes #191 contributed to this file, and the one this branch
        # did. The merge had to keep all three, bodies included.
        "ModelVersionRegisterRequest",
        "ModelVersionResponse",
        "AdapterReadinessResponse",
    ],
)
def test_the_classes_the_merge_combined_kept_their_configuration(name):
    model = getattr(schemas, name)
    assert model.model_config.get("extra") == "forbid"
    assert model.model_config.get("populate_by_name") is True, (
        f"{name} lost populate_by_name; a merge boundary can fall before the "
        "model_config line"
    )
    assert _aliased(model), f"{name} is in this list because it has aliases"


def test_the_response_can_be_built_by_field_name_and_by_alias():
    """The property the lost line actually provided, exercised both ways."""
    import datetime as dt

    values = {
        "version_id": "mdv_01J8Z3XQ2K9WMV5T7N4B6C8D0E",
        "parent_model_id": "mdl_01J8Z3XQ2K9WMV5T7N4B6C8D0E",
        "version": "1.4.0",
        "stage": "draft",
        "content_sha256": "a" * 64,
        "byte_size": 4096,
        "uri": "inv://models/demo@1.4.0",
        "created_at": dt.datetime(2026, 9, 28, tzinfo=dt.timezone.utc),
    }
    by_field = schemas.ModelVersionResponse(**values)
    dumped = by_field.model_dump(by_alias=True, mode="json")
    by_alias = schemas.ModelVersionResponse(**dumped)
    assert by_alias.model_dump(by_alias=True, mode="json") == dumped
    # The wire names are the aliases either way round.
    assert set(dumped) == {
        "modelVersionId",
        "modelId",
        "version",
        "stage",
        "contentSha256",
        "byteSize",
        "uri",
        "createdAt",
    }
