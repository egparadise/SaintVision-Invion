"""UNREGISTERED Rev2 symbolic contract model, never a production authenticator.

Every BoundInputs source is explicitly SYNTHETIC_ALREADY_BOUND in the harness.
There is no source loader, signature/PKI/clock/OS verifier, signer or factory.
"""
from dataclasses import dataclass
import datetime
import hashlib
import json
import re

import jsonschema
from p02_rev2_schema import schema, FACT_KEYS, PIN_MAP

FORMAT='fleet5-p02-registry-candidate:2'
PURPOSE='installed-policy-registry'
DOMAIN=b'fleet5/p02/installed-policy-registry/candidate/v2'
PUBLIC_REFUSAL='TRUST_UNKNOWN_OR_PIN_MISMATCH'
ECHO='runningMeasurementSHA256'
MAX_ENVELOPE=2<<20
MAX_POLICY=16<<20
MAX_ARTIFACT=256<<20
MAX_EPOCH=253402300799
REASONS=frozenset(('ANCHOR','FORMAT','OWNERSHIP','SCOPE','SIGNATURE','TIME',
    'STATUS','VERSION','REPLAY','PROVENANCE','CI','ARTIFACT','INSTALLATION','READBACK'))

# This single list supplies execution order, refusal tables and test trace order.
STAGES=(
 ('01_ANCHOR',('ANCHOR','OWNERSHIP')),
 ('02_SOURCES',('PROVENANCE','CI','STATUS','TIME','INSTALLATION','OWNERSHIP')),
 ('03_ENVELOPE',('FORMAT',)),('03_PAYLOAD',('FORMAT',)),('03_C2',('FORMAT',)),
 ('04_SIGNATURE',('SCOPE','SIGNATURE')),('04_KEY_INTERVAL',('TIME',)),
 ('05_PAYLOAD_JOINS',('PROVENANCE',)),('05_COMPONENTS',('PROVENANCE',)),
 ('05_REVIEWS',('PROVENANCE',)),('05_SOURCE',('PROVENANCE',)),('05_CI',('CI',)),
 ('05_ARTIFACT',('ARTIFACT',)),('05_RUNNING',('INSTALLATION',)),
 ('06_STATUS',('STATUS',)),('06_VERSION',('VERSION',)),('06_REPLAY',('REPLAY',)),
 ('06_TIME',('TIME',)),('06_READBACK',('READBACK',)),
 ('07_PROJECTION',('PROVENANCE','CI','INSTALLATION')),
)
_VALIDATORS={name:jsonschema.Draft202012Validator(schema(name))
             for name in ('envelope','payload','authorityScope')}

@dataclass(frozen=True)
class BoundInputs:
    capsule: bytes | None
    source_facts: bytes | None
    ci: bytes | None
    reviews: bytes | None
    coverage: bytes | None
    lifecycle: bytes | None
    ticket: bytes | None
    h5: bytes | None
    clock: bytes | None
    signatures: frozenset
    v0: bytes
    v1: bytes

@dataclass(frozen=True)
class Result:
    label: str
    reason: str
    failed_stage: str
    detail: str
    passed_stages: tuple
    projection_bytes: bytes

class Refusal(Exception):
    def __init__(self,reason,detail):
        self.reason=reason;self.detail=detail

def need(condition,reason,detail):
    if not condition: raise Refusal(reason,detail)

def canonical(v):
    return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')

def c2(v):
    # K1 C2 uses Go Marshal HTML escaping, raw Unicode and escaped U+2028/2029.
    b=canonical(v)
    for old,new in ((b'&',b'\\u0026'),(b'<',b'\\u003c'),(b'>',b'\\u003e'),
                    ('\u2028'.encode(),b'\\u2028'),('\u2029'.encode(),b'\\u2029')):
        b=b.replace(old,new)
    return b

def sha(raw): return hashlib.sha256(raw).hexdigest()

def _pairs(items):
    d={}
    for k,v in items:
        if k in d: raise ValueError('duplicate key')
        d[k]=v
    return d

def _number(token):
    if len(token)>17: raise ValueError('integer bound')
    n=int(token)
    if abs(n)>9007199254740991 or str(n)!=token: raise ValueError('integer token')
    return n

def _no_float(_): raise ValueError('noninteger token')

def strict_json(raw,limit=MAX_ENVELOPE,max_string=65536,ascii_only=True,c2_mode=False):
    if type(raw) is not bytes or not raw or len(raw)>limit or raw.startswith(b'\xef\xbb\xbf'):
        raise ValueError('bounded owned UTF8 bytes')
    v=json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs,parse_int=_number,
                 parse_float=_no_float,parse_constant=_no_float)
    nodes=0;strings=0
    def walk(x,depth):
        nonlocal nodes,strings
        nodes+=1
        if nodes>100000 or depth>32: raise ValueError('tree budget')
        if type(x) is str:
            encoded=x.encode('utf-8')
            strings+=len(encoded)
            if len(encoded)>max_string or strings>limit: raise ValueError('string budget')
            if ascii_only and any(ord(c)<32 or ord(c)>126 for c in x):
                raise ValueError('manifest lexical subset')
        elif type(x) is dict:
            for k,y in x.items(): walk(k,depth+1);walk(y,depth+1)
        elif type(x) is list:
            for y in x: walk(y,depth+1)
        elif type(x) not in (bool,int,type(None)): raise ValueError('JSON algebra')
    walk(v,0)
    if (c2(v) if c2_mode else canonical(v))!=raw: raise ValueError('canonical roundtrip')
    return v

def unhex(text):
    if type(text) is not str or len(text)%2 or re.fullmatch('[0-9a-f]+',text) is None:
        raise ValueError('hex lexical form')
    raw=bytes.fromhex(text)
    if raw.hex()!=text: raise ValueError('hex roundtrip')
    return raw

def projection(e): return DOMAIN+b'\0'+canonical({'body':e['body'],'signer':e['signer']})

def record_identity(e):
    b=e['body']
    stable={k:b[k] for k in ('format','purpose','selector','scopeSHA256','capsuleSHA256',
        'provisioningGeneration','anchorVersion','recordVersion','facts','ciRuns','reviews')}
    stable['facts']={k:v for k,v in b['facts'].items() if k!=ECHO}
    return sha(canonical(stable))

def grant_registration(g,sc):
    return sha(c2(dict(role=g['role'],authorityScope=sc,publicKeyHex=g['publicKeyHex'],
                       notBefore=g['notBefore'],notAfter=g['notAfter'])))

def components(p):
    scopes=[strict_json(unhex(g['authorityScopeC2Hex']),65536,65536,False,True) for g in p['grants']]
    grants=[dict(role=g['role'],authorityScope=sc,publicKeyHex=g['publicKeyHex'],
                 notBefore=g['notBefore'],notAfter=g['notAfter']) for g,sc in zip(p['grants'],scopes)]
    cohort=dict(**{'class':'COHORT'},cohortId=p['cohortId'],members=[x['scope'] for x in p['members']])
    return dict(graphSHA256=sha(unhex(p['graphHex'])),contractSetSHA256=sha(c2(p['contractPins'])),
        semanticPinsSHA256=sha(c2(p['semanticPins'])),cohortScopeSHA256=sha(c2(cohort)),
        keyGrantsSHA256=sha(c2(grants)),registryProofSlotsSHA256=sha(unhex(p['proofSlotRegistryHex'])),
        designRegistrationSHA256=sha(unhex(p['designRegistrationHex'])))

def request_projection(a):
    cap=strict_json(a.capsule,65536);life=strict_json(a.lifecycle);ticket=strict_json(a.ticket)
    return dict(format=FORMAT,purpose=PURPOSE,capsuleSHA256=sha(a.capsule),
        provisioningGeneration=cap['generation'],selector=cap['selector'],scopeSHA256=cap['scopeSHA256'],
        recordVersion=life['currentVersion'],currentRecordIdentity=life['currentRecordIdentity'],
        componentSHA256=cap['componentSHA256'],ticketId=ticket['id'],
        ticketIssuedAt=ticket['issuedAt'],ticketExpiresAt=ticket['expiresAt'],h5EvidenceSHA256=sha(a.h5))

def _bound(raw,reason,detail,limit=MAX_ENVELOPE):
    try: return strict_json(raw,limit,limit)
    except (ValueError,TypeError,UnicodeError,RecursionError): raise Refusal(reason,detail)

def _anchor(c):
    a=c['a']
    need(type(a) is BoundInputs,'ANCHOR','missing-bound-capsule')
    need(all(type(c[k]) is bytes for k in ('raw','policy','artifact')),'OWNERSHIP','immutable-untrusted-byte-snapshots')
    need(type(a.signatures) is frozenset and len(a.signatures)<=16,'OWNERSHIP','immutable-signature-table')
    cap=_bound(a.capsule,'ANCHOR','capsule-unavailable',65536)
    required={'format','purpose','selector','scopeSHA256','generation','anchorVersion','keySPKI',
        'keyNotBefore','keyNotAfter','approvedReviewScope','primaryCI','sourceConstants','memberBindings',
        'sourceParts','reviewedParts','requiredParts','requiredSteps','optionalSteps','rootApprovalIdentity',
        'rootApprovalPurpose','approvedReviewOutcomes','componentSHA256','expectedUID','expectedRootSHA256',
        'minimumRecordVersion'}
    need(type(cap) is dict and set(cap)==required,'ANCHOR','closed-capsule-descriptor')
    need(cap['format']==FORMAT and cap['purpose']==PURPOSE,'ANCHOR','independent-purpose-format')
    need(type(cap['expectedUID']) is int and 0<=cap['expectedUID']<=4294967295 and all(type(cap[k]) is int for k in ('anchorVersion','keyNotBefore','keyNotAfter','minimumRecordVersion')),'ANCHOR','capsule-integer-types')
    c['cap']=cap

def _sources(c):
    a=c['a']
    for field,reason in [('source_facts','PROVENANCE'),('ci','CI'),('reviews','PROVENANCE'),
                         ('coverage','PROVENANCE'),('lifecycle','STATUS'),('ticket','TIME'),
                         ('h5','INSTALLATION'),('clock','TIME')]:
        raw=getattr(a,field)
        need(type(raw) is bytes and bool(raw),'OWNERSHIP' if raw is not None and type(raw) is not bytes else reason,'independent-'+field)
        c[field]=_bound(raw,reason,'bound-'+field)
    need(type(a.v0) is bytes and type(a.v1) is bytes,'OWNERSHIP','owned-readback-tokens')
    need(type(c['source_facts']) is dict and set(c['source_facts'])==FACT_KEYS-{ECHO},'PROVENANCE','closed-independent-source-facts')
    need(type(c['clock']) is dict and set(c['clock'])=={'lower','upper'} and all(type(x) is int for x in c['clock'].values()),'TIME','authenticated-integer-clock-bounds')

def _envelope(c):
    e=strict_json(c['raw'])
    need(not list(_VALIDATORS['envelope'].iter_errors(e)),'FORMAT','closed-envelope-schema')
    b=e['body'];runs=b['ciRuns']
    need([(r['workflow'],r['runId']) for r in runs]==sorted((r['workflow'],r['runId']) for r in runs),'FORMAT','canonical-CI-run-order')
    need(len({r['runId'] for r in runs})==len(runs),'FORMAT','unique-CI-runs')
    for r in runs:
        need([j['name'] for j in r['jobs']]==sorted({j['name'] for j in r['jobs']}),'FORMAT','canonical-unique-jobs')
        need(len({j['id'] for j in r['jobs']})==len(r['jobs']),'FORMAT','unique-job-id')
        for j in r['jobs']:
            need([s['number'] for s in j['steps']]==sorted({s['number'] for s in j['steps']}),'FORMAT','canonical-unique-step-numbers')
            need(len({s['name'] for s in j['steps']})==len(j['steps']),'FORMAT','unique-step-names')
    reviews=b['reviews']
    need([r['ordinal'] for r in reviews]==list(range(1,len(reviews)+1)) and len({r['reviewSHA'] for r in reviews})==len(reviews),'FORMAT','ordered-closed-review-set')
    c['e']=e;c['b']=b;c['f']=b['facts']

def _payload(c):
    p=strict_json(c['policy'],MAX_POLICY,MAX_POLICY)
    need(not list(_VALIDATORS['payload'].iter_errors(p)),'FORMAT','closed-policy-schema')
    c['p']=p

def _c2_components(c):
    p=c['p'];scopes=[]
    for name in ('graphHex','proofSlotRegistryHex','designRegistrationHex'):
        unhex(p[name])
    for g in p['grants']:
        sc=strict_json(unhex(g['authorityScopeC2Hex']),65536,65536,False,True)
        need(not list(_VALIDATORS['authorityScope'].iter_errors(sc)),'FORMAT','closed-C2-authority-scope')
        scopes.append(sc)
    for member in p['members']:
        unhex(member['certificateDERHex']);unhex(member['caRootDERHex'])
    for r in c['b']['reviews']:
        scope=unhex(r['scopeUTF8Hex']);scope.decode('utf-8')
        need(sha(scope)==r['scopeSHA256'],'FORMAT','original-review-scope-byte-hash')
    c['scopes']=scopes

def _signature(c):
    b=c['b'];cap=c['cap'];e=c['e'];a=c['a']
    need((b['selector'],b['scopeSHA256'],b['capsuleSHA256'],b['provisioningGeneration'],b['anchorVersion'])==
         (cap['selector'],cap['scopeSHA256'],sha(a.capsule),cap['generation'],cap['anchorVersion']),'SCOPE','exact-independent-capsule-binding')
    need(e['signer']['keySPKISHA256']==cap['keySPKI'] and (sha(projection(e)),e['signatureHex'],cap['keySPKI']) in a.signatures,'SIGNATURE','symbolic-preauthenticated-signature-binding')

def _key_interval(c):
    cap=c['cap'];b=c['b'];clk=c['clock']
    need(cap['keyNotBefore']<=b['issuedAt']<cap['keyNotAfter'] and cap['keyNotBefore']<=clk['lower']<=clk['upper']<cap['keyNotAfter'],'TIME','registry-key-issue-and-current-interval')

def _joins(c):
    p=c['p'];b=c['b'];f=c['f'];v=p['verifier']
    need(p['selector']==b['selector'],'PROVENANCE','payload-selector')
    need(p['version']==str(b['recordVersion']),'PROVENANCE','canonical-version-to-recordVersion')
    for field,fact in [('sourceSHA','sourceSHA'),('artifactSHA256','binarySHA256'),('reviewSHA','effectiveReviewSHA')]:
        need(v[field]==f[fact],'PROVENANCE','payload-verifier-'+field)
    need(v['ciRunIDs']==[r['runId'] for r in b['ciRuns']],'PROVENANCE','ordered-payload-CI-run-IDs')

def _digests(c):
    p=c['p'];f=c['f'];cap=c['cap'];values=components(p)
    need(sha(c['policy'])==f['policyPayloadSHA256'],'PROVENANCE','exact-canonical-payload-digest')
    for field,value in values.items():need(f[field]==value,'PROVENANCE','derived-'+field)
    need(values['cohortScopeSHA256']==c['b']['scopeSHA256'],'PROVENANCE','derived-cohort-to-independent-scope')
    sc=cap['sourceConstants'];sp=p['semanticPins']
    expected={'k1SourcePinSetSHA256','recipeDefinitionsSHA256','derivedDigestContractSHA256','proofSlotRegistrySHA256','graphSHA256','nodeKindsSHA256','designRegistrationSHA256'}
    need(type(sc) is dict and set(sc)==expected,'PROVENANCE','closed-independent-source-components')
    for name,value in sp.items():need(value==sc[name],'PROVENANCE','independent-semantic-source-'+name)
    for name,value in [('proofSlotRegistrySHA256',values['registryProofSlotsSHA256']),('graphSHA256',values['graphSHA256']),('nodeKindsSHA256',sha(c2(p['nodeKinds']))),('designRegistrationSHA256',values['designRegistrationSHA256'])]:
        need(sc[name]==value,'PROVENANCE','source-component-'+name)

def _reviews(c):
    b=c['b'];f=c['f'];cov=c['coverage'];cap=c['cap'];rs=b['reviews']
    need(canonical(rs)==c['a'].reviews,'PROVENANCE','original-authenticated-review-rows')
    need(set(cov)=={'purpose','authorityId','evidenceRawSHA256','statement'} and cov['purpose']==cap['rootApprovalPurpose'] and cov['authorityId']==cap['rootApprovalIdentity'],'PROVENANCE','independent-effective-approval-purpose-origin')
    s=cov['statement']
    need(set(s)=={'sourceSHA','sourceTreeSHA256','reviewSetSHA256','effective','parts'},'PROVENANCE','closed-Root-coverage-statement')
    need(s['sourceSHA']==f['sourceSHA'] and s['sourceTreeSHA256']==f['sourceTreeSHA256'] and s['reviewSetSHA256']==sha(c2(rs)),'PROVENANCE','coverage-current-source-and-original-set')
    mapping={r['reviewSHA']:r for r in rs}
    need(set(cap['approvedReviewOutcomes'])==set(mapping),'PROVENANCE','independent-review-outcome-set')
    for r in rs:need(r['verdict']==cap['approvedReviewOutcomes'][r['reviewSHA']],'PROVENANCE','independent-original-review-verdict')
    parts=s['parts'];ids=[p['partId'] for p in parts]
    need(ids==cap['requiredParts'] and len(set(ids))==len(ids) and set(ids)==set(cap['sourceParts']),'PROVENANCE','complete-ordered-source-partition')
    for part in parts:
        need(set(part)=={'partId','reviewSHA','reviewTargetSHA','reviewedBlobSHA256','currentBlobSHA256','relation'},'PROVENANCE','closed-part-coverage')
        r=mapping.get(part['reviewSHA']);pid=part['partId']
        need(r is not None and part['reviewTargetSHA']==r['targetSHA'],'PROVENANCE','preserved-original-review-target')
        need(part['currentBlobSHA256']==cap['sourceParts'][pid] and part['reviewedBlobSHA256']==cap['reviewedParts'].get(r['reviewSHA'],{}).get(pid),'PROVENANCE','independent-current-and-reviewed-part-bytes')
        need(part['currentBlobSHA256']==part['reviewedBlobSHA256'],'PROVENANCE','byte-equivalence-not-scope-label')
        need(part['relation'] in ('DIRECT','BYTE_IDENTICAL') and (part['relation']=='DIRECT')==(r['targetSHA']==s['sourceSHA']),'PROVENANCE','explicit-direct-or-inherited-relation')
    eff=s['effective']
    need(set(eff)=={'publicationSHA','targetSourceSHA','scopeId','verdict'} and eff['targetSourceSHA']==s['sourceSHA'],'PROVENANCE','effective-approval-current-target')
    for field,key in [('effectiveReviewSHA','publicationSHA'),('effectiveReviewTargetSHA','targetSourceSHA'),('effectiveReviewScope','scopeId'),('effectiveReviewVerdict','verdict')]:
        need(f[field]==eff[key],'PROVENANCE','effective-'+key)
    need(f['reviewCoverageSHA256']==sha(c2(s)) and f['rootChoiceSHA256']==cov['evidenceRawSHA256'] and f['sourceEquivalenceSHA256']==sha(c2(parts)),'PROVENANCE','Root-coverage-and-equivalence-evidence')

def _source(c):
    need({k:v for k,v in c['f'].items() if k!=ECHO}==c['source_facts'],'PROVENANCE','independent-source-acquisition-facts')
    f=c['f']
    need(not f['binaryVCSModified'] and f['binaryVCSRevision']==f['sourceSHA'],'PROVENANCE','source-VCS-join')

def _ci(c):
    b=c['b'];cap=c['cap'];f=c['f']
    need(canonical(b['ciRuns'])==c['a'].ci,'CI','independently-acquired-CI-records')
    actual={}
    for r in b['ciRuns']:
        need(r['headSHA']==f['sourceSHA'] and r['conclusion']=='success','CI','run-head-and-conclusion')
        for j in r['jobs']:
            need(j['conclusion']=='success','CI','job-conclusion')
            for st in j['steps']:actual[(r['runId'],j['name'],st['number'],st['name'])]=st['conclusion']
    req={tuple(x) for x in cap['requiredSteps']};opt={tuple(x) for x in cap['optionalSteps']}
    need(bool(req) and not req&opt and len(req)==len(cap['requiredSteps']) and len(opt)==len(cap['optionalSteps']) and set(actual)==req|opt,'CI','exact-required-and-optional-policy')
    need(all(actual[k]=='success' for k in req) and all(actual[k] in ('success','skipped') for k in opt),'CI','every-required-step-success')

def _artifact(c):
    f=c['f'];raw=c['artifact']
    need(type(raw) is bytes and len(raw)<=MAX_ARTIFACT and sha(raw)==f['artifactZipSHA256'] and len(raw)==f['artifactZipBytes'],'ARTIFACT','downloaded-archive-bytes-size-digest')

def _running(c):
    h=c['h5'];cap=c['cap'];f=c['source_facts']
    required={'purpose','componentSHA256','executableSHA256','sourceSHA','receiptSHA256','runtimeLockSHA256','linkedClosureSHA256','pid','startGeneration','uid','rootIdentitySHA256','observedAt','expiresAt','proofNonce'}
    need(type(h) is dict and set(h)==required and h['purpose']=='running-integration-measurement','INSTALLATION','independent-H5-purpose-shape')
    need(h['componentSHA256']==cap['componentSHA256'] and type(h['pid']) is int and h['pid']>0 and bool(h['startGeneration']) and h['uid']==cap['expectedUID'] and h['rootIdentitySHA256']==cap['expectedRootSHA256'],'INSTALLATION','actual-component-process-generation-root-UID')
    for key,fact in [('executableSHA256','binarySHA256'),('sourceSHA','sourceSHA'),('receiptSHA256','installationReceiptSHA256'),('runtimeLockSHA256','runtimeLockSHA256'),('linkedClosureSHA256','linkedClosureSHA256')]:
        need(h[key]==f[fact],'INSTALLATION','independent-H5-'+key)
    need(f['binarySHA256']==f['installationBinarySHA256']==f['runningBinarySHA256'] and f['sourceSHA']==f['installationSourceSHA']==f['runningSourceSHA'] and f['installationReceiptSHA256']==f['runningReceiptSHA256'] and f['runtimeLockSHA256']==f['runningRuntimeLockSHA256'] and f['linkedClosureSHA256']==f['runningLinkedClosureSHA256'],'INSTALLATION','approved-target-versus-installation-closure')

def _status(c):
    life=c['lifecycle']
    need(all(life.get(k)=='ACTIVE' for k in ('status','keyStatus','sourceStatus','coverageStatus','receiptStatus')),'STATUS','independent-current-status-not-record-claim')
    for r in c['b']['reviews']:need(life['reviews'].get(r['reviewSHA'])=='ACTIVE','STATUS','current-review-registration')
    for g,sc in zip(c['p']['grants'],c['scopes']):need(life['grants'].get(grant_registration(g,sc))=='ACTIVE','STATUS','current-independent-grant-registration')
    for member in c['p']['members']:need(life['certificates'].get(sha(unhex(member['certificateDERHex'])))=='ACTIVE','STATUS','current-independent-certificate-registration')

def _version(c):
    life=c['lifecycle'];cap=c['cap'];b=c['b']
    need(life['generation']==cap['generation'] and life['capsuleSHA256']==sha(c['a'].capsule),'VERSION','current-installation-generation')
    need(b['recordVersion']==life['currentVersion'] and b['recordVersion']>=max(cap['minimumRecordVersion'],life['floor']) and life['currentRecordIdentity']==record_identity(c['e']),'VERSION','current-stable-record-and-protected-floor')

def _replay(c):
    t=c['ticket'];cap=c['cap'];life=c['lifecycle'];a=c['a']
    need(t['purpose']=='p02-read-ticket-candidate:2' and t['selector']==cap['selector'] and t['scopeSHA256']==cap['scopeSHA256'] and t['capsuleSHA256']==sha(a.capsule) and t['generation']==cap['generation'] and t['currentVersion']==life['currentVersion'] and t['currentRecordIdentity']==life['currentRecordIdentity'],'REPLAY','independent-ticket-scope-current-binding')
    request=request_projection(a)
    need(c['b']['requestBindingSHA256']==sha(c2(request)) and c['f'][ECHO]==request['h5EvidenceSHA256'],'REPLAY','zero-weight-H5-echo-bound-through-client-request')

def _time(c):
    l=c['clock']['lower'];u=c['clock']['upper'];life=c['lifecycle'];t=c['ticket'];b=c['b'];h=c['h5']
    need(0<=u-l<=1,'TIME','whole-clock-interval')
    need(life['checkedAt']<=l<=u<life['expiresAt'] and u-life['checkedAt']<=120,'TIME','current-status-freshness')
    need(t['issuedAt']<=b['issuedAt']<=l<=u<t['expiresAt'] and u<b['validUntil'] and u-b['issuedAt']<=120,'TIME','response-ticket-freshness')
    need(h['observedAt']<=l<=u<h['expiresAt'] and u-h['observedAt']<=120,'TIME','independent-H5-freshness-not-echo')

def _readback(c):
    a=c['a']
    need(bool(a.v0) and len(a.v0)<=65536 and a.v0==a.v1,'READBACK','mandatory-exact-final-readback')

def utc_epoch(value):
    if type(value) is not int or not 0<=value<=MAX_EPOCH: raise ValueError('Go-compatible UTC epoch bound')
    d=datetime.datetime(1970,1,1,tzinfo=datetime.timezone.utc)+datetime.timedelta(seconds=value)
    return f'{d.year:04d}-{d.month:02d}-{d.day:02d}T{d.hour:02d}:{d.minute:02d}:{d.second:02d}Z'

def _project(c):
    p=c['p'];cap=c['cap'];s=c['source_facts'];h=c['h5'];cov=c['coverage']['statement'];life=c['lifecycle']
    primary=cap['primaryCI']
    need(set(primary)=={'runId','jobId','jobName'},'CI','provisioned-primary-CI-tuple-shape')
    need(all(type(primary[k]) is int and 0<primary[k]<=9007199254740991 for k in ('runId','jobId')) and type(primary['jobName']) is str,'CI','canonical-primary-CI-identifiers')
    runs=[r for r in c['b']['ciRuns'] if r['runId']==primary['runId']]
    need(len(runs)==1,'CI','provisioned-primary-run-not-first-green')
    run=runs[0];jobs=[j for j in run['jobs'] if j['id']==primary['jobId'] and j['name']==primary['jobName']]
    need(len(jobs)==1,'CI','provisioned-primary-job-not-first-green')
    grants=[]
    for g,sc in zip(p['grants'],c['scopes']):
        need(g['notBefore']<g['notAfter'],'PROVENANCE','original-grant-interval-order')
        grants.append(dict(Role=g['role'],AuthorityScope=sc,PublicKeyHex=g['publicKeyHex'],
            NotBefore=utc_epoch(g['notBefore']),NotAfter=utc_epoch(g['notAfter']),
            Status=life['grants'][grant_registration(g,sc)]))
    members=[dict(Slot=m['slot'],Scope=m['scope'],CertificateDER=m['certificateDERHex'],CARootDER=m['caRootDERHex']) for m in p['members']]
    provenance=dict(ReviewTargetSHA=cov['effective']['targetSourceSHA'],ReviewScope=cov['effective']['scopeId'],
        ApprovedReviewScope=cap['approvedReviewScope'],BinaryVCS=s['binaryVCSRevision'],RuntimeLockSHA256=h['runtimeLockSHA256'],
        CIHeadSHA=run['headSHA'],CIRef=run['ref'],CIWorkflow=run['workflow'],CIRunID=str(run['runId']),CIAttempt=str(run['attempt']),CIJobID=str(primary['jobId']),
        ArtifactDigest=s['artifactZipSHA256'],InstallationReceiptSHA256=h['receiptSHA256'],RunningExecutableSHA256=h['executableSHA256'],LinkedClosureSHA256=h['linkedClosureSHA256'])
    v=p['verifier']
    publication=dict(ID=v['id'],SourceSHA=s['sourceSHA'],ArtifactSHA256=s['binarySHA256'],ReviewSHA=cov['effective']['publicationSHA'],CIRunIDs=[str(i) for i in v['ciRunIDs']])
    out=dict(Selector=cap['selector'],Version=p['version'],RegistrySHA256=sha(c['policy']),Verifier=publication,
        ContractPins={k:dict(ContractSHA256=x['contractSHA256'],SchemaSHA256=x['schemaSHA256'],Codec=x['codec'],RequiredVerifier=x['requiredVerifier']) for k,x in p['contractPins'].items()},
        Grants=grants,CohortID=p['cohortId'],Members=members,GraphBytes=p['graphHex'],GraphSHA256=sha(unhex(p['graphHex'])),NodeKinds=p['nodeKinds'],Provenance=provenance)
    need(provenance['ReviewTargetSHA']==publication['SourceSHA'] and provenance['ReviewScope']==provenance['ApprovedReviewScope'],'PROVENANCE','effective-current-target-and-independent-approved-scope')
    need(provenance['CIHeadSHA']==publication['SourceSHA']==provenance['BinaryVCS'] and provenance['CIRunID'] in publication['CIRunIDs'],'PROVENANCE','K1-provenance-primary-membership')
    keys=[(g['Role'],sha(c2(g['AuthorityScope'])),g['PublicKeyHex']) for g in grants]
    need(len(set(keys))==len(keys),'PROVENANCE','unique-role-scope-public-key-grants')
    need([m['Slot'] for m in members]==['PC2','PC4'] and len({sha(c2(m['Scope'])) for m in members})==2 and len({m['CertificateDER'] for m in members})==2,'PROVENANCE','ordered-distinct-legacy-members')
    bindings=cap['memberBindings'];need(len(bindings)==2,'PROVENANCE','independent-public-member-bindings')
    spkis=[]
    for member,binding in zip(members,bindings):
        need(member['Slot']==binding['slot'] and member['Scope']==binding['scope'] and sha(unhex(member['CertificateDER']))==binding['certificateSHA256'] and sha(unhex(member['CARootDER']))==binding['caSHA256'],'PROVENANCE','independent-DER-CA-scope-bindings')
        spkis.append(binding['SPKISHA256'])
        authority=dict(**{'class':'NODE'},scope=member['Scope'])
        need(any(g['Role']=='node-leaf' and g['PublicKeyHex']==binding['publicKeyHex'] and g['AuthorityScope']==authority for g in grants),'PROVENANCE','node-leaf-grant-C2-public-key-binding')
    need(len(set(spkis))==2,'PROVENANCE','independent-member-SPKI-uniqueness')
    # This semantic DTO encodes []byte as lowercase hex and UTC times as exact Z strings.
    # No opaque Go input is constructed; real DER/SPKI/signature checks remain with K1.
    c['projection']=canonical(out)

_CHECKS=(_anchor,_sources,_envelope,_payload,_c2_components,_signature,_key_interval,
         _joins,_digests,_reviews,_source,_ci,_artifact,_running,_status,_version,
         _replay,_time,_readback,_project)
assert len(_CHECKS)==len(STAGES)

def evaluate(raw,policy,artifact,a):
    c=dict(raw=raw,policy=policy,artifact=artifact,a=a);passed=[]
    for (stage,allowed),check in zip(STAGES,_CHECKS):
        try:
            check(c)
        except Refusal as error:
            assert error.reason in allowed,(stage,error.reason)
            return Result('REFUSE',error.reason,stage,error.detail,tuple(passed),b'')
        except (ValueError,UnicodeError,RecursionError,TypeError,KeyError,OverflowError):
            reason='FORMAT' if stage.startswith('03_') else allowed[0]
            return Result('REFUSE',reason,stage,'closed-input-shape',tuple(passed),b'')
        passed.append(stage)
    return Result('SYNTHETIC_ALREADY_BOUND','','','',tuple(passed),c['projection'])

def production_projection(_result): return PUBLIC_REFUSAL
