"""Operator-only real Node component acceptance; never pretends to be user Run admission.

Permits use explicit acceptance-only claim/allocation identifiers. No browser
endpoint issues permits. This does not create product approvals, leases or Evidence.
"""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import uuid4
import zipfile
from lan_pilot import ROOT, load, runtime, tls, run, bundle as observation_bundle
from cryptography.hazmat.primitives import serialization
from inv.approvals import digest
from inv.ids import new_id
from inv.node_channels import NodeChannels
from inv.node_transport import NodeTLSClient
from inv.node_execution import seal_permit
from inv.tooling import ClaimResult, NodePrincipal
from inv.output_ingestion import output_bytes


def bundle(args):
    state=load(args.state)
    build=args.state/'execution-build'
    build.mkdir(exist_ok=True)
    env=dict(os.environ,GOOS='linux',GOARCH='amd64',CGO_ENABLED='0')
    for output,package in [('probe','./tests/probe'),('inv-supervisor','./cmd/inv-supervisor')]:
        run([args.go,'build','-trimpath','-o',build/output,package],cwd=ROOT/'services/node-agent',env=env,timeout=180)
    shutil.copyfile(ROOT/'deploy/lan/Dockerfile.probe',build/'Dockerfile')
    tag='saintvision-lan-probe:'+state['epoch'][:8]
    run(['docker','build','--pull=false','--network=none','-t',tag,build],timeout=120)
    image=json.loads(run(['docker','image','inspect',tag]))[0]
    run(['docker','save','-o',args.state/'execution-image.tar',tag],timeout=60)
    args.reuse_image=True
    observation_bundle(args)
    target=args.state/'public/worker.zip'
    tmp=target.with_suffix('.tmp')
    with zipfile.ZipFile(target) as old,zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as new:
        manifest=json.loads(old.read('manifest.json'))
        manifest['executionTest']=dict(agentTag=tag,agentImage=image['Id'],imageLayers=image['RootFS']['Layers'],imageConfig=image['Config'])
        for name in old.namelist():
            if name!='manifest.json': new.writestr(name,old.read(name))
        new.writestr('manifest.json',json.dumps(manifest,indent=2))
        new.write(args.state/'execution-image.tar','execution-image.tar')
        for name in ('worker_execution.py','Enable-ExecutionTests.ps1'):
            new.write(ROOT/'deploy/lan'/name,name)
    os.replace(tmp,target)
    sha=hashlib.sha256(target.read_bytes()).hexdigest()
    (args.state/'public/worker.sha256').write_text(sha+'\n')
    print(json.dumps(dict(sha256=sha,bytes=target.stat().st_size,scope='bounded-node-component-tests')))


def permit(state,image,mode):
    now=datetime.now(timezone.utc)
    deadline=(now+timedelta(seconds=25)).isoformat()
    argv=['/probe']+([] if mode=='isolation' else [mode])
    launch=dict(profileVersion='lan-test-v1',imageDigest=image,argv=argv,workspaceId=new_id('wsp'),
        workingDirectory='/workspace',workspaceMode='ephemeral',cpuMillis=500,memoryBytes=64*1024*1024,
        timeoutSeconds=3 if mode=='sleep' else 10,pidsLimit=64,userId=65532,network='none',
        rootfsReadOnly=True,capDropAll=True,noNewPrivileges=True,privileged=False,hostAccess=False)
    claim=dict(commandId=str(uuid4()),claimId=str(uuid4()),runId=new_id('run'),tenantId=state['tenantId'],
        projectId=new_id('prj'),nodeId=state['nodeId'],actionDigest=digest({'acceptanceMode':mode}),
        planDigest=digest(launch),policyVersion='operator-acceptance-only:1',profileVersion='lan-test-v1',
        recoveryEpoch=state['epoch'],notAfter=deadline)
    allocations=[]
    for kind,amount in [('cpu',500),('memory',64*1024*1024)]:
        allocations.append(dict(nodeId=state['nodeId'],kind=kind,lease=dict(leaseId=new_id('lse'),
            tenantId=state['tenantId'],runId=claim['runId'],resourceId=new_id('res'),amount=amount,
            fencingToken=state['epoch']+':1',grantedAt=now.isoformat(),expiresAt=deadline)))
    return ClaimResult(True,claim,launch),allocations


def context(path):
    state=load(path)
    channel=NodeChannels(runtime(state)).snapshot(NodePrincipal(state['tenantId'],state['nodeId']),observation_only=True)
    client=NodeTLSClient(**{**tls(path),'timeout':35})
    return state,channel,client


def verify_result(state,envelope,result):
    payload=json.loads(base64.b64decode(envelope['payload']))
    receipt=result['receipt']
    for key in ('tenantId','nodeId','runId','claimId','commandId','recoveryEpoch','planDigest'):
        if receipt[key]!=payload['claim'][key]: raise ValueError('Receipt identity differs')
    if result['cleanupPending'] or not receipt['stopped'] or not receipt['processStarted']:
        raise ValueError('Physical execution or cleanup is not confirmed')
    data=output_bytes(receipt) if 'output' in receipt else None
    artifact=json.loads(data) if data else {}
    stdout=base64.b64decode(artifact.get('stdout','')).decode('utf-8',errors='replace')
    stderr=base64.b64decode(artifact.get('stderr','')).decode('utf-8',errors='replace')
    return dict(receipt=receipt,stdout=stdout,stderr=stderr,outputSha256=hashlib.sha256(data).hexdigest() if data else None)


def execute(args):
    # Operator-authorized acceptance temporarily opens only the empty pilot
    # tenant's gate. Ordinary project grants and product commands stay absent.
    state=load(args.state)
    import psycopg
    lock=args.state/'acceptance.lock'
    with lock.open('x') as held:
        held.write(str(os.getpid()))
    opened=False
    try:
        with runtime(state).transaction(state['tenantId']) as conn:
            if conn.execute('SELECT count(*) AS n FROM inv.tool_claims').fetchone()['n']:
                raise ValueError('Pilot contains admitted user work; automatic test setup refused')
        with psycopg.connect(state['adminDSN']) as conn:
            row=conn.execute('UPDATE inv.tenant_controls SET kill_switch=false,version=version+1 WHERE tenant_id=%s AND kill_switch=true RETURNING version',(state['tenantId'],)).fetchone()
            if not row: raise ValueError('Pilot execution gate is already open')
        opened=True
        _execute(args)
    finally:
        if opened:
            with psycopg.connect(state['adminDSN']) as conn:
                conn.execute('UPDATE inv.tenant_controls SET kill_switch=true,version=version+1 WHERE tenant_id=%s AND kill_switch=false',(state['tenantId'],))
        lock.unlink()


def _execute(args):
    state,channel,client=context(args.state)
    key=serialization.load_pem_private_key((args.state/'signer-key.pem').read_bytes(),password=None)
    results=[]
    report=args.state/'acceptance-report.json'
    # Fixed modes only: no arbitrary command, mount, image tag or user data input.
    for mode in ('isolation','output','fail','sleep'):
        with runtime(state).transaction(state['tenantId']) as conn:
            if conn.execute('SELECT kill_switch FROM inv.tenant_controls').fetchone()['kill_switch']:
                raise ValueError('Pilot kill switch enabled during acceptance')
        channel=NodeChannels(runtime(state)).snapshot(NodePrincipal(state['tenantId'],state['nodeId']))
        claim,allocations=permit(state,args.image,mode)
        envelope=seal_permit(claim,allocations,key)
        attempt=args.state/('acceptance-'+claim.claim['commandId']+'.json')
        attempt.write_text(json.dumps(dict(mode=mode,envelope=envelope)),encoding='utf-8')
        attempt.chmod(0o600)
        started=time.monotonic()
        result=client.exchange(channel,envelope)
        elapsed=time.monotonic()-started
        verified=verify_result(state,envelope,result)
        receipt=verified['receipt']
        expected=(receipt['exitCode']==0 if mode in ('isolation','output') else receipt['exitCode']!=0)
        if mode=='fail': expected=receipt['exitCode']==7
        if mode=='sleep': expected=(receipt['reason']=='timeout' or receipt['exitCode']==124) and 2<=elapsed<15
        if mode=='output': expected=expected and verified['stdout']=='actual-node-output\n' and verified['stderr']=='actual-node-stderr\n'
        row=dict(test=mode,passed=expected,durationSeconds=round(elapsed,3),completedAt=datetime.now(timezone.utc).isoformat(),**verified)
        results.append(row)
        write_report(report,dict(scope='node-component-acceptance',nodeId=state['nodeId'],tests=results))
        print(json.dumps(dict(test=mode,passed=expected,exitCode=receipt['exitCode'],reason=receipt['reason'],outputSha256=verified['outputSha256'])),flush=True)
        if not expected: raise ValueError('Remote acceptance failed: '+mode)
    # A separate sender physically exits before committing an acceptance result.
    # Its witness is for the test assertion only; recovery uses the saved permit
    # with the observation endpoint, never the execution endpoint.
    claim,allocations=permit(state,args.image,'output')
    recovery=args.state/'receipt-recovery.json'
    recovery.write_text(json.dumps(dict(envelope=seal_permit(claim,allocations,key))),encoding='utf-8')
    recovery.chmod(0o600)
    fault=subprocess.run([sys.executable,__file__,'--state',str(args.state),'transmit-fault'],capture_output=True,timeout=40)
    if fault.returncode!=17: raise ValueError('Expected sender interruption did not occur')
    run([sys.executable,__file__,'--state',args.state,'recover'],timeout=40)
    print('Sender exited 17; a new process recovered the same receipt without execution.',flush=True)


def transmit_fault(args):
    state,_,client=context(args.state)
    channel=NodeChannels(runtime(state)).snapshot(NodePrincipal(state['tenantId'],state['nodeId']))
    saved=json.loads((args.state/'receipt-recovery.json').read_text())
    result=client.exchange(channel,saved['envelope'])
    verify_result(state,saved['envelope'],result)
    # Private test witness is never consumed to complete the recovery operation.
    witness=args.state/'receipt-fault-witness.json'
    witness.write_text(json.dumps(result['receipt']),encoding='utf-8')
    witness.chmod(0o600)
    os._exit(17)


def recover(args):
    state,channel,client=context(args.state)
    saved=json.loads((args.state/'receipt-recovery.json').read_text())
    result=client.exchange(channel,saved['envelope'],observation_only=True)
    witness=json.loads((args.state/'receipt-fault-witness.json').read_text())
    if not result['duplicate'] or result['receipt']!=witness or result['cleanupPending']:
        raise ValueError('Receipt recovery differs or would require new execution')
    report=args.state/'acceptance-report.json'
    data=json.loads(report.read_text())
    data['tests'].append(dict(test='receipt-recovery',passed=True,completedAt=datetime.now(timezone.utc).isoformat(),
        duplicate=True,sameReceipt=True,senderExitCode=17,commandId=witness['commandId'],processId=os.getpid()))
    write_report(report,data)


def write_report(path,data):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,indent=2),encoding='utf-8')
    temporary.chmod(0o600)
    os.replace(temporary,path)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,required=True)
    commands=parser.add_subparsers(dest='action',required=True)
    commands.add_parser('bundle').add_argument('--go',required=True)
    commands.add_parser('run').add_argument('--image',required=True)
    commands.add_parser('recover')
    commands.add_parser('transmit-fault')
    args=parser.parse_args()
    {'bundle':bundle,'run':execute,'recover':recover,'transmit-fault':transmit_fault}[args.action](args)
