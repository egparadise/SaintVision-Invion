"""Fresh bounded deterministic rebuild plus original-blob and input checks."""
import ast,json,subprocess,sys
import a7_build
from a7_common import *

def main():
    sys.stdout.reconfigure(encoding='utf8');before=(E/'a7-snapshot-sidecar.json').read_bytes();actual=a7_build.build();expected=(json.dumps(actual,indent=2,sort_keys=True)+'\n').encode();assert before==expected,'sidecar nondeterministic'
    assert actual['body']['bodyAccepted'] and not actual['callers']['callerClosureAccepted'];assert actual['status']=='SOURCE_STATIC_UNRESOLVED_RUNTIME_PENDING'
    receipt=json.loads((E/'input-receipts.json').read_bytes());copies=[]
    for row in receipt['actualAcceptedReview']:
        blob=subprocess.check_output(['git','show',row['commit']+':'+row['path']],cwd=ROOT);assert blob==(E/row['copy']).read_bytes();oid=subprocess.check_output(['git','rev-parse',row['commit']+':'+row['path']],cwd=ROOT).decode().strip();assert oid==row['objectID'];copies.append({'file':row['copy'],'objectID':oid,'sha256':sha(blob.decode('utf8'))})
    for row in receipt['immutableRetained']:assert hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()==row['sha256']
    for row in actual['callers']['census']['sourceFiles']:assert sha(frozen_source(row['path']))==row['sha256']
    tests=json.loads((E/'a7-test-results.json').read_bytes());assert not tests['failures'] and all(x['expectationMet'] for x in tests['cases']);inputs=json.loads((E/'a7-test-inputs.json').read_bytes())
    for row in tests['cases']:
        for p,s in inputs[row['name']].items():compile(s,p,'exec',dont_inherit=True);assert sha(s)==row['inputSHA256'][p]
    from a7_record import producers
    files=producers()
    for p in E.glob('*.py'):ast.parse(p.read_bytes(),str(p))
    result={'verified':True,'deterministicSidecarSHA256':hashlib.sha256(before).hexdigest(),'originalReviewCopiesVerified':copies,'sourceCandidatesParsed':len(actual['callers']['census']['sourceFiles']),'constructorSites':len(actual['callers']['census']['constructorSites']),'snapshotSites':len(actual['callers']['census']['snapshotSites']),'sourceForwardingStates':len(actual['callers']['forwarding']['states']),'sourceForwardingEvents':len(actual['callers']['forwarding']['events']),'callerObligations':len(actual['callers']['obligations']),'sourceCases':len(tests['cases']),'literalTruthinessUnits':len(tests['literalTruthinessUnits']),'finalProducerHashes':files,'actualRuntimeB':0,'independentA7Review':'PENDING through Root'}
    emit('a7-current-verification.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ('finalProducerHashes','originalReviewCopiesVerified')}))
if __name__=='__main__':main()
