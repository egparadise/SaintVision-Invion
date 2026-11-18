"""Generate the PROPOSED FLEET5 authority-replacement fixtures and expectations.

Writes static JSON under contracts/proposed/fleet5-authority-replacement/. The
committed files are the reviewable artifact; tests regenerate in memory and fail
on drift. Synthetic fixtures use sha256("fixture:<label>") placeholders and
synthetic IDs/addresses, never fleet values. The single instances/ document is
the real Nov18 fleet plan in HOLD, with every unknown left null.

    python tools/generate_fleet5_authority_replacement_fixtures.py [--check]
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # script mode: allow `from tools import ...`
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "contracts" / "proposed" / "fleet5-authority-replacement"


def h(label: str) -> str:
    return hashlib.sha256(f"fixture:{label}".encode()).hexdigest()


def nid(tag: str) -> str:
    return "nod_" + "0" * 22 + tag


TENANT = "00000000-0000-4000-8000-0000000000a1"
EPOCH = "00000000-0000-4000-8000-0000000000e1"
OTHER_EPOCH = "00000000-0000-4000-8000-0000000000e2"
PCS = {"PC2": "0PC2", "PC3": "0PC3", "PC4": "0PC4"}
ROTATION_FLOOR = {"PC2": 2, "PC3": 2, "PC4": 5}
ROTATION_CHANNEL = {"PC2": 1, "PC3": 1, "PC4": 3}


def node_uri(tenant: str, node: str, epoch: str) -> str:
    return f"spiffe://saintvision.ai/tenant/{tenant}/node/{node}/epoch/{epoch}"


def cp_uri(tenant: str, epoch: str) -> str:
    return f"spiffe://saintvision.ai/tenant/{tenant}/control-plane/epoch/{epoch}"


def rotation(pc: str, address: str, account: str) -> dict:
    node = nid(PCS[pc])
    return {
        "pc": pc,
        "kind": "ROTATION",
        "nodeID": node,
        "account": account,
        "address": address,
        "spiffeURI": node_uri(TENANT, node, EPOCH),
        "nodePublicKeySHA256": h(f"{pc}-node-key"),
        "priorNodePublicKeySHA256": h(f"{pc}-node-key"),
        "plannedLeafSHA256": h(f"{pc}-leaf-new-ca"),
        "counters": {
            "channelVersionBefore": ROTATION_CHANNEL[pc],
            "channelVersionAfter": ROTATION_CHANNEL[pc] + 1,
            "policyFloorBefore": ROTATION_FLOOR[pc],
            "policyVersionAfter": ROTATION_FLOOR[pc] + 1,
        },
    }


def enrollment() -> dict:
    node = nid("0PC1")
    return {
        "pc": "PC1",
        "kind": "NEW_ENROLLMENT",
        "nodeID": node,
        # Same account name as PC4 on purpose: an account/host name is never identity.
        "account": "inviz",
        "address": "10.0.0.1",
        "spiffeURI": node_uri(TENANT, node, EPOCH),
        "nodePublicKeySHA256": h("PC1-node-key-fresh"),
        "priorNodePublicKeySHA256": None,
        "plannedLeafSHA256": h("PC1-leaf-new-ca"),
        "counters": {
            "channelVersionBefore": 0,
            "channelVersionAfter": 1,
            "policyFloorBefore": 0,
            "policyVersionAfter": 1,
        },
    }


def base() -> dict:
    return {
        "schema": "fleet5-authority-replacement-plan:1",
        "planID": "ARP-20261118-fixture-base",
        "status": "PROPOSED",
        "activation": "NOT_AUTHORIZED",
        "fixture": True,
        "observedAt": "2026-11-18T12:00:00Z",
        "tenantID": TENANT,
        "projectID": "prj_" + "0" * 24 + "P1",
        "preservedEpoch": {"epoch": EPOCH, "source": "DB_READBACK", "readbackSHA256": h("epoch-readback")},
        "terminalAuthority": {
            "caCertificateSHA256": h("terminal-ca-cert"),
            "caPublicKeySHA256": h("terminal-ca-key"),
            "subjectCommonName": "SaintVision LAN pilot CA",
            "notAfter": "2026-11-14T07:15:30Z",
            "state": "CA_TERMINAL",
            "usage": "REFERENCE_ONLY",
        },
        "newAuthority": {
            "caCertificateSHA256": h("new-ca-cert"),
            "caPublicKeySHA256": h("new-ca-key"),
            "subjectCommonName": "SaintVision FLEET5 authority 2026-11 R1",
            "keyAlgorithm": "Ed25519",
            "keyGeneratedFresh": True,
            "crossSignedByTerminal": False,
            "pathLength": 0,
            "notBefore": "2026-11-18T12:00:00Z",
            "notAfter": "2027-11-18T12:00:00Z",
            "custody": {
                "holder": "ROOT_OFFLINE_OPERATOR",
                "privateMaterialInRepository": False,
                "custodyEvidenceRef": "fixture:custody/new-ca",
            },
            "trustAuthorization": {"decisionRef": "fixture:decision/new-trust", "authorizedBy": "fixture-root-operator"},
            "anchorBundle": [h("new-ca-cert")],
        },
        "advanceRenewal": {
            "caLifetimeSeconds": 31536000,
            "caSuccessorLeadSeconds": 2592000,
            "caWarningLeadSeconds": 3888000,
            "leafLifetimeSeconds": 518400,
            "leafRenewalLeadSeconds": 259200,
            "policyLifetimeSeconds": 172800,
            "policyRenewalLeadSeconds": 86400,
            "overlapSeconds": 14400,
            "normalBudgetSeconds": 7200,
            "caSuccessorBudgetSeconds": 86400,
            "safetySeconds": 630,
            "clockSkewSeconds": 30,
        },
        "controlPlaneClient": {
            "spiffeURI": cp_uri(TENANT, EPOCH),
            "keyContinuity": "RETAINED",
            "publicKeySHA256": h("cp-client-key"),
            "priorPublicKeySHA256": h("cp-client-key"),
            "plannedLeafSHA256": h("cp-client-leaf-new-ca"),
            "contextSites": [
                "observer_worker",
                "delivery_worker",
                "workspace_runtime",
                "build_product_runtime",
                "storage_check_collector",
            ],
        },
        "roleKeys": [
            {
                "role": "LAUNCH_SIGNER",
                "publicKeySHA256": h("launch-signer-key"),
                "disposition": "RETAINED",
                "custodyEvidenceRef": "fixture:custody/launch-signer",
            }
        ],
        "members": [
            rotation("PC2", "10.0.0.2", "saintvision-invion"),
            rotation("PC3", "10.0.0.3", "saintvision-invion3"),
            rotation("PC4", "10.0.0.4", "inviz"),
            enrollment(),
        ],
        "existingNodeRows": {
            "source": "DB_READBACK",
            "nodeIDs": [nid("0PC2"), nid("0PC3"), nid("0PC4"), nid("RTR1"), nid("RTR2")],
            "publicKeySHA256s": [
                h("PC2-node-key"),
                h("PC3-node-key"),
                h("PC4-node-key"),
                h("RTR1-node-key"),
                h("RTR2-node-key"),
            ],
        },
        "checkpoint": {
            "lastDurablePhase": None,
            "inFlightPhase": None,
            "inFlightOutcome": None,
            "readback": {"dbAvailable": True, "epoch": EPOCH, "custodyState": "NOT_READ", "members": []},
            "expectedRecoveryAction": "NOT_STARTED",
            "expectedResumePhase": None,
        },
    }


def member(doc: dict, pc: str) -> dict:
    return next(m for m in doc["members"] if m["pc"] == pc)


def row(doc: dict, pc: str, *, version: int | None = None, cert: str | None = None, floor: int | None = None,
        present: bool = True) -> dict:
    m = member(doc, pc)
    c = m["counters"]
    return {
        "nodeID": m["nodeID"],
        "rowPresent": present,
        "channelVersion": c["channelVersionBefore"] if version is None else version,
        "channelCertificateSHA256": h(f"{pc}-leaf-terminal-ca") if cert is None else cert,
        "policyFloor": c["policyFloorBefore"] if floor is None else floor,
    }


def settled_row(doc: dict, pc: str) -> dict:
    m = member(doc, pc)
    return row(doc, pc, version=m["counters"]["channelVersionAfter"], cert=m["plannedLeafSHA256"],
               floor=m["counters"]["policyVersionAfter"])


def interrupted(doc: dict, last: str | None, flight: str | None, outcome: str | None, custody: str,
                rows: list[dict], action: str, resume: str | None = None, db: bool = True,
                epoch: str | None = EPOCH) -> dict:
    doc["checkpoint"] = {
        "lastDurablePhase": last,
        "inFlightPhase": flight,
        "inFlightOutcome": outcome,
        "readback": {"dbAvailable": db, "epoch": epoch, "custodyState": custody, "members": rows},
        "expectedRecoveryAction": action,
        "expectedResumePhase": resume,
    }
    return doc


ROT = ("PC2", "PC3", "PC4")


def positives() -> dict[str, tuple[str, dict]]:
    out: dict[str, tuple[str, dict]] = {}

    def add(name, why, doc):
        doc["planID"] = f"ARP-20261118-{name}"[:53]
        out[name] = (why, doc)

    add("p01-proposed-not-started", "Complete PROPOSED plan: 3 rotations + PC1 enrollment, nothing started.", base())

    d = base()
    add("p02-a4-partial-cas-resume",
        "CAS applied on PC2 only, outcome UNKNOWN; resume A4 with the same expected versions.",
        interrupted(d, "A3_ROTATION_LEAVES_ISSUED", "A4_CHANNEL_CAS", "UNKNOWN", "NEW_KEY_PRESENT_MATCHES_PLAN",
                    [row(d, "PC2", version=2, cert=member(d, "PC2")["plannedLeafSHA256"]), row(d, "PC3"), row(d, "PC4")],
                    "RESUME_FORWARD", "A4_CHANNEL_CAS"))

    d = base()
    add("p03-a1-unknown-no-key-abandon",
        "New-CA generation interrupted; custody readback proves no new key exists, so abandoning is safe.",
        interrupted(d, "A0_PREFLIGHT_READBACK", "A1_NEW_TRUST_AUTHORIZED", "UNKNOWN", "NO_NEW_KEY",
                    [row(d, pc) for pc in ROT], "ABANDON_BEFORE_NEW_TRUST"))

    d = base()
    add("p04-e2-enrollment-resume",
        "Rotation settled; PC1 admission outcome UNKNOWN but DB shows the planned row/leaf; resume E2.",
        interrupted(d, "E1_ENROLLMENT_AUTHORIZED", "E2_ENROLLMENT_ADMITTED", "UNKNOWN",
                    "NEW_KEY_PRESENT_MATCHES_PLAN",
                    [settled_row(d, pc) for pc in ROT]
                    + [row(d, "PC1", version=1, cert=member(d, "PC1")["plannedLeafSHA256"], floor=0)],
                    "RESUME_FORWARD", "E2_ENROLLMENT_ADMITTED"))

    d = base()
    add("p05-complete", "Every phase durable, every counter at its planned value.",
        interrupted(d, "E3_ENROLLMENT_SETTLED", None, None, "NEW_KEY_PRESENT_MATCHES_PLAN",
                    [settled_row(d, pc) for pc in ("PC2", "PC3", "PC4", "PC1")], "COMPLETE"))

    d = base()
    add("p06-db-unavailable-hold", "Interrupted after A5 while the DB cannot be read: HOLD, no blind replay.",
        interrupted(d, "A5_POLICY_PUBLISHED", None, None, "NEW_KEY_PRESENT_MATCHES_PLAN", [],
                    "HOLD_DB_READBACK_REQUIRED", db=False, epoch=None))

    d = base()
    add("p07-custody-mismatch-hold", "New CA key in custody differs from the plan after A2: HOLD.",
        interrupted(d, "A2_ANCHOR_STAGED", None, None, "NEW_KEY_PRESENT_MISMATCH",
                    [row(d, pc) for pc in ROT], "HOLD_CUSTODY_UNRESOLVED"))

    d = base()
    d["members"] = [m for m in d["members"] if m["kind"] == "ROTATION"]
    add("p08-rotation-only-complete",
        "Rotation cohort completes without any enrollment: the two tracks are separable.",
        interrupted(d, "A7_ROTATION_SETTLED", None, None, "NEW_KEY_PRESENT_MATCHES_PLAN",
                    [settled_row(d, pc) for pc in ROT], "COMPLETE"))

    d = base()
    add("p09-durable-cas-undone-hold",
        "Journal says A4 durable but PC3 is back at its old version (restore/foreign writer): HOLD.",
        interrupted(d, "A4_CHANNEL_CAS", None, None, "NEW_KEY_PRESENT_MATCHES_PLAN",
                    [row(d, "PC2", version=2, cert=member(d, "PC2")["plannedLeafSHA256"]), row(d, "PC3"),
                     row(d, "PC4", version=4, cert=member(d, "PC4")["plannedLeafSHA256"])],
                    "HOLD_FOREIGN_WRITER"))

    d = base()
    add("p10-enrollment-before-rotation-hold",
        "A PC1 row exists while rotation is only at A5: ordering violation, HOLD.",
        interrupted(d, "A5_POLICY_PUBLISHED", None, None, "NEW_KEY_PRESENT_MATCHES_PLAN",
                    [settled_row(d, pc) for pc in ROT]
                    + [row(d, "PC1", version=1, cert=member(d, "PC1")["plannedLeafSHA256"], floor=0)],
                    "HOLD_ENROLLMENT_BEFORE_ROTATION_SETTLED"))

    d = base()
    add("p11-epoch-diverged-hold", "DB control epoch differs from the preserved epoch: HOLD, never adopt it.",
        interrupted(d, "A3_ROTATION_LEAVES_ISSUED", None, None, "NEW_KEY_PRESENT_MATCHES_PLAN",
                    [row(d, pc) for pc in ROT], "HOLD_EPOCH_DIVERGED", epoch=OTHER_EPOCH))

    d = base()
    add("p12-floor-above-plan-hold", "PC2 floor is above the planned P: a foreign policy publication, HOLD.",
        interrupted(d, "A5_POLICY_PUBLISHED", "A6_CP_CONTEXT_SWITCH", "UNKNOWN", "NEW_KEY_PRESENT_MATCHES_PLAN",
                    [row(d, "PC2", version=2, cert=member(d, "PC2")["plannedLeafSHA256"], floor=4)]
                    + [settled_row(d, pc) for pc in ("PC3", "PC4")],
                    "HOLD_POLICY_ABOVE_PLAN"))

    d = base()
    add("p13-unplanned-row-hold", "A Node row that is neither planned nor pre-existing appeared: HOLD.",
        interrupted(d, "A7_ROTATION_SETTLED", "E1_ENROLLMENT_AUTHORIZED", "UNKNOWN",
                    "NEW_KEY_PRESENT_MATCHES_PLAN",
                    [settled_row(d, pc) for pc in ROT]
                    + [{"nodeID": nid("XTRA"), "rowPresent": True, "channelVersion": 1,
                        "channelCertificateSHA256": h("unknown-leaf"), "policyFloor": 1}],
                    "HOLD_UNPLANNED_ROW"))

    d = base()
    add("p14-pc1-first-enrollment-ready",
        "Concrete PC1 first enrollment: rotation settled, no PC1 row yet, fresh unique identity; next is E1.",
        interrupted(d, "A7_ROTATION_SETTLED", None, None, "NEW_KEY_PRESENT_MATCHES_PLAN",
                    [settled_row(d, pc) for pc in ROT], "RESUME_FORWARD", "E1_ENROLLMENT_AUTHORIZED"))
    return out


def rejections() -> dict[str, tuple[str, list[str], dict]]:
    out: dict[str, tuple[str, list[str], dict]] = {}

    def add(name, why, codes, doc):
        doc["planID"] = f"ARP-20261118-{name}"[:53]
        out[name] = (why, codes, doc)

    d = base(); d["newAuthority"]["caCertificateSHA256"] = d["terminalAuthority"]["caCertificateSHA256"]
    d["newAuthority"]["anchorBundle"] = []
    add("r01-terminal-ca-reused", "New CA certificate is the expired CA.", ["AR-TERMINAL-REUSE"], d)

    d = base(); d["newAuthority"]["caPublicKeySHA256"] = d["terminalAuthority"]["caPublicKeySHA256"]
    add("r02-terminal-key-reissued", "New CA re-uses the expired CA key (same-CA renewal in disguise).",
        ["AR-TERMINAL-REUSE"], d)

    d = base(); d["newAuthority"]["subjectCommonName"] = "saintvision lan pilot ca "
    add("r03-terminal-subject-reused", "New CA subject equals the expired CA subject.", ["AR-TERMINAL-REUSE"], d)

    d = base(); d["newAuthority"]["anchorBundle"].append(d["terminalAuthority"]["caCertificateSHA256"])
    add("r04-terminal-in-anchor-bundle", "Expired CA kept as a trust anchor.", ["AR-TERMINAL-ANCHOR"], d)

    d = base(); d["newAuthority"]["crossSignedByTerminal"] = True
    add("r05-cross-signed-by-terminal", "New CA chained to the expired CA.", ["AR-SCHEMA"], d)

    d = base(); m = member(d, "PC3"); m["spiffeURI"] = node_uri(TENANT, m["nodeID"], OTHER_EPOCH)
    add("r06-epoch-replaced", "A rotation leaf would carry a new epoch.", ["AR-EPOCH-SPIFFE"], d)

    d = base(); member(d, "PC4")["counters"]["channelVersionAfter"] = 1
    add("r07-channel-counter-reset", "Channel version reset instead of C+1.", ["AR-CHANNEL-NONMONOTONE"], d)

    d = base(); c = member(d, "PC2")["counters"]; c["policyVersionAfter"] = c["policyFloorBefore"]
    add("r08-policy-not-above-floor", "New policy version equals the authenticated floor.",
        ["AR-POLICY-NONMONOTONE"], d)

    d = base(); m = member(d, "PC1"); m["nodeID"] = nid("0PC4"); m["spiffeURI"] = node_uri(TENANT, nid("0PC4"), EPOCH)
    add("r09-pc1-copies-pc4-identity", "PC1 re-uses PC4's NodeID (copied share directory).",
        ["AR-ENROLLMENT-REUSES-IDENTITY", "AR-IDENTITY-COLLISION"], d)

    d = base(); m = member(d, "PC1"); m["nodeID"] = nid("RTR1"); m["spiffeURI"] = node_uri(TENANT, nid("RTR1"), EPOCH)
    add("r10-pc1-reuses-retired-row", "PC1 revives a retired/disabled NodeID.", ["AR-ENROLLMENT-REUSES-IDENTITY"], d)

    d = base(); member(d, "PC1")["nodePublicKeySHA256"] = h("RTR2-node-key")
    add("r11-pc1-reuses-existing-key", "PC1 enrolls with a key already bound to another row.",
        ["AR-ENROLLMENT-REUSES-IDENTITY"], d)

    d = base(); member(d, "PC3")["nodePublicKeySHA256"] = h("PC3-node-key-new")
    add("r12-rotation-key-changed", "Rotation silently swaps the Node key.", ["AR-ROTATION-KEY-CHANGED"], d)

    d = base(); m = member(d, "PC2"); m["nodeID"] = nid("0PC5"); m["spiffeURI"] = node_uri(TENANT, nid("0PC5"), EPOCH)
    add("r13-rotation-of-unknown-identity", "ROTATION for an identity absent from the DB is an enrollment in disguise.",
        ["AR-ROTATION-UNKNOWN-IDENTITY"], d)

    d = base(); member(d, "PC1")["counters"]["channelVersionBefore"] = 2
    add("r14-enrollment-counter-nonzero", "New enrollment does not start from an empty channel.",
        ["AR-ENROLLMENT-COUNTER"], d)

    d = base(); d["advanceRenewal"]["normalBudgetSeconds"] = None
    add("r15-proposed-with-unknown-budget", "PROPOSED while a budget is unknown; must be HOLD.", ["AR-HOLD-REQUIRED"], d)

    d = base(); d["preservedEpoch"]["source"] = "HISTORICAL_EVIDENCE"
    add("r16-proposed-with-historical-epoch", "PROPOSED from a historical epoch, not a DB readback.",
        ["AR-HOLD-REQUIRED"], d)

    d = base(); d["advanceRenewal"]["caSuccessorLeadSeconds"] = 518400
    add("r17-successor-lead-too-short", "Successor CA lead shorter than one leaf lifetime + budgets.",
        ["AR-RENEWAL-BUDGET"], d)

    d = base(); d["advanceRenewal"]["caLifetimeSeconds"] = 604800; d["newAuthority"]["notAfter"] = "2026-11-25T12:00:00Z"
    add("r18-seven-day-ca-repeats-failure", "Seven-day CA (the Nov 14 failure shape) cannot hold an advance window.",
        ["AR-RENEWAL-BUDGET"], d)

    d = base(); d["advanceRenewal"]["leafRenewalLeadSeconds"] = 20000
    add("r19-leaf-lead-below-budget", "Leaf renewal lead below budget + overlap + 660s.", ["AR-RENEWAL-BUDGET"], d)

    d = base(); d["observedAt"] = "2026-11-14T07:00:00Z"
    d["newAuthority"]["notBefore"] = "2026-11-14T07:00:00Z"; d["newAuthority"]["notAfter"] = "2027-11-14T07:00:00Z"
    add("r20-terminal-not-yet-expired", "Old CA still valid: this contract is not the applicable branch.",
        ["AR-TERMINAL-NOT-EXPIRED"], d)

    d = base(); d["activation"] = "RELEASED"
    add("r21-activation-released", "A proposal document cannot carry an operating release.", ["AR-SCHEMA"], d)

    d = base(); d["newAuthority"]["custody"]["custodyEvidenceRef"] = "-----BEGIN PRIVATE KEY----- MC4CAQ"
    add("r22-private-material-embedded", "Private key material embedded in the plan.", ["AR-SECRET-MATERIAL"], d)

    _, p09 = positives()["p09-durable-cas-undone-hold"]
    d = copy.deepcopy(p09); d["checkpoint"]["expectedRecoveryAction"] = "RESUME_FORWARD"
    d["checkpoint"]["expectedResumePhase"] = "A5_POLICY_PUBLISHED"
    add("r23-resume-over-undone-cas", "Declares RESUME where readback proves a foreign writer.",
        ["AR-RECOVERY-MISMATCH"], d)

    _, p10 = positives()["p10-enrollment-before-rotation-hold"]
    d = copy.deepcopy(p10); d["checkpoint"]["expectedRecoveryAction"] = "RESUME_FORWARD"
    d["checkpoint"]["expectedResumePhase"] = "A6_CP_CONTEXT_SWITCH"
    add("r24-enrollment-mixed-into-rotation", "Declares RESUME although PC1 was admitted before rotation settled.",
        ["AR-RECOVERY-MISMATCH"], d)

    d = base()
    interrupted(d, "A5_POLICY_PUBLISHED", "A6_CP_CONTEXT_SWITCH", "UNKNOWN", "NEW_KEY_PRESENT_MATCHES_PLAN",
                [settled_row(d, "PC2"), row(d, "PC3", version=2, cert=member(d, "PC3")["plannedLeafSHA256"], floor=1),
                 settled_row(d, "PC4")], "RESUME_FORWARD", "A6_CP_CONTEXT_SWITCH")
    add("r25-resume-over-floor-reset", "Declares RESUME although PC3's floor went below its preserved value.",
        ["AR-RECOVERY-MISMATCH"], d)

    d = base()
    interrupted(d, "A2_ANCHOR_STAGED", "A4_CHANNEL_CAS", "UNKNOWN", "NEW_KEY_PRESENT_MATCHES_PLAN",
                [row(d, pc) for pc in ROT], "RESUME_FORWARD", "A4_CHANNEL_CAS")
    add("r26-checkpoint-skips-phase", "In-flight phase skips A3.", ["AR-CHECKPOINT-ORDER"], d)

    d = base(); d["checkpoint"]["expectedRecoveryAction"] = "ROLLBACK_TO_TERMINAL_CA"
    add("r27-rollback-to-terminal", "Rollback to the expired authority is not a representable action.",
        ["AR-SCHEMA"], d)

    d = base(); member(d, "PC1")["plannedLeafSHA256"] = member(d, "PC2")["plannedLeafSHA256"]
    add("r28-shared-planned-leaf", "Two members planned onto one leaf certificate.", ["AR-PLANNED-LEAF-REUSE"], d)

    d = base(); d["status"] = "HOLD"
    interrupted(d, "A1_NEW_TRUST_AUTHORIZED", None, None, "NEW_KEY_PRESENT_MATCHES_PLAN",
                [row(d, pc) for pc in ROT], "RESUME_FORWARD", "A2_ANCHOR_STAGED")
    add("r29-hold-plan-already-mutating", "A HOLD plan (unknown inputs) claims new trust was already created.",
        ["AR-CHECKPOINT-ORDER"], d)

    d = base(); member(d, "PC1")["counters"]["policyVersionAfter"] = 2
    add("r30-pc1-first-policy-skips-version", "PC1 first enrollment must start at P=1, not skip ahead.",
        ["AR-ENROLLMENT-COUNTER"], d)
    return out


HANDOFF_SOURCE = "fixtures/positive/p05-complete.json"
HANDOFF_PATH = "handoff/pc1-first-enrollment-handoff.json"
HANDOFF_HOSTS = {"PC1": "host-pc1", "PC2": "host-pc2", "PC3": "host-pc3", "PC4": "host-pc4"}
HANDOFF_CP_HOST = "host-cp"


def current_instance() -> dict:
    """Real Nov18 fleet plan (Root544 evidence). Every unknown stays null -> HOLD."""
    tenant = "97968b42-68aa-40ce-af5e-3a33e2fc2205"
    epoch = "bcd581be-31b4-4aca-86e6-3ca31b69ed09"

    def rot(pc, node, account, address):
        return {
            "pc": pc, "kind": "ROTATION", "nodeID": node, "account": account, "address": address,
            "spiffeURI": node_uri(tenant, node, epoch), "nodePublicKeySHA256": None,
            "priorNodePublicKeySHA256": None, "plannedLeafSHA256": None,
            "counters": {"channelVersionBefore": None, "channelVersionAfter": None,
                         "policyFloorBefore": None, "policyVersionAfter": None},
        }

    nodes = {
        "PC2": ("nod_01M6TGQZ8S3DAFS7TYE8TY1PX2", "saintvision-invion", "192.168.45.143"),
        "PC3": ("nod_01M6TAWG25JTA3F7J7S1EE4N2W", "saintvision-invion3", "192.168.45.222"),
        "PC4": ("nod_01M6TGSXV1J7XWC5D5H7N6EW1D", "inviz", "192.168.45.210"),
    }
    doc = base()
    doc.update({
        "planID": "ARP-20261118-fleet5-nov18-ca-terminal",
        "status": "HOLD",
        "fixture": False,
        "observedAt": "2026-11-18T11:53:13Z",
        "tenantID": tenant,
        "projectID": "prj_01M6NDBHVD2DZQ1Q38DCKN1XE3",
        "preservedEpoch": {"epoch": epoch, "source": "HISTORICAL_EVIDENCE", "readbackSHA256": None},
        "terminalAuthority": {
            "caCertificateSHA256": "b8d777ab04c65a44f827fdda9629d54a086e9ff8cc752b90a09023a93341c5a3",
            "caPublicKeySHA256": None,
            "subjectCommonName": None,
            "notAfter": "2026-11-14T07:15:30Z",
            "state": "CA_TERMINAL",
            "usage": "REFERENCE_ONLY",
        },
    })
    new = doc["newAuthority"]
    new.update({"caCertificateSHA256": None, "caPublicKeySHA256": None, "notBefore": None, "notAfter": None,
                "anchorBundle": []})
    new["custody"]["custodyEvidenceRef"] = None
    new["trustAuthorization"] = {"decisionRef": None, "authorizedBy": None}
    doc["advanceRenewal"]["normalBudgetSeconds"] = None
    doc["advanceRenewal"]["caSuccessorBudgetSeconds"] = None
    doc["controlPlaneClient"].update({"spiffeURI": cp_uri(tenant, epoch), "publicKeySHA256": None,
                                      "priorPublicKeySHA256": None, "plannedLeafSHA256": None})
    doc["roleKeys"] = [{"role": "LAUNCH_SIGNER", "publicKeySHA256": None, "disposition": "RETAINED",
                        "custodyEvidenceRef": None}]
    pc1 = enrollment()
    pc1.update({"nodeID": None, "spiffeURI": None, "address": "192.168.45.13", "nodePublicKeySHA256": None,
                "plannedLeafSHA256": None})
    doc["members"] = [rot(pc, *nodes[pc]) for pc in ("PC2", "PC3", "PC4")] + [pc1]
    doc["existingNodeRows"] = {"source": "HISTORICAL_EVIDENCE", "nodeIDs": [v[0] for v in nodes.values()],
                               "publicKeySHA256s": []}
    doc["checkpoint"] = {
        "lastDurablePhase": None, "inFlightPhase": None, "inFlightOutcome": None,
        "readback": {"dbAvailable": False, "epoch": None, "custodyState": "NOT_READ", "members": []},
        "expectedRecoveryAction": "NOT_STARTED", "expectedResumePhase": None,
    }
    return doc


def render() -> dict[str, str]:
    files: dict[str, str] = {}
    entries = []

    def dump(doc):
        return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"

    files["instances/fleet5-nov18-ca-terminal-hold.json"] = dump(current_instance())
    entries.append({"path": "instances/fleet5-nov18-ca-terminal-hold.json", "codes": [],
                    "why": "Real Nov18 fleet plan from Root544 evidence; HOLD with every unknown null."})
    for name, (why, doc) in positives().items():
        path = f"fixtures/positive/{name}.json"
        files[path] = dump(doc)
        entries.append({"path": path, "codes": [], "why": why})
    for name, (why, codes, doc) in rejections().items():
        path = f"fixtures/rejection/{name}.json"
        files[path] = dump(doc)
        entries.append({"path": path, "codes": sorted(codes), "why": why})
    from tools.check_fleet5_authority_replacement import enrollment_handoff

    source_text = files[HANDOFF_SOURCE]
    files[HANDOFF_PATH] = dump(enrollment_handoff(json.loads(source_text), HANDOFF_SOURCE,
                                                  source_text.encode("utf-8"), hosts=HANDOFF_HOSTS,
                                                  control_plane_host=HANDOFF_CP_HOST))
    files["expectations.json"] = dump({
        "schema": "fleet5-authority-replacement-expectations:1",
        "status": "PROPOSED_NOT_IMPLEMENTED",
        "generator": "tools/generate_fleet5_authority_replacement_fixtures.py",
        "checker": "tools/check_fleet5_authority_replacement.py",
        "documents": entries,
        "handoffs": [{
            "path": HANDOFF_PATH,
            "sourcePlan": HANDOFF_SOURCE,
            "hosts": HANDOFF_HOSTS,
            "controlPlaneHostId": HANDOFF_CP_HOST,
            "why": "PC1 first-enrollment operator handoff: new identity, public CA evidence, five-node inventory.",
        }],
    })
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if committed files differ")
    args = parser.parse_args(argv)
    drift = []
    for rel, text in render().items():
        path = OUT / rel
        if args.check:
            if not path.is_file() or path.read_text("utf-8") != text:
                drift.append(rel)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
    for rel in drift:
        print(f"DRIFT {rel}")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
