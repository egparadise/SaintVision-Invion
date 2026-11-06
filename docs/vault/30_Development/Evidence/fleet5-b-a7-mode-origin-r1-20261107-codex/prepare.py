"""Finite card inputs and immutable review origins, no product execution."""
import datetime,hashlib,json,subprocess,sys
from pathlib import Path
E=Path(__file__).resolve().parent;R=next(p for p in E.parents if (p/'AGENTS.md').exists());OLD=E.parent/'fleet5-b-a7-snapshot-r2-20261107-codex';V=Path('D:/Project/SaintVisionI-Invion/fleet-five-orchestration-20261105/docs/vault');BASE='969030dbc7716b9cadf75bd314713005306ed34c';REVIEW='145238898e8c86e1beb091b93efd712c70a6f5ba'
def git(*args):return subprocess.check_output(['git',*args],cwd=R)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
    sys.stdout.reconfigure(encoding='utf8');assert git('rev-parse','HEAD').decode().strip()==BASE;assert not (E/'inputs.json').exists();docs=[]
    for row in json.loads((OLD/'input-receipts.json').read_bytes())['docs']:
        rel=row['path'];p=V/rel.removeprefix('ROOT_READ_ONLY/docs/vault/') if rel.startswith('ROOT_READ_ONLY/') else R/rel;raw=p.read_bytes();s=raw.decode('utf-8-sig');fm=s.split('---',2)[1].strip() if s.startswith('---') else None;docs.append({'path':rel,'sha256':sha(raw),'frontmatter':fm})
    originals=[]
    for p in git('diff-tree','--no-commit-id','--name-only','-z','-r',REVIEW).decode('utf8').split(chr(0))[:-1]:
        name='review-'+(p.rsplit('/',1)[-1] if '/Evidence/' in p else 'original-history.md.txt')
        if p.endswith('/.gitattributes'):name='review-original-gitattributes.txt'
        raw=git('show',REVIEW+':'+p);(E/name).write_bytes(raw);originals.append({'commit':REVIEW,'path':p,'copy':name,'objectID':git('rev-parse',REVIEW+':'+p).decode().strip(),'sha256':sha(raw)})
    assert len(originals)==11;retained=[]
    names=['a7_body.py','a7_inventory.py','a7-snapshot-sidecar.json','proof-producer-hashes.json','development-failures.json','targeted-category-delta.json','writer-census-delta.json','reader-io-catalog.json','authority-matrix.json','contract.schema.json','pilot-closure.json','model.py','lifecycle.py','pending-interface-contracts.stage1.json','pending-interface-contracts.json','producer-order.json']
    for name in names:
        p=OLD/name;retained.append({'path':p.relative_to(R).as_posix(),'sha256':sha(p.read_bytes()),'objectID':git('rev-parse',BASE+':'+p.relative_to(R).as_posix()).decode().strip()})
    data={'task':'FLEET5-B-A7-MODE-ORIGIN-R1-20261107','orcaTask':'task_a8fd2969f0b3','dispatch':'ctx_6f0f8253b8a7','owner':'Codex','reviewer':'Independent mode-origin review through Root PENDING','rootMessage':'msg_ec880f3ed724','base':BASE,'branch':'agent/codex/fleet5-b-a7-mode-origin-r1-20261107','productSource':'72028cbac903c4415d9979f980a6e0f9948e914f','kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'rootHeadAtRead':git('-C',str(V.parents[1]),'rev-parse','HEAD').decode().strip(),'docs':docs,'reviewOriginals':originals,'immutablePredecessor':retained,'scope':'ONE NodeDelivery snapshot A7_PURPOSE_PROVENANCE auxiliary source candidate and minimal future predicate proposal; no baseline discharge or product delta','actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING'}
    (E/'inputs.json').write_bytes((json.dumps(data,indent=2)+'\n').encode());(E/'.gitattributes').write_bytes(b'* -text\n*.log binary\n*.txt binary\n');print(json.dumps({'reviewOriginals':11,'rootHead':data['rootHeadAtRead'],'kst':data['kst'],'boards':[r['frontmatter'] for r in docs[:2]]}))
if __name__=='__main__':main()
