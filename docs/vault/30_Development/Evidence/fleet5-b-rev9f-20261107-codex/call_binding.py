"""Lexical call target/signature binding only; full source provenance required."""
import ast

def arguments(call,fn,bound=False):
    positional=list(fn.args.posonlyargs)+list(fn.args.args)
    if bound:
        if not positional:return None,'UNRESOLVED:BOUND_CALL_WITHOUT_RECEIVER_PARAMETER'
        positional=positional[1:]
    mapping={};known={a.arg for a in positional+list(fn.args.kwonlyargs)};posonly={a.arg for a in fn.args.posonlyargs}
    for i,value in enumerate(call.args):
        if isinstance(value,ast.Starred):return None,'UNRESOLVED:OWNED_ARGUMENT_STAR_BINDING'
        if i>=len(positional):
            if fn.args.vararg:return None,'UNRESOLVED:OWNED_ARGUMENT_VARIADIC_BINDING'
            return None,'UNRESOLVED:ARGUMENT_POSITION_OUT_OF_RANGE'
        mapping[positional[i].arg]=value
    keywords=[]
    for keyword in call.keywords:
        if keyword.arg is not None:keywords.append((keyword.arg,keyword.value));continue
        if not isinstance(keyword.value,ast.Dict) or any(not isinstance(k,ast.Constant) or not isinstance(k.value,str) for k in keyword.value.keys):return None,'UNRESOLVED:OWNED_ARGUMENT_KEYWORD_SPREAD_BINDING'
        keywords.extend((k.value,v) for k,v in zip(keyword.value.keys,keyword.value.values))
    extra=[]
    for name,value in keywords:
        if name in mapping:return None,'UNRESOLVED:DUPLICATE_ARGUMENT_BINDING'
        if name not in known:
            if fn.args.kwarg:extra.append((name,value));continue
            return None,'UNRESOLVED:UNKNOWN_ARGUMENT_BINDING'
        if name in posonly:return None,'UNRESOLVED:UNKNOWN_ARGUMENT_BINDING'
        mapping[name]=value
    if extra:
        if len({name for name,_ in extra})!=len(extra):return None,'UNRESOLVED:DUPLICATE_ARGUMENT_BINDING'
        pack=ast.Dict(keys=[ast.Constant(name) for name,_ in extra],values=[value for _,value in extra]);pack._binding_members=[value for _,value in extra];pack._binding_kind='EXPLICIT_KEYWORDS_TO_KWARG_DICT'
        mapping[fn.args.kwarg.arg]=pack
    return mapping,None

def registry(facts):
    functions={};classes={}
    for f in facts.values():
        functions.update({f.module+'.'+q:(f,fn) for q,fn in f.functions.items()})
        classes.update({f.module+'.'+q:f for q in f.classes})
    return functions,classes

def target(f,call,functions,classes,canonical=lambda s:s):
    symbol=canonical(f.resolve(call.func));bound=False
    if symbol in classes:
        symbol+='.__init__';bound=True
    elif symbol not in functions and isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name):
        q=f.enclosing(call);parts=q.split('.')
        for i in range(len(parts)-1,0,-1):
            owner='.'.join(parts[:i]);method='.'.join(parts[:i+1]);enclosing=f.functions.get(method)
            if owner not in f.classes or not enclosing:continue
            args=enclosing.args.posonlyargs+enclosing.args.args
            if args and call.func.value.id==args[0].arg:
                symbol=f.module+'.'+owner+'.'+call.func.attr;bound=True
                break
    pair=functions.get(symbol)
    if pair is None and isinstance(call.func,ast.Name):
        # An import can shadow the lexical def. Preserve its identity only to
        # diagnose CALLEE_REBOUND, never to authorize the shadowing import.
        parts=f.scope[id(call)].split('.') if f.scope[id(call)] else []
        for size in range(len(parts),-1,-1):
            candidate=f.defs['.'.join(parts[:size])].get(call.func.id)
            if candidate in functions:
                symbol=candidate;pair=functions[candidate];break
    if pair:
        fn=pair[1];decorators={ast.unparse(x) for x in fn.decorator_list}
        if 'staticmethod' in decorators:bound=False
        elif 'classmethod' in decorators:bound=True
        return symbol,pair,bound
    return symbol,None,bound
