"""Serial old/new actual-gap contrast and byte-exact original47 owner replay."""
import datetime,hashlib,json,subprocess,sys
from pathlib import Path
E=Path(__file__).resolve().parent;OLD=E.parent/'fleet5-b-rev9c-20261106-codex'

def run(script,target,out,label):
    log=E/(label+'.log');cmd=[sys.executable,'-B',str(E/'measured_run.py'),str(script),str(target),str(out)]
    with log.open('wb') as stream:p=subprocess.run(cmd,stdout=stream,stderr=subprocess.STDOUT)
    row={'command':cmd,'actualExit':p.returncode,'log':log.name,'logSHA256':hashlib.sha256(log.read_bytes()).hexdigest(),'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()}
    if p.returncode:print(log.read_text('utf8',errors='replace')[-2500:]);raise SystemExit(p.returncode)
    return json.loads(out.read_bytes()),row

def main():
    old,a=run(E/'rev9d_gap_driver.py',OLD,E/'old-gap-results.json','old-gap-contrast')
    new,b=run(E/'rev9d_gap_driver.py',E,E/'new-gap-results.json','new-gap-contrast')
    closed=[]
    for x,y in zip(old['cases'],new['cases']):
        assert x['case']==y['case'] and y['observed']==y['expectedNew'] and y['witnessesChecked']==15
        if x['gapAt5ea']:assert x['observed']=='ACCEPT' and y['observed']=='REFUSE';closed.append(y['case'])
    assert len(closed)==8
    raw,c=run(E/'rev9c-review-reviewer_rev9c_delta_probes.py.txt',E,E/'owner-original47-results.json','owner-original47-replay')
    # The optional keyword binder strengthens one refusal from the use-site
    # layer to the graph. Preserve original expectations/results verbatim and
    # explain only that exact label change; every semantic expectation remains.
    allowed={'L2-keyword-only-in-source-full'}
    unexpected=[]
    for row in raw['cases']:
        assert row['astValid'] and not row['newUnboundNames'] and row['witnessesChecked'] in (14,15)
        if row['matchesExpectation']:continue
        if row['case'] in allowed and row['observed']=='REFUSE' and row['reason'].startswith('RECEIVER_UNION_UNPROVEN:'):continue
        unexpected.append(row)
    assert not unexpected,unexpected
    result={'executionOwner':'Codex OWNER; original reviewer metadata/script retained byte-exact, not new independent review','commands':[a,b,c],'actualGapContrasts':closed,'oldNewCasesEach':len(new['cases']),'original47Cases':len(raw['cases']),'rawOriginal47MismatchLabels':raw['mismatches'],'explainedStrengthenedKeywordRefusal':sorted(allowed & set(raw['mismatches'])),'unexpectedSemanticResults':unexpected,'actualRuntimeB':0,'realBindings':None,'fixtureBugs':'Original reviewer run1/run3 line-shift failures retained separately; no product negative inferred from them'}
    (E/'rev9d-regression-results.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps({'actualGapsClosed':8,'original47Cases':len(raw['cases']),'unexpectedSemanticResults':0,'rawMismatchLabels':raw['mismatches']}))
if __name__=='__main__':main()
