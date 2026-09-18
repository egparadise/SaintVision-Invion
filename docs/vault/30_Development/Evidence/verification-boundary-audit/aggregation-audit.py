"""Offline audit of real runner/gates. No Docker, PG, CI or external network."""
import contextlib, importlib.util, io, json, os, re, subprocess, sys, tempfile, textwrap
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(sys.argv[1]).resolve(); OUTPUT=Path(sys.argv[2]).resolve()
sys.path.insert(0,str(ROOT/'tools'))
import run_vf_security_tests as runner
import node_dependent_tests as selection
PASS='<testsuites><testsuite><testcase name="previous-run"/></testsuite></testsuites>'
EMPTY='<testsuites><testsuite tests="0"/></testsuites>'
results=[]
class Connection:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def execute(self,*args):return None
original_cwd=Path.cwd()
try:
    for case,prior,child_code,new_xml in [
        ('timeout-with-stale-pass',PASS,124,None),
        ('exit1-with-stale-pass',PASS,1,None),
        ('exit0-with-stale-pass',PASS,0,None),
        ('exit0-missing-xml',None,0,None),
        ('exit0-empty-xml',None,0,EMPTY),
        ('exit0-malformed-xml',None,0,'<broken'),
        ('exit5-zero-collection',None,5,EMPTY),
        ('exit0-partial-one-case',None,0,PASS),
    ]:
        with tempfile.TemporaryDirectory(prefix='vf-aggregation-audit-') as folder:
            root=Path(folder); work=root/'.work';work.mkdir();xml=work/'audit-tests.xml'
            if prior:xml.write_text(prior)
            name={}
            def docker(args,**kwargs):
                if args[1]=='run':name['value']=args[args.index('--name')+1];out='synthetic-container'
                elif args[1]=='inspect' and '--format' not in args:out=json.dumps([{'NetworkSettings':{'Ports':{'5432/tcp':[{'HostPort':'1'}]},'IPAddress':'127.0.0.1'}}])
                elif args[1]=='inspect':out=name['value']
                else:out='synthetic'
                return subprocess.CompletedProcess(args,0,out,'')
            def child(args,**kwargs):
                if new_xml is not None:xml.write_text(new_xml)
                if child_code==124:raise subprocess.TimeoutExpired(args,1800)
                return subprocess.CompletedProcess(args,child_code)
            with patch.object(runner,'ROOT',root), patch.object(runner,'dependents',return_value=[]), patch.object(runner.docker_diag,'run',side_effect=docker), patch.object(runner.psycopg,'connect',return_value=Connection()), patch.object(runner.subprocess,'run',side_effect=child), patch.object(sys,'argv',['runner','tests/synthetic.py']), patch.dict(os.environ,{'VF_EVIDENCE_PREFIX':'audit','VF_BROWSER_TEST':'1'},clear=True), contextlib.redirect_stdout(io.StringIO()):
                code=runner.main()
            proof=json.loads((work/'audit.json').read_text())
            # No credentials/log contents are persisted.
            results.append({'case':case,'exitCode':code,'tests':proof.get('tests'),'testReport':proof.get('testReport'),'provenanceFields':sorted(set(proof)&{'codeSHA','runId','sourceHashes','xmlSha256','startedAt','finishedAt'}),'cleanup':proof.get('isolatedContainerRemoved')})
            os.chdir(original_cwd)
    # Execute actual embedded Python gates in temporary working directories.
    for workflow in ['backend','core','desktop-browser']:
        source=(ROOT/f'.github/workflows/{workflow}.yml').read_text()
        blocks=re.findall(r"python - <<'PY'\n(.*?)\n\s+PY",source,re.S)
        gate=textwrap.dedent(blocks[-1])
        for case,body in [('empty',EMPTY),('one-pass',PASS),('one-skip','<testsuites><testsuite><testcase name="x"><skipped/></testcase></testsuite></testsuites>')]:
            with tempfile.TemporaryDirectory(prefix='ci-gate-audit-') as folder:
                os.chdir(folder);Path('dist').mkdir();Path('.work').mkdir()
                Path('backend-tests.xml').write_text(body);Path('dist/core-tests.xml').write_text(body)
                Path('dist/docker-host-tests.xml').write_text('<testsuites><testsuite><testcase name="one"/><testcase name="two"/></testsuite></testsuites>')
                proof={'browserOptIn':True,'exitCode':0,'tests':{'failure':0,'error':0,'skipped':0,'passed':6},'isolatedContainerRemoved':True,'codeSHA':'wrong-sha','runId':'old-run'}
                if case=='empty':proof['tests']['passed']=0
                if case=='one-skip':proof['tests']['skipped']=1
                Path('.work/vf-desktop-browser-ci.json').write_text(json.dumps(proof))
                try:exec(compile(gate,workflow,'exec'),{});outcome='accept'
                except (AssertionError,KeyError,ValueError):outcome='reject'
                results.append({'gate':workflow,'case':case if workflow!='desktop-browser' else {'empty':'zero-browser','one-pass':'six-passes-wrong-sha-old-run','one-skip':'browser-skip'}[case],'gateOutcome':outcome,'scope':'gate only; prior workflow steps not simulated'})
                os.chdir(original_cwd)
    with tempfile.TemporaryDirectory(prefix='node-selection-audit-') as folder:
        suite=Path(folder)
        for name,code in {'test_node_runtime':'', 'test_direct':'from test_node_runtime import node_runtime', 'test_transitive':'from test_direct import node_runtime','test_independent':'def test_x(): pass'}.items():(suite/(name+'.py')).write_text(code)
        with patch.object(selection,'SUITE',suite):normal=selection.dependents()
        (suite/'test_node_runtime.py').unlink()
        with patch.object(selection,'SUITE',suite):missing=selection.dependents()
        results.append({'selectionDirectTransitive':normal,'missingRoot':missing,'scope':'synthetic flat imports; not an actual missing root in repository'})
finally:os.chdir(original_cwd)
OUTPUT.write_text(json.dumps({'baseSHA':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'scope':'offline actual main with fake external boundaries, and extracted workflow gates; not CI execution','results':results},indent=2)+'\n')
print(json.dumps(results,indent=2))
