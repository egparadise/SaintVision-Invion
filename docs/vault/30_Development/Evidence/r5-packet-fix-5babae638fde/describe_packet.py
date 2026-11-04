from pathlib import Path
import copy,hashlib,importlib.util,json
P=Path(__file__).resolve().parent;B=P.parent/'r5-followup-0814ec2a5432'
b=json.loads((B/'bindings.private.json').read_text())
spec=importlib.util.spec_from_file_location('reviewed_scheduler',Path(b['schedulerSource'])/'tools/scheduled_leaf_renewal.py')
canonical=importlib.util.module_from_spec(spec);spec.loader.exec_module(canonical)
RID='20261104T090000Z-5babae638fde'
def describe_command(command,run_id=RID):
    canonical._command(command,'transition')
    argv=[str(canonical._regular(Path(command['executable']))),*[canonical._expand(x,run_id) for x in command['arguments']]]
    expected=b['context']['powershell']
    if Path(argv[0])!=Path(expected) or command['executableSha256']!=b['executables'][expected]:raise ValueError('Transition executable/hash must be pinned PowerShell')
    if hashlib.sha256(Path(argv[0]).read_bytes()).hexdigest()!=command['executableSha256']:raise ValueError('Actual transition executable hash differs')
    if argv[1:4]!=['-NoProfile','-NonInteractive','-File']:raise ValueError('PowerShell binary/argument contract differs')
    return dict(argv=argv,workingDirectory=command['workingDirectory'],executableSHA256=command['executableSha256'],inputPinCount=len(command['inputFiles']),descriptionOnly=True,operationExecuted=False)

if __name__=='__main__':
    v={}
    for name in ['attended-cycle-config.private.json','scheduled-config-proposed-only.private.json']:
        plan=json.loads((P/name).read_text());v[name]=describe_command(plan['commands']['transition'])
    (P/'flattened-transition-descriptions.json').write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(describedConfigs=2,argv0='powershell.exe',executableAndArgumentsValidated=True,operationsExecuted=False)))
