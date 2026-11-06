"""Source semantics/type-provenance augmentation, no application imports/DB IO."""
import ast
from collections import defaultdict
import hashlib
import re
import sys
from pathlib import Path
from functools import lru_cache

CRITICAL=['BuildExecutionService._commit_consequences','BuildExecutionService._mark_node_quarantined',
 'BuildExecutionService.execute','BuildExecutionIntentQueue.enqueue','BuildPreparationService._terminalize',
 'model_commit.capture_locations','model_source.capture_channels','provision_channel','revoke_channel',
 'NodeDelivery._quarantine_gpu_node','NodeDelivery.deliver','NodeObservation.accept','NodeObservation.mark_offline',
 'ResultStore.complete','RunStore.complete','ShardCompletion.once','StorageSampleStore.apply_sample',
 'set_resource_offer','storage._owned_for_update','identity.node_auth.NodePrincipal.lock_current']


@lru_cache(maxsize=50000)
def text(n):return ast.unparse(n)


def status_semantics(expression,sql=None):
    s=sql if sql is not None else expression
    result={}
    for field in ('status','kill_switch','enabled'):
        if sql is not None:
            match=re.search(r'\b'+field+r'\s*=\s*(CASE[\s\S]*?END|\'[^\']*\'|true\b|false\b|%s|:[a-z_]+)',s,re.I)
            if not match:continue
            value=match.group(1)
        else:
            # ORM keyword or attribute assignment, and setattr's value.
            match=re.search(r'(?:\.'+field+r'\s*=|\b'+field+r'\s*=)\s*([\s\S]*)',s)
            value=match.group(1) if match else s if s.startswith('setattr(') and repr(field) in s else None
            if value is None:continue
        if re.match(r'CASE\b|case\(',value,re.I):
            pairs=re.findall(r"WHEN\s+(?:\w+\.)?"+field+r"\s*=\s*'([^']+)'\s+THEN\s*'([^']+)'",value,re.I)
            if not pairs:pairs=re.findall(r"\."+field+r"\s*==\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]",value)
            result[field]={'kind':'CASE','fromTo':[list(p) for p in pairs],
                'elseRetainsColumn':bool(re.search(r'ELSE\s+(?:\w+\.)?'+field+r'\b|else_\s*=\s*\w+\.'+field,value,re.I))}
        else:
            literal=re.match(r"['\"]([^'\"]+)['\"]",value)
            if s.startswith('setattr('):
                try:literal_value=ast.literal_eval(ast.parse(s).body[0].value.args[2])
                except (ValueError,TypeError,SyntaxError):literal_value=None
                literal=None
            else:literal_value=literal.group(1) if literal else value.lower() if value.lower() in ('true','false') else None
            result[field]={'kind':'LITERAL' if literal_value is not None else 'PARAMETER','value':literal_value}
    where=re.split(r'\bWHERE\b',s,maxsplit=1,flags=re.I)[1] if sql is not None and re.search(r'\bWHERE\b',s,re.I) else ''
    return {'assignments':result,'whereStatusEquals':re.findall(r"(?:\w+\.)?status\s*=\s*'([^']+)'",where,re.I),
            'whereNormalized':re.sub(r'\s+',' ',where).strip()}


def enhance(sources,result):
    text.cache_clear()
    from source_analysis import modname,ownwalk
    funcs={};aliases={};parent_nodes={}
    for path,raw in sources.items():
        if not path.endswith('.py'):continue
        tree=ast.parse(raw.decode('utf-8-sig'));mod=modname(path)
        alias={}
        for n in ast.walk(tree):
            if isinstance(n,ast.ImportFrom):
                for a in n.names:alias[a.asname or a.name]=(n.module or '')+'.'+a.name
            elif isinstance(n,ast.Import):
                for a in n.names:alias[a.asname or a.name.split('.')[0]]=a.name
        aliases[path]=alias
        def visit(n,scope=()):
            for c in ast.iter_child_nodes(n):
                if isinstance(c,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
                    q=scope+(c.name,)
                    if not isinstance(c,ast.ClassDef):funcs[mod+'.'+'.'.join(q)]=(path,c)
                    visit(c,q)
                else:visit(c,scope)
        visit(tree)
    def literal(n):
        try:return ast.literal_eval(n)
        except (ValueError,TypeError):return None
    models=result['modelTables'];model_names={k.rsplit('.',1)[-1]:v for k,v in models.items()}
    oldkeys={(w['path'],w['line'],w['column'],w['table'],w['verb'],tuple(w['columns'])) for w in result['writers']}
    unknown_sql=[];model_writes=[]
    for fn,(path,node) in funcs.items():
        alias=aliases[path];symbols={};values={}
        def model(n):
            if isinstance(n,ast.Name):
                if n.id in symbols:return symbols[n.id]
                resolved=alias.get(n.id,n.id).rsplit('.',1)[-1]
                return model_names.get(resolved)
            if isinstance(n,ast.Attribute) and n.attr=='__table__':return model(n.value)
            if isinstance(n,ast.Call):
                target=alias.get(text(n.func),text(n.func))
                if target.endswith('.Table') and n.args and isinstance(literal(n.args[0]),str):
                    schema=next((literal(k.value) for k in n.keywords if k.arg=='schema'),None)
                    if schema in ('public','inv'):return schema+'.'+literal(n.args[0])
                for c in ast.walk(n):
                    if isinstance(c,ast.Name) and (v:=model(c)):return v
            return None
        for n in ownwalk(node):
            if isinstance(n,(ast.Assign,ast.AnnAssign)) and n.value is not None:
                for t in n.targets if isinstance(n,ast.Assign) else [n.target]:
                    if isinstance(t,ast.Name):
                        values[t.id]=n.value
                        if (v:=model(n.value)):symbols[t.id]=v
        def statement(n,seen=()):
            if isinstance(n,ast.Name) and n.id in values and n.id not in seen:return statement(values[n.id],(*seen,n.id))
            return n
        def add(n,table,verb,cols,kind):
            w=dict(source=result['source'],path=path,function=fn,line=n.lineno,column=n.col_offset,
                expression=text(n),expressionSHA256=hashlib.sha256(text(n).encode()).hexdigest(),kind=kind,
                table=table,verb=verb,columns=sorted(cols))
            key=(path,w['line'],w['column'],table,verb,tuple(w['columns']))
            if key not in oldkeys:result['writers'].append(w);oldkeys.add(key)
            model_writes.append(w)
        for n in ownwalk(node):
            if not isinstance(n,ast.Call):continue
            spelling=text(n.func);method=spelling.split('.')[-1]
            if method=='setattr' and len(n.args)==3 and (table:=model(n.args[0])):
                field=literal(n.args[1])
                if isinstance(field,str):add(n,table,'UPDATE',[field],'ORM_SETATTR')
                else:unknown_sql.append(dict(path=path,function=fn,line=n.lineno,column=n.col_offset,expression=text(n),reason='DYNAMIC_MODEL_FIELD_BLOCK'))
            if method not in ('execute','scalars','scalar','executemany') or not n.args:continue
            stmt=statement(n.args[0])
            for c in ast.walk(stmt):
                if not isinstance(c,ast.Call):continue
                cs=text(c.func);tail=cs.split('.')[-1];qualified=alias.get(cs.split('.')[0],cs.split('.')[0])+('.'+'.'.join(cs.split('.')[1:]) if '.' in cs else '')
                table=None;verb=None
                if qualified.startswith('sqlalchemy') and qualified.split('.')[-1] in ('insert','update','delete') and c.args:
                    table=model(c.args[0]);verb=qualified.split('.')[-1].upper()
                elif tail in ('insert','update','delete') and isinstance(c.func,ast.Attribute):
                    table=model(c.func.value);verb=tail.upper()
                if table and verb:
                    cols=set()
                    for value in ast.walk(stmt):
                        if isinstance(value,ast.Call) and isinstance(value.func,ast.Attribute) and value.func.attr=='values':
                            cols.update(k.arg for k in value.keywords if k.arg)
                            for a in value.args:
                                if isinstance(a,ast.Dict):cols.update(k.value for k in a.keys if isinstance(k,ast.Constant) and isinstance(k.value,str))
                    add(n,table,verb,cols or ['ROW_DELETE' if verb=='DELETE' else 'UNKNOWN_COLUMNS_BLOCK'],'ORM_CORE_DML')
            constants=' '.join(v.value for v in ast.walk(stmt) if isinstance(v,ast.Constant) and isinstance(v.value,str))
            dml=re.search(r'\b(?:INSERT\s+INTO|UPDATE\s+\S+\s+SET|DELETE\s+FROM)\b',constants,re.I)
            templates=[]
            for c in ast.walk(stmt):
                if isinstance(c,ast.JoinedStr):templates.append(''.join(v.value if isinstance(v,ast.Constant) and isinstance(v.value,str) else '<dynamic>' for v in c.values))
                if isinstance(c,ast.Constant) and isinstance(c.value,str):templates.append(c.value.replace('{}','<dynamic>'))
            dynamic=any(re.search(r'\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+[^\s]*(?:<dynamic>|\{[^}]*\})',template,re.I) for template in templates)
            if dml and dynamic:
                names={v.value.id for v in ast.walk(stmt) if isinstance(v,ast.FormattedValue) and isinstance(v.value,ast.Name)}
                bounded=[]
                for loop in ownwalk(node):
                    if isinstance(loop,ast.For) and isinstance(loop.target,ast.Name) and loop.target.id in names:
                        val=literal(loop.iter)
                        if isinstance(val,(tuple,list)) and all(isinstance(v,str) for v in val):bounded.extend(val)
                unknown_sql.append(dict(path=path,function=fn,line=n.lineno,column=n.col_offset,expression=text(n),reason='DYNAMIC_SQL_IDENTIFIER_BLOCK',
                    possibleIdentifierValues=sorted(set(bounded)) if bounded else None))
            elif dml:
                for match in re.finditer(r'\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+([a-z_][a-z_0-9]*)\b(?!\.)',constants,re.I):
                    verb=match.group(1).split()[0].upper();name=match.group(2)
                    if name.upper() in ('SET','SELECT','IF','ON','RETURNING'):continue
                    before=[c for c in ownwalk(node) if isinstance(c,ast.Constant) and isinstance(c.value,str) and getattr(c,'lineno',0)<n.lineno and re.search(r'SET\s+(?:LOCAL\s+)?search_path\s*(?:TO|=)',c.value,re.I)]
                    search=None
                    if before:
                        setting=max(before,key=lambda c:c.lineno).value
                        suffix=re.split(r'SET\s+(?:LOCAL\s+)?search_path\s*(?:TO|=)',setting,flags=re.I)[-1]
                        parts=[p.strip(' "\'') for p in suffix.split(',')]
                        if parts and all(p in ('public','inv','pg_catalog') for p in parts):search=parts
                    if not search:
                        unknown_sql.append(dict(path=path,function=fn,line=n.lineno,column=n.col_offset,expression=text(n),reason='UNQUALIFIED_DML_UNKNOWN_EFFECTIVE_SEARCH_PATH',unqualifiedName=name))
                    else:
                        schema=next((p for p in search if p in ('inv','public')),None)
                        if schema:
                            columns=re.findall(r'\b([a-z_]+)\s*=',constants.split('SET',1)[-1].split('WHERE',1)[0]) if verb=='UPDATE' else []
                            add(n,schema+'.'+name,verb,columns or ['UNKNOWN_COLUMNS_BLOCK'],'SQL_EXPLICIT_SEARCH_PATH')
    for w in result['writers']:
        w['transitionSemantics']=status_semantics(w['expression'],w.get('resolvedSQL') if w['kind'].startswith('SQL') else None)
        if w['kind']=='ORM_DML' or w['kind']=='ORM_CORE_DML':
            stmt=next((n for n in ast.walk(funcs[w['function']][1]) if isinstance(n,ast.Call) and n.lineno==w['line'] and n.col_offset==w['column']),None)
            if stmt:w['transitionSemantics']=status_semantics(text(stmt))
        node=funcs[w['function']][1] if w['function'] in funcs else None
        w['sourceFunctionGuards']={'statusComparisons':[text(n) for n in ast.walk(node) if isinstance(n,ast.Compare) and '.status' in text(n)] if node else [],
            'ownedForUpdate':any(isinstance(n,ast.Call) and text(n.func).endswith('_owned_for_update') for n in ast.walk(node)) if node else False,
            'sourceBodySHA256':hashlib.sha256(text(node).encode()).hexdigest() if node else None}
    unknown_keys={(u['path'],u['line'],u['column']) for u in unknown_sql}
    sql_issues=[]
    for r in result['records']:
        if (r['path'],r['line'],r['column']) in unknown_keys:
            r.update(scopeDisposition='UNKNOWN_SQL_IDENTIFIER_OR_SEARCHPATH_BLOCK',unresolvedSQL=True)
        if r.get('unresolvedSQL'):
            transparent=r['function']=='inv.db._ObservedConnection.execute' and 'self._conn.execute(query, params, **kwargs)' in text(funcs[r['function']][1])
            if transparent:
                r.update(scopeDisposition='RESOLVED_TRANSPARENT_DB_FORWARDER',unresolvedSQL=False,
                    forwardingProof='exact source query/params forwarding to psycopg; callers SQL is censused independently; no text/table mutation')
            else:
                sql_issues.append(dict(id='sql:'+hashlib.sha256((r['path']+':'+str(r['line'])+':'+str(r['column'])).encode()).hexdigest(),
                    function=r['function'],path=r['path'],line=r['line'],classification='BLOCK',reason='recorded DB API has unresolved SQL scope; no duplicate callgraph unknown'))
        if 'SESSION_ADVISORY_OFFLINE_ONLY' in r.get('modes',[]):
            r['modes']=['SESSION_ADVISORY' if mode=='SESSION_ADVISORY_OFFLINE_ONLY' else mode for mode in r['modes']]
            r['tables']=[t if t!='@transaction_advisory' else '@session_advisory_requires_exclusive_maintenance' for t in r['tables']]
            r['scopeDisposition']='SESSION_ADVISORY_UNSUPPORTED_ONLINE_OR_WITHOUT_EXCLUSIVE_MAINTENANCE_PROOF'
            sql_issues.append(dict(id='session:'+hashlib.sha256((r['path']+':'+str(r['line'])).encode()).hexdigest(),
                function=r['function'],path=r['path'],line=r['line'],classification='BLOCK',reason='session advisory is NOT a transaction advisory or automatic offline exemption; separately reviewed exclusive no-B-traffic maintenance required'))

    # Classify actual call sites with receiver/import/source provenance, not a
    # collision against all reached method names. DB records are never UNKNOWN twice.
    recordkeys={(r['path'],r['line'],r['column']) for r in result['records']}
    authority_modules={r['function'].rsplit('.',1)[0] for r in result['records']}|{w['function'].rsplit('.',1)[0] for w in result['writers']}
    authority_classes={f.rsplit('.',1)[0] for f in result['reachableFunctions'] if f.rsplit('.',1)[0].split('.')[-1][:1].isupper()}
    classified=[];unknown=[];boundaries=[]
    for c in result['allCallSites']:
        key=(c['path'],c['line'],c['column']);target=c['inferredTarget'];recv=c.get('receiverType') or '';method=c['method'];s=c['spelling']
        kind,reason='NONAUTHORITY_UNRESOLVED_EXTERNAL_BACKLOG','no authority type/target evidence; retained bounded callsite backlog, not a BLOCK by name'
        if key in recordkeys:kind,reason='RESOLVED_DB_RECORD','same exact callsite already has SQL/ORM record; no duplicate unknown'
        elif c['targets']:kind,reason='RESOLVED_SOURCE_TARGET','exact import/constructor/injected receiver target in source definitions'
        elif method in ('transaction','begin','begin_nested') and (recv.startswith('DB:') or recv.endswith(('.Database','.BoundDatabase'))):
            kind,reason='RESOLVED_TRANSACTION_OWNER','DB/Session receiver type and source context-manager propagation'
        elif method=='cursor' and recv.startswith('DB:'):
            kind,reason='RESOLVED_DB_CURSOR_FACTORY','typed psycopg connection cursor context factory; SQL executes are individually recorded'
        elif method in ('flush','add','add_all','merge','refresh','expire','rollback','commit') and recv.startswith('DB:Session'):
            kind,reason='RESOLVED_TYPED_ORM_UOW','pinned SQLAlchemy Session unit of work, pending source Model writes recorded separately; not an unknown helper'
        elif recv.startswith(('PY:dict','PY:Mapping','PY:JSON','DB:Row')) and method in ('get','copy','items','keys','values','update','pop','setdefault','clear'):
            kind,reason='NONAUTHORITY_MAPPING','builtin/Mapping/decoded JSON or dict-row receiver proven by AST type propagation'
        elif target.split('.')[0] in sys.stdlib_module_names or recv.startswith('STDLIB:'):
            kind,reason='NONAUTHORITY_STDLIB','actual qualified stdlib import/constructor receiver; external IO separately bounded'
        elif c.get('isDynamicGetattr'):
            module=target.partition(':')[2]
            if any(module==a or a.startswith(module+'.') for a in authority_modules):kind,reason='BLOCK','nonliteral getattr on relevant authority module/receiver'
        elif s=='getattr':kind,reason='NONAUTHORITY_ATTRIBUTE_FACTORY','getattr returns an attribute; its actual outer invocation is classified separately'
        elif recv.startswith('DB:') or recv in authority_classes or any(recv==a for a in authority_modules):
            kind,reason='BLOCK','unresolved invocation on a source-proven authority receiver'
        item={**c,'id':hashlib.sha256((c['path']+':'+str(c['line'])+':'+str(c['column'])+':'+s).encode()).hexdigest(),
              'classification':kind,'reason':reason,'provenance':dict(receiverType=recv,qualifiedTarget=target,source=c['sourceOfType'])}
        classified.append(item)
        if kind=='BLOCK':unknown.append(item)
        if method in ('transaction','begin','begin_nested') and (kind=='RESOLVED_TRANSACTION_OWNER' or any(t.endswith(('.Database.transaction','.BoundDatabase.transaction')) for t in c['targets'])):
            boundaries.append({**item,'boundary':'SHARE_CALLER_OUTER' if 'BoundDatabase' in (recv+target) else 'SAVEPOINT' if method=='begin_nested' or recv=='DB:Connection' else 'OPEN_OUTER_TRANSACTION',
                               'networkInside':'FORBIDDEN'})
    for u in unknown_sql:
        if (u['path'],u['line'],u['column']) not in recordkeys:
            sql_issues.append({**u,'id':'sql:'+hashlib.sha256(repr(sorted(u.items())).encode()).hexdigest(),'classification':'BLOCK'})
    result['unknownEdges']=unknown;result['classifiedCalls']=classified;result['transactionBoundaries']=boundaries;result['unknownSqlWriters']=unknown_sql;result['sqlScopeIssues']=sql_issues
    # Add dynamic authority callers as seeds, then close over exact resolved edges.
    allcalls=result['allCallSites'];reached=set(result['reachableFunctions'])|{u['function'] for u in unknown}|{w['function'] for w in result['writers']}|{u['function'] for u in sql_issues}
    while True:
        more={c['function'] for c in allcalls if set(c['targets'])&reached}
        if more<=reached:break
        reached|=more
    edges=[c for c in allcalls if set(c['targets'])&reached];forward=defaultdict(set)
    for c in edges:forward[c['function']].update(c['targets'])
    plans={p['function']:p for p in result['functionPlans']}
    for fn in sorted(reached):
        if fn not in plans:
            path,node=funcs.get(fn,('',None))
            plans[fn]=dict(function=fn,path=path,line=getattr(node,'lineno',1),parameters=[],rankedResourceLocks=[],
                discovery={'scopeKeys':[],'querySites':[]},concreteEntryContracts=[{'source':'dynamic scoped authority entry; resolve exact target before implementation'}],transitiveFunctions=[])
        plan=plans[fn];todo=[fn];seen=set()
        while todo:
            f=todo.pop()
            if f in seen:continue
            seen.add(f);todo.extend(forward[f]-seen)
        dispositions=[{k:c[k] for k in ('id','classification','reason')} for c in classified if c['function'] in seen and c['classification']!='NONAUTHORITY_UNRESOLVED_EXTERNAL_BACKLOG']
        blockers=[{k:u[k] for k in ('id','function','path','line','classification','reason')} for u in [*unknown,*sql_issues] if u['function'] in seen]
        plan['transitiveFunctions']=sorted(seen);plan['callDispositions']=dispositions;plan['unknownIDs']=[b['id'] for b in blockers];plan['remainingUnknowns']=blockers
        plan['unresolvedDbSites']=[u for u in sql_issues if u['function'] in seen]
        from rank_contract import RANK
        lockset={(t,mode) for r in result['records'] if r['function'] in seen for t in r['tables'] for mode in r['modes']}
        plan['rankedResourceLocks']=[dict(table=t,mode=mode,rank=RANK.get(t),disposition='NAMED_RANK' if t in RANK else 'UNKNOWN_OR_UNSUPPORTED_ONLINE_LOCK_BLOCK') for t,mode in sorted(lockset,key=lambda v:(RANK.get(v[0],99999),v))]
        plan['supportStatus']='UNSUPPORTED_PENDING_SCOPED_AUTHORITY_RESOLUTION' if blockers else 'SUPPORTED_STATIC_PLAN'
        plan['transactionBoundaries']=[b for b in boundaries if b['function'] in seen]
        plan['criticalEntry']=any(fn.endswith('.'+suffix) for suffix in CRITICAL)
    result.update(functionPlans=sorted(plans.values(),key=lambda p:p['function']),edges=edges,reachableFunctions=sorted(reached),
        classificationPolicy='per callsite DB record / source target / transaction owner / proven Mapping or stdlib / typed authority UNKNOWN; never bare-method name collision',
        criticalEntries=[{'function':p['function'],'supportStatus':p['supportStatus'],'unknownIDs':p['unknownIDs']} for p in plans.values() if p['criticalEntry']])
    result['semanticsToolSHA256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result['rankToolSHA256']=hashlib.sha256((Path(__file__).parent/'rank_contract.py').read_bytes()).hexdigest()
    return result
