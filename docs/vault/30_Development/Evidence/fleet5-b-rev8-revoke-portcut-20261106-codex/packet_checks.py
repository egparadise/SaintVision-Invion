"""Streaming own packet invariants. No full assembler or product invocation."""
import hashlib,json,subprocess
from pathlib import Path
from jsonschema import Draft202012Validator
from schema import build
from authority import build as authority,invariants
from model import World,binding,scope,sk,VER
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    receipt=json.loads((E/'input-receipts.json').read_bytes());assert receipt['base']=='33f7c6b48883cb06d1ea7d645bdb88634eb1bca0'
    for item in receipt['immutableRetained']:assert sha(ROOT/item['path'])==item['sha256'],item['path']
    schema=build();Draft202012Validator.check_schema(schema);assert not invariants(authority())
    pilot=json.loads((E/'pilot-closure.json').read_bytes());assert pilot['entry']=='inv.node_channels.revoke_channel' and pilot['notGrantable'] and len(pilot['closedAnalysisEdges'])==3
    cat=json.loads((E/'critical-edge-categories.json').read_bytes());assert cat['criticalEntryCount']==21 and cat['nonPilotEntryStatusChanges']==0 and cat['sourceLockPlanCounts']=={'all':39,'withProcedureRefs':33,'withoutProcedureRefs':6}
    assert cat['missingPortOccurrences']==757 and cat['distinctReferencedUnknowns']==598
    for edge in cat['edges']:
        assert all(k in edge for k in ('source','type','receiver','binding','proof','futureWork','blocksGrant'))
        assert edge['category']=='DYNAMIC_BLOCK' or edge['category'].startswith(('ANALYSIS_RULE:A','NAMED_PORT:','IO_CATALOG_LINK:'))
        if not edge['blocksGrant']:assert edge['closedOnlyForEntry']=='inv.node_channels.revoke_channel'
    c=json.loads((E/'pending-interface-contracts.json').read_bytes());assert len(c['contracts'])==10
    for port in c['contracts']:assert port['actualBinding'] is None and not port['codeGrant'] and not port['portGrant']
    w=World();b=binding(w);b['observation_only']=True
    from model import shape
    assert not shape('ioBinding',b) # no public flag can choose the recovery lane
    census=json.loads((E/'writer-census-delta.json').read_bytes());assert census['allWriterRows']==389 and census['BAuthorityWriters']==34 and census['BWriterMappingUnchanged']
    diff=subprocess.check_output(['git','diff','72028cbac903c4415d9979f980a6e0f9948e914f','--name-only','--','deploy','services','src','migrations','tests','tools','contracts','packages','apps','.github'],cwd=ROOT)
    assert not diff,diff.decode()
    result={'retainedImmutableFilesVerified':len(receipt['immutableRetained']),'criticalUnknownsCategorized':598,'onlyPilotEdgesClosed':3,'allDBWriters':389,'BauthorityWriters':34,'productDiffPaths':0,'actualRuntimeB':0,'independentRev8Review':'PENDING','realBindings':None,'partialFreeze':False}
    (E/'packet-check-results.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps(result))
if __name__=='__main__':main()
