"""Hosted-only REAL Linux/Docker/Go/retained-key candidate proof, never live recovery.

All private fixture keys remain in a disposable directory excluded from artifacts.
Node keys are generated inside their own mount; CP receives public CSR only.
"""
from dataclasses import replace
import base64
import fcntl
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/control-plane/src'))
from inv import proposed_expired_policy_recovery as r
from recovery_candidate_fixture import Fixture
from cryptography import x509
from cryptography.hazmat.primitives import serialization

OUT=ROOT/'dist/expired-policy-candidate'
REPORT={'schema':'sv-expired-policy-hosted-proof:1','sourceSHA':os.environ.get('GITHUB_SHA'),'candidateOnly':True,'activationAllowed':False,'cycles':[],'negativeControls':[],'productionIntegration':'NOT_RUN','productionBudgets':None}
CONTAINERS=[]


def command(args,**kwargs):
    result=subprocess.run(args,capture_output=True,timeout=90,**kwargs)
    if result.returncode:
        raise RuntimeError(f'owned fixture command failed: {args[0:3]} exit={result.returncode} {result.stderr.decode()[-1500:]}')
    return result.stdout


def write(path,raw):
    path.write_bytes(raw); path.chmod(0o600); os.chown(path,1000,1000)


def line(process):
    selector=selectors.DefaultSelector(); selector.register(process.stdout,selectors.EVENT_READ)
    if not selector.select(20):
        raise RuntimeError('actual Go output deadline')
    raw=process.stdout.readline()
    if not raw:
        raise RuntimeError('actual Go process closed before proof: '+process.stderr.read().decode()[-500:])
    return json.loads(raw)


def proof_args(f,auth,node):
    return ['/custody-proof','--candidate-custody-proof-only','--request','/trust/request.json','--node',node,'--tenant',f.tenant,'--epoch',f.epoch,'--members-digest',r.sha(r.canonical(auth['members'])),'--authorizer-sha256',r.sha(f.authorizer.public_key().public_bytes_raw()),'--operator-sha256',r.sha(f.operator.public_key().public_bytes_raw()),'--helper-sha256',f.trust.helper_sha256]


def failure(name,cid,args,expected,extra=()):
    result=subprocess.run(['docker','exec',*extra,cid,*args],capture_output=True,timeout=15)
    payload=json.loads(result.stdout)
    assert result.returncode==1 and payload=={'error':expected,'activationAllowed':False}, (name,result.returncode,payload)
    REPORT['negativeControls'].append({'name':name,'exit':result.returncode,'typedError':expected})


def main():
    assert sys.platform=='linux' and os.environ.get('GITHUB_ACTIONS')=='true' and os.geteuid()==0, 'hosted owned fixture only'
    OUT.mkdir(parents=True,exist_ok=True)
    binaries=ROOT/'dist/expired-policy-binaries'
    image='sv-expired-policy-candidate:'+os.environ['GITHUB_SHA']
    build=Path(tempfile.mkdtemp(prefix='sv-recovery-build-'))
    shutil.copyfile(binaries/'custody-proof',build/'custody-proof'); shutil.copyfile(binaries/'fixture-key',build/'fixture-key')
    for p in build.iterdir(): p.chmod(0o555)
    (build/'Dockerfile').write_text('FROM scratch\nCOPY --chown=1000:1000 custody-proof /custody-proof\nCOPY --chown=1000:1000 fixture-key /fixture-key\nUSER 1000:1000\nENTRYPOINT ["/fixture-key","--isolated-fixture-hold"]\n')
    command(['docker','build','--network=none','--pull=false','-t',image,str(build)])
    image_id=command(['docker','image','inspect','--format','{{.Id}}',image]).decode().strip().removeprefix('sha256:')
    REPORT.update(imageId=image_id,helperSHA256=r.sha((build/'custody-proof').read_bytes()),runner='GitHub ubuntu-latest Linux; root fixture supervisor; UID1000 child containers; no network/capabilities/privileges',realCrypto='Ed25519 retained Node keys, separate CA/TLS/recovery/operator actors')
    with tempfile.TemporaryDirectory(prefix='sv-expired-policy-fixture-') as temp:
        scope=Path(temp); nodes={}; public={}
        # Bootstrap isolated Node keys locally in each Node mount, not at CP.
        for i in range(3):
            node=f'candidate_node_{i}'; base=scope/node; base.mkdir(mode=0o755)
            paths={k:base/k for k in ['config','state','custody','trust']}
            for p in paths.values(): p.mkdir(mode=0o700); os.chown(p,1000,1000)
            output=command(['docker','run','--rm','--network=none','--user','1000:1000','--read-only','--cap-drop=ALL','--security-opt','no-new-privileges','--mount',f'type=bind,src={paths["config"]},dst=/config', '--entrypoint','/fixture-key',image,'--isolated-fixture-keygen'])
            csr=x509.load_der_x509_csr(base64.b64decode(json.loads(output)['csr']))
            assert csr.is_signature_valid
            public[node]=csr.public_key(); nodes[node]={'paths':paths}
        f=Fixture(public); f.trust=replace(f.trust,helper_sha256=REPORT['helperSHA256'])
        for node,item in nodes.items():
            paths=item['paths']
            for name,raw in {'node-cert.pem':f.certs[node].public_bytes(serialization.Encoding.PEM),'client-ca.pem':f.ca.public_bytes(serialization.Encoding.PEM),'launch-signer.pub':f.operator.public_key().public_bytes_raw()}.items(): write(paths['config']/name,raw)
            for name,key in [('authorizer.pub',f.authorizer),('operator.pub',f.operator)]: write(paths['trust']/name,key.public_key().public_bytes_raw())
            write(paths['state']/'identity.json',r.canonical({'Tenant':f.tenant,'Node':node,'Epoch':f.epoch}))
            for folder in ['state','custody']: write(paths[folder]/'.lock',b'')
            args=['docker','run','-d','--network=none','--user','1000:1000','--read-only','--cap-drop=ALL','--security-opt','no-new-privileges','--pids-limit','32','--memory','128m']
            for kind,path in paths.items(): args+=['--mount',f'type=bind,src={path},dst=/{kind}'+(',readonly' if kind in {'config','trust'} else '')]
            cid=command([*args,image]).decode().strip(); CONTAINERS.append(cid); item['cid']=cid
        ledger=r.CandidateLedger.create_reference(scope/'reference.sqlite',f.trust,{n:(f.c[i],f.p[i]) for i,n in enumerate(sorted(nodes))})
        for cycle in [1,2]:
            # Cycle 2 advances ONLY the isolated fixture's public policy/floor
            # inputs after the previous reference CAS, NOT a production adapter.
            members=[]
            for i,(node,item) in enumerate(sorted(nodes.items())):
                paths=item['paths']; expiry=int(time.time())-60
                policy=r.canonical({'version':f.p[i],'tenantId':f.tenant,'nodeId':node,'recoveryEpoch':f.epoch,'expiresAt':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(expiry)),'clientFingerprints':[r.sha(f.trust.cp_der)]})
                write(paths['config']/'peer-policy.json',policy)
                write(paths['state']/'.peer-policy',r.canonical({'Version':f.p[i],'Hash':r.sha(policy)}))
                config={name:r.sha((paths['config']/name).read_bytes()) for name in ['node-cert.pem','client-ca.pem','launch-signer.pub','peer-policy.json']}
                members.append(dict(nodeId=node,ip=f.trust.nodes[node].ip,nodeFingerprint=r.sha(f.trust.nodes[node].certificate_der),priorC=f.c[i],targetC=f.c[i]+1,priorP=f.p[i],targetP=f.p[i]+1,floorSHA256=r.sha((paths['state']/'.peer-policy').read_bytes()),identitySHA256=r.sha((paths['state']/'identity.json').read_bytes()),policySHA256=r.sha(policy),configDigest=r.sha(r.canonical(config)),previousCheckpoint=f.prior[node],priorPolicyExpiresAt=expiry))
            auth,env=f.authorization(cycle,members); requests={}; proofs={}; processes={}; records={}
            originals={n:{p.name:r.sha(p.read_bytes()) for p in x['paths']['state'].iterdir()} for n,x in nodes.items()}
            for node,item in nodes.items():
                st=(item['paths']['state']/'.lock').stat()
                requests[node]=f.request(auth,env,node,(st.st_dev,st.st_ino),image_id,item['cid'])
                write(item['paths']['trust']/'request.json',requests[node])
                args=proof_args(f,auth,node)
                if cycle==1:
                    failure('default-deny-entry',item['cid'],['/custody-proof'],'RECOVERY_HOLD_UNBOUND')
                    failure('wrong-uid',item['cid'],args,'RECOVERY_HOLD_UID',extra=('--user','0:0'))
                    failure('wrong-helper-digest',item['cid'],args[:-1]+['0'*64],'RECOVERY_HELPER_PROVENANCE')
                    request_path=item['paths']['trust']/'request.json'
                    bad=r.parse(requests[node]); bad['authorization']['signature']='0'*128
                    write(request_path,r.canonical(bad))
                    failure('bad-authorization-signature',item['cid'],args,'RECOVERY_SIGNATURE')
                    write(request_path,requests[node])
                    floor_path=item['paths']['state']/'.peer-policy'; floor_original=floor_path.read_bytes()
                    write(floor_path,r.canonical({'Version':999,'Hash':'0'*64}))
                    failure('authenticated-journal-floor-mismatch',item['cid'],args,'RECOVERY_AUTHENTICATED_FLOOR')
                    write(floor_path,floor_original)
                    # Real expired certificates signed by this isolated CA,
                    # retaining the same public key: no fake parser or clock.
                    from recovery_candidate_fixture import certificate
                    cert_path=item['paths']['config']/'node-cert.pem'; cert_original=cert_path.read_bytes()
                    expired=certificate(public[node],f.ca_key,f.ca,uri=f'spiffe://saintvision.ai/tenant/{f.tenant}/node/{node}/epoch/{f.epoch}',ip=f.trust.nodes[node].ip,expiry=-1)
                    write(cert_path,expired.public_bytes(serialization.Encoding.PEM))
                    failure('real-expired-node-leaf',item['cid'],args,'RECOVERY_TERMINAL_LEAF_EXPIRED')
                    write(cert_path,cert_original)
                    ca_path=item['paths']['config']/'client-ca.pem'; ca_original=ca_path.read_bytes()
                    expired_ca=certificate(f.ca_key.public_key(),f.ca_key,None,ca_cert=True,expiry=-1)
                    write(ca_path,expired_ca.public_bytes(serialization.Encoding.PEM))
                    failure('real-expired-ca',item['cid'],args,'RECOVERY_TERMINAL_CA_EXPIRED')
                    write(ca_path,ca_original)
                    mount_args=['docker','run','--rm','--network=none','--user','1000:1000','--read-only','--cap-drop=ALL','--security-opt','no-new-privileges']
                    for kind,path in item['paths'].items():
                        mount_args+=['--mount',f'type=bind,src={path},dst=/{kind}'+(',readonly' if kind in {'config','trust','state'} else '')]
                    wrong_mount=subprocess.run([*mount_args,'--entrypoint','/custody-proof',image,*args[1:]],capture_output=True,timeout=15)
                    assert wrong_mount.returncode==1 and json.loads(wrong_mount.stdout)['error']=='RECOVERY_HOLD_MOUNT_UID_MODE'
                    REPORT['negativeControls'].append({'name':'read-only-state-mount','exit':1,'typedError':'RECOVERY_HOLD_MOUNT_UID_MODE'})
                process=subprocess.Popen(['docker','exec','-i',item['cid'],*args],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                processes[node]=process; response=line(process)
                assert response['kind']=='nonserving-custody-proof', response
                proofs[node]=response['proof']
                # The unchanged ordinary M2 verifier rejects the actual Go
                # candidate output; this proof can never stand in for live M2.
                sys.path.insert(0,str(ROOT/'deploy/lan'))
                import peer_policy_phase
                candidate_body,_=r.verify(response['proof'],r.PROOF,public[node])
                try:
                    peer_policy_phase.verify_floor(candidate_body,f.certs[node].public_bytes(serialization.Encoding.PEM),{'tenantId':f.tenant,'nodeId':node,'epoch':f.epoch})
                except ValueError as error:
                    assert str(error)=='Actual Node floor observation shape differs'
                else:
                    raise AssertionError('non-serving candidate accepted as ordinary live M2')
                failure('exclusive-journal-lock-held',item['cid'],args,'RECOVERY_HOLD_EXCLUSIVE_CUSTODY')
            ledger.prepare(env,requests,proofs)
            acks=r.checkpoint_requests(env,requests,proofs,f.trust,f.authorizer)
            for node,process in processes.items():
                process.stdin.write(r.canonical(acks[node])+b'\n'); process.stdin.flush(); process.stdin.close()
                result=line(process); assert process.wait(15)==0 and result['kind']=='candidate-checkpoint-complete-lock-released-after-return',result
                records[node]=result['record']
            receipt=ledger.commit_reference(env,requests,proofs,acks,records)
            assert ledger.commit_reference(env,requests,proofs,acks,records)==receipt
            for node,item in nodes.items():
                assert originals[node]=={p.name:r.sha(p.read_bytes()) for p in item['paths']['state'].iterdir()},'candidate mutated original journal'
                name=f'{cycle:08d}-{auth["operation"]}.json'
                raw=(item['paths']['custody']/name).read_bytes(); assert raw==r.canonical(records[node])
                f.prior[node]=r.sha(raw)
                replay=json.loads(command(['docker','exec',item['cid'],*proof_args(f,auth,node)]))
                assert replay=={'kind':'completed-candidate-checkpoint-replay','record':records[node]}
                f.c[sorted(nodes).index(node)]+=1; f.p[sorted(nodes).index(node)]+=1
            REPORT['cycles'].append({'cycle':cycle,'memberCount':3,'actualGoNodeSignatures':3,'actualDurableNodeCheckpoints':3,'referenceCASAuditRows':3,'P':list(f.p),'C':list(f.c),'receipt':receipt,'durableRecordHashes':dict(f.prior),'freshContexts':'all five sites explicitly absent in isolated fixture; production unknown'})
        # Host-held actual journal lock and foreign residue are independently
        # enforced by the executable, not mocked filesystem results.
        node=next(iter(nodes)); item=nodes[node]; args=proof_args(f,auth,node)
        with (item['paths']['state']/'.lock').open('rb') as held:
            fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
            failure('host-held-same-inode-lock',item['cid'],args,'RECOVERY_HOLD_EXCLUSIVE_CUSTODY')
        write(item['paths']['custody']/'partial.next',b'partial')
        failure('partial-write-foreign-residue',item['cid'],args,'RECOVERY_HOLD_FOREIGN_RESIDUE')
        (item['paths']['custody']/'partial.next').unlink() # exact owned fixture file
        policy=item['paths']['config']/'peer-policy.json'; original=policy.read_bytes()
        policy.unlink(); policy.symlink_to('/trust/request.json')
        failure('symlink-config',item['cid'],args,'RECOVERY_HOLD_FILE')
        policy.unlink(); write(policy,original)
        policy.unlink(); os.link(item['paths']['config']/'node-cert.pem',policy)
        failure('hardlink-config',item['cid'],args,'RECOVERY_HOLD_FILE_METADATA')
        policy.unlink(); write(policy,original)
        write(item['paths']['state']/'foreign-job.json',b'{}')
        failure('unknown-journal-residue',item['cid'],args,'RECOVERY_HOLD_ACTIVE_OR_UNKNOWN_JOURNAL')
        (item['paths']['state']/'foreign-job.json').unlink()
        with ledger.connect() as db:
            assert db.execute('SELECT COUNT(*) FROM audit').fetchone()[0]==6
        try: ledger.activate()
        except r.Refusal as error: assert error.code=='RECOVERY_HOLD_INTEGRATION_NOT_BOUND'
        else: raise AssertionError('candidate enabled activation')
        REPORT['status']='CANDIDATE_COMPONENT_PROOF_PASSED_KEEP_INTEGRATION_HOLD'
        REPORT['P1toP7']={'P1':'candidate-only isolated signatures/locks/schema; current-profile serving M2 NOT_RUN','P2':'actual Linux UID1000 ROconfig/RWstate/checkpoint links; production publication NOT_RUN','P3':'singleCA valid leaf/public constraints tested, production private reattestation NOT_RUN','P4':'two real three-member candidate cycles; normal/live migration cycles NOT_RUN','P5':'reference CAS/unknown retry tested; production DB/transport NOT_RUN','P6':'all five context inventory gate tested; actual deployed instance inventory/switch NOT_RUN','P7':'review/release/migration budget/B_Rpolicy/live recovery NOT_RUN'}


if __name__=='__main__':
    try:
        main()
    except BaseException as error:
        REPORT['status']='FAILED'; REPORT['failureType']=type(error).__name__; REPORT['failure']=str(error)
        raise
    finally:
        for cid in CONTAINERS:
            subprocess.run(['docker','rm','-f',cid],capture_output=True,timeout=30)
        OUT.mkdir(parents=True,exist_ok=True)
        (OUT/'result.json').write_text(json.dumps(REPORT,indent=2)+'\n')
