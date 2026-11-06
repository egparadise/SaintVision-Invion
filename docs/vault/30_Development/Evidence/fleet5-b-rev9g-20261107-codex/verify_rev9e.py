"""Exact six causal contrasts and current closure/immutable binding receipts."""
import argparse,hashlib,json
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(n):return json.loads((E/n).read_bytes())
def main():
    p=argparse.ArgumentParser();p.add_argument('--contrasts',action='store_true');a=p.parse_args()
    if a.contrasts:
        old=load('rev9e-old-six-results.json');new=load('rev9e-new-results.json');contrasts=[]
        assert len(old['cases'])==6 and len(new['cases'])==13
        for o,n in zip(old['cases'],new['cases'][:6]):
            assert o['case']==n['case'] and o['mutatedSHA256']==n['mutatedSHA256']
            assert o['observed']=='ACCEPT' and n['observed']=='REFUSE',(o,n)
            assert o['witnessesChecked']==n['witnessesChecked']==15 and n['sixFrozenRootsPreserved']
            contrasts.append({'case':n['case'],'old':'ACCEPT','new':'REFUSE','reason':n['reason']})
        for n in new['cases']:assert n['observed']==n['expectedNew'],n
        hidden=next(n for n in new['cases'] if 'hidden-seventh' in n['case']);assert hidden['visibleRoots']==6 and hidden['fixtureSemanticRootCount']==7
        result={'actual9266GapsNowRefused':contrasts,'controls':new['cases'][6:],'reasonPrefixPolicy':'Declared conservative refusal is refusal; reviewer guessed prefix-only mismatches remain REFUSALS, never semantic gaps','actualRuntimeB':0}
        (E/'rev9e-contrast-verification.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps({'oldAcceptedNewRefused':6,'controls':7}));return
    receipts=load('input-receipts.json');old=E.parent/'fleet5-b-rev9d-20261107-codex'
    for r in receipts['immutableRetained']:assert sha(ROOT/r['path'])==r['sha256'],r
    for n,h in receipts['modelLifecycleFrozen'].items():assert sha(E/n)==h
    for r in receipts['accountingBaseline']:assert sha(E/r['file'])==r['sha256'],r
    c=load('t1-mark-offline-closure.json');assert len(c['edges'])==19 and c['analysisEdgesClosed']==16 and c['namedRuntimeEdgesPending']==3
    assert len(c['sharedOwnerReferencedCriticalEntries'])==12 and c['actualRuntimeB']==0 and c['realBindings'] is None and c['A1_A16']=='PENDING'
    owner=c['narrowA8Proof'];assert not owner['boundedParameterProvenance']['unresolved']
    g=owner['completeConstructorGraph'];census=g['census'];discovery=g['derivedForwardingCallerInventory']
    parsed={x['path'] for x in census['sourceFiles']+discovery['sourceFiles']};audits=census['reflectionAudits']+discovery['reflectionAudits']
    assert parsed=={x['path'] for x in audits} and not any(x['newRelevantHits'] for x in audits if x['scope']=='PRODUCTION_SOURCE')
    assert len(census['production'])==6 and len(census['harness'])==20
    order=load('producer-order.json');assert order['requiredOrder']==['pending_contracts.py','edge_categories.py']
    for key,script in [('stage1','pending_contracts.py'),('final','edge_categories.py')]:
        row=order[key];assert sha(E/row['artifact'])==row['sha256'] and sha(E/script)==row['producerSHA256']
    contract=load('pending-interface-contracts.json');assert contract['artifactStage']=='PRODUCER2_FINAL_ORDERED_CONTRACT_PROOF' and contract['targetedCategorySHA256']==sha(E/'targeted-category-delta.json')
    for n,count in [('rev9e-unit-results.json',31),('parameter-binding-test-results.json',11),('universe-audit-test-results.json',6)]:assert len(load(n)['cases'])==count and all(x['pass'] for x in load(n)['cases'])
    names=['analysis-rule-test-results.json','rev9b-analysis-test-results.json','t1-test-results.json','rev9c-regression-results.json','rev9d-regression-results.json','owner-original-reviewer70-results.json','proof-checks.json','publication-gates.json','deterministic-generation-results.json','completed-regression-source-seal.json']
    retained=[{'path':(old/n).relative_to(ROOT).as_posix(),'sha256':sha(old/n),'atBase':receipts['base'],'rerun':False} for n in names]
    before=E/'completed-before-final-identity-t1-mark-offline-closure.json'
    if before.exists():assert sha(before)==sha(E/'t1-mark-offline-closure.json')
    result={'verified':True,'finalIdentityRefreshClosureByteIdentical':before.exists(),'closureSHA256':sha(E/'t1-mark-offline-closure.json'),'source':receipts['productSource'],'parsedAndAuditedPaths':sorted(parsed),'productionPaths':sorted(p for p in parsed if not p.startswith('tests/')),'parameterBindings':len(owner['boundedParameterProvenance']['bindings']),'modelLifecycleFrozen':receipts['modelLifecycleFrozen'],'accountingArtifactsByteIdentical':6,'retainedBroadReceipts':retained,'stage1SHA256':order['stage1']['sha256'],'finalSHA256':order['final']['sha256'],'actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING','independentReview':'Rev9e PENDING through Root','sealTiming':'POST_RUN byte seal; not instrumentation proving producer bytes during preceding executions'}
    (E/'rev9e-current-verification.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps({'verified':True,'parsedAuditedPaths':len(parsed),'bindings':result['parameterBindings'],'retainedBroadReceipts':len(retained)}))
if __name__=='__main__':main()
