from pathlib import Path,PurePosixPath
import copy,datetime as dt,hashlib,json
P=Path(__file__).resolve().parent;OLD=P.parent/'r5-renewal-idp-plan-20261104'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_bytes((json.dumps(v,indent=2)+'\n').encode())
b=json.loads((P/'bindings.private.json').read_text());oldb=json.loads((OLD/'bindings.private.json').read_text())
b.update(followupGatePath=str(P/'renewal_gate.py'),attendedRunId='20261104T073000Z-0814ec2a5432',attendedReceiptPath=str(P/'attended-first-transition.private.json'),recoveryObserverStdout=str(P/'attended-observer.private.stdout'),recoveryObserverStderr=str(P/'attended-observer.private.stderr'),scheduledTransitionScriptPath=str(OLD/'transition.private.ps1'),attendedTransitionScriptSHA256=sha(P/'Invoke-AttendedTransition.private.ps1'))
write(P/'bindings.private.json',b);bpin=sha(P/'bindings.private.json')
plan=json.loads((OLD/'renewal-config.private.json').read_text());oldbpin=sha(OLD/'bindings.private.json');changes=[]
for value in plan['commands'].values():
 for c in value if isinstance(value,list) else [value]:
  original=copy.deepcopy(c)
  c['arguments']=[a.replace(str(OLD/'renewal_gate.py'),str(P/'renewal_gate.py')).replace(str(OLD/'bindings.private.json'),str(P/'bindings.private.json')).replace(oldbpin,bpin) for a in c['arguments']]
  if any(str(a).replace('\\','/').endswith('/tools/lan_pilot.py') for a in c['arguments']) and '-E' not in c['arguments']:
   c['arguments'].insert(c['arguments'].index('-B'),'-E')
  for f in c['inputFiles']:
   if Path(f['path'])==OLD/'renewal_gate.py':f.update(path=str(P/'renewal_gate.py'),sha256=sha(P/'renewal_gate.py'))
   elif Path(f['path'])==OLD/'bindings.private.json':f.update(path=str(P/'bindings.private.json'),sha256=bpin)
  if c!=original:changes.append(c['id'])
write(P/'renewal-config.private.json',plan)
# Preserve all unchanged directory-create/transfer commands. Replace only each
# install script with the Bash/exact-Python/post-prep proof implementation.
prep=json.loads((OLD/'preparation-commands.private.json').read_text())
for i,n in enumerate(b['nodes'],1):
 root=PurePosixPath(n['transferRoot']);runtime=PurePosixPath(n['runtimeRoot']);v=n['bash']
 expected=dict(b['remoteSourceFiles']);expected['leaf-rotation-runtime.zip']=b['runtimeBundleSHA256']
 argv=[n['python'],'-I','-B',str(root/'leaf_rotation_standalone_runtime.py'),'run','--runtime-dir',str(runtime),'--worker-script',str(root/'worker_leaf_rotation.py'),'--','runtime-preflight']
 body=f'''import pathlib,hashlib,subprocess,sys,shutil,json
p=pathlib.Path({str(root)!r})
assert hashlib.sha256(pathlib.Path(sys.executable).resolve().read_bytes()).hexdigest()=={n['pythonSHA256']!r}
assert str(pathlib.Path(shutil.which('python3')).resolve())=={n['python']!r}
bash=pathlib.Path({v['bashResolved']!r});assert bash.is_file() and not bash.is_symlink()
assert str(pathlib.Path(shutil.which('bash')).resolve())==str(bash)
assert hashlib.sha256(bash.read_bytes()).hexdigest()=={v['bashSHA256']!r}
for name,pin in {expected!r}.items():
 f=p/name;assert f.is_file() and not f.is_symlink() and hashlib.sha256(f.read_bytes()).hexdigest()==pin
subprocess.run([str(bash),str(p/'prepare-leaf-rotation-runtime.sh'),'--standalone',{str(runtime)!r},str(p/'worker_leaf_rotation.py'),str(p/'leaf-rotation-runtime.zip')],check=True,timeout=150)
# Actual post-prep worker invocation, not Python version metadata alone.
r=subprocess.run({argv!r},capture_output=True,text=True,check=True,timeout=90)
proof=json.loads(r.stdout)
assert proof.get('compatible') is True and proof.get('pythonVersion')=={n['version']!r} and proof.get('cryptographyVersion')=='50.0.1' and proof.get('utcCertificateAPI') is True
print(json.dumps(dict(postPrepWorkerPreflight=proof,bashPinned=True,requiredPython={n['version']!r},nodeIdentityChanged=False)))
'''
 target=P/(n['alias']+'-install-runtime.private.py');target.write_bytes(body.encode())
 row=next(s for s in prep if s['id']==n['alias']+'-install-and-preflight-new-r5-runtime')
 row.update(stdinFile=str(target),stdinSHA256=sha(target),expectedActualWorkerPython=n['version'],bashPath=v['bashResolved'],bashSHA256=v['bashSHA256'])
write(P/'preparation-commands.private.json',prep)
idp=json.loads((OLD/'idp-local-repair-plan.private.json').read_text())
idp.update(applyScriptPath=str(P/'Apply-IdPLocalProposal.private.ps1'),applyScriptSHA256=sha(P/'Apply-IdPLocalProposal.private.ps1'),pathGuardScriptPath=str(P/'IdPPathGuards.private.ps1'),pathGuardScriptSHA256=sha(P/'IdPPathGuards.private.ps1'),trustedWorkspaceRoot='D:/Project/SaintVisionI-Invion',scopeRoot='D:/Project/SaintVisionI-Invion/.work/intranet')
write(P/'idp-local-repair-plan.private.json',idp)
# Exact non-mutating S4U scope: no transition, prepare, certificate or launcher.
nonce='20261104T073100Z-0814ec2a5432'
commands=[]
for key in ['currentStatus','runtimePreflight']:
 for c in plan['commands'][key] if isinstance(plan['commands'][key],list) else [plan['commands'][key]]:
  row=dict(action=c['id'],argv=[x.replace('{runId}',nonce) for x in c['arguments']],expectedPythonVersion=b['nodes'][int(c['id'][-1])-1]['version'] if key=='runtimePreflight' else None)
  row['argv'].insert(0,c['executable']);commands.append(row)
taskname='SaintVision-r5-S4U-Probe-0814ec2a5432'
owner='SaintVision one-shot read-only r5 probe owner='+b['context']['sid']+';nonce=0814ec2a5432'
pins=copy.deepcopy(plan['commands']['currentStatus']['inputFiles'])
for f in [P/'s4u_context_probe.py',P/'Register-S4UContextProbe.private.ps1']:
 pins.append(dict(path=str(f),sha256=sha(f)))
probe=dict(schemaVersion='r5-s4u-readonly-probe:1',taskName=taskname,ownerSid=b['context']['sid'],ownerMarker=owner,maximumExecutions=1,powershell=b['context']['powershell'],python=b['python'],runnerPath=str(P/'s4u_context_probe.py'),gatePath=str(P/'renewal_gate.py'),bindingsPath=str(P/'bindings.private.json'),bindingsSHA256=bpin,runId=nonce,inputFiles=pins,commands=commands,nodeIds=[n['nodeId'] for n in b['nodes']],receiptPath=str(P/'s4u-context-receipt.private.json'))
write(P/'s4u-probe-plan.private.json',probe)
probe_registration=[b['context']['powershell'],'-NoProfile','-NonInteractive','-File',str(P/'Register-S4UContextProbe.private.ps1'),'-PlanPath',str(P/'s4u-probe-plan.private.json'),'-ExpectedPlanSHA256',sha(P/'s4u-probe-plan.private.json')]
manual=[]
for group in ['currentStatus','runtimePreflight','prepare','install','stage','commit','transition','observe','finalize','finalObserve']:
 for c in plan['commands'][group] if isinstance(plan['commands'][group],list) else [plan['commands'][group]]:
  if group=='transition':
   argv=[b['context']['powershell'],'-NoProfile','-File',str(P/'Invoke-AttendedTransition.private.ps1'),'-BindingsPath',str(P/'bindings.private.json'),'-BindingsSHA256',bpin,'-Attended']
  else:argv=[c['executable'],*[a.replace('{runId}',b['attendedRunId']) for a in c['arguments']]]
  manual.append(dict(gate=c['id'],argv=argv,executed=False))
registration=dict(probePlanOnly=probe_registration+['-PlanOnly'],probeRegisterAfterTechnicalRelease=probe_registration,probeDemandStartAfterOwnerReadback=[b['context']['powershell'],'-NoProfile','-Command',"Start-ScheduledTask -TaskName '"+taskname+"'"],certificateTaskRegistrationReleased=False,firstTransitionMustBeAttended=True,terminalExitPersistenceProofPending=True)
write(P/'registration-and-first-attended-sequence.private.json',dict(registration=registration,attendedFirstCycle=manual,attendedRecoveryCommand=[b['context']['powershell'],'-NoProfile','-File',str(P/'Invoke-AttendedTransition.private.ps1'),'-BindingsPath',str(P/'bindings.private.json'),'-BindingsSHA256',bpin,'-Attended','-RecoverObserverOnly']))
manifest=dict(basePacket='52e236491213dc4d57ea98fc24d560187ab8d651',preparedAt=dt.datetime.now(dt.timezone.utc).isoformat(),renewalConfigurationSHA256=sha(P/'renewal-config.private.json'),bindingSHA256=bpin,idpProposalSHA256=sha(P/'idp-local-repair-plan.private.json'),s4uProbePlanSHA256=sha(P/'s4u-probe-plan.private.json'),preparationCommandsSHA256=sha(P/'preparation-commands.private.json'),operationalSequenceSHA256=sha(P/'registration-and-first-attended-sequence.private.json'),changedRenewalCommands=changes,sourceAndRuntimePathsUnchanged=True,unchangedSourceHead=b['schedulerSourceHead'],runtimePrepExecuted=False,idpWriteExecuted=False,s4uProbeTaskCreated=False,attendedTransitionExecuted=False)
write(P/'followup-bindings.json',manifest);print(json.dumps(manifest))
