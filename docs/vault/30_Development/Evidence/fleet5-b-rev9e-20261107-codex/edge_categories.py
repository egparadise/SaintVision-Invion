"""Producer2: precise target-only category delta; no global substring classifier."""
import ast,datetime,hashlib,json,subprocess
from pathlib import Path
import bounded_analysis as a
import analysis_rules as r
import t1_provenance as t
E=Path(__file__).resolve().parent;R8=E.parent/'fleet5-b-rev8-revoke-portcut-20261106-codex'
SIX={
 '0c55b8d56234e5a548d5eec022a9d6965ff20f80d91f130d83c5dcb23aff1d60':'ANALYSIS_RULE:A2',
 '12fc7b7611336899d3e12cf34f87113ced7398cf2eec4f44fea1f3be9d9fcde7':'NAMED_PORT:P-PUBLIC-SIGNATURE-VERIFY',
 '2694f1602e6f243a7e23931c0fa37e9d915490fe0cf6b5dbbcbd415201bdc5bb':'ANALYSIS_RULE:A4',
 '2805a1b950907c9dd052f9d5a1cf2242522334a2f2721eadcfea4ed6236b8c52':'ANALYSIS_RULE:A4',
 '6f527581d8b2eed4619b5265fc998693453e6e0ea11695fd2cfda50c6e7688ff':'ANALYSIS_RULE:A2',
 'bc24f7b2291988a25339d1b50cf267a6396a4cbf0753d2b33657adaf45996fe1':'IO_CATALOG_LINK'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    old=json.loads((R8/'critical-edge-categories.json').read_bytes());closure=json.loads((E/'t1-mark-offline-closure.json').read_bytes());oldby={e['callRef']:e for e in old['edges']}
    calls={c['id']:c for c in a.rows('classifiedCalls') if c['id'] in SIX};assert set(calls)==set(SIX)
    paths=sorted({c['path'] for c in calls.values()});sources=t.read_batch(paths)
    transport=json.loads((E.parent/'fleet5-b-contract-rev7-20261106-codex/transport-inventory.json').read_bytes());io={}
    tls_kinds={'EXECUTE','CANCEL','RECEIPT_OBSERVE','HEARTBEAT_OBSERVE','GPU_ACTIVE_OBSERVE','STORAGE_SAMPLE','OBJECT_READ','TERMINAL_FRAME','QUARANTINE_RECONCILE'}
    for c in transport['callers']:
        for v in c['variants']:
            if v['kind'] in tls_kinds:io.setdefault(v['kind'],[]).append({'path':c['path'],'line':c['line'],'function':c['function'],'fileSHA256':c['fileSHA256'],'effectClass':v['effectClass'],'selector':v['predicate']})
    assert set(io)==tls_kinds # local protected reads/buildctl never inherit TLS permission
    delta=[]
    for edge in closure['edges']:
        category='ANALYSIS_RULE:'+edge['rule'] if not edge['rule'].startswith('NAMED_PORT:') else edge['rule']
        delta.append({'callRef':edge['callRef'],'oldCategory':oldby[edge['callRef']]['category'],'category':category,'source':edge['source'],'receiver':edge['receiver'],'proof':edge['proof'],'pendingRuntimeContract':edge['pendingRuntimeContract'],'blocksGrant':edge['blocksGrant'],'sharedOwner':edge['sharedOwner'],'closedOnlyForEntry':edge['closedOnlyForEntry'],'scope':'T1_TARGET_SUBGRAPH_ONLY'})
    for ref,category in SIX.items():
        c=calls[ref];source=sources[c['path']];node=a.node_at(source,c);w=t.witness(c['path'],source,node,function=c['function'])
        common={'callRef':ref,'oldCategory':oldby[ref]['category'],'source':w,'receiver':{'expression':c['spelling'],'inferredType':c['receiverType'],'exactInferredTarget':c['inferredTarget']},'blocksGrant':True,'closedOnlyForEntry':None,'proofStatus':'UNRESOLVED_NAMED_OR_ANALYSIS_CONTRACT_NOT_APPLIED','actualBinding':None,'scope':'EXACT_REVIEW_NAMED_MISCATEGORY_ONLY'}
        if category=='IO_CATALOG_LINK':
            cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name=='OneConnection');assert [r.text(b) for b in cls.bases]==['http.client.HTTPSConnection'] and r.text(node.func)=='super().connect'
            for kind,refs in sorted(io.items()):delta.append({**common,'category':'IO_CATALOG_LINK:'+kind,'binding':{'existingInterface':'T2 NodeTLSClient._request -> OneConnection HTTPSConnection','kind':kind,'exactCallerBoundaries':refs,'effectClass':refs[0]['effectClass']},'futureWork':'Actual TLS/peer/current channel/opaque-handle enforcement remains pending for this exact existing kind. Shared transport IO never becomes READ_ONLY from method naming; no new network permission.'})
        else:
            explanation={'ANALYSIS_RULE:A2':'Exact InvError.__post_init__/category_of body with imported builtin Exception/Enum bindings; pending outside selected T1 DomainError cut, not a dynamic dispatch claim.',
              'ANALYSIS_RULE:A4':"Exact importlib.resources files('inv').joinpath('generated/core.schema.json') readonly owned package resource contract; installed readonly package/parent/mode proof pending, no arbitrary path permission.",
              'NAMED_PORT:P-PUBLIC-SIGNATURE-VERIFY':'Exact certificate_key(...).verify public signature authority check for signed storage sample; current signer/DER/channel/challenge/time/algorithm proof pending, never crypto purity.'}[category]
            delta.append({**common,'category':category,'binding':{'requiredContract':category,'sourceSHA256':w['sourceFileSHA256']},'futureWork':explanation})
    touched={e['callRef'] for e in delta};assert len(touched)==len(closure['edges'])+6
    outside=[e for e in old['edges'] if e['callRef'] not in touched]
    result={'source':a.SOURCE,'baseSidecar':{'path':str((R8/'critical-edge-categories.json').relative_to(a.ROOT)).replace('\\','/'),'sha256':sha(R8/'critical-edge-categories.json')},
      'immutableAccounting':{'criticalParents':21,'distinctUnknownRefs':598,'missingLabels':757,'unknownRefOccurrences':1071},'deltas':delta,'uniqueTouchedUnknownRefs':len(touched),'reviewNamedOutsideCutRefs':sorted(SIX),'nonTargetCategoryRowsReferencedUnchanged':len(outside),
      'outsideRowCanonicalSHA256':hashlib.sha256(json.dumps(outside,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'priorFallbackRows':227,'remainingUnreviewedFallbackRows':sum(e['category']=='DYNAMIC_BLOCK' for e in outside),'unreviewedFallbackBacklog':'All other parent categorization stays immutable/unreviewed. No global Low closure, exemption, runtime denial or support upgrade.',
      'parentStatusUpgrades':0,'sourceSubset':{'files':paths,'count':len(paths),'bytes':sum(len(s.encode()) for s in sources.values())},'actualRuntimeB':0,'realBindings':None}
    p=E/'targeted-category-delta.json';p.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    staged=E/'pending-interface-contracts.stage1.json';contracts=json.loads(staged.read_bytes())
    for contract in contracts['contracts']:
        if contract['id'] in ('T1','P-DBROLE','P-PUBLIC-SIGNATURE-VERIFY'):
            contract['targetedWiring']=[{k:e[k] for k in ('callRef','category','source','receiver','blocksGrant')} for e in delta if (contract['id']=='P-PUBLIC-SIGNATURE-VERIFY' and e['category']=='NAMED_PORT:'+contract['id']) or (contract['id'] in ('T1','P-DBROLE') and e['callRef'] in {x['callRef'] for x in closure['edges']})]
    contracts['artifactStage']='PRODUCER2_FINAL_ORDERED_CONTRACT_PROOF';contracts['targetedCategorySHA256']=sha(p)
    final=E/'pending-interface-contracts.json';final.write_bytes((json.dumps(contracts,indent=2)+'\n').encode())
    order={'requiredOrder':['pending_contracts.py','edge_categories.py'],'stage1':{'artifact':staged.name,'sha256':sha(staged),'producerSHA256':sha(E/'pending_contracts.py'),'acceptedFinalProof':False},'final':{'artifact':final.name,'sha256':sha(final),'producerSHA256':sha(E/'edge_categories.py'),'acceptedFinalProof':'ORDERED_STATIC_ARTIFACT_ONLY_NOT_REVIEW_OR_RUNTIME_ACCEPTANCE'},'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'actualRuntimeB':0}
    (E/'producer-order.json').write_bytes((json.dumps(order,indent=2)+'\n').encode());print(json.dumps({'touchedUnknownRefs':len(touched),'deltaRows':len(delta),'nonTargetUnchanged':len(outside),'stage1SHA256':sha(staged),'finalSHA256':sha(final),'outsideStatusUpgrades':0}))
if __name__=='__main__':main()
