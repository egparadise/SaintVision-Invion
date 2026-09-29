"""An unmeasured identity claim must not be able to reach a pass.

These tests run without a provider. They exist to pin the shape of the verdict and
the redaction, because those are the parts a hand-written runbook sentence gets wrong:
a pass that nobody measured, or an artifact that quietly carries a token.
"""

from __future__ import annotations

import json

import pytest

from tools import collect_oidc_identity_evidence as collector


def passing_evidence():
    return {
        "schemaVersion": collector.SCHEMA_VERSION,
        "codeSha": "0" * 40,
        "collectorSha256": "a" * 64,
        "criteria": dict(collector.CRITERIA),
        "provenance": {"commit": "0" * 40, "workingTreeClean": True, "contentClean": True},
        "source": {
            "observedAt": "2026-09-30T00:00:00Z",
            "issuerScheme": "https",
            "providerRole": "cutover-rehearsal",
            "issuerSha256": "b" * 64,
            "temporaryBundleRemoved": True,
        },
        "observations": {name: {"status": "MEASURED_PASS"} for name in collector.REQUIRED},
        "verdict": "PASS",
        "acceptanceClaim": True,
    }


def test_the_shape_this_collector_writes_is_accepted():
    collector.validate_evidence(passing_evidence())


@pytest.mark.parametrize("name", collector.REQUIRED)
def test_a_single_unmeasured_observation_cannot_be_carried_by_a_pass(name):
    evidence = passing_evidence()
    evidence["observations"][name] = {"status": "NOT_OBSERVED", "reason": "not supplied"}
    with pytest.raises(ValueError, match="verdict"):
        collector.validate_evidence(evidence)
    # Recomputing gives the only verdict such a run may claim.
    assert collector.overall_verdict(evidence["observations"], collector.REQUIRED) == "NOT_OBSERVED"


def test_a_failed_refusal_check_makes_the_whole_run_fail():
    evidence = passing_evidence()
    evidence["observations"]["tamperedTokenRefused"] = {"status": "MEASURED_FAIL"}
    assert collector.overall_verdict(evidence["observations"], collector.REQUIRED) == "FAIL"


def test_a_hand_edited_verdict_is_refused():
    evidence = passing_evidence()
    evidence["observations"]["liveTokenVerified"] = {"status": "NOT_OBSERVED", "reason": "none"}
    evidence["verdict"] = "PASS"
    with pytest.raises(ValueError, match="verdict"):
        collector.validate_evidence(evidence)


def test_acceptance_claim_must_follow_the_verdict():
    evidence = passing_evidence()
    evidence["acceptanceClaim"] = False
    with pytest.raises(ValueError, match="acceptanceClaim"):
        collector.validate_evidence(evidence)


def test_a_pass_cannot_be_reported_for_a_plain_http_issuer():
    """AccessTokens refuses a non-https issuer, so such a PASS contradicts the product."""
    evidence = passing_evidence()
    evidence["source"]["issuerScheme"] = "http"
    with pytest.raises(ValueError, match="non-https"):
        collector.validate_evidence(evidence)


def test_the_measured_provider_must_be_named():
    """A rehearsal on a throwaway instance is not evidence about production."""
    evidence = passing_evidence()
    del evidence["source"]["providerRole"]
    with pytest.raises(ValueError, match="providerRole"):
        collector.validate_evidence(evidence)
    evidence["source"]["providerRole"] = "something-else"
    with pytest.raises(ValueError, match="providerRole"):
        collector.validate_evidence(evidence)


def test_cleanup_must_be_confirmed():
    evidence = passing_evidence()
    evidence["source"]["temporaryBundleRemoved"] = False
    with pytest.raises(ValueError, match="cleanup"):
        collector.validate_evidence(evidence)


def test_an_extra_observation_is_refused():
    evidence = passing_evidence()
    evidence["observations"]["somethingElse"] = {"status": "MEASURED_PASS"}
    with pytest.raises(ValueError, match="exactly the three"):
        collector.validate_evidence(evidence)


def test_tampering_changes_the_payload_and_leaves_the_signature():
    token = "aGVhZGVy.cGF5bG9hZA.c2ln"
    edited = collector.tamper(token)
    assert edited != token
    assert edited.split(".")[0] == token.split(".")[0]
    assert edited.split(".")[2] == token.split(".")[2]
    assert edited.split(".")[1] != token.split(".")[1]


def test_measurement_without_a_provider_stays_unobserved_and_cleans_up():
    """An http issuer cannot be measured at all; it must not look like a failure to pass."""
    observations, facts = collector.measure(
        issuer="http://idp.sv.lan:8080/realms/saintvision",
        jwks={"keys": []},
        token="a.b.c",
        tenant_id="00000000-0000-4000-8000-000000000001",
        audience="sv-api",
        client_id="sv-portal",
        now=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    assert {o["status"] for o in observations.values()} == {"NOT_OBSERVED"}
    assert facts["temporaryBundleRemoved"] is True
    assert collector.overall_verdict(observations, collector.REQUIRED) == "NOT_OBSERVED"


def test_the_markdown_never_renders_a_token_or_a_key_id():
    evidence = passing_evidence()
    evidence["source"]["signedByKidSha256"] = "c" * 64
    rendered = collector.render_markdown(evidence)
    assert "eyJ" not in rendered
    assert "SHA-256" in rendered
    assert json.dumps(evidence["criteria"]) not in rendered


def test_evidence_from_a_dirty_tree_is_refused():
    """codeSha names a commit; on a dirty tree it names bytes that were never in it."""
    for field in ("workingTreeClean", "contentClean"):
        evidence = passing_evidence()
        evidence["provenance"][field] = False
        with pytest.raises(ValueError, match="clean"):
            collector.validate_evidence(evidence)


def test_a_short_or_absent_code_sha_is_refused():
    for value in (None, "", "abc123", "g" * 40):
        evidence = passing_evidence()
        evidence["codeSha"] = value
        with pytest.raises(ValueError, match="codeSha"):
            collector.validate_evidence(evidence)
