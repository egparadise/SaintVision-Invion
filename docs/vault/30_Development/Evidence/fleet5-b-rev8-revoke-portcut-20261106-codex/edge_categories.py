"""Categorize critical unknowns without changing parent graph/entry ledgers.

Category is a proof obligation, never an allowlist. Only the three proven pilot
edges close. Reviewer 646/757 taxonomy is retained as triage, not proof.
"""
import collections,json
import bounded_analysis as a
E=a.E
RULES={
 'A1':{'contract':'Already resolved DB execute -> recorded cursor result, exact AST producer span, cursor factory/import/receiver provenance. Preserve read/control flow.','implemented':'PILOT_ONLY','negative':'mystery().execute/foreign cursor/rebound cursor BLOCK'},
 'A2':{'contract':'Exact DomainError/InvError Exception dataclass/base/init/post_init/category_of/ErrorCategory/_STATUS/_RETRYABLE/Exception.__init__ body closure; no Exception-wide exemption.','implemented':'SELECTED_SOURCE_PROBES_ONLY','negative':'Constructor DB/postinit IO BLOCK'},
 'A3':{'contract':'Exact module-proven ContextVar get/set/reset; retain transaction phase/yield/commit/rollback/control flow relation. Not a generic memory provider.','implemented':False,'negative':'Foreign/shadowed context object or phase relation change BLOCK'},
 'A4':{'contract':'Exact import/type public Jsonb/jsonschema/hash/crypto PUBLIC parse/IP/URL/PurePosixPath/nullcontext/deepcopy summaries. Package literal files(inv) only readonly owned resource under closed parent.','implemented':False,'negative':'Private signing/randomness/system roots/network/arbitrary paths keep actual AUTH/IO; no crypto/net blanket pure'},
 'A5':{'contract':'Proven builtin receiver methods only, with lexical shadowing/alias checks. datetime.now/time/perf_counter are actual clock sources, not pure conversion.','implemented':False,'negative':'User receiver or actual clock source cannot inherit value conversion'},
 'A6':{'contract':'Typed Session/model instance provenance; per-occurrence read/write/lock modes, builders and UOW. delete known instance -> DELETE, merge -> UPSERT.','implemented':'BOUNDED_UOW_DELETE_MERGE_ONLY','negative':'W23/W23b loaded B model becomes unmapped writer census failure; unknown instance/model/Session DYNAMIC_BLOCK'},
 'A7':{'contract':'Prove exact tools sys.path convention, from lan_pilot import runtime -> tools.lan_pilot.runtime literal Database constructor at four actual import call sites.','implemented':False,'negative':'runtime replaced with object() BLOCK; imports never accepted by short name alone'},
 'A8':{'contract':'Interprocedural self.db constructor argument propagation across ALL production wiring; exact Database/BoundDatabase implementation types only. Keep nonproduction harness object doubles separate with provenance and counts.','implemented':False,'negative':'Unknown production receiver or Database subclass transaction override BLOCK; no harness evidence dropped'}}
def choose(c):
    fn=c.get('function','');sp=c.get('spelling','');target=c.get('inferredTarget','');receiver=c.get('receiverType') or ''
    # Analysis obligations remain analysis even inside the transaction owner.
    if target in ('inv.errors.DomainError','saintvision.errors.InvError'):return 'ANALYSIS_RULE:A2'
    if fn in ('saintvision.services.settings._apply_to_kernel','saintvision.services.settings.require_global_administrator') and any(x in sp for x in ('public.apply_capability_offer','public.business_admin_allowed')):return 'NAMED_PORT:P-DBFUNC'
    if any(x in sp for x in ('.fetchone','.fetchall','.scalar_one','.scalar(')):return 'ANALYSIS_RULE:A1'
    if '_statement_phase.' in sp or fn=='inv.db.Database.transaction' and sp=='phase.get':return 'ANALYSIS_RULE:A3'
    if fn.startswith(('inv.db.Database.transaction','inv.db.BoundDatabase.transaction')):
        return 'NAMED_PORT:P-DBROLE' if 'psycopg.connect' in sp else 'NAMED_PORT:T1'
    if fn.startswith('inv.node_transport.NodeTLSClient.'):
        return 'NAMED_PORT:T2'
    if fn.startswith('inv.buildkit_transport._protected_json') or fn=='inv.storage.verify_content':return 'NAMED_PORT:T3'
    if sp=='getattr' or 'getattr(' in sp:return 'NAMED_PORT:P-GETATTR'
    if fn.startswith('saintvision.api.v1.settings.') and sp in ('Depends','Header','router.put'):return 'NAMED_PORT:P-API-DI'
    if fn.startswith(('inv.build_execution.','inv.buildkit_transport.')) and any(x in sp for x in ('_clock','_now','_request_id_factory','_runner.run')):return 'NAMED_PORT:P-INJECT-BUILD'
    if any(x in target for x in ('jsonschema','psycopg.types.json.Jsonb','importlib.resources','cryptography','ipaddress','urllib.parse','hashlib','unicodedata','PurePosixPath','nullcontext','deepcopy')):return 'ANALYSIS_RULE:A4'
    if 'runtime' in target and fn.startswith('tools.'):return 'ANALYSIS_RULE:A7'
    if sp=='self.db.transaction':return 'ANALYSIS_RULE:A8'
    if 'Session' in receiver or sp.startswith('session.'):return 'ANALYSIS_RULE:A6'
    if receiver in ('builtin:str','builtin:dict','builtin:list','builtin:set'):return 'ANALYSIS_RULE:A5'
    return 'DYNAMIC_BLOCK'
def main():
    critical=list(a.rows('criticalEntries'));wanted={x for r in critical for x in r['unknownIDs']}
    calls={}
    for c in a.rows('classifiedCalls'):
        if c['id'] in wanted:calls[c['id']]=c
    pilot=json.loads((E/'pilot-closure.json').read_bytes());closed={r['callRef']:r for r in pilot['closedAnalysisEdges']}
    sqlissues={r['id']:r for r in a.rows('sqlScopeIssues') if r['id'] in wanted}
    byentry={r['function']:r for r in critical};edges=[];planrows=[]
    # Referenced parent rows are immutable, even if a category suggests a future
    # rule. No other entry receives a support-status upgrade.
    for callid in sorted(wanted):
        refs=[r['function'] for r in critical if callid in r['unknownIDs']]
        c=calls.get(callid)
        if callid in closed:
            row={**closed[callid],'affectedEntryRefs':refs};row['closedOnlyForEntry']=a.PILOT
        elif c:
            cat=choose(c);row={'callRef':callid,'affectedEntryRefs':refs,'category':cat,
              'source':{'path':c['path'],'function':c['function'],'span':[c['line'],c['column'],c['endLine'],c['endColumn']],'parentLedger':'classifiedCalls','parentLedgerSHA256':a.M['ledgers']['classifiedCalls']['sha256']},
              'type':c['inferredTarget'],'receiver':{'expression':c['spelling'],'inferredType':c['receiverType'],'possibleTypes':c['possibleReceiverTypes']},
              'binding':{'actual':None,'requiredExactTarget':c['inferredTarget'],'requiredReceiverProvenance':c['receiverType'],'categoryIsProof':False},
              'proof':{'status':'NOT_APPLIED_TO_NONPILOT','originalReason':c['reason'],'ruleContract':cat,'noAllowlist':True},
              'futureWork':{'callee':c['inferredTarget'],'sourceFunction':c['function'],'span':[c['line'],c['column'],c['endLine'],c['endColumn']],
                'action':'Prove exact selected import/producer/type/effect closure under '+cat+'; unknown dynamic receiver stays blocked; do not register a production port from a taxonomy label'},
              'blocksGrant':True,'originalEntryStatusRetained':True}
        elif callid in sqlissues:
            issue=sqlissues[callid]
            row={'callRef':callid,'affectedEntryRefs':refs,'category':'NAMED_PORT:P-SQLSCOPE' if issue['function']=='saintvision.api.lock_wait.bound_lock_wait' else 'DYNAMIC_BLOCK',
              'source':{k:issue[k] for k in ('path','function','line','fileSHA256','exactLine')},'type':'RECORDED_SESSION_SQL_SCOPE','receiver':{'expression':'session.execute','inferredType':'sqlalchemy.orm.Session; owning transaction proof pending'},
              'binding':{'actual':None,'requiredOwner':'existing tenant-scoped Session','formatter':'validate_lock_timeout(timeout_ms) -> fixed SET LOCAL lock_timeout'},
              'proof':{'status':'UNRESOLVED_SQL_SCOPE_RETAINED','parentLedger':'sqlScopeIssues','parentLedgerSHA256':a.M['ledgers']['sqlScopeIssues']['sha256'],'originalReason':issue['reason']},
              'futureWork':{'exactUnknownRef':callid,'sourceFunction':issue['function'],'line':issue['line'],'action':'Prove bounded validated-integer SET LOCAL formatter and existing transaction/tenant scope; bind P-SQLSCOPE before affected grant'},'blocksGrant':True}
        else:
            # SQL-scope identifiers are not fictional Python receiver calls.
            row={'callRef':callid,'affectedEntryRefs':refs,'category':'NAMED_PORT:P-SQLSCOPE' if any('lock_wait' in x for x in refs) else 'DYNAMIC_BLOCK',
              'source':{'parentLedger':'criticalEntries','parentLedgerSHA256':a.M['ledgers']['criticalEntries']['sha256'],'exactUnknownRef':callid},'type':'SQL_OR_UNRESOLVED_SCOPE','receiver':None,
              'binding':None,'proof':'No Python producer identified; no inferred exemption','futureWork':{'exactUnknownRef':callid,'affectedEntryRefs':refs,'action':'Resolve exact SQL/body/scope or receiver dependency before grant'},'blocksGrant':True}
        edges.append(row)
    for r in critical:
        planrows.append({'entry':r['function'],'parentStatus':r['supportStatus'],'parentMissingPorts':r['missingPorts'],'unknownRefs':r['unknownIDs'],
          'rev8View':'SOURCE_TO_PROPOSED_PROCEDURE_STATIC_CLOSED_RUNTIME_PENDING' if r['function']==a.PILOT else 'UNCHANGED_PARENT_REFERENCE',
          'runtimeGrant':False,'parentCanonicalRowSHA256':a.sha(json.dumps(r,sort_keys=True,separators=(',',':')).encode())})
    parentplans=json.loads((a.R7/'entry-lock-plans.json').read_bytes())['plans']
    contracts=json.loads((E/'pending-interface-contracts.json').read_bytes())
    transport=json.loads((a.R7/'transport-inventory.json').read_bytes())
    io_links=[{'category':'IO_CATALOG_LINK:'+v['kind'],'effectClass':v['effectClass'],'source':{k:r[k] for k in ('path','line','function','fileSHA256')},'blocksGrant':True,'binding':None,'proof':'Existing caller source binding only; real T2 implementation enforcement NOT_RUN'} for r in transport['callers'] for v in r['variants']]
    for contract in contracts['contracts']:
        if contract['id']=='P-GETATTR':
            contract['wiring']=[{'callRef':r['callRef'],**r['source'],'receiver':r['receiver'],'inferredTarget':r['type']} for r in edges if r['category']=='NAMED_PORT:P-GETATTR']
        if contract['id']=='P-LOCKRANK':
            tables=set(contract['input']);contract['wiring']=[{k:r[k] for k in ('path','function','line','table','verb','expressionSHA256') if k in r} for r in a.rows('writers') if r['table'] in tables]
    (E/'pending-interface-contracts.json').write_bytes((json.dumps(contracts,indent=2)+'\n').encode())
    result={'source':a.SOURCE,'scope':'ALL critical entry unknown references; noncritical graph remains immutable fail-closed by reference, not reclassified or waived',
      'closedCategoryGrammar':['ANALYSIS_RULE:A1..A8','IO_CATALOG_LINK:<exact existing kind>','NAMED_PORT:<declared id>','DYNAMIC_BLOCK'],
      'triageIsNotProof':True,'ruleContracts':RULES,'criticalEntries':planrows,'edges':edges,'existingCallerIOCatalogLinks':io_links,'criticalEntryCount':len(critical),
      'missingPortOccurrences':sum(len(x['missingPorts']) for x in critical),'distinctReferencedUnknowns':len(wanted),'categoryCounts':dict(collections.Counter(x['category'] for x in edges)),
      'nonPilotEntryStatusChanges':0,'sourceLockPlanCounts':{'all':len(parentplans),'withProcedureRefs':sum(bool(p['procedureRefs']) for p in parentplans),'withoutProcedureRefs':sum(not p['procedureRefs'] for p in parentplans)},
      'remainingNoncriticalUnknownPolicy':'DYNAMIC_BLOCK on original exact callRef/source/type/receiver when queried; no support change and no exemption; immutable unknownEdges and full 47608 accounting preserved',
      'actualRuntimeB':0,'A1_A16':'PENDING','realBindings':None}
    a.write('critical-edge-categories.json',result)
    print(json.dumps({'criticalEntries':len(critical),'referencedUnknowns':len(wanted),'missingPortOccurrences':result['missingPortOccurrences'],'categories':result['categoryCounts'],'sourceLockPlanCounts':result['sourceLockPlanCounts']}))
if __name__=='__main__':main()
