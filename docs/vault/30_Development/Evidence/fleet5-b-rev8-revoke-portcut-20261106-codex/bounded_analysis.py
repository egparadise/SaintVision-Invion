"""Small source-bound Rev8 sidecar. Never imports application code or runs DB IO.

Only A1/A2 needed by revoke_channel are used to close that pilot. A6 is an
incremental all-writer recount over immutable recorded occurrences. All other
entry statuses and normalized Rev7 ledgers remain immutable by hash.
"""
import ast,hashlib,json,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent
ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
R7=E.parent/'fleet5-b-contract-rev7-20261106-codex'
SOURCE='72028cbac903c4415d9979f980a6e0f9948e914f'
PILOT='inv.node_channels.revoke_channel'
M=json.loads((R7/'source-manifest.json').read_bytes())
CACHE={}
def sha(x):return hashlib.sha256(x).hexdigest()
def source(path):
    if path not in CACHE:
        assert len(CACHE)<12, 'bounded selected-file budget'
        CACHE[path]=subprocess.check_output(['git','show',SOURCE+':'+path],cwd=ROOT)
        assert sum(map(len,CACHE.values()))<2*1024*1024
    return CACHE[path].decode('utf-8-sig')
def write(name,d): (E/name).write_bytes((json.dumps(d,ensure_ascii=True,indent=2)+'\n').encode())
def rows(key):
    item=M['ledgers'][key];h=hashlib.sha256();count=0
    with (R7/item['file']).open('rb') as f:
        for raw in f:
            h.update(raw);count+=1;r=json.loads(raw)
            if key=='classifiedCalls':
                r.update(function=M['functionDictionary'][r['functionRef']],path=M['pathDictionary'][r['pathRef']],reason=M['reasonDictionary'][r['reasonRef']])
            yield r
    assert h.hexdigest()==item['sha256'] and count==item['rows'],key
def span(n):return n.lineno,n.col_offset,n.end_lineno,n.end_col_offset
def expr(n):return ast.unparse(n)
def node_at(text,record):
    return next(n for n in ast.walk(ast.parse(text)) if isinstance(n,ast.Call) and span(n)==(record['line'],record['column'],record['endLine'],record['endColumn']))
def functions(text):return [n for n in ast.walk(ast.parse(text)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
def error_initializer(text,class_name):
    """Exact selected Exception dataclass contracts, not an Exception allowlist.

    Constructor/base/decorator/field/post_init and InvError's category closure
    are checked. Other exception classes stay unknown. No source execution.
    """
    t=ast.parse(text);classes={n.name:n for n in t.body if isinstance(n,ast.ClassDef)}
    c=classes.get(class_name)
    if class_name not in ('DomainError','InvError') or not c:return False
    if [expr(b) for b in c.bases]!=['Exception']:return False
    if not any(isinstance(n,ast.ImportFrom) and n.module=='dataclasses' and any(a.name=='dataclass' and not a.asname for a in n.names) for n in t.body):return False
    if any(isinstance(n,(ast.Assign,ast.AnnAssign,ast.FunctionDef,ast.ClassDef)) and ((isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in ('Exception','dataclass')) or isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id in ('Exception','dataclass') for x in n.targets)) for n in t.body):return False
    if len(c.decorator_list)!=1 or expr(c.decorator_list[0]) not in ('dataclass','dataclass(slots=True)'):return False
    methods={n.name:n for n in c.body if isinstance(n,ast.FunctionDef)}
    if '__init__' in methods or any(n.name.startswith('__') and n.name not in ('__str__','__post_init__') for n in methods.values()):return False
    # Dataclass field defaults cannot execute arbitrary constructors.
    for n in c.body:
        if isinstance(n,ast.AnnAssign) and n.value is not None:
            if not isinstance(n.value,(ast.Constant,ast.Call)):return False
            if isinstance(n.value,ast.Call) and expr(n.value) not in ('field(default_factory=dict)','field(init=False)'):return False
        elif not isinstance(n,(ast.AnnAssign,ast.FunctionDef,ast.Expr)):return False
    if class_name=='DomainError':return '__post_init__' not in methods
    p=methods.get('__post_init__')
    if not p or [expr(n.func) for n in ast.walk(p) if isinstance(n,ast.Call)]!=['category_of','Exception.__init__']:return False
    if any(not isinstance(n.targets[0],ast.Attribute) or not isinstance(n.targets[0].value,ast.Name) or n.targets[0].value.id!='self' or len(n.targets)!=1 for n in ast.walk(p) if isinstance(n,ast.Assign)):return False
    if any(isinstance(n,(ast.With,ast.AsyncWith,ast.Await,ast.Yield,ast.Delete)) for n in ast.walk(p)):return False
    cat=next((n for n in t.body if isinstance(n,ast.FunctionDef) and n.name=='category_of'),None)
    if not cat or [expr(n.func) for n in ast.walk(cat) if isinstance(n,ast.Call)]!=['code.split','ErrorCategory','ValueError']:return False
    ec=classes.get('ErrorCategory')
    if not ec or [expr(b) for b in ec.bases]!=['str','Enum']:return False
    if not all(isinstance(n,ast.Assign) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str) for n in ec.body):return False
    for name in ('_STATUS','_RETRYABLE'):
        maps=[n for n in t.body if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id==name]
        if len(maps)!=1 or not isinstance(maps[0].value,ast.Dict):return False
        if any(not isinstance(v,ast.Constant) for v in maps[0].value.values):return False
        if any(not isinstance(k,ast.Attribute) or not isinstance(k.value,ast.Name) or k.value.id!='ErrorCategory' for k in maps[0].value.keys):return False
    return True
def cursor_result(text,call,records,calls):
    if not isinstance(call.func,ast.Attribute) or call.func.attr not in ('fetchone','fetchall','scalar','scalar_one','scalar_one_or_none'):return None
    inner=call.func.value
    if not isinstance(inner,ast.Call) or not isinstance(inner.func,ast.Attribute) or not isinstance(inner.func.value,ast.Name) or inner.func.attr!='execute':return None
    record=next((r for r in records if span(inner)==(r['line'],r['column'],r['endLine'],r['endColumn'])),None)
    resolved=next((r for r in calls if span(inner)==(r['line'],r['column'],r['endLine'],r['endColumn']) and r['classification']=='RESOLVED_DB_RECORD'),None)
    if not record or not resolved or record['unresolvedSQL'] or sha(ast.get_source_segment(text,inner).encode())!=record['expressionSHA256']:return None
    cursor=inner.func.value.id;f=next(n for n in functions(text) if n.lineno<=call.lineno<=n.end_lineno)
    owners=[];allowed_stores=set()
    for w in ast.walk(f):
        if not isinstance(w,ast.With):continue
        for i in w.items:
            if isinstance(i.optional_vars,ast.Name) and i.optional_vars.id==cursor and isinstance(i.context_expr,ast.Call):
                factory=i.context_expr
                proof=next((r for r in calls if span(factory)==(r['line'],r['column'],r['endLine'],r['endColumn']) and r['classification']=='RESOLVED_DB_CURSOR_FACTORY' and r['receiverType']=='DB:Connection'),None)
                if proof and expr(factory.func)=='conn.cursor':owners.append(proof['id']);allowed_stores.add(id(i.optional_vars))
    # A rebound/foreign cursor is not the recorded DB result.
    if len(owners)!=1 or any(isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store) and n.id==cursor and id(n) not in allowed_stores for n in ast.walk(f)):return None
    return {'classification':'RESOLVED_DB_CURSOR_RESULT','retainsDatabaseRead':True,'recordSHA256':record['expressionSHA256'],'recordSpan':list(span(inner)),'cursorFactoryCallRef':owners[0],'controlFlow':'Original result use/None guard/version comparison retained byte-exact; no pure-value exemption'}
def uow(text,model_tables):
    """A6 bounded Session instance tracking; unsupported alias/rebind is BLOCK."""
    tree=ast.parse(text);aliases={}
    session_import=any(isinstance(n,ast.ImportFrom) and n.module=='sqlalchemy.orm' and any(a.name=='Session' and not a.asname for a in n.names) for n in tree.body)
    for n in tree.body:
        if isinstance(n,ast.ImportFrom) and (n.module or '').endswith('db.models'):
            for a in n.names:
                known=[(k,v) for k,v in model_tables.items() if k.rsplit('.',1)[1]==a.name]
                if len(known)==1:aliases[a.asname or a.name]=known[0][1]
    out=[]
    for f in [n for n in tree.body if isinstance(n,ast.FunctionDef)]:
        typed=session_import and any(a.arg=='session' and isinstance(a.annotation,ast.Name) and a.annotation.id=='Session' for a in f.args.args+f.args.kwonlyargs)
        env={}
        for stmt in sorted([n for n in ast.walk(f) if isinstance(n,(ast.Assign,ast.AnnAssign,ast.Expr))],key=lambda n:(n.lineno,n.col_offset)):
            if isinstance(stmt,(ast.Assign,ast.AnnAssign)):
                targets=stmt.targets if isinstance(stmt,ast.Assign) else [stmt.target];v=stmt.value;table=None
                if isinstance(v,ast.Call) and isinstance(v.func,ast.Attribute) and expr(v.func)=='session.get' and v.args and isinstance(v.args[0],ast.Name):table=aliases.get(v.args[0].id)
                elif isinstance(v,ast.Call) and isinstance(v.func,ast.Name):table=aliases.get(v.func.id)
                for target in targets:
                    if isinstance(target,ast.Name):env[target.id]=table
                    if isinstance(target,ast.Name) and target.id=='session':typed=False
            for call in ast.walk(stmt):
                if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Attribute) or expr(call.func) not in ('session.delete','session.merge'):continue
                table=env.get(call.args[0].id) if call.args and isinstance(call.args[0],ast.Name) else None
                known=bool(typed and table)
                out.append({'function':f.name,'line':call.lineno,'column':call.col_offset,'endLine':call.end_lineno,'endColumn':call.end_col_offset,'expression':ast.get_source_segment(text,call),
                  'expressionSHA256':sha(ast.get_source_segment(text,call).encode()),'table':table if known else None,'verb':'DELETE' if call.func.attr=='delete' else 'UPSERT',
                  'kind':'ORM_TYPED_UOW' if known else 'DYNAMIC_BLOCK','mode':'FOR UPDATE' if known else 'UNKNOWN','blocksGrant':not known})
    return out
def main():
    pilot=next(r for r in rows('criticalEntries') if r['function']==PILOT)
    # Consume streams fully so integrity assertions cannot be bypassed by early stop.
    calls=[];wanted=set(pilot['unknownIDs']);edge_rows=[]
    for c in rows('classifiedCalls'):
        if c['function']==PILOT:calls.append(c)
    records=[r for r in rows('records') if r['function']==PILOT]
    path='services/control-plane/src/inv/node_channels.py';text=source(path);errors=source('services/control-plane/src/inv/errors.py')
    assert error_initializer(errors,'DomainError')
    assert any(isinstance(n,ast.ImportFrom) and n.module=='errors' and n.level==1 and any(a.name=='DomainError' and not a.asname for a in n.names) for n in ast.parse(text).body)
    for c in calls:
        if c['id'] not in wanted:continue
        call=node_at(text,c);proof=cursor_result(text,call,records,calls)
        if proof:
            category='ANALYSIS_RULE:A1';binding={'DBResult':proof}
        else:
            assert expr(call.func)=='DomainError' and c['inferredTarget']=='inv.errors.DomainError'
            category='ANALYSIS_RULE:A2';binding={'constructor':'inv.errors.DomainError','base':'builtin Exception','decorator':'dataclasses.dataclass','fileSHA256':sha(errors.encode()),'init':'generated field assignment; no explicit init/post_init; __str__ not executed by construction'}
        edge_rows.append({'callRef':c['id'],'category':category,'source':{'path':path,'span':list(span(call)),'expressionSHA256':sha(ast.get_source_segment(text,call).encode()),'fileSHA256':sha(text.encode())},
          'type':c['receiverType'] or c['inferredTarget'],'receiver':c['spelling'],'binding':binding,'proof':'Exact source AST span + recorded producer/proven import and constructor closure','futureWork':'Real operator-role/PG transaction and denial-preservation trace before any code inclusion','blocksGrant':False,'proofScope':'ANALYSIS_ONLY_NO_GRANT'})
    assert len(edge_rows)==3
    plans=json.loads((R7/'entry-lock-plans.json').read_bytes());join=next(p for p in plans['plans'] if p['entry']==PILOT)
    assert join['procedureRefs']==['b_revoke_node_channel'] and not join['lockPorts']
    authority=json.loads((R7/'authority-matrix.json').read_bytes())
    write('pilot-closure.json',{'source':SOURCE,'entry':PILOT,'original':pilot,'closedAnalysisEdges':edge_rows,'sourceCalls':len(calls),'unchangedDBReadRecords':len(records),
      'status':'SOURCE_TO_PROPOSED_PROCEDURE_STATIC_CLOSED_RUNTIME_PENDING','notGrantable':True,'procedureJoin':join,'procedure':authority['procedures']['b_revoke_node_channel'],
      'nonPilotEntryStatusChanges':0,'remainingNamedPilotPorts':[],'actualRuntimeB':0,'PG':'NOT_RUN','crypto':'NOT_RUN','portGrant':False})
    # A6 incremental census: all old writer rows retained; all recorded UOW
    # delete/merge occurrences revisited, not just a hardcoded expected pair.
    old_writers=list(rows('writers'));occurrences=[]
    for r in rows('records'):
        if r['expression'].startswith(('session.delete(', 'session.merge(')):occurrences.append(r)
    added=[]
    for path in sorted({r['path'] for r in occurrences}):
        for r in uow(source(path),M['modelTables']):
            assert r['kind']!='DYNAMIC_BLOCK',r
            r['path']=path;added.append(r)
    assert len(added)==len(occurrences)
    b=json.loads((R7/'writer-reconciliation.json').read_bytes())['writers']
    write('writer-census-delta.json',{'scope':'All recorded DB writers, incremental A6 closure; no full graph rebuild','oldWriterLedger':M['ledgers']['writers'],'priorWriterRows':len(old_writers),
      'allRecordedDeleteMergeOccurrences':len(occurrences),'additionalWriters':added,'allWriterRows':len(old_writers)+len(added),'BAuthorityWriters':len(b),
      'BWriterMappingUnchanged':not any(x['table'] in {w['table'] for w in b} for x in added),'unresolvedDBAndSQLScopesRetained':M['ledgers']['unknownSqlWriters'],'actualPG':'NOT_RUN'})
    write('source-resource-receipt.json',{'selectedFiles':[{'path':p,'bytes':len(raw),'sha256':sha(raw)} for p,raw in CACHE.items()],
      'sourceBytes':sum(map(len,CACHE.values())),'fileBudget':12,'byteBudget':2*1024*1024,'serial':True,'budgetOSenforced':False,'fullAssembler':'NOT_RUN','sourceFilesCensusRetained':523,'callsRetained':47608,'oldBacklogRetained':29573,'oldTransactionDenominatorRetained':107})
    print(json.dumps({'pilotClosedAnalysisEdges':len(edge_rows),'allDBWriterRows':len(old_writers)+len(added),'BauthorityWriters':len(b),'selectedFiles':len(CACHE),'sourceBytes':sum(map(len,CACHE.values()))}))
if __name__=='__main__':main()
