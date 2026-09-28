"""Every aliased response model keeps ``populate_by_name``, and the merge kept it.

This file exists because a merge lost one line. Resolving #191 into this branch put
both lanes' classes into ``api/schemas.py``, and the class-name set came out as the
union -- but ``ModelVersionResponse`` lost its trailing

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

because the conflict block's boundary fell just before it. Nothing caught it: the
route constructs that response with the **alias** keywords, so serialisation was
unaffected and hosted CI stayed green. What was lost is the ability to build or
validate the model by its **field** names -- which every test and every caller that
uses the Python names relies on.

So the guard here is not "these three classes look right". It is the invariant whose
breach was invisible: a ``Strict`` model that declares any ``Field(alias=...)`` and
does **not** set ``populate_by_name=True`` can only be populated one way, and a
future merge that drops the line again fails here rather than in whatever reads it
next.
"""

from __future__ import annotations

import pytest

from saintvision.api import schemas

#: Known to breach the invariant before this file existed, and out of this card's
#: scope. Pinned rather than tolerated: the test below fails if the entry stops
#: breaching, so a fix removes it here instead of leaving a stale exemption.
PRE_EXISTING_EXEMPTIONS = frozenset({"ReplicaObservationResponse"})


def _strict_models():
    for name in dir(schemas):
        candidate = getattr(schemas, name)
        if (
            isinstance(candidate, type)
            and issubclass(candidate, schemas.Strict)
            and candidate is not schemas.Strict
        ):
            yield name, candidate


def _aliased(model) -> list[str]:
    return [field for field, info in model.model_fields.items() if info.alias]


def test_every_aliased_strict_model_can_be_populated_by_field_name():
    breaching = {
        name
        for name, model in _strict_models()
        if _aliased(model) and not model.model_config.get("populate_by_name")
    }
    assert breaching <= PRE_EXISTING_EXEMPTIONS, sorted(breaching - PRE_EXISTING_EXEMPTIONS)


def test_the_exemption_list_is_not_stale():
    """A fixed model must be removed from the list, not left in it.

    An exemption that no longer applies reads as permission for the next one.
    """
    breaching = {
        name
        for name, model in _strict_models()
        if _aliased(model) and not model.model_config.get("populate_by_name")
    }
    assert PRE_EXISTING_EXEMPTIONS <= breaching, sorted(PRE_EXISTING_EXEMPTIONS - breaching)


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
