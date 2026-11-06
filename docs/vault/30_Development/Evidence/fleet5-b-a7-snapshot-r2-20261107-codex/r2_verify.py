"""Bounded deterministic R2 rebuild, immutable review and unchanged proof checks."""
import json,subprocess,sys
import a7_build
from a7_common import *
from a7_record import producers
def main():
    sys.stdout.reconfigure(encoding='utf8');raw=(E/'a7-snapshot-sidecar.json').read_bytes();current=json.loads(json.dumps(a7_build.build()));assert raw==(json.dumps(current,sort_keys=True,indent=2)+'\n').encode()
    old=json.loads((E/'r1-a7-snapshot-sidecar.json').read_bytes());assert current['body']==old['body'];assert current['callers']['obligations']==old['callers']['obligations'] and len(current['callers']['obligations'])==19
    assert current['grants']==old['grants'] and current['status']==old['status']=='SOURCE_STATIC_UNRESOLVED_RUNTIME_PENDING';assert not current['callers']['callerClosureAccepted']
    c=current['callers']['census'];assert c['sourceFiles']==old['callers']['census']['sourceFiles'];assert c['guardCoverage']['parsedPathSHA256']==c['guardCoverage']['auditedPathSHA256']
    assert len(c['guards'])==len(c['sourceFiles'])==30 and len(c['constructorSites'])==len(c['snapshotSites'])==10
    assert current['callers']['forwarding']==old['callers']['forwarding'];assert len(current['callers']['forwarding']['states'])==7 and len(current['callers']['forwarding']['events'])==12
    newly_audited=[r for r in c['guards'] if not r['retainedForCallClosure']];assert len(newly_audited)==18 and all(not r['reflection']['newRelevantHits'] and r['error'] is None for r in newly_audited)
    receipt=json.loads((E/'input-receipts.json').read_bytes());originals=[]
    for row in receipt['actualReview']:
        blob=subprocess.check_output(['git','show',row['commit']+':'+row['path']],cwd=ROOT);oid=subprocess.check_output(['git','rev-parse',row['commit']+':'+row['path']],cwd=ROOT).decode().strip();assert blob==(E/row['copy']).read_bytes() and oid==row['objectID'] and hashlib.sha256(blob).hexdigest()==row['sha256'];originals.append(row)
    preserved=[]
    for row in receipt['copiedProducerClosure']:
        actual=hashlib.sha256((E/row['copy']).read_bytes()).hexdigest()
        if row['copy']!='a7_inventory.py':assert actual==row['sha256'],row['copy'];preserved.append(row['copy'])
    for row in receipt['immutableRetained']+receipt['priorHistoryCopies']:assert hashlib.sha256((E/row['copy']).read_bytes()).hexdigest()==row['sha256']
    tests=json.loads((E/'r2-test-results.json').read_bytes());assert tests['allExpected'] and len(tests['cases'])==5 and all(r['expectationMet'] and r['bodyAccepted'] and not r['callerClosureAccepted'] for r in tests['cases'])
    inputs=json.loads((E/'r2-test-inputs.json').read_bytes())
    for row in tests['cases']:
        for p,s in inputs[row['name']].items():compile(s,p,'exec',dont_inherit=True);assert sha(s)==row['inputSHA256'][p]
    red=json.loads((E/'red-original01.json').read_bytes())['commands'][0];assert red['exit']==red['expectedExit']==1 and red['producersUnchanged'];assert b'MISSING_OR_INEXACT_NEW_CENSUS_DELTA' in (E/red['rawLog']).read_bytes()
    result={'verified':True,'deterministicSidecarSHA256':hashlib.sha256(raw).hexdigest(),'parsedEqualsAudited':c['guardCoverage'],'newlyAudited18Clean':[{'path':r['path'],'sha256':r['sourceSHA256'],'useSiteError':r['error'],'newRelevantHits':r['reflection']['newRelevantHits']} for r in newly_audited],'unchangedOriginal19Obligations':True,'unchangedSelectedBodyProof':True,'unchangedCopiedProducers':preserved,'actualReviewOriginals':originals,'newRegressionAndControls':5,'redActualExit':1,'status':current['status'],'finalProducerHashes':producers(),'actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING','independentR2Review':'PENDING through Root'}
    emit('r2-current-verification.json',result);print(json.dumps({'verified':True,'parsed':30,'audited':30,'newlyAudited18Clean':True,'baselineObligations':19,'cases':5,'sidecarSHA256':result['deterministicSidecarSHA256'],'actualRuntimeB':0}))
if __name__=='__main__':main()
