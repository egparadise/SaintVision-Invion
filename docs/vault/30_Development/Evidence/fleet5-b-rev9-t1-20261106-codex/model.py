"""Rev6 symbolic CP/adapter/service state model. NO real keys/DB/Node/IO.

Opaque Python identities model trusted installed connection/capability boundaries;
role-labelled digests are NOT Ed25519, TLS, custody or durable filesystem proof.
The existing plain wire is never amended with an obligation field.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from authority import OP,VER,RUN,DEL,SAFE,REV,ISS,BUD,DOMAINS
from catalog import READERS,IO
from io_contract import EFFECT,RECOVERY,fixture_footprint
from schema import build

SCHEMA=build();NOW=2000000000;H='a'*64;Z='0'*64
TEMPLATE=json.loads((Path(__file__).resolve().parent.parent/'fleet5-b-contract-rev4-20261106-codex/stateful-positive.json').read_bytes())['state']


def strict(x):
    if isinstance(x,float):return False
    if isinstance(x,str):
        try:x.encode('utf-8','strict')
        except UnicodeError:return False
        return not any(ord(c)<32 or 127<=ord(c)<=159 for c in x)
    if type(x) is int:return abs(x)<=9007199254740991
    if isinstance(x,list):return all(strict(v) for v in x)
    if isinstance(x,dict):return all(isinstance(k,str) and strict(k) and strict(v) for k,v in x.items())
    return x is None or isinstance(x,bool)


def canonical(x):
    if not strict(x):raise ValueError('strict C2 domain')
    return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def shape(kind,x):return strict(x) and Draft202012Validator({'$defs':SCHEMA['$defs'],'$ref':'#/$defs/'+kind}).is_valid(x)
def scope(t='tenant-1',n='node-1',e='epoch-1'):return {'tenantId':t,'nodeId':n,'epoch':e}
def sk(s):return tuple(s[k] for k in ('tenantId','nodeId','epoch'))


def seal(kind,body,signer='SYMBOLIC_NODE_LEAF',domain=None):
    domain=domain or (DOMAINS[kind][0] if kind in DOMAINS else 'symbolic/existing-kernel-validation')
    return {'kind':kind,'domain':domain,'signer':signer,'body':deepcopy(body),
            'signature':digest({'roleLabel':signer,'domain':domain,'body':body})}


def verified(record,kind,signer,domain=None):
    try:return record==seal(kind,record['body'],signer,domain)
    except (KeyError,TypeError,ValueError):return False


@dataclass(frozen=True)
class Connection:
    service:str
    incarnation:str


@dataclass(frozen=True)
class CommittedIOHandle:
    handle_hash:str


class RetainedWorld:
    def __init__(self):
        self.now=NOW;self.nodes={};self.obligations={};self.handles={};self.private_caps={};self.connections=[]
        self.authority={'serviceId':VER,'incarnation':'verifier-1','state':'ACTIVE','durableSequence':0,'lastErrorHash':None}
        self.intents={};self.unpublished={};self.issued={};self.outbox={};self.tombstones={};self.audit=[];self.counter=0;self.connection_scopes={};self.switches={}
        self.readers={'R'+str(i).zfill(2):row[2] for i,row in enumerate(READERS,1)};self.original_requests={};self.control_epoch='epoch-1'
        self.catalog={r[0]:r for r in IO};self.add_node(scope());self.add_node(scope(n='node-2'))

    def add_node(self,s):
        self.nodes[sk(s)]={'scope':deepcopy(s),'profile':'B','authorityVersion':1,'lineageVersion':1,'lineageId':H,
            'facts':{},'liveness':'online','generation':'generation-0','epoch':s['epoch'],'DER':'b'*64,'C':1,
            'policyR':1,'policyHash':'c'*64,'expiresAt':NOW+3600,'fenced':False,'grantLive':True,
            'channelEnabled':True,'keyLive':True,'certNotAfter':NOW+3600,
            'observeGrantLive':True,'observeGrantUntil':NOW+3600,'dbCandidates':{},
            'approvals':{'A0':{'prior':None,'root':H,'expiresAt':NOW+600},'A1':{'prior':'A0','root':H,'expiresAt':NOW+1800}},
            'currentApproval':'A1','activeClaims':{'claim-1'},'leaseActive':True,'workloadActive':True,
            'gate':{'gateId':'gate-0','releaseHash':'d'*64,'state':'ARMED','generation':'generation-0','sequence':1},
            'retiredGates':set(),'retiredReleases':set(),'gateRecords':{},'gateCommands':{},
            'activation':{'ledgerHash':'e'*64,'gateAckHash':'f'*64,'keyHash':'1'*64,'issuer':'issuer-1','issuerTLSHash':'5'*64,'challengeHash':'2'*64,
                          'ledgerId':'ledger-1','deliveryId':'delivery-1','challengeId':'challenge-1','ackExpiresAt':NOW+60,
                          'deliveryState':'PREPARED','possessionHash':'6'*64,'consumptionLedgerId':'consume-1','priorCurrentPointerHash':'7'*64,
                          'releaseHash':'d'*64,'deliveredCurrent':True,'leaseExpiresAt':NOW+300,'committed':True},
            'contribution':{'id':'contrib-1','path':'/synthetic/contribution','owner':'owner-1','status':'active','version':1},
            'root':{'device':'1','inode':'2','mountId':'3','mountNamespaceId':'4','mountIdentityHash':'3'*64},
            'folderChallenges':{},'folderProofs':{},'installedROMountProof':True}
        n=self.nodes[sk(s)]
        n['observeAuthBinding']={'scope':deepcopy(s),'generation':n['generation'],'C':n['C'],'DER':n['DER']}
        static=deepcopy(TEMPLATE['static'])
        static.update(nodeId=s['nodeId'],tenantId=s['tenantId'],epoch=s['epoch'],DER=n['DER'],C=n['C'],R=n['policyR'],policySha256=n['policyHash'])
        static['root'].update(deviceMajorHex8='00000000',deviceMinorHex8='00000001',inodeHex16='0000000000000002')
        n['static']=static;n['staticHash']=digest(static);n['recordId']=digest(n['gate'])
        n['cpGate']=deepcopy(n['gate']);n['cpRecordId']=n['recordId']
        n['storageApproval']={'rootHash':digest(n['root']),'ownerVersion':n['contribution']['version'],'C':n['C'],'DER':n['DER'],'R':n['policyR'],'policyHash':n['policyHash'],'path':n['contribution']['path']}
        prev=Z
        for aid in ('A0','A1'):
            record=n['approvals'][aid];body=deepcopy(TEMPLATE['current']['approval']['body'])
            body.update(approvalId=aid,static=deepcopy(static),priorApprovalHash=prev,expiresAt=record['expiresAt'])
            if aid=='A0':n['lineageId']=digest({'rootApprovalId':aid,'static':static,'operatorGrantHash':body['operatorGrantHash'],'nonce':body['nonce']})
            body['rootLineageID']=n['lineageId'];record['root']=n['lineageId'];record['envelope']=seal('APPROVAL',body,'SYMBOLIC_OPERATOR_ANCHOR');prev=digest(record['envelope'])

    def connect(self,service,scopes=None):
        c=Connection(service,self.authority['incarnation'] if service==VER else 'installed-1');self.connections.append(c)
        self.connection_scopes[id(c)]=set(sk(s) for s in scopes) if scopes is not None else set(self.nodes)
        return c

    def authenticated(self,c,allowed,s=None):return any(c is a for a in self.connections) and c.service in allowed and (s is None or sk(s) in self.connection_scopes[id(c)])

    def chain_live(self,s,approval=None,check_current_expiry=True):
        node=self.nodes.get(sk(s));a=approval or node['currentApproval'] if node else None;seen=set()
        if not node:return False
        while a:
            if a in seen or a not in node['approvals'] or (sk(s),a) in self.tombstones:return False
            seen.add(a);record=node['approvals'][a]
            if record['root']!=node['lineageId']:return False
            envelope=record.get('envelope')
            if not envelope or not verified(envelope,'APPROVAL','SYMBOLIC_OPERATOR_ANCHOR') or not shape('approval',envelope['body']):return False
            prior=record['prior'];expected=digest(node['approvals'][prior]['envelope']) if prior in node['approvals'] else Z if prior is None else None
            if envelope['body']['priorApprovalHash']!=expected or envelope['body']['rootLineageID']!=node['lineageId'] or envelope['body']['static']!=node['static']:return False
            a=record['prior']
        current=node['approvals'].get(approval or node['currentApproval'])
        return bool(current and (not check_current_expiry or self.now<current['envelope']['body']['expiresAt'])) # ancestor expiry alone is not revocation

    def projection(self,s):
        n=self.nodes[sk(s)];facts={key[0] for key,present in n['facts'].items() if present}
        return 'retired' if 'RETIRE' in facts else 'quarantined' if 'QUARANTINE' in facts else 'draining' if 'DRAIN' in facts else n['liveness']


    def b_binding_current(self,s):
        n=self.nodes.get(sk(s))
        if not n:return False
        expected={'rootHash':digest(n['root']),'ownerVersion':n['contribution']['version'],'C':n['C'],'DER':n['DER'],'R':n['policyR'],'policyHash':n['policyHash'],'path':n['contribution']['path']}
        return bool(n['installedROMountProof'] and n['storageApproval']==expected and n['contribution']['status']=='active'
            and n['static']['C']==n['C'] and n['static']['DER']==n['DER'] and n['static']['R']==n['policyR'] and n['static']['policySha256']==n['policyHash'])


    def observe_scope(self,c,s):
        n=self.nodes.get(sk(s))
        return {'available':True,'businessAuthority':False} if self.authenticated(c,{RUN,VER,SAFE,OP,REV},s) and n and n['epoch']==s['epoch'] else None



        # If DB write fails, PENDING remains a denial. No ordinary completion
        # capability is exposed to runtime or reconstructed after restart.


    def outcome(self,handle,tag='ACTIVE',valid=True):
        # SYMBOLIC independent existing-kernel-verifier fixture boundary.
        body={'bindingHash':handle.handle_hash,'tag':tag,'existingKernelValidation':'EXACT_TYPED_RECEIPT' if valid else 'MISMATCH'}
        return seal('EXISTING_VERIFIED_OUTCOME',body,'SYMBOLIC_CURRENT_NODE_PEER')


    def settle(self,c,handle,physical_proof=None):
        if not self.authenticated(c,{OP}) or not physical_proof:return False
        ref=self.handles[handle.handle_hash];row=self.obligations[ref['key']];cap=self.private_caps[handle.handle_hash]
        if not self.authenticated(c,{OP},row['binding']['scope']):return False
        if row['state']!='UNCERTAIN' and not (row['state']=='PENDING_IO' and (cap['state']!='LIVE' or cap['incarnation']!=self.authority['incarnation'])):return False
        if not verified(physical_proof,'PROTECTED_PHYSICAL_RECOVERY','SYMBOLIC_OPERATOR_INDEPENDENT_PHYSICAL_VERIFIER') or physical_proof['body']!={'bindingHash':handle.handle_hash,'recovery':'EXACT_PHYSICAL_RECONCILIATION'}:return False
        row.update(state='SETTLED_PROTECTED',protectedRecoveryHash=digest(physical_proof));cap['state']='CONSUMED';return True

    def set_fact(self,c,s,kind,present=True,proof=None,cause='original-operation'):
        if kind not in ('DRAIN','QUARANTINE','RETIRE'):return False
        if present and not self.authenticated(c,{OP,SAFE},s):return False
        expected={'scope':s,'factKind':kind,'causeOperationId':cause,'recovery':'EXACT_PHYSICAL_RECONCILIATION'}
        if not present and (kind=='RETIRE' or not self.authenticated(c,{OP},s) or not proof or not verified(proof,'EXISTING_PROTECTED_CLEAR','SYMBOLIC_OPERATOR_INDEPENDENT_PHYSICAL_VERIFIER') or proof['body']!=expected):return False
        self.nodes[sk(s)]['facts'][(kind,cause)]=present;self.nodes[sk(s)]['authorityVersion']+=1;return True

    def revoke(self,c,s,ancestor='A0',causal=None,known_gate=True):
        if not self.authenticated(c,{OP,SAFE},s) or causal is None:return None
        n=self.nodes[sk(s)]
        if ancestor not in n['approvals']:return None
        n['lineageVersion']+=1;n['authorityVersion']+=1
        record={'scope':deepcopy(s),'rootLineageID':n['lineageId'],'revokedAncestorHash':digest(n['approvals'][ancestor]['envelope']),
            'authenticatedPrincipal':c.service,'causalEvidenceHash':causal,'auditRef':'audit-'+str(n['lineageVersion']),
            'anchorVersion':n['lineageVersion'],'recordedAt':self.now}
        self.tombstones[(sk(s),ancestor)]=record
        outid='revoke-'+str(len(self.outbox)+1);gate=n['cpGate'] if known_gate else None
        self.outbox[outid]={'outboxId':outid,'scope':deepcopy(s),'rootLineageID':n['lineageId'],'ancestorHash':record['revokedAncestorHash'],
            'anchorVersion':n['lineageVersion'],'targetGateId':gate['gateId'] if gate else None,
            'targetReleaseHash':gate['releaseHash'] if gate else None,'state':'PENDING' if gate else 'UNKNOWN_TARGET_HOLD',
            'commandHash':None,'ackHash':None,'causalEvidenceHash':causal}
        self.audit.append(record);return outid

    def begin_planned_switch(self,c,s):
        if not self.authenticated(c,{OP},s) or not self.chain_live(s) or not self.eligible('R03',s):return None
        n=self.nodes[sk(s)];sid='switch-'+str(len(self.switches)+1)
        self.switches[sid]={'scope':deepcopy(s),'gateId':n['cpGate']['gateId'],'releaseHash':n['cpGate']['releaseHash'],
            'staticHash':n['staticHash'],'purpose':'SAME_CONFIG_RENEW','state':'PREPARED'}
        n['authorityVersion']+=1;return sid

    def protected_signing_read(self,c,s,kind,body):
        if not self.authenticated(c,{OP,DEL,SAFE,REV},s):return None
        if not isinstance(body,dict) or not strict(body):return None
        n=self.nodes.get(sk(s))
        if not n or s['epoch']!=self.control_epoch or body.get('scope')!=s or body.get('epoch')!=s['epoch'] or not self.now<body.get('expiresAt',0)<=n['expiresAt']:return None
        required={'scope','epoch','approvalId','generation','nodeDER','channelVersion','policyR','policyHash','gateId','releaseHash','action','nonce','issuedAt','expiresAt','wireBody'}|set(n['activation'])-{'committed'}
        optional={'outboxId','lineageVersion','switchId'}
        if not required<=set(body) or set(body)-required-optional or type(body['channelVersion']) is not int or type(body['policyR']) is not int:return None
        wire=body.get('wireBody');shape_name={'APPROVAL':'approval','RELEASE':'release','DELEGATION':'delegation','GATE_CONTROL':'gateControl','DELIVERY_CHALLENGE':'deliveryChallenge','KEY_DELIVERY_RECEIPT':'keyDeliveryReceipt'}.get(kind)
        if not shape_name or not wire or not shape(shape_name,wire):return None
        if kind=='GATE_CONTROL' and any(wire.get(k)!=v for k,v in {'nodeId':s['nodeId'],'epoch':s['epoch'],'generation':n['generation'],'staticHash':n['staticHash'],'action':body['action'],'gateId':body['gateId'],'releaseHash':body['releaseHash']}.items()):return None
        if wire.get('expiresAt')!=body['expiresAt']:return None
        if kind=='GATE_CONTROL' and (wire['expiresAt']-wire['issuedAt']>120 or wire['issuedAt']>self.now):return None
        if kind=='GATE_CONTROL' and body.get('action')=='INVALIDATE_EXACT_GATE':
            if c.service not in (OP,SAFE,REV):return None
            current=n['cpGate']
            if not current or current['state']!='ARMED':return None
            if body.get('outboxId'):
                out=self.outbox.get(body['outboxId'])
                if not out or out['scope']!=s or out['state'] not in ('PENDING','PREPARED','SIGNED_UNPUBLISHED','RETRY_SAME_COMMAND') or out['targetGateId'] is None:return None
                if body.get('gateId')!=out['targetGateId'] or body.get('releaseHash')!=out['targetReleaseHash'] or body.get('lineageVersion')!=out['anchorVersion']:return None
                if current['gateId']!=out['targetGateId'] or current['releaseHash']!=out['targetReleaseHash']:return None
            else:
                switch=self.switches.get(body.get('switchId'))
                if c.service!=OP or not switch or switch['scope']!=s or switch['state']!='PREPARED' or not self.chain_live(s):return None
                if switch['staticHash']!=n['staticHash'] or body['gateId']!=switch['gateId'] or body['releaseHash']!=switch['releaseHash'] or current['gateId']!=switch['gateId']:return None
        else:
            if c.service in (SAFE,REV):return None
            allowed={OP:{'APPROVAL','RELEASE','DELEGATION','GATE_CONTROL'},DEL:{'DELIVERY_CHALLENGE','KEY_DELIVERY_RECEIPT'}}
            if kind not in allowed.get(c.service,set()) or not self.chain_live(s,body.get('approvalId'),check_current_expiry=kind!='APPROVAL'):return None
            if n['profile']=='B' and not self.b_binding_current(s):return None
            if kind!='APPROVAL' and body['expiresAt']>n['approvals'][body['approvalId']]['envelope']['body']['expiresAt']:return None
            if n['fenced'] or not n['grantLive'] or any(n['facts'].values()) or self.unresolved(s):return None
            exact={'generation':n['generation'],'nodeDER':n['DER'],'channelVersion':n['C'],'policyR':n['policyR'],'policyHash':n['policyHash']}
            if any(body.get(k)!=v for k,v in exact.items()):return None
            if kind=='GATE_CONTROL' and body.get('action')!='ARM_EXACT_RELEASE':return None
            if kind in ('APPROVAL','RELEASE') and wire.get('static')!=n['static']:return None
            if kind=='APPROVAL':
                prior=n['approvals'][body['approvalId']]['envelope']
                purpose='APPROVAL_RENEW_SAME_CONFIG' if self.now<prior['body']['expiresAt'] else 'REAPPROVE_SAME_CONFIG'
                if wire['purpose']!=purpose or wire['priorApprovalHash']!=digest(prior) or wire['rootLineageID']!=n['lineageId'] or wire['expiresAt']>self.now+86400:return None
            if kind=='RELEASE' and (wire['approvalHash']!=digest(n['approvals'][body['approvalId']]['envelope']) or wire['generation']!=n['generation']):return None
            if kind=='DELEGATION' and any(wire.get(k)!=v for k,v in {'nodeId':s['nodeId'],'epoch':s['epoch'],'generation':n['generation'],'gateId':body['gateId'],'releaseHash':body['releaseHash'],'useKeyHash':n['activation']['keyHash']}.items()):return None
            if c.service==DEL:
                a=n['activation']
                if not a['committed'] or self.now>=a['ackExpiresAt'] or any(body.get(k)!=a[k] for k in ('ledgerHash','gateAckHash','keyHash','issuer','challengeHash')):return None
                if a['deliveryState']!=('PREPARED' if kind=='DELIVERY_CHALLENGE' else 'CONSUMED_PENDING_RECEIPT'):return None
                exact_wire={'nodeId':s['nodeId'],'epoch':s['epoch'],'generation':n['generation'],'gateId':n['cpGate']['gateId'],
                    'releaseHash':n['cpGate']['releaseHash'],'activationLedgerHash':a['ledgerHash'],'gateAckHash':a['gateAckHash'],
                    'useKeyHash':a['keyHash'],'issuerServiceId':a['issuer'],'issuerTLSHash':a['issuerTLSHash'],'activationLedgerId':a['ledgerId'],
                    'deliveryId':a['deliveryId'],'challengeId':a['challengeId'],'staticHash':n['staticHash']}
                if any(wire.get(k)!=v for k,v in exact_wire.items()):return None
                if kind=='DELIVERY_CHALLENGE' and wire['expiresAt']-wire['issuedAt']>60:return None
                if kind=='KEY_DELIVERY_RECEIPT' and any(wire.get(k)!=v for k,v in {'challengeHash':a['challengeHash'],'possessionHash':a['possessionHash'],'consumptionLedgerId':a['consumptionLedgerId'],'priorCurrentPointerHash':a['priorCurrentPointerHash'],'priorState':'CONSUMED_PENDING_RECEIPT','currentState':'DELIVERED_CURRENT'}.items()):return None
        return {'authorityVersion':n['authorityVersion'],'lineageVersion':n['lineageVersion'],'scope':deepcopy(s),'bodyHash':digest(wire),'authorityFootprintHash':self.signature_footprint(s,kind,body)}

    def prepare_sign(self,c,s,kind,body):
        read=self.protected_signing_read(c,s,kind,body)
        if not read:return None
        self.counter+=1;i='signing-'+str(self.counter)
        self.intents[i]={'intentId':i,'scope':deepcopy(s),'authenticatedService':c.service,'kind':kind,
            'purpose':('GATE_CONTROL_INVALIDATE' if kind=='GATE_CONTROL' and body.get('action')=='INVALIDATE_EXACT_GATE' else kind),
            'domain':DOMAINS[kind][0],'bodyHash':digest(body['wireBody']),'authorityVersion':read['authorityVersion'],'lineageVersion':read['lineageVersion'],'authorityFootprintHash':read['authorityFootprintHash'],
            'state':'PREPARED','issuedSignatureHash':None,'issuedAt':self.now,'expiresAt':body['expiresAt']}
        self.unpublished[i]={'body':deepcopy(body),'connection':c,'signature':None}
        if body.get('outboxId'):self.outbox[body['outboxId']]['state']='PREPARED'
        return i

    def hsm_sign_private(self,i):
        intent=self.intents[i]
        if intent['state']!='PREPARED':return False
        self.unpublished[i]['signature']=seal(intent['kind'],self.unpublished[i]['body']['wireBody'],'SYMBOLIC_OPERATOR_ANCHOR')
        outid=self.unpublished[i]['body'].get('outboxId')
        if outid:self.outbox[outid]['state']='SIGNED_UNPUBLISHED'
        intent['state']='HSM_UNPUBLISHED';return True # no signature exposed to requester

    def publish_sign(self,c,i):
        intent=self.intents.get(i);private=self.unpublished.get(i)
        if not intent or not private or private['connection'] is not c or intent['state']!='HSM_UNPUBLISHED':return None
        read=self.protected_signing_read(c,intent['scope'],intent['kind'],private['body'])
        if not read or any(read[k]!=intent[k] for k in ('authorityVersion','lineageVersion','bodyHash','authorityFootprintHash')):
            intent['state']='DISCARDED';private['signature']=None;return None
        signed=private['signature'];intent['state']='ISSUED';intent['issuedSignatureHash']=digest(signed)
        self.issued[digest(signed)]={'intent':i,'signature':deepcopy(signed)}
        if private['body'].get('outboxId'):
            out=self.outbox[private['body']['outboxId']];out.update(state='READY_TO_DISPATCH',commandHash=digest(signed))
        return deepcopy(signed)

    def sign(self,c,s,kind,body):
        i=self.prepare_sign(c,s,kind,body)
        if i is None:return None
        assert self.hsm_sign_private(i);return self.publish_sign(c,i)

    def node_gate(self,s,command):
        if not command or not verified(command,'GATE_CONTROL','SYMBOLIC_OPERATOR_ANCHOR') or not shape('gateControl',command['body']):return None
        b=command['body'];n=self.nodes[sk(s)]
        if b['nodeId']!=s['nodeId'] or b['epoch']!=s['epoch'] or not self.now<b['expiresAt'] or b['generation']!=n['generation'] or b['staticHash']!=n['staticHash']:return None
        duplicate=n['gateCommands'].get(digest(command))
        if duplicate:
            row=n['gateRecords'][duplicate]
            return deepcopy(row['ack']) if n['recordId']==duplicate else None
        current=n['gate'];action=b['action']
        prior=current['gateId'] if current else 'NONE';prior_seq=current['sequence'] if current else 0
        if b['expectedPriorGateId']!=prior or b['expectedPriorSequence']!=prior_seq or b['expectedPriorRecordHash']!=n['recordId']:return None
        if action=='INVALIDATE_EXACT_GATE':
            if not current or current['gateId']!=b['gateId'] or current['releaseHash']!=b['releaseHash'] or current['state']!='ARMED':return None
            n['retiredGates'].add(b['gateId']);n['retiredReleases'].add(b['releaseHash']);state='INVALIDATED'
        else:
            if b['gateId'] in n['retiredGates'] or b['releaseHash'] in n['retiredReleases'] or current and current['state']=='ARMED':return None
            state='ARMED'
        sequence=(current['sequence'] if current else 0)+1
        record={'gateId':b['gateId'],'releaseHash':b['releaseHash'],'state':state,'generation':n['generation'],'sequence':sequence,
            'commandHash':digest(command),'priorRecord':n['recordId'],'delegationHash':b['delegationHash'],'staticHash':n['staticHash']}
        rid=digest(record);n['gate']=record
        ack=seal('GATE_ACK',{'nodeId':s['nodeId'],'tenantId':s['tenantId'],'nodeCertificateSHA256':n['DER'],'epoch':s['epoch'],
            'generation':n['generation'],'static':n['static'],'action':action,'commandHash':digest(command),
            'requestBodyHash':digest(command),'releaseHash':b['releaseHash'],'delegationHash':b['delegationHash'],'useKeyHash':b['useKeyHash'],
            'gateId':b['gateId'],'priorGateId':prior,'nonce':b['nonce'],'sequence':sequence,'priorSequence':prior_seq,
            'localGateRecordId':rid,'priorLocalGateRecordId':n['recordId'],'state':state,'observedAt':self.now,'expiresAt':min(self.now+60,b['expiresAt'])},'SYMBOLIC_NODE_LEAF')
        n['recordId']=rid;n['gateRecords'][rid]={'record':deepcopy(record),'ack':deepcopy(ack)};n['gateCommands'][digest(command)]=rid
        return ack

    def dispatch_invalidation(self,c,outid,command,handle,dispatch_intent_commit_proven=True):
        out=self.outbox[outid]
        if not self.authenticated(c,{OP,SAFE,REV},out['scope']) or not command or digest(command)!=out['commandHash'] or digest(command) not in self.issued:return False
        if self.now>=command['body']['expiresAt']:out['state']='EXPIRED_HOLD';return False
        if out['state'] not in ('READY_TO_DISPATCH','RETRY_SAME_COMMAND','DISPATCHED_AWAIT_ACK') or not dispatch_intent_commit_proven:return False
        out['state']='DISPATCHED_AWAIT_ACK' # durable dispatch intent before IO, not delivery proof
        return self.invoke(handle,digest(command),'POST','/v1/roles/gate')

    def gate_readback(self,c,s,nonce=H):
        if not self.observe_scope(c,s):return None
        n=self.nodes[sk(s)];row=n['gateRecords'].get(n['recordId'])
        if not row or not row.get('ack'):
            status,reason='UNKNOWN_RECORD','MISSING_DURABLE_PROOF'
        elif row['record']['generation']!=n['generation']:
            status,reason='CONFLICT','INCONSISTENT_HISTORY'
        elif self.now>=row['ack']['body']['expiresAt']:
            status,reason='STALE_ACK','ORIGINAL_ACK_EXPIRED'
        else:
            b={'status':'AVAILABLE','businessAuthority':False,'method':'POST','path':'/v1/roles/observe',
                'nodeId':s['nodeId'],'epoch':s['epoch'],'generation':n['generation'],'nonce':nonce,'observedAt':self.now,'expiresAt':self.now+30,
                'recordId':n['recordId'],'record':row['record'],'sequence':row['record']['sequence'],
                'retiredGateIDs':sorted(n['retiredGates']),'retiredReleaseHashes':sorted(n['retiredReleases']),
                'originalAckHash':digest(row['ack']),'originalAckExpiresAt':row['ack']['body']['expiresAt']}
            return seal('GATE_OBSERVATION',b,'SYMBOLIC_NODE_LEAF')
        return seal('GATE_OBSERVATION',{'status':status,'businessAuthority':False,'nodeId':s['nodeId'],'nonce':nonce,
            'observedAt':self.now,'reason':reason,'recovery':'B-RECOVERY1_HOLD'},'SYMBOLIC_NODE_LEAF')

    def record_invalidation_ack(self,c,outid,ack):
        out=self.outbox[outid];n=self.nodes[sk(out['scope'])]
        if getattr(c,'service',None)==RECOVERY and not any(proof['body']['commandHash']==out['commandHash'] for proof in getattr(self,'_verified_gate_recovery',{}).values()):return False
        if not self.authenticated(c,{VER,OP,SAFE,REV,RECOVERY},out['scope']) or not verified(ack,'GATE_ACK','SYMBOLIC_NODE_LEAF') or not self.now<ack['body']['expiresAt']:return False
        if out['commandHash']!=ack['body']['commandHash'] or ack['body']['state']!='INVALIDATED' or n['recordId']!=ack['body']['localGateRecordId'] or not shape('gateAck',ack['body']):return False
        out.update(state='ACK_RECORDED',ackHash=digest(ack));return True

    def confirm_many(self,c,pairs,receipt_transaction_commits=True):
        before=(deepcopy(self.obligations),deepcopy(self.private_caps),deepcopy(self.nodes))
        if not receipt_transaction_commits:return False
        if not all(self.confirm(c,h,outcome) for h,outcome in pairs):
            before=(before[0],self.preserve_capability_death(before[1]),before[2])
            self.obligations,self.private_caps,self.nodes=before;return False
        return True

    def confirm_gate_ack(self,c,outid,handle,ack,transaction_commits=True):
        before=(deepcopy(self.obligations),deepcopy(self.private_caps),deepcopy(self.outbox))
        if not transaction_commits:return False
        if not self.record_invalidation_ack(c,outid,ack) or not self.confirm(c,handle,self.outcome(handle,'OBSERVED')):
            before=(before[0],self.preserve_capability_death(before[1]),before[2])
            self.obligations,self.private_caps,self.outbox=before;return False
        n=self.nodes[sk(self.outbox[outid]['scope'])];n['cpGate']=deepcopy(n['gate']);n['cpRecordId']=n['recordId']
        return True

    def confirm_planned_gate_ack(self,c,s,switch_id,handle,ack):
        if not self.authenticated(c,{VER},s) or switch_id not in self.switches or not verified(ack,'GATE_ACK','SYMBOLIC_NODE_LEAF') or not shape('gateAck',ack['body']) or self.now>=ack['body']['expiresAt']:return False
        n=self.nodes[sk(s)];h=self.handles.get(handle.handle_hash)
        if not h or ack['body']['localGateRecordId']!=n['recordId'] or self.obligations[h['key']]['binding']['bodySHA']!=ack['body']['commandHash']:return False
        if not self.confirm(c,handle,self.outcome(handle,'OBSERVED')):return False
        n['cpGate']=deepcopy(n['gate']);n['cpRecordId']=n['recordId'];self.switches[switch_id]['state']=ack['body']['state'];return True

    def folder_observe(self,c,s,challenge,permit_hash=H):
        if not self.observe_scope(c,s):return None
        n=self.nodes[sk(s)];con=n['contribution']
        n['folderChallenges'][challenge]={'issuedAt':self.now,'ownerVersion':con['version'],'consumed':False}
        body={'kind':'FOLDER_ROOT_OBSERVATION','stage':'PREFLIGHT_ROOT_IDENTITY','purpose':'B_PREFLIGHT_FOLDER_ROOT','businessAuthority':False,
            'scope':s,'contributionId':con['id'],'normalizedPath':con['path'],'heldRoot':deepcopy(n['root']),
            'generation':n['generation'],'channelVersion':n['C'],'nodeDER':n['DER'],'policyR':n['policyR'],'policyHash':n['policyHash'],
            'ownerConsentVersion':con['version'],'observePermitHash':permit_hash,'challenge':challenge,'observedAt':self.now,'expiresAt':self.now+30}
        return seal('FOLDER_ROOT_OBSERVATION',body,'SYMBOLIC_CURRENT_NODE_LEAF')

    def approve_folder(self,c,s,record):
        if not self.authenticated(c,{OP},s) or not verified(record,'FOLDER_ROOT_OBSERVATION','SYMBOLIC_CURRENT_NODE_LEAF') or not shape('folderRootObservation',record['body']):return False
        n=self.nodes[sk(s)];b=record['body'];con=n['contribution'];challenge=n['folderChallenges'].get(b['challenge'])
        if not challenge or challenge['consumed'] or not b['observedAt']<=self.now<b['expiresAt'] or b['expiresAt']-b['observedAt']>30:return False
        expected={'scope':s,'contributionId':con['id'],'normalizedPath':con['path'],'heldRoot':n['root'],'generation':n['generation'],
            'channelVersion':n['C'],'nodeDER':n['DER'],'policyR':n['policyR'],'policyHash':n['policyHash'],'ownerConsentVersion':con['version']}
        if any(b[k]!=v for k,v in expected.items()) or con['status']!='active':return False
        if any(int(b['heldRoot'][k])>18446744073709551615 for k in ('device','inode','mountId','mountNamespaceId')):return False
        challenge['consumed']=True;n['folderProofs'][digest(record)]=record
        n['storageApproval']={'rootHash':digest(n['root']),'ownerVersion':con['version'],'C':n['C'],'DER':n['DER'],'R':n['policyR'],'policyHash':n['policyHash'],'path':con['path']}
        return True


from lifecycle import WorldMixin
class World(WorldMixin,RetainedWorld):
    pass

def binding(w,s=None,op='operation-1',kind='EXECUTE',parent=None,resource='resource-1',run='run-1',known=True):
    s=s or scope();n=w.nodes[sk(s)];row=w.catalog[kind]
    result={'scope':deepcopy(s),'operationId':op,'attemptId':'attempt-1','effectClass':EFFECT[kind],'footprint':fixture_footprint(resource,run,known),'kind':kind,'method':row[3],'rawPath':row[4],
        'channelVersion':n['C'],'nodeDER':n['DER'],'targetBindingSHA':digest({'kind':kind,'resource':resource,'run':run}),'ownerBindingSHA':None if kind.startswith('B_') else digest({'owner':'synthetic-owner-1','run':run}),'bodySHA':digest({'SYNTHETIC_EXISTING_REQUEST_BYTES':op}),'existingPermitOrApprovalSHA':H,'nonce':digest({'SYNTHETIC_NONCE':op}),
        'runId':None if kind.startswith('B_') else run,'generation':n['generation'],'claimBindingSHA':None if kind.startswith('B_') else digest({'run':run,'resource':resource}),'parentHandleHash':parent,
        'parentCommandSHA':w.obligations[w.handles[parent]['key']]['binding']['bodySHA'] if parent in w.handles else None,
        'admittedClaimVersion':None,'executionAttemptId':None,'protectedReadBindingSHA':None}
    workload={'EXECUTE','CANCEL','RECEIPT_OBSERVE','BUILD_DISPATCH','BUILD_CLEANUP_READ','TERMINAL_FRAME'}
    if kind not in workload and kind!='OBJECT_READ':
        result.update(runId=None,claimBindingSHA=None,ownerBindingSHA=None)
        result['footprint']['rows']=[r for r in result['footprint']['rows'] if r['table'] in ('inv.node_channels','inv.node_role_current')]
        if kind in ('B_GATE_ARM','B_GATE_INVALIDATE'):
            for r in result['footprint']['rows']:
                if r['table']=='inv.node_role_current':r['mode']='UPDATE'
        if kind=='QUARANTINE_RECONCILE':
            from rank_contract import RANK
            result['footprint']['rows'].append({'table':'inv.resources','rank':RANK['inv.resources'],'key':resource,'mode':'UPDATE'})
    if kind=='OBJECT_READ' and parent in getattr(w,'read_parents',{}):
        record=w.read_parents[parent];result.update(runId=None,claimBindingSHA=None,ownerBindingSHA=record['ownerBindingSHA'],targetBindingSHA=record['targetBindingSHA'],footprint=deepcopy(record['footprint']))
    # Test-only seeding of the ORIGINAL independently admitted operation record.
    # Registration rereads this immutable record, never a request profile/opid flag.
    if parent in w.handles:
        original=w.obligations[w.handles[parent]['key']]['binding']
        result.update(admittedClaimVersion=original['admittedClaimVersion'],executionAttemptId=original['executionAttemptId'])
    if kind=='BUILD_CLEANUP_READ':
        record=getattr(w,'protected_cleanup_parents',{}).get(parent)
        result['protectedReadBindingSHA']=digest(record) if record else None
    if kind in ('EXECUTE','BUILD_DISPATCH'):
        n['activeClaims'].add(result['claimBindingSHA']);versions=n.setdefault('claimVersions',{});key=result['claimBindingSHA'];versions[key]=versions.get(key,0)+1
        result.update(admittedClaimVersion=versions[key],executionAttemptId='execution-attempt-1')
        n.setdefault('claimRights',{})[key]={'ownerBindingSHA':result['ownerBindingSHA'],'runId':run,'leaseExpiresAt':w.now+300,'notAfter':w.now+300,
          'version':versions[key],'executionAttemptId':result['executionAttemptId'],'currentAttemptId':result['executionAttemptId'],
          'workloadState':'RUNNING','terminalCapability':True,'ownerCurrent':True,'projectMemberCurrent':True,'leasesKnown':True,
          'leases':[{'released':False,'expiresAt':w.now+300,'epoch':s['epoch']}],'releasedByKernelReceipt':None}
    w.original_requests[(sk(s),op)]=deepcopy(result)
    return result


def sign_body(w,s=None,action='ARM_EXACT_RELEASE',outid=None,kind='GATE_CONTROL',switch_id=None):
    s=s or scope();n=w.nodes[sk(s)]
    b={'scope':s,'epoch':s['epoch'],'approvalId':'A1','generation':n['generation'],'nodeDER':n['DER'],
       'channelVersion':n['C'],'policyR':n['policyR'],'policyHash':n['policyHash'],'gateId':'gate-new','releaseHash':'4'*64,
       'action':action,'nonce':H,'issuedAt':w.now,'expiresAt':w.now+60,**n['activation']}
    b.pop('committed')
    if kind in ('GATE_CONTROL','RELEASE','DELEGATION'):b['releaseHash']='4'*64
    if outid:
        out=w.outbox[outid];b.update(outboxId=outid,gateId=out['targetGateId'],releaseHash=out['targetReleaseHash'],lineageVersion=out['anchorVersion'])
    if switch_id:
        switch=w.switches[switch_id];b.update(switchId=switch_id,gateId=switch['gateId'],releaseHash=switch['releaseHash'])
    if kind=='GATE_CONTROL':
        g=n['cpGate'];wire={'action':action,'method':'POST','path':'/v1/roles/gate','staticHash':n['staticHash'],
            'nodeId':s['nodeId'],'epoch':s['epoch'],'generation':n['generation'],'gateId':b['gateId'],
            'expectedPriorGateId':g['gateId'] if g else 'NONE','releaseHash':b['releaseHash'],'delegationHash':H,'useKeyHash':b['keyHash'],
            'nonce':b['nonce'],'issuedAt':w.now,'expiresAt':b['expiresAt'],'expectedPriorRecordHash':n['cpRecordId'],
            'expectedPriorSequence':g['sequence'] if g else 0}
    else:
        template={'APPROVAL':'approval','RELEASE':'release','DELEGATION':'delegation','DELIVERY_CHALLENGE':None,'KEY_DELIVERY_RECEIPT':None}[kind]
        if template:wire=deepcopy(TEMPLATE['current'][template]['body'])
        else:wire=deepcopy(TEMPLATE['current']['receipt']['body'] if kind=='KEY_DELIVERY_RECEIPT' else next(iter(TEMPLATE['challenges'].values()))['artifact']['body'])
        wire.update(issuedAt=w.now,expiresAt=b['expiresAt'])
        if 'static' in wire:wire['static']=deepcopy(n['static'])
        if kind=='APPROVAL':wire.update(rootLineageID=n['lineageId'],priorApprovalHash=digest(n['approvals']['A1']['envelope']),approvalId='approval-new-'+str(w.now),purpose='APPROVAL_RENEW_SAME_CONFIG' if w.now<n['approvals']['A1']['envelope']['body']['expiresAt'] else 'REAPPROVE_SAME_CONFIG')
        if 'generation' in wire:wire['generation']=n['generation']
        if kind=='RELEASE':wire.update(approvalHash=digest(n['approvals']['A1']['envelope']),gateId=b['gateId'],useKeyHash=b['keyHash'])
        if kind=='DELEGATION':wire.update(nodeId=s['nodeId'],epoch=s['epoch'],gateId=b['gateId'],releaseHash=b['releaseHash'],useKeyHash=b['keyHash'])
        if kind in ('DELIVERY_CHALLENGE','KEY_DELIVERY_RECEIPT'):
            a=n['activation'];b.update(gateId=n['cpGate']['gateId'],releaseHash=n['cpGate']['releaseHash'])
            wire.update(nodeId=s['nodeId'],epoch=s['epoch'],generation=n['generation'],gateId=n['cpGate']['gateId'],releaseHash=n['cpGate']['releaseHash'],
                activationLedgerHash=a['ledgerHash'],gateAckHash=a['gateAckHash'],useKeyHash=a['keyHash'],issuerServiceId=a['issuer'],issuerTLSHash=a['issuerTLSHash'],
                activationLedgerId=a['ledgerId'],deliveryId=a['deliveryId'],challengeId=a['challengeId'],staticHash=n['staticHash'])
            if kind=='KEY_DELIVERY_RECEIPT':wire.update(challengeHash=a['challengeHash'],possessionHash=a['possessionHash'],consumptionLedgerId=a['consumptionLedgerId'],priorCurrentPointerHash=a['priorCurrentPointerHash'],priorState='CONSUMED_PENDING_RECEIPT',currentState='DELIVERED_CURRENT')
    b['wireBody']=wire
    return b
