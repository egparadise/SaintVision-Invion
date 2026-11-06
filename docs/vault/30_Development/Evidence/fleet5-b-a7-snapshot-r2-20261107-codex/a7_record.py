"""Serial own-command recorder, complete producer brackets and raw output."""
import datetime,hashlib,json,os,subprocess,sys,time
from pathlib import Path
E=Path(__file__).resolve().parent;R=next(p for p in E.parents if (p/'AGENTS.md').exists());P='D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe'
def producers():
    result={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(E.iterdir()) if p.name.endswith(('.py','.py.txt'))}
    # The copied accepted analysis_rules loads this immutable historical body
    # predicate; bounded_analysis reads this manifest, not its giant ledgers.
    for rel in ('fleet5-b-rev8-revoke-portcut-20261106-codex/bounded_analysis.py','fleet5-b-contract-rev7-20261106-codex/source-manifest.json'):
        result['../'+rel]=hashlib.sha256((E.parent/rel).read_bytes()).hexdigest()
    return result
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
def run(label,args,expected=0,state=None):
    assert not (E/(label+'.json')).exists(),label
    before=producers();state_before=sha(state) if state else None;start=time.monotonic();kst=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat();argv=[P,'-B',str(E/'measured_run.py'),*args];env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONIOENCODING='utf-8')
    proc=subprocess.run(argv,cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env);raw=E/(label+'.log');raw.write_bytes(proc.stdout);after=producers();state_after=sha(state) if state else None
    row={'argv':argv,'cwd':str(R),'python':sys.version,'kst':kst,'exit':proc.returncode,'expectedExit':expected,'elapsedSeconds':time.monotonic()-start,'rawLog':raw.name,'rawSHA256':sha(raw),'producerHashesBefore':before,'producerHashesAfter':after,'producersUnchanged':before==after,'canonicalStateBefore':state_before,'canonicalStateAfter':state_after,'canonicalStateUnchanged':state_before==state_after if state else None,'resourceMeaning':'measured child process peak only, no aggregate or hard quota/OS enforcement'}
    (E/(label+'.json')).write_bytes((json.dumps(row,indent=2)+'\n').encode());print(json.dumps({'label':label,'exit':proc.returncode,'expected':expected,'producersUnchanged':before==after,'stateUnchanged':row['canonicalStateUnchanged'],'tail':proc.stdout.decode('utf-8','replace')[-1800:]}),flush=True)
    assert before==after,label+' producer mutation';assert proc.returncode==expected,label+' exit mismatch'
    if state:assert state_before==state_after,label+' canonical state changed (concurrent Root writes must be preserved)'
    return row
def main():run(sys.argv[1],sys.argv[2:])
if __name__=='__main__':main()
