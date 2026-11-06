"""Seal final receipts without changing source, canonical state or runtime."""
import argparse,datetime,hashlib,json,subprocess
from pathlib import Path
from run_rev9g import snapshot
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists());OLD=E.parent/'fleet5-b-rev9f-20261107-codex'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def main():
    p=argparse.ArgumentParser();p.add_argument('--proof',required=True);p.add_argument('--docs',required=True);a=p.parse_args()
    receipts=load(E/'input-receipts.json');current=load(E/'rev9g-current-verification.json');proof=load(E/a.proof);docs=load(E/a.docs);sources=snapshot()
    assert current['verified'] and len(proof['commands'])==9 and proof['allExpectedExits']
    assert len(docs['commands'])==8
    all_commands=proof['commands']+docs['commands']
    for row in all_commands:
        assert sha(E/row['log'])==row['logSHA256'] and row['producerHashesBefore']==row['producerHashesAfter']==sources
        if Path(row['argv'][3]).name!='sync_obsidian.py':assert row['matchedExpected']
    sync=next(row for row in docs['commands'] if Path(row['argv'][3]).name=='sync_obsidian.py')
    originals=[]
    for row in load(OLD/'proof-producer-hashes.json')['originalReviewCopiesVerified']:
        assert sha(E/row['file'])==row['sha256'];originals.append(row)
    for row in receipts['actualPriorReview']:
        assert sha(E/row['copy'])==row['sha256']
        assert subprocess.check_output(['git','rev-parse',row['commit']+':'+row['path']],cwd=ROOT).decode().strip()==row['objectID']
        originals.append({'file':row['copy'],'sha256':row['sha256'],'reviewCommit':row['commit'],'objectID':row['objectID']})
    assert len(originals)==81
    for row in receipts['immutableRetained']:assert sha(ROOT/row['path'])==row['sha256']
    for name,h in receipts['modelLifecycleFrozen'].items():assert sha(E/name)==h
    for row in receipts['accountingBaseline']:assert sha(E/row['file'])==row['sha256']
    scripts=[{'file':p.name,'sha256':sha(p),'bytes':p.stat().st_size,'byteIdenticalToPredecessor':(OLD/p.name).exists() and sha(OLD/p.name)==sha(p)} for p in sorted(E.iterdir()) if p.is_file() and (p.suffix=='.py' or p.name.endswith('.py.txt'))]
    history=ROOT/'docs/vault/30_Development/History/2026-11-07_FLEET5_B_Rev9g_FixOnly_Codex.md'
    names=['input-receipts.json','rev9g-unit-results.json','rev9g-gap-results.json','rev9g-current-verification.json','t1-mark-offline-closure.json','pending-obligations.json','pending-interface-contracts.stage1.json','pending-interface-contracts.json','producer-order.json','development-failures.json',a.proof,a.docs]
    peaks=[row['resource']['peakWorkingSetBytes'] for row in all_commands if row['resource'] and row['resource']['peakWorkingSetBytes'] is not None]
    out={'task':receipts['task'],'base':receipts['base'],'productSource':receipts['productSource'],'rootMessage':receipts['rootMessage'],'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'producersAndRetainedScripts':scripts,'originalReviewCopiesVerified':originals,'actualReviewOriginalsPreserved':13,'modelLifecycleFrozen':receipts['modelLifecycleFrozen'],'accountingArtifactsByteIdentical':6,'commandReceipts':[{'file':n,'sha256':sha(E/n)} for n in (a.proof,a.docs)],'artifacts':[{'file':n,'sha256':sha(E/n),'bytes':(E/n).stat().st_size} for n in names],'history':{'path':history.relative_to(ROOT).as_posix(),'sha256':sha(history)},'finalProofCommands':9,'finalProofAllExpectedExits':True,'finalDocsCommands':8,'finalDocsMatchingExpected':sum(r['matchedExpected'] for r in docs['commands']),'canonicalSyncCheck':{'exit':sync['actualExit'],'stateBeforeSHA256':sync['canonicalStateBeforeSHA256'],'stateAfterSHA256':sync['canonicalStateAfterSHA256'],'matchesExpected':sync['matchedExpected'],'apply':False,'concurrentRootWritesPossible':True},'sourceExecutionBrackets':'Every final command has identical per-file before/after hashes, equal to these final script bytes. This is bracketing evidence, not continuous instrumentation. No final guard changed after the final causal cases.','currentCases':{'relevantASTBinder':28,'actualIndependentRedOwnerGreen':3,'fullProvenanceControls':9},'closureSHA256':current['closureSHA256'],'stage1SHA256':current['stage1SHA256'],'finalSHA256':current['finalSHA256'],'retainedPredecessor':current['retainedPredecessor'],'immutableRetainedFilesVerified':len(receipts['immutableRetained']),'maximumObservedProcessPeakBytes':max(peaks),'resourceScope':'Observed per-process peaks only; no aggregate or hard quota/OS enforcement claim','expectedR4Exits':[0,1],'actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING','A7':'UNSTARTED / NOT_GRANTED','independentRev9gReview':'PENDING through Root','codeOrPortGrant':False,'partialFreeze':False,'fullAssembler':'NOT_RUN','obsidianApply':False,'CIAtCommit':'One exact own Docs follows commit/push; actual run returned to Root, no future ID invented'}
    (E/'proof-producer-hashes.json').write_bytes((json.dumps(out,indent=2)+'\n').encode());print(json.dumps({'scripts':len(scripts),'scriptBytes':sum(r['bytes'] for r in scripts),'originalReviewCopies':len(originals),'actualReviewOriginals':13,'proofCommands':9,'docsMatchingExpected':out['finalDocsMatchingExpected'],'manifestSHA256':sha(E/'proof-producer-hashes.json'),'peak':max(peaks)}))
if __name__=='__main__':main()
