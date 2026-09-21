"""Opt-in real LAN Workspace acceptance in a new isolated DB, or local self-test.

Does not alter the existing pilot database, execution gate, Node identity or profile.
The operator supplies the image ID verified by the worker's upgrade output.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import time
from uuid import uuid4

from lan_pilot import ROOT, load, runtime, tls, run, private_directory
from lan_pki import ca_pair,issue,pem,private_pem,fingerprint
from acceptance_evidence import case_name_drift, EXPECTED_REMOTE_WORKSPACE_CASE_NAMES
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from inv.ids import new_id
from inv.node_channels import NodeChannels
from inv.node_transport import NodeTLSClient
from inv.tooling import NodePrincipal
from psycopg.conninfo import make_conninfo


def copy_private(name, files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w') as tar:
        for filename,data in files.items():
            assert '/' not in filename and '\\' not in filename
            entry = tarfile.TarInfo(filename)
            entry.size,entry.mode,entry.uid,entry.gid = len(data),0o600,0,0
            tar.addfile(entry,io.BytesIO(data))
    result = subprocess.run(['docker','cp','-a','-',name+':/run/test'],input=stream.getvalue(),capture_output=True,timeout=30)
    if result.returncode: raise ValueError('Private test configuration copy failed')


def boundary(state):
    with runtime(state).transaction(state['tenantId']) as conn:
        gate = conn.execute('SELECT kill_switch FROM inv.tenant_controls').fetchone()['kill_switch']
        claims = conn.execute('SELECT count(*) AS n FROM inv.tool_claims').fetchone()['n']
        grants = conn.execute('SELECT count(*) AS n FROM inv.project_grants').fetchone()['n']
        leases = conn.execute('SELECT count(*) AS n FROM inv.resource_leases WHERE released_at IS NULL').fetchone()['n']
    if not gate or claims or grants or leases:
        raise ValueError('Pilot is no longer an empty, contained observation environment; automatic acceptance refused')
    return dict(killSwitch=gate,toolClaims=claims,projectGrants=grants,activeLeases=leases)


def self_node(work, network, name, agent, image):
    subnet = json.loads(run(['docker','network','inspect',network]))[0]['IPAM']['Config'][0]['Subnet']
    address = str(ipaddress.ip_network(subnet)[10])
    tenant,node,epoch = str(uuid4()),new_id('nod'),str(uuid4())
    ca_key,ca = ca_pair()
    node_key,control_key,signer = (Ed25519PrivateKey.generate() for _ in range(3))
    node_cert = issue(ca_key,ca,node_key.public_key(),f'spiffe://saintvision.ai/tenant/{tenant}/node/{node}/epoch/{epoch}',address=address)
    control = issue(ca_key,ca,control_key.public_key(),f'spiffe://saintvision.ai/tenant/{tenant}/control-plane/epoch/{epoch}')
    policy = dict(version=1,tenantId=tenant,nodeId=node,recoveryEpoch=epoch,
                  expiresAt=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),clientFingerprints=[fingerprint(control)])
    files = {'ca.pem':pem(ca),'node-cert.pem':pem(node_cert),'control-cert.pem':pem(control),
             'node-key.pem':private_pem(node_key),'control-key.pem':private_pem(control_key),
             'signer-key.pem':private_pem(signer),'signer.pub':signer.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw),
             'peer-policy.json':json.dumps(policy).encode()}
    run(['docker','volume','create','--label','ai.saintvision.remote-test='+name,name+'-node-state'])
    run(['docker','create','--name',name+'-node','--label','ai.saintvision.remote-test='+name,
         '--network',network,'--ip',address,'--read-only','--pids-limit','128','--memory','256m','--cpus','0.5',
         '--cap-drop','ALL','--security-opt','no-new-privileges',
         '--mount','type=volume,source='+name+'-node-state,target=/state',
         '--mount','type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock',agent,
         '--serve','--listen','0.0.0.0:18443','--tenant',tenant,'--node',node,'--epoch',epoch,
         '--profile','lan-workspace-v1','--image',image,'--executable','/usr/local/bin/python3',
         '--state','/state/journal','--public-key','/state/signer.pub','--tls-cert','/state/node-cert.pem',
         '--tls-key','/state/node-key.pem','--client-ca','/state/ca.pem','--peer-policy','/state/peer-policy.json'])
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w') as tar:
        for filename in ('ca.pem','node-cert.pem','node-key.pem','signer.pub','peer-policy.json'):
            data=files[filename];entry=tarfile.TarInfo(filename)
            entry.size,entry.uid,entry.gid,entry.mode=len(data),0,0,0o600
            tar.addfile(entry,io.BytesIO(data))
    copied=subprocess.run(['docker','cp','-a','-',name+'-node:/state'],input=stream.getvalue(),capture_output=True,timeout=30)
    if copied.returncode: raise ValueError('Synthetic Node configuration copy failed')
    run(['docker','start',name+'-node'])
    files.pop('node-key.pem')
    return dict(tenantId=tenant,nodeId=node,epoch=epoch,endpoint=f'https://{address}:18443'),files


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--image',required=True)
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--agent-image')
    parser.add_argument('--preflight-only',action='store_true')
    args=parser.parse_args()
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',args.image): raise ValueError('Verified worker image content ID required')
    if args.self_test == bool(args.state): raise ValueError('Choose either --state or --self-test')
    if args.preflight_only and not args.state: raise ValueError('Preflight requires an existing LAN pilot')
    if args.self_test and not args.agent_image: raise ValueError('Explicit local Node image required')
    prepared=json.loads(args.prepared.read_text('utf-8'))
    # The runtime image is reused only when the current kernel still matches it.
    for path,expected in prepared['sourceHashes'].items():
        if path.startswith(('services/control-plane/src/','src/','migrations/','contracts/')):
            if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=expected:
                raise ValueError('Prepared runtime source differs; rebuild before acceptance')
    before=None;state=None;files=None
    if args.state:
        state=load(args.state)
        before=boundary(state)
        channel=NodeChannels(runtime(state)).snapshot(NodePrincipal(state['tenantId'],state['nodeId']),observation_only=True)
        probe=NodeTLSClient(**tls(args.state)).resource_snapshot(channel,{'nonce':uuid4().hex+uuid4().hex})
        if probe['profileVersion']!='lan-workspace-v1':
            print(json.dumps({'ready':False,'nodeId':state['nodeId'],'profile':probe['profileVersion'],'required':'lan-workspace-v1','executed':False}))
            return 2
        if args.preflight_only:
            print(json.dumps({'ready':True,'nodeId':state['nodeId'],'profile':probe['profileVersion'],'executed':False,'operatingBoundary':before}))
            return 0
        config={k:state[k] for k in ('tenantId','nodeId','epoch')};config['endpoint']=channel.endpoint
        files={f:(args.state/f).read_bytes() for f in ('ca.pem','control-cert.pem','control-key.pem','signer-key.pem')}
        files['node-cert.pem']=(args.state/'public/node-cert.pem').read_bytes()
    name='sv-remote-workspace-'+uuid4().hex[:12]
    work=ROOT/'.work'/name;private_directory(work)
    network=name+'-net'
    run(['docker','network','create','--label','ai.saintvision.remote-test='+name,network])
    if args.self_test:
        # Docker 20.10 permits static container addresses only on explicitly
        # configured subnets. Reserve a free range, then recreate this EMPTY,
        # uniquely owned network with that same range explicitly configured.
        allocation=json.loads(run(['docker','network','inspect',network]))[0]
        if allocation['Labels'].get('ai.saintvision.remote-test')!=name or allocation['Containers']:
            raise ValueError('New self-test network changed before subnet pinning')
        subnet=allocation['IPAM']['Config'][0]['Subnet']
        run(['docker','network','rm',network])
        run(['docker','network','create','--label','ai.saintvision.remote-test='+name,'--subnet',subnet,network])
        config,files=self_node(work,network,name,args.agent_image,args.image)
    config.update(image=args.image,scope='local-self-test-real-docker-not-two-pcs' if args.self_test else 'two-physical-pcs-isolated-test-db-synthetic-identity')
    dbpassword=uuid4().hex+uuid4().hex
    envpath=work/'postgres.env'
    envpath.write_text('POSTGRES_USER=postgres\nPOSTGRES_DB=workspace_acceptance\nPOSTGRES_PASSWORD='+dbpassword+'\n',encoding='utf-8')
    run(['docker','volume','create','--label','ai.saintvision.remote-test='+name,name+'-db-data'])
    run(['docker','run','-d','--name',name+'-db','--label','ai.saintvision.remote-test='+name,
         '--network',network,'--pids-limit','128','--memory','256m','--cpus','1','--env-file',envpath,
         '--mount','type=volume,source='+name+'-db-data,target=/var/lib/postgresql/data',prepared['postgresImage']])
    for _ in range(30):
        ready=subprocess.run(['docker','exec',name+'-db','pg_isready','-U','postgres','-d','workspace_acceptance'],capture_output=True,timeout=5)
        if ready.returncode==0: break
        time.sleep(0.5)
    else: raise ValueError('Private acceptance database did not become ready')
    config['adminDSN']=make_conninfo(host=name+'-db',port=5432,dbname='workspace_acceptance',user='postgres',password=dbpassword,connect_timeout=5)
    (work/'private-config.json').write_text(json.dumps(config),encoding='utf-8')
    run(['docker','create','--name',name+'-runner','--label','ai.saintvision.remote-test='+name,'--network',network,
         '--pids-limit','256','--memory','512m','--cpus','1','--entrypoint','python',prepared['kernelImage'],'/app/tools/remote_workspace_entry.py'])
    run(['docker','cp',ROOT/'tools/remote_workspace_entry.py',name+'-runner:/app/tools/remote_workspace_entry.py'])
    copy_private(name+'-runner',{**files,'config.json':json.dumps(config).encode()})
    print(json.dumps({'started':name,'scope':config['scope'],'nodeId':config['nodeId'],'privateState':str(work)}),flush=True)
    completed=False
    try:
        result=subprocess.run(['docker','start','-a',name+'-runner'],capture_output=True,timeout=300)
        (work/'runner.log').write_bytes(result.stdout+result.stderr)
        run(['docker','cp',name+'-runner:/evidence',work/'evidence'],timeout=30)
        report=json.loads((work/'evidence/remote-report.json').read_text())
        case_drift=case_name_drift(EXPECTED_REMOTE_WORKSPACE_CASE_NAMES,
                                   (t.get('test') for t in report['tests']))
        completed=(result.returncode==0 and report['passed']
                   and case_drift=={'missing':[],'unexpected':[],'duplicates':[]}
                   and all(t['passed'] and t['activeLeases']==0 for t in report['tests']))
        public=dict(at=datetime.now(timezone.utc).isoformat(),codeSHA=run(['git','rev-parse','HEAD'],cwd=ROOT),
                    dirty=bool(run(['git','status','--porcelain'],cwd=ROOT)),runtimeImageCodeSHA=prepared['codeSHA'],
                    entrySHA256=hashlib.sha256((ROOT/'tools/remote_workspace_entry.py').read_bytes()).hexdigest(),
                    operatingBefore=before,operatingAfter=boundary(state) if state else None,
                    exitCode=result.returncode,passed=completed,caseNameDrift=case_drift,report=report)
        (work/'result.json').write_text(json.dumps(public,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'passed':completed,'cases':len(report['tests']),'evidence':str(work/'result.json'),'scope':config['scope']}),flush=True)
        return 0 if completed else 1
    finally:
        # Preserve DB, objects and Node journals for investigation if completion
        # is uncertain. No existing Node, database, key or volume is reset.
        if completed:
            for suffix in ('-runner','-db')+ (('-node',) if args.self_test else ()):
                value=json.loads(run(['docker','inspect',name+suffix]))[0]
                if value['Config']['Labels'].get('ai.saintvision.remote-test')!=name:
                    raise ValueError('Acceptance container ownership changed')
                if value['State']['Running']:run(['docker','stop',name+suffix])
        else:
            print('Acceptance incomplete; owned database and evidence preserved for observation-only recovery.',flush=True)


if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as error:
        print('Remote Workspace check stopped ('+type(error).__name__+'); no credentials printed.',file=sys.stderr)
        raise SystemExit(1)
