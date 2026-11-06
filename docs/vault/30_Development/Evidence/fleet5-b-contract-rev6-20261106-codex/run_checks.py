"""Sequential local proof/docs checks with exact exits and raw log digests."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

E=Path(__file__).resolve().parent
ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())


def checks(kind,commands):
    results=[]
    for i,(args,expected) in enumerate(commands,1):
        cmd=[sys.executable,'-B',*map(str,args)]
        run=subprocess.run(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        log=E/(kind+'-'+str(i)+'.log');log.write_bytes(run.stdout)
        result=dict(command=cmd,expectedExit=expected,actualExit=run.returncode,
                    log=log.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(run.stdout).hexdigest())
        results.append(result)
        (E/(kind+'.json')).write_bytes((json.dumps(dict(recordedAtKST=datetime.now(timezone(timedelta(hours=9))).isoformat(),
             checks=results,obsidianApply=False,productionChanges=False),indent=2)+'\n').encode())
        print(json.dumps(result),flush=True)
        if run.returncode!=expected:raise SystemExit(run.returncode or 1)


if __name__=='__main__':
    if '--source' in sys.argv:
        checks('source-checks',[([E/'source_analysis.py'],0),([E/'reconcile.py'],0),([E/'source_fixtures.py'],0)])
    elif '--publication' in sys.argv:
        checks('publication-gates', [([p,*extra],0) for p,extra in [
            ('tools/check_docs.py',[]),('tools/check_ontology.py',[]),('tools/sync_obsidian.py',['--check']),
            ('tools/check_contract_bindings.py',[]),('tools/check_frontend_integrity.py',[]),
            ('tools/check_doc_single_source.py',['--ratchet']),('tools/check_response_freshness.py',[]),
            ('tools/check_doc_path_citations.py',['--ratchet','--base-ref','228e2a2062d8a64bce7f772f668da7df2fd2ac0d'])]])
    else:
        checks('proof-checks', [([E/'schema.py'],0),([E/'authority.py'],0),([E/'fixtures.py'],0),
            ([E/'reconcile.py'],0),([E/'link_plans.py'],0),(['tests/proofs/fleet5_compute_storage_contract_probe.py'],0),
            (['tests/proofs/fleet5_compute_storage_contract_probe.py','--require-coexistence'],1)])
