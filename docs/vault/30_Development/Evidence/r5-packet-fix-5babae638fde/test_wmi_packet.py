from pathlib import Path
import copy,hashlib,importlib.util,json,subprocess
import pytest
import types
P=Path(__file__).resolve().parent;B=P.parent/'r5-followup-0814ec2a5432'
load=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
b=load(B/'bindings.private.json')

@pytest.mark.parametrize('change',[
 {},{'inJob':True},{'jobQuerySucceeded':False},{'ownerMatched':False},
 {'sessionId':99},{'userInteractive':False},{'windowStation':'Service'},{'desktop':'Other'},
])
def test_actual_context_guard_predicates_only_synthetic_context(tmp_path,change):
    context=dict(ownerMatched=True,jobQuerySucceeded=True,inJob=False,sessionId=1,userInteractive=True,windowStation='WinSta0',desktop='Default');context.update(change)
    f=tmp_path/'context.json';f.write_text(json.dumps(context))
    script=r'''param($Guards,$InputFile,$ShouldReject)
$ErrorActionPreference='Stop'
. $Guards
$v=Get-Content -LiteralPath $InputFile -Raw | ConvertFrom-Json
$rejected=$false
try{Assert-SvJobFreeContext -Context $v -ExpectedSession 1 -Attended}catch{$rejected=$true}
if($rejected -ne ($ShouldReject -eq 'yes')){throw 'Context predicate outcome differs'}
'''
    s=tmp_path/'test.ps1';s.write_text(script)
    r=subprocess.run([b['context']['powershell'],'-NoProfile','-File',str(s),'-Guards',str(P/'R5ContextGuards.private.ps1'),'-InputFile',str(f),'-ShouldReject','yes' if change else 'no'],capture_output=True,timeout=20)
    assert r.returncode==0,r.stderr.decode(errors='replace')

def test_receipt_publication_refuses_existing_target_without_overwrite(tmp_path):
    s=tmp_path/'receipt.ps1';s.write_text(r'''param($Guards,$Target)
$ErrorActionPreference='Stop'
. $Guards
Write-SvNewReceipt $Target @{generation=1}
$refused=$false
try{Write-SvNewReceipt $Target @{generation=2}}catch{$refused=$true}
if(-not $refused -or (Get-Content -LiteralPath $Target -Raw | ConvertFrom-Json).generation -ne 1){throw 'One-shot receipt was overwritten'}
''')
    r=subprocess.run([b['context']['powershell'],'-NoProfile','-File',str(s),'-Guards',str(P/'R5ContextGuards.private.ps1'),'-Target',str(tmp_path/'receipt.json')],capture_output=True,timeout=20)
    assert r.returncode==0,r.stderr.decode(errors='replace')

def test_thirteen_non_transition_commands_and_safety_values_are_unchanged():
    before=load(B/'renewal-config.private.json');after=load(P/'attended-cycle-config.private.json')
    assert all(before['commands'][k]==v for k,v in after['commands'].items() if k!='transition')
    assert sum(len(v) if isinstance(v,list) else 1 for v in after['commands'].values())==14
    for key in ['sourceHeadSha','statePath','renewalWindowSeconds','heartbeatFreshnessSeconds','expectedNodeCount']:
        assert before[key]==after[key]
    assert '-Operation' in after['commands']['transition']['arguments']
    assert after['commands']['transition']['arguments'][-3:]==['Transition','-RunId','{runId}']

@pytest.mark.parametrize('name,allowed',[('transition-context-plan.private.json',['ContextOnly','Transition','ObserverRecovery','ScheduledTransition']),('cycle-context-plan.private.json',['Cycle'])])
def test_operation_scope_and_all_file_hashes_are_exact(name,allowed):
    p=load(P/name);assert p['allowedOperations']==allowed
    for row in p['pins']:assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256']

def test_manual_config_uses_reviewed_canonical_executor_contract():
    source=Path(b['schedulerSource'])/'tools/scheduled_leaf_renewal.py'
    spec=importlib.util.spec_from_file_location('canonical_scheduler',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    config=P/'attended-cycle-config.private.json'
    v=module.load_plan(config,hashlib.sha256(config.read_bytes()).hexdigest())
    assert v['renewalWindowSeconds']==172800 and v['expectedNodeCount']==2
    assert '--force' not in json.dumps(v) and '--reset-failure-latch' not in json.dumps(v)

def test_transition_proposal_fixes_environment_pair_ownership_and_job_lifetime():
    core=(P/'Invoke-OwnedR5Transition.private.ps1').read_text()
    assert 'Assert-SvJobFreeContext' in core and 'Get-SvActualContext' in core
    assert "SetEnvironmentVariable('PYTHONHOME',$null" in core and "SetEnvironmentVariable('PYTHONPATH',$null" in core
    assert 'Stop-SvExactObserver $svChild' in core and 'Stop-SvExactObserver $svRoot' in core
    assert 'Observer PID was reused' in core and 'GetOwnerSid' in core
    assert 'Multiple independent observer roots' in core
    assert 'primary gate remains failed' in core
    proposed=load(P/'scheduled-config-proposed-only.private.json')
    assert 'ScheduledTransition' in proposed['commands']['transition']['arguments']

def test_actual_wmi_startup_class_supports_the_desktop_property_used():
    script="(Get-CimClass Win32_ProcessStartup -ErrorAction Stop).CimClassProperties.Name | ConvertTo-Json"
    r=subprocess.run([b['context']['powershell'],'-NoProfile','-NonInteractive','-Command',script],capture_output=True,timeout=20)
    assert r.returncode==0
    fields=json.loads(r.stdout.decode('utf-8-sig'))
    assert 'WinstationDesktop' in fields and 'Desktop' not in fields
    controller=(P/'Invoke-R5WmiContext.private.ps1').read_text()
    assert "WinstationDesktop='Winsta0\\Default'" in controller

def describer():
    spec=importlib.util.spec_from_file_location('packet_description',P/'describe_packet.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

@pytest.mark.parametrize('name',['attended-cycle-config.private.json','scheduled-config-proposed-only.private.json'])
def test_H1_actual_canonical_flattened_argv0_and_description(monkeypatch,name):
    m=describer();c=load(P/name)['commands']['transition'];d=m.describe_command(c);seen=[]
    def capture(argv,**kwargs):seen.append(argv);return types.SimpleNamespace(returncode=0,stdout=b'{}')
    monkeypatch.setattr(m.canonical.subprocess,'run',capture)
    assert m.canonical._run(c,m.RID)=='{}'
    assert seen==[d['argv']] and Path(seen[0][0])==Path(b['context']['powershell'])
    assert Path(c['executable'])==Path(b['context']['powershell'])
    assert c['executableSha256']==b['executables'][b['context']['powershell']]

@pytest.mark.parametrize('field',['executable','executableSha256'])
def test_H1_mutated_binary_or_hash_is_refused_by_full_shape_guard(field):
    m=describer();c=copy.deepcopy(load(P/'attended-cycle-config.private.json')['commands']['transition'])
    c[field]=b['python'] if field=='executable' else '0'*64
    with pytest.raises(ValueError,match='executable'):m.describe_command(c)

@pytest.mark.parametrize('scenario',['valid','missing-hash','missing-pin','mutated-pin','mutated-file','duplicate-pin','missing-file'])
def test_M2_required_scheduler_pin_before_any_invocation(tmp_path,scenario):
    f=tmp_path/'scheduler.py';f.write_text("raise RuntimeError('this fixture must never execute')\n")
    pin=hashlib.sha256(f.read_bytes()).hexdigest();plan=dict(schedulerPath=str(f),schedulerSHA256=pin,pins=[dict(path=str(f),sha256=pin)])
    if scenario=='missing-hash':plan.pop('schedulerSHA256')
    if scenario=='missing-pin':plan['pins']=[]
    if scenario=='mutated-pin':plan['pins'][0]['sha256']='0'*64
    if scenario=='mutated-file':f.write_text('MUTATED - never executed')
    if scenario=='duplicate-pin':plan['pins'].append(dict(plan['pins'][0]))
    if scenario=='missing-file':f.unlink()
    v=tmp_path/'plan.json';v.write_text(json.dumps(plan))
    s=tmp_path/'guard.ps1';s.write_text(r'''param($Guards,$Plan,$Expected)
$ErrorActionPreference='Stop'
. $Guards
$v=Get-Content -LiteralPath $Plan -Raw | ConvertFrom-Json
$rejected=$false
try{Assert-SvPinnedScheduler $v}catch{$rejected=$true}
if($rejected -ne ($Expected -eq 'reject')){throw 'Scheduler pin predicate differs'}
''')
    r=subprocess.run([b['context']['powershell'],'-NoProfile','-File',str(s),'-Guards',str(P/'R5ContextGuards.private.ps1'),'-Plan',str(v),'-Expected','accept' if scenario=='valid' else 'reject'],capture_output=True,timeout=20)
    assert r.returncode==0,r.stderr.decode(errors='replace')

def test_M2_exact_scheduler_hash_pin_and_guard_precedes_both_calls():
    p=load(P/'cycle-context-plan.private.json');rows=[v for v in p['pins'] if Path(v['path'])==Path(p['schedulerPath'])]
    assert len(rows)==1 and rows[0]['sha256']==p['schedulerSHA256']==hashlib.sha256(Path(p['schedulerPath']).read_bytes()).hexdigest()
    source=(P/'Enter-R5WmiContext.private.ps1').read_text().splitlines()
    invocations=[i for i,v in enumerate(source) if '& $svP.python' in v and '$svP.schedulerPath' in v]
    assert len(invocations)==2
    assert all(source[i-1].strip()=='Assert-SvPinnedScheduler $svP' for i in invocations)

def test_scheduled_outputs_and_notification_policy_are_separate():
    m=load(P/'attended-cycle-config.private.json');s=load(P/'scheduled-config-proposed-only.private.json')
    assert s['statusPath']!=m['statusPath'] and s['logPath']!=m['logPath']
    assert s['notificationsEnabled'] is True and m['notificationsEnabled'] is False
    assert all(s['commands'][k]==v for k,v in m['commands'].items() if k!='transition')

def test_timeout_is_durable_unknown_preserves_intent_and_allows_late_receipt(tmp_path):
    s=tmp_path/'timeout.ps1';s.write_text(r'''param($Guards,$Root)
$ErrorActionPreference='Stop'
. $Guards
$intent=Join-Path $Root 'intent.json'
$receipt=Join-Path $Root 'result.json'
$unknown=Join-Path $Root 'completion-unknown.json'
Write-SvNewReceipt $intent @{original='keep'}
$before=(Get-FileHash -LiteralPath $intent).Hash
$v=Wait-SvContextReceipt -ReceiptPath $receipt -UnknownPath $unknown -Deadline ([DateTimeOffset]::UtcNow.AddSeconds(-1)) -UnknownRecord @{exit=124;outcome='completion-unknown';intentPreserved=$true;automaticRetry=$false;childTerminationAttempted=$false}
if($v -ne $false -or (Get-FileHash -LiteralPath $intent).Hash -cne $before){throw 'Timeout did not preserve unknown intent'}
$u=Get-Content -LiteralPath $unknown -Raw | ConvertFrom-Json
if($u.outcome -cne 'completion-unknown' -or $u.automaticRetry -ne $false -or $u.exit -ne 124){throw 'Timeout classification differs'}
Write-SvNewReceipt $receipt @{late=$true}
if(-not(Test-Path -LiteralPath $unknown)){throw 'Late receipt erased uncertainty record'}
''')
    r=subprocess.run([b['context']['powershell'],'-NoProfile','-File',str(s),'-Guards',str(P/'R5ContextGuards.private.ps1'),'-Root',str(tmp_path)],capture_output=True,timeout=20)
    assert r.returncode==0,r.stderr.decode(errors='replace')

def test_future_operation_ids_are_unused_distinct_from_harmless_and_old_sealed_id():
    c=load(P/'wmi-cycle-commands.private.json')
    ids=[c[k][-1] for k in ['contextOnly','firstCycleAfterReviewAndRootRelease','observerRecoveryAfterSeparateRootRelease','scheduledTransitionProposedOnly']]
    assert len(set(ids))==4 and '20261104T082522Z-c50115dce654' not in ids
    for k in ['firstCycleAfterReviewAndRootRelease','observerRecoveryAfterSeparateRootRelease','scheduledTransitionProposedOnly']:
        runid=c[k][-1];assert not list((P/'wmi-runtime').glob('*'+runid+'*'))
