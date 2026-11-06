"""OWNER rerun of retained symbolic cases against Rev8; no independent review."""
import importlib.util,json,subprocess,sys
from pathlib import Path
E=Path(__file__).resolve().parent;R7=E.parent/'fleet5-b-contract-rev7-20261106-codex'
def main():
    spec=importlib.util.spec_from_file_location('immutable_rev7_fixtures',R7/'fixtures.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.E=E;m.main()
    p=R7/'prior-reviewer_l3l4_attacks.py.txt'
    r=subprocess.run([sys.executable,'-B',str(p),str(E)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    assert r.returncode==0,r.stderr.decode()
    cases=json.loads(r.stdout);assert len(cases)==8 and not any(c['defect'] for c in cases)
    (E/'retained-owner-rerun.json').write_bytes((json.dumps({'ownerOnly':True,'scope':'Original Rev7 symbolic cases and eight prior closed reviewer probes rerun by OWNER, not independent review','priorClosedCases':cases,'actualIndependentRev8Review':'PENDING through Root','actualRuntimeB':0},indent=2)+'\n').encode())
    print(json.dumps({'retainedPriorClosedCases':len(cases),'actualIndependentRev8Review':'PENDING'}))
if __name__=='__main__':main()
