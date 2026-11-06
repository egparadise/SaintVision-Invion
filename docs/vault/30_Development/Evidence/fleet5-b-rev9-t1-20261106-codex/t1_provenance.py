"""Narrow actual-source T1/A8 proof. No application import or runtime binding."""
import ast,hashlib,json,subprocess
from pathlib import Path
import analysis_rules as r
import bounded_analysis as a
E=Path(__file__).resolve().parent;CP='services/control-plane/src/inv/'
CORE=['observation.py','db.py','errors.py','observer_worker.py','workspace_api.py','workspace_config.py','app.py']
CTOR_PATHS=[CP+n for n in ('app.py','observer_worker.py','worker.py')]+['tools/lan_pilot.py','tools/remote_workspace_entry.py','tools/run_s04_fe_matrix.py','tools/rehearse_independent_restore.py']
MAIN_CTOR_PATHS=CTOR_PATHS[:5]
EXTRA_CTOR_PATHS=CTOR_PATHS[5:]
def read_batch(paths,overrides=None):
    assert len(paths)<=10
    d={p:(overrides[p] if overrides and p in overrides else subprocess.check_output(['git','show',a.SOURCE+':'+p],cwd=a.ROOT).decode('utf-8-sig')) for p in paths}
    assert sum(len(t.encode()) for t in d.values())<2*1024*1024
    return d
def qualified_functions(source):
    out={}
    def walk(n,q=()):
        for c in ast.iter_child_nodes(n):
            if isinstance(c,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):
                name=q+(c.name,)
                if not isinstance(c,ast.ClassDef):out['.'.join(name)]=c
                walk(c,name)
            else:walk(c,q)
    walk(ast.parse(source));return out
def function(source,name):return qualified_functions(source)[name]
def witness(path,source,node,**extra):return {'path':path,'span':list(r.span(node)),'sourceFileSHA256':r.sha(source),'expressionSHA256':r.sha(ast.get_source_segment(source,node)),**extra}
def observed_union(db):
    fs=qualified_functions(db);f=fs['_ObservedConnection.execute'];init=fs['_ObservedConnection.__init__'];delegate=fs['_ObservedConnection.__getattr__'];txn=fs['Database.transaction']
    assigns=[n for n in ast.walk(f) if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='result' for x in n.targets)]
    returns=[n for n in ast.walk(f) if isinstance(n,ast.Return)]
    if len(assigns)!=1 or r.text(assigns[0].value)!='self._conn.execute(query, params, **kwargs)' or len(returns)!=1 or r.text(returns[0].value)!='result':return None,'RECEIVER_UNION_UNPROVEN:CHANGED_OBSERVED_RETURN'
    if [r.text(n) for n in init.body]!=['self._conn = conn','self._observer = observer']:return None,'RECEIVER_UNION_UNPROVEN:OBSERVED_CTOR'
    if len(delegate.body)!=1 or r.text(delegate.body[0])!='return getattr(self._conn, name)':return None,'RECEIVER_UNION_UNPROVEN:DELEGATE'
    assignments=[n for n in ast.walk(txn) if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='observed_conn' for x in n.targets)]
    expected='_ObservedConnection(conn, self.statement_observer) if self.statement_observer is not None else conn'
    if len(assignments)!=1 or r.text(assignments[0].value)!=expected:return None,'RECEIVER_UNION_UNPROVEN:YIELD_SELECTION'
    yields=[n for n in ast.walk(txn) if isinstance(n,ast.Yield)]
    if len(yields)!=1 or r.text(yields[0].value)!='observed_conn':return None,'RECEIVER_UNION_UNPROVEN:YIELD'
    for cls in [n for n in ast.walk(ast.parse(db)) if isinstance(n,ast.ClassDef)]:
        if any(r.text(b).rsplit('.',1)[-1] in ('Database','BoundDatabase','_ObservedConnection') for b in cls.bases):return None,'RECEIVER_UNION_UNPROVEN:SUBCLASS_OVERRIDE'
    if r.dynamic_module_mutation(ast.parse(db),{'Database','BoundDatabase','_ObservedConnection'}):return None,'DYNAMIC_BLOCK:DB_CLASS_MUTATION'
    return {'receiverUnion':['psycopg.Connection','inv.db._ObservedConnection'],'yieldSelection':witness(CP+'db.py',db,assignments[0]),'executeForward':witness(CP+'db.py',db,assigns[0]),'returnUnchanged':witness(CP+'db.py',db,returns[0]),'delegate':witness(CP+'db.py',db,delegate),'observerEffect':'Named T1 observability; current source constructors default None, runtime handler/config proof pending'},None
def local_field_proof(source,owner,field,param):
    cls=next(n for n in ast.parse(source).body if isinstance(n,ast.ClassDef) and n.name==owner)
    stores=[n for n in ast.walk(cls) if isinstance(n,ast.Attribute) and isinstance(n.ctx,(ast.Store,ast.Del)) and r.text(n)=='self.'+field]
    if len(stores)!=1:return False
    f=function(source,owner+'.__init__')
    for n in ast.walk(f):
        if not isinstance(n,ast.Assign):continue
        for target in n.targets:
            if isinstance(target,ast.Attribute) and r.text(target)=='self.'+field and r.text(n.value)==param:return True
            if isinstance(target,ast.Tuple) and isinstance(n.value,ast.Tuple):
                if any(r.text(x)=='self.'+field and r.text(y)==param for x,y in zip(target.elts,n.value.elts)):return True
    return False
def database_constructors(sources):
    rows=[]
    for path,source in sources.items():
        tree=ast.parse(source)
        if any('__import__' in r.bound_names(n) for n in ast.walk(tree)):return None,'DYNAMIC_BLOCK:SHADOWED_DYNAMIC_IMPORT'
        if not r.exact_import(tree,'Database','db',1) and not r.exact_import(tree,'Database','inv.db',0):return None,'RECEIVER_UNION_UNPROVEN:DB_IMPORT'
        # The app has an unrelated route-local __import__('re') validator. It
        # cannot bind Database; this proof makes no purity claim for that route.
        # All Database stores/imports are checked above; dynamic global writes,
        # class mutation and class aliases remain blocked.
        scan=ast.parse(source)
        class NonTargetRegexImport(ast.NodeTransformer):
            def visit_Call(self,n):
                if isinstance(n.func,ast.Name) and n.func.id=='__import__' and len(n.args)==1 and isinstance(n.args[0],ast.Constant) and n.args[0].value=='re':return ast.copy_location(ast.Constant(value=None),n)
                return self.generic_visit(n)
        if r.dynamic_module_mutation(NonTargetRegexImport().visit(scan),{'Database'}):return None,'DYNAMIC_BLOCK:DB_CONSTRUCTOR_MUTATION'
        for cls in [n for n in ast.walk(tree) if isinstance(n,ast.ClassDef)]:
            if any(r.text(b).rsplit('.',1)[-1] in ('Database','BoundDatabase','_ObservedConnection') for b in cls.bases):return None,'RECEIVER_UNION_UNPROVEN:SUBCLASS_OVERRIDE'
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='Database']
        if len(calls)!=1:return None,'RECEIVER_UNION_UNPROVEN:EXTRA_OR_MISSING_PRODUCTION_DATABASE_SITE'
        c=calls[0]
        if any(k.arg is None or k.arg in ('statement_observer','placement_metric_sink') and not (isinstance(k.value,ast.Constant) and k.value.value is None) for k in c.keywords):return None,'DYNAMIC_BLOCK:UNPROVEN_PRODUCTION_OBSERVER_OR_SINK'
        rows.append(witness(path,source,c,constructor='inv.db.Database',statement_observer='None default or exact None',placement_metric_sink='None default or exact None',authority='SOURCE_PROVENANCE_ONLY_RUNTIME_BINDING_NULL'))
    return rows,None
def provenance(core,ctors):
    if any(core[p]!=ctors[p] for p in set(core)&set(ctors)):return None,'RECEIVER_UNION_UNPROVEN:SOURCE_INPUT_DISAGREEMENT'
    db=core[CP+'db.py'];union,error=observed_union(db)
    if error:return None,error
    constructors,error=database_constructors(ctors)
    if error:return None,error
    init=function(db,'Database.__init__');args=init.args.kwonlyargs;defaults=init.args.kw_defaults
    for key in ('statement_observer','placement_metric_sink'):
        ix=next((i for i,x in enumerate(args) if x.arg==key),None)
        if ix is None or not isinstance(defaults[ix],ast.Constant) or defaults[ix].value is not None:return None,'RECEIVER_UNION_UNPROVEN:OBSERVABILITY_DEFAULT'
        if not any(isinstance(n,ast.Assign) and r.text(n.value)==key and any(r.text(t)=='self.'+key for t in n.targets) for n in ast.walk(init)):return None,'RECEIVER_UNION_UNPROVEN:OBSERVABILITY_FIELD'
    for path,cls in [(CP+'observation.py','NodeObservation'),(CP+'workspace_api.py','RestrictedWorkspaceRuntime')]:
        if not local_field_proof(core[path],cls,'db','database'):return None,'RECEIVER_UNION_UNPROVEN:SELF_DB_STORE'
    # Closed production construction graph, with all constructor sites consumed
    # from the immutable census. Helpers are AST-bound, not accepted by names.
    chains=[]
    expected={
      (CP+'observer_worker.py','ObservationWorker.__init__','NodeObservation'):'database',
      (CP+'workspace_api.py','RestrictedWorkspaceRuntime.observe','NodeObservation'):'self.db',
      (CP+'workspace_config.py','configured_workspace','RestrictedWorkspaceRuntime'):'database',
      ('tools/remote_workspace_entry.py','setup','RestrictedWorkspaceRuntime'):'db'}
    all_input={**core,**ctors}
    seen=set()
    for path,source in all_input.items():
        for name,f in qualified_functions(source).items():
            for c in ast.walk(f):
                if not isinstance(c,ast.Call) or not isinstance(c.func,ast.Name) or c.func.id not in ('NodeObservation','RestrictedWorkspaceRuntime'):continue
                key=(path,name,c.func.id)
                if key not in expected or key in seen or not c.args or r.text(c.args[0])!=expected[key]:return None,'RECEIVER_UNION_UNPROVEN:EXTRA_OBSERVATION_CONSTRUCTOR'
                seen.add(key);chains.append(witness(path,source,c,argument=expected[key],provenType='inv.db.Database'))
    if seen!=set(expected):return None,'RECEIVER_UNION_UNPROVEN:MISSING_OBSERVATION_CHAIN'
    # Verify concrete actual assignments/forwarding along the three roots.
    checks=[(CP+'observer_worker.py','main','worker = ObservationWorker(db, NodeTLSClient(**tls))'),
      (CP+'app.py','create_configured_app','workspace = configured_workspace(database, identity.tenant_id, settings[\'workspace\'])'),
      (CP+'workspace_config.py','configured_workspace','configured_workspace(database, tenant, target)'),
      ('tools/remote_workspace_entry.py','setup','db = database(config)')]
    for path,name,code in checks:
        f=function(all_input[path],name)
        if code not in r.text(f):return None,'RECEIVER_UNION_UNPROVEN:CONSTRUCTION_CHAIN_CHANGED'
    for path,name,var in [(CP+'observer_worker.py','main','db'),(CP+'app.py','create_configured_app','database')]:
        f=function(all_input[path],name)
        assignments=[n for n in ast.walk(f) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==var for t in n.targets)]
        if len(assignments)!=1 or not isinstance(assignments[0].value,ast.Call) or r.text(assignments[0].value.func)!='Database':return None,'RECEIVER_UNION_UNPROVEN:ROOT_DATABASE_VALUE'
    remote=function(all_input['tools/remote_workspace_entry.py'],'database')
    ret=[n for n in ast.walk(remote) if isinstance(n,ast.Return)]
    if len(ret)!=1 or not isinstance(ret[0].value,ast.Call) or r.text(ret[0].value.func)!='Database':return None,'RECEIVER_UNION_UNPROVEN:REMOTE_RETURN'
    return {'status':'SOURCE_PROVEN_RUNTIME_PENDING','dbSourceSHA256':r.sha(db),'receiverUnion':union,'productionDatabaseConstructors':constructors,'NodeObservationDbUnion':['inv.db.Database'],'constructionChains':chains,
      'productionObservabilityBindings':'SOURCE defaults None; installed runtime/config handlers NOT_PROVEN','BoundDatabase':'Existing exact-tenant borrowing owner; all non-target constructor census references retained, no other entry upgraded','runtimeBinding':None},None
def context_phase(db):
    tree=ast.parse(db);txn=function(db,'Database.transaction')
    if not r.exact_import(tree,'ContextVar','contextvars'):return None,'RULE_NOT_APPLICABLE:CONTEXTVAR_IMPORT'
    binds=[n for n in ast.walk(tree) if '_statement_phase' in r.bound_names(n)]
    if len(binds)!=1:return None,'DYNAMIC_BLOCK:CONTEXTVAR_REBIND'
    init=next((n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_statement_phase' for t in n.targets)),None)
    if not init or r.text(init.value)!="ContextVar('inv_statement_phase', default='outside-transaction')":return None,'RULE_NOT_APPLICABLE:CONTEXTVAR_FACTORY'
    if r.dynamic_module_mutation(tree,{'_statement_phase'}):return None,'DYNAMIC_BLOCK:CONTEXTVAR_MUTATION'
    tokens=[n for n in ast.walk(txn) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='phase_token' for t in n.targets)]
    if len(tokens)!=1 or r.text(tokens[0].value)!="_statement_phase.set('transaction-pre-placement-lock')":return None,'DYNAMIC_BLOCK:PHASE_TOKEN_PRODUCER'
    final=next((n for n in txn.body if isinstance(n,ast.Try) and n.finalbody),None)
    if not final:return None,'DYNAMIC_BLOCK:MISSING_FINALLY_RESET'
    resets=[n for n in final.finalbody for n in ast.walk(n) if isinstance(n,ast.Call) and r.text(n.func)=='_statement_phase.reset']
    if len(resets)!=1 or r.text(resets[0])!='_statement_phase.reset(phase_token)':return None,'DYNAMIC_BLOCK:FOREIGN_CONTEXT_TOKEN'
    tests=[n for n in ast.walk(txn) if isinstance(n,ast.If) and any(isinstance(x,ast.Name) and x.id=='phase' for x in ast.walk(n.test))]
    expected="isinstance(phase, dict) and phase.get('startedNs') is not None"
    if len(tests)!=1 or r.text(tests[0].test)!=expected or tests[0] not in final.finalbody:return None,'DYNAMIC_BLOCK:PHASE_AUTHORITY_PREDICATE'
    metricif=tests[0]
    calls={r.text(n.func) for n in ast.walk(metricif) if isinstance(n,ast.Call)}
    if calls!={'isinstance','phase.get','round','perf_counter_ns','record_placement_metric'}:return None,'DYNAMIC_BLOCK:PHASE_NONMETRIC_EFFECT'
    return {'moduleFactory':witness(CP+'db.py',db,init),'tokenSet':witness(CP+'db.py',db,tokens[0]),'finallyReset':witness(CP+'db.py',db,resets[0]),'metricsOnly':witness(CP+'db.py',db,metricif),'clock':'perf_counter_ns actual clock source retained, not pure conversion'},None
def local_list(source,call):
    fn=next(f for f in qualified_functions(source).values() if f.name=='mark_offline')
    stores=[n for n in ast.walk(fn) if isinstance(n,ast.Name) and n.id=='changed' and isinstance(n.ctx,(ast.Store,ast.Del))]
    assigns=[n for n in ast.walk(fn) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='changed' for t in n.targets)]
    if len(stores)!=1 or len(assigns)!=1 or not isinstance(assigns[0].value,ast.List) or assigns[0].value.elts:return None,'DYNAMIC_BLOCK:LOCAL_CONTAINER_REBIND'
    reason=r.mutation_reason(source,fn,{'changed'},[id(stores[0])])
    if reason:return None,reason
    before=[n for n in ast.walk(fn) if getattr(n,'lineno',0)<call.lineno]
    if any(isinstance(n,(ast.Assign,ast.NamedExpr)) and isinstance(n.value,ast.Name) and n.value.id=='changed' for n in before):return None,'DYNAMIC_BLOCK:LOCAL_CONTAINER_ALIAS'
    if any(isinstance(n,ast.Call) and any(isinstance(x,ast.Name) and x.id=='changed' for x in n.args) for n in before):return None,'DYNAMIC_BLOCK:LOCAL_CONTAINER_ESCAPE'
    if r.text(call.func)!='changed.append':return None,'RULE_NOT_APPLICABLE'
    return {'literalListAssignment':list(r.span(assigns[0])),'receiver':'function-local list','noRebindAliasOrEscapeBeforeCall':True,'returnsListAfterLoop':True},None
