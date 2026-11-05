"""Rev3 schema/static/SYMBOLIC authority model; no real keys or system actions.

All mock signature bindings are digest+signer LABELS, never Ed25519 proof. Attacks
recompute dependent digests so semantic rejection cannot hide behind a stale hash.
"""
from copy import deepcopy
from pathlib import Path
import base64
import csv
import hashlib
import ipaddress
import json
import re
import sys

from jsonschema import Draft202012Validator

E=Path(__file__).resolve().parent
SCHEMA=json.loads((E/'contract.schema.json').read_bytes())
NOW=2000000000
H='a'*64
USE_PUB_HEX='11'*32  # SYNTHETIC public encoding, no real signing key/provenance
USE_KEY_HASH=hashlib.sha256(bytes.fromhex(USE_PUB_HEX)).hexdigest()
RESULTS=[]


def check(name, actual, expected):
    RESULTS.append({'name':name,'actual':actual,'expected':expected,'passed':actual==expected})


def no_float(obj):
    if type(obj) is float:return False
    if isinstance(obj,dict):return all(no_float(v) for v in obj.values())
    if isinstance(obj,list):return all(no_float(v) for v in obj)
    return True


def shape(kind,obj):
    if not no_float(obj):return False
    return Draft202012Validator({'$schema':SCHEMA['$schema'],'$defs':SCHEMA['$defs'],'$ref':'#/$defs/'+kind}).is_valid(obj)


def strings_valid(obj):
    if isinstance(obj,str):
        return all(not (ord(c)<32 or ord(c)==127 or 0xd800<=ord(c)<=0xdfff) for c in obj)
    if isinstance(obj,dict):return all(strings_valid(k) and strings_valid(v) for k,v in obj.items())
    if isinstance(obj,list):return all(strings_valid(v) for v in obj)
    return True


def canonical(obj):
    if not strings_valid(obj):raise ValueError('control/surrogate')
    s=json.dumps(obj,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    for old,new in [('&','\\u0026'),('<','\\u003c'),('>','\\u003e'),('\u2028','\\u2028'),('\u2029','\\u2029')]:s=s.replace(old,new)
    return s.encode('utf-8','strict')


def strict_json(raw):
    def pairs(items):
        out={}
        for k,v in items:
            if k in out:raise ValueError('duplicate')
            out[k]=v
        return out
    def nofloat(_):raise ValueError('noninteger')
    obj=json.loads(raw.decode('utf-8','strict'),object_pairs_hook=pairs,parse_float=nofloat,parse_constant=nofloat)
    if not strings_valid(obj):raise ValueError('invalid string')
    return obj


def fullhex(s,size):
    return type(s) is str and len(s)==size and all(c in '0123456789abcdef' for c in s)


def seal(domain,body,signer):
    return {'body':deepcopy(body),'MOCK_signer':signer,'MOCK_input_sha256':hashlib.sha256(domain.encode('ascii')+b'\0'+canonical(body)).hexdigest()}


def signed(obj,domain,signer):
    try:return obj==seal(domain,obj['body'],signer)
    except (KeyError,ValueError,TypeError,UnicodeError):return False


def tuple_value():
    return {'nodeId':'node-0','cohortId':'cohort','operationId':'operation','epoch':'epoch','C':8,'R':2,'P':103,
            **{k:H for k in ['DER','configSha256','policySha256','imageSha256','exeSha256','peerFloorSha256','storageFloorSha256']},
            'root':{'deviceMajorHex8':'00000008','deviceMinorHex8':'00000001','inodeHex16':'0000000000000100','filesystem':'ext4','contextId':'vm-fixture','uid':0,'modeOctal4':'0750'},
            'generation':'boot.pidstart.fresh-start-nonce','gateId':'gate-1'}


def make_chain(t=None,release_signer='protected-release',use_signer='delegated-use',issued=NOW,expires=NOW+60,release_end=NOW+3600,delegation_end=NOW+1800,release_label=None):
    t=deepcopy(t or tuple_value())
    release=seal('saintvision/node-role-release/v1',{'tuple':t,'issuedAt':NOW-100,'expiresAt':release_end,'approvalId':'approval','candidateSha256':H,'useKeySha256':USE_KEY_HASH},release_signer)
    if release_label is not None:release=seal('saintvision/node-role-release/v1',{**release['body'],'displayLabel':release_label},release_signer)
    rh=hashlib.sha256(canonical(release)).hexdigest()
    delegation=seal('saintvision/node-role-delegation/v1',{'releaseSha256':rh,'nodeId':t['nodeId'],'generation':t['generation'],'useKeySha256':USE_KEY_HASH,'usePublicKeyHex64':USE_PUB_HEX,'caller':'cp.execution','purposes':['EXECUTION'],'issuedAt':NOW-100,'expiresAt':delegation_end},release_signer)
    body={'schemaVersion':'saintvision-node-role-use:1','releaseSha256':rh,'delegationSha256':hashlib.sha256(canonical(delegation)).hexdigest(),'tuple':t,'purpose':'EXECUTION','method':'POST','path':'/v1/executions','bodySha256':H,'nonce':'c'*64,'issuedAt':issued,'expiresAt':expires}
    return {'release':release,'delegation':delegation,'use':seal('saintvision/node-role-use/v1',body,use_signer)}


def valid_chain(chain,current=None,approval=None,fenced=False,lease_end=NOW+300,caller='cp.execution'):
    try:
        r,d,u=chain['release'],chain['delegation'],chain['use'];rb,db,ub=r['body'],d['body'],u['body']
        current=current or tuple_value();approval=approval or tuple_value()
        if fenced or not strings_valid(chain) or not shape('roleUse',ub) or not shape('release',rb) or not shape('delegation',db):return False
        if not (signed(r,'saintvision/node-role-release/v1','protected-release') and signed(d,'saintvision/node-role-delegation/v1','protected-release') and signed(u,'saintvision/node-role-use/v1','delegated-use')):return False
        if rb['tuple']!=current or ub['tuple']!=current:return False
        # Approval pins static scope; only protected readmission can bind a new generation.
        if any(current[k]!=approval[k] for k in current if k not in ('generation','gateId')):return False
        if (ub['releaseSha256']!=hashlib.sha256(canonical(r)).hexdigest() or db['releaseSha256']!=ub['releaseSha256'] or ub['delegationSha256']!=hashlib.sha256(canonical(d)).hexdigest()):return False
        if db['nodeId']!=current['nodeId'] or db['generation']!=current['generation'] or rb['useKeySha256']!=db['useKeySha256'] or db['useKeySha256']!=USE_KEY_HASH or hashlib.sha256(bytes.fromhex(db['usePublicKeyHex64'])).hexdigest()!=db['useKeySha256']:return False
        if caller!=db['caller'] or ub['purpose'] not in db['purposes']:return False
        scope={'EXECUTION':'/v1/executions','MODEL':'/v1/executions','TRANSFER':'/v1/objects/read','TERMINAL':'/v1/terminals/frame','STORAGE_COLLECT':'/v1/storage/sample'}
        if scope.get(ub['purpose'])!=ub['path']:return False
        if any(type(b[k]) is not int for b in (rb,db,ub) for k in ('issuedAt','expiresAt')):return False
        if not (0<ub['expiresAt']-ub['issuedAt']<=120 and ub['issuedAt']<=NOW<ub['expiresAt']):return False
        if not (0<rb['expiresAt']-rb['issuedAt']<=86400 and rb['expiresAt']<=NOW+4000 and db['issuedAt']<db['expiresAt']<=rb['expiresAt']):return False
        if not (rb['issuedAt']<=db['issuedAt']<=ub['issuedAt'] and ub['expiresAt']<=min(db['expiresAt'],rb['expiresAt'],lease_end,NOW+4000)):return False
        return True
    except (KeyError,ValueError,TypeError):return False


def selected_valid(selected,members,eligible):
    return (type(selected) is list and bool(selected) and all(type(n) is str for n in selected)
            and len(set(selected))==len(selected) and set(selected)<=set(members) and set(selected)<=set(eligible))


def lane(path,cp_auth=True,epoch=True,permit=True,safety=False,recorded=True,method='POST',raw_query='',raw_path='',gate_authority=False):
    if not cp_auth or not epoch or method!='POST' or raw_query or raw_path:return 'DENY'
    if path=='/v1/roles/gate':return 'PROTECTED_GATE_CONTROL_ONLY' if gate_authority else 'DENY'
    if path in ('/v1/heartbeats','/v1/snapshots','/v1/roles/observe'):return 'OBSERVE_NO_BUSINESS'
    if path=='/v1/executions/receipts':return 'RECONCILE_EXISTING_ONLY' if permit and recorded else 'DENY'
    if path in ('/v1/executions/cancel','/v1/builds/quarantine'):return 'SAFETY_ONLY' if safety and permit else 'DENY'
    return 'BUSINESS_CHAIN_REQUIRED' if path in ('/v1/executions','/v1/objects/read','/v1/terminals/frame','/v1/storage/sample') else 'DENY'


def readmit(old,new,approval_valid=True,fence=False,protected=True):
    return (approval_valid and not fence and protected and strings_valid(new) and shape('tuple',new)
            and all(old[k]==new[k] for k in old if k not in ('generation','gateId')))


def capability():
    fields=SCHEMA['$defs']['capability']['properties'];c={k:1 for k in fields}
    c.update(producer={'producerId':'independent-probe','artifactSha256':H,'version':'v1','observedAt':NOW,'nonce':H,'proofSha256':H},contextKind='managed-separate-kernel-linux-vm-v1',hostId='host-fixture',vmUuid='vm-fixture',hostKernelId='host-kernel',vmKernelBootId='guest-kernel',nodeKernelBootId='guest-kernel',hypervisor='hyperv',hostOS='windows',hostLogicalCpus=8,hostCpuAvailableMilliCpus=4000,
             hostPhysicalTotalBytes=16*2**30,hostPhysicalAvailableBytes=8*2**30,hostCommitLimitBytes=32*2**30,hostCommitAvailableBytes=8*2**30,hostDiskCapacityBytes=100*2**30,hostDiskAvailableBytes=40*2**30,
             vmVcpus=2,vmRamBytes=4*2**30,vmDiskBytes=20*2**30,vmPhysicalAvailableBytes=3*2**30,vmCommitAvailableBytes=3*2**30,guestNativeFsAvailableBytes=5*2**30,root=tuple_value()['root'],socketPath='/var/run/docker.sock',engineApi='1.45',engineVersion='fixture-approved-engine',engineId='guest-daemon',sourceAncestry=['ext4'],routes=[{'interfaceId':'vm-net','destination':'198.51.100.0/24','gateway':'198.51.100.1','producerRef':'independent-probe'}],ports=[{'port':7443,'owner':'fixture-planned-node','reservedFor':'node-0'}],endpointTests=[{'targetId':'fixture-cp','routeInterface':'vm-net','tcpLatencyMillis':1,'tlsPeerSha256':H,'status':'CONNECTED_TLS_VERIFIED','observedAt':NOW}])
    c.update(hostProducer=deepcopy(c['producer']),vmProducer=deepcopy(c['producer']),launcherAdapterSha256=H,vmCpuCapacityMilliCpus=2000,vmCpuAvailableMilliCpus=1500)
    return c


def budget_value():
    return seal('saintvision/context-budget/v1',{'contextId':'vm-fixture','hostId':'host-fixture','vmUuid':'vm-fixture','vcpus':2,'guestRamBytes':4*2**30,'guestDiskBytes':20*2**30,'hostMemoryHeadroomBytes':2*2**30,'hostDiskHeadroomBytes':10*2**30,'guestNativeFreeMinBytes':2**30,'hostCpuSpareMinMilliCpus':1000,'expiresAt':NOW+3600},'protected-release')


def cap_valid(c,budget=None):
    if not shape('capability',c) or not strings_valid(c):return False
    if budget is None or not signed(budget,'saintvision/context-budget/v1','protected-release'):return False
    b=budget['body']
    if not shape('budget',b):return False
    if b['expiresAt']<=NOW or b['contextId']!=c['root']['contextId'] or b['hostId']!=c['hostId'] or b['vmUuid']!=c['vmUuid']:return False
    if not shape('capability',c) or not strings_valid(c):return False
    if any(not NOW-30<=c[k]['observedAt']<=NOW for k in ('producer','hostProducer','vmProducer')):return False
    if c['nodeKernelBootId']!=c['vmKernelBootId'] or c['vmKernelBootId']==c['hostKernelId']:return False
    if c['hostPhysicalAvailableBytes']<b['guestRamBytes']+b['hostMemoryHeadroomBytes'] or c['hostCommitAvailableBytes']<b['guestRamBytes']+b['hostMemoryHeadroomBytes'] or c['hostDiskAvailableBytes']<b['guestDiskBytes']+b['hostDiskHeadroomBytes']:return False
    if c['vmVcpus']<b['vcpus'] or c['vmRamBytes']<b['guestRamBytes'] or c['vmDiskBytes']<b['guestDiskBytes'] or c['guestNativeFsAvailableBytes']<b['guestNativeFreeMinBytes'] or c['hostCpuAvailableMilliCpus']<b['hostCpuSpareMinMilliCpus']:return False
    if c['vmCpuCapacityMilliCpus']!=c['vmVcpus']*1000 or c['vmCpuAvailableMilliCpus']>c['vmCpuCapacityMilliCpus'] or c['hostCpuAvailableMilliCpus']>c['hostLogicalCpus']*1000 or c['vmPhysicalAvailableBytes']>c['vmRamBytes']:return False
    if c['hostPhysicalAvailableBytes']>c['hostPhysicalTotalBytes'] or c['hostCommitAvailableBytes']>c['hostCommitLimitBytes'] or c['hostDiskAvailableBytes']>c['hostDiskCapacityBytes']:return False
    if len({p['port'] for p in c['ports']})!=len(c['ports']) or any(p['owner']!='fixture-planned-node' or p['reservedFor']!='node-0' for p in c['ports']):return False
    if any(not NOW-30<=t['observedAt']<=NOW or t['routeInterface'] not in [r['interfaceId'] for r in c['routes']] for t in c['endpointTests']):return False
    try:
        for r in c['routes']:ipaddress.ip_network(r['destination'],strict=True)
    except ValueError:return False
    return True


def workload_valid(host):
    a=json.loads((E/'workload-allowlist.json').read_bytes());keys=set(a['requiredExact'])|set(a['neutralExact'])|set(a['permitBound'])|set(a['specialExact'])
    return set(host)==keys and all(exact_value(host[k],v) for k,v in {**a['requiredExact'],**a['neutralExact']}.items()) and all(type(host[k]) is int for k in ('Memory','MemorySwap','NanoCpus')) and host['Memory']==host['MemorySwap']==536870912 and host['NanoCpus']==1000000000 and host['DeviceRequests']==[] and host['Tmpfs']=='FIXTURE_EXACT_EXISTING_TMPFS' and host['MaskedPaths']==['FIXTURE_FROZEN_DAEMON_MASKS'] and host['ReadonlyPaths']==['FIXTURE_FROZEN_DAEMON_READONLY']


def exact_value(actual,expected):
    if type(actual) is not type(expected):return False
    if isinstance(expected,dict):return set(actual)==set(expected) and all(exact_value(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):return len(actual)==len(expected) and all(exact_value(a,b) for a,b in zip(actual,expected))
    return actual==expected


def token_syntax(token):
    try:
        if not shape('token',token) or not token.isascii():return False
        _,payload,signature=token.split('.')
        if len(payload)%4==1 or not fullhex(signature,128):return False
        raw=base64.b64decode(payload+'='*((-len(payload))%4),altchars=b'-_',validate=True)
        if base64.urlsafe_b64encode(raw).rstrip(b'=').decode()!=payload:return False
        body=strict_json(raw)
        return raw==canonical(body) and shape('roleUse',body)
    except (ValueError,UnicodeError,TypeError):return False


class ReplayModel:
    def __init__(self,generation,cap=3):self.generation=generation;self.cap=cap;self.entries={};self.sequence=0
    def consume(self,nonce,expiry,now,generation,sequence=None):
        if generation!=self.generation or not fullhex(nonce,64) or type(expiry) is not int or not now<expiry<=now+120:return False
        if sequence is not None and (type(sequence) is not int or sequence!=self.sequence):return False
        self.entries={n:e for n,e in self.entries.items() if e+30>=now}
        if nonce in self.entries or len(self.entries)>=self.cap:return False
        self.entries[nonce]=expiry
        if sequence is not None:self.sequence+=1
        return True


def main():
    Draft202012Validator.check_schema(SCHEMA)
    original=make_chain();check('symbolic-chain-positive',valid_chain(original),True)
    check('legitimate-Unicode-release-chain',valid_chain(make_chain(release_label='A<&>\u2028e\u0301')),True)
    check('online-key-cannot-sign-release-even-with-rebound-hashes',valid_chain(make_chain(release_signer='delegated-use')),False)
    check('wrong-use-signer-rebound',valid_chain(make_chain(use_signer='protected-release')),False)
    for field in ('epoch','C','R','P','configSha256','policySha256','imageSha256','exeSha256','peerFloorSha256','storageFloorSha256'):
        t=tuple_value();t[field]=t[field]+1 if type(t[field]) is int else 'b'*64
        check('approval-scope-change-'+field,valid_chain(make_chain(t),current=t),False)
    t=tuple_value();t['root']['inodeHex16']='0000000000000200'
    check('root-substitution-all-hashes-rebound',valid_chain(make_chain(t),current=t),False)
    for issued,expires,name in [(NOW,NOW-1,'backward'),(NOW,NOW,'zero'),(NOW,NOW+121,'121'),(NOW,NOW+1000000000,'huge'),(NOW+1,NOW+2,'future'),(True,NOW+2,'bool'),(float(NOW),NOW+2,'float')]:
        check('time-'+name,valid_chain(make_chain(issued=issued,expires=expires)),False)
    check('new-lease-300-vs-token-120-separate',valid_chain(make_chain(expires=NOW+120),lease_end=NOW+300),True)
    check('token-120-positive',valid_chain(make_chain(expires=NOW+120)),True)
    check('admission-shorter-than-token',valid_chain(original,lease_end=NOW+30),False)
    check('protected-release-cannot-exceed-approval-rebound',valid_chain(make_chain(release_end=NOW+5000)),False)
    check('delegation-cannot-exceed-release-rebound',valid_chain(make_chain(delegation_end=NOW+3700)),False)
    check('delegation-expired-rebound',valid_chain(make_chain(delegation_end=NOW-1)),False)
    check('fenced-business-denied',valid_chain(original,fenced=True),False)
    check('unauthenticated-caller-label-denied',valid_chain(original,caller='cp.model'),False)
    for suffix in ('\n','\r','\0','x','\u2028'):
        check('hash-full-string-'+repr(suffix),shape('hash',H+suffix),False)
    check('hash-63',shape('hash','a'*63),False);check('hash-65',shape('hash','a'*65),False)
    check('hash-byte-loop-positive',fullhex(H,64),True)
    check('device8-positive',fullhex('00000008',8),True);check('inode16-positive',fullhex('0000000000000100',16),True)
    token='v1.YWJj.'+'a'*128
    check('token-shape-positive-only',shape('token',token),True)
    for suffix in ('\n','\0','extra','\u2028'):check('token-full-string-'+repr(suffix),shape('token',token+suffix),False)
    goodtoken='v1.'+base64.urlsafe_b64encode(canonical(original['use']['body'])).rstrip(b'=').decode()+'.'+'a'*128
    check('token-strict-framing-positive-NO_CRYPTO_CLAIM',token_syntax(goodtoken),True)
    for bad in ('v1.A.'+'a'*128,goodtoken+'\n',goodtoken.replace('v1.','v1.=',1),token):check('token-semantic-decode-deny-'+str(len(RESULTS)),token_syntax(bad),False)
    for raw in (b'"\xff"',b'{"x":"\\ud800"}',b'{"x":"\\u0000"}',b'{"x":1,"x":2}',b'{"x":1.0}',b'{"x":1e2}'):
        try:strict_json(raw);ok=True
        except (ValueError,UnicodeError):ok=False
        check('strict-bytes-'+raw.hex(),ok,False)
    label={'displayLabel':'A<&>\u2028\u2029e\u0301'}
    expected=b'{"displayLabel":"A\\u003c\\u0026\\u003e\\u2028\\u2029e\xcc\x81"}'
    check('legitimate-Unicode-C2-no-NFC',canonical(label)==expected,True)
    check('composed-differs-no-NFC',canonical({'displayLabel':'\u00e9'})!=canonical({'displayLabel':'e\u0301'}),True)
    check('signature-domain-single-NUL-no-LF',hashlib.sha256(b'domain\0'+canonical(label)).hexdigest()==seal('domain',label,'fixture')['MOCK_input_sha256'],True)
    members=['node-'+str(i) for i in range(5)]
    for selection in ([],['node-0','node-0'],['foreign'],[0],[999],['node-0',None],None):check('selection-deny-'+repr(selection),selected_valid(selection,members,members),False)
    check('selected-healthy-unrelated-offline',selected_valid(['node-0'],members,['node-0']),True)
    new=tuple_value();new['generation']='fresh-restart-nonce';new['gateId']='new-protected-gate'
    check('per-node-same-config-readmit',readmit(tuple_value(),new),True)
    check('readmit-during-fence-deny',readmit(tuple_value(),new,fence=True),False)
    check('readmit-expired-approval-deny',readmit(tuple_value(),new,approval_valid=False),False)
    check('readmit-online-cannot-authorize',readmit(tuple_value(),new,protected=False),False)
    check('old-generation-token-deny',valid_chain(original,current=new),False)
    check('new-protected-generation-release-positive',valid_chain(make_chain(new),current=new),True)
    for field in ('epoch','C','R','P','configSha256','policySha256'):
        changed=deepcopy(new);changed[field]=('changed' if type(changed[field]) is str else changed[field]+1)
        check('readmit-changed-'+field,readmit(tuple_value(),changed),False)
    for path in ('/v1/heartbeats','/v1/snapshots','/v1/roles/observe'):
        check('observe-without-business-'+path,lane(path),'OBSERVE_NO_BUSINESS')
    check('receipts-fenced-or-expired-business-still-reconcile',lane('/v1/executions/receipts'),'RECONCILE_EXISTING_ONLY')
    check('observe-query-alias-deny',lane('/v1/roles/observe',raw_query='x=1'),'DENY')
    check('observe-rawpath-deny',lane('/v1/roles/observe',raw_path='/v1/roles/%6fbserve'),'DENY')
    check('observe-wrong-method-deny',lane('/v1/roles/observe',method='GET'),'DENY')
    check('unknown-path-deny',lane('/v1/unknown'),'DENY')
    check('gate-without-protected-authority-deny',lane('/v1/roles/gate'),'DENY')
    check('gate-protected-only',lane('/v1/roles/gate',gate_authority=True),'PROTECTED_GATE_CONTROL_ONLY')
    check('receipts-unseen-no-execution',lane('/v1/executions/receipts',recorded=False),'DENY')
    check('receipts-bad-epoch-deny',lane('/v1/executions/receipts',epoch=False),'DENY')
    check('receipts-no-TLS-deny',lane('/v1/executions/receipts',cp_auth=False),'DENY')
    for path in ('/v1/executions/cancel','/v1/builds/quarantine'):
        check('safety-no-authority-'+path,lane(path),'DENY');check('typed-safety-'+path,lane(path,safety=True),'SAFETY_ONLY')
    replay=ReplayModel('fresh-generation')
    check('stream-opener',replay.consume('1'*64,NOW+60,NOW,'fresh-generation',0),True)
    check('duplicate-nonce',replay.consume('1'*64,NOW+60,NOW,'fresh-generation',1),False)
    check('sequence-gap-deny',replay.consume('2'*64,NOW+60,NOW,'fresh-generation',2),False)
    check('frame-sequence-next',replay.consume('2'*64,NOW+60,NOW,'fresh-generation',1),True)
    check('old-generation-token',replay.consume('3'*64,NOW+60,NOW,'old-generation',2),False)
    check('next-frame',replay.consume('3'*64,NOW+60,NOW,'fresh-generation',2),True)
    check('replay-cap-no-live-eviction',replay.consume('4'*64,NOW+60,NOW,'fresh-generation',3),False)
    check('expiry-GC-reclaims-only-expired',replay.consume('4'*64,NOW+160,NOW+100,'fresh-generation',3),True)
    check('expired-frame-deny',replay.consume('5'*64,NOW+60,NOW+100,'fresh-generation',4),False)
    phases=json.loads((E/'phase-authority-matrix.json').read_bytes())['cases']
    for row in phases:
        if row['phase']!='BEFORE_INTENT':check('partial-'+row['phase']+'-'+row['event'],row['fence'] and row['business']=='DENY_ALL_FIVE' and row['newOrdinaryIntent'] is False,True)
        if row['phase']!='BEFORE_INTENT' and row['next']=='B_RECOVERY1_REVIEWED_GATE':check('invalid-authority-no-replay-'+row['phase']+'-'+row['event'],row['sameIntentReplay'],False)
    cap=capability();budget=budget_value();check('raw-capability-positive-SYNTHETIC',cap_valid(cap,budget),True)
    check('unapproved-budget-deny',cap_valid(cap),False)
    badbudget=deepcopy(budget);badbudget['MOCK_signer']='delegated-use'
    check('online-issuer-cannot-approve-budget',cap_valid(cap,badbudget),False)
    for field,value in [('contextKind','wsl2-ext4-dedicated-engine-v1'),('hostPhysicalAvailableBytes',125*2**20),('hostCommitAvailableBytes',2**30),('hostDiskAvailableBytes',20*2**30),('vmVcpus',1),('vmRamBytes',2**30),('vmKernelBootId','host-kernel'),('nodeKernelBootId','other'),('sourceAncestry',['9p']),('engineApi','1.41')]:
        changed=deepcopy(cap);changed[field]=value;changed['producer']['proofSha256']=hashlib.sha256(canonical(changed)).hexdigest()
        check('rebound-capability-'+field,cap_valid(changed,budget),False)
    a=json.loads((E/'workload-allowlist.json').read_bytes());host={**a['requiredExact'],**a['neutralExact'],'Memory':536870912,'MemorySwap':536870912,'NanoCpus':1000000000,'DeviceRequests':[],'Tmpfs':'FIXTURE_EXACT_EXISTING_TMPFS','MaskedPaths':['FIXTURE_FROZEN_DAEMON_MASKS'],'ReadonlyPaths':['FIXTURE_FROZEN_DAEMON_READONLY']}
    check('closed-workload-positive-SYNTHETIC',workload_valid(host),True)
    for field,value in [('CapAdd',['SYS_ADMIN']),('UsernsMode','host'),('Sysctls',{'x':'y'}),('Runtime','other'),('VolumeDriver','plugin'),('CgroupParent','host'),('Mounts',[{}]),('VolumesFrom',['other']),('UnknownFutureField',False),('Privileged',0),('Memory',536870912.0)]:
        changed=deepcopy(host);changed[field]=value;check('workload-closed-'+field,workload_valid(changed),False)
    ledger=json.loads((E/'callsite-locks.json').read_bytes());csvrows=list(csv.DictReader((E/'callsite-locks.csv').read_text(encoding='utf-8').splitlines()))
    check('callsite-count-consistent',len(csvrows)==ledger['callsiteCount'],True)
    check('explicit-expression-disposition-not-path-heuristic',set(ledger['dynamicExpressions'])==set(ledger['explicitExpressionResolutions']) and not ledger['unresolvedExpressionIds'],True)
    check('epoch-first-kept',ledger['rank0OuterGuards'][0].startswith('control_epoch'),True)
    result={'version':'fleet5-b-rev3-fixtures:1','level':'SCHEMA_STATIC_SYMBOLIC_ONLY_NOT_ED25519_OR_RUNTIME','python':sys.version,'passed':sum(x['passed'] for x in RESULTS),'failed':sum(not x['passed'] for x in RESULTS),'realGo':0,'realPG':0,'realDocker':0,'realPhysical':0,'cases':RESULTS}
    (E/'fixture-results.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
    (E/'synthetic-positive-fixtures.json').write_bytes((json.dumps({'WARNING':'SYNTHETIC/SYMBOLIC, ALL REAL BINDINGS NULL','chain':original,'capability':cap,'SYNTHETIC_approvedBudget':budget,'workload':host},indent=2)+'\n').encode())
    print(json.dumps({k:v for k,v in result.items() if k!='cases'}))
    if result['failed']:
        print(json.dumps([x for x in RESULTS if not x['passed']]));raise SystemExit(1)


if __name__=='__main__':main()
