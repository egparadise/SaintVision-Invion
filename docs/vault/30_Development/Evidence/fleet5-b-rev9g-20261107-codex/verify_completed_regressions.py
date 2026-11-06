"""Verify already-completed targeted runs against a transparent post-run source seal."""
import hashlib,json
from pathlib import Path
E=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    seal=json.loads((E/'completed-regression-source-seal.json').read_bytes())
    for r in seal['sourceFiles']:assert sha(E/r['file'])==r['sha256'],r['file']
    for r in seal['artifacts']:assert sha(E/r['file'])==r['sha256'],r['file']
    d=json.loads((E/'rev9d-regression-results.json').read_bytes());assert len(d['actualGapContrasts'])==8 and d['original47Cases']==47 and not d['unexpectedSemanticResults']
    for r in d['commands']:assert r['actualExit']==0 and sha(E/r['log'])==r['logSHA256']
    raw=json.loads((E/'owner-original47-results.json').read_bytes());assert len(raw['cases'])==47
    high=next(r for r in raw['cases'] if r['case']=='L2-keyword-forwarder-higher-hop-inventory');assert high['higherHopInventoried']
    out={'verified':True,'reuse':'Completed exact old/new12 and original47 execution receipts, not a second execution','sealTiming':seal['timing'],'sourceFilesVerified':len(seal['sourceFiles']),'actualRuntimeB':0}
    (E/'completed-regression-verification.json').write_bytes((json.dumps(out,indent=2)+'\n').encode());print(json.dumps(out))
if __name__=='__main__':main()
