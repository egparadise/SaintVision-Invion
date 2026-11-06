"""OWNER old/new AST counterexample runner; fixture source view, never runtime."""
import ast,inspect,json,sys,builtins
from pathlib import Path
E=Path(sys.argv[1]).resolve(strict=True);OUT=Path(sys.argv[2]);sys.path.insert(0,str(E))
import t1_provenance as t,constructor_graph as cg,source_bindings as sb
assert Path(t.__file__).resolve().parent==E
CP=t.CP;LP='tools/lan_pilot.py';WC=CP+'workspace_config.py';AP=CP+'app.py';BH=CP+'business_handoff.py'
core=t.read_batch([CP+n for n in t.CORE]+['tools/remote_workspace_entry.py']);ctors=t.read_batch(t.MAIN_CTOR_PATHS)
S={**core,**ctors};R=[]
OLD=Path(__file__).resolve().parent.parent/'fleet5-b-rev9b-20261106-codex'
closure=json.loads((OLD/'t1-mark-offline-closure.json').read_bytes())['narrowA8Proof']
W=[r['source'] for r in closure['completeConstructorGraph']['productionConstructorProofs']]+[r['source'] for r in closure['completeConstructorGraph']['localHelperProofs']]+[{'path':r['path'],'span':r['span'],'expressionSHA256':r['expressionSHA256']} for r in closure['productionDatabaseConstructors']]
SANITY_CACHE={}

def unbound(source):
    tr=ast.parse(source);bound=set(dir(builtins))
    for n in ast.walk(tr):
        if isinstance(n,(ast.Import,ast.ImportFrom)):bound.update((a.asname or a.name).split('.')[0] for a in n.names)
        elif isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):bound.add(n.name)
        elif isinstance(n,ast.arg):bound.add(n.arg)
        elif isinstance(n,ast.Name) and isinstance(n.ctx,(ast.Store,ast.Del)):bound.add(n.id)
        elif isinstance(n,ast.ExceptHandler) and n.name:bound.add(n.name)
    return {n.id for n in ast.walk(tr) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load) and n.id not in bound}

def sanity(sources,skip=()):
    count=0
    for path in sorted({w['path'] for w in W}):
        source=sources.get(path) or sb.frozen_source(path);key=(path,sb.sha(source),tuple(sorted(span for p,span in skip if p==path)))
        if key not in SANITY_CACHE:
            tree=ast.parse(source);checked=0
            for w in W:
                if w['path']!=path or (path,tuple(w['span'])) in skip:continue
                node=next((n for n in ast.walk(tree) if hasattr(n,'lineno') and [n.lineno,n.col_offset,n.end_lineno,n.end_col_offset]==w['span']),None)
                assert node is not None and sb.sha(ast.get_source_segment(source,node))==w['expressionSHA256'],w
                checked+=1
            SANITY_CACHE[key]=checked
        count+=SANITY_CACHE[key]
    return count

def run(name,changes=None,world=None,expected='REFUSE',reason=None,skip=(),red=True,detail=None):
    changed={**S,**(changes or {})};c2={p:changed[p] for p in core};k2={p:changed[p] for p in ctors}
    checked=sanity(changed,skip)
    for p,s in {**(changes or {}),**(world or {})}.items():
        ast.parse(s)
        try:base=sb.frozen_source(p)
        except Exception:base=''
        assert not unbound(s)-unbound(base),(name,sorted(unbound(s)-unbound(base)))
    new_api='universe_overrides' in inspect.signature(t.provenance).parameters
    owner,error=t.provenance(c2,k2,universe_overrides=world) if new_api else t.provenance(c2,k2)
    discovery=None;owner_targets={}
    if new_api:
        import forwarding_discovery as fd
        from owner_transfer import derive
        census=cg.current_census({**(world or {}),**changed})
        discovery,discovery_error=fd.discover(census['production'],{**(world or {}),**changed});assert not discovery_error
        if detail:detail(discovery)
        for p in (WC,AP):owner_targets[p]=derive(sb.Facts(p,changed[p]),discovery['ownerFactorySymbols'])[0]['owners']
        if name.startswith('L3-five-runtime'):assert {'runtime','pool'}<=set(owner_targets[WC]['configured_workspace'])
        if name.startswith('L3-five-workspace'):assert 'workspace' in owner_targets[AP]['create_configured_app']
        if name=='L3-with-target':assert 'held_runtime' in owner_targets[WC]['configured_workspace']
        if name=='L3-comprehension-target':assert {'aliases','entry'}<=set(owner_targets[WC]['configured_workspace'])
        if name=='L3-attribute-subscript':assert 'runtime_alias' in owner_targets[WC]['configured_workspace']
    row={'case':name,'expectedNew':expected,'observed':'ACCEPT' if error is None else 'REFUSE','reason':error,'expectedReasonPrefix':reason,'oldGapExpected':red,'producerSanity':True,'originalWitnessesChecked':checked,'intentionalRootRewrites':len(skip),'mutatedSourceSHA256':{p:sb.sha(s) for p,s in sorted({**(changes or {}),**(world or {})}.items())},'sourceUniverseOverlay':bool(world),'newUnboundNames':[],
         'currentVisibleProductionRoots':len(census['production']) if new_api else (len(owner['completeConstructorGraph']['census']['production']) if owner else None),'discoveredProductionFiles':discovery['productionFiles'] if discovery else None,'discoveredHarnessFiles':discovery['harnessFiles'] if discovery else None,'trackedForwarders':discovery['trackedForwarders'] if discovery else None,'exportAliases':discovery['exportAliases'] if discovery else None,'ownerTargets':owner_targets if name.startswith('L3') else None}
    if new_api:
        assert row['observed']==expected,(name,error)
        if reason:assert error and error.startswith(reason),(name,error)
    R.append(row);print(json.dumps({'case':name,'observed':row['observed'],'reason':error}),flush=True)

def import_lp(source,module):return source.replace('\nimport argparse\n','\nimport argparse, '+module+'\n',1)
ROOT_SKIP={(LP,(3945,15,3945,82))};call='ObservationWorker(runtime(state), '
run('actual-source-positive',expected='ACCEPT',red=False)
for label,arg in [('state','state'),('runtime','runtime(state)')]:
    source=import_lp(S[LP],'operator').replace(call,"operator.attrgetter('ObservationWorker')(sys.modules['inv.observer_worker'])("+arg+', ',1)
    run('L1-hidden-replacement-'+label,{LP:source},reason='UNRESOLVED:CONSTRUCTOR_ROOT_REMOVED_OR_HIDDEN',skip=ROOT_SKIP)
run('L1-removed-root',{LP:S[LP].replace('observer = ObservationWorker(runtime(state), NodeTLSClient(**tls(args.state)))','observer = state',1)},reason='UNRESOLVED:CONSTRUCTOR_ROOT_REMOVED_OR_HIDDEN',skip=ROOT_SKIP)
for label,module,expr in [
 ('six-plus-hidden-operator','operator',"operator.attrgetter('ObservationWorker')(sys.modules['inv.observer_worker'])(state, None)"),
 ('six-plus-hidden-inspect','inspect',"inspect.getattr_static(sys.modules['inv.observer_worker'], 'ObservationWorker')(runtime(state), None)"),
 ('inspect-members','inspect',"inspect.getmembers(sys.modules['inv.observer_worker'])"),
 ('importlib-module','importlib',"importlib.import_module('inv.observer_worker')"),
 ('sys-module','sys',"sys.modules['inv.observer_worker']"),
 ('methodcaller','operator',"operator.methodcaller('transaction')(state)"),
 ('operator-module-alias','operator',"operator.attrgetter")]:
    source=import_lp(S[LP],module)+'\n\ndef _b9c_hidden(state):\n    return '+expr+'\n'
    run('L1-'+label,{LP:source},reason='UNRESOLVED:RELEVANT_REFLECTION_USE_NOT_ALLOWLISTED')
run('L1-benign-unused-import-and-nonreflective-string',{LP:import_lp(S[LP],'operator')+"\nPROOF_NOTE = 'ObservationWorker'\n"},expected='ACCEPT',red=False)
alias_lp=S[LP].replace('from inv.observer_worker import ObservationWorker','import inv.observer_worker as _fixture_observer_module').replace(call,'_fixture_observer_module.ObservationWorker(runtime(state), ',1)
run('L1-benign-current-constructor-module-alias',{LP:alias_lp},expected='ACCEPT',red=False,skip=ROOT_SKIP)

outside=sb.frozen_source(BH)+'\nfrom .workspace_config import configured_workspace as _cw\n\ndef _extra_root(tenant, settings):\n    return _cw(object(), tenant, settings)\n'
def require_bh(d):assert BH in d['productionFiles']
run('L2-reviewer-business-handoff-alias-omitted',world={BH:outside},reason='UNCATALOGUED_PRODUCTION_SOURCE:',detail=require_bh)
export=CP+'b9c_reexport_fixture.py';caller=CP+'business_surface.py'
export_source='from .workspace_config import configured_workspace as exported_factory\n'
reexport_caller=sb.frozen_source(BH)+'\nfrom .b9c_reexport_fixture import exported_factory as factory_alias\n\ndef _extra_root(tenant, settings):\n    return factory_alias(object(), tenant, settings)\n'
def require_reexport(d):assert export in d['productionFiles'] and BH in d['productionFiles'] and d['exportAliases']['inv.b9c_reexport_fixture.exported_factory']=='inv.workspace_config.configured_workspace'
run('L2-reexport-alias-omitted',world={export:export_source,BH:reexport_caller},reason='UNCATALOGUED_PRODUCTION_SOURCE:',detail=require_reexport)
module_export='from . import workspace_config as exported_module\n'
module_caller=sb.frozen_source(BH)+'\nfrom .b9c_reexport_fixture import exported_module as module_alias\n\ndef _extra_root(tenant, settings):\n    return module_alias.configured_workspace(object(), tenant, settings)\n'
def require_module_export(d):assert export in d['productionFiles'] and BH in d['productionFiles'] and d['exportAliases']['inv.b9c_reexport_fixture.exported_module']=='inv.workspace_config'
run('L2-module-reexport-omitted',world={export:module_export,BH:module_caller},reason='UNCATALOGUED_PRODUCTION_SOURCE:',detail=require_module_export)
forward=sb.frozen_source(BH)+'\nfrom .workspace_config import configured_workspace as _cw\n\ndef _b9c_forward(database, tenant, settings):\n    return _cw(database, tenant, settings)\n'
upper=sb.frozen_source(caller)+'\nfrom .business_handoff import _b9c_forward as _higher\n\ndef _extra_root(tenant, settings):\n    return _higher(object(), tenant, settings)\n'
def require_forward(d):assert caller in d['productionFiles'] and 'inv.business_handoff._b9c_forward' in d['trackedForwarders']
run('L2-forwarding-fixed-point-omitted',world={BH:forward,caller:upper},reason='UNCATALOGUED_PRODUCTION_SOURCE:',detail=require_forward)
hp='tests/integration/test_node_extensions.py';hs=sb.frozen_source(hp)+'\nfrom inv.workspace_config import configured_workspace as harness_factory\n\ndef _harness(tenant, settings):\n    return harness_factory(object(), tenant, settings)\n'
def require_harness(d):assert hp in d['harnessFiles'] and hp not in d['productionFiles']
run('L2-harness-is-separated',world={hp:hs},expected='ACCEPT',red=False,detail=require_harness)
alias=S[AP].replace('from .workspace_config import configured_workspace','from .workspace_config import configured_workspace as _fixture_cw').replace('workspace = configured_workspace(database,','workspace = _fixture_cw(database,')
run('L2-benign-current-import-alias',{AP:alias},expected='ACCEPT',red=False)
module_alias=S[AP].replace('from .workspace_config import configured_workspace','from . import workspace_config as _fixture_module').replace('workspace = configured_workspace(database,','workspace = _fixture_module.configured_workspace(database,')
run('L2-benign-current-module-alias',{AP:module_alias},expected='ACCEPT',red=False)

loop='    for runtime in pool.values():\n        runtime.destinations = pool\n'
for expr in ('runtime','runtime.db','runtime.db.transaction'):
    source=S[WC].replace(loop,loop+'        from foreign_module import register_runtime\n        register_runtime('+expr+')\n',1)
    run('L3-five-runtime-'+expr,{WC:source},reason='DYNAMIC_BLOCK:USE_SITE_NOT_ALLOWLISTED:')
line='            workspace = configured_workspace(database, identity.tenant_id, settings["workspace"])\n'
for expr in ('workspace','workspace.runtime.db'):
    source=S[AP].replace(line,line+'            from foreign_module import register_workspace\n            register_workspace('+expr+')\n',1)
    run('L3-five-workspace-'+expr,{AP:source},reason='DYNAMIC_BLOCK:USE_SITE_NOT_ALLOWLISTED:')
extra=[('with-target','    from contextlib import nullcontext as held_context\n    from foreign_module import register_runtime\n    with held_context(result.runtime) as held_runtime:\n        register_runtime(held_runtime.db)\n'),
 ('comprehension-target','    aliases = [entry for entry in pool.values()]\n    from foreign_module import register_runtime\n    register_runtime(aliases[0].db)\n'),
 ('attribute-subscript','    runtime_alias = pool[result.runtime.node.node_id]\n    from foreign_module import register_runtime\n    register_runtime(runtime_alias.db.transaction)\n')]
for label,statement in extra:
    run('L3-'+label,{WC:S[WC].replace('    return result\n',statement+'    return result\n',1)},reason='DYNAMIC_BLOCK:USE_SITE_NOT_ALLOWLISTED:',red=label=='comprehension-target')
benign='    notes = [entry for entry in ("alpha", "beta")]\n    for note in notes:\n        pass\n'
run('L3-benign-unrelated-containers',{WC:S[WC].replace('    return result\n',benign+'    return result\n',1)},expected='ACCEPT',red=False)
OUT.write_bytes((json.dumps({'executionOwner':'Codex OWNER counterexample reproduction','targetEvidence':E.name,'cases':R,'effectfulMutantsImportedOrExecuted':False,'fixtureSourceUniverse':'Frozen git72028 plus explicit in-memory overlay; no product/source files modified','arbitraryPythonReflectionOrHeapCompleteness':False,'actualRuntimeB':0},indent=2)+'\n').encode())
print(json.dumps({'cases':len(R),'newAPI':('universe_overrides' in inspect.signature(t.provenance).parameters)}))
