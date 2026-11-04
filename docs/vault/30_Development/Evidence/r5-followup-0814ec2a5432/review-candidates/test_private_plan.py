from pathlib import Path
import importlib.util,json
import pytest
import os,subprocess

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('candidate_gate',HERE/'renewal_gate.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
B=json.loads((HERE/'bindings.private.json').read_text())
RID='20261104T060000Z-0123456789ab'

@pytest.mark.parametrize('action,node',[('currentStatus',None),('runtimePreflight',1),('runtimePreflight',2),('install',1),('install',2),('finalize',1),('finalize',2),('transition',None)])
def test_descriptions_never_execute_and_keep_remote_paths_posix(monkeypatch,action,node):
 def forbidden(*_a,**_k):raise AssertionError('Description executed a child')
 monkeypatch.setattr(gate,'run',forbidden)
 description=gate.describe(B,action,RID,node)
 for value in description.get('remoteWorkerArgv',[]):
  assert '\\' not in value and '{' not in value and '}' not in value
 if action in {'install','finalize'}:
  assert description['remoteBundle'].startswith(B['nodes'][node-1]['transferRoot']+'/runs/'+RID+'/')
  assert description['nodeLocalKeyPreserved']

@pytest.mark.parametrize('value',['../../other','x; touch /tmp/other','x\ny','{runId}'])
def test_run_id_and_remote_argument_grammar_reject_injection(value):
 assert not gate.RUN.fullmatch(value)
 with pytest.raises(ValueError):gate.remote_refuse_unsafe([value])

def test_binding_digest_failure_precedes_any_identity_or_executable_read(tmp_path):
 f=tmp_path/'bindings.json';f.write_bytes(b'{"secret":"synthetic-only"}')
 with pytest.raises(ValueError,match='binding digest'):
  gate.load(f,'0'*64)

def test_drifted_actual_members_are_refused_before_any_child(monkeypatch,tmp_path):
 state=tmp_path/'state';state.mkdir()
 (state/'private-state.json').write_text(json.dumps(dict(tenantId='a',epoch='b',nodes=[dict(nodeId='wrong')])) )
 hosts=tmp_path/'known_hosts';hosts.write_text('synthetic public host key')
 binding=dict(B,statePath=str(state),stateSHA256=gate.sha(state/'private-state.json'),tenantId='a',epoch='b',executables={},knownHostsPath=str(hosts),knownHostsSHA256=gate.sha(hosts))
 f=tmp_path/'bindings.json';f.write_text(json.dumps(binding))
 with pytest.raises(ValueError,match='identity set'):
  gate.load(f,gate.sha(f))

def test_status_never_contacts_database_after_tunnel_ownership_refusal(monkeypatch):
 calls=[]
 def child(args,**_kwargs):
  calls.append(args)
  if 'rev-parse' in args:return B['pilotSourceHead'].encode()
  if 'status' in args and '--porcelain' in args:return b''
  raise RuntimeError('synthetic ownership refusal')
 monkeypatch.setattr(gate,'run',child)
 with pytest.raises(RuntimeError,match='ownership refusal'):
  gate.execute(B,'currentStatus',RID,None)
 assert len(calls)==3
 assert not any(str(x).endswith('lan_pilot.py') for args in calls for x in args)

def test_C3_child_environment_is_sanitized_without_changing_parent(monkeypatch):
 monkeypatch.setenv('PYTHONPATH','poison-path');monkeypatch.setenv('PYTHONHOME','poison-home')
 seen={}
 def child(*a,**kw):
  seen.update(kw['env'])
  return type('Result',(),dict(returncode=0,stdout=b'{}'))()
 monkeypatch.setattr(gate.subprocess,'run',child)
 assert gate.run(['synthetic-child'])==b'{}'
 assert not any(k.upper() in {'PYTHONPATH','PYTHONHOME'} for k in seen)
 assert os.environ['PYTHONPATH']=='poison-path' and os.environ['PYTHONHOME']=='poison-home'

@pytest.mark.parametrize('node,version',[(2,'3.14.4'),(2,'3.12.4'),(1,'3.12.3')])
def test_C4_actual_worker_version_drift_is_refused(monkeypatch,node,version):
 monkeypatch.setattr(gate,'remote',lambda *_:json.dumps(dict(compatible=True,pythonVersion=version,cryptographyVersion='50.0.1')).encode())
 with pytest.raises(ValueError,match='Actual worker runtime preflight'):
  gate.execute(B,'runtimePreflight',RID,node)

def test_C4_actual_312_worker_preflight_is_required_and_accepted(monkeypatch):
 monkeypatch.setattr(gate,'remote',lambda *_:json.dumps(dict(compatible=True,pythonVersion='3.12.3',cryptographyVersion='50.0.1')).encode())
 assert gate.execute(B,'runtimePreflight',RID,2)['pythonVersion']=='3.12.3'

def test_C3_every_direct_lan_pilot_command_uses_E_and_B():
 p=json.loads((HERE/'renewal-config.private.json').read_text())
 found=0
 for value in p['commands'].values():
  for c in value if isinstance(value,list) else [value]:
   if any(x.replace('\\','/').endswith('/tools/lan_pilot.py') for x in c['arguments']):
    assert c['arguments'][:2]==['-E','-B'];found+=1
 assert found==6

def test_C1_probe_rejects_extra_mutating_or_duplicate_action(tmp_path):
 spec=importlib.util.spec_from_file_location('context_probe',HERE/'s4u_context_probe.py');probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
 p=json.loads((HERE/'s4u-probe-plan.private.json').read_text());p['inputFiles']=[]
 p['commands'][0]['argv']+=['--action','install','--node','1']
 f=tmp_path/'probe.json';f.write_text(json.dumps(p))
 with pytest.raises(ValueError,match='Probe child scope'):
  probe.read_plan(f,gate.sha(f))

@pytest.mark.parametrize('scenario',['missing-parent','existing-parent','existing-target','outside-scope','junction-parent'])
def test_C2_scoped_backup_parent_guard_only_on_fixture(tmp_path,scenario):
 # Only the functions module runs against a fresh pytest fixture; the IdP apply
 # entrypoint and actual project identity/backup paths are never executed.
 script=r'''param($Guard,$Root,$Scenario)
$ErrorActionPreference='Stop'
. $Guard
$scope=Join-Path $Root 'intranet'
New-Item -ItemType Directory -Path $scope | Out-Null
New-Item -ItemType Directory -Path (Join-Path $scope 'r5') | Out-Null
$parent=Join-Path $scope 'backups'
$backup=Join-Path $parent 'sample'
if($Scenario -eq 'existing-parent'){New-Item -ItemType Directory -Path $parent | Out-Null}
if($Scenario -eq 'existing-target'){New-Item -ItemType Directory -Path $backup | Out-Null}
if($Scenario -eq 'outside-scope'){$backup=Join-Path $Root 'outside/sample'}
if($Scenario -eq 'junction-parent'){
 $outside=Join-Path $Root 'outside'
 New-Item -ItemType Directory -Path $outside | Out-Null
 New-Item -ItemType Junction -Path $parent -Target $outside | Out-Null
}
$refused=$false
try{Ensure-SvImmediateBackupsParent -TrustedRoot $Root -ScopeRoot $scope -BackupDirectory $backup}catch{$refused=$true}
if($Scenario -in @('existing-target','outside-scope','junction-parent')){if(-not $refused){throw 'Unsafe fixture path was admitted'}}else{if($refused -or -not(Test-Path -LiteralPath $parent)){throw 'Expected ordinary immediate parent was not ensured'}}
if(Test-Path -LiteralPath (Join-Path $scope 'r5/identity')){throw 'Identity write occurred in guard test'}
Write-Output 'guard-fixture-pass'
'''
 f=tmp_path/'guard-fixture.ps1';f.write_text(script)
 r=subprocess.run([B['context']['powershell'],'-NoProfile','-File',str(f),'-Guard',str(HERE/'IdPPathGuards.private.ps1'),'-Root',str(tmp_path),'-Scenario',scenario],capture_output=True,timeout=20)
 assert r.returncode==0,r.stderr.decode(errors='replace')
