"""AUTHOR rerun of eight actual prior reviewer probes, not independent review."""
import hashlib,json,subprocess,sys
from pathlib import Path
E=Path(__file__).resolve().parent
def main():
    p=E/'prior-reviewer_l3l4_attacks.py.txt';r=subprocess.run([sys.executable,'-B',str(p),str(E)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    assert r.returncode==0,r.stderr.decode()
    cases=json.loads(r.stdout);assert len(cases)==8 and not any(c['defect'] for c in cases),cases
    (E/'prior-closed-owner-rerun.json').write_text(json.dumps({'scope':'AUTHOR_REPRODUCTION_OF_PRIOR_CLOSED_DESIGN_PROBES_ONLY','priorProbeSHA256':hashlib.sha256(p.read_bytes()).hexdigest(),'cases':cases,'actualIndependentRev7Review':'PENDING via Root','actualRuntimeB':0},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'ownerRerunPriorClosedCases':len(cases),'defects':0}))
if __name__=='__main__':main()
