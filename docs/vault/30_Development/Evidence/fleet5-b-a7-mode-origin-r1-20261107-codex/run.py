"""Compact command receipts and artifact manifest; no analysis/sealing framework."""
import datetime,hashlib,json,os,subprocess,sys
from pathlib import Path
E=Path(__file__).resolve().parent;R=next(p for p in E.parents if (p/'AGENTS.md').exists());OLD=E.parent/'fleet5-b-a7-snapshot-r2-20261107-codex';P='D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe';STATE=Path('D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json')
HELPERS=('source_bindings.py','call_binding.py','callee_identity.py','lexical_bindings.py','reflection_audit.py','use_sites.py','owner_transfer.py','measured_run.py')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def hashes():return {p.relative_to(R).as_posix():sha(p) for p in [*sorted(E.glob('*.py')),*sorted(E.glob('*.py.txt')),*[OLD/n for n in HELPERS]]}
def command(label,args):
    assert not (E/(label+'.json')).exists();before=hashes();state_before=sha(STATE) if '--check' in args and any('sync_obsidian.py' in x for x in args) else None;argv=[P,'-B',str(OLD/'measured_run.py'),*args];kst=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat();proc=subprocess.run(argv,cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1'));raw=E/(label+'.log');raw.write_bytes(proc.stdout);after=hashes();state_after=sha(STATE) if state_before else None
    row={'argv':argv,'cwd':str(R),'python':sys.version,'kst':kst,'exit':proc.returncode,'log':raw.name,'logSHA256':sha(raw),'producerHashesBefore':before,'producerHashesAfter':after,'stateBefore':state_before,'stateAfter':state_after,'measurementScope':'child process only, serial; no aggregate/quota/OS enforcement'};(E/(label+'.json')).write_bytes((json.dumps(row,indent=2)+'\n').encode());print(json.dumps({'label':label,'exit':proc.returncode,'hashesEqual':before==after,'stateEqual':state_before==state_after,'tail':proc.stdout.decode('utf8','replace')[-800:]}),flush=True);assert before==after and proc.returncode==0,label
    if state_before:assert state_before==state_after,'canonical state changed during CHECK; preserve concurrent Root writes'
def main():
    phase=sys.argv[1]
    if phase=='cmd':command(sys.argv[2],sys.argv[3:])
    elif phase=='docs':
        tag=sys.argv[2];jobs=[['tools/check_docs.py'],['tools/check_ontology.py'],['tools/sync_obsidian.py','--check','--state',str(STATE),'--conflicts-out',str(E/(tag+'-conflicts.json'))],['tools/check_contract_bindings.py'],['tools/check_frontend_integrity.py'],['tools/check_doc_single_source.py','--ratchet'],['tools/check_response_freshness.py'],['tools/check_doc_path_citations.py','--ratchet','--base-ref','969030dbc7716b9cadf75bd314713005306ed34c']]
        for i,args in enumerate(jobs,1):command(tag+'-'+str(i),args)
    elif phase=='manifest':
        inputs=json.loads((E/'inputs.json').read_bytes())
        prior=[E.parent/'fleet5-b-a7-snapshot-r1-20261107-codex',OLD];assert not subprocess.check_output(['git','diff','--name-only',inputs['base'],'--',*[str(p.relative_to(R)) for p in prior]],cwd=R)
        for x in inputs['immutablePredecessor']:assert sha(R/x['path'])==x['sha256']
        for x in inputs['reviewOriginals']:assert sha(E/x['copy'])==x['sha256']
        files=[{'file':p.name,'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(E.iterdir()) if p.is_file() and p.name!='manifest.json'];h=R/'docs/vault/30_Development/History/2026-11-07_FLEET5_B_A7_Mode_Origin_R1_Codex.md';result={'base':inputs['base'],'productSource':inputs['productSource'],'files':files,'producerHashes':hashes(),'history':{'path':h.relative_to(R).as_posix(),'sha256':sha(h)},'independentReview':'PENDING','baselineAcceptedDischarges':0,'actualRuntimeB':0};(E/'manifest.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps({'files':len(files),'producerAndHelperFiles':len(result['producerHashes']),'manifestSHA256':sha(E/'manifest.json')}))
    else:raise ValueError(phase)
if __name__=='__main__':main()
