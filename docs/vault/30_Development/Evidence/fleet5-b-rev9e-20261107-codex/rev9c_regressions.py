"""Serial old/new contrast with explicit source fixtures, raw outputs retained."""
import datetime,hashlib,json,subprocess,sys
from pathlib import Path
E=Path(__file__).resolve().parent;OLD=E.parent/'fleet5-b-rev9b-20261106-codex'

def main():
    receipts=[];data=[]
    for label,target in [('old',OLD),('new',E)]:
        out=E/(label+'-bound-contrast-results.json');log=E/(label+'-bound-contrast.log')
        cmd=[sys.executable,'-B',str(E/'measured_run.py'),str(E/'rev9c_probe_driver.py'),str(target),str(out)]
        with log.open('wb') as stream:r=subprocess.run(cmd,stdout=stream,stderr=subprocess.STDOUT)
        row={'command':cmd,'actualExit':r.returncode,'log':log.name,'logSHA256':hashlib.sha256(log.read_bytes()).hexdigest(),'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()};receipts.append(row)
        if r.returncode:print(log.read_text('utf8',errors='replace')[-2500:]);raise SystemExit(r.returncode)
        d=json.loads(out.read_bytes());data.append(d)
    old,new=data;assert len(old['cases'])==len(new['cases'])
    gaps=[];controls=[]
    for a,b in zip(old['cases'],new['cases']):
        assert a['case']==b['case'] and b['producerSanity'] and not b['newUnboundNames']
        assert b['observed']==b['expectedNew']
        if b['expectedReasonPrefix']:assert b['reason'].startswith(b['expectedReasonPrefix'])
        if a['oldGapExpected']:
            assert a['observed']=='ACCEPT',a
            gaps.append(a['case'])
        else:controls.append({'case':a['case'],'old':a['observed'],'new':b['observed']})
    result={'executionOwner':'Codex OWNER, not independent review','commands':receipts,'cases':len(new['cases']),'oldAcceptedNewRefused':gaps,'controls':controls,
            'oldWorldOverlayNote':'Old pipeline has no complete source-view discovery API; outside overlay is omitted from its manually selected inputs. New pipeline receives the explicit fixture source view and discovers/refuses omitted relevant production files.',
            'effectfulMutantsImportedOrExecuted':False,'actualRuntimeB':0,'realBindings':None}
    (E/'rev9c-regression-results.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps({'cases':result['cases'],'oldGapsNowRefused':len(gaps),'controls':len(controls)}))

if __name__=='__main__':main()
