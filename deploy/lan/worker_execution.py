"""Operator-invoked setup of a bounded probe profile on the existing Node."""
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
from worker_config import same_identity, image_id, repair_target, install_files, check_running


def run(*args, **kwargs):
    return subprocess.run(['docker',*args], capture_output=True, check=True,
                          timeout=kwargs.pop('timeout',30), **kwargs).stdout


def main():
    os.umask(0o077)
    folder=Path(__file__).resolve().parent
    manifest=json.loads((folder/'manifest.json').read_text())
    node=manifest['nodeId']
    state=Path.home()/'.local/share/saintvision'/node
    same_identity(json.loads((state/'manifest.json').read_text()),manifest)
    name='saintvision-'+node.lower()
    inspect=json.loads(run('inspect',name))[0]
    if inspect['Config']['Labels'].get('ai.saintvision.node')!=node:
        raise ValueError('Container ownership differs')
    run('load','-i',str(folder/'execution-image.tar'),timeout=120)
    expected=manifest['executionTest']
    actual=image_id(expected,json.loads(run('image','inspect',expected['agentTag']))[0])
    agent=image_id(manifest,json.loads(run('image','inspect',inspect['Image']))[0])
    args=inspect['Config']['Cmd']
    if args[args.index('--profile')+1]=='lan-test-v1':
        if args[args.index('--image')+1]!=actual:
            raise ValueError('Existing test image differs')
        check_running(name)
    else:
        backup=name+'-observation-backup'
        if subprocess.run(['docker','inspect',backup],capture_output=True).returncode==0:
            raise ValueError('Recovery backup already exists; preserve both containers')
        # This named Node is stopped only after identity and both images verify.
        run('stop',name)
        inspect=json.loads(run('inspect',name))[0]
        repair_target(manifest,inspect)
        volume=name+'-state'
        ownership=json.loads(run('volume','inspect',volume))[0]['Labels'].get('ai.saintvision.node')
        if ownership!=node: raise ValueError('Volume ownership differs')
        run('rename',name,backup)
        for flag,value in {'--profile':'lan-test-v1','--image':actual,'--executable':'/probe'}.items():
            args[args.index(flag)+1]=value
        try:
            run('create','--name',name,'--label','ai.saintvision.node='+node,
                '--restart','unless-stopped','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
                '--pids-limit','128','--memory','256m','--cpus','0.5',
                '--publish',str(manifest['nodeIP'])+':'+str(manifest['nodePort'])+':18443',
                '--mount','type=volume,source='+volume+',target=/state',
                '--mount','type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock',
                agent,*args)
            install_files(name,state)
            run('start',name)
            check_running(name)
        except (ValueError,OSError,subprocess.SubprocessError):
            failed=subprocess.run(['docker','inspect',name],capture_output=True,timeout=15)
            if failed.returncode==0:
                value=json.loads(failed.stdout)[0]
                if value['Config']['Labels'].get('ai.saintvision.node')!=node:
                    raise ValueError('Unexpected container; rollback requires inspection')
                run('stop',name)
                run('rename',name,name+'-setup-failed-'+uuid4().hex[:8])
            run('rename',backup,name)
            run('start',name)
            raise
    result=dict(nodeId=node,executionImage=actual,profile='lan-test-v1',
                maxTestCPU=0.5,maxTestMemoryMiB=64,workloadNetwork='none',
                backupContainer=name+'-observation-backup')
    (state/'execution-ready.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))


if __name__=='__main__':
    try: main()
    except (ValueError,KeyError,OSError,subprocess.SubprocessError) as error:
        print('Execution test setup stopped: '+str(error),file=sys.stderr)
        raise SystemExit(1)
