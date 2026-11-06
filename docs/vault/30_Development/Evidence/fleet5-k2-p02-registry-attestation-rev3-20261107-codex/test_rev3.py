"""Rev3 only: M1 acceptance and L1 independent projection; STATIC/SYMBOLIC."""
from dataclasses import fields,replace
from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,sys,traceback
import jsonschema
HERE=Path(__file__).parent
BASE=HERE.parent/'fleet5-k2-p02-registry-attestation-rev2-20261107-codex'
for name,path in [('p02_rev2_schema',BASE/'schema_defs.py'),('p02_rev3_model',HERE/'candidate_model.py'),('p02_rev3_fixtures',HERE/'fixture_data.py')]:
 spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
m=sys.modules['p02_rev3_model'];fx=sys.modules['p02_rev3_fixtures'];sd=sys.modules['p02_rev2_schema']
OUT=HERE/'test-runs';OUT.mkdir(exist_ok=True)
attempt=1
while (OUT/f'attempt-{attempt:02d}.json').exists():attempt+=1
rows=[];seen=set();isolation=[];start=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()

def primitive(v):
 if type(v) is m.BoundInputs:return dict(type='BoundInputs',fields={f.name:primitive(getattr(v,f.name)) for f in fields(v)})
 if type(v) is bytes:return dict(type='bytes',hex=v.hex())
 if type(v) is frozenset:return dict(type='frozenset',items=sorted([primitive(x) for x in v],key=lambda x:json.dumps(x,sort_keys=True)))
 if type(v) is tuple:return dict(type='tuple',items=[primitive(x) for x in v])
 if v is None or type(v) in (str,int,bool):return v
 raise TypeError(type(v))

def check(name,inp,reason='',stage='',detail=None,reviewEquivalent=None):
 raw,policy,artifact,a=inp;e=json.loads(raw);cap=json.loads(a.capsule)
 pre=dict(envelopeSchemaValid=jsonschema.Draft202012Validator(sd.schema('envelope')).is_valid(e),
  payloadSchemaValid=jsonschema.Draft202012Validator(sd.schema('payload')).is_valid(json.loads(policy)),
  retainedFormat=e['body']['format']==m.FORMAT,exactCanonicalEnvelope=m.canonical(e)==raw,
  payloadDigestBound=m.sha(policy)==e['body']['facts']['policyPayloadSHA256'],
  signatureTupleBound=(m.sha(m.projection(e)),e['signatureHex'],cap['keySPKI']) in a.signatures)
 assert all(pre.values()),(name,pre)
 fp=m.sha(m.canonical(primitive(inp)));assert fp not in seen,(name,'duplicate input');seen.add(fp)
 r=m.evaluate(*inp);names=[x for x,_ in m.STAGES];prefix=names if not stage else names[:names.index(stage)]
 row=dict(id=name,reviewEquivalent=reviewEquivalent,inputSHA256=fp,expectedReason=reason,expectedStage=stage,observedLabel=r.label,observedReason=r.reason,observedStage=r.failed_stage,detail=r.detail,alreadyBoundPreconditions=pre,passedStages=list(r.passed_stages),expectedEarlierStages=prefix,earlierStagesExactlyPass=list(r.passed_stages)==prefix,productionProjection=m.production_projection(r))
 rows.append(row)
 assert r.reason==reason and r.failed_stage==stage,(name,r)
 assert list(r.passed_stages)==prefix,(name,'earlier-stage-prefix')
 if detail:assert r.detail==detail,(name,r.detail,detail)
 assert m.production_projection(r)==m.PUBLIC_REFUSAL
 return r

def capmod(e,a,fn):
 cap=json.loads(a.capsule);fn(cap);a=replace(a,capsule=m.canonical(cap));e['body']['capsuleSHA256']=m.sha(a.capsule);return a

def covmod(a,fn):
 cov=json.loads(a.coverage);fn(cov);return replace(a,coverage=m.canonical(cov))

def k1_running_comparison(policy,provenance,measured):
 # ONLY the unchanged final checkPolicyBindings predicate; NOT K1 execution/authentication.
 v=policy['Verifier'];pr=provenance;h=measured
 return (h['ExecutableSHA256']==v['ArtifactSHA256'] and pr['RunningExecutableSHA256']==h['ExecutableSHA256'] and h['SourceSHA']==v['SourceSHA'] and h['InstallationReceiptSHA256']==pr['InstallationReceiptSHA256'] and h['RuntimeLockSHA256']==pr['RuntimeLockSHA256'] and h['LinkedClosureSHA256']==pr['LinkedClosureSHA256'])

try:
 e,p,z,a=fx.fixture();ctl=(m.canonical(e),m.canonical(p),z,a)
 r=check('C01-benign-independent-approval',ctl)
 policy=json.loads(r.projection_bytes);src=json.loads(a.source_facts);h5=json.loads(a.h5)
 assert e['body']['reviews']==fx.REVIEWS
 assert json.loads(a.coverage)['statement']['parts']==fx.STATEMENT['parts']
 assert fx.EXPECTED_EFFECTIVE_VERDICT==json.loads(a.capsule)['expectedEffectiveVerdict']
 assert policy['Provenance']['RunningExecutableSHA256']==h5['executableSHA256']
 assert all(policy['Provenance'][k]==src[f] for k,f in [('InstallationReceiptSHA256','installationReceiptSHA256'),('RuntimeLockSHA256','runtimeLockSHA256'),('LinkedClosureSHA256','linkedClosureSHA256')])
 measured=m.running_data_projection(h5)
 assert len(measured)==5 and k1_running_comparison(policy,policy['Provenance'],measured)
 # Independent original identities/targets/verdicts stay unchanged in all three rebased attacks.
 for name,kind,idx in [('M01-nonapproval','verdict',None),('M02-direct-publication-alias','publication',1),('M03-inherited-publication-alias','publication',0)]:
  e,p,z,a=fx.fixture();original=copy.deepcopy(e['body']['reviews'])
  if kind=='verdict':
   bad='SYNTHETIC_REVISION_REQUIRED_NOT_APPROVED';a=covmod(a,lambda c:c['statement']['effective'].update(verdict=bad));e['body']['facts']['effectiveReviewVerdict']=bad
   inp=fx.seal(e,p,z,a,bind_coverage=True,source_fields=('effectiveReviewVerdict',),new_head=True,new_request=True)
   detail='independently-approved-effective-verdict'
  else:
   old=original[idx]['reviewSHA'];a=covmod(a,lambda c:c['statement']['effective'].update(publicationSHA=old));p['verifier']['reviewSHA']=old;e['body']['facts']['effectiveReviewSHA']=old
   inp=fx.seal(e,p,z,a,bind_payload=True,bind_coverage=True,source_fields=('effectiveReviewSHA',),new_head=True,new_request=True)
   detail='effective-publication-distinct-from-every-original-and-part'
  assert json.loads(inp[0])['body']['reviews']==original==fx.REVIEWS
  assert json.loads(inp[3].reviews)==original
  assert json.loads(inp[3].coverage)['statement']['parts']==fx.STATEMENT['parts']
  check(name,inp,'PROVENANCE','05_REVIEWS',detail,{'M01-nonapproval':'V19','M02-direct-publication-alias':'V20','M03-inherited-publication-alias':'V20b'}[name])
 # EVERY original includes an authenticated review not used by any part; no registry omission escape.
 e,p,z,a=fx.fixture();third=fx._review(3,'c2'*20,'c1'*20,'SYNTHETIC_EXTRA_SCOPE_ACCEPT','Original synthetic unused scope','synthetic-reviewer-C')
 e['body']['reviews'].append(third)
 a=capmod(e,a,lambda c:c['approvedReviewOutcomes'].update({third['reviewSHA']:third['verdict']}))
 a=covmod(a,lambda c:c['statement'].update(reviewSetSHA256=m.sha(m.c2(e['body']['reviews']))))
 a=covmod(a,lambda c:c['statement']['effective'].update(publicationSHA=third['reviewSHA']))
 p['verifier']['reviewSHA']=third['reviewSHA'];e['body']['facts']['effectiveReviewSHA']=third['reviewSHA']
 check('M04-unused-original-alias',fx.seal(e,p,z,a,bind_payload=True,bind_reviews=True,bind_coverage=True,source_fields=('effectiveReviewSHA',),new_head=True,new_request=True),'PROVENANCE','05_REVIEWS','effective-publication-distinct-from-every-original-and-part')
 for name,value in [('M05-empty-expectation',''),('M06-independent-other-verdict','SYNTHETIC_ANOTHER_REQUIRED_APPROVAL'),('M08-nonstring-expectation',True)]:
  e,p,z,a=fx.fixture();a=capmod(e,a,lambda c:c.update(expectedEffectiveVerdict=value))
  check(name,fx.seal(e,p,z,a,new_head=True,new_request=True),'PROVENANCE','05_REVIEWS','independently-approved-effective-verdict' if name.startswith('M06') else 'closed-independent-effective-verdict-expectation')
 e,p,z,a=fx.fixture();a=capmod(e,a,lambda c:c.pop('expectedEffectiveVerdict'))
 check('M07-missing-provisioned-expectation',fx.seal(e,p,z,a,new_head=True,new_request=True),'ANCHOR','01_ANCHOR','closed-capsule-descriptor')
 # Full evaluator: tamper either independent source while keeping outer envelope/digest/signature valid.
 triples=[('receipt','installationReceiptSHA256','receiptSHA256','InstallationReceiptSHA256'),('lock','runtimeLockSHA256','runtimeLockSHA256','RuntimeLockSHA256'),('link','linkedClosureSHA256','linkedClosureSHA256','LinkedClosureSHA256')]
 for label,h3key,h5key,outkey in triples:
  e,p,z,a=fx.fixture();e['body']['facts'][h3key]='af'*32
  check('H3-'+label+'-differs',fx.seal(e,p,z,a,source_fields=(h3key,),new_head=True,new_request=True),'INSTALLATION','05_RUNNING','independent-H5-'+h5key)
  e,p,z,a=fx.fixture();h=json.loads(a.h5);h[h5key]='bf'*32;a=replace(a,h5=m.canonical(h))
  check('H5-'+label+'-differs',fx.seal(e,p,z,a,new_request=True),'INSTALLATION','05_RUNNING','independent-H5-'+h5key)
 # Isolated projection mutation tests are NOT accepted/evaluated policy or authentication.
 for label,h3key,h5key,outkey in triples:
  approved=copy.deepcopy(src);approved[h3key]='af'*32
  pr=m.installation_provenance_projection(approved,h5);measured=m.running_data_projection(h5)
  assert pr[outkey]==approved[h3key] and pr[outkey]!=measured[outkey]
  assert not k1_running_comparison(policy,pr,measured)
  isolation.append(dict(id='APPROVED-'+label,classification='ISOLATED_PROJECTION_NO_ACCEPTANCE',expectedSide='H3',measuredSide='H5',K1_lastPredicate=False))
  observed=copy.deepcopy(h5);observed[h5key]='bf'*32
  pr=m.installation_provenance_projection(src,observed);measured=m.running_data_projection(observed)
  assert pr[outkey]==src[h3key] and pr[outkey]!=measured[outkey]
  assert not k1_running_comparison(policy,pr,measured)
  unsafe_coupled=dict(pr);unsafe_coupled[outkey]=measured[outkey]
  assert k1_running_comparison(policy,unsafe_coupled,measured)
  isolation.append(dict(id='MEASURED-'+label,classification='ISOLATED_PROJECTION_MUTANT_NO_ACCEPTANCE',expectedSide='H3',measuredSide='H5',K1_lastPredicate=False,regressedSameSourceMutantWouldPass=True))
 for key in ('executableSHA256','sourceSHA'):
  observed=copy.deepcopy(h5);observed[key]='bf'*(20 if key=='sourceSHA' else 32)
  assert not k1_running_comparison(policy,m.installation_provenance_projection(src,observed),m.running_data_projection(observed))
  isolation.append(dict(id='MEASURED-'+key,classification='ISOLATED_PROJECTION_NO_ACCEPTANCE',K1_lastPredicate=False))
 error=None
except Exception:
 error=traceback.format_exc()
report=dict(classification='REV3_TARGETED_STATIC_SYMBOLIC_ONLY_NOT_CRYPTO_PRODUCER_OR_RUNTIME_PROOF',attempt=attempt,startedKST=start,completedKST=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),executedRows=len(rows),distinctCompleteInputTuples=len(seen),symbolicControls=sum(x['observedLabel']=='SYNTHETIC_ALREADY_BOUND' for x in rows),refusals=sum(x['observedLabel']=='REFUSE' for x in rows),failures=int(error is not None),error=error,rows=rows,projectionIsolationChecks=isolation,sourceHashes={p.name:m.sha(p.read_bytes()) for p in (HERE/'candidate_model.py',HERE/'fixture_data.py',HERE/'test_rev3.py')},parentSchemaSHA256=m.sha((BASE/'schema_defs.py').read_bytes()),originalReviewRows48='ARCHIVED_NOT_RERUN',oldOwner97Rows='UNCHANGED_NOT_RERUN',actualProducer=None,actualAuthentication=False,productionAlwaysRefuses=True,actualH1H7='NULL_HOLD',H3_EA='ABSENT_UNREGISTERED_HOLD',registrationByteOrigin='HOLD_FACT_ONLY',A01A40='NOT_RUN')
(OUT/f'attempt-{attempt:02d}.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
if error:
 print(error);raise SystemExit(1)
(HERE/'test-results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(executedRows=len(rows),distinctInputs=len(seen),controls=report['symbolicControls'],refusals=report['refusals'],isolationChecks=len(isolation),failures=0,attempt=attempt)))
