"""Opt-in Docker lifecycle test: synthetic owned Node, key preservation and rollback."""
from pathlib import Path
import argparse,json,subprocess,hashlib,sys
from uuid import uuid4
from datetime import datetime,timezone
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tools'))
from lan_pilot import run,private_directory
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--prepared',type=Path,required=True)
parser.add_argument('--agent-image',required=True)
args=parser.parse_args()
p=json.loads(args.prepared.read_text())
tag='sv-workspace-upgrade-'+uuid4().hex[:12]
work=root/'.work'/tag;private_directory(work)
agent=run(['docker','image','inspect',args.agent_image,'--format','{{.Id}}'])
run(['docker','create','--name',tag,'--label','ai.saintvision.upgrade-test='+tag,'--network','none',
     '--pids-limit','256','--memory','512m','--cpus','1','--mount','type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock',
     '--env','INV_UPGRADE_AGENT_IMAGE='+agent,'--env','INV_PYTHON_NODE_IMAGE='+p['nodeImage'],'--entrypoint','python',p['kernelImage'],
     '-m','pytest','-x','-q','tests/integration/test_workspace_upgrade.py','--junitxml=/evidence/upgrade.xml','--basetemp=/tmp/workspace-upgrade-proof'])
try:
    run(['docker','cp',root/'deploy/lan',tag+':/app/deploy/lan'])
    run(['docker','cp',root/'tests/integration/test_workspace_upgrade.py',tag+':/app/tests/integration/test_workspace_upgrade.py'])
    result=subprocess.run(['docker','start','-a',tag],capture_output=True,timeout=240)
    (work/'pytest.log').write_bytes(result.stdout+result.stderr)
    run(['docker','cp',tag+':/evidence/upgrade.xml',work/'upgrade.xml'])
    xml=ET.parse(work/'upgrade.xml')
    cases=[dict(name=c.get('name'),passed=not any(c.find(x) is not None for x in ('failure','error','skipped'))) for c in xml.iter('testcase')]
    proof=dict(at=datetime.now(timezone.utc).isoformat(),codeSHA=run(['git','rev-parse','HEAD'],cwd=root),
               dirty=bool(run(['git','status','--porcelain'],cwd=root)),scope='local-real-docker-installer-synthetic-pki',
               agentImage=agent,nodeImage=p['nodeImage'],runtimeImageCodeSHA=p['codeSHA'],exitCode=result.returncode,cases=cases,
               sourceHashes={f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in ('deploy/lan/worker_workspace.py','deploy/lan/worker_config.py','tests/integration/test_workspace_upgrade.py')})
    (work/'evidence.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(dict(evidence=str(work/'evidence.json'),exitCode=result.returncode,cases=cases)),flush=True)
finally:
    inspected=json.loads(run(['docker','inspect',tag]))[0]
    assert inspected['Config']['Labels']['ai.saintvision.upgrade-test']==tag
    if inspected['State']['Running']:run(['docker','stop',tag])
    assert not json.loads(run(['docker','inspect',tag]))[0]['State']['Running']
if result.returncode or len(cases)!=3 or not all(c['passed'] for c in cases):
    raise SystemExit(1)
