"""Generate the PROPOSED FLEET5 authority-replacement R2 fixtures and expectations.

Writes static JSON under contracts/proposed/fleet5-authority-replacement-r2/. The
committed files are the reviewable artifact; tests regenerate in memory and fail
on drift.

Synthetic fixtures carry REAL ephemeral PKI: Ed25519 CA certificates, Node/CP
CSRs and leaves built with ``cryptography`` and verified by the checker. Every
fixture key is derived from a public label (sha256("fixture-key:<label>")), so the
keys are deliberately NOT secret and only their public certificates/CSRs are
written. Fixture IDs, addresses and labels are synthetic, never fleet values.
The single instances/ document is the real Nov18 fleet plan in HOLD with every
unknown left null.

    python tools/generate_fleet5_authority_replacement_r2_fixtures.py [--check]
"""

from __future__ import annotations

import argparse
import base64
import copy
from datetime import timedelta
import hashlib
from ipaddress import ip_address
import json
from pathlib import Path
import sys
from typing import Callable

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # script mode: allow `from tools import ...`
    sys.path.insert(0, str(ROOT))

from tools import check_fleet5_authority_replacement_r2 as checker  # noqa: E402

OUT = checker.CONTRACT_DIR
_ts, _iso = checker._ts, checker._iso


def h(label: str) -> str:
    return hashlib.sha256(f"fixture:{label}".encode()).hexdigest()


def nid(tag: str) -> str:
    return "nod_" + "0" * 22 + tag


def key(label: str) -> Ed25519PrivateKey:
    """Deterministic, publicly derivable fixture key. Never used outside synthetic fixtures."""
    return Ed25519PrivateKey.from_private_bytes(hashlib.sha256(f"fixture-key:{label}".encode()).digest())


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def der(cert) -> bytes:
    return cert.public_bytes(serialization.Encoding.DER)


def serial(label: str) -> int:
    return int.from_bytes(hashlib.sha256(f"serial:{label}".encode()).digest()[:15], "big") | 1


def spki(label: str) -> str:
    return checker.spki_sha256(key(label).public_key())


def make_ca(label: str, cn: str, not_before: str, not_after: str, *, ca: bool = True):
    k = key(label)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(k.public_key())
        .serial_number(serial(label))
        .not_valid_before(_ts(not_before))
        .not_valid_after(_ts(not_after))
        .add_extension(x509.BasicConstraints(ca=ca, path_length=0 if ca else None), critical=True)
        .add_extension(x509.KeyUsage(not ca, False, False, False, False, ca, ca, False, False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(k.public_key()), critical=False)
        .sign(k, None)
    )
    return k, cert


def make_leaf(ca_key, ca_cert, public_key, uri: str, address: str | None, *, not_before: str, not_after: str,
              label: str, client: bool = False, eku=None, ips: list[str] | None = None):
    names = [x509.UniformResourceIdentifier(uri)]
    for ip in (ips if ips is not None else ([] if client else [address])):
        names.append(x509.IPAddress(ip_address(ip)))
    usage = eku or (ExtendedKeyUsageOID.CLIENT_AUTH if client else ExtendedKeyUsageOID.SERVER_AUTH)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(
            NameOID.COMMON_NAME, "SaintVision control plane" if client else "SaintVision LAN peer")]))
        .issuer_name(ca_cert.subject)
        .public_key(public_key)
        .serial_number(serial(label))
        .not_valid_before(_ts(not_before))
        .not_valid_after(_ts(not_after))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False), critical=True)
        .add_extension(x509.ExtendedKeyUsage([usage]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(public_key), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .add_extension(x509.SubjectAlternativeName(names), critical=False)
        .sign(ca_key, None)
    )
    return cert


def make_csr(label: str, common_name: str) -> str:
    csr = (x509.CertificateSigningRequestBuilder()
           .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)]))
           .sign(key(label), None))
    return b64(csr.public_bytes(serialization.Encoding.DER))


def node_uri(tenant: str, node: str, epoch: str) -> str:
    return checker.SPIFFE_NODE.format(tenant=tenant, node=node, epoch=epoch)


def cp_uri(tenant: str, epoch: str) -> str:
    return checker.SPIFFE_CP.format(tenant=tenant, epoch=epoch)


TENANT = "00000000-0000-4000-8000-0000000000a1"
EPOCH = "00000000-0000-4000-8000-0000000000e1"
OTHER_EPOCH = "00000000-0000-4000-8000-0000000000e2"
OBSERVED = "2026-11-18T12:00:00Z"
RESUME = "2026-11-18T14:00:00Z"
NEW_CN = "SaintVision FLEET5 authority 2026-11 R2"
TERMINAL = {"label": "terminal-ca", "cn": "SaintVision LAN pilot CA", "notBefore": "2026-11-07T07:15:30Z",
            "notAfter": "2026-11-14T07:15:30Z", "leafNotBefore": "2026-11-08T07:15:30Z"}
CURRENT = {"label": "current-ca", "cn": "SaintVision FLEET5 authority 2026-01 R1", "notBefore": "2026-01-01T00:00:00Z",
           "notAfter": "2026-12-31T00:00:00Z", "leafNotBefore": "2026-11-15T00:00:00Z"}
ROTATION_PCS = ("PC2", "PC3", "PC4")
ADDRESS = {"PC1": "10.0.0.1", "PC2": "10.0.0.2", "PC3": "10.0.0.3", "PC4": "10.0.0.4"}
ACCOUNT = {"PC1": "inviz", "PC2": "saintvision-invion", "PC3": "saintvision-invion3", "PC4": "inviz"}
CHANNEL = {"PC2": 1, "PC3": 1, "PC4": 3}
FLOOR = {"PC2": 2, "PC3": 2, "PC4": 5}
INVENTORY = [
    {"site": "observer_worker", "processID": "observer-1", "kind": "SERVICE"},
    {"site": "delivery_worker", "processID": "delivery-1", "kind": "SERVICE"},
    {"site": "delivery_worker", "processID": "delivery-2", "kind": "SERVICE"},
    {"site": "workspace_runtime", "processID": "workspace-1", "kind": "SERVICE"},
    {"site": "build_product_runtime", "processID": "build-product-1", "kind": "SERVICE"},
    {"site": "storage_check_collector", "processID": "storage-check-cli", "kind": "INVOKED_CLIENT"},
]
NONCE = "fixture-challenge-0001"
FENCE_GENERATION = 7
FRESHNESS, HEARTBEAT, CHALLENGE = 120, 15, 300  # fixture "measured" serving windows (= the contract caps)


def prior_ca(doc: dict):
    world = TERMINAL if doc["mode"] == "TERMINAL_REPLACEMENT" else CURRENT
    return make_ca(world["label"], world["cn"], world["notBefore"], doc["priorAuthority"]["notAfter"]), world


def set_member_identity(doc: dict, m: dict, *, node_id: str, key_label: str, csr_cn: str | None = None) -> None:
    """(Re)derive a member's identity: NodeID, URI, Node key and its Node-signed CSR."""
    m["nodeID"] = node_id
    m["spiffeURI"] = node_uri(doc["tenantID"], node_id, doc["preservedEpoch"]["epoch"])
    m["nodePublicKeySHA256"] = spki(key_label)
    m["csrDER"] = make_csr(key_label, csr_cn or node_id)


def issue_prior_leaf(doc: dict, m: dict, key_label: str) -> None:
    (ca_key, ca_cert), world = prior_ca(doc)
    cert = make_leaf(ca_key, ca_cert, key(key_label).public_key(), m["spiffeURI"], m["address"],
                     not_before=world["leafNotBefore"], not_after=doc["priorAuthority"]["notAfter"],
                     label=f"prior-leaf:{m['pc']}:{key_label}")
    m["priorLeafDER"] = b64(der(cert))


def rotation_member(doc: dict, pc: str) -> dict:
    m = {"pc": pc, "kind": "ROTATION", "nodeID": None, "account": ACCOUNT[pc], "address": ADDRESS[pc],
         "endpoint": f"https://{ADDRESS[pc]}:7443", "spiffeURI": None, "nodePublicKeySHA256": None, "csrDER": None,
         "priorLeafDER": None, "priorPolicyDigest": h(f"{pc}-policy-prior"), "leafDER": None,
         "plannedLeafSHA256": None, "plannedPolicy": None,
         "counters": {"channelVersionBefore": CHANNEL[pc], "channelVersionAfter": CHANNEL[pc] + 1,
                      "policyFloorBefore": FLOOR[pc], "policyVersionAfter": FLOOR[pc] + 1},
         "reservation": None}
    set_member_identity(doc, m, node_id=nid("0" + pc), key_label=f"{pc}-node")
    issue_prior_leaf(doc, m, f"{pc}-node")
    return m


def enrollment_member(doc: dict) -> dict:
    m = {"pc": "PC1", "kind": "NEW_ENROLLMENT", "nodeID": None,
         # Same account name as PC4 on purpose: an account/host name is never identity.
         "account": "inviz", "address": ADDRESS["PC1"], "endpoint": f"https://{ADDRESS['PC1']}:7443",
         "spiffeURI": None, "nodePublicKeySHA256": None, "csrDER": None, "priorLeafDER": None,
         "priorPolicyDigest": None, "leafDER": None, "plannedLeafSHA256": None, "plannedPolicy": None,
         "counters": {"channelVersionBefore": 0, "channelVersionAfter": 1, "policyFloorBefore": 0,
                      "policyVersionAfter": 1},
         "reservation": {"tenantID": None, "epoch": None, "pc": "PC1", "nodeID": None, "csrSHA256": None,
                         "planDigest": None, "fenceToken": None, "rowsReadbackSHA256": None,
                         "nodeStateEmpty": {"verified": True, "evidenceRef": "fixture:node-state/pc1-empty"}}}
    set_member_identity(doc, m, node_id=nid("0PC1"), key_label="PC1-node-fresh")
    return m


def empty_readback(db: bool = True, epoch: str | None = EPOCH, custody: str = "NOT_READ") -> dict:
    return {"dbAvailable": db, "epoch": epoch, "custodyState": custody, "writerFence": None,
            "journalManifestDigest": None, "ceremonyLog": None, "members": [], "reservations": [], "serving": None}


def live_fence(doc: dict, resume_at: str, **override) -> dict:
    """The live writer-fence row as held by this plan, read 30 s before resumeAt."""
    fence = {"token": doc["writerFence"]["token"], "generation": doc["writerFence"]["generation"],
             "holderPlanDigest": checker.plan_digest(doc), "readAt": _iso(_ts(resume_at) - timedelta(seconds=30))}
    fence.update(override)
    return fence


def checkpoint(last=None, flight=None, outcome=None, resume_at=OBSERVED, readback=None) -> dict:
    return {"lastDurablePhase": last, "inFlightPhase": flight, "inFlightOutcome": outcome, "resumeAt": resume_at,
            "consumedChallengeNonces": [], "readback": readback or empty_readback(), "expectedRecoveryAction": "NOT_STARTED",
            "expectedResumePhase": None, "expectedApply": [], "expectedAcknowledge": []}


def proposal(name: str, *, mode: str = "TERMINAL_REPLACEMENT", enroll: bool = True, cutover: str | None = None,
             prior_not_after: str | None = None) -> dict:
    """A complete PROPOSED plan before A1: every pre-ceremony input known, no ceremony output."""
    terminal = mode == "TERMINAL_REPLACEMENT"
    world = TERMINAL if terminal else CURRENT
    cutover = cutover or ("TERMINAL_SINGLETON" if terminal else "DUAL_ANCHOR_OVERLAP")
    doc = {
        "schema": "fleet5-authority-replacement-plan:2",
        "revision": "R2",
        "planID": f"ARP-20261119-{name}"[:53],
        "status": "PROPOSED",
        "activation": "NOT_AUTHORIZED",
        "fixture": True,
        "mode": mode,
        "observedAt": OBSERVED,
        "tenantID": TENANT,
        "projectID": "prj_" + "0" * 24 + "P1",
        "preservedEpoch": {"epoch": EPOCH, "source": "DB_READBACK", "readbackSHA256": h("epoch-readback")},
        "priorAuthority": {"certificateDER": None, "caCertificateSHA256": None,
                           "caPublicKeySHA256": spki(world["label"]), "subjectCommonName": world["cn"],
                           "notAfter": prior_not_after or world["notAfter"],
                           "state": "CA_TERMINAL" if terminal else "CA_CURRENT",
                           "usage": "REFERENCE_ONLY" if terminal else "OVERLAP_ANCHOR_UNTIL_RETIRED"},
        "newAuthority": {
            "certificateDER": None, "caCertificateSHA256": None, "caPublicKeySHA256": None,
            "subjectCommonName": NEW_CN, "keyAlgorithm": "Ed25519", "keyGeneratedFresh": True,
            "crossSignedByPrior": False, "pathLength": 0,
            "notBefore": "2026-11-18T12:00:00Z", "notAfter": "2027-11-18T12:00:00Z",
            "leafValidity": {"notBefore": "2026-11-18T12:00:00Z", "notAfter": "2026-11-24T12:00:00Z"},
            "custody": {"holder": "ROOT_OFFLINE_OPERATOR", "privateMaterialInRepository": False,
                        "custodyEvidenceRef": "fixture:custody/new-ca"},
            "trustAuthorization": {"decisionRef": "fixture:decision/new-trust",
                                   "authorizedBy": "fixture-root-operator"},
        },
        "trustTransition": {
            "cutover": cutover,
            "overlap": ({"startsAt": "2026-11-18T12:00:00Z", "mustEndBy": "2026-11-19T06:00:00Z"}
                        if cutover == "DUAL_ANCHOR_OVERLAP" else None),
            "quiesceEvidenceRef": "fixture:quiesce/window" if cutover == "QUIESCED" else None,
            "targetGeneration": 2, "stagedAnchorBundle": None, "finalAnchorBundle": None,
        },
        "advanceRenewal": {
            "caLifetimeSeconds": 31536000, "caSuccessorLeadSeconds": 2592000, "caWarningLeadSeconds": 3888000,
            "leafLifetimeSeconds": 518400, "leafRenewalLeadSeconds": 259200, "policyLifetimeSeconds": 172800,
            "policyRenewalLeadSeconds": 86400, "overlapSeconds": 14400, "normalBudgetSeconds": 7200,
            "caSuccessorBudgetSeconds": 86400, "safetySeconds": 630, "clockSkewSeconds": 30,
        },
        "measuredBudgets": {"source": "MEASURED", "evidenceRef": "fixture:budget/measured",
                            "phaseSeconds": {p: 600 for p in checker.PHASES},
                            "observationFreshnessSeconds": FRESHNESS, "heartbeatFreshnessSeconds": HEARTBEAT,
                            "challengeLifetimeSeconds": CHALLENGE},
        "servingBinaryMigration": {"status": "REVIEWED", "reviewRef": "fixture:review/node-binary-migration"},
        "writerFence": {"token": "fence:fixture-arp-r2", "generation": FENCE_GENERATION},
        "placement": {"controlPlaneHostPC": "PC3", "excludedPCs": ["PC5"]},
        "controlPlaneClient": {"spiffeURI": cp_uri(TENANT, EPOCH), "keyContinuity": "RETAINED",
                               "publicKeySHA256": spki("cp-client"),
                               "csrDER": make_csr("cp-client", checker.CP_CSR_COMMON_NAME), "priorLeafDER": None,
                               "leafDER": None, "plannedLeafSHA256": None, "contextSites": list(checker.SITES),
                               "processInventory": copy.deepcopy(INVENTORY)},
        "roleKeys": [{"role": "LAUNCH_SIGNER", "publicKeySHA256": h("launch-signer-key"), "disposition": "RETAINED",
                      "continuity": {"verifiedBy": "fixture-custody-card", "scope": "LAUNCH_SIGNATURES",
                                     "custodyEvidenceRef": "fixture:custody/launch-signer",
                                     "compromiseDecision": "AFFIRMED_NOT_COMPROMISED",
                                     "decisionRef": "fixture:decision/launch-signer-not-compromised"}}],
        "members": [],
        "existingNodeRows": {"source": "DB_READBACK", "includesRetired": True, "readbackSHA256": h("rows-readback"),
                             "rows": []},
        "operationManifest": None,
        "checkpoint": checkpoint(),
    }
    (_, prior_cert), _ = prior_ca(doc)
    doc["priorAuthority"]["certificateDER"] = b64(der(prior_cert))
    doc["priorAuthority"]["caCertificateSHA256"] = checker.sha256_hex(der(prior_cert))
    cp = doc["controlPlaneClient"]
    (ca_key, ca_cert), _ = prior_ca(doc)
    cp["priorLeafDER"] = b64(der(make_leaf(ca_key, ca_cert, key("cp-client").public_key(), cp["spiffeURI"], None,
                                           client=True, not_before=world["leafNotBefore"],
                                           not_after=doc["priorAuthority"]["notAfter"], label="prior-cp-leaf")))
    doc["members"] = [rotation_member(doc, pc) for pc in ROTATION_PCS] + ([enrollment_member(doc)] if enroll else [])
    rows = [{"nodeID": m["nodeID"], "status": "ACTIVE", "publicKeySHA256": m["nodePublicKeySHA256"],
             "channelCertificateSHA256": checker.prior_leaf_sha(m)} for m in doc["members"] if m["kind"] == "ROTATION"]
    rows += [{"nodeID": nid("RTR1"), "status": "RETIRED", "publicKeySHA256": spki("RTR1-node"),
              "channelCertificateSHA256": h("RTR1-leaf")},
             {"nodeID": nid("RTR2"), "status": "DISABLED", "publicKeySHA256": spki("RTR2-node"),
              "channelCertificateSHA256": h("RTR2-leaf")}]
    doc["existingNodeRows"]["rows"] = rows
    return seal(doc)


def seal(doc: dict) -> dict:
    """Recompute every derived binding: reservations, then the frozen manifest pin."""
    for m in doc["members"]:
        if m["kind"] == "NEW_ENROLLMENT" and m["reservation"] is not None:
            m["reservation"].update({
                "tenantID": doc["tenantID"], "epoch": doc["preservedEpoch"]["epoch"], "pc": m["pc"],
                "nodeID": m["nodeID"], "csrSHA256": checker.sha256_hex(checker.der_bytes(m["csrDER"])),
                "planDigest": checker.plan_digest(doc), "fenceToken": doc["writerFence"]["token"],
                "rowsReadbackSHA256": doc["existingNodeRows"]["readbackSHA256"]})
    if checker.ceremony_present(doc):
        doc["operationManifest"] = checker.manifest_pin(doc)
    return doc


def ceremony(doc: dict, *, root_ca: bool = True, leaf_overrides: dict[str, dict] | None = None) -> dict:
    """The A1 offline ceremony: new root, every leaf from its CSR, policy bytes, anchor bundles."""
    new = doc["newAuthority"]
    root_key, root = make_ca("new-ca", new["subjectCommonName"], new["notBefore"], new["notAfter"], ca=root_ca)
    new["certificateDER"] = b64(der(root))
    new["caCertificateSHA256"] = checker.sha256_hex(der(root))
    new["caPublicKeySHA256"] = checker.spki_sha256(root_key.public_key())
    lv = new["leafValidity"]
    overrides = leaf_overrides or {}
    for m in doc["members"]:
        o = overrides.get(m["pc"], {})
        csr = x509.load_der_x509_csr(checker.der_bytes(m["csrDER"]))
        signer_key, signer = (make_ca(*o["signer"], new["notBefore"], new["notAfter"]) if "signer" in o
                              else (root_key, root))
        cert = make_leaf(signer_key, signer, csr.public_key(), o.get("uri", m["spiffeURI"]), m["address"],
                         not_before=lv["notBefore"], not_after=o.get("notAfter", lv["notAfter"]),
                         label=f"leaf:{m['pc']}", eku=o.get("eku"), ips=o.get("ips"))
        m["leafDER"] = b64(der(cert))
        m["plannedLeafSHA256"] = checker.sha256_hex(der(cert))
        m["plannedPolicy"] = {"digest": h(f"{m['pc']}-policy-new"), "notBefore": "2026-11-18T12:00:00Z",
                              "notAfter": "2026-11-20T12:00:00Z"}
    cp = doc["controlPlaneClient"]
    csr = x509.load_der_x509_csr(checker.der_bytes(cp["csrDER"]))
    cert = make_leaf(root_key, root, csr.public_key(), cp["spiffeURI"], None, client=True,
                     not_before=lv["notBefore"], not_after=lv["notAfter"], label="leaf:control-plane")
    cp["leafDER"] = b64(der(cert))
    cp["plannedLeafSHA256"] = checker.sha256_hex(der(cert))
    tt = doc["trustTransition"]
    tt["finalAnchorBundle"] = [new["caCertificateSHA256"]]
    tt["stagedAnchorBundle"] = (sorted([doc["priorAuthority"]["caCertificateSHA256"], new["caCertificateSHA256"]])
                                if tt["cutover"] == "DUAL_ANCHOR_OVERLAP" else [new["caCertificateSHA256"]])
    return seal(doc)


def manifest_ops(doc: dict) -> list[dict]:
    return checker.expected_manifest(doc)["operations"]


def initial_readback(doc: dict, resume_at: str) -> dict:
    """Fresh Root readback of the pre-replacement state, with ceremony output in custody."""
    at = _ts(resume_at)
    observed = _iso(at - timedelta(seconds=30))
    prior_d = checker.anchor_digest([doc["priorAuthority"]["caCertificateSHA256"]])
    pin = doc["operationManifest"]
    rows = [{"nodeID": m["nodeID"], "rowPresent": True, "reservationDigest": None,
             "channelVersion": m["counters"]["channelVersionBefore"],
             "channelCertificateSHA256": checker.prior_leaf_sha(m), "channelAuditOpIDs": [],
             "policyFloor": m["counters"]["policyFloorBefore"], "installedPolicyDigest": m["priorPolicyDigest"],
             "policyJournalOpIDs": [], "installedLeafSHA256": checker.prior_leaf_sha(m),
             "stagedAnchorDigest": prior_d, "nodeObservedAt": observed, "nodeReceivedAt": observed,
             "nodeChallengeNonce": NONCE}
            for m in doc["members"] if m["kind"] == "ROTATION"]
    cp = doc["controlPlaneClient"]
    processes = [{"site": p["site"], "processID": p["processID"], "instanceID": f"{p['processID']}-i1",
                  "trustGeneration": 1, "loadedAnchorDigest": prior_d, "clientLeafSHA256": checker.prior_leaf_sha(cp),
                  "observedAt": observed, "receivedAt": observed, "challengeNonce": NONCE}
                 for p in cp["processInventory"]]
    live = {"source": "CP_PROCESS_REGISTRY", "observedAt": observed, "receivedAt": observed, "challengeNonce": NONCE,
            "processes": [dict(p, instanceID=f"{p['processID']}-i1") for p in cp["processInventory"]]}
    signed = [{"subject": m["nodeID"], "leafSHA256": m["plannedLeafSHA256"]} for m in doc["members"]
              if m["plannedLeafSHA256"] is not None]
    if cp["plannedLeafSHA256"] is not None:
        signed.append({"subject": "control-plane", "leafSHA256": cp["plannedLeafSHA256"]})
    return {"dbAvailable": True, "epoch": doc["preservedEpoch"]["epoch"],
            "custodyState": "NEW_KEY_PRESENT_MATCHES_PLAN",
            "writerFence": live_fence(doc, resume_at),
            "journalManifestDigest": None if pin is None else pin["digest"],
            "ceremonyLog": {"caKeysCreated": 1, "signed": signed}, "members": rows, "reservations": [],
            "serving": {"challengeNonce": NONCE, "challengeIssuedAt": _iso(at - timedelta(seconds=60)),
                        "liveInventory": live, "processes": processes, "handshakes": []}}


Selector = Callable[[dict], bool]


def at_state(doc: dict, last: str | None, flight: str | None = None, *, landed: Selector = lambda op: False,
             resume_at: str = RESUME) -> dict:
    """Journal at ``last`` (+ ``flight`` in flight, outcome UNKNOWN); readback = every durable effect
    plus the in-flight effects selected by ``landed``."""
    doc["checkpoint"] = checkpoint(last, flight, "UNKNOWN" if flight else None, resume_at,
                                   initial_readback(doc, resume_at))
    li = checker._idx(last)
    for op in manifest_ops(doc):
        if checker.INDEX[op["phase"]] <= li or (op["phase"] == flight and landed(op)):
            checker.apply_op(doc, op)
    return doc


def expect(doc: dict, action: str, phase: str | None = None, *, landed: Selector = lambda op: False) -> dict:
    """Record the expected decision. apply/ack come from what the generator itself landed."""
    cp = doc["checkpoint"]
    cp["expectedRecoveryAction"], cp["expectedResumePhase"] = action, phase
    ops = [op for op in manifest_ops(doc) if op["phase"] == phase] if action == "RESUME_FORWARD" and phase else []
    cp["expectedApply"] = [op["opID"] for op in ops if not landed(op)]
    cp["expectedAcknowledge"] = [op["opID"] for op in ops if landed(op)]
    return doc


def on(pc_ids: set[str], kind: str | None = None) -> Selector:
    return lambda op: op["target"] in pc_ids and (kind is None or op["kind"] == kind)


def member(doc: dict, pc: str) -> dict:
    return next(m for m in doc["members"] if m["pc"] == pc)


def row(doc: dict, pc: str) -> dict:
    node = member(doc, pc)["nodeID"]
    return next(r for r in doc["checkpoint"]["readback"]["members"] if r["nodeID"] == node)


def op_of(doc: dict, phase: str, pc_or_target: str) -> dict:
    target = next((m["nodeID"] for m in doc["members"] if m["pc"] == pc_or_target), pc_or_target)
    return next(op for op in manifest_ops(doc) if op["phase"] == phase and op["target"] == target)


def a1_durable(doc: dict) -> dict:
    """Journal A1 durable over a fresh readback; the recorded decision is RESUME at A2."""
    return expect(at_state(doc, "A1_NEW_TRUST_AUTHORIZED"), "RESUME_FORWARD", "A2_ANCHOR_STAGED")


def ceremony_done(name: str, **kw) -> dict:
    """A1 durable: the standard base for evidence fixtures; next is A2."""
    return a1_durable(ceremony(proposal(name, **kw)))


A = {p[:2]: p for p in checker.PHASES}  # "A4" -> "A4_CHANNEL_CAS"


NODE = {pc: nid("0" + pc) for pc in ("PC1", "PC2", "PC3", "PC4")}


def ids(*pcs: str) -> set[str]:
    return {NODE[pc] for pc in pcs}


# ---------------------------------------------------------------- positive fixtures


def positives() -> dict[str, tuple[str, dict]]:
    out: dict[str, tuple[str, dict]] = {}

    def add(name, why, doc):
        out[name] = (why, doc)

    def resume(name, why, last, flight, landed, phase, **kw):
        d = at_state(ceremony_done(name, **kw), last, flight, landed=landed)
        add(name, why, expect(d, "RESUME_FORWARD", phase, landed=landed))

    def hold(name, why, last, action, flight=None, landed=lambda op: False, mutate=None, resume_at=RESUME, **kw):
        d = at_state(ceremony_done(name, **kw), last, flight, landed=landed, resume_at=resume_at)
        if mutate:
            mutate(d)
        add(name, why, expect(d, action))

    no = lambda op: False  # noqa: E731
    every = lambda op: True  # noqa: E731

    add("p01-proposed-not-started", "Complete PROPOSED plan before A1: 3 rotations + PC1 enrollment, nothing started.",
        proposal("p01-proposed-not-started"))
    resume("p02-a1-durable-resume-anchor-stage", "A1 ceremony durable (root, leaves, manifest); next is A2 on all members.",
           A["A1"], None, no, A["A2"])

    d = proposal("p03-a1-unknown-no-key-abandon")
    rb = empty_readback(custody="NO_NEW_KEY")
    rb["writerFence"] = live_fence(d, RESUME)
    d["checkpoint"] = checkpoint(A["A0"], A["A1"], "UNKNOWN", RESUME, rb)
    add("p03-a1-unknown-no-key-abandon", "Ceremony interrupted; custody proves no new key exists: abandon is safe.",
        expect(d, "ABANDON_BEFORE_NEW_TRUST"))

    resume("p04-a4-partial-cas-ack-and-apply",
           "F4: PC2's CAS committed (exact postimage + one audit row), PC3/PC4 at exact preimage: ack PC2, apply the rest.",
           A["A3"], A["A4"], on(ids("PC2")), A["A4"])
    d = at_state(ceremony_done("p05-complete"), A["E5"])
    add("p05-complete", "Every phase durable with fresh serving evidence for every process and member.",
        expect(d, "COMPLETE"))

    def db_down(doc):
        doc["checkpoint"]["readback"] = empty_readback(db=False, epoch=None, custody="NEW_KEY_PRESENT_MATCHES_PLAN")
    hold("p06-db-unavailable-hold", "Interrupted after A5 while the DB cannot be read: HOLD, no blind replay.",
         A["A5"], "HOLD_DB_READBACK_REQUIRED", mutate=db_down)
    hold("p07-custody-mismatch-hold", "New CA key in custody differs from the plan after A2: HOLD.", A["A2"],
         "HOLD_CUSTODY_UNRESOLVED", mutate=lambda d: d["checkpoint"]["readback"].update(
             custodyState="NEW_KEY_PRESENT_MISMATCH"))
    d = at_state(ceremony_done("p08-rotation-only-complete", enroll=False), A["A7"])
    add("p08-rotation-only-complete", "Rotation cohort completes without any enrollment: the tracks are separable.",
        expect(d, "COMPLETE"))

    def undo_pc3_cas(doc):
        r = row(doc, "PC3")
        r.update(channelVersion=CHANNEL["PC3"], channelCertificateSHA256=checker.prior_leaf_sha(member(doc, "PC3")),
                 channelAuditOpIDs=[])
    hold("p09-durable-cas-undone-hold", "Journal says A4 durable but PC3 is back at its exact preimage: HOLD.",
         A["A4"], "HOLD_FOREIGN_WRITER", mutate=undo_pc3_cas)

    def pc1_row_early(doc):
        op = op_of(doc, A["E2"], "PC1")
        checker.apply_op(doc, op)
    hold("p10-enrollment-before-rotation-hold", "A PC1 row exists while rotation is only at A5: HOLD.", A["A5"],
         "HOLD_ENROLLMENT_BEFORE_ROTATION_SETTLED", mutate=pc1_row_early)
    hold("p11-epoch-diverged-hold", "DB control epoch differs from the preserved epoch: HOLD, never adopt it.",
         A["A3"], "HOLD_EPOCH_DIVERGED", mutate=lambda d: d["checkpoint"]["readback"].update(epoch=OTHER_EPOCH))
    hold("p12-floor-above-plan-hold", "PC2's floor is above the planned P: a foreign policy publication, HOLD.",
         A["A5"], "HOLD_POLICY_ABOVE_PLAN", flight=A["A6"],
         mutate=lambda d: row(d, "PC2").update(policyFloor=FLOOR["PC2"] + 2))

    def unplanned(doc):
        extra = copy.deepcopy(row(doc, "PC2"))
        extra.update(nodeID=nid("XTRA"), channelAuditOpIDs=[], policyJournalOpIDs=[])
        doc["checkpoint"]["readback"]["members"].append(extra)
    hold("p13-unplanned-row-hold", "A Node row that is neither planned nor pre-existing appeared: HOLD.", A["A7"],
         "HOLD_UNPLANNED_ROW", flight=A["E1"], mutate=unplanned)
    resume("p14-pc1-first-enrollment-ready",
           "Rotation settled with fresh evidence; no PC1 reservation or row yet; next is the fenced E1 reservation.",
           A["A7"], None, no, A["E1"])

    # F1: first admission crosses the row/channel boundary with a distinct, journaled decision.
    resume("p15-e2-row-landed-acknowledge",
           "F1: crash after the reserved PC1 row was created, before channel provisioning: acknowledge ROW_ADMIT.",
           A["E1"], A["E2"], every, A["E2"])
    resume("p16-e3-channel-missing-apply",
           "F1: E2 durable (row with matching reservation, C=0), E3 in flight, nothing landed: apply CHANNEL_PROVISION.",
           A["E2"], A["E3"], no, A["E3"])

    def foreign_row(doc):
        doc["checkpoint"]["readback"]["members"].append({
            "nodeID": member(doc, "PC1")["nodeID"], "rowPresent": True, "reservationDigest": h("foreign-reservation"),
            "channelVersion": 0, "channelCertificateSHA256": None, "channelAuditOpIDs": [], "policyFloor": 0,
            "installedPolicyDigest": None, "policyJournalOpIDs": [], "installedLeafSHA256": None,
            "stagedAnchorDigest": None, "nodeObservedAt": None, "nodeReceivedAt": None, "nodeChallengeNonce": None})
    hold("p17-foreign-row-reservation-hold",
         "F1: a PC1 row exists but was created under another reservation: HOLD, never adopt it.", A["E1"],
         "HOLD_RESERVATION_MISMATCH", flight=A["E2"], mutate=foreign_row)

    # F4: exact preimage/postimage; a matching counter alone is never enough.
    hold("p18-cas-old-fingerprint-differs-hold",
         "F4: PC3 is at the expected old version but carries a different fingerprint: HOLD, no CAS.", A["A3"],
         "HOLD_FOREIGN_WRITER", flight=A["A4"],
         mutate=lambda d: row(d, "PC3").update(channelCertificateSHA256=h("PC3-foreign-leaf")))
    hold("p19-policy-floor-matches-digest-differs-hold",
         "F4: PC4's floor equals the planned P but different policy bytes landed: HOLD.", A["A4"],
         "HOLD_FOREIGN_WRITER", flight=A["A5"],
         mutate=lambda d: row(d, "PC4").update(policyFloor=FLOOR["PC4"] + 1, installedPolicyDigest=h("foreign-policy"),
                                               policyJournalOpIDs=[op_of(d, A["A5"], "PC4")["opID"]]))
    hold("p20-cas-postimage-without-audit-hold",
         "F4: PC2 shows the planned version and leaf but no audit row for the operation: HOLD.", A["A3"],
         "HOLD_FOREIGN_WRITER", flight=A["A4"], landed=on(ids("PC2")),
         mutate=lambda d: row(d, "PC2").update(channelAuditOpIDs=[]))
    hold("p21-writer-fence-lost-hold", "F4: another plan holds the writer fence: HOLD, never write.", A["A4"],
         "HOLD_WRITER_FENCE", flight=A["A5"],
         mutate=lambda d: d["checkpoint"]["readback"]["writerFence"].update(holderPlanDigest=h("other-plan")))
    hold("p22-journal-manifest-mismatch-hold", "F4: the durable journal pins a different manifest: HOLD.", A["A3"],
         "HOLD_MANIFEST_MISMATCH", mutate=lambda d: d["checkpoint"]["readback"].update(
             journalManifestDigest=h("other-manifest")))

    d = ceremony_done("p23-a1-in-flight-key-present-resume")
    d["checkpoint"] = checkpoint(A["A0"], A["A1"], "UNKNOWN", RESUME, initial_readback(d, RESUME))
    log = d["checkpoint"]["readback"]["ceremonyLog"]
    log["signed"] = log["signed"][:2]
    add("p23-a1-in-flight-key-present-resume",
        "F4: ceremony interrupted with the planned key present and two leaves signed: resume A1 (deterministic re-signing).",
        expect(d, "RESUME_FORWARD", A["A1"]))
    hold("p24-second-ca-key-hold", "F4: custody shows a second CA key was generated: HOLD.", A["A2"],
         "HOLD_CUSTODY_UNRESOLVED", mutate=lambda d: d["checkpoint"]["readback"]["ceremonyLog"].update(caKeysCreated=2))
    hold("p25-extra-leaf-signed-hold", "F4: a second, different leaf was issued for PC2: HOLD.", A["A3"],
         "HOLD_FOREIGN_WRITER", mutate=lambda d: d["checkpoint"]["readback"]["ceremonyLog"]["signed"].append(
             {"subject": member(d, "PC2")["nodeID"], "leafSHA256": h("PC2-second-leaf")}))

    # F3: serving evidence, duplicates, staging gate.
    def duplicate_row(doc):
        doc["checkpoint"]["readback"]["members"].append(copy.deepcopy(row(doc, "PC3")))
    hold("p26-duplicate-readback-row-hold", "F3: two readback rows for PC3 (never collapsed): HOLD.", A["A4"],
         "HOLD_DUPLICATE_EVIDENCE", flight=A["A5"], mutate=duplicate_row)
    hold("p27-a3-without-verified-staging-hold",
         "F3: A2 durable but PC4's anchor readback answers an old challenge: A3 stays blocked.", A["A2"],
         "HOLD_ANCHOR_STAGING_UNVERIFIED", mutate=lambda d: row(d, "PC4").update(nodeChallengeNonce="fixture-old-0000"))

    def drop_process(doc):
        procs = doc["checkpoint"]["readback"]["serving"]["processes"]
        procs[:] = [p for p in procs if p["processID"] != "storage-check-cli"]
    hold("p28-settled-journal-missing-process-evidence-hold",
         "F3: journal says A7 durable but the separately invoked storage-check client has no trust readback: HOLD.",
         A["A7"], "HOLD_SERVING_EVIDENCE_INCOMPLETE", mutate=drop_process, enroll=False)

    def stale_handshake(doc):
        shake = next(s for s in doc["checkpoint"]["readback"]["serving"]["handshakes"]
                     if s["nodeID"] == member(doc, "PC2")["nodeID"])
        shake["observedAt"] = shake["receivedAt"] = _iso(_ts(RESUME) - timedelta(seconds=FRESHNESS + 1))
    hold("p29-stale-handshake-hold", "F3: PC2's handshake is older than the freshness window: COMPLETE is refused.",
         A["A7"], "HOLD_SERVING_EVIDENCE_INCOMPLETE", mutate=stale_handshake, enroll=False)
    resume("p30-a6-rolling-switch-resume",
           "F3: A6 in flight; observer-1 and delivery-1 reloaded the new trust, the rest still on the prior: apply the rest.",
           A["A5"], A["A6"], lambda op: op["target"] in ("observer-1", "delivery-1"), A["A6"])
    resume("p31-a7-awaiting-fresh-handshakes-resume",
           "F3: A7 in flight; only PC2 has a fresh handshake under the new pins: observe PC3 and PC4 again.",
           A["A6"], A["A7"], on(ids("PC2")), A["A7"])

    # F5: deadlines at resume time, and the separate advance-renewal transition.
    hold("p32-paused-policy-expiry-hold",
         "F5: paused one day before A4; the planned policy cannot cover the outstanding work: HOLD, re-plan.",
         A["A3"], "HOLD_DEADLINE_INSUFFICIENT", flight=A["A4"], resume_at="2026-11-19T14:00:00Z")

    d = proposal("p33-successor-not-yet-valid-hold")
    d["newAuthority"].update(notBefore="2026-11-18T15:00:00Z", notAfter="2027-11-18T15:00:00Z",
                             leafValidity={"notBefore": "2026-11-18T15:00:00Z", "notAfter": "2026-11-24T15:00:00Z"})
    d = at_state(ceremony(seal(d)), A["A2"])
    d["checkpoint"]["resumeAt"] = RESUME
    add("p33-successor-not-yet-valid-hold", "F5: at resume time the new CA and its leaves are not yet valid: HOLD.",
        expect(d, "HOLD_DEADLINE_INSUFFICIENT"))

    add("p34-advance-dual-not-started",
        "F5: ADVANCE_RENEWAL while the current CA is valid: bounded dual-anchor overlap, nothing started.",
        proposal("p34-advance-dual-not-started", mode="ADVANCE_RENEWAL", enroll=False))
    adv = {"mode": "ADVANCE_RENEWAL", "enroll": False}
    resume("p35-advance-dual-a4-resume", "F5: advance renewal inside the overlap, PC2's CAS committed: resume A4.",
           A["A3"], A["A4"], on(ids("PC2")), A["A4"], **adv)
    d = at_state(ceremony_done("p36-advance-dual-complete-retired", **adv), A["A7"])
    add("p36-advance-dual-complete-retired",
        "F5: every member and process retired the prior anchor (final bundle only) with fresh handshakes: COMPLETE.",
        expect(d, "COMPLETE"))
    hold("p37-advance-overlap-elapsed-hold",
         "F5: resuming A5 would finish after the overlap's mustEndBy: HOLD, never extend the overlap.", A["A4"],
         "HOLD_DEADLINE_INSUFFICIENT", resume_at="2026-11-19T05:40:00Z", **adv)
    add("p38-advance-quiesced-not-started",
        "F5: ADVANCE_RENEWAL by explicitly quiesced cutover (singleton successor anchor), nothing started.",
        proposal("p38-advance-quiesced-not-started", mode="ADVANCE_RENEWAL", enroll=False, cutover="QUIESCED"))
    resume("p39-advance-a7-partial-retire-resume",
           "F5: A7 in flight; PC2 and observer-1 retired the prior anchor: retire the rest, then observe.",
           A["A6"], A["A7"], lambda op: op["target"] in ids("PC2") | {"observer-1"} and op["kind"] != "SETTLE",
           A["A7"], **adv)

    # Review R2 finding 4: the writer fence and the ceremony log gate every A1-in-flight decision.
    d = ceremony_done("p40-a1-interrupted-fence-transferred-hold")
    rb = initial_readback(d, RESUME)
    rb["ceremonyLog"]["signed"] = rb["ceremonyLog"]["signed"][:2]
    rb["writerFence"].update(token="fence:fixture-other-writer", holderPlanDigest=h("other-plan"))
    d["checkpoint"] = checkpoint(A["A0"], A["A1"], "UNKNOWN", RESUME, rb)
    add("p40-a1-interrupted-fence-transferred-hold",
        "Ceremony interrupted with the planned key present, but another writer now holds the fence: HOLD, never re-sign.",
        expect(d, "HOLD_WRITER_FENCE"))
    d = proposal("p41-a1-interrupted-log-absent-hold")
    rb = initial_readback(d, RESUME)
    rb["ceremonyLog"] = None
    d["checkpoint"] = checkpoint(A["A0"], A["A1"], "UNKNOWN", RESUME, rb)
    add("p41-a1-interrupted-log-absent-hold",
        "Ceremony interrupted: custody reports a key, the plan records none and there is no ceremony log: HOLD.",
        expect(d, "HOLD_CUSTODY_UNRESOLVED"))
    d = proposal("p42-a1-interrupted-no-key-stale-fence-hold")
    rb = empty_readback(custody="NO_NEW_KEY")
    rb["writerFence"] = live_fence(d, RESUME, generation=FENCE_GENERATION + 1)
    d["checkpoint"] = checkpoint(A["A0"], A["A1"], "UNKNOWN", RESUME, rb)
    add("p42-a1-interrupted-no-key-stale-fence-hold",
        "Ceremony interrupted with no key, but the fence was re-acquired at a later generation: HOLD, not abandon.",
        expect(d, "HOLD_WRITER_FENCE"))

    # Review R2 finding 3: the authoritative live inventory, one-use challenges and their issuance age.
    def extra_replica(doc):
        serving = doc["checkpoint"]["readback"]["serving"]
        serving["liveInventory"]["processes"].append(
            {"site": "delivery_worker", "processID": "delivery-3", "kind": "SERVICE", "instanceID": "delivery-3-i1"})
        serving["processes"].append(dict(copy.deepcopy(serving["processes"][1]), processID="delivery-3",
                                         instanceID="delivery-3-i1"))
    hold("p43-live-replica-outside-inventory-hold",
         "F3: a delivery replica absent from the frozen inventory is serving (R2 ignored it and completed): HOLD.",
         A["A7"], "HOLD_PROCESS_INVENTORY_CHANGED", mutate=extra_replica, enroll=False)
    hold("p44-consumed-challenge-hold",
         "F3: the readback answers a challenge an earlier decision already consumed: HOLD, re-challenge.", A["A3"],
         "HOLD_SERVING_EVIDENCE_INCOMPLETE", mutate=lambda d: d["checkpoint"]["consumedChallengeNonces"].append(NONCE))
    hold("p45-challenge-issued-too-long-ago-hold",
         "F3: every answer is recent but the challenge itself was issued beyond its lifetime: HOLD.", A["A3"],
         "HOLD_SERVING_EVIDENCE_INCOMPLETE", mutate=lambda d: d["checkpoint"]["readback"]["serving"].update(
             challengeIssuedAt=_iso(_ts(RESUME) - timedelta(seconds=CHALLENGE + 1))))
    return out


# ---------------------------------------------------------------- rejection fixtures


def rejections() -> dict[str, tuple[str, list[str], dict]]:
    out: dict[str, tuple[str, list[str], dict]] = {}

    def add(name, why, codes, doc):
        out[name] = (why, codes, doc)

    def prop(name, **kw):
        return proposal(name, **kw)

    d = prop("r01-new-ca-is-prior"); d["newAuthority"]["caCertificateSHA256"] = d["priorAuthority"]["caCertificateSHA256"]
    add("r01-new-ca-is-prior", "New CA certificate is the prior CA.", ["AR-PRIOR-REUSE"], d)
    d = prop("r02-new-ca-key-is-prior"); d["newAuthority"]["caPublicKeySHA256"] = d["priorAuthority"]["caPublicKeySHA256"]
    add("r02-new-ca-key-is-prior", "New CA re-uses the prior CA key (same-CA renewal in disguise).",
        ["AR-PRIOR-REUSE", "AR-ROLE-SEPARATION"], d)
    d = prop("r03-new-ca-subject-reused"); d["newAuthority"]["subjectCommonName"] = "saintvision lan pilot ca "
    add("r03-new-ca-subject-reused", "New CA subject equals the prior CA subject.", ["AR-PRIOR-REUSE"], seal(d))
    d = ceremony_done("r04-terminal-in-anchor-bundle")
    d["trustTransition"]["finalAnchorBundle"].append(d["priorAuthority"]["caCertificateSHA256"])
    add("r04-terminal-in-anchor-bundle", "Expired CA kept as a trust anchor.", ["AR-TERMINAL-ANCHOR"], seal(d))
    d = prop("r05-cross-signed-by-prior"); d["newAuthority"]["crossSignedByPrior"] = True
    add("r05-cross-signed-by-prior", "New CA chained to the prior CA.", ["AR-SCHEMA"], d)
    d = prop("r06-epoch-replaced"); m = member(d, "PC3"); m["spiffeURI"] = node_uri(TENANT, m["nodeID"], OTHER_EPOCH)
    add("r06-epoch-replaced", "A rotation identity would carry a new epoch; its prior leaf cannot authenticate it.",
        ["AR-EPOCH-SPIFFE", "AR-PRIOR-BINDING"], seal(d))
    d = prop("r07-channel-counter-reset"); member(d, "PC4")["counters"]["channelVersionAfter"] = 1
    add("r07-channel-counter-reset", "Channel version reset instead of C+1.", ["AR-CHANNEL-NONMONOTONE"], seal(d))
    d = prop("r08-policy-not-above-floor"); c = member(d, "PC2")["counters"]; c["policyVersionAfter"] = c["policyFloorBefore"]
    add("r08-policy-not-above-floor", "New policy version equals the authenticated floor.",
        ["AR-POLICY-NONMONOTONE"], seal(d))
    d = prop("r09-pc1-copies-pc4-identity")
    set_member_identity(d, member(d, "PC1"), node_id=member(d, "PC4")["nodeID"], key_label="PC1-node-fresh")
    add("r09-pc1-copies-pc4-identity", "PC1 re-uses PC4's NodeID (copied share directory).",
        ["AR-ENROLLMENT-REUSES-IDENTITY", "AR-IDENTITY-COLLISION"], seal(d))
    d = prop("r10-pc1-reuses-retired-row")
    set_member_identity(d, member(d, "PC1"), node_id=nid("RTR1"), key_label="PC1-node-fresh")
    add("r10-pc1-reuses-retired-row", "PC1 revives a retired NodeID.", ["AR-ENROLLMENT-REUSES-IDENTITY"], seal(d))
    d = prop("r11-pc1-reuses-existing-key")
    set_member_identity(d, member(d, "PC1"), node_id=nid("0PC1"), key_label="RTR2-node")
    add("r11-pc1-reuses-existing-key", "PC1 enrolls with a key bound to a disabled row.",
        ["AR-ENROLLMENT-REUSES-IDENTITY"], seal(d))
    d = prop("r12-rotation-key-changed")
    set_member_identity(d, member(d, "PC3"), node_id=member(d, "PC3")["nodeID"], key_label="PC3-node-new")
    add("r12-rotation-key-changed", "Rotation CSR proves a different key than the authenticated prior leaf.",
        ["AR-ROTATION-KEY-CHANGED"], seal(d))
    d = prop("r13-rotation-of-unknown-identity")
    set_member_identity(d, member(d, "PC2"), node_id=nid("0PC5"), key_label="PC2-node")
    add("r13-rotation-of-unknown-identity", "ROTATION for an identity absent from the DB tuples.",
        ["AR-PRIOR-BINDING", "AR-ROTATION-UNKNOWN-IDENTITY"], seal(d))
    d = prop("r14-enrollment-counter-nonzero"); member(d, "PC1")["counters"]["channelVersionBefore"] = 2
    add("r14-enrollment-counter-nonzero", "New enrollment does not start from an empty channel.",
        ["AR-ENROLLMENT-COUNTER"], seal(d))
    d = prop("r15-proposed-with-unknown-budget"); d["advanceRenewal"]["normalBudgetSeconds"] = None
    add("r15-proposed-with-unknown-budget", "PROPOSED while a budget is unknown; must be HOLD.",
        ["AR-HOLD-REQUIRED"], seal(d))
    d = prop("r16-proposed-with-historical-epoch"); d["preservedEpoch"]["source"] = "HISTORICAL_EVIDENCE"
    add("r16-proposed-with-historical-epoch", "PROPOSED from a historical epoch, not a DB readback.",
        ["AR-HOLD-REQUIRED"], seal(d))
    d = prop("r17-successor-lead-too-short"); d["advanceRenewal"]["caSuccessorLeadSeconds"] = 518400
    add("r17-successor-lead-too-short", "Successor CA lead shorter than one leaf lifetime + budgets.",
        ["AR-RENEWAL-BUDGET"], d)
    d = prop("r18-seven-day-ca-repeats-failure"); d["advanceRenewal"]["caLifetimeSeconds"] = 604800
    d["newAuthority"]["notAfter"] = "2026-11-25T12:00:00Z"
    add("r18-seven-day-ca-repeats-failure", "Seven-day CA (the Nov 14 failure shape).", ["AR-RENEWAL-BUDGET"], seal(d))
    d = prop("r19-leaf-lead-below-budget"); d["advanceRenewal"]["leafRenewalLeadSeconds"] = 20000
    add("r19-leaf-lead-below-budget", "Leaf renewal lead below budget + overlap + 660 s.", ["AR-RENEWAL-BUDGET"], d)
    d = prop("r20-terminal-not-yet-expired"); d["observedAt"] = "2026-11-14T07:00:00Z"
    d["checkpoint"]["resumeAt"] = d["observedAt"]
    d["newAuthority"].update(notBefore="2026-11-14T07:00:00Z", notAfter="2027-11-14T07:00:00Z")
    add("r20-terminal-not-yet-expired", "Prior CA still valid: TERMINAL_REPLACEMENT is not the applicable branch.",
        ["AR-TERMINAL-NOT-EXPIRED"], seal(d))
    d = prop("r21-activation-released"); d["activation"] = "RELEASED"
    add("r21-activation-released", "A proposal document cannot carry an operating release.", ["AR-SCHEMA"], d)
    d = prop("r22-private-material-embedded")
    d["newAuthority"]["custody"]["custodyEvidenceRef"] = "-----BEGIN PRIVATE KEY----- MC4CAQ"
    add("r22-private-material-embedded", "Private key material embedded in the plan.", ["AR-SECRET-MATERIAL"], d)
    _, p09 = positives_cache()["p09-durable-cas-undone-hold"]
    d = copy.deepcopy(p09)
    d["checkpoint"].update(expectedRecoveryAction="RESUME_FORWARD", expectedResumePhase=A["A5"])
    add("r23-resume-over-undone-cas", "Declares RESUME where readback proves a foreign writer.",
        ["AR-RECOVERY-MISMATCH"], d)
    d = prop("r24-rollback-to-terminal"); d["checkpoint"]["expectedRecoveryAction"] = "ROLLBACK_TO_TERMINAL_CA"
    add("r24-rollback-to-terminal", "Rollback to the expired authority is not representable.", ["AR-SCHEMA"], d)
    d = ceremony_done("r25-shared-planned-leaf")
    member(d, "PC1")["plannedLeafSHA256"] = member(d, "PC2")["plannedLeafSHA256"]
    add("r25-shared-planned-leaf", "Two members pinned to one leaf certificate.",
        ["AR-CERT-LEAF", "AR-PLANNED-LEAF-REUSE"], seal(d))

    # F2: authenticated identity and authority.
    def leaf_variant(name, why, pc, **override):
        d = a1_durable(ceremony(proposal(name), leaf_overrides={pc: override}))
        add(name, why, ["AR-CERT-LEAF"], d)

    leaf_variant("r26-leaf-from-impostor-root", "F2: PC3's leaf is signed by an impostor CA with the same subject.",
                 "PC3", signer=("impostor-ca", NEW_CN))
    leaf_variant("r27-leaf-uri-other-node", "F2: PC3's leaf carries PC4's SPIFFE URI.", "PC3",
                 uri=node_uri(TENANT, nid("0PC4"), EPOCH))
    leaf_variant("r28-leaf-client-eku", "F2: a Node leaf with clientAuth instead of serverAuth.", "PC2",
                 eku=ExtendedKeyUsageOID.CLIENT_AUTH)
    leaf_variant("r29-leaf-ip-san-differs", "F2: PC4's leaf address SAN differs from its inventory address.", "PC4",
                 ips=["10.0.0.99"])
    leaf_variant("r30-leaf-validity-not-planned", "F2: PC2's leaf outlives the planned leaf validity.", "PC2",
                 notAfter="2026-11-30T12:00:00Z")
    d = ceremony_done("r31-csr-signature-tampered")
    raw = bytearray(checker.der_bytes(member(d, "PC3")["csrDER"])); raw[-1] ^= 0x01
    member(d, "PC3")["csrDER"] = b64(bytes(raw))
    add("r31-csr-signature-tampered", "F2: PC3's CSR signature does not verify: no proof of possession.",
        ["AR-CSR-POP"], seal(d))
    d = prop("r32-csr-subject-not-node")
    m = member(d, "PC2"); m["csrDER"] = make_csr("PC2-node", "SaintVision LAN peer")
    add("r32-csr-subject-not-node", "F2: PC2's CSR subject is not its NodeID.", ["AR-CSR-POP"], seal(d))
    d = prop("r33-prior-leaf-forged")
    m = member(d, "PC4")
    fake_key, fake_ca = make_ca("impostor-prior-ca", TERMINAL["cn"], TERMINAL["notBefore"], TERMINAL["notAfter"])
    m["priorLeafDER"] = b64(der(make_leaf(fake_key, fake_ca, key("PC4-node").public_key(), m["spiffeURI"], m["address"],
                                          not_before=TERMINAL["leafNotBefore"], not_after=TERMINAL["notAfter"],
                                          label="forged-prior")))
    next(r for r in d["existingNodeRows"]["rows"] if r["nodeID"] == m["nodeID"])["channelCertificateSHA256"] = \
        checker.prior_leaf_sha(m)
    add("r33-prior-leaf-forged", "F2: PC4's prior tuple is consistent but its leaf was not signed by the prior CA.",
        ["AR-PRIOR-BINDING"], seal(d))
    d = prop("r34-prior-leaf-not-row-tuple")
    next(r for r in d["existingNodeRows"]["rows"] if r["nodeID"] == member(d, "PC2")["nodeID"])[
        "channelCertificateSHA256"] = h("PC2-other-pinned-leaf")
    add("r34-prior-leaf-not-row-tuple", "F2: PC2's prior leaf is not the leaf the DB row pins.",
        ["AR-PRIOR-BINDING"], d)
    d = prop("r35-role-key-equals-cp-key")
    d["roleKeys"][0]["publicKeySHA256"] = d["controlPlaneClient"]["publicKeySHA256"]
    add("r35-role-key-equals-cp-key", "F2: the launch signer is the CP client key.", ["AR-ROLE-SEPARATION"], d)
    d = ceremony_done("r36-role-key-equals-new-ca-key")
    d["roleKeys"][0]["publicKeySHA256"] = d["newAuthority"]["caPublicKeySHA256"]
    add("r36-role-key-equals-new-ca-key", "F2: the launch signer is the new CA key.", ["AR-ROLE-SEPARATION"], d)
    d = prop("r37-retained-signer-compromised")
    d["roleKeys"][0]["continuity"]["compromiseDecision"] = "COMPROMISED"
    add("r37-retained-signer-compromised", "F2: a signer Root found compromised cannot be retained.",
        ["AR-ROLE-CONTINUITY"], d)
    d = prop("r38-retained-cp-key-changed")
    cp = d["controlPlaneClient"]; cp["publicKeySHA256"] = spki("cp-client-new")
    cp["csrDER"] = make_csr("cp-client-new", checker.CP_CSR_COMMON_NAME)
    add("r38-retained-cp-key-changed", "F2: CP key declared RETAINED but the CSR proves a different key.",
        ["AR-ROTATION-KEY-CHANGED"], seal(d))
    d = a1_durable(ceremony(proposal("r39-root-not-a-ca"), root_ca=False))
    add("r39-root-not-a-ca", "F2: the new root is not a CA certificate (BasicConstraints CA=false).",
        ["AR-CERT-ROOT"], d)
    d = prop("r40-retained-signer-wrong-scope"); d["roleKeys"][0]["continuity"]["scope"] = "POLICY_SIGNATURES"
    add("r40-retained-signer-wrong-scope", "F2: retained launch signer continuity verified for another scope.",
        ["AR-ROLE-CONTINUITY"], d)

    # F1: reservation binding.
    d = prop("r41-reservation-plan-digest-stale"); member(d, "PC1")["reservation"]["planDigest"] = h("stale-plan")
    add("r41-reservation-plan-digest-stale", "F1: PC1's reservation binds an older plan.",
        ["AR-ENROLLMENT-RESERVATION"], d)
    d = prop("r42-reservation-node-state-not-empty")
    member(d, "PC1")["reservation"]["nodeStateEmpty"]["verified"] = False
    add("r42-reservation-node-state-not-empty", "F1: PC1 has Node-owned state left over: not a first admission.",
        ["AR-ENROLLMENT-RESERVATION"], d)
    d = prop("r43-rows-readback-excludes-retired"); d["existingNodeRows"]["includesRetired"] = False
    add("r43-rows-readback-excludes-retired", "F1: historical uniqueness was not checked against retired rows.",
        ["AR-HOLD-REQUIRED"], d)
    d = prop("r44-reservation-csr-mismatch"); member(d, "PC1")["reservation"]["csrSHA256"] = h("other-csr")
    add("r44-reservation-csr-mismatch", "F1: the reservation binds a different CSR than PC1's proof of possession.",
        ["AR-ENROLLMENT-RESERVATION"], d)

    # F3
    d = prop("r45-process-inventory-missing-site")
    inv = d["controlPlaneClient"]["processInventory"]
    inv[:] = [p for p in inv if p["site"] != "storage_check_collector"]
    add("r45-process-inventory-missing-site", "F3: the separately invoked storage-check client is not inventoried.",
        ["AR-PROCESS-INVENTORY"], seal(d))
    _, p29 = positives_cache()["p29-stale-handshake-hold"]
    d = copy.deepcopy(p29); d["checkpoint"]["expectedRecoveryAction"] = "COMPLETE"
    add("r46-complete-declared-over-stale-evidence", "F3: declares COMPLETE from the journal over stale evidence.",
        ["AR-RECOVERY-MISMATCH"], d)
    d = prop("r47-serving-binary-not-reviewed"); d["servingBinaryMigration"]["status"] = "NOT_REVIEWED"
    add("r47-serving-binary-not-reviewed", "F3: serving under the new trust without the reviewed binary migration.",
        ["AR-HOLD-REQUIRED"], d)

    # F4
    d = ceremony_done("r48-manifest-digest-altered"); d["operationManifest"]["digest"] = h("edited-manifest")
    add("r48-manifest-digest-altered", "F4: the pinned manifest is not the plan's frozen manifest.", ["AR-MANIFEST"], d)
    d = at_state(ceremony_done("r49-ceremony-missing-after-a1"), A["A1"])
    member(d, "PC3").update(leafDER=None, plannedLeafSHA256=None)
    d["operationManifest"] = None
    add("r49-ceremony-missing-after-a1", "F4: A1 durable without PC3's leaf or a frozen manifest.",
        ["AR-CEREMONY-INCOMPLETE"], d)
    _, p04 = positives_cache()["p04-a4-partial-cas-ack-and-apply"]
    d = copy.deepcopy(p04); cp = d["checkpoint"]
    cp["expectedApply"] = sorted(cp["expectedApply"] + cp["expectedAcknowledge"])
    cp["expectedAcknowledge"] = []
    add("r50-apply-declared-for-committed-op", "F4: plans to re-apply PC2's committed CAS (would hit NODE-0034).",
        ["AR-RECOVERY-MISMATCH"], d)
    d = ceremony_done("r51-ceremony-before-a1"); d["checkpoint"] = checkpoint()
    add("r51-ceremony-before-a1", "F4: ceremony outputs exist while the journal says nothing started.",
        ["AR-CHECKPOINT-ORDER"], d)

    # F5
    d = ceremony_done("r52-terminal-mode-with-dual-bundle")
    d["trustTransition"]["stagedAnchorBundle"] = sorted([d["priorAuthority"]["caCertificateSHA256"],
                                                         d["newAuthority"]["caCertificateSHA256"]])
    add("r52-terminal-mode-with-dual-bundle", "F5: a terminal replacement may not stage the expired CA.",
        ["AR-TERMINAL-ANCHOR"], seal(d))
    d = prop("r53-advance-mode-prior-expired", mode="ADVANCE_RENEWAL", enroll=False,
             prior_not_after="2026-11-17T00:00:00Z")
    add("r53-advance-mode-prior-expired", "F5: ADVANCE_RENEWAL over an expired CA is a terminal replacement.",
        ["AR-ADVANCE-WINDOW"], d)
    d = prop("r54-advance-overlap-exceeds-lead", mode="ADVANCE_RENEWAL", enroll=False)
    d["trustTransition"]["overlap"]["mustEndBy"] = "2026-12-19T12:00:01Z"
    add("r54-advance-overlap-exceeds-lead", "F5: dual-anchor overlap longer than the successor lead.",
        ["AR-ADVANCE-WINDOW"], seal(d))
    d = prop("r55-advance-started-too-late", mode="ADVANCE_RENEWAL", enroll=False,
             prior_not_after="2026-12-10T00:00:00Z")
    add("r55-advance-started-too-late", "F5: advance renewal started with less than the successor lead left.",
        ["AR-ADVANCE-WINDOW"], d)
    _, p32 = positives_cache()["p32-paused-policy-expiry-hold"]
    d = copy.deepcopy(p32); cp = d["checkpoint"]
    cp.update(expectedRecoveryAction="RESUME_FORWARD", expectedResumePhase=A["A4"],
              expectedApply=[op["opID"] for op in manifest_ops(d) if op["phase"] == A["A4"]])
    add("r56-resume-declared-over-expiry", "F5: declares RESUME after a pause the planned validity cannot cover.",
        ["AR-RECOVERY-MISMATCH"], d)
    d = prop("r57-quiesced-without-evidence", mode="ADVANCE_RENEWAL", enroll=False, cutover="QUIESCED")
    d["trustTransition"]["quiesceEvidenceRef"] = None
    add("r57-quiesced-without-evidence", "F5: quiesced cutover without quiesce evidence: must be HOLD.",
        ["AR-HOLD-REQUIRED"], seal(d))
    d = prop("r58-terminal-mode-with-overlap")
    d["trustTransition"]["overlap"] = {"startsAt": OBSERVED, "mustEndBy": "2026-11-19T06:00:00Z"}
    add("r58-terminal-mode-with-overlap", "F5: a terminal replacement has no overlap window.", ["AR-MODE"], seal(d))
    d = prop("r59-serving-window-above-cap"); d["measuredBudgets"]["observationFreshnessSeconds"] = 600
    add("r59-serving-window-above-cap", "F3: a measured freshness window wider than the 120 s contract cap.",
        ["AR-SERVING-WINDOW"], d)
    return out


_POSITIVES: dict | None = None


def positives_cache() -> dict[str, tuple[str, dict]]:
    global _POSITIVES
    if _POSITIVES is None:
        _POSITIVES = positives()
    return _POSITIVES


# ---------------------------------------------------------------- real instance, handoff, rendering


HANDOFF_SOURCE = "fixtures/positive/p05-complete.json"
HANDOFF_PATH = "handoff/pc1-first-enrollment-handoff.json"
HANDOFF_HOSTS = {"PC1": "host-pc1", "PC2": "host-pc2", "PC3": "host-pc3", "PC4": "host-pc4"}
HANDOFF_CP_HOST = "host-pc3"  # mirrors the real fleet: API/portal/observer run on PC3
MANIFEST_SAMPLE_SOURCE = "fixtures/positive/p02-a1-durable-resume-anchor-stage.json"
MANIFEST_SAMPLE_PATH = "manifests/p02-operation-manifest.json"


def current_instance() -> dict:
    """Real Nov18 fleet plan (Root544 evidence). Every unknown stays null -> HOLD."""
    tenant = "97968b42-68aa-40ce-af5e-3a33e2fc2205"
    epoch = "bcd581be-31b4-4aca-86e6-3ca31b69ed09"
    nodes = {
        "PC2": ("nod_01M6TGQZ8S3DAFS7TYE8TY1PX2", "saintvision-invion", "192.168.45.143"),
        "PC3": ("nod_01M6TAWG25JTA3F7J7S1EE4N2W", "saintvision-invion3", "192.168.45.222"),
        "PC4": ("nod_01M6TGSXV1J7XWC5D5H7N6EW1D", "inviz", "192.168.45.210"),
    }
    nulls = {"channelVersionBefore": None, "channelVersionAfter": None, "policyFloorBefore": None,
             "policyVersionAfter": None}

    def rot(pc):
        node, account, address = nodes[pc]
        return {"pc": pc, "kind": "ROTATION", "nodeID": node, "account": account, "address": address,
                "endpoint": None, "spiffeURI": node_uri(tenant, node, epoch), "nodePublicKeySHA256": None,
                "csrDER": None, "priorLeafDER": None, "priorPolicyDigest": None, "leafDER": None,
                "plannedLeafSHA256": None, "plannedPolicy": None, "counters": dict(nulls), "reservation": None}

    pc1 = {"pc": "PC1", "kind": "NEW_ENROLLMENT", "nodeID": None, "account": "inviz", "address": "192.168.45.13",
           "endpoint": None, "spiffeURI": None, "nodePublicKeySHA256": None, "csrDER": None, "priorLeafDER": None,
           "priorPolicyDigest": None, "leafDER": None, "plannedLeafSHA256": None, "plannedPolicy": None,
           "counters": {"channelVersionBefore": 0, "channelVersionAfter": 1, "policyFloorBefore": 0,
                        "policyVersionAfter": 1},
           "reservation": {"tenantID": tenant, "epoch": epoch, "pc": "PC1", "nodeID": None, "csrSHA256": None,
                           "planDigest": None, "fenceToken": None, "rowsReadbackSHA256": None,
                           "nodeStateEmpty": {"verified": None, "evidenceRef": None}}}
    return {
        "schema": "fleet5-authority-replacement-plan:2",
        "revision": "R2",
        "planID": "ARP-20261119-fleet5-nov18-ca-terminal-r2",
        "status": "HOLD",
        "activation": "NOT_AUTHORIZED",
        "fixture": False,
        "mode": "TERMINAL_REPLACEMENT",
        "observedAt": "2026-11-18T11:53:13Z",
        "tenantID": tenant,
        "projectID": "prj_01M6NDBHVD2DZQ1Q38DCKN1XE3",
        "preservedEpoch": {"epoch": epoch, "source": "HISTORICAL_EVIDENCE", "readbackSHA256": None},
        "priorAuthority": {"certificateDER": None,
                           "caCertificateSHA256": "b8d777ab04c65a44f827fdda9629d54a086e9ff8cc752b90a09023a93341c5a3",
                           "caPublicKeySHA256": None, "subjectCommonName": None, "notAfter": "2026-11-14T07:15:30Z",
                           "state": "CA_TERMINAL", "usage": "REFERENCE_ONLY"},
        "newAuthority": {
            "certificateDER": None, "caCertificateSHA256": None, "caPublicKeySHA256": None,
            "subjectCommonName": NEW_CN, "keyAlgorithm": "Ed25519", "keyGeneratedFresh": True,
            "crossSignedByPrior": False, "pathLength": 0, "notBefore": None, "notAfter": None,
            "leafValidity": {"notBefore": None, "notAfter": None},
            "custody": {"holder": "ROOT_OFFLINE_OPERATOR", "privateMaterialInRepository": False,
                        "custodyEvidenceRef": None},
            "trustAuthorization": {"decisionRef": None, "authorizedBy": None},
        },
        "trustTransition": {"cutover": "TERMINAL_SINGLETON", "overlap": None, "quiesceEvidenceRef": None,
                            "targetGeneration": 1, "stagedAnchorBundle": None, "finalAnchorBundle": None},
        "advanceRenewal": {
            "caLifetimeSeconds": 31536000, "caSuccessorLeadSeconds": 2592000, "caWarningLeadSeconds": 3888000,
            "leafLifetimeSeconds": 518400, "leafRenewalLeadSeconds": 259200, "policyLifetimeSeconds": 172800,
            "policyRenewalLeadSeconds": 86400, "overlapSeconds": 14400, "normalBudgetSeconds": None,
            "caSuccessorBudgetSeconds": None, "safetySeconds": 630, "clockSkewSeconds": 30,
        },
        "measuredBudgets": {"source": "UNKNOWN", "evidenceRef": None, "phaseSeconds": {p: None for p in checker.PHASES},
                            "observationFreshnessSeconds": None, "heartbeatFreshnessSeconds": None,
                            "challengeLifetimeSeconds": None},
        "servingBinaryMigration": {"status": "NOT_REVIEWED", "reviewRef": None},
        "writerFence": {"token": None, "generation": None},
        "placement": {"controlPlaneHostPC": "PC3", "excludedPCs": ["PC5"]},
        "controlPlaneClient": {"spiffeURI": cp_uri(tenant, epoch), "keyContinuity": "RETAINED",
                               "publicKeySHA256": None, "csrDER": None, "priorLeafDER": None, "leafDER": None,
                               "plannedLeafSHA256": None, "contextSites": list(checker.SITES),
                               "processInventory": None},
        "roleKeys": [{"role": "LAUNCH_SIGNER", "publicKeySHA256": None, "disposition": "RETAINED",
                      "continuity": {"verifiedBy": None, "scope": "LAUNCH_SIGNATURES", "custodyEvidenceRef": None,
                                     "compromiseDecision": "UNDETERMINED", "decisionRef": None}}],
        "members": [rot(pc) for pc in ("PC2", "PC3", "PC4")] + [pc1],
        "existingNodeRows": {"source": "HISTORICAL_EVIDENCE", "includesRetired": None, "readbackSHA256": None,
                             "rows": [{"nodeID": v[0], "status": "ACTIVE", "publicKeySHA256": None,
                                       "channelCertificateSHA256": None} for v in nodes.values()]},
        "operationManifest": None,
        "checkpoint": checkpoint(resume_at="2026-11-18T11:53:13Z",
                                 readback=empty_readback(db=False, epoch=None)),
    }


def render() -> dict[str, str]:
    files: dict[str, str] = {}
    entries = []

    def dump(doc):
        return json.dumps(doc, indent=1, ensure_ascii=False) + "\n"

    files["instances/fleet5-nov18-ca-terminal-hold-r2.json"] = dump(current_instance())
    entries.append({"path": "instances/fleet5-nov18-ca-terminal-hold-r2.json", "codes": [],
                    "why": "Real Nov18 fleet plan from Root544 evidence; HOLD with every unknown null."})
    for name, (why, doc) in positives_cache().items():
        path = f"fixtures/positive/{name}.json"
        files[path] = dump(doc)
        entries.append({"path": path, "codes": [], "why": why})
    for name, (why, codes, doc) in rejections().items():
        path = f"fixtures/rejection/{name}.json"
        files[path] = dump(doc)
        entries.append({"path": path, "codes": sorted(codes), "why": why})
    source_text = files[HANDOFF_SOURCE]
    files[HANDOFF_PATH] = dump(checker.enrollment_handoff(json.loads(source_text), HANDOFF_SOURCE,
                                                          source_text.encode("utf-8"), hosts=HANDOFF_HOSTS,
                                                          control_plane_host=HANDOFF_CP_HOST))
    sample = json.loads(files[MANIFEST_SAMPLE_SOURCE])
    files[MANIFEST_SAMPLE_PATH] = dump({"schema": "fleet5-authority-replacement-manifest-sample:2",
                                        "sourcePlan": MANIFEST_SAMPLE_SOURCE,
                                        "manifest": checker.expected_manifest(sample)})
    files["expectations.json"] = dump({
        "schema": "fleet5-authority-replacement-expectations:2",
        "status": "PROPOSED_NOT_IMPLEMENTED",
        "generator": "tools/generate_fleet5_authority_replacement_r2_fixtures.py",
        "checker": "tools/check_fleet5_authority_replacement_r2.py",
        "documents": entries,
        "handoffs": [{"path": HANDOFF_PATH, "sourcePlan": HANDOFF_SOURCE, "hosts": HANDOFF_HOSTS,
                      "controlPlaneHostId": HANDOFF_CP_HOST,
                      "why": "PC1 first-enrollment handoff, scoped as four-member migration evidence."}],
        "manifestSamples": [{"path": MANIFEST_SAMPLE_PATH, "sourcePlan": MANIFEST_SAMPLE_SOURCE}],
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
