"""Own Rev9e final byte receipts. Post-run seal, never runtime instrumentation."""
import datetime,hashlib,json,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists());OLD=E.parent/'fleet5-b-rev9d-20261107-codex'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def main():
    receipts=load(E/'input-receipts.json');current=load(E/'rev9e-current-verification.json');contrast=load(E/'rev9e-contrast-verification.json')
    assert current['verified'] and len(contrast['actual9266GapsNowRefused'])==6
    commands=[]
    for n,count in [('proof-checks.json',13),('publication-gates.json',8)]:
        d=load(E/n);assert len(d['commands'])==count
        for c in d['commands']:assert c['actualExit']==c['expectedExit'] and sha(E/c['log'])==c['sha256']
        commands+=d['commands']
        if n.startswith('publication'):assert d['canonicalSyncStateBeforeSHA256']==d['canonicalSyncStateAfterSHA256']
    originals=[]
    for r in load(OLD/'proof-producer-hashes.json')['originalReviewCopiesVerified']:
        assert sha(E/r['file'])==r['sha256'];originals.append(r)
    for r in receipts['actualPriorReview']:
        assert sha(E/r['copy'])==r['sha256']
        raw=subprocess.check_output(['git','show',r['commit']+':'+r['path']],cwd=ROOT);assert hashlib.sha256(raw).hexdigest()==r['sha256']
        originals.append({'file':r['copy'],'sha256':r['sha256'],'reviewCommit':r['commit']})
    assert len(originals)==54
    for r in receipts['immutableRetained']:assert sha(ROOT/r['path'])==r['sha256']
    for n,h in receipts['modelLifecycleFrozen'].items():assert sha(E/n)==h
    for r in receipts['accountingBaseline']:assert sha(E/r['file'])==r['sha256']
    scripts=[{'file':p.name,'sha256':sha(p),'bytes':p.stat().st_size,'byteIdenticalToPrior':(OLD/p.name).exists() and sha(OLD/p.name)==sha(p)} for p in sorted(E.iterdir()) if p.is_file() and (p.suffix=='.py' or p.name.endswith('.py.txt'))]
    history=ROOT/'docs/vault/30_Development/History/2026-11-07_FLEET5_B_Rev9e_FixOnly_Codex.md'
    peaks=[c['resource']['peakWorkingSetBytes'] for c in commands if c['resource'] and c['resource']['peakWorkingSetBytes'] is not None]
    artifact_names=['input-receipts.json','rev9e-unit-results.json','parameter-binding-test-results.json','universe-audit-test-results.json','rev9e-old-six-results.json','rev9e-new-results.json','rev9e-contrast-verification.json','rev9e-current-verification.json','t1-mark-offline-closure.json','pending-obligations.json','pending-interface-contracts.stage1.json','pending-interface-contracts.json','producer-order.json','proof-checks.json','publication-gates.json','development-failures.json','development-first-run-proof-checks.json','development-first-run-rev9e-new-results.json','completed-before-final-identity-proof-checks.json','completed-before-final-identity-t1-mark-offline-closure.json']
    data={'task':receipts['task'],'base':receipts['base'],'productSource':receipts['productSource'],'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'rootGrant':receipts['rootMessage'],'producersAndRetainedScripts':scripts,'originalReviewCopiesVerified':originals,'immutableRetainedFilesVerified':len(receipts['immutableRetained']),'modelLifecycleFrozen':receipts['modelLifecycleFrozen'],'accountingArtifactsByteIdentical':6,'currentStaticCaseCounts':{'affectedNewUnits':31,'existingParameterBinder':11,'existingUniverseGuards':6,'oldCausalGapsAccepted':6,'newCausalGapsRefused':6,'newFullProvenanceControls':7},'commandReceipts':[{'file':n,'sha256':sha(E/n)} for n in ('proof-checks.json','publication-gates.json')],'artifacts':[{'file':n,'sha256':sha(E/n),'bytes':(E/n).stat().st_size} for n in artifact_names],'history':{'path':history.relative_to(ROOT).as_posix(),'sha256':sha(history)},'retainedBroadReceipts':current['retainedBroadReceipts'],'all21FinalCommandsMatchedExpectedExit':True,'expectedR4Exits':[0,1],'closureSHA256':current['closureSHA256'],'stage1SHA256':current['stage1SHA256'],'finalSHA256':current['finalSHA256'],'maximumObservedProcessPeakBytes':max(peaks),'resourceScope':'Observed per-process peak only, no aggregate or hard quota/OS enforcement','producerSealTiming':'POST_RUN byte seal. Does not instrument or prove producer stability throughout the earlier runs. Broad unchanged receipts are retained, not executed again.','CIAtCommit':'Exact own Docs run follows this commit/push; no future run ID invented','actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING','A7':'UNSTARTED / NOT_GRANTED','independentRev9eReview':'PENDING through Root','codeOrPortGrant':False,'partialFreeze':False,'fullAssembler':'NOT_RUN','obsidianApply':False}
    first=load(E/'development-first-run-proof-checks.json')
    for c in first['commands']:assert sha(E/('development-first-run-'+c['log']))==c['sha256']
    data['firstAttempt']={'commandCount':len(first['commands']),'actualExits':[c['actualExit'] for c in first['commands']],'preservedReceipt':'development-first-run-proof-checks.json','producerSealAtFirstExecution':'NOT_INSTRUMENTED','maximumObservedProcessPeakBytes':max(c['resource']['peakWorkingSetBytes'] for c in first['commands'] if c['resource'])}
    data['maximumObservedProcessPeakBytes']=max(data['maximumObservedProcessPeakBytes'],data['firstAttempt']['maximumObservedProcessPeakBytes'])
    data['reusedCompletedCommands']=[c['log'] for c in commands if c.get('reusedCompletedReceipt')]
    (E/'proof-producer-hashes.json').write_bytes((json.dumps(data,indent=2)+'\n').encode())
    print(json.dumps({'scripts':len(scripts),'rawReviewCopies':len(originals),'finalCommands':21,'oldAcceptedNewRefused':6,'accountingByteIdentical':6,'maximumObservedProcessPeakBytes':max(peaks),'manifestSHA256':sha(E/'proof-producer-hashes.json')}))
if __name__=='__main__':main()
