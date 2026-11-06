"""Actual764c five causal overlays and existing controls at final supplied bytes.

Only the static producers are imported. Every mutant compiles for syntax only;
no mutated or product source is imported/executed. Prior independent red rows
are bound by exact overlay SHA, not counted as a new owner execution.
"""
import ast,builtins,json
from collections import Counter
from pathlib import Path
import t1_provenance as t,constructor_graph as cg,source_bindings as sb
E=Path(__file__).resolve().parent;OLD=E.parent/'fleet5-b-rev9e-20261107-codex'
CP=t.CP;BA=CP+'business_auth.py';WA=CP+'workspace_api.py';LP='tools/lan_pilot.py'
core=t.read_batch([CP+n for n in t.CORE]+['tools/remote_workspace_entry.py']);ctors=t.read_batch(t.MAIN_CTOR_PATHS);S={**core,**ctors};ROWS=[];CACHE={}
o=json.loads((OLD/'t1-mark-offline-closure.json').read_bytes())['narrowA8Proof'];prior=json.loads((E/'rev9e-review-reviewer-rev9e-delta-probes-result.json').read_bytes())
W=[r['source'] for r in o['completeConstructorGraph']['productionConstructorProofs']]+[r['source'] for r in o['completeConstructorGraph']['localHelperProofs']]+[{'path':r['path'],'span':r['span'],'expressionSHA256':r['expressionSHA256']} for r in o['productionDatabaseConstructors']]
def unbound(source):
    tree=ast.parse(source);bound=set(dir(builtins))
    for n in ast.walk(tree):
        if isinstance(n,(ast.Import,ast.ImportFrom)):bound.update((a.asname or a.name).split('.')[0] for a in n.names)
        elif isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):bound.add(n.name)
        elif isinstance(n,ast.arg):bound.add(n.arg)
        elif isinstance(n,ast.Name) and isinstance(n.ctx,(ast.Store,ast.Del)):bound.add(n.id)
        elif isinstance(n,ast.ExceptHandler) and n.name:bound.add(n.name)
        elif isinstance(n,(ast.MatchAs,ast.MatchStar)) and n.name:bound.add(n.name)
        elif isinstance(n,ast.MatchMapping) and n.rest:bound.add(n.rest)
    return {n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load) and n.id not in bound}
def replace(source,old,new):assert source.count(old)==1;return source.replace(old,new,1)
def run(name,changes=None,world=None,gap=False,expected='ACCEPT'):
    changes=changes or {};world=world or {};changed={**S,**changes};all_sources={**world,**changed}
    mutations={p:sb.sha(s) for p,s in sorted({**changes,**world}.items())}
    oldrow=next((r for r in prior['cases'] if r['case']==name),None)
    if gap:assert oldrow and oldrow['observed']=='ACCEPT' and oldrow['mutatedSHA256']==mutations,(name,mutations,(oldrow or {}).get('mutatedSHA256'))
    for p,s in {**changes,**world}.items():compile(s,p,'exec');assert not unbound(s)-unbound(sb.frozen_source(p)),name
    checked=0
    for p in sorted({w['path'] for w in W}):
        s=all_sources.get(p) or sb.frozen_source(p);key=(p,sb.sha(s))
        if key not in CACHE:
            tree=ast.parse(s);count=0
            for w in W:
                if w['path']!=p:continue
                node=next((n for n in ast.walk(tree) if hasattr(n,'lineno') and [n.lineno,n.col_offset,n.end_lineno,n.end_col_offset]==w['span']),None)
                assert node is not None and sb.sha(ast.get_source_segment(s,node))==w['expressionSHA256'],(name,w);count+=1
            CACHE[key]=count
        checked+=CACHE[key]
    assert checked==15
    out,error=t.provenance({p:changed[p] for p in core},{p:changed[p] for p in ctors},world or None)
    census=cg.current_census(all_sources);facts={p:sb.Facts(p,s) for p,s in all_sources.items()};keys=Counter(cg.root_key(r,facts[r['source']['path']]) for r in census['production'])
    assert not (cg.frozen_root_keys()-keys) and len(census['production'])==6
    if gap:
        assert error and (error=='UNRESOLVED:CALLEE_REBOUND' if name.startswith('L2') else error.startswith(('UNCATALOGUED_PRODUCTION_SOURCE:','UNRESOLVED:RELEVANT_REFLECTION_'))),(name,error)
    row={'case':name,'actual764cGap':gap,'oldIndependentObserved':oldrow['observed'] if gap else None,'observed':'REFUSE' if error else 'ACCEPT','reason':error,'expected':expected,'astValid':True,'syntaxCompiledOnly':True,'newUnboundNames':[],'witnessesChecked':checked,'visibleProductionRoots':len(census['production']),'sixFrozenRootsPreserved':True,'mutatedSHA256':mutations,'effectfulMutantsImportedOrExecuted':False}
    assert row['observed']==expected,row;ROWS.append(row);print(json.dumps(row),flush=True)
TAIL='\n\n\ndef _claude_root(tenant, settings):\n    return '
run('L1-near-import_module-relative-variable-package',world={BA:sb.frozen_source(BA)+"\nimport importlib\n_CLAUDE_PKG = 'inv'\n"+TAIL+"importlib.import_module('.workspace_config', _CLAUDE_PKG).configured_workspace(object(), tenant, settings)\n"},gap=True,expected='REFUSE')
run('L1-near-import_module-relative-literal-package',world={BA:sb.frozen_source(BA)+"\nimport importlib\n"+TAIL+"importlib.import_module('.workspace_config', 'inv').configured_workspace(object(), tenant, settings)\n"},gap=True,expected='REFUSE')
run('L1-near-dunder-import-relative-level1',world={BA:sb.frozen_source(BA)+"\n"+TAIL+"__import__('workspace_config', globals(), None, (), 1).configured_workspace(object(), tenant, settings)\n"},gap=True,expected='REFUSE')
guard='\n\n\nif __name__ == "__main__":\n'
run('L2-near-lan_pilot-global-import-in-function',{LP:replace(S[LP],guard,'\ndef _claude_install(): global _current_finalized_batch; from foreign_module import _current_finalized_batch\n_claude_install()\nif __name__ == "__main__":\n')},gap=True,expected='REFUSE')
run('L2-near-lan_pilot-star-import-shadow',{LP:replace(S[LP],guard,'\nfrom foreign_module import *\n\nif __name__ == "__main__":\n')},gap=True,expected='REFUSE')
run('actual-72028-positive')
run('outside-benign-database-helper',world={BA:sb.frozen_source(BA)+"\nfrom .db import Database\n\n\ndef _claude_db(dsn):\n    return Database(dsn)\n"})
run('outside-assigned-string-unused-import',world={BA:sb.frozen_source(BA)+"\nimport operator\n_CLAUDE_NOTE = 'inv.workspace_config.configured_workspace'\n"})
run('outside-bounded-literal-json',world={BA:sb.frozen_source(BA)+"\nimport sys\n\n\ndef _claude_json():\n    return sys.modules['js' + 'on']\n"})
init='        self.db, self.working, self.runtime = database, working, runtime\n'
run('same-function-unowned-working',{WA:replace(S[WA],init,init+'        import foreign_module\n        foreign_module.register_note(working)\n')})
run('unrelated-module-helper',{LP:replace(S[LP],guard,'\ndef _claude_note(text): return text\n_CLAUDE_NOTE = _claude_note("ok")\nif __name__ == "__main__":\n')})
run('unrelated-same-spelled-local',{LP:S[LP]+'\ndef _unrelated():\n    _current_finalized_batch = 1\n    return _current_finalized_batch\n'})
(E/'rev9f-gap-results.json').write_bytes((json.dumps({'executionOwner':'Codex OWNER, not independent review','source':'72028cbac903c4415d9979f980a6e0f9948e914f','oldRedEvidenceCommit':'764c3bf3fd9d4046abcaab4b891a1cd1db085a06','cases':ROWS,'actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING'},indent=2)+'\n').encode())
