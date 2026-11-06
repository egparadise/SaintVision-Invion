"""Rev7 advancing-state symbolic counterexamples; NO actual crypto/DB/Node IO."""
import json
from copy import deepcopy
from pathlib import Path
from model import World,binding,scope,sk,VER,RUN,OP,SAFE,REV,seal,sign_body,H,CommittedIOHandle,digest
from io_contract import EFFECT,READ_ONLY,SAFETY,RECOVERY,fixture_footprint
from schema import build
from jsonschema import Draft202012Validator
E=Path(__file__).resolve().parent;R=[];s=scope();s2=scope(n='node-2')
def check(name,value):
    R.append({'case':name,'pass':bool(value)});assert value,name
def state(w,h):return w.obligations[w.handles[h.handle_hash]['key']]['state']
def send(w,h):
    b=w.obligations[w.handles[h.handle_hash]['key']]['binding'];return w.invoke(h,b['bodySHA'],b['method'],b['rawPath'])
def parent(w,c):return w.register(c,binding(w,op='parent'))
def phys(h):return seal('PROTECTED_PHYSICAL_RECOVERY',{'bindingHash':h.handle_hash,'recovery':'EXACT_PHYSICAL_RECONCILIATION'},'SYMBOLIC_OPERATOR_INDEPENDENT_PHYSICAL_VERIFIER')

def main():
    for profile in ('PLAIN','B'):
        for kind,effect in EFFECT.items():
            w=World();w.nodes[sk(s)]['profile']=profile;c=w.connect(VER);ph=parent(w,c) if kind in ('OBJECT_READ','BUILD_CLEANUP_READ','CANCEL','RECEIPT_OBSERVE','TERMINAL_FRAME') else None
            b=binding(w,op='attempt',kind=kind,parent=ph.handle_hash if ph else None)
            bad=deepcopy(b);bad['effectClass']='READ_ONLY' if effect!='READ_ONLY' else 'SIDE_EFFECT'
            check(profile+kind+'-caller-cannot-downgrade',w.register(c,bad) is None)
            h=w.register(c,b)
            if profile=='PLAIN' and kind in ('B_GATE_ARM','B_GATE_INVALIDATE','B_ROLE_OBSERVE'):
                check(profile+kind+'-no-implicit-B-role',h is None);continue
            check(profile+kind+'-register',h is not None)
            check(profile+kind+'-forged-opaque-handle',not w.invoke(CommittedIOHandle(h.handle_hash),b['bodySHA'],b['method'],b['rawPath']))
            check(profile+kind+'-invoke',send(w,h));check(profile+kind+'-no-resend',not send(w,h));w.now+=3;w.failure(h)
            check(profile+kind+'-failure-state',state(w,h)==('NO_EFFECT_ABANDONED' if effect==READ_ONLY else 'UNCERTAIN'))
            check(profile+kind+'-poison-not-ordinary',not w.confirm(c,h,w.outcome(h,'OBSERVED')))
            if effect==READ_ONLY:
                check(profile+kind+'-read-no-business-denial',w.eligible('R03',s,fixture_footprint('other','other-run')))
                check(profile+kind+'-no-OP-needed',not w.settle(w.connect(OP),h,phys(h)))
            elif effect==SAFETY:
                rv=w.connect(RECOVERY);check(profile+kind+'-forged-recovery-refused',not w.reconcile_safety(rv,h,w.recovery_ack(h,valid=False)))
                check(profile+kind+'-unrelated-role-refused',not w.reconcile_safety(w.connect(RUN),h,w.recovery_ack(h)))
                check(profile+kind+'-wrong-retry-refused',not w.retry_safety_exact(rv,h,'0'*64))
                check(profile+kind+'-same-command-recovery-send',w.retry_safety_exact(rv,h,b['bodySHA']))
                if kind=='B_GATE_INVALIDATE':
                    check(profile+kind+'-generic-gate-ACK-insufficient',not w.reconcile_safety(rv,h,w.recovery_ack(h)))
                    continue
                check(profile+kind+'-exact-fresh-recovery',w.reconcile_safety(rv,h,w.recovery_ack(h)))
                check(profile+kind+'-recovery-replay-refused',not w.reconcile_safety(rv,h,w.recovery_ack(h)))
                check(profile+kind+'-safety-ACK-retains-workload',w.nodes[sk(s)]['workloadActive'])
            else:
                check(profile+kind+'-side-unknown-protected',w.settle(w.connect(OP),h,phys(h)))
    w=World();c=w.connect(VER);op=w.connect(OP)
    b=binding(w,op='hb',kind='HEARTBEAT_OBSERVE');h=w.register(c,b)
    check('pending-read-does-not-deny',w.eligible('R03',s));v=w.nodes[sk(s)]['authorityVersion'];send(w,h);w.failure(h)
    check('failed-read-no-security-version-change',w.nodes[sk(s)]['authorityVersion']==v)
    w.now+=5;hb=w.register(c,binding(w,op='hb-next',kind='HEARTBEAT_OBSERVE'));send(w,hb)
    check('good-later-heartbeat-original-verifier-success',w.confirm(c,hb,w.outcome(hb,'OBSERVED')))
    check('good-later-heartbeat-no-OP',w.eligible('R03',s))
    w.set_fact(op,s,'DRAIN',cause='prior');check('good-heartbeat-never-clears-drain',not w.eligible('R03',s))
    w=World();c=w.connect(VER);op=w.connect(OP);i=w.prepare_sign(op,s,'GATE_CONTROL',sign_body(w));w.hsm_sign_private(i)
    w.register(c,binding(w,kind='HEARTBEAT_OBSERVE'));check('prepared-ARM-survives-read-registration',w.publish_sign(op,i) is not None)
    w=World();op=w.connect(OP);i=w.prepare_sign(op,s,'GATE_CONTROL',sign_body(w));w.hsm_sign_private(i);w.revoke(op,s,causal=H)
    check('prepared-ARM-actual-revoke-invalidates',w.publish_sign(op,i) is None)
    for profile in ('PLAIN','B'):
        w=World();w.nodes[sk(s)]['profile']=profile;c=w.connect(VER);a=w.register(c,binding(w,op='one'))
        b=w.register(c,binding(w,op='two',resource='resource-2',run='run-2'))
        check(profile+'-disjoint-executions-allowed',a is not None and b is not None)
        check(profile+'-same-resource-denied',w.register(c,binding(w,op='overlap',resource='resource-1',run='run-3')) is None)
        send(w,a);w.failure(a);check(profile+'-side-unknown-nodewide',not w.eligible('R03',s,fixture_footprint('resource-4','run-4')))
        check(profile+'-other-node-unaffected',w.eligible('R03',s2,fixture_footprint()))
    w=World();c=w.connect(VER);a=w.register(c,binding(w));b=w.register(c,binding(w,s=s2,op='two',kind='GPU_ACTIVE_OBSERVE'));send(w,a);send(w,b)
    w.failure(a,persist_error=False,persist_fuse=False)
    check('row-fuse-failure-retains-PENDING',state(w,a)=='PENDING_IO')
    check('row-fuse-failure-only-own-capability',w.confirm(c,b,w.outcome(b,'ACTIVE')))
    check('own-capability-death-refuses-reconstruction',not w.confirm(c,a,w.outcome(a,'TERMINAL_CLEAN')))
    w=World();c=w.connect(VER);a=w.register(c,binding(w));read=w.register(c,binding(w,op='read',kind='HEARTBEAT_OBSERVE'));safe=w.register(c,binding(w,op='safe',kind='QUARANTINE_RECONCILE',resource='r2',run='r2'))
    for h in (a,read,safe):send(w,h)
    w.restart_verifier();fresh=w.connect(VER)
    check('actual-restart-loses-every-LIVE-capability',all(w.private_caps[h.handle_hash]['state']=='LOST_INCARNATION' for h in (a,read,safe)))
    check('restart-read-ordinary-abandon',w.abandon_read(fresh,read))
    check('restart-side-no-ordinary-rebuild',not w.confirm(fresh,a,w.outcome(a,'TERMINAL_CLEAN')))
    check('restart-safety-fresh-recovery',w.reconcile_safety(w.connect(RECOVERY),safe,w.recovery_ack(safe)))
    check('restart-side-protected-physical',w.settle(w.connect(OP),a,phys(a)))
    w=World();c=w.connect(VER);p=parent(w,c);w.set_fact(w.connect(OP),s,'DRAIN')
    b=binding(w,op='term',kind='TERMINAL_FRAME',parent=p.handle_hash);h=w.register(c,b)
    check('exact-terminal-under-DRAIN',h is not None and send(w,h))
    bad=binding(w,op='wrong-parent',kind='TERMINAL_FRAME',parent='0'*64);check('wrong-terminal-parent-refused',w.register(c,bad) is None)
    w.nodes[sk(s)]['leaseActive']=False;check('expired-terminal-lease-refused',w.register(c,binding(w,op='expired',kind='TERMINAL_FRAME',parent=p.handle_hash)) is None)
    w=World();c=w.connect(VER);h=w.register(c,binding(w));check('atomic-proven-never-invoked-abort',w.abort_never_invoked(c,h) and state(w,h)=='NO_EFFECT' and not send(w,h))
    w=World();c=w.connect(VER);h=w.register(c,binding(w));send(w,h);w.failure(h)
    check('ambiguous-timeout-not-never-invoked-proof',not w.abort_never_invoked(c,h))
    # Exact current channel/leaf/epoch and multiple causal facts remain binding.
    w=World();c=w.connect(VER);h=w.register(c,binding(w,kind='QUARANTINE_RECONCILE'));send(w,h);w.failure(h);rv=w.connect(RECOVERY)
    w.set_fact(w.connect(OP),s,'DRAIN',cause='another');w.nodes[sk(s)]['C']+=1
    check('renewed-leaf-channel-refuses-stale-recovery',not w.reconcile_safety(rv,h,w.recovery_ack(h)))
    w.nodes[sk(s)]['C']-=1;check('exact-safety-closes-own-obligation',w.reconcile_safety(rv,h,w.recovery_ack(h)))
    check('safety-never-clears-another-drain',not w.eligible('R03',s))
    check('receipt-observe-side-effect-exception',EFFECT['RECEIPT_OBSERVE']=='SIDE_EFFECT')
    w=World();v=w.connect(VER);bad=binding(w,kind='HEARTBEAT_OBSERVE');bad['rawPath']='/v1/executions';w.original_requests[(sk(s),bad['operationId'])]=deepcopy(bad)
    check('kind-name-cannot-downgrade-side-effect-path',w.register(v,bad) is None)
    # The actual existing gate command/ACK contract, with timeout then a NEW
    # narrow reconciliation verifier; no CP-outbox-as-ACK shortcut.
    w=World();op=w.connect(OP);v=w.connect(VER);rv=w.connect(RECOVERY)
    oid=w.revoke(op,s,causal=H);cmd=w.sign(w.connect(REV),s,'GATE_CONTROL',sign_body(w,action='INVALIDATE_EXACT_GATE',outid=oid))
    check('signed-exact-invalidation-proposed-service',cmd is not None)
    b=binding(w,op='invalidate',kind='B_GATE_INVALIDATE')
    b.update(bodySHA=digest(cmd),nonce=cmd['body']['nonce'],targetBindingSHA=digest({'gateId':w.outbox[oid]['targetGateId'],'releaseHash':w.outbox[oid]['targetReleaseHash'],'staticHash':w.nodes[sk(s)]['staticHash']}))
    w.original_requests[(sk(s),b['operationId'])]=deepcopy(b);h=w.register(v,b);send(w,h)
    ack=w.node_gate(s,cmd);w.failure(h)
    check('timeout-does-not-invent-CP-gate-ACK',w.nodes[sk(s)]['cpGate']['state']=='ARMED')
    forged=deepcopy(ack);forged['body']['nonce']='0'*64
    check('fresh-gate-recovery-wrong-ACK-refused',not w.reconcile_gate_ack(rv,oid,h,forged))
    check('original-poisoned-gate-capability-stays-dead',not w.confirm(v,h,w.outcome(h,'OBSERVED')))
    check('fresh-exact-durable-gate-ACK-closes-without-OP',w.reconcile_gate_ack(rv,oid,h,ack))
    check('CP-gate-advances-only-verified-ACK',w.nodes[sk(s)]['cpGate']['state']=='INVALIDATED' and w.outbox[oid]['state']=='ACK_RECORDED')
    check('gate-safety-does-not-release-active-claim',w.nodes[sk(s)]['workloadActive'])
    check('retired-gate-history-retained',cmd['body']['gateId'] in w.nodes[sk(s)]['retiredGates'])
    # Private death survives a failed compound receipt transaction, while an
    # unrelated healthy scope remains live and can confirm its exact response.
    w=World();v=w.connect(VER);a=w.register(v,binding(w));send(w,a)
    z=w.register(v,binding(w,s=s2,op='z',kind='GPU_ACTIVE_OBSERVE'));send(w,z)
    check('compound-mismatch-refused',not w.confirm_many(v,[(a,w.outcome(a,'TERMINAL_CLEAN',valid=False))]))
    check('compound-rollback-does-not-revive-poison',w.private_caps[a.handle_hash]['state']=='POISONED' and not w.confirm(v,a,w.outcome(a,'TERMINAL_CLEAN')))
    check('compound-row-failure-other-Node-capability-live',w.confirm(v,z,w.outcome(z,'ACTIVE')))
    # Terminal proof releases the matched original claim only.
    w=World();v=w.connect(VER);b1=binding(w);a=w.register(v,b1);b2=binding(w,op='other',run='run-2',resource='resource-2');z=w.register(v,b2);send(w,a)
    check('original-terminal-receipt-removes-only-matched-claim',w.confirm(v,a,w.outcome(a,'TERMINAL_CLEAN')) and b1['claimBindingSHA'] not in w.nodes[sk(s)]['activeClaims'] and b2['claimBindingSHA'] in w.nodes[sk(s)]['activeClaims'] and w.nodes[sk(s)]['workloadActive'])
    w=World();v=w.connect(VER);op=w.connect(OP);i=w.prepare_sign(op,s,'GATE_CONTROL',sign_body(w));w.hsm_sign_private(i)
    binding(w,op='admitted-new-claim',run='r2',resource='resource-2')
    check('role-wide-ARM-invalidated-by-relevant-claim-version',w.publish_sign(op,i) is None)
    w=World();v=w.connect(VER);op=w.connect(OP);i=w.prepare_sign(op,s,'APPROVAL',sign_body(w,kind='APPROVAL'));w.hsm_sign_private(i)
    binding(w,op='disjoint-workload',run='r2',resource='resource-2')
    check('same-config-renewal-not-starved-by-unrelated-workload-claim',w.publish_sign(op,i) is not None)
    w=World();v=w.connect(VER);op=w.connect(OP);w.nodes[sk(s)]['liveness']='offline'
    hb=w.register(v,binding(w,kind='HEARTBEAT_OBSERVE'));send(w,hb);before=w.nodes[sk(s)]['authorityVersion']
    check('good-heartbeat-applies-original-offline-to-online-rule',w.apply_heartbeat(v,hb,w.outcome(hb,'OBSERVED')) and w.nodes[sk(s)]['liveness']=='online' and w.nodes[sk(s)]['authorityVersion']==before+1)
    w=World();v=w.connect(VER);w.authority['state']='FENCED_UNKNOWN';w.restart_verifier()
    check('real-global-trust-fence-not-erased-by-process-restart',w.authority['state']=='FENCED_UNKNOWN' and w.register(v,binding(w,kind='HEARTBEAT_OBSERVE')) is None)
    w=World();v=w.connect(VER);read_parent=w.seed_read_parent_fixture(s);w.nodes[sk(s)]['workloadActive']=False;w.nodes[sk(s)]['leaseActive']=False
    b=binding(w,kind='OBJECT_READ',parent=read_parent);h=w.register(v,b)
    check('object-read-parent-no-invented-kernel-Run',h is not None and b['runId'] is None and b['claimBindingSHA'] is None and send(w,h))
    w.failure(h);check('object-read-failure-abandoned-without-workload',state(w,h)=='NO_EFFECT_ABANDONED')
    w.read_parents[read_parent]['revoked']=True
    check('object-read-current-read-rights-rechecked',w.register(v,binding(w,op='read-after-revoke',kind='OBJECT_READ',parent=read_parent)) is None)
    w=World();v=w.connect(VER);p=parent(w,v);w.set_fact(w.connect(OP),s,'DRAIN');b=binding(w,op='frame',kind='TERMINAL_FRAME',parent=p.handle_hash);h=w.register(v,b)
    check('R12-exact-current-claimed-terminal-under-DRAIN',w.eligible('R12',s,handle=h))
    wrong=binding(w,op='wrong-owner',kind='TERMINAL_FRAME',parent=p.handle_hash);wrong['ownerBindingSHA']='0'*64;w.original_requests[(sk(s),wrong['operationId'])]=deepcopy(wrong)
    check('terminal-wrong-original-owner-refused',w.register(v,wrong) is None)
    (E/'fixture-results.json').write_text(json.dumps({'level':'SYMBOLIC_ONLY','cases':R,'count':len(R),'actualRuntimeB':0},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'symbolicDeltaCases':len(R),'failed':sum(not r['pass'] for r in R)}))

if __name__=='__main__':main()
