"""Finite relevant-reflection audit for every parsed source-view production file."""
import ast
from collections import Counter
from functools import lru_cache
from source_bindings import Facts,frozen_source,sha,text
MODULES={'inv.db','inv.errors','inv.observer_worker','inv.observation','inv.workspace_api','inv.workspace_config'}
NAMES={'Database','BoundDatabase','_ObservedConnection','DomainError','ObservationWorker','NodeObservation','RestrictedWorkspaceRuntime','WorkspaceAPI','configured_workspace'}
APIS={'operator.attrgetter','operator.methodcaller','inspect.getattr_static','inspect.getmembers','builtins.getattr','builtins.__import__'}

def literal(n,depth=0):
    if depth>4:return None
    if isinstance(n,ast.Constant) and isinstance(n.value,str) and len(n.value)<=512:return n.value
    if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Add):
        a,b=literal(n.left,depth+1),literal(n.right,depth+1)
        if a is not None and b is not None and len(a+b)<=512:return a+b
    return None

def resolve_aliases(f):
    for _ in range(16):
        changed=False
        for n in ast.walk(f.tree):
            if isinstance(n,(ast.Assign,ast.AnnAssign)):
                targets=n.targets if isinstance(n,ast.Assign) else [n.target];symbol=f.resolve(n.value)
                if symbol:
                    for target in targets:
                        if isinstance(target,ast.Name) and f.aliases[f.scope[id(n)]].get(target.id)!=symbol:
                            f.aliases[f.scope[id(n)]][target.id]=symbol;changed=True
        if not changed:break

def relevant_string(value,symbols,dotted_only=False):
    if value is None:return False
    modules=MODULES|{s.rsplit('.',1)[0] for s in symbols if '.' in s}
    if any(value==m or value.startswith(m+'.') or value.startswith(m+':') for m in modules):return True
    return not dotted_only and (value in NAMES or value in symbols or value in {s.rsplit('.',1)[-1] for s in symbols})

def keys(n,symbol):
    """Only the already enumerated APIs; no arbitrary string interpretation.

    None is an unknown key, including missing/spread arguments or enumeration.
    The object argument of getattr is deliberately not a name/key argument.
    """
    if isinstance(n,ast.Subscript):return [n.slice] if symbol=='sys.modules' else [None]
    index=1 if symbol in {'builtins.getattr','inspect.getattr_static'} else 0
    if symbol=='inspect.getmembers':return [None]
    if symbol=='operator.attrgetter':return list(n.args) or [None]
    if len(n.args)>index:return [n.args[index]]
    names={'name','key','module'}
    matches=[k.value for k in n.keywords if k.arg in names]
    return matches or [None]

def hits(f,symbols=()):
    resolve_aliases(f);rows=[]
    def api(symbol):return symbol in APIS or bool(symbol and (symbol=='sys.modules' or symbol.startswith(('sys.modules.','importlib.'))))
    for n in ast.walk(f.tree):
        if not isinstance(n,(ast.Call,ast.Subscript)):continue
        symbol=f.resolve(n.func if isinstance(n,ast.Call) else n.value)
        values=[literal(x) for x in ast.walk(n) if isinstance(x,(ast.Constant,ast.BinOp))]
        refs=[f.resolve(x) for x in ast.walk(n) if isinstance(x,(ast.Name,ast.Attribute))]
        relevant=any(relevant_string(x,symbols) for x in values) or any(relevant_string(x,symbols) for x in refs)
        # Optional finite tightening: a protected dotted path passed to ANY call
        # is relevant, including pkgutil.resolve_name. Bare log strings are not.
        dotted=isinstance(n,ast.Call) and any(relevant_string(literal(x),symbols,True) for x in n.args+[k.value for k in n.keywords])
        unknown=api(symbol) and any(literal(k) is None for k in keys(n,symbol))
        if not (api(symbol) and relevant or dotted or unknown):continue
        kind='ENUMERATED_REFLECTION_NONLITERAL_KEY' if unknown else 'PROTECTED_DOTTED_CALL_STRING' if dotted and not api(symbol) else 'ENUMERATED_RELEVANT_REFLECTION'
        witness=f.witness(n);rows.append({'kind':kind,'api':symbol,'source':witness,'expressionSHA256':sha(ast.get_source_segment(f.source,n)),'expression':text(n)})
    return rows

def key(row):return (row['kind'],row['api'],row['source']['function'],row['expressionSHA256'])
@lru_cache(maxsize=64)
def frozen_hits(path,symbols):
    try:return hits(Facts(path,frozen_source(path)),symbols)
    except Exception as e:
        # A new fixture-only path has no trusted baseline. Parsing/read failures
        # must not create an allowlist for a relevant use.
        return []

def audit(f,symbols=()):
    symbols=tuple(sorted(set(symbols)));current=hits(f,symbols);allowed=Counter(key(x) for x in frozen_hits(f.path,symbols));violations=[]
    for row in current:
        k=key(row)
        if allowed[k]:allowed[k]-=1
        else:violations.append(row)
    return {'path':f.path,'sourceSHA256':sha(f.source),'scope':'HARNESS_ONLY_PROVENANCE' if f.path.startswith('tests/') else 'PRODUCTION_SOURCE','hits':current,'newRelevantHits':violations,
            'bound':'Enumerated APIs: unprovable module/name/key is relevant UNKNOWN; str Constant <=512 chars or Add tree depth <=4. Plus protected dotted literal call arguments. Exact expression bytes/function/multiplicity vs frozen72028; not arbitrary Python reflection completeness.'}
