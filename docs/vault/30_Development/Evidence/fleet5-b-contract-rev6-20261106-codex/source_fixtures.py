"""Actual in-memory Git-source mutations and per-plan causal classification."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time
import source_analysis as sc
import reconcile as rc
from authority import build
from rank_contract import CATALOG
import sqlalchemy
from sqlalchemy import Column,Integer,MetaData,Table,select
from sqlalchemy.dialects import postgresql

E=Path(__file__).resolve().parent;CASES=[];MUTATIONS=[]


def check(name,okay,detail=None):
    assert okay,(name,detail)
    CASES.append(dict(case=name,passed=True,detail=detail))


def main():
    sources=sc.load_sources();base=sc.analyze(sources);matrix=build();mapped=rc.mapping(base,matrix)
    check('baseline-34-known-writers',len(mapped)==34)
    check('baseline-semantic-audit',not rc.audit(base,matrix,mapped),rc.audit(base,matrix,mapped))
    check('baseline-producer-and-census-fidelity',json.loads((E/'source-analysis.json').read_bytes())==base)
    check('all21-critical-plans-present',len(base['criticalEntries'])==21,len(base['criticalEntries']))
    for p in base['functionPlans']:
        if p['criticalEntry']:
            check('critical-usable-'+p['function'],p['supportStatus']=='SUPPORTED_STATIC_PLAN' and not p['unknownIDs'] and not p['unresolvedDbSites'],p['remainingUnknowns'])
        expected={u['id'] for u in [*base['unknownEdges'],*base['sqlScopeIssues']] if u['function'] in p['transitiveFunctions']}
        check('closure-unknown-attachment-'+p['function'],set(p['unknownIDs'])==expected)
        check('support-status-consistency-'+p['function'],p['supportStatus']==('UNSUPPORTED_PENDING_SCOPED_AUTHORITY_RESOLUTION' if expected else 'SUPPORTED_STATIC_PLAN'))
    recordkeys={(r['path'],r['line'],r['column']) for r in base['records']}
    check('no-second-UNKNOWN-for-DB-record',not any((u['path'],u['line'],u['column']) in recordkeys for u in base['unknownEdges']))
    check('explicit-all-proposed-table-ranks',all(t in CATALOG for t in matrix['tables']))
    for i,w in enumerate(mapped):check('removed-mapping-semantic-deny-'+str(i),'SOURCE_WRITER_COVERAGE_MISMATCH' in rc.audit(base,matrix,mapped[:i]+mapped[i+1:]))
    cp='services/control-plane/src/inv/zz_rev6_probe.py';api='src/saintvision/services/zz_rev6_probe.py'
    def add(path,body,extra=None):
        d=dict(sources);d[path]=body.encode();d.update(extra or {});return d
    def mutate(path,old,new):
        d=dict(sources);text=d[path].decode('utf-8-sig');assert old in text,(path,old)
        d[path]=text.replace(old,new,1).encode();return d
    nt='services/control-plane/src/inv/node_transport.py';ob='services/control-plane/src/inv/observation.py';be='services/control-plane/src/inv/build_execution.py';st='src/saintvision/services/storage.py'
    variants=[
      ('W1-runtime-quarantine-reversed-to-online',mutate(nt,"UPDATE inv.nodes SET status='quarantined' WHERE node_id=%s","UPDATE inv.nodes SET status='online' WHERE node_id=%s"),'DENY_ONLY_STATUS_TARGET'),
      ('W2-CASE-removed-to-unconditional-online',mutate(ob,"status=CASE WHEN status='offline' THEN 'online' ELSE status END","status='online'"),'OBSERVATION_CASE_TRANSITION'),
      ('W3-ORM-insert',add(api,'from sqlalchemy import insert\nfrom saintvision.db.models import Node\ndef sneaky(session):\n session.execute(insert(Node).values(node_id="n",tenant_id="t",status="active"))\n'),'UNMAPPED_WRITER'),
      ('W4-dynamic-fstring-table',add(cp,'def sneaky(conn,t,n):\n conn.execute(f"UPDATE inv.{t} SET status=\'online\' WHERE node_id=%s",(n,))\n'),'UNKNOWN_SQL_WRITER_SCOPE'),
      ('W5-unqualified-unknown-effective-searchpath',add(api,'from sqlalchemy import text\ndef sneaky(session,n):\n session.execute(text("UPDATE nodes SET status=\'active\' WHERE node_id=:n"),{"n":n})\n'),'UNKNOWN_SQL_WRITER_SCOPE'),
      ('W6-model-setattr',add(api,'from saintvision.db.models import Node\ndef sneaky(session,n):\n node=session.get(Node,n)\n setattr(node,"status","active")\n'),'UNMAPPED_WRITER'),
      ('W7-ORM-attribute-positive-detector',add(api,'from saintvision.db.models import Node\ndef sneaky(session,n):\n node=session.get(Node,n)\n node.status="active"\n'),'UNMAPPED_WRITER'),
      ('W8-new-SQL-writer-positive-detector',add(api,'def sneaky(conn,n):\n conn.execute("UPDATE public.storage_contributions SET status=\'active\' WHERE contribution_id=%s",(n,))\n'),'UNMAPPED_WRITER'),
      ('W9-renamed-current-writer',mutate(be,'def _mark_node_quarantined(','def _mark_node_q('),'STALE_REQUIRED_RULE'),
      ('W10-removed-current-safety-writer',mutate(nt,'            conn.execute(\n                "UPDATE inv.nodes SET status=\'quarantined\' WHERE node_id=%s",\n                (node.node_id,),\n            )\n',''),'STALE_REQUIRED_RULE'),
      ('W11-owner-impersonation-new-column',mutate(st,'contribution.status = "active"','contribution.status = "active"\n    contribution.registered_by_user_id = actor_user_id'),'WRITER_COLUMN_UNCOVERED'),
      ('W12-ORM-pg-insert-alias',add(api,'from sqlalchemy.dialects.postgresql import insert as pg_insert\nfrom saintvision.db.models import Node\ndef sneaky(session):\n statement=pg_insert(Node).values(node_id="n",tenant_id="t",status="active")\n session.execute(statement)\n'),'UNMAPPED_WRITER'),
      ('W13-Table-update-alias',add(api,'from saintvision.db.models import Node\ndef sneaky(session):\n table=Node.__table__\n statement=table.update().values(status="active")\n session.execute(statement)\n'),'UNMAPPED_WRITER'),
      ('W14-explicit-effective-public-searchpath',add(api,'def sneaky(conn,n):\n conn.execute("SET LOCAL search_path TO public, pg_catalog")\n conn.execute("UPDATE nodes SET status=\'active\' WHERE node_id=%s",(n,))\n'),'UNMAPPED_WRITER'),
      ('W15-dynamic-format-identifier',add(cp,'def sneaky(conn,t,n):\n conn.execute("UPDATE inv.{} SET status=\'online\' WHERE node_id=%s".format(t),(n,))\n'),'UNKNOWN_SQL_WRITER_SCOPE'),
      ('W16-from-state-WHERE-guard-removed',mutate(ob,"AND status='online' RETURNING node_id","RETURNING node_id"),'OBSERVATION_FROM_GUARD'),
    ]
    for name,src,error in variants:
        started=time.monotonic();got=sc.analyze(src);errs=rc.audit(got,matrix,rc.mapping(got,matrix))
        check(name,any(e.startswith(error) for e in errs),errs)
        row=dict(case=name,expectedSemanticError=error,actualErrors=errs,seconds=round(time.monotonic()-started,3),level='MUTATED_GIT_BYTES_NOT_JSON_COMPARATOR')
        MUTATIONS.append(row);print(json.dumps({'sourceMutation':name,'semanticRejected':True}),flush=True)
    def has_edge(got,tail):return any(e['path']==cp and any(t.endswith(tail) for t in e['targets']) for e in got['edges'])
    typed=[
      ('S4-dotted-import',add(cp,'import inv.leases\ndef sneaky(conn,r):\n return inv.leases.lock_run(conn,r)\n'),lambda g:has_edge(g,'.lock_run')),
      ('S5-instance-receiver',add(cp,'from .leases import LeaseStore\ndef sneaky(db,conn,p,r):\n store=LeaseStore(db)\n return store._admit_locked(conn,p,r)\n'),lambda g:has_edge(g,'.LeaseStore._admit_locked')),
      ('S6-SQL-constant',add(cp,'Q="SELECT node_id FROM inv.nodes WHERE node_id=%s FOR UPDATE"\ndef sneaky(conn,n):\n return conn.execute(Q,(n,))\n'),lambda g:any(r['path']==cp and r['tables']==['inv.nodes'] and r['modes']==['FOR UPDATE'] for r in g['records'])),
      ('M2-dict-get-vs-DB-get-no-duplicate',add(cp,'from sqlalchemy.orm import Session\nfrom saintvision.db.models import Node\ndef sneaky(session:Session):\n payload={"k":1}\n payload.get("k")\n return session.get(Node,"n",with_for_update=True)\n'),
       lambda g:any(c['path']==cp and c['spelling']=='payload.get' and c['classification']=='NONAUTHORITY_MAPPING' for c in g['classifiedCalls']) and any(c['path']==cp and c['spelling']=='session.get' and c['classification']=='RESOLVED_DB_RECORD' for c in g['classifiedCalls']) and not any(u['path']==cp for u in g['unknownEdges'])),
      ('M2-Timer-cancel-actual-stdlib-provenance',add(cp,'from threading import Timer\ndef sneaky(conn):\n timer=Timer(1,lambda:None)\n timer.cancel()\n return conn.execute("SELECT * FROM inv.nodes FOR SHARE")\n'),
       lambda g:any(c['path']==cp and c['spelling']=='timer.cancel' and c['classification']=='NONAUTHORITY_STDLIB' and c['provenance']['receiverType']=='STDLIB:threading.Timer' for c in g['classifiedCalls']) and not any(u['path']==cp for u in g['unknownEdges'])),
      ('M2-literal-getattr-reaches-lock-helper',add(cp,'from . import leases\ndef sneaky(conn,r,p):\n return getattr(leases,"lock_run")(conn,r,p)\n'),lambda g:has_edge(g,'.lock_run') and not any(u['path']==cp for u in g['unknownEdges'])),
      ('M2-nonliteral-getattr-scoped-causal-BLOCK',add(cp,'from . import leases\ndef sneaky(conn,r,p,name):\n return getattr(leases,name)(conn,r,p)\n'),
       lambda g:any(u['path']==cp and 'nonliteral getattr' in u['reason'] for u in g['unknownEdges']) and any(p['path']==cp and p['unknownIDs'] and p['supportStatus'].startswith('UNSUPPORTED') for p in g['functionPlans']) and all(p['supportStatus']=='SUPPORTED_STATIC_PLAN' for p in g['functionPlans'] if p['criticalEntry'])),
      ('M2-runtime-constructor-transaction-owner',add(cp,'from .db import Database,BoundDatabase\ndef runtime(state):\n return Database("SYNTHETIC_NOT_A_DSN","epoch")\ndef sneaky(state,t):\n with runtime(state).transaction(t) as conn:\n  return conn.execute("SELECT * FROM inv.nodes FOR UPDATE")\n'),
       lambda g:any(b['path']==cp and b['spelling']=='runtime(state).transaction' and b['boundary']=='OPEN_OUTER_TRANSACTION' for b in g['transactionBoundaries'])),
      ('M2-bound-and-session-outer-transactions',add(cp,'from .db import BoundDatabase\nfrom sqlalchemy.orm import Session\ndef sneaky(db:BoundDatabase,session:Session,t):\n with db.transaction(t) as conn:\n  with conn.transaction():\n   session.begin()\n   return conn.execute("SELECT * FROM inv.nodes FOR SHARE")\n'),
       lambda g:any(b['path']==cp and b['boundary']=='SHARE_CALLER_OUTER' for b in g['transactionBoundaries']) and any(b['path']==cp and b['boundary']=='OPEN_OUTER_TRANSACTION' and b['spelling']=='session.begin' for b in g['transactionBoundaries'])),
      ('M2-online-session-advisory-no-offline-relabel',add(cp,'def sneaky(conn,k):\n return conn.execute("SELECT pg_advisory_lock(%s)",(k,))\n'),
       lambda g:any(r['path']==cp and r['scopeDisposition'].startswith('SESSION_ADVISORY_UNSUPPORTED') for r in g['records']) and any(p['path']==cp and p['supportStatus'].startswith('UNSUPPORTED') for p in g['functionPlans'])),
    ]
    for name,src,predicate in typed:
        started=time.monotonic();got=sc.analyze(src);okay=bool(predicate(got));check(name,okay)
        MUTATIONS.append(dict(case=name,semanticDetected=okay,seconds=round(time.monotonic()-started,3),level='MUTATED_GIT_BYTES_NOT_JSON_COMPARATOR'))
        print(json.dumps({'sourceMutation':name,'semanticDetected':okay}),flush=True)
    check('pinned-SQLAlchemy',sqlalchemy.__version__=='2.0.52')
    tab=Table('nodes',MetaData(),Column('node_id',Integer),schema='public');compilations=[]
    for opts,expected in [({},'FOR UPDATE'),({'read':True},'FOR SHARE'),({'key_share':True},'FOR NO KEY UPDATE'),({'read':True,'key_share':True},'FOR KEY SHARE'),({'skip_locked':True},'FOR UPDATE SKIP LOCKED'),({'nowait':True},'FOR UPDATE NOWAIT')]:
        sql=str(select(tab).with_for_update(**opts).compile(dialect=postgresql.dialect()));check('offline-PG-compile-'+expected,sql.endswith(expected));compilations.append(dict(options=opts,SQL=sql))
    result={'level':'STATIC_GIT_AST_SOURCE_MUTATION_AND_OFFLINE_SQL_COMPILATION_ONLY','source':sc.BASE,'passed':len(CASES),'failed':0,
        'sourceMutationCount':len(MUTATIONS),'mutations':MUTATIONS,'cases':CASES,'criticalPlans':base['criticalEntries'],
        'sqlAlchemyVersion':sqlalchemy.__version__,'offlinePGCompilations':compilations,'actualGoCryptoPGEngineCrashConcurrencyEquipment':0}
    (E/'source-fixture-results.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps({'passed':len(CASES),'sourceMutations':len(MUTATIONS),'actualPG':0}))


if __name__=='__main__':main()
