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
                expression=text(n),endLine=n.end_lineno,endColumn=n.end_col_offset,expressionSHA256=hashlib.sha256(text(n).encode()).hexdigest(),kind=kind,
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
            if method in ('bulk_update_mappings','bulk_insert_mappings') and n.args and (table:=model(n.args[0])):
                cols={k.value for a in n.args[1:] for d in ast.walk(a) if isinstance(d,ast.Dict) for k in d.keys if isinstance(k,ast.Constant) and isinstance(k.value,str)}
                add(n,table,'UPDATE' if method=='bulk_update_mappings' else 'INSERT',cols or ['UNKNOWN_COLUMNS_BLOCK'],'ORM_BULK_MAPPINGS')
            if method in ('update','delete') and isinstance(n.func,ast.Attribute) and any(isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute) and c.func.attr=='query' for c in ast.walk(n.func.value)) and (table:=model(n.func.value)):
                cols={k.value for a in n.args for d in ast.walk(a) if isinstance(d,ast.Dict) for k in d.keys if isinstance(k,ast.Constant) and isinstance(k.value,str)}
                add(n,table,method.upper(),cols or ['ROW_DELETE' if method=='delete' else 'UNKNOWN_COLUMNS_BLOCK'],'ORM_QUERY_DML')
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
            def closed(n,seen=frozenset()):
                if isinstance(n,ast.Constant) and isinstance(n.value,str):return {n.value}
                if isinstance(n,ast.Name) and n.id in values and n.id not in seen:return closed(values[n.id],seen|{n.id})
                if isinstance(n,ast.IfExp):
                    a,b=closed(n.body,seen),closed(n.orelse,seen)
                    return a|b if a is not None and b is not None else None
                if isinstance(n,ast.BinOp):
                    a,b=closed(n.left,seen),closed(n.right,seen)
                    if a is None or b is None:return None
                    try:return {x+y if isinstance(n.op,ast.Add) else x%y for x in a for y in b} if isinstance(n.op,(ast.Add,ast.Mod)) else None
                    except (ValueError,TypeError):return None
                if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('format','join'):
                    base=closed(n.func.value,seen);args=[closed(a,seen) for a in n.args]
                    if base is None or any(a is None for a in args):return None
                    import itertools
                    try:return {fmt.format(*a) for fmt in base for a in itertools.product(*args)} if n.func.attr=='format' else None
                    except (ValueError,KeyError,IndexError):return None
                return None
            literal_set=closed(stmt)
            compositional=any(isinstance(c,(ast.JoinedStr,ast.BinOp)) or isinstance(c,ast.Call) and isinstance(c.func,ast.Attribute) and c.func.attr in ('format','join') for c in ast.walk(stmt))
            if literal_set:
                for rec in result['records']:
                    if (rec['path'],rec['line'],rec['column'])==(path,n.lineno,n.col_offset):
                        rec['closedLiteralVariants']=sorted(literal_set)
                        rec['tables']=sorted(set(rec['tables'])|{t.lower() for value in literal_set for t in re.findall(r'\b(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+((?:inv|public)\.[a-z_][a-z_0-9]*)',value,re.I)})
                        rec['unresolvedSQL']=False;rec['scopeDisposition']='CLOSED_LITERAL_SET_ALL_VARIANTS_ANALYZED'
                        for value in literal_set:
                            for m in re.finditer(r'pg_(?:try_)?advisory_(xact_)?lock(?:_shared)?\s*\(',value,re.I):
                                mode='TRANSACTION_ADVISORY' if m.group(1) else 'SESSION_ADVISORY_OFFLINE_ONLY'
                                if mode not in rec['modes']:rec['modes'].append(mode)
            if compositional and literal_set is None:
                unknown_sql.append(dict(path=path,function=fn,line=n.lineno,column=n.col_offset,expression=text(n),reason='NONCONSTANT_SQL_COMPOSITION_BLOCK'))
            elif literal_set and len(literal_set)>1:
                for variant in sorted(literal_set):
                    for match in re.finditer(r'\b(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+((?:inv|public)\.[a-z_][a-z_0-9]*)',variant,re.I):
                        verb=match.group(1).split()[0].upper();cols=re.findall(r'\b([a-z_]+)\s*=',variant.split('SET',1)[-1].split('WHERE',1)[0])
                        add(n,match.group(2).lower(),verb,cols or ['UNKNOWN_COLUMNS_BLOCK'],'SQL_CLOSED_LITERAL_VARIANT')
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
                sql_issues.append(dict(id='sql:'+hashlib.sha256(repr((r['path'],r['function'],r['line'],r['column'],r.get('endLine'),r.get('endColumn'))).encode()).hexdigest(),
                    function=r['function'],path=r['path'],line=r['line'],classification='BLOCK',reason='recorded DB API has unresolved SQL scope; no duplicate callgraph unknown'))
        if 'SESSION_ADVISORY_OFFLINE_ONLY' in r.get('modes',[]):
            r['modes']=['SESSION_ADVISORY' if mode=='SESSION_ADVISORY_OFFLINE_ONLY' else mode for mode in r['modes']]
            r['tables']=[t if t!='@transaction_advisory' else '@session_advisory_requires_exclusive_maintenance' for t in r['tables']]
            r['scopeDisposition']='SESSION_ADVISORY_UNSUPPORTED_ONLINE_OR_WITHOUT_EXCLUSIVE_MAINTENANCE_PROOF'
            sql_issues.append(dict(id='session:'+hashlib.sha256((r['path']+':'+str(r['line'])).encode()).hexdigest(),
                function=r['function'],path=r['path'],line=r['line'],classification='BLOCK',reason='session advisory is NOT a transaction advisory or automatic offline exemption; separately reviewed exclusive no-B-traffic maintenance required'))

    from graph_policy import classify_and_plan
    result['sqlScopeIssues']=sql_issues;result['unknownSqlWriters']=unknown_sql
    return classify_and_plan(sources,result,funcs)
