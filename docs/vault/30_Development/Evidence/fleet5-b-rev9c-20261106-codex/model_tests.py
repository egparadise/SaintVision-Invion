"""OWNER symbolic Rev9 guards; no real Node/crypto/clock/DB enforcement."""
import json
from copy import deepcopy
from pathlib import Path
from model import World,binding,scope,sk,VER,OP,seal
from io_contract import fixture_footprint
E=Path(__file__).resolve().parent;R=[]
def check(n,x):
    R.append({'case':n,'pass':bool(x)})
    if not x:raise AssertionError(n)
def send(w,h):
    if h is None:return False
    b=w.obligations[w.handles[h.handle_hash]['key']]['binding'];return w.invoke(h,b['bodySHA'],b['method'],b['rawPath'])
def row(w,h):return w.obligations[w.handles[h.handle_hash]['key']]
def setup(profile='B',kind='EXECUTE',other=True):
    w=World();s=scope();n=w.nodes[sk(s)];n['profile']=profile;c=w.connect(VER);p=w.register(c,binding(w,op='parent',kind=kind));assert p and send(w,p)
    if not other:n['activeClaims']={row(w,p)['binding']['claimBindingSHA']}
    return w,s,n,c,p
def frame(w,c,p,op='frame'):return w.register(c,binding(w,op=op,kind='TERMINAL_FRAME',parent=p.handle_hash))
def main():
    for profile in ('PLAIN','B'):
        for path in ('original','cancel'):
            for other in (False,True):
                w,s,n,c,p=setup(profile,other=other);claim=row(w,p)['binding']['claimBindingSHA'];version=n['claimVersions'][claim]
                prepared=frame(w,c,p);check(f'{profile}-{path}-{other}-live-prepared',prepared is not None)
                h=p
                if path=='cancel':h=w.register(c,binding(w,op='cancel',kind='CANCEL',parent=p.handle_hash));assert send(w,h)
                check(f'{profile}-{path}-{other}-kernel-release',w.confirm(c,h,w.outcome(h,'TERMINAL_CLEAN')))
                check(f'{profile}-{path}-{other}-exact-tombstone',claim not in n['activeClaims'] and n['claimVersions'][claim]==version+1 and n['claimRights'][claim]['workloadState']=='TERMINAL_TOMBSTONED')
                check(f'{profile}-{path}-{other}-identity-retained',claim in n['claimRights'])
                check(f'{profile}-{path}-{other}-new-frame-refused',frame(w,c,p,op='after') is None)
                check(f'{profile}-{path}-{other}-prepared-invoke-refused',not send(w,prepared))
                check(f'{profile}-{path}-{other}-prepared-confirm-refused',not w.confirm(c,prepared,w.outcome(prepared,'OBSERVED')))
                if path=='cancel':check(f'{profile}-{other}-parent-stays-PENDING',row(w,p)['state']=='PENDING_IO')
        for fact,expect in [('DRAIN',True),('QUARANTINE',False),('RETIRE',False)]:
            w,s,n,c,p=setup(profile);w.set_fact(w.connect(OP),s,fact);h=frame(w,c,p)
            check(profile+'-terminal-'+fact,(h is not None and send(w,h))==expect)
        for bad in ('missing-rights','released-matched','version','attempt','workload','missing-workload','unknown-leases','no-leases','one-expired-lease','one-released-lease','lease-epoch','deadline','lease-expiry','owner','project-member','parent-UNKNOWN','parent-deadcap'):
            w,s,n,c,p=setup(profile);b=row(w,p)['binding'];claim=b['claimBindingSHA'];rights=n['claimRights'][claim]
            if bad=='missing-rights':del n['claimRights'][claim]
            elif bad=='released-matched':n['activeClaims'].discard(claim)
            elif bad=='version':n['claimVersions'][claim]+=1
            elif bad=='attempt':rights['currentAttemptId']='superseded-attempt'
            elif bad=='workload':rights['workloadState']='STOPPED'
            elif bad=='missing-workload':del rights['workloadState']
            elif bad=='unknown-leases':rights['leasesKnown']=False
            elif bad=='no-leases':rights['leases']=[]
            elif bad=='one-expired-lease':rights['leases'].append({'released':False,'expiresAt':w.now,'epoch':s['epoch']})
            elif bad=='one-released-lease':rights['leases'][0]['released']=True
            elif bad=='lease-epoch':rights['leases'][0]['epoch']='foreign-epoch'
            elif bad=='deadline':rights['notAfter']=w.now+5
            elif bad=='lease-expiry':rights['leaseExpiresAt']=w.now
            elif bad=='owner':rights['ownerCurrent']=False
            elif bad=='project-member':rights['projectMemberCurrent']=False
            elif bad=='parent-UNKNOWN':w.failure(p)
            else:w.private_caps[p.handle_hash]['state']='LOST_INCARNATION'
            n['leaseActive']=True;n['workloadActive']=True
            check(profile+'-matched-guard-'+bad,frame(w,c,p) is None)
        w,s,n,c,p=setup(profile);h=frame(w,c,p);assert send(w,h);assert w.confirm(c,p,w.outcome(p,'TERMINAL_CLEAN'))
        check(profile+'-inflight-frame-confirm-after-release-refused',not w.confirm(c,h,w.outcome(h,'OBSERVED')))
        w,s,n,c,p=setup(profile);w.failure(p);w.set_fact(w.connect(OP),s,'QUARANTINE',cause='other')
        h=w.register(c,binding(w,op='cancel',kind='CANCEL',parent=p.handle_hash));assert send(w,h);assert w.confirm(c,h,w.outcome(h,'TERMINAL_CLEAN'))
        check(profile+'-release-never-clears-parentUNKNOWN-or-otherfact',row(w,p)['state']=='UNCERTAIN' and w.private_caps[p.handle_hash]['state']=='POISONED' and n['facts'][('QUARANTINE','other')])
        for parent_state in ('released','UNKNOWN','live-expired-deadline'):
            w,s,n,c,p=setup(profile,kind='BUILD_DISPATCH');w.seed_protected_cleanup_fixture(p)
            if parent_state=='released':assert w.confirm(c,p,w.outcome(p,'TERMINAL_CLEAN'))
            elif parent_state=='UNKNOWN':w.failure(p)
            w.now+=301
            before=(deepcopy(n),deepcopy(row(w,p)),deepcopy(w.private_caps[p.handle_hash]))
            h=w.register(c,binding(w,op='cleanup',kind='BUILD_CLEANUP_READ',parent=p.handle_hash))
            check(profile+'-cleanup-'+parent_state+'-read-after-stop',h is not None and send(w,h) and w.confirm(c,h,w.outcome(h,'OBSERVED')))
            check(profile+'-cleanup-'+parent_state+'-no-business-effects',before==(n,row(w,p),w.private_caps[p.handle_hash]))
        for field in ('buildSessionId','heldOwnedRootSHA','protectedDescriptorSHA','daemonIdentitySHA','fencingDescriptorSHA','leaseId','resourceId'):
            w,s,n,c,p=setup(profile,kind='BUILD_DISPATCH');w.seed_protected_cleanup_fixture(p)
            w.protected_cleanup_parents[p.handle_hash][field]='forged'
            h=w.register(c,binding(w,op='bad-read',kind='BUILD_CLEANUP_READ',parent=p.handle_hash))
            check(profile+'-cleanup-forged-'+field,h is None)
        w,s,n,c,p=setup(profile,kind='BUILD_DISPATCH')
        check(profile+'-cleanup-unknown-T3-binding-HOLD',w.register(c,binding(w,kind='BUILD_CLEANUP_READ',parent=p.handle_hash)) is None)
        w,s,n,c,p=setup(profile,kind='BUILD_DISPATCH');w.seed_protected_cleanup_fixture(p);h=w.register(c,binding(w,kind='BUILD_CLEANUP_READ',parent=p.handle_hash));assert send(w,h)
        claims=deepcopy(n['activeClaims']);version=deepcopy(n['claimVersions'])
        check(profile+'-cleanup-read-label-cannot-release',not w.confirm(c,h,w.outcome(h,'TERMINAL_CLEAN')) and n['activeClaims']==claims and n['claimVersions']==version)
        for reader in ('R01','R05'):
            for field,value in [('channelEnabled',False),('keyLive',False),('certNotAfter',2000000000),('epoch','other'),('generation','other'),('C',2),('DER','0'*64),('observeGrantLive',False),('observeGrantUntil',2000000000),('fenced',True)]:
                w,s,n,c,p=setup(profile);n['dbCandidates']={'A':fixture_footprint(),'B':fixture_footprint('resource-2','run-2')};v=n['authorityVersion'];facts=deepcopy(n['facts']);n[field]=value
                check(profile+reader+'-auth-'+field,w.candidate_hint(c,s,'B',reader)['status']=='AUTHORITY_DENIED' and n['authorityVersion']==v and n['facts']==facts)
            w,s,n,c,p=setup(profile);n['dbCandidates']={'A':fixture_footprint(),'B':fixture_footprint('resource-2','run-2')}
            check(profile+reader+'-disjoint-positive',w.candidate_hint(c,s,'B',reader)['status']=='HINT_AVAILABLE')
            check(profile+reader+'-forged-footprint-ignored',w.candidate_hint(c,s,'A',reader,fixture_footprint('forged','forged'))['status']=='HINT_OVERLAP')
    (E/'model-test-results.json').write_bytes((json.dumps({'ownerOnly':True,'scope':'SYMBOLIC_PROPOSAL_ONLY','cases':R,'actualRuntimeB':0,'realBindings':None},indent=2)+'\n').encode());print(json.dumps({'passed':len(R),'actualRuntimeB':0}))
if __name__=='__main__':main()
