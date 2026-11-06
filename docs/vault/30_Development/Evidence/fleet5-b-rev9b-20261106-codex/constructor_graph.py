"""Derived narrow constructor graph, including every production/harness caller."""
import ast,copy,subprocess
from functools import lru_cache
from source_bindings import Facts,TARGETS,constructor_census,frozen_source,sha,text,span
DB='inv.db.Database';UNKNOWN='UNRESOLVED'
@lru_cache(maxsize=1)
def base_census():return constructor_census()
@lru_cache(maxsize=64)
def frozen_hash(path):return sha(frozen_source(path))
def current_census(sources):
    b=base_census();changed={}
    for p,s in sources.items():
        try:old_hash=frozen_hash(p)
        except subprocess.CalledProcessError:old_hash=None
        if old_hash!=sha(s):changed[p]=s
    out=copy.deepcopy(b)
    if not changed:return out
    out['sourceFiles']=[{**r,'bytes':len(changed[r['path']].encode()),'sha256':sha(changed[r['path']])} if r['path'] in changed else r for r in out['sourceFiles']]
    known={r['path'] for r in out['sourceFiles']}
    out['sourceFiles'] += [{'path':p,'bytes':len(s.encode()),'sha256':sha(s),'scope':'HARNESS_ONLY_PROVENANCE' if p.startswith('tests/') else 'PRODUCTION_SOURCE','sourceKind':'NEW_AST_INPUT_NOT_IN_FROZEN_CENSUS'} for p,s in changed.items() if p not in known]
    for key in ('production','harness','unresolvedConstructorBindings'):
        out[key]=[r for r in out[key] if r['source']['path'] not in changed]
    for p,s in changed.items():
        f=Facts(p,s)
        for n in ast.walk(f.tree):
            if not isinstance(n,ast.Call):continue
            target=f.resolve(n.func);short=text(n.func).rsplit('.',1)[-1]
            if target not in TARGETS and short not in {x.rsplit('.',1)[1] for x in TARGETS}:continue
            row={'constructor':target or 'UNRESOLVED:'+short,'calleeSpelling':text(n.func),'source':f.witness(n),'argument0':text(n.args[0]) if n.args else None,'argument0AST':ast.dump(n.args[0],include_attributes=False) if n.args else None,'importAliases':f.visible_aliases(f.scope[id(n)]),'scope':'HARNESS_ONLY_PROVENANCE' if p.startswith('tests/') else 'PRODUCTION_SOURCE'}
            out['harness' if p.startswith('tests/') else 'production'].append(row)
            if target not in TARGETS:out['unresolvedConstructorBindings'].append(row)
    return out
def helper_return(f,target):
    qual=target.removeprefix(f.module+'.');fn=f.functions.get(qual)
    if not fn or '.' in qual:return None,'RECEIVER_UNION_UNPROVEN:NOT_SINGLE_LOCAL_HELPER'
    if not isinstance(fn,ast.FunctionDef) or fn.decorator_list or fn.args.defaults or any(x is not None for x in fn.args.kw_defaults):return None,'RECEIVER_UNION_UNPROVEN:HELPER_CALLABLE_BINDING'
    if len([n for n in f.tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==qual])!=1:return None,'RECEIVER_UNION_UNPROVEN:HELPER_DEFINITION'
    for n in ast.walk(f.tree):
        if isinstance(n,ast.Name) and n.id==qual and isinstance(n.ctx,(ast.Store,ast.Del)):return None,'RECEIVER_UNION_UNPROVEN:HELPER_REBIND'
        if isinstance(n,(ast.Import,ast.ImportFrom)) and any((a.asname or a.name)==qual for a in n.names):return None,'RECEIVER_UNION_UNPROVEN:HELPER_IMPORT_SHADOW'
    body=[n for n in fn.body if not (isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str))]
    if len(body)!=1 or not isinstance(body[0],ast.Return) or not isinstance(body[0].value,ast.Call) or f.resolve(body[0].value.func)!=DB:return None,'RECEIVER_UNION_UNPROVEN:HELPER_RETURN'
    return {'helper':target,'source':f.witness(fn),'returnType':DB,'singleLocalReturn':True,'noNameRebindingOrImportShadow':True},None
def prove(sources):
    census=current_census(sources);facts={p:Facts(p,s) for p,s in sources.items()}
    if any(r['scope']=='PRODUCTION_SOURCE' for r in census['unresolvedConstructorBindings']):return None,'RECEIVER_UNION_UNPROVEN:CONSTRUCTOR_BINDING'
    production=census['production'];nodes=[]
    for row in production:
        p=row['source']['path'];f=facts.get(p)
        if not f:return None,'RECEIVER_UNION_UNPROVEN:UNCATALOGUED_PRODUCTION_SOURCE'
        c=next((n for n in ast.walk(f.tree) if isinstance(n,ast.Call) and span(n)==row['source']['span']),None)
        if not c or not c.args:return None,'RECEIVER_UNION_UNPROVEN:CONSTRUCTOR_ARGUMENT'
        nodes.append((row,f,c,f.enclosing(c)))
    incoming={c:set() for c in TARGETS};params={};helpers={};helper_error=[]
    # Functions whose parameters forward into constructors (and their callers)
    # are discovered from the current AST, not from a hand-written root list.
    tracked={f.module+'.'+q for _,f,_,q in nodes}
    allcalls=[]
    for f in facts.values():
        for n in ast.walk(f.tree):
            if isinstance(n,ast.Call):allcalls.append((f,n,f.enclosing(n),f.resolve(n.func)))
    for _ in range(8):
        before=len(tracked)
        tracked.update(f.module+'.'+q for f,n,q,target in allcalls if q and target in tracked)
        if len(tracked)==before:break
    def value(n,f,q,env):
        if isinstance(n,ast.Name):return env.get(n.id,{UNKNOWN})
        if isinstance(n,ast.Attribute) and text(n)=='self.db':
            klass=f.module+'.'+q.split('.')[0];return incoming.get(klass,{UNKNOWN})
        if isinstance(n,ast.IfExp):return value(n.body,f,q,env)|value(n.orelse,f,q,env)
        if isinstance(n,ast.Call):
            target=f.resolve(n.func)
            if target==DB:return {DB}
            if target and target.startswith(f.module+'.') and target.removeprefix(f.module+'.') in f.functions:
                proof,error=helper_return(f,target)
                if proof:helpers[target]=proof;return {DB}
                # Local helpers are needed only when their result is used as a
                # DB constructor input; callers below decide whether UNKNOWN is
                # relevant, rather than waiving a foreign return.
                return {UNKNOWN}
            return {UNKNOWN}
        return {UNKNOWN}
    def environment(f,q,line):
        fn=f.functions.get(q)
        if not fn:return {}
        env={}
        for arg in fn.args.posonlyargs+fn.args.args+fn.args.kwonlyargs:
            if q.endswith('.__init__') and arg.arg=='database':env[arg.arg]=incoming.get(f.module+'.'+q.rsplit('.',1)[0],set())
            else:env[arg.arg]=params.get((f.module+'.'+q,arg.arg),set())
        assigns=sorted((n for n in ast.walk(fn) if isinstance(n,(ast.Assign,ast.AnnAssign,ast.NamedExpr)) and f.enclosing(n)==q and n.lineno<line),key=lambda n:(n.lineno,n.col_offset))
        for n in assigns:
            targets=n.targets if isinstance(n,ast.Assign) else [n.target]
            v=value(n.value,f,q,env)
            for target in targets:
                if isinstance(target,ast.Name):env[target.id]=v
                elif isinstance(target,ast.Tuple) and isinstance(n.value,ast.Tuple):
                    for lhs,rhs in zip(target.elts,n.value.elts):
                        if isinstance(lhs,ast.Name):env[lhs.id]=value(rhs,f,q,env)
        return env
    for _ in range(16):
        before=(repr(incoming),repr(params))
        for f,c,q,target in allcalls:
            if target not in tracked or not c.args:continue
            tf=next((ff for ff in facts.values() if target.startswith(ff.module+'.') and target.removeprefix(ff.module+'.') in ff.functions),None)
            if not tf:continue
            tq=target.removeprefix(tf.module+'.');fn=tf.functions[tq];args=fn.args.posonlyargs+fn.args.args
            ev=environment(f,q,c.lineno)
            for arg,expr in zip(args,c.args):params.setdefault((target,arg.arg),set()).update(value(expr,f,q,ev))
        for row,f,c,q in nodes:incoming[row['constructor']].update(value(c.args[0],f,q,environment(f,q,c.lineno)))
        if before==(repr(incoming),repr(params)):break
    proofs=[]
    for row,f,c,q in nodes:
        types=value(c.args[0],f,q,environment(f,q,c.lineno))
        if types!={DB}:return None,'RECEIVER_UNION_UNPROVEN:CONSTRUCTOR_INPUT:'+row['constructor']
        # Re-validate every directly used local helper, including module-level
        # rebindings that an import-only alias table cannot erase.
        if isinstance(c.args[0],ast.Call):
            target=f.resolve(c.args[0].func)
            if target and target.startswith(f.module+'.'):
                hp,err=helper_return(f,target)
                if err:return None,err
        proofs.append({**row,'provenDbInputUnion':sorted(types),'derivation':'AST import aliases + current local assignments/helper returns + all constructor/function callers fixed point'})
    if any(v!={DB} for v in incoming.values()):return None,'RECEIVER_UNION_UNPROVEN:INCOMPLETE_CLASS_INPUT_UNION'
    return {'census':census,'productionConstructorProofs':proofs,'classDbInputUnions':{k:sorted(v) for k,v in incoming.items()},'localHelperProofs':list(helpers.values()),'derivedCallersNotHandwritten':True,'runtimeBinding':None,'actualRuntimeB':0},None
