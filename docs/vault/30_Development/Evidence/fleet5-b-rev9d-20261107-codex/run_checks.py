"""Serial exact owner commands/exits/KST/hash/resource and fresh sync CHECK."""
import argparse,datetime,hashlib,json,subprocess,sys,time
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--publication',action='store_true');a=p.parse_args()
    if a.publication:
        phase='publication-gates';spec=[([str(ROOT/'tools'/n),*args],0) for n,args in (
          ('check_docs.py',[]),('check_ontology.py',[]),('sync_obsidian.py',['--check','--state','D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json','--conflicts-out',str(E/'canonical-sync-check-conflicts.json')]),
          ('check_contract_bindings.py',[]),('check_frontend_integrity.py',[]),('check_doc_single_source.py',['--ratchet']),('check_response_freshness.py',[]),('check_doc_path_citations.py',['--ratchet','--base-ref','5ea87937f1b542f8cbe32c08dc224526965a8e2d']))]
    else:
        phase='proof-checks';spec=[([str(E/n)],0) for n in ('schema.py','authority.py','bounded_analysis.py','analysis_rule_tests.py','rev9b_factory_binding_tests.py','rev9b_function_header_tests.py','rev9b_analysis_tests.py','parameter_binding_tests.py','universe_audit_tests.py','t1_build.py','t1_tests.py','rev9c_regressions.py','verify_completed_regressions.py','deterministic_generation.py','pending_obligations.py','pending_contracts.py','edge_categories.py','packet_checks.py')]
        spec += [(['tests/proofs/fleet5_compute_storage_contract_probe.py'],0),(['tests/proofs/fleet5_compute_storage_contract_probe.py','--require-coexistence'],1)]
    state=Path('D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json');before=None;after=None
    commands=[]
    for i,(args,expected) in enumerate(spec,1):
        cmd=[sys.executable,'-B',str(E/'measured_run.py'),*args];log=E/f'{phase}-{i}.log';t=time.monotonic()
        sync_call=Path(args[0]).name=='sync_obsidian.py'
        if sync_call:before=sha(state)
        with log.open('wb') as out:r=subprocess.run(cmd,cwd=ROOT,stdout=out,stderr=subprocess.STDOUT)
        if sync_call:after=sha(state)
        raw=log.read_bytes();resource=None
        for line in raw.decode('utf8','replace').splitlines():
            try:v=json.loads(line)
            except ValueError:continue
            if isinstance(v,dict) and 'ownerResourceMeasurement' in v:resource=v['ownerResourceMeasurement']
        row={'command':cmd,'expectedExit':expected,'actualExit':r.returncode,'seconds':round(time.monotonic()-t,3),'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'log':log.name,'sha256':hashlib.sha256(raw).hexdigest(),'resource':resource};commands.append(row)
        data={'phase':phase,'commands':commands,'canonicalSyncStateBeforeSHA256':before,'canonicalSyncStateAfterSHA256':after,'syncHashTiming':'IMMEDIATELY_BEFORE_AND_AFTER_EACH_SYNC_CALL','obsidianApply':False,'actualRuntimeB':0,'fullAssembler':'NOT_RUN','productSource':'72028cbac903c4415d9979f980a6e0f9948e914f','independentReview':'Rev9d PENDING via Root; actual4288 Rev9c LOW-only REVISION_REQUIRED; M1/current-source closure stands','actualRuntimeBindings':None,'modelLifecycle':'BYTE_IDENTICAL_TO_5ea/870; retained accepted model/recovery tests referenced, not rerun'}
        (E/f'{phase}.json').write_bytes((json.dumps(data,indent=2)+'\n').encode());print(json.dumps(row),flush=True)
        if r.returncode!=expected:print(raw.decode('utf8','replace')[-4500:]);raise SystemExit(1)
        if sync_call:assert before==after,'Canonical state changed during CHECK; no apply was requested'
    if a.publication:assert data['canonicalSyncStateBeforeSHA256']==data['canonicalSyncStateAfterSHA256']
if __name__=='__main__':main()
