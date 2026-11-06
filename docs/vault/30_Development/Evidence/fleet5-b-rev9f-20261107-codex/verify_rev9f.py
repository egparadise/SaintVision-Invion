"""Final source artifacts, causal cases, ordering and immutable accounting checks."""
import hashlib,json
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(n):return json.loads((E/n).read_bytes())
def main():
    r=load('input-receipts.json')
    for row in r['immutableRetained']:assert sha(ROOT/row['path'])==row['sha256']
    for row in r['actualPriorReview']:assert sha(E/row['copy'])==row['sha256']
    for name,h in r['modelLifecycleFrozen'].items():assert sha(E/name)==h
    for row in r['accountingBaseline']:assert sha(E/row['file'])==row['sha256']
    units=load('rev9f-unit-results.json');assert len(units['cases'])==55 and all(x['pass'] for x in units['cases'])
    gaps=load('rev9f-gap-results.json');assert len(gaps['cases'])==12 and sum(x['actual764cGap'] for x in gaps['cases'])==5
    for row in gaps['cases']:
        assert row['observed']==row['expected'] and row['witnessesChecked']==15 and row['sixFrozenRootsPreserved']
        if row['actual764cGap']:assert row['oldIndependentObserved']=='ACCEPT' and row['observed']=='REFUSE'
    c=load('t1-mark-offline-closure.json');assert len(c['edges'])==19 and c['analysisEdgesClosed']==16 and c['namedRuntimeEdgesPending']==3 and len(c['sharedOwnerReferencedCriticalEntries'])==12
    assert c['actualRuntimeB']==0 and c['realBindings'] is None and c['A1_A16']=='PENDING'
    o=c['narrowA8Proof'];params=o['boundedParameterProvenance'];assert len(params['bindings'])==576 and not params['unresolved']
    g=o['completeConstructorGraph'];census=g['census'];discovery=g['derivedForwardingCallerInventory'];audits=census['reflectionAudits']+discovery['reflectionAudits']
    parsed={x['path'] for x in census['sourceFiles']+discovery['sourceFiles']};assert parsed=={x['path'] for x in audits} and len(parsed)==25 and len([p for p in parsed if not p.startswith('tests/')])==11
    assert len(census['production'])==6 and len(census['harness'])==20 and not any(x['newRelevantHits'] for x in audits if x['scope']=='PRODUCTION_SOURCE')
    order=load('producer-order.json');assert order['requiredOrder']==['pending_contracts.py','edge_categories.py']
    for key,script in [('stage1','pending_contracts.py'),('final','edge_categories.py')]:
        row=order[key];assert sha(E/row['artifact'])==row['sha256'] and sha(E/script)==row['producerSHA256']
    final=load('pending-interface-contracts.json');assert final['artifactStage']=='PRODUCER2_FINAL_ORDERED_CONTRACT_PROOF' and final['targetedCategorySHA256']==sha(E/'targeted-category-delta.json')
    prior=load('prior-input-receipts.json');old=E.parent/'fleet5-b-rev9e-20261107-codex';m=json.loads((old/'proof-producer-hashes.json').read_bytes())
    assert len(m['producersAndRetainedScripts'])==71 and sum(x['bytes'] for x in m['producersAndRetainedScripts'])==528040
    d={'verified':True,'source':r['productSource'],'base':r['base'],'unitCases':55,'actualIndependentRedOwnerGreenContrasts':5,'fullProvenanceControls':7,'closureSHA256':sha(E/'t1-mark-offline-closure.json'),'parsedAuditedPaths':sorted(parsed),'bindings':576,'stage1SHA256':order['stage1']['sha256'],'finalSHA256':order['final']['sha256'],'modelLifecycleFrozen':r['modelLifecycleFrozen'],'accountingArtifactsByteIdentical':6,'retainedPredecessor':{'manifestSHA256':sha(old/'proof-producer-hashes.json'),'scripts':71,'scriptBytes':528040,'newCoverage':False},'retainedBroadSuites':'70/19/31/83/29/model/terminal/recovery retained by immutable input hashes; NOT_RERUN','independentRev9fReview':'PENDING through Root','actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING','A7':'UNSTARTED / NOT_GRANTED'}
    (E/'rev9f-current-verification.json').write_bytes((json.dumps(d,indent=2)+'\n').encode());print(json.dumps({'verified':True,'units':55,'causal5':5,'controls':7,'paths':25,'bindings':576,'accountingUnchanged':6}))
if __name__=='__main__':main()
