"""Serial source-derived T1 forwarding census; future cross-module A7 excluded."""
import ast,re,subprocess
from functools import lru_cache
from source_bindings import Facts,ROOT,SOURCE,frozen_source,sha,TARGETS,text,module_name
from owner_transfer import derive
SCOPE=('services/control-plane/src','src','tools','tests')

def canonical(symbol,exports):
    seen=set()
    while symbol and symbol not in seen:
        seen.add(symbol)
        match=next((key for key in sorted(exports,key=lambda x:(-len(x),x)) if symbol==key or symbol.startswith(key+'.')),None)
        if not match:break
        symbol=exports[match]+symbol[len(match):]
    return symbol

def aliases(f,exports):
    # Only direct lexical import/name aliases. Reflection/dynamic exports stay
    # unresolved and are not upgraded to a known forwarding callable.
    for _ in range(16):
        changed=False
        for n in f.tree.body:
            if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name):
                value=canonical(f.resolve(n.value),exports)
                if value and f.aliases[''].get(n.targets[0].id)!=value:
                    f.aliases[''][n.targets[0].id]=value;changed=True
        if not changed:break

def discover(constructor_rows,overrides=None):
    overrides=overrides or {};seeds=set();commands=[];files={};callers={};exports={};factories=set();unresolved=[]
    # A forwarding seed must actually pass a function parameter into one of the
    # three constructors. Local closed Database factories are inventoried in the
    # existing local-helper proof, not promoted to future runtime-import A7.
    for row in constructor_rows:
        p=row['source']['path'];source=overrides.get(p) if p in overrides else frozen_source(p);f=Facts(p,source)
        q=row['source']['function'].removeprefix(f.module+'.');fn=f.functions.get(q)
        if not fn or q.endswith('.__init__'):continue
        params={x.arg for x in fn.args.posonlyargs+fn.args.args+fn.args.kwonlyargs}
        c=next((n for n in ast.walk(fn) if isinstance(n,ast.Call) and f.resolve(n.func)==row['constructor'] and f.witness(n)['span']==row['source']['span']),None)
        if c and c.args and isinstance(c.args[0],ast.Name) and c.args[0].id in params:seeds.add(f.module+'.'+q)
    tracked=set(seeds);export_names=set();scanned=set()
    for iteration in range(32):
        state=(frozenset(tracked),tuple(sorted(exports.items())),frozenset(factories))
        names=sorted(tracked|export_names)
        tokens=sorted({part for target in names for part in (target.rsplit('.',1)[-1],target.rsplit('.',1)[0].rsplit('.',1)[-1])})
        if not tokens:break
        pattern='|'.join(re.escape(x) for x in tokens)
        cmd=['git','grep','-l','-E',pattern,SOURCE,'--',*SCOPE]
        r=subprocess.run(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE);assert r.returncode in (0,1)
        commands.append({'command':cmd,'exit':r.returncode})
        paths=sorted({x.split(':',1)[1] for x in r.stdout.decode('utf8').splitlines()}|set(overrides))
        for p in paths:
            if not p.endswith('.py'):continue
            source=overrides[p] if p in overrides else frozen_source(p);f=Facts(p,source);aliases(f,exports)
            files[p]={'path':p,'sha256':sha(source),'bytes':len(source.encode()),'scope':'HARNESS_ONLY_PROVENANCE' if p.startswith('tests/') else 'PRODUCTION_SOURCE'}
            for local,target in sorted(f.aliases[''].items()):
                target=canonical(target,exports)
                if target in tracked or any(t.startswith((target or '')+'.') for t in tracked):
                    exported=f.module+'.'+local
                    if exported!=target:exports[exported]=target;export_names.add(exported)
            for n in ast.walk(f.tree):
                if isinstance(n,ast.ImportFrom) and any(a.name=='*' for a in n.names):
                    # A star import from a relevant module cannot prove a closed
                    # callable binding. Harness entries remain separate.
                    mod=n.module or ''
                    if any(t.rsplit('.',1)[0].endswith(mod) for t in tracked):unresolved.append({'source':f.witness(n),'reason':'UNRESOLVED:RELEVANT_FORWARDER_STAR_IMPORT','scope':'HARNESS_ONLY_PROVENANCE' if p.startswith('tests/') else 'PRODUCTION_SOURCE'})
                if not isinstance(n,ast.Call):continue
                target=canonical(f.resolve(n.func),exports)
                if target not in tracked:continue
                row={'source':f.witness(n),'target':target,'calleeSpelling':text(n.func),'argument0':text(n.args[0]) if n.args else None,'aliases':f.visible_aliases(f.scope[id(n)]),'scope':'HARNESS_ONLY_PROVENANCE' if p.startswith('tests/') else 'PRODUCTION_SOURCE'}
                callers[(p,tuple(row['source']['span']))]=row
                q=f.enclosing(n);fn=f.functions.get(q)
                if fn and n.args:
                    params={x.arg for x in fn.args.posonlyargs+fn.args.args+fn.args.kwonlyargs}
                    if isinstance(n.args[0],ast.Name) and n.args[0].id in params and not p.startswith('tests/'):tracked.add(f.module+'.'+q)
            ownership,_=derive(f,factories|{k for k,v in exports.items() if canonical(v,exports) in factories})
            factories.update(x for x in ownership['ownerReturningFunctions'] if x in tracked)
        for key,value in sorted(exports.items()):
            if canonical(value,exports) in factories:factories.add(key)
            module=canonical(value,exports)
            factories.update(key+factory[len(module):] for factory in list(factories) if module and factory.startswith(module+'.'))
        if state==(frozenset(tracked),tuple(sorted(exports.items())),frozenset(factories)):break
    else:return None,'UNRESOLVED:FORWARDING_DISCOVERY_DID_NOT_CONVERGE'
    # Import-only re-exports are part of the proof even if they do not call.
    relevant=set(r['source']['path'] for r in callers.values())
    for symbol in exports:
        module=symbol.rsplit('.',1)[0]
        relevant.update(p for p in files if module_name(p)==module)
    production=sorted(p for p in relevant if not p.startswith('tests/'))
    harness=sorted(p for p in relevant if p.startswith('tests/'))
    unique_unresolved={str(x):x for x in unresolved}
    return {'seedForwarders':sorted(seeds),'trackedForwarders':sorted(tracked),'exportAliases':dict(sorted(exports.items())),
            'ownerFactorySymbols':sorted(factories),'productionFiles':production,'harnessFiles':harness,
            'callers':sorted(callers.values(),key=lambda r:(r['source']['path'],r['source']['span'])),
            'sourceFiles':[files[p] for p in sorted(files)],'unresolved':list(unique_unresolved.values()),'commands':commands,
            'mode':'Serial bounded symbol-driven fixed point; no application import or full assembler',
            'A7':'DEFERRED: no global callers of local Database-return helpers promoted here'},None

@lru_cache(maxsize=1)
def baseline():
    from constructor_graph import base_census
    d,error=discover(base_census()['production']);assert not error,error
    return d
