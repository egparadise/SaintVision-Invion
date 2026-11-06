"""Bounded OWNER symbolic regressions; NOT crypto/DB/Node enforcement evidence."""
from copy import deepcopy
import json
from pathlib import Path
from model import World,binding,scope,sk,seal,shape,VER,RUN,OP,Connection
from io_contract import fixture_footprint,RECOVERY
E=Path(__file__).resolve().parent
cases=[]
def check(name,value):
    cases.append({'case':name,'pass':bool(value)})
    if not value:raise AssertionError(name)
def send(w,h):
    if h is None:return False
    b=w.obligations[w.handles[h.handle_hash]['key']]['binding']
    return w.invoke(h,b['bodySHA'],b['method'],b['rawPath'])
def row(w,h):return w.obligations[w.handles[h.handle_hash]['key']]
def setup(profile='B'):
    w=World();s=scope();w.nodes[sk(s)]['profile']=profile;c=w.connect(VER)
    p=w.register(c,binding(w,op='parent'));assert p and send(w,p)
    return w,s,c,p
def mutate_original(w,b,field,value):
    b[field]=value;w.original_requests[(sk(b['scope']),b['operationId'])]=deepcopy(b)
def main():
    for profile in ('PLAIN','B'):
        for kind in ('CANCEL','RECEIPT_OBSERVE'):
            for lost in ('QUARANTINE','DRAIN','RETIRE_BUSINESS_ONLY','EXECUTION_LEASE','ACTIVATION_LEASE','OFFLINE','EXECUTION_GRANT'):
                w,s,c,p=setup(profile);n=w.nodes[sk(s)]
                if lost in ('QUARANTINE','DRAIN'):w.set_fact(w.connect(OP),s,lost)
                elif lost=='RETIRE_BUSINESS_ONLY':w.set_fact(w.connect(OP),s,'RETIRE')
                elif lost=='EXECUTION_LEASE':w.now+=301
                elif lost=='ACTIVATION_LEASE':n['activation']['leaseExpiresAt']=w.now
                elif lost=='OFFLINE':n['liveness']='offline'
                else:n['grantLive']=False
                claims=deepcopy(n['activeClaims']);h=w.register(c,binding(w,op='recovery',kind=kind,parent=p.handle_hash))
                check(profile+kind+lost+'-register',h is not None)
                check(profile+kind+lost+'-invoke',send(w,h))
                check(profile+kind+lost+'-retains-claims',n['activeClaims']==claims)
        for bad,value in [('parentHandleHash','0'*64),('parentCommandSHA','0'*64),('runId','wrong-run'),('claimBindingSHA','0'*64),('ownerBindingSHA','0'*64),('existingPermitOrApprovalSHA','0'*64),('channelVersion',2),('nodeDER','0'*64),('generation','other-generation')]:
            w,s,c,p=setup(profile);b=binding(w,kind='CANCEL',parent=p.handle_hash);mutate_original(w,b,bad,value)
            check(profile+'-wrong-'+bad,w.register(c,b) is None)
        for field,value in [('channelEnabled',False),('keyLive',False),('certNotAfter',2000000000),('observeGrantLive',False),('observeGrantUntil',2000000000),('epoch','epoch-other'),('fenced',True)]:
            for phase in ('register','invoke'):
                w,s,c,p=setup(profile);b=binding(w,kind='CANCEL',parent=p.handle_hash)
                h=w.register(c,b) if phase=='invoke' else None
                w.nodes[sk(s)][field]=value
                check(profile+phase+'-auth-'+field,(not send(w,h)) if phase=='invoke' else w.register(c,b) is None)
        w,s,c,p=setup(profile);b=binding(w,kind='CANCEL',parent=p.handle_hash)
        check(profile+'-unauthenticated-connection',w.register(Connection(VER,'verifier-1'),b) is None)
        check(profile+'-wrong-authenticated-scope',w.register(w.connect(VER,[scope(n='node-2')]),b) is None)
        w,s,c,p=setup(profile);w.control_epoch='other'
        check(profile+'-wrong-control-epoch',w.register(c,binding(w,kind='CANCEL',parent=p.handle_hash)) is None)
        w,s,c,p=setup(profile);w.failure(p);h=w.register(c,binding(w,op='cancel-unknown',kind='CANCEL',parent=p.handle_hash))
        check(profile+'-UNKNOWN-parent-cancel',h is not None and send(w,h))
        check(profile+'-UNKNOWN-parent-receipt-protected-only',w.register(c,binding(w,op='observe-unknown',kind='RECEIPT_OBSERVE',parent=p.handle_hash)) is None)
        claims=deepcopy(w.nodes[sk(s)]['activeClaims'])
        check(profile+'-cancel-ACK-own-only',w.confirm(c,h,w.outcome(h,'OBSERVED')) and w.nodes[sk(s)]['activeClaims']==claims and row(w,p)['state']=='UNCERTAIN')
        check(profile+'-UNKNOWN-ordinary-late-confirm-refused',not w.confirm(c,p,w.outcome(p,'TERMINAL_CLEAN')))
        w,s,c,p=setup(profile);w.failure(p);w.set_fact(w.connect(OP),s,'QUARANTINE',cause='other')
        h=w.register(c,binding(w,op='terminal-cancel',kind='CANCEL',parent=p.handle_hash));assert send(w,h)
        matched=row(w,p)['binding']['claimBindingSHA'];claims=deepcopy(w.nodes[sk(s)]['activeClaims'])
        check(profile+'-exact-original-receipt-frees-matched-only',w.confirm(c,h,w.outcome(h,'TERMINAL_CLEAN')) and w.nodes[sk(s)]['activeClaims']==claims-{matched})
        check(profile+'-physical-receipt-does-not-settle-UNKNOWN',row(w,p)['state']=='UNCERTAIN' and w.private_caps[p.handle_hash]['state']=='POISONED')
        check(profile+'-other-denials-retained',w.nodes[sk(s)]['facts'][('QUARANTINE','other')] and not w.eligible('R03',s,fixture_footprint('other','other')))
        for invalid in ('schemaValid','stopped','cleanupPending','projectClaimPlanExact','exactUnreleasedAllocationSet','uniqueAllocationIds','resourceNodeKindAmountFenceExact','receiptIdContentImmutable','sameTransactionRecordAndRelease','commandSHA','generation'):
            w,s,c,p=setup(profile);h=w.register(c,binding(w,kind='CANCEL',parent=p.handle_hash));assert send(w,h)
            o=w.outcome(h,'TERMINAL_CLEAN');kr=o['body']['kernelReceipt'];body=deepcopy(kr['body'])
            body[invalid]=not body[invalid] if type(body[invalid]) is bool else 'wrong'
            o['body']['kernelReceipt']=seal(kr['kind'],body,kr['signer']);o=seal(o['kind'],o['body'],o['signer'])
            claims=deepcopy(w.nodes[sk(s)]['activeClaims'])
            check(profile+'-kernel-negative-'+invalid,not w.confirm(c,h,o) and w.nodes[sk(s)]['activeClaims']==claims)
        w,s,c,p=setup(profile);h=w.register(c,binding(w,kind='CANCEL',parent=p.handle_hash));send(w,h)
        check(profile+'-ACK-label-not-original-receipt',not w.confirm(c,h,w.outcome(h,'TERMINAL_CLEAN',include_kernel=False)))
        for fact,expected in [('DRAIN',True),('QUARANTINE',False),('RETIRE',False)]:
            w,s,c,p=setup(profile);w.set_fact(w.connect(OP),s,fact)
            h=w.register(c,binding(w,kind='TERMINAL_FRAME',parent=p.handle_hash))
            check(profile+'-terminal-'+fact,(h is not None and send(w,h))==expected)
        w,s,c,p=setup(profile);w.now+=301
        check(profile+'-terminal-expired-refused',w.register(c,binding(w,kind='TERMINAL_FRAME',parent=p.handle_hash)) is None)
        w,s,c,p=setup(profile);h=w.register(c,binding(w,kind='RECEIPT_OBSERVE',parent=p.handle_hash));assert send(w,h);w.failure(p)
        check(profile+'-parent-dies-before-confirm-no-revival',not w.confirm(c,h,w.outcome(h,'TERMINAL_CLEAN')) and row(w,h)['state']=='UNCERTAIN')
        for reader in ('R01','R05'):
            w,s,c,p=setup(profile);n=w.nodes[sk(s)];n['dbCandidates']={'A':fixture_footprint(),'B':fixture_footprint('resource-2','run-2')};v=n['authorityVersion']
            check(profile+reader+'-overlap-A',w.candidate_hint(c,s,'A',reader)['status']=='HINT_OVERLAP')
            check(profile+reader+'-disjoint-B',w.candidate_hint(c,s,'B',reader)['status']=='HINT_AVAILABLE')
            result=w.candidate_hint(c,s,'missing',reader)
            check(profile+reader+'-missing-explicit',result['status']=='MISSING_RESOURCE_SCOPE' and not result['businessAuthority'] and n['authorityVersion']==v and shape('candidateHintResult',result))
            check(profile+reader+'-forged-caller-footprint-ignored',w.candidate_hint(c,s,'A',reader,fixture_footprint('forged','forged'))['status']=='HINT_OVERLAP')
            w.set_fact(w.connect(OP),s,'QUARANTINE')
            check(profile+reader+'-selected-admission-rechecks',w.register(c,binding(w,op='new',resource='resource-2',run='run-2')) is None)
            w,s,c,p=setup(profile);w.nodes[sk(s)]['dbCandidates']['B']=fixture_footprint('resource-2','run-2');w.failure(p)
            check(profile+reader+'-unknown-parent-nodewide',w.candidate_hint(c,s,'B',reader)['status']=='UNKNOWN_PARENT_HOLD')
    (E/'symbolic-results.json').write_bytes((json.dumps({'ownerOnly':True,'scope':'SYMBOLIC_PROPOSAL_ONLY','cases':cases,'actualRuntimeB':0},indent=2)+'\n').encode())
    print(json.dumps({'passed':len(cases),'actualRuntimeB':0}))
if __name__=='__main__':main()
