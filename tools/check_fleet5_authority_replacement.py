"""Check PROPOSED FLEET5 authority-replacement plans (schema + cross-field invariants).

PROPOSED / NOT_IMPLEMENTED contract checker. It reads JSON documents only: no
network, database, SSH, certificate, key or process access. Accepting a document
means "the plan is internally consistent", never "an operation is released".

Usage:
    python tools/check_fleet5_authority_replacement.py            # fixtures + current instance
    python tools/check_fleet5_authority_replacement.py FILE...    # print codes for files

Exit 0 only when every fixture/instance yields exactly its expected verdict.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # script mode: allow `from tools import ...`
    sys.path.insert(0, str(ROOT))
CONTRACT_DIR = ROOT / "contracts" / "proposed" / "fleet5-authority-replacement"
SCHEMA_PATH = CONTRACT_DIR / "fleet5-authority-replacement-v1.schema.json"
EXPECTATIONS_PATH = CONTRACT_DIR / "expectations.json"

PHASES = (
    "A0_PREFLIGHT_READBACK",
    "A1_NEW_TRUST_AUTHORIZED",
    "A2_ANCHOR_STAGED",
    "A3_ROTATION_LEAVES_ISSUED",
    "A4_CHANNEL_CAS",
    "A5_POLICY_PUBLISHED",
    "A6_CP_CONTEXT_SWITCH",
    "A7_ROTATION_SETTLED",
    "E1_ENROLLMENT_AUTHORIZED",
    "E2_ENROLLMENT_ADMITTED",
    "E3_ENROLLMENT_SETTLED",
)
INDEX = {name: i for i, name in enumerate(PHASES)}
LEAF_MIN_SECONDS = 60
LEAF_MAX_SECONDS = 518400  # existing lan_pki/lan_pilot six-day cap
OVERLAP_MAX_SECONDS = 21600
SPIFFE_NODE = "spiffe://saintvision.ai/tenant/{tenant}/node/{node}/epoch/{epoch}"
SPIFFE_CP = "spiffe://saintvision.ai/tenant/{tenant}/control-plane/epoch/{epoch}"
SECRET_MARKERS = ("PRIVATE KEY", "-----BEGIN", "password=", "postgresql://")


def _ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _idx(phase: str | None) -> int:
    return -1 if phase is None else INDEX[phase]


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _nulls(doc: dict) -> list[str]:
    """Paths of genuine inputs that are still unknown; any of them forces HOLD."""
    missing: list[str] = []
    epoch = doc["preservedEpoch"]
    if epoch["source"] != "DB_READBACK" or epoch["readbackSHA256"] is None:
        missing.append("preservedEpoch")
    if doc["existingNodeRows"]["source"] != "DB_READBACK":
        missing.append("existingNodeRows.source")
    new = doc["newAuthority"]
    for key in ("caCertificateSHA256", "caPublicKeySHA256", "notBefore", "notAfter"):
        if new[key] is None:
            missing.append(f"newAuthority.{key}")
    if new["custody"]["custodyEvidenceRef"] is None:
        missing.append("newAuthority.custody.custodyEvidenceRef")
    for key, value in new["trustAuthorization"].items():
        if value is None:
            missing.append(f"newAuthority.trustAuthorization.{key}")
    for key in ("caPublicKeySHA256", "subjectCommonName"):
        if doc["terminalAuthority"][key] is None:
            missing.append(f"terminalAuthority.{key}")
    for key, value in doc["advanceRenewal"].items():
        if value is None:
            missing.append(f"advanceRenewal.{key}")
    cp = doc["controlPlaneClient"]
    for key in ("publicKeySHA256", "plannedLeafSHA256"):
        if cp[key] is None:
            missing.append(f"controlPlaneClient.{key}")
    if cp["keyContinuity"] == "RETAINED" and cp["priorPublicKeySHA256"] is None:
        missing.append("controlPlaneClient.priorPublicKeySHA256")
    for i, role in enumerate(doc["roleKeys"]):
        if role["publicKeySHA256"] is None:
            missing.append(f"roleKeys[{i}].publicKeySHA256")
        if role["disposition"] == "RETAINED" and role["custodyEvidenceRef"] is None:
            missing.append(f"roleKeys[{i}].custodyEvidenceRef")
    for m in doc["members"]:
        for key in ("nodeID", "spiffeURI", "nodePublicKeySHA256", "plannedLeafSHA256"):
            if m[key] is None:
                missing.append(f"{m['pc']}.{key}")
        if m["kind"] == "ROTATION" and m["priorNodePublicKeySHA256"] is None:
            missing.append(f"{m['pc']}.priorNodePublicKeySHA256")
        for key, value in m["counters"].items():
            if value is None:
                missing.append(f"{m['pc']}.counters.{key}")
    return missing


def _renewal_errors(doc: dict) -> list[str]:
    r = doc["advanceRenewal"]
    if any(value is None for value in r.values()):
        return []
    fixed = r["safetySeconds"] + r["clockSkewSeconds"]
    rules = [
        LEAF_MIN_SECONDS <= r["leafLifetimeSeconds"] <= LEAF_MAX_SECONDS,
        r["safetySeconds"] < r["overlapSeconds"] <= OVERLAP_MAX_SECONDS,
        r["leafRenewalLeadSeconds"] >= r["normalBudgetSeconds"] + r["overlapSeconds"] + fixed,
        r["leafRenewalLeadSeconds"] < r["leafLifetimeSeconds"],
        r["policyRenewalLeadSeconds"] >= r["normalBudgetSeconds"] + fixed,
        r["policyRenewalLeadSeconds"] < r["policyLifetimeSeconds"],
        r["policyLifetimeSeconds"] <= r["leafLifetimeSeconds"],
        # Successor CA must be anchored and every leaf re-issued under it while the
        # current CA is still valid: one full leaf lifetime + its own budget + overlap.
        r["caSuccessorLeadSeconds"]
        >= r["leafLifetimeSeconds"] + r["caSuccessorBudgetSeconds"] + r["overlapSeconds"] + fixed,
        r["caWarningLeadSeconds"] > r["caSuccessorLeadSeconds"],
        r["caLifetimeSeconds"] >= 2 * r["caWarningLeadSeconds"],
    ]
    if not all(rules):
        return ["AR-RENEWAL-BUDGET"]
    new = doc["newAuthority"]
    if new["notBefore"] and new["notAfter"]:
        life = (_ts(new["notAfter"]) - _ts(new["notBefore"])).total_seconds()
        remaining = (_ts(new["notAfter"]) - _ts(doc["observedAt"])).total_seconds()
        if life > r["caLifetimeSeconds"] or remaining <= r["caWarningLeadSeconds"]:
            return ["AR-RENEWAL-BUDGET"]
    return []


def _identity_errors(doc: dict) -> list[str]:
    errors: set[str] = set()
    tenant, epoch = doc["tenantID"], doc["preservedEpoch"]["epoch"]
    terminal = doc["terminalAuthority"]
    rows = doc["existingNodeRows"]
    members = doc["members"]
    rotation_keys = set()
    for field in ("pc", "nodeID", "spiffeURI", "nodePublicKeySHA256", "plannedLeafSHA256", "address"):
        values = [m[field] for m in members if m[field] is not None]
        if len(values) != len(set(values)):
            errors.add("AR-PLANNED-LEAF-REUSE" if field == "plannedLeafSHA256" else "AR-IDENTITY-COLLISION")
    cp = doc["controlPlaneClient"]
    leaves = [m["plannedLeafSHA256"] for m in members] + [cp["plannedLeafSHA256"]]
    if terminal["caCertificateSHA256"] in leaves or (
        cp["plannedLeafSHA256"] is not None
        and cp["plannedLeafSHA256"] in [m["plannedLeafSHA256"] for m in members]
    ):
        errors.add("AR-PLANNED-LEAF-REUSE")
    if cp["spiffeURI"] != SPIFFE_CP.format(tenant=tenant, epoch=epoch):
        errors.add("AR-EPOCH-SPIFFE")
    if cp["keyContinuity"] == "RETAINED" and None not in (cp["publicKeySHA256"], cp["priorPublicKeySHA256"]):
        if cp["publicKeySHA256"] != cp["priorPublicKeySHA256"]:
            errors.add("AR-ROTATION-KEY-CHANGED")
    if cp["keyContinuity"] == "FRESH" and cp["publicKeySHA256"] is not None:
        if cp["publicKeySHA256"] in (cp["priorPublicKeySHA256"], *rows["publicKeySHA256s"]):
            errors.add("AR-ENROLLMENT-REUSES-IDENTITY")
    for m in members:
        if m["nodeID"] is not None and m["spiffeURI"] != SPIFFE_NODE.format(
            tenant=tenant, node=m["nodeID"], epoch=epoch
        ):
            errors.add("AR-EPOCH-SPIFFE")
        if m["kind"] == "ROTATION":
            rotation_keys.add(m["priorNodePublicKeySHA256"])
            if m["nodeID"] is None or m["nodeID"] not in rows["nodeIDs"]:
                errors.add("AR-ROTATION-UNKNOWN-IDENTITY")
            if None not in (m["nodePublicKeySHA256"], m["priorNodePublicKeySHA256"]) and (
                m["nodePublicKeySHA256"] != m["priorNodePublicKeySHA256"]
            ):
                errors.add("AR-ROTATION-KEY-CHANGED")
    for m in members:
        if m["kind"] != "NEW_ENROLLMENT":
            continue
        if m["priorNodePublicKeySHA256"] is not None:
            errors.add("AR-ENROLLMENT-REUSES-IDENTITY")
        if m["nodeID"] is not None and m["nodeID"] in rows["nodeIDs"]:
            errors.add("AR-ENROLLMENT-REUSES-IDENTITY")
        key = m["nodePublicKeySHA256"]
        if key is not None and (key in rows["publicKeySHA256s"] or key in rotation_keys):
            errors.add("AR-ENROLLMENT-REUSES-IDENTITY")
    role_keys = [r["publicKeySHA256"] for r in doc["roleKeys"] if r["publicKeySHA256"] is not None]
    if len(role_keys) != len(set(role_keys)) or len({r["role"] for r in doc["roleKeys"]}) != len(doc["roleKeys"]):
        errors.add("AR-IDENTITY-COLLISION")
    node_keys = {m["nodePublicKeySHA256"] for m in members}
    if set(role_keys) & (node_keys | {cp["publicKeySHA256"], doc["newAuthority"]["caPublicKeySHA256"]}):
        errors.add("AR-IDENTITY-COLLISION")
    return sorted(errors)


def _counter_errors(doc: dict) -> list[str]:
    errors: set[str] = set()
    for m in doc["members"]:
        c = m["counters"]
        cb, ca, pf, pa = (c[k] for k in ("channelVersionBefore", "channelVersionAfter", "policyFloorBefore", "policyVersionAfter"))
        if m["kind"] == "ROTATION":
            if cb is not None and ca is not None and (cb < 1 or ca != cb + 1):
                errors.add("AR-CHANNEL-NONMONOTONE")
            if pf is not None and pa is not None and (pf < 1 or pa != pf + 1):
                errors.add("AR-POLICY-NONMONOTONE")
        else:
            if (cb not in (None, 0)) or (ca not in (None, 1)) or (pf not in (None, 0)) or (pa not in (None, 1)):
                errors.add("AR-ENROLLMENT-COUNTER")
    return sorted(errors)


def _authority_errors(doc: dict) -> list[str]:
    errors: set[str] = set()
    terminal, new = doc["terminalAuthority"], doc["newAuthority"]
    if _ts(terminal["notAfter"]) > _ts(doc["observedAt"]):
        errors.add("AR-TERMINAL-NOT-EXPIRED")
    if new["caCertificateSHA256"] == terminal["caCertificateSHA256"]:
        errors.add("AR-TERMINAL-REUSE")
    if new["caPublicKeySHA256"] is not None and new["caPublicKeySHA256"] == terminal["caPublicKeySHA256"]:
        errors.add("AR-TERMINAL-REUSE")
    terminal_cn = terminal["subjectCommonName"]
    if terminal_cn is not None and new["subjectCommonName"].strip().casefold() == terminal_cn.strip().casefold():
        errors.add("AR-TERMINAL-REUSE")
    bundle = new["anchorBundle"]
    if terminal["caCertificateSHA256"] in bundle:
        errors.add("AR-TERMINAL-ANCHOR")
    others = [b for b in bundle if b != terminal["caCertificateSHA256"]]
    reused = new["caCertificateSHA256"] == terminal["caCertificateSHA256"]  # reported as AR-TERMINAL-REUSE
    expected = [] if new["caCertificateSHA256"] is None or reused else [new["caCertificateSHA256"]]
    if others != expected:
        errors.add("AR-ANCHOR-MISMATCH")
    if new["notBefore"] and new["notAfter"] and _ts(new["notBefore"]) >= _ts(new["notAfter"]):
        errors.add("AR-RENEWAL-BUDGET")
    return sorted(errors)


def _checkpoint_errors(doc: dict) -> list[str]:
    cp = doc["checkpoint"]
    last, flight, outcome = cp["lastDurablePhase"], cp["inFlightPhase"], cp["inFlightOutcome"]
    enrolls = any(m["kind"] == "NEW_ENROLLMENT" for m in doc["members"])
    if (flight is None) != (outcome is None):
        return ["AR-CHECKPOINT-ORDER"]
    if flight is not None and _idx(flight) != _idx(last) + 1:
        return ["AR-CHECKPOINT-ORDER"]
    final = _idx("E3_ENROLLMENT_SETTLED" if enrolls else "A7_ROTATION_SETTLED")
    if max(_idx(last), _idx(flight)) > final:
        return ["AR-CHECKPOINT-ORDER"]
    if max(_idx(last), _idx(flight)) >= _idx("A1_NEW_TRUST_AUTHORIZED") and doc["status"] != "PROPOSED":
        # A plan with unknown inputs can never have started a mutation.
        return ["AR-CHECKPOINT-ORDER"]
    return []


def recovery_action(doc: dict) -> tuple[str, str | None]:
    """The only permitted next step after an interruption, from durable journal + readback."""
    cp = doc["checkpoint"]
    rb = cp["readback"]
    last, flight, outcome = cp["lastDurablePhase"], cp["inFlightPhase"], cp["inFlightOutcome"]
    if last is None and flight is None:
        return "NOT_STARTED", None
    li = _idx(last)
    # Nothing irreversible can exist before A1 is attempted.
    if li < INDEX["A1_NEW_TRUST_AUTHORIZED"] and flight in (None, "A0_PREFLIGHT_READBACK"):
        return "ABANDON_BEFORE_NEW_TRUST", None
    if not rb["dbAvailable"]:
        return "HOLD_DB_READBACK_REQUIRED", None
    if rb["epoch"] != doc["preservedEpoch"]["epoch"]:
        return "HOLD_EPOCH_DIVERGED", None
    custody = rb["custodyState"]
    if li < INDEX["A1_NEW_TRUST_AUTHORIZED"]:  # A1 in flight
        if outcome == "FAILED_BEFORE_MUTATION" and custody == "NO_NEW_KEY":
            return "ABANDON_BEFORE_NEW_TRUST", None
        if outcome == "UNKNOWN" and custody == "NO_NEW_KEY":
            return "ABANDON_BEFORE_NEW_TRUST", None
        if custody != "NEW_KEY_PRESENT_MATCHES_PLAN":
            return "HOLD_CUSTODY_UNRESOLVED", None
    elif custody != "NEW_KEY_PRESENT_MATCHES_PLAN":
        return "HOLD_CUSTODY_UNRESOLVED", None

    planned = {m["nodeID"]: m for m in doc["members"] if m["nodeID"] is not None}
    known = set(doc["existingNodeRows"]["nodeIDs"])
    observed = {r["nodeID"]: r for r in rb["members"]}
    for node_id, row in observed.items():
        if node_id not in planned and node_id not in known and row["rowPresent"]:
            return "HOLD_UNPLANNED_ROW", None
    reach = max(li, _idx(flight))
    # Enrollment identity must not exist before rotation settled.
    for node_id, m in planned.items():
        row = observed.get(node_id)
        if m["kind"] == "NEW_ENROLLMENT" and row is not None and row["rowPresent"]:
            if li < INDEX["A7_ROTATION_SETTLED"]:
                return "HOLD_ENROLLMENT_BEFORE_ROTATION_SETTLED", None
    for node_id, m in planned.items():
        row = observed.get(node_id)
        c = m["counters"]
        if m["kind"] == "ROTATION":
            if row is None or not row["rowPresent"]:
                return "HOLD_FOREIGN_WRITER", None
            v, before = row["channelVersion"], c["channelVersionBefore"]
            if v == before:
                if li >= INDEX["A4_CHANNEL_CAS"]:
                    return "HOLD_FOREIGN_WRITER", None  # durable CAS undone: restore/rollback
            elif v == before + 1:
                if reach < INDEX["A4_CHANNEL_CAS"] or row["channelCertificateSHA256"] != m["plannedLeafSHA256"]:
                    return "HOLD_FOREIGN_WRITER", None
            else:
                return "HOLD_FOREIGN_WRITER", None
            floor = row["policyFloor"]
            if floor is None or floor < c["policyFloorBefore"]:
                return "HOLD_FOREIGN_WRITER", None  # floor reset/decrease
            if floor > c["policyVersionAfter"]:
                return "HOLD_POLICY_ABOVE_PLAN", None
            if floor == c["policyVersionAfter"] and reach < INDEX["A5_POLICY_PUBLISHED"]:
                return "HOLD_FOREIGN_WRITER", None
            if li >= INDEX["A7_ROTATION_SETTLED"] and (v != before + 1 or floor != c["policyVersionAfter"]):
                return "HOLD_FOREIGN_WRITER", None
        else:
            present = row is not None and row["rowPresent"]
            if not present:
                if li >= INDEX["E2_ENROLLMENT_ADMITTED"]:
                    return "HOLD_FOREIGN_WRITER", None
                continue
            if reach < INDEX["E2_ENROLLMENT_ADMITTED"]:
                return "HOLD_FOREIGN_WRITER", None
            if row["channelVersion"] != 1 or row["channelCertificateSHA256"] != m["plannedLeafSHA256"]:
                return "HOLD_FOREIGN_WRITER", None
            floor = row["policyFloor"]
            if floor is None or floor > c["policyVersionAfter"]:
                return "HOLD_POLICY_ABOVE_PLAN" if floor is not None else "HOLD_FOREIGN_WRITER", None
            if li >= INDEX["E3_ENROLLMENT_SETTLED"] and floor != c["policyVersionAfter"]:
                return "HOLD_FOREIGN_WRITER", None
    enrolls = any(m["kind"] == "NEW_ENROLLMENT" for m in doc["members"])
    final = "E3_ENROLLMENT_SETTLED" if enrolls else "A7_ROTATION_SETTLED"
    if last == final and flight is None:
        return "COMPLETE", None
    return "RESUME_FORWARD", flight if flight is not None else PHASES[li + 1]


def evaluate(doc: Any, schema: dict | None = None) -> list[str]:
    """Return the sorted rejection codes for ``doc``; [] means internally consistent."""
    schema = schema if schema is not None else json.loads(SCHEMA_PATH.read_text("utf-8"))
    if any(marker.casefold() in s.casefold() for s in _strings(doc) for marker in SECRET_MARKERS):
        return ["AR-SECRET-MATERIAL"]
    if list(Draft202012Validator(schema).iter_errors(doc)):
        return ["AR-SCHEMA"]
    codes: set[str] = set()
    codes.update(_authority_errors(doc))
    codes.update(_identity_errors(doc))
    codes.update(_counter_errors(doc))
    codes.update(_renewal_errors(doc))
    if doc["status"] == "PROPOSED" and _nulls(doc):
        codes.add("AR-HOLD-REQUIRED")
    order = _checkpoint_errors(doc)
    codes.update(order)
    if not order and not codes:
        action, phase = recovery_action(doc)
        cp = doc["checkpoint"]
        if action != cp["expectedRecoveryAction"] or phase != cp.get("expectedResumePhase"):
            codes.add("AR-RECOVERY-MISMATCH")
    return sorted(codes)


HANDOFF_SCHEMA = "fleet5-authority-replacement-enrollment-handoff:1"
VERIFIER = "tools/five_node_lab_preflight.py"


def enrollment_handoff(doc: dict, source_rel: str, source_bytes: bytes, *, hosts: dict[str, str],
                       control_plane_host: str) -> dict:
    """Operator handoff after a settled enrollment: the new identity, the public CA
    evidence, and the exact five-node inventory the existing verifier consumes.

    Refuses unless the plan is internally consistent and recovery_action is COMPLETE.
    """
    import hashlib

    from tools.five_node_lab_preflight import (
        FIVE_NODE_INVENTORY_SCHEMA_VERSION,
        FIVE_NODE_PROFILE,
        five_node_inventory_revision,
        validate_five_node_inventory,
    )

    codes = evaluate(doc)
    if codes:
        raise ValueError(f"plan rejected: {codes}")
    if recovery_action(doc) != ("COMPLETE", None):
        raise ValueError("handoff requires a COMPLETE (settled) plan")
    enrolled = [m for m in doc["members"] if m["kind"] == "NEW_ENROLLMENT"]
    if len(enrolled) != 1:
        raise ValueError("handoff covers exactly one new enrollment")
    new_member = enrolled[0]
    nodes = []
    for m in doc["members"]:
        host = hosts[m["pc"]]
        colocated = host == control_plane_host
        nodes.append({
            "nodeId": m["nodeID"],
            "ip": m["address"],
            "certificateSHA256": m["plannedLeafSHA256"],
            "profile": FIVE_NODE_PROFILE,
            "hostId": host,
            "failureDomainId": f"fd-{m['pc'].lower()}",
            "coLocatedWithControlPlane": colocated,
            "measurementEligible": {"s05": not colocated, "s07": not colocated},
            "exclusionReason": "cp-host-colocation" if colocated else None,
        })
    inventory = {
        "schemaVersion": FIVE_NODE_INVENTORY_SCHEMA_VERSION,
        "controlPlaneHostId": control_plane_host,
        "nodes": nodes,
    }
    inventory["revision"] = five_node_inventory_revision(inventory)
    validate_five_node_inventory(inventory)
    new = doc["newAuthority"]
    return {
        "schema": HANDOFF_SCHEMA,
        "fixture": doc.get("fixture") is True,
        "activation": "NOT_AUTHORIZED",
        "sourcePlan": source_rel,
        "sourcePlanSHA256": hashlib.sha256(source_bytes).hexdigest(),
        "newIdentity": {
            "pc": new_member["pc"],
            "nodeID": new_member["nodeID"],
            "spiffeURI": new_member["spiffeURI"],
            "epoch": doc["preservedEpoch"]["epoch"],
            "nodePublicKeySHA256": new_member["nodePublicKeySHA256"],
            "leafCertificateSHA256": new_member["plannedLeafSHA256"],
            "channelVersion": new_member["counters"]["channelVersionAfter"],
            "policyVersion": new_member["counters"]["policyVersionAfter"],
        },
        "publicCAEvidence": {
            "caCertificateSHA256": new["caCertificateSHA256"],
            "caPublicKeySHA256": new["caPublicKeySHA256"],
            "subjectCommonName": new["subjectCommonName"],
            "notBefore": new["notBefore"],
            "notAfter": new["notAfter"],
            "anchorBundle": new["anchorBundle"],
            "trustDecisionRef": new["trustAuthorization"]["decisionRef"],
            "excludedTerminalCACertificateSHA256": doc["terminalAuthority"]["caCertificateSHA256"],
        },
        "verifier": {
            "tool": VERIFIER,
            "consumes": ["nodeId", "ip", "certificateSHA256 (leaf DER, compared with inv.node_channels)",
                         "hostId", "failureDomainId", "coLocatedWithControlPlane", "revision"],
            "doesNotCheck": [
                "issuer chain to publicCAEvidence.caCertificateSHA256 (established only by the A6 CP contexts "
                "and Node anchor bundles)",
                "SPIFFE URI / epoch inside the leaf",
                "terminal CA absence from anchor bundles",
            ],
        },
        "fiveNodeInventory": inventory,
    }


def check_all() -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text("utf-8"))
    Draft202012Validator.check_schema(schema)
    expectations = json.loads(EXPECTATIONS_PATH.read_text("utf-8"))
    failures: list[str] = []
    listed = set()
    for entry in expectations["documents"]:
        path = CONTRACT_DIR / entry["path"]
        listed.add(path.resolve())
        doc = json.loads(path.read_text("utf-8"))
        got = evaluate(doc, schema)
        want = sorted(entry["codes"])
        if got != want:
            failures.append(f"{entry['path']}: expected {want or 'ACCEPT'}, got {got or 'ACCEPT'}")
        if not want and not entry["path"].startswith("instances/") and doc.get("fixture") is not True:
            failures.append(f"{entry['path']}: synthetic fixture must set fixture=true")
    for entry in expectations.get("handoffs", []):
        path = CONTRACT_DIR / entry["path"]
        listed.add(path.resolve())
        source = CONTRACT_DIR / entry["sourcePlan"]
        try:
            rebuilt = enrollment_handoff(json.loads(source.read_text("utf-8")), entry["sourcePlan"],
                                         source.read_bytes(), hosts=entry["hosts"],
                                         control_plane_host=entry["controlPlaneHostId"])
        except (ValueError, KeyError) as exc:
            failures.append(f"{entry['path']}: handoff refused: {exc}")
            continue
        if json.loads(path.read_text("utf-8")) != rebuilt:
            failures.append(f"{entry['path']}: handoff differs from its source plan")
    on_disk = {p.resolve() for p in CONTRACT_DIR.rglob("*.json")} - {SCHEMA_PATH.resolve(), EXPECTATIONS_PATH.resolve()}
    for path in sorted(on_disk - listed):
        failures.append(f"unlisted document: {path.relative_to(CONTRACT_DIR).as_posix()}")
    positives = [e for e in expectations["documents"] if not e["codes"]]
    negatives = [e for e in expectations["documents"] if e["codes"]]
    if not positives or not negatives:
        failures.append("expectations need at least one accepted and one rejected document")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path)
    args = parser.parse_args(argv)
    if args.files:
        worst = 0
        for path in args.files:
            doc = json.loads(path.read_text("utf-8"))
            codes = evaluate(doc)
            action = recovery_action(doc) if not codes else None
            print(json.dumps({"file": str(path), "codes": codes, "recovery": action}))
            worst = worst or (1 if codes else 0)
        return worst
    failures = check_all()
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        return 1
    count = len(json.loads(EXPECTATIONS_PATH.read_text("utf-8"))["documents"])
    print(f"PASS fleet5 authority replacement: {count} documents matched their expected verdicts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
