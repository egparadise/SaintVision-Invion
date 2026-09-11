"""Package verified first-Workspace software for an existing enrolled LAN Node.

No private keys, DB credentials or user Workspace files are packaged. This tool
does not change an execution gate, enrollment, resource offers or remote state.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from uuid import uuid4
import zipfile

from lan_pilot import ROOT, load, run, private_directory

PROFILE = 'lan-workspace-v1'


def sha(path):
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def bundle(args):
    state = load(args.state)
    prepared = json.loads(args.prepared.read_text('utf-8'))
    proof = json.loads(args.evidence.read_text('utf-8'))
    if (not proof['passed'] or proof['dirty'] or proof['codeSHA'] != prepared['codeSHA']
            or proof['nodeImage'] != prepared['nodeImage']
            or proof['binaryHashes'] != prepared['binaryHashes']
            or proof['sourceHashes'] != prepared['sourceHashes']
            or not {'python','ai','output-recovery','failure'} <= {x['case'] for x in proof['firstWorkloads']}):
        raise ValueError('A matching clean first-Workspace execution proof is required')
    for relative, expected in prepared['sourceHashes'].items():
        if relative.startswith(('services/node-agent/', 'packages/contracts-go/')) and sha(ROOT/relative) != expected:
            raise ValueError('Node source changed after the verified build')
    binary = Path(prepared['work'])/'context/binaries/inv-node'
    if sha(binary) != prepared['binaryHashes']['inv-node']:
        raise ValueError('Verified Node binary differs')
    if not state.get('initialized') or not (args.state/'public/node-cert.pem').is_file():
        raise ValueError('Existing enrolled Node required')
    work = args.state/('workspace-package-'+uuid4().hex[:12])
    private_directory(work)
    shutil.copyfile(binary, work/'inv-node')
    shutil.copyfile(ROOT/'deploy/lan/Dockerfile.node', work/'Dockerfile')
    agent_tag = 'saintvision-workspace-agent:'+prepared['codeSHA'][:12]
    run(['docker','build','--network=none','--pull=false','-t',agent_tag,work],timeout=120)
    workload_tag = 'saintvision-workspace-python:'+prepared['codeSHA'][:12]
    run(['docker','tag',prepared['nodeImage'],workload_tag])
    def pack_image(tag, filename):
        image = json.loads(run(['docker','image','inspect',tag]))[0]
        path = work/filename
        run(['docker','save','-o',path,tag],timeout=180)
        return dict(agentTag=tag, agentImage=image['Id'], imageLayers=image['RootFS']['Layers'],
                    imageConfig=image['Config'], archiveSHA256=sha(path))
    manifest = {k:state[k] for k in ('tenantId','nodeId','epoch','serverIP','nodeIP','nodePort')}
    manifest.update(schemaVersion=1, scope='workspace-node-acceptance', profile=PROFILE,
                    imageCodeSHA=prepared['codeSHA'], packageCodeSHA=run(['git','rev-parse','HEAD'],cwd=ROOT),
                    packageDirty=bool(run(['git','status','--porcelain'],cwd=ROOT)),
                    installerHashes={name:sha(ROOT/'deploy/lan'/name) for name in ('worker_config.py','worker_workspace.py','Enable-Workspace.ps1')},
                    preparedAt=datetime.now(timezone.utc).isoformat(),
                    certificateSHA256=sha(args.state/'public/node-cert.pem'),
                    agent=pack_image(agent_tag,'node-agent.tar'),
                    workload=pack_image(workload_tag,'workspace-image.tar'))
    (work/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    target = work/'workspace-worker.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in ('manifest.json','node-agent.tar','workspace-image.tar'):
            archive.write(work/name,name)
        for name in ('ca.pem','signer.pub','peer-policy.json'):
            archive.write(args.state/name,name)
        for name in ('worker_config.py','worker_workspace.py','Enable-Workspace.ps1'):
            archive.write(ROOT/'deploy/lan'/name,name)
    result = dict(archive=str(target),sha256=sha(target),bytes=target.stat().st_size,
                  nodeId=state['nodeId'],profile=PROFILE,imageCodeSHA=prepared['codeSHA'],
                  packageCodeSHA=manifest['packageCodeSHA'],agentImage=manifest['agent']['agentImage'],
                  workloadImage=manifest['workload']['agentImage'],status='staged-not-installed')
    (work/'package-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    args = parser.parse_args()
    try:
        bundle(args)
    except (ValueError,KeyError,OSError,RuntimeError) as error:
        print('Workspace package stopped: '+str(error),file=sys.stderr)
        raise SystemExit(1)
