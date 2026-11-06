"""Bounded synthetic contract attacks; no crypto/provider/runtime acceptance."""
from dataclasses import replace
from pathlib import Path
import copy
import datetime
import importlib.util
import json
import sys

import jsonschema  # existing requirements-docs environment; no new dependency

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('p02_model',HERE/'candidate_model.py')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)

POLICY=b'SYNTHETIC_ALREADY_BOUND_POLICY_BYTES_NOT_A_CERTIFICATE_OR_RUNTIME_PROOF'
ARTIFACT=b'SYNTHETIC_ALREADY_BOUND_ARTIFACT_BYTES_NOT_A_BINARY'
facts={k:'a1'*(20 if k in m.HASH40 else 32) for k in m.HASH40|m.HASH64}
facts.update(reviewScope='synthetic-exact-scope',reviewVerdict='SYNTHETIC_SCOPED_ACCEPT',
    toolchain='synthetic-toolchain',artifactId=303,artifactZipBytes=len(ARTIFACT),binaryVCSModified=False)
facts['policyPayloadSHA256']=m.sha(POLICY);facts['artifactZipSHA256']=m.sha(ARTIFACT)
facts['cohortScopeSHA256']='91'*32
for k in ('binarySHA256','installationBinarySHA256','runningBinarySHA256'):facts[k]='b2'*32
facts['installationReceiptSHA256']=facts['runningReceiptSHA256']='c3'*32
facts['runtimeLockSHA256']=facts['runningRuntimeLockSHA256']='d4'*32
facts['linkedClosureSHA256']=facts['runningLinkedClosureSHA256']='e5'*32
ci=[dict(runId=101,repository='synthetic/repo',headSHA=facts['sourceSHA'],ref='synthetic/ref',
    event='workflow_dispatch',workflow='.github/workflows/core.yml',correlation='synthetic-one',
    attempt=1,conclusion='success',jobs=[dict(id=201,name='core',conclusion='success',steps=[
        dict(number=1,name='actual-required-build',conclusion='success'),
        dict(number=2,name='actual-required-test',conclusion='success'),
        dict(number=3,name='explicit-optional-proof',conclusion='skipped')])]),
    dict(runId=102,repository='synthetic/repo',headSHA=facts['sourceSHA'],ref='synthetic/ref',
    event='workflow_dispatch',workflow='.github/workflows/docs.yml',correlation='synthetic-two',
    attempt=1,conclusion='success',jobs=[dict(id=202,name='docs',conclusion='success',steps=[
        dict(number=1,name='actual-required-docs',conclusion='success')])])]
control=dict(body=dict(format=m.FORMAT,purpose=m.PURPOSE,selector='synthetic_legacy_two',
    scopeSHA256='91'*32,capsuleSHA256='95'*32,provisioningGeneration='synthetic-install-1',anchorVersion=1,recordVersion=7,requestBindingSHA256='92'*32,
    issuedAt=990,validUntil=1100,facts=facts,ciRuns=ci),signer=dict(keySPKISHA256='93'*32),signatureHex='94'*64)
required=((101,'core',1,'actual-required-build'),(101,'core',2,'actual-required-test'),(102,'docs',1,'actual-required-docs'))
optional=((101,'core',3,'explicit-optional-proof'),)

def bound(envelope=control,**changes):
    # This is an explicit synthetic authentication bypass, never a signature verifier.
    defaults=dict(key_spki=control['signer']['keySPKISHA256'],selector=control['body']['selector'],
        scope=control['body']['scopeSHA256'],anchor_version=1,capsule_sha='95'*32,generation='synthetic-install-1',purpose=m.PURPOSE,
        facts=m.canonical(facts),ci=m.canonical(ci),required_steps=required,allowed_skips=optional,
        signatures=frozenset(((m.sha(m.projection(envelope)),envelope['signatureHex'],control['signer']['keySPKISHA256']),)),
        minimum_version=7,current_version=7,current_digest=m.record_identity(envelope),
        request_binding='92'*32,lower=1000,upper=1001,checked=995,status_expires=1100,
        ticket_issued=985,ticket_expires=1100,key_before=900,key_after=1200,status='ACTIVE',v0=b'synthetic-V0',v1=b'synthetic-V0')
    defaults.update(changes)
    return m.SyntheticBoundInputs(**defaults)

results=[]
def run(name,expected,envelope=None,anchor=None,raw=None,policy=POLICY,artifact=ARTIFACT):
    env=control if envelope is None else envelope
    authority=bound(env) if anchor is None else anchor
    result=m.evaluate(m.canonical(env) if raw is None else raw,policy,artifact,authority)
    assert result.internal_reason==expected,(name,expected,result)
    assert result.label==('REFUSE' if expected else 'SYNTHETIC_ALREADY_BOUND'),name
    assert m.production_projection(result)==m.PUBLIC_REFUSAL,name
    results.append(dict(id=name,label=result.label,internalReason=result.internal_reason,
        productionProjection=m.PUBLIC_REFUSAL,cryptographicOrRuntimeAuthentication=False))

def changed(path,value):
    env=copy.deepcopy(control);target=env
    for k in path[:-1]:target=target[k]
    target[path[-1]]=value
    return env

run('C01-synthetic-already-bound-control','')
run('C02-idempotent-same-ticket-read','')
run('C03-exact-upper-key-status-bound-control','',anchor=bound(lower=1098,upper=1099,checked=1090,key_after=1100))
run('N01-missing-anchor','ANCHOR',anchor=False)
run('N02-wrong-anchor-purpose','ANCHOR',anchor=bound(purpose='node-leaf'))
for name,path,value,reason in [
 ('N03-provider-self-key',['signer','keySPKISHA256'],'a9'*32,'SIGNATURE'),
 ('N04-plan-purpose',['body','purpose'],'root-plan','FORMAT'),
 ('N05-foreign-scope',['body','scopeSHA256'],'a8'*32,'SCOPE'),
 ('N06-foreign-selector',['body','selector'],'other_scope','SCOPE'),
 ('N07-anchor-version',['body','anchorVersion'],2,'SCOPE'),
 ('N08-record-rollback',['body','recordVersion'],6,'VERSION'),
 ('N09-future-unpublished-version',['body','recordVersion'],8,'VERSION'),
 ('N10-replayed-ticket',['body','requestBindingSHA256'],'a7'*32,'REPLAY'),
 ('N11-future-issued',['body','issuedAt'],1002,'TIME'),
 ('N12-expired-record',['body','validUntil'],1001,'TIME'),
 ('N13-stale-backdated-issue',['body','issuedAt'],800,'TIME'),
 ('N14-wrong-format',['body','format'],'normalized-proof-v1','FORMAT'),
 ('N15-required-skip',['body','ciRuns',0,'jobs',0,'steps',1,'conclusion'],'skipped','CI'),
]:
    env=changed(path,value)
    a=bound(env)
    if name=='N15-required-skip':a=replace(a,ci=m.canonical(env['body']['ciRuns']))
    run(name,reason,envelope=env,anchor=a)
env=changed(['body','facts','reviewScope'],'attacker-scope')
run('N16-tampered-projection-no-resign','SIGNATURE',envelope=env,anchor=replace(bound(),current_digest=m.sha(m.canonical(env))))
for index,(field,value) in enumerate([
 ('sourceSHA','a0'*20),('reviewSHA','a0'*20),('reviewTargetSHA','a0'*20),
 ('reviewScope','another-narrow-scope'),('reviewVerdict','UNSCOPED_GREEN'),
 ('reviewCoverageSHA256','a0'*32),('rootChoiceSHA256','a0'*32),
 ('sourceEquivalenceSHA256','a0'*32),('graphSHA256','a0'*32),
 ('contractSetSHA256','a0'*32),('semanticPinsSHA256','a0'*32),
 ('artifactId',304),('artifactZipSHA256','a0'*32),('artifactZipBytes',999),
 ('binaryVCSRevision','a0'*20),('binaryVCSModified',True),
 ('toolchain','another-toolchain'),('moduleClosureSHA256','a0'*32),
 ('helperClosureSHA256','a0'*32),('runtimeLockSHA256','a0'*32),
 ('linkedClosureSHA256','a0'*32),('installationReceiptSHA256','a0'*32),
 ('runningMeasurementSHA256','a0'*32),('sourcePublicationAnchorSHA256','a0'*32),
 ('sourceAcquisitionSHA256','a0'*32),
],17):
    run(f'N{index:02d}-independently-mismatched-{field}','PROVENANCE',envelope=changed(['body','facts',field],value))
for i,field,value in [(42,'correlation','other-run'),(43,'ref','other-ref'),(44,'event','pull_request'),(45,'attempt',2),(46,'workflow','.github/workflows/core-other.yml'),(47,'headSHA','a0'*20)]:
    run(f'N{i}-ci-{field}','CI',envelope=changed(['body','ciRuns',0,field],value))
env=changed(['body','ciRuns',0,'jobs',0,'steps'],[ci[0]['jobs'][0]['steps'][0],ci[0]['jobs'][0]['steps'][2]])
run('N48-authenticated-CI-omits-required-step','CI',envelope=env,anchor=bound(env,ci=m.canonical(env['body']['ciRuns'])))
env=changed(['body','ciRuns'],[ci[0]])
run('N49-authenticated-CI-omits-required-docs-job','CI',envelope=env,anchor=bound(env,ci=m.canonical(env['body']['ciRuns'])))
env=changed(['body','ciRuns',0,'jobs',0,'steps',2,'conclusion'],'failure')
run('N50-optional-failure-not-a-skip','CI',envelope=env,anchor=bound(env,ci=m.canonical(env['body']['ciRuns'])))
run('N51-wrong-artifact-bytes','ARTIFACT',artifact=ARTIFACT+b'tamper')
run('N52-wrong-sealed-policy-bytes','ARTIFACT',policy=POLICY+b'tamper')
for i,field in enumerate(['installationSourceSHA','installationBinarySHA256','runningBinarySHA256','runningReceiptSHA256','runningRuntimeLockSHA256','runningLinkedClosureSHA256','runningSourceSHA'],53):
    env=changed(['body','facts',field],'ab'*(20 if field.endswith('SourceSHA') else 32))
    # Independently authenticated but internally inconsistent: equal strings do not excuse it.
    run(f'N{i}-authentic-inconsistent-{field}','INSTALLATION',envelope=env,anchor=bound(env,facts=m.canonical(env['body']['facts'])))
for name,changes,reason in [
 ('N60-revoked',dict(status='REVOKED'),'STATUS'),
 ('N61-unknown-status',dict(status='UNKNOWN'),'STATUS'),
 ('N62-stale-status',dict(checked=800),'TIME'),
 ('N63-expired-status',dict(status_expires=1001),'TIME'),
 ('N64-wide-clock',dict(upper=1002),'TIME'),
 ('N65-inverted-clock',dict(lower=1002),'TIME'),
 ('N66-original-key-not-yet-authorized',dict(key_before=991),'TIME'),
 ('N67-original-key-expired',dict(key_after=990),'TIME'),
 ('N68-independent-floor-ahead',dict(minimum_version=8),'VERSION'),
 ('N69-independent-current-digest-changed',dict(current_digest='ae'*32),'VERSION'),
 ('N70-final-readback-changed',dict(v1=b'changed'),'READBACK'),
 ('N71-final-readback-unknown',dict(v1=b''),'READBACK'),
 ('N72-mutable-bound-step-policy',dict(required_steps=list(required)),'OWNERSHIP'),
]:run(name,reason,anchor=bound(**changes))
run('N73-mutable-untrusted-policy','OWNERSHIP',policy=bytearray(POLICY))
run('N74-mutable-untrusted-envelope','OWNERSHIP',raw=bytearray(m.canonical(control)))
raw=m.canonical(control)
for name,data in [
 ('N75-duplicate-key',raw.replace(b'"body":',b'"body":{},"body":',1)),
 ('N76-trailing-data',raw+b'{}'),('N77-BOM',b'\xef\xbb\xbf'+raw),
 ('N78-whitespace-alias',b' '+raw),('N79-float-version',raw.replace(b'"recordVersion":7',b'"recordVersion":7.0')),
 ('N80-invalid-UTF8',b'\xff'+raw),('N81-envelope-size',b' '*(m.MAX_ENVELOPE+1)),
 ('N82-deep-tree',b'['*40+b'0'+b']'*40),
]:run(name,'FORMAT',raw=data)
run('N83-boolean-version','FORMAT',envelope=changed(['body','recordVersion'],True))
env=copy.deepcopy(control);env['trustedKey']='attacker'
run('N84-payload-trust-key-injection','FORMAT',envelope=env)
env=changed(['body','ciRuns',0,'jobs',0,'steps',2,'number'],2)
run('N85-duplicate-step-number','FORMAT',envelope=env)
env=changed(['body','ciRuns',0,'jobs',0,'steps',2,'name'],'unexpected-extra-step')
run('N86-authenticated-unknown-step-policy','CI',envelope=env,anchor=bound(env,ci=m.canonical(env['body']['ciRuns'])))
run('N87-current-registry-key-expired-after-issue','TIME',anchor=bound(key_after=1001))
run('N88-clock-numeric-type-mismatch','TIME',anchor=bound(lower=1000.0))
run('N89-self-current-publication-without-independent-anchor','ANCHOR',anchor=False)
run('N90-negative-zero-alias','FORMAT',raw=raw.replace(b'"anchorVersion":1',b'"anchorVersion":-0'))
run('N91-NaN','FORMAT',raw=raw.replace(b'"recordVersion":7',b'"recordVersion":NaN'))
run('N92-response-before-ticket-issue','TIME',anchor=bound(ticket_issued=991))
run('N93-ticket-expired','TIME',anchor=bound(ticket_expires=1001))
env=changed(['body','facts','cohortScopeSHA256'],'a0'*32)
run('N94-authentic-scope-join-inconsistent','PROVENANCE',envelope=env,anchor=bound(env,facts=m.canonical(env['body']['facts'])))
run('N95-foreign-capsule-digest','SCOPE',envelope=changed(['body','capsuleSHA256'],'a0'*32))
run('N96-replayed-installation-generation','SCOPE',envelope=changed(['body','provisioningGeneration'],'synthetic-install-0'))
env=changed(['body','requestBindingSHA256'],'a6'*32)
env['body']['issuedAt']=1000
assert m.record_identity(env)==m.record_identity(control)
assert m.sha(m.canonical(env))!=m.sha(m.canonical(control))
run('C04-new-ticket-same-stable-record','',envelope=env,anchor=bound(env,request_binding='a6'*32,ticket_issued=995,current_digest=m.record_identity(control)))

# Independent schema/type/closed-field checks; these are not signature tests.
schema=json.loads((HERE/'candidate-envelope.schema.json').read_text())
jsonschema.Draft202012Validator.check_schema(schema)
validator=jsonschema.Draft202012Validator(schema)
assert not list(validator.iter_errors(control))
assert set(schema['properties']['body']['properties']['facts']['properties'])==m.FACT_KEYS
for env in [changed(['body','recordVersion'],True),changed(['body','purpose'],'node-leaf'),changed(['body','facts','artifactId'],False)]:
    assert list(validator.iter_errors(env))
payload_schema=json.loads((HERE/'policy-payload.schema.json').read_text())
jsonschema.Draft202012Validator.check_schema(payload_schema)
assert 'RegistrySHA256' not in payload_schema['properties'] and 'status' not in payload_schema['properties']
assert len(payload_schema['properties']['contractPins']['properties'])==28
payload=dict(selector=control['body']['selector'],version='synthetic-policy-v7',
    verifier=dict(id='saintvision-migrationverify-k1:1',sourceSHA=facts['sourceSHA'],artifactSHA256=facts['binarySHA256'],reviewSHA=facts['reviewSHA'],ciRunIDs=[101,102]),
    contractPins={i:{k:v['const'] for k,v in rule['properties'].items()} for i,rule in payload_schema['properties']['contractPins']['properties'].items()},
    grants=[dict(role='node-leaf',authorityScopeC2Hex=m.canonical(dict(class_='SYNTHETIC')).hex(),publicKeyHex='a1'*32,notBefore=900,notAfter=1200)],
    cohortId='synthetic-legacy-two',members=[dict(slot=slot,scope=dict(tenantId='synthetic-tenant',nodeId='synthetic-'+slot,recoveryEpoch='synthetic-epoch'),certificateDERHex=('a1' if slot=='PC2' else 'a2')*64,caRootDERHex='a3'*64) for slot in ['PC2','PC4']],
    graphHex=b'SYNTHETIC_GRAPH_BYTES'.hex(),nodeKinds={'synthetic-kind':'SYNTHETIC'})
pv=jsonschema.Draft202012Validator(payload_schema)
assert not list(pv.iter_errors(payload))
payload_mutants=[]
for key,val in [('RegistrySHA256','a1'*32),('status','ACTIVE')]:
    v=copy.deepcopy(payload);v[key]=val;payload_mutants.append(v)
v=copy.deepcopy(payload);v['members'].reverse();payload_mutants.append(v)
v=copy.deepcopy(payload);v['contractPins']['saintvision-proof-node-floor-v2:1']['codec']='normalized-proof-v1';payload_mutants.append(v)
v=copy.deepcopy(payload);v['verifier']['ciRunIDs']=[101,101];payload_mutants.append(v)
assert all(list(pv.iter_errors(v)) for v in payload_mutants)
fixture=dict(classification='SYNTHETIC_ALREADY_BOUND_NO_CRYPTO_OR_PRODUCER_RUNTIME_ACCEPTANCE',envelope=control,
    policyBytesHex=POLICY.hex(),artifactBytesHex=ARTIFACT.hex(),authorityOrigin='In-memory static fixture ONLY; no key generation or signature verification',realAuthorities='NULL_HOLD')
(HERE/'synthetic-control.json').write_bytes((json.dumps(fixture,indent=2)+'\n').encode())
(HERE/'synthetic-policy-shape.json').write_bytes((json.dumps(dict(classification='SYNTHETIC_SCHEMA_SHAPE_ONLY_INVALID_DER_NO_CRYPTO_PROOF',payload=payload),indent=2)+'\n').encode())
report=dict(classification='EXECUTED_SYMBOLIC_CANDIDATE_CONTRACT_TESTS_ONLY',
    cases=len(results),syntheticControls=sum(x['label']=='SYNTHETIC_ALREADY_BOUND' for x in results),
    negativeRefusals=sum(x['label']=='REFUSE' for x in results),failures=0,results=results,
    schemaValidation='2 candidate schemas valid; envelope and policy shape controls pass; 3 envelope and 5 policy schema mutants refused; no DER/crypto/graph validation claimed',
    signatureMechanism='SYMBOLIC_ALREADY_BOUND_TABLE_NO_ED25519_AUTHENTICATION',
    productionProjectionAlwaysRefuses=True,actualRuntime40='NOT_RUN',realBindings='NULL_HOLD',
    completedKST=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat())
(HERE/'candidate-test-results.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
print(json.dumps({k:v for k,v in report.items() if k!='results'}))
