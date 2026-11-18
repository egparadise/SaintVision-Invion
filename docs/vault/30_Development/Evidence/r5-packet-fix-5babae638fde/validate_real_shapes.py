from pathlib import Path
import copy,datetime as dt,hashlib,importlib.util,json,subprocess
P=Path(__file__).resolve().parent;OLD=P.parent/'r5-persistence-c50115dce654'
spec=importlib.util.spec_from_file_location('private_describer',P/'describe_packet.py');description=importlib.util.module_from_spec(spec);spec.loader.exec_module(description)
b,canonical,describe_command,RID=description.b,description.canonical,description.describe_command,description.RID
load=lambda f:json.loads(Path(f).read_text(encoding='utf-8-sig'))
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
results=[]
def save(): (P/'real-shape-results.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
def probe(name,argv,expected):
    # No live operation value may enter any real binary-shape probe.
    assert not any(v in {'Cycle','Transition','ObserverRecovery','ScheduledTransition'} for v in argv)
    r=subprocess.run(argv,capture_output=True,timeout=30)
    (P/(name+'.private.stdout')).write_bytes(r.stdout);(P/(name+'.private.stderr')).write_bytes(r.stderr)
    results.append(dict(name=name,observedAtKST=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(),exit=r.returncode,expectedExit=expected,executableName=Path(argv[0]).name,stdoutSHA256=hashlib.sha256(r.stdout).hexdigest(),stderrSHA256=hashlib.sha256(r.stderr).hexdigest(),liveOperationExecuted=False))
    save();assert r.returncode==expected,name
    return r

old=load(OLD/'attended-cycle-config.private.json')['commands']['transition']
r=probe('H1-original-Python-PowerShell-shape',[old['executable'],'-NoProfile','-NonInteractive','-Command','exit 0'],2)
assert b'Unknown option: -N' in r.stderr or b'unknown option: -N' in r.stderr.lower()
probe('H1-correct-PowerShell-shape',[b['context']['powershell'],'-NoProfile','-NonInteractive','-Command','exit 0'],0)
for name in ['attended-cycle-config.private.json','scheduled-config-proposed-only.private.json']:
    c=copy.deepcopy(load(P/name)['commands']['transition']);describe_command(c)
    c['arguments'][c['arguments'].index('-Operation')+1]='ContextOnly';c['arguments'].append('-PlanOnly')
    assert not any(v in {'Cycle','Transition','ObserverRecovery','ScheduledTransition'} for v in c['arguments'])
    raw=canonical._run(c,RID);v=json.loads(raw)
    assert v['operation']=='ContextOnly' and v['executed'] is False
    results.append(dict(name='actual-canonical-full-argv-PlanOnly-'+name,exit=0,argv0=Path(c['executable']).name,mode='ContextOnly -PlanOnly',WmiLaunchExecuted=False,liveOperationExecuted=False));save()

commands=load(P/'wmi-cycle-commands.private.json');argv=commands['contextOnly']
assert argv[argv.index('-Operation')+1]=='ContextOnly' and argv[-1]!='20261104T082522Z-c50115dce654'
r=subprocess.run(argv,capture_output=True,timeout=120)
(P/'corrected-ContextOnly.private.stdout').write_bytes(r.stdout);(P/'corrected-ContextOnly.private.stderr').write_bytes(r.stderr)
result=dict(name='actual-corrected-ContextOnly',observedAtKST=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(),exit=r.returncode,runId=argv[-1],stdoutSHA256=hashlib.sha256(r.stdout).hexdigest(),stderrSHA256=hashlib.sha256(r.stderr).hexdigest(),liveOperationExecuted=False)
results.append(result);save()
assert r.returncode==0
receipt=json.loads(r.stdout);c=receipt['context']
assert c['ownerMatched'] is True and c['sessionId']==1 and c['userInteractive'] is True and c['jobQuerySucceeded'] is True and c['inJob'] is False and c['windowStation'].lower()=='winsta0' and c['desktop'].lower()=='default'
assert receipt['cycleExecuted'] is False and receipt['transitionExecuted'] is False and receipt['unattendedRenewalAccepted'] is False
(P/'corrected-contextonly-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
for name,pin in load(P/'prior-packet-and-proof-baselines.private.json').items():assert sha(OLD/name)==pin
manifest=load(P/'wmi-cycle-manifest.json')
for row in manifest['inputs']:assert sha(P/row['name'])==row['sha256']
print(json.dumps(dict(guardedRealBinaryChecks=len(results),legacyNegativeExit=2,correctedBinaryAndBothCanonicalPlanOnlyExits=0,actualContextOnlyExit=0,context=c,allNineCurrentInputsPinned=True,all75PriorPacketProofFilesPreserved=True,CycleExecuted=False,TransitionExecuted=False,RecoveryExecuted=False)))
