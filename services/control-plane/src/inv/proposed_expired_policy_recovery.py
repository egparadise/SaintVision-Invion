"""PROPOSED policy-expired/leaf-valid candidate, never imported by live composition.

Real signatures and a durable *reference* CAS ledger. It owns no production
connection, policy publisher, migration adapter or activation authority.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import time

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.x509.oid import ExtendedKeyUsageOID

MAX_BYTES = 65536
MAX_INT = 9007199254740991
AUTH = b"saintvision/expired-policy/authorization/v1\0"
OPERATOR = b"saintvision/expired-policy/operator-custody/v1\0"
PROOF = b"saintvision/expired-policy/nonserving-proof/v1\0"
ACK = b"saintvision/expired-policy/checkpoint-request/v1\0"
CHECKPOINT = b"saintvision/expired-policy/candidate-checkpoint/v1\0"
SITES = frozenset({"observer_worker.py:58", "worker.py:122", "workspace_config.py:54",
                   "build_product_runtime.py:537", "storage_check_collect.py:381"})
HEX = re.compile(r"[0-9a-f]{64}\Z")
OPID = re.compile(r"[0-9a-f]{32}\Z")
AUTH_KEYS = frozenset({"schema", "role", "operation", "nonce", "counter", "issuedAt", "deadline",
    "candidateBudgetSeconds", "productionBudgetSeconds", "scenario", "tenantId", "epoch", "members",
    "caFingerprint", "cpDER", "cpFingerprint", "contexts", "contextGeneration", "revokedFingerprints", "publicationAllowed"})
MEMBER_KEYS = frozenset({"nodeId", "ip", "nodeFingerprint", "priorC", "targetC", "priorP", "targetP",
    "floorSHA256", "identitySHA256", "policySHA256", "configDigest", "previousCheckpoint", "priorPolicyExpiresAt"})
OPERATOR_KEYS = frozenset({"schema", "role", "proposalDigest", "nodeId", "containerId", "imageId",
    "helperSHA256", "UID", "lockDevice", "lockInode", "contextsDigest", "issuedAt", "deadline"})
PROOF_KEYS = frozenset({"schema", "assurance", "serving", "servingPID", "operation", "nonce", "counter",
    "tenantId", "epoch", "nodeId", "proposalDigest", "requestDigest", "operatorDigest", "helperSHA256",
    "containerId", "imageId", "lockDevice", "lockInode", "lockHeldAtSigning", "observedAt", "deadline",
    "priorP", "priorC", "floorSHA256", "identitySHA256", "configDigest", "previousCheckpoint", "activationAllowed"})
ACK_KEYS = frozenset({"schema", "role", "operation", "proposalDigest", "proofDigest", "batchProofDigest", "counter", "deadline"})
CHECKPOINT_KEYS = frozenset({"schema", "operation", "counter", "requestDigest", "proofDigest", "ackDigest",
    "batchProofDigest", "previousCheckpoint", "nodeId", "tenantId", "epoch", "checkpointAt", "lockHeldThroughCheckpoint", "activationAllowed"})


class Refusal(ValueError):
    """Typed, content-free refusal suitable for public evidence."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise Refusal(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    def check(item, depth=0):
        require(depth <= 16, "RECOVERY_WIRE_DEPTH")
        if isinstance(item, dict):
            for key, child in item.items():
                require(type(key) is str, "RECOVERY_WIRE_KEY")
                check(key, depth+1); check(child, depth+1)
        elif isinstance(item, list):
            require(len(item) <= 128, "RECOVERY_WIRE_ARRAY")
            for child in item:
                check(child, depth+1)
        elif type(item) is str:
            require(all(32 <= ord(c) <= 126 and c not in '<>&' for c in item), "RECOVERY_WIRE_STRING")
        elif type(item) is int:
            require(-MAX_INT <= item <= MAX_INT, "RECOVERY_WIRE_NUMBER")
        else:
            require(item is None or type(item) is bool, "RECOVERY_WIRE_TYPE")
    check(value)
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def parse(raw):
    require(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, "RECOVERY_WIRE_SIZE")
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "RECOVERY_WIRE_DUPLICATE")
            out[key] = value
        return out
    def invalid(_):
        raise Refusal("RECOVERY_WIRE_NUMBER")
    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_float=invalid, parse_constant=invalid)
    except Refusal:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise Refusal("RECOVERY_WIRE_JSON") from None
    require(type(value) is dict and canonical(value) == raw, "RECOVERY_WIRE_NONCANONICAL")
    return value


def closed(value, keys, code):
    require(type(value) is dict and set(value) == set(keys), code)


def number(value, minimum=0, maximum=MAX_INT):
    return type(value) is int and minimum <= value <= maximum


def unbase64(text):
    require(type(text) is str, "RECOVERY_ENVELOPE")
    try:
        raw = base64.b64decode(text, validate=True)
    except (ValueError, TypeError):
        raise Refusal("RECOVERY_ENVELOPE") from None
    require(base64.b64encode(raw).decode() == text and len(raw) <= MAX_BYTES, "RECOVERY_ENVELOPE")
    return raw


def verify(envelope, domain, public):
    closed(envelope, {"payload", "signature"}, "RECOVERY_ENVELOPE")
    raw = unbase64(envelope['payload'])
    require(type(envelope['signature']) is str and re.fullmatch(r'[0-9a-f]{128}', envelope['signature']) is not None, "RECOVERY_SIGNATURE")
    try:
        public.verify(bytes.fromhex(envelope['signature']), domain+raw)
    except (InvalidSignature, ValueError, TypeError):
        raise Refusal("RECOVERY_SIGNATURE") from None
    return parse(raw), raw


def sign(body, domain, private):
    raw = canonical(body)
    require(len(raw) <= MAX_BYTES, "RECOVERY_WIRE_SIZE")
    return {'payload': base64.b64encode(raw).decode(), 'signature': private.sign(domain+raw).hex()}


@dataclass(frozen=True)
class NodeBinding:
    certificate_der: bytes
    ip: str


@dataclass(frozen=True)
class CandidateTrust:
    """Explicit out-of-band PUBLIC bindings, not values learned from a request."""
    tenant: str
    epoch: str
    nodes: dict[str, NodeBinding]
    ca_der: bytes
    cp_der: bytes
    authorizer: Ed25519PublicKey
    operator: Ed25519PublicKey
    helper_sha256: str
    contexts_digest: str
    revoked: frozenset[str] = frozenset()


def leafs(trust, now):
    try:
        ca = x509.load_der_x509_certificate(trust.ca_der)
        cp = x509.load_der_x509_certificate(trust.cp_der)
        require(isinstance(ca.public_key(), Ed25519PublicKey), "RECOVERY_ALGORITHM")
        require(now < ca.not_valid_after_utc.timestamp(), "RECOVERY_TERMINAL_CA_EXPIRED")
        require(ca.not_valid_before_utc.timestamp() <= now and ca.issuer == ca.subject, "RECOVERY_CA")
        basic = ca.extensions.get_extension_for_class(x509.BasicConstraints).value
        require(basic.ca and basic.path_length == 0 and ca.extensions.get_extension_for_class(x509.KeyUsage).value.key_cert_sign, "RECOVERY_CA")
        ca.public_key().verify(ca.signature, ca.tbs_certificate_bytes)
        result = {}
        for node_id, binding in [(None, NodeBinding(trust.cp_der, '')), *sorted(trust.nodes.items())]:
            cert = cp if node_id is None else x509.load_der_x509_certificate(binding.certificate_der)
            require(now < cert.not_valid_after_utc.timestamp(), "RECOVERY_TERMINAL_LEAF_EXPIRED")
            require(isinstance(cert.public_key(), Ed25519PublicKey), "RECOVERY_ALGORITHM")
            require(cert.not_valid_before_utc.timestamp() <= now and cert.not_valid_after_utc <= ca.not_valid_after_utc and cert.issuer == ca.subject, "RECOVERY_LEAF")
            require(not cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca and cert.extensions.get_extension_for_class(x509.KeyUsage).value.digital_signature, "RECOVERY_LEAF")
            for extension in cert.extensions:
                require(not extension.critical or isinstance(extension.value, (x509.BasicConstraints, x509.KeyUsage, x509.SubjectAlternativeName)), "RECOVERY_LEAF_CRITICAL")
            ca.public_key().verify(cert.signature, cert.tbs_certificate_bytes)
            san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
            uri = f'spiffe://saintvision.ai/tenant/{trust.tenant}/' + (f'node/{node_id}/epoch/{trust.epoch}' if node_id else f'control-plane/epoch/{trust.epoch}')
            require(san.get_values_for_type(x509.UniformResourceIdentifier) == [uri], "RECOVERY_SCOPE")
            expected_usage = ExtendedKeyUsageOID.SERVER_AUTH if node_id else ExtendedKeyUsageOID.CLIENT_AUTH
            require(list(cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value) == [expected_usage], "RECOVERY_EKU")
            ips = san.get_values_for_type(x509.IPAddress)
            require((len(ips) == 1 and str(ips[0]) == binding.ip) if node_id else not ips, "RECOVERY_IP")
            require(len(san) == (2 if node_id else 1), "RECOVERY_SCOPE")
            require(sha(cert.public_bytes(serialization.Encoding.DER)) not in trust.revoked, "RECOVERY_REVOKED")
            result[node_id] = cert
        require(sha(trust.ca_der) not in trust.revoked, "RECOVERY_REVOKED")
        public_values = [key.public_bytes_raw() for key in [trust.authorizer, trust.operator, ca.public_key(), cp.public_key(), *[result[n].public_key() for n in trust.nodes]]]
        require(len(set(public_values)) == len(public_values), "RECOVERY_ROLE_SEPARATION")
        return result
    except Refusal:
        raise
    except Exception:
        raise Refusal("RECOVERY_LEAF") from None


def verify_contexts(contexts, generation, expected_digest):
    require(type(contexts) is list and len(contexts) == 5 and number(generation, 1), "RECOVERY_HOLD_CONTEXT_INVENTORY")
    require(sha(canonical(contexts)) == expected_digest, "RECOVERY_HOLD_CONTEXT_INVENTORY")
    seen = set()
    for item in contexts:
        closed(item, {'site', 'state', 'instances', 'basis'}, "RECOVERY_HOLD_CONTEXT_INVENTORY")
        require(type(item['site']) is str and item['site'] in SITES and item['site'] not in seen and item['basis'] == 'trusted-operator-inventory-not-hardware', "RECOVERY_HOLD_CONTEXT_INVENTORY")
        seen.add(item['site'])
        require(type(item['instances']) is list and type(item['state']) is str and item['state'] in {'present', 'absent'}, "RECOVERY_HOLD_CONTEXT_INVENTORY")
        require(bool(item['instances']) == (item['state'] == 'present'), "RECOVERY_HOLD_CONTEXT_INVENTORY")
        ids = set()
        for instance in item['instances']:
            closed(instance, {'id', 'generation', 'credentialFingerprint'}, "RECOVERY_HOLD_CONTEXT_INVENTORY")
            require(type(instance['id']) is str and instance['id'] and instance['id'] not in ids and number(instance['generation'],1) and instance['generation'] == generation and type(instance['credentialFingerprint']) is str and HEX.fullmatch(instance['credentialFingerprint']), "RECOVERY_HOLD_STALE_CONTEXT")
            ids.add(instance['id'])


def authorization(envelope, trust):
    now = int(time.time())
    certificates = leafs(trust, now)
    body, raw = verify(envelope, AUTH, trust.authorizer)
    closed(body, AUTH_KEYS, "RECOVERY_AUTHORIZATION")
    require(body['schema'] == 'sv-expired-policy-authorization:1' and body['role'] == 'recovery-authorizer' and body['publicationAllowed'] is False and body['productionBudgetSeconds'] is None, "RECOVERY_AUTHORIZATION")
    require(body['tenantId'] == trust.tenant and body['epoch'] == trust.epoch and len(trust.nodes) == 3, "RECOVERY_SCOPE")
    require(type(body['operation']) is str and OPID.fullmatch(body['operation']) and type(body['nonce']) is str and HEX.fullmatch(body['nonce']), "RECOVERY_SCOPE")
    require(number(body['counter'], 1, 99999999), "RECOVERY_COUNTER_REUSE")
    require(body['scenario'] in {'never-started', 'partial-migration', 'partial-publication'}, "RECOVERY_SCENARIO")
    require(body['scenario'] == 'never-started', "RECOVERY_HOLD_PARTIAL_RECONCILIATION_NOT_BOUND")
    require(number(body['issuedAt']) and number(body['deadline']) and -30 <= now-body['issuedAt'] <= 120 and now < body['deadline'] <= body['issuedAt']+120, "RECOVERY_CHALLENGE_EXPIRED")
    require(number(body['candidateBudgetSeconds'], 1, 60) and now+body['candidateBudgetSeconds'] < body['deadline'], "RECOVERY_DEADLINE")
    require(min(cert.not_valid_after_utc.timestamp() for cert in certificates.values())-now > body['candidateBudgetSeconds']+660, "RECOVERY_DEADLINE")
    require(body['caFingerprint'] == sha(trust.ca_der) and body['cpFingerprint'] == sha(trust.cp_der) and unbase64(body['cpDER']) == trust.cp_der, "RECOVERY_CERTIFICATE_PIN")
    require(body['revokedFingerprints'] == sorted(trust.revoked), "RECOVERY_REVOCATION_BINDING")
    verify_contexts(body['contexts'], body['contextGeneration'], trust.contexts_digest)
    for item in body['contexts']:
        require(all(instance['credentialFingerprint'] == sha(trust.cp_der) for instance in item['instances']), "RECOVERY_HOLD_STALE_CONTEXT")
    require(type(body['members']) is list and all(type(m) is dict for m in body['members']) and [m.get('nodeId') for m in body['members']] == sorted(trust.nodes), "RECOVERY_MEMBERS")
    for m in body['members']:
        closed(m, MEMBER_KEYS, "RECOVERY_MEMBERS")
        require(m['ip'] == trust.nodes[m['nodeId']].ip and m['nodeFingerprint'] == sha(trust.nodes[m['nodeId']].certificate_der), "RECOVERY_CERTIFICATE_PIN")
        require(number(m['priorC'], 1, MAX_INT-1) and m['targetC'] == m['priorC']+1 and type(m['targetC']) is int and number(m['priorP'], 1, MAX_INT-1) and m['targetP'] == m['priorP']+1 and type(m['targetP']) is int, "RECOVERY_GENERATIONS")
        require(number(m['priorPolicyExpiresAt']) and m['priorPolicyExpiresAt'] <= now, "RECOVERY_POLICY_NOT_EXPIRED")
        require(all(type(m[k]) is str and HEX.fullmatch(m[k]) for k in ['floorSHA256','identitySHA256','policySHA256','configDigest']), "RECOVERY_SCOPE")
        require(m['previousCheckpoint'] == '' or type(m['previousCheckpoint']) is str and HEX.fullmatch(m['previousCheckpoint']), "RECOVERY_COUNTER_REUSE")
    return body, raw, certificates


def verify_proofs(auth_envelope, requests, proofs, trust):
    auth, raw, certificates = authorization(auth_envelope, trust)
    require(set(requests) == set(proofs) == set(trust.nodes), "RECOVERY_MEMBERS")
    now = int(time.time())
    for member in auth['members']:
        node = member['nodeId']; request = parse(requests[node])
        closed(request, {'authorization','operator'}, "RECOVERY_REQUEST")
        require(request['authorization'] == auth_envelope, "RECOVERY_REPLAY_MISMATCH")
        operator, opraw = verify(request['operator'], OPERATOR, trust.operator)
        closed(operator, OPERATOR_KEYS, "RECOVERY_OPERATOR_BINDING")
        require(operator['schema'] == 'sv-expired-policy-operator:1' and operator['role'] == 'operator-custody-not-hardware' and operator['proposalDigest'] == sha(raw) and operator['nodeId'] == node and operator['UID'] == 1000, "RECOVERY_OPERATOR_BINDING")
        require(operator['helperSHA256'] == trust.helper_sha256 and operator['contextsDigest'] == trust.contexts_digest and all(type(operator[k]) is str and HEX.fullmatch(operator[k]) for k in ['containerId','imageId']) and number(operator['lockDevice']) and number(operator['lockInode']), "RECOVERY_OPERATOR_BINDING")
        require(number(operator['issuedAt']) and -30 <= now-operator['issuedAt'] <= 120 and operator['deadline'] == auth['deadline'], "RECOVERY_CHALLENGE_EXPIRED")
        proof, _ = verify(proofs[node], PROOF, certificates[node].public_key())
        closed(proof, PROOF_KEYS, "RECOVERY_PROOF_SHAPE")
        require(all(number(proof[k]) for k in ['counter','lockDevice','lockInode','observedAt','deadline','priorP','priorC']), 'RECOVERY_PROOF_SHAPE')
        require(proof['schema'] == 'sv-expired-policy-nonserving-proof:1' and proof['serving'] is False and proof['servingPID'] is None and proof['assurance'] == 'operator-custody-and-file-lock-not-hardware' and proof['activationAllowed'] is False and proof['lockHeldAtSigning'] is True, "RECOVERY_NOT_LIVE_M2")
        expected = {'operation':auth['operation'],'nonce':auth['nonce'],'counter':auth['counter'],'tenantId':trust.tenant,'epoch':trust.epoch,'nodeId':node,'proposalDigest':sha(raw),'requestDigest':sha(requests[node]),'operatorDigest':sha(opraw),'helperSHA256':trust.helper_sha256,'deadline':auth['deadline']}
        expected.update({k:operator[k] for k in ['containerId','imageId','lockDevice','lockInode']})
        expected.update({k:member[k] for k in ['priorC','priorP','floorSHA256','identitySHA256','configDigest','previousCheckpoint']})
        require(all(proof[k] == v for k,v in expected.items()), "RECOVERY_PROOF_BINDING")
        require(number(proof['observedAt']) and -30 <= now-proof['observedAt'] <= 120 and proof['observedAt'] >= auth['issuedAt']-30, "RECOVERY_CHALLENGE_EXPIRED")
    return auth, raw, sha(canonical(proofs))


def checkpoint_requests(auth_envelope, requests, proofs, trust, authorizer_private):
    auth, raw, batch = verify_proofs(auth_envelope, requests, proofs, trust)
    require(authorizer_private.public_key() == trust.authorizer or authorizer_private.public_key().public_bytes_raw() == trust.authorizer.public_bytes_raw(), "RECOVERY_ROLE_SEPARATION")
    return {node:sign({'schema':'sv-expired-policy-checkpoint-request:1','role':'recovery-authorizer','operation':auth['operation'],'proposalDigest':sha(raw),'proofDigest':sha(canonical(proofs[node])),'batchProofDigest':batch,'counter':auth['counter'],'deadline':auth['deadline']},ACK,authorizer_private) for node in trust.nodes}


class CandidateLedger:
    """SQLite reference CAS only. No DSN, real provisioning or live publication.

    Bootstrap is explicit and exclusive. The caller's out-of-band trust and
    initial C/P values must be authenticated; this fixture/reference is not that
    production authorizer. Missing adapters always block activation.
    """
    def __init__(self, path, trust):
        self.path, self.trust = Path(path), trust

    @classmethod
    def create_reference(cls, path, trust, initial):
        path = Path(path)
        require(set(initial) == set(trust.nodes), "RECOVERY_MEMBERS")
        fd = os.open(path, os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW, 0o600)
        os.close(fd)
        ledger = cls(path, trust)
        with ledger.connect() as db:
            db.executescript('CREATE TABLE nodes(node TEXT PRIMARY KEY,c INTEGER NOT NULL,p INTEGER NOT NULL); CREATE TABLE operations(op TEXT PRIMARY KEY,nonce TEXT UNIQUE NOT NULL,digest TEXT NOT NULL,counter INTEGER UNIQUE NOT NULL,phase TEXT NOT NULL,batch TEXT NOT NULL,receipt BLOB); CREATE TABLE audit(op TEXT NOT NULL,node TEXT NOT NULL,c INTEGER NOT NULL,p INTEGER NOT NULL,digest TEXT NOT NULL,PRIMARY KEY(op,node));')
            for node,(c,p) in initial.items():
                require(number(c,1) and number(p,1), "RECOVERY_GENERATIONS")
                db.execute('INSERT INTO nodes VALUES(?,?,?)',(node,c,p))
        return ledger

    def connect(self):
        st = self.path.lstat()
        require(stat.S_ISREG(st.st_mode) and st.st_uid == os.geteuid() and st.st_mode & 0o077 == 0 and st.st_nlink == 1, "RECOVERY_HOLD_LEDGER_CUSTODY")
        db = sqlite3.connect(self.path, isolation_level=None, timeout=5)
        after = self.path.lstat()
        require((st.st_dev,st.st_ino,st.st_mode,st.st_uid,st.st_nlink) == (after.st_dev,after.st_ino,after.st_mode,after.st_uid,after.st_nlink), "RECOVERY_HOLD_LEDGER_CUSTODY")
        db.execute('PRAGMA synchronous=FULL')
        return db

    def prepare(self, envelope, requests, proofs):
        auth, raw, batch = verify_proofs(envelope,requests,proofs,self.trust)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                old = db.execute('SELECT nonce,digest,counter,phase,batch FROM operations WHERE op=?',(auth['operation'],)).fetchone()
                phase = 'PREPARED'
                expected = (auth['nonce'],sha(raw),auth['counter'])
                if old:
                    phase = old[3]
                    require(old[:3] == expected and old[3] in {'PREPARED','CANDIDATE_COMMITTED'} and old[4] == batch, "RECOVERY_REPLAY_MISMATCH")
                else:
                    require(auth['counter'] == db.execute('SELECT COALESCE(MAX(counter),0)+1 FROM operations').fetchone()[0], "RECOVERY_COUNTER_REUSE")
                    for m in auth['members']:
                        require(db.execute('SELECT c,p FROM nodes WHERE node=?',(m['nodeId'],)).fetchone() == (m['priorC'],m['priorP']), "RECOVERY_CAS_CONFLICT")
                    require(db.execute('SELECT 1 FROM operations WHERE nonce=?',(auth['nonce'],)).fetchone() is None, 'RECOVERY_REPLAY_MISMATCH')
                    db.execute('INSERT INTO operations VALUES(?,?,?,?,?,?,NULL)',(auth['operation'],auth['nonce'],sha(raw),auth['counter'],'PREPARED',batch))
                db.commit()
            except Exception:
                db.rollback(); raise
        return {'phase':phase,'activationAllowed':False,'scope':'REFERENCE_CANDIDATE_ONLY','batchProofDigest':batch}

    def commit_reference(self, envelope, requests, proofs, acknowledgements, records):
        auth, raw, batch = verify_proofs(envelope,requests,proofs,self.trust)
        require(set(records) == set(acknowledgements) == set(self.trust.nodes), "RECOVERY_MEMBERS")
        certificates = leafs(self.trust,int(time.time()))
        for m in auth['members']:
            node = m['nodeId']; record = records[node]
            closed(record, {'schema','requestDigest','proof','checkpoint'}, "RECOVERY_CHECKPOINT_SHAPE")
            require(record['schema'] == 'sv-expired-policy-record:1' and record['proof'] == proofs[node] and record['requestDigest'] == sha(requests[node]), "RECOVERY_REPLAY_MISMATCH")
            ack, _ = verify(acknowledgements[node],ACK,self.trust.authorizer)
            closed(ack,ACK_KEYS,"RECOVERY_CHECKPOINT_AUTHORIZATION")
            require(number(ack['counter'],1) and number(ack['deadline']), 'RECOVERY_CHECKPOINT_AUTHORIZATION')
            expected_ack = {'schema':'sv-expired-policy-checkpoint-request:1','role':'recovery-authorizer','operation':auth['operation'],'proposalDigest':sha(raw),'proofDigest':sha(canonical(proofs[node])),'batchProofDigest':batch,'counter':auth['counter'],'deadline':auth['deadline']}
            require(ack == expected_ack, "RECOVERY_CHECKPOINT_AUTHORIZATION")
            cp, _ = verify(record['checkpoint'],CHECKPOINT,certificates[node].public_key())
            closed(cp,CHECKPOINT_KEYS,"RECOVERY_CHECKPOINT_SHAPE")
            require(number(cp['counter'],1) and number(cp['checkpointAt']) and cp['lockHeldThroughCheckpoint'] is True and cp['activationAllowed'] is False, 'RECOVERY_CHECKPOINT_SHAPE')
            expected = {'schema':'sv-expired-policy-candidate-checkpoint:1','operation':auth['operation'],'counter':auth['counter'],'requestDigest':sha(requests[node]),'proofDigest':sha(canonical(proofs[node])),'ackDigest':sha(canonical(acknowledgements[node])),'batchProofDigest':batch,'previousCheckpoint':m['previousCheckpoint'],'nodeId':node,'tenantId':self.trust.tenant,'epoch':self.trust.epoch,'lockHeldThroughCheckpoint':True,'activationAllowed':False}
            require(all(cp[k] == v for k,v in expected.items()) and number(cp['checkpointAt']) and auth['issuedAt']-30 <= cp['checkpointAt'] < auth['deadline'], "RECOVERY_CHECKPOINT_BINDING")
        receipt = canonical({'schema':'sv-expired-policy-reference-result:1','operation':auth['operation'],'proposalDigest':sha(raw),'phase':'CANDIDATE_COMMITTED','activationAllowed':False,'liveIntegration':'HOLD_INTEGRATION_NOT_BOUND','recordsDigest':sha(canonical(records))})
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                row = db.execute('SELECT digest,phase,batch,receipt FROM operations WHERE op=?',(auth['operation'],)).fetchone()
                require(row is not None and row[0] == sha(raw) and row[2] == batch, "RECOVERY_UNKNOWN_PHASE")
                if row[1] == 'CANDIDATE_COMMITTED':
                    require(row[3] == receipt, "RECOVERY_REPLAY_MISMATCH")
                    db.commit(); return parse(row[3])
                require(row[1] == 'PREPARED', "RECOVERY_UNKNOWN_PHASE")
                for m in auth['members']:
                    changed = db.execute('UPDATE nodes SET c=?,p=? WHERE node=? AND c=? AND p=?',(m['targetC'],m['targetP'],m['nodeId'],m['priorC'],m['priorP'])).rowcount
                    require(changed == 1,"RECOVERY_CAS_CONFLICT")
                    db.execute('INSERT INTO audit VALUES(?,?,?,?,?)',(auth['operation'],m['nodeId'],m['targetC'],m['targetP'],sha(canonical(records[m['nodeId']]))))
                db.execute('UPDATE operations SET phase=?,receipt=? WHERE op=?',('CANDIDATE_COMMITTED',receipt,auth['operation']))
                db.commit()
            except Exception:
                db.rollback(); raise
        return parse(receipt)

    def activate(self):
        raise Refusal('RECOVERY_HOLD_INTEGRATION_NOT_BOUND')

    def reconcile(self, operation, proposal_digest):
        """Read-only durable outcome, never fresh authority or activation.

        Can report historical state after a challenge expires. It never retries
        a write with changed bytes or treats a missing operation as committed.
        """
        require(type(operation) is str and OPID.fullmatch(operation) and type(proposal_digest) is str and HEX.fullmatch(proposal_digest), 'RECOVERY_SCOPE')
        with self.connect() as db:
            row=db.execute('SELECT digest,phase,receipt FROM operations WHERE op=?',(operation,)).fetchone()
        require(row is not None and row[0] == proposal_digest, 'RECOVERY_UNKNOWN_OUTCOME')
        require(row[1] in {'PREPARED','CANDIDATE_COMMITTED'}, 'RECOVERY_UNKNOWN_PHASE')
        return {'phase':row[1], 'receipt':parse(row[2]) if row[2] is not None else None,
                'historicalOnly':True, 'activationAllowed':False}


def main():
    # No request/credential/env auto-discovery, production writer or force flag.
    print(json.dumps({'error':'RECOVERY_HOLD_INTEGRATION_NOT_BOUND','activationAllowed':False}))
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
