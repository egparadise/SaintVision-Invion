"""Targeted Rev2 contract delta: distinct complete input tuples, symbolic only."""
from dataclasses import fields,replace
from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,sys,traceback

import jsonschema

HERE=Path(__file__).parent
for name,file in [('p02_rev2_schema','schema_defs.py'),('p02_rev2_model','candidate_model.py'),('p02_rev2_fixtures','fixture_data.py')]:
    spec=importlib.util.spec_from_file_location(name,HERE/file)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
m=sys.modules['p02_rev2_model'];fx=sys.modules['p02_rev2_fixtures'];sd=sys.modules['p02_rev2_schema']
OUT=HERE/'test-runs';OUT.mkdir(exist_ok=True)
ATTEMPT=1
while (OUT/f'attempt-{ATTEMPT:02d}.json').exists():ATTEMPT+=1
rows=[];schema_rows=[];seen={};started=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()

def primitive(v):
    if type(v) is m.BoundInputs:return {'type':'BoundInputs','fields':{f.name:primitive(getattr(v,f.name)) for f in fields(v)}}
    if isinstance(v,(bytes,bytearray)):return {'type':type(v).__name__,'hex':bytes(v).hex()}
    if type(v) is frozenset:return {'type':'frozenset','items':sorted([primitive(x) for x in v],key=lambda x:json.dumps(x,sort_keys=True))}
    if type(v) is tuple:return {'type':'tuple','items':[primitive(x) for x in v]}
    if v is None or type(v) in (bool,int,str):return v
    return {'type':type(v).__name__}

def fingerprint(inp):return m.sha(m.canonical(primitive(inp)))

def preconditions(inp):
    raw,p,artifact,a=inp;out={}
    try:
        e=m.strict_json(raw)
        out['newEnvelopeSchema']=not list(jsonschema.Draft202012Validator(sd.schema('envelope')).iter_errors(e))
        out['newFormat']=e['body']['format']==m.FORMAT
        out['alreadyBoundPayloadDigest']=m.sha(p)==e['body']['facts']['policyPayloadSHA256']
        if type(a) is m.BoundInputs:
            cap=m.strict_json(a.capsule,65536)
            out['alreadyBoundSignatureTuple']=(m.sha(m.projection(e)),e['signatureHex'],cap['keySPKI']) in a.signatures
    except (ValueError,TypeError,KeyError,UnicodeError):pass
    return out

def persist(error=None):
    report=dict(classification='REV2_SYMBOLIC_CONTRACT_DELTA_ONLY_NO_PRODUCER_CRYPTO_OR_RUNTIME_PROOF',
        attempt=ATTEMPT,startedKST=started,completedKST=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),
        executedRows=len(rows),distinctCompleteInputTuples=len(seen),duplicateRows=len(rows)-len(seen),
        symbolicControls=sum(r['observedLabel']=='SYNTHETIC_ALREADY_BOUND' for r in rows),
        refusals=sum(r['observedLabel']=='REFUSE' for r in rows),failures=int(error is not None),
        error=error,rows=rows,schemaChecks=schema_rows,sourceHashes={p.name:m.sha(p.read_bytes()) for p in [HERE/'candidate_model.py',HERE/'schema_defs.py',HERE/'fixture_data.py',HERE/'test_contract.py']},
        originalOwnerEvidence='100 rows/98 distinct unchanged in78468',originalReviewer='38 immutable de4 rows copied, not rerun',
        actualProducer=None,actualCryptographicAuthentication=False,productionProjectionAlwaysRefuses=True,
        actualA01A40='NOT_RUN',actualBindings='NULL_HOLD')
    (OUT/f'attempt-{ATTEMPT:02d}.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    if error is None:(HERE/'test-results.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    return report

def check(name,inp,reason='',stage='',*,already_bound=True,detail=None,purpose=''):
    fp=fingerprint(inp)
    assert fp not in seen,(name,'duplicate complete input tuple',seen.get(fp))
    pre=preconditions(inp)
    if already_bound:
        assert all(pre.get(k) for k in ('newEnvelopeSchema','newFormat','alreadyBoundPayloadDigest','alreadyBoundSignatureTuple')),(name,'not rebased to a valid already-bound envelope',pre)
    result=m.evaluate(*inp)
    expected_prefix=[s for s,_ in m.STAGES]
    prefix=expected_prefix if not stage else expected_prefix[:expected_prefix.index(stage)]
    row=dict(id=name,inputSHA256=fp,purpose=purpose,expectedReason=reason,expectedStage=stage,
        observedLabel=result.label,observedReason=result.reason,observedStage=result.failed_stage,
        observedDetail=result.detail,passedStages=list(result.passed_stages),expectedEarlierStages=prefix,
        earlierStagesExactlyPass=list(result.passed_stages)==prefix,preconditions=pre,
        productionProjection=m.production_projection(result))
    rows.append(row);seen[fp]=name
    assert result.reason==reason and result.failed_stage==stage,(name,reason,stage,result)
    assert list(result.passed_stages)==prefix,(name,'wrong first failed gate',result)
    if detail is not None:assert result.detail==detail,(name,detail,result)
    assert m.production_projection(result)==m.PUBLIC_REFUSAL
    return result

def base():
    e,p,z,a=fx.fixture();return e,p,z,a

def mutate_policy(name,fn,reason='PROVENANCE',stage='05_PAYLOAD_JOINS',**options):
    e,p,z,a=base();fn(p)
    inp=fx.seal(e,p,z,a,bind_payload=True,**options)
    return check(name,inp,reason,stage,purpose='M1 new valid envelope and explicitly already-bound payload digest')

def semantic_variant(e,p,z,a):
    e['body']['facts'].update(m.components(p))
    return fx.seal(e,p,z,a,bind_payload=True,source_fields=tuple(m.components(p)),new_head=True,new_request=True,bind_grant_status=True,bind_member_status=True)

try:
    # Meaningful controls, never duplicate calls relabelled as new cases.
    e,p,z,a=base();control=(m.canonical(e),m.canonical(p),z,a)
    r=check('C01-inherited-reviews-and-complete-projection',control,purpose='L1 multiple raw targets plus independent effective source approval; M1 all field projections')
    projected=json.loads(r.projection_bytes)
    assert projected['Verifier']['CIRunIDs']==['101','102']
    assert projected['Provenance']['CIRunID']=='102' and projected['Provenance']['CIJobID']=='202'
    assert projected['Provenance']['CIAttempt']=='2' and projected['Provenance']['CIRef']=='synthetic/docs-ref'
    assert projected['Provenance']['ArtifactDigest']==m.sha(z) and projected['Verifier']['ArtifactSHA256']!=m.sha(z)
    assert projected['Provenance']['ReviewTargetSHA']==fx.SOURCE
    assert projected['Verifier']['ReviewSHA']==fx.EFFECTIVE['publicationSHA'] not in [x['reviewSHA'] for x in e['body']['reviews']]
    assert projected['Grants'][0]['NotAfter']=='1970-01-01T00:15:50Z'  # original interval already ended; current registration independent
    assert all(g['Status']=='ACTIVE' for g in projected['Grants'])
    assert set(projected)=={'Selector','Version','RegistrySHA256','Verifier','ContractPins','Grants','CohortID','Members','GraphBytes','GraphSHA256','NodeKinds','Provenance'}
    assert set(projected['Verifier'])=={'ID','SourceSHA','ArtifactSHA256','ReviewSHA','CIRunIDs'}
    assert set(projected['Provenance'])=={'ReviewTargetSHA','ReviewScope','ApprovedReviewScope','BinaryVCS','RuntimeLockSHA256','CIHeadSHA','CIRef','CIWorkflow','CIRunID','CIAttempt','CIJobID','ArtifactDigest','InstallationReceiptSHA256','RunningExecutableSHA256','LinkedClosureSHA256'}
    assert set(projected['Grants'][0])=={'Role','AuthorityScope','PublicKeyHex','NotBefore','NotAfter','Status'}
    assert set(projected['Members'][0])=={'Slot','Scope','CertificateDER','CARootDER'}
    assert set(next(iter(projected['ContractPins'].values())))=={'ContractSHA256','SchemaSHA256','Codec','RequiredVerifier'}
    h5=m.strict_json(a.h5)
    assert projected['Provenance']['RunningExecutableSHA256']==h5['executableSHA256']
    assert projected['Provenance']['RuntimeLockSHA256']==h5['runtimeLockSHA256']
    assert projected['Provenance']['LinkedClosureSHA256']==h5['linkedClosureSHA256']
    e,p,z,a=base();original_identity=m.record_identity(e)
    h=m.strict_json(a.h5);h.update(proofNonce='synthetic-H5-2',observedAt=999,expiresAt=1090)
    t=m.strict_json(a.ticket);t.update(id='synthetic-ticket-2',issuedAt=997,expiresAt=1090)
    a=replace(a,h5=m.canonical(h),ticket=m.canonical(t),v0=b'fresh-readback-2',v1=b'fresh-readback-2')
    e['body'].update(issuedAt=999,validUntil=1050)
    inp=fx.seal(e,p,z,a,new_request=True)
    assert m.record_identity(json.loads(inp[0]))==original_identity and inp[0]!=control[0]
    check('C02-fresh-ticket-new-expiry-new-H5-same-record',inp,purpose='L4/L5 genuinely distinct legal repeat; zero-weight echo changes, stable record unchanged')
    e,p,z,a=base();cap=m.strict_json(a.capsule);cap['primaryCI']=dict(runId=101,jobId=201,jobName='core')
    a=replace(a,capsule=m.canonical(cap));e['body']['capsuleSHA256']=m.sha(a.capsule)
    result=check('C03-different-independently-provisioned-primary',fx.seal(e,p,z,a,new_head=True,new_request=True),purpose='M1 primary tuple comes from capsule, never first/last green response')
    assert json.loads(result.projection_bytes)['Provenance']['CIRunID']=='101'
    e,p,z,a=base();p['version']='8';e['body']['recordVersion']=8
    p['grants'][2].update(notBefore=0,notAfter=m.MAX_EPOCH)
    result=check('C04-Go-UTC-epoch-boundaries',semantic_variant(e,p,z,a),purpose='M1 exact integer->UTC conversion, no physical clock use')
    assert json.loads(result.projection_bytes)['Grants'][2]['NotBefore']=='1970-01-01T00:00:00Z'
    assert json.loads(result.projection_bytes)['Grants'][2]['NotAfter']=='9999-12-31T23:59:59Z'

    # M1(a): every malformed payload has a NEW valid canonical envelope and bound digest/signature.
    for name,make in [('P01-leading-space',lambda p:b' '+m.canonical(p)),('P02-non-JSON',lambda p:b'not JSON'),
                      ('P03-trailing-LF',lambda p:m.canonical(p)+b'\n'),('P04-trailing-CRLF',lambda p:m.canonical(p)+b'\r\n'),
                      ('P05-duplicate-key',lambda p:m.canonical(p).replace(b'"selector":',b'"selector":"x","selector":',1))]:
        e,p,z,a=base();check(name,fx.seal(e,make(p),z,a,bind_payload=True),'FORMAT','03_PAYLOAD')
    for field,value in [('status','ACTIVE'),('RegistrySHA256','ab'*32),('Provenance',{'ApprovedReviewScope':'self'})]:
        mutate_policy('P06-self-asserted-'+field,lambda p,k=field,v=value:p.update({k:v}),'FORMAT','03_PAYLOAD')
    mutate_policy('P07-self-asserted-grant-status',lambda p:p['grants'][0].update(status='ACTIVE'),'FORMAT','03_PAYLOAD')
    mutate_policy('P08-missing-semantic-component',lambda p:p.pop('semanticPins'),'FORMAT','03_PAYLOAD')
    mutate_policy('P09-missing-proof-slot-component',lambda p:p.pop('proofSlotRegistryHex'),'FORMAT','03_PAYLOAD')
    mutate_policy('P10-missing-registration-component',lambda p:p.pop('designRegistrationHex'),'FORMAT','03_PAYLOAD')
    mutate_policy('P11-non-JSON-C2-scope',lambda p:p['grants'][2].update(authorityScopeC2Hex=b'not JSON'.hex()),'FORMAT','03_C2')
    mutate_policy('P12-wrong-C2-HTML-escaping',lambda p:p['grants'][2].update(authorityScopeC2Hex=m.canonical(dict(**{'class':'COMPONENT'},component='synthetic&helper')).hex()),'FORMAT','03_C2')
    mutate_policy('P13-unknown-scope-class',lambda p:p['grants'][2].update(authorityScopeC2Hex=m.c2(dict(**{'class':'SELF_TRUST'},scope='x')).hex()),'FORMAT','03_C2')

    # M1(b): isolate each payload-envelope binding behind the same valid outer preconditions.
    mutate_policy('J01-selector',lambda p:p.update(selector='other_selector'))
    mutate_policy('J02-source',lambda p:p['verifier'].update(sourceSHA='ac'*20))
    mutate_policy('J03-executable-not-archive',lambda p:p['verifier'].update(artifactSHA256=m.sha(fx.ARTIFACT)))
    mutate_policy('J04-effective-review-publication',lambda p:p['verifier'].update(reviewSHA=fx.REVIEWS[0]['reviewSHA']))
    mutate_policy('J05-CI-run-membership',lambda p:p['verifier'].update(ciRunIDs=[777]))
    mutate_policy('J06-CI-run-order',lambda p:p['verifier'].update(ciRunIDs=[102,101]))
    mutate_policy('J07-version-mapping',lambda p:p.update(version='8'))
    mutate_policy('J08-noncanonical-version-string',lambda p:p.update(version='07'),'FORMAT','03_PAYLOAD')
    mutate_policy('J09-boolean-CI-ID',lambda p:p['verifier'].update(ciRunIDs=[True,102]),'FORMAT','03_PAYLOAD')

    # M1(c): externally bound coarse claims cannot substitute for derivation or source components.
    for field in ['graphSHA256','contractSetSHA256','semanticPinsSHA256','cohortScopeSHA256','keyGrantsSHA256','registryProofSlotsSHA256','designRegistrationSHA256']:
        e,p,z,a=base();e['body']['facts'][field]='ad'*32
        check('D01-derived-'+field,fx.seal(e,p,z,a,source_fields=(field,),new_head=True,new_request=True),'PROVENANCE','05_COMPONENTS')
    mutate_policy('D02-nodeKinds-source',lambda p:p['nodeKinds'].update({'synthetic-kind':'OTHER'}),stage='05_COMPONENTS')
    for field in ['k1SourcePinSetSHA256','recipeDefinitionsSHA256','derivedDigestContractSHA256']:
        e,p,z,a=base();p['semanticPins'][field]='ae'*32
        check('D03-semantic-origin-'+field,semantic_variant(e,p,z,a),'PROVENANCE','05_COMPONENTS')
    for name,field,newbytes in [('D04-graph-raw-bytes','graphHex',b' {"syntheticGraph":true}\n'),
                               ('D05-proof-slot-raw-bytes','proofSlotRegistryHex',b'{"otherSlots":77}'),
                               ('D06-registration-no-newline-normalization','designRegistrationHex',fx.REGISTRATION.replace(b'\r\n',b'\n'))]:
        e,p,z,a=base();p[field]=newbytes.hex()
        if field=='graphHex':p['semanticPins']['graphSHA256']=m.sha(newbytes)
        check(name,semantic_variant(e,p,z,a),'PROVENANCE','05_COMPONENTS')
    e,p,z,a=base();cap=m.strict_json(a.capsule);cap['sourceConstants'].pop('recipeDefinitionsSHA256')
    a=replace(a,capsule=m.canonical(cap));e['body']['capsuleSHA256']=m.sha(a.capsule)
    check('D07-missing-independent-safety-source',fx.seal(e,p,z,a,new_head=True,new_request=True),'PROVENANCE','05_COMPONENTS')

    # L1: ordered original reviews and the effective approval are different authorities.
    e,p,z,a=base();check('R01-missing-effective-producer',(m.canonical(e),m.canonical(p),z,replace(a,coverage=None)),'PROVENANCE','02_SOURCES')
    e,p,z,a=base();e['body']['reviews'][0]['targetSHA']='af'*20
    check('R02-original-review-target-substitution',fx.seal(e,p,z,a),'PROVENANCE','05_REVIEWS')
    e,p,z,a=base();e['body']['reviews'][0]['verdict']='SELF_GREEN'
    check('R03-original-review-verdict-substitution',fx.seal(e,p,z,a),'PROVENANCE','05_REVIEWS')
    e,p,z,a=base();e['body']['reviews'][0]['scopeId']='other-scope'
    check('R04-original-review-scope-substitution',fx.seal(e,p,z,a),'PROVENANCE','05_REVIEWS')
    e,p,z,a=base();e['body']['reviews'].reverse()
    check('R05-review-order',fx.seal(e,p,z,a),'FORMAT','03_ENVELOPE',already_bound=False)
    for name,change in [
        ('R06-missing-source-part',lambda s:s['parts'].pop()),
        ('R07-fake-reviewed-byte-equivalence',lambda s:s['parts'][0].update(reviewedBlobSHA256='bc'*32)),
        ('R08-changed-current-part-bytes',lambda s:s['parts'][0].update(currentBlobSHA256='bd'*32)),
        ('R09-inherited-labelled-direct',lambda s:s['parts'][0].update(relation='DIRECT')),
        ('R10-relabelled-original-target',lambda s:s['parts'][0].update(reviewTargetSHA=fx.SOURCE)),
        ('R11-effective-target-not-current',lambda s:s['effective'].update(targetSourceSHA='be'*20)),
    ]:
        e,p,z,a=base();cov=m.strict_json(a.coverage);change(cov['statement']);a=replace(a,coverage=m.canonical(cov))
        check(name,fx.seal(e,p,z,a,bind_coverage=True,source_fields=(),new_head=True,new_request=True),'PROVENANCE','05_REVIEWS')

    # M1(d): the projected approved scope/primary selector originate outside the response.
    for name,cap_change,reason in [
        ('Q01-approved-scope-not-copied-from-facts',lambda cap:cap.update(approvedReviewScope='independently-different-scope'),'PROVENANCE'),
        ('Q02-primary-run-not-first-green',lambda cap:cap['primaryCI'].update(runId=999),'CI'),
        ('Q03-primary-job-not-first-green',lambda cap:cap['primaryCI'].update(jobId=999),'CI'),
        ('Q04-primary-job-name',lambda cap:cap['primaryCI'].update(jobName='core'),'CI'),
        ('Q05-primary-ID-boolean',lambda cap:cap['primaryCI'].update(runId=True),'CI'),
    ]:
        e,p,z,a=base();cap=m.strict_json(a.capsule);cap_change(cap);a=replace(a,capsule=m.canonical(cap));e['body']['capsuleSHA256']=m.sha(a.capsule)
        check(name,fx.seal(e,p,z,a,new_head=True,new_request=True),reason,'07_PROJECTION')
    for name,value in [('Q06-epoch-below-zero',-1),('Q07-epoch-above-Go-JSON-bound',m.MAX_EPOCH+1),('Q08-epoch-bool',True)]:
        mutate_policy(name,lambda p,v=value:p['grants'][0].update(notBefore=v),'FORMAT','03_PAYLOAD')
    e,p,z,a=base();p['grants'][2].update(notBefore=1500,notAfter=800)
    check('Q09-inverted-original-grant-interval',semantic_variant(e,p,z,a),'PROVENANCE','07_PROJECTION')
    e,p,z,a=base();life=m.strict_json(a.lifecycle);life['grants'].pop(next(iter(life['grants'])));a=replace(a,lifecycle=m.canonical(life))
    check('Q10-grant-ACTIVE-not-from-payload',(m.canonical(e),m.canonical(p),z,a),'STATUS','06_STATUS')
    e,p,z,a=base();p['members'][1]['certificateDERHex']=p['members'][0]['certificateDERHex']
    check('Q11-duplicate-public-DER',semantic_variant(e,p,z,a),'PROVENANCE','07_PROJECTION')

    # L2: single normative first-failed order, with real double faults.
    e,p,z,a=base();e['body']['facts']['toolchain']='wrong-toolchain';life=m.strict_json(a.lifecycle);life['checkedAt']=800
    a=replace(a,lifecycle=m.canonical(life))
    check('O01-toolchain-before-status-time',fx.seal(e,p,z,a),'PROVENANCE','05_SOURCE')
    e,p,z,a=base();e['body']['facts']['toolchain']='wrong-toolchain';e['body']['issuedAt']=800
    check('O02-key-interval-before-toolchain',fx.seal(e,p,z,a),'TIME','04_KEY_INTERVAL')
    e,p,z,a=base();p['selector']='other_selector';life=m.strict_json(a.lifecycle);life['status']='REVOKED';a=replace(a,lifecycle=m.canonical(life))
    check('O03-payload-join-before-status',fx.seal(e,p,z,a,bind_payload=True),'PROVENANCE','05_PAYLOAD_JOINS')
    e,p,z,a=base();e['body']['ciRuns'][0]['jobs'][0]['steps'][1]['conclusion']='skipped';life=m.strict_json(a.lifecycle);life['floor']=8
    a=replace(a,lifecycle=m.canonical(life))
    check('O04-CI-before-floor',fx.seal(e,p,z,a,bind_ci=True),'CI','05_CI')

    # L4/L5: correct registry signature/echo never supplies missing or foreign H5/current authority.
    e,p,z,a=base();check('H01-registry-signed-current-without-independent-current',(m.canonical(e),m.canonical(p),z,replace(a,lifecycle=None)),'STATUS','02_SOURCES')
    e,p,z,a=base();check('H02-correct-signed-echo-without-H5',(m.canonical(e),m.canonical(p),z,replace(a,h5=None)),'INSTALLATION','02_SOURCES')
    for name,updates,reason,stage in [
        ('H03-correct-echo-foreign-component',{'componentSHA256':'bf'*32},'INSTALLATION','05_RUNNING'),
        ('H04-correct-echo-wrong-purpose',{'purpose':'node-floor-v2'},'INSTALLATION','05_RUNNING'),
        ('H05-correct-echo-stale-H5',{'observedAt':800},'TIME','06_TIME'),
        ('H06-correct-echo-wrong-receipt',{'receiptSHA256':'c0'*32},'INSTALLATION','05_RUNNING'),
        ('H09-correct-echo-wrong-executable',{'executableSHA256':'c3'*32},'INSTALLATION','05_RUNNING'),
        ('H10-correct-echo-wrong-runtime-lock',{'runtimeLockSHA256':'c4'*32},'INSTALLATION','05_RUNNING'),
        ('H11-correct-echo-wrong-linked-closure',{'linkedClosureSHA256':'c5'*32},'INSTALLATION','05_RUNNING'),
        ('H12-correct-echo-missing-process-generation',{'startGeneration':''},'INSTALLATION','05_RUNNING'),
    ]:
        e,p,z,a=base();h=m.strict_json(a.h5);h.update(updates);a=replace(a,h5=m.canonical(h))
        check(name,fx.seal(e,p,z,a,new_request=True),reason,stage)
    e,p,z,a=base();e['body']['facts'][m.ECHO]='c1'*32
    check('H07-registry-signs-wrong-echo',fx.seal(e,p,z,a),'REPLAY','06_REPLAY')
    e,p,z,a=base();forged=m.request_projection(a);forged['h5EvidenceSHA256']='c1'*32
    e['body']['facts'][m.ECHO]='c1'*32;e['body']['requestBindingSHA256']=m.sha(m.c2(forged))
    check('H08-registry-cannot-choose-client-request',fx.seal(e,p,z,a),'REPLAY','06_REPLAY')

    # Preserve changed-format envelope/current protections without rerunning the original suite.
    e,p,z,a=base();check('B01-missing-independent-capsule',(m.canonical(e),m.canonical(p),z,None),'ANCHOR','01_ANCHOR',already_bound=False)
    e,p,z,a=base();life=m.strict_json(a.lifecycle);life['floor']=8;a=replace(a,lifecycle=m.canonical(life))
    check('B02-protected-floor',(m.canonical(e),m.canonical(p),z,a),'VERSION','06_VERSION')
    e,p,z,a=base();a=replace(a,v1=b'changed-current-readback')
    check('B03-final-readback',(m.canonical(e),m.canonical(p),z,a),'READBACK','06_READBACK')
    e,p,z,a=base();e['body']['requestBindingSHA256']='c2'*32
    check('B04-response-replay-new-client-request',fx.seal(e,p,z,a),'REPLAY','06_REPLAY')
    e,p,z,a=base();a=replace(a,clock=m.canonical(dict(lower=1000,upper=1002)))
    check('B05-clock-interval',(m.canonical(e),m.canonical(p),z,a),'TIME','06_TIME')
    e,p,z,a=base();check('B06-artifact-byte-mismatch',(m.canonical(e),m.canonical(p),z+b'changed',a),'ARTIFACT','05_ARTIFACT')

    # L3 actual schema + canonical codec: trailing LF/CRLF, not `$` search assumptions.
    for suffix,label in [('\n','LF'),('\r\n','CRLF')]:
        for name,path in [('selector',['body','selector']),('hash',['body','scopeSHA256'])]:
            e,p,z,a=base();target=e
            for k in path[:-1]:target=target[k]
            target[path[-1]]+=suffix
            valid=not list(jsonschema.Draft202012Validator(sd.schema('envelope')).iter_errors(e))
            assert not valid
            schema_rows.append(dict(id='S-envelope-'+name+'-'+label,accepted=False))
            check('L3-envelope-'+name+'-'+label,fx.seal(e,p,z,a),'FORMAT','03_ENVELOPE',already_bound=False)
        for name,path in [('selector',['selector']),('publicKey',['grants',0,'publicKeyHex']),('componentHex',['graphHex'])]:
            e,p,z,a=base();target=p
            for k in path[:-1]:target=target[k]
            target[path[-1]]+=suffix
            assert list(jsonschema.Draft202012Validator(sd.schema('payload')).iter_errors(p))
            schema_rows.append(dict(id='S-payload-'+name+'-'+label,accepted=False))
            check('L3-payload-'+name+'-'+label,fx.seal(e,p,z,a,bind_payload=True),'FORMAT','03_PAYLOAD')
    for kind in ('envelope','payload','authorityScope'):jsonschema.Draft202012Validator.check_schema(sd.schema(kind))
    for seconds,expected in [(0,'1970-01-01T00:00:00Z'),(m.MAX_EPOCH,'9999-12-31T23:59:59Z')]:assert m.utc_epoch(seconds)==expected
    for bad in (-1,m.MAX_EPOCH+1,True):
        try:m.utc_epoch(bad)
        except ValueError:pass
        else:raise AssertionError('UTC helper accepted out-of-domain input')
    # Immutable published constants remain identical, not repinned to make tests green.
    assert len(sd.PIN_MAP)==28
    report=persist()
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows','schemaChecks')},indent=2))
except BaseException as error:
    report=persist(dict(type=type(error).__name__,message=str(error),traceback=traceback.format_exc()))
    print(json.dumps(dict(attempt=ATTEMPT,executedRows=report['executedRows'],distinct=report['distinctCompleteInputTuples'],failure=str(error))))
    raise
