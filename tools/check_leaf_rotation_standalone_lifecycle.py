"""CI-only installed CLI interoperability using synthetic Docker/floor fixtures.

This never claims actual Go/Docker acceptance; the native and provisioned Core
lanes must independently supply it. All keys/state here belong to a temp fixture.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
WORKER=ROOT/'deploy/lan/worker_leaf_rotation.py'
LAUNCHER=ROOT/'deploy/lan/leaf_rotation_standalone_runtime.py'

FAKE_DOCKER=r'''#!/usr/bin/env python3
import io,json,os,sys,tarfile,hashlib
from pathlib import Path
from datetime import datetime,timezone
from cryptography import x509
from cryptography.hazmat.primitives import serialization
root=Path(os.environ['INV_FAKE_DOCKER_STATE'])
meta=json.loads((root/'meta.json').read_bytes());args=sys.argv[1:]
canonical=lambda v:json.dumps(v,sort_keys=True,separators=(',',':')).encode()
sha=lambda raw:hashlib.sha256(raw).hexdigest()
name='saintvision-'+meta['nodeId'].lower();cid=meta['cid']
def status():return json.loads((root/'status.json').read_bytes())
def put(value):(root/'status.json').write_bytes(canonical(value))
def inspected():
 s=status()
 return dict(Id=cid,Name='/'+name,Image=meta['image'],Config=meta['config'],HostConfig=meta['host'],Mounts=meta['mounts'],
  State=dict(Running=s['running'],Restarting=False,Status='running' if s['running'] else 'exited',StartedAt='fixture-'+str(s['count'])),RestartCount=s['count'])
if args[:2]==['container','inspect'] and args[2] in (name,cid):print(json.dumps([inspected()]));sys.exit(0)
if args[:2]==['volume','inspect'] and args[2]==name+'-state':print(json.dumps([meta['volume']]));sys.exit(0)
if args[:2]==['ps','-aq']:print(cid);sys.exit(0)
if args[:2]==['inspect','--format']:
 s=status();print(('true' if s['running'] else 'false')+' false '+str(s['count']));sys.exit(0)
if len(args)==2 and args[0] in ('stop','start') and args[1]==cid:
 s=status()
 if args[0]=='stop':s['running']=False
 else:
  raw=(root/'peer-policy.json').read_bytes();p=json.loads(raw)
  if p['version']<s['version'] or (p['version']==s['version'] and sha(raw)!=s['hash']):sys.exit(3)
  s.update(running=True,count=s['count']+1,version=p['version'],hash=sha(raw))
 put(s);print(cid);sys.exit(0)
if args[:3]==['cp','-a','-'] and args[3] in (name+':/state',cid+':/state'):
 with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:') as archive:
  for entry in archive:
   if not entry.isfile() or '/' in entry.name or '\\' in entry.name:sys.exit(4)
   (root/entry.name).write_bytes(archive.extractfile(entry).read())
 sys.exit(0)
if len(args)==3 and args[0]=='cp' and args[2]=='-':
 filename=args[1].rsplit('/',1)[-1];raw=(root/filename).read_bytes();data=io.BytesIO()
 with tarfile.open(fileobj=data,mode='w') as archive:
  entry=tarfile.TarInfo(filename);entry.uid=entry.gid=0;entry.mode=0o600;entry.size=len(raw);archive.addfile(entry,io.BytesIO(raw))
 sys.stdout.buffer.write(data.getvalue());sys.exit(0)
if args[:3]==['exec',cid,'/inv-node'] and args[3]=='--observe-peer-policy-floor':
 s=status();raw=(root/'peer-policy.json').read_bytes();p=json.loads(raw)
 if not s['running'] or (s['version'],s['hash'])!=(p['version'],sha(raw)):sys.exit(5)
 cert=x509.load_pem_x509_certificate((root/'node-cert.pem').read_bytes())
 key=serialization.load_pem_private_key((root/'node-key.pem').read_bytes(),password=None)
 value=dict(schemaVersion='saintvision-node-peer-policy-floor:2',tenantId=meta['tenantId'],nodeId=meta['nodeId'],recoveryEpoch=meta['epoch'],
  nonce=args[args.index('--peer-floor-nonce')+1],observedAt=int(datetime.now(timezone.utc).timestamp()),
  certificateDER_SHA256=sha(cert.public_bytes(serialization.Encoding.DER)),peerPolicyVersion=s['version'],peerPolicySHA256=s['hash'],
  floorSHA256=sha(canonical(dict(Version=s['version'],Hash=s['hash']))),journalIdentitySHA256=sha(canonical(dict(Tenant=meta['tenantId'],Node=meta['nodeId'],Epoch=meta['epoch']))),
  journalUID=0,servingPID=1,servingProcessSHA256=sha(b'SYNTHETIC CLI ARGV'),servingExecutableSHA256=sha(b'SYNTHETIC UNIT EXECUTABLE BYTES'),plainServingProcess=True)
 value['nodeSignature']=key.sign(b'saintvision/node-peer-policy-floor/v2\x00'+canonical(value)).hex()
 print(json.dumps(value));sys.exit(0)
sys.exit(2)
'''


def _run(runtime,arguments,env,*,rejected=False):
    value=subprocess.run([sys.executable,'-I','-B',str(LAUNCHER),'run','--runtime-dir',str(runtime),
                          '--worker-script',str(WORKER),'--',*map(str,arguments)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=90)
    if rejected:
        if value.returncode==0:raise RuntimeError('Standalone unsafe operation was accepted')
        return None
    if value.returncode:raise RuntimeError('Standalone CLI failed closed: '+value.stderr[-500:])
    return json.loads(value.stdout.splitlines()[-1])


def validate_result(value):
    expected=dict(schemaVersion='saintvision-leaf-rotation-standalone-lifecycle:3',fixtureOnly=True,actualGoAcceptanceAssessed=False,
                  completedNormalCycles=2,installRestartReceipt=True,finalized=True,finalizedAttestationVerified=True,
                  rollbackRejected=True,rolledBack=False,restartCount=4,bytecodeCacheCount=0)
    if set(value)!=set(expected) or any(type(value[k]) is not type(v) or value[k]!=v for k,v in expected.items()):
        raise ValueError('Standalone versioned result differs')
    return value


def main():
    parser=argparse.ArgumentParser(allow_abbrev=False);parser.add_argument('--runtime-dir',type=Path,required=True);args=parser.parse_args()
    if sys.platform!='linux' or os.environ.get('GITHUB_ACTIONS')!='true':
        raise ValueError('Installed CLI fixture PKI proof is restricted to isolated Linux CI')
    sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools'),str(ROOT/'deploy/lan')]
    from test_lan_leaf_rotation import _fixture
    from cryptography import x509
    import lan_pilot
    import peer_policy_phase as phase
    import worker_leaf_rotation as worker
    with tempfile.TemporaryDirectory(prefix='leaf-runtime-v3-fixture-') as value:
        temporary=Path(value);fixture=_fixture(temporary/'fixture',now=datetime.now(timezone.utc).replace(microsecond=0))
        daemon=temporary/'synthetic-daemon';daemon.mkdir(mode=0o700)
        for name in ('ca.pem','node-key.pem','node-cert.pem','signer.pub','peer-policy.json'):
            (daemon/name).write_bytes((fixture.worker/name).read_bytes())
        node,tenant,epoch=fixture.manifest['nodeId'],fixture.manifest['tenantId'],fixture.manifest['recoveryEpoch']
        image='sha256:'+'a'*64;cid=hashlib.sha256(str(daemon).encode()).hexdigest();name='saintvision-'+node.lower()
        cmd=['--serve','--listen','0.0.0.0:18443','--tenant',tenant,'--node',node,'--epoch',epoch,'--profile','lan-observe-v1','--image',image,'--executable','/inv-node',
             '--state','/state/journal','--public-key','/state/signer.pub','--tls-cert','/state/node-cert.pem','--tls-key','/state/node-key.pem','--client-ca','/state/ca.pem','--peer-policy','/state/peer-policy.json']
        meta=dict(nodeId=node,tenantId=tenant,epoch=epoch,cid=cid,image=image,
                  config=dict(User='',Cmd=cmd,Labels={'ai.saintvision.node':node}),host=dict(ReadonlyRootfs=True,Privileged=False,RestartPolicy={'Name':'unless-stopped'}),
                  mounts=[dict(Type='volume',Name=name+'-state',Source='/fixture/owned',Destination='/state',RW=True,Propagation='')],
                  volume=dict(Name=name+'-state',Labels={'ai.saintvision.node':node},Driver='local'))
        (daemon/'meta.json').write_bytes(phase.canonical(meta));initial=(daemon/'peer-policy.json').read_bytes()
        (daemon/'status.json').write_bytes(phase.canonical(dict(running=True,count=0,version=7,hash=phase.digest(initial))))
        (fixture.worker/'manifest.json').write_bytes(phase.canonical(dict(nodeId=node,tenantId=tenant,epoch=epoch,serverIP='127.0.0.2',nodeIP=fixture.manifest['nodeIP'],nodePort=18443)))
        fake_bin=temporary/'bin';fake_bin.mkdir();(fake_bin/'docker').write_text(FAKE_DOCKER,encoding='utf-8');(fake_bin/'docker').chmod(0o700)
        env={**os.environ,'PATH':str(fake_bin)+os.pathsep+os.environ.get('PATH',''),'INV_FAKE_DOCKER_STATE':str(daemon)}
        current_control=fixture.current_control;archives={}
        for cycle in (1,2):
            if cycle==2:time.sleep(1.05)
            observed=_run(args.runtime_dir,['observe-floor','--worker-root',fixture.worker,'--nonce',os.urandom(32).hex()],env)
            bundle=temporary/('normal-cycle-'+str(cycle))
            raw,manifest,_files=lan_pilot._write_rotation_public_material(bundle,state={'tenantId':tenant,'epoch':epoch},node={'nodeId':node,'nodeIP':fixture.manifest['nodeIP']},
                current_node=x509.load_pem_x509_certificate((fixture.worker/'node-cert.pem').read_bytes()),current_control=current_control,
                control_key=fixture.control_key,public_key=fixture.node_key.public_key(),ca_key=fixture.issuer_key,intermediate=fixture.issuer,chain_raw=fixture.chain,
                revocations=set(),now=datetime.now(timezone.utc),current_version=6+cycle,overlap_seconds=3600,leaf_valid_seconds=21600,rotation_id=('a' if cycle==1 else 'b')*32,
                peer_floor_observation=observed,peer_floor_nonce=observed['nonce'],current_policy_raw=(fixture.worker/'peer-policy.json').read_bytes(),current_node_raw=(fixture.worker/'node-cert.pem').read_bytes())
            receipt=_run(args.runtime_dir,['install','--bundle',bundle,'--worker-root',fixture.worker],env)
            assert receipt['restartObserved'] is True and receipt['postPeerFloor']['peerPolicyVersion']==manifest['overlapPeerPolicyVersion']
            before={str(p.relative_to(fixture.worker)):p.read_bytes() for p in fixture.worker.rglob('*') if p.is_file()}
            daemon_before={p.name:p.read_bytes() for p in daemon.iterdir()}
            _run(args.runtime_dir,['rollback','--bundle',bundle,'--worker-root',fixture.worker],env,rejected=True)
            assert before=={str(p.relative_to(fixture.worker)):p.read_bytes() for p in fixture.worker.rglob('*') if p.is_file()}
            assert daemon_before=={p.name:p.read_bytes() for p in daemon.iterdir()}
            body=phase.commit_body(manifest,raw);commit=temporary/f'commit-{cycle}.json'
            commit.write_bytes(phase.canonical({**body,'controlSignature':fixture.control_key.sign(worker._canonical(body)).hex()}))
            final=_run(args.runtime_dir,['finalize','--bundle',bundle,'--worker-root',fixture.worker,'--commit-receipt',commit],env)
            assert final['finalized'] is True and final['finalPeerPolicyVersion']==7+cycle*2
            files={name:(bundle/name).read_bytes() for name in worker.file_names(manifest)}
            attestation=_run(args.runtime_dir,['attest-finalized','--bundle',bundle,'--worker-root',fixture.worker],env)
            worker.verify_finalized_attestation(attestation,raw,files)
            for archived,body in archives.items():assert archived.read_bytes()==body
            archive=fixture.worker/'leaf-rotation-finalized'/(manifest['rotationId']+'.json');archives[archive]=archive.read_bytes()
            current_control=x509.load_pem_x509_certificate(files['control-cert.pem'])
        result=validate_result(dict(schemaVersion='saintvision-leaf-rotation-standalone-lifecycle:3',fixtureOnly=True,actualGoAcceptanceAssessed=False,
            completedNormalCycles=2,installRestartReceipt=True,finalized=True,finalizedAttestationVerified=True,rollbackRejected=True,rolledBack=False,
            restartCount=json.loads((daemon/'status.json').read_bytes())['count'],bytecodeCacheCount=len(list(args.runtime_dir.rglob('__pycache__')))))
        print(json.dumps(result,sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
