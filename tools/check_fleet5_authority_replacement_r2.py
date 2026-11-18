"""Check PROPOSED FLEET5 authority-replacement R2 plans (schema, PKI evidence, recovery).

PROPOSED / NOT_IMPLEMENTED contract checker, revision R2. It reads JSON documents
only: no network, database, SSH, key, private material or process access. It
parses the *public* DER certificates and CSRs that a plan carries and verifies
their signatures offline. Accepting a document means "the plan and its recorded
evidence are internally consistent", never "an operation is released".

R2 closes the five HIGH findings of the R1 independent review
(docs/vault/30_Development/History/2026-11-19_FLEET5_Authority_Replacement_R1_Codex_Review.md):

  F1  first admission: fenced reservation bound to tenant/epoch/PC/NodeID/CSR/plan
      digest/readback, journaled ROW_ADMIT and CHANNEL_PROVISION substeps.
  F2  authenticated identity: CSR proof of possession, prior leaf signed by the
      prior CA and bound to the DB row tuple, new leaf chain/profile verified
      against the exact new root, pairwise role-key separation, retained-signer
      continuity with an affirmative compromise decision.
  F3  serving evidence: per-process trust readback for the declared CP process
      inventory, per-member fresh mTLS handshakes, duplicate/stale rejection,
      A3+ gated on verified A2 staging, serving gated on the reviewed binary
      migration.
  F4  same-phase retry: immutable operation manifest with exact pre/post images,
      expected versions and per-operation audit identity under a writer fence;
      apply on exact preimage, acknowledge exact postimage, hold otherwise.
  F5  expiry: deadline checks at resume time from actual certificate validity and
      measured budgets; separate ADVANCE_RENEWAL mode with bounded dual-anchor
      overlap or quiesced cutover and a retirement proof.

Usage:
    python tools/check_fleet5_authority_replacement_r2.py            # fixtures + instance
    python tools/check_fleet5_authority_replacement_r2.py FILE...    # print codes for files

Exit 0 only when every document yields exactly its expected verdict.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # script mode: allow `from tools import ...`
    sys.path.insert(0, str(ROOT))
CONTRACT_DIR = ROOT / "contracts" / "proposed" / "fleet5-authority-replacement-r2"
SCHEMA_PATH = CONTRACT_DIR / "fleet5-authority-replacement-v2.schema.json"
EXPECTATIONS_PATH = CONTRACT_DIR / "expectations.json"

ROTATION_PHASES = (
    "A0_PREFLIGHT_READBACK",
    "A1_NEW_TRUST_AUTHORIZED",
    "A2_ANCHOR_STAGED",
    "A3_ROTATION_LEAVES_INSTALLED",
    "A4_CHANNEL_CAS",
    "A5_POLICY_PUBLISHED",
    "A6_CP_CONTEXT_SWITCH",
    "A7_ROTATION_SETTLED",
)
ENROLLMENT_PHASES = (
    "E1_ENROLLMENT_RESERVED",
    "E2_ENROLLMENT_ROW_ADMITTED",
    "E3_ENROLLMENT_CHANNEL_PROVISIONED",
    "E4_ENROLLMENT_POLICY_PUBLISHED",
    "E5_ENROLLMENT_SETTLED",
)
PHASES = ROTATION_PHASES + ENROLLMENT_PHASES
INDEX = {name: i for i, name in enumerate(PHASES)}
A1 = INDEX["A1_NEW_TRUST_AUTHORIZED"]
A2 = INDEX["A2_ANCHOR_STAGED"]
A7 = INDEX["A7_ROTATION_SETTLED"]

LEAF_MIN_SECONDS = 60
LEAF_MAX_SECONDS = 518400  # existing lan_pki/lan_pilot six-day cap
OVERLAP_MAX_SECONDS = 21600
# Serving windows are plan inputs (measuredBudgets) that need fleet measurement; these are the
# contract caps a measured value may only tighten.
FRESHNESS_CAP_SECONDS = 120  # an observation received longer ago than this at resumeAt is stale
HEARTBEAT_CAP_SECONDS = 15  # NodeChannels.snapshot accepts a heartbeat at most 15 s old
CHALLENGE_CAP_SECONDS = 300  # a one-use challenge issued longer ago than this at resumeAt is stale
SERVING_WINDOWS = {"observationFreshnessSeconds": FRESHNESS_CAP_SECONDS,
                   "heartbeatFreshnessSeconds": HEARTBEAT_CAP_SECONDS,
                   "challengeLifetimeSeconds": CHALLENGE_CAP_SECONDS}
SITES = ("observer_worker", "delivery_worker", "workspace_runtime", "build_product_runtime",
         "storage_check_collector")
CP_CSR_COMMON_NAME = "control-plane"
SPIFFE_NODE = "spiffe://saintvision.ai/tenant/{tenant}/node/{node}/epoch/{epoch}"
SPIFFE_CP = "spiffe://saintvision.ai/tenant/{tenant}/control-plane/epoch/{epoch}"
SECRET_MARKERS = ("PRIVATE KEY", "-----BEGIN", "password=", "postgresql://")
ROLE_SCOPE = {"LAUNCH_SIGNER": "LAUNCH_SIGNATURES", "POLICY_SIGNER": "POLICY_SIGNATURES"}

PENDING, COMMITTED, CONFLICT, ABOVE_PLAN, UNVERIFIED = (
    "PENDING", "COMMITTED", "CONFLICT", "ABOVE_PLAN", "UNVERIFIED")


# ---------------------------------------------------------------- primitives


def _ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _idx(phase: str | None) -> int:
    return -1 if phase is None else INDEX[phase]


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def der_bytes(value: str | None) -> bytes | None:
    if value is None:
        return None
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def spki_sha256(public_key) -> str:
    return sha256_hex(public_key.public_bytes(serialization.Encoding.DER,
                                              serialization.PublicFormat.SubjectPublicKeyInfo))


def anchor_digest(bundle: list[str]) -> str:
    return digest(sorted(bundle))


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


def enrolls(doc: dict) -> bool:
    return any(m["kind"] == "NEW_ENROLLMENT" for m in doc["members"])


def final_phase(doc: dict) -> str:
    return "E5_ENROLLMENT_SETTLED" if enrolls(doc) else "A7_ROTATION_SETTLED"


def plan_phases(doc: dict) -> tuple[str, ...]:
    return PHASES[: INDEX[final_phase(doc)] + 1]


def window(doc: dict, key: str) -> int:
    """A measured serving window; unknown is 0 so that nothing is fresh (fail closed)."""
    value = doc["measuredBudgets"][key]
    return 0 if value is None else value


def dual(doc: dict) -> bool:
    return doc["trustTransition"]["cutover"] == "DUAL_ANCHOR_OVERLAP"


# ---------------------------------------------------------------- certificates (public bytes only)


def load_certificate(value: str | None) -> x509.Certificate | None:
    raw = der_bytes(value)
    if raw is None:
        return None
    try:
        return x509.load_der_x509_certificate(raw)
    except (ValueError, TypeError):
        return None


def _ext(cert, cls):
    try:
        return cert.extensions.get_extension_for_class(cls).value
    except x509.ExtensionNotFound:
        return None


def _cn(name: x509.Name) -> str | None:
    attrs = name.get_attributes_for_oid(NameOID.COMMON_NAME)
    return attrs[0].value if len(attrs) == 1 and len(list(name)) == 1 else None


def signed_by(cert: x509.Certificate, issuer: x509.Certificate) -> bool:
    key = issuer.public_key()
    if not isinstance(key, Ed25519PublicKey) or cert.issuer != issuer.subject:
        return False
    try:
        key.verify(cert.signature, cert.tbs_certificate_bytes)
    except InvalidSignature:
        return False
    return True


def _sans(cert) -> tuple[list[str], list[str], int]:
    san = _ext(cert, x509.SubjectAlternativeName)
    if san is None:
        return [], [], 0
    uris = list(san.get_values_for_type(x509.UniformResourceIdentifier))
    ips = [str(ip) for ip in san.get_values_for_type(x509.IPAddress)]
    return uris, ips, len(san) - len(uris) - len(ips)


def csr_public_key(value: str | None, common_name: str | None):
    """The CSR's Ed25519 key when it is a valid proof of possession for ``common_name``."""
    raw = der_bytes(value)
    if raw is None or common_name is None:
        return None
    try:
        csr = x509.load_der_x509_csr(raw)
        key = csr.public_key()
        if (not csr.is_signature_valid or _cn(csr.subject) != common_name
                or not isinstance(key, Ed25519PublicKey) or len(csr.extensions)):
            return None
    except (ValueError, TypeError):
        return None
    return key


def new_root(doc: dict) -> x509.Certificate | None:
    """The new root, only when it is exactly the planned self-signed Ed25519 CA."""
    new = doc["newAuthority"]
    cert = load_certificate(new["certificateDER"])
    if cert is None or not isinstance(cert.public_key(), Ed25519PublicKey) or not signed_by(cert, cert):
        return None
    bc, ku = _ext(cert, x509.BasicConstraints), _ext(cert, x509.KeyUsage)
    if bc is None or not bc.ca or bc.path_length != 0 or ku is None or not ku.key_cert_sign or ku.digital_signature:
        return None
    if (sha256_hex(der_bytes(new["certificateDER"])) != new["caCertificateSHA256"]
            or spki_sha256(cert.public_key()) != new["caPublicKeySHA256"]
            or _cn(cert.subject) != new["subjectCommonName"]
            or _iso(cert.not_valid_before_utc) != new["notBefore"]
            or _iso(cert.not_valid_after_utc) != new["notAfter"]):
        return None
    return cert


def prior_root(doc: dict) -> x509.Certificate | None:
    prior = doc["priorAuthority"]
    cert = load_certificate(prior["certificateDER"])
    if cert is None or not signed_by(cert, cert):
        return None
    if (sha256_hex(der_bytes(prior["certificateDER"])) != prior["caCertificateSHA256"]
            or (prior["caPublicKeySHA256"] is not None and spki_sha256(cert.public_key()) != prior["caPublicKeySHA256"])
            or (prior["subjectCommonName"] is not None and _cn(cert.subject) != prior["subjectCommonName"])
            or _iso(cert.not_valid_after_utc) != prior["notAfter"]):
        return None
    return cert


def leaf_ok(doc: dict, root: x509.Certificate, leaf_der: str, *, public_sha: str | None, uri: str | None,
            address: str | None, client: bool, planned_sha: str | None) -> bool:
    """Leaf chains to the exact new root and carries exactly the planned profile."""
    cert = load_certificate(leaf_der)
    if cert is None or not signed_by(cert, root):
        return False
    if public_sha is None or spki_sha256(cert.public_key()) != public_sha:
        return False
    bc, ku, eku = (_ext(cert, x509.BasicConstraints), _ext(cert, x509.KeyUsage),
                   _ext(cert, x509.ExtendedKeyUsage))
    if bc is None or bc.ca or ku is None or not ku.digital_signature or ku.key_cert_sign:
        return False
    if eku is None or list(eku) != [ExtendedKeyUsageOID.CLIENT_AUTH if client else ExtendedKeyUsageOID.SERVER_AUTH]:
        return False
    uris, ips, other = _sans(cert)
    if uris != [uri] or other or ips != ([] if client else [address]):
        return False
    validity = doc["newAuthority"]["leafValidity"]
    nb, na = cert.not_valid_before_utc, cert.not_valid_after_utc
    if _iso(nb) != validity["notBefore"] or _iso(na) != validity["notAfter"]:
        return False
    if nb < root.not_valid_before_utc or na > root.not_valid_after_utc:
        return False
    life = (na - nb).total_seconds()
    cap = doc["advanceRenewal"]["leafLifetimeSeconds"] or LEAF_MAX_SECONDS
    if not LEAF_MIN_SECONDS <= life <= min(cap, LEAF_MAX_SECONDS):
        return False
    return sha256_hex(der_bytes(leaf_der)) == planned_sha


def prior_leaf(doc: dict, value: str | None, uri: str | None) -> x509.Certificate | None:
    """A prior leaf only when the prior CA signed it for exactly ``uri`` (expiry is irrelevant)."""
    root = prior_root(doc)
    cert = load_certificate(value)
    if root is None or cert is None or not signed_by(cert, root):
        return None
    uris, _, other = _sans(cert)
    return cert if uris == [uri] and not other else None


def prior_leaf_sha(member_or_cp: dict) -> str | None:
    raw = der_bytes(member_or_cp["priorLeafDER"])
    return None if raw is None else sha256_hex(raw)


# ---------------------------------------------------------------- plan digest and manifest


def plan_digest(doc: dict) -> str:
    """Digest of the frozen pre-ceremony plan inputs. Reservations and the manifest bind to it."""
    new, cp = doc["newAuthority"], doc["controlPlaneClient"]

    def csr_sha(value):
        raw = der_bytes(value)
        return None if raw is None else sha256_hex(raw)

    return digest({
        "schema": doc["schema"],
        "planID": doc["planID"],
        "mode": doc["mode"],
        "tenantID": doc["tenantID"],
        "projectID": doc["projectID"],
        "epoch": doc["preservedEpoch"]["epoch"],
        "priorCA": doc["priorAuthority"]["caCertificateSHA256"],
        "newAuthority": {k: new[k] for k in ("subjectCommonName", "notBefore", "notAfter", "leafValidity",
                                             "trustAuthorization")},
        "trustTransition": {k: doc["trustTransition"][k] for k in ("cutover", "overlap", "targetGeneration")},
        "writerFence": {k: doc["writerFence"][k] for k in ("token", "generation")},
        "controlPlaneClient": {"spiffeURI": cp["spiffeURI"], "keyContinuity": cp["keyContinuity"],
                               "publicKeySHA256": cp["publicKeySHA256"], "csrSHA256": csr_sha(cp["csrDER"]),
                               "priorLeafSHA256": prior_leaf_sha(cp), "processInventory": cp["processInventory"]},
        "members": [{
            "pc": m["pc"], "kind": m["kind"], "nodeID": m["nodeID"], "address": m["address"],
            "endpoint": m["endpoint"], "spiffeURI": m["spiffeURI"], "nodePublicKeySHA256": m["nodePublicKeySHA256"],
            "csrSHA256": csr_sha(m["csrDER"]), "priorLeafSHA256": prior_leaf_sha(m),
            "priorPolicyDigest": m["priorPolicyDigest"], "counters": m["counters"],
        } for m in doc["members"]],
    })


def reservation_digest(member: dict) -> str | None:
    return None if member["reservation"] is None else digest(member["reservation"])


def ceremony_missing(doc: dict) -> list[str]:
    """A1 outputs that must exist once A1 is durable."""
    new, cp, tt = doc["newAuthority"], doc["controlPlaneClient"], doc["trustTransition"]
    missing = [f"newAuthority.{k}" for k in ("certificateDER", "caCertificateSHA256", "caPublicKeySHA256")
               if new[k] is None]
    missing += [f"controlPlaneClient.{k}" for k in ("leafDER", "plannedLeafSHA256") if cp[k] is None]
    missing += [f"trustTransition.{k}" for k in ("stagedAnchorBundle", "finalAnchorBundle") if tt[k] is None]
    for m in doc["members"]:
        missing += [f"{m['pc']}.{k}" for k in ("leafDER", "plannedLeafSHA256", "plannedPolicy") if m[k] is None]
    return missing


def ceremony_present(doc: dict) -> bool:
    new, cp = doc["newAuthority"], doc["controlPlaneClient"]
    return (new["certificateDER"] is not None or cp["leafDER"] is not None
            or any(m["leafDER"] is not None for m in doc["members"]))


def expected_manifest(doc: dict) -> dict | None:
    """The only operation manifest this plan may freeze at A1 (None while ceremony output is missing)."""
    if ceremony_missing(doc) or doc["controlPlaneClient"]["processInventory"] is None:
        return None
    pd = plan_digest(doc)
    epoch = doc["preservedEpoch"]["epoch"]
    tt, cp = doc["trustTransition"], doc["controlPlaneClient"]
    prior_d = anchor_digest([doc["priorAuthority"]["caCertificateSHA256"]])
    staged_d, final_d = anchor_digest(tt["stagedAnchorBundle"]), anchor_digest(tt["finalAnchorBundle"])
    ops: list[dict] = []

    def op(phase, kind, target, pre, post, *, expected=None, endpoint=None):
        op_id = "op_" + digest({"planDigest": pd, "phase": phase, "kind": kind, "target": target})[:24]
        ops.append({"opID": op_id, "phase": phase, "kind": kind, "target": target, "epoch": epoch,
                    "expectedVersion": expected, "endpoint": endpoint, "pre": pre, "post": post})

    rotation = [m for m in doc["members"] if m["kind"] == "ROTATION"]
    for m in rotation:
        op("A2_ANCHOR_STAGED", "ANCHOR_STAGE", m["nodeID"], {"stagedAnchorDigest": prior_d},
           {"stagedAnchorDigest": staged_d})
    for m in rotation:
        op("A3_ROTATION_LEAVES_INSTALLED", "LEAF_INSTALL", m["nodeID"], {"installedLeafSHA256": prior_leaf_sha(m)},
           {"installedLeafSHA256": m["plannedLeafSHA256"]})
    for m in rotation:
        c = m["counters"]
        op("A4_CHANNEL_CAS", "CHANNEL_CAS", m["nodeID"],
           {"channelVersion": c["channelVersionBefore"], "channelCertificateSHA256": prior_leaf_sha(m)},
           {"channelVersion": c["channelVersionAfter"], "channelCertificateSHA256": m["plannedLeafSHA256"]},
           expected=c["channelVersionBefore"], endpoint=m["endpoint"])
    for m in rotation:
        c = m["counters"]
        op("A5_POLICY_PUBLISHED", "POLICY_PUBLISH", m["nodeID"],
           {"policyFloor": c["policyFloorBefore"], "installedPolicyDigest": m["priorPolicyDigest"]},
           {"policyFloor": c["policyVersionAfter"], "installedPolicyDigest": m["plannedPolicy"]["digest"],
            "installedPolicyNotAfter": m["plannedPolicy"]["notAfter"]})
    for p in cp["processInventory"]:
        op("A6_CP_CONTEXT_SWITCH", "CP_CONTEXT_SWITCH", p["processID"],
           {"clientLeafSHA256": prior_leaf_sha(cp), "loadedAnchorDigest": prior_d},
           {"clientLeafSHA256": cp["plannedLeafSHA256"], "loadedAnchorDigest": staged_d,
            "trustGeneration": tt["targetGeneration"]})
    if dual(doc):
        for m in rotation:
            op("A7_ROTATION_SETTLED", "ANCHOR_RETIRE", m["nodeID"], {"stagedAnchorDigest": staged_d},
               {"stagedAnchorDigest": final_d})
        for p in cp["processInventory"]:
            op("A7_ROTATION_SETTLED", "CP_ANCHOR_RETIRE", p["processID"], {"loadedAnchorDigest": staged_d},
               {"loadedAnchorDigest": final_d})
    for m in rotation:
        op("A7_ROTATION_SETTLED", "SETTLE", m["nodeID"], {},
           {"peerLeafSHA256": m["plannedLeafSHA256"], "anchorDigest": final_d,
            "policyDigest": m["plannedPolicy"]["digest"]})
    for m in doc["members"]:
        if m["kind"] != "NEW_ENROLLMENT":
            continue
        rd = reservation_digest(m)
        op("E1_ENROLLMENT_RESERVED", "RESERVE", m["nodeID"], {"reservationDigest": None}, {"reservationDigest": rd})
        op("E2_ENROLLMENT_ROW_ADMITTED", "ROW_ADMIT", m["nodeID"], {"rowExists": False},
           {"rowExists": True, "reservationDigest": rd})
        op("E3_ENROLLMENT_CHANNEL_PROVISIONED", "CHANNEL_PROVISION", m["nodeID"],
           {"channelVersion": 0, "channelCertificateSHA256": None},
           {"channelVersion": 1, "channelCertificateSHA256": m["plannedLeafSHA256"]}, expected=0,
           endpoint=m["endpoint"])
        op("E4_ENROLLMENT_POLICY_PUBLISHED", "POLICY_PUBLISH", m["nodeID"],
           {"policyFloor": 0, "installedPolicyDigest": None},
           {"policyFloor": 1, "installedPolicyDigest": m["plannedPolicy"]["digest"],
            "installedPolicyNotAfter": m["plannedPolicy"]["notAfter"]})
        op("E5_ENROLLMENT_SETTLED", "SETTLE", m["nodeID"], {},
           {"peerLeafSHA256": m["plannedLeafSHA256"], "anchorDigest": final_d,
            "policyDigest": m["plannedPolicy"]["digest"]})
    return {"planDigest": pd, "digest": digest({"planDigest": pd, "operations": ops}), "operations": ops}


def manifest_pin(doc: dict) -> dict | None:
    """What the plan and the durable journal record about the frozen manifest."""
    manifest = expected_manifest(doc)
    if manifest is None:
        return None
    return {"planDigest": manifest["planDigest"], "digest": manifest["digest"],
            "operationCount": len(manifest["operations"])}


# ---------------------------------------------------------------- static invariants


def _nulls(doc: dict) -> list[str]:
    """Genuine pre-ceremony inputs that are still unknown; any of them forces HOLD."""
    missing: list[str] = []
    epoch = doc["preservedEpoch"]
    if epoch["source"] != "DB_READBACK" or epoch["readbackSHA256"] is None:
        missing.append("preservedEpoch")
    rows = doc["existingNodeRows"]
    if rows["source"] != "DB_READBACK" or rows["readbackSHA256"] is None or rows["includesRetired"] is not True:
        missing.append("existingNodeRows")
    prior = doc["priorAuthority"]
    missing += [f"priorAuthority.{k}" for k in ("certificateDER", "caPublicKeySHA256", "subjectCommonName")
                if prior[k] is None]
    new = doc["newAuthority"]
    missing += [f"newAuthority.{k}" for k in ("notBefore", "notAfter") if new[k] is None]
    missing += [f"newAuthority.leafValidity.{k}" for k, v in new["leafValidity"].items() if v is None]
    if new["custody"]["custodyEvidenceRef"] is None:
        missing.append("newAuthority.custody.custodyEvidenceRef")
    missing += [f"newAuthority.trustAuthorization.{k}" for k, v in new["trustAuthorization"].items() if v is None]
    tt = doc["trustTransition"]
    if tt["cutover"] == "DUAL_ANCHOR_OVERLAP" and tt["overlap"] is None:
        missing.append("trustTransition.overlap")
    if tt["cutover"] == "DUAL_ANCHOR_OVERLAP" and tt["overlapRuntimeEvidenceRef"] is None:
        missing.append("trustTransition.overlapRuntimeEvidenceRef")  # reload, retirement, timing, interruption
    if tt["cutover"] == "QUIESCED" and tt["quiesceEvidenceRef"] is None:
        missing.append("trustTransition.quiesceEvidenceRef")
    missing += [f"advanceRenewal.{k}" for k, v in doc["advanceRenewal"].items() if v is None]
    budgets = doc["measuredBudgets"]
    if budgets["source"] != "MEASURED" or budgets["evidenceRef"] is None:
        missing.append("measuredBudgets")
    missing += [f"measuredBudgets.{p}" for p in plan_phases(doc) if budgets["phaseSeconds"].get(p) is None]
    missing += [f"measuredBudgets.{k}" for k in SERVING_WINDOWS if budgets[k] is None]
    migration = doc["servingBinaryMigration"]
    if migration["status"] != "REVIEWED" or migration["reviewRef"] is None:
        missing.append("servingBinaryMigration")
    missing += [f"writerFence.{k}" for k in ("token", "generation") if doc["writerFence"][k] is None]
    cp = doc["controlPlaneClient"]
    missing += [f"controlPlaneClient.{k}" for k in ("publicKeySHA256", "csrDER", "priorLeafDER", "processInventory")
                if cp[k] is None]
    for i, role in enumerate(doc["roleKeys"]):
        if role["publicKeySHA256"] is None:
            missing.append(f"roleKeys[{i}].publicKeySHA256")
        cont = role["continuity"]
        if role["disposition"] == "RETAINED":
            if cont is None or any(v is None for v in cont.values()) or cont["compromiseDecision"] == "UNDETERMINED":
                missing.append(f"roleKeys[{i}].continuity")
    for m in doc["members"]:
        missing += [f"{m['pc']}.{k}" for k in ("nodeID", "spiffeURI", "nodePublicKeySHA256", "csrDER", "endpoint")
                    if m[k] is None]
        missing += [f"{m['pc']}.counters.{k}" for k, v in m["counters"].items() if v is None]
        if m["kind"] == "ROTATION":
            missing += [f"{m['pc']}.{k}" for k in ("priorLeafDER", "priorPolicyDigest") if m[k] is None]
        elif m["reservation"] is not None:
            res = m["reservation"]
            missing += [f"{m['pc']}.reservation.{k}" for k, v in res.items() if v is None and k != "nodeStateEmpty"]
            if res["nodeStateEmpty"]["verified"] is None or res["nodeStateEmpty"]["evidenceRef"] is None:
                missing.append(f"{m['pc']}.reservation.nodeStateEmpty")
    if doc["placement"]["controlPlaneHostPC"] is None:
        missing.append("placement.controlPlaneHostPC")
    return missing


def _renewal_errors(doc: dict) -> list[str]:
    r = doc["advanceRenewal"]
    errors: set[str] = set()
    if all(value is not None for value in r.values()):
        fixed = r["safetySeconds"] + r["clockSkewSeconds"]
        rules = [
            LEAF_MIN_SECONDS <= r["leafLifetimeSeconds"] <= LEAF_MAX_SECONDS,
            r["safetySeconds"] < r["overlapSeconds"] <= OVERLAP_MAX_SECONDS,
            r["leafRenewalLeadSeconds"] >= r["normalBudgetSeconds"] + r["overlapSeconds"] + fixed,
            r["leafRenewalLeadSeconds"] < r["leafLifetimeSeconds"],
            r["policyRenewalLeadSeconds"] >= r["normalBudgetSeconds"] + fixed,
            r["policyRenewalLeadSeconds"] < r["policyLifetimeSeconds"],
            r["policyLifetimeSeconds"] <= r["leafLifetimeSeconds"],
            r["caSuccessorLeadSeconds"]
            >= r["leafLifetimeSeconds"] + r["caSuccessorBudgetSeconds"] + r["overlapSeconds"] + fixed,
            r["caWarningLeadSeconds"] > r["caSuccessorLeadSeconds"],
            r["caLifetimeSeconds"] >= 2 * r["caWarningLeadSeconds"],
        ]
        if not all(rules):
            errors.add("AR-RENEWAL-BUDGET")
        new = doc["newAuthority"]
        if new["notBefore"] and new["notAfter"]:
            life = (_ts(new["notAfter"]) - _ts(new["notBefore"])).total_seconds()
            remaining = (_ts(new["notAfter"]) - _ts(doc["observedAt"])).total_seconds()
            if life > r["caLifetimeSeconds"] or remaining <= r["caWarningLeadSeconds"]:
                errors.add("AR-RENEWAL-BUDGET")
    new = doc["newAuthority"]
    if new["notBefore"] and new["notAfter"] and _ts(new["notBefore"]) >= _ts(new["notAfter"]):
        errors.add("AR-RENEWAL-BUDGET")
    lv = new["leafValidity"]
    if lv["notBefore"] and lv["notAfter"]:
        nb, na = _ts(lv["notBefore"]), _ts(lv["notAfter"])
        cap = r["leafLifetimeSeconds"] or LEAF_MAX_SECONDS
        if nb >= na or (na - nb).total_seconds() > min(cap, LEAF_MAX_SECONDS):
            errors.add("AR-RENEWAL-BUDGET")
        if new["notAfter"] and (na > _ts(new["notAfter"]) or (new["notBefore"] and nb < _ts(new["notBefore"]))):
            errors.add("AR-RENEWAL-BUDGET")
    for m in doc["members"]:
        p = m["plannedPolicy"]
        if p is None:
            continue
        pb, pa = _ts(p["notBefore"]), _ts(p["notAfter"])
        if pb >= pa or (r["policyLifetimeSeconds"] and (pa - pb).total_seconds() > r["policyLifetimeSeconds"]):
            errors.add("AR-RENEWAL-BUDGET")
        if lv["notAfter"] and pa > _ts(lv["notAfter"]):
            errors.add("AR-RENEWAL-BUDGET")
    return sorted(errors)


def _authority_errors(doc: dict) -> list[str]:
    errors: set[str] = set()
    prior, new, tt = doc["priorAuthority"], doc["newAuthority"], doc["trustTransition"]
    r = doc["advanceRenewal"]
    fixed = r["safetySeconds"] + r["clockSkewSeconds"]
    observed = _ts(doc["observedAt"])
    if doc["mode"] == "TERMINAL_REPLACEMENT":
        if prior["state"] != "CA_TERMINAL" or prior["usage"] != "REFERENCE_ONLY":
            errors.add("AR-MODE")
        if tt["cutover"] != "TERMINAL_SINGLETON" or tt["overlap"] is not None:
            errors.add("AR-MODE")
        if tt["overlapRuntimeEvidenceRef"] is not None:
            errors.add("AR-MODE")
        if _ts(prior["notAfter"]) > observed:
            errors.add("AR-TERMINAL-NOT-EXPIRED")
    else:
        if prior["state"] != "CA_CURRENT" or prior["usage"] != "OVERLAP_ANCHOR_UNTIL_RETIRED":
            errors.add("AR-MODE")
        if tt["cutover"] not in ("DUAL_ANCHOR_OVERLAP", "QUIESCED"):
            errors.add("AR-MODE")
        remaining = (_ts(prior["notAfter"]) - observed).total_seconds()
        lead = r["caSuccessorLeadSeconds"]
        if remaining <= 0 or (lead is not None and remaining < lead):
            errors.add("AR-ADVANCE-WINDOW")  # expired or started too late: not an advance renewal
        if tt["cutover"] == "QUIESCED" and (tt["overlap"] is not None or tt["overlapRuntimeEvidenceRef"] is not None):
            errors.add("AR-MODE")
        overlap = tt["overlap"]
        if tt["cutover"] == "DUAL_ANCHOR_OVERLAP" and overlap is not None:
            start, end = _ts(overlap["startsAt"]), _ts(overlap["mustEndBy"])
            if (end <= start or end > _ts(prior["notAfter"]) - timedelta(seconds=fixed)
                    or (lead is not None and (end - start).total_seconds() > lead)
                    or (new["notBefore"] is not None and start < _ts(new["notBefore"]))):
                errors.add("AR-ADVANCE-WINDOW")
    if new["caCertificateSHA256"] is not None and new["caCertificateSHA256"] == prior["caCertificateSHA256"]:
        errors.add("AR-PRIOR-REUSE")
    if new["caPublicKeySHA256"] is not None and new["caPublicKeySHA256"] == prior["caPublicKeySHA256"]:
        errors.add("AR-PRIOR-REUSE")
    if (prior["subjectCommonName"] is not None
            and new["subjectCommonName"].strip().casefold() == prior["subjectCommonName"].strip().casefold()):
        errors.add("AR-PRIOR-REUSE")
    staged, final = tt["stagedAnchorBundle"], tt["finalAnchorBundle"]
    bundles = [b for b in (staged, final) if b is not None]
    if doc["mode"] == "TERMINAL_REPLACEMENT" and any(prior["caCertificateSHA256"] in b for b in bundles):
        errors.add("AR-TERMINAL-ANCHOR")
    elif new["caCertificateSHA256"] is None:
        if bundles:
            errors.add("AR-ANCHOR-MISMATCH")
    elif "AR-PRIOR-REUSE" not in errors:
        want_final = [new["caCertificateSHA256"]]
        want_staged = (sorted([prior["caCertificateSHA256"], new["caCertificateSHA256"]])
                       if tt["cutover"] == "DUAL_ANCHOR_OVERLAP" else want_final)
        if (staged is not None and staged != want_staged) or (final is not None and final != want_final):
            errors.add("AR-ANCHOR-MISMATCH")
    return sorted(errors)


def _identity_errors(doc: dict) -> list[str]:
    errors: set[str] = set()
    tenant, epoch = doc["tenantID"], doc["preservedEpoch"]["epoch"]
    members, cp = doc["members"], doc["controlPlaneClient"]
    row_list = doc["existingNodeRows"]["rows"]
    rows = {r["nodeID"]: r for r in row_list}
    if len(rows) != len(row_list):
        errors.add("AR-IDENTITY-COLLISION")
    root = new_root(doc)
    if doc["newAuthority"]["certificateDER"] is not None and root is None:
        errors.add("AR-CERT-ROOT")
    if doc["priorAuthority"]["certificateDER"] is not None and prior_root(doc) is None:
        errors.add("AR-PRIOR-BINDING")
    for field in ("pc", "nodeID", "spiffeURI", "nodePublicKeySHA256", "address"):
        values = [m[field] for m in members if m[field] is not None]
        if len(values) != len(set(values)):
            errors.add("AR-IDENTITY-COLLISION")
    leaves = [m["plannedLeafSHA256"] for m in members if m["plannedLeafSHA256"] is not None]
    if cp["plannedLeafSHA256"] is not None:
        leaves.append(cp["plannedLeafSHA256"])
    if len(leaves) != len(set(leaves)) or doc["priorAuthority"]["caCertificateSHA256"] in leaves:
        errors.add("AR-PLANNED-LEAF-REUSE")
    if cp["spiffeURI"] != SPIFFE_CP.format(tenant=tenant, epoch=epoch):
        errors.add("AR-EPOCH-SPIFFE")
    rotation_keys = {m["nodePublicKeySHA256"] for m in members if m["kind"] == "ROTATION"}
    for m in members:
        if m["nodeID"] is not None and m["spiffeURI"] != SPIFFE_NODE.format(tenant=tenant, node=m["nodeID"],
                                                                             epoch=epoch):
            errors.add("AR-EPOCH-SPIFFE")
        if m["endpoint"] is not None and urlsplit(m["endpoint"]).hostname != m["address"]:
            errors.add("AR-ENDPOINT")
        if m["csrDER"] is not None:
            key = csr_public_key(m["csrDER"], m["nodeID"])
            if key is None or spki_sha256(key) != m["nodePublicKeySHA256"]:
                errors.add("AR-CSR-POP")
        if m["leafDER"] is not None or m["plannedLeafSHA256"] is not None:
            if root is not None and (m["leafDER"] is None or not leaf_ok(
                    doc, root, m["leafDER"], public_sha=m["nodePublicKeySHA256"], uri=m["spiffeURI"],
                    address=m["address"], client=False, planned_sha=m["plannedLeafSHA256"])):
                errors.add("AR-CERT-LEAF")
        if m["kind"] == "ROTATION":
            row = rows.get(m["nodeID"])
            if row is None or row["status"] != "ACTIVE":
                errors.add("AR-ROTATION-UNKNOWN-IDENTITY")
            if m["reservation"] is not None:
                errors.add("AR-ENROLLMENT-RESERVATION")
            if m["priorLeafDER"] is not None:
                prior = prior_leaf(doc, m["priorLeafDER"], m["spiffeURI"])
                if prior is None:
                    errors.add("AR-PRIOR-BINDING")
                else:
                    prior_key = spki_sha256(prior.public_key())
                    if prior_key != m["nodePublicKeySHA256"]:
                        errors.add("AR-ROTATION-KEY-CHANGED")
                    if row is not None and (row["channelCertificateSHA256"] != prior_leaf_sha(m)
                                            or row["publicKeySHA256"] != prior_key):
                        errors.add("AR-PRIOR-BINDING")
        else:
            if m["priorLeafDER"] is not None or m["priorPolicyDigest"] is not None:
                errors.add("AR-ENROLLMENT-REUSES-IDENTITY")
            if m["nodeID"] is not None and m["nodeID"] in rows:
                errors.add("AR-ENROLLMENT-REUSES-IDENTITY")
            key = m["nodePublicKeySHA256"]
            if key is not None and (key in {r["publicKeySHA256"] for r in row_list} or key in rotation_keys):
                errors.add("AR-ENROLLMENT-REUSES-IDENTITY")
            errors.update(_reservation_errors(doc, m))
    # Control-plane client: proof of possession, profile, prior binding.
    if cp["csrDER"] is not None:
        key = csr_public_key(cp["csrDER"], CP_CSR_COMMON_NAME)
        if key is None or spki_sha256(key) != cp["publicKeySHA256"]:
            errors.add("AR-CSR-POP")
    if (cp["leafDER"] is not None or cp["plannedLeafSHA256"] is not None) and root is not None:
        if cp["leafDER"] is None or not leaf_ok(doc, root, cp["leafDER"], public_sha=cp["publicKeySHA256"],
                                                uri=cp["spiffeURI"], address=None, client=True,
                                                planned_sha=cp["plannedLeafSHA256"]):
            errors.add("AR-CERT-LEAF")
    cp_prior_key = None
    if cp["priorLeafDER"] is not None:
        prior = prior_leaf(doc, cp["priorLeafDER"], cp["spiffeURI"])
        if prior is None:
            errors.add("AR-PRIOR-BINDING")
        else:
            cp_prior_key = spki_sha256(prior.public_key())
            if cp["keyContinuity"] == "RETAINED" and cp_prior_key != cp["publicKeySHA256"]:
                errors.add("AR-ROTATION-KEY-CHANGED")
            if cp["keyContinuity"] == "FRESH" and cp_prior_key == cp["publicKeySHA256"]:
                errors.add("AR-FRESH-KEY-REUSED")
    errors.update(_role_errors(doc, cp_prior_key))
    return sorted(errors)


def _reservation_errors(doc: dict, m: dict) -> list[str]:
    res = m["reservation"]
    if res is None:
        return ["AR-ENROLLMENT-RESERVATION"]
    csr = der_bytes(m["csrDER"])
    expected = {
        "tenantID": doc["tenantID"],
        "epoch": doc["preservedEpoch"]["epoch"],
        "pc": m["pc"],
        "nodeID": m["nodeID"],
        "csrSHA256": None if csr is None else sha256_hex(csr),
        "planDigest": plan_digest(doc),
        "fenceToken": doc["writerFence"]["token"],
        "rowsReadbackSHA256": doc["existingNodeRows"]["readbackSHA256"],
    }
    for key, value in expected.items():
        if res[key] is not None and value is not None and res[key] != value:
            return ["AR-ENROLLMENT-RESERVATION"]
    if res["nodeStateEmpty"]["verified"] is False:
        return ["AR-ENROLLMENT-RESERVATION"]
    return []


def _role_errors(doc: dict, cp_prior_key: str | None) -> list[str]:
    errors: set[str] = set()
    cp = doc["controlPlaneClient"]
    roles = doc["roleKeys"]
    if len({r["role"] for r in roles}) != len(roles):
        errors.add("AR-IDENTITY-COLLISION")
    owners: list[tuple[str, str]] = [
        ("prior-ca", doc["priorAuthority"]["caPublicKeySHA256"]),
        ("new-ca", doc["newAuthority"]["caPublicKeySHA256"]),
        ("cp", cp["publicKeySHA256"]),
    ]
    if cp["keyContinuity"] == "FRESH":
        owners.append(("cp-prior", cp_prior_key))
    owners += [(f"node:{m['pc']}", m["nodePublicKeySHA256"]) for m in doc["members"]]
    owners += [(f"role:{r['role']}", r["publicKeySHA256"]) for r in roles]
    owners = [(o, k) for o, k in owners if k is not None]
    for i, (oi, ki) in enumerate(owners):
        for oj, kj in owners[i + 1:]:
            if ki == kj and not (oi.startswith("node:") and oj.startswith("node:")):
                errors.add("AR-ROLE-SEPARATION")
    member_ids = {m["nodeID"] for m in doc["members"] if m["kind"] == "ROTATION"}
    foreign_row_keys = {r["publicKeySHA256"] for r in doc["existingNodeRows"]["rows"] if r["nodeID"] not in member_ids}
    if foreign_row_keys & {k for o, k in owners if not o.startswith("node:")}:
        errors.add("AR-ROLE-SEPARATION")
    for r in roles:
        cont = r["continuity"]
        if r["disposition"] == "REPLACED":
            if cont is not None:
                errors.add("AR-ROLE-CONTINUITY")
        elif cont is not None:
            if cont["compromiseDecision"] == "COMPROMISED":
                errors.add("AR-ROLE-CONTINUITY")
            if cont["scope"] is not None and cont["scope"] != ROLE_SCOPE[r["role"]]:
                errors.add("AR-ROLE-CONTINUITY")
    return sorted(errors)


def _counter_errors(doc: dict) -> list[str]:
    errors: set[str] = set()
    for m in doc["members"]:
        c = m["counters"]
        cb, ca, pf, pa = (c[k] for k in ("channelVersionBefore", "channelVersionAfter", "policyFloorBefore",
                                         "policyVersionAfter"))
        if m["kind"] == "ROTATION":
            if cb is not None and ca is not None and (cb < 1 or ca != cb + 1):
                errors.add("AR-CHANNEL-NONMONOTONE")
            if pf is not None and pa is not None and (pf < 1 or pa != pf + 1):
                errors.add("AR-POLICY-NONMONOTONE")
        elif (cb not in (None, 0)) or (ca not in (None, 1)) or (pf not in (None, 0)) or (pa not in (None, 1)):
            errors.add("AR-ENROLLMENT-COUNTER")
    return sorted(errors)


def _window_errors(doc: dict) -> list[str]:
    budgets = doc["measuredBudgets"]
    return ["AR-SERVING-WINDOW"] if any(budgets[k] is not None and budgets[k] > cap
                                        for k, cap in SERVING_WINDOWS.items()) else []


def _inventory_errors(doc: dict) -> list[str]:
    errors: set[str] = set()
    inventory = doc["controlPlaneClient"]["processInventory"]
    if inventory is not None:
        ids = [p["processID"] for p in inventory]
        if len(ids) != len(set(ids)) or {p["site"] for p in inventory} != set(SITES):
            errors.add("AR-PROCESS-INVENTORY")
    placement = doc["placement"]
    pcs = {m["pc"] for m in doc["members"]}
    host = placement["controlPlaneHostPC"]
    if (host is not None and host not in pcs) or set(placement["excludedPCs"]) & pcs:
        errors.add("AR-PLACEMENT")
    return sorted(errors)


def _checkpoint_errors(doc: dict) -> list[str]:
    cp = doc["checkpoint"]
    last, flight, outcome = cp["lastDurablePhase"], cp["inFlightPhase"], cp["inFlightOutcome"]
    if (flight is None) != (outcome is None):
        return ["AR-CHECKPOINT-ORDER"]
    if flight is not None and _idx(flight) != _idx(last) + 1:
        return ["AR-CHECKPOINT-ORDER"]
    if max(_idx(last), _idx(flight)) > INDEX[final_phase(doc)]:
        return ["AR-CHECKPOINT-ORDER"]
    if max(_idx(last), _idx(flight)) >= A1 and doc["status"] != "PROPOSED":
        return ["AR-CHECKPOINT-ORDER"]  # a plan with unknown inputs can never have started a mutation
    if _ts(cp["resumeAt"]) < _ts(doc["observedAt"]):
        return ["AR-CHECKPOINT-ORDER"]
    if ceremony_present(doc) and _idx(last) < A1 and flight != "A1_NEW_TRUST_AUTHORIZED":
        return ["AR-CHECKPOINT-ORDER"]  # A1 outputs cannot exist before A1 was attempted
    return []


def _ceremony_errors(doc: dict) -> list[str]:
    codes: set[str] = set()
    durable_a1 = _idx(doc["checkpoint"]["lastDurablePhase"]) >= A1
    manifest = doc["operationManifest"]
    if durable_a1 and (ceremony_missing(doc) or manifest is None):
        codes.add("AR-CEREMONY-INCOMPLETE")
    if manifest is not None and manifest != manifest_pin(doc):
        codes.add("AR-MANIFEST")
    return sorted(codes)


# ---------------------------------------------------------------- recovery decision


class _Context:
    def __init__(self, doc: dict):
        self.doc = doc
        cp = doc["checkpoint"]
        self.rb = cp["readback"]
        self.at = _ts(cp["resumeAt"])
        serving = self.rb["serving"]
        self.nonce = None if serving is None else serving["challengeNonce"]
        self.issued = None if serving is None else _ts(serving["challengeIssuedAt"])
        self.rows = {r["nodeID"]: r for r in self.rb["members"]}
        self.procs = {} if serving is None else {p["processID"]: p for p in serving["processes"]}
        self.shakes = {} if serving is None else {h["nodeID"]: h for h in serving["handshakes"]}
        self.live = {} if serving is None else {p["processID"]: p for p in serving["liveInventory"]["processes"]}
        self.freshness = window(doc, "observationFreshnessSeconds")
        self.heartbeat = window(doc, "heartbeatFreshnessSeconds")
        self.skew = doc["advanceRenewal"]["clockSkewSeconds"] or 0
        tt = doc["trustTransition"]
        self.prior_d = anchor_digest([doc["priorAuthority"]["caCertificateSHA256"]])
        self.staged_d = None if tt["stagedAnchorBundle"] is None else anchor_digest(tt["stagedAnchorBundle"])
        self.final_d = None if tt["finalAnchorBundle"] is None else anchor_digest(tt["finalAnchorBundle"])
        self.kinds = {m["nodeID"]: m["kind"] for m in doc["members"]}

    def fresh(self, observed_at: str | None, received_at: str | None, nonce: str | None) -> bool:
        """Answers this challenge, received by the CP (trusted clock) after issuance and within the
        freshness window, with the responder's own clock within the skew bound of that receipt."""
        if observed_at is None or received_at is None or self.nonce is None or nonce != self.nonce:
            return False
        observed, received = _ts(observed_at), _ts(received_at)
        return (self.issued <= received <= self.at and (self.at - received).total_seconds() <= self.freshness
                and abs((observed - received).total_seconds()) <= self.skew)


def _duplicates(rb: dict) -> bool:
    def dup(items, key):
        values = [i[key] for i in items]
        return len(values) != len(set(values))

    serving = rb["serving"] or {"processes": [], "handshakes": [], "liveInventory": {"processes": []}}
    return (dup(rb["members"], "nodeID") or dup(rb["reservations"], "nodeID")
            or dup(serving["processes"], "processID") or dup(serving["handshakes"], "nodeID")
            or dup(serving["liveInventory"]["processes"], "processID"))


def _serving_hold(doc: dict, ctx: "_Context") -> str | None:
    """Gate every post-A1 decision on one fresh, unconsumed challenge and an unchanged live inventory."""
    serving = ctx.rb["serving"]
    if serving is None or serving["challengeNonce"] in doc["checkpoint"]["consumedChallengeNonces"]:
        return "HOLD_SERVING_EVIDENCE_INCOMPLETE"  # no challenge, or a challenge an earlier decision used
    age = (ctx.at - ctx.issued).total_seconds()
    if age < 0 or age > window(doc, "challengeLifetimeSeconds"):
        return "HOLD_SERVING_EVIDENCE_INCOMPLETE"  # issuance itself is too old (or in the future)
    live = serving["liveInventory"]
    if live["source"] != "CP_PROCESS_REGISTRY" or not ctx.fresh(live["observedAt"], live["receivedAt"],
                                                                 live["challengeNonce"]):
        return "HOLD_SERVING_EVIDENCE_INCOMPLETE"
    planned = {p["processID"]: (p["site"], p["kind"]) for p in doc["controlPlaneClient"]["processInventory"]}
    if {pid: (p["site"], p["kind"]) for pid, p in ctx.live.items()} != planned:
        return "HOLD_PROCESS_INVENTORY_CHANGED"  # a replica started, stopped or moved: re-plan, never ignore it
    if any(planned.get(pid, (None,))[0] != p["site"] for pid, p in ctx.procs.items()):
        return "HOLD_PROCESS_INVENTORY_CHANGED"  # trust readback from a process the plan does not cover
    return None


def op_state(doc: dict, op: dict, ctx: _Context | None = None) -> str:
    """PENDING (exact preimage), COMMITTED (exact postimage + audit), CONFLICT, ABOVE_PLAN or UNVERIFIED."""
    ctx = ctx or _Context(doc)
    kind, target, pre, post = op["kind"], op["target"], op["pre"], op["post"]
    row = ctx.rows.get(target)
    present = row is not None  # one representation: a readback row exists iff the DB returned it
    node_fresh = present and ctx.fresh(row["nodeObservedAt"], row["nodeReceivedAt"], row["nodeChallengeNonce"])
    enrolling = ctx.kinds.get(target) == "NEW_ENROLLMENT"
    if kind in ("ANCHOR_STAGE", "ANCHOR_RETIRE", "LEAF_INSTALL"):
        if not present:
            return CONFLICT
        if not node_fresh:
            return UNVERIFIED
        if kind == "LEAF_INSTALL":
            value = row["installedLeafSHA256"]
            return PENDING if value == pre["installedLeafSHA256"] else (
                COMMITTED if value == post["installedLeafSHA256"] else CONFLICT)
        value = row["stagedAnchorDigest"]
        if kind == "ANCHOR_STAGE":
            if value == pre["stagedAnchorDigest"]:
                return PENDING
            return COMMITTED if value in (post["stagedAnchorDigest"], ctx.final_d) else CONFLICT
        if value in (ctx.prior_d, pre["stagedAnchorDigest"]):
            return PENDING
        return COMMITTED if value == post["stagedAnchorDigest"] else CONFLICT
    if kind in ("CHANNEL_CAS", "CHANNEL_PROVISION"):
        if not present:
            return PENDING if kind == "CHANNEL_PROVISION" else CONFLICT
        audits = row["channelAuditOpIDs"].count(op["opID"])
        version, cert = row["channelVersion"], row["channelCertificateSHA256"]
        if version == pre["channelVersion"] and cert == pre["channelCertificateSHA256"] and audits == 0:
            return PENDING
        if version == post["channelVersion"] and cert == post["channelCertificateSHA256"] and audits == 1:
            return COMMITTED
        return CONFLICT
    if kind == "POLICY_PUBLISH":
        if not present:
            return PENDING if enrolling else CONFLICT
        if not node_fresh:
            return UNVERIFIED
        floor, installed = row["policyFloor"], row["installedPolicyDigest"]
        journal = row["policyJournalOpIDs"].count(op["opID"])
        if floor is None or floor < pre["policyFloor"]:
            return CONFLICT
        if floor > post["policyFloor"]:
            return ABOVE_PLAN
        if floor == pre["policyFloor"] and installed == pre["installedPolicyDigest"] and journal == 0:
            return PENDING
        if (floor == post["policyFloor"] and installed == post["installedPolicyDigest"] and journal == 1
                and row["installedPolicyNotAfter"] == post["installedPolicyNotAfter"]):
            return COMMITTED
        return CONFLICT
    if kind in ("CP_CONTEXT_SWITCH", "CP_ANCHOR_RETIRE"):
        proc, live = ctx.procs.get(target), ctx.live.get(target)
        if (proc is None or live is None or proc["instanceID"] != live["instanceID"]
                or not ctx.fresh(proc["observedAt"], proc["receivedAt"], proc["challengeNonce"])):
            return UNVERIFIED  # no readback, or a readback from an instance that is no longer the live one
        leaf, loaded = proc["clientLeafSHA256"], proc["loadedAnchorDigest"]
        if kind == "CP_CONTEXT_SWITCH":
            if leaf == pre["clientLeafSHA256"] and loaded == pre["loadedAnchorDigest"]:
                return PENDING
            if (leaf == post["clientLeafSHA256"] and loaded in (post["loadedAnchorDigest"], ctx.final_d)
                    and proc["trustGeneration"] == post["trustGeneration"]):
                return COMMITTED
            return CONFLICT
        planned_leaf = ctx.doc["controlPlaneClient"]["plannedLeafSHA256"]
        if loaded == ctx.prior_d and leaf != planned_leaf:
            return PENDING  # not switched yet
        if leaf != planned_leaf:
            return CONFLICT
        return PENDING if loaded == pre["loadedAnchorDigest"] else (
            COMMITTED if loaded == post["loadedAnchorDigest"] else CONFLICT)
    if kind == "RESERVE":
        found = [r for r in ctx.rb["reservations"] if r["nodeID"] == target]
        if not found:
            return PENDING
        ok = (found[0]["reservationDigest"] == post["reservationDigest"]
              and found[0]["fenceToken"] == ctx.doc["writerFence"]["token"])
        return COMMITTED if ok else CONFLICT
    if kind == "ROW_ADMIT":
        if not present:
            return PENDING
        return COMMITTED if row["reservationDigest"] == post["reservationDigest"] else CONFLICT
    if kind == "SETTLE":
        shake = ctx.shakes.get(target)
        if shake is None or not ctx.fresh(shake["observedAt"], shake["receivedAt"], shake["challengeNonce"]):
            return PENDING
        if shake["peerLeafSHA256"] != post["peerLeafSHA256"]:
            return CONFLICT
        heartbeat = _ts(shake["heartbeatAt"])
        if (shake["anchorDigest"] == post["anchorDigest"] and shake["policyDigest"] == post["policyDigest"]
                and shake["cpClientURI"] == ctx.doc["controlPlaneClient"]["spiffeURI"]
                and heartbeat <= ctx.at and (ctx.at - heartbeat).total_seconds() <= ctx.heartbeat):
            return COMMITTED
        return PENDING
    raise ValueError(f"unknown operation kind {kind}")


def _hold_for(op: dict, state: str, position: str) -> str | None:
    """Map an operation state at a journal position to a HOLD, or None when it is acceptable."""
    kind = op["kind"]
    if state == ABOVE_PLAN:
        return "HOLD_POLICY_ABOVE_PLAN"
    if position == "future":
        if kind == "SETTLE" or state in (PENDING, UNVERIFIED):
            return None  # pre-settlement handshakes and not-yet-observed processes are normal
        return "HOLD_FOREIGN_WRITER"  # an effect of a phase that never started
    if state == UNVERIFIED:
        return ("HOLD_ANCHOR_STAGING_UNVERIFIED" if kind in ("ANCHOR_STAGE", "ANCHOR_RETIRE")
                else "HOLD_SERVING_EVIDENCE_INCOMPLETE")
    if state == CONFLICT:
        return "HOLD_FOREIGN_WRITER"
    if position == "durable" and state == PENDING:
        return "HOLD_SERVING_EVIDENCE_INCOMPLETE" if kind == "SETTLE" else "HOLD_FOREIGN_WRITER"
    if position == "next" and state == COMMITTED and kind != "SETTLE":
        return "HOLD_FOREIGN_WRITER"  # landed although the phase was never marked in flight
    return None


def deadline_insufficient(doc: dict, resume_phase: str) -> bool:
    """True when actual validity at resumeAt cannot cover the outstanding work (F5)."""
    at = _ts(doc["checkpoint"]["resumeAt"])
    budgets = doc["measuredBudgets"]["phaseSeconds"]
    phases = plan_phases(doc)[INDEX[resume_phase]:]
    if any(budgets.get(p) is None for p in phases):
        return True
    r = doc["advanceRenewal"]
    end = at + timedelta(seconds=sum(budgets[p] for p in phases) + r["safetySeconds"] + r["clockSkewSeconds"])
    new = doc["newAuthority"]
    if at < _ts(new["notBefore"]) or (_ts(new["notAfter"]) - end).total_seconds() <= r["caWarningLeadSeconds"]:
        return True
    lv = new["leafValidity"]
    if at < _ts(lv["notBefore"]) or (_ts(lv["notAfter"]) - end).total_seconds() < r["leafRenewalLeadSeconds"]:
        return True
    for m in doc["members"]:
        p = m["plannedPolicy"]
        if p is not None and (at < _ts(p["notBefore"])  # relied upon from publication, which may be now
                              or (_ts(p["notAfter"]) - end).total_seconds() < r["policyRenewalLeadSeconds"]):
            return True
    if doc["mode"] == "ADVANCE_RENEWAL" and INDEX[resume_phase] <= A7:
        if end > _ts(doc["priorAuthority"]["notAfter"]):
            return True
        overlap = doc["trustTransition"]["overlap"]
        if dual(doc) and overlap is not None and end > _ts(overlap["mustEndBy"]):
            return True
        # Still-serving prior leaves (Nodes and the CP client) must outlive the remaining work.
        for holder in [m for m in doc["members"] if m["kind"] == "ROTATION"] + [doc["controlPlaneClient"]]:
            cert = load_certificate(holder["priorLeafDER"])
            if cert is None or end > cert.not_valid_after_utc:
                return True
        # The installed prior policy, known only by digest in the plan, is judged on its validity readback.
        rows = {row["nodeID"]: row for row in doc["checkpoint"]["readback"]["members"]}
        for m in _on_prior_policy(doc, rows, resume_phase):
            value = rows[m["nodeID"]]["installedPolicyNotAfter"]
            if value is None or end > _ts(value):
                return True
    return False


def _on_prior_policy(doc: dict, rows: dict, resume_phase: str) -> list[dict]:
    """ADVANCE_RENEWAL rotation members still relying on their installed prior policy."""
    if doc["mode"] != "ADVANCE_RENEWAL" or INDEX[resume_phase] > INDEX["A5_POLICY_PUBLISHED"]:
        return []
    return [m for m in doc["members"] if m["kind"] == "ROTATION" and m["nodeID"] in rows
            and rows[m["nodeID"]]["installedPolicyDigest"] == m["priorPolicyDigest"]]


def validity_lapsed(doc: dict, at: datetime) -> bool:
    """True when a credential or policy the settled cohort relies on is outside its validity at ``at``:
    not yet valid, or within the safety + skew margin of its end (the new CA, every leaf, every policy)."""
    r = doc["advanceRenewal"]
    margin = timedelta(seconds=r["safetySeconds"] + r["clockSkewSeconds"])
    new = doc["newAuthority"]
    windows = [(new["notBefore"], new["notAfter"]),
               (new["leafValidity"]["notBefore"], new["leafValidity"]["notAfter"])]
    for m in doc["members"]:
        p = m["plannedPolicy"] or {"notBefore": None, "notAfter": None}
        windows.append((p["notBefore"], p["notAfter"]))
    return any(nb is None or na is None or at < _ts(nb) or at + margin >= _ts(na) for nb, na in windows)


def fence_held(doc: dict) -> bool:
    """True only when the live writer fence is held by exactly this plan, at its planned generation,
    and was read back fresh at resumeAt. Checked before every decision that can write, including
    the decisions taken while A1 (the ceremony) is in flight."""
    plan = doc["writerFence"]
    fence = doc["checkpoint"]["readback"]["writerFence"]
    if fence is None or plan["token"] is None or plan["generation"] is None:
        return False  # missing
    if fence["token"] != plan["token"] or fence["holderPlanDigest"] != plan_digest(doc):
        return False  # transferred to another writer or another plan
    if fence["generation"] != plan["generation"]:
        return False  # stale: the fence was re-acquired after this plan took it
    if fence["readAt"] is None:
        return False
    read, at = _ts(fence["readAt"]), _ts(doc["checkpoint"]["resumeAt"])
    return read <= at and (at - read).total_seconds() <= window(doc, "observationFreshnessSeconds")


def _a1_custody_hold(doc: dict) -> str | None:
    """A1 in flight with a key in custody: the plan must record which key, and the log must agree."""
    new = doc["newAuthority"]
    if new["certificateDER"] is None or new["caPublicKeySHA256"] is None:
        return "HOLD_CUSTODY_UNRESOLVED"  # a key exists that the plan never recorded: cannot "match plan"
    return _ceremony_log_hold(doc, durable_a1=False)


def _ceremony_log_hold(doc: dict, durable_a1: bool) -> str | None:
    log = doc["checkpoint"]["readback"]["ceremonyLog"]
    if log is None:
        return "HOLD_CUSTODY_UNRESOLVED"  # no log: what was signed is unknown
    if log["caKeysCreated"] != 1:
        return "HOLD_CUSTODY_UNRESOLVED"  # a second CA key "to be safe", or a key custody cannot account for
    planned = {m["nodeID"]: m["plannedLeafSHA256"] for m in doc["members"]}
    planned["control-plane"] = doc["controlPlaneClient"]["plannedLeafSHA256"]
    signed = [(s["subject"], s["leafSHA256"]) for s in log["signed"]]
    if len(signed) != len(set(signed)):
        return "HOLD_DUPLICATE_EVIDENCE"
    for subject, leaf in signed:
        if subject not in planned:
            return "HOLD_FOREIGN_WRITER"  # a leaf signed for an identity outside the plan
        if planned[subject] is None:
            return "HOLD_CUSTODY_UNRESOLVED"  # signed, but the plan does not yet record what
        if leaf != planned[subject]:
            return "HOLD_FOREIGN_WRITER"  # a second, different issuance for a planned identity
    if durable_a1 and {s for s, _ in signed} != set(planned):
        return "HOLD_CUSTODY_UNRESOLVED"
    return None


def recovery_action(doc: dict) -> tuple[str, str | None, list[str], list[str]]:
    """The only permitted next step: (action, resume phase, ops to apply, ops to acknowledge)."""
    cp = doc["checkpoint"]
    rb = cp["readback"]
    last, flight, outcome = cp["lastDurablePhase"], cp["inFlightPhase"], cp["inFlightOutcome"]
    none: tuple[list[str], list[str]] = ([], [])
    if last is None and flight is None:
        return "NOT_STARTED", None, *none
    li = _idx(last)
    if li < A1 and flight in (None, "A0_PREFLIGHT_READBACK"):
        return "ABANDON_BEFORE_NEW_TRUST", None, *none
    if not rb["dbAvailable"]:
        return "HOLD_DB_READBACK_REQUIRED", None, *none
    if rb["epoch"] != doc["preservedEpoch"]["epoch"]:
        return "HOLD_EPOCH_DIVERGED", None, *none
    if not fence_held(doc):  # before any custody, ceremony or resume decision, A1 in flight included
        return "HOLD_WRITER_FENCE", None, *none
    custody = rb["custodyState"]
    if li < A1:  # A1 in flight
        if outcome in ("FAILED_BEFORE_MUTATION", "UNKNOWN") and custody == "NO_NEW_KEY":
            return "ABANDON_BEFORE_NEW_TRUST", None, *none
        if custody != "NEW_KEY_PRESENT_MATCHES_PLAN":
            return "HOLD_CUSTODY_UNRESOLVED", None, *none
    elif custody != "NEW_KEY_PRESENT_MATCHES_PLAN":
        return "HOLD_CUSTODY_UNRESOLVED", None, *none
    if _duplicates(rb):
        return "HOLD_DUPLICATE_EVIDENCE", None, *none
    if li < A1:  # A1 in flight with the planned key present: deterministic re-signing only
        hold = _a1_custody_hold(doc)  # always: an absent log or unrecorded key is never "nothing to check"
        if hold:
            return hold, None, *none
        if deadline_insufficient(doc, "A1_NEW_TRUST_AUTHORIZED"):
            return "HOLD_DEADLINE_INSUFFICIENT", None, *none
        return "RESUME_FORWARD", "A1_NEW_TRUST_AUTHORIZED", *none
    hold = _ceremony_log_hold(doc, durable_a1=True)
    if hold:
        return hold, None, *none
    pinned = doc["operationManifest"]
    manifest = expected_manifest(doc)
    if pinned is None or manifest is None or pinned != manifest_pin(doc):
        return "HOLD_MANIFEST_MISMATCH", None, *none
    if rb["journalManifestDigest"] != manifest["digest"]:
        return "HOLD_MANIFEST_MISMATCH", None, *none
    ctx = _Context(doc)
    hold = _serving_hold(doc, ctx)
    if hold:
        return hold, None, *none
    planned_ids = {m["nodeID"] for m in doc["members"]}
    known = {r["nodeID"] for r in doc["existingNodeRows"]["rows"]}
    for node_id, row in ctx.rows.items():
        if node_id not in planned_ids and node_id not in known:
            return "HOLD_UNPLANNED_ROW", None, *none
    for m in doc["members"]:
        if m["kind"] != "NEW_ENROLLMENT":
            continue
        row = ctx.rows.get(m["nodeID"])
        found = [r for r in rb["reservations"] if r["nodeID"] == m["nodeID"]]
        if li < A7 and (row is not None or found):
            return "HOLD_ENROLLMENT_BEFORE_ROTATION_SETTLED", None, *none
        rd = reservation_digest(m)
        if any(r["reservationDigest"] != rd or r["fenceToken"] != doc["writerFence"]["token"] for r in found):
            return "HOLD_RESERVATION_MISMATCH", None, *none
        if row is not None and row["reservationDigest"] != rd:
            return "HOLD_RESERVATION_MISMATCH", None, *none
    final = final_phase(doc)
    resume = flight if flight is not None else (None if last == final else PHASES[li + 1])
    ri = _idx(resume)
    apply: list[str] = []
    ack: list[str] = []
    for op in manifest["operations"]:
        pi = INDEX[op["phase"]]
        position = "durable" if pi <= li else ("future" if pi > ri else ("flight" if flight else "next"))
        state = op_state(doc, op, ctx)
        hold = _hold_for(op, state, position)
        if hold:
            return hold, None, *none
        if position in ("flight", "next"):
            (apply if state == PENDING else ack).append(op["opID"])
    if resume is None:  # settled: judge validity at the final observation, never from the journal alone
        return ("HOLD_VALIDITY_LAPSED" if validity_lapsed(doc, ctx.at) else "COMPLETE"), None, *none
    if any(not ctx.fresh(ctx.rows[m["nodeID"]]["nodeObservedAt"], ctx.rows[m["nodeID"]]["nodeReceivedAt"],
                         ctx.rows[m["nodeID"]]["nodeChallengeNonce"])
           or ctx.rows[m["nodeID"]]["installedPolicyNotAfter"] is None
           for m in _on_prior_policy(doc, ctx.rows, resume)):
        return "HOLD_SERVING_EVIDENCE_INCOMPLETE", None, *none  # a dependency in use without validity readback
    if deadline_insufficient(doc, resume):
        return "HOLD_DEADLINE_INSUFFICIENT", None, *none
    return "RESUME_FORWARD", resume, apply, ack


# ---------------------------------------------------------------- reference executor model


class ExecutorConflict(Exception):
    """The model refuses an operation whose preimage does not match (cf. NODE-0034)."""


def apply_op(doc: dict, op: dict) -> bool:
    """Apply one manifest operation's exact postimage to the readback model. Returns True on mutation."""
    rb = doc["checkpoint"]["readback"]
    observed_at = _iso(_ts(doc["checkpoint"]["resumeAt"]) - timedelta(seconds=30))
    stamp = {"nodeObservedAt": observed_at, "nodeReceivedAt": observed_at,
             "nodeChallengeNonce": rb["serving"]["challengeNonce"]}
    kind, target, post = op["kind"], op["target"], op["post"]
    rows = {r["nodeID"]: r for r in rb["members"]}
    row = rows.get(target)
    if kind in ("ANCHOR_STAGE", "ANCHOR_RETIRE"):
        row.update(stagedAnchorDigest=post["stagedAnchorDigest"], **stamp)
    elif kind == "LEAF_INSTALL":
        row.update(installedLeafSHA256=post["installedLeafSHA256"], **stamp)
    elif kind in ("CHANNEL_CAS", "CHANNEL_PROVISION"):
        row.update(channelVersion=post["channelVersion"], channelCertificateSHA256=post["channelCertificateSHA256"])
        row["channelAuditOpIDs"] = row["channelAuditOpIDs"] + [op["opID"]]
    elif kind == "POLICY_PUBLISH":
        row.update(policyFloor=post["policyFloor"], installedPolicyDigest=post["installedPolicyDigest"],
                   installedPolicyNotAfter=post["installedPolicyNotAfter"], **stamp)
        row["policyJournalOpIDs"] = row["policyJournalOpIDs"] + [op["opID"]]
    elif kind in ("CP_CONTEXT_SWITCH", "CP_ANCHOR_RETIRE"):
        proc = next(p for p in rb["serving"]["processes"] if p["processID"] == target)
        proc.update({k: v for k, v in post.items()}, observedAt=observed_at, receivedAt=observed_at,
                    challengeNonce=rb["serving"]["challengeNonce"])
    elif kind == "RESERVE":
        rb["reservations"].append({"nodeID": target, "reservationDigest": post["reservationDigest"],
                                   "fenceToken": doc["writerFence"]["token"]})
    elif kind == "ROW_ADMIT":
        if row is not None:  # never a second row for one NodeID: admission updates nothing in place
            raise ExecutorConflict(op["opID"])
        member = next(m for m in doc["members"] if m["nodeID"] == target)
        rb["members"].append({
            "nodeID": target, "reservationDigest": post["reservationDigest"],
            "channelVersion": 0, "channelCertificateSHA256": None, "channelAuditOpIDs": [],
            "policyFloor": 0, "installedPolicyDigest": None, "installedPolicyNotAfter": None,
            "policyJournalOpIDs": [],
            "installedLeafSHA256": member["plannedLeafSHA256"],
            "stagedAnchorDigest": anchor_digest(doc["trustTransition"]["finalAnchorBundle"]), **stamp})
    elif kind == "SETTLE":
        handshakes = rb["serving"]["handshakes"]
        handshakes[:] = [h for h in handshakes if h["nodeID"] != target]
        handshakes.append({"nodeID": target, "observedAt": observed_at, "receivedAt": observed_at,
                           "challengeNonce": rb["serving"]["challengeNonce"], "peerLeafSHA256": post["peerLeafSHA256"],
                           "anchorDigest": post["anchorDigest"], "cpClientURI": doc["controlPlaneClient"]["spiffeURI"],
                           "heartbeatAt": _iso(_ts(doc["checkpoint"]["resumeAt"]) - timedelta(seconds=5)),
                           "policyDigest": post["policyDigest"]})
        return False
    else:
        raise ValueError(kind)
    return True


def execute_resume(doc: dict) -> tuple[dict, list[str]]:
    """Model one fenced execution of the decided resume step, crashing before the journal write.

    Returns the new document (same journal position, phase now in flight with outcome UNKNOWN)
    and the list of mutating operation IDs. Raises ExecutorConflict on any preimage mismatch.
    """
    action, phase, apply, _ = recovery_action(doc)
    if action != "RESUME_FORWARD":
        raise ValueError(f"not resumable: {action}")
    if not fence_held(doc):  # defence in depth: the model never writes without the live fence
        raise ExecutorConflict("writer fence not held")
    new = copy.deepcopy(doc)
    mutations: list[str] = []
    if phase == "A1_NEW_TRUST_AUTHORIZED":
        log = new["checkpoint"]["readback"]["ceremonyLog"]
        if log is None:
            raise ExecutorConflict("no ceremony log")
        signed = {(s["subject"], s["leafSHA256"]) for s in log["signed"]}
        wanted = [(m["nodeID"], m["plannedLeafSHA256"]) for m in new["members"]]
        wanted.append(("control-plane", new["controlPlaneClient"]["plannedLeafSHA256"]))
        for subject, leaf in wanted:
            if leaf is not None and (subject, leaf) not in signed:  # deterministic Ed25519 re-signing
                log["signed"].append({"subject": subject, "leafSHA256": leaf})
                mutations.append(f"sign:{subject}")
    ops = {op["opID"]: op for op in (expected_manifest(new) or {"operations": []})["operations"]}
    for op_id in apply:
        if op_state(new, ops[op_id]) != PENDING:
            raise ExecutorConflict(op_id)
        if apply_op(new, ops[op_id]):
            mutations.append(op_id)
    cp = new["checkpoint"]
    if phase != "A1_NEW_TRUST_AUTHORIZED":
        cp["consumedChallengeNonces"].append(cp["readback"]["serving"]["challengeNonce"])  # one use
    if cp["inFlightPhase"] is None:
        cp["inFlightPhase"], cp["inFlightOutcome"] = phase, "UNKNOWN"
    return new, mutations


def observe(doc: dict, nonce: str) -> dict:
    """Model a fresh Root readback under a new one-use challenge issued by the CP. The world state is
    unchanged; every observation the model holds is re-stamped with the new challenge and CP times."""
    new = copy.deepcopy(doc)
    cp = new["checkpoint"]
    rb = cp["readback"]
    at = _ts(cp["resumeAt"])
    seen = _iso(at - timedelta(seconds=30))
    if rb["writerFence"] is not None:
        rb["writerFence"]["readAt"] = seen
    serving = rb["serving"]
    if serving is None:
        return new
    serving.update(challengeNonce=nonce, challengeIssuedAt=_iso(at - timedelta(seconds=60)))
    for row in rb["members"]:
        if row["nodeObservedAt"] is not None:
            row.update(nodeObservedAt=seen, nodeReceivedAt=seen, nodeChallengeNonce=nonce)
    for proc in serving["processes"]:
        proc.update(observedAt=seen, receivedAt=seen, challengeNonce=nonce)
    for shake in serving["handshakes"]:
        shake.update(observedAt=seen, receivedAt=seen, challengeNonce=nonce,
                     heartbeatAt=_iso(at - timedelta(seconds=5)))
    serving["liveInventory"].update(observedAt=seen, receivedAt=seen, challengeNonce=nonce)
    return new


def journal_durable(doc: dict) -> dict:
    """Model the journal write after a phase's effects are acknowledged."""
    new = copy.deepcopy(doc)
    cp = new["checkpoint"]
    cp["lastDurablePhase"], cp["inFlightPhase"], cp["inFlightOutcome"] = cp["inFlightPhase"], None, None
    return new


# ---------------------------------------------------------------- evaluation


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
    codes.update(_inventory_errors(doc))
    codes.update(_window_errors(doc))
    if doc["status"] == "PROPOSED" and _nulls(doc):
        codes.add("AR-HOLD-REQUIRED")
    order = _checkpoint_errors(doc)
    codes.update(order)
    if not order:
        codes.update(_ceremony_errors(doc))
    if not codes:
        cp = doc["checkpoint"]
        got = recovery_action(doc)
        want = (cp["expectedRecoveryAction"], cp["expectedResumePhase"], cp["expectedApply"], cp["expectedAcknowledge"])
        if got != want:
            codes.add("AR-RECOVERY-MISMATCH")
    return sorted(codes)


HANDOFF_SCHEMA = "fleet5-authority-replacement-enrollment-handoff:2"
VERIFIER = "tools/five_node_lab_preflight.py"


def enrollment_handoff(doc: dict, source_rel: str, source_bytes: bytes, *, hosts: dict[str, str],
                       control_plane_host: str, at: str | None = None) -> dict:
    """Operator handoff after a settled enrollment (R2: scoped as four-member migration evidence).

    Refuses unless the plan is internally consistent, recovery_action is COMPLETE, and every credential
    and policy is still valid at the handoff time ``at`` (default: the settled observation, resumeAt).
    """
    from tools.five_node_lab_preflight import (
        FIVE_NODE_INVENTORY_SCHEMA_VERSION,
        FIVE_NODE_PROFILE,
        five_node_inventory_revision,
        validate_five_node_inventory,
    )

    codes = evaluate(doc)
    if codes:
        raise ValueError(f"plan rejected: {codes}")
    if recovery_action(doc)[0] != "COMPLETE":
        raise ValueError("handoff requires a COMPLETE (settled) plan")
    settled = _ts(doc["checkpoint"]["resumeAt"])
    when = settled if at is None else _ts(at)
    if when < settled:
        raise ValueError("a handoff cannot predate the settled observation")
    if validity_lapsed(doc, when):
        raise ValueError("a credential or policy is outside its validity at handoff time")
    r = doc["advanceRenewal"]
    lv = doc["newAuthority"]["leafValidity"]
    policy_end = min(_ts(m["plannedPolicy"]["notAfter"]) for m in doc["members"])
    enrolled = [m for m in doc["members"] if m["kind"] == "NEW_ENROLLMENT"]
    if len(enrolled) != 1:
        raise ValueError("handoff covers exactly one new enrollment")
    host_pc = doc["placement"]["controlPlaneHostPC"]
    if hosts[host_pc] != control_plane_host:
        raise ValueError("declared control-plane host PC does not match the inventory host")
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
    inventory = {"schemaVersion": FIVE_NODE_INVENTORY_SCHEMA_VERSION, "controlPlaneHostId": control_plane_host,
                 "nodes": nodes}
    inventory["revision"] = five_node_inventory_revision(inventory)
    validate_five_node_inventory(inventory)
    new = doc["newAuthority"]
    return {
        "schema": HANDOFF_SCHEMA,
        "fixture": doc.get("fixture") is True,
        "activation": "NOT_AUTHORIZED",
        "sourcePlan": source_rel,
        "sourcePlanSHA256": hashlib.sha256(source_bytes).hexdigest(),
        "acceptance": {
            "scope": "FOUR_MEMBER_MIGRATION",
            "members": [m["pc"] for m in doc["members"]],
            "fiveNodeReadiness": "NOT_ESTABLISHED",
            "excludedFromThisAdmission": doc["placement"]["excludedPCs"],
            "controlPlaneHostPC": host_pc,
            "reason": ("Four members and one CP-colocated Node: the five-node readiness expression "
                       "(five ready, one colocated, four eligible) cannot hold. Readiness is a separate decision."),
        },
        "newIdentity": {
            "pc": new_member["pc"],
            "nodeID": new_member["nodeID"],
            "spiffeURI": new_member["spiffeURI"],
            "epoch": doc["preservedEpoch"]["epoch"],
            "nodePublicKeySHA256": new_member["nodePublicKeySHA256"],
            "leafCertificateSHA256": new_member["plannedLeafSHA256"],
            "reservationDigest": reservation_digest(new_member),
            "channelVersion": new_member["counters"]["channelVersionAfter"],
            "policyVersion": new_member["counters"]["policyVersionAfter"],
        },
        "publicCAEvidence": {
            "caCertificateSHA256": new["caCertificateSHA256"],
            "caPublicKeySHA256": new["caPublicKeySHA256"],
            "subjectCommonName": new["subjectCommonName"],
            "notBefore": new["notBefore"],
            "notAfter": new["notAfter"],
            "finalAnchorBundle": doc["trustTransition"]["finalAnchorBundle"],
            "trustDecisionRef": new["trustAuthorization"]["decisionRef"],
            "excludedPriorCACertificateSHA256": doc["priorAuthority"]["caCertificateSHA256"],
            "operationManifestDigest": doc["operationManifest"]["digest"],
        },
        "validity": {
            "evaluatedAt": _iso(when),
            "validUntil": _iso(min(_ts(new["notAfter"]), _ts(lv["notAfter"]), policy_end)),
            "renewalDueBy": _iso(min(_ts(new["notAfter"]) - timedelta(seconds=r["caWarningLeadSeconds"]),
                                     _ts(lv["notAfter"]) - timedelta(seconds=r["leafRenewalLeadSeconds"]),
                                     policy_end - timedelta(seconds=r["policyRenewalLeadSeconds"]))),
            "consumer": "re-check validity at use; this handoff proves validity only at evaluatedAt",
        },
        "verifier": {
            "tool": VERIFIER,
            "consumes": ["nodeId", "ip", "certificateSHA256 (leaf DER, compared with inv.node_channels)",
                         "hostId", "failureDomainId", "coLocatedWithControlPlane", "revision"],
            "doesNotCheck": [
                "issuer chain to publicCAEvidence.caCertificateSHA256 (checked offline by this contract's "
                "checker on the plan's public DER; not by the verifier)",
                "SPIFFE URI / epoch inside the leaf",
                "a fresh mTLS handshake (only this plan's serving evidence records one)",
                "five-node readiness (acceptance.fiveNodeReadiness)",
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
        if not entry["path"].startswith("instances/") and doc.get("fixture") is not True:
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
    for entry in expectations.get("manifestSamples", []):
        path = CONTRACT_DIR / entry["path"]
        listed.add(path.resolve())
        source = json.loads((CONTRACT_DIR / entry["sourcePlan"]).read_text("utf-8"))
        sample = json.loads(path.read_text("utf-8"))
        if sample["manifest"] != expected_manifest(source) or manifest_pin(source) != source["operationManifest"]:
            failures.append(f"{entry['path']}: manifest sample differs from its source plan's frozen manifest")
    on_disk = {p.resolve() for p in CONTRACT_DIR.rglob("*.json")} - {SCHEMA_PATH.resolve(), EXPECTATIONS_PATH.resolve()}
    for path in sorted(on_disk - listed):
        failures.append(f"unlisted document: {path.relative_to(CONTRACT_DIR).as_posix()}")
    if not [e for e in expectations["documents"] if not e["codes"]] or not [
            e for e in expectations["documents"] if e["codes"]]:
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
            action = list(recovery_action(doc)) if not codes else None
            print(json.dumps({"file": str(path), "codes": codes, "recovery": action}))
            worst = worst or (1 if codes else 0)
        return worst
    failures = check_all()
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        return 1
    count = len(json.loads(EXPECTATIONS_PATH.read_text("utf-8"))["documents"])
    print(f"PASS fleet5 authority replacement R2: {count} documents matched their expected verdicts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
