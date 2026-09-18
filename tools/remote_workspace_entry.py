"""Private container entry for real Node acceptance with an isolated test database.

Synthetic JWT actors exercise the kernel; no public listener or production login
is created. The original operating database/gate is not available to this process.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from types import SimpleNamespace
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo, conninfo_to_dict
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient
from inv.app import create_app
from inv.db import Database
from inv.dispatch import DeliveryWorker
from inv.ids import new_id
from inv.node_channels import provision_channel, NodeChannels
from inv.node_transport import NodeDelivery, NodeTLSClient
from inv.object_store import LocalObjects
from inv.output_ingestion import OutputIngestion, output_bytes
from inv.sandbox import SandboxProfile
from inv.snapshots import SnapshotStore
from inv.tooling import NodePrincipal
from inv.workspace_api import RestrictedWorkspaceRuntime, WorkspaceAPI
from inv.workspace_files import WorkingGenerations, decode_snapshot
from jwt_support import jwt_fixture
from test_workspace_start import input_files, prepare, enqueue, run
from test_workspace_api import approve
from test_node_runtime import active

ROOT = Path('/app')
CONFIG = Path('/run/test/config.json')
CASES = ('python','ai','cancel-before-start','cancel-running','failure','timeout','output-recovery')


def write(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    temporary.chmod(0o600)
    os.replace(temporary,path)


def client():
    return NodeTLSClient(ca_file='/run/test/ca.pem',certificate_file='/run/test/control-cert.pem',
                         key_file='/run/test/control-key.pem',timeout=35)


def database(config):
    return Database(config['runtimeDSN'],recovery_epoch=config['epoch'])


def initialize(config):
    from sqlalchemy.engine import URL
    info = conninfo_to_dict(config['adminDSN'])
    url = URL.create('postgresql+psycopg',username=info['user'],password=info['password'],
                     host=info['host'],port=int(info['port']),database=info['dbname'])
    environment = dict(os.environ,INV_MIGRATION_DSN=url.render_as_string(hide_password=False))
    result = subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=ROOT,env=environment,capture_output=True,timeout=90)
    Path('/evidence/migrations.log').write_bytes(result.stdout+result.stderr)
    if result.returncode: raise ValueError('Isolated database migration failed')
    password = uuid4().hex+uuid4().hex
    config['runtimeDSN'] = make_conninfo(config['adminDSN'],user='inv_remote_runtime',password=password)
    with psycopg.connect(config['adminDSN']) as conn:
        conn.execute(sql.SQL('CREATE ROLE inv_remote_runtime LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE').format(sql.Literal(password)))
        conn.execute('GRANT inv_kernel TO inv_remote_runtime')
        conn.execute('INSERT INTO inv.control_epoch VALUES(true,%s)',(config['epoch'],))
        conn.execute('INSERT INTO inv.tenants VALUES(%s,%s)',(config['tenantId'],'isolated acceptance; synthetic actors'))
        conn.execute("INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch,clock_skew_seconds) VALUES(%s,%s,'online',%s,0)",(config['tenantId'],config['nodeId'],config['epoch']))
        provision_channel(conn,NodePrincipal(config['tenantId'],config['nodeId']),epoch=config['epoch'],
                          endpoint=config['endpoint'],certificate_der=x509.load_pem_x509_certificate(Path('/run/test/node-cert.pem').read_bytes()).public_bytes(serialization.Encoding.DER),expected_version=0)
    write(CONFIG,config)


def setup(config, mode):
    folder = Path('/evidence')/mode
    folder.mkdir(mode=0o700)
    for part in ('objects','working'): (folder/part).mkdir(mode=0o700)
    db = database(config)
    e = SimpleNamespace(tenant=config['tenantId'],node=config['nodeId'],epoch=config['epoch'],
                        project=new_id('prj'),resource=new_id('res'),db=db)
    a = SimpleNamespace(e=e,memory=new_id('res'),workspace_id=new_id('wsp'),folder=folder)
    a.jwt = jwt_fixture(folder,e.tenant)
    with psycopg.connect(config['adminDSN']) as conn:
        conn.execute('INSERT INTO inv.projects VALUES(%s,%s)',(e.tenant,e.project))
        conn.execute('INSERT INTO inv.project_nodes(tenant_id,project_id,node_id) VALUES(%s,%s,%s)',(e.tenant,e.project,e.node))
        for resource,kind,amount in [(e.resource,'cpu',500),(a.memory,'memory',67108864)]:
            conn.execute('INSERT INTO inv.resources VALUES(%s,%s,%s,%s,%s,%s)',(e.tenant,resource,e.node,kind,amount,amount))
        conn.execute('INSERT INTO inv.storage_budgets VALUES(%s,%s,%s)',(e.tenant,e.project,8*1024*1024))
        for actor in ('requester','alice','bob'):
            conn.execute('INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request,can_approve) VALUES(%s,%s,%s,%s,%s)',(e.tenant,e.project,a.jwt.subject(actor),actor=='requester',actor!='requester'))
    a.node = NodePrincipal(e.tenant,e.node)
    a.client = client()
    a.delivery = NodeDelivery(db,a.client)
    a.storage = SnapshotStore(db,LocalObjects(folder/'objects'))
    profile = SandboxProfile('lan-workspace-v1',frozenset({config['image']}),frozenset({'/usr/local/bin/python3'}),500,67108864,20)
    key = serialization.load_pem_private_key(Path('/run/test/signer-key.pem').read_bytes(),password=None)
    a.runtime = RestrictedWorkspaceRuntime(db,profile=profile,node=a.node,resources={'cpu':e.resource,'memory':a.memory},
                                          signing_key=key,policy_version='isolated-remote-acceptance:1',client=a.client)
    a.http = TestClient(create_app(db,a.jwt.auth,workspace=WorkspaceAPI(db,WorkingGenerations(folder/'working'),a.runtime)),raise_server_exceptions=False)
    a.headers = lambda actor='requester',key='first-prepare': {'Authorization':'Bearer '+a.jwt.token(actor),'Idempotency-Key':key}
    response = a.http.post(f'/v1/projects/{e.project}/runs',json={},headers=a.headers(key='create'))
    assert response.status_code == 201
    a.run = response.json()
    a.url = f'/v1/projects/{e.project}/runs/'+a.run['runId']
    a.workload = dict(apiVersion='inv.saintvision.ai/v1alpha1',kind='Workload',workloadId=new_id('wld'),
                     tenantId=e.tenant,projectId=e.project,workspaceId=a.workspace_id,
                     resources=dict(cpuMillis=500,memoryBytes=67108864,gpuCount=0,minVramBytes=0),
                     imageDigest=config['image'],command=['/usr/local/bin/python3','-B','src/app.py'],timeoutSeconds=10)
    a.prepare_input = dict(startId=str(uuid4()),stepId='first-step',expectedVersion=a.run['version'],targetNodeId=e.node)
    input_files(a,'ai' if mode in ('ai','output-recovery') else 'python')
    if mode in ('cancel-running','timeout'):
        a.prepare_input['workload'].update(command=['/usr/local/bin/python3','-B','-c',"import time; print('remote-sleep-started', flush=True); time.sleep(20)"],timeoutSeconds=2 if mode=='timeout' else 20)
    if mode == 'failure': a.prepare_input['workload']['command'] = ['/usr/local/bin/python3','-B','-c','raise SystemExit(7)']
    return a


def cancel(a):
    response = a.http.post(a.url+'/cancel',json={'expectedVersion':run(a)['version']},headers=a.headers(key='cancel'))
    assert response.status_code == 200


def receipt(a):
    with a.e.db.transaction(a.e.tenant) as conn:
        return conn.execute('SELECT envelope FROM inv.node_stop_receipts WHERE command_id=%s',(a.enqueued['commandId'],)).fetchone()['envelope']


def child(config, mode):
    a = config['recovery']
    db = database(config)
    if mode == 'deliver-and-exit':
        assert DeliveryWorker(db,NodeDelivery(db,client())).once(config['tenantId'],command_id=a['commandId']) == 'stopped'
        os._exit(17)
    assert mode == 'recover-output'
    outcome = OutputIngestion(db,LocalObjects(Path(a['objects']))).once(config['tenantId'],command_id=a['commandId'])
    print(json.dumps({'pid':os.getpid(),'outcome':outcome}),flush=True)


def execute(config, mode):
    a = setup(config,mode)
    try:
        prepare(a)
        assert enqueue(a).status_code == 403 and active(a) == 0
        approve(a)
        assert enqueue(a).status_code == 202 and active(a) == 2
        command = a.enqueued['commandId']
        write(a.folder/'accepted.json',dict(runId=a.run['runId'],commandId=command,projectId=a.e.project,scope=config['scope']))
        worker = DeliveryWorker(a.e.db,a.delivery,output_provider=a.storage.provider)
        recovery = None
        if mode == 'cancel-before-start':
            cancel(a)
            assert active(a) == 2
            worker.once(a.e.tenant,command_id=command)
        elif mode == 'cancel-running':
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(worker.once,a.e.tenant,command_id=command)
                time.sleep(2)
                cancel(a)
                DeliveryWorker(a.e.db,a.delivery).once(a.e.tenant,command_id=command,control_only=True)
                pending.result(timeout=35)
        elif mode == 'output-recovery':
            config['recovery'] = dict(commandId=command,objects=str(a.folder/'objects'))
            write(CONFIG,config)
            proc = subprocess.Popen([sys.executable,__file__,'--child','deliver-and-exit'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            stdout,stderr = proc.communicate(timeout=40)
            (a.folder/'sender.log').write_bytes(stdout+stderr)
            assert proc.returncode == 17 and run(a)['state'] == 'running' and active(a) == 0
            saved = receipt(a)
            fixed = subprocess.run([sys.executable,__file__,'--child','recover-output'],capture_output=True,timeout=30)
            (a.folder/'recovery.log').write_bytes(fixed.stdout+fixed.stderr)
            assert fixed.returncode == 0
            recovered = json.loads(fixed.stdout)
            assert recovered['pid'] != proc.pid and receipt(a) == saved
            recovery = dict(senderPID=proc.pid,senderExitCode=17,recoveryPID=recovered['pid'],sameReceipt=True)
        else:
            assert worker.once(a.e.tenant,command_id=command) == 'stopped'
        assert active(a) == 0
        r = receipt(a)
        assert r['stopped']
        current = run(a)
        expected = 'cancelled' if mode.startswith('cancel-') else 'failed' if mode in ('failure','timeout') else 'succeeded'
        assert current['state'] == expected
        assert current['attempt'] == (0 if mode=='cancel-before-start' else 1)
        assert r['processStarted'] is (mode != 'cancel-before-start')
        if mode == 'failure': assert r['exitCode'] == 7
        if mode == 'timeout': assert r['reason'] == 'timeout' or r['exitCode'] == 124
        if mode == 'cancel-running': assert r['reason'] == 'cancelled'
        with a.e.db.transaction(a.e.tenant) as conn:
            completion = conn.execute('SELECT evidence_id FROM inv.result_completions WHERE command_id=%s',(command,)).fetchone()
            envelope = conn.execute('SELECT envelope FROM inv.execution_deliveries WHERE command_id=%s',(command,)).fetchone()['envelope']
        # Re-read the SAME receipt over mTLS; this endpoint cannot execute work.
        duplicate = a.client.exchange(NodeChannels(a.e.db).snapshot(a.node,observation_only=True),envelope,observation_only=True)
        assert duplicate['duplicate'] and not duplicate['cleanupPending'] and duplicate['receipt'] == r
        result = dict(test=mode,passed=True,completedAt=datetime.now(timezone.utc).isoformat(),runId=a.run['runId'],
                      commandId=command,attempt=current['attempt'],state=current['state'],receiptId=r['receiptId'],
                      stopped=r['stopped'],processStarted=r['processStarted'],reason=r['reason'],exitCode=r['exitCode'],
                      activeLeases=0,sameReceiptOnObservation=True,evidenceId=completion['evidence_id'] if completion else None,
                      imageDigest=config['image'],nodeId=config['nodeId'])
        if 'output' in r: result['outputSHA256'] = hashlib.sha256(output_bytes(r)).hexdigest()
        if expected == 'succeeded':
            assert completion
            raw = a.storage.restore(a.e.tenant,a.e.project,a.run['runId'],1,'first-step')
            _,files = decode_snapshot(raw,a.workspace_id)
            result['snapshotSHA256'] = hashlib.sha256(raw).hexdigest()
            result['fileSHA256'] = {p:hashlib.sha256(b).hexdigest() for p,b in files.items()}
            if mode in ('ai','output-recovery'):
                result['metrics'] = json.loads(files['outputs/metrics.json'])
                assert result['metrics']['evaluationMSE'] < 1e-8
        else: assert completion is None
        if recovery: result['recovery'] = recovery
        assert enqueue(a).status_code == 202 if not mode.startswith('cancel-') else True
        return result
    finally:
        a.http.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child',choices=('deliver-and-exit','recover-output'))
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text())
    if args.child:
        child(config,args.child)
        return
    report = dict(scope=config['scope'],nodeId=config['nodeId'],endpoint=config['endpoint'],
                  identity='synthetic-test-actors-isolated-db',productionDatabaseModified=False,tests=[],passed=False)
    try:
        initialize(config)
        for mode in CASES:
            value = execute(config,mode)
            report['tests'].append(value)
            write(Path('/evidence/remote-report.json'),report)
            print(json.dumps({'test':mode,'passed':True,'state':value['state']}),flush=True)
        report['passed'] = True
    except Exception as error:
        Path('/evidence/private-error.txt').write_text(traceback.format_exc())
        report['error'] = dict(type=type(error).__name__,code=getattr(error,'code',None))
        raise
    finally:
        report['completedAt'] = datetime.now(timezone.utc).isoformat()
        write(Path('/evidence/remote-report.json'),report)


if __name__ == '__main__':
    try: main()
    except Exception:
        print('Remote acceptance stopped; private diagnostic retained; no automatic re-execution.',file=sys.stderr)
        raise SystemExit(1)
