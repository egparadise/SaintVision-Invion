"""STATEFUL SYMBOLIC CONTRACT MODEL ONLY. No keys/crypto/DB/Node operations.

Mock signatures are role-labelled hashes, not Ed25519 or custody evidence.
"""
from copy import deepcopy
from pathlib import Path
import base64
import hashlib
import json
import re

from jsonschema import Draft202012Validator
from authority import DOMAINS,OP,VER,ISS,DEL
from schema import build

NOW=2000000000;Z='0'*64;H='a'*64
SCHEMA=build()


def strict_strings(x):
    if isinstance(x,str):return all(not(ord(c)<32 or ord(c)==127 or 0xd800<=ord(c)<=0xdfff) for c in x)
    if isinstance(x,dict):return all(strict_strings(k) and strict_strings(v) for k,v in x.items())
    if isinstance(x,list):return all(strict_strings(v) for v in x)
    return type(x) is not float


def canonical(x):
    if not strict_strings(x):raise ValueError('invalid UTF8/control/surrogate/float')
    s=json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    for a,b in [('&',r'\u0026'),('<',r'\u003c'),('>',r'\u003e'),('\u2028',r'\u2028'),('\u2029',r'\u2029')]:s=s.replace(a,b)
    return s.encode('utf-8','strict')


def digest(x):return hashlib.sha256(canonical(x)).hexdigest()


def shape(kind,x):
    return strict_strings(x) and Draft202012Validator({'$defs':SCHEMA['$defs'],'$ref':'#/$defs/'+kind}).is_valid(x)


def seal(kind,body,signer=None,domain=None):
    expected=DOMAINS[kind][1];domain=domain or DOMAINS[kind][0]
    return {'kind':kind,'body':deepcopy(body),'MOCK_signer':signer or expected,'MOCK_domain':domain,'MOCK_digest':hashlib.sha256(domain.encode('ascii')+b'\0'+canonical(body)).hexdigest()}


def verified(a,kind,signer=None):
    try:return a==seal(kind,a['body'],signer or DOMAINS[kind][1])
    except (KeyError,ValueError,TypeError,UnicodeError):return False


def window(body,now,limit=None):
    a=body.get('issuedAt',body.get('observedAt'));b=body.get('expiresAt')
    return type(a) is int and type(b) is int and a<=now<b and 0<b-a and (limit is None or b-a<=limit)


def make_state():
    prior=json.loads((Path(__file__).parent.parent/'fleet5-b-contract-rev3-20261106-codex/synthetic-positive-fixtures.json').read_bytes())
    static={k:v for k,v in prior['chain']['release']['body']['tuple'].items() if k not in ('operationId','generation','gateId')};static['tenantId']='tenant-fixture'
    grant={'grantId':'operator-current','nodeIds':[static['nodeId']],'staticHash':digest(static),'purposes':['FRESH_ACTIVATE','APPROVAL_RENEW_SAME_CONFIG','REAPPROVE_SAME_CONFIG','READMIT_SAME_CONFIG'],'issuedAt':NOW-86400,'expiresAt':NOW+172800,'revoked':False}
    trust={'nodeDER':static['DER'],'nodeCertificateNotBefore':NOW-86400,'nodeCertificateNotAfter':NOW+172800,'operatorTrustNotBefore':NOW-86400,'operatorTrustNotAfter':NOW+172800,'cpTrustNotAfter':NOW+172800,'revoked':False}
    return {'now':NOW,'static':static,'frozenStatic':deepcopy(static),'grant':grant,'trust':trust,'cohortFence':False,'quarantined':False,'containment':False,'revokedApprovals':set(),'otherWorkers':'OFFLINE_NOT_A_DEPENDENCY','cpAuthenticated':True,'quiescenceKnown':True,'node':{'generation':'generation-0','gate':None,'recordId':Z,'records':{}},'approvals':{},'gateAcks':{},'ledgers':{},'challenges':{},'receipts':{},'current':None,'switchPending':False,'issuer':{'id':'registered-issuer','tlsHash':'b'*64}}


def trust_end(s):return min(s['trust'][k] for k in ('nodeCertificateNotAfter','operatorTrustNotAfter','cpTrustNotAfter'))


def live_authority(s):
    return (s['static']==s['frozenStatic'] and s['grant']['staticHash']==digest(s['static']) and s['static']['nodeId'] in s['grant']['nodeIds'] and not s['grant']['revoked'] and not s['trust']['revoked'] and window(s['grant'],s['now']) and max(s['trust']['nodeCertificateNotBefore'],s['trust']['operatorTrustNotBefore'])<=s['now']<trust_end(s) and not(s['cohortFence'] or s['quarantined'] or s['containment']))


def candidate(s):
    return {'candidateId':'candidate-'+s['node']['generation'],'static':deepcopy(s['static']),'generation':s['node']['generation'],'nodeProofHash':H,'hostProofHash':'c'*64,'nonce':'d'*64,'observedAt':s['now'],'expiresAt':s['now']+30}


def append_approval(s,purpose,expiry,role=OP,c=None):
    c=c or candidate(s);old=s['current']['approval'] if s['current'] else None
    if role!=OP or s['switchPending'] or (s['current'] is not None and s['current']['receipt'] is None) or not live_authority(s) or purpose not in s['grant']['purposes'] or not shape('candidate',c) or c['static']!=s['static'] or not window(c,s['now'],30):return None
    if old and (digest(old) in s['revokedApprovals'] or old['body']['static']!=s['static']):return None
    if purpose=='APPROVAL_RENEW_SAME_CONFIG' and (old is None or not window(old['body'],s['now'])):return None
    if purpose=='REAPPROVE_SAME_CONFIG' and (old is None or old['body']['expiresAt']>s['now']):return None
    if type(expiry) is not int or not s['now']<expiry<=min(s['now']+86400,s['grant']['expiresAt'],trust_end(s)):return None
    body={'approvalId':'approval-'+str(expiry),'priorApprovalHash':digest(old) if old else Z,'static':deepcopy(s['static']),'operationId':'node-operation-'+str(expiry),'operatorGrantHash':digest(s['grant']),'trustHash':digest(s['trust']),'candidateHash':digest(c),'purpose':purpose,'nonce':H,'issuedAt':s['now'],'expiresAt':expiry}
    result=seal('APPROVAL',body);s['approvals'][digest(result)]=result;return result


def approval_valid(s,a,cp=True):
    if not verified(a,'APPROVAL') or not shape('approval',a['body']) or not window(a['body'],s['now'],86400) or a['body']['static']!=s['static'] or a['body']['expiresAt']>trust_end(s):return False
    if cp and (not live_authority(s) or digest(a) in s['revokedApprovals'] or a['body']['operatorGrantHash']!=digest(s['grant']) or a['body']['trustHash']!=digest(s['trust']) or a['body']['expiresAt']>s['grant']['expiresAt']):return False
    return True


def material(s,a,suffix):
    pub=hashlib.sha256(('SYNTHETIC_PUBLIC_ONLY_'+suffix).encode()).hexdigest();keyhash=hashlib.sha256(bytes.fromhex(pub)).hexdigest()
    end=min(a['body']['expiresAt'],s['grant']['expiresAt'],trust_end(s))
    r=seal('RELEASE',{'releaseId':'release-'+suffix,'approvalHash':digest(a),'static':deepcopy(s['static']),'operationId':a['body']['operationId'],'generation':s['node']['generation'],'gateId':'gate-'+suffix,'activationLedgerId':'activation-'+suffix,'expectedPriorCurrentPointerHash':s['current']['pointerHash'] if s['current'] else Z,'useKeyHash':keyhash,'issuerServiceId':s['issuer']['id'],'issuerTLSHash':s['issuer']['tlsHash'],'issuedAt':s['now'],'expiresAt':end})
    d=seal('DELEGATION',{'delegationId':'delegation-'+suffix,'releaseHash':digest(r),'nodeId':s['static']['nodeId'],'epoch':s['static']['epoch'],'generation':s['node']['generation'],'gateId':r['body']['gateId'],'usePublicKeyHex64':pub,'useKeyHash':keyhash,'issuerServiceId':s['issuer']['id'],'issuerTLSHash':s['issuer']['tlsHash'],'purposes':['EXECUTION','MODEL','TRANSFER','TERMINAL','STORAGE_COLLECT'],'issuedAt':s['now'],'expiresAt':end})
    return {'approval':a,'release':r,'delegation':d}


def command(s,m,action):
    r=m['release']['body'];old=s['node']['gate'];gid=r['gateId'];prior=old['gateId'] if old else 'NONE'
    return seal('GATE_CONTROL',{'action':action,'method':'POST','path':'/v1/roles/gate','staticHash':digest(s['static']),'nodeId':s['static']['nodeId'],'epoch':s['static']['epoch'],'generation':s['node']['generation'],'gateId':gid,'expectedPriorGateId':prior,'releaseHash':digest(m['release']),'delegationHash':digest(m['delegation']),'useKeyHash':r['useKeyHash'],'nonce':digest({'action':action,'gate':gid,'record':s['node']['recordId']}),'issuedAt':s['now'],'expiresAt':min(s['now']+120,trust_end(s))})


def node_command(s,m,cmd):
    b=cmd['body'];old=s['node']['gate'];prior=old['gateId'] if old else 'NONE'
    if not s['cpAuthenticated'] or not verified(cmd,'GATE_CONTROL') or not shape('gateControl',b) or not window(b,s['now'],120) or b['staticHash']!=digest(s['static']) or b['generation']!=s['node']['generation'] or b['expectedPriorGateId']!=prior:return None
    if b['releaseHash']!=digest(m['release']) or b['delegationHash']!=digest(m['delegation']) or b['nodeId']!=s['static']['nodeId'] or b['epoch']!=s['static']['epoch'] or b['gateId']!=m['release']['body']['gateId'] or b['useKeyHash']!=m['release']['body']['useKeyHash']:return None
    if b['action']=='ARM_EXACT_RELEASE':
        if not approval_valid(s,m['approval'],False) or not verified(m['release'],'RELEASE') or not verified(m['delegation'],'DELEGATION') or old and old['state']=='ARMED' or not s['quiescenceKnown']:return None
        state='ARMED'
    else:
        if old is None or old['gateId']!=b['gateId'] or old['state']!='ARMED':return None
        state='INVALIDATED'
    requestHash=digest({'command':cmd,'release':m['release'],'delegation':m['delegation']})
    record={'commandHash':digest(cmd),'priorRecord':s['node']['recordId'],'generation':b['generation'],'state':state,'gateId':b['gateId']};recordId=digest(record)
    ack=seal('GATE_ACK',{'nodeId':s['static']['nodeId'],'tenantId':s['static']['tenantId'],'nodeCertificateSHA256':s['static']['DER'],'action':b['action'],'commandHash':digest(cmd),'requestBodyHash':requestHash,'releaseHash':b['releaseHash'],'delegationHash':b['delegationHash'],'useKeyHash':b['useKeyHash'],'gateId':b['gateId'],'priorGateId':prior,'generation':b['generation'],'epoch':s['static']['epoch'],'static':deepcopy(s['static']),'nonce':b['nonce'],'observedAt':s['now'],'expiresAt':min(s['now']+60,b['expiresAt'],trust_end(s)),'localGateRecordId':recordId,'priorLocalGateRecordId':s['node']['recordId'],'state':state},'NODE:'+s['static']['DER'])
    s['node']['records'][recordId]={'record':record,'ack':ack};s['node']['recordId']=recordId;s['node']['gate']={**record,'releaseHash':b['releaseHash'],'delegationHash':b['delegationHash'],'ackHash':digest(ack)};return ack


def record_ack(s,ack,role=VER):
    try:
        b=ack['body'];local=s['node']['records'].get(b['localGateRecordId'])
        if role not in (OP,VER) or not verified(ack,'GATE_ACK','NODE:'+s['static']['DER']) or not shape('gateAck',b) or not window(b,s['now'],60) or b['nodeCertificateSHA256']!=s['static']['DER'] or b['static']!=s['static'] or b['generation']!=s['node']['generation'] or not local or local['ack']!=ack:return False
        s['gateAcks'][digest(ack)]=ack;return True
    except (KeyError,TypeError):return False


def commit_activation(s,m,ack,role=OP):
    if role!=OP or not approval_valid(s,m['approval']) or digest(ack) not in s['gateAcks'] or not s['node']['gate'] or s['node']['gate']['state']!='ARMED' or s['node']['gate']['releaseHash']!=digest(m['release']) or not window(ack['body'],s['now'],60):return False
    r=m['release']['body']
    if ack['body']['action']!='ARM_EXACT_RELEASE' or ack['body']['state']!='ARMED' or ack['body']['releaseHash']!=digest(m['release']) or ack['body']['delegationHash']!=digest(m['delegation']) or ack['body']['gateId']!=r['gateId'] or ack['body']['localGateRecordId']!=s['node']['recordId'] or s['node']['gate']['ackHash']!=digest(ack):return False
    if r['expectedPriorCurrentPointerHash']!=(s['current']['pointerHash'] if s['current'] else Z):return False
    if s['current'] and digest(m['approval'])!=digest(s['current']['approval']) and m['approval']['body']['priorApprovalHash']!=digest(s['current']['approval']):return False
    lid=r['activationLedgerId'];pointer=digest({'approval':digest(m['approval']),'release':digest(m['release']),'generation':r['generation'],'gateId':r['gateId'],'delivery':None})
    ledger={'id':lid,'releaseHash':digest(m['release']),'delegationHash':digest(m['delegation']),'approvalHash':digest(m['approval']),'gateAckHash':digest(ack),'currentPointerHash':pointer,'committed':True}
    s['ledgers'][lid]=ledger;s['current']={**deepcopy(m),'ack':ack,'ledgerId':lid,'pointerHash':pointer,'lease':{'issuedAt':s['now'],'expiresAt':min(s['now']+300,r['expiresAt'])},'receipt':None};s['switchPending']=False;return True


def delivery_challenge(s,role=DEL):
    cur=s['current']
    if role!=DEL or s['switchPending'] or not cur or not approval_valid(s,cur['approval']) or s['cohortFence'] or not window(cur['ack']['body'],s['now'],60):return None
    r=cur['release']['body'];d=cur['delegation']['body'];ledger=s['ledgers'].get(cur['ledgerId'])
    if not ledger or not ledger['committed'] or s['node']['gate'] is None or s['node']['gate']['ackHash']!=digest(cur['ack']):return None
    cid='challenge-'+cur['ledgerId']
    if cid in s['challenges']:
        existing=s['challenges'][cid]
        return existing['artifact'] if existing['state']=='PREPARED' and window(existing['artifact']['body'],s['now'],60) else None
    body={'deliveryId':'delivery-'+cur['ledgerId'],'challengeId':cid,'activationLedgerId':cur['ledgerId'],'activationLedgerHash':digest(ledger),'releaseHash':digest(cur['release']),'delegationHash':digest(cur['delegation']),'useKeyHash':r['useKeyHash'],'gateAckHash':digest(cur['ack']),'nodeId':s['static']['nodeId'],'cohortId':s['static']['cohortId'],'epoch':s['static']['epoch'],'generation':r['generation'],'gateId':r['gateId'],'staticHash':digest(s['static']),'issuerServiceId':d['issuerServiceId'],'issuerTLSHash':d['issuerTLSHash'],'nonce':digest({'UNPREDICTABLE_32_BYTES_IN_REAL_IMPLEMENTATION':cid}),'issuedAt':s['now'],'expiresAt':min(s['now']+60,r['expiresAt'])}
    result=seal('DELIVERY_CHALLENGE',body);s['challenges'][cid]={'artifact':result,'state':'PREPARED'};return result


def possession(challenge,signer=None,domain=None):return seal('KEY_POSSESSION',{'challengeHash':digest(challenge),'challenge':deepcopy(challenge['body'])},signer or 'USE:'+challenge['body']['useKeyHash'],domain)


def consume_possession(s,ch,pop,authenticatedIssuer=None,role=DEL):
    try:
        b=ch['body'];row=s['challenges'].get(b['challengeId']);cur=s['current'];issuer=authenticatedIssuer or s['issuer']
        if role!=DEL or s['switchPending'] or not row or row['state']!='PREPARED' or row['artifact']!=ch or not verified(ch,'DELIVERY_CHALLENGE') or not shape('deliveryChallenge',b) or not window(b,s['now'],60) or not cur or not approval_valid(s,cur['approval']):return None
        if issuer!={'id':b['issuerServiceId'],'tlsHash':b['issuerTLSHash']} or not verified(pop,'KEY_POSSESSION','USE:'+b['useKeyHash']) or pop['body']!={'challengeHash':digest(ch),'challenge':b}:return None
        if not s['node']['gate'] or s['node']['gate']['state']!='ARMED' or s['node']['gate']['ackHash']!=digest(cur['ack']):return None
        ledger=s['ledgers'].get(b['activationLedgerId'])
        if not ledger or b['activationLedgerId']!=cur['ledgerId'] or digest(ledger)!=b['activationLedgerHash'] or b['releaseHash']!=digest(cur['release']) or b['gateAckHash']!=digest(cur['ack']):return None
        expected={'nodeId':s['static']['nodeId'],'cohortId':s['static']['cohortId'],'epoch':s['static']['epoch'],'staticHash':digest(s['static']),'generation':cur['release']['body']['generation'],'gateId':cur['release']['body']['gateId'],'delegationHash':digest(cur['delegation']),'useKeyHash':cur['release']['body']['useKeyHash'],'issuerServiceId':cur['delegation']['body']['issuerServiceId'],'issuerTLSHash':cur['delegation']['body']['issuerTLSHash']}
        if any(b[k]!=v for k,v in expected.items()):return None
        row['state']='CONSUMED_PENDING_RECEIPT';row['possession']=pop;row['consumptionId']='consume-'+b['challengeId']
        rb={**deepcopy(b),'receiptId':'receipt-'+b['deliveryId'],'challengeHash':digest(ch),'possessionHash':digest(pop),'consumptionLedgerId':row['consumptionId'],'priorCurrentPointerHash':cur['pointerHash'],'priorState':'CONSUMED_PENDING_RECEIPT','currentState':'DELIVERED_CURRENT','issuedAt':s['now'],'expiresAt':min(cur['approval']['body']['expiresAt'],cur['release']['body']['expiresAt'],cur['delegation']['body']['expiresAt'],trust_end(s))}
        draft=seal('KEY_DELIVERY_RECEIPT',rb);row['protectedControllerDraft']=draft;return draft
    except (KeyError,TypeError):return None


def record_delivery(s,receipt,role=DEL):
    try:
        b=receipt['body'];cur=s['current'];row=s['challenges'].get(b['challengeId'])
        if role!=DEL or s['switchPending'] or not verified(receipt,'KEY_DELIVERY_RECEIPT') or not shape('keyDeliveryReceipt',b) or not window(b,s['now']) or not cur or not approval_valid(s,cur['approval']) or not row or row['state']!='CONSUMED_PENDING_RECEIPT':return False
        if any(b[k]!=row['artifact']['body'][k] for k in row['artifact']['body'] if k not in ('issuedAt','expiresAt')) or b['consumptionLedgerId']!=row['consumptionId']:return False
        if b['expiresAt']>min(cur['approval']['body']['expiresAt'],cur['release']['body']['expiresAt'],cur['delegation']['body']['expiresAt'],trust_end(s)):return False
        if b['possessionHash']!=digest(row['possession']) or b['challengeHash']!=digest(row['artifact']) or b['activationLedgerId']!=cur['ledgerId'] or b['activationLedgerHash']!=digest(s['ledgers'][cur['ledgerId']]) or b['priorCurrentPointerHash']!=cur['pointerHash'] or b['releaseHash']!=digest(cur['release']):return False
        row['state']='DELIVERED_CURRENT';s['receipts'][digest(receipt)]=receipt;cur['receipt']=receipt;return True
    except (KeyError,TypeError):return False


def role_use(s,bodyHash=H):
    c=s['current'];r=c['release']['body'];return seal('ROLE_USE',{'releaseHash':digest(c['release']),'delegationHash':digest(c['delegation']),'receiptHash':digest(c['receipt']),'nodeId':s['static']['nodeId'],'epoch':s['static']['epoch'],'generation':r['generation'],'gateId':r['gateId'],'purpose':'EXECUTION','method':'POST','path':'/v1/executions','bodyHash':bodyHash,'nonce':H,'issuedAt':s['now'],'expiresAt':min(s['now']+120,c['delegation']['body']['expiresAt'])},'USE:'+r['useKeyHash'])


def node_accepts(s,c,use,requestBodyHash=H):
    try:
        a,r,d,q,u=[c[k] for k in ('approval','release','delegation','receipt')]+[use];rb=r['body'];db=d['body'];qb=q['body'];ub=u['body'];gate=s['node']['gate']
        if not gate or gate['state']!='ARMED' or gate['generation']!=s['node']['generation'] or gate['releaseHash']!=digest(r):return False
        if not approval_valid(s,a,False) or not verified(r,'RELEASE') or not verified(d,'DELEGATION') or not verified(q,'KEY_DELIVERY_RECEIPT') or not verified(u,'ROLE_USE','USE:'+rb['useKeyHash']):return False
        if not all(shape(k,b) for k,b in [('release',rb),('delegation',db),('keyDeliveryReceipt',qb),('roleUse',ub)]) or not window(ub,s['now'],120) or not window(qb,s['now']):return False
        if rb['approvalHash']!=digest(a) or db['releaseHash']!=digest(r) or rb['static']!=s['static'] or rb['generation']!=s['node']['generation'] or rb['gateId']!=gate['gateId']:return False
        if hashlib.sha256(bytes.fromhex(db['usePublicKeyHex64'])).hexdigest()!=rb['useKeyHash'] or db['useKeyHash']!=rb['useKeyHash']:return False
        expected={'activationLedgerId':rb['activationLedgerId'],'releaseHash':digest(r),'delegationHash':digest(d),'useKeyHash':rb['useKeyHash'],'gateAckHash':gate['ackHash'],'nodeId':s['static']['nodeId'],'cohortId':s['static']['cohortId'],'epoch':s['static']['epoch'],'generation':rb['generation'],'gateId':rb['gateId'],'staticHash':digest(s['static']),'issuerServiceId':db['issuerServiceId'],'issuerTLSHash':db['issuerTLSHash']}
        if any(qb[k]!=v for k,v in expected.items()):return False
        if ub['nodeId']!=s['static']['nodeId'] or ub['epoch']!=s['static']['epoch'] or ub['bodyHash']!=requestBodyHash or ub['purpose'] not in db['purposes']:return False
        if ub['releaseHash']!=digest(r) or ub['delegationHash']!=digest(d) or ub['receiptHash']!=digest(q) or ub['gateId']!=rb['gateId'] or ub['generation']!=rb['generation']:return False
        end=min(a['body']['expiresAt'],rb['expiresAt'],db['expiresAt'],qb['expiresAt'],trust_end(s))
        return rb['expiresAt']<=a['body']['expiresAt'] and db['expiresAt']<=rb['expiresAt'] and ub['expiresAt']<=end
    except (KeyError,ValueError,TypeError):return False


def cp_eligible(s,c,use):
    return bool(s['current'] and not s['switchPending'] and live_authority(s) and window(s['current']['lease'],s['now'],300) and c==s['current'] and c['receipt'] and digest(c['receipt']) in s['receipts'] and approval_valid(s,c['approval']) and node_accepts(s,c,use))


def readmit_allowed(s,c,a=None,role=OP):
    a=a or (s['current']['approval'] if s['current'] else None)
    return bool(role==OP and not s['switchPending'] and s['current'] and s['current']['receipt'] is not None and a and approval_valid(s,a) and shape('candidate',c) and c['static']==s['static'] and window(c,s['now'],30) and c['generation']==s['node']['generation'] and c['generation']!=s['current']['release']['body']['generation'])


def refresh_same_generation(s,c,role=VER):
    if role!=VER or not s['current'] or s['current']['receipt'] is None or s['switchPending'] or not approval_valid(s,s['current']['approval']) or not shape('candidate',c) or not window(c,s['now'],30) or c['static']!=s['static'] or c['generation']!=s['node']['generation'] or c['generation']!=s['current']['release']['body']['generation']:return False
    s['current']['lease']={'issuedAt':s['now'],'expiresAt':min(s['now']+300,s['current']['release']['body']['expiresAt'])};return True


def finish(s,m):
    if s['node']['gate'] and s['node']['gate']['state']=='ARMED':
        old={k:s['current'][k] for k in ('approval','release','delegation')};ack=node_command(s,old,command(s,old,'INVALIDATE_EXACT_GATE'));assert ack and record_ack(s,ack)
    ack=node_command(s,m,command(s,m,'ARM_EXACT_RELEASE'));assert ack and record_ack(s,ack) and commit_activation(s,m,ack)
    ch=delivery_challenge(s);assert ch;receipt=consume_possession(s,ch,possession(ch));assert receipt and record_delivery(s,receipt)
    return role_use(s)


def released_state():
    s=make_state();a=append_approval(s,'FRESH_ACTIVATE',s['now']+600);m=material(s,a,'old');finish(s,m);return s
