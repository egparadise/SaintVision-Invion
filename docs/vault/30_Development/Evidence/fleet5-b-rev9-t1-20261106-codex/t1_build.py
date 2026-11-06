"""Frozen-source T1/mark_offline sidecar. Never a runtime/registration grant."""
import ast,hashlib,json,subprocess
from pathlib import Path
import bounded_analysis as a
import analysis_rules as r
import t1_provenance as t
E=Path(__file__).resolve().parent;R8=E.parent/'fleet5-b-rev8-revoke-portcut-20261106-codex'
TARGET='inv.observation.NodeObservation.mark_offline'
FUNCTIONS={TARGET,'inv.db.Database.transaction','inv.db.record_placement_metric'}
def main():
    core=t.read_batch([t.CP+n for n in t.CORE]+['tools/remote_workspace_entry.py'])
    ctors=t.read_batch(t.MAIN_CTOR_PATHS)
    all_paths=set(core)|set(ctors);assert len(all_paths)<=10
    owner,error=t.provenance(core,ctors);assert not error,error
    phase,error=t.context_phase(core[t.CP+'db.py']);assert not error,error
    errors=core[t.CP+'errors.py'];db=core[t.CP+'db.py']
    assert r.error_initializer(errors,'DomainError') and r.constructor_binding(db)
    calls=[];ctor_census=[]
    for c in a.rows('classifiedCalls'):
        if c['function'] in FUNCTIONS:calls.append(c)
        targets=[a.M['functionDictionary'][i] for i in c['targetRefs']]
        if any(x in ('inv.db.Database.__init__','inv.db.BoundDatabase.__init__','inv.db._ObservedConnection.__init__','inv.observation.NodeObservation.__init__','inv.workspace_api.RestrictedWorkspaceRuntime.__init__') for x in targets):
            ctor_census.append({'callRef':c['id'],'source':{'path':c['path'],'function':c['function'],'span':[c['line'],c['column'],c['endLine'],c['endColumn']]},'resolvedTargets':targets,'classification':c['classification'],'scope':'PRODUCTION_SOURCE_CENSUS_NOT_A_GRANT'})
    records=[x for x in a.rows('records') if x['function'] in FUNCTIONS]
    old_plan=next(x for x in a.rows('functionPlans') if x['function']==TARGET)
    edges=[]
    for c in calls:
        if not c['blocksGrant']:continue
        source=core[c['path']];node=a.node_at(source,c);proof=None;pending=None
        if isinstance(node.func,ast.Attribute) and node.func.attr in ('fetchone','fetchall'):
            result=r.connection_result_explain(source,node,[x for x in records if x['path']==c['path']],[x for x in calls if x['path']==c['path']],db,owner)
            assert result['proof'],(c['id'],result['reason']);rule='A1c';proof=result['proof']
        elif c['spelling']=='DomainError':
            rule='A2_HARDENED';proof={'constructor':'inv.errors.DomainError','constructorFileSHA256':r.sha(errors),'callerBinding':'exact .errors import, all Store/import/alias/class mutations refused','bodyContract':'exact dataclass/Exception binding; no custom keywords/init/post_init/field effect'}
        elif '_statement_phase.' in c['spelling'] or c['spelling']=='phase.get':rule='A3';proof=phase
        elif c['spelling']=='changed.append':
            rule='A5_LOCAL';proof,error=t.local_list(source,node);assert not error,error
        elif c['function']=='inv.db.record_placement_metric' and c['spelling']=='getattr':
            rule='A8_T1_ATTRIBUTE';proof={'receiver':'Database self from transaction -> record_placement_metric(self,metric)','constructorFieldProvenance':owner['productionDatabaseConstructors'],'attribute':ast.literal_eval(node.args[1]),'scope':'Exact optional known field; not a generic getattr exemption','value':'placement_metric_sink source default None; placement_short_commit typed bool, current setting/log handlers runtime pending'}
        elif c['spelling']=='psycopg.connect':rule='NAMED_PORT:P-DBROLE';pending='Actual credential/installed non-superuser/non-owner/no-RLS-bypass role/PG transaction proof NOT_RUN'
        elif c['spelling'] in ('database.placement_metric_sink','_placement_logger.info'):rule='NAMED_PORT:T1-OBSERVABILITY';pending='Exact existing optional sink/logging implementation. In-process/nonblocking/no-network/exception-contained/no-authority required; installed logging handlers/config NOT_PROVEN'
        else:raise AssertionError(('unclassified target edge',c['id'],c['spelling']))
        proven_type=owner['receiverUnion']['receiverUnion'] if rule=='A1c' else ['inv.errors.DomainError'] if rule=='A2_HARDENED' else ['contextvars.ContextVar phase/token; metric dict'] if rule=='A3' else ['builtin list'] if rule=='A5_LOCAL' else ['inv.db.Database'] if rule=='A8_T1_ATTRIBUTE' else ['exact named runtime interface; installed binding unproven']
        edges.append({'callRef':c['id'],'rule':rule,'source':t.witness(c['path'],source,node,function=c['function']),'receiver':{'expression':c['spelling'],'oldInferredType':c['receiverType'],'provenUnion':proven_type},
          'producerRecord':proof.get('producerSanity',{}).get('producerRecord') if proof else None,'proof':proof,'pendingRuntimeContract':pending,
          'blocksGrant':bool(pending),'sharedOwner':'inv.db.Database.transaction' if c['function']!=TARGET else None,'closedOnlyForEntry':TARGET if c['function']==TARGET else None,'closureScope':'SOURCE_ANALYSIS_ONLY_NO_RUNTIME_GRANT'})
    assert {x['callRef'] for x in edges}==set(old_plan['remainingUnknownRefs'])
    previous=json.loads((R8/'critical-edge-categories.json').read_bytes())
    txids={c['id'] for c in calls if c['function']=='inv.db.Database.transaction' and c['blocksGrant']}
    entryset=sorted({e for row in previous['edges'] if row['callRef'] in txids for e in row['affectedEntryRefs']})
    assert len(entryset)==12
    resources=[{'subset':'T1_CORE_AND_ROOT_CONSTRUCTORS','files':[{'path':p,'bytes':len(s.encode()),'sha256':r.sha(s)} for p,s in {**core,**ctors}.items()],'fileCount':len(all_paths),'sourceBytes':sum(len(s.encode()) for s in {**core,**ctors}.values())}]
    # Release source buffers before the separate, non-target constructor census.
    del core,ctors,source,db,errors
    extra=t.read_batch(t.EXTRA_CTOR_PATHS);extra_rows,error=t.database_constructors(extra);assert not error,error
    owner['productionDatabaseConstructors']+=extra_rows
    resources.append({'subset':'REMAINING_SOURCE_CONSTRUCTOR_CENSUS_ONLY','files':[{'path':p,'bytes':len(s.encode()),'sha256':r.sha(s)} for p,s in extra.items()],'fileCount':len(extra),'sourceBytes':sum(len(s.encode()) for s in extra.values())})
    expected_db={x['source']['path'] for x in ctor_census if x['resolvedTargets']==['inv.db.Database.__init__']}
    assert expected_db=={x['path'] for x in owner['productionDatabaseConstructors']} and len(expected_db)==7
    # Source inventory grep only, no whole-program assembler or application import.
    grep=['git','grep','-n','-E',r'^class .*\((.*\.)?(Database|BoundDatabase|_ObservedConnection)[,)]',a.SOURCE,'--','services/control-plane/src','tools']
    sub=subprocess.run(grep,cwd=a.ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);assert sub.returncode==1
    harness=['git','grep','-n','-E',r'(_GetDatabase\(_Database\)|RestrictedWorkspaceRuntime\(object\(\))',a.SOURCE,'--','tests']
    h=subprocess.run(harness,cwd=a.ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);assert h.returncode==0
    a.write('t1-mark-offline-closure.json',{'source':a.SOURCE,'entry':TARGET,'status':'SOURCE_STATIC_CLOSED_RUNTIME_PENDING','notGrantable':True,'oldPlanReference':{'ledger':a.M['ledgers']['functionPlans'],'entry':TARGET,'unknownIDs':old_plan['remainingUnknownRefs']},'edges':edges,
      'analysisEdgesClosed':sum(not x['blocksGrant'] for x in edges),'namedRuntimeEdgesPending':sum(x['blocksGrant'] for x in edges),'sharedOwnerReferencedCriticalEntries':entryset,'entryStatusUpgrades':0,
      'narrowA8Proof':owner,'productionConstructorCensus':ctor_census,'nonProductionHarness':{'scope':'HARNESS_ONLY_PROVENANCE; retained, never runtime type evidence','command':harness,'exit':h.returncode,'exactSourceReferences':h.stdout.decode().splitlines()},
      'noProductionSubclass':{'command':grep,'exit':sub.returncode,'outputSHA256':hashlib.sha256(sub.stdout).hexdigest()},'sourceSubsets':resources,'maximumSimultaneousSelectedFiles':10,'sourceBudgetBytes':2097152,'OSMemoryLimitEnforced':False,
      'runtimePending':['P-DBROLE installed roles/credentials/RLS/no schema owner/no superuser/no bypass','READ COMMITTED/tenant SET LOCAL/timeouts actual PG','two-session Node FOR UPDATE vs heartbeat lock traces','clock_timestamp heartbeat cutoff semantics','logging handlers/observability configuration','B purpose roles/current auth/cutover'],
      'A7':'DEFERRED_NOT_NEEDED_ON_THIS_GRAPH','actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING','fullAssembler':'NOT_RUN'})
    print(json.dumps({'sourceEdges':len(edges),'closedAnalysis':sum(not x['blocksGrant'] for x in edges),'pendingNamedRuntime':sum(x['blocksGrant'] for x in edges),'sharedEntrySet':len(entryset),'productionDatabaseConstructors':len(expected_db),'maximumSelectedFiles':10}))
if __name__=='__main__':main()
