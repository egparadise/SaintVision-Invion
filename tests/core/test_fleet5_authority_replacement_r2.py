"""Gate for the PROPOSED FLEET5 authority-replacement contract R2.

Offline only: JSON documents, public DER certificates/CSRs built from publicly
derivable fixture keys, the schema and pure functions. Nothing here touches a
database, a real key, a network or a process.

Sections map to the five HIGH findings of the R1 independent review:
F1 first admission, F2 identity/authority, F3 serving evidence, F4 retry after a
committed effect, F5 expiry during a pause and advance renewal.
"""

from __future__ import annotations

import base64
import copy
from datetime import timedelta
import hashlib
import json

from cryptography.hazmat.primitives.serialization import load_der_private_key
from cryptography.x509.oid import ExtendedKeyUsageOID
from jsonschema import Draft202012Validator
import pytest

from tools import check_fleet5_authority_replacement_r2 as checker
from tools import generate_fleet5_authority_replacement_r2_fixtures as gen

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
A = gen.A


def load(rel: str) -> dict:
    return json.loads((checker.CONTRACT_DIR / rel).read_text("utf-8"))


def base(name: str = "t-base", **kw) -> dict:
    return gen.ceremony_done(name, **kw)


def state(last, flight=None, *, landed=lambda op: False, resume_at=gen.RESUME, **kw) -> dict:
    return gen.at_state(base(**kw), last, flight, landed=landed, resume_at=resume_at)


def action(doc: dict) -> str:
    return checker.recovery_action(doc)[0]


# ---------------------------------------------------------------- corpus integrity


def test_schema_is_valid_draft_2020_12():
    Draft202012Validator.check_schema(SCHEMA)


def test_committed_files_match_generator():
    assert gen.main(["--check"]) == 0


def test_every_document_matches_expected_verdict():
    assert checker.check_all() == []
    assert checker.main([]) == 0


@pytest.mark.parametrize("entry", EXPECTATIONS, ids=[e["path"] for e in EXPECTATIONS])
def test_document_verdict(entry):
    assert checker.evaluate(load(entry["path"]), SCHEMA) == sorted(entry["codes"])


def test_every_recovery_action_and_rejection_code_is_exercised():
    actions = {load(e["path"])["checkpoint"]["expectedRecoveryAction"] for e in EXPECTATIONS if not e["codes"]}
    assert actions == set(SCHEMA["$defs"]["checkpoint"]["properties"]["expectedRecoveryAction"]["enum"])
    codes = {c for e in EXPECTATIONS for c in e["codes"]}
    assert codes >= {
        "AR-SCHEMA", "AR-SECRET-MATERIAL", "AR-PRIOR-REUSE", "AR-TERMINAL-ANCHOR", "AR-TERMINAL-NOT-EXPIRED",
        "AR-EPOCH-SPIFFE", "AR-CHANNEL-NONMONOTONE", "AR-POLICY-NONMONOTONE", "AR-ENROLLMENT-REUSES-IDENTITY",
        "AR-IDENTITY-COLLISION", "AR-ROTATION-KEY-CHANGED", "AR-ROTATION-UNKNOWN-IDENTITY", "AR-ENROLLMENT-COUNTER",
        "AR-HOLD-REQUIRED", "AR-RENEWAL-BUDGET", "AR-RECOVERY-MISMATCH", "AR-CHECKPOINT-ORDER",
        "AR-PLANNED-LEAF-REUSE", "AR-CERT-ROOT", "AR-CERT-LEAF", "AR-CSR-POP", "AR-PRIOR-BINDING",
        "AR-ROLE-SEPARATION", "AR-ROLE-CONTINUITY", "AR-ENROLLMENT-RESERVATION", "AR-PROCESS-INVENTORY",
        "AR-MANIFEST", "AR-CEREMONY-INCOMPLETE", "AR-ADVANCE-WINDOW", "AR-MODE",
    }


@pytest.mark.parametrize("rel, path", [
    ("fixtures/rejection/r05-cross-signed-by-prior.json", ["newAuthority", "crossSignedByPrior"]),
    ("fixtures/rejection/r21-activation-released.json", ["activation"]),
    ("fixtures/rejection/r24-rollback-to-terminal.json", ["checkpoint", "expectedRecoveryAction"]),
])
def test_schema_rejections_fail_on_the_mutated_field(rel, path):
    errors = list(Draft202012Validator(SCHEMA).iter_errors(load(rel)))
    assert [list(e.absolute_path) for e in errors] == [path]


def _der_fields(value):
    if isinstance(value, dict):
        for k, v in value.items():
            if k.endswith("DER") and isinstance(v, str):
                yield v
            else:
                yield from _der_fields(v)
    elif isinstance(value, list):
        for item in value:
            yield from _der_fields(item)


def test_fixtures_carry_public_pki_only_and_no_fleet_values():
    seen = 0
    for entry in EXPECTATIONS:
        if not entry["path"].startswith("fixtures/"):
            continue
        text = (checker.CONTRACT_DIR / entry["path"]).read_text("utf-8")
        assert not any(v in text for v in REAL_IDS), entry["path"]
        doc = json.loads(text)
        assert doc["fixture"] is True
        for value in _der_fields(doc):
            seen += 1
            with pytest.raises(ValueError):
                load_der_private_key(base64.b64decode(value), password=None)
    assert seen > 500


def test_real_instance_is_hold_and_cannot_be_promoted():
    doc = load("instances/fleet5-nov18-ca-terminal-hold-r2.json")
    assert doc["status"] == "HOLD" and doc["fixture"] is False and doc["activation"] == "NOT_AUTHORIZED"
    assert checker.recovery_action(doc) == ("NOT_STARTED", None, [], [])
    promoted = copy.deepcopy(doc)
    promoted["status"] = "PROPOSED"
    assert "AR-HOLD-REQUIRED" in checker.evaluate(promoted, SCHEMA)
    missing = set(checker._nulls(doc))
    assert {"preservedEpoch", "existingNodeRows", "priorAuthority.certificateDER", "measuredBudgets",
            "servingBinaryMigration", "writerFence.token", "controlPlaneClient.processInventory",
            "roleKeys[0].continuity", "PC1.nodeID", "PC1.csrDER", "PC2.priorLeafDER",
            "PC2.counters.channelVersionBefore"} <= missing
    assert doc["placement"] == {"controlPlaneHostPC": "PC3", "excludedPCs": ["PC5"]}


def test_r1_contract_is_preserved_alongside_r2():
    from tools import check_fleet5_authority_replacement as r1

    assert r1.check_all() == []
    assert r1.CONTRACT_DIR != checker.CONTRACT_DIR


# ---------------------------------------------------------------- F1 first admission


def test_f1_row_without_channel_during_e2_is_a_journaled_resume_not_a_foreign_writer():
    """R1 returned HOLD_FOREIGN_WRITER for a present row without C=1 even during E2."""
    doc = state(A["E1"], A["E2"], landed=lambda op: True)
    row = gen.row(doc, "PC1")
    assert row["channelVersion"] == 0
    rd = checker.reservation_digest(gen.member(doc, "PC1"))
    admit = gen.op_of(doc, A["E2"], "PC1")["opID"]
    assert checker.recovery_action(doc) == ("RESUME_FORWARD", A["E2"], [], [admit])
    assert row["reservationDigest"] == rd


@pytest.mark.parametrize("flight", checker.ENROLLMENT_PHASES)
@pytest.mark.parametrize("landed", [False, True])
def test_f1_every_enrollment_boundary_has_a_distinct_decision(flight, landed):
    last = checker.PHASES[checker.INDEX[flight] - 1]
    doc = state(last, flight, landed=lambda op: landed)
    act, phase, apply, ack = checker.recovery_action(doc)
    ops = [op["opID"] for op in gen.manifest_ops(doc) if op["phase"] == flight]
    assert (act, phase) == ("RESUME_FORWARD", flight)
    assert (ack, apply) == ((ops, []) if landed else ([], ops))


@pytest.mark.parametrize("mutate, hold", [
    (lambda d: d["checkpoint"]["readback"]["reservations"][0].update(reservationDigest=gen.h("other")),
     "HOLD_RESERVATION_MISMATCH"),
    (lambda d: d["checkpoint"]["readback"]["reservations"][0].update(fenceToken="fence:other-plan"),
     "HOLD_RESERVATION_MISMATCH"),
    (lambda d: gen.row(d, "PC1").update(reservationDigest=None), "HOLD_RESERVATION_MISMATCH"),
    (lambda d: gen.row(d, "PC1").update(channelVersion=1, channelCertificateSHA256=gen.h("foreign-leaf")),
     "HOLD_FOREIGN_WRITER"),
])
def test_f1_admission_substeps_hold_on_foreign_effects(mutate, hold):
    doc = state(A["E2"], A["E3"])
    mutate(doc)
    assert action(doc) == hold


@pytest.mark.parametrize("field, value", [
    ("tenantID", "00000000-0000-4000-8000-0000000000ff"),
    ("epoch", gen.OTHER_EPOCH),
    ("nodeID", gen.nid("0PC9")),
    ("csrSHA256", gen.h("x")),
    ("planDigest", gen.h("x")),
    ("fenceToken", "fence:other"),
    ("rowsReadbackSHA256", gen.h("x")),
])
def test_f1_reservation_binds_every_field(field, value):
    doc = gen.proposal("t-res")
    gen.member(doc, "PC1")["reservation"][field] = value
    assert "AR-ENROLLMENT-RESERVATION" in checker.evaluate(doc, SCHEMA)


def test_f1_shared_account_or_inventory_ip_is_no_ownership_evidence():
    doc = gen.proposal("t-acct")
    pc1, pc4 = gen.member(doc, "PC1"), gen.member(doc, "PC4")
    assert pc1["account"] == pc4["account"]
    assert checker.evaluate(doc, SCHEMA) == []
    # Ownership comes only from the Node-signed CSR: PC1 cannot present PC4's key.
    pc1["csrDER"] = gen.make_csr("PC4-node", pc1["nodeID"])
    assert {"AR-CSR-POP"} <= set(checker.evaluate(gen.seal(doc), SCHEMA))


# ---------------------------------------------------------------- review R2 finding 4: E2 row representation


def test_r2f4_a_placeholder_row_for_an_absent_node_is_not_representable():
    """R2 counted a rowPresent=false placeholder as pending, then ROW_ADMIT appended a second row."""
    doc = state(A["E1"], A["E2"])
    placeholder = copy.deepcopy(gen.row(state(A["E1"], A["E2"], landed=lambda op: True), "PC1"))
    placeholder["rowPresent"] = False
    doc["checkpoint"]["readback"]["members"].append(placeholder)
    assert checker.evaluate(doc, SCHEMA) == ["AR-SCHEMA"]


def test_r2f4_row_admission_never_creates_a_second_row():
    doc = state(A["E1"], A["E2"], landed=lambda op: True)
    before = copy.deepcopy(doc["checkpoint"]["readback"])
    admit = gen.op_of(doc, A["E2"], "PC1")
    with pytest.raises(checker.ExecutorConflict):
        checker.apply_op(doc, admit)
    assert doc["checkpoint"]["readback"] == before


def test_r2f4_interrupted_e2_resumes_to_exactly_one_row():
    doc = state(A["E1"], A["E2"])
    admit = gen.op_of(doc, A["E2"], "PC1")["opID"]
    assert checker.recovery_action(doc) == ("RESUME_FORWARD", A["E2"], [admit], [])
    crashed, mutations = checker.execute_resume(doc)
    assert mutations == [admit]
    crashed = checker.observe(crashed, "fixture-challenge-0002")
    assert checker.recovery_action(crashed) == ("RESUME_FORWARD", A["E2"], [], [admit])
    replay, second = checker.execute_resume(crashed)
    assert second == []
    pc1 = [r for r in replay["checkpoint"]["readback"]["members"] if r["nodeID"] == gen.NODE["PC1"]]
    assert len(pc1) == 1
    nxt = checker.observe(checker.journal_durable(replay), "fixture-challenge-0003")
    assert checker.recovery_action(nxt)[:2] == ("RESUME_FORWARD", A["E3"])


# ---------------------------------------------------------------- F2 identity and authority


@pytest.mark.parametrize("override", [
    {"signer": ("impostor-ca", gen.NEW_CN)},
    {"uri": gen.node_uri(gen.TENANT, gen.nid("0PC4"), gen.EPOCH)},
    {"uri": gen.node_uri(gen.TENANT, gen.nid("0PC3"), gen.OTHER_EPOCH)},
    {"eku": ExtendedKeyUsageOID.CLIENT_AUTH},
    {"ips": []},
    {"ips": ["10.0.0.3", "10.0.0.33"]},
    {"notAfter": "2026-11-24T12:00:01Z"},
], ids=["impostor-root", "other-node-uri", "other-epoch-uri", "client-eku", "no-ip-san", "extra-ip-san",
        "validity-not-planned"])
def test_f2_leaf_must_chain_to_the_exact_root_with_the_exact_profile(override):
    doc = gen.a1_durable(gen.ceremony(gen.proposal("t-leaf"), leaf_overrides={"PC3": override}))
    assert checker.evaluate(doc, SCHEMA) == ["AR-CERT-LEAF"]


def test_f2_a_leaf_for_a_different_key_than_the_csr_is_rejected():
    doc = base("t-key")
    gen.member(doc, "PC2")["leafDER"] = gen.member(doc, "PC3")["leafDER"]
    assert "AR-CERT-LEAF" in checker.evaluate(doc, SCHEMA)


def test_f2_hashes_alone_no_longer_pass():
    """R1 accepted label hashes; R2 requires parseable public DER for every pin."""
    doc = base("t-hash")
    gen.member(doc, "PC2")["leafDER"] = None
    assert "AR-CERT-LEAF" in checker.evaluate(doc, SCHEMA)


@pytest.mark.parametrize("pc", ["PC2", "PC3", "PC4"])
def test_f2_prior_tuple_must_match_the_db_row_exactly(pc):
    doc = gen.proposal("t-tuple")
    row = next(r for r in doc["existingNodeRows"]["rows"] if r["nodeID"] == gen.member(doc, pc)["nodeID"])
    row["publicKeySHA256"] = gen.spki("someone-else")
    assert checker.evaluate(doc, SCHEMA) == ["AR-PRIOR-BINDING"]


@pytest.mark.parametrize("status", ["DISABLED", "RETIRED"])
def test_f2_rotation_requires_an_active_row(status):
    doc = gen.proposal("t-status")
    next(r for r in doc["existingNodeRows"]["rows"] if r["nodeID"] == gen.NODE["PC2"])["status"] = status
    assert checker.evaluate(doc, SCHEMA) == ["AR-ROTATION-UNKNOWN-IDENTITY"]


def test_f2_prior_ca_certificate_must_match_its_recorded_identity():
    doc = gen.proposal("t-prior")
    doc["priorAuthority"]["subjectCommonName"] = "Someone else"
    assert "AR-PRIOR-BINDING" in checker.evaluate(doc, SCHEMA)


OWNERS = ["prior-ca", "new-ca", "cp", "role", "node"]


def _set_key(doc, owner, value):
    if owner == "prior-ca":
        doc["priorAuthority"]["caPublicKeySHA256"] = value
    elif owner == "new-ca":
        doc["newAuthority"]["caPublicKeySHA256"] = value
    elif owner == "cp":
        doc["controlPlaneClient"]["publicKeySHA256"] = value
    elif owner == "role":
        doc["roleKeys"][0]["publicKeySHA256"] = value
    else:
        gen.member(doc, "PC2")["nodePublicKeySHA256"] = value


@pytest.mark.parametrize("a, b", [(a, b) for i, a in enumerate(OWNERS) for b in OWNERS[i + 1:]])
def test_f2_role_keys_are_pairwise_separated(a, b):
    doc = gen.proposal("t-sep")
    shared = gen.h(f"shared-{a}-{b}")
    _set_key(doc, a, shared)
    _set_key(doc, b, shared)
    assert "AR-ROLE-SEPARATION" in checker.evaluate(doc, SCHEMA)


@pytest.mark.parametrize("decision, code", [
    ("UNDETERMINED", "AR-HOLD-REQUIRED"),
    ("COMPROMISED", "AR-ROLE-CONTINUITY"),
])
def test_f2_retained_signer_needs_an_affirmative_compromise_decision(decision, code):
    doc = gen.proposal("t-signer")
    doc["roleKeys"][0]["continuity"]["compromiseDecision"] = decision
    assert checker.evaluate(doc, SCHEMA) == [code]


def test_f2_replaced_signer_carries_no_continuity_claim():
    doc = gen.proposal("t-replaced")
    doc["roleKeys"][0]["disposition"] = "REPLACED"
    assert checker.evaluate(doc, SCHEMA) == ["AR-ROLE-CONTINUITY"]
    doc["roleKeys"][0]["continuity"] = None
    assert checker.evaluate(doc, SCHEMA) == []


def test_f2_fresh_cp_key_must_differ_from_the_prior_cp_key():
    doc = gen.proposal("t-cp-fresh")
    doc["controlPlaneClient"]["keyContinuity"] = "FRESH"
    assert "AR-FRESH-KEY-REUSED" in checker.evaluate(gen.seal(doc), SCHEMA)


# ---------------------------------------------------------------- F3 serving evidence


@pytest.mark.parametrize("process", [p["processID"] for p in gen.INVENTORY])
def test_f3_every_inventoried_process_needs_its_own_fresh_readback(process):
    doc = state(A["A7"], enroll=False)
    assert action(doc) == "COMPLETE"
    procs = doc["checkpoint"]["readback"]["serving"]["processes"]
    procs[:] = [p for p in procs if p["processID"] != process]
    assert action(doc) == "HOLD_SERVING_EVIDENCE_INCOMPLETE"


@pytest.mark.parametrize("field, value, hold", [
    ("challengeNonce", "fixture-old-0000", "HOLD_SERVING_EVIDENCE_INCOMPLETE"),
    ("anchorDigest", gen.h("prior-only-bundle"), "HOLD_SERVING_EVIDENCE_INCOMPLETE"),
    ("policyDigest", gen.h("old-policy"), "HOLD_SERVING_EVIDENCE_INCOMPLETE"),
    ("cpClientURI", "spiffe://saintvision.ai/tenant/x/control-plane/epoch/y", "HOLD_SERVING_EVIDENCE_INCOMPLETE"),
    ("peerLeafSHA256", gen.h("unplanned-leaf"), "HOLD_FOREIGN_WRITER"),
])
def test_f3_settlement_needs_a_fresh_handshake_under_the_new_pins(field, value, hold):
    doc = state(A["A7"], enroll=False)
    shake = doc["checkpoint"]["readback"]["serving"]["handshakes"][1]
    shake[field] = value
    assert action(doc) == hold


@pytest.mark.parametrize("age, ok", [(gen.HEARTBEAT, True), (gen.HEARTBEAT + 1, False)])
def test_f3_heartbeat_freshness_boundary(age, ok):
    doc = state(A["A7"], enroll=False)
    at = checker._ts(doc["checkpoint"]["resumeAt"])
    doc["checkpoint"]["readback"]["serving"]["handshakes"][0]["heartbeatAt"] = checker._iso(at - timedelta(seconds=age))
    assert (action(doc) == "COMPLETE") is ok


@pytest.mark.parametrize("age, ok", [(gen.FRESHNESS, True), (gen.FRESHNESS + 1, False)])
def test_f3_observation_freshness_boundary(age, ok):
    doc = state(A["A7"], enroll=False)
    at = checker._ts(doc["checkpoint"]["resumeAt"])
    serving = doc["checkpoint"]["readback"]["serving"]
    serving["challengeIssuedAt"] = checker._iso(at - timedelta(seconds=gen.CHALLENGE))
    received = checker._iso(at - timedelta(seconds=age))
    serving["processes"][2].update(observedAt=received, receivedAt=received)
    assert (action(doc) == "COMPLETE") is ok


@pytest.mark.parametrize("collection", ["members", "processes", "handshakes", "reservations"])
def test_f3_duplicate_evidence_is_never_collapsed(collection):
    doc = state(A["E1"], A["E2"])
    rb = doc["checkpoint"]["readback"]
    items = rb[collection] if collection in ("members", "reservations") else rb["serving"][collection]
    if not items:
        items.append(copy.deepcopy(rb["serving"]["handshakes"][0]) if collection == "handshakes" else None)
    items.append(copy.deepcopy(items[0]))
    assert action(doc) == "HOLD_DUPLICATE_EVIDENCE"


@pytest.mark.parametrize("pc", ["PC2", "PC3", "PC4"])
def test_f3_a3_waits_for_verified_staging_on_every_member(pc):
    doc = state(A["A2"])
    assert checker.recovery_action(doc)[:2] == ("RESUME_FORWARD", A["A3"])
    gen.row(doc, pc)["nodeObservedAt"] = None
    assert action(doc) == "HOLD_ANCHOR_STAGING_UNVERIFIED"
    gen.row(doc, pc).update(nodeObservedAt=gen.row(doc, "PC2" if pc != "PC2" else "PC3")["nodeObservedAt"],
                            stagedAnchorDigest=gen.h("half-staged"))
    assert action(doc) == "HOLD_FOREIGN_WRITER"


def test_f3_serving_is_gated_on_the_reviewed_binary_migration():
    doc = gen.proposal("t-binary")
    doc["servingBinaryMigration"] = {"status": "NOT_REVIEWED", "reviewRef": None}
    assert checker.evaluate(doc, SCHEMA) == ["AR-HOLD-REQUIRED"]


@pytest.mark.parametrize("site", checker.SITES)
def test_f3_inventory_covers_all_five_sites(site):
    doc = gen.proposal("t-inv")
    inv = doc["controlPlaneClient"]["processInventory"]
    inv[:] = [p for p in inv if p["site"] != site]
    pad = next(s for s in checker.SITES if s != site)
    inv.extend([{"site": pad, "processID": f"pad-{i}", "kind": "SERVICE"} for i in range(5 - len(inv))])
    assert "AR-PROCESS-INVENTORY" in checker.evaluate(gen.seal(doc), SCHEMA)


# ---------------------------------------------------------------- review R2 finding 3: freshness, inventory


def _complete() -> dict:
    doc = state(A["A7"], enroll=False)
    assert action(doc) == "COMPLETE"
    return doc


def _serving(doc: dict) -> dict:
    return doc["checkpoint"]["readback"]["serving"]


@pytest.mark.parametrize("age, ok", [(gen.CHALLENGE, True), (gen.CHALLENGE + 1, False), (-1, False)])
def test_r2f3_challenge_issuance_age_is_bounded(age, ok):
    """R2 bounded only the age of each answer, never the age of the challenge they answered."""
    doc = _complete()
    _serving(doc)["challengeIssuedAt"] = checker._iso(_AT - timedelta(seconds=age))
    assert action(doc) == ("COMPLETE" if ok else "HOLD_SERVING_EVIDENCE_INCOMPLETE")


def _evidence(doc: dict, target: str) -> tuple[dict, str, str]:
    """(record, responder-clock field, trusted CP receipt field) for one kind of challenged evidence."""
    rb = doc["checkpoint"]["readback"]
    return {"row": (rb["members"][1], "nodeObservedAt", "nodeReceivedAt"),
            "process": (rb["serving"]["processes"][3], "observedAt", "receivedAt"),
            "handshake": (rb["serving"]["handshakes"][2], "observedAt", "receivedAt"),
            "live-inventory": (rb["serving"]["liveInventory"], "observedAt", "receivedAt")}[target]


EVIDENCE_HOLD = {"row": "HOLD_ANCHOR_STAGING_UNVERIFIED", "process": "HOLD_SERVING_EVIDENCE_INCOMPLETE",
                 "handshake": "HOLD_SERVING_EVIDENCE_INCOMPLETE", "live-inventory": "HOLD_SERVING_EVIDENCE_INCOMPLETE"}


@pytest.mark.parametrize("target", list(EVIDENCE_HOLD))
@pytest.mark.parametrize("fault", ["received-before-issuance", "received-after-resume", "responder-clock-skewed",
                                   "other-challenge"])
def test_r2f3_freshness_is_judged_on_trusted_cp_issuance_and_receipt_times(target, fault):
    doc = _complete()
    record, observed, received = _evidence(doc, target)
    issued = checker._ts(_serving(doc)["challengeIssuedAt"])
    if fault == "received-before-issuance":
        record[observed] = record[received] = checker._iso(issued - timedelta(seconds=1))
    elif fault == "received-after-resume":
        record[observed] = record[received] = checker._iso(_AT + timedelta(seconds=1))
    elif fault == "responder-clock-skewed":
        skew = doc["advanceRenewal"]["clockSkewSeconds"]
        record[observed] = checker._iso(checker._ts(record[received]) - timedelta(seconds=skew + 1))
    else:
        record["nodeChallengeNonce" if target == "row" else "challengeNonce"] = "fixture-challenge-other"
    assert action(doc) == EVIDENCE_HOLD[target]


@pytest.mark.parametrize("target", list(EVIDENCE_HOLD))
def test_r2f3_responder_clock_within_the_skew_bound_is_accepted(target):
    doc = _complete()
    record, observed, received = _evidence(doc, target)
    record[observed] = checker._iso(checker._ts(record[received]) + timedelta(
        seconds=doc["advanceRenewal"]["clockSkewSeconds"]))
    assert action(doc) == "COMPLETE"


def test_r2f3_a_measured_window_tighter_than_the_cap_is_the_one_applied():
    doc = _complete()
    doc["measuredBudgets"]["observationFreshnessSeconds"] = 60
    record, observed, received = _evidence(doc, "process")
    record[observed] = record[received] = checker._iso(_AT - timedelta(seconds=61))
    assert action(doc) == "HOLD_SERVING_EVIDENCE_INCOMPLETE"
    record[observed] = record[received] = checker._iso(_AT - timedelta(seconds=60))
    assert action(doc) == "COMPLETE"


@pytest.mark.parametrize("key", list(checker.SERVING_WINDOWS))
def test_r2f3_serving_windows_are_measured_plan_inputs_under_contract_caps(key):
    doc = gen.proposal("t-window")
    doc["measuredBudgets"][key] = None
    assert checker.evaluate(doc, SCHEMA) == ["AR-HOLD-REQUIRED"]
    doc["measuredBudgets"][key] = checker.SERVING_WINDOWS[key] + 1
    assert checker.evaluate(doc, SCHEMA) == ["AR-SERVING-WINDOW"]


def test_r2f3_a_challenge_decides_once():
    doc = state(A["A3"], A["A4"])
    assert action(doc) == "RESUME_FORWARD"
    crashed, _ = checker.execute_resume(doc)
    assert crashed["checkpoint"]["consumedChallengeNonces"] == [gen.NONCE]
    assert checker.recovery_action(crashed) == ("HOLD_SERVING_EVIDENCE_INCOMPLETE", None, [], [])
    with pytest.raises(ValueError):
        checker.execute_resume(crashed)  # replaying the consumed evidence executes nothing
    assert action(checker.observe(crashed, "fixture-challenge-0002")) == "RESUME_FORWARD"


def _replica(site="delivery_worker", pid="delivery-3", kind="SERVICE", instance="delivery-3-i1") -> dict:
    return {"site": site, "processID": pid, "kind": kind, "instanceID": instance}


INVENTORY_CHURN = {
    "replica-started-live-only": lambda s: s["liveInventory"]["processes"].append(_replica()),
    "replica-started-with-readback": lambda s: (
        s["liveInventory"]["processes"].append(_replica()),
        s["processes"].append(dict(copy.deepcopy(s["processes"][1]), processID="delivery-3",
                                   instanceID="delivery-3-i1"))),
    "planned-process-stopped": lambda s: s["liveInventory"]["processes"].pop(2),
    "process-moved-site": lambda s: s["liveInventory"]["processes"][2].update(site="observer_worker"),
    "process-kind-changed": lambda s: s["liveInventory"]["processes"][5].update(kind="SERVICE"),
    "readback-from-unplanned-process": lambda s: s["processes"].append(
        dict(copy.deepcopy(s["processes"][0]), processID="observer-9", instanceID="observer-9-i1")),
    "readback-site-differs": lambda s: s["processes"][0].update(site="workspace_runtime"),
}


@pytest.mark.parametrize("position", ["A3-durable", "A6-in-flight", "complete"])
@pytest.mark.parametrize("churn", list(INVENTORY_CHURN))
def test_r2f3_live_inventory_churn_is_never_ignored(churn, position):
    """R2 visited only inventoried processes at settlement, so an unplanned live replica was ignored."""
    doc = {"A3-durable": lambda: state(A["A3"], enroll=False),
           "A6-in-flight": lambda: state(A["A5"], A["A6"], enroll=False),
           "complete": _complete}[position]()
    assert action(doc) in ("RESUME_FORWARD", "COMPLETE")
    INVENTORY_CHURN[churn](_serving(doc))
    assert checker.recovery_action(doc) == ("HOLD_PROCESS_INVENTORY_CHANGED", None, [], [])


def test_r2f3_a_restarted_process_needs_a_readback_from_its_live_instance():
    doc = _complete()
    live = next(p for p in _serving(doc)["liveInventory"]["processes"] if p["processID"] == "observer-1")
    live["instanceID"] = "observer-1-i2"  # restarted under the same ID after its trust readback was taken
    assert action(doc) == "HOLD_SERVING_EVIDENCE_INCOMPLETE"
    next(p for p in _serving(doc)["processes"] if p["processID"] == "observer-1")["instanceID"] = "observer-1-i2"
    assert action(doc) == "COMPLETE"


def test_r2f3_live_inventory_must_come_from_the_cp_registry():
    doc = _complete()
    _serving(doc)["liveInventory"]["source"] = "UNKNOWN"
    assert action(doc) == "HOLD_SERVING_EVIDENCE_INCOMPLETE"


def test_r2f3_duplicate_live_inventory_entries_are_never_collapsed():
    doc = _complete()
    procs = _serving(doc)["liveInventory"]["processes"]
    procs.append(copy.deepcopy(procs[0]))
    assert action(doc) == "HOLD_DUPLICATE_EVIDENCE"


# ---------------------------------------------------------------- F4 retry after a committed effect


def test_f4_drive_every_phase_with_crash_replay_and_duplicate_delivery():
    """From A1 durable to COMPLETE: at every phase, crash after the effects and before the journal
    write, re-decide, and run the decided step again. The second execution must mutate nothing."""
    doc = state(A["A1"])
    audits_seen = 0
    challenges = iter(f"fixture-challenge-{i:04d}" for i in range(2, 100))
    for _ in range(len(checker.PHASES)):
        act, phase, apply, ack = checker.recovery_action(doc)
        if act == "COMPLETE":
            break
        assert act == "RESUME_FORWARD", act
        crashed, mutations = checker.execute_resume(doc)
        ops = {op["opID"]: op for op in checker.expected_manifest(doc)["operations"]}
        assert set(mutations) == {o for o in apply if ops[o]["kind"] != "SETTLE"}
        # The executor consumed the challenge it acted on: the same evidence decides nothing again.
        assert checker.recovery_action(crashed)[0] == "HOLD_SERVING_EVIDENCE_INCOMPLETE"
        crashed = checker.observe(crashed, next(challenges))
        # Re-decide after the crash: everything that landed is acknowledged, nothing re-applied.
        again = checker.recovery_action(crashed)
        assert again[:2] == ("RESUME_FORWARD", phase) and again[2] == []
        assert sorted(again[3]) == sorted(apply + ack)
        replay, second = checker.execute_resume(crashed)
        assert second == []
        assert replay["checkpoint"]["readback"] == crashed["checkpoint"]["readback"]
        audits_seen = sum(len(r["channelAudit"]) + len(r["policyJournal"])
                          for r in crashed["checkpoint"]["readback"]["members"])
        doc = checker.observe(checker.journal_durable(crashed), next(challenges))
    assert checker.recovery_action(doc)[0] == "COMPLETE"
    assert doc["checkpoint"]["lastDurablePhase"] == "E5_ENROLLMENT_SETTLED"
    rotation = 3
    assert audits_seen == rotation * 2 + 2  # one CAS + one policy audit per rotation, provision + policy for PC1
    for r in doc["checkpoint"]["readback"]["members"]:
        assert all(r["channelAudit"].count(e) == 1 for e in r["channelAudit"])
        assert all(e["manifestDigest"] == doc["operationManifest"]["digest"] for e in r["channelAudit"])


@pytest.mark.parametrize("phase", [A["A2"], A["A3"], A["A4"], A["A5"], A["A6"], A["E3"], A["E4"]])
def test_f4_crash_after_any_prefix_of_a_phase_applies_exactly_the_rest(phase):
    probe = state(checker.PHASES[checker.INDEX[phase] - 1], phase)
    ops = [op["opID"] for op in gen.manifest_ops(probe) if op["phase"] == phase]
    for k in range(len(ops) + 1):
        landed = set(ops[:k])
        doc = state(checker.PHASES[checker.INDEX[phase] - 1], phase, landed=lambda op: op["opID"] in landed)
        assert checker.recovery_action(doc) == ("RESUME_FORWARD", phase, ops[k:], ops[:k])


def test_f4_executor_refuses_an_operation_whose_preimage_moved():
    doc = state(A["A3"], A["A4"])
    gen.row(doc, "PC3")["channelVersion"] += 1  # concurrent writer advanced the row
    with pytest.raises(ValueError):  # decision is already HOLD; the executor never runs
        checker.execute_resume(doc)
    assert action(doc) == "HOLD_FOREIGN_WRITER"
    cas = gen.op_of(state(A["A3"], A["A4"]), A["A4"], "PC3")
    moved = state(A["A3"], A["A4"])
    gen.row(moved, "PC3")["channelVersion"] += 1
    assert checker.op_state(moved, cas) == checker.CONFLICT  # NODE-0034 analogue


@pytest.mark.parametrize("audit", [0, 2])
def test_f4_postimage_needs_exactly_one_audit_row(audit):
    doc = state(A["A3"], A["A4"], landed=gen.on(gen.ids("PC2")))
    op = gen.op_of(doc, A["A4"], "PC2")["opID"]
    gen.row(doc, "PC2")["channelAudit"] = [checker.audit_key(doc, op)] * audit
    assert action(doc) == "HOLD_FOREIGN_WRITER"


def test_f4_old_fingerprint_is_compared_when_the_version_is_unchanged():
    doc = state(A["A3"], A["A4"])
    gen.row(doc, "PC4")["channelCertificateSHA256"] = gen.h("swapped")
    assert action(doc) == "HOLD_FOREIGN_WRITER"


def test_f4_policy_bytes_not_just_the_floor_decide_commitment():
    doc = state(A["A4"], A["A5"], landed=gen.on(gen.ids("PC2")))
    assert checker.recovery_action(doc)[0] == "RESUME_FORWARD"
    gen.row(doc, "PC2")["installedPolicyDigest"] = gen.h("other-bytes")
    assert action(doc) == "HOLD_FOREIGN_WRITER"


@pytest.mark.parametrize("phase, pc", [(A["A4"], "PC2"), (A["A5"], "PC3"), (A["E1"], "PC1")])
def test_f4_effect_of_a_phase_never_marked_in_flight_is_a_foreign_writer(phase, pc):
    """With no phase in flight, the next phase's effect cannot be ours: it must not be acknowledged."""
    last = checker.PHASES[checker.INDEX[phase] - 1]
    doc = state(last)
    checker.apply_op(doc, gen.op_of(doc, phase, pc))
    assert action(doc) == "HOLD_FOREIGN_WRITER"


def test_f4_writer_fence_and_manifest_pin_are_required():
    doc = state(A["A4"], A["A5"])
    doc["checkpoint"]["readback"]["writerFence"] = None
    assert action(doc) == "HOLD_WRITER_FENCE"
    doc = state(A["A4"], A["A5"])
    doc["checkpoint"]["readback"]["journalManifestDigest"] = None
    assert action(doc) == "HOLD_MANIFEST_MISMATCH"


def test_f4_manifest_changes_when_any_frozen_input_changes():
    doc = base("t-manifest")
    pin = checker.manifest_pin(doc)
    for mutate in (lambda d: gen.member(d, "PC2")["counters"].update(channelVersionBefore=7, channelVersionAfter=8),
                   lambda d: gen.member(d, "PC3").update(endpoint="https://10.0.0.3:7444"),
                   lambda d: d["preservedEpoch"].update(epoch=gen.OTHER_EPOCH),
                   lambda d: d["trustTransition"].update(targetGeneration=3)):
        changed = copy.deepcopy(doc)
        mutate(changed)
        assert checker.manifest_pin(changed)["digest"] != pin["digest"]
        assert "AR-MANIFEST" in checker.evaluate(changed, SCHEMA)


def test_f4_manifest_sample_is_the_frozen_manifest_of_its_source():
    sample = load(gen.MANIFEST_SAMPLE_PATH)
    source = load(sample["sourcePlan"])
    assert sample["manifest"] == checker.expected_manifest(source)
    kinds = [op["kind"] for op in sample["manifest"]["operations"]]
    assert kinds.count("CHANNEL_CAS") == 3 and kinds.count("CP_CONTEXT_SWITCH") == len(gen.INVENTORY)
    cas = next(op for op in sample["manifest"]["operations"] if op["kind"] == "CHANNEL_CAS")
    assert cas["expectedVersion"] == cas["pre"]["channelVersion"] and cas["endpoint"].startswith("https://")
    assert cas["pre"]["channelCertificateSHA256"] and cas["post"]["channelCertificateSHA256"]


def _a1_in_flight(name: str = "t-a1", *, key: bool = True, outputs: bool = True, signed: int = 2) -> dict:
    """A1 (the ceremony) interrupted: journal at A0, A1 in flight with an UNKNOWN outcome."""
    doc = base(name) if outputs else gen.proposal(name)
    rb = gen.initial_readback(doc, gen.RESUME)
    rb["ceremonyLog"]["signed"] = rb["ceremonyLog"]["signed"][:signed]
    if not key:
        rb["custodyState"] = "NO_NEW_KEY"
    doc["checkpoint"] = gen.checkpoint(A["A0"], A["A1"], "UNKNOWN", gen.RESUME, rb)
    return doc


_AT = checker._ts(gen.RESUME)
FENCE_FAULTS = {
    "missing": lambda f: None,
    "token-transferred": lambda f: {**f, "token": "fence:fixture-other-writer"},
    "plan-transferred": lambda f: {**f, "holderPlanDigest": gen.h("other-plan")},
    "generation-advanced": lambda f: {**f, "generation": f["generation"] + 1},
    "generation-behind": lambda f: {**f, "generation": f["generation"] - 1},
    "read-stale": lambda f: {**f, "readAt": checker._iso(_AT - timedelta(seconds=gen.FRESHNESS + 1))},
    "read-after-resume": lambda f: {**f, "readAt": checker._iso(_AT + timedelta(seconds=1))},
    "read-unknown": lambda f: {**f, "readAt": None},
}


@pytest.mark.parametrize("key", [True, False], ids=["key-present", "no-key"])
@pytest.mark.parametrize("fault", FENCE_FAULTS)
def test_r2f4_interrupted_a1_decides_nothing_outside_the_live_fence(fault, key):
    """Review R2 finding 4 (high): A1 RESUME was returned before the live fence was compared."""
    doc = _a1_in_flight(key=key)
    assert action(doc) == ("RESUME_FORWARD" if key else "ABANDON_BEFORE_NEW_TRUST")
    rb = doc["checkpoint"]["readback"]
    rb["writerFence"] = FENCE_FAULTS[fault](rb["writerFence"])
    assert checker.recovery_action(doc) == ("HOLD_WRITER_FENCE", None, [], [])
    with pytest.raises(ValueError):  # not resumable: no deterministic re-signing outside the fence
        checker.execute_resume(doc)


def test_r2f4_fence_read_exactly_at_the_freshness_bound_is_held():
    doc = _a1_in_flight()
    doc["checkpoint"]["readback"]["writerFence"]["readAt"] = checker._iso(_AT - timedelta(seconds=gen.FRESHNESS))
    assert action(doc) == "RESUME_FORWARD"


@pytest.mark.parametrize("position", ["A4-in-flight", "A7-durable-complete", "E2-in-flight"])
@pytest.mark.parametrize("fault", ["missing", "generation-advanced", "read-stale"])
def test_r2f4_every_later_decision_also_requires_the_live_fence(position, fault):
    doc = {"A4-in-flight": lambda: state(A["A3"], A["A4"]),
           "A7-durable-complete": lambda: state(A["A7"], enroll=False),
           "E2-in-flight": lambda: state(A["E1"], A["E2"])}[position]()
    assert action(doc) in ("RESUME_FORWARD", "COMPLETE")
    rb = doc["checkpoint"]["readback"]
    rb["writerFence"] = FENCE_FAULTS[fault](rb["writerFence"])
    assert action(doc) == "HOLD_WRITER_FENCE"  # COMPLETE is not declared under a lost fence either


def test_r2f4_executor_refuses_to_sign_without_the_fence_even_if_told_to_resume(monkeypatch):
    doc = _a1_in_flight()
    doc["checkpoint"]["readback"]["writerFence"] = None
    monkeypatch.setattr(checker, "recovery_action", lambda d: ("RESUME_FORWARD", A["A1"], [], []))
    with pytest.raises(checker.ExecutorConflict):
        checker.execute_resume(doc)


@pytest.mark.parametrize("outputs", [True, False], ids=["outputs-recorded", "no-outputs"])
@pytest.mark.parametrize("log", [None, "empty", "zero-keys", "two-keys"])
def test_r2f4_interrupted_a1_with_a_key_needs_a_consistent_ceremony_log(outputs, log):
    """R2 skipped log validation when no outputs and no signed entries existed, then the executor
    dereferenced the absent log. Every such state is now a custody HOLD, never a resume."""
    doc = _a1_in_flight(outputs=outputs)
    rb = doc["checkpoint"]["readback"]
    rb["ceremonyLog"] = {None: None, "empty": {"caKeysCreated": 1, "signed": []},
                         "zero-keys": {"caKeysCreated": 0, "signed": rb["ceremonyLog"]["signed"]},
                         "two-keys": {"caKeysCreated": 2, "signed": rb["ceremonyLog"]["signed"]}}[log]
    want = "RESUME_FORWARD" if (outputs and log == "empty") else "HOLD_CUSTODY_UNRESOLVED"
    assert action(doc) == want
    if want != "RESUME_FORWARD":
        with pytest.raises(ValueError):
            checker.execute_resume(doc)


def test_r2f4_an_unrecorded_key_in_custody_never_matches_the_plan():
    doc = _a1_in_flight(outputs=False, signed=0)
    assert doc["newAuthority"]["caPublicKeySHA256"] is None
    assert action(doc) == "HOLD_CUSTODY_UNRESOLVED"


def test_f4_a1_resume_is_deterministic_re_signing():
    doc = load("fixtures/positive/p23-a1-in-flight-key-present-resume.json")
    first, signed = checker.execute_resume(doc)
    assert len(signed) == 3  # PC4, PC1 and the CP leaf were missing
    second, again = checker.execute_resume(first)
    assert again == []
    # Re-signing reproduces byte-identical leaves (Ed25519 is deterministic).
    rebuilt = gen.ceremony(gen.proposal("p23-a1-in-flight-key-present-resume"))
    assert [m["leafDER"] for m in rebuilt["members"]] == [m["leafDER"] for m in doc["members"]]


# ---------------------------------------------------------------- review R2: manifest-scoped identities


def _r2_op_id(plan_digest_value: str, op: dict) -> str:
    """The R2 derivation: pre-ceremony plan digest, phase, kind and target only."""
    return "op_" + checker.digest({"planDigest": plan_digest_value, "phase": op["phase"], "kind": op["kind"],
                                   "target": op["target"]})[:24]


def test_r2id_ceremony_outputs_that_differ_never_share_an_op_id():
    doc = base("t-ids")
    other = copy.deepcopy(doc)
    gen.member(other, "PC2")["plannedLeafSHA256"] = gen.h("another-ceremony-leaf")  # same frozen inputs
    assert checker.plan_digest(other) == checker.plan_digest(doc)
    mine, theirs = gen.op_of(doc, A["A3"], "PC2"), gen.op_of(other, A["A3"], "PC2")
    assert mine["post"] != theirs["post"]
    assert _r2_op_id(checker.plan_digest(doc), mine) == _r2_op_id(checker.plan_digest(other), theirs)  # R2 collided
    assert mine["opID"] != theirs["opID"]
    assert checker.manifest_pin(doc)["digest"] != checker.manifest_pin(other)["digest"]


def test_r2id_every_op_id_is_its_canonical_body_under_the_plan_digest():
    manifest = checker.expected_manifest(base("t-ids-body"))
    ids = [op["opID"] for op in manifest["operations"]]
    assert len(ids) == len(set(ids))
    for op in manifest["operations"]:
        body = {k: v for k, v in op.items() if k != "opID"}
        assert op["opID"] == checker.operation_id(manifest["planDigest"], body)


@pytest.mark.parametrize("position", ["in-flight", "durable"])
@pytest.mark.parametrize("journal", ["channelAudit", "policyJournal"])
def test_r2id_an_op_id_under_another_manifest_is_never_acknowledged(journal, position):
    phase = A["A4"] if journal == "channelAudit" else A["A5"]
    prev = checker.PHASES[checker.INDEX[phase] - 1]
    doc = state(prev, phase, landed=gen.on(gen.ids("PC2"))) if position == "in-flight" else state(phase)
    assert action(doc) == "RESUME_FORWARD"
    r = gen.row(doc, "PC2")
    r[journal] = [dict(e, manifestDigest=gen.h("other-manifest")) for e in r[journal]]
    assert action(doc) == "HOLD_FOREIGN_WRITER"


@pytest.mark.parametrize("journal", ["channelAudit", "policyJournal"])
def test_r2id_our_op_id_audited_under_another_manifest_blocks_even_at_the_preimage(journal):
    """The row is still at its exact preimage, but this opID was already audited under a different
    manifest: applying would double-use one idempotency identity, so it is a foreign writer."""
    phase = A["A4"] if journal == "channelAudit" else A["A5"]
    doc = state(checker.PHASES[checker.INDEX[phase] - 1], phase)
    op = gen.op_of(doc, phase, "PC3")
    assert op["opID"] in checker.recovery_action(doc)[2]
    gen.row(doc, "PC3")[journal] = [{"manifestDigest": gen.h("other-manifest"), "opID": op["opID"]}]
    assert action(doc) == "HOLD_FOREIGN_WRITER"


def test_r2id_audit_history_of_other_operations_is_not_confused_with_ours():
    doc = state(A["A3"], A["A4"])
    gen.row(doc, "PC3")["channelAudit"] = [{"manifestDigest": gen.h("earlier-plan"), "opID": "op_" + "a" * 24}]
    assert checker.recovery_action(doc)[2] == [op["opID"] for op in gen.manifest_ops(doc) if op["phase"] == A["A4"]]


def test_r2id_a_bare_op_id_is_not_an_audit_key():
    doc = state(A["A4"])
    r = gen.row(doc, "PC2")
    r["channelAudit"] = [e["opID"] for e in r["channelAudit"]]
    assert checker.evaluate(doc, SCHEMA) == ["AR-SCHEMA"]


# ---------------------------------------------------------------- F5 expiry and advance renewal


def _a4_in_flight(resume_at):
    return state(A["A3"], A["A4"], resume_at=resume_at)


def test_f5_policy_deadline_boundary_at_resume_time():
    # Remaining A4..E5 = 9 phases x 600 s; margin 660 s; policy notAfter 2026-11-20T12:00Z; lead 86400 s.
    remaining = 600 * len(checker.PHASES[checker.INDEX[A["A4"]]:])
    assert remaining == 5400
    limit = checker._ts("2026-11-20T12:00:00Z") - timedelta(seconds=86400 + remaining + 660)
    assert action(_a4_in_flight(checker._iso(limit))) == "RESUME_FORWARD"
    assert action(_a4_in_flight(checker._iso(limit + timedelta(seconds=1)))) == "HOLD_DEADLINE_INSUFFICIENT"


def test_f5_leaf_deadline_is_checked_from_the_actual_certificate():
    doc = gen.proposal("t-leafdl")
    doc["newAuthority"]["leafValidity"]["notAfter"] = "2026-11-21T12:00:00Z"
    doc = gen.ceremony(gen.seal(doc))
    for m in doc["members"]:
        m["plannedPolicy"]["notAfter"] = "2026-11-20T00:00:00Z"
    doc = gen.seal(doc)
    # Leaf lead is 259200 s: at 2026-11-18T14:00Z the leaf has ~3d-2h-11m left after the work.
    assert action(gen.at_state(doc, A["A3"], A["A4"])) == "HOLD_DEADLINE_INSUFFICIENT"
    cert = checker.load_certificate(gen.member(doc, "PC2")["leafDER"])
    assert checker._iso(cert.not_valid_after_utc) == "2026-11-21T12:00:00Z"


def test_f5_successor_must_be_valid_at_use_time():
    doc = load("fixtures/positive/p33-successor-not-yet-valid-hold.json")
    assert action(doc) == "HOLD_DEADLINE_INSUFFICIENT"
    doc["checkpoint"]["resumeAt"] = "2026-11-18T15:00:00Z"
    doc = checker.observe(doc, "fixture-challenge-0002")  # re-read everything, the fence included
    assert action(doc) == "RESUME_FORWARD"


@pytest.mark.parametrize("field, value", [
    ("newAuthority.notBefore", "2026-11-18T14:00:01Z"),
    ("newAuthority.leafValidity.notBefore", "2026-11-18T14:00:01Z"),
])
def test_f5_each_not_before_is_checked_independently(field, value):
    """Each validity start is its own condition; one may not mask the other."""
    doc = _a4_in_flight(gen.RESUME)
    assert checker.deadline_insufficient(doc, A["A4"]) is False
    target = doc
    *path, last = field.split(".")
    for part in path:
        target = target[part]
    target[last] = value
    assert checker.deadline_insufficient(doc, A["A4"]) is True


ADV = {"mode": "ADVANCE_RENEWAL", "enroll": False}


def test_f5_advance_overlap_deadline_boundary():
    # Remaining A5..A7 = 3 x 600 s + 660 s must end by mustEndBy 2026-11-19T06:00Z.
    limit = checker._ts("2026-11-19T06:00:00Z") - timedelta(seconds=1800 + 660)
    ok = gen.at_state(base("t-adv", **ADV), A["A4"], resume_at=checker._iso(limit))
    late = gen.at_state(base("t-adv", **ADV), A["A4"], resume_at=checker._iso(limit + timedelta(seconds=1)))
    assert action(ok) == "RESUME_FORWARD"
    assert action(late) == "HOLD_DEADLINE_INSUFFICIENT"


def test_f5_advance_dual_stages_both_anchors_then_retires_the_prior():
    doc = load("fixtures/positive/p36-advance-dual-complete-retired.json")
    tt = doc["trustTransition"]
    assert tt["stagedAnchorBundle"] == sorted([doc["priorAuthority"]["caCertificateSHA256"],
                                               doc["newAuthority"]["caCertificateSHA256"]])
    assert tt["finalAnchorBundle"] == [doc["newAuthority"]["caCertificateSHA256"]]
    final = checker.anchor_digest(tt["finalAnchorBundle"])
    rb = doc["checkpoint"]["readback"]
    assert all(r["stagedAnchorDigest"] == final for r in rb["members"])
    assert all(p["loadedAnchorDigest"] == final for p in rb["serving"]["processes"])
    # Without the retirement proof on one process, COMPLETE is refused.
    rb["serving"]["processes"][0]["loadedAnchorDigest"] = checker.anchor_digest(tt["stagedAnchorBundle"])
    assert action(doc) == "HOLD_FOREIGN_WRITER"


def test_f5_advance_retire_before_its_phase_is_a_foreign_writer():
    doc = gen.at_state(base("t-early", **ADV), A["A4"])
    final = checker.anchor_digest(doc["trustTransition"]["finalAnchorBundle"])
    gen.row(doc, "PC3")["stagedAnchorDigest"] = final
    assert action(doc) == "HOLD_FOREIGN_WRITER"


def test_f5_terminal_checker_still_rejects_staging_the_expired_ca():
    doc = base("t-term")
    doc["trustTransition"]["stagedAnchorBundle"] = sorted([doc["priorAuthority"]["caCertificateSHA256"],
                                                           doc["newAuthority"]["caCertificateSHA256"]])
    assert checker.evaluate(gen.seal(doc), SCHEMA) == ["AR-TERMINAL-ANCHOR"]


@pytest.mark.parametrize("prior_not_after, ok", [
    ("2026-12-18T12:00:00Z", True),   # exactly the 30-day successor lead
    ("2026-12-18T11:59:59Z", False),
])
def test_f5_advance_must_start_with_the_successor_lead_remaining(prior_not_after, ok):
    doc = gen.proposal("t-lead", prior_not_after=prior_not_after, **ADV)
    assert (checker.evaluate(doc, SCHEMA) == []) is ok


# ---------------------------------------------------------------- review R2 finding 5: validity where relied upon


POLICY_END = checker._ts("2026-11-20T12:00:00Z")  # every planned policy's notAfter in the fixtures
MARGIN = timedelta(seconds=660)  # safety 630 s + clock skew 30 s


def _settled_at(at) -> dict:
    return gen.at_state(base("t-settled", enroll=False), A["A7"], resume_at=checker._iso(at))


@pytest.mark.parametrize("delta, want", [(-1, "COMPLETE"), (0, "HOLD_VALIDITY_LAPSED")])
def test_r2f5_complete_is_judged_on_validity_at_the_final_observation(delta, want):
    """R2 returned COMPLETE from the journal before evaluating credential or policy validity."""
    doc = _settled_at(POLICY_END - MARGIN + timedelta(seconds=delta))
    assert action(doc) == want


@pytest.mark.parametrize("field, value", [
    ("newAuthority.notBefore", "2026-11-18T14:00:01Z"),
    ("newAuthority.notAfter", "2026-11-18T14:11:00Z"),
    ("newAuthority.leafValidity.notBefore", "2026-11-18T14:00:01Z"),
    ("newAuthority.leafValidity.notAfter", "2026-11-18T14:11:00Z"),
    ("PC3.plannedPolicy.notBefore", "2026-11-18T14:00:01Z"),
    ("PC3.plannedPolicy.notAfter", "2026-11-18T14:11:00Z"),
])
def test_r2f5_each_settled_dependency_is_checked_independently(field, value):
    doc = _settled_at(_AT)
    assert checker.validity_lapsed(doc, _AT) is False
    head, *path, last = field.split(".")
    target = gen.member(doc, head) if head.startswith("PC") else doc[head]
    for part in path:
        target = target[part]
    target[last] = value
    assert checker.validity_lapsed(doc, _AT) is True


def test_r2f5_a_policy_must_be_valid_when_it_is_published():
    """R2 checked policy end times only."""
    doc = state(A["A4"])
    assert checker.deadline_insufficient(doc, A["A5"]) is False
    gen.member(doc, "PC4")["plannedPolicy"]["notBefore"] = "2026-11-18T14:00:01Z"
    assert checker.deadline_insufficient(doc, A["A5"]) is True
    assert action(doc) == "HOLD_DEADLINE_INSUFFICIENT"


def test_r2f5_handoff_rechecks_validity_at_handoff_time():
    raw = (checker.CONTRACT_DIR / gen.HANDOFF_SOURCE).read_bytes()
    doc = json.loads(raw)
    kw = {"hosts": gen.HANDOFF_HOSTS, "control_plane_host": gen.HANDOFF_CP_HOST}
    handoff = checker.enrollment_handoff(doc, gen.HANDOFF_SOURCE, raw, **kw)
    assert handoff["validity"]["evaluatedAt"] == doc["checkpoint"]["resumeAt"]
    assert handoff["validity"]["validUntil"] == "2026-11-20T12:00:00Z"
    late = checker._iso(POLICY_END - MARGIN)  # after a pause: the same settled plan, handed off later
    with pytest.raises(ValueError, match="validity"):
        checker.enrollment_handoff(doc, gen.HANDOFF_SOURCE, raw, at=late, **kw)
    ok = checker._iso(POLICY_END - MARGIN - timedelta(seconds=1))
    assert checker.enrollment_handoff(doc, gen.HANDOFF_SOURCE, raw, at=ok, **kw)["validity"]["evaluatedAt"] == ok
    with pytest.raises(ValueError, match="predate"):
        checker.enrollment_handoff(doc, gen.HANDOFF_SOURCE, raw, at="2026-11-18T13:59:59Z", **kw)


def _advance(last=A["A3"], flight=A["A4"], *, prior_leaf_not_after=None, holder="PC4"):
    doc = gen.proposal("t-adv-dep", **ADV)
    if prior_leaf_not_after is not None:  # re-issue one still-serving prior leaf with an earlier end
        (ca_key, ca_cert), world = gen.prior_ca(doc)
        if holder == "cp":
            cp = doc["controlPlaneClient"]
            cp["priorLeafDER"] = gen.b64(gen.der(gen.make_leaf(
                ca_key, ca_cert, gen.key("cp-client").public_key(), cp["spiffeURI"], None, client=True,
                not_before=world["leafNotBefore"], not_after=prior_leaf_not_after, label="prior-cp-leaf-short")))
        else:
            m = gen.member(doc, holder)
            m["priorLeafDER"] = gen.b64(gen.der(gen.make_leaf(
                ca_key, ca_cert, gen.key(f"{holder}-node").public_key(), m["spiffeURI"], m["address"],
                not_before=world["leafNotBefore"], not_after=prior_leaf_not_after, label="prior-leaf-short")))
            next(r for r in doc["existingNodeRows"]["rows"] if r["nodeID"] == m["nodeID"])[
                "channelCertificateSHA256"] = checker.prior_leaf_sha(m)
        doc = gen.seal(doc)
    return gen.at_state(gen.a1_durable(gen.ceremony(doc)), last, flight)


@pytest.mark.parametrize("holder", ["PC2", "PC4", "cp"])
def test_r2f5_advance_renewal_budgets_still_serving_prior_leaves(holder):
    """R2 budgeted the prior CA but not the prior leaves still serving until the rotation settles."""
    assert action(_advance()) == "RESUME_FORWARD"
    short = _advance(prior_leaf_not_after="2026-11-18T14:30:00Z", holder=holder)
    assert checker.evaluate(short, SCHEMA) == ["AR-RECOVERY-MISMATCH"]  # consistent plan, different decision
    assert action(short) == "HOLD_DEADLINE_INSUFFICIENT"


def test_r2f5_advance_renewal_needs_validity_readback_of_the_installed_prior_policy():
    doc = _advance()
    gen.row(doc, "PC2")["installedPolicyNotAfter"] = None
    assert action(doc) == "HOLD_SERVING_EVIDENCE_INCOMPLETE"
    doc = _advance()
    gen.row(doc, "PC2")["installedPolicyNotAfter"] = "2026-11-18T14:30:00Z"
    assert action(doc) == "HOLD_DEADLINE_INSUFFICIENT"
    doc = _advance()
    gen.row(doc, "PC2")["nodeChallengeNonce"] = "fixture-challenge-other"  # validity read under no challenge
    # Never a resume. The staging gate holds the stale row first; the dependency rule repeats it on its own.
    assert action(doc) == "HOLD_ANCHOR_STAGING_UNVERIFIED"


def test_r2f5_a_replaced_prior_policy_is_no_longer_a_dependency():
    doc = gen.at_state(base("t-adv-after", **ADV), A["A5"])
    for r in doc["checkpoint"]["readback"]["members"]:
        assert r["installedPolicyNotAfter"] == "2026-11-20T12:00:00Z"  # the planned policy, read back
    assert action(doc) == "RESUME_FORWARD"


def test_r2f5_a_committed_publication_reads_back_the_planned_policy_validity():
    doc = state(A["A5"])
    gen.row(doc, "PC3")["installedPolicyNotAfter"] = "2026-11-21T12:00:00Z"
    assert action(doc) == "HOLD_FOREIGN_WRITER"


@pytest.mark.parametrize("mode, cutover, value, code", [
    ("ADVANCE_RENEWAL", "DUAL_ANCHOR_OVERLAP", None, "AR-HOLD-REQUIRED"),
    ("ADVANCE_RENEWAL", "QUIESCED", "fixture:runtime/x", "AR-MODE"),
    ("TERMINAL_REPLACEMENT", None, "fixture:runtime/x", "AR-MODE"),
])
def test_r2f5_dual_overlap_is_conditional_on_independent_runtime_evidence(mode, cutover, value, code):
    doc = gen.proposal("t-overlap", mode=mode, enroll=False, cutover=cutover)
    assert checker.evaluate(doc, SCHEMA) == []
    doc["trustTransition"]["overlapRuntimeEvidenceRef"] = value
    assert checker.evaluate(doc, SCHEMA) == [code]


# ---------------------------------------------------------------- handoff (medium finding 6)


def test_handoff_is_scoped_as_four_member_migration_evidence():
    from tools.five_node_lab_preflight import validate_five_node_inventory

    handoff = load(gen.HANDOFF_PATH)
    plan_bytes = (checker.CONTRACT_DIR / handoff["sourcePlan"]).read_bytes()
    assert handoff["sourcePlanSHA256"] == hashlib.sha256(plan_bytes).hexdigest()
    inventory = handoff["fiveNodeInventory"]
    assert validate_five_node_inventory(inventory) is inventory
    assert handoff["acceptance"]["scope"] == "FOUR_MEMBER_MIGRATION"
    assert handoff["acceptance"]["fiveNodeReadiness"] == "NOT_ESTABLISHED"
    assert handoff["acceptance"]["excludedFromThisAdmission"] == ["PC5"]
    colocated = [n for n in inventory["nodes"] if n["coLocatedWithControlPlane"]]
    assert len(inventory["nodes"]) == 4 and len(colocated) == 1
    assert colocated[0]["nodeId"] == gen.NODE["PC3"] and colocated[0]["exclusionReason"] == "cp-host-colocation"
    assert handoff["activation"] == "NOT_AUTHORIZED"


@pytest.mark.parametrize("rel", [
    "fixtures/positive/p14-pc1-first-enrollment-ready.json",
    "fixtures/positive/p16-e3-channel-missing-apply.json",
    "fixtures/positive/p29-stale-handshake-hold.json",
    "fixtures/rejection/r09-pc1-copies-pc4-identity.json",
])
def test_handoff_refuses_unsettled_or_rejected_plans(rel):
    raw = (checker.CONTRACT_DIR / rel).read_bytes()
    with pytest.raises(ValueError):
        checker.enrollment_handoff(json.loads(raw), rel, raw, hosts=gen.HANDOFF_HOSTS,
                                   control_plane_host=gen.HANDOFF_CP_HOST)
