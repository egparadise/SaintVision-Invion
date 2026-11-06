"""Bounded OWNER reproduction of the 8 actual4288 gaps plus controls."""
import ast,builtins,json,sys
from pathlib import Path
E=Path(sys.argv[1]).resolve(strict=True);OUT=Path(sys.argv[2]);sys.path.insert(0,str(E))
import t1_provenance as t,constructor_graph as cg,source_bindings as sb
assert Path(t.__file__).resolve().parent==E
CP=t.CP;AP=CP+'app.py';WA=CP+'workspace_api.py';BA=CP+'business_auth.py';LP='tools/lan_pilot.py'
core=t.read_batch([CP+n for n in t.CORE]+['tools/remote_workspace_entry.py']);ctors=t.read_batch(t.MAIN_CTOR_PATHS);S={**core,**ctors};R=[];CACHE={}
BASE=Path(__file__).resolve().parent.parent/'fleet5-b-rev9c-20261106-codex'
o=json.loads((BASE/'t1-mark-offline-closure.json').read_bytes())['narrowA8Proof']
W=[r['source'] for r in o['completeConstructorGraph']['productionConstructorProofs']]+[r['source'] for r in o['completeConstructorGraph']['localHelperProofs']]+[{'path':r['path'],'span':r['span'],'expressionSHA256':r['expressionSHA256']} for r in o['productionDatabaseConstructors']]

def unbound(s):
    tree=ast.parse(s);bound=set(dir(builtins))
    for n in ast.walk(tree):
        if isinstance(n,(ast.Import,ast.ImportFrom)):bound.update((a.asname or a.name).split('.')[0] for a in n.names)
        elif isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):bound.add(n.name)
        elif isinstance(n,ast.arg):bound.add(n.arg)
        elif isinstance(n,ast.Name) and isinstance(n.ctx,(ast.Store,ast.Del)):bound.add(n.id)
        elif isinstance(n,ast.ExceptHandler) and n.name:bound.add(n.name)
    return {n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load) and n.id not in bound}

def sanity(changed):
    count=0
    for path in sorted({r['path'] for r in W}):
        source=changed.get(path) or sb.frozen_source(path);key=(path,sb.sha(source))
        if key not in CACHE:
            tree=ast.parse(source);checked=0
            for w in W:
                if w['path']!=path:continue
                n=next((n for n in ast.walk(tree) if hasattr(n,'lineno') and [n.lineno,n.col_offset,n.end_lineno,n.end_col_offset]==w['span']),None)
                assert n is not None and sb.sha(ast.get_source_segment(source,n))==w['expressionSHA256'],w
                checked+=1
            CACHE[key]=checked
        count+=CACHE[key]
    return count

def run(name,changes=None,world=None,gap=False,expected='REFUSE'):
    changes=changes or {};world=world or {};changed={**S,**changes}
    for p,s in {**changes,**world}.items():ast.parse(s);assert not unbound(s)-unbound(sb.frozen_source(p)),name
    witnesses=sanity({**world,**changed});assert witnesses==15
    c={p:changed[p] for p in core};k={p:changed[p] for p in ctors}
    owner,error=t.provenance(c,k,world or None);census=cg.current_census({**world,**changed})
    row={'case':name,'gapAt5ea':gap,'expectedNew':expected,'observed':'REFUSE' if error else 'ACCEPT','reason':error,'astValid':True,'newUnboundNames':[],'witnessesChecked':witnesses,'visibleProductionRoots':len(census['production']),'mutatedSHA256':{p:sb.sha(s) for p,s in sorted({**changes,**world}.items())},'effectfulMutantsImportedOrExecuted':False}
    R.append(row);print(json.dumps(row),flush=True)

run('actual-source-positive',expected='ACCEPT')
for label,body in [('operator-sys',"import operator\nimport sys\ndef _hidden():\n    return operator.attrgetter('ObservationWorker')(sys.modules['inv.observer_worker'])(object(), None)\n"),('importlib-forwarder',"import importlib\ndef _hidden(tenant, settings):\n    return importlib.import_module('inv.workspace_config').configured_workspace(object(), tenant, settings)\n"),('sys-forwarder',"import sys\ndef _hidden(tenant, settings):\n    return sys.modules['inv.workspace_config'].configured_workspace(object(), tenant, settings)\n")]:
    run('outside-'+label,world={BA:sb.frozen_source(BA)+'\n'+body},gap=True)
init='        self.db, self.working, self.runtime = database, working, runtime\n'
assert S[WA].count(init)==1
for expr in ('runtime','runtime.db','runtime.db.transaction'):
    run('parameter-WorkspaceAPI-'+expr,{WA:S[WA].replace(init,init+'        import foreign_module\n        foreign_module.register_runtime('+expr+')\n',1)},gap=True)
svc='            raise DomainError("SYS-0001", "Workspace admission is not configured", 503)\n        return workspace\n'
assert S[AP].count(svc)==1
for expr in ('workspace','workspace.runtime.db'):
    run('parameter-create_app-'+expr,{AP:S[AP].replace(svc,'            raise DomainError("SYS-0001", "Workspace admission is not configured", 503)\n        import foreign_module; foreign_module.register_workspace('+expr+'); return workspace\n',1)},gap=True)
run('outside-importlib-attribute-retained',world={BA:sb.frozen_source(BA)+"\nimport importlib\ndef _hidden():\n    return importlib.import_module('inv.observer_worker').ObservationWorker(object(), None)\n"})
run('outside-module-getattr-retained',world={BA:sb.frozen_source(BA)+"\nfrom . import workspace_config as _wc\ndef _hidden(tenant, settings):\n    return getattr(_wc, 'configured_workspace')(object(), tenant, settings)\n"})
run('outside-benign-database-helper',world={BA:sb.frozen_source(BA)+'\nfrom .db import Database\ndef _helper(dsn):\n    return Database(dsn)\n'},expected='ACCEPT')
OUT.write_bytes((json.dumps({'executionOwner':'Codex OWNER, not independent review','targetEvidence':E.name,'cases':R,'actualRuntimeB':0,'productFilesWritten':0},indent=2)+'\n').encode());print(json.dumps({'cases':len(R)}))
