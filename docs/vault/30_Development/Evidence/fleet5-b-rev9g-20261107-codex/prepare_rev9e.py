"""One-time Rev9e preparation: read-only Root docs and exact actual review bytes."""
import datetime,hashlib,json,subprocess,sys
from pathlib import Path
E=Path(__file__).resolve().parent;R=next(p for p in E.parents if (p/'AGENTS.md').exists())
OLD=E.parent/'fleet5-b-rev9d-20261107-codex';V=Path('D:/Project/SaintVisionI-Invion/fleet-five-orchestration-20261105/docs/vault')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    sys.stdout.reconfigure(encoding='utf-8')
    assert not (E/'input-receipts.json').exists()
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R).decode().strip()=='54549b90774aab3599c0486a5217d0d1634baca8'
    prior=json.loads((OLD/'input-receipts.json').read_bytes());reads=[]
    for row in prior['docs']:
        rel=row['path'];p=V/rel.removeprefix('ROOT_READ_ONLY/docs/vault/') if rel.startswith('ROOT_READ_ONLY/') else R/rel
        s=p.read_text('utf-8-sig');front=s.split('---',2)[1].strip() if s.startswith('---') else None
        reads.append({'path':rel,'sha256':sha(p),'frontmatter':front});print(rel+'\n'+s[:1800])
    for p in OLD.iterdir():
        if p.name=='prepare_rev9e.py':continue
        if p.suffix=='.py' or p.name.endswith('.py.txt') or p.name.startswith(('prior-','rev9-review-','rev9b-review-','rev9c-review-')) or p.name=='.gitattributes':(E/p.name).write_bytes(p.read_bytes())
    (E/'prior-input-receipts.json').write_bytes((OLD/'input-receipts.json').read_bytes())
    review='9266f719fe97f41b9b4ba38cee4a963a3c1218dc';prefix='docs/vault/30_Development/Evidence/fleet5-b-rev9d-545-review-20261107-claude/';copies=[]
    paths=subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-z','-r',review],cwd=R).decode('utf8').split(chr(0))
    for p in paths:
        if not p.startswith(prefix) or p.endswith('.gitattributes'):continue
        raw=subprocess.check_output(['git','show',review+':'+p],cwd=R);name='rev9d-review-'+p[len(prefix):];(E/name).write_bytes(raw)
        copies.append({'commit':review,'path':p,'copy':name,'sha256':hashlib.sha256(raw).hexdigest()})
    accounting=[];retained=list(prior['immutableRetained'])
    for n in ('targeted-category-delta.json','writer-census-delta.json','reader-io-catalog.json','authority-matrix.json','contract.schema.json','pilot-closure.json'):
        p=OLD/n;(E/n).write_bytes(p.read_bytes());row={'path':p.relative_to(R).as_posix(),'file':n,'sha256':sha(p),'bytes':p.stat().st_size};accounting.append(row);retained.append(row)
    for n in ('model.py','lifecycle.py','t1-mark-offline-closure.json','proof-producer-hashes.json','producer-order.json','pending-interface-contracts.json','deterministic-generation-results.json','rev9d-regression-results.json','proof-checks.json','publication-gates.json','completed-regression-source-seal.json'):
        p=OLD/n;retained.append({'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size})
    data={'task':'FLEET5-B-REV9E-FIX-ONLY-20261107','orcaTask':'task_a8fd2969f0b3','dispatch':'ctx_6f0f8253b8a7','owner':'Codex','reviewer':'Independent Claude through Root PENDING','rootMessage':'msg_533819c42490','base':'54549b90774aab3599c0486a5217d0d1634baca8','productSource':'72028cbac903c4415d9979f980a6e0f9948e914f','rootHeadAtRead':subprocess.check_output(['git','-C',str(V.parents[1]),'rev-parse','HEAD']).decode().strip(),'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'docs':reads,'actualPriorReview':copies,'immutableRetained':retained,'accountingBaseline':accounting,'modelLifecycleFrozen':prior['modelLifecycleFrozen'],'scope':'Rev9e FIX-ONLY B9d-L1 enumerated nonliteral reflection keys and B9d-L2 callable/class construction authentication; bounded fixed-point I1 correction and targeted six causal regressions/benign controls. Prior broad suites retained by hash. No model/product/runtime/A7 changes.','actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING'}
    (E/'input-receipts.json').write_bytes((json.dumps(data,indent=2)+'\n').encode())
    (E/'development-failures.json').write_bytes((json.dumps({'scope':'Rev9e own static checks only','events':[{'stage':'prepare_rev9e.py first invocation','exit':1,'reason':'Console cp949 cannot encode Root document U+2013; no input receipts/copies written before failure','fix':'stdout explicitly UTF-8; same guarded one-time preparation rerun'}]},indent=2)+'\n').encode())
    print(json.dumps({'boards':reads[:2],'reviewCopies':len(copies),'immutableFiles':len(retained)}))
if __name__=='__main__':main()
