from pathlib import Path
import copy,hashlib,importlib.util,json,subprocess
import pytest
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
