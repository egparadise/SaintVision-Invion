"""Six actual9266 causal mutants; AST only, 15 unchanged source witnesses."""
import ast,builtins,json,sys
from collections import Counter
from pathlib import Path
E=Path(sys.argv[1]).resolve(strict=True);OUT=Path(sys.argv[2]);sys.path.insert(0,str(E))
import t1_provenance as t,constructor_graph as cg,source_bindings as sb
assert Path(t.__file__).resolve().parent==E
CP=t.CP;BA=CP+'business_auth.py';WA=CP+'workspace_api.py';AP=CP+'app.py';LP='tools/lan_pilot.py'
core=t.read_batch([CP+n for n in t.CORE]+['tools/remote_workspace_entry.py']);ctors=t.read_batch(t.MAIN_CTOR_PATHS);S={**core,**ctors};rows=[];cache={}
BASE=Path(__file__).resolve().parent.parent/'fleet5-b-rev9d-20261107-codex'
g=json.loads((BASE/'t1-mark-offline-closure.json').read_bytes())['narrowA8Proof']
W=[r['source'] for r in g['completeConstructorGraph']['productionConstructorProofs']]+[r['source'] for r in g['completeConstructorGraph']['localHelperProofs']]+[{'path':r['path'],'span':r['span'],'expressionSHA256':r['expressionSHA256']} for r in g['productionDatabaseConstructors']]
def unbound(source):
    tree=ast.parse(source);bound=set(dir(builtins))
    for n in ast.walk(tree):
        if isinstance(n,(ast.Import,ast.ImportFrom)):bound.update((a.asname or a.name).split('.')[0] for a in n.names)
        elif isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):bound.add(n.name)
        elif isinstance(n,ast.arg):bound.add(n.arg)
        elif isinstance(n,ast.Name) and isinstance(n.ctx,(ast.Store,ast.Del)):bound.add(n.id)
        elif isinstance(n,ast.ExceptHandler) and n.name:bound.add(n.name)
    return {n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load) and n.id not in bound}
def run(name,changes=None,world=None,gap=False,expect='REFUSE',hidden=0):
    changes=changes or {};world=world or {};changed={**S,**changes};all_sources={**world,**changed}
    for p,s in {**changes,**world}.items():ast.parse(s);assert not unbound(s)-unbound(sb.frozen_source(p)),name
    checked=0
    for p in sorted({w['path'] for w in W}):
        s=all_sources.get(p) or sb.frozen_source(p);key=(p,sb.sha(s))
        if key not in cache:
            tree=ast.parse(s);count=0
            for w in W:
                if w['path']!=p:continue
                n=next((n for n in ast.walk(tree) if hasattr(n,'lineno') and [n.lineno,n.col_offset,n.end_lineno,n.end_col_offset]==w['span']),None)
                assert n is not None and sb.sha(ast.get_source_segment(s,n))==w['expressionSHA256'],(name,w);count+=1
            cache[key]=count
        checked+=cache[key]
    assert checked==15
    out,error=t.provenance({p:changed[p] for p in core},{p:changed[p] for p in ctors},world or None)
    census=cg.current_census(all_sources);facts={p:sb.Facts(p,s) for p,s in all_sources.items()}
    keys=Counter(cg.root_key(r,facts[r['source']['path']]) for r in census['production'])
    assert not (cg.frozen_root_keys()-keys),name
    row={'case':name,'actual9266Gap':gap,'expectedNew':expect,'observed':'REFUSE' if error else 'ACCEPT','reason':error,'astValid':True,'newUnboundNames':[],'witnessesChecked':checked,'sixFrozenRootsPreserved':True,'visibleRoots':len(census['production']),'hiddenSemanticRootsInFixture':hidden,'fixtureSemanticRootCount':len(census['production'])+hidden,'mutatedSHA256':{p:sb.sha(s) for p,s in sorted({**changes,**world}.items())},'newUnknownReflectionHits':sum(x['kind']=='ENUMERATED_REFLECTION_NONLITERAL_KEY' for a in census['reflectionAudits'] for x in a['newRelevantHits']),'effectfulMutantsImportedOrExecuted':False}
    rows.append(row);print(json.dumps(row),flush=True)
tail='\ndef _claude_root(tenant, settings):\n    return '
for name,body,hidden in [
 ('sys-variable',"import sys\n_CLAUDE_MOD='inv.workspace_config'\n"+tail+"sys.modules[_CLAUDE_MOD].configured_workspace(object(), tenant, settings)\n",0),
 ('sys-fstring',"import sys\n"+tail+"sys.modules[f\"inv.{'workspace_config'}\"].configured_workspace(object(), tenant, settings)\n",0),
 ('importlib-join',"import importlib\n"+tail+"importlib.import_module('.'.join(('inv','workspace_config'))).configured_workspace(object(), tenant, settings)\n",0),
 ('getattr-variable-hidden-seventh',"import importlib\n_CLAUDE_MOD='inv.observer_worker'\n_CLAUDE_NAME='ObservationWorker'\ndef _claude_hidden_root():\n    return getattr(importlib.import_module(_CLAUDE_MOD), _CLAUDE_NAME)(object(), None)\n",1),
]:run(name,world={BA:sb.frozen_source(BA)+'\n'+body},gap=True,hidden=hidden)
anchor='        self.control, self.ledger = Control(database), ApprovalStore(database)\n\n    def _scope('
assert S[WA].count(anchor)==1
run('WorkspaceAPI-new-runtime',{WA:S[WA].replace(anchor,'        self.control, self.ledger = Control(database), ApprovalStore(database)\n    def __new__(cls, *args, **kwargs): import foreign_module; foreign_module.register_runtime(args[2]); return super().__new__(cls)\n    def _scope(',1)},gap=True)
guard='\n\n\nif __name__ == "__main__":\n';assert S[LP].count(guard)==1
run('nonfactory-rebound-conn',{LP:S[LP].replace(guard,'\ndef _claude_wrap(fn): import foreign_module; return lambda *a, **k: (foreign_module.register_conn(a[4]), fn(*a, **k))[1]\n_current_finalized_batch = _claude_wrap(_current_finalized_batch)\nif __name__ == "__main__":\n',1)},gap=True)
if E.name.endswith('rev9e-20261107-codex'):
    run('actual72028-positive',expect='ACCEPT')
    run('outside-assigned-string-unused-import',world={BA:sb.frozen_source(BA)+"\nimport operator\n_CLAUDE_NOTE='inv.workspace_config.configured_workspace'\n"},expect='ACCEPT')
    run('outside-benign-database-helper',world={BA:sb.frozen_source(BA)+'\nfrom .db import Database\ndef _claude_db(dsn):\n    return Database(dsn)\n'},expect='ACCEPT')
    init='        self.db, self.working, self.runtime = database, working, runtime\n';assert S[WA].count(init)==1
    run('same-function-unowned-working',{WA:S[WA].replace(init,init+'        import foreign_module\n        foreign_module.register_note(working)\n',1)},expect='ACCEPT')
    run('outside-benign-literal-reflection',world={BA:sb.frozen_source(BA)+"\nimport sys\ndef _plain():\n    return sys.modules['json']\n"},expect='ACCEPT')
    run('unrelated-local-callee-name',{LP:S[LP]+'\ndef _unrelated():\n    _current_finalized_batch = 1\n    return _current_finalized_batch\n'},expect='ACCEPT')
    run('existing-factory-rebind-control',{AP:S[AP]+'\ndef _claude_wrap(fn):\n    return fn\ncreate_app = _claude_wrap(create_app)\n'})
OUT.write_bytes((json.dumps({'executionOwner':'Codex OWNER, not independent review','targetEvidence':E.name,'cases':rows,'actualRuntimeB':0,'productFilesWritten':0},indent=2)+'\n').encode())
