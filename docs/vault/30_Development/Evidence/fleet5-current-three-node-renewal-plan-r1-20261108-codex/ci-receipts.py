"""GitHub CLI receipts only; never executes product or tests locally."""
import datetime
import json
from pathlib import Path
import subprocess
import sys
import uuid
HERE = Path(__file__).resolve().parent
REPO = 'egparadise/SaintVision-Invion'
BRANCH = 'agent/codex/fleet5-current-three-node-renewal-plan-r1-20261108'
def run(argv):
    p = subprocess.run(argv, capture_output=True)
    if p.returncode:
        raise RuntimeError(f'{argv[:3]} exit {p.returncode}: {p.stderr.decode("utf8",errors="replace")[:1000]}')
    return p.stdout
def write(name, value):
    (HERE/name).write_text(json.dumps(value, indent=2, ensure_ascii=True)+'\n', encoding='utf8')
if sys.argv[1] == 'dispatch':
    sha = run(['git','rev-parse','HEAD']).decode().strip()
    assert sha == run(['git','ls-remote','origin','refs/heads/'+BRANCH]).decode().split()[0]
    records = []
    for workflow in ['docs']:
        correlation = 'fleet5-current-three-node-renewal-plan-'+workflow+'-'+uuid.uuid4().hex
        entry = dict(workflow=workflow, sourceSHA=sha, ref=BRANCH, correlation=correlation,
                     atUTC=datetime.datetime.now(datetime.timezone.utc).isoformat(), dispatchExit=None)
        records.append(entry);write('ci-dispatch-'+sha[:12]+'.json', records)
        run(['gh','workflow','run',workflow+'.yml','--repo',REPO,'--ref',BRANCH,'-f','correlation_id='+correlation])
        entry['dispatchExit'] = 0;write('ci-dispatch-'+sha[:12]+'.json', records)
        print(json.dumps(entry), flush=True)
elif sys.argv[1] == 'observe':
    path = Path(sys.argv[2]); records = json.loads(path.read_text('utf8'))
    for entry in records:
        raw = json.loads(run(['gh','api','-X','GET',f'repos/{REPO}/actions/workflows/{entry["workflow"]}.yml/runs',
                '-f','branch='+BRANCH,'-f','event=workflow_dispatch','-f','per_page=50']))
        matches = [r for r in raw['workflow_runs'] if r['display_title']==entry['correlation']]
        assert len(matches) <= 1
        if not matches:
            print(entry['workflow'],'not registered yet',flush=True);continue
        result = matches[0]
        assert result['head_sha']==entry['sourceSHA'] and result['head_branch']==BRANCH
        assert result['event']=='workflow_dispatch' and result['run_attempt']==1
        entry['runID']=result['id']
        jobs = json.loads(run(['gh','api','-X','GET',f'repos/{REPO}/actions/runs/{result["id"]}/jobs','-f','per_page=100']))
        artifacts = json.loads(run(['gh','api',f'repos/{REPO}/actions/runs/{result["id"]}/artifacts']))
        prefix='ci-'+entry['sourceSHA'][:12]+'-'+entry['workflow']
        write(prefix+'-run.json',result);write(prefix+'-jobs.json',jobs);write(prefix+'-artifacts.json',artifacts)
        print(json.dumps(dict(workflow=entry['workflow'],runID=result['id'],sourceSHA=result['head_sha'],status=result['status'],conclusion=result['conclusion'],
            jobs=[dict(id=j['id'],name=j['name'],conclusion=j['conclusion'],status=j['status'],failedSteps=[s['name'] for s in j['steps'] if s['conclusion']=='failure']) for j in jobs['jobs']],
            artifacts=[dict(id=a['id'],name=a['name'],digest=a.get('digest')) for a in artifacts['artifacts']])),flush=True)
    write(path.name,records)
else: raise ValueError('dispatch or observe only')
