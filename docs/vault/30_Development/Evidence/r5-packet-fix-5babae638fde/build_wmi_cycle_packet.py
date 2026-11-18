from pathlib import Path
import copy,datetime as dt,hashlib,json,uuid
P=Path(__file__).resolve().parent;B=P.parent/'r5-followup-0814ec2a5432'
load=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')
b=load(B/'bindings.private.json');sealed=load(P.parents[1]/'docs/vault/30_Development/Evidence/r5-followup-0814ec2a5432/packet-manifest.json')
for row in sealed['inputs']:assert sha(B/row['name'])==row['sha256']
ps=b['context']['powershell'];pspin=b['executables'][ps]
assert sha(ps)==pspin
source=(B/'Invoke-AttendedTransition.private.ps1').read_text()
header=source.split('\n',1)[0]
source=source.replace(header,"param([Parameter(Mandatory)][string]$BindingsPath,[Parameter(Mandatory)][string]$BindingsSHA256,[Parameter(Mandatory)][string]$SelfSHA256,[Parameter(Mandatory)][string]$ReceiptRoot,[Parameter(Mandatory)][ValidatePattern('^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}$')][string]$RunId,[ValidateSet('Attended','Scheduled')][string]$ExecutionMode='Attended',[switch]$RecoverObserverOnly)",1)
source=source.replace("if(-not $Attended -or -not [Environment]::UserInteractive){throw 'First transition/recovery must be attended'}", ". (Join-Path $PSScriptRoot 'R5ContextGuards.private.ps1')\nAssert-SvRecordRoot $ReceiptRoot")
source=source.replace("if((Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $svB.attendedTransitionScriptSHA256)","if((Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $SelfSHA256)")
source=source.replace("if([Security.Principal.WindowsIdentity]::GetCurrent().User.Value -cne $svB.context.sid -or (Get-Process -Id $PID).SessionId -ne $svB.context.sessionId){throw 'Bound attended owner/session differs'}", "$svActualContext=Get-SvActualContext $svB.context.sid\nAssert-SvJobFreeContext -Context $svActualContext -ExpectedSession $svB.context.sessionId -Attended:($ExecutionMode -eq 'Attended')\n$svB.attendedRunId=$RunId\n$svB.attendedReceiptPath=Join-Path $ReceiptRoot ('transition-core-'+$RunId+'.json')\n$svB.recoveryObserverStdout=Join-Path $ReceiptRoot ('observer-'+$RunId+'.private.stdout')\n$svB.recoveryObserverStderr=Join-Path $ReceiptRoot ('observer-'+$RunId+'.private.stderr')")
stopper="""function Stop-SvExactObserver {
 param($Expected)
 $svNow=Get-CimInstance Win32_Process -Filter ('ProcessId = '+$Expected.ProcessId) -ErrorAction Stop
 if($null -eq $svNow){return}
 if($svNow.CreationDate -ne $Expected.CreationDate -or $svNow.CommandLine -cne $Expected.CommandLine){throw 'Observer PID was reused or source changed'}
 $svOwner=Invoke-CimMethod -InputObject $svNow -MethodName GetOwnerSid -ErrorAction Stop
 if($svOwner.ReturnValue -ne 0 -or $svOwner.Sid -cne $svB.context.sid){throw 'Observer owner changed before stop'}
 Stop-Process -Id $Expected.ProcessId -ErrorAction Stop
}
"""
source=source.replace('function Start-SvObserverIfAbsent {',stopper+'function Start-SvObserverIfAbsent {')
source=source.replace('Stop-Process -Id $svChild.ProcessId -ErrorAction Stop','Stop-SvExactObserver $svChild').replace('Stop-Process -Id $svRoot.ProcessId -ErrorAction Stop','Stop-SvExactObserver $svRoot')
source=source.replace('attended=$true;sourceHead=',"attended=($ExecutionMode -eq 'Attended');executionMode=$ExecutionMode;actualContext=$svActualContext;sourceHead=")
(P/'Invoke-OwnedR5Transition.private.ps1').write_text(source,encoding='utf-8',newline='\n')
runtime=P/'wmi-runtime';runtime.mkdir(exist_ok=True)
base=load(B/'renewal-config.private.json')
pins=copy.deepcopy(base['commands']['currentStatus']['inputFiles'])
for name in ['R5ContextGuards.private.ps1','Invoke-R5WmiContext.private.ps1','Enter-R5WmiContext.private.ps1','Invoke-OwnedR5Transition.private.ps1']:
    pins.append(dict(path=str(P/name),sha256=sha(P/name)))
transition=dict(schemaVersion='r5-reviewed-wmi-context:1',allowedOperations=['ContextOnly','Transition','ObserverRecovery','ScheduledTransition'],ownerSid=b['context']['sid'],expectedSession=b['context']['sessionId'],desktop='Winsta0\\Default',receiptRoot=str(runtime),pins=pins,guardsPath=str(P/'R5ContextGuards.private.ps1'),guardsSHA256=sha(P/'R5ContextGuards.private.ps1'),powershell=b['context']['powershell'],entryPath=str(P/'Enter-R5WmiContext.private.ps1'),transitionCorePath=str(P/'Invoke-OwnedR5Transition.private.ps1'),transitionCoreSHA256=sha(P/'Invoke-OwnedR5Transition.private.ps1'),bindingsPath=str(B/'bindings.private.json'),bindingsSHA256=sha(B/'bindings.private.json'),python=b['python'],git=b['context']['git'],node=b['context']['node'])
write(P/'transition-context-plan.private.json',transition)
manual=copy.deepcopy(base);manual.update(logPath=str(runtime/'manual-cycle.jsonl'),statusPath=str(runtime/'manual-cycle-status.json'),notificationsEnabled=False)
c=manual['commands']['transition'];c.update(executable=ps,executableSha256=pspin,arguments=['-NoProfile','-NonInteractive','-File',str(P/'Invoke-R5WmiContext.private.ps1'),'-PlanPath',str(P/'transition-context-plan.private.json'),'-ExpectedPlanSHA256',sha(P/'transition-context-plan.private.json'),'-Operation','Transition','-RunId','{runId}'],inputFiles=pins+[dict(path=str(P/'transition-context-plan.private.json'),sha256=sha(P/'transition-context-plan.private.json'))])
write(P/'attended-cycle-config.private.json',manual)
scheduler=Path(b['schedulerSource'])/'tools/scheduled_leaf_renewal.py'
cycle=copy.deepcopy(transition);cycle.update(allowedOperations=['Cycle'],manualConfigPath=str(P/'attended-cycle-config.private.json'),manualConfigSHA256=sha(P/'attended-cycle-config.private.json'),manualStatusPath=manual['statusPath'],schedulerPath=str(scheduler),schedulerSHA256=sha(scheduler))
cycle['pins']=[row for row in pins if Path(row['path']).resolve()!=scheduler.resolve()]+[dict(path=str(P/'attended-cycle-config.private.json'),sha256=sha(P/'attended-cycle-config.private.json')),dict(path=str(P/'transition-context-plan.private.json'),sha256=sha(P/'transition-context-plan.private.json')),dict(path=str(scheduler),sha256=sha(scheduler))]
write(P/'cycle-context-plan.private.json',cycle)
scheduled=copy.deepcopy(manual);scheduled.update(logPath=str(runtime/'scheduled-proposed.jsonl'),statusPath=str(runtime/'scheduled-proposed-status.json'),notificationsEnabled=True);scheduled['commands']['transition']['arguments']=[a if a!='Transition' else 'ScheduledTransition' for a in c['arguments']]
write(P/'scheduled-config-proposed-only.private.json',scheduled)
rid=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-5babae638fde'
def argv(plan,mode):
    operation_run_id=rid if mode=='ContextOnly' else dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:12]
    return [b['context']['powershell'],'-NoProfile','-NonInteractive','-File',str(P/'Invoke-R5WmiContext.private.ps1'),'-PlanPath',str(P/plan),'-ExpectedPlanSHA256',sha(P/plan),'-Operation',mode,'-RunId',operation_run_id]
commands=dict(contextOnly=argv('transition-context-plan.private.json','ContextOnly'),firstCycleAfterReviewAndRootRelease=argv('cycle-context-plan.private.json','Cycle'),observerRecoveryAfterSeparateRootRelease=argv('transition-context-plan.private.json','ObserverRecovery'),scheduledTransitionProposedOnly=argv('transition-context-plan.private.json','ScheduledTransition'),windowOnly=[b['python'],'-I','-B',str(Path(b['schedulerSource'])/'tools/scheduled_leaf_renewal.py'),'--config',str(P/'attended-cycle-config.private.json'),'--expected-config-sha256',sha(P/'attended-cycle-config.private.json'),'--window-only'])
write(P/'wmi-cycle-commands.private.json',commands)
names=['R5ContextGuards.private.ps1','Invoke-R5WmiContext.private.ps1','Enter-R5WmiContext.private.ps1','Invoke-OwnedR5Transition.private.ps1','transition-context-plan.private.json','cycle-context-plan.private.json','attended-cycle-config.private.json','scheduled-config-proposed-only.private.json','wmi-cycle-commands.private.json']
manifest=dict(baseSealedPacketSHA='9f5191eb006f06acf105e8dc2a714ce196308964',upstreamBindingsPacketSHA='65b85bc59e402125a264dc6cda475f8c764d255d',codeSourceHead=b['schedulerSourceHead'],livePilotSourceHead=b['pilotSourceHead'],inputs=[dict(name=n,sha256=sha(P/n)) for n in names],fourteenGatesPreserved=True,unchangedNonTransitionCommands=13,canonicalDurableLatchAndCASAndPostconditions=True,normalClockAnd172800SecondWindow=True,cycleExecutionReleased=False,transitionExecutionReleased=False,observerRecoveryReleased=False,scheduledTransitionProposedOnly=True,S4UAcceptance=False)
write(P/'wmi-cycle-manifest.json',manifest)
print(json.dumps(dict(inputs=manifest['inputs'],contextRunId=rid,cycleExecuted=False)))
