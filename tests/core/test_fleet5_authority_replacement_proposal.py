"""Gate for the PROPOSED FLEET5 authority-replacement and advance-renewal plan.

Offline only: JSON documents, schema and pure invariant functions. Nothing here
touches a database, key, certificate, network or process.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import json

from jsonschema import Draft202012Validator
import pytest

from tools import check_fleet5_authority_replacement as checker
from tools import generate_fleet5_authority_replacement_fixtures as generator

SCHEMA = json.loads(checker.SCHEMA_PATH.read_text("utf-8"))
EXPECTATIONS = json.loads(checker.EXPECTATIONS_PATH.read_text("utf-8"))["documents"]
REAL_IDS = (
    "97968b42-68aa-40ce-af5e-3a33e2fc2205",
    "bcd581be-31b4-4aca-86e6-3ca31b69ed09",
    "nod_01M6TGQZ8S3DAFS7TYE8TY1PX2",
    "nod_01M6TAWG25JTA3F7J7S1EE4N2W",
    "nod_01M6TGSXV1J7XWC5D5H7N6EW1D",
    "b8d777ab04c65a44f827fdda9629d54a086e9ff8cc752b90a09023a93341c5a3",
)


def load(rel: str) -> dict:
    return json.loads((checker.CONTRACT_DIR / rel).read_text("utf-8"))


def test_schema_is_valid_draft_2020_12():
    Draft202012Validator.check_schema(SCHEMA)


def test_committed_files_match_generator():
    assert generator.main(["--check"]) == 0


def test_every_document_matches_expected_verdict():
    assert checker.check_all() == []
    assert checker.main([]) == 0


@pytest.mark.parametrize("entry", EXPECTATIONS, ids=[e["path"] for e in EXPECTATIONS])
def test_document_verdict(entry):
    assert checker.evaluate(load(entry["path"]), SCHEMA) == sorted(entry["codes"])


def test_coverage_of_rejection_codes():
    rejected = {code for e in EXPECTATIONS for code in e["codes"]}
    assert rejected >= {
        "AR-SCHEMA", "AR-SECRET-MATERIAL", "AR-TERMINAL-REUSE", "AR-TERMINAL-ANCHOR",
        "AR-TERMINAL-NOT-EXPIRED", "AR-EPOCH-SPIFFE", "AR-CHANNEL-NONMONOTONE", "AR-POLICY-NONMONOTONE",
        "AR-ENROLLMENT-REUSES-IDENTITY", "AR-IDENTITY-COLLISION", "AR-ROTATION-KEY-CHANGED",
        "AR-ROTATION-UNKNOWN-IDENTITY", "AR-ENROLLMENT-COUNTER", "AR-HOLD-REQUIRED", "AR-RENEWAL-BUDGET",
        "AR-RECOVERY-MISMATCH", "AR-CHECKPOINT-ORDER", "AR-PLANNED-LEAF-REUSE",
    }
    actions = {load(e["path"])["checkpoint"]["expectedRecoveryAction"] for e in EXPECTATIONS if not e["codes"]}
    assert actions == set(SCHEMA["$defs"]["checkpoint"]["properties"]["expectedRecoveryAction"]["enum"])


@pytest.mark.parametrize(
    "rel, path",
    [
        ("fixtures/rejection/r05-cross-signed-by-terminal.json", ["newAuthority", "crossSignedByTerminal"]),
        ("fixtures/rejection/r21-activation-released.json", ["activation"]),
        ("fixtures/rejection/r27-rollback-to-terminal.json", ["checkpoint", "expectedRecoveryAction"]),
    ],
)
def test_schema_rejections_fail_on_the_mutated_field(rel, path):
    errors = list(Draft202012Validator(SCHEMA).iter_errors(load(rel)))
    assert [list(e.absolute_path) for e in errors] == [path]


def test_synthetic_fixtures_never_carry_fleet_values():
    for entry in EXPECTATIONS:
        if entry["path"].startswith("fixtures/"):
            text = (checker.CONTRACT_DIR / entry["path"]).read_text("utf-8")
            assert not any(value in text for value in REAL_IDS), entry["path"]
            assert json.loads(text)["fixture"] is True


def test_real_instance_is_hold_and_cannot_be_promoted():
    doc = load("instances/fleet5-nov18-ca-terminal-hold.json")
    assert doc["status"] == "HOLD" and doc["fixture"] is False
    assert doc["activation"] == "NOT_AUTHORIZED"
    assert checker.recovery_action(doc) == ("NOT_STARTED", None)
    promoted = copy.deepcopy(doc)
    promoted["status"] = "PROPOSED"
    assert "AR-HOLD-REQUIRED" in checker.evaluate(promoted, SCHEMA)
    # The genuine inputs that must come from Root readback / custody / decision before PROPOSED.
    missing = set(checker._nulls(doc))
    assert {"preservedEpoch", "existingNodeRows.source", "newAuthority.caCertificateSHA256",
            "newAuthority.trustAuthorization.decisionRef", "advanceRenewal.normalBudgetSeconds",
            "PC1.nodeID", "PC2.counters.channelVersionBefore"} <= missing


def _base() -> dict:
    return generator.base()


@pytest.mark.parametrize("pc", ["PC2", "PC3", "PC4"])
@pytest.mark.parametrize("delta", [-1, 0, 2, 3])
def test_rotation_channel_must_be_exactly_c_plus_one(pc, delta):
    doc = _base()
    c = generator.member(doc, pc)["counters"]
    c["channelVersionAfter"] = c["channelVersionBefore"] + delta
    assert "AR-CHANNEL-NONMONOTONE" in checker.evaluate(doc, SCHEMA)


@pytest.mark.parametrize("pc", ["PC2", "PC3", "PC4"])
@pytest.mark.parametrize("delta", [-1, 0, 2])
def test_rotation_policy_must_be_exactly_floor_plus_one(pc, delta):
    doc = _base()
    c = generator.member(doc, pc)["counters"]
    c["policyVersionAfter"] = c["policyFloorBefore"] + delta
    assert "AR-POLICY-NONMONOTONE" in checker.evaluate(doc, SCHEMA)


def test_account_name_is_not_identity():
    doc = _base()
    assert generator.member(doc, "PC1")["account"] == generator.member(doc, "PC4")["account"]
    assert checker.evaluate(doc, SCHEMA) == []


@pytest.mark.parametrize("field", ["caSuccessorLeadSeconds", "caWarningLeadSeconds", "leafRenewalLeadSeconds",
                                   "policyRenewalLeadSeconds"])
def test_advance_renewal_leads_have_a_hard_floor(field):
    doc = _base()
    doc["advanceRenewal"][field] = 661
    assert checker.evaluate(doc, SCHEMA) == ["AR-RENEWAL-BUDGET"]


def test_recovery_never_resumes_after_db_epoch_or_custody_doubt():
    for name in ("p06-db-unavailable-hold", "p07-custody-mismatch-hold", "p11-epoch-diverged-hold"):
        doc = load(f"fixtures/positive/{name}.json")
        action, phase = checker.recovery_action(doc)
        assert action.startswith("HOLD_") and phase is None


def test_resume_replays_the_interrupted_phase_not_the_next():
    doc = load("fixtures/positive/p02-a4-partial-cas-resume.json")
    assert checker.recovery_action(doc) == ("RESUME_FORWARD", "A4_CHANNEL_CAS")


def test_secret_scan_covers_nested_strings():
    doc = _base()
    doc["members"][0]["account"] = "x"
    doc["roleKeys"][0]["custodyEvidenceRef"] = "see postgresql://user:pw@host/db"
    assert checker.evaluate(doc, SCHEMA) == ["AR-SECRET-MATERIAL"]


# ---------------------------------------------------------------- expiry boundaries


def _renewal(**changes) -> list[str]:
    doc = _base()
    doc["advanceRenewal"].update(changes)
    return checker.evaluate(doc, SCHEMA)


def _iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_terminal_expiry_boundary_is_inclusive():
    doc = _base()
    doc["terminalAuthority"]["notAfter"] = doc["observedAt"]  # expired exactly at observation
    assert checker.evaluate(doc, SCHEMA) == []
    doc["terminalAuthority"]["notAfter"] = "2026-11-18T12:00:01Z"  # one second still valid
    assert checker.evaluate(doc, SCHEMA) == ["AR-TERMINAL-NOT-EXPIRED"]


def test_leaf_lifetime_cap_boundary():
    assert _renewal(leafLifetimeSeconds=518400) == []
    assert _renewal(leafLifetimeSeconds=518401) == ["AR-RENEWAL-BUDGET"]


@pytest.mark.parametrize("overlap, ok", [(630, False), (631, True), (21600, True), (21601, False)])
def test_overlap_boundaries(overlap, ok):
    assert (_renewal(overlapSeconds=overlap) == []) is ok


def test_leaf_renewal_lead_exact_floor():
    floor = 7200 + 14400 + 630 + 30
    assert _renewal(leafRenewalLeadSeconds=floor) == []
    assert _renewal(leafRenewalLeadSeconds=floor - 1) == ["AR-RENEWAL-BUDGET"]


def test_policy_renewal_lead_exact_floor():
    floor = 7200 + 630 + 30
    assert _renewal(policyRenewalLeadSeconds=floor) == []
    assert _renewal(policyRenewalLeadSeconds=floor - 1) == ["AR-RENEWAL-BUDGET"]


def test_ca_successor_lead_exact_floor():
    floor = 518400 + 86400 + 14400 + 630 + 30
    assert _renewal(caSuccessorLeadSeconds=floor) == []
    assert _renewal(caSuccessorLeadSeconds=floor - 1) == ["AR-RENEWAL-BUDGET"]


def test_warning_must_exceed_successor_lead():
    assert _renewal(caWarningLeadSeconds=2592000) == ["AR-RENEWAL-BUDGET"]
    assert _renewal(caWarningLeadSeconds=2592001) == []


@pytest.mark.parametrize("lifetime, ok", [(7776000, True), (7775999, False)])
def test_ca_lifetime_at_least_twice_warning(lifetime, ok):
    doc = _base()
    doc["advanceRenewal"]["caLifetimeSeconds"] = lifetime
    doc["newAuthority"]["notBefore"] = doc["observedAt"]
    doc["newAuthority"]["notAfter"] = _iso(checker._ts(doc["observedAt"]).timestamp() + lifetime)
    assert (checker.evaluate(doc, SCHEMA) == []) is ok


@pytest.mark.parametrize("extra, ok", [(0, False), (1, True)])
def test_new_ca_must_not_be_born_inside_its_warning_window(extra, ok):
    doc = _base()
    warning = doc["advanceRenewal"]["caWarningLeadSeconds"]
    doc["newAuthority"]["notBefore"] = doc["observedAt"]
    doc["newAuthority"]["notAfter"] = _iso(checker._ts(doc["observedAt"]).timestamp() + warning + extra)
    assert (checker.evaluate(doc, SCHEMA) == []) is ok


def test_new_ca_lifetime_longer_than_declared_is_rejected():
    doc = _base()
    doc["newAuthority"]["notAfter"] = "2027-11-18T12:00:01Z"
    assert checker.evaluate(doc, SCHEMA) == ["AR-RENEWAL-BUDGET"]


# ---------------------------------------------------------------- interruption sweep

ROTATION_PCS = ("PC2", "PC3", "PC4")
MUTATING = checker.PHASES[1:]


def _state_rows(doc: dict, last: str | None) -> list[dict]:
    """Readback consistent with every phase up to and including ``last`` being durable."""
    li = checker._idx(last)
    rows = []
    for pc in ROTATION_PCS:
        m = generator.member(doc, pc)
        c = m["counters"]
        cas = li >= checker.INDEX["A4_CHANNEL_CAS"]
        settled = li >= checker.INDEX["A7_ROTATION_SETTLED"]
        rows.append(generator.row(
            doc, pc,
            version=c["channelVersionAfter"] if cas else c["channelVersionBefore"],
            cert=m["plannedLeafSHA256"] if cas else None,
            floor=c["policyVersionAfter"] if settled else c["policyFloorBefore"],
        ))
    if li >= checker.INDEX["E2_ENROLLMENT_ADMITTED"]:
        m = generator.member(doc, "PC1")
        settled = li >= checker.INDEX["E3_ENROLLMENT_SETTLED"]
        rows.append(generator.row(doc, "PC1", version=1, cert=m["plannedLeafSHA256"], floor=1 if settled else 0))
    return rows


def _interrupted(last, flight, outcome, state, custody="NEW_KEY_PRESENT_MATCHES_PLAN"):
    doc = _base()
    generator.interrupted(doc, last, flight, outcome, custody, _state_rows(doc, state), "NOT_STARTED")
    return doc


@pytest.mark.parametrize("flight", MUTATING)
def test_every_interrupted_phase_resumes_at_itself(flight):
    last = checker.PHASES[checker.INDEX[flight] - 1]
    doc = _interrupted(last, flight, "UNKNOWN", last)
    assert checker.recovery_action(doc) == ("RESUME_FORWARD", flight)


@pytest.mark.parametrize("flight", MUTATING)
def test_interrupted_phase_whose_effect_already_landed_still_resumes_at_itself(flight):
    """Effect visible in the DB but not yet in the journal: replay the same phase idempotently."""
    last = checker.PHASES[checker.INDEX[flight] - 1]
    doc = _interrupted(last, flight, "UNKNOWN", flight)
    assert checker.recovery_action(doc) == ("RESUME_FORWARD", flight)


@pytest.mark.parametrize("last", checker.PHASES[1:-1])
def test_durable_boundary_resumes_at_next_phase(last):
    doc = _interrupted(last, None, None, last)
    assert checker.recovery_action(doc) == ("RESUME_FORWARD", checker.PHASES[checker.INDEX[last] + 1])


def test_final_phase_is_complete():
    doc = _interrupted("E3_ENROLLMENT_SETTLED", None, None, "E3_ENROLLMENT_SETTLED")
    assert checker.recovery_action(doc) == ("COMPLETE", None)


@pytest.mark.parametrize("last", [p for p in checker.PHASES if checker.INDEX[p] >= checker.INDEX["A4_CHANNEL_CAS"]])
def test_rolled_back_channel_after_durable_cas_holds(last):
    doc = _interrupted(last, None, None, last)
    rows = doc["checkpoint"]["readback"]["members"]
    rows[0] = generator.row(doc, "PC2")  # PC2 back at its pre-replacement version and leaf
    assert checker.recovery_action(doc) == ("HOLD_FOREIGN_WRITER", None)


@pytest.mark.parametrize("custody, action", [
    ("NO_NEW_KEY", "ABANDON_BEFORE_NEW_TRUST"),
    ("NEW_KEY_PRESENT_MATCHES_PLAN", "RESUME_FORWARD"),
    ("NEW_KEY_PRESENT_MISMATCH", "HOLD_CUSTODY_UNRESOLVED"),
    ("UNKNOWN", "HOLD_CUSTODY_UNRESOLVED"),
    ("NOT_READ", "HOLD_CUSTODY_UNRESOLVED"),
])
def test_interrupted_new_trust_creation_depends_only_on_custody(custody, action):
    doc = _interrupted("A0_PREFLIGHT_READBACK", "A1_NEW_TRUST_AUTHORIZED", "UNKNOWN", "A0_PREFLIGHT_READBACK",
                       custody=custody)
    assert checker.recovery_action(doc)[0] == action


@pytest.mark.parametrize("last", checker.PHASES[1:])
def test_custody_doubt_after_new_trust_always_holds(last):
    doc = _interrupted(last, None, None, last, custody="UNKNOWN")
    assert checker.recovery_action(doc) == ("HOLD_CUSTODY_UNRESOLVED", None)


# ---------------------------------------------------------------- PC1 first-enrollment handoff


def test_pc1_first_enrollment_fixture_is_concrete_and_unique():
    doc = load("fixtures/positive/p14-pc1-first-enrollment-ready.json")
    pc1 = generator.member(doc, "PC1")
    rows = doc["existingNodeRows"]
    assert pc1["kind"] == "NEW_ENROLLMENT" and pc1["priorNodePublicKeySHA256"] is None
    assert pc1["nodeID"] not in rows["nodeIDs"]
    assert pc1["nodePublicKeySHA256"] not in rows["publicKeySHA256s"]
    assert pc1["spiffeURI"].endswith(f"/node/{pc1['nodeID']}/epoch/{doc['preservedEpoch']['epoch']}")
    assert pc1["counters"] == {"channelVersionBefore": 0, "channelVersionAfter": 1,
                               "policyFloorBefore": 0, "policyVersionAfter": 1}
    assert checker.recovery_action(doc) == ("RESUME_FORWARD", "E1_ENROLLMENT_AUTHORIZED")


def test_handoff_feeds_the_existing_five_node_verifier():
    from tools.five_node_lab_preflight import validate_five_node_inventory

    handoff = load("handoff/pc1-first-enrollment-handoff.json")
    plan_bytes = (checker.CONTRACT_DIR / handoff["sourcePlan"]).read_bytes()
    plan = json.loads(plan_bytes)
    assert handoff["sourcePlanSHA256"] == hashlib.sha256(plan_bytes).hexdigest()
    assert validate_five_node_inventory(handoff["fiveNodeInventory"]) is handoff["fiveNodeInventory"]
    pc1 = generator.member(plan, "PC1")
    entry = next(n for n in handoff["fiveNodeInventory"]["nodes"] if n["nodeId"] == pc1["nodeID"])
    assert entry["certificateSHA256"] == pc1["plannedLeafSHA256"] == handoff["newIdentity"]["leafCertificateSHA256"]
    assert entry["ip"] == pc1["address"]
    ca = handoff["publicCAEvidence"]
    assert ca["anchorBundle"] == [plan["newAuthority"]["caCertificateSHA256"]] == [ca["caCertificateSHA256"]]
    assert ca["excludedTerminalCACertificateSHA256"] not in ca["anchorBundle"]
    assert handoff["activation"] == "NOT_AUTHORIZED"


@pytest.mark.parametrize("rel", [
    "fixtures/positive/p14-pc1-first-enrollment-ready.json",
    "fixtures/positive/p04-e2-enrollment-resume.json",
    "fixtures/rejection/r09-pc1-copies-pc4-identity.json",
])
def test_handoff_refuses_unsettled_or_rejected_plans(rel):
    raw = (checker.CONTRACT_DIR / rel).read_bytes()
    with pytest.raises(ValueError):
        checker.enrollment_handoff(json.loads(raw), rel, raw, hosts=generator.HANDOFF_HOSTS,
                                   control_plane_host=generator.HANDOFF_CP_HOST)
