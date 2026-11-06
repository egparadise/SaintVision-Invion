"""Selected analysis mutants only. No application imports/DB/Docker/Node IO."""
import ast,json
from pathlib import Path
import bounded_analysis as a
E=Path(__file__).resolve().parent
cases=[]
def check(name,value):
    cases.append({'case':name,'pass':bool(value)})
    if not value:raise AssertionError(name)
def main():
    domain=a.source('services/control-plane/src/inv/errors.py')
    inv=a.source('src/saintvision/errors.py')
    check('A2-DomainError-actual-nonfrozen-constructor',a.error_initializer(domain,'DomainError'))
    check('A2-InvError-actual-postinit-category-map-base',a.error_initializer(inv,'InvError'))
    for name,text in [('DomainError',domain),('InvError',inv)]:
        before='    def __str__' if name=='DomainError' else '    def __post_init__'
        mutated=text.replace(before,'    def __init__(self):\n        database.execute("UPDATE inv.nodes SET status=1")\n\n'+before)
        check(name+'-ctor-DB-BLOCK',not a.error_initializer(mutated,name))
        if name=='DomainError':mutated=text.replace(before,'    def __post_init__(self):\n        socket.send(b"x")\n\n'+before)
        else:mutated=text.replace('self.category = category_of(self.code)','self.category = category_of(self.code)\n        socket.send(b"x")')
        check(name+'-postinit-IO-BLOCK',not a.error_initializer(mutated,name))
    text=a.source('services/control-plane/src/inv/node_channels.py')
    calls=[c for c in a.rows('classifiedCalls') if c['function']==a.PILOT]
    records=[r for r in a.rows('records') if r['function']==a.PILOT]
    unknown=[c for c in calls if c['classification']=='UNRESOLVED' and 'fetchone' in c['spelling']]
    for i,c in enumerate(unknown):
        check('A1-actual-recorded-result-'+str(i),a.cursor_result(text,a.node_at(text,c),records,calls) is not None)
    # Same method spelling cannot substitute an unrecorded producer/foreign cursor.
    for spelling in ['mystery().execute("SELECT 1").fetchone()','foreign_cursor.execute("SELECT 1").fetchone()']:
        call=ast.parse(spelling).body[0].value
        check('A1-'+spelling+'-BLOCK',a.cursor_result(text,call,records,calls) is None)
    mutated=text.replace('    with conn.transaction(), conn.cursor(row_factory=tuple_row) as cursor:\n        cursor.execute(', '    with conn.transaction(), conn.cursor(row_factory=tuple_row) as cursor:\n        cursor = foreign_cursor\n        cursor.execute(')
    check('A1-cursor-rebinding-BLOCK',a.cursor_result(mutated,a.node_at(text,unknown[0]),records,calls) is None)
    template='from sqlalchemy.orm import Session\nfrom saintvision.db.models import Node\ndef remove(session: Session):\n    row = session.get(Node, "synthetic-id")\n    session.METHOD(row)\n'
    b_tables={r['table'] for r in json.loads((a.R7/'writer-reconciliation.json').read_bytes())['writers']}
    for method,verb,label in [('delete','DELETE','W23'),('merge','UPSERT','W23b')]:
        r=a.uow(template.replace('METHOD',method),a.M['modelTables'])
        check(label+'-loaded-B-model-writer',len(r)==1 and r[0]['table']=='public.nodes' and r[0]['verb']==verb and r[0]['mode']=='FOR UPDATE')
        check(label+'-new-unmapped-B-writer-fails-census',any(x['table'] in b_tables for x in r))
        r=a.uow(template.replace('METHOD',method).replace('session.get(Node, "synthetic-id")','mystery()'),a.M['modelTables'])
        check(label+'-unknown-instance-DYNAMIC_BLOCK',len(r)==1 and r[0]['kind']=='DYNAMIC_BLOCK' and r[0]['blocksGrant'] and r[0]['mode']=='UNKNOWN')
        r=a.uow(template.replace('METHOD',method).replace('session: Session','session: object'),a.M['modelTables'])
        check(label+'-foreign-session-DYNAMIC_BLOCK',r[0]['blocksGrant'])
    for path in ['src/saintvision/services/pools.py','src/saintvision/services/settings.py']:
        r=a.uow(a.source(path),a.M['modelTables']);check('A6-actual-'+path,len(r)==1 and r[0]['kind']=='ORM_TYPED_UOW')
    a.write('analysis-test-results.json',{'ownerOnly':True,'scope':'BOUNDED_AST_PROOFS_ONLY','cases':cases,'resource':{'sourceFiles':len(a.CACHE),'bytes':sum(map(len,a.CACHE.values()))},'notImplementedRules':['A3','A4','A5','A7','A8'],'actualRuntimeB':0})
    print(json.dumps({'passed':len(cases),'selectedSourceFiles':len(a.CACHE)}))
if __name__=='__main__':main()
