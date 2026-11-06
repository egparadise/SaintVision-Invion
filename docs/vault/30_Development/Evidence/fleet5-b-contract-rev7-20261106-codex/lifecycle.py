"""Rev7 symbolic overrides, no DB/network/crypto/physical operations.

Private object identities represent installed verifier boundaries. Durable fuse,
dispatch CAS and fresh recovery attestations still require real implementation CI.
"""
from copy import deepcopy
from io_contract import EFFECT,SIDE_EFFECT,READ_ONLY,SAFETY,CONTINUATIONS,RECOVERY,intersects
from model import sk,digest,shape,verified,seal,CommittedIOHandle,OP,VER,RUN,SAFE,REV,H

class WorldMixin:
    def unresolved(self,s,footprint=None,exclude=None):
        out=[]
        for key,row in self.obligations.items():
            if key[0]!=sk(s) or row['state'] not in ('PENDING_IO','UNCERTAIN'):continue
            if key in (exclude if isinstance(exclude,set) else {exclude}) and row['state']=='PENDING_IO' and self.private_caps[row['bindingHash']]['state']=='LIVE':continue
            b=row['binding'];effect=b['effectClass'];cap=self.private_caps[row['bindingHash']]
            if effect==READ_ONLY:continue
            if effect==SIDE_EFFECT:
                if row['state']=='UNCERTAIN' or cap['state']!='LIVE' or intersects(b['footprint'],footprint):out.append(row)
            elif intersects(b['footprint'],footprint):out.append(row) # exact safety target/causal scope only
        return out

    def eligible(self,reader,s,footprint=None,handle=None):
        if self.authority['state']!='ACTIVE' or reader not in self.readers:return False
        n=self.nodes.get(sk(s));ref=self.handles.get(getattr(handle,'handle_hash',None))
        exact=bool(ref and ref['object'] is handle and ref['key'][0]==sk(s))
        continuation=reader in ('R12','R13')
        if continuation and not exact:return False
        b=self.obligations[ref['key']]['binding'] if exact else None
        if reader=='R12' and (b['kind']!='TERMINAL_FRAME' or not self._parent_current(b)):return False
        allow_drain=reader=='R12' and exact
        return bool(n and n['epoch']==s['epoch']==self.control_epoch and n['liveness']=='online'
          and not any(v and (k!='DRAIN' or not allow_drain) for (k,cause),v in n['facts'].items())
          and n['grantLive'] and not n['fenced'] and self.now<n['expiresAt']
          and not self.unresolved(s,footprint or (b['footprint'] if b else None),({ref['key']}|({self.handles[b['parentHandleHash']]['key']} if b and b['parentHandleHash'] in self.handles else set())) if exact else None)
          and (n['profile']=='PLAIN' or self.chain_live(s) and self.b_binding_current(s)
               and n['cpGate']['state']=='ARMED' and n['activation']['deliveredCurrent']
               and self.now<n['activation']['leaseExpiresAt']))

    def _parent_current(self,b):
        n=self.nodes.get(sk(b['scope']))
        read=getattr(self,'read_parents',{}).get(b['parentHandleHash'])
        if b['kind']=='OBJECT_READ' and read:
            return bool(n and read['scope']==b['scope'] and read['generation']==b['generation']==n['generation'] and read['C']==b['channelVersion']==n['C'] and read['DER']==b['nodeDER']==n['DER'] and read['readUntil']>self.now and not read['revoked'] and read['ownerBindingSHA']==b['ownerBindingSHA'] and read['targetBindingSHA']==b['targetBindingSHA'] and b['runId'] is None and b['claimBindingSHA'] is None and not n['fenced'] and n['grantLive'] and not any(n['facts'].values()) and (n['profile']=='PLAIN' or self.chain_live(b['scope']) and self.b_binding_current(b['scope'])))
        p=self.handles.get(b['parentHandleHash'])
        if not p or not n:return False
        original=self.obligations[p['key']]['binding'];rights=n.get('claimRights',{}).get(original['claimBindingSHA'])
        if not rights or rights['runId']!=b['runId'] or rights['ownerBindingSHA']!=b['ownerBindingSHA'] or rights['leaseExpiresAt']<=self.now or rights['notAfter']<=self.now+5:return False
        # Exact installed original claimed operation, not a user-selected opid.
        return bool(original['scope']==b['scope'] and original['generation']==b['generation']==n['generation']
          and original['runId']==b['runId'] and original['claimBindingSHA']==b['claimBindingSHA']
          and original['existingPermitOrApprovalSHA']==b['existingPermitOrApprovalSHA']
          and n['grantLive'] and not n['fenced'] and original['channelVersion']==b['channelVersion']==n['C'] and original['nodeDER']==b['nodeDER']==n['DER'] and not any(v and k in ('QUARANTINE','RETIRE') for (k,cause),v in n['facts'].items()) and n['leaseActive'] and n['workloadActive'] and self.now<n['activation']['leaseExpiresAt'])

    def register(self,c,b,commit_proven=True):
        if self.authority['state']!='ACTIVE' or not shape('ioBinding',b) or EFFECT.get(b['kind'])!=b['effectClass'] or not self.authenticated(c,{RUN,VER,SAFE},b['scope']):return None
        if self.original_requests.get((sk(b['scope']),b['operationId']))!=b:return None
        from rank_contract import RANK
        if any(RANK.get(r['table'])!=r['rank'] for r in b['footprint']['rows']):return None
        n=self.nodes.get(sk(b['scope']));kind=b['kind']
        if (b['method'],b['rawPath'])!=(self.catalog[kind][3],self.catalog[kind][4]):return None
        if not n or n['generation']!=b['generation'] or b['scope']['epoch']!=self.control_epoch or b['channelVersion']!=n['C'] or b['nodeDER']!=n['DER']:return None
        if kind.startswith('B_') and c.service not in (VER,SAFE):return None
        if kind in ('B_GATE_ARM','B_GATE_INVALIDATE','B_ROLE_OBSERVE') and n['profile']!='B':return None
        if kind in CONTINUATIONS and not self._parent_current(b):return None
        if b['effectClass']==READ_ONLY or b['effectClass']==SAFETY:
            if not self.observe_scope(c,b['scope']):return None
        elif kind in ('TERMINAL_FRAME','RECEIPT_OBSERVE'):
            if any(v and k!='DRAIN' for (k,cause),v in n['facts'].items()) or not n['grantLive'] or n['fenced']:return None
            parent=self.handles[b['parentHandleHash']]
            if self.unresolved(b['scope'],b['footprint'],parent['key']):return None
        elif not self.eligible('R03',b['scope'],b['footprint']):return None
        key=(sk(b['scope']),b['operationId'])
        if key in self.obligations or not commit_proven:return None
        h=digest(b);handle=CommittedIOHandle(h)
        self.obligations[key]={'binding':deepcopy(b),'bindingHash':h,'state':'PENDING_IO','completionService':VER,
          'completionIncarnation':self.authority['incarnation'],'completionCapabilityHash':digest({'PRIVATE':h}),
          'verifiedOutcomeHash':None,'causalErrorHash':None,'protectedRecoveryHash':None}
        self.handles[h]={'object':handle,'key':key,'sendCount':0,'dispatchState':'NOT_INVOKED','attempt':b['attemptId']}
        self.private_caps[h]={'state':'LIVE','incarnation':self.authority['incarnation'],'error':None}
        # IO ledger rows are not security-authority version writers. Actual claim,
        # consent, containment, fence, config or lineage changes remain writers.
        return handle

    def invoke(self,h,body_sha,method,path):
        ref=self.handles.get(getattr(h,'handle_hash',None))
        if not ref or ref['object'] is not h or self.authority['state']!='ACTIVE':return False
        row=self.obligations[ref['key']];b=row['binding'];n=self.nodes[sk(b['scope'])]
        if row['state']!='PENDING_IO' or self.private_caps[h.handle_hash]['state']!='LIVE' or ref['sendCount'] or ref['dispatchState']!='NOT_INVOKED':return False
        if (body_sha,method,path)!=(b['bodySHA'],b['method'],b['rawPath']) or n['generation']!=b['generation'] or n['fenced'] or b['scope']['epoch']!=self.control_epoch or b['channelVersion']!=n['C'] or b['nodeDER']!=n['DER']:return False
        if b['kind'] in CONTINUATIONS and not self._parent_current(b):return False
        if b['effectClass']==SIDE_EFFECT:
            allowed={'DRAIN'} if b['kind']=='TERMINAL_FRAME' else set()
            if not n['grantLive'] or any(v and k not in allowed for (k,cause),v in n['facts'].items()):return False
            if n['profile']=='B' and (not self.chain_live(b['scope']) or not self.b_binding_current(b['scope'])):return False
            parent=self.handles.get(b['parentHandleHash']);ignore={ref['key']}|({parent['key']} if parent else set())
            if self.unresolved(b['scope'],b['footprint'],ignore):return False
        # Symbolic atomic dispatch/capability CAS. A real timeout after this edge
        # cannot be described as never invoked, even if transport says not sent.
        ref['dispatchState']='INVOKED';ref['sendCount']=1;return True

    def failure(self,h,persist_error=True,persist_fuse=True):
        ref=self.handles[h.handle_hash];row=self.obligations[ref['key']];cap=self.private_caps[h.handle_hash]
        cap.update(state='POISONED' if persist_fuse else 'PERSISTENCE_UNKNOWN',error=H)
        if row['binding']['effectClass']==READ_ONLY:
            if persist_error:row.update(state='NO_EFFECT_ABANDONED',causalErrorHash=H)
        elif persist_error:row.update(state='UNCERTAIN',causalErrorHash=H)
        # This operation/attempt capability only. No global authority fence.

    def restart_verifier(self):
        self.authority['durableSequence']+=1
        self.authority.update(incarnation='restart-'+str(self.authority['durableSequence'])) # restart never clears a real global trust fence
        for cap in self.private_caps.values():
            if cap['state']=='LIVE':cap['state']='LOST_INCARNATION'

    def abandon_read(self,c,h):
        ref=self.handles.get(getattr(h,'handle_hash',None))
        if not ref or ref['object'] is not h:return False
        row=self.obligations[ref['key']]
        if not self.authenticated(c,{VER,RECOVERY},row['binding']['scope']) or row['binding']['effectClass']!=READ_ONLY or row['state']!='PENDING_IO':return False
        row['state']='NO_EFFECT_ABANDONED';self.private_caps[h.handle_hash]['state']='CONSUMED';return True

    def abort_never_invoked(self,c,h):
        ref=self.handles.get(getattr(h,'handle_hash',None))
        if not ref or ref['object'] is not h:return False
        row=self.obligations[ref['key']];cap=self.private_caps[h.handle_hash]
        if not self.authenticated(c,{VER},row['binding']['scope']) or row['state']!='PENDING_IO' or ref['dispatchState']!='NOT_INVOKED' or ref['sendCount'] or cap['state']!='LIVE' or cap['incarnation']!=self.authority['incarnation']:return False
        # Same atomic row+private dispatcher CAS as invoke; no caller boolean.
        ref['dispatchState']='ABORTED';cap['state']='CONSUMED';row['state']='NO_EFFECT';return True

    def confirm(self,c,h,outcome,commit_receipt=True):
        ref=self.handles.get(getattr(h,'handle_hash',None))
        if not ref or ref['object'] is not h:return False
        row=self.obligations[ref['key']];cap=self.private_caps[h.handle_hash];b=row['binding']
        if self.authority['state']!='ACTIVE' or not self.authenticated(c,{VER},b['scope']) or c.incarnation!=self.authority['incarnation'] or cap['incarnation']!=c.incarnation or cap['state']!='LIVE' or row['state']!='PENDING_IO' or ref['dispatchState']!='INVOKED':return False
        if not verified(outcome,'EXISTING_VERIFIED_OUTCOME','SYMBOLIC_CURRENT_NODE_PEER') or outcome['body'].get('bindingHash')!=h.handle_hash or outcome['body'].get('existingKernelValidation')!='EXACT_TYPED_RECEIPT':self.failure(h);return False
        tag=outcome['body']['tag'];terminal={'EXECUTE','CANCEL','RECEIPT_OBSERVE','BUILD_DISPATCH','BUILD_CLEANUP_READ'}
        if tag not in ('ACTIVE','TERMINAL_CLEAN','OBSERVED') or tag=='ACTIVE' and b['kind']!='GPU_ACTIVE_OBSERVE' or b['kind'] in {'EXECUTE','CANCEL','RECEIPT_OBSERVE','BUILD_DISPATCH'} and tag!='TERMINAL_CLEAN' or tag=='TERMINAL_CLEAN' and b['kind'] not in terminal:self.failure(h);return False
        if not commit_receipt:return False # only proven rollback, not unknown commit
        row.update(state='CONFIRMED_OUTCOME',verifiedOutcomeHash=digest(outcome));cap['state']='CONSUMED'
        if tag=='TERMINAL_CLEAN':
            # Original exact kernel/physical receipt path only, not row-state.
            n=self.nodes[sk(b['scope'])]
            if b['claimBindingSHA'] in n['activeClaims']:
                versions=n.setdefault('claimVersions',{});versions[b['claimBindingSHA']]=versions.get(b['claimBindingSHA'],0)+1
            n['activeClaims'].discard(b['claimBindingSHA'])
            n['leaseActive']=bool(n['activeClaims']);n['workloadActive']=bool(n['activeClaims'])
        return True

    def recovery_ack(self,h,tag='DURABLE_EXACT_ACK',valid=True):
        row=self.obligations[self.handles[h.handle_hash]['key']];b=row['binding']
        return seal('RECOVERY_OBSERVATION',{'bindingHash':h.handle_hash,'scope':b['scope'],'generation':b['generation'],
          'commandHash':b['bodySHA'],'nonce':b['nonce'],'target':b['rawPath'],'targetBindingSHA':b['targetBindingSHA'],'channelVersion':b['channelVersion'],'nodeDER':b['nodeDER'],'attemptId':b['attemptId'],'outcome':tag},'SYMBOLIC_CURRENT_NODE_PEER' if valid else 'FORGED')

    def reconcile_safety(self,c,h,ack):
        ref=self.handles.get(getattr(h,'handle_hash',None))
        if not ref or ref['object'] is not h or self.authority['state']!='ACTIVE':return False
        row=self.obligations[ref['key']];b=row['binding'];n=self.nodes[sk(b['scope'])]
        if not self.authenticated(c,{RECOVERY},b['scope']) or self.authority['state']!='ACTIVE' or b['effectClass']!=SAFETY or row['state'] not in ('PENDING_IO','UNCERTAIN') or n['generation']!=b['generation'] or n['fenced'] or b['scope']['epoch']!=self.control_epoch or b['channelVersion']!=n['C'] or b['nodeDER']!=n['DER']:return False
        if b['kind']=='B_GATE_INVALIDATE' and getattr(self,'_verified_gate_recovery',{}).get(h.handle_hash) is not ack:return False
        if not verified(ack,'RECOVERY_OBSERVATION','SYMBOLIC_CURRENT_NODE_PEER') or ack['body']!={
          'bindingHash':h.handle_hash,'scope':b['scope'],'generation':b['generation'],'commandHash':b['bodySHA'],
          'nonce':b['nonce'],'target':b['rawPath'],'targetBindingSHA':b['targetBindingSHA'],'channelVersion':b['channelVersion'],'nodeDER':b['nodeDER'],'attemptId':b['attemptId'],'outcome':'DURABLE_EXACT_ACK'}:return False
        row.update(state='CONFIRMED_OUTCOME',verifiedOutcomeHash=digest(ack));self.private_caps[h.handle_hash]['state']='CONSUMED'
        # No claim freeing, fact clearing, or Node/CP gate advance. Those require
        # their ORIGINAL typed receipt/ACK consumers in the same implementation TX.
        return True

    def retry_safety_exact(self,c,h,body_sha):
        ref=self.handles.get(getattr(h,'handle_hash',None))
        if not ref or ref['object'] is not h or self.authority['state']!='ACTIVE':return False
        row=self.obligations[ref['key']];b=row['binding'];n=self.nodes[sk(b['scope'])]
        if not self.authenticated(c,{RECOVERY},b['scope']) or b['effectClass']!=SAFETY or row['state']!='UNCERTAIN' or body_sha!=b['bodySHA'] or n['generation']!=b['generation'] or n['C']!=b['channelVersion'] or n['DER']!=b['nodeDER'] or b['scope']['epoch']!=self.control_epoch or n['fenced']:return False
        ref['freshRecoverySameCommandSends']=ref.get('freshRecoverySameCommandSends',0)+1
        # Original completion cap remains dead and row uncertain until verified ACK.
        return True

    def preserve_capability_death(self,before):
        restored=deepcopy(before)
        for h,c in self.private_caps.items():
            if c['state'] in ('POISONED','PERSISTENCE_UNKNOWN','LOST_INCARNATION'):restored[h]=deepcopy(c)
        return restored

    def reconcile_gate_ack(self,c,outid,h,ack,transaction_commits=True):
        ref=self.handles.get(getattr(h,'handle_hash',None));out=self.outbox.get(outid)
        if not ref or ref['object'] is not h or not out:return False
        row=self.obligations[ref['key']];b=row['binding'];n=self.nodes[sk(b['scope'])]
        current=n['gateRecords'].get(n['recordId']);issued=self.issued.get(out['commandHash']);command=issued['signature'] if issued else None
        if not self.authenticated(c,{RECOVERY},b['scope']) or not transaction_commits or b['kind']!='B_GATE_INVALIDATE' or out['scope']!=b['scope'] or not command or not current or current['ack']!=ack:return False
        expected_target=digest({'gateId':out['targetGateId'],'releaseHash':out['targetReleaseHash'],'staticHash':n['staticHash']})
        if b['bodySHA']!=out['commandHash'] or b['nonce']!=command['body']['nonce'] or b['targetBindingSHA']!=expected_target:return False
        if not verified(ack,'GATE_ACK','SYMBOLIC_NODE_LEAF') or not shape('gateAck',ack['body']) or self.now>=ack['body']['expiresAt']:return False
        exact={'tenantId':b['scope']['tenantId'],'nodeId':b['scope']['nodeId'],'epoch':b['scope']['epoch'],'generation':b['generation'],'nodeCertificateSHA256':b['nodeDER'],'nonce':b['nonce'],'commandHash':b['bodySHA'],'gateId':out['targetGateId'],'releaseHash':out['targetReleaseHash'],'state':'INVALIDATED','action':'INVALIDATE_EXACT_GATE'}
        if any(ack['body'].get(k)!=v for k,v in exact.items()):return False
        proof=self.recovery_ack(h);self._verified_gate_recovery={h.handle_hash:proof}
        before=(deepcopy(self.obligations),deepcopy(self.private_caps),deepcopy(self.outbox))
        try:
            if not self.reconcile_safety(c,h,proof) or not self.record_invalidation_ack(c,outid,ack):
                self.obligations,self.private_caps,self.outbox=before;return False
            n['cpGate']=deepcopy(n['gate']);n['cpRecordId']=n['recordId'];return True
        finally:self._verified_gate_recovery={}

    def signature_footprint(self,s,kind,body):
        n=self.nodes[sk(s)]
        # Role-wide ARM affects all existing claims on this Node; plain approval
        # renewal preserves exact config and does not lock a workload's claims.
        claims=[list(pair) for pair in sorted(n.get('claimVersions',{}).items())] if kind=='GATE_CONTROL' and body.get('action')=='ARM_EXACT_RELEASE' else []
        return digest({'scope':s,'kind':kind,'action':body.get('action'),'nodeAuthorityVersion':n['authorityVersion'],
          'lineageVersion':n['lineageVersion'],'staticHash':n['staticHash'],'relevantClaimVersions':claims})

    def apply_heartbeat(self,c,h,outcome):
        b=self.obligations[self.handles[h.handle_hash]['key']]['binding']
        if b['kind']!='HEARTBEAT_OBSERVE' or not self.confirm(c,h,outcome):return False
        n=self.nodes[sk(b['scope'])]
        if n['liveness']=='offline':n['liveness']='online';n['authorityVersion']+=1
        # Existing offline->online liveness rule only; no fact is removed.
        return True

    def seed_read_parent_fixture(self,s):
        # DATA-ONLY FIXTURE of an independently committed CP project/source-plan
        # read authorization, no kernel Run, workload claim or host-path right.
        from io_contract import fixture_footprint
        n=self.nodes[sk(s)];fp=fixture_footprint();fp['rows']=[r for r in fp['rows'] if r['table']=='inv.node_channels']
        record={'scope':deepcopy(s),'generation':n['generation'],'C':n['C'],'DER':n['DER'],'readUntil':self.now+30,
          'revoked':False,'ownerBindingSHA':digest({'synthetic':'project-read-owner'}),'targetBindingSHA':digest({'synthetic':'immutable-object-source-plan'}),'footprint':fp}
        key=digest(record)
        if not hasattr(self,'read_parents'):self.read_parents={}
        self.read_parents[key]=record;return key
