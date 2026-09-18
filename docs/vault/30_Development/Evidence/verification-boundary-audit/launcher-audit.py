"""Execute unchanged intranet PS1 with native-command stand-ins in a temp tree."""
import hashlib,json,os,shutil,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(sys.argv[1]).resolve(); OUT=Path(sys.argv[2]).resolve()
source=ROOT/'tools/deploy_intranet.ps1'
results=[]
for case,failed in [('tls-failure','python'),('tests-failure','npm'),('smoke-failure','node'),('compose-failure','docker'),('success',None)]:
    with tempfile.TemporaryDirectory(prefix='sv-launcher-audit-') as folder:
        work=Path(folder)
        for d in ['tools','.venv/Scripts','apps/web','bin']:(work/d).mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,work/'tools/deploy_intranet.ps1')
        for name in ['python','npm','node','docker']:
            path=work/('.venv/Scripts/python.cmd' if name=='python' else 'bin/'+name+'.cmd')
            path.write_text('@echo off\necho '+name+' %*>>"'+str(work/'trace.txt')+'"\nexit /b '+('23' if name==failed else '0')+'\n')
        # No sockets, npm, Docker, certificates or production directories are used.
        (work/'entry.ps1').write_text("$ErrorActionPreference='Stop'\nfunction Invoke-WebRequest { [pscustomobject]@{StatusCode=200} }\n& ./tools/deploy_intranet.ps1\n",encoding='utf-8')
        env={**os.environ,'PATH':str(work/'bin')+os.pathsep+os.environ['PATH']}
        child=subprocess.run([shutil.which('powershell.exe'),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(work/'entry.ps1')],cwd=work,env=env,capture_output=True,timeout=30)
        output=child.stdout.decode(errors='replace')
        result={'case':case,'injectedNativeExit':23 if failed else 0,'processExit':child.returncode,'zeroErrorsBanner':'All Exit Codes 0' in output,'trace':(work/'trace.txt').read_text().splitlines(),'sourceUnchanged':(work/'tools/deploy_intranet.ps1').read_bytes()==source.read_bytes()}
        assert result['sourceUnchanged']
        if failed in (None,'python'): assert child.returncode==0 and result['zeroErrorsBanner']
        else: assert child.returncode!=0 and not result['zeroErrorsBanner']
        results.append(result)
OUT.write_text(json.dumps({'scope':'Windows PowerShell original script, synthetic native command results and HTTP stub; no deployment','sourceSHA256':hashlib.sha256(source.read_bytes()).hexdigest(),'results':results},indent=2)+'\n')
print(json.dumps(results,indent=2))
