"""Relevant relative-import and lexical binding category regressions; AST only."""
import ast,json
from pathlib import Path
from source_bindings import Facts,sha
import reflection_audit as ra,callee_identity as ci,parameter_flow as pf
E=Path(__file__).resolve().parent;P='fixtures/b9f_units.py'
PRE='from inv.workspace_api import WorkspaceAPI as Owner\nfrom foreign_module import receive\nheld=Owner(None,None,None)\ndef accept(slot): pass\n'
def main():
    rows=[]
    for name,expression,unknown in [
      ('relative-variable-package',"importlib.import_module('.workspace_config', package)",True),
      ('relative-literal-package',"importlib.import_module('.workspace_config', 'inv')",True),
      ('relative-keyword-package',"importlib.import_module('.workspace_config', package='inv')",True),
      ('absolute-variable-package',"importlib.import_module('json', package=package)",True),
      ('absolute-literal-package',"importlib.import_module('json', 'json')",False),
      ('absolute-no-package',"importlib.import_module('json')",False),
      ('absolute-keyword-name',"importlib.import_module(name='json')",False),
      ('relative-leading-dots',"importlib.import_module('..json', 'json')",True),
      ('level-positional-one',"__import__('workspace_config', globals(), None, (), 1)",True),
      ('level-keyword-one',"__import__('workspace_config', level=1)",True),
      ('level-keyword-variable',"__import__('json', level=level)",True),
      ('level-positional-variable',"__import__('json', globals(), None, (), level)",True),
      ('level-keyword-zero',"__import__('json', level=0)",False),
      ('level-positional-zero',"__import__('json', globals(), None, (), 0)",False),
      ('level-absent',"__import__('json')",False),
      ('level-bool-conservative',"__import__('json', level=False)",True),
      ('dunder-relative-name',"__import__('.json')",True),
      ('package-spread-unknown',"importlib.import_module('json', **bag)",True),
      ('level-spread-unknown',"__import__('json', **bag)",True),
    ]:
        source='import importlib\n'+expression+'\n';compile(source,P,'exec');f=Facts(P,source)
        hits=ra.hits(f);actual=any(h['kind']=='ENUMERATED_REFLECTION_NONLITERAL_KEY' for h in hits)
        assert actual is unknown,(name,hits);rows.append({'case':name,'pass':True,'sourceSHA256':sha(source),'unknown':actual,'syntaxCompiledOnly':True})
    variants=[
      ('import','import foreign_module as accept'),('importfrom','from foreign_module import accept'),('importfrom-alias','from foreign_module import receive as accept'),
      ('def','def accept(slot):\n    return receive(slot)'),('async-def','async def accept(slot):\n    return receive(slot)'),('class','class accept:\n    pass'),
      ('match-as','match "value":\n    case accept: pass'),('match-star','match []:\n    case [*accept]: pass'),('match-mapping-rest','match {}:\n    case {**accept}: pass'),
      ('except','try:\n    raise ValueError()\nexcept ValueError as accept:\n    pass'),
      ('store','accept=receive'),('delete','del accept'),('augmented','accept+=1'),('named-expression','(accept:=receive)')]
    for name,body in variants:
        for global_binding in (True,False):
            source=PRE+'def alter():\n'+('    global accept\n' if global_binding else '')+'\n'.join('    '+line for line in body.splitlines())+'\nalter()\naccept(held)\n'
            compile(source,P,'exec');data,error=pf.solve({P:source});assert error is None,(name,error)
            reasons=[r['reason'] for r in data['unresolved']];rebound=ci.rebound(Facts(P,source),'accept')
            assert rebound is global_binding,(name,global_binding,rebound)
            assert ('UNRESOLVED:CALLEE_REBOUND' in reasons) is global_binding,(name,global_binding,reasons)
            if not global_binding:assert 'slot' in data['parameters'][P].get('accept',[])
            rows.append({'case':('global-' if global_binding else 'local-control-')+name,'pass':True,'sourceSHA256':sha(source),'reason':reasons,'syntaxCompiledOnly':True})
    controls=[
      ('global-declaration-alone','def alter():\n global accept\n pass\n'),
      ('nested-function-boundary','def alter():\n global accept\n def inner():\n  accept=receive\n return inner\n'),
      ('nested-class-boundary','def alter():\n global accept\n class Local:\n  accept=receive\n return Local\n'),
      ('comprehension-boundary','def alter():\n global accept\n return [accept for accept in (receive,)]\n'),
      ('module-comprehension-boundary','shadow=[accept for accept in (receive,)]\n'),
      ('lambda-boundary','shadow=lambda accept: accept\n')]
    for name,body in controls:
        source=PRE+body+'accept(held)\n';compile(source,P,'exec');data,error=pf.solve({P:source});assert error is None and not data['unresolved'],(name,error,(data or {}).get('unresolved'))
        assert not ci.rebound(Facts(P,source),'accept');rows.append({'case':name,'pass':True,'sourceSHA256':sha(source),'syntaxCompiledOnly':True})
    for name,body in [('star-import','from foreign_module import *\n'),('global-walrus-through-comprehension','def alter():\n global accept\n return [(accept:=receive) for x in (1,)]\n')]:
        source=PRE+body+'accept(held)\n';compile(source,P,'exec');data,error=pf.solve({P:source});assert error is None and any(x['reason']=='UNRESOLVED:CALLEE_REBOUND' for x in data['unresolved']),(name,error)
        rows.append({'case':name,'pass':True,'sourceSHA256':sha(source),'syntaxCompiledOnly':True})
    (E/'rev9f-unit-results.json').write_bytes((json.dumps({'cases':rows,'count':len(rows),'nonlocal':'INFO/OUTSIDE_REQUIRED_CUT','binderAlone':'INSUFFICIENT; full provenance/use-site guard required for class-body/attribute stores','effectfulFixturesExecuted':False,'actualRuntimeB':0},indent=2)+'\n').encode());print(json.dumps({'cases':len(rows),'passed':True}))
if __name__=='__main__':main()
