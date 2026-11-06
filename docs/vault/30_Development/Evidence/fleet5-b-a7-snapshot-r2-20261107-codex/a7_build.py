"""A7 sidecar only. Retained global artifacts are compared, never regenerated."""
import sys
import a7_body as body,a7_inventory as inventory
from a7_common import *

def build(world=None):
    with body.target_scope():b=body.prove(world);c=inventory.prove(world)
    frozen=json.loads((E/'input-receipts.json').read_bytes());unchanged=[]
    for row in frozen['immutableRetained']:
        if 'copy' not in row:continue
        actual=hashlib.sha256((E/row['copy']).read_bytes()).hexdigest();assert actual==row['sha256'],row['copy'];unchanged.append({'file':row['copy'],'sha256':actual})
    status='SOURCE_STATIC_CLOSED_RUNTIME_PENDING' if b['bodyAccepted'] and c['callerClosureAccepted'] else 'SOURCE_STATIC_UNRESOLVED_RUNTIME_PENDING'
    return {'entry':'A7 NodeChannels.snapshot HELPER_SIDECAR_NOT_AN_ADDITIONAL_GRANTABLE_ENTRY','status':status,'body':b,'callers':c,'retainedByteEqual':unchanged,'grants':{'actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING','sharedEntries':12,'edges':19,'analysisEdges':16,'runtimeEdges':3,'unchangedGlobalCounts':[598,757,1071,21,573,218]},'interpretation':'AST/source certification only; unresolved mode/Database-owner/caller obligations block grant. Frozen no-new-use guards are not runtime effect closure.'}

def main():
    sys.stdout.reconfigure(encoding='utf8');result=build();emit('a7-snapshot-sidecar.json',result)
    print(json.dumps({'status':result['status'],'bodyAccepted':result['body']['bodyAccepted'],'bodyReason':result['body']['reason'],'constructors':len(result['callers']['census']['constructorSites']),'snapshots':len(result['callers']['census']['snapshotSites']),'callerObligations':len(result['callers']['obligations']),'actualRuntimeB':0}));assert result['body']['bodyAccepted'],result['body']['reason']
if __name__=='__main__':main()
