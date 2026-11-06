"""Bounded syntactic ownership relevance; no Python heap/type completeness claim."""
import ast
from collections import defaultdict
PREFIXES=('inv.db','inv.errors','saintvision.errors','inv.observation','inv.observer_worker','inv.workspace_api','psycopg','builtins','dataclasses')
SEEDS={'conn','observed_conn','cursor','db','database','self'}

def protected(symbol):return bool(symbol and any(symbol==p or symbol.startswith(p+'.') for p in PREFIXES))

def derive(f,factories=()):
    owners=defaultdict(set)
    def scope(n):return f.scope.get(id(n),'')
    def known(name,q):
        parts=q.split('.') if q else []
        return name in SEEDS or any(name in owners['.'.join(parts[:i])] for i in range(len(parts),-1,-1))
    def owned(n,q):
        if n is None:return False
        if isinstance(n,ast.Name):return known(n.id,q)
        if isinstance(n,(ast.Attribute,ast.Subscript)):return owned(n.value,q)
        if isinstance(n,ast.Call):
            return protected(f.resolve(n.func)) or f.resolve(n.func) in factories or owned(n.func,q) or any(owned(x,q) for x in n.args) or any(owned(x.value,q) for x in n.keywords)
        if isinstance(n,(ast.List,ast.Tuple,ast.Set)):return any(owned(x,q) for x in n.elts)
        if isinstance(n,ast.Dict):return any(owned(x,q) for x in n.keys+n.values if x is not None)
        if isinstance(n,(ast.ListComp,ast.SetComp,ast.GeneratorExp)):return owned(n.elt,q) or any(owned(x.iter,q) for x in n.generators)
        if isinstance(n,ast.DictComp):return owned(n.key,q) or owned(n.value,q) or any(owned(x.iter,q) for x in n.generators)
        if isinstance(n,ast.IfExp):return owned(n.body,q) or owned(n.orelse,q)
        if isinstance(n,ast.Starred):return owned(n.value,q)
        return False
    def bind(target,q):
        if isinstance(target,ast.Name):owners[q].add(target.id)
        elif isinstance(target,(ast.Tuple,ast.List)):
            for n in target.elts:bind(n,q)
        elif isinstance(target,ast.Starred):bind(target.value,q)
        elif isinstance(target,(ast.Attribute,ast.Subscript)):bind(target.value,q)
    nodes=list(ast.walk(f.tree))
    # Monotone finite union over the names present in this one bounded AST.
    # Relevant unknown escapes are refused by use-site checks, not certified here.
    while True:
        before=sum(len(v) for v in owners.values())
        for n in nodes:
            q=scope(n)
            if isinstance(n,(ast.Assign,ast.AnnAssign,ast.NamedExpr)) and owned(n.value,q):
                for t in n.targets if isinstance(n,ast.Assign) else [n.target]:bind(t,q)
            elif isinstance(n,(ast.For,ast.AsyncFor,ast.comprehension)) and owned(n.iter,q):bind(n.target,q)
            elif isinstance(n,(ast.With,ast.AsyncWith)):
                for item in n.items:
                    if item.optional_vars and owned(item.context_expr,q):bind(item.optional_vars,q)
        if sum(len(v) for v in owners.values())==before:break
    returns=[]
    for q,fn in sorted(f.functions.items()):
        r=[n for n in ast.walk(fn) if isinstance(n,ast.Return) and f.enclosing(n)==q]
        if r and all(owned(n.value,q) for n in r):returns.append(f.module+'.'+q)
    return {'owners':{q:sorted(v) for q,v in sorted(owners.items())},'ownerReturningFunctions':returns,
            'scope':'Bounded conservative owner/container relevance only; full provenance/use-site checks required'},known
