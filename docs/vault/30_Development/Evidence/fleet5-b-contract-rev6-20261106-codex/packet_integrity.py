"""Byte/source/scope verification only; not product/PG/Engine acceptance."""
import hashlib
import json
from pathlib import Path
import subprocess
from authority import build,invariants
from reconcile import audit
from rank_contract import CATALOG,check as rank_check
from source_analysis import load_sources,BASE,dump

E=Path(__file__).resolve().parent
ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())


def main():
    logs=[]
    for name,count in [('proof-checks.json',7),('publication-gates.json',8)]:
        doc=json.loads((E/name).read_bytes());assert len(doc['checks'])==count
        for row in doc['checks']:
            assert row['actualExit']==row['expectedExit'],row
            assert hashlib.sha256((ROOT/row['log']).read_bytes()).hexdigest()==row['sha256'],row
            logs.append(row)
    command=json.loads((E/'source-command-record.json').read_bytes())
    assert command['actualShellExit']==0 and all(r['actualExit']==0 for r in command['commands'])
    for artifact in command['resultArtifacts']:assert hashlib.sha256((E/artifact['path']).read_bytes()).hexdigest()==artifact['sha256'],artifact
    source=json.loads((E/'source-analysis.json').read_bytes());files=load_sources()
    assert {(r['path'],r['sha256']) for r in source['sourceFiles']}=={(p,hashlib.sha256(b).hexdigest()) for p,b in files.items()}
    for field,name in [('analysisToolSHA256','source_analysis.py'),('semanticsToolSHA256','source_semantics.py'),('rankToolSHA256','rank_contract.py'),('planSpecsSHA256','plan_specs.py')]:assert source[field]==hashlib.sha256((E/name).read_bytes()).hexdigest(),name
    matrix=json.loads((E/'authority-matrix.json').read_bytes());assert matrix==build() and not invariants(matrix) and not rank_check(matrix)
    mapping=json.loads((E/'writer-reconciliation.json').read_bytes())['writers'];assert len(mapping)==34 and not audit(source,matrix,mapping)
    critical=source['criticalEntries'];assert len(critical)==21 and all(not r['unknownIDs'] and r['supportStatus']=='SUPPORTED_STATIC_PLAN' for r in critical)
    records={(r['path'],r['line'],r['column']) for r in source['records']}
    assert not any((u['path'],u['line'],u['column']) in records for u in source['unknownEdges'])
    prior=json.loads((E/'prior-byte-integrity.json').read_bytes())
    for row in prior:
        blob=subprocess.check_output(['git','show',row['sourceSHA']+':'+row['source']],cwd=ROOT)
        assert (E/row['path']).read_bytes()==blob and hashlib.sha256(blob).hexdigest()==row['sha256']
    parent=E.parent/'fleet5-b-contract-rev5-20261106-codex'
    for name in ('fixture-results.json','source-fixture-results.json','packet-summary.json','revision-record.json'):assert (E/('prior-owner-'+name)).read_bytes()==(parent/name).read_bytes()
    assert not subprocess.check_output(['git','diff','--name-only',BASE,'--','deploy','services','src','migrations','tests','tools','contracts','packages','apps','.github'],cwd=ROOT)
    state=json.loads((E/'fixture-results.json').read_bytes());mutations=json.loads((E/'source-fixture-results.json').read_bytes())
    assert state['failed']==mutations['failed']==0 and all(c['passed'] for c in state['cases']+mutations['cases'])
    readers=json.loads((E/'reader-io-catalog.json').read_bytes());assert len(readers['plainReaders'])==13
    b_tables=[t for t in matrix['tables'] if t.startswith('inv.node_role_')]
    assert all(t in CATALOG for t in b_tables)
    result=dict(level='SCHEMA_STATIC_SYMBOLIC_BYTE_PROVENANCE_ONLY',source=BASE,sourceFiles=len(files),sourceRecords=len(source['records']),
        matrixWriters=34,knownWriterComposition='27 SQL +7 ORM, exact72028; independently accepted Rev5 census retained',
        statefulSchemaCases=state['passed'],sourceCases=mutations['passed'],newTotal=state['passed']+mutations['passed'],
        sourceMutationCount=mutations['sourceMutationCount'],criticalPlans=21,criticalUnjustifiedBlocks=0,
        remainingScopedCallgraphUnknowns=len(source['unknownEdges']),remainingScopedSQLIssues=len(source['sqlScopeIssues']),
        sourcePlans=len(source['functionPlans']),plainEligibilityReaders=13,ioKinds=len(readers['ioKinds']),explicitProposedBTables=len(b_tables),
        priorActualReviewByteExactFiles=len(prior),old335='preserved prior snapshots, not new/runtime evidence',
        rawProofPublicationLogs=logs,sourceCommandEvidence='source-command-record.json actual exit0 + content-hashed result artifacts, no raw stdout retention claim',
        actualNewGoCryptoPGEngineCrashConcurrencyEquipment=0,allRealBindings=None,A1_A16='PENDING',independentWholeReview='PENDING via Root',obsidianApply=False)
    dump(E/'packet-summary.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='rawProofPublicationLogs'}))


if __name__=='__main__':main()
