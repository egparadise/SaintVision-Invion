"""Bounded use-site allowlists. No application/mutant code is executed.

Receiver proofs allow individual current AST nodes from recorded DB producers
and checked owner/yield/forwarding contexts. Namespace and construction uses are
frozen, import-resolved contexts from the pinned source, never method-name grants.
"""
import ast,hashlib,json,subprocess
from collections import Counter,defaultdict
from functools import lru_cache
from source_bindings import Facts,frozen_source,text,sha
PROTECTED_PREFIXES=('inv.db','inv.errors','saintvision.errors','inv.observation','inv.observer_worker','inv.workspace_api','psycopg','builtins','dataclasses')
REFLECTION={'builtins.getattr','builtins.setattr','builtins.delattr','builtins.vars','builtins.globals','builtins.locals','builtins.eval','builtins.exec','builtins.__import__'}
INSTANCE_NAMES={'conn','observed_conn','cursor','db','database','self'}
PROTECTED_CLASS_NAMES={'Database','BoundDatabase','_ObservedConnection','DomainError','InvError','ErrorCategory','ObservationWorker','NodeObservation','RestrictedWorkspaceRuntime'}
def infer_path(source):
    t=ast.parse(source);classes={n.name for n in t.body if isinstance(n,ast.ClassDef)};functions={n.name for n in t.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    if 'Database' in classes and '_ObservedConnection' in classes:return 'services/control-plane/src/inv/db.py'
    if 'DomainError' in classes:return 'services/control-plane/src/inv/errors.py'
    if 'InvError' in classes:return 'src/saintvision/errors.py'
    if 'NodeObservation' in classes:return 'services/control-plane/src/inv/observation.py'
    if 'ObservationWorker' in classes:return 'services/control-plane/src/inv/observer_worker.py'
    if 'RestrictedWorkspaceRuntime' in classes:return 'services/control-plane/src/inv/workspace_api.py'
    if 'create_configured_app' in functions:return 'services/control-plane/src/inv/app.py'
    if 'configured_workspace' in functions:return 'services/control-plane/src/inv/workspace_config.py'
    if 'revoke_channel' in functions:return 'services/control-plane/src/inv/node_channels.py'
    if {'runtime','observe'}<=functions:return 'tools/lan_pilot.py'
    if {'database','setup'}<=functions:return 'tools/remote_workspace_entry.py'
    return None
def protected(canonical):return bool(canonical and any(canonical==p or canonical.startswith(p+'.') for p in PROTECTED_PREFIXES))
def chain_root(n):
    while isinstance(n,(ast.Attribute,ast.Subscript)):n=n.value
    return n.id if isinstance(n,ast.Name) else None
def owner_prefix(n):
    if isinstance(n,ast.Attribute):
        expr=text(n)
        return expr=='self.db' or expr.startswith('self.db.') or expr=='self._conn' or expr.startswith('self._conn.')
    return False
def scope_key(f,n):return f.scope.get(id(n),'')
def context(f,n):
    # Climb the value chain, but not an unrelated function/If/With body.
    current=n
    while id(current) in f.parent:
        p=f.parent[id(current)]
        if isinstance(p,ast.Attribute) and p.value is current or isinstance(p,ast.Subscript) and p.value is current:
            current=p;continue
        if isinstance(p,ast.Call):current=p;continue
        if isinstance(p,(ast.keyword,ast.Starred,ast.List,ast.Tuple,ast.Set,ast.Dict,ast.Lambda,ast.NamedExpr)):
            current=p;continue
        if isinstance(p,(ast.Assign,ast.AnnAssign,ast.AugAssign,ast.Return,ast.Raise,ast.Expr,ast.Yield,ast.YieldFrom)):
            return p
        if isinstance(p,ast.ClassDef):return ('CLASS_HEADER',p.name,tuple(text(x) for x in p.bases),tuple(text(x) for x in p.decorator_list),tuple((x.arg,text(x.value)) for x in p.keywords))
        return current
    return current
def canonical_dump(f,n):
    if isinstance(n,tuple):return repr(n)
    # Resolve imported module/class aliases in an isolated AST copy.
    class Normalize(ast.NodeTransformer):
        def visit_Attribute(self,x):
            def resolve(n):
                if isinstance(n,ast.Name):return f.lookup(n.id,scope_key(f,n) if id(n) in f.scope else scope_key(f,site))
                if isinstance(n,ast.Attribute):
                    parent=resolve(n.value)
                    return parent+'.'+n.attr if parent else None
                return None
            c=resolve(x)
            return ast.copy_location(ast.Name(id=c,ctx=x.ctx),x) if c else self.generic_visit(x)
        def visit_Name(self,x):
            # Original node identity isn't preserved in a copy; use the use-site
            # scope, and only replace imported/defined symbols, not local values.
            c=f.lookup(x.id,scope_key(f,n))
            return ast.copy_location(ast.Name(id=c,ctx=x.ctx),x) if c else x
    site=n
    clone=ast.parse(text(n),mode='eval').body if isinstance(n,ast.expr) else ast.parse(text(n)).body[0]
    return ast.dump(Normalize().visit(clone),include_attributes=False)
def key_for(f,n,tag):
    # Lexical headers affect the meaning of an unchanged body load: a new
    # parameter can shadow an imported class, and a decorator can replace the
    # callable. Bind each use to all enclosing function headers, not whole bodies.
    scope=scope_key(f,n);parts=scope.split('.') if scope else [];headers=[]
    for length in range(1,len(parts)+1):
        q='.'.join(parts[:length]);fn=f.functions.get(q)
        if fn:
            headers.append((q,type(fn).__name__,ast.dump(fn.args,include_attributes=False),tuple(ast.dump(x,include_attributes=False) for x in fn.decorator_list),ast.dump(fn.returns,include_attributes=False) if fn.returns else None,tuple(ast.dump(x,include_attributes=False) for x in getattr(fn,'type_params',[]))))
    stamped_scope=(scope,tuple(headers))
    if tag.startswith('CLASS_DECL:'):
        header=(n.name,tuple(text(x) for x in n.bases),tuple(text(x) for x in n.decorator_list),tuple((x.arg,text(x.value)) for x in n.keywords))
        return (stamped_scope,tag,repr(header))
    c=context(f,n);return (stamped_scope,tag,canonical_dump(f,c))
def class_field_factory_allowed(f,n):
    if not isinstance(n,ast.Name) or f.resolve(n)!='dataclasses.field':return False
    p=f.parent.get(id(n))
    if not isinstance(p,ast.Call) or p.func is not n:return False
    if text(p)=='field(init=False)':return True
    if text(p)!='field(default_factory=dict)':return False
    # The narrow dataclass exception is for the builtin dict factory, not a
    # same-spelling imported/rebound callable. No mutant is executed here.
    for node in ast.walk(f.tree):
        if isinstance(node,ast.Name) and node.id=='dict' and isinstance(node.ctx,(ast.Store,ast.Del)):return False
        if isinstance(node,ast.arg) and node.arg=='dict':return False
        if isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and node.name=='dict':return False
        if isinstance(node,(ast.Import,ast.ImportFrom)) and any((a.asname or a.name.split('.')[0])=='dict' for a in node.names):return False
    return True
REFLECT_NAMESPACES=('sys','importlib','operator','inspect')
PROTECTED_STRINGS={'Database','BoundDatabase','_ObservedConnection','DomainError','InvError','ObservationWorker','NodeObservation','RestrictedWorkspaceRuntime','db','observer','statement_observer','placement_metric_sink','runtime','workspace'}

def reflective(f,n):
    symbol=f.resolve(n)
    return bool(symbol and any(symbol==p or symbol.startswith(p+'.') for p in REFLECT_NAMESPACES))

@lru_cache(maxsize=12)
def baseline_owners(path,factories,parameters=()):
    from owner_transfer import derive
    return derive(Facts(path,frozen_source(path)),factories,dict(parameters))[0]['owners']

def audited_nodes(f,instances=True,factories=(),parameters=None,prior_parameters=(),prior_factories=None):
    from owner_transfer import derive
    ownership,known=derive(f,factories,parameters)
    try:prior=baseline_owners(f.path,tuple(sorted(prior_factories if prior_factories is not None else factories)),tuple(prior_parameters))
    except subprocess.CalledProcessError:prior={}
    def relevant(name,q):
        parts=q.split('.') if q else []
        return known(name,q) or any(name in prior.get('.'.join(parts[:i]),[]) for i in range(len(parts),-1,-1))
    for n in ast.walk(f.tree):
        if isinstance(n,(ast.Name,ast.Attribute,ast.Subscript)) and reflective(f,n.value if isinstance(n,ast.Subscript) else n):yield n,'REFLECTION_NAMESPACE:'+str(f.resolve(n.value if isinstance(n,ast.Subscript) else n))
        elif isinstance(n,ast.Constant) and isinstance(n.value,str) and (n.value in PROTECTED_STRINGS or n.value.startswith(('inv.db','inv.observer_worker','inv.observation','inv.workspace_api'))):
            current=n
            while id(current) in f.parent and not isinstance(current,(ast.stmt,ast.FunctionDef,ast.ClassDef)):
                current=f.parent[id(current)]
            if any(isinstance(x,(ast.Name,ast.Attribute)) and (reflective(f,x) or f.resolve(x) in REFLECTION) for x in ast.walk(current)):yield n,'PROTECTED_REFLECTION_STRING:'+n.value
        elif isinstance(n,ast.ClassDef) and n.name in PROTECTED_CLASS_NAMES:yield n,'CLASS_DECL:'+n.name
        elif isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in PROTECTED_CLASS_NAMES:yield n,'CLASS_NAME_REBIND:'+n.name
        elif isinstance(n,ast.Name) and isinstance(n.ctx,(ast.Load,ast.Store,ast.Del)):
            c=f.resolve(n)
            if (c in PROTECTED_PREFIXES or any(factory.startswith((c or '')+'.') for factory in factories)) and isinstance(n.ctx,ast.Load):
                parent=f.parent.get(id(n))
                if isinstance(parent,ast.Attribute) and f.resolve(parent) and (parent.attr in PROTECTED_CLASS_NAMES or f.resolve(parent) in factories):c=f.resolve(parent)
            if c in factories:yield n,'FORWARDING_FACTORY_SYMBOL:'+c
            elif protected(c):yield n,'SYMBOL:'+str(c)
            elif instances and relevant(n.id,scope_key(f,n)):yield n,'INSTANCE:'+n.id
        elif isinstance(n,(ast.Attribute,ast.Subscript)) and isinstance(n.ctx,(ast.Store,ast.Del)):
            c=f.resolve(n)
            # Every write in this bounded source scope has an individual frozen
            # context. An unresolved receiver is not silently exempted.
            yield n,'WRITE_USE:'+str(c or text(n))
        elif isinstance(n,ast.Attribute) and isinstance(n.ctx,ast.Load) and chain_root(n)=='self':
            yield n,'OWNER_READ:'+text(n)
        elif isinstance(n,ast.Attribute) and n.attr in ('__dict__','__class__','__setattr__','__delattr__','__getattribute__'):
            yield n,'INTROSPECTION:'+n.attr
def globals_dispatch(f,node):
    # Exactly the existing CLI's closed command dispatch; no protected class or
    # receiver may be selected or passed. This is not a generic globals grant.
    if f.path!='tools/lan_pilot.py' or f.enclosing(node)!='main':return False
    c=context(f,node)
    if isinstance(c,ast.Expr):c=c.value
    expected="globals()[args.command.replace('-', '_')](args)"
    if text(c)!=expected:return False
    b=Facts(f.path,frozen_source(f.path));baseline=[x for x in ast.walk(b.tree) if isinstance(x,ast.Call) and text(x)==expected]
    if ast.dump(f.functions['main'],include_attributes=False)!=ast.dump(b.functions['main'],include_attributes=False):return False
    if len(baseline)!=1 or sha(ast.get_source_segment(f.source,c))!=sha(ast.get_source_segment(b.source,baseline[0])):return False
    def commands(facts):
        return sorted({x.args[0].value for x in ast.walk(facts.functions['main']) if isinstance(x,ast.Call) and text(x.func)=='commands.add_parser' and x.args and isinstance(x.args[0],ast.Constant) and isinstance(x.args[0].value,str)})
    if commands(f)!=commands(b):return False
    names={x.replace('-','_') for x in commands(f)}
    if not names or not names<={x.name for x in f.tree.body if isinstance(x,ast.FunctionDef)}:return False
    return not any(isinstance(x,ast.Name) and (x.id in INSTANCE_NAMES or protected(f.resolve(x))) and x.id!='globals' for x in ast.walk(c))
@lru_cache(maxsize=12)
def baseline_sites(path,instances,factories,parameters=()):
    f=Facts(path,frozen_source(path));return Counter(key_for(f,n,tag) for n,tag in audited_nodes(f,instances,factories,dict(parameters),parameters,factories))
def module_uses(source,path=None,instances=True,factories=None,parameter_context=None):
    path=path or infer_path(source)
    if not path:return None,'UNRESOLVED:SOURCE_SCOPE_NOT_IDENTIFIED'
    if factories is None:
        from forwarding_discovery import baseline
        factories=baseline()['ownerFactorySymbols']
    explicit_parameters=parameter_context is not None
    if parameter_context is None and instances:
        from parameter_flow import default_frozen
        parameter_context=default_frozen()
    parameter_context=parameter_context or {}
    params=parameter_context.get('parameters',{}).get(path,{})
    prior=parameter_context.get('frozenParameterFacts',{}).get(path,{})
    prior_key=tuple((q,tuple(v)) for q,v in sorted(prior.items()))
    prior_factories=tuple(sorted(parameter_context.get('frozenOwnerFactorySymbols',factories)))
    factories=tuple(sorted(parameter_context.get('ownerFactorySymbols',factories)))
    f=Facts(path,source)
    try:allowed=baseline_sites(path,instances,prior_factories,prior_key).copy()
    except subprocess.CalledProcessError:return None,'UNRESOLVED:NO_FROZEN_USE_SITE_SCOPE'
    used=[]
    for n,tag in audited_nodes(f,instances,factories,params,prior_key,prior_factories):
        if class_field_factory_allowed(f,n):continue
        if f.resolve(n)=='builtins.globals' and isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load):
            if not globals_dispatch(f,n):return None,'DYNAMIC_BLOCK:NAMESPACE_USE_NOT_ALLOWLISTED'
        k=key_for(f,n,tag)
        if allowed[k]<=0:return None,('UNRESOLVED:RELEVANT_REFLECTION_USE_NOT_ALLOWLISTED:' if tag.startswith(('REFLECTION_NAMESPACE:','PROTECTED_REFLECTION_STRING:')) else 'DYNAMIC_BLOCK:USE_SITE_NOT_ALLOWLISTED:')+tag
        allowed[k]-=1;used.append(k)
    from owner_transfer import derive
    return {'path':path,'sourceSHA256':sha(source),'useSiteCount':len(used),'allowlistSHA256':sha(json.dumps(sorted((repr(k),v) for k,v in baseline_sites(path,instances,prior_factories,prior_key).items()))),'boundedOwnerPropagation':derive(f,factories,params)[0],'explicitFullParameterContext':explicit_parameters,'policy':'No new protected uses vs frozen72028; current/frozen ownership parameters and names audited, frozen-only allowlist. Individual receiver proof/full provenance required. No arbitrary Python reflection/heap completeness or runtime authority.'},None
def receiver_uses(source,fn,receivers,allowed_stores=(),allowed_forwards=(),records=(),calls=(),allow_yield=False,extra_load_nodes=()):
    allowed=set(allowed_stores);loads=set(extra_load_nodes);parents={id(c):n for n in ast.walk(fn) for c in ast.iter_child_nodes(n)}
    byspan={(x['line'],x['column'],x['endLine'],x['endColumn']):x for x in records}
    dbspans={(x['line'],x['column'],x['endLine'],x['endColumn']) for x in calls if x['classification']=='RESOLVED_DB_RECORD'}
    for n in ast.walk(fn):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('execute','cursor','transaction') and isinstance(n.func.value,ast.Name) and n.func.value.id in receivers:
            s=(n.lineno,n.col_offset,n.end_lineno,n.end_col_offset);record=byspan.get(s)
            if record and s in dbspans and sha(ast.get_source_segment(source,n))==record['expressionSHA256']:loads.add(id(n.func.value))
        if id(n) in set(allowed_forwards):
            loads.update(id(x) for x in ast.walk(n.value) if isinstance(x,ast.Name) and isinstance(x.ctx,ast.Load) and x.id in receivers)
        if allow_yield and isinstance(n,ast.Yield) and isinstance(n.value,ast.Name) and n.value.id in receivers:loads.add(id(n.value))
    for n in ast.walk(fn):
        if isinstance(n,ast.Name) and n.id in receivers:
            if isinstance(n.ctx,ast.Load) and id(n) not in loads:return None,'DYNAMIC_BLOCK:RECEIVER_LOAD_NOT_ALLOWLISTED'
            if isinstance(n.ctx,(ast.Store,ast.Del)) and id(n) not in allowed:return None,'DYNAMIC_BLOCK:RECEIVER_BINDING_NOT_ALLOWLISTED'
        if isinstance(n,ast.Attribute) and isinstance(n.ctx,(ast.Store,ast.Del)) and chain_root(n) in receivers:return None,'DYNAMIC_BLOCK:RECEIVER_ATTRIBUTE_WRITE_NOT_ALLOWLISTED'
    return {'receiverLoadSites':len(loads),'policy':'Recorded execute receivers and individually checked forwarding/yield contexts only'},None
