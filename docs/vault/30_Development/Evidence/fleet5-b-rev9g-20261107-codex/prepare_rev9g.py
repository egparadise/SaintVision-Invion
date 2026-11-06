"""Unique Rev9g input preparation: original review blobs and Root read-only docs."""
import datetime,hashlib,json,subprocess,sys
from pathlib import Path
E=Path(__file__).resolve().parent;R=next(p for p in E.parents if (p/'AGENTS.md').exists());OLD=E.parent/'fleet5-b-rev9f-20261107-codex';V=Path('D:/Project/SaintVisionI-Invion/fleet-five-orchestration-20261105/docs/vault')
BASE='9cea33e8a087981fdedcddb71c4381bdc25c1507';REVIEW='ce713a85fc428198468ea078c2fef035ac704ba8'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=R)
def main():
    sys.stdout.reconfigure(encoding='utf8');assert not (E/'input-receipts.json').exists();assert git('rev-parse','HEAD').decode().strip()==BASE
    prior=json.loads((OLD/'input-receipts.json').read_bytes());old_manifest=json.loads((OLD/'proof-producer-hashes.json').read_bytes());reads=[]
    for row in prior['docs']:
        rel=row['path'];p=V/rel.removeprefix('ROOT_READ_ONLY/docs/vault/') if rel.startswith('ROOT_READ_ONLY/') else R/rel
        s=p.read_text('utf-8-sig');reads.append({'path':rel,'sha256':sha(p),'frontmatter':s.split('---',2)[1].strip() if s.startswith('---') else None});print(rel+'\n'+s[:1400])
    for p in OLD.iterdir():
        if p.suffix=='.py' or p.name.endswith('.py.txt') or p.name=='.gitattributes':(E/p.name).write_bytes(p.read_bytes())
    for row in old_manifest['originalReviewCopiesVerified']:
        p=OLD/row['file'];assert sha(p)==row['sha256'];(E/p.name).write_bytes(p.read_bytes())
    (E/'prior-input-receipts.json').write_bytes((OLD/'input-receipts.json').read_bytes())
    paths=[p for p in git('diff-tree','--no-commit-id','--name-only','-z','-r',REVIEW).decode('utf8').split(chr(0)) if p];assert len(paths)==13;copies=[]
    for p in paths:
        name='rev9f-review-'+(p.rsplit('/',1)[-1] if '/Evidence/' in p else 'original-history.md.txt')
        if p.endswith('/.gitattributes'):name='rev9f-review-original-gitattributes.txt'
        raw=git('show',REVIEW+':'+p);(E/name).write_bytes(raw);copies.append({'commit':REVIEW,'objectID':git('rev-parse',REVIEW+':'+p).decode().strip(),'path':p,'copy':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
    retained=list(prior['immutableRetained']);accounting=[]
    for n in ('targeted-category-delta.json','writer-census-delta.json','reader-io-catalog.json','authority-matrix.json','contract.schema.json','pilot-closure.json'):
        p=OLD/n;(E/n).write_bytes(p.read_bytes());row={'path':p.relative_to(R).as_posix(),'file':n,'sha256':sha(p),'bytes':p.stat().st_size};accounting.append(row);retained.append(row)
    for n in ('model.py','lifecycle.py','proof-producer-hashes.json','t1-mark-offline-closure.json','producer-order.json','pending-interface-contracts.json','pending-obligations.json','proof-final01.json','docs-final01.json','rev9f-current-verification.json','rev9f-gap-results.json','rev9f-unit-results.json','development-failures.json'):
        p=OLD/n;retained.append({'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size})
    d={'task':'FLEET5-B-REV9G-FIX-ONLY-20261107','orcaTask':'task_a8fd2969f0b3','dispatch':'ctx_6f0f8253b8a7','owner':'Codex','reviewer':'Actual independent narrow Claude Rev9g delta through Root PENDING','rootMessage':'msg_6a4d15e35b3e','base':BASE,'branch':'agent/codex/fleet5-b-rev9g-20261107','productSource':'72028cbac903c4415d9979f980a6e0f9948e914f','rootHeadAtRead':subprocess.check_output(['git','-C',str(V.parents[1]),'rev-parse','HEAD']).decode().strip(),'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'docs':reads,'actualPriorReview':copies,'immutableRetained':retained,'accountingBaseline':accounting,'modelLifecycleFrozen':prior['modelLifecycleFrozen'],'scope':'Only B9f-L1 starred positional import identity/importlib.__import__ parity and B9f-L2 precise frozen caller binding-event multisets for imported Name callees; actual3 full-provenance cases +2 binder-only; no general resolver/heap/nonlocal/product/runtime/A7 grant','actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING'}
    (E/'input-receipts.json').write_bytes((json.dumps(d,indent=2)+'\n').encode());(E/'development-failures.json').write_bytes(b'{"events": []}\n');print(json.dumps({'actualReviewOriginals':len(copies),'inheritedRawCopies':len(old_manifest['originalReviewCopiesVerified']),'boards':reads[:2],'root':d['rootHeadAtRead']}))
if __name__=='__main__':main()
