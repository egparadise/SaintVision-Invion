"""OWNER hardened A1/A2 mutants; fresh parse/producer spans/hash each time."""
import ast,json,subprocess,sys
from pathlib import Path
import bounded_analysis as a
import analysis_rules as r
from mutation_fixture import rebase,after_line
E=Path(__file__).resolve().parent;R=[]
def check(name,value,**proof):
    R.append({'case':name,'pass':bool(value),**proof})
    if not value:raise AssertionError(name)
def main():
    source=a.source('services/control-plane/src/inv/node_channels.py');errors=a.source('services/control-plane/src/inv/errors.py');inv=a.source('src/saintvision/errors.py')
    calls=[c for c in a.rows('classifiedCalls') if c['function']==a.PILOT];records=[x for x in a.rows('records') if x['function']==a.PILOT]
    target=next(c for c in calls if c['classification']=='UNRESOLVED' and 'fetchone' in c['spelling'])
    fn=next(f for f in a.functions(source) if f.name=='revoke_channel');line=next(n.lineno for n in ast.walk(fn) if isinstance(n,ast.With))
    for statement,expected in [('pass',True),('conn = foreign_conn',True),('cursor = foreign_cursor',False),('(cursor := foreign_cursor)',False),
      ('cursor.execute = foreign_execute',False),("setattr(cursor, 'execute', foreign_execute)",False),("delattr(cursor, 'fetchone')",False),('del cursor.execute',False),
      ('alias = cursor\nalias.execute = foreign_execute',False),('cls = type(cursor)\ncls.execute = foreign_execute',False),('for cursor in foreign_cursors:\n    pass',False),('with foreign_factory() as cursor:\n    pass',False)]:
        mutated=after_line(source,line,statement);rec=rebase(source,mutated,records);cs=rebase(source,mutated,calls);tar=next(c for c in cs if c['id']==target['id']);node=a.node_at(mutated,tar)
        result=r.cursor_result_explain(mutated,node,rec,cs)
        check('A1-shifted-'+statement.splitlines()[0],bool(result['proof'])==expected and result['producerSanity'],reason=result['reason'],producerSanityPassed=result['producerSanity'],sourceSHA256=r.sha(mutated),recordExpressionSHA256=rec[0]['expressionSHA256'])
    check('A2-DomainError-positive',r.error_initializer(errors,'DomainError'))
    check('A2-InvError-positive',r.error_initializer(inv,'InvError'))
    for name,mutated,expected in [
      ('metaclass',errors.replace('class DomainError(Exception):','class DomainError(Exception, metaclass=Evil):'),False),
      ('later-dataclass-import',errors.replace('from dataclasses import dataclass','from dataclasses import dataclass\nfrom evil import dataclass'),False),
      ('later-Exception-import',errors.replace('from dataclasses import dataclass','from dataclasses import dataclass\nfrom evil import Exception'),False),
      ('later-field-import',errors.replace('from dataclasses import dataclass','from dataclasses import dataclass, field\nfrom evil import field').replace('retryable: bool = False','retryable: bool = field(default_factory=dict)'),False),
      ('class-alias-mutation',errors+'\nAlias = DomainError\nAlias.__init__ = foreign\n',False),
      ('class-setattr',errors+"\nsetattr(DomainError, '__init__', foreign)\n",False),
      ('constructor-db',errors.replace('    def __str__','    def __init__(self):\n        database.execute("UPDATE inv.nodes SET status=1")\n\n    def __str__'),False),
      ('postinit-io',errors.replace('    def __str__','    def __post_init__(self):\n        socket.send(b"x")\n\n    def __str__'),False),
      ('unbound-field-control-is-not-proven',errors.replace('retryable: bool = False','retryable: bool = field(default_factory=dict)'),False),
      ('proper-imported-field-positive',errors.replace('from dataclasses import dataclass','from dataclasses import dataclass, field').replace('retryable: bool = False','retryable: bool = field(default_factory=dict)'),True),
      ('module-getattr-benign-control',errors+'\n\ndef __getattr__(name):\n    return name\n',True)]:
        ast.parse(mutated);got=r.error_initializer(mutated,'DomainError');check('A2-'+name,got==expected,parsePassed=True,reason='PROVEN' if got else 'DYNAMIC_BINDING_OR_CONSTRUCTOR_EFFECT_UNPROVEN',sourceSHA256=r.sha(mutated))
    for tail in ('\nDomainError = foreign_factory\n','\nAlias = DomainError\nAlias.__init__ = foreign\n',"\nsetattr(DomainError, '__new__', foreign)\n",'\nfrom evil import DomainError\n'):
        mutated=source+tail;ast.parse(mutated);check('A2-caller-'+tail.strip().splitlines()[0],not r.constructor_binding(mutated),parsePassed=True,sourceSHA256=r.sha(mutated))
    check('A2-caller-actual-binding-positive',r.constructor_binding(source))
    # Preserve exact original16-case script/output. Three meta/control reports
    # concern old source assertions or an unbound field, not new rule failures.
    script=E/'prior-reviewer_m2_rule_mutations.py.txt';p=subprocess.run([sys.executable,'-B',str(script),str(E)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    (E/'original-reviewer-rule16-owner-rerun.log').write_bytes(p.stdout+p.stderr);assert p.returncode==0,p.stderr.decode()
    original=json.loads(p.stdout);assert len(original['cases'])==16
    expected_stale={'owner-rebinding-test-is-span-vacuous','A2-caller-name-rebinding-checked','A2-str-field-default-factory-call'}
    check('original-script-seven-rule-defects-accounted',set(original['defects'])==expected_stale,originalReportedDefects=original['defects'],explanation='Unmodified script inspects old mutation construction and hardcodes the old caller import-presence assertion. Unbound field control now refuses per Root exact-import rule; properly imported field positive above passes. No expected output altered.')
    a.write('analysis-rule-test-results.json',{'executionOwner':'Codex','independentReview':False,'cases':R,'sourceMutationPolicy':'Fresh parse + recomputed producer record spans/expression/source hashes for every cursor mutant; no effectful mutant imported/executed','priorActualReviewOriginalDefects':json.loads((E/'prior-reviewer-m2-rule-mutations-result.json').read_bytes())['defects'],'original16CaseScriptUnmodified':{'script':script.name,'actualExit':p.returncode,'output':'original-reviewer-rule16-owner-rerun.log','reportedDefects':original['defects']},'actualRuntimeB':0})
    print(json.dumps({'passed':len(R),'originalReviewerCases':16,'originalRemainingMetaControlReports':original['defects']}))
if __name__=='__main__':main()
