from pathlib import Path
import importlib.util,json
import pytest

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
