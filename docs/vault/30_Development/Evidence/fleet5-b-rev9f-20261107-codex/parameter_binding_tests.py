"""AST-only binder controls, separate from full actual-source provenance tests."""
import ast,json
from pathlib import Path
from source_bindings import Facts,sha
from parameter_flow import solve
from use_sites import audited_nodes
E=Path(__file__).resolve().parent;P='fixtures/b9d_parameter_fixture.py'

def main():
    rows=[]
    prefix='from inv.workspace_api import WorkspaceAPI as Owner\nfrom foreign_module import receive\nheld = Owner(None, None, None)\n'
    same='def accept(runtime: "UntrustedAnnotation"):\n    return receive(runtime)\n'
    variants=[('same-function-unowned-positive',same+'accept("plain")\n','accept','runtime',False,None),
      ('same-function-owned-positional',same+'accept(held)\n','accept','runtime',True,None),
      ('owned-alias-keyword',same+'chosen = accept\nchosen(runtime=held)\n','accept','runtime',True,None),
      ('owned-literal-keyword-spread',same+'accept(**{"runtime": held})\n','accept','runtime',True,None),
      ('owned-unknown-keyword-spread',same+'payload = {"runtime": held}\naccept(**payload)\n','accept','runtime',False,'UNRESOLVED:OWNED_ARGUMENT_KEYWORD_SPREAD_BINDING'),
      ('arbitrary-formal-name','def accept(recipient):\n    return receive(recipient)\naccept(held)\n','accept','recipient',True,None),
      ('constructor-skips-receiver','class Box:\n    def __init__(that, slot):\n        receive(slot)\nBox(held)\n','Box.__init__','slot',True,None),
      ('constructor-keyword-alias','class Box:\n    def __init__(that, slot):\n        receive(slot)\nAlias = Box\nAlias(slot=held)\n','Box.__init__','slot',True,None),
      ('bound-method-skips-receiver','class Box:\n    def accept(that, slot):\n        receive(slot)\n    def start(that, payload):\n        that.accept(payload)\nBox.start(Box(), held)\n','Box.accept','slot',True,None),
      ('nested-enclosing-parameter','def accept(recipient):\n    def inner():\n        return receive(recipient)\n    return inner()\naccept(held)\n','accept','recipient',True,None),
      ('duplicate-owned-binding',same+'accept(held, runtime=held)\n','accept','runtime',False,'UNRESOLVED:DUPLICATE_ARGUMENT_BINDING')]
    for name,body,q,formal,expected,expected_error in variants:
        source=prefix+body;ast.parse(source);data,error=solve({P:source});assert error is None
        owned=formal in data['parameters'][P].get(q,[])
        assert owned is expected,(name,data['parameters'])
        if expected_error:assert any(r['reason']==expected_error for r in data['unresolved']),(name,data['unresolved'])
        else:assert not data['unresolved'],(name,data['unresolved'])
        f=Facts(P,source);tags=[(f.enclosing(n),getattr(n,'id',None),tag) for n,tag in audited_nodes(f,True,data['ownerFactorySymbols'],data['parameters'][P])]
        if expected:assert any(tag=='INSTANCE:'+formal and (scope==q or scope.startswith(q+'.')) for scope,_,tag in tags),(name,tags)
        rows.append({'case':name,'pass':True,'ownedParameter':owned,'expectedOwned':expected,'reason':expected_error,'sourceSHA256':sha(source),'bindings':data['bindings'],'astValid':True,'effectfulFixtureExecuted':False})
    (E/'parameter-binding-test-results.json').write_bytes((json.dumps({'executionOwner':'Codex','cases':rows,'scope':'Lexical binder unit fixtures only; no standalone provenance/runtime grant','actualRuntimeB':0},indent=2)+'\n').encode());print(json.dumps({'parameterBindingCases':len(rows),'passed':True}))
if __name__=='__main__':main()
