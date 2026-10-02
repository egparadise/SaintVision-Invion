"""Fail-closed guards for Card 194's target/Evidence resolver."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from saintvision.db.models import APPEND_ONLY_TABLES, TENANT_SCOPED_TABLES
from saintvision.services import release_acceptance as acceptance
from saintvision.services import release_acceptance_resolver as resolver

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations/versions/0058_release_acceptance_resolver.py"
DEFINER_POLICY = ROOT / "tools/definer-policy.json"
UTC = dt.timezone.utc


def test_checked_in_registry_is_exactly_pinned_and_nonempty():
    loaded = resolver.load_target_registry()
    assert loaded.git_blob_sha == resolver.REGISTRY_GIT_BLOB_SHA
    assert loaded.file_sha256 == resolver.REGISTRY_FILE_SHA256
    assert loaded.document.registry_version == 1
    assert len(loaded.document.targets) == 1
    assert loaded.document.targets[0].acceptance_id_ref == "AC-12"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda raw: b"",
        lambda raw: raw.replace(b'"targets": [', b'"targets": []'),
        lambda raw: raw.replace(b'"registryVersion": 1', b'"registryVersion": 2'),
        lambda raw: raw + b"\n",
    ],
)
def test_registry_absence_empty_version_or_byte_drift_is_a_prerequisite_failure(tmp_path, mutate):
    target = tmp_path / "registry.json"
    target.write_bytes(mutate(resolver.REGISTRY_PATH.read_bytes()))
    with pytest.raises(acceptance.PrerequisitesUnavailable):
        resolver.load_target_registry(target)


def test_target_hash_is_compared_to_registry_not_to_another_caller_value():
    loaded = resolver.load_target_registry()
    target = loaded.document.targets[0]
    acceptance_ref, resolved = resolver._targets(  # noqa: SLF001 - mutation guard
        loaded,
        [{"targetId": target.target_id, "targetSha256": target.target_sha256}],
    )
    assert acceptance_ref == "AC-12"
    assert resolved[0]["targetSha256"] == target.target_sha256
    with pytest.raises(acceptance.ReferencesUnresolvable):
        resolver._targets(  # noqa: SLF001
            loaded,
            [{"targetId": target.target_id, "targetSha256": "0" * 64}],
        )


def test_resolved_target_must_name_the_write_criterion():
    acceptance._require_resolution_criterion(  # noqa: SLF001 - mutation guard
        SimpleNamespace(acceptance_id_ref="AC-12"), "AC-12"
    )
    with pytest.raises(acceptance.ReferencesUnresolvable):
        acceptance._require_resolution_criterion(  # noqa: SLF001
            SimpleNamespace(acceptance_id_ref="AC-13"), "AC-12"
        )
    with pytest.raises(acceptance.ReferencesUnresolvable):
        acceptance._require_resolution_criterion(None, "AC-12")  # noqa: SLF001


def test_cursor_is_opaque_exact_and_rejects_extra_or_naive_state():
    instant = dt.datetime(2026, 10, 1, 1, 2, 3, 456789, tzinfo=UTC)
    encoded = resolver._encode_cursor(instant, "ev_01")  # noqa: SLF001
    assert resolver._decode_cursor(encoded) == (instant, "ev_01")  # noqa: SLF001

    payload = {"recordedAt": "2026-10-01T01:02:03", "evidenceId": "ev_01"}
    import base64

    malformed = (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )
    with pytest.raises(acceptance.ReferencesUnresolvable):
        resolver._decode_cursor(malformed)  # noqa: SLF001


def test_migration_is_linear_invoker_only_and_caller_values_are_not_preserved():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision = "0057_release_acceptance_quorum"' in source
    assert "SECURITY DEFINER" not in source
    assert source.count("SECURITY INVOKER") >= 3
    assert "NEW.envelope_sha256 :=" in source
    assert "binding_project_is_server_derived" in source
    assert "binding_digest_is_server_derived" in source
    assert "release_target_registry_pin_immutable" in source
    assert "NEW.target_registry_version IS DISTINCT FROM OLD.target_registry_version" in source
    assert "LANGUAGE sql SECURITY INVOKER STABLE" in source
    assert "ALTER TABLE release_evidence_bindings FORCE ROW LEVEL SECURITY" in source
    assert "pg_catalog.sha256" in source
    assert "pgcrypto" not in source
    assert "public.digest" not in source
    assert "SET search_path = pg_catalog" in source
    assert "dynamic SQL" not in source


def test_definer_policy_tracks_the_new_head_without_claiming_invoker_functions():
    policy = json.loads(DEFINER_POLICY.read_text(encoding="utf-8"))
    assert policy["revision"] == "0061_build_preparations"
    assert all("evidence_envelope" not in signature for signature in policy["functions"])


def test_binding_is_tenant_scoped_and_append_only_in_the_declarative_inventory():
    assert "release_evidence_bindings" in TENANT_SCOPED_TABLES
    assert "release_evidence_bindings" in APPEND_ONLY_TABLES


def test_production_resolver_is_bound_but_write_enable_remains_an_independent_gate():
    assert acceptance.active_resolver().bound is True
    with pytest.raises(acceptance.PrerequisitesUnavailable):
        acceptance.require_prerequisites(enabled=False, resolver=acceptance.active_resolver())
