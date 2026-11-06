"""Affected reflection/callable identity/finite kwargs AST units only."""
import ast,json
from pathlib import Path
from source_bindings import Facts,sha
import reflection_audit as ra
import parameter_flow as pf
E=Path(__file__).resolve().parent;P='fixtures/b9e_units.py'
PRE='from inv.workspace_api import WorkspaceAPI as Owner\nfrom foreign_module import receive\nheld=Owner(None,None,None)\n'
def main():
    rows=[]
    for name,source,unknown in [
      ('sys-name',"import sys\nkey='json'\nsys.modules[key]\n",True),
      ('sys-fstring',"import sys\nsys.modules[f'json']\n",True),
      ('sys-attribute',"import sys\nsys.modules(settings.key)\n",True),
      ('sys-subscript',"import sys\nsys.modules[keys[0]]\n",True),
      ('importlib-call',"import importlib\nimportlib.import_module('.'.join(('inv','workspace_config')))\n",True),
      ('getattr-name',"name='runtime'\ngetattr(obj,name)\n",True),
      ('inspect-name',"import inspect\ninspect.getattr_static(obj,name)\n",True),
      ('attrgetter-name',"import operator\noperator.attrgetter(name)\n",True),
      ('methodcaller-name',"import operator\noperator.methodcaller(name)\n",True),
      ('import-name',"__import__(name)\n",True),
      ('import-keyword',"import importlib\nimportlib.import_module(name=name)\n",True),
      ('over-depth',"import sys\nsys.modules['j'+'s'+'o'+'n'+'.'+'x']\n",True),
      ('over-length',"import sys\nsys.modules["+repr('x'*513)+"]\n",True),
      ('benign-literal',"import sys\nsys.modules['json']\n",False),
      ('unused-import-string',"import operator\nnote='inv.workspace_api.WorkspaceAPI'\n",False),
      ('bounded-literal',"import sys\nsys.modules['j'+'s'+'o'+'n']\n",False),
    ]:
        hits=ra.hits(Facts(P,source));actual=any(r['kind']=='ENUMERATED_REFLECTION_NONLITERAL_KEY' for r in hits)
        assert actual==unknown,(name,hits);rows.append({'case':name,'pass':True,'unknown':actual,'sha256':sha(source)})
    for name,body,reason,owned in [
      ('new-varargs','class Box:\n def __new__(cls,*args): return super().__new__(cls)\n def __init__(self,slot): pass\nBox(held)\n','UNRESOLVED:CLASS_CONSTRUCTION_BINDING',None),
      ('new-without-init','class Box:\n def __new__(cls,*args): return super().__new__(cls)\nBox(held)\n','UNRESOLVED:CLASS_CONSTRUCTION_BINDING',None),
      ('in-proof-base-new','class Base:\n def __new__(cls,*args): return super().__new__(cls)\nclass Box(Base):\n def __init__(self,slot): pass\nBox(held)\n','UNRESOLVED:CLASS_CONSTRUCTION_BINDING',None),
      ('metaclass','class Meta(type): pass\nclass Box(metaclass=Meta):\n def __init__(self,slot): pass\nBox(held)\n','UNRESOLVED:CLASS_CONSTRUCTION_BINDING',None),
      ('unknown-base','class Box(Foreign):\n def __init__(self,slot): pass\nBox(held)\n','UNRESOLVED:CLASS_CONSTRUCTION_BINDING',None),
      ('rebind','def accept(slot): pass\ndef wrap(fn): return fn\naccept=wrap(accept)\naccept(held)\n','UNRESOLVED:CALLEE_REBOUND',None),
      ('alias-before-rebind','def accept(slot): pass\ndef other(slot): pass\ndef wrap(fn): return fn\naccept=other\naccept=wrap(accept)\naccept(held)\n','UNRESOLVED:CALLEE_REBOUND',None),
      ('delete','def accept(slot): pass\ndel accept\naccept(held)\n','UNRESOLVED:CALLEE_REBOUND',None),
      ('import-shadow','def accept(slot): pass\nfrom foreign_module import accept\naccept(held)\n','UNRESOLVED:CALLEE_REBOUND',None),
      ('global-rebind','def accept(slot): pass\ndef alter():\n global accept\n accept=receive\naccept(held)\n','UNRESOLVED:CALLEE_REBOUND',None),
      ('new-decorator','def swap(fn): return fn\n@swap\ndef accept(slot): pass\naccept(held)\n','UNRESOLVED:CALLEE_REBOUND',None),
      ('unrelated-local','def accept(slot): pass\ndef unrelated():\n accept=receive\n return accept\naccept(held)\n',None,('accept','slot')),
      ('ordinary-init','class Box:\n def __init__(self,slot): pass\nBox(held)\n',None,('Box.__init__','slot')),
      ('unowned-rebound','def accept(slot): pass\ndef wrap(fn): return fn\naccept=wrap(accept)\naccept("plain")\n',None,None),
      ('kwargs-member','def accept(**extra): return receive(extra)\naccept(slot=held)\n',None,('accept','extra')),
    ]:
        source=PRE+body;data,error=pf.solve({P:source});assert error is None,(name,error)
        reasons=[x['reason'] for x in data['unresolved']]
        assert (reason in reasons if reason else not reasons),(name,reasons)
        if owned:assert owned[1] in data['parameters'][P].get(owned[0],[]),(name,data['parameters'])
        if name=='kwargs-member':
            binding=next(x for x in data['bindings'] if x['formal']=='extra');member=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='accept').keywords[0].value
            assert binding['argumentForm']=='EXPLICIT_KEYWORDS_TO_KWARG_DICT'
            assert binding['argumentEvidence']==[{'span':[member.lineno,member.col_offset,member.end_lineno,member.end_col_offset],'sourceExpressionSHA256':sha(ast.get_source_segment(source,member))}]
        rows.append({'case':name,'pass':True,'reason':reason,'sourceSHA256':sha(source),'iterations':data['iterations'],'iterationBound':data['iterationBound'],'bindings':data['bindings']})
    (E/'rev9e-unit-results.json').write_bytes((json.dumps({'cases':rows,'effectfulFixturesExecuted':False,'actualRuntimeB':0},indent=2)+'\n').encode());print(json.dumps({'cases':len(rows),'passed':True}))
if __name__=='__main__':main()
