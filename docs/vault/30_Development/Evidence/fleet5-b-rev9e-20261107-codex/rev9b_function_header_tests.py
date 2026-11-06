"""OWNER lexical-header controls; source AST only, no mutant execution."""
import ast,json
from pathlib import Path
import analysis_rules as r
import use_sites as u
from source_bindings import frozen_source,sha
E=Path(__file__).resolve().parent

def main():
    source=frozen_source('services/control-plane/src/inv/observation.py');cases=[]
    for kind in ('unchanged-positive','argument-shadow','decorator'):
        tree=ast.parse(source);fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='mark_offline')
        if kind=='argument-shadow':
            fn.args.kwonlyargs.append(ast.arg(arg='DomainError'));fn.args.kw_defaults.append(ast.Constant(None))
        elif kind=='decorator':fn.decorator_list.append(ast.Name(id='foreign_decorator',ctx=ast.Load()))
        mutated=ast.unparse(ast.fix_missing_locations(tree));ast.parse(mutated)
        accepted=r.constructor_binding(mutated);_,reason=u.module_uses(mutated,instances=False);expected=kind=='unchanged-positive'
        assert accepted is expected and (reason is None if expected else reason.startswith('DYNAMIC_BLOCK:USE_SITE_NOT_ALLOWLISTED')),kind
        cases.append({'case':kind,'accepted':accepted,'expectedAccepted':expected,'pass':True,'sourceSHA256':sha(mutated),'reason':reason,'parsedOnly':True})
    (E/'function-header-test-results.json').write_bytes((json.dumps({'executionOwner':'Codex','cases':cases,'effectfulMutantsImportedOrExecuted':False,'actualRuntimeB':0},indent=2)+'\n').encode());print(json.dumps({'functionHeaderCases':3,'passed':True}))

if __name__=='__main__':main()
