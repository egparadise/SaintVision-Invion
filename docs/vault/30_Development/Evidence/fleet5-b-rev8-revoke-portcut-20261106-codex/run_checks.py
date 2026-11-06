"""Exact serial OWNER commands/KST/exits/hashes, unique Evidence outputs only."""
import argparse,datetime,hashlib,json,subprocess,sys,time
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--publication',action='store_true');a=p.parse_args()
    if a.publication:
        phase='publication-gates';spec=[([str(ROOT/'tools'/n),*args],0) for n,args in (
          ('check_docs.py',[]),('check_ontology.py',[]),('sync_obsidian.py',['--check','--state','D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json','--conflicts-out',str(E/'canonical-sync-check-conflicts.json')]),
          ('check_contract_bindings.py',[]),('check_frontend_integrity.py',[]),('check_doc_single_source.py',['--ratchet']),('check_response_freshness.py',[]),('check_doc_path_citations.py',['--ratchet','--base-ref','33f7c6b48883cb06d1ea7d645bdb88634eb1bca0']))]
    else:
        phase='proof-checks';spec=[([str(E/n)],0) for n in ('schema.py','authority.py')]
        spec += [([str(E/'regression_red_green.py'),str(E.parent/'fleet5-b-contract-rev7-20261106-codex')],1),([str(E/'regression_red_green.py'),str(E)],0)]
        spec += [([str(E/n)],0) for n in ('proof_tests.py','bounded_analysis.py','analysis_tests.py','pending_contracts.py','edge_categories.py','transport_delta.py','retained_tests.py','packet_checks.py')]
        spec += [(['tests/proofs/fleet5_compute_storage_contract_probe.py'],0),(['tests/proofs/fleet5_compute_storage_contract_probe.py','--require-coexistence'],1)]
    state=Path('D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json');before=sha(state) if a.publication else None
    commands=[]
    for i,(args,expected) in enumerate(spec,1):
        cmd=[sys.executable,'-B',str(E/'measured_run.py'),*args];log=E/f'{phase}-{i}.log';t=time.monotonic()
        with log.open('wb') as out:r=subprocess.run(cmd,cwd=ROOT,stdout=out,stderr=subprocess.STDOUT)
        raw=log.read_bytes();resource=None
        for line in raw.decode('utf-8','replace').splitlines():
            try:value=json.loads(line)
            except ValueError:continue
            if isinstance(value,dict) and 'ownerResourceMeasurement' in value:resource=value['ownerResourceMeasurement']
        row={'command':cmd,'expectedExit':expected,'actualExit':r.returncode,'seconds':round(time.monotonic()-t,3),'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'log':log.name,'sha256':hashlib.sha256(raw).hexdigest(),'resource':resource};commands.append(row)
        data={'phase':phase,'commands':commands,'canonicalSyncStateBeforeSHA256':before,'canonicalSyncStateAfterSHA256':sha(state) if a.publication else None,'obsidianApply':False,'actualRuntimeB':0,'fullAssembler':'NOT_RUN','source':'72028cbac903c4415d9979f980a6e0f9948e914f','independentReview':'PENDING through Root'}
        (E/f'{phase}.json').write_bytes((json.dumps(data,indent=2)+'\n').encode());print(json.dumps(row),flush=True)
        if r.returncode!=expected:
            print(raw.decode('utf-8','replace')[-4000:]);raise SystemExit(1)
    if a.publication:assert data['canonicalSyncStateBeforeSHA256']==data['canonicalSyncStateAfterSHA256']
if __name__=='__main__':main()
