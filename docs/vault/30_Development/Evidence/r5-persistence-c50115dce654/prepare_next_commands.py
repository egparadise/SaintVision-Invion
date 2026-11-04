from pathlib import Path
import hashlib,json
P=Path(__file__).resolve().parent
B=P.parent/'r5-followup-0814ec2a5432'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
b=load(B/'bindings.private.json');f=load(B/'followup-bindings.json')
old=load(B/'registration-and-first-attended-sequence.private.json')
def quote(v):return "'"+str(v).replace("'","''")+"'"
context=r'''$ErrorActionPreference='Stop'
$svBindingPath=__BINDING__
if((Get-FileHash -LiteralPath $svBindingPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne '__PIN__'){throw 'Sealed binding differs'}
$svB=Get-Content -LiteralPath $svBindingPath -Encoding UTF8 -Raw | ConvertFrom-Json
if(-not [Environment]::UserInteractive -or [Security.Principal.WindowsIdentity]::GetCurrent().User.Value -cne $svB.context.sid -or (Get-Process -Id $PID).SessionId -ne $svB.context.sessionId){throw 'Bound attended console required'}
if(-not ('SvReadOnlyJobContextProof' -as [type])){
 Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public static class SvReadOnlyJobContextProof { [DllImport("kernel32.dll", SetLastError=true)] [return: MarshalAs(UnmanagedType.Bool)] public static extern bool IsProcessInJob(IntPtr process, IntPtr job, [MarshalAs(UnmanagedType.Bool)] out bool result); }'
}
$svInJob=$false
$svJobQuery=[SvReadOnlyJobContextProof]::IsProcessInJob([Diagnostics.Process]::GetCurrentProcess().Handle,[IntPtr]::Zero,[ref]$svInJob)
if(-not $svJobQuery -or $svInJob){throw 'Attended entry is job-owned or job proof unavailable; no observer may be stopped'}
$svScript=__SCRIPT__
if((Get-FileHash -LiteralPath $svScript -Algorithm SHA256).Hash.ToLowerInvariant() -cne $svB.attendedTransitionScriptSHA256){throw 'Sealed attended script differs'}
& $svScript -BindingsPath $svBindingPath -BindingsSHA256 '__PIN__' -Attended __RECOVERY__
$svNativeExit=$LASTEXITCODE
if($svNativeExit -ne 0){throw ('Attended entry native gate failed: '+$svNativeExit)}
'''.replace('__BINDING__',quote(B/'bindings.private.json')).replace('__PIN__',f['bindingSHA256']).replace('__SCRIPT__',quote(B/'Invoke-AttendedTransition.private.ps1'))
transition=context.replace('__RECOVERY__','')
recovery=context.replace('__RECOVERY__','-RecoverObserverOnly')
(P/'attended-jobfree-context.ps1.review').write_text(transition,encoding='utf-8',newline='\n')
manual=old['attendedFirstCycle']
for row in manual:
    if row['gate']=='transition':row['argv']=[b['context']['powershell'],'-NoProfile','-Command',transition]
out=dict(schemaVersion='r5-next-commands-after-persistence:1',baseSealedEvidenceSHA='65b85bc59e402125a264dc6cda475f8c764d255d',sealedPacketPath=str(B),rootTechnicalReleaseReceived=False,executed=False,preparationCommandsPath=str(B/'preparation-commands.private.json'),preparationCommandsSHA256=f['preparationCommandsSHA256'],idpApply=[b['context']['powershell'],'-NoProfile','-NonInteractive','-File',str(B/'Apply-IdPLocalProposal.private.ps1'),'-PlanPath',str(B/'idp-local-repair-plan.private.json'),'-PlanSHA256',f['idpProposalSHA256']],S4U=old['registration'],windowOnly=[b['python'],'-I','-B',str(P.parent/'r5-renewal-idp-plan-20261104/source-b5b8/tools/scheduled_leaf_renewal.py'),'--config',str(B/'renewal-config.private.json'),'--expected-config-sha256',f['renewalConfigurationSHA256'],'--window-only'],firstAttendedCycle=manual,attendedContextGuardSHA256=sha(P/'attended-jobfree-context.ps1.review'),observerRecoveryFromProvenJobFreeConsole=[b['context']['powershell'],'-NoProfile','-Command',recovery],acceptedWMIMechanismAlternative='Requires a new exact one-shot transition plan/review; do not replay the already-used restoration controller',certificateScheduledRegistrationReleased=False,scheduledTransitionEnvironmentAndLifetimeFixRequired=True)
(P/'next-commands.private.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
proof=load(P/'process-persistence.json')
proof.pop('priorWorkerDoneAtUTC',None);proof.pop('priorWorkerDoneTimeApproximate',None)
proof.update(priorWorkerDoneMessage='msg_22ee1c05cc1d',priorWorkerDoneLowerBoundUTC='2026-11-04T07:48:17Z',priorWorkerDoneUpperBoundUTC='2026-11-04T07:50:30Z',exactPriorWorkerDoneTimestampRecorded=False)
for row in proof['processes']:
    row.pop('priorWorkerDonePredatedCreation',None);row['creationPredatesPriorWorkerDoneLowerBound']=True
(P/'process-persistence.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(nextCommandsSHA256=sha(P/'next-commands.private.json'),attendedContextGuardSHA256=out['attendedContextGuardSHA256'],executed=False)))
