"""Ephemeral CI cryptographic scope. Never reads production material."""
from datetime import datetime, timedelta, timezone
import base64
import ipaddress
import secrets
import time
from dataclasses import replace
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from inv import proposed_expired_policy_recovery as r


def certificate(key, ca_key, ca, uri=None, ip=None, ca_cert=False, expiry=3600):
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'isolated-candidate-actor')])
    b = x509.CertificateBuilder().subject_name(name).issuer_name(ca.subject if ca else name).public_key(key).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(seconds=60)).not_valid_after(now+timedelta(seconds=expiry))
    b = b.add_extension(x509.BasicConstraints(ca=ca_cert, path_length=0 if ca_cert else None),critical=True)
    b = b.add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False, data_encipherment=False, key_agreement=False, key_cert_sign=ca_cert, crl_sign=ca_cert, encipher_only=None, decipher_only=None),critical=True)
    if not ca_cert:
        sans = [x509.UniformResourceIdentifier(uri)] + ([x509.IPAddress(ipaddress.ip_address(ip))] if ip else [])
        b = b.add_extension(x509.SubjectAlternativeName(sans),critical=False).add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH if ip else ExtendedKeyUsageOID.CLIENT_AUTH]),critical=False)
    return b.sign(ca_key,algorithm=None)


class Fixture:
    def __init__(self, node_public=None):
        self.tenant = 'candidate-'+secrets.token_hex(8)
        self.epoch = 'epoch-'+secrets.token_hex(8)
        self.ca_key = Ed25519PrivateKey.generate()
        self.ca = certificate(self.ca_key.public_key(),self.ca_key,None,ca_cert=True,expiry=7200)
        self.cp_key = Ed25519PrivateKey.generate()
        self.cp = certificate(self.cp_key.public_key(),self.ca_key,self.ca,uri=f'spiffe://saintvision.ai/tenant/{self.tenant}/control-plane/epoch/{self.epoch}')
        self.authorizer = Ed25519PrivateKey.generate(); self.operator = Ed25519PrivateKey.generate()
        self.node_keys = {} if node_public else {f'candidate_node_{i}':Ed25519PrivateKey.generate() for i in range(3)}
        public = node_public or {n:k.public_key() for n,k in self.node_keys.items()}
        self.certs = {n:certificate(pub,self.ca_key,self.ca,uri=f'spiffe://saintvision.ai/tenant/{self.tenant}/node/{n}/epoch/{self.epoch}',ip=f'172.30.0.{i+2}') for i,(n,pub) in enumerate(sorted(public.items()))}
        self.contexts = [{'site':site,'state':'absent','instances':[],'basis':'trusted-operator-inventory-not-hardware'} for site in sorted(r.SITES)]
        self.trust = r.CandidateTrust(self.tenant,self.epoch,{n:r.NodeBinding(c.public_bytes(serialization.Encoding.DER),f'172.30.0.{i+2}') for i,(n,c) in enumerate(sorted(self.certs.items()))},self.ca.public_bytes(serialization.Encoding.DER),self.cp.public_bytes(serialization.Encoding.DER),self.authorizer.public_key(),self.operator.public_key(),'a'*64,r.sha(r.canonical(self.contexts)))
        self.c = [8,21,42]; self.p = [4,13,29]
        self.prior = {n:'' for n in self.certs}

    def authorization(self, counter=1, members=None, **changes):
        now = int(time.time())
        if members is None:
            members = [dict(nodeId=n,ip=b.ip,nodeFingerprint=r.sha(b.certificate_der),priorC=self.c[i],targetC=self.c[i]+1,priorP=self.p[i],targetP=self.p[i]+1,floorSHA256='b'*64,identitySHA256='c'*64,policySHA256='d'*64,configDigest='e'*64,previousCheckpoint=self.prior[n],priorPolicyExpiresAt=now-60) for i,(n,b) in enumerate(sorted(self.trust.nodes.items()))]
        body = dict(schema='sv-expired-policy-authorization:1',role='recovery-authorizer',operation=secrets.token_hex(16),nonce=secrets.token_hex(32),counter=counter,issuedAt=now,deadline=now+90,candidateBudgetSeconds=10,productionBudgetSeconds=None,scenario='never-started',tenantId=self.tenant,epoch=self.epoch,members=members,caFingerprint=r.sha(self.trust.ca_der),cpDER=base64.b64encode(self.trust.cp_der).decode(),cpFingerprint=r.sha(self.trust.cp_der),contexts=self.contexts,contextGeneration=counter,revokedFingerprints=[],publicationAllowed=False)
        body.update(changes)
        return body,r.sign(body,r.AUTH,self.authorizer)

    def request(self, auth, envelope, node, lock=(0,1), image='f'*64, container='9'*64):
        op = dict(schema='sv-expired-policy-operator:1',role='operator-custody-not-hardware',proposalDigest=r.sha(r.canonical(auth)),nodeId=node,containerId=container,imageId=image,helperSHA256=self.trust.helper_sha256,UID=1000,lockDevice=lock[0],lockInode=lock[1],contextsDigest=self.trust.contexts_digest,issuedAt=auth['issuedAt'],deadline=auth['deadline'])
        return r.canonical({'authorization':envelope,'operator':r.sign(op,r.OPERATOR,self.operator)})

    def reference_proofs(self, auth, envelope):
        # Unit tests sign reference payloads. The Docker proof never uses these
        # synthetic filesystem observations and uses only actual Go output.
        requests = {n:self.request(auth,envelope,n) for n in self.trust.nodes}
        proofs = {}
        for m in auth['members']:
            n = m['nodeId']; request = r.parse(requests[n]); op,opraw = r.verify(request['operator'],r.OPERATOR,self.trust.operator)
            body = dict(schema='sv-expired-policy-nonserving-proof:1',assurance='operator-custody-and-file-lock-not-hardware',serving=False,servingPID=None,operation=auth['operation'],nonce=auth['nonce'],counter=auth['counter'],tenantId=self.tenant,epoch=self.epoch,nodeId=n,proposalDigest=r.sha(r.canonical(auth)),requestDigest=r.sha(requests[n]),operatorDigest=r.sha(opraw),helperSHA256=self.trust.helper_sha256,containerId=op['containerId'],imageId=op['imageId'],lockDevice=op['lockDevice'],lockInode=op['lockInode'],lockHeldAtSigning=True,observedAt=int(time.time()),deadline=auth['deadline'],activationAllowed=False)
            body.update({k:m[k] for k in ['priorC','priorP','floorSHA256','identitySHA256','configDigest','previousCheckpoint']})
            proofs[n] = r.sign(body,r.PROOF,self.node_keys[n])
        return requests,proofs

    def reference_records(self, auth, requests, proofs, acks):
        records = {}
        for m in auth['members']:
            n=m['nodeId']; ack,_=r.verify(acks[n],r.ACK,self.trust.authorizer)
            cp=dict(schema='sv-expired-policy-candidate-checkpoint:1',operation=auth['operation'],counter=auth['counter'],requestDigest=r.sha(requests[n]),proofDigest=r.sha(r.canonical(proofs[n])),ackDigest=r.sha(r.canonical(acks[n])),batchProofDigest=ack['batchProofDigest'],previousCheckpoint=m['previousCheckpoint'],nodeId=n,tenantId=self.tenant,epoch=self.epoch,checkpointAt=int(time.time()),lockHeldThroughCheckpoint=True,activationAllowed=False)
            records[n]=dict(schema='sv-expired-policy-record:1',requestDigest=r.sha(requests[n]),proof=proofs[n],checkpoint=r.sign(cp,r.CHECKPOINT,self.node_keys[n]))
        return records
