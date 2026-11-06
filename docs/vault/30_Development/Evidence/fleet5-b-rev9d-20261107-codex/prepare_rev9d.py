"""One-time unique Rev9d input preparation; prior inputs and Root vault read only."""
import datetime,hashlib,json,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent;R=next(p for p in E.parents if (p/'AGENTS.md').exists())
OLD=E.parent/'fleet5-b-rev9c-20261106-codex';V=Path('D:/Project/SaintVisionI-Invion/fleet-five-orchestration-20261105/docs/vault')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert not (E/'input-receipts.json').exists(),'One-time preparation already completed'
    prior=json.loads((OLD/'input-receipts.json').read_bytes());reads=[]
    for row in prior['docs']:
        rel=row['path'];p=V/rel.removeprefix('ROOT_READ_ONLY/docs/vault/') if rel.startswith('ROOT_READ_ONLY/') else R/rel
        b=p.read_bytes();s=b.decode('utf-8-sig');reads.append({'path':rel,'sha256':sha(p),'frontmatter':s.split('---',2)[1].strip() if s.startswith('---') else None})
    for p in OLD.iterdir():
        if p.suffix=='.py' or p.name.endswith('.py.txt') or p.name.startswith(('prior-','rev9-review-','rev9b-review-')) or p.name=='.gitattributes':(E/p.name).write_bytes(p.read_bytes())
    (E/'prior-input-receipts.json').write_bytes((OLD/'input-receipts.json').read_bytes())
    review='4288a1c403bc15ac1174c49e512ab8c7314d522f';prefix='docs/vault/30_Development/Evidence/fleet5-b-rev9c-5ea-review-20261106-claude/';copies=[]
    paths=subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-z','-r',review],cwd=R).decode('utf8').split(chr(0))
    for p in paths:
        if not p.startswith(prefix) or p.endswith('.gitattributes'):continue
        raw=subprocess.check_output(['git','show',review+':'+p],cwd=R);name='rev9c-review-'+p[len(prefix):];(E/name).write_bytes(raw);copies.append({'commit':review,'path':p,'copy':name,'sha256':hashlib.sha256(raw).hexdigest()})
    accounting=[];retained=list(prior['immutableRetained'])
    for n in ('targeted-category-delta.json','writer-census-delta.json','reader-io-catalog.json','authority-matrix.json','contract.schema.json','pilot-closure.json'):
        p=OLD/n;row={'path':p.relative_to(R).as_posix(),'file':n,'sha256':sha(p),'bytes':p.stat().st_size};accounting.append(row);retained.append(row)
    for n in ('model.py','lifecycle.py','t1-mark-offline-closure.json','proof-producer-hashes.json','producer-order.json','pending-interface-contracts.json','deterministic-generation-results.json','rev9c-regression-results.json'):
        p=OLD/n;retained.append({'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size})
    data={'task':'FLEET5-B-REV9D-FIX-ONLY-20261107','orcaTask':'task_a8fd2969f0b3','dispatch':'ctx_6f0f8253b8a7','owner':'Codex','reviewer':'Actual independent narrow Claude Rev9d delta through Root PENDING','rootMessage':'msg_1a4f33b7e3e6','base':'5ea87937f1b542f8cbe32c08dc224526965a8e2d','productSource':'72028cbac903c4415d9979f980a6e0f9948e914f','rootHeadAtRead':subprocess.check_output(['git','-C',str(V.parents[1]),'rev-parse','HEAD']).decode().strip(),'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'docs':reads,'actualPriorReview':copies,'immutableRetained':retained,'accountingBaseline':accounting,'modelLifecycleFrozen':prior['modelLifecycleFrozen'],'scope':'Rev9d only: universe-wide enumerated reflection auditing, interprocedural parameter ownership fixed point and targeted fixtures; optional bounded dotted strings and keyword binder; new machine-readable future tenant-epoch obligation. No model/product/runtime/A7 changes.','actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING'}
    (E/'input-receipts.json').write_bytes((json.dumps(data,indent=2)+'\n').encode())
    (E/'development-failures.json').write_bytes((json.dumps({'scope':'Rev9d own preparation/static checks only','events':[]},indent=2)+'\n').encode())
    print(json.dumps({'boards':reads[:2],'reviewCopies':len(copies),'immutableFiles':len(retained),'accountingBaselineFiles':len(accounting)}))
if __name__=='__main__':main()
