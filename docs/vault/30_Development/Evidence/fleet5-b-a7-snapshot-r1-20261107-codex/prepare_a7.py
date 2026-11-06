"""Prepare only A7 static-proof dependencies and immutable read receipts."""
import ast,datetime,hashlib,json,subprocess,sys
from pathlib import Path
E=Path(__file__).resolve().parent;R=next(p for p in E.parents if (p/'AGENTS.md').exists());OLD=E.parent/'fleet5-b-rev9g-20261107-codex';V=Path('D:/Project/SaintVisionI-Invion/fleet-five-orchestration-20261105/docs/vault')
BASE='0e66b5ab2b5fbc131dd6e98f5d5e8930ac045148';REVIEW='90cccfb34718a8bb375bd7c1b7e06beb49670823'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=R)
def main():
    sys.stdout.reconfigure(encoding='utf8');assert not (E/'input-receipts.json').exists();assert git('rev-parse','HEAD').decode().strip()==BASE
    prior=json.loads((OLD/'input-receipts.json').read_bytes());reads=[]
    for row in prior['docs']:
        rel=row['path'];p=V/rel.removeprefix('ROOT_READ_ONLY/docs/vault/') if rel.startswith('ROOT_READ_ONLY/') else R/rel
        s=p.read_text('utf-8-sig');reads.append({'path':rel,'sha256':sha(p),'frontmatter':s.split('---',2)[1].strip() if s.startswith('---') else None});print(rel+'\n'+s[:1100])
    modules={'source_bindings','reflection_audit','lexical_bindings','callee_identity','call_binding','parameter_flow','owner_transfer','use_sites','t1_provenance','analysis_rules','bounded_analysis','constructor_graph','forwarding_discovery','pending_contracts','edge_categories','measured_run'};seen=set()
    while modules-seen:
        name=sorted(modules-seen)[0];seen.add(name);p=OLD/(name+'.py');tree=ast.parse(p.read_bytes());(E/p.name).write_bytes(p.read_bytes())
        for n in ast.walk(tree):
            names=[a.name.split('.')[0] for a in n.names] if isinstance(n,ast.Import) else [n.module.split('.')[0]] if isinstance(n,ast.ImportFrom) and n.module else []
            modules.update(x for x in names if (OLD/(x+'.py')).exists())
    (E/'.gitattributes').write_bytes((OLD/'.gitattributes').read_bytes());copies=[]
    paths=[p for p in git('diff-tree','--no-commit-id','--name-only','-z','-r',REVIEW).decode('utf8').split(chr(0)) if p];assert len(paths)==19
    for p in paths:
        name='accepted-review-'+(p.rsplit('/',1)[-1] if '/Evidence/' in p else 'original-history.md.txt')
        if p.endswith('/.gitattributes'):name='accepted-review-original-gitattributes.txt'
        raw=git('show',REVIEW+':'+p);(E/name).write_bytes(raw);copies.append({'commit':REVIEW,'objectID':git('rev-parse',REVIEW+':'+p).decode().strip(),'path':p,'copy':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
    retained=[];accounting=[]
    for n in ('targeted-category-delta.json','writer-census-delta.json','reader-io-catalog.json','authority-matrix.json','contract.schema.json','pilot-closure.json','model.py','lifecycle.py','pending-interface-contracts.stage1.json','pending-interface-contracts.json','producer-order.json'):
        p=OLD/n;(E/n).write_bytes(p.read_bytes());row={'path':p.relative_to(R).as_posix(),'copy':n,'sha256':sha(p),'bytes':p.stat().st_size};retained.append(row)
        if n in ('targeted-category-delta.json','writer-census-delta.json','reader-io-catalog.json','authority-matrix.json','contract.schema.json','pilot-closure.json'):accounting.append(row)
    for n in ('proof-producer-hashes.json','t1-mark-offline-closure.json','proof-final01.json','docs-final01.json','rev9g-current-verification.json','input-receipts.json'):
        p=OLD/n;retained.append({'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size})
    d={'task':'FLEET5-B-A7-SNAPSHOT-R1-20261107','orcaTask':'task_a8fd2969f0b3','dispatch':'ctx_6f0f8253b8a7','owner':'Codex','reviewer':'Independent A7 static review through Root PENDING after D04 reviewer exit/release','rootMessage':'msg_35937c8787d1','base':BASE,'branch':'agent/codex/fleet5-b-a7-snapshot-r1-20261107','productSource':'72028cbac903c4415d9979f980a6e0f9948e914f','rootHeadAtRead':subprocess.check_output(['git','-C',str(V.parents[1]),'rev-parse','HEAD']).decode().strip(),'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'docs':reads,'actualAcceptedReview':copies,'copiedProducerClosure':sorted(seen),'immutableRetained':retained,'accountingFrozen':accounting,'modelLifecycleFrozen':prior['modelLifecycleFrozen'],'scope':'NodeChannels.snapshot ONLY, necessary containment/proof/assert_channel/import/caller/DB ownership closure; sidecar only, explicit unresolved obligations when closure is not proven; no product/runtime/port/NodeDelivery.deliver grant','actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING'}
    (E/'input-receipts.json').write_bytes((json.dumps(d,indent=2)+'\n').encode());(E/'development-failures.json').write_bytes(b'{"events": []}\n');print(json.dumps({'producerModules':len(seen),'reviewOriginals':len(copies),'boards':reads[:2],'root':d['rootHeadAtRead']}))
if __name__=='__main__':main()
