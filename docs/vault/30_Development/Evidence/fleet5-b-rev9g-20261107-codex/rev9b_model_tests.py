"""Only new terminal status/tenant parity and wrapper controls; symbolic only."""
import json,subprocess,sys
from copy import deepcopy
from pathlib import Path
from model import World,binding,scope,sk,VER,OP
from model_tests import setup,send,row
E=Path(__file__).resolve().parent;R=[]
def check(name,value):
    R.append({'case':name,'pass':bool(value)})
    if not value:raise AssertionError(name)
def frame(w,c,p,name='frame'):return w.register(c,binding(w,op=name,kind='TERMINAL_FRAME',parent=p.handle_hash))
def main():
    for profile in ('PLAIN','B'):
        for phase in ('register','invoke','confirm'):
            w,s,n,c,p=setup(profile);h=frame(w,c,p) if phase!='register' else None
            if phase=='confirm':assert send(w,h)
            claims=deepcopy(n['activeClaims']);n['liveness']='offline'
            refused=frame(w,c,p) is None if phase=='register' else not send(w,h) if phase=='invoke' else not w.confirm(c,h,w.outcome(h,'OBSERVED'))
            check(profile+'-offline-'+phase,refused and n['activeClaims']==claims)
            if phase=='confirm':check(profile+'-late-offline-frame-protected-hold',row(w,h)['state']=='UNCERTAIN' and w.private_caps[h.handle_hash]['state']=='POISONED' and not w.eligible('R03',s))
        for status in ('online','draining'):
            w,s,n,c,p=setup(profile);n['liveness']=status;h=frame(w,c,p)
            check(profile+'-projection-'+status,h is not None and send(w,h) and w.eligible('R12',s,handle=h))
        w,s,n,c,p=setup(profile);w.set_fact(w.connect(OP),s,'DRAIN');h=frame(w,c,p)
        check(profile+'-DRAIN-fact-positive',h is not None and send(w,h))
        for gate in ({'known':True,'killSwitch':True},{'known':False,'killSwitch':False},None):
            w,s,n,c,p=setup(profile)
            if gate is None:del w.tenant_execution[(s['tenantId'],s['epoch'])]
            else:w.tenant_execution[(s['tenantId'],s['epoch'])]=gate
            check(profile+'-tenant-stop-or-unknown-'+str(gate),frame(w,c,p) is None)
            second=scope(n='node-2');w.nodes[sk(second)]['profile']=profile
            check(profile+'-tenant-stop-other-node-'+str(gate),not w.eligible('R03',second))
            for kind in ('CANCEL','RECEIPT_OBSERVE'):
                h=w.register(c,binding(w,op=kind+'-recovery',kind=kind,parent=p.handle_hash))
                check(profile+'-tenant-stop-recovery-'+kind+str(gate),h is not None and send(w,h))
        w,s,n,c,p=setup(profile);h=frame(w,c,p);assert send(w,h);w.tenant_execution[(s['tenantId'],s['epoch'])]['killSwitch']=True
        check(profile+'-tenant-stop-before-confirm',not w.confirm(c,h,w.outcome(h,'OBSERVED')))
        w,s,n,c,p=setup(profile);s2=scope(n='node-2');w.nodes[sk(s2)]['profile']=profile
        p2=w.register(c,binding(w,s=s2,op='parent-two',resource='resource-2',run='run-2'));assert send(w,p2)
        f1=frame(w,c,p);f2=w.register(c,binding(w,s=s2,op='frame-two',kind='TERMINAL_FRAME',parent=p2.handle_hash,resource='resource-2',run='run-2'));assert f1 and f2
        w.tenant_execution[(s['tenantId'],s['epoch'])]['killSwitch']=True
        check(profile+'-tenant-stop-prepared-both-nodes',not send(w,f1) and not send(w,f2))
        check(profile+'-tenant-stop-new-both-nodes',frame(w,c,p,'new-one') is None and w.register(c,binding(w,s=s2,op='new-two',kind='TERMINAL_FRAME',parent=p2.handle_hash,resource='resource-2',run='run-2')) is None)
    for path in ('not-a-real-model-directory',str(E.parent/'__missing_rev9b_model__'),str(E.parent)):
        p=subprocess.run([sys.executable,'-B',str(E/'terminal_claim_regression.py'),path],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        check('wrapper-refuses-'+path,p.returncode==2 and b'INVALID_MODEL_DIRECTORY' in p.stderr)
    (E/'rev9b-model-test-results.json').write_bytes((json.dumps({'executionOwner':'Codex','cases':R,'scope':'SYMBOLIC_ONLY','actualRuntimeB':0,'trackedInfo':{'versionAttemptCAS':'TRACKED_INFO_ONLY_NOT_CHANGED_NO_NEW_RECEIPT_FIELDS','inflightFrame':'UNCERTAIN/POISONED same-Node HOLD needs existing protected settlement, never generic receipt/ACK clear'}},indent=2)+'\n').encode());print(json.dumps({'passed':len(R)}))
if __name__=='__main__':main()
