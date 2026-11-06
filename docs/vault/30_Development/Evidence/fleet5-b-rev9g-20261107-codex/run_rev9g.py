"""Serial bounded final runs; exact before/after source hashes and honest sync."""
import argparse,datetime,hashlib,json,os,re,subprocess,sys,time
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists());STATE=Path('D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()
def snapshot():return {p.name:sha(p) for p in sorted(E.iterdir()) if p.is_file() and (p.suffix=='.py' or p.name.endswith('.py.txt'))}
def main():
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=('proof','docs'),required=True);p.add_argument('--attempt',required=True);a=p.parse_args();assert re.fullmatch('[a-zA-Z0-9_-]+',a.attempt)
    label=a.phase+'-'+a.attempt;ledger=E/(label+'.json');assert not ledger.exists(),'Never overwrite an attempt'
    if a.phase=='proof':
        specs=[([str(E/n)],0) for n in ('rev9g_units.py','rev9g_gap_driver.py','t1_build.py','pending_obligations.py','pending_contracts.py','edge_categories.py','verify_rev9g.py')]
        specs += [(['tests/proofs/fleet5_compute_storage_contract_probe.py'],0),(['tests/proofs/fleet5_compute_storage_contract_probe.py','--require-coexistence'],1)]
    else:
        specs=[([str(ROOT/'tools'/n),*args],0) for n,args in (
          ('check_docs.py',[]),('check_ontology.py',[]),('sync_obsidian.py',['--check','--state',str(STATE),'--conflicts-out',str(E/(label+'-sync-conflicts.json'))]),
          ('check_contract_bindings.py',[]),('check_frontend_integrity.py',[]),('check_doc_single_source.py',['--ratchet']),('check_response_freshness.py',[]),('check_doc_path_citations.py',['--ratchet','--base-ref','9cea33e8a087981fdedcddb71c4381bdc25c1507']))]
    data={'phase':a.phase,'attempt':a.attempt,'commands':[],'allExpectedExits':True,'sourceHashContract':'Exact per-file hashes immediately before/after each final command. Bracketing checks, not continuous execution-time instrumentation. Any change fails; affected causal runs must be redone after a guard change.','actualRuntimeB':0,'obsidianApply':False,'independentReview':'PENDING'}
    for i,(args,expected) in enumerate(specs,1):
        before=snapshot();started=now();t=time.monotonic();sync=Path(args[0]).name=='sync_obsidian.py';state_before=sha(STATE) if sync else None
        argv=[sys.executable,'-B',str(E/'measured_run.py'),*args];log=E/f'{label}-{i}.log'
        with log.open('wb') as out:r=subprocess.run(argv,cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONUTF8':'1','PYTHONHASHSEED':'0'})
        state_after=sha(STATE) if sync else None;after=snapshot();raw=log.read_bytes();resource=None
        for line in raw.decode('utf8','replace').splitlines():
            try:v=json.loads(line)
            except ValueError:continue
            if isinstance(v,dict) and 'ownerResourceMeasurement' in v:resource=v['ownerResourceMeasurement']
        row={'argv':argv,'cwd':str(ROOT),'python':sys.version,'childEnvironmentOverrides':{'PYTHONUTF8':'1','PYTHONHASHSEED':'0'},'expectedExit':expected,'actualExit':r.returncode,'startedKST':started,'finishedKST':now(),'seconds':round(time.monotonic()-t,3),'log':log.name,'logSHA256':sha(log),'producerHashesBefore':before,'producerHashesAfter':after,'producerHashesMatch':before==after,'canonicalStateBeforeSHA256':state_before,'canonicalStateAfterSHA256':state_after,'resource':resource}
        ok=r.returncode==expected and before==after and (not sync or state_before==state_after);row['matchedExpected']=ok;data['commands'].append(row);data['allExpectedExits'] &= ok
        ledger.write_bytes((json.dumps(data,indent=2)+'\n').encode());print(json.dumps({k:row[k] for k in ('argv','actualExit','expectedExit','seconds','producerHashesMatch','canonicalStateBeforeSHA256','canonicalStateAfterSHA256','resource')}),flush=True)
        if not ok:
            print(raw.decode('utf8','replace')[-3500:])
            # Preserve sync conflicts/state changes honestly and finish the
            # seven other doc checks, without any canonical write or retry.
            if not sync:raise SystemExit(1)
    raise SystemExit(0 if data['allExpectedExits'] else 1)
if __name__=='__main__':main()
