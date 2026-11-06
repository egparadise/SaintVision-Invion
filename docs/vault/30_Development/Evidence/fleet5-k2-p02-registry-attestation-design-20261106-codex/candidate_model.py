"""SYMBOLIC CONTRACT MODEL ONLY. No crypto/provider/clock/OS authentication.

SyntheticBoundInputs represents preauthenticated external facts in static tests.
It has no production loader. No result issues a policy or other capability.
"""
from dataclasses import dataclass
import hashlib
import json
import re

FORMAT = 'fleet5-p02-registry-candidate:1'
PURPOSE = 'installed-policy-registry'
DOMAIN = b'fleet5/p02/installed-policy-registry/candidate/v1'
PUBLIC_REFUSAL = 'TRUST_UNKNOWN_OR_PIN_MISMATCH'
MAX_ENVELOPE = 2 << 20
MAX_POLICY = 16 << 20
MAX_ARTIFACT = 256 << 20
BODY_KEYS = frozenset(('format', 'purpose', 'selector', 'scopeSHA256',
    'capsuleSHA256', 'provisioningGeneration', 'anchorVersion', 'recordVersion', 'requestBindingSHA256', 'issuedAt',
    'validUntil', 'facts', 'ciRuns'))
HASH40 = frozenset(('sourceSHA', 'reviewSHA', 'reviewTargetSHA',
    'binaryVCSRevision', 'installationSourceSHA', 'runningSourceSHA'))
TEXT = frozenset(('reviewScope', 'reviewVerdict', 'toolchain'))
NUMBERS = frozenset(('artifactId', 'artifactZipBytes'))
HASH64 = frozenset(('policyPayloadSHA256', 'registryProofSlotsSHA256',
    'designRegistrationSHA256', 'graphSHA256', 'contractSetSHA256',
    'semanticPinsSHA256', 'cohortScopeSHA256', 'keyGrantsSHA256',
    'sourceTreeSHA256', 'reviewCoverageSHA256', 'rootChoiceSHA256',
    'sourceEquivalenceSHA256', 'artifactZipSHA256', 'binarySHA256',
    'moduleClosureSHA256', 'helperClosureSHA256', 'runtimeLockSHA256',
    'linkedClosureSHA256', 'installationReceiptSHA256',
    'installationBinarySHA256', 'runningBinarySHA256', 'runningReceiptSHA256',
    'runningRuntimeLockSHA256', 'runningLinkedClosureSHA256',
    'runningMeasurementSHA256', 'sourcePublicationAnchorSHA256', 'sourceAcquisitionSHA256'))
FACT_KEYS = HASH40 | HASH64 | TEXT | NUMBERS | {'binaryVCSModified'}
RUN_KEYS = frozenset(('runId','repository','headSHA','ref','event','workflow',
    'correlation','attempt','conclusion','jobs'))
JOB_KEYS = frozenset(('id','name','conclusion','steps'))
STEP_KEYS = frozenset(('number','name','conclusion'))
REASONS = frozenset(('ANCHOR','FORMAT','OWNERSHIP','SCOPE','SIGNATURE','TIME',
    'STATUS','VERSION','REPLAY','PROVENANCE','CI','ARTIFACT','INSTALLATION','READBACK'))

@dataclass(frozen=True)
class SyntheticBoundInputs:
    key_spki: str
    selector: str
    scope: str
    anchor_version: int
    capsule_sha: str
    generation: str
    purpose: str
    facts: bytes
    ci: bytes
    required_steps: tuple  # (runId, jobName, number, exactName), from independent policy
    allowed_skips: tuple  # exact separately approved optional step set
    signatures: frozenset  # (projectionSHA256, signatureHex, pinnedSPKI); symbolic only
    minimum_version: int
    current_version: int
    current_digest: str
    request_binding: str
    lower: int
    upper: int
    checked: int
    status_expires: int
    ticket_issued: int
    ticket_expires: int
    key_before: int
    key_after: int
    status: str
    v0: bytes
    v1: bytes

@dataclass(frozen=True)
class ModelResult:
    label: str
    internal_reason: str

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def projection(envelope):
    return DOMAIN+b'\0'+canonical({'body':envelope['body'],'signer':envelope['signer']})

def record_identity(envelope):
    # Head identity precedes read response: no fresh ticket/time/signature or
    # independently measured fresh running-proof digest enters this projection.
    b=envelope['body']
    stable={k:b[k] for k in ('format','purpose','selector','scopeSHA256',
        'capsuleSHA256','provisioningGeneration','anchorVersion','recordVersion','facts','ciRuns')}
    stable['facts']={k:v for k,v in b['facts'].items() if k!='runningMeasurementSHA256'}
    return sha(canonical(stable))

def _integer(text):
    if len(text)>16:
        raise ValueError('integer size')
    value=int(text)
    if value<0 or value>9007199254740991:
        raise ValueError('integer range')
    return value

def _reject(_):
    raise ValueError('noninteger numeric value')

def _pairs(pairs):
    obj={}
    for key,value in pairs:
        if key in obj:
            raise ValueError('duplicate key')
        obj[key]=value
    return obj

def _parse(raw):
    if type(raw) is not bytes or len(raw)>MAX_ENVELOPE or raw.startswith(b'\xef\xbb\xbf'):
        raise ValueError('bounded immutable bytes required')
    value=json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs,
                     parse_int=_integer,parse_float=_reject,parse_constant=_reject)
    nodes=0
    strings=0
    def walk(v,depth):
        nonlocal nodes,strings
        nodes+=1
        if nodes>100000 or depth>32:
            raise ValueError('tree budget')
        if type(v) is str:
            if len(v)>65536 or any(ord(c)<32 or ord(c)>126 for c in v):
                raise ValueError('restricted manifest string')
            strings+=len(v)
            if strings>1<<20:
                raise ValueError('string budget')
        elif type(v) is dict:
            for k,x in v.items():
                walk(k,depth+1);walk(x,depth+1)
        elif type(v) is list:
            for x in v:
                walk(x,depth+1)
        elif type(v) not in (bool,int,type(None)):
            raise ValueError('closed JSON algebra')
    walk(value,0)
    if canonical(value)!=raw:
        raise ValueError('noncanonical bytes')
    return value

def _hex(value,n):
    return type(value) is str and re.fullmatch('[0-9a-f]{'+str(n)+'}',value) is not None and set(value)!={'0'}

def _pos(v):
    return type(v) is int and 1<=v<=9007199254740991

def _shape(e):
    if type(e) is not dict or set(e)!={'body','signer','signatureHex'}:
        return False
    b=e['body'];signer=e['signer']
    if type(b) is not dict or set(b)!=BODY_KEYS or type(signer) is not dict or set(signer)!={'keySPKISHA256'}:
        return False
    if not _hex(signer['keySPKISHA256'],64) or not _hex(e['signatureHex'],128):
        return False
    if b['format']!=FORMAT or b['purpose']!=PURPOSE or type(b['selector']) is not str or re.fullmatch('[A-Za-z0-9_-]{1,128}',b['selector']) is None:
        return False
    if type(b['provisioningGeneration']) is not str or re.fullmatch('[A-Za-z0-9_-]{1,128}',b['provisioningGeneration']) is None:
        return False
    if not all(_hex(b[k],64) for k in ('scopeSHA256','requestBindingSHA256','capsuleSHA256')) or not all(_pos(b[k]) for k in ('anchorVersion','recordVersion','issuedAt','validUntil')):
        return False
    f=b['facts']
    if type(f) is not dict or set(f)!=FACT_KEYS or not all(_hex(f[k],40) for k in HASH40) or not all(_hex(f[k],64) for k in HASH64):
        return False
    if not all(type(f[k]) is str and 1<=len(f[k])<=256 for k in TEXT) or not all(_pos(f[k]) for k in NUMBERS) or type(f['binaryVCSModified']) is not bool:
        return False
    runs=b['ciRuns']
    if type(runs) is not list or not 1<=len(runs)<=8:
        return False
    run_ids=[];order=[]
    for r in runs:
        if type(r) is not dict or set(r)!=RUN_KEYS or not _pos(r['runId']) or not _pos(r['attempt']) or not _hex(r['headSHA'],40):
            return False
        if not all(type(r[k]) is str and 1<=len(r[k])<=256 for k in RUN_KEYS-{'runId','attempt','headSHA','jobs'}):
            return False
        run_ids.append(r['runId']);order.append((r['workflow'],r['runId']))
        if type(r['jobs']) is not list or not 1<=len(r['jobs'])<=8:
            return False
        job_ids=[];names=[]
        for j in r['jobs']:
            if type(j) is not dict or set(j)!=JOB_KEYS or not _pos(j['id']) or type(j['name']) is not str or not 1<=len(j['name'])<=128 or type(j['conclusion']) is not str:
                return False
            job_ids.append(j['id']);names.append(j['name'])
            if type(j['steps']) is not list or not 1<=len(j['steps'])<=128:
                return False
            numbers=[];step_names=[]
            for s in j['steps']:
                if type(s) is not dict or set(s)!=STEP_KEYS or not _pos(s['number']) or not all(type(s[k]) is str and 1<=len(s[k])<=256 for k in ('name','conclusion')):
                    return False
                numbers.append(s['number']);step_names.append(s['name'])
            if numbers!=sorted(set(numbers)) or len(set(step_names))!=len(step_names):
                return False
        if len(set(job_ids))!=len(job_ids) or names!=sorted(set(names)):
            return False
    return len(set(run_ids))==len(run_ids) and order==sorted(order)

def _evaluate(raw,policy_bytes,artifact_bytes,a):
    if type(a) is not SyntheticBoundInputs or a.purpose!=PURPOSE:
        return 'ANCHOR'
    if any(type(x) is not bytes for x in (raw,policy_bytes,artifact_bytes,a.facts,a.ci,a.v0,a.v1)):
        return 'OWNERSHIP'
    if type(a.required_steps) is not tuple or type(a.allowed_skips) is not tuple or type(a.signatures) is not frozenset or len(a.required_steps)+len(a.allowed_skips)>8192 or len(a.signatures)>16:
        return 'OWNERSHIP'
    if len(a.facts)>MAX_ENVELOPE or len(a.ci)>MAX_ENVELOPE or len(a.v0)>65536 or len(a.v1)>65536:
        return 'FORMAT'
    if not all(type(x) is int for x in (a.lower,a.upper,a.checked,a.status_expires,a.key_before,a.key_after,a.ticket_issued,a.ticket_expires)):
        return 'TIME'
    if len(policy_bytes)>MAX_POLICY or len(artifact_bytes)>MAX_ARTIFACT:
        return 'FORMAT'
    e=_parse(raw)
    if not _shape(e):
        return 'FORMAT'
    b=e['body'];f=b['facts']
    if (b['selector'],b['scopeSHA256'],b['anchorVersion'],b['capsuleSHA256'],b['provisioningGeneration'])!=(a.selector,a.scope,a.anchor_version,a.capsule_sha,a.generation):
        return 'SCOPE'
    if e['signer']['keySPKISHA256']!=a.key_spki or (sha(projection(e)),e['signatureHex'],a.key_spki) not in a.signatures:
        return 'SIGNATURE'
    if a.status!='ACTIVE':
        return 'STATUS'
    if b['recordVersion']!=a.current_version or b['recordVersion']<a.minimum_version or record_identity(e)!=a.current_digest:
        return 'VERSION'
    if b['requestBindingSHA256']!=a.request_binding:
        return 'REPLAY'
    if not (0<=a.upper-a.lower<=1 and a.key_before<=b['issuedAt']<a.key_after and a.key_before<=a.lower<=a.upper<a.key_after and a.checked<=a.lower<=a.upper<a.status_expires and a.upper-a.checked<=120 and a.ticket_issued<=b['issuedAt']<=a.lower<=a.upper<a.ticket_expires and a.upper<b['validUntil'] and a.upper-b['issuedAt']<=120):
        return 'TIME'
    expected=_parse(a.facts)
    if f!=expected or f['cohortScopeSHA256']!=b['scopeSHA256'] or f['binaryVCSModified'] or f['binaryVCSRevision']!=f['sourceSHA'] or f['reviewTargetSHA']!=f['sourceSHA']:
        return 'PROVENANCE'
    if canonical(b['ciRuns'])!=a.ci:
        return 'CI'
    actual_steps={}
    for run in b['ciRuns']:
        if run['headSHA']!=f['sourceSHA'] or run['conclusion']!='success':
            return 'CI'
        for job in run['jobs']:
            if job['conclusion']!='success':
                return 'CI'
            for step in job['steps']:
                actual_steps[(run['runId'],job['name'],step['number'],step['name'])]=step['conclusion']
    required=set(a.required_steps);optional=set(a.allowed_skips)
    if not required or required&optional or len(required)!=len(a.required_steps) or len(optional)!=len(a.allowed_skips) or set(actual_steps)!=required|optional:
        return 'CI'
    if any(actual_steps.get(k)!='success' for k in required) or any(actual_steps[k] not in ('success','skipped') for k in optional):
        return 'CI'
    if sha(policy_bytes)!=f['policyPayloadSHA256'] or sha(artifact_bytes)!=f['artifactZipSHA256'] or len(artifact_bytes)!=f['artifactZipBytes']:
        return 'ARTIFACT'
    if not (f['binarySHA256']==f['installationBinarySHA256']==f['runningBinarySHA256'] and f['sourceSHA']==f['installationSourceSHA']==f['runningSourceSHA'] and f['installationReceiptSHA256']==f['runningReceiptSHA256'] and f['runtimeLockSHA256']==f['runningRuntimeLockSHA256'] and f['linkedClosureSHA256']==f['runningLinkedClosureSHA256']):
        return 'INSTALLATION'
    if not a.v0 or a.v0!=a.v1:
        return 'READBACK'
    return ''

def evaluate(raw,policy_bytes,artifact_bytes,already_bound_synthetic_inputs):
    try:
        reason=_evaluate(raw,policy_bytes,artifact_bytes,already_bound_synthetic_inputs)
    except (ValueError,UnicodeError,RecursionError,TypeError,KeyError,OverflowError):
        reason='FORMAT'
    assert not reason or reason in REASONS
    return ModelResult('REFUSE' if reason else 'SYNTHETIC_ALREADY_BOUND',reason)

def production_projection(_model_result):
    # There is no registered anchor/verifier/producer or positive factory here.
    return PUBLIC_REFUSAL
