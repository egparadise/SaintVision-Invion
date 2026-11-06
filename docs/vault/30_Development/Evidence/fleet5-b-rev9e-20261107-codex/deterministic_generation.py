"""Cross-hash-seed byte reproducibility of own targeted closure, serial only."""
import datetime,hashlib,json,os,subprocess,sys
from pathlib import Path
E=Path(__file__).resolve().parent

def main():
    rows=[]
    for seed in ('11','29'):
        env=dict(os.environ,PYTHONHASHSEED=seed);cmd=[sys.executable,'-B',str(E/'measured_run.py'),str(E/'t1_build.py')]
        log=E/('determinism-'+seed+'.log')
        with log.open('wb') as f:r=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
        row={'command':cmd,'PYTHONHASHSEED':seed,'actualExit':r.returncode,'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'log':log.name,'logSHA256':hashlib.sha256(log.read_bytes()).hexdigest()};rows.append(row)
        if r.returncode:print(log.read_text('utf8',errors='replace')[-2000:]);raise SystemExit(r.returncode)
        row['closureSHA256']=hashlib.sha256((E/'t1-mark-offline-closure.json').read_bytes()).hexdigest()
    assert rows[0]['closureSHA256']==rows[1]['closureSHA256']
    (E/'deterministic-generation-results.json').write_bytes((json.dumps({'executionOwner':'Codex','commands':rows,'byteIdentical':True,'producerOrderNext':['pending_contracts.py','edge_categories.py'],'actualRuntimeB':0},indent=2)+'\n').encode());print(json.dumps({'byteIdentical':True,'closureSHA256':rows[0]['closureSHA256']}))

if __name__=='__main__':main()
