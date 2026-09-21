"""The freshness inventory must detect a removed expected timestamp field."""

import json

from tools import check_response_freshness


def test_curated_freshness_fields_exist_in_contracts():
    present, missing = check_response_freshness.check()
    assert len(present) == 9
    assert not missing


def test_removing_shard_as_of_from_schema_is_reported(tmp_path, monkeypatch):
    schema = json.loads(check_response_freshness.CORE.read_text(encoding="utf-8"))
    del schema["$defs"]["ShardObservation"]["properties"]["stateAsOf"]
    changed = tmp_path / "core.schema.json"
    changed.write_text(json.dumps(schema), encoding="utf-8")
    monkeypatch.setattr(check_response_freshness, "CORE", changed)

    present, missing = check_response_freshness.check()
    assert "kernel:ShardObservation.stateAsOf" in missing
    assert len(present) == 8 and len(missing) == 1
