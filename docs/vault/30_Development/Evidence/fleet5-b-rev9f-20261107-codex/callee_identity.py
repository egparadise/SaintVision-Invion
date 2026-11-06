"""Conservative callable authentication for relevant owned-argument bindings.

No runtime callable inference. Frozen-identical decorators/class headers are a
compatibility bound, not a claim that arbitrary decorators are transparent.
"""
import ast
from functools import lru_cache
from source_bindings import Facts,frozen_source
from lexical_bindings import index

@lru_cache(maxsize=32)
def baseline(path):
    try:return Facts(path,frozen_source(path))
    except Exception:return None

def dump(nodes):return [ast.dump(n,include_attributes=False) for n in nodes]

def frozen_call(f,call):
    old=baseline(f.path)
    if not old:return False
    # A retained inherited initializer has no supplied signature. It is never
    # a new binding proof: only the exact old call/function/span may stay outside
    # this binder, after construction identity was separately checked.
    return any(isinstance(n,ast.Call) and old.enclosing(n)==f.enclosing(call)
               and old.witness(n)['span']==f.witness(call)['span']
               and ast.get_source_segment(old.source,n)==ast.get_source_segment(f.source,call)
               for n in ast.walk(old.tree))

def rebound(f,q):
    scope,_,name=q.rpartition('.')
    bindings=index(f)
    if (scope,name) in bindings.writes or bindings.definitions[(scope,name)]!=1:return True
    old=baseline(f.path);allowed=index(old).stars if old else {}
    return any(s==scope and count>allowed.get((s,key),0) for (s,key),count in bindings.stars.items())

def decorators_ok(f,q,node):
    if not node.decorator_list:return True
    old=baseline(f.path);prior=(old.functions.get(q) or old.classes.get(q)) if old else None
    if prior and dump(prior.decorator_list)==dump(node.decorator_list):return True
    for d in node.decorator_list:
        spelling=ast.unparse(d);symbol=f.resolve(d)
        if spelling in {'staticmethod','classmethod'}:
            # Builtin spellings are accepted only without lexical replacement.
            if any(isinstance(n,ast.Name) and n.id==spelling and isinstance(n.ctx,(ast.Store,ast.Del)) for n in ast.walk(f.tree)):return False
            if any(isinstance(n,(ast.Import,ast.ImportFrom)) and any((a.asname or a.name.split('.')[0])==spelling for a in n.names) for n in ast.walk(f.tree)):return False
        elif symbol in {'contextlib.contextmanager','contextlib.asynccontextmanager'}:
            root=d
            while isinstance(root,ast.Attribute):root=root.value
            if not isinstance(root,ast.Name):return False
            if any(isinstance(n,ast.Name) and n.id==root.id and isinstance(n.ctx,(ast.Store,ast.Del)) for n in ast.walk(f.tree)):return False
        else:return False
    return True

def construction(f,q,classes,seen=None):
    seen=set() if seen is None else seen;symbol=f.module+'.'+q
    if symbol in seen:return 'UNRESOLVED:CLASS_CONSTRUCTION_BINDING'
    seen.add(symbol);node=f.classes[q]
    if rebound(f,q):return 'UNRESOLVED:CALLEE_REBOUND'
    if not decorators_ok(f,q,node):return 'UNRESOLVED:CLASS_CONSTRUCTION_BINDING'
    if any(q+'.'+method in f.functions for method in ('__new__','__call__')):return 'UNRESOLVED:CLASS_CONSTRUCTION_BINDING'
    old=baseline(f.path);prior=old.classes.get(q) if old else None
    frozen_header=prior is not None and dump(node.bases+node.keywords)==dump(prior.bases+prior.keywords)
    if node.keywords and not frozen_header:return 'UNRESOLVED:CLASS_CONSTRUCTION_BINDING'
    for base in node.bases:
        target=f.resolve(base)
        if target in classes:
            bf=classes[target];error=construction(bf,target.removeprefix(bf.module+'.'),classes,set(seen))
            if error:return error
        elif target!='builtins.object' and not frozen_header:return 'UNRESOLVED:CLASS_CONSTRUCTION_BINDING'
    return None

def error(f,call,symbol,pair,classes):
    if isinstance(call.func,ast.Name):
        declared=f.defs[''].get(call.func.id)
        # A direct alias followed by a computed assignment must not let the
        # alias resolver substitute a different def and hide this name's Store.
        if declared and declared!=symbol and rebound(f,declared.removeprefix(f.module+'.')):return 'UNRESOLVED:CALLEE_REBOUND'
    # target() represents class calls as Class.__init__, even without a body.
    class_symbol=symbol.removesuffix('.__init__') if symbol else None
    if class_symbol in classes:
        cf=classes[class_symbol];reason=construction(cf,class_symbol.removeprefix(cf.module+'.'),classes)
        if reason:return reason
    if pair:
        receiver,fn=pair;q=symbol.removeprefix(receiver.module+'.')
        # A nested method's class name may itself have been replaced.
        for size in range(1,len(q.split('.'))+1):
            prefix='.'.join(q.split('.')[:size])
            if prefix in receiver.classes or prefix in receiver.functions:
                if rebound(receiver,prefix):return 'UNRESOLVED:CALLEE_REBOUND'
        if not decorators_ok(receiver,q,fn):return 'UNRESOLVED:CALLEE_REBOUND'
    return None
