"""Offline synthetic CLI probes; no Docker, database, or real credentials.
Run: python <this-file> --root <repository> --output <JSON>
Exit 0 means the audit reproduced its recorded behavior, NOT product acceptance.
"""
import argparse, ast, hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); root=args.root.resolve()
    rows=[]
    with tempfile.TemporaryDirectory(prefix='verification-audit-') as temp:
        folder=Path(temp)
        env={k:v for k,v in os.environ.items() if not k.startswith('INV_')}
        env['PYTHONPATH']=str(folder)
        cases={
          'lazy_missing_dependency': ('def create_app():\n    raise ModuleNotFoundError("synthetic missing dependency")\n','create_app',0),
          'factory_body_typeerror': ('def create_app():\n    raise TypeError("synthetic internal bug")\n','create_app',0),
          'missing_entrypoint': ('value = 1\n','app',0),
          'required_arguments_control': ('def create_app(*, configuration):\n    return configuration\n','create_app',0),
          'module_import_failure_control': ('raise ModuleNotFoundError("synthetic missing dependency")\n','app',1),
        }
        header='from fastapi import FastAPI, Request\nfrom fastapi.responses import JSONResponse\napp=FastAPI()\n@app.get("/v1/approvals")\ndef approvals(request: Request):\n    if not request.headers.get("authorization"):\n        return JSONResponse({},status_code=401)\n'
        cases['forged_probe_exception']=(header+'    raise RuntimeError("synthetic probe crash")\n','app',0)
        cases['forged_probe_success_control']=(header+'    return {"items":[]}\n','app',1)
        cases['forged_probe_denied_control']=(header+'    return JSONResponse({},status_code=403)\n','app',0)
        for name,(source,attr,expected) in cases.items():
            (folder/(name+'.py')).write_text(source,encoding='utf-8')
            result=subprocess.run([sys.executable,str(root/'tools/deployment_surface.py'),'--app',name+':'+attr,'--json'],env=env,cwd=root,capture_output=True,text=True,timeout=30)
            report=json.loads(result.stdout)
            rows.append(dict(case=name,exitCode=result.returncode,expectedObservedExit=expected,report=report))
        client=folder/'client';server=folder/'server';client.mkdir();server.mkdir()
        empty=subprocess.run([sys.executable,str(root/'tools/route_coverage.py'),'--served',str(server),'--client',str(client),'--json'],env=env,cwd=root,capture_output=True,text=True,timeout=30)
        rows.append(dict(case='empty_route_inputs',exitCode=empty.returncode,expectedObservedExit=0,report=json.loads(empty.stdout)))
    counts={};candidates=[]
    for tree in ('tools','tests'):
        files=list((root/tree).rglob('*.py'));counts[tree]=len(files)
        for file in files:
            parsed=ast.parse(file.read_text('utf-8-sig'))
            for node in ast.walk(parsed):
                if not isinstance(node,ast.Assert):continue
                x=node.test
                if isinstance(x,ast.Constant) and x.value is True:
                    candidates.append(dict(path=file.relative_to(root).as_posix(),line=node.lineno,pattern='literal true'))
                if isinstance(x,ast.Compare) and len(x.comparators)==1 and ast.dump(x.left)==ast.dump(x.comparators[0]):
                    candidates.append(dict(path=file.relative_to(root).as_posix(),line=node.lineno,pattern='same operand syntax'))
    files=['tools/deployment_surface.py','tools/route_coverage.py','tests/test_deployment_surface.py','tests/test_route_coverage.py','tests/integration/test_snapshots.py']
    proof=dict(baseSHA=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),scope='synthetic offline audit, not operational acceptance',sourceHashes={f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in files},scannedPythonFiles=counts,syntacticCandidates=candidates,observations=rows)
    args.output.write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    matched=all(r['exitCode']==r['expectedObservedExit'] for r in rows)
    print(json.dumps(dict(observations=len(rows),recordedBehaviorReproduced=matched,scannedPythonFiles=counts)))
    return 0 if matched else 1
if __name__=='__main__':raise SystemExit(main())
