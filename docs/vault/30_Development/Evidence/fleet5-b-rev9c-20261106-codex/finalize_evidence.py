"""Final own Rev9c receipts; no shared state mutation or product execution."""
import datetime,hashlib,json
from pathlib import Path
E=Path(__file__).resolve().parent
ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(n):return json.loads((E/n).read_bytes())
def main():
    commands=[]
    for name,count in [('proof-checks.json',16),('publication-gates.json',8)]:
        d=load(name);assert len(d['commands'])==count
        for c in d['commands']:
            assert c['expectedExit']==c['actualExit']
            assert sha(E/c['log'])==c['sha256']
        if name.startswith('publication'):assert d['canonicalSyncStateBeforeSHA256']==d['canonicalSyncStateAfterSHA256']
        commands.extend(d['commands'])
    receipts=load('input-receipts.json');prior=load('prior-input-receipts.json');originals=[]
    for r in receipts['actualPriorReview']:
        p=E/r['copy'];assert sha(p)==r['sha256'];originals.append({'file':p.name,'sha256':sha(p),'reviewCommit':r['commit']})
    for r in prior['actualPriorReview']:
        p=E/('rev9-review-'+Path(r['path']).name);assert sha(p)==r['sha256'];originals.append({'file':p.name,'sha256':sha(p),'reviewCommit':r['commit']})
    for r in receipts['immutableRetained']:assert sha(ROOT/r['path'])==r['sha256']
    for n,h in receipts['modelLifecycleFrozen'].items():assert sha(E/n)==h
    counts={}
    for n,expected in [('analysis-rule-test-results.json',31),('t1-test-results.json',83),('factory-binding-test-results.json',4),('function-header-test-results.json',3)]:
        d=load(n);assert len(d['cases'])==expected and all(x['pass'] for x in d['cases']);counts[n]=expected
    d=load('rev9b-analysis-test-results.json');assert len(d['additionalCases'])==19 and all(x['pass'] for x in d['additionalCases']) and not d['exactOriginal70SoundGaps'] and not d['exactOriginal70PositiveFailures']
    r=load('rev9c-regression-results.json');assert r['cases']>=29 and len(r['oldAcceptedNewRefused'])>=20
    deterministic=load('deterministic-generation-results.json');assert deterministic['byteIdentical']
    sources=[{'file':p.name,'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(E.iterdir()) if p.is_file() and (p.suffix=='.py' or p.name.endswith('.py.txt'))]
    history=ROOT/'docs/vault/30_Development/History/2026-11-06_FLEET5_B_Rev9c_FixOnly_Codex.md'
    peaks=[c['resource']['peakWorkingSetBytes'] for c in commands if c['resource'] and c['resource']['peakWorkingSetBytes'] is not None]
    nested=[]
    for n in ('old-bound-contrast.log','new-bound-contrast.log','determinism-11.log','determinism-29.log'):
        for line in (E/n).read_text('utf8').splitlines():
            try:x=json.loads(line)
            except ValueError:continue
            if isinstance(x,dict) and 'ownerResourceMeasurement' in x:nested.append({'log':n,**x['ownerResourceMeasurement']})
    peaks.extend(x['peakWorkingSetBytes'] for x in nested if x['peakWorkingSetBytes'] is not None)
    out={'task':receipts['task'],'base':receipts['base'],'productSource':receipts['productSource'],'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),
         'producersAndRetainedScripts':sources,'originalReviewCopiesVerified':originals,'immutableRetainedFilesVerified':len(receipts['immutableRetained']),'modelLifecycleFrozen':receipts['modelLifecycleFrozen'],
         'commandReceipts':[{'file':n,'sha256':sha(E/n)} for n in ('proof-checks.json','publication-gates.json')],'history':{'path':history.relative_to(ROOT).as_posix(),'sha256':sha(history)},
         'currentStaticCases':counts,'original70OwnerReplay':{'gaps':0,'positiveFailures':0},'additionalInheritedAnalysisCases':19,'newRegressionCases':r['cases'],'oldGapsNowRefused':len(r['oldAcceptedNewRefused']),
         'retainedModelEvidence':'Accepted 870486 model182/terminal47/recovery79+8/terminal old-new exits1,1,0 referenced without rerunning unchanged model bytes',
         'all24CommandsMatchedExpectedExit':True,'expectedR4Exits':[0,1],'deterministicClosureSHA256':deterministic['commands'][0]['closureSHA256'],'nestedProcessObservations':nested,'maximumObservedProcessPeakBytes':max(peaks),
         'resourceScope':'Per-process observations only, not aggregate or hard quota; OS limit not enforced; legacy70 inner subprocess peak unmeasured',
         'actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING','independentRev9cReview':'PENDING through Root','codeOrPortGrant':False,'partialFreeze':False,'fullAssembler':'NOT_RUN','obsidianApply':False}
    (E/'proof-producer-hashes.json').write_bytes((json.dumps(out,indent=2)+'\n').encode())
    print(json.dumps({'producersAndScripts':len(sources),'reviewCopies':len(originals),'commands':24,'newCases':r['cases'],'oldGapsNowRefused':len(r['oldAcceptedNewRefused']),'maximumObservedProcessPeakBytes':max(peaks),'independentReview':'PENDING'}))
if __name__=='__main__':main()
