"""Source-level causal mutation tests, not JSON golden self-comparisons."""
from copy import deepcopy
import json
from pathlib import Path
import time
import sqlalchemy
from sqlalchemy import Column, Integer, MetaData, Table, select
from sqlalchemy.dialects import postgresql
import source_analysis as sc
from authority import build
from reconcile import mapping, audit

E=Path(__file__).resolve().parent
RESULTS=[]


def check(name,value,detail=None):
    assert value,(name,detail)
    RESULTS.append(dict(case=name,passed=True,detail=detail))


def main():
    sources=sc.load_sources();baseline=sc.analyze(sources)
    matrix=build();mapped=mapping(baseline,matrix)
    check('unmodified-semantic-writer-audit',not audit(baseline,matrix,mapped),audit(baseline,matrix,mapped))
    # Fidelity is separate from semantic probes, never a replacement for them.
    stored=json.loads((E/'source-analysis.json').read_bytes())
    check('unmodified-golden-fidelity',stored==baseline)
    old=json.loads((E/'prior-census-audit-result.json').read_bytes())
    cp=[r for r in old['instanceReceiverHelperCallsDropped'] if r['path'].startswith('services/control-plane/')]
    check('reviewer-real-CP-drop-count',len(cp)==24,len(cp))
    for r in cp:
        found=[e for e in baseline['edges'] if e['path']==r['path'] and e['line']==r['line'] and e['spelling']==r['spelling']]
        check('real-dropped-edge-'+r['path'].rsplit('/',1)[-1]+':'+str(r['line']),bool(found and found[0]['targets']),found)
    planned={f['function'] for f in baseline['functionPlans']}
    check('constructor-injected-worker-service-edge',any(e['function']=='inv.build_execution_worker.BuildExecutionWorker.once' and e['spelling']=='self.service.execute' and e['targets']==['inv.build_execution.BuildExecutionService.execute'] for e in baseline['edges']))
    lockers={r['function'] for r in baseline['records'] if r['modes']}
    check('ALL-actual-lockers-seeded-and-planned',lockers<=set(baseline['seedFunctions']) and lockers<=planned,{'lockers':len(lockers),'plans':len(planned)})
    for r in old['lockModeMislabels']:
        name=r['path'].rsplit('/',1)[-1]
        if name in ('leases.py','placement.py','shard_recovery.py'):expected='FOR NO KEY UPDATE'
        elif name in ('deps.py','tracking.py','operational_readiness.py','provision_account.py'):expected='TRANSACTION_ADVISORY'
        elif name=='evidence.py':expected='FOR UPDATE SKIP LOCKED'
        elif name=='lineage.py' or (name,r['line']) in {('projects.py',94),('settings.py',162)}:expected='FOR SHARE'
        else:expected='FOR UPDATE'
        modes=[mode for x in baseline['records'] if x['path']==r['path'] and x['line']==r['line'] for mode in x['modes']]
        check('actual-review-mode-'+r['path'].rsplit('/',1)[-1]+':'+str(r['line']),expected in modes,{'expected':expected,'actual':modes})
    for suffix in ('BuildPreparationService._terminalize','BuildExecutionIntentQueue.enqueue','NodePrincipal.lock_current',
                   'NodeObservation.accept','NodeObservation.mark_offline','provision_channel','revoke_channel',
                   'BuildExecutionService._mark_node_quarantined','NodeDelivery._quarantine_gpu_node',
                   'capture_channels','capture_locations','_owned_for_update','set_resource_offer'):
        matched=[p for p in baseline['functionPlans'] if p['function'].endswith('.'+suffix)]
        check('concrete-plan-'+suffix,bool(matched) and all(isinstance(p['concreteEntryContracts'][0]['discoverNodeResourceSet'],str) for p in matched))
    # Every source writer's removed mapping MUST fail semantic coverage.
    for i,w in enumerate(mapped):
        bad=mapped[:i]+mapped[i+1:]
        check('remove-writer-mapping-'+str(i), 'SOURCE_WRITER_COVERAGE_MISMATCH' in audit(baseline,matrix,bad),{'function':w['function'],'line':w['line']})

    def mutate(path,old,new):
        result=dict(sources);raw=result[path].decode('utf-8-sig')
        assert old in raw,(path,old)
        result[path]=raw.replace(old,new,1).encode();return result

    probe='services/control-plane/src/inv/zz_rev5_static_probe.py'
    def added(body):
        result=dict(sources);result[probe]=body.encode();return result
    def edge(result,tail):
        return any(e['path']==probe and any(t.endswith(tail) for t in e['targets']) for e in result['edges'])
    bp='services/control-plane/src/inv/build_preparations.py'
    na='src/saintvision/identity/node_auth.py'
    mutations=[
      ('S1-remove-known-lock_run',mutate(bp,'run = lock_run(conn, preparation["run_id"], preparation["project_id"])','run = None'),
       lambda got:not any(e['path']==bp and e['line']==223 and any(t.endswith('.lock_run') for t in e['targets']) for e in got['edges'])),
      ('S2-remove-ORM-Node-lock',mutate(na,'.with_for_update()\n            .execution_options(populate_existing=True)','\n            .execution_options(populate_existing=True)'),
       lambda got:not any(r['path']==na and r['function'].endswith('.lock_current') and r['modes'] for r in got['records'])),
      ('S3-alias-helper',added('from .leases import lock_run as lr\n\ndef sneaky(conn,run_id):\n return lr(conn,run_id)\n'),lambda got:edge(got,'.lock_run')),
      ('S4-dotted-import',added('import inv.leases\n\ndef sneaky(conn,run_id):\n return inv.leases.lock_run(conn,run_id)\n'),lambda got:edge(got,'.lock_run')),
      ('S5-instance-wrapper',added('from .leases import LeaseStore\n\ndef sneaky(db,conn,project,run_id):\n store=LeaseStore(db)\n return store._admit_locked(conn,project,run_id)\n'),lambda got:edge(got,'.LeaseStore._admit_locked')),
      ('S6-SQL-constant',added('_SQL="SELECT node_id FROM inv.nodes WHERE node_id=%s FOR UPDATE"\n\ndef sneaky(conn,node_id):\n return conn.execute(_SQL,(node_id,)).fetchone()\n'),
       lambda got:any(r['path']==probe and r['tables']==['inv.nodes'] and r['modes']==['FOR UPDATE'] for r in got['records']) and any(f['path']==probe for f in got['functionPlans'])),
      ('S7-real-NO-KEY-mode-change',mutate('services/control-plane/src/inv/leases.py','FOR NO KEY UPDATE','FOR SHARE'),
       lambda got:any(r['path'].endswith('/leases.py') and 'FOR SHARE' in r['modes'] and 'inv.projects' in r['tables'] for r in got['records'])),
      ('S8-new-unmapped-writer',added('def sneaky(conn,node_id):\n conn.execute("UPDATE inv.nodes SET status=\'online\' WHERE node_id=%s",(node_id,))\n'),
       lambda got:any(x.startswith('UNMAPPED_WRITER:') for x in audit(got,matrix,mapping(got,matrix)))),
      ('S9-unknown-locked-table-block',added('def sneaky(conn):\n return conn.execute("SELECT * FROM inv.unknown_guard_scope FOR UPDATE")\n'),
       lambda got:any(p['path']==probe and any(x['table']=='inv.unknown_guard_scope' and x['disposition']=='UNKNOWN_LOCKED_TABLE_BLOCK' for x in p['rankedResourceLocks']) for p in got['functionPlans'])),
      ('S10-unknown-instance-explicit',added('def sneaky(unknown,conn,project,run_id):\n return unknown._admit_locked(conn,project,run_id)\n'),
       lambda got:any(e['path']==probe and e['spelling']=='unknown._admit_locked' and e['disposition'].startswith('BLOCK_THIS_ENTRY') for e in got['unknownEdges'])),
      ('S11-ORM-keyword-mode',added('def sneaky(session,Node,node_id):\n return session.get(Node,node_id,with_for_update={"read":True,"key_share":True,"nowait":True})\n'),
       lambda got:any(r['path']==probe and r['modes']==['FOR KEY SHARE NOWAIT'] for r in got['records'])),
      ('S12-unresolved-SQL-explicit-block',added('def sneaky(conn,unknown_query):\n return conn.execute(unknown_query)\n'),
       lambda got:any(r['path']==probe and r['scopeDisposition']=='UNKNOWN_SQL_SCOPE_BLOCK_THIS_ENTRY' for r in got['records']) and any(p['path']==probe and p['unresolvedDbSites'] for p in got['functionPlans'])),
    ]
    source_results=[]
    for name,src,predicate in mutations:
        started=time.monotonic();got=sc.analyze(src);okay=bool(predicate(got))
        detail={'changedSemanticProjection':okay,'seconds':round(time.monotonic()-started,2),
                'probeEdges':[e for e in got['edges'] if e['path']==probe],
                'probeRecords':[{k:r[k] for k in ('function','tables','modes','kind')} for r in got['records'] if r['path']==probe]}
        check(name,okay,detail);source_results.append(dict(case=name,**detail))
        print(json.dumps({'sourceMutation':name,'semanticDetected':okay}),flush=True)
    # PostgreSQL SQL compilation with the repository-pinned library, no engine/session.
    check('pinned-SQLAlchemy-2.0.52',sqlalchemy.__version__=='2.0.52',sqlalchemy.__version__)
    table=Table('nodes',MetaData(),Column('node_id',Integer),schema='public')
    compiled=[]
    for opts,expected in [({},'FOR UPDATE'),({'key_share':True},'FOR NO KEY UPDATE'),
          ({'read':True},'FOR SHARE'),({'read':True,'key_share':True},'FOR KEY SHARE'),
          ({'skip_locked':True},'FOR UPDATE SKIP LOCKED'),({'nowait':True},'FOR UPDATE NOWAIT'),
          ({'read':True,'key_share':True,'nowait':True},'FOR KEY SHARE NOWAIT')]:
        sql=str(select(table).with_for_update(**opts).compile(dialect=postgresql.dialect()))
        check('PostgreSQL-compile-'+expected,sql.endswith(expected),sql)
        compiled.append(dict(options=opts,SQL=sql,expectedMode=expected))
    sc.dump(E/'source-fixture-results.json',dict(level='STATIC_GIT_AST_MUTATIONS_AND_OFFLINE_SQL_COMPILATION_ONLY',
        source=sc.BASE,passed=len(RESULTS),failed=0,sourceMutationCount=len(source_results),sourceMutations=source_results,
        sqlalchemyVersion=sqlalchemy.__version__,postgreSQLCompilations=compiled,cases=RESULTS,actualDBOrPGTrace=False))
    print(json.dumps({'passed':len(RESULTS),'sourceMutations':len(source_results),'actualPG':0}))


if __name__=='__main__':main()
