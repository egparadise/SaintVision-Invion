"""Causal static closure with an UNRESOLVED default, never a non-DB waiver."""
import ast,builtins,hashlib,sys
from collections import defaultdict,Counter
from source_semantics import CRITICAL,text

def classify_and_plan(sources,result,funcs):
    from source_analysis import modname
    def span(r):return r['path'],r['line'],r['column'],r.get('endLine'),r.get('endColumn')
    recordkeys={span(r) for r in result['records']}
    writerkeys={span(r) for r in result['writers']}
    module_shadows={}
    for path,raw in sources.items():
        if not path.endswith('.py'):continue
        tree=ast.parse(raw.decode('utf-8-sig'));names=set()
        for n in tree.body:
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):names.add(n.name)
            elif isinstance(n,(ast.Assign,ast.AnnAssign)):
                for target in n.targets if isinstance(n,ast.Assign) else [n.target]:names.update(x.id for x in ast.walk(target) if isinstance(x,ast.Name))
            elif isinstance(n,(ast.Import,ast.ImportFrom)):names.update(a.asname or a.name.split('.')[0] for a in n.names)
        module_shadows[path]=names
    calls=result['allCallSites'];boundaries=[];unknown=[];constructors=result['valueConstructors']
    filehash={p:hashlib.sha256(b).hexdigest() for p,b in sources.items()}
    lines={p:b.decode('utf-8-sig').splitlines() for p,b in sources.items()}
    function_nodes={k:n for k,(p,n) in funcs.items()}
    # Function-local shadowing forbids a bare builtin-name allowlist.
    shadows={}
    for f,(path,node) in funcs.items():
        args=getattr(node,'args',None)
        names={a.arg for a in args.posonlyargs+args.args+args.kwonlyargs} if args else set()
        names|={n.id for n in ast.walk(node) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)}
        names|={n.name for n in ast.walk(node) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))}
        names|={n.name for n in ast.walk(node) if isinstance(n,ast.ExceptHandler) and n.name}
        if args and args.vararg:names.add(args.vararg.arg)
        if args and args.kwarg:names.add(args.kwarg.arg)
        shadows[f]=names|module_shadows.get(path,set())
    # A literal getattr factory for an existing SOURCE MODULE function is a
    # proven attribute read; the outer invocation retains the source effect edge.
    # Instance properties and nonliteral dispatch never inherit this exemption.
    module_names={modname(path) for path in sources if path.endswith('.py')}
    bypoint={(c['path'],c['line'],c['column']):c for c in calls if c['targets'] and c.get('resolutionComplete')};literal_factories=set()
    for fn,(path,node) in funcs.items():
        for n in ast.walk(node):
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Call) and isinstance(n.func.func,ast.Name) and n.func.func.id=='getattr' and len(n.func.args)>=2 and isinstance(n.func.args[1],ast.Constant) and isinstance(n.func.args[1].value,str):
                outer=bypoint.get((path,n.lineno,n.col_offset),{})
                if outer.get('targets') and outer.get('resolutionComplete') and all(t.rsplit('.',1)[0] in module_names for t in outer['targets']):literal_factories.add((path,n.func.lineno,n.func.col_offset))
    for c in calls:
        path,fn=c['path'],c['function'];key=(path,c['line'],c['column'])
        target=c['inferredTarget'];recv=c.get('receiverType') or '';method=c['method'];sp=c['spelling']
        kind='UNRESOLVED';reason='unproven receiver/dispatch; resolve exact installed type or named mediated port before affected grant'
        if span(c) in recordkeys:kind,reason='RESOLVED_DB_RECORD','exact same source call already represented by DB/SQL/ORM record'
        elif span(c) in writerkeys:kind,reason='RESOLVED_SOURCE_WRITER','exact source SQL/ORM mutation recorded with transition and procedure mapping, never NONAUTHORITY'
        elif c['targets'] and c.get('resolutionComplete',True):kind,reason='RESOLVED_SOURCE_TARGET','exact imported source target, recursively checked in referenced closure'
        elif target in constructors:
            proof=constructors[target]
            if proof['safeGeneratedValueInit']:kind,reason='NONAUTHORITY_VALUE_INITIALIZER',proof['proof']
            elif proof['specialTargets']:
                c['targets']=proof['specialTargets'];kind,reason='RESOLVED_SOURCE_TARGET','constructor special initialization bodies included, never skipped as value object'
        elif method in ('transaction','begin','begin_nested') and (recv.startswith('DB:') or recv.endswith(('.Database','.BoundDatabase')) or c.get('possibleReceiverTypes') and all(t.endswith(('.Database','.BoundDatabase')) or t.startswith('DB:') for t in c['possibleReceiverTypes'])):kind,reason='RESOLVED_TRANSACTION_OWNER','typed context owner; boundary retained without treating status as writer'
        elif key in literal_factories:kind,reason='RESOLVED_ATTRIBUTE_FACTORY','literal existing source-module function attribute; outer invocation source targets/effects remain in closure'
        elif method=='in_transaction' and recv.startswith('DB:Session'):kind,reason='RESOLVED_TRANSACTION_STATUS','SQLAlchemy Session.in_transaction is readonly status; owner/control-flow relationship retained'
        elif method=='cursor' and recv.startswith('DB:'):kind,reason='RESOLVED_DB_CURSOR_FACTORY','typed connection factory; individual SQL calls separately recorded'
        elif method in ('flush','add','add_all','merge','refresh','expire','rollback','commit') and recv.startswith('DB:Session'):kind,reason='RESOLVED_TYPED_ORM_UOW','typed SQLAlchemy Session unit of work; model writes enumerated separately'
        elif recv.startswith(('PY:dict','PY:Mapping','PY:JSON','DB:Row')) and method in ('get','copy','items','keys','values','update','pop','setdefault','clear'):kind,reason='NONAUTHORITY_TYPED_MAPPING','actual typed Mapping/JSON/row receiver provenance, not method-name inference'
        elif recv.startswith('STDLIB:threading.Timer') and method=='start':kind,reason='EXTERNAL_IO_UNMEDIATED','Timer.start schedules an actual callback effect; cancel/value handling is distinct, callback requires a closed mediated port'
        elif target.startswith(('http.','socket.','ssl.','subprocess.','urllib.','requests.')) or recv.startswith(('STDLIB:subprocess','STDLIB:socket')):
            kind,reason='EXTERNAL_IO_UNMEDIATED','actual external client/IO effect requires exact IO catalog entry or a separately closed trusted port; not NONAUTHORITY'
        elif target.split('.')[0] in {'datetime','time','uuid','hashlib','hmac','base64','json','re','math','decimal','collections','itertools','functools','dataclasses','typing','secrets','enum','threading'} or recv.startswith('STDLIB:threading.Timer'):
            kind,reason='NONAUTHORITY_STDLIB','qualified known stdlib value/timer source provenance; effectful network/process modules excluded'
        elif sp in ('open','input','print','breakpoint') and sp not in shadows.get(fn,set()):kind,reason='EXTERNAL_IO_UNMEDIATED','actual unshadowed builtin IO requires a closed mediated/exempted port'
        elif sp in vars(builtins) and sp not in ('eval','exec','__import__','getattr','setattr','delattr','globals','locals','vars') and sp not in shadows.get(fn,set()) and target==modname(path)+'.'+sp:
            kind,reason='NONAUTHORITY_BUILTIN','unshadowed actual builtin binding; argument/nested calls still individually checked'
        # A module alias constructor, dynamic dict/list dispatch or untyped store
        # falls through to UNRESOLVED. A negative type inference is never proof.
        from transport_inventory import QUALIFIED_SITES
        if c['line'] in QUALIFIED_SITES.get(path,set()) and (method in ('probe','resource_snapshot','storage_sample','read_chunk','terminal_frame','quarantine','exchange','collect_product_health','collect_cleanup_receipt') or sp=='self._adapter.execute'):
            kind,reason='AUTHORITY_EXTERNAL_IO_CATALOGUE_BOUND','exact source-bound Node/adapter/local receipt effect port; see transport-inventory.json caller and fixed per-kind effect policy; future wrapper required'
        cid=hashlib.sha256(f'{path}:{c["line"]}:{c["column"]}:{sp}'.encode()).hexdigest()
        c.update(id=cid,classification=kind,reason=reason,source=result['source'],fileSHA256=filehash[path],
          exactLine=lines[path][c['line']-1],scope={'sourceFunction':fn,'path':path,'line':c['line'],'column':c['column']},
          provenance={'receiverType':recv,'qualifiedTarget':target,'source':c['sourceOfType']},
          futureWork=None if kind!='UNRESOLVED' and kind!='EXTERNAL_IO_UNMEDIATED' else 'Implement/review typed source target or exact purpose-restricted mediated port; retain HOLD until resolved',
          blocksGrant=kind in ('UNRESOLVED','EXTERNAL_IO_UNMEDIATED'),affectedEntryIDs=[])
        if c['blocksGrant']:unknown.append(c)
        if kind in ('RESOLVED_TRANSACTION_OWNER','RESOLVED_TRANSACTION_STATUS') or method in ('transaction','begin','begin_nested') and c['targets']:
            boundaries.append(dict(id=cid,function=fn,path=path,line=c['line'],receiver=recv,targets=c['targets'],
              classification=kind,ownerVariants=[{'target':t,'boundary':'SHARE_CALLER_OUTER' if 'BoundDatabase' in t else 'OPEN_OUTER_TRANSACTION' if 'Database.transaction' in t else 'TYPED_SAVEPOINT_OR_SESSION'} for t in c['targets']],boundary='UNRESOLVED_TRANSACTION_OWNER' if kind=='UNRESOLVED' else 'STATUS_READ_NO_NEW_OWNER' if kind=='RESOLVED_TRANSACTION_STATUS' else 'SHARE_CALLER_OUTER' if 'BoundDatabase' in recv+target else 'TYPED_OUTER_OR_SAVEPOINT',networkInside='FORBIDDEN',fileSHA256=filehash[path]))
    # One causal SQL issue per exact source binding/reason; nested ORM records
    # may describe the same call but must not duplicate its unknown.
    sqlissues=[];seen_sql=set()
    for q in result['sqlScopeIssues']:
        identity=(q['id'],q['function'],q['path'],q['line'],q['reason'])
        if identity in seen_sql:continue
        seen_sql.add(identity);sqlissues.append(q)
    result['sqlScopeIssues']=sqlissues
    for q in sqlissues:
        q.update(source=result['source'],fileSHA256=filehash[q['path']],scope={'sourceFunction':q['function'],'path':q['path'],'line':q['line']},
          exactLine=lines[q['path']][q['line']-1],futureWork='Resolve effective SQL scope/identifier/lock owner or named exclusive maintenance boundary before affected grant',blocksGrant=True,affectedEntryIDs=[])
    forward=defaultdict(set);local=defaultdict(list);records=defaultdict(list)
    for c in calls:forward[c['function']].update(c['targets']);local[c['function']].append(c)
    for r in result['records']:records[r['function']].append(r)
    def closure(fn):
        seen=set();todo=[fn]
        while todo:
            f=todo.pop()
            if f in seen:continue
            seen.add(f);todo.extend(forward[f]-seen)
        return seen
    issues=defaultdict(list)
    for u in [*unknown,*sqlissues]:issues[u['function']].append(u)
    plans={p['function']:p for p in result['functionPlans']}
    # Inventory all old named critical entries and all actual API functions.
    seeds=set(plans)|{c['function'] for c in calls if c['path'].startswith('src/saintvision/api/v1/')}
    seeds|={u['function'] for u in [*unknown,*sqlissues]}
    while True:
        more={c['function'] for c in calls if set(c['targets'])&seeds}
        if more<=seeds:break
        seeds|=more
    for fn in sorted(seeds):
        seen=closure(fn);blockers=[u for f in seen for u in issues[f]]
        path,node=funcs.get(fn,('',None));plan=plans.setdefault(fn,{'function':fn,'path':path,'line':getattr(node,'lineno',1),'parameters':[],'discovery':{'querySites':[]},'rankedResourceLocks':[]})
        # Local refs plus graph traversal are normative; no recursively copied
        # function paths, callsite payloads or disposition lists.
        plan.update(callees=sorted(forward[fn]),localCallIDs=[c['id'] for c in local[fn]],
          localUnknownIDs=[u['id'] for u in issues[fn]],closureFunctions=sorted(seen),
          remainingUnknownRefs=[u['id'] for u in blockers],unknownIDs=[u['id'] for u in blockers],
          supportStatus='UNSUPPORTED_NAMED_PORTS_PENDING' if blockers else 'SUPPORTED_STATIC_PLAN',
          missingPorts=sorted({u['function']+':'+u.get('spelling',u.get('reason','SQL')) for u in blockers}),
          criticalEntry=any(fn.endswith('.'+suffix) for suffix in CRITICAL),actualPGTrace=False)
        for u in blockers:u['affectedEntryIDs'].append(fn)
        locks={(t,mode) for f in seen for r in records[f] for t in r['tables'] for mode in r['modes']}
        from rank_contract import RANK
        plan['rankedResourceLocks']=[dict(table=t,mode=mode,rank=RANK.get(t)) for t,mode in sorted(locks,key=lambda x:(RANK.get(x[0],99999),x))]
        plan['transactionBoundaries']=[b['id'] for b in boundaries if b['function'] in seen]
    for u in [*unknown,*sqlissues]:
        u['affectedEntryIDs']=sorted(set(u['affectedEntryIDs']))
        u['reachabilityScope']='CAUSAL_RESOLVED_GRAPH_TO_LISTED_ENTRIES' if u['affectedEntryIDs'] else 'NO_NAMED_ENTRY_IN_RESOLVED_GRAPH; dynamic reachability UNPROVEN, no unreachable exemption/grant'
    result.update(functionPlans=sorted(plans.values(),key=lambda p:p['function']),classifiedCalls=calls,unknownEdges=unknown,
      transactionBoundaries=boundaries,edges=[c for c in calls if c['targets']],reachableFunctions=sorted(seeds),
      valueConstructorProofs=[dict(function=k,**v) for k,v in sorted(constructors.items())],
      criticalEntries=[{'function':p['function'],'supportStatus':p['supportStatus'],'unknownIDs':p['unknownIDs'],'missingPorts':p['missingPorts']} for p in plans.values() if p['criticalEntry']])
    return result
