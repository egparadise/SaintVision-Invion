"""Read-only expanded Git-object static census; never imports application code.

Conservative same-name method edges are reported as candidates, not claimed
runtime reachability. Every candidate ORM method is recorded on every receiver.
"""
from pathlib import Path
import ast
import collections
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile

E=Path(__file__).resolve().parent
ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
BASE='72028cbac903c4415d9979f980a6e0f9948e914f'
DB={'execute','executemany','execute_values','query','scalar','scalars','refresh','merge','copy','with_for_update','get','add','add_all','flush','delete','bulk_save_objects','bulk_insert_mappings','bulk_update_mappings'}
HELPERS={'lock_run','lock_resources','require_execution'}
TABLES=re.compile(r'\b(?:inv\.|public\.)?(?:nodes|node_channels|storage_contributions|control_epoch|tenant_controls|runs|operator_grants|resource_claims|claims)\b')


def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)


def load_sources():
    names=[p for p in git('ls-tree','-r','--name-only',BASE).decode('utf-8').splitlines() if p.endswith('.py') and not p.startswith(('docs/','tests/')) and '/tests/' not in p]
    raw=git('archive',BASE,*names)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        return {p:archive.extractfile(p).read() for p in names}


def module_name(path):
    for prefix in ('services/control-plane/src/','src/'):
        if path.startswith(prefix):path=path[len(prefix):]
    return path.removesuffix('.py').replace('/','.').removesuffix('.__init__')


def analyze(sources):
    parsed={p:ast.parse(raw.decode('utf-8-sig')) for p,raw in sources.items()}
    source={p:r.decode('utf-8-sig') for p,r in sources.items()}
    definitions={};by_name=collections.defaultdict(set);owners={};aliases={};calls=[];alias_edges=[];import_edges=[]
    for p,tree in parsed.items():
        mod=module_name(p);binding={}
        for n in ast.walk(tree):
            if isinstance(n,ast.ImportFrom):
                prefix=mod.split('.')[:-n.level] if n.level else []
                target='.'.join(prefix+([n.module] if n.module else []))
                for a in n.names:
                    binding[a.asname or a.name]=target+'.'+a.name
                    import_edges.append({'path':p,'line':n.lineno,'alias':a.asname or a.name,'target':target+'.'+a.name})
            if isinstance(n,ast.Import):
                for a in n.names:
                    binding[a.asname or a.name.split('.')[0]]=a.name
                    import_edges.append({'path':p,'line':n.lineno,'alias':a.asname or a.name.split('.')[0],'target':a.name})
            if isinstance(n,(ast.With,ast.AsyncWith)):
                for item in n.items:
                    if item.optional_vars is not None:alias_edges.append((p,n.lineno,ast.unparse(item.optional_vars),'CONTEXT_MANAGER:'+ast.unparse(item.context_expr)))
            if isinstance(n,ast.arg) and n.annotation is not None and 'Session' in ast.unparse(n.annotation):alias_edges.append((p,n.lineno,n.arg,'ANNOTATION:'+ast.unparse(n.annotation)))
            if isinstance(n,(ast.Assign,ast.AnnAssign)):
                value=n.value
                targets=n.targets if isinstance(n,ast.Assign) else [n.target]
                for target in targets:
                    if isinstance(target,ast.Name) and isinstance(value,(ast.Name,ast.Attribute)):
                        alias_edges.append((p,n.lineno,target.id,ast.unparse(value)))
                        binding[target.id]=binding.get(ast.unparse(value),ast.unparse(value))
        aliases[p]=binding
        def visit(node,scope=()):
            for n in ast.iter_child_nodes(node):
                if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
                    q=scope+(n.name,);key=mod+'.'+'.'.join(q)
                    if not isinstance(n,ast.ClassDef):definitions[key]=(p,n,q);by_name[n.name].add(key)
                    visit(n,q)
                else:visit(n,scope)
        visit(tree)
    by_file=collections.defaultdict(list)
    for key,(p,fn,scope) in definitions.items():by_file[p].append((key,fn,scope))
    for p,tree in parsed.items():
        module_key=module_name(p)+'.<module>'
        definitions[module_key]=(p,tree,())
        for n in ast.walk(tree):
            if not isinstance(n,ast.Call):continue
            inner=[(k,f,q) for k,f,q in by_file[p] if f.lineno<=n.lineno<=f.end_lineno]
            key,fn,scope=min(inner,key=lambda x:x[1].end_lineno-x[1].lineno) if inner else (module_key,tree,())
            spelling=ast.unparse(n.func);name=spelling.split('.')[-1];target=aliases[p].get(spelling)
            if target is None and '.' in spelling and spelling.split('.')[0] in aliases[p]:target=aliases[p][spelling.split('.')[0]]+'.'+'.'.join(spelling.split('.')[1:])
            if target is None and isinstance(n.func,ast.Name):target=aliases[p].get(name,module_name(p)+'.'+name)
            if spelling.startswith('self.') and len(scope)>1:target=module_name(p)+'.'+'.'.join(scope[:-1])+'.'+name
            matches={target} & definitions.keys() if target else set()
            edge_kind='RESOLVED_IMPORT_LOCAL_OR_SELF'
            if not matches and name in by_name and (isinstance(n.func,ast.Name) or spelling.startswith(('self.','cls.'))):
                matches=by_name[name];edge_kind='CONSERVATIVE_SAME_NAME_CANDIDATE'
            expr=ast.get_source_segment(source[p],n) or ast.unparse(n)
            calls.append({'path':p,'line':n.lineno,'column':n.col_offset,'function':key,'spelling':spelling,'method':name,'expression':expr,'sha256':hashlib.sha256(expr.encode()).hexdigest(),'targets':sorted(matches),'edgeKind':edge_kind})
    seeds={k for k in definitions if k.split('.')[-1] in HELPERS}
    reached=set(seeds)
    while True:
        more={c['function'] for c in calls if set(c['targets'])&reached}
        if more<=reached:break
        reached|=more
    prior=json.loads((E.parent/'fleet5-b-contract-rev3-20261106-codex/callsite-locks.json').read_bytes())
    reviewer=json.loads((E/'prior-census-result.json').read_bytes())
    scope={f['path'] for f in prior['sourceFiles']}|{r['path'] for r in reviewer['outside']}
    scope|={definitions[k][0] for k in reached}
    orm_methods={'query','scalar','scalars','refresh','merge','copy','with_for_update','bulk_save_objects','bulk_insert_mappings','bulk_update_mappings','execute_values'}
    scope|={c['path'] for c in calls if c['method'] in orm_methods}
    for c in calls:
        if c['method'] not in DB:continue
        model_names={'Node','StorageContribution'}|{a for a,t in aliases[c['path']].items() if t.rsplit('.',1)[-1] in ('Node','StorageContribution')}
        model_hit=any(re.search(r'\b(?:select|query|update|delete|get)\(\s*(?:[A-Za-z_][A-Za-z_0-9]*\.)*'+re.escape(n)+r'\b',c['expression']) for n in model_names)
        if TABLES.search(c['expression']) or model_hit:scope.add(c['path'])
    records=[];unknown=[]
    for c in calls:
        if c['path'] not in scope or c['method'] not in DB:continue
        text=c['expression'];kind='DB_LIKE_RECEIVER_UNRESOLVED'
        if c['method']=='with_for_update':kind='ORM_LOCK_MODIFIER_FOR_UPDATE'
        elif re.search(r'\b(SELECT|INSERT|UPDATE|DELETE|SET|CREATE|ALTER|DROP|GRANT|REVOKE)\b',text):kind='SQL_EXPRESSION'
        elif c['method'] in {'scalar','scalars','query','refresh','merge','add','add_all','flush','bulk_save_objects','bulk_insert_mappings','bulk_update_mappings'}:kind='ORM_EXECUTION_OR_UNIT_OF_WORK'
        elif 'session' in c['spelling'].lower() or 'select(' in text:kind='ORM_SESSION_RECEIVER'
        else:
            fn=definitions[c['function']][1]
            recv=c['spelling'].rsplit('.',1)[0]
            assigned=[n.value for n in ast.walk(fn) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==recv for t in n.targets)]
            if isinstance(c.get('receiver'),ast.Dict) or any(isinstance(v,(ast.Dict,ast.DictComp,ast.List,ast.ListComp)) or isinstance(v,ast.Call) and ast.unparse(v.func) in ('dict','json.loads','strict_json') for v in assigned):kind='PROVEN_NON_DB_CONTAINER_CALL'
            elif recv in ('os.environ','dict') or c['method']=='copy' and recv.endswith('environ'):kind='PROVEN_NON_DB_MAPPING_COPY'
            elif c['spelling']=='self._adapter.execute':kind='PROVEN_EXTERNAL_ADAPTER_IO_NO_DB_LOCKS_ALLOWED'
        modes=sorted(set(re.findall(r'FOR\s+(?:KEY\s+)?(?:SHARE|UPDATE)',text,re.I)))
        if c['method']=='with_for_update' or '.with_for_update(' in text:modes=['ORM FOR UPDATE']
        r={k:c[k] for k in ('path','line','column','function','spelling','sha256')}
        r.update(kind=kind,currentModes=modes or ['MVCC read or implicit ORM/UOW/FK lock: exact expression retained'],tables=sorted(set(re.findall(r'\b(?:inv|public)\.[a-z_]+',text))),expression=text,
                 requiredBPlan='SD epoch+tenant guard first -> routing/fence -> sorted full Node/public/contribution/channel/current set -> run/grant/resource/business -> nonce/evidence/ledger; discover without locks, reread scope under locks; external I/O outside tx')

        for model,table in [('Node','public.nodes'),('StorageContribution','public.storage_contributions')]:
            if re.search(r'\b(?:select|update|query)\('+model+r'\b',text) and table not in r['tables']:r['tables'].append(table)
        records.append(r)
        if kind=='DB_LIKE_RECEIVER_UNRESOLVED':unknown.append({k:r[k] for k in ('path','line','column','function','spelling')})
    edges=[{'path':c['path'],'line':c['line'],'column':c['column'],'caller':c['function'],'spelling':c['spelling'],'targets':[t for t in c['targets'] if t in reached],'kind':c['edgeKind']} for c in calls if set(c['targets'])&reached]
    summaries=[]
    for fn in sorted(reached):
        p,node,q=definitions[fn]
        direct=[{'line':r['line'],'column':r['column'],'tables':r['tables'],'modes':r['currentModes'],'kind':r['kind']} for r in records if r['function']==fn]
        helper=[e for e in edges if e['caller']==fn]
        summaries.append({'function':fn,'path':p,'line':getattr(node,'lineno',1),'directLexicalLockOrder':sorted(direct,key=lambda r:(r['line'],r['column'])),'helperEdges':helper,'outerTransaction':'mandatory control_epoch then tenant_controls via fixed SECURITY DEFINER guard for B; no runtime authority UPDATE grant','canonicalBPlan':'discover run/plan/member/resource/Node set without row locks; SD scope locks epoch/tenant/fence/sorted Nodes/public/contribution/channel/current BEFORE Run/plan/budget/operator grants/resources; reread discovery and grants, changed scope abort/replan; helpers use predeclared protected scope, no later lower-rank lock; Node I/O outside transaction','traceClaim':'lexical/static only, branches/dynamic edges need actual PG trace'})
    return {'source':BASE,'scannedFiles':[{'path':p,'sha256':hashlib.sha256(raw).hexdigest()} for p,raw in sorted(sources.items())],
            'functionPlans':summaries,'importBindings':[r for r in import_edges if r['path'] in scope],'scopeFiles':sorted(scope),'helperSeeds':sorted(seeds),'reachableFunctions':sorted(reached),'helperEdges':edges,
            'aliasBindings':[{'path':p,'line':line,'alias':a,'source':v} for p,line,a,v in alias_edges if p in scope],
            'records':records,'unknownStaticReceivers':unknown,'claim':'STATIC conservative graph/source census only. Unknown receiver edges are explicit implementation BLOCK until resolved/traced, not claimed nonDB. Required known business/observe entries have canonical plans; never disable all B to hide omissions. Actual PG traces0.'}


def identity(record):return tuple(record[k] for k in ('path','line','column','sha256'))


def audit_matches(expected,actual):
    return (collections.Counter(identity(r) for r in expected['records'])==collections.Counter(identity(r) for r in actual['records'])
            and expected['helperEdges']==actual['helperEdges'] and expected['aliasBindings']==actual['aliasBindings']
            and expected['importBindings']==actual['importBindings'] and expected['functionPlans']==actual['functionPlans']
            and expected['scopeFiles']==actual['scopeFiles'] and expected['scannedFiles']==actual['scannedFiles'])


def main():
    if '--audit-stdin' in sys.argv:
        expected=json.loads((E/'expanded-source-census.json').read_bytes());given=json.loads(sys.stdin.buffer.read())
        ok=audit_matches(expected,given);print('CENSUS_MATCH' if ok else 'CENSUS_MISMATCH');raise SystemExit(0 if ok else 1)
    current=analyze(load_sources());path=E/'expanded-source-census.json'
    if '--write' in sys.argv:path.write_bytes((json.dumps(current,separators=(',',':'))+'\n').encode())
    stored=json.loads(path.read_bytes());assert audit_matches(stored,current),'source census mismatch'
    assert any(r['path'].endswith('identity/node_auth.py') and r['line']==108 for r in stored['records'])
    negatives=[]
    for label,field,predicate in [('remove-known-callsite','records',lambda r:r['path'].endswith('build_preparations.py') and r['kind']=='SQL_EXPRESSION'),('remove-orm-lock','records',lambda r:r['kind']=='ORM_LOCK_MODIFIER_FOR_UPDATE' and r['path'].endswith('node_auth.py')),('remove-helper-edge','helperEdges',lambda r:bool(r['targets'])),('remove-alias-binding','aliasBindings',lambda r:True),('remove-helper-import','importBindings',lambda r:r['target'].endswith('.lock_run'))]:
        from copy import deepcopy
        bad=deepcopy(stored);index=next(i for i,r in enumerate(bad[field]) if predicate(r));bad[field].pop(index);command=[sys.executable,'-B',str(Path(__file__).resolve()),'--audit-stdin'];run=subprocess.run(command,input=json.dumps(bad).encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE);killed=run.returncode==1 and run.stdout.strip()==b'CENSUS_MISMATCH' and not run.stderr;assert killed,(label,run.returncode,run.stderr);negatives.append({'attack':label,'rejected':killed,'actualExit':run.returncode,'expectedExit':1,'command':command,'stdout':run.stdout.decode().strip()})
    result={'level':'STATIC_GIT_AST_ONLY','source':BASE,'scannedFiles':len(current['scannedFiles']),'scopeFiles':len(current['scopeFiles']),'records':len(current['records']),'helperEdges':len(current['helperEdges']),'aliasBindings':len(current['aliasBindings']),'explicitUnknownReceivers':len(current['unknownStaticReceivers']),'causalNegatives':negatives,'actualPGTrace':False}
    (E/'source-census-results.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps(result))


if __name__=='__main__':main()
