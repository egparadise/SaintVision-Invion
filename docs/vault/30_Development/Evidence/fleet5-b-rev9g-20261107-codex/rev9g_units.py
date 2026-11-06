"""Bounded import-position and caller event-multiset regressions; no source execution."""
import ast,json
from pathlib import Path
from unittest.mock import patch
from source_bindings import Facts,sha
import reflection_audit as ra,callee_identity as ci,lexical_bindings as lb,parameter_flow as pf
E=Path(__file__).resolve().parent;P='fixtures/claude_b9f_binder.py';PA='fixtures/claude_b9f_callee.py';TARGET='fixtures.claude_b9f_callee'
PRE='from inv.workspace_api import WorkspaceAPI as Owner\nfrom foreign_module import receive\nheld = Owner(None, None, None)\n';DEF='def accept(slot):\n    return None\n';IMPORT='from '+TARGET+' import accept\n'
def main():
    rows=[]
    for name,source,expected in [
      ('starred-hidden-level',"__import__('workspace_config', *(globals(), None, (), 1))",True),
      ('starred-tail-level',"__import__('workspace_config', globals(), None, (), *(1,))",True),
      ('starred-name',"__import__(*args)",True),
      ('starred-package',"importlib.import_module('json', *('x',))",True),
      ('importlib-dunder-level1',"importlib.__import__('workspace_config', globals(), None, (), 1)",True),
      ('importlib-dunder-keyword',"importlib.__import__('workspace_config', level=1)",True),
      ('importlib-dunder-alias',"im('workspace_config', level=1)",True),
      ('builtin-level0',"__import__('json', level=0)",False),
      ('importlib-level0',"importlib.__import__('json', globals(), None, (), 0)",False),
      ('importlib-level0-keyword',"importlib.__import__('json', level=0)",False),
      ('starred-prefix-even-keyword-zero',"__import__('json', *args, level=0)",True),
      ('plain-import-module',"importlib.import_module('json')",False),
    ]:
        source='import importlib\nim=importlib.__import__\n'+source+'\n';compile(source,P,'exec');hits=ra.hits(Facts(P,source));observed=any(x['kind']=='ENUMERATED_REFLECTION_NONLITERAL_KEY' for x in hits)
        assert observed is expected,(name,hits);rows.append({'case':name,'pass':True,'sourceSHA256':sha(source),'unknown':observed,'scope':'AST_ONLY'})
    baseline=PRE+IMPORT+'accept(held)\n'
    prior=json.loads((E/'rev9f-review-reviewer-rev9f-delta-probes-result.json').read_bytes());prior={r['case']:r for r in prior['binderFixtures']}
    variants=[
      ('control-cross-module-import-plain',IMPORT,None),
      ('near-cross-module-imported-callee-star-shadow',IMPORT+'from foreign_module import *\n','UNRESOLVED:CALLEE_REBOUND'),
      ('near-cross-module-imported-callee-global-import',IMPORT+'def alter():\n    global accept\n    from foreign_module import accept\nalter()\n','UNRESOLVED:CALLEE_REBOUND'),
      ('global-declaration-alone',IMPORT+'def alter():\n    global accept\n    pass\n',None),
      ('unrelated-local',IMPORT+'def alter():\n    accept=receive\n    return accept\n',None),
      ('unrelated-unused-alias',IMPORT+'spare=accept\n',None),
      ('nested-class-scope',IMPORT+'class Local:\n    accept=receive\n',None),
      ('lambda-scope',IMPORT+'local=lambda accept: accept\n',None),
      ('comprehension-scope',IMPORT+'local=[accept for accept in (receive,)]\n',None),
      ('direct-reassignment',IMPORT+'accept=receive\n','UNRESOLVED:CALLEE_REBOUND'),
      ('duplicate-import-event',IMPORT+IMPORT,'UNRESOLVED:CALLEE_REBOUND'),
      ('replaced-import-same-count','from foreign_module import accept\n','UNRESOLVED:CALLEE_REBOUND'),
    ]
    frozen_baseline=ci.baseline
    for name,body,reason in variants:
        source=PRE+body+'accept(held)\n';compile(source,P,'exec');sources={PA:DEF,P:source}
        exact=name in prior
        if exact:assert prior[name]['sourceSHA256']=={p:sha(s) for p,s in sorted(sources.items())}
        # These two exact reviewer regressions also exercise the no-frozen
        # structural binder bound. Frozen-source fixtures then check identity.
        contexts=[False,True] if exact else [True]
        for frozen in contexts:
            with patch.object(ci,'baseline',side_effect=lambda p:Facts(P,baseline) if p==P and frozen else frozen_baseline(p)):
                data,error=pf.solve(sources);assert error is None,(name,error)
                reasons=[x['reason'] for x in data['unresolved']]
                assert (reason in reasons if reason else not reasons),(name,frozen,reasons)
                if not reason:assert 'slot' in data['parameters'][PA].get('accept',[]),(name,frozen)
            rows.append({'case':name,'pass':True,'frozenFixtureBaseline':frozen,'exactCe713BinderInput':exact,'sourceSHA256':{p:sha(s) for p,s in sorted(sources.items())},'reason':reason,'scope':'BINDER_ONLY_NO_FULL_PROVENANCE_OR_RUNTIME_GRANT'})
    # Equal cardinality cannot authenticate a different import or scope event.
    old=lb.index(Facts(P,baseline));new=lb.index(Facts(P,PRE+'from foreign_module import accept\naccept(held)\n'))
    a=old.events_for('','accept');b=new.events_for('','accept');assert sum(a.values())==sum(b.values())==1 and a!=b
    duplicate=lb.index(Facts(P,PRE+IMPORT+IMPORT+'accept(held)\n'));assert sum(duplicate.events_for('','accept').values())==2
    assert old.records and all(r['expressionSHA256'] and len(r['span'])==4 for r in old.records)
    rows.append({'case':'exact-event-identity-and-multiplicity','pass':True,'sameCountDifferentImportRejected':True,'duplicateCount':2,'records':old.records,'scope':'BINDER_ONLY'})
    (E/'rev9g-unit-results.json').write_bytes((json.dumps({'cases':rows,'count':len(rows),'nonlocal':'INFO/OUTSIDE_CUT','binderAlone':'INSUFFICIENT; full source/use-site/provenance required','effectfulFixturesExecuted':False,'actualRuntimeB':0},indent=2)+'\n').encode());print(json.dumps({'cases':len(rows),'passed':True}))
if __name__=='__main__':main()
