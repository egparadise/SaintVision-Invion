"""OWNER execution of unmodified actual reviewer probes, not new review."""
import hashlib,json,subprocess,sys
from pathlib import Path
E=Path(__file__).resolve().parent
def run(script,args,label):
    cmd=[sys.executable,'-B',str(script),*map(str,args)];r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    (E/(label+'.log')).write_bytes(r.stdout+r.stderr)
    assert r.returncode==0,r.stderr.decode(errors='replace')
    return json.loads(r.stdout),{'command':cmd,'actualExit':r.returncode,'scriptSHA256':hashlib.sha256(script.read_bytes()).hexdigest(),'stdoutSHA256':hashlib.sha256(r.stdout).hexdigest(),'log':label+'.log'}
def main():
    result=[]
    for name,expect in [('fleet5-b-contract-rev7-20261106-codex',True),('fleet5-b-rev8-revoke-portcut-20261106-codex',True),(E.name,False)]:
        d,receipt=run(E/'prior-reviewer_tf_released_claim_probe.py.txt',[E.parent/name],'actual-tf-probe-'+name)
        assert d['defect']==expect and d['parentConfirmedTerminalClean'] and d['matchedClaimReleased']
        result.append({'expectedDefect':expect,'observed':d,'receipt':receipt})
    d,receipt=run(E/'prior-reviewer_m1_l2_rev8_attacks.py.txt',[E],'actual-prior-recovery-hints-owner-rerun')
    assert len(d['cases'])==79 and not d['defects'],d['defects']
    legacy=E.parent/'fleet5-b-contract-rev7-20261106-codex/prior-reviewer_l3l4_attacks.py.txt'
    closed,cr=run(legacy,[E],'actual-prior-closed-owner-rerun');assert len(closed)==8 and not any(c['defect'] for c in closed)
    value={'executionOwner':'Codex OWNER reproduction of original Claude-authored scripts','notIndependentRev9Review':True,'tfOriginalScriptUnmodified':result,'retainedRecoveryHintCases':79,'retainedRecoveryReceipt':receipt,'retainedPriorClosedCases':8,'retainedPriorClosedReceipt':cr,'actualRuntimeB':0,'realBindings':None}
    (E/'retained-probe-results.json').write_bytes((json.dumps(value,indent=2)+'\n').encode());print(json.dumps({'tfOldDefects':[x['observed']['defect'] for x in result],'retainedRecoveryHintCases':79,'retainedPriorClosedCases':8}))
if __name__=='__main__':main()
