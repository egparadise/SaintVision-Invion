"""Focused OWNER AST-only factory binding controls; never execute mutants."""
import ast,json
from pathlib import Path
import analysis_rules as r
from source_bindings import frozen_source,sha
E=Path(__file__).resolve().parent

def main():
    source=frozen_source('services/control-plane/src/inv/errors.py').replace('from dataclasses import dataclass','from dataclasses import dataclass, field').replace('    retryable: bool = False','    retryable: bool = False\n    metadata: dict = field(default_factory=dict)')
    cases=[]
    for name,mutated,expected in [('unshadowed-builtin-positive',source,True),('factory-rebound',source+'\ndict = foreign_factory\n',False),('factory-import-alias',source+'\nfrom foreign_module import foreign_factory as dict\n',False),('factory-class-rebind',source+'\nclass dict:\n    pass\n',False)]:
        ast.parse(mutated);accepted=r.error_initializer(mutated,'DomainError')
        cases.append({'case':name,'accepted':accepted,'expectedAccepted':expected,'pass':accepted is expected,'sourceSHA256':sha(mutated),'parsedOnly':True})
        assert accepted is expected,name
    (E/'factory-binding-test-results.json').write_bytes((json.dumps({'executionOwner':'Codex','cases':cases,'effectfulMutantsImportedOrExecuted':False,'actualRuntimeB':0},indent=2)+'\n').encode())
    print(json.dumps({'factoryBindingCases':len(cases),'passed':True}))

if __name__=='__main__':main()
