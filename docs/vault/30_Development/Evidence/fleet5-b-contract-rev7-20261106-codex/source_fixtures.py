"""Bounded serial selected-source counterexamples. No app imports/DB/Node.

Each mutation analyzes only the affected real source and explicit dependencies;
unrelated missing RULES in a selected subset are never called a mutation failure.
"""
import ast,gc,hashlib,json,subprocess,time
from pathlib import Path
from copy import deepcopy
import source_analysis as sc
import reconcile as rc
from authority import build
E=Path(__file__).resolve().parent;R=[]
CP='services/control-plane/src/inv/zz_rev7_probe.py';API='src/saintvision/services/zz_rev7_probe.py'
NEED=['services/control-plane/src/inv/leases.py','services/control-plane/src/inv/runs.py','services/control-plane/src/inv/db.py','src/saintvision/db/models/__init__.py','src/saintvision/db/models/resource.py','src/saintvision/db/models/storage.py']
def source(p):return subprocess.check_output(['git','show',sc.BASE+':'+p])
def check(n,b,detail=None):R.append(dict(case=n,pass_=bool(b),detail=detail));assert b,(n,detail)
def analyze(src):
    assert len(src)<=12 and sum(map(len,src.values()))<2*1024*1024,'bounded selected source budget'
    result=sc.analyze(src);return result
def cleanup(g):
    del g;sc.spelling.cache_clear()
    from source_semantics import text
    text.cache_clear();gc.collect()

def main():
    deps={p:source(p) for p in NEED};matrix=build()
    # Preserve actual W1-W16 source shapes from the immutable owner proof,
    # extracting its literal mutation list as data, never executing its main.
    prior=(E.parent/'fleet5-b-contract-rev6-20261106-codex/source_fixtures.py').read_text(encoding='utf8')
    old=ast.parse(prior);main=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    node=next(n.value for n in main.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='variants' for t in n.targets))
    NT='services/control-plane/src/inv/node_transport.py';OB='services/control-plane/src/inv/observation.py';BE='services/control-plane/src/inv/build_execution.py';ST='src/saintvision/services/storage.py'
    def add(path,body):return {**deps,path:body.encode()}
    def mutate(path,old,new):
        raw=source(path);assert old.encode() in raw;return {**deps,path:raw.replace(old.encode(),new.encode(),1)}
    cases=eval(compile(ast.Expression(node),'IMMUTABLE_REV6_VARIANTS_AS_DATA','eval'),{'__builtins__':{}},{'add':add,'mutate':mutate,'cp':CP,'api':API,'nt':NT,'ob':OB,'be':BE,'st':ST})
    for name,src,expected in cases:
        g=analyze(src);mapped=rc.mapping(g,matrix);errs=rc.audit(g,matrix,mapped)
        # A mutation must have its own causal signal. Other missing subset
        # writers are a scope limitation, not evidence that this mutant failed.
        if name.startswith(('W4-','W15-')):ok=any(u['path']==CP for u in g['sqlScopeIssues'])
        elif name.startswith('W5-'):ok=any(u['path']==API for u in g['sqlScopeIssues'])
        elif name.startswith('W9-'):ok=any(e.startswith('STALE_REQUIRED_RULE:') and '_mark_node_quarantined' in e for e in errs)
        elif name.startswith('W10-'):ok=any(e.startswith('STALE_REQUIRED_RULE:') and '_quarantine_gpu_node' in e for e in errs)
        else:ok=any(e.startswith(expected) and ('.zz_rev7_probe.' in e or any(x in e for x in ('_quarantine_gpu_node','NodeObservation.','storage.activate_contribution'))) for e in errs)
        check(name,ok,{'expected':expected,'causalErrors':[e for e in errs if e.startswith(expected)],'SQLIssues':[q['id'] for q in g['sqlScopeIssues'] if q['path'] in (CP,API)]})
        print(name,flush=True);cleanup(g)
    counter=[
      ('W17-percent-identifier',CP,'def f(conn,t):\n conn.execute("UPDATE inv.%s SET status=\'online\'" % t)\n','sql'),
      ('W18-concat-identifier',CP,'def f(conn,t):\n conn.execute("UPDATE inv."+t+" SET status=\'online\'")\n','sql'),
      ('W19-format-identifier',CP,'def f(conn,t):\n conn.execute("UPDATE inv.{} SET status=\'online\'".format(t))\n','sql'),
      ('W19b-join-identifier',CP,'def f(conn,t):\n conn.execute("".join(["UPDATE inv.",t," SET status=\'online\'"]))\n','sql'),
      ('W20-query-update',API,'from sqlalchemy.orm import Session\nfrom saintvision.db.models import Node\ndef f(session:Session,n):\n session.query(Node).filter(Node.node_id==n).update({"status":"active"})\n','writer'),
      ('W20b-query-delete',API,'from sqlalchemy.orm import Session\nfrom saintvision.db.models import Node\ndef f(session:Session,n):\n session.query(Node).filter(Node.node_id==n).delete()\n','writer'),
      ('W21-bulk-update',API,'from sqlalchemy.orm import Session\nfrom saintvision.db.models import Node as N\ndef f(session:Session,n):\n session.bulk_update_mappings(N,[{"node_id":n,"status":"active"}])\n','writer'),
      ('W21b-bulk-insert',API,'from sqlalchemy.orm import Session\nfrom saintvision.db.models import Node as N\ndef f(session:Session,n):\n session.bulk_insert_mappings(N,[{"node_id":n,"status":"active"}])\n','writer'),
      ('W22-mixed-session-and-xact',CP,'def f(conn,k):\n conn.execute("SELECT pg_advisory_xact_lock(%s),pg_advisory_lock(%s)",(k,k))\n','session'),
      ('closed-literal-set-positive',CP,'def f(conn,flag):\n q="UPDATE inv.nodes SET status=\'offline\'" if flag else "UPDATE public.nodes SET status=\'lost\'"\n conn.execute(q)\n','closed'),
      ('tuple-RunStore-equivalent',CP,'from .runs import RunStore\nfrom .db import BoundDatabase\ndef f(db,t,conn,run):\n bound=BoundDatabase(db,t,conn)\n runs,other=RunStore(bound),[]\n return runs.transition(t,run,"planned",expected_version=1)\n','edge'),
      ('starred-RunStore-equivalent',CP,'from .runs import RunStore\ndef f(db,t,conn,run):\n runs,*other=RunStore(db),1,2\n return runs.transition(t,run,"planned",expected_version=1)\n','edge'),
      ('chained-RunStore-equivalent',CP,'from .runs import RunStore\ndef f(db,t,conn,run):\n runs=also=RunStore(db)\n return runs.transition(t,run,"planned",expected_version=1)\n','edge'),
      ('dict-authority-dispatch-BLOCK',CP,'from . import leases\ndef f(conn,r,p,k):\n return {"a":leases.lock_run}[k](conn,r,p)\n','unknown'),
      ('untyped-injected-admit-BLOCK',CP,'def f(store,conn,p,r):\n return store._admit_locked(conn,p,r)\n','unknown'),
      ('builtin-shadow-is-not-waived',CP,'def f(s):\n def len(x):return x.db.execute("UPDATE inv.nodes SET status=\'online\'")\n return len(s)\n','unknown'),
      ('inner-factory-not-hidden-by-outer-DB-record',CP,'def f(mystery):\n return mystery().execute("SELECT * FROM inv.nodes FOR SHARE")\n','unknown'),
      ('dynamic-eval-not-NONAUTHORITY',CP,'def f(code):return eval(code)\n','unknown'),
      ('typed-Session-status-positive',CP,'from sqlalchemy.orm import Session\ndef f(session:Session):\n return session.in_transaction()\n','status'),
      ('retained-Timer-cancel-positive',CP,'from threading import Timer\ndef f():\n timer=Timer(1,lambda:None)\n timer.cancel()\n','timer'),
      ('retained-literal-module-getattr-positive',CP,'from . import leases\ndef f(conn,r):\n return getattr(leases,"lock_run")(conn,r)\n','getattr'),
      ('actual-dataclass-module-alias-positive',CP,'from saintvision.services import nodes as ns\ndef f():\n return ns.ObservationInput(kind="cpu",total_quantity=1,unit="m")\n','value'),
    ]
    for name,path,body,expect in counter:
        extra={'src/saintvision/services/nodes.py':source('src/saintvision/services/nodes.py')} if expect=='value' else {}
        g=analyze({**add(path,body),**extra});local=[c for c in g['classifiedCalls'] if c['path']==path]
        if expect=='sql':ok=any(u['path']==path for u in g['sqlScopeIssues']) and any(p['path']==path and p['supportStatus'].startswith('UNSUPPORTED') for p in g['functionPlans'])
        elif expect=='writer':ok=any(w['path']==path and w['table']=='public.nodes' for w in g['writers'])
        elif expect=='session':ok=any(r['path']==path and any('SESSION_ADVISORY' in m for m in r['modes']) for r in g['records']) and any(p['path']==path and p['supportStatus'].startswith('UNSUPPORTED') for p in g['functionPlans'])
        elif expect=='closed':ok={w['table'] for w in g['writers'] if w['path']==path}=={'inv.nodes','public.nodes'} and not any(u['path']==path for u in g['sqlScopeIssues'])
        elif expect=='edge':ok=any(t.endswith('RunStore.transition') for c in local for t in c['targets']) and any(t.endswith('RunStore._transition') for p in g['functionPlans'] if p['path']==path for t in p['closureFunctions'])
        elif expect=='unknown':ok=any(c['blocksGrant'] for c in local) and any(p['path']==path and p['supportStatus'].startswith('UNSUPPORTED') for p in g['functionPlans'])
        elif expect=='timer':ok=any(c['spelling']=='timer.cancel' and c['classification']=='NONAUTHORITY_STDLIB' for c in local)
        elif expect=='getattr':ok=any(c['classification']=='RESOLVED_ATTRIBUTE_FACTORY' for c in local) and not any(c['blocksGrant'] for c in local)
        elif expect=='status':ok=any(c['classification']=='RESOLVED_TRANSACTION_STATUS' for c in local) and not any(c['blocksGrant'] for c in local)
        else:ok=any(c['classification']=='NONAUTHORITY_VALUE_INITIALIZER' for c in local)
        check(name,ok,{'localClasses':[(c['spelling'],c['classification']) for c in local]});print(name,flush=True);cleanup(g)
    # Negative real value-object post_init effect, not just a forged type label.
    path='src/saintvision/services/nodes.py';raw=source(path);marker=b'class ObservationInput:';start=raw.index(marker);end=raw.index(b'\ndef record_observations',start)
    changed=raw[:end]+b'\n    def __post_init__(self):\n        self.db.execute("UPDATE inv.nodes SET status=\'online\'")\n'+raw[end:]
    g=analyze({**deps,path:changed,CP:b'from saintvision.services import nodes as ns\ndef f():\n return ns.ObservationInput()\n'})
    check('real-value-post-init-authority-not-skipped',any(t.endswith('ObservationInput.__post_init__') for c in g['classifiedCalls'] if c['path']==CP for t in c['targets']) and any(w['function'].endswith('ObservationInput.__post_init__') for w in g['writers']));cleanup(g)
    # Causal closure: a newly unresolved edge blocks only actual resolved callers.
    g=analyze({CP:b'def f(store):return store._admit_locked()\ndef affected(s):return f(s)\ndef healthy():return 1\n'})
    check('causal-default-unknown-no-false-supported',any(p['function'].endswith('.affected') and p['supportStatus'].startswith('UNSUPPORTED') and p['unknownIDs'] for p in g['functionPlans']))
    check('no-global-denial-from-unknown',not any(u['function'].endswith('.healthy') for u in g['unknownEdges']));cleanup(g)
    from own_memory import measure
    result={'memory':measure(),'level':'BOUNDED_SERIAL_SELECTED_GIT_AST_ONLY','cases':R,'passed':len(R),'failed':0,'maxCaseFiles':12,'maxCaseSourceBytes':2*1024*1024,'enforcedOSRAMLimit':None,'actualRuntimeB':0,'notClaimed':'No full1905 independent reproduction; these are author delta checks; whole independent Rev7 review pending'}
    (E/'source-fixture-results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps({'sourceDeltaCases':len(R),'failed':0}))

if __name__=='__main__':main()
