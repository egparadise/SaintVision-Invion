"""Final own packet receipts; reads no private state except prior check receipts."""
import datetime,hashlib,json,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent
ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def load(name):return json.loads((E/name).read_bytes())

def main():
    commands=[]
    for name,count in [('proof-checks.json',20),('publication-gates.json',8)]:
        d=load(name);assert len(d['commands'])==count
        for c in d['commands']:
            assert c['expectedExit']==c['actualExit'],c
            assert sha(E/c['log'])==c['sha256'],c['log']
        if name.startswith('publication'):
            assert d['canonicalSyncStateBeforeSHA256']==d['canonicalSyncStateAfterSHA256']
        commands.extend(d['commands'])
    receipts=load('input-receipts.json');originals=[]
    for r in receipts['actualPriorReview']:
        p=E/('rev9-review-'+Path(r['path']).name)
        assert sha(p)==r['sha256'],p
        originals.append({'file':p.name,'sha256':sha(p),'immutableReviewCommit':r['commit']})
    for r in receipts['immutableRetained']:assert sha(ROOT/r['path'])==r['sha256']
    cases={}
    for n,expected in [('model-test-results.json',182),('rev9b-model-test-results.json',47),('analysis-rule-test-results.json',31),('t1-test-results.json',83),('factory-binding-test-results.json',4),('function-header-test-results.json',3)]:
        d=load(n);assert len(d['cases'])==expected and all(x['pass'] for x in d['cases']);cases[n]=expected
    d=load('rev9b-analysis-test-results.json');assert len(d['additionalCases'])==19 and all(x['pass'] for x in d['additionalCases']) and not d['exactOriginal70SoundGaps'] and not d['exactOriginal70PositiveFailures']
    original70=load('owner-original-reviewer70-results.json');assert len(original70['cases'])==70 and all(x.get('producerSanity',True) for x in original70['cases'])
    sources=[{'file':p.name,'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(E.iterdir()) if p.is_file() and (p.suffix=='.py' or p.name.endswith('.py.txt'))]
    history=ROOT/'docs/vault/30_Development/History/2026-11-06_FLEET5_B_Rev9b_FixOnly_Codex.md'
    peaks=[c['resource']['peakWorkingSetBytes'] for c in commands if c['resource'] and c['resource']['peakWorkingSetBytes'] is not None]
    d={'task':receipts['task'],'base':receipts['base'],'productSource':receipts['productSource'],
       'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),
       'producers':sources,'originalReviewCopiesVerified':originals,'immutableRetainedFilesVerified':len(receipts['immutableRetained']),
       'commandReceipts':[{'file':n,'sha256':sha(E/n)} for n in ('proof-checks.json','publication-gates.json')],
       'history':{'path':str(history.relative_to(ROOT)).replace('\\','/'),'sha256':sha(history)},
       'symbolicAndStaticCases':cases,'original70Gaps':0,'original70PositiveFailures':0,'additionalAnalysisCases':19,
       'expectedRedExits':{'oldTerminalRev7':1,'oldTerminalRev8':1,'newTerminalRev9b':0,'R4Baseline':0,'R4RequireCoexistence':1},
       'maximumMeasuredOwnerProcessPeakBytes':max(peaks),'resourcePolicy':'Observed per owner process; not a hard quota; nested subprocess peaks not included; OS memory limit not enforced',
       'all28CommandsMatchedExpectedExit':True,'actualRuntimeB':0,'runtimeBindings':None,'A1_A16':'PENDING',
       'independentRev9bReview':'PENDING through Root; original raw reviewer metadata retained without implying a new review',
       'noCodeOrPortGrant':True,'noPartialFreeze':True,'fullAssembler':'NOT_RUN','obsidianApply':False}
    (E/'proof-producer-hashes.json').write_bytes((json.dumps(d,indent=2)+'\n').encode())
    print(json.dumps({'producerHashes':len(sources),'originalReviewCopies':len(originals),'commands':28,'peakBytes':max(peaks),'independentRev9bReview':'PENDING'}))

if __name__=='__main__':main()
