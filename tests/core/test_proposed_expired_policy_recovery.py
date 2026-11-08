"""Reference verifier tests; actual filesystem/Go proof is a separate Linux job."""
from dataclasses import replace
import copy
import importlib.util
from pathlib import Path
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from inv import proposed_expired_policy_recovery as r

spec = importlib.util.spec_from_file_location('candidate_fixture', Path(__file__).parents[1]/'proofs/recovery_candidate_fixture.py')
fixture_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_module)
Fixture = fixture_module.Fixture


def refused(code, call):
    with pytest.raises(r.Refusal) as failure:
        call()
    assert failure.value.code == code


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}',b'{"a":1.0}',b'{"a":1e1}',b'{"a":NaN}',b'{"a":9007199254740992}',b'{ "a":1}',b'{}{}',b'[]',b'x'*65537])
def test_bounded_exact_parser(raw):
    with pytest.raises(r.Refusal):
        r.parse(raw)


@pytest.mark.parametrize('field,value,code', [
    ('role','service','RECOVERY_AUTHORIZATION'),('epoch','foreign','RECOVERY_SCOPE'),
    ('tenantId','foreign','RECOVERY_SCOPE'),('publicationAllowed',True,'RECOVERY_AUTHORIZATION'),
    ('nonce','bad','RECOVERY_SCOPE'),('counter',0,'RECOVERY_COUNTER_REUSE'),
    ('scenario','unknown','RECOVERY_SCENARIO'),
    ('scenario','partial-migration','RECOVERY_HOLD_PARTIAL_RECONCILIATION_NOT_BOUND'),
    ('scenario','partial-publication','RECOVERY_HOLD_PARTIAL_RECONCILIATION_NOT_BOUND'),
    ('deadline',0,'RECOVERY_CHALLENGE_EXPIRED'),('candidateBudgetSeconds',61,'RECOVERY_DEADLINE'),
    ('caFingerprint','0'*64,'RECOVERY_CERTIFICATE_PIN')])
def test_authorization_one_invalid_property(field,value,code):
    f=Fixture(); body,env=f.authorization(**{field:value})
    refused(code,lambda:r.authorization(env,f.trust))


def test_real_roles_domains_and_member_set():
    f=Fixture(); body,env=f.authorization()
    assert r.authorization(env,f.trust)[0] == body
    refused('RECOVERY_SIGNATURE',lambda:r.authorization(r.sign(body,r.AUTH,f.operator),f.trust))
    refused('RECOVERY_SIGNATURE',lambda:r.authorization(r.sign(body,b'normal-M2:2',f.authorizer),f.trust))
    body['members'].pop()
    refused('RECOVERY_MEMBERS',lambda:r.authorization(r.sign(body,r.AUTH,f.authorizer),f.trust))


@pytest.mark.parametrize('field,value,code',[
    ('priorPolicyExpiresAt',int(time.time())+3600,'RECOVERY_POLICY_NOT_EXPIRED'),
    ('targetP',1,'RECOVERY_GENERATIONS'),('targetC',1,'RECOVERY_GENERATIONS'),
    ('ip','127.0.0.1','RECOVERY_CERTIFICATE_PIN'),('nodeFingerprint','0'*64,'RECOVERY_CERTIFICATE_PIN')])
def test_member_guards(field,value,code):
    f=Fixture(); body,_=f.authorization(); body['members'][0][field]=value
    refused(code,lambda:r.authorization(r.sign(body,r.AUTH,f.authorizer),f.trust))


def test_all_five_contexts_and_stale_present_instance():
    f=Fixture(); body,env=f.authorization()
    r.authorization(env,f.trust)
    body['contexts']=copy.deepcopy(body['contexts']); body['contexts'].pop()
    refused('RECOVERY_HOLD_CONTEXT_INVENTORY',lambda:r.authorization(r.sign(body,r.AUTH,f.authorizer),f.trust))
    f=Fixture(); f.contexts[0].update(state='present',instances=[dict(id='explicit-fixture-instance',generation=0,credentialFingerprint=r.sha(f.trust.cp_der))])
    f.trust=replace(f.trust,contexts_digest=r.sha(r.canonical(f.contexts)))
    body,env=f.authorization()
    refused('RECOVERY_HOLD_STALE_CONTEXT',lambda:r.authorization(env,f.trust))


@pytest.mark.parametrize('which,code',[('ca','RECOVERY_TERMINAL_CA_EXPIRED'),('cp','RECOVERY_TERMINAL_LEAF_EXPIRED'),('node','RECOVERY_TERMINAL_LEAF_EXPIRED')])
def test_real_certificate_terminal_refusals(which,code):
    f=Fixture()
    cert = fixture_module.certificate(f.ca_key.public_key() if which=='ca' else f.cp_key.public_key(),f.ca_key,None if which=='ca' else f.ca,ca_cert=which=='ca',uri=f'spiffe://saintvision.ai/tenant/{f.tenant}/control-plane/epoch/{f.epoch}',expiry=-1)
    der=cert.public_bytes(serialization.Encoding.DER)
    trust=replace(f.trust,**({'ca_der':der} if which=='ca' else {'cp_der':der}))
    if which=='node':
        nodes=dict(f.trust.nodes); n=next(iter(nodes)); nodes[n]=replace(nodes[n],certificate_der=der)
        trust=replace(f.trust,nodes=nodes)
    refused(code,lambda:r.leafs(trust,int(time.time())))


def test_revocation_and_role_key_reuse():
    f=Fixture()
    refused('RECOVERY_REVOKED',lambda:r.leafs(replace(f.trust,revoked=frozenset({r.sha(f.trust.cp_der)})),int(time.time())))
    refused('RECOVERY_ROLE_SEPARATION',lambda:r.leafs(replace(f.trust,operator=f.trust.authorizer),int(time.time())))


def test_signed_proof_binding_not_live_or_other_binary():
    f=Fixture(); body,env=f.authorization(); requests,proofs=f.reference_proofs(body,env)
    r.verify_proofs(env,requests,proofs,f.trust)
    node=next(iter(proofs)); proof,_=r.verify(proofs[node],r.PROOF,f.node_keys[node].public_key())
    proof['serving']=True; proofs[node]=r.sign(proof,r.PROOF,f.node_keys[node])
    refused('RECOVERY_NOT_LIVE_M2',lambda:r.verify_proofs(env,requests,proofs,f.trust))
    proof['serving']=False; proof['helperSHA256']='0'*64; proofs[node]=r.sign(proof,r.PROOF,f.node_keys[node])
    refused('RECOVERY_PROOF_BINDING',lambda:r.verify_proofs(env,requests,proofs,f.trust))


def test_reference_atomic_cas_uncertain_retry_and_counter(tmp_path):
    f=Fixture(); body,env=f.authorization(); req,proof=f.reference_proofs(body,env)
    ledger=r.CandidateLedger.create_reference(tmp_path/'reference.sqlite',f.trust,{m['nodeId']:(m['priorC'],m['priorP']) for m in body['members']})
    acks=r.checkpoint_requests(env,req,proof,f.trust,f.authorizer); records=f.reference_records(body,req,proof,acks)
    ledger.prepare(env,req,proof)
    # Two actual concurrent transactions, identical unknown-outcome retry.
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda _:ledger.commit_reference(env,req,proof,acks,records),range(2)))
    assert results[0] == results[1] and results[0]['activationAllowed'] is False
    with ledger.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM audit').fetchone()[0] == 3
        assert db.execute('SELECT COUNT(*) FROM operations').fetchone()[0] == 1
    outcome=ledger.reconcile(body['operation'],r.sha(r.canonical(body)))
    assert outcome['phase']=='CANDIDATE_COMMITTED' and outcome['historicalOnly'] is True and outcome['activationAllowed'] is False
    refused('RECOVERY_UNKNOWN_OUTCOME',lambda:ledger.reconcile('0'*32,'0'*64))
    refused('RECOVERY_HOLD_INTEGRATION_NOT_BOUND',ledger.activate)
    other,other_env=f.authorization()
    req2,proof2=f.reference_proofs(other,other_env)
    refused('RECOVERY_COUNTER_REUSE',lambda:ledger.prepare(other_env,req2,proof2))


def test_reference_cas_rolls_back_all_three_and_unknown_phase(tmp_path):
    f=Fixture(); body,env=f.authorization(); req,proof=f.reference_proofs(body,env)
    ledger=r.CandidateLedger.create_reference(tmp_path/'reference.sqlite',f.trust,{m['nodeId']:(m['priorC'],m['priorP']) for m in body['members']})
    acks=r.checkpoint_requests(env,req,proof,f.trust,f.authorizer); records=f.reference_records(body,req,proof,acks)
    refused('RECOVERY_UNKNOWN_PHASE',lambda:ledger.commit_reference(env,req,proof,acks,records))
    ledger.prepare(env,req,proof)
    with ledger.connect() as db:
        last=body['members'][-1]['nodeId']; db.execute('UPDATE nodes SET c=c+1 WHERE node=?',(last,))
        prior=db.execute('SELECT * FROM nodes ORDER BY node').fetchall()
    refused('RECOVERY_CAS_CONFLICT',lambda:ledger.commit_reference(env,req,proof,acks,records))
    with ledger.connect() as db:
        assert db.execute('SELECT * FROM nodes ORDER BY node').fetchall()==prior
        assert db.execute('SELECT COUNT(*) FROM audit').fetchone()[0]==0


def test_partial_record_and_replayed_nonce_are_not_success(tmp_path):
    f=Fixture(); body,env=f.authorization(); req,proof=f.reference_proofs(body,env)
    ledger=r.CandidateLedger.create_reference(tmp_path/'reference.sqlite',f.trust,{m['nodeId']:(m['priorC'],m['priorP']) for m in body['members']})
    ledger.prepare(env,req,proof)
    acks=r.checkpoint_requests(env,req,proof,f.trust,f.authorizer); records=f.reference_records(body,req,proof,acks)
    records.pop(next(iter(records)))
    refused('RECOVERY_MEMBERS',lambda:ledger.commit_reference(env,req,proof,acks,records))
    other,other_env=f.authorization(counter=2,nonce=body['nonce']); req2,proof2=f.reference_proofs(other,other_env)
    refused('RECOVERY_REPLAY_MISMATCH',lambda:ledger.prepare(other_env,req2,proof2))


def test_proposed_schema_closed_shapes_and_actual_signed_payloads():
    import json
    from jsonschema import Draft202012Validator
    schema=json.loads((Path(__file__).parents[2]/'contracts/proposed/expired-policy-custody-v1.schema.json').read_text())
    Draft202012Validator.check_schema(schema)
    for name,keys in [('auth',r.AUTH_KEYS),('member',r.MEMBER_KEYS),('operator',r.OPERATOR_KEYS),('proof',r.PROOF_KEYS),('ack',r.ACK_KEYS),('checkpoint',r.CHECKPOINT_KEYS)]:
        assert set(schema['$defs'][name]['required'])==keys
        assert schema['$defs'][name]['additionalProperties'] is False
    f=Fixture(); body,env=f.authorization(); requests,proofs=f.reference_proofs(body,env)
    validator=Draft202012Validator(schema)
    validator.validate(body)
    for node in proofs:
        validator.validate(r.verify(proofs[node],r.PROOF,f.node_keys[node].public_key())[0])
    body['unexpected']=True
    assert list(validator.iter_errors(body))
