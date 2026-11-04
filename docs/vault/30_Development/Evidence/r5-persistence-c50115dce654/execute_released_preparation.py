from pathlib import Path
import datetime as dt,hashlib,json,os,subprocess
P=Path(__file__).resolve().parent
B=P.parent/'r5-followup-0814ec2a5432'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp():return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
pin='c981dc09dc8eaf5ff7a1596771cb679cad43024cc913abefa119998ceba4c7e6'
assert sha(B/'preparation-commands.private.json')==pin
manifest=json.loads((P.parents[1]/'docs/vault/30_Development/Evidence/r5-followup-0814ec2a5432/packet-manifest.json').read_text())
for v in manifest['inputs']:assert sha(B/v['name'])==v['sha256']
rows=json.loads((B/'preparation-commands.private.json').read_text())
results=[];failed=False
env={k:v for k,v in os.environ.items() if k.upper() not in {'PYTHONPATH','PYTHONHOME'}}
for alias in ['node-1','node-2']:
    for row in [r for r in rows if r['id'].startswith(alias+'-')]:
        data=None
        if row.get('stdinFile'):
            assert sha(row['stdinFile'])==row['stdinSHA256'];data=Path(row['stdinFile']).read_bytes()
        result=dict(id=row['id'],startedAtKST=stamp(),commandSourceSHA256=pin,technicalRelease='msg_c6fa3bda6ff3')
        try:
            r=subprocess.run(row['argv'],input=data,capture_output=True,timeout=240,env=env)
            result['exit']=r.returncode;stdout=r.stdout;stderr=r.stderr
        except subprocess.TimeoutExpired as error:
            result.update(exit=124,errorClass='TimeoutExpired',remoteCompletionUnknown=True)
            stdout=error.stdout or b'';stderr=error.stderr or b''
        (P/(row['id']+'.private.stdout')).write_bytes(stdout)
        (P/(row['id']+'.private.stderr')).write_bytes(stderr)
        result.update(finishedAtKST=stamp(),stdoutSHA256=sha(P/(row['id']+'.private.stdout')),stderrSHA256=sha(P/(row['id']+'.private.stderr')))
        if result['exit']==0 and 'install-and-preflight' in row['id']:
            v=json.loads(stdout.decode().splitlines()[-1]);proof=v['postPrepWorkerPreflight']
            assert proof['compatible'] is True and proof['pythonVersion']==row['expectedActualWorkerPython'] and proof['cryptographyVersion']=='50.0.1' and proof['utcCertificateAPI'] is True
            result.update(actualWorkerPreflight={k:proof[k] for k in ['compatible','pythonVersion','cryptographyVersion','utcCertificateAPI']},bashPinned=v['bashPinned'],nodeIdentityChanged=v['nodeIdentityChanged'])
        results.append(result)
        (P/'runtime-preparation-results.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result),flush=True)
        if result['exit']!=0:failed=True;break
raise SystemExit(2 if failed else 0)
