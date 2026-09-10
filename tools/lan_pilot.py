"""Operator-only two-PC observation bootstrap. No web login, grants or workload dispatch.

All generated material belongs in an ignored private state directory. The worker
archive contains public material only; its private TLS key is created on the worker.
Existing databases, containers, certificates and journals are never reset.
"""
import argparse
from datetime import datetime, timedelta, timezone
import getpass
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from threading import BoundedSemaphore
import time
from uuid import uuid4
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/control-plane/src'))
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from inv.db import Database
from inv.ids import new_id
from inv.node_channels import provision_channel, node_uri
from inv.node_transport import NodeTLSClient
from inv.observer_worker import ObservationWorker
from inv.tooling import NodePrincipal
from lan_pki import ca_pair, issue, pem, private_pem, fingerprint, csr_public_key


def run(args, **kwargs):
    result = subprocess.run([str(x) for x in args], capture_output=True, timeout=kwargs.pop('timeout', 30), **kwargs)
    if result.returncode:
        raise RuntimeError(f'{Path(str(args[0])).name} failed; exit={result.returncode}; diagnostics suppressed')
    return result.stdout.decode('utf-8', errors='replace').strip()


def write(path, data):
    if path.exists():
        raise ValueError(f'Refusing to replace {path.name}')
    with path.open('xb') as stream:
        stream.write(data.encode() if isinstance(data, str) else data)
    path.chmod(0o600)


def private_directory(path):
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('Private state must not be a symlink')
    if os.name == 'nt':
        run(['icacls.exe', path, '/inheritance:r', '/grant:r',
             f'{getpass.getuser()}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F', '*S-1-5-32-544:(OI)(CI)F'])
    else:
        path.chmod(0o700)


def load(path):
    return json.loads((path / 'private-state.json').read_text('utf-8'))


def save(path, data):
    temp = path / 'private-state.tmp'
    with temp.open('w', encoding='utf-8') as out:
        json.dump(data, out, indent=2)
    temp.chmod(0o600)
    os.replace(temp, path / 'private-state.json')


def runtime(state):
    return Database(state['runtimeDSN'], recovery_epoch=state['epoch'])


def tls(path):
    return dict(ca_file=str(path/'ca.pem'), certificate_file=str(path/'control-cert.pem'), key_file=str(path/'control-key.pem'), timeout=5)


def provision_observation_node(conn, state):
    conn.execute('INSERT INTO inv.tenants VALUES(%s,%s) ON CONFLICT DO NOTHING',(state['tenantId'],'two-PC connection pilot'))
    conn.execute("INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch) VALUES(%s,%s,'offline',%s) ON CONFLICT DO NOTHING",(state['tenantId'],state['nodeId'],state['epoch']))
    # The tenant insert trigger creates a row with false. Pin the gate before
    # committing the new pilot; never leave its execution authority implicit.
    conn.execute('INSERT INTO inv.tenant_controls(tenant_id,kill_switch) VALUES(%s,true) ON CONFLICT(tenant_id) DO UPDATE SET kill_switch=true,version=inv.tenant_controls.version+1,updated_at=clock_timestamp()',(state['tenantId'],))


def init(args):
    path = args.state
    for value in (args.server_ip, args.node_ip):
        addr = ipaddress.ip_address(value)
        if addr.version != 4 or not addr.is_private or addr.is_loopback:
            raise ValueError('Explicit private LAN IPv4 addresses are required')
    if args.server_ip == args.node_ip:
        raise ValueError('Two distinct PCs required')
    private_directory(path)
    if (path/'private-state.json').exists():
        state = load(path)
        if (state['serverIP'], state['nodeIP']) != (args.server_ip, args.node_ip):
            raise ValueError('Existing deployment addresses differ')
        if state.get('initialized'):
            print('Existing pilot preserved; use status.')
            return
    else:
        epoch, tenant = str(uuid4()), str(uuid4())
        db_password, app_password = uuid4().hex + uuid4().hex, uuid4().hex + uuid4().hex
        state = dict(epoch=epoch, tenantId=tenant, nodeId=new_id('nod'),
                     serverIP=args.server_ip, nodeIP=args.node_ip, nodePort=18443, downloadPort=18081,
                     container='saintvision-lan-db-'+epoch[:8], dbPort=55440,
                     baseSHA=run(['git','rev-parse','HEAD'], cwd=ROOT), initialized=False)
        state['adminDSN'] = make_conninfo(host='127.0.0.1', port=55440, dbname='saintvision_lan', user='postgres', password=db_password, connect_timeout=5)
        state['runtimeDSN'] = make_conninfo(state['adminDSN'], user='inv_lan_runtime', password=app_password)
        save(path, state)
        write(path/'postgres.env', f'POSTGRES_DB=saintvision_lan\nPOSTGRES_USER=postgres\nPOSTGRES_PASSWORD={db_password}\n')
    exists = subprocess.run(['docker','container','inspect',state['container']], capture_output=True, timeout=15)
    if exists.returncode:
        image = run(['docker','image','inspect','pgvector/pgvector:pg16','--format','{{.Id}}'])
        run(['docker','run','-d','--name',state['container'],'--label','ai.saintvision.pilot='+state['epoch'],
             '--restart','unless-stopped','--pids-limit','256','--memory','512m','--cpus','1',
             '--publish','127.0.0.1:55440:5432','--env-file',path/'postgres.env',
             '--mount',f'type=volume,source={state["container"]}-data,target=/var/lib/postgresql/data', image], timeout=60)
    else:
        info = json.loads(exists.stdout)[0]
        if info['Config']['Labels'].get('ai.saintvision.pilot') != state['epoch']:
            raise ValueError('Container ownership differs')
        if not info['State']['Running']:
            run(['docker','start',state['container']])
    for attempt in range(30):
        try:
            with psycopg.connect(state['adminDSN']):
                break
        except psycopg.OperationalError:
            if attempt == 29:
                raise RuntimeError('Pilot database readiness timed out') from None
            time.sleep(1)
    from sqlalchemy.engine import URL
    info = psycopg.conninfo.conninfo_to_dict(state['adminDSN'])
    url = URL.create('postgresql+psycopg', username=info['user'], password=info['password'], host=info['host'], port=int(info['port']), database=info['dbname'])
    env = dict(os.environ, INV_MIGRATION_DSN=url.render_as_string(hide_password=False))
    print('Applying published migrations to the isolated pilot database.', flush=True)
    run([sys.executable,'-m','alembic','upgrade','head'], env=env, cwd=ROOT, timeout=120)
    with psycopg.connect(state['adminDSN']) as conn:
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname='inv_lan_runtime'").fetchone():
            password = psycopg.conninfo.conninfo_to_dict(state['runtimeDSN'])['password']
            conn.execute(sql.SQL('CREATE ROLE inv_lan_runtime LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE').format(sql.Literal(password)))
        conn.execute('GRANT inv_kernel TO inv_lan_runtime')
        prior = conn.execute('SELECT epoch FROM inv.control_epoch').fetchone()
        if prior and str(prior[0]) != state['epoch']:
            raise ValueError('Recovery epoch differs; refusing reset')
        conn.execute('INSERT INTO inv.control_epoch VALUES(true,%s) ON CONFLICT DO NOTHING',(state['epoch'],))
        provision_observation_node(conn,state)
    if not (path/'ca.pem').exists():
        ca_key, ca_cert = ca_pair()
        control_key, signing_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
        control = issue(ca_key, ca_cert, control_key.public_key(), f'spiffe://saintvision.ai/tenant/{state["tenantId"]}/control-plane/epoch/{state["epoch"]}')
        for name, data in [('ca-key.pem',private_pem(ca_key)),('control-key.pem',private_pem(control_key)),
                           ('control-cert.pem',pem(control)),('signer-key.pem',private_pem(signing_key)),
                           ('signer.pub',signing_key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)),('ca.pem',pem(ca_cert))]:
            write(path/name,data)
        policy = dict(version=1, tenantId=state['tenantId'], nodeId=state['nodeId'], recoveryEpoch=state['epoch'],
                      expiresAt=(datetime.now(timezone.utc)+timedelta(days=6)).isoformat(),clientFingerprints=[fingerprint(control)])
        write(path/'peer-policy.json',json.dumps(policy,indent=2))
    with runtime(state).transaction(state['tenantId']) as conn:
        conn.execute('SELECT node_id FROM inv.node_resource_snapshots LIMIT 0')
        if not conn.execute('SELECT kill_switch FROM inv.tenant_controls').fetchone()['kill_switch']:
            raise ValueError('Observation-only execution gate was not persisted')
    state['initialized'] = True
    save(path,state)
    print(json.dumps(dict(database='ready',scope='observation-only',nodeId=state['nodeId'],node='offline-awaiting-CSR',workloadExecution='disabled')))


def bundle(args):
    path, state = args.state, load(args.state)
    if not state['initialized']:
        raise ValueError('Initialize the pilot first')
    output = path/'public'
    output.mkdir(exist_ok=True)
    build = path/'node-build'
    build.mkdir(exist_ok=True)
    env = dict(os.environ, GOOS='linux', GOARCH='amd64', CGO_ENABLED='0')
    print('Building Linux Node binary.',flush=True)
    run([args.go,'build','-trimpath','-o',build/'inv-node','./cmd/inv-node'], cwd=ROOT/'services/node-agent', env=env, timeout=180)
    shutil.copyfile(ROOT/'deploy/lan/Dockerfile.node',build/'Dockerfile')
    tag = 'saintvision-lan-node:'+state['epoch'][:8]
    run(['docker','build','--network=none','--pull=false','-t',tag,build],timeout=120)
    image = run(['docker','image','inspect',tag,'--format','{{.Id}}'])
    # Preserve a named reference when importing into another Docker image store.
    run(['docker','save','-o',path/'node-agent.tar',tag],timeout=60)
    inspected = json.loads(run(['docker','image','inspect',image]))[0]
    state['agentImage'] = image
    save(path,state)
    manifest = {k:state[k] for k in ('tenantId','nodeId','epoch','serverIP','nodeIP','nodePort','baseSHA','agentImage')}
    manifest.update(scope='observation-only',schemaVersion=2,agentTag=tag,
                    imageLayers=inspected['RootFS']['Layers'],imageConfig=inspected['Config'])
    temporary = output/'worker.zip.tmp'
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json',json.dumps(manifest,indent=2))
        for name in ('ca.pem','signer.pub','peer-policy.json','node-agent.tar'):
            archive.write(path/name,name)
        for name in ('prepare-worker.sh','start-node.sh','finish-worker.sh','Prepare-Worker.ps1','Start-Worker.ps1','worker_config.py'):
            archive.write(ROOT/'deploy/lan'/name,name)
    os.replace(temporary,output/'worker.zip')
    digest = hashlib.sha256((output/'worker.zip').read_bytes()).hexdigest()
    (output/'worker.sha256').write_text(digest+'\n','ascii')
    print(json.dumps(dict(archive=str(output/'worker.zip'),sha256=digest,bytes=(output/'worker.zip').stat().st_size)))


def enroll(args):
    path, state = args.state, load(args.state)
    raw = args.csr.read_bytes()
    public = csr_public_key(raw,state['nodeId'])
    target = path/'public'/'node-cert.pem'
    if target.exists():
        cert = x509.load_pem_x509_certificate(target.read_bytes())
        if cert.public_key().public_bytes_raw() != public.public_bytes_raw():
            raise ValueError('Node already enrolled with a different key; explicit rotation required')
    else:
        ca = x509.load_pem_x509_certificate((path/'ca.pem').read_bytes())
        key = serialization.load_pem_private_key((path/'ca-key.pem').read_bytes(),password=None)
        cert = issue(key,ca,public,node_uri(NodePrincipal(state['tenantId'],state['nodeId']),state['epoch']),address=state['nodeIP'])
        write(target,pem(cert))
    with psycopg.connect(state['adminDSN']) as conn:
        conn.execute("SELECT set_config('inv.tenant_id',%s,true)",(state['tenantId'],))
        previous = conn.execute('SELECT certificate_sha256 FROM inv.node_channels WHERE tenant_id=%s AND node_id=%s',(state['tenantId'],state['nodeId'])).fetchone()
        if previous and previous[0] != fingerprint(cert):
            raise ValueError('Pinned channel differs; explicit rotation required')
        if not previous:
            provision_channel(conn,NodePrincipal(state['tenantId'],state['nodeId']),epoch=state['epoch'],
                              endpoint=f'https://{state["nodeIP"]}:{state["nodePort"]}',certificate_der=cert.public_bytes(serialization.Encoding.DER),expected_version=0)
    print(json.dumps(dict(enrolled=True,certificateSHA256=fingerprint(cert),fileSHA256=hashlib.sha256(target.read_bytes()).hexdigest(),node='awaiting-mTLS-observation')))


def status(args):
    state = load(args.state)
    with runtime(state).transaction(state['tenantId']) as conn:
        row = conn.execute('SELECT node_id,status,heartbeat_at FROM inv.nodes WHERE node_id=%s',(state['nodeId'],)).fetchone()
        snap = conn.execute('SELECT received_at,snapshot FROM inv.node_resource_snapshots WHERE node_id=%s',(state['nodeId'],)).fetchone()
    result = dict(database='ready',node=dict(row),observed=bool(snap),snapshot=dict(snap) if snap else None,
                  scope='observation-only',webLogin='not-configured',workloadExecution='disabled')
    print(json.dumps(result,default=str,ensure_ascii=False))


def observe(args):
    state = load(args.state)
    observer = ObservationWorker(runtime(state),NodeTLSClient(**tls(args.state)))
    while True:
        try:
            result = observer.once(state['tenantId'])
            print(json.dumps(dict(time=datetime.now(timezone.utc).isoformat(),**result)),flush=True)
        except Exception:
            print(json.dumps(dict(status='observation-unavailable')),flush=True)
        if args.once:
            return
        time.sleep(5)


def serve(args):
    state = load(args.state)
    public = args.state/'public'
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.client_address[0] not in {state['serverIP'],state['nodeIP'],'127.0.0.1'}:
                self.send_error(403)
                return
            names = {'/worker.zip':'worker.zip','/worker.sha256':'worker.sha256','/node-cert.pem':'node-cert.pem'}
            if self.path == '/healthz':
                data = b'{"service":"SaintVision LAN bootstrap","status":"ready","scope":"public-file-transfer-only"}'
            elif self.path in names and (public/names[self.path]).is_file():
                data = (public/names[self.path]).read_bytes()
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type','application/octet-stream')
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers()
            self.wfile.write(data)
        def log_message(self,*_):
            pass
        def setup(self):
            super().setup()
            self.connection.settimeout(10)
    class Server(ThreadingHTTPServer):
        slots = BoundedSemaphore(8)
        request_queue_size = 8
        def process_request(self, request, address):
            if not self.slots.acquire(blocking=False):
                request.close()
                return
            try:
                super().process_request(request, address)
            except Exception:
                self.slots.release()
                raise
        def process_request_thread(self, request, address):
            try:
                super().process_request_thread(request, address)
            finally:
                self.slots.release()
        def handle_error(self, request, address):
            pass
    server = Server((state['serverIP'],state['downloadPort']),Handler)
    server.daemon_threads = True
    print(json.dumps(dict(service='public-bootstrap',listening=f'{state["serverIP"]}:{state["downloadPort"]}')),flush=True)
    server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,required=True)
    commands = parser.add_subparsers(dest='command',required=True)
    p = commands.add_parser('init')
    p.add_argument('--server-ip',required=True)
    p.add_argument('--node-ip',required=True)
    p = commands.add_parser('bundle')
    p.add_argument('--go',required=True)
    p = commands.add_parser('enroll')
    p.add_argument('--csr',type=Path,required=True)
    commands.add_parser('status')
    p = commands.add_parser('observe')
    p.add_argument('--once',action='store_true')
    commands.add_parser('serve')
    args = parser.parse_args()
    args.state = args.state.resolve()
    try:
        globals()[args.command](args)
    except KeyboardInterrupt:
        pass
    except Exception as error:
        # Neither DSNs nor private credentials belong in console/error reporting.
        print(f'LAN {args.command} failed ({type(error).__name__}); no credentials printed.',file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
