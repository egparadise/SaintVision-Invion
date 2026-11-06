"""Own packet integrity only; immutable old ledgers streamed, no assembler."""
import hashlib,json,subprocess
from pathlib import Path
from jsonschema import Draft202012Validator
from schema import build
from authority import build as authority,invariants
from io_contract import EFFECT
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    receipts=json.loads((E/'input-receipts.json').read_bytes())
    for item in receipts['immutableRetained']:assert sha(ROOT/item['path'])==item['sha256'],item['path']
    Draft202012Validator.check_schema(build());assert not invariants(authority())
    closure=json.loads((E/'t1-mark-offline-closure.json').read_bytes());assert len(closure['edges'])==19 and closure['analysisEdgesClosed']==16 and closure['namedRuntimeEdgesPending']==3 and closure['notGrantable']
    assert len(closure['sharedOwnerReferencedCriticalEntries'])==12 and len(closure['narrowA8Proof']['productionDatabaseConstructors'])==7
    for subset in closure['sourceSubsets']:assert subset['fileCount']<=10 and subset['sourceBytes']<2097152
    delta=json.loads((E/'targeted-category-delta.json').read_bytes());assert delta['uniqueTouchedUnknownRefs']==25 and delta['nonTargetCategoryRowsReferencedUnchanged']==573 and delta['parentStatusUpgrades']==0
    assert delta['immutableAccounting']=={'criticalParents':21,'distinctUnknownRefs':598,'missingLabels':757,'unknownRefOccurrences':1071}
    links=[x for x in delta['deltas'] if x['category'].startswith('IO_CATALOG_LINK:')]
    expected={'EXECUTE','CANCEL','RECEIPT_OBSERVE','HEARTBEAT_OBSERVE','GPU_ACTIVE_OBSERVE','STORAGE_SAMPLE','OBJECT_READ','TERMINAL_FRAME','QUARANTINE_RECONCILE'}
    assert len(links)==9 and {e['category'].split(':',1)[1] for e in links}==expected
    for link in links:assert link['blocksGrant'] and link['binding']['exactCallerBoundaries'] and link['binding']['effectClass']==EFFECT[link['binding']['kind']]
    assert len([x for x in delta['deltas'] if x['category']=='NAMED_PORT:P-PUBLIC-SIGNATURE-VERIFY'])==1
    for e in delta['deltas']:
        if e['callRef'] in delta['reviewNamedOutsideCutRefs']:assert e['blocksGrant']
    oldpath=ROOT/delta['baseSidecar']['path'];old=json.loads(oldpath.read_bytes());touched={e['callRef'] for e in delta['deltas']};outside=[e for e in old['edges'] if e['callRef'] not in touched]
    assert hashlib.sha256(json.dumps(outside,sort_keys=True,separators=(',',':')).encode()).hexdigest()==delta['outsideRowCanonicalSHA256']
    order=json.loads((E/'producer-order.json').read_bytes());assert order['requiredOrder']==['pending_contracts.py','edge_categories.py']
    assert sha(E/order['stage1']['artifact'])==order['stage1']['sha256'] and sha(E/order['final']['artifact'])==order['final']['sha256']
    assert order['stage1']['acceptedFinalProof'] is False
    contracts=json.loads((E/'pending-interface-contracts.json').read_bytes());assert contracts['artifactStage']=='PRODUCER2_FINAL_ORDERED_CONTRACT_PROOF'
    for p in contracts['contracts']:assert p['actualBinding'] is None and not p['codeGrant'] and not p['portGrant']
    diff=subprocess.check_output(['git','diff','72028cbac903c4415d9979f980a6e0f9948e914f','--name-only','--','deploy','services','src','migrations','tests','tools','contracts','packages','apps','.github'],cwd=ROOT);assert not diff
    out={'retainedImmutableFilesVerified':len(receipts['immutableRetained']),'T1AnalysisEdges':16,'T1PendingRuntimeEdges':3,'targetedUnknownRefs':25,'nonTargetUnchanged':573,'remainingUnreviewedFallbackRows':delta['remainingUnreviewedFallbackRows'],'orderedFinalContractSHA256':order['final']['sha256'],'productDiffPaths':0,'actualRuntimeB':0,'realBindings':None,'independentRev9Review':'PENDING via Root','partialFreeze':False}
    (E/'packet-check-results.json').write_bytes((json.dumps(out,indent=2)+'\n').encode());print(json.dumps(out))
if __name__=='__main__':main()
