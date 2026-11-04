"""One-shot S4U context observation: three allowlisted read-only gate actions only."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,datetime

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read_plan(path,pin):
 if Path(path).is_symlink() or sha(path)!=pin:raise ValueError('Probe plan digest differs')
 p=json.loads(Path(path).read_text())
 if p['schemaVersion']!='r5-s4u-readonly-probe:1' or p['maximumExecutions']!=1:raise ValueError('Probe scope differs')
 if [c['action'] for c in p['commands']]!=['currentStatus','runtimePreflight-1','runtimePreflight-2']:raise ValueError('Only the three exact read-only actions are admitted')
 for row in p['inputFiles']:
  f=Path(row['path'])
  if f.is_symlink() or not f.is_file() or sha(f)!=row['sha256']:raise ValueError('Probe input digest differs')
 for c in p['commands']:
  action='currentStatus' if c['action']=='currentStatus' else 'runtimePreflight'
  expected=[p['python'],'-I','-B',p['gatePath'],'--bindings',p['bindingsPath'],'--bindings-sha256',p['bindingsSHA256'],'--action',action,'--run-id',p['runId']]
  if action=='runtimePreflight':expected+=['--node',c['action'][-1]]
  if c['argv']!=expected:raise ValueError('Probe child scope differs')
 return p
def run_probe(p):
 # Verify actual task principal/logon type, rather than inferring it from a PID.
 text="""$ErrorActionPreference='Stop'
$svT=Get-ScheduledTask -TaskName '%s' -ErrorAction Stop
@{sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;sessionId=(Get-Process -Id $PID).SessionId;userInteractive=[Environment]::UserInteractive;logonType=$svT.Principal.LogonType.ToString();taskOwner=$svT.Description} | ConvertTo-Json -Compress
""" % p['taskName']
 env={k:v for k,v in os.environ.items() if k.upper() not in {'PYTHONPATH','PYTHONHOME'}}
 r=subprocess.run([p['powershell'],'-NoProfile','-NonInteractive','-Command',text],capture_output=True,timeout=20,env=env)
 if r.returncode:raise RuntimeError('Actual S4U context could not be read')
 context=json.loads(r.stdout)
 if context['sid']!=p['ownerSid'] or context['logonType']!='S4U' or context['userInteractive'] is not False or context['taskOwner']!=p['ownerMarker']:raise ValueError('Actual one-shot S4U context differs')
 target=Path(p['receiptPath']);intent=target.with_suffix('.intent.json')
 # O_EXCL prevents a second demand-start from silently becoming another sample.
 with intent.open('xb') as f:
  f.write(json.dumps(dict(startedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='read-only-context-probe',sessionId=context['sessionId'])).encode());f.flush();os.fsync(f.fileno())
 results=[]
 for c in p['commands']:
  r=subprocess.run(c['argv'],capture_output=True,timeout=180,env=env)
  facts=dict(action=c['action'],exit=r.returncode,accepted=False)
  if r.returncode==0:
   v=json.loads(r.stdout)
   if c['action']=='currentStatus':
    now=datetime.datetime.now(datetime.timezone.utc)
    fresh=all(n.get('node',{}).get('status')=='online' and -1<=(now-datetime.datetime.fromisoformat(str(n['node'].get('heartbeat_at',n['node'].get('heartbeatAt'))).replace('Z','+00:00'))).total_seconds()<=120 for n in v.get('nodes',[]))
    facts['accepted']=len(v.get('nodes',[]))==2 and {n.get('nodeId') for n in v['nodes']}==set(p['nodeIds']) and fresh
   else:
    facts['accepted']=v.get('compatible') is True and v.get('pythonVersion')==c['expectedPythonVersion'] and v.get('cryptographyVersion')=='50.0.1'
  results.append(facts)
 receipt=dict(schemaVersion='r5-s4u-readonly-context-receipt:1',observedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),context=dict(sessionId=context['sessionId'],logonType=context['logonType'],userInteractive=context['userInteractive'],ownerMatched=True),results=results,allReadOnlyChecksAccepted=all(x['accepted'] for x in results),certificateRotationExecuted=False,transitionExecuted=False,unattendedRenewalAccepted=False)
 with target.open('xb') as f:f.write((json.dumps(receipt,indent=2)+'\n').encode());f.flush();os.fsync(f.fileno())
 return 0 if receipt['allReadOnlyChecksAccepted'] else 2
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--plan',required=True,type=Path);a.add_argument('--expected-sha256',required=True);a.add_argument('--describe',action='store_true');q=a.parse_args()
 try:
  p=read_plan(q.plan,q.expected_sha256)
  if q.describe:
   print(json.dumps(dict(taskName=p['taskName'],actions=[c['action'] for c in p['commands']],maximumExecutions=1,readOnly=True,executed=False)));raise SystemExit(0)
  raise SystemExit(run_probe(p))
 except Exception as e:
  print('S4U read-only probe refused ('+type(e).__name__+'); no diagnostics printed',file=sys.stderr);raise SystemExit(2)
