"""Serial narrow Rev9e commands/exits/KST/hash/process observations."""
import argparse,datetime,hashlib,json,subprocess,sys,time
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--publication',action='store_true');p.add_argument('--resume-fix',action='store_true');p.add_argument('--final-identity',action='store_true');a=p.parse_args()
    if a.publication:
        phase='publication-gates';spec=[([str(ROOT/'tools'/n),*args],0) for n,args in (
          ('check_docs.py',[]),('check_ontology.py',[]),('sync_obsidian.py',['--check','--state','D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json','--conflicts-out',str(E/'canonical-sync-check-conflicts.json')]),
          ('check_contract_bindings.py',[]),('check_frontend_integrity.py',[]),('check_doc_single_source.py',['--ratchet']),('check_response_freshness.py',[]),('check_doc_path_citations.py',['--ratchet','--base-ref','54549b90774aab3599c0486a5217d0d1634baca8']))]
    else:
        phase='proof-checks';spec=[([str(E/n)],0) for n in ('rev9e_units.py','parameter_binding_tests.py','universe_audit_tests.py')]
        spec += [([str(E/'rev9e_gap_driver.py'),str(E.parent/'fleet5-b-rev9d-20261107-codex'),str(E/'rev9e-old-six-results.json')],0),([str(E/'rev9e_gap_driver.py'),str(E),str(E/'rev9e-new-results.json')],0),([str(E/'verify_rev9e.py'),'--contrasts'],0)]
        spec += [([str(E/n)],0) for n in ('t1_build.py','pending_obligations.py','pending_contracts.py','edge_categories.py','verify_rev9e.py')]
        spec += [(['tests/proofs/fleet5_compute_storage_contract_probe.py'],0),(['tests/proofs/fleet5_compute_storage_contract_probe.py','--require-coexistence'],1)]
    state=Path('D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json');before=None;after=None
    commands=[]
    for i,(args,expected) in enumerate(spec,1):
        if a.final_identity and not a.publication and i not in (1,7,11):
            prior=json.loads((E/'completed-before-final-identity-proof-checks.json').read_bytes())['commands'][i-1]
            assert prior['actualExit']==prior['expectedExit']==expected and sha(E/prior['log'])==prior['sha256']
            commands.append({**prior,'reusedCompletedReceipt':True,'reuseReason':'Final module-name alias correction only strengthens identity refusal. Unchanged prior targeted results reused; affected31 units/current positive artifact/hash verification rerun'})
            print(json.dumps(commands[-1]),flush=True);continue
        if a.resume_fix and not a.publication and i in (3,4):
            prior=json.loads((E/'development-first-run-proof-checks.json').read_bytes())['commands'][i-1]
            assert prior['actualExit']==prior['expectedExit']==expected and sha(E/prior['log'])==prior['sha256']
            commands.append({**prior,'reusedCompletedReceipt':True,'reuseReason':'Unchanged reflection universe guard or old immutable54549 six-gap baseline; final new-source cases rerun after constructor correction'})
            print(json.dumps(commands[-1]),flush=True);continue
        cmd=[sys.executable,'-B',str(E/'measured_run.py'),*args];log=E/f'{phase}-{i}.log';t=time.monotonic();started=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()
        sync_call=Path(args[0]).name=='sync_obsidian.py'
        if sync_call:before=sha(state)
        with log.open('wb') as out:r=subprocess.run(cmd,cwd=ROOT,stdout=out,stderr=subprocess.STDOUT)
        if sync_call:after=sha(state)
        raw=log.read_bytes();resource=None
        for line in raw.decode('utf8','replace').splitlines():
            try:v=json.loads(line)
            except ValueError:continue
            if isinstance(v,dict) and 'ownerResourceMeasurement' in v:resource=v['ownerResourceMeasurement']
        row={'command':cmd,'cwd':str(ROOT),'python':sys.version,'expectedExit':expected,'actualExit':r.returncode,'seconds':round(time.monotonic()-t,3),'startedKST':started,'finishedKST':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'log':log.name,'sha256':hashlib.sha256(raw).hexdigest(),'resource':resource};commands.append(row)
        data={'phase':phase,'commands':commands,'canonicalSyncStateBeforeSHA256':before,'canonicalSyncStateAfterSHA256':after,'syncHashTiming':'IMMEDIATELY_BEFORE_AND_AFTER_EACH_SYNC_CALL','obsidianApply':False,'actualRuntimeB':0,'fullAssembler':'NOT_RUN','productSource':'72028cbac903c4415d9979f980a6e0f9948e914f','independentReview':'Rev9e PENDING via Root; actual9266 LOW-only REVISION_REQUIRED','actualRuntimeBindings':None,'unchangedBroadSuites':'NOT_RERUN; immutable 54549 receipts retained by hash'}
        (E/f'{phase}.json').write_bytes((json.dumps(data,indent=2)+'\n').encode());print(json.dumps(row),flush=True)
        if r.returncode!=expected:print(raw.decode('utf8','replace')[-4500:]);raise SystemExit(1)
        if sync_call:assert before==after,'Canonical state changed during CHECK; no apply was requested'
    # Reused tail rows also belong to the persisted ledger, even when no new
    # process follows them. They retain their original measured receipts.
    (E/f'{phase}.json').write_bytes((json.dumps(data,indent=2)+'\n').encode())
    if a.publication:assert data['canonicalSyncStateBeforeSHA256']==data['canonicalSyncStateAfterSHA256']
if __name__=='__main__':main()
