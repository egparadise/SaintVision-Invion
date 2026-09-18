"""Original CLI/report boundaries, synthetic rehearsals, no database or Docker."""
import contextlib,importlib,io,json,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(sys.argv[1]).resolve();OUT=Path(sys.argv[2]).resolve()
for rel in ['src','services/control-plane/src','tools']:sys.path.insert(0,str(ROOT/rel))
lan=importlib.import_module('rehearse_lan_upgrade')
independent=importlib.import_module('rehearse_independent_restore')
readiness=importlib.import_module('operational_readiness')
storage=importlib.import_module('storage_check')
from saintvision.storage.readroot import ReadRoot
results=[]
with tempfile.TemporaryDirectory(prefix='sv-evidence-audit-') as folder:
    root=Path(folder);output=root/'report.json'
    old='{"oldRun":true,"restoreExactRows":true}\n';output.write_text(old)
    with patch.object(sys,'argv',['runner','--state',str(root),'--output',str(output)]),patch.object(lan,'rehearse',side_effect=RuntimeError('injected current rehearsal failure')),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
        code=lan.main()
    assert code==2 and output.read_text()==old
    results.append({'case':'lan-failed-reuse','exitCode':code,'oldSuccessfulReportUnchanged':True,'scope':'nonzero preserved; no downstream false acceptance demonstrated'})
    with patch.object(sys,'argv',['runner','--backup',str(root),'--expected-sha256','0'*64,'--output',str(output)]),patch.object(independent,'rehearse') as run,contextlib.redirect_stderr(io.StringIO()):
        try: independent.main()
        except SystemExit as exc: code=exc.code
        else: raise AssertionError('existing report accepted')
    assert code==2 and not run.called and output.read_text()==old
    results.append({'case':'independent-existing-report','exitCode':code,'rehearsalCalled':False})
    outcome=storage._check_one(SimpleNamespace(normalized_path=str(root)),[],32,allowed_root=ReadRoot(root))
    assert outcome['sampleHealthy'] is False and outcome['sampled']==0
    results.append({'case':'storage-empty-sample','sampleHealthy':False,'sampled':0})
for complete in [False,True]:
    code=readiness._exit_code({'absent':[],'offerAgreement':{'disagreeing':[]},'acceptanceEvidence':{'evidenceComplete':complete}})
    assert code==(0 if complete else 1)
    results.append({'case':'readiness-catalog-gate','syntheticEvidenceComplete':complete,'exitCode':code,'scope':'record completeness, not physical recovery'})
OUT.write_text(json.dumps({'scope':'offline original functions; synthetic rehearsal/record data; no operational acceptance','results':results},indent=2)+'\n')
print(json.dumps(results,indent=2))
