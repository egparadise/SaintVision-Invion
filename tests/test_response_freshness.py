"""The freshness inventory must detect a removed expected timestamp field."""

import json
import pytest

from tools import check_response_freshness


def test_curated_freshness_fields_exist_in_contracts():
    present, missing = check_response_freshness.check()
    assert len(present) == 11
    assert not missing


@pytest.mark.parametrize("response,field", [
    ("ShardObservation", "stateAsOf"),
    ("ProjectNodeCertificateObservationResponse", "observedAt"),
])
def test_removing_expected_truth_time_from_schema_is_reported(tmp_path, monkeypatch, response, field):
    schema = json.loads(check_response_freshness.CORE.read_text(encoding="utf-8"))
    del schema["$defs"][response]["properties"][field]
    changed = tmp_path / "core.schema.json"
    changed.write_text(json.dumps(schema), encoding="utf-8")
    monkeypatch.setattr(check_response_freshness, "CORE", changed)

    present, missing = check_response_freshness.check()
    assert f"kernel:{response}.{field}" in missing
    assert len(present) == 10 and len(missing) == 1
