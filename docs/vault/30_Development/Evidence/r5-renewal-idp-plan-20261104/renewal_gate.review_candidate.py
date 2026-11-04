"""Private r5 gate candidate, pinned by the reviewed scheduler configuration.

Only --describe may be used before coordinator's post-review technical release.
No credentials are accepted as arguments or emitted in diagnostics.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

SAFE_REMOTE=re.compile(r'[A-Za-z0-9_/:@.,=+\-]+\Z')
RUN=re.compile(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}\Z')
PUBLIC_FILES=('rotation.json','ca.pem','node-cert.pem','control-cert.pem',
              'peer-policy-overlap.json','peer-policy-final.json')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def regular(p):
 p=Path(p)
 if p.is_symlink() or not p.is_file():raise ValueError('Expected regular pinned input')
 return p
def load(path,pin):
 if sha(regular(path))!=pin:raise ValueError('Private binding digest differs')
 b=json.loads(Path(path).read_text())
 if b['schemaVersion']!='r5-private-renewal-bindings:1' or len(b['nodes'])!=2:raise ValueError('Binding schema differs')
 for exe,pin in b['executables'].items():
  if sha(regular(exe))!=pin:raise ValueError('Executable digest differs')
 if sha(regular(b['knownHostsPath']))!=b['knownHostsSHA256']:raise ValueError('Pinned SSH host authority differs')
 state_path=Path(b['statePath'])/'private-state.json'
 if sha(regular(state_path))!=b['stateSHA256']:raise ValueError('Actual r5 private configuration drifted')
 state=json.loads(state_path.read_text())
 active={n['nodeId'] for n in state['nodes'] if not n.get('disabled',False)}
 if state['tenantId']!=b['tenantId'] or state['epoch']!=b['epoch'] or active!={n['nodeId'] for n in b['nodes']}:raise ValueError('Actual r5 identity set differs')
 return b
def run(args,*,data=None,timeout=180):
 r=subprocess.run([str(v) for v in args],input=data,capture_output=True,timeout=timeout)
 if r.returncode:raise RuntimeError('Pinned gate child failed; no diagnostics printed')
 if len(r.stdout)>1024*1024:raise ValueError('Gate output exceeds bound')
 return r.stdout
def remote(n,script):return run([*n['sshArguments'],n['python'],'-I','-B','-'],data=script.encode())
def remote_refuse_unsafe(args):
 if not all(SAFE_REMOTE.fullmatch(str(v)) and '..' not in PurePosixPath(str(v)).parts for v in args):raise ValueError('Unsafe remote argument')
def scp_args(b):
 return [b['scp'],'-q','-i',b['sshKeyPath'],'-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no','-o','UserKnownHostsFile='+b['knownHostsPath'],'-o','ConnectTimeout=5']
def remote_checks(b,n):
 # No install, bytecode cache write, network fetch, pip, key read or Node state write.
 pins={str(PurePosixPath(n['transferRoot'])/name):pin for name,pin in b['remoteSourceFiles'].items()}
 script=f'''import pathlib,hashlib,subprocess,sys
assert hashlib.sha256(pathlib.Path(sys.executable).resolve().read_bytes()).hexdigest()=={n['pythonSHA256']!r}
for name,pin in {pins!r}.items():
 p=pathlib.Path(name);assert p.is_file() and not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest()==pin
'''
 return script
def worker_command(n,action,bundle,receipt=None):
 args=[n['python'],'-I','-B',str(PurePosixPath(n['transferRoot'])/'leaf_rotation_standalone_runtime.py'),
       'run','--runtime-dir',n['runtimeRoot'],'--worker-script',str(PurePosixPath(n['transferRoot'])/'worker_leaf_rotation.py'),
       '--',action,'--bundle',str(bundle),'--worker-root',n['workerRoot']]
 if receipt:args+=['--commit-receipt',str(receipt)]
 remote_refuse_unsafe(args)
 return args
def describe(b,action,runid,index):
 node=b['nodes'][index-1] if index else None
 batch=Path(b['batchParent'])/runid
 if action=='currentStatus':return dict(argv=[b['python'],'-B',str(Path(b['pilotSource'])/'tools/lan_pilot.py'),'--state',b['statePath'],'status'],readOnly=True,requiresOwnedDatabaseTunnel=True)
 if action=='runtimePreflight':return dict(ssh=node['sshArguments'],remoteWorkerArgv=[node['python'],'-I','-B',str(PurePosixPath(node['transferRoot'])/'leaf_rotation_standalone_runtime.py'),'run','--runtime-dir',node['runtimeRoot'],'--worker-script',str(PurePosixPath(node['transferRoot'])/'worker_leaf_rotation.py'),'--','runtime-preflight'],readOnly=True)
 if action in {'install','finalize'}:
  bundle=str(PurePosixPath(node['transferRoot'])/'runs'/runid/'bundle')
  receipt=str(PurePosixPath(node['transferRoot'])/'runs'/runid/'commit-receipt.json')
  return dict(ssh=node['sshArguments'],sourcePublicBundle=str(batch/'nodes'/node['nodeId']),remoteBundle=bundle,publicFiles=list(PUBLIC_FILES),remoteWorkerArgv=worker_command(node,action,bundle,receipt if action=='finalize' else None),nodeLocalKeyPreserved=True)
 if action=='transition':return dict(powershell=b['context']['powershell'],script=str(Path(__file__).with_name('transition.private.ps1')),statePath=b['statePath'],existingSource=b['pilotSource'],stopOnlyExactOwnedObserver=True,reuseOwnedTunnelConsoleWeb=True,hidden=True)
 raise ValueError('Unknown action')
def execute(b,action,runid,index):
 desc=describe(b,action,runid,index)
 if action=='currentStatus':
  head=run([b['context']['git'],'-C',b['pilotSource'],'rev-parse','HEAD']).decode().strip()
  dirty=run([b['context']['git'],'-C',b['pilotSource'],'status','--porcelain','--untracked-files=no'])
  if head!=b['pilotSourceHead'] or dirty:raise ValueError('Pilot execution source changed')
  def quote(s):return "'"+str(s).replace("'","''")+"'"
  helper=quote(Path(b['pilotSource'])/'deploy/lan/SvLauncherInput.ps1')
  target=quote(b['nodes'][0]['user']+'@'+b['nodes'][0]['ip'])
  proof=f'''$ErrorActionPreference='Stop'
. {helper}
$svListeners=@(Get-NetTCPConnection -LocalPort 55448 -State Listen -ErrorAction SilentlyContinue)
$svProvider={{param($svPid) (Get-CimInstance Win32_Process -Filter "ProcessId = $svPid").CommandLine}}
if(-not(Assert-SvOwnedTunnelListeners -Listeners $svListeners -ExpectedForward '127.0.0.1:55448:127.0.0.1:55448' -ExpectedTarget {target} -CommandLineProvider $svProvider)){{throw 'Owned r5 database transport unavailable'}}
Write-Output 'owned'
'''
  if run([b['context']['powershell'],'-NoProfile','-NonInteractive','-Command',proof],timeout=30).decode().strip()!='owned':raise ValueError('Owned r5 database transport unavailable')
  return json.loads(run(desc['argv']))
 if action=='transition':
  return json.loads(run([desc['powershell'],'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',desc['script'],'-BindingsPath',str(ARGS.bindings),'-BindingsSHA256',ARGS.bindings_sha256]))
 n=b['nodes'][index-1]
 script=remote_checks(b,n)
 if action=='runtimePreflight':
  script+=f"r=subprocess.run({desc['remoteWorkerArgv']!r},capture_output=True,check=True,timeout=90);sys.stdout.buffer.write(r.stdout)\n"
  return json.loads(remote(n,script))
 batch=Path(b['batchParent'])/runid
 remote_bundle=desc['remoteBundle']
 if action=='install':
  local=batch/'nodes'/n['nodeId'];pins={name:sha(regular(local/name)) for name in PUBLIC_FILES}
  # The scheduler latches before prepare. Any partial upload/install is preserved.
  script+=f"p=pathlib.Path({remote_bundle!r});assert not p.exists();p.mkdir(parents=True,mode=0o700)\n"
  remote(n,script)
  scp=scp_args(b)
  destination=n['user']+'@'+n['ip']+':'+remote_bundle+'/'
  remote_refuse_unsafe([destination])
  run([*scp,*[str(local/name) for name in PUBLIC_FILES],destination])
  script=remote_checks(b,n)+f'''p=pathlib.Path({remote_bundle!r})
for name,pin in {pins!r}.items():
 q=p/name;assert q.is_file() and not q.is_symlink() and hashlib.sha256(q.read_bytes()).hexdigest()==pin
r=subprocess.run({desc['remoteWorkerArgv']!r},capture_output=True,check=True,timeout=180)
sys.stdout.buffer.write(r.stdout)
'''
  value=json.loads(remote(n,script))
  dest=batch/'install-receipts';dest.mkdir(exist_ok=True)
  target=dest/(n['nodeId']+'.json')
  with target.open('xb') as f:f.write((json.dumps(value,sort_keys=True)+'\n').encode());f.flush();os.fsync(f.fileno())
  return dict(installed=True,nodeOrdinal=index,privateKeyTransferred=False)
 if action=='finalize':
  local=regular(batch/'commit-receipts'/(n['nodeId']+'.json'));pin=sha(local)
  destination=n['user']+'@'+n['ip']+':'+str(PurePosixPath(remote_bundle).parent/'commit-receipt.json')
  remote_refuse_unsafe([destination])
  run([*scp_args(b),str(local),destination])
  script+=f'''p=pathlib.Path({str(PurePosixPath(remote_bundle).parent/'commit-receipt.json')!r});assert p.is_file() and not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest()=={pin!r}
r=subprocess.run({desc['remoteWorkerArgv']!r},capture_output=True,check=True,timeout=180);sys.stdout.buffer.write(r.stdout)
'''
  value=json.loads(remote(n,script))
  if value.get('finalized') is not True:raise ValueError('Node did not finalize the exact rotation')
  return dict(finalized=True,nodeOrdinal=index)
 raise ValueError('Unknown action')
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--bindings',type=Path,required=True);parser.add_argument('--bindings-sha256',required=True)
 parser.add_argument('--action',choices=['currentStatus','runtimePreflight','install','finalize','transition'],required=True)
 parser.add_argument('--node',type=int,choices=[1,2]);parser.add_argument('--run-id',required=True);parser.add_argument('--describe',action='store_true')
 ARGS=parser.parse_args()
 try:
  if not RUN.fullmatch(ARGS.run_id):raise ValueError('Run identity differs')
  if (ARGS.action in {'runtimePreflight','install','finalize'}) != (ARGS.node is not None):raise ValueError('Node selection differs')
  binding=load(ARGS.bindings,ARGS.bindings_sha256)
  result=describe(binding,ARGS.action,ARGS.run_id,ARGS.node) if ARGS.describe else execute(binding,ARGS.action,ARGS.run_id,ARGS.node)
  print(json.dumps(result))
 except Exception as error:
  print('Private r5 gate rejected ('+type(error).__name__+'); no diagnostics printed',file=sys.stderr)
  raise SystemExit(2)
