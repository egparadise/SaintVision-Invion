"""Rev6 targeted schema/state/race fixtures, no crypto/PG/Node/Engine operation."""
from copy import deepcopy
import json
from pathlib import Path
import model as m
from authority import build,invariants,OP,VER,RUN,DEL,SAFE,REV,ISS,BUD
from rank_contract import CATALOG,check as check_ranks

E=Path(__file__).resolve().parent;CASES=[];TRACES=[]


def check(name,value,expected=True):
    CASES.append(dict(case=name,passed=value==expected,actual=value,expected=expected))
    assert value==expected,(name,value,expected)


def snapshot(w,label):return dict(label=label,now=w.now,obligations=[dict(bindingHash=r['bindingHash'],state=r['state']) for r in w.obligations.values()],authority=deepcopy(w.authority))


def physical(handle):return m.seal('PROTECTED_PHYSICAL_RECOVERY',{'bindingHash':handle.handle_hash,'recovery':'EXACT_PHYSICAL_RECONCILIATION'},'SYMBOLIC_OPERATOR_INDEPENDENT_PHYSICAL_VERIFIER')
def clear_proof(s,kind,cause='original-operation'):return m.seal('EXISTING_PROTECTED_CLEAR',{'scope':s,'factKind':kind,'causeOperationId':cause,'recovery':'EXACT_PHYSICAL_RECONCILIATION'},'SYMBOLIC_OPERATOR_INDEPENDENT_PHYSICAL_VERIFIER')


def schema_cases(kind,value,branch=None):
    check('schema-positive-'+kind,m.shape(kind,value))
    check('schema-extra-'+kind,m.shape(kind,{**deepcopy(value),'unrequested':True}),False)
    selected=branch or m.SCHEMA['$defs'][kind]
    for field in selected['required']:
        bad=deepcopy(value);bad.pop(field);check('schema-missing-'+kind+'-'+field,m.shape(kind,bad),False)
        bad=deepcopy(value);bad[field]={};check('schema-type-'+kind+'-'+field,m.shape(kind,bad),False)


def main():
    # Ordinary success, exact own first IO despite registration denial, active
    # observation retains every workload/claim/lease; both DB-selected profiles.
    for profile in ('PLAIN','B'):
        w=m.World();s=m.scope();w.nodes[m.sk(s)]['profile']=profile;r=w.connect(RUN);v=w.connect(VER)
        trace=[snapshot(w,'before-registration')];b=m.binding(w,kind='GPU_ACTIVE_OBSERVE');w.now+=1
        h=w.register(r,b);check(profile+'-registration-committed',h is not None);trace.append(snapshot(w,'registered'))
        for reader in w.readers:check(profile+'-'+reader+'-unresolved-denial',w.eligible(reader,s),False)
        check(profile+'-exact-own-first-IO',w.invoke(h,b['bodySHA'],b['method'],b['rawPath']))
        check(profile+'-new-admission-not-opid-bypass',w.eligible('R03',s),False)
        check(profile+'-observe-lane-remains-available',w.observe_scope(r,s)=={'available':True,'businessAuthority':False})
        w.now+=2;check(profile+'-ordinary-ACTIVE-confirm',w.confirm(v,h,w.outcome(h,'ACTIVE')))
        n=w.nodes[m.sk(s)];check(profile+'-ACTIVE-retains-claims',n['activeClaims']=={'claim-1'} and n['leaseActive'] and n['workloadActive'])
        for reader in w.readers:check(profile+'-'+reader+'-confirmed-no-ambiguity',w.eligible(reader,s))
        trace.append(snapshot(w,'confirmed-outcome-no-OP'));TRACES.append(trace)
    # Terminal receipt and IO state commit atomically. Confirmation by itself is
    # not a resource release; original validated terminal kernel path is required.
    w=m.World();r=w.connect(RUN);v=w.connect(VER);b=m.binding(w);h=w.register(r,b)
    check('terminal-receipt-transaction-failure-no-close',w.confirm(v,h,w.outcome(h,'TERMINAL_CLEAN'),commit_receipt=False),False)
    check('terminal-failure-retains-claims',w.nodes[m.sk(m.scope())]['leaseActive'])
    check('terminal-independent-exact-receipt',w.confirm(v,h,w.outcome(h,'TERMINAL_CLEAN')))
    check('terminal-original-kernel-path-releases-only-validated',not w.nodes[m.sk(m.scope())]['leaseActive'])
    w=m.World();r=w.connect(RUN);v=w.connect(VER);h=w.register(r,m.binding(w))
    check('observation-cannot-stand-in-for-terminal-receipt',w.confirm(v,h,w.outcome(h,'OBSERVED')),False)
    check('wrong-outcome-kind-retains-lease',w.nodes[m.sk(m.scope())]['leaseActive'])
    for field in ('bodySHA','method','rawPath','nonce','runId','generation','claimBindingSHA','existingPermitOrApprovalSHA'):
        w=m.World();r=w.connect(RUN);b=m.binding(w);bad=deepcopy(b);bad[field]='f'*64 if field.endswith(('SHA','nonce')) else 'wrong'
        check('registration-original-binding-deny-'+field,w.register(r,bad) is None)
    w=m.World();r=w.connect(RUN);b=m.binding(w);check('no-IO-without-proven-COMMIT',w.register(r,b,commit_proven=False) is None)
    h=w.register(r,b);check('fake-handle-same-hash-no-capability',w.invoke(m.CommittedIOHandle(h.handle_hash),b['bodySHA'],b['method'],b['rawPath']),False)
    check('request-substitution-refused',w.invoke(h,'f'*64,b['method'],b['rawPath']),False)
    check('duplicate-send-refused-after-exact-own-send',w.invoke(h,b['bodySHA'],b['method'],b['rawPath']))
    check('duplicate-send-not-new-operation',w.invoke(h,b['bodySHA'],b['method'],b['rawPath']),False)
    # Failure/unknown/EXECUTE loss: explicit poisoned/lost completion capability,
    # not a healthy bit. Losing DB error persistence leaves PENDING denial.
    for persist_error,persist_fuse in ((True,True),(False,True),(False,False)):
        w=m.World();r=w.connect(RUN);v=w.connect(VER);op=w.connect(OP);b=m.binding(w);h=w.register(r,b)
        w.now+=2;w.failure(h,persist_error=persist_error,persist_fuse=persist_fuse);w.now+=2
        check('failure-state-'+str((persist_error,persist_fuse)),w.obligations[(m.sk(m.scope()),b['operationId'])]['state']==('UNCERTAIN' if persist_error else 'PENDING_IO'))
        for reader in w.readers:check('EXECUTE-loss-'+str((persist_error,persist_fuse))+'-'+reader,w.eligible(reader,m.scope()),False)
        check('swallowed-fence-cannot-fallthrough-confirm-'+str((persist_error,persist_fuse)),w.confirm(v,h,w.outcome(h,'TERMINAL_CLEAN')),False)
        check('RUN-no-uncertain-settle-'+str((persist_error,persist_fuse)),w.settle(r,h,physical(h)),False)
        check('OP-no-proof-settle-'+str((persist_error,persist_fuse)),w.settle(op,h),False)
        check('protected-exact-recovery-'+str((persist_error,persist_fuse)),w.settle(op,h,physical(h)))
        check('protected-settle-not-physical-stop',w.nodes[m.sk(m.scope())]['leaseActive'])
    w=m.World();r=w.connect(RUN);v=w.connect(VER);h=w.register(r,m.binding(w));w.failure(h,persist_error=False);w.restart_verifier();newv=w.connect(VER)
    check('restart-no-reconstructed-completion-capability',w.confirm(newv,h,w.outcome(h,'TERMINAL_CLEAN')),False)
    check('old-verifier-incarnation-refused',w.confirm(v,h,w.outcome(h,'TERMINAL_CLEAN')),False)
    check('mismatched-receipt-denied',w.confirm(newv,h,w.outcome(h,'TERMINAL_CLEAN',valid=False)),False)
    w=m.World();r=w.connect(RUN);v=w.connect(VER);h=w.register(r,m.binding(w))
    check('healthy-capability-mismatched-receipt-poisons',w.confirm(v,h,w.outcome(h,'TERMINAL_CLEAN',valid=False)),False)
    check('mismatch-cannot-fallthrough-later-good-receipt',w.confirm(v,h,w.outcome(h,'TERMINAL_CLEAN')),False)
    # Scope tests insert historical/other-node rows directly as FIXTURE DATA.
    for other in (m.scope(n='node-2'),m.scope(t='tenant-other'),m.scope(e='epoch-old')):
        w=m.World();w.obligations[(m.sk(other),'other-operation')]={'state':'UNCERTAIN'}
        for reader in w.readers:check('wrong-scope-'+str(m.sk(other))+'-'+reader,w.eligible(reader,m.scope()))
    w=m.World();w.control_epoch='epoch-new';check('stale-current-epoch-denied',w.eligible('R03',m.scope()),False)
    # Orthogonal persistent facts. One protected clear cannot erase old drain
    # nor another quarantine cause. Observation changes liveness only.
    w=m.World();op=w.connect(OP);safe=w.connect(SAFE);s=m.scope()
    w.set_fact(op,s,'DRAIN');w.set_fact(safe,s,'QUARANTINE');check('projection-quarantine-retains-drain',w.projection(s)=='quarantined' and w.nodes[m.sk(s)]['facts'][('DRAIN','original-operation')])
    check('clear-quarantine-with-exact-proof',w.set_fact(op,s,'QUARANTINE',False,clear_proof(s,'QUARANTINE')))
    check('clear-reveals-preserved-drain',w.projection(s)=='draining')
    w.nodes[m.sk(s)]['liveness']='online';check('observation-never-clears-drain',w.eligible('R01',s),False)
    w.set_fact(safe,s,'QUARANTINE',cause='second-cause');w.set_fact(op,s,'QUARANTINE',True,cause='first-cause')
    w.set_fact(op,s,'QUARANTINE',False,clear_proof(s,'QUARANTINE','first-cause'),cause='first-cause')
    check('clear-own-cause-only',w.projection(s)=='quarantined')
    check('runtime-cannot-clear-fact',w.set_fact(w.connect(RUN),s,'DRAIN',False,clear_proof(s,'DRAIN')),False)
    # Signing SERVICE direct call, independent of CP caller command helper.
    for kind in ('GATE_CONTROL','RELEASE','DELEGATION','DELIVERY_CHALLENGE','KEY_DELIVERY_RECEIPT'):
        w=m.World();s=m.scope();op=w.connect(OP);caller=w.connect(DEL) if kind.startswith(('DELIVERY','KEY_DELIVERY')) else op
        if kind=='KEY_DELIVERY_RECEIPT':w.nodes[m.sk(s)]['activation']['deliveryState']='CONSUMED_PENDING_RECEIPT' # FIXTURE verified PoP/consumption already committed
        body=m.sign_body(w,kind=kind);check('service-positive-'+kind,w.sign(caller,s,kind,body) is not None)
        w=m.World();op=w.connect(OP);caller=w.connect(DEL) if kind.startswith(('DELIVERY','KEY_DELIVERY')) else op;body=m.sign_body(w,kind=kind)
        if kind=='KEY_DELIVERY_RECEIPT':w.nodes[m.sk(s)]['activation']['deliveryState']='CONSUMED_PENDING_RECEIPT';body=m.sign_body(w,kind=kind)
        w.revoke(op,s,causal=m.H);w.now+=1
        sig=w.sign(caller,s,kind,body);check('MA3b-direct-service-revoked-deny-'+kind,sig is None)
        if kind=='GATE_CONTROL':check('MA3c-no-Node-ARM-after-denied-signature',w.node_gate(s,sig) is None)
    for mutate in ('revoke','fence','tuple','expiry','missing-ancestor'):
        w=m.World();s=m.scope();op=w.connect(OP);body=m.sign_body(w);intent=w.prepare_sign(op,s,'GATE_CONTROL',body);assert intent
        w.now+=1;assert w.hsm_sign_private(intent)
        check('HSM-not-exposed-before-publication-'+mutate,not w.issued)
        if mutate=='revoke':w.revoke(op,s,causal=m.H)
        elif mutate=='fence':w.nodes[m.sk(s)]['fenced']=True;w.nodes[m.sk(s)]['authorityVersion']+=1
        elif mutate=='tuple':w.nodes[m.sk(s)]['C']+=1;w.nodes[m.sk(s)]['authorityVersion']+=1
        elif mutate=='missing-ancestor':w.nodes[m.sk(s)]['approvals'].pop('A0')
        else:w.now=body['expiresAt']+1
        check('race-before-publication-'+mutate,w.publish_sign(op,intent) is None)
    w=m.World();op=w.connect(OP);body=m.sign_body(w);forged=m.Connection(OP,'installed-1')
    check('caller-role-label-not-authenticated',w.sign(forged,m.scope(),'GATE_CONTROL',body) is None)
    for caller in (RUN,VER,ISS,SAFE,REV,BUD,DEL):check('installed-purpose-no-ARM-'+caller,w.sign(w.connect(caller),m.scope(),'GATE_CONTROL',body) is None)
    w=m.World();op=w.connect(OP);body=m.sign_body(w);body['lineageLive']=True
    check('caller-boolean-not-authority',w.sign(op,m.scope(),'GATE_CONTROL',body) is None)
    w=m.World();op=w.connect(OP);body=m.sign_body(w);body['channelVersion']=True
    check('bool-not-channel-integer',w.sign(op,m.scope(),'GATE_CONTROL',body) is None)
    w=m.World();op=w.connect(OP);w.now+=601
    check('ancestor-time-expiry-still-current-descendant',w.sign(op,m.scope(),'GATE_CONTROL',m.sign_body(w)) is not None)
    w=m.World();op=w.connect(OP);check('same-config-renew-service-preserved',w.sign(op,m.scope(),'APPROVAL',m.sign_body(w,kind='APPROVAL')) is not None)
    w.now+=1801;check('expired-current-protected-reapprove-preserved',w.sign(op,m.scope(),'APPROVAL',m.sign_body(w,kind='APPROVAL')) is not None)
    # Ordinary planned renewal INVALIDATE uses the protected switch intent,
    # never creates a lineage-revoking tombstone. SAFE cannot use this OP path.
    w=m.World();s=m.scope();op=w.connect(OP);v=w.connect(VER);sid=w.begin_planned_switch(op,s);assert sid
    invbody=m.sign_body(w,action='INVALIDATE_EXACT_GATE',switch_id=sid)
    check('SAFE-cannot-borrow-ordinary-switch-intent',w.sign(w.connect(SAFE),s,'GATE_CONTROL',invbody) is None)
    inv=w.sign(op,s,'GATE_CONTROL',invbody);assert inv
    b=m.binding(w,op='planned-invalidate',kind='B_GATE_INVALIDATE');b.update(bodySHA=m.digest(inv),nonce=inv['body']['nonce']);w.original_requests[(m.sk(s),b['operationId'])]=deepcopy(b)
    h=w.register(v,b);assert h and w.invoke(h,b['bodySHA'],b['method'],b['rawPath']);ack=w.node_gate(s,inv);assert ack
    check('planned-switch-confirm-ACK',w.confirm_planned_gate_ack(v,s,sid,h,ack))
    check('planned-switch-no-lineage-tombstone',not w.tombstones and w.chain_live(s))
    check('planned-invalidated-gate-business-denied',w.eligible('R03',s),False)
    arm=w.sign(op,s,'GATE_CONTROL',m.sign_body(w));assert arm
    b=m.binding(w,op='planned-arm',kind='B_GATE_ARM');b.update(bodySHA=m.digest(arm),nonce=arm['body']['nonce']);w.original_requests[(m.sk(s),b['operationId'])]=deepcopy(b)
    h=w.register(v,b);assert h and w.invoke(h,b['bodySHA'],b['method'],b['rawPath']);ack=w.node_gate(s,arm);assert ack
    check('planned-new-ARM-confirm-ACK',w.confirm_planned_gate_ack(v,s,sid,h,ack))
    check('new-ARM-not-current-delivered-chain-yet',w.eligible('R03',s),False)
    check('old-gate-release-terminal-history','gate-0' in w.nodes[m.sk(s)]['retiredGates'] and 'd'*64 in w.nodes[m.sk(s)]['retiredReleases'])
    # A valid issuance committed before revoke can still arrive at Node until
    # ACK/expiry. Node does not read CP tombstones or a CP publication registry.
    w=m.World();s=m.scope();op=w.connect(OP);w.nodes[m.sk(s)]['gate']=None;w.nodes[m.sk(s)]['cpGate']=None;body=m.sign_body(w);sig=w.sign(op,s,'GATE_CONTROL',body);assert sig
    w.revoke(op,s,causal=m.H);w.now+=1;ack=w.node_gate(s,sig)
    check('post-issuance-revoke-honest-Node-bound',ack is not None)
    check('CP-current-immediate-revoke-denial',w.eligible('R03',s),False)
    # Unsigned CP tombstone -> exact INVALIDATE outbox/service -> existing Node
    # durable invalidator -> ACK. No Node tombstone domain/cache is invented.
    w=m.World();s=m.scope();safe=w.connect(SAFE);rev=w.connect(REV);v=w.connect(VER)
    outid=w.revoke(safe,s,causal=m.H);out=w.outbox[outid]
    schema_cases('cpTombstoneRecord',next(iter(w.tombstones.values())))
    schema_cases('revocationOutbox',out)
    check('unsigned-CP-tombstone-no-signature','signature' not in next(iter(w.tombstones.values())))
    check('no-fictitious-Node-tombstone-domain','LINEAGE_TOMBSTONE' not in m.DOMAINS and 'knownLineageRevocations' not in w.nodes[m.sk(s)])
    body=m.sign_body(w,action='INVALIDATE_EXACT_GATE',outid=outid);intent=w.prepare_sign(rev,s,'GATE_CONTROL',body);assert intent
    check('outbox-prepared',out['state']=='PREPARED');w.now+=1;w.hsm_sign_private(intent);check('outbox-private-signature-stage',out['state']=='SIGNED_UNPUBLISHED')
    w.now+=1;command=w.publish_sign(rev,intent);assert command;check('outbox-publication-ready',out['state']=='READY_TO_DISPATCH')
    b=m.binding(w,op='invalidate-op',kind='B_GATE_INVALIDATE');b.update(bodySHA=m.digest(command),nonce=command['body']['nonce']);w.original_requests[(m.sk(s),b['operationId'])]=deepcopy(b)
    h=w.register(safe,b);assert h;check('dispatch-exact-committed-safety-handle',w.dispatch_invalidation(rev,outid,command,h))
    w.now+=1;ack=w.node_gate(s,command);assert ack;check('existing-ACK-wire-shape',m.shape('gateAck',ack['body']))
    check('Node-invalidation-terminal',w.nodes[m.sk(s)]['gate']['state']=='INVALIDATED')
    check('gate-ACK-and-IO-atomic-failure',w.confirm_gate_ack(v,outid,h,ack,transaction_commits=False),False)
    check('failed-ACK-commit-retains-pending',w.obligations[(m.sk(s),b['operationId'])]['state']=='PENDING_IO')
    w.now+=1;check('gate-ACK-and-IO-atomic-success',w.confirm_gate_ack(v,outid,h,ack));check('outbox-ACK-recorded',out['state']=='ACK_RECORDED')
    check('duplicate-original-ACK-no-new-time',w.node_gate(s,command)==ack)
    readback=w.gate_readback(v,s);schema_cases('gateObservation',readback['body'],m.SCHEMA['$defs']['gateObservation']['oneOf'][0])
    w.now=ack['body']['expiresAt']+1;stale=w.gate_readback(v,s)
    check('lost-ACK-stale-HOLD',stale['body']['status']=='STALE_ACK');schema_cases('gateObservation',stale['body'],m.SCHEMA['$defs']['gateObservation']['oneOf'][1])
    check('no-old-ACK-renew-time',w.node_gate(s,command) is None or w.node_gate(s,command)==ack)
    w=m.World();op=w.connect(OP);oid=w.revoke(op,m.scope(),causal=m.H,known_gate=False)
    check('unknown-gate-propagation-HOLD',w.outbox[oid]['state']=='UNKNOWN_TARGET_HOLD')
    check('unknown-gate-no-invalidation-signature',w.sign(op,m.scope(),'GATE_CONTROL',m.sign_body(w,action='INVALIDATE_EXACT_GATE',outid=oid)) is None)
    # Plain activation correction vs additional B-only root proof.
    matrix=build();check('plain-owner-no-new-confirmation',matrix['procedures']['b_activate_owner_contribution']['requiresNodeConfirmation'],False)
    w=m.World();s=m.scope();ver=w.connect(VER);op=w.connect(OP);w.nodes[m.sk(s)]['installedROMountProof']=False;obs=w.folder_observe(ver,s,m.H)
    schema_cases('folderRootObservation',obs['body']);check('B-folder-positive-current-root',w.approve_folder(op,s,obs))
    check('preflight-not-installed-RO-mount',w.nodes[m.sk(s)]['installedROMountProof'],False)
    check('preflight-alone-never-business-admission',w.eligible('R03',s),False)
    check('preflight-alone-no-ARM-signature',w.sign(op,s,'GATE_CONTROL',m.sign_body(w)) is None)
    w=m.World();v=w.connect(VER);limited=w.connect(OP,scopes=[m.scope()]);other=m.scope(n='node-2');proof=w.folder_observe(v,other,m.H)
    check('folder-operator-cannot-impersonate-other-scope',w.approve_folder(limited,other,proof),False)
    for field in ('normalizedPath','heldRoot','generation','channelVersion','nodeDER','policyR','policyHash','ownerConsentVersion','challenge','contributionId'):
        w=m.World();ver=w.connect(VER);op=w.connect(OP);obs=w.folder_observe(ver,s,m.H);body=deepcopy(obs['body'])
        if field=='heldRoot':body[field]['inode']='9'
        elif isinstance(body[field],int):body[field]+=1
        else:body[field]='wrong' if field not in ('nodeDER','policyHash','challenge') else 'f'*64
        bad=m.seal('FOLDER_ROOT_OBSERVATION',body,'SYMBOLIC_CURRENT_NODE_LEAF')
        check('B-folder-binding-deny-'+field,w.approve_folder(op,s,bad),False)
    w=m.World();ver=w.connect(VER);op=w.connect(OP);obs=w.folder_observe(ver,s,m.H);w.now+=31
    check('B-folder-stale-deny',w.approve_folder(op,s,obs),False)
    for change in ('revoked','withdraw-version','new-DER','mount-substitution'):
        w=m.World();ver=w.connect(VER);op=w.connect(OP);obs=w.folder_observe(ver,s,m.H);n=w.nodes[m.sk(s)]
        if change=='revoked':n['contribution']['status']='revoked'
        elif change=='withdraw-version':n['contribution']['version']+=1
        elif change=='new-DER':n['DER']='f'*64;n['C']+=1
        else:n['root']['mountIdentityHash']='f'*64
        check('B-folder-current-change-'+change,w.approve_folder(op,s,obs),False)
    available={'status':'AVAILABLE','observation':obs['body']};refused={'status':'ROOT_UNKNOWN','businessAuthority':False,'scope':s,'challenge':m.H,'observedAt':w.now,'reason':'UNVERIFIABLE_ROOT'}
    schema_cases('folderRootResponse',available,m.SCHEMA['$defs']['folderRootResponse']['oneOf'][0]);schema_cases('folderRootResponse',refused,m.SCHEMA['$defs']['folderRootResponse']['oneOf'][1])
    check('folder-refusal-no-eligible-root',m.shape('folderRootResponse',{**refused,'observation':obs['body']}),False)
    check('folder-preflight-no-future-RO-field',m.shape('folderRootObservation',{**obs['body'],'installedReadonlyMount':True}),False)
    check('authority-semantic-invariants',not invariants(matrix));check('ALL-table-ranks-and-procedure-locklists',not check_ranks(matrix))
    for table in matrix['tables']:check('explicit-rank-'+table,table in CATALOG)
    for name,proc in matrix['procedures'].items():
        check('exact-numeric-lock-order-'+name,[r['rank'] for r in proc['lockList']]==sorted(r['rank'] for r in proc['lockList']))
    result={'level':'SCHEMA_STATEFUL_SYMBOLIC_ONLY','passed':len(CASES),'failed':0,'cases':CASES,'advancingTimeTraces':TRACES,
        'prior335':'immutable Rev5 cases and actual reviewer reproduction preserved; NOT relabelled as new runtime evidence',
        'actualNewGoCryptoPGEngineCrashConcurrencyEquipment':0,'A1_A16':'PENDING','realBindings':None}
    (E/'fixture-results.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps({'passed':len(CASES),'failed':0,'actualB':0}))


if __name__=='__main__':main()
