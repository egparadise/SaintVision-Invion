"""Final byte/provenance/scope check, not product or runtime acceptance."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from authority import build,invariants
from reconcile import audit
from source_analysis import BASE,load_sources,dump

E=Path(__file__).resolve().parent
ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())


def main():
    ledgers=[]
    for name,count in [('proof-checks.json',6),('source-checks.json',3),('publication-gates.json',8)]:
        doc=json.loads((E/name).read_bytes());assert len(doc['checks'])==count,(name,len(doc['checks']))
        for row in doc['checks']:
            b=(ROOT/row['log']).read_bytes()
            assert row['actualExit']==row['expectedExit'],row
            assert hashlib.sha256(b).hexdigest()==row['sha256'],row
            ledgers.append({'ledger':name,'log':row['log'],'expectedExit':row['expectedExit'],'actualExit':row['actualExit'],'sha256':row['sha256']})
    census=json.loads((E/'source-analysis.json').read_bytes())
    assert census['analysisToolSHA256']==hashlib.sha256((E/'source_analysis.py').read_bytes()).hexdigest()
    assert census['planSpecsSHA256']==hashlib.sha256((E/'plan_specs.py').read_bytes()).hexdigest()
    sources=load_sources()
    assert {(r['path'],r['sha256']) for r in census['sourceFiles']}=={(p,hashlib.sha256(b).hexdigest()) for p,b in sources.items()}
    matrix=json.loads((E/'authority-matrix.json').read_bytes());assert matrix==build() and not invariants(matrix)
    reconciliation=json.loads((E/'writer-reconciliation.json').read_bytes())
    assert not audit(census,matrix,reconciliation['writers'])
    cases=json.loads((E/'fixture-results.json').read_bytes());source_cases=json.loads((E/'source-fixture-results.json').read_bytes())
    assert cases['failed']==0 and source_cases['failed']==0 and all(c['passed'] for c in cases['cases']+source_cases['cases'])
    assert any(c['case']=='constructor-injected-worker-service-edge' for c in source_cases['cases'])
    assert not subprocess.check_output(['git','diff','--name-only',BASE,'--','deploy','services','src','migrations','tests'],cwd=ROOT)
    prior=json.loads((E/'prior-byte-integrity.json').read_bytes())
    for row in prior:
        blob=subprocess.check_output(['git','show',row['sourceSHA']+':'+row['sourcePath']],cwd=ROOT)
        assert (E/row['file']).read_bytes()==blob and hashlib.sha256(blob).hexdigest()==row['sha256']
    ips=set()
    for p in E.iterdir():
        if p.suffix in ('.json','.py','.log'):
            ips.update(re.findall(rb'(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])',p.read_bytes()))
    assert all(ip.startswith((b'127.',b'198.51.100.',b'203.0.113.',b'192.0.2.')) for ip in ips),'non-fixture IPv4 candidate requires source/provenance review; not printed'
    result=dict(level='STATIC_BYTE_PROVENANCE_SCOPE_ONLY',source=BASE,
        modelCases=cases['passed'],sourceCases=source_cases['passed'],totalCases=cases['passed']+source_cases['passed'],
        sourceMutationCount=source_cases['sourceMutationCount'],files=len(sources),records=len(census['records']),
        sourceWriters=len(census['writers']),mappedMatrixWriters=len(reconciliation['writers']),
        functionPlans=len(census['functionPlans']),observedLockingFunctions=len({r['function'] for r in census['records'] if r['modes']}),
        realPreviouslyDroppedCPReceiverEdges=24,priorReviewByteExactFiles=len(prior),verifiedFinalRawLogs=ledgers,
        actualNewGoCryptoPGDockerCrashConcurrencyEquipment=0,allRealBindings=None,independentWholeReview='PENDING via Root',
        historicalDevelopmentFailureLedger='development-run-record.json explicitly separates retained failure from regenerated final logs')
    dump(E/'packet-summary.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='verifiedFinalRawLogs'}))


if __name__=='__main__':main()
