from pathlib import Path
import ast, datetime as dt, hashlib, json, os, subprocess

P=Path(__file__).resolve().parent
ROOT=P.parents[1]
OLD=P.parent/'r5-renewal-idp-plan-20261104'
b=json.loads((P/'bindings.private.json').read_text())
f=json.loads((P/'followup-bindings.json').read_text())
ledger=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def call(name,argv,env=None,expected=0):
    started=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
    r=subprocess.run([str(v) for v in argv],capture_output=True,timeout=150,env=env)
    (P/(name+'.private.stdout')).write_bytes(r.stdout)
    (P/(name+'.private.stderr')).write_bytes(r.stderr)
    ledger.append(dict(name=name,startedKST=started,exit=r.returncode,expectedExit=expected,stdoutSHA256=sha(P/(name+'.private.stdout')),stderrSHA256=sha(P/(name+'.private.stderr'))))
    (P/'validation-results.json').write_text(json.dumps(ledger,indent=2)+'\n')
    if r.returncode!=expected:raise RuntimeError(name+' failed exit '+str(r.returncode))
    return r.stdout

python=b['python'];ps=b['context']['powershell']
call('guard-suite',[python,'-I','-B','-m','pytest',P/'test_private_plan.py','-q','--junitxml='+str(P/'followup-guards.xml')])
for p in P.glob('*.py'):ast.parse(p.read_text(),filename=p.name)
ledger.append(dict(name='python-AST',exit=0,files=len(list(P.glob('*.py')))))
psparse="$ErrorActionPreference='Stop'; $svFiles=Get-ChildItem -LiteralPath '"+str(P)+"' -Filter '*.ps1'; foreach($svF in $svFiles){$svTokens=$null;$svErrors=$null;$null=[Management.Automation.Language.Parser]::ParseFile($svF.FullName,[ref]$svTokens,[ref]$svErrors);if($svErrors.Count){throw ('Parse failed: '+$svF.Name)}};@{files=$svFiles.Count;parsed=$true}|ConvertTo-Json -Compress"
call('powershell-AST',[ps,'-NoProfile','-NonInteractive','-Command',psparse])
poison=dict(os.environ,PYTHONHOME=str(P/'nonexistent-python-home'),PYTHONPATH=str(P/'nonexistent-python-path'))
pilot=Path(b['pilotSource'])/'tools/lan_pilot.py'
call('C3-poisoned-help',[python,'-E','-B',pilot,'--help'],env=poison)
v=json.loads(call('C3-poisoned-status',[python,'-E','-B',pilot,'--state',b['statePath'],'status'],env=poison))
assert len(v['nodes'])==2 and {n['nodeId'] for n in v['nodes']}=={n['nodeId'] for n in b['nodes']}
v=json.loads(call('C3-poisoned-wrapper-status',[python,'-I','-B',P/'renewal_gate.py','--bindings',P/'bindings.private.json','--bindings-sha256',f['bindingSHA256'],'--action','currentStatus','--run-id',b['attendedRunId']],env=poison))
assert len(v['nodes'])==2 and all(n['node']['status']=='online' for n in v['nodes'])
call('window-only',[python,'-I','-B',OLD/'source-b5b8/tools/scheduled_leaf_renewal.py','--config',P/'renewal-config.private.json','--expected-config-sha256',f['renewalConfigurationSHA256'],'--window-only'])
call('probe-describe',[python,'-I','-B',P/'s4u_context_probe.py','--plan',P/'s4u-probe-plan.private.json','--expected-sha256',f['s4uProbePlanSHA256'],'--describe'])
call('probe-registration-PlanOnly',[ps,'-NoProfile','-NonInteractive','-File',P/'Register-S4UContextProbe.private.ps1','-PlanPath',P/'s4u-probe-plan.private.json','-ExpectedPlanSHA256',f['s4uProbePlanSHA256'],'-PlanOnly'])
baseline=json.loads((P/'prior-packet-baselines.private.json').read_text())
assert all(sha(OLD/name)==pin for name,pin in baseline.items())
assert sha(Path(b['statePath'])/'private-state.json')==b['stateSHA256']
idp=json.loads((P/'idp-local-repair-plan.private.json').read_text())
assert all(sha(v['source'])==v['sourceSHA256'] for v in idp['backups'])
assert not Path(idp['targetDirectory']).exists() and not Path(idp['backupDirectory']).exists()
ledger.append(dict(name='preserved-state-and-prior-packet',exit=0,oldPacketFiles=len(baseline),oldIdentityInputs=len(idp['backups']),stateBytesPreserved=True,identityTargetAbsent=True,backupTargetAbsent=True))
head=call('source03-head',[b['context']['git'],'-C',b['pilotSource'],'rev-parse','HEAD']).decode().strip()
dirty=call('source03-clean',[b['context']['git'],'-C',b['pilotSource'],'status','--porcelain','--untracked-files=no'])
assert head==b['pilotSourceHead'] and not dirty
integration=call('integration-head',[b['context']['git'],'rev-parse','origin/integration/all-agents-unified']).decode().strip()
assert integration=='fd1530d9b46e6b90a708daa59b4394599684309a'
source=json.loads((P/'source-equivalence.json').read_text())
source.update(initialLandedIntegrationObserved=source.pop('landedIntegrationObserved',None),landedIntegrationObserved=integration,observedAtKST=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat())
(P/'source-equivalence.json').write_text(json.dumps(source,indent=2)+'\n')
ci=call('fd-ci',[ 'gh','run','list','--repo','egparadise/SaintVision-Invion','--commit',integration,'--limit','45','--json','databaseId,name,headSha,status,conclusion,event,url'])
(P/'fd-ci-readback.json').write_bytes(ci)
ledger.append(dict(name='C1-C4-boundary',exit=0,actualS4UProbeExecuted=False,runtimePreparationExecuted=False,identityWriteExecuted=False,scheduledTaskCreated=False,attendedCertificateTransitionExecuted=False,terminalReopenPersistencePending=True))
(P/'validation-results.json').write_text(json.dumps(ledger,indent=2)+'\n')
print(json.dumps(dict(checks=len(ledger),allRecordedExitsZero=all(v['exit']==0 for v in ledger),preservedPacketFiles=len(baseline),integrationHead=integration)))
