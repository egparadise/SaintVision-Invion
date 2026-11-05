"""Rev5 advancing-time/schema/semantic fixtures; symbolic hashes, no real keys."""
from copy import deepcopy
import json
from pathlib import Path
import model as m
from authority import build, invariants, OP, RUN, VER, ISS, DEL, SAFE, BUD, USER

E = Path(__file__).resolve().parent
RESULTS=[]
TRACES=[]


def check(name,value,expected=True):
    passed=value==expected
    RESULTS.append(dict(case=name,passed=passed,actual=value,expected=expected))
    assert passed,(name,value,expected)


def phase(s,label):
    return dict(phase=label,now=s['now'],nodeSequence=s['node']['sequence'],
                nodeGate=deepcopy(s['node']['gate']),switchPending=s['switchPending'],
                currentPointer=s['current']['pointerHash'] if s['current'] else None)


def renewal(s,suffix='new',expiry=None):
    a=m.append_approval(s,'APPROVAL_RENEW_SAME_CONFIG',expiry or s['now']+1200)
    assert a
    return m.material(s,a,suffix)


def invalidate(s):
    old={k:s['current'][k] for k in ('approval','release','delegation')}
    old['approvalChain']=deepcopy(m.chain(s,old['approval']) or [])
    s['switchPending']=True
    ack=m.node_command(s,old,m.command(s,old,'INVALIDATE_EXACT_GATE'))
    assert ack and m.record_ack(s,ack)
    return old,ack


def arm(s,mat):
    cmd=m.command(s,mat,'ARM_EXACT_RELEASE')
    ack=m.node_command(s,mat,cmd)
    return cmd,ack


def schema_cases(kind,samples):
    definition=m.SCHEMA['$defs'][kind]
    branches=definition.get('oneOf',[definition])
    for idx,sample in enumerate(samples):
        branch=branches[min(idx,len(branches)-1)]
        check(f'{kind}-branch{idx}-positive',m.shape(kind,sample))
        extra={**deepcopy(sample),'unexpected':True}
        check(f'{kind}-branch{idx}-extra',m.shape(kind,extra),False)
        for field in branch['required']:
            bad=deepcopy(sample);bad.pop(field)
            check(f'{kind}-branch{idx}-missing-{field}',m.shape(kind,bad),False)
            bad=deepcopy(sample);bad[field]={}
            check(f'{kind}-branch{idx}-type-{field}',m.shape(kind,bad),False)


def main():
    s=m.released_state();check('initial-complete-flow',m.cp_eligible(s,s['current'],m.role_use(s)))
    safety=m.released_state();original=deepcopy(safety['current'])
    check('safety-pre-IO-obligation-commits',m.pre_io_obligation(safety,'cleanup-operation'))
    check('quarantine-EXECUTE-loss-reported',m.raise_quarantine(safety,'cleanup-operation',can_execute=False),False)
    check('quarantine-EXECUTE-loss-still-denied',m.cp_eligible(safety,safety['current'],m.role_use(safety)),False)
    check('quarantine-failure-current-preserved',safety['current']==original)
    check('pre-IO-EXECUTE-loss-denies-IO',m.pre_io_obligation(safety,'next-operation',can_execute=False),False)
    # Lost ACK resolved by exact original ACK + fresh readback, never by re-ARM.
    s['now']+=5;mat=renewal(s);trace=[phase(s,'append')]
    s['now']+=2;old,inv=invalidate(s);trace.append(phase(s,'invalidate'))
    s['now']+=3;cmd,ack=arm(s,mat);assert ack;trace.append(phase(s,'ARM-ack-lost'))
    s['now']+=4;rb=m.gate_observe(s);before=deepcopy(s['node'])
    check('lost-ack-fresh-resolve',m.resolve_lost_ack(s,rb,cmd,ack))
    check('lost-ack-resolve-no-node-mutation',s['node']==before)
    s['now']+=2;check('resolved-ack-CAS',m.commit_activation(s,mat,ack));trace.append(phase(s,'CAS'))
    s['now']+=2;ch=m.delivery_challenge(s);assert ch
    s['now']+=1;receipt=m.consume_possession(s,ch,m.possession(ch));assert receipt
    s['now']+=1;check('delivery-after-time-advance',m.record_delivery(s,receipt));trace.append(phase(s,'delivery'))
    check('new-current-eligible',m.cp_eligible(s,s['current'],m.role_use(s)))
    TRACES.append(trace)
    schema_cases('gateObservation',[rb['body'],m.gate_observe(s,authenticated=False)['body']])
    # Terminal gate/release history defeats A4 with consistent fresh commands.
    newer=deepcopy(s['current']);s['now']+=1;invalidate(s)
    fresh_old=m.command(s,old,'ARM_EXACT_RELEASE');before=deepcopy(s['node'])
    check('A4-fresh-signed-old-g0-rearm',m.node_command(s,old,fresh_old) is None)
    check('A4-no-history-mutation',s['node']==before)
    # Restart retains durable records/tombstones but changes current generation.
    r=m.released_state();om={k:r['current'][k] for k in ('approval','release','delegation')};om['approvalChain']=deepcopy(m.chain(r,om['approval']))
    r['node']['generation']='generation-1';r['node']['gate']=None
    wrong=m.command(r,om,'ARM_EXACT_RELEASE')
    check('A5-release-generation-must-current',m.node_command(r,om,wrong) is None)
    # Exact duplicates replay the original ack only while transition still current.
    d=m.make_state();a=m.append_approval(d,'FRESH_ACTIVATE',d['now']+600);mm=m.material(d,a,'dup')
    dc,da=arm(d,mm);assert da;dn=deepcopy(d['node']);d['now']+=3
    check('duplicate-original-ACK',m.node_command(d,mm,dc)==da)
    check('duplicate-no-mutation',d['node']==dn)
    ia=m.node_command(d,mm,m.command(d,mm,'INVALIDATE_EXACT_GATE'));assert ia
    check('duplicate-cannot-resurrect-invalidated',m.node_command(d,mm,dc) is None)
    for field,value in [('expectedPriorSequence',999),('expectedPriorRecordHash','f'*64)]:
        q=m.make_state();qa=m.append_approval(q,'FRESH_ACTIVATE',q['now']+600);qm=m.material(q,qa,'cas')
        body=deepcopy(m.command(q,qm,'ARM_EXACT_RELEASE')['body']);body[field]=value
        check('gate-prior-CAS-'+field,m.node_command(q,qm,m.seal('GATE_CONTROL',body)) is None)
    # Ancestor explicit revocation at multiple commit gates.
    for gate in ('append','ARM','activation','delivery','refresh','issuance-current-use'):
        q=m.released_state();ancestor=m.digest(q['current']['approval']);q['now']+=2;qm=renewal(q)
        if gate in ('activation','delivery'):
            invalidate(q);qc,qa=arm(q,qm);assert qa and m.record_ack(q,qa)
            if gate=='delivery':assert m.commit_activation(q,qm,qa)
        if gate in ('refresh','issuance-current-use'):m.finish(q,qm)
        q['now']+=3;check('revoke-'+gate,m.revoke_lineage(q,ancestor))
        if gate=='append':result=m.append_approval(q,'APPROVAL_RENEW_SAME_CONFIG',q['now']+1300) is None
        elif gate=='ARM':result=m.command(q,qm,'ARM_EXACT_RELEASE') is None
        elif gate=='activation':result=not m.commit_activation(q,qm,qa)
        elif gate=='delivery':result=m.delivery_challenge(q) is None
        elif gate=='refresh':result=not m.refresh_same_generation(q,m.candidate(q))
        else:result=not m.cp_eligible(q,q['current'],m.role_use(q))
        check('ancestor-revocation-denies-'+gate,result)
    # CP immediate revoke does not magically deliver a Node invalidation.
    q=m.released_state();u=m.role_use(q);m.revoke_lineage(q,m.digest(q['current']['approval']))
    check('CP-revoke-immediate',m.cp_eligible(q,q['current'],u),False)
    check('Node-no-instant-remote-revocation-claim',m.node_accepts(q,q['current'],u))
    invalidate(q);check('Node-acknowledged-invalidation-denies',m.node_accepts(q,q['current'],u),False)
    # Ancestor expiry alone permits legitimate already-completed new approval.
    q=m.released_state();oldend=q['current']['approval']['body']['expiresAt'];qm=renewal(q);m.finish(q,qm)
    q['now']=oldend+1
    check('ancestor-time-expiry-not-revocation',m.approval_valid(q,q['current']['approval']))
    check('refresh-after-ancestor-time-expiry',m.refresh_same_generation(q,m.candidate(q)))
    check('business-after-ancestor-time-expiry',m.cp_eligible(q,q['current'],m.role_use(q)))
    parent=q['current']['approval']['body']['priorApprovalHash'];q['approvals'].pop(parent)
    check('missing-authenticated-ancestor-UNKNOWN-deny',m.approval_valid(q,q['current']['approval']),False)
    # Time advances through a switch and the new approval expires mid-switch.
    q=m.released_state();qm=renewal(q,expiry=q['now']+15);tr=[phase(q,'append')]
    q['now']+=5;invalidate(q);tr.append(phase(q,'invalidate'))
    q['now']+=11;check('mid-switch-expiry-before-ARM',arm(q,qm)[1] is None);tr.append(phase(q,'expiry-HOLD'))
    check('mid-switch-preserves-CP-pointer',q['current']['release']['body']['gateId']=='gate-old')
    check('mid-switch-remains-fenced',q['switchPending']);TRACES.append(tr)
    # Lost/stale ACK >60s is HOLD, never reissued with a fresh time.
    q=m.released_state();qm=renewal(q);invalidate(q);qc,qa=arm(q,qm);assert qa
    q['now']+=61;readback=m.gate_observe(q)
    check('stale-ACK-closed-refusal',readback['body']['status']=='STALE_ACK')
    check('stale-ACK-no-resolution',m.resolve_lost_ack(q,readback,qc,qa),False)
    check('stale-duplicate-original-time',m.node_command(q,qm,qc)==qa)
    check('stale-ACK-not-recordable',m.record_ack(q,qa),False)
    check('stale-ACK-no-CAS',m.commit_activation(q,qm,qa),False)
    check('stale-ACK-no-ordinary-renewal-reset',m.append_approval(q,'APPROVAL_RENEW_SAME_CONFIG',q['now']+1300) is None)
    q['node']['records'][q['node']['recordId']].pop('ack')
    check('missing-ACK-HOLD',m.gate_observe(q)['body']['status']=='UNKNOWN_RECORD')
    for status in ('CONFLICT','EXPIRED'):
        z=m.released_state()
        if status=='CONFLICT':z['node']['sequence']+=1
        else:z['now']=m.trust_end(z)
        refused_readback=m.gate_observe(z)['body']
        check('readback-closed-'+status,refused_readback['status']==status and m.shape('gateObservation',refused_readback))
    stale_rb=deepcopy(rb);s['now']=rb['body']['expiresAt']+1
    check('expired-available-readback-denied',m.resolve_lost_ack(s,stale_rb,cmd,ack),False)
    for branch in ('cohortFence','containment','quarantined'):
        q=m.released_state();qm=renewal(q);q['now']+=3;q[branch]=True
        check('after-append-'+branch+'-ARM-denied',m.command(q,qm,'ARM_EXACT_RELEASE') is None)
    q=m.released_state();q['now']+=2;qm=renewal(q);invalidate(q);qc,qa=arm(q,qm)
    assert qa and m.record_ack(q,qa);q['now']+=3;assert m.commit_activation(q,qm,qa)
    q['now']+=61;check('ACK-expiry-after-CAS-denies-delivery',m.delivery_challenge(q) is None)
    q=m.released_state();q['now']+=2;qm=renewal(q);invalidate(q);qc,qa=arm(q,qm)
    assert qa and m.record_ack(q,qa);q['now']+=3;assert m.commit_activation(q,qm,qa)
    ch=m.delivery_challenge(q);assert ch;q['now']+=2;q['cohortFence']=True
    check('fence-after-delivery-prepare-denies-possession-commit',m.consume_possession(q,ch,m.possession(ch)) is None)
    # Signing-service access, beyond DB EXECUTE. No raw controller anchor key.
    q=m.released_state();q['now']+=2;qm=renewal(q);invalidate(q);qc,qa=arm(q,qm)
    assert qa and m.record_ack(q,qa) and m.commit_activation(q,qm,qa)
    cur=q['current']
    samples={'APPROVAL':cur['approval']['body'],'RELEASE':cur['release']['body'],
             'DELEGATION':cur['delegation']['body'],'GATE_CONTROL':m.command(q,cur,'INVALIDATE_EXACT_GATE')['body']}
    for caller in (DEL,RUN,VER,ISS,SAFE,BUD):
        for kind,body in samples.items():
            check('signer-purpose-deny-'+caller+'-'+kind,m.service_sign(q,caller,kind,body) is None)
    ch=m.delivery_challenge(q);assert ch
    check('controller-exact-prepare',m.service_sign(q,DEL,'DELIVERY_CHALLENGE',ch['body']) is not None)
    for field in ('nodeId','issuerServiceId','issuerTLSHash','useKeyHash','gateAckHash','activationLedgerHash','generation','gateId'):
        bad=deepcopy(ch['body']);bad[field]='f'*64 if field.endswith('Hash') else 'wrong'
        check('controller-scope-deny-'+field,m.service_sign(q,DEL,'DELIVERY_CHALLENGE',bad) is None)
    # Semantic ACL/status/owner invariants, not build()==golden.
    matrix=build();check('matrix-semantic-positive',not invariants(matrix))
    mutants=[]
    def mutate(label,fn):
        bad=deepcopy(matrix);fn(bad);mutants.append((label,bad))
    mutate('ordinary-protected',lambda x:x['procedures']['b_append_approval']['execute'].append(RUN))
    mutate('remove-protected-tag',lambda x:x['procedures']['b_append_approval'].update(protected=False))
    mutate('clear-containment-runtime',lambda x:x['procedures']['b_clear_node_containment'].update(execute=[RUN]))
    mutate('runtime-quarantine-not-deny',lambda x:x['procedures']['b_raise_node_quarantine'].update(denyOnly=False))
    mutate('owner-impersonation',lambda x:x['procedures']['b_revoke_owner_contribution'].update(execute=[OP]))
    mutate('liveness-clears-quarantine',lambda x:x['procedures']['b_commit_node_observation']['statusTransitions'].append(['quarantined','online']))
    mutate('evidence-update',lambda x:x['procedures']['b_append_run_completion_evidence']['effects']['inv.evidence'].update(verb='UPDATE'))
    mutate('runtime-SET-ROLE',lambda x:x['allOnlineDirectAuthorityDML'].update(SET_ROLE_to_owner_operator_or_legacy_inv_kernel=True))
    mutate('table-no-writer',lambda x:x['tables'].update({'public.unknown_authority':[]}))
    mutate('remove-table-mapping',lambda x:x['tables']['public.nodes'].pop())
    mutate('read-lock-is-write',lambda x:next(iter(x['lockOnlyProcedures'].values())).update(columnsWritten=['status']))
    mutate('controller-raw-key',lambda x:x['signingService'].update(rawOperatorPrivateKeyToController=True))
    mutate('remove-ordinary-classification',lambda x:x.update(ordinaryOnline=[]))
    def rogue(x):
        x['procedures']['b_rogue_approval']=deepcopy(x['procedures']['b_append_approval'])
        x['procedures']['b_rogue_approval'].update(protected=False,execute=[RUN])
    mutate('renamed-approval-factory',rogue)
    for label,bad in mutants:check('semantic-'+label,bool(invariants(bad)))
    # Each oneOf branch: missing/extra/type; refusals cannot carry eligible data.
    available={'kind':'OBSERVATION_SCOPE','status':'AVAILABLE','businessAuthority':False,
        'source':'CURRENT_REGISTERED','tenantId':q['static']['tenantId'],'nodeId':q['static']['nodeId'],
        'currentControlEpoch':q['static']['epoch'],'targetNodeEpoch':q['static']['epoch'],
        'targetDER':q['static']['DER'],'currentTuple':q['static'],'provenanceHash':m.H,
        'intentId':None,'method':'POST','paths':['/v1/roles/observe'],'challenge':m.H,
        'issuedAt':q['now'],'expiresAt':q['now']+30,'diagnostic':'OBSERVE_ONLY'}
    refused={'kind':'OBSERVATION_SCOPE','status':'SCOPE_DENIED','businessAuthority':False,
             'reason':'NO_OBSERVER_GRANT','nodeId':q['static']['nodeId'],'observedAt':q['now']}
    schema_cases('observationScope',[available,refused])
    for field in available:
        if field not in refused:
            check('observation-refusal-no-payload-'+field,m.shape('observationScope',{**refused,field:available[field]}),False)
    result={'level':'SCHEMA_STATIC_STATEFUL_SYMBOLIC_ONLY','passed':len(RESULTS),'failed':0,
            'cases':RESULTS,'advancingTimeTraces':TRACES,'actualGoCryptoPGDockerCrashConcurrencyEquipment':0}
    (E/'fixture-results.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print(json.dumps({'passed':len(RESULTS),'failed':0,'advancingTimeTraces':len(TRACES),'actualB':0}))


if __name__=='__main__':main()
