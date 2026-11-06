"""R2 setup: only own new Evidence, immutable originals and read receipts."""
import datetime,hashlib,json,subprocess,sys
from pathlib import Path
E=Path(__file__).resolve().parent;R=next(p for p in E.parents if (p/'AGENTS.md').exists());OLD=E.parent/'fleet5-b-a7-snapshot-r1-20261107-codex';V=Path('D:/Project/SaintVisionI-Invion/fleet-five-orchestration-20261105/docs/vault')
BASE='1550453d1f072a87fd9a7baa53d4fe4ce8a98d5d';REVIEW='7a8012f47de5aa94a4264366df6722c1f6755a9c'
def git(*args):return subprocess.check_output(['git',*args],cwd=R)
def h(raw):return hashlib.sha256(raw).hexdigest()
def emit(name,data):(E/name).write_bytes((json.dumps(data,indent=2)+'\n').encode())
def main():
    sys.stdout.reconfigure(encoding='utf8');assert git('rev-parse','HEAD').decode().strip()==BASE;assert not (E/'input-receipts.json').exists()
    prior=json.loads((OLD/'input-receipts.json').read_bytes());docs=[]
    for row in prior['docs']:
        rel=row['path'];p=V/rel.removeprefix('ROOT_READ_ONLY/docs/vault/') if rel.startswith('ROOT_READ_ONLY/') else R/rel
        raw=p.read_bytes();s=raw.decode('utf-8-sig');fm=s.split('---',2)[1].strip() if s.startswith('---') else None;docs.append({'path':rel,'sha256':h(raw),'frontmatter':fm});print(json.dumps({'doc':rel,'frontmatter':fm},ensure_ascii=False))
    modules=prior['copiedProducerClosure']+['a7_common','a7_body','a7_inventory','a7_build','a7_record','model','lifecycle'];copied=[]
    for name in sorted(set(modules)):
        p=OLD/(name+'.py');raw=p.read_bytes();(E/p.name).write_bytes(raw);copied.append({'path':p.relative_to(R).as_posix(),'copy':p.name,'sha256':h(raw)})
    (E/'.gitattributes').write_bytes((OLD/'.gitattributes').read_bytes());originals=[]
    paths=git('diff-tree','--no-commit-id','--name-only','-z','-r',REVIEW).decode('utf8').split(chr(0))[:-1];assert len(paths)==10
    for p in paths:
        name='actual-review-'+(p.rsplit('/',1)[-1] if '/Evidence/' in p else 'original-history.md.txt')
        if p.endswith('/.gitattributes'):name='actual-review-original-gitattributes.txt'
        raw=git('show',REVIEW+':'+p);(E/name).write_bytes(raw);originals.append({'commit':REVIEW,'path':p,'copy':name,'objectID':git('rev-parse',REVIEW+':'+p).decode().strip(),'sha256':h(raw),'bytes':len(raw)})
    retained=[]
    for row in prior['immutableRetained']:
        if 'copy' not in row:continue
        name=row['copy'];raw=(OLD/name).read_bytes();(E/name).write_bytes(raw);retained.append({'path':(OLD/name).relative_to(R).as_posix(),'copy':name,'sha256':h(raw)})
    history=[]
    for name in ('development-failures.json','dev02-tests.log','dev03-tests.log','a7_tests.py','a7-test-results.json','input-receipts.json','a7-snapshot-sidecar.json','proof-producer-hashes.json'):
        raw=(OLD/name).read_bytes();copy='r1-'+name+('.txt' if name.endswith('.py') else '');(E/copy).write_bytes(raw);history.append({'path':(OLD/name).relative_to(R).as_posix(),'copy':copy,'sha256':h(raw),'scope':'HISTORICAL_NOT_NEW_EXECUTED_CASES'})
    root=git('-C',str(V.parents[1]),'rev-parse','HEAD').decode().strip()
    emit('input-receipts.json',{'task':'FLEET5-B-A7-SNAPSHOT-R2-20261107','orcaTask':'task_a8fd2969f0b3','dispatch':'ctx_6f0f8253b8a7','owner':'Codex','reviewer':'Actual independent narrow A7R2 delta through Root PENDING after D04 CODE reviewer exit/release','rootMessage':'msg_e051a19e0010','base':BASE,'branch':'agent/codex/fleet5-b-a7-snapshot-r2-20261107','productSource':'72028cbac903c4415d9979f980a6e0f9948e914f','kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'rootHeadAtRead':root,'docs':docs,'actualReview':originals,'reviewVerdict':'LOW-only REVISION_REQUIRED A7R-L1; other conditional body proof and honest 19HOLD preserved; INFO I1-I4, no HIGH/MEDIUM','copiedProducerClosure':copied,'immutableRetained':retained,'modelLifecycleFrozen':prior['modelLifecycleFrozen'],'priorHistoryCopies':history,'actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING','scope':'Existing guard coverage on EVERY parsed lexical candidate before call-retention filter; exact reviewer source regression and complete baseline delta oracle; no predicate/resolver/body/product/port change'})
    emit('development-failures.json',{'events':[{'stage':'preparation','firstCommandExit':1,'firstToolChunk':'ecdccb','cause':'LookupError unknown encoding utf8-sig before any module copies or source proofs','unchangedRecordedReproduction':'prepare-attempt02.log','reproductionExit':1,'correction':'canonical codec spelling utf-8-sig; fresh preparation after correction','qualification':'harness preparation failure, not a product semantic refusal'}],'priorFailuresPreserved':'r1-development-failures.json and raw dev02/dev03 logs; original review INFO/invalid preconditions retained separately'})
    print(json.dumps({'copiedModules':len(copied),'reviewOriginals':len(originals),'rootHead':root,'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()}))
if __name__=='__main__':main()
