import os,subprocess,secrets,json,time,sys,uuid
from pathlib import Path
import psycopg
from psycopg.conninfo import make_conninfo
root=Path(__file__).resolve().parents[1]; os.chdir(root); (root/'.work').mkdir(exist_ok=True); name='sv-container-'+uuid.uuid4().hex
image='postgres:16'
password=secrets.token_urlsafe(32)
cid=None
try:
    cid=subprocess.check_output(['docker','run','-d','--name',name,'--label','ai.saintvision.configured='+name,'--memory','768m','--cpus','1','--pids-limit','256','--tmpfs','/var/lib/postgresql/data','--publish','127.0.0.1::5432','--env','POSTGRES_PASSWORD',image],env={**os.environ,'POSTGRES_PASSWORD':password},text=True).strip()
    info=json.loads(subprocess.check_output(['docker','inspect',cid],text=True))[0]
    port=info['NetworkSettings']['Ports']['5432/tcp'][0]['HostPort']
    dsn=make_conninfo(host='127.0.0.1',port=port,dbname='postgres',user='postgres',password=password,connect_timeout=2)
    for _ in range(100):
        try:
            with psycopg.connect(dsn) as conn: conn.execute('SELECT 1')
            break
        except psycopg.OperationalError: time.sleep(.2)
    else: raise RuntimeError('isolated PostgreSQL unavailable')
    cmd=[sys.executable,'-m','pytest','-q','tests/integration/test_approval_browser.py','--junitxml=.work/approval-browser-tests.xml']
    result=subprocess.run(cmd,env={**os.environ,'INV_TEST_ADMIN_DSN':dsn,'INV_BROWSER_TEST':'1','INV_TEST_SERVER_IMAGE':'saintvision-backend-candidate:6ff090b','INV_CONTAINER_TEST_DB_HOST':info['NetworkSettings']['IPAddress']},capture_output=True,text=True,timeout=300)
    (root/'.work/approval-browser-private.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    # Pytest failures might contain DSNs: output only summary lines here.
    print('\n'.join(l for l in result.stdout.splitlines() if l.startswith(('FAILED','ERROR','===','..')) or 'passed' in l))
    proof={'command':'python -m pytest -q tests/integration/test_approval_browser.py','exitCode':result.returncode,'postgres':'isolated tmpfs cluster; localhost ephemeral port','http':'real kernel FastAPI routes with non-owner PostgreSQL and synthetic JWT; no Node execution','identity':'synthetic RS256 issuer; no operational SSO claim','browser':'real headless Chromium/Edge; production ApprovalCenter in test-only entry; configured server factory over HTTP'}
finally:
    if cid:
        label=subprocess.check_output(['docker','inspect',cid,'--format','{{index .Config.Labels "ai.saintvision.configured"}}'],text=True).strip()
        assert label==name
        subprocess.run(['docker','rm','-f',cid],check=True,stdout=subprocess.DEVNULL)
if 'proof' in locals():
    proof['isolatedContainerRemoved']=True
    (root/'.work/approval-browser.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')

if 'proof' in locals(): sys.exit(proof['exitCode'])
