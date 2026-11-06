"""Finite lexical parameter ownership fixed point; no runtime/heap certificate."""
import ast
from collections import defaultdict
from functools import lru_cache
from source_bindings import Facts,frozen_source,sha
from owner_transfer import evaluate
import call_binding as cb

def solve(sources,factories=(),exports=None,initial=None):
    # This operates only on supplied proof bodies. Source-universe reflection and
    # missing-file checks remain independent required parts of full provenance.
    from forwarding_discovery import canonical,aliases
    exports=exports or {};facts={p:Facts(p,s) for p,s in sorted(sources.items())}
    for f in facts.values():aliases(f,exports)
    functions,classes=cb.registry(facts);params={p:defaultdict(set,{q:set(v) for q,v in (initial or {}).get(p,{}).items()}) for p in facts}
    factory_set=set(factories);bindings={};unresolved={}
    calls=[];called=set()
    for p,f in facts.items():
        for call in ast.walk(f.tree):
            if not isinstance(call,ast.Call):continue
            symbol,pair,bound_receiver=cb.target(f,call,functions,classes,lambda s:canonical(s,exports))
            if pair is None:continue
            mapping,error=cb.arguments(call,pair[1],bound_receiver)
            calls.append((p,f,call,symbol,pair,bound_receiver,mapping,error));called.add(symbol)
    bound=1+len(functions)+sum(len(fn.args.posonlyargs+fn.args.args+fn.args.kwonlyargs) for _,fn in functions.values())
    for iteration in range(bound):
        before=(sum(len(v) for scopes in params.values() for v in scopes.values()),len(factory_set))
        local={}
        for p,f in facts.items():
            data,known,owned=evaluate(f,factory_set,params[p]);local[p]=(data,known,owned)
            factory_set.update(x for x in data['ownerReturningFunctions'] if x in called)
        for p,f,call,symbol,pair,bound_receiver,mapping,error in calls:
            owned=local[p][2]
            receiver,fn=pair;q=f.enclosing(call);span=(call.lineno,call.col_offset,call.end_lineno,call.end_col_offset)
            if error:
                if any(owned(v,q) for v in call.args+[k.value for k in call.keywords]):
                    key=(p,span);unresolved[key]={'source':f.witness(call),'target':symbol,'reason':error}
                continue
            target_q=symbol.removeprefix(receiver.module+'.')
            for name,value in mapping.items():
                if not owned(value,q):continue
                params[receiver.path][target_q].add(name)
                key=(p,span,symbol,name)
                if key not in bindings:
                    members=getattr(value,'_binding_members',[value])
                    evidence=[{'span':[v.lineno,v.col_offset,v.end_lineno,v.end_col_offset],'sourceExpressionSHA256':sha(ast.get_source_segment(f.source,v))} for v in members]
                    bindings[key]={'source':f.witness(call),'target':symbol,'targetPath':receiver.path,'formal':name,'boundReceiverSkipped':bound_receiver,'argument':ast.unparse(value),'argumentEvidence':evidence,'argumentForm':getattr(value,'_binding_kind','ORIGINAL_SOURCE_EXPRESSION'),'binding':'ACTUAL_POSITION_OR_KEYWORD_NAME; packs cite their original expression members, never a synthetic source span'}
        after=(sum(len(v) for scopes in params.values() for v in scopes.values()),len(factory_set))
        if after==before:break
    else:return None,'UNRESOLVED:PARAMETER_OWNERSHIP_DID_NOT_CONVERGE'
    result={'parameters':{p:{q:sorted(v) for q,v in sorted(scopes.items()) if v} for p,scopes in sorted(params.items())},
            'ownerFactorySymbols':sorted(factory_set),'bindings':[bindings[k] for k in sorted(bindings)],'unresolved':[unresolved[k] for k in sorted(unresolved)],
            'iterations':iteration+1,'sourceFiles':[{'path':p,'sha256':sha(s)} for p,s in sorted(sources.items())],
            'scope':'Lexically resolved supplied functions/class initializers; current and frozen union; MAY-owner argument flow, no name/annotation substitution. Full provenance and no-new-use checks required.'}
    return result,None

@lru_cache(maxsize=16)
def frozen(paths,factories,exports):
    sources={p:frozen_source(p) for p in paths};data,error=solve(sources,factories,dict(exports));assert not error,error
    return data

def prove(sources,factories=(),exports=None):
    paths=tuple(sorted(sources));exports=exports or {};base=frozen(paths,tuple(sorted(factories)),tuple(sorted(exports.items())))
    current,error=solve(sources,base['ownerFactorySymbols'],exports,base['parameters'])
    if error:return None,error
    if current['unresolved']:return None,current['unresolved'][0]['reason']
    current['frozenParameterFacts']=base['parameters'];current['frozenBindingCount']=len(base['bindings']);current['frozenOwnerFactorySymbols']=base['ownerFactorySymbols']
    return current,None

@lru_cache(maxsize=1)
def default_frozen():
    import t1_provenance as t
    from forwarding_discovery import baseline
    d=baseline();paths=tuple(sorted({t.CP+n for n in t.CORE}|set(t.MAIN_CTOR_PATHS)|{'tools/remote_workspace_entry.py'}))
    base=frozen(paths,tuple(d['ownerFactorySymbols']),tuple(sorted(d['exportAliases'].items())))
    return {**base,'frozenParameterFacts':base['parameters'],'frozenOwnerFactorySymbols':base['ownerFactorySymbols']}
