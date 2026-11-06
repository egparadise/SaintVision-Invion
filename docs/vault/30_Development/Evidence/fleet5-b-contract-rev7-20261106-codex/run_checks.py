"""Exact serial commands/exits/raw hashes. No physical/runtime operations."""
import argparse,datetime,hashlib,json,subprocess,sys,time
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
def main():
    arg=argparse.ArgumentParser();arg.add_argument('--source',action='store_true');arg.add_argument('--publication',action='store_true');arg.add_argument('--display',action='store_true');a=arg.parse_args()
    if a.source:
        phase='source-checks';spec=[([str(E/n)],0) for n in ('source_fixtures.py','source_analysis.py','sanitize_display.py','reconcile.py','link_plans.py','baseline_accounting.py')]
    elif a.display:
        phase='display-checks';spec=[([str(E/n)],0) for n in ('sanitize_display.py','reconcile.py','link_plans.py','baseline_accounting.py')]
    elif a.publication:
        phase='publication-gates';spec=[([str(ROOT/'tools'/n),*args],0) for n,args in (
          ('check_docs.py',[]),('check_ontology.py',[]),('sync_obsidian.py',['--check','--state','D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json','--conflicts-out',str(E/'canonical-sync-check-conflicts.json')]),
          ('check_contract_bindings.py',[]),('check_frontend_integrity.py',[]),('check_doc_single_source.py',['--ratchet']),('check_response_freshness.py',[]),('check_doc_path_citations.py',['--ratchet','--base-ref','ee97c27a5d135a4059256124290731cd2b791193']))]
    else:
        phase='proof-checks';spec=[([str(E/n)],0) for n in ('schema.py','authority.py','fixtures.py','transport_inventory.py','prior_closed.py','packet_checks.py')]+[(['tests/proofs/fleet5_compute_storage_contract_probe.py'],0),(['tests/proofs/fleet5_compute_storage_contract_probe.py','--require-coexistence'],1)]
    output=[];state=Path('D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json')
    before=hashlib.sha256(state.read_bytes()).hexdigest() if a.publication else None
    for i,(args,expected) in enumerate(spec,1):
        cmd=[sys.executable,'-B',*args];log=E/f'{phase}-{i}.log';started=time.monotonic()
        with log.open('wb') as stream:r=subprocess.run(cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        row={'command':cmd,'expectedExit':expected,'actualExit':r.returncode,'seconds':round(time.monotonic()-started,3),'log':log.name,'sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()};output.append(row)
        data={'phase':phase,'commands':output,'canonicalSyncStateBeforeSHA256':before,'canonicalSyncStateAfterSHA256':hashlib.sha256(state.read_bytes()).hexdigest() if a.publication else None,'obsidianApply':False,'actualRuntimeB':0}
        (E/f'{phase}.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf8');print(json.dumps(row),flush=True)
        if r.returncode!=expected:
            print(log.read_text(encoding='utf8',errors='replace')[-6000:]);raise SystemExit(1)
    if a.publication:assert data['canonicalSyncStateBeforeSHA256']==data['canonicalSyncStateAfterSHA256']
if __name__=='__main__':main()
