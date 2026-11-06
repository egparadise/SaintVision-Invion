"""Streaming causal/source/lock/contract integrity, static evidence only."""
import ast,hashlib,io,json,subprocess,tarfile
from collections import defaultdict,Counter
from copy import deepcopy
from pathlib import Path
from normalized import rows,load
from authority import build,invariants
from entry_locks import validate,merged,concrete_order
from catalog import build_catalog,source_bytes,source_record
from transport_inventory import inventory
E=Path(__file__).resolve().parent;R=[]
def check(name,b,detail=None):R.append({'case':name,'pass':bool(b),'detail':detail});assert b,(name,detail)
def main():
    manifest=json.loads((E/'source-manifest.json').read_text(encoding='utf8'));source=load();matrix=build()
    check('matrix-invariants',not invariants(matrix),invariants(matrix))
    for name,h in manifest['producerHashes'].items():check('producer-'+name,hashlib.sha256((E/name).read_bytes()).hexdigest()==h)
    display=manifest.get('displayPostprocessing')
    check('explicit-display-postprocessor',display and hashlib.sha256((E/display['script']).read_bytes()).hexdigest()==display['scriptSHA256'])
    mask=json.loads((E/'display-redaction-ledger.json').read_text(encoding='utf8'))
    check('display-raw-input-chain',mask['originalManifestSHA256']==display['originalManifestSHA256'] and not mask['policyOrAuthorityChange'])
    # Stream all immutable source bytes rather than loading a tar/AST aggregate.
    expected={r['path']:r['sha256'] for r in source['sourceFiles']};seen={}
    proc=subprocess.Popen(['git','archive',manifest['source'],*expected],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    with tarfile.open(fileobj=proc.stdout,mode='r|') as archive:
        for entry in archive:
            if entry.isfile():seen[entry.name]=hashlib.sha256(archive.extractfile(entry).read()).hexdigest()
    rc=proc.wait();check('all-523-source-bytes',rc==0 and seen==expected and len(seen)==523)
    plans={p['function']:p for p in source['functionPlans']};issues=defaultdict(set)
    for row in rows('unknownEdges'):
        check('unknown-is-not-waived-'+row['callRef'],row['blocksGrant'] and not row['unreachableExemption'])
    callkeys=set();classes=Counter()
    for c in rows('classifiedCalls'):
        classes[c['classification']]+=1;callkeys.add(c['id'])
        check('default-cannot-be-NONAUTH-unresolved-'+c['id'],'UNRESOLVED_EXTERNAL_BACKLOG' not in c['classification'])
        if c['blocksGrant']:issues[c['function']].add(c['id'])
    for q in rows('sqlScopeIssues'):
        check('SQL-scope-binding-'+q['id'],q['blocksGrant'] and bool(q['scope']) and bool(q['futureWork']) and q['source']==manifest['source']);issues[q['function']].add(q['id'])
    for fn,p in plans.items():
        todo=[fn];closure=set()
        while todo:
            f=todo.pop()
            if f in closure:continue
            closure.add(f);todo.extend(plans.get(f,{}).get('callees',[]))
        unknown=set().union(*(issues[f] for f in closure));refs=p['remainingUnknownRefs']
        if isinstance(refs,list):okay=set(refs)==unknown
        else:okay=refs['count']==len(unknown) and refs['sha256']==hashlib.sha256(json.dumps(sorted(unknown)).encode()).hexdigest()
        check('causal-closure-'+fn,okay)
        check('truthful-support-'+fn,p['supportStatus']==('UNSUPPORTED_NAMED_PORTS_PENDING' if unknown else 'SUPPORTED_STATIC_PLAN'))
    check('all21-critical-present',len(source['criticalEntries'])==21)
    actual_transactions=[]
    wanted={('inv.observation.NodeObservation.accept',52),('inv.observation.NodeObservation.mark_offline',139),('inv.results.ResultStore.complete',164),('inv.shard_completion.ShardCompletion.once',46)}
    for c in rows('classifiedCalls'):
        if (c['function'],c['line']) in wanted and c['spelling']=='self.db.transaction':actual_transactions.append(c)
    check('actual-four-outer-transaction-sites-retained',len(actual_transactions)==4)
    for c in actual_transactions:check('actual-owner-'+c['function'],c['targets'] or c['blocksGrant'],{'classification':c['classification'],'targets':c['targets'],'types':c['possibleReceiverTypes']})
    shard=plans['inv.shard_recovery.ShardRecovery.prepare']
    check('actual-shard-validated-to-planned-writer-reached','inv.runs.RunStore._transition' in shard['closureFunctions'])
    reconcile=json.loads((E/'writer-reconciliation.json').read_text(encoding='utf8'))
    check('current34-census-no-errors',len(reconcile['writers'])==34 and not reconcile['errors'])
    check('composition27SQL7ORM',Counter('SQL' if w['kind'].startswith('SQL') else 'ORM' for w in reconcile['writers'])=={'SQL':27,'ORM':7})
    # Actual SQL bytes, not edited result JSON: the sole SQL RULE also retains
    # tenant input and source DDL defaults when no live B traffic is admitted.
    import source_analysis as sc
    import reconcile as contract_audit
    sqlpath='services/control-plane/src/inv/migrations/0022_node_containment.sql';raw=source_bytes(sqlpath)
    for name,changed,error in (
      ('SQL-seed-wrong-tenant',raw.replace(b'VALUES(NEW.tenant_id)',b"VALUES('wrong-tenant')",1),'SQL_ROUTINE_INSERT_AUTHORITY_DRIFT'),
      ('SQL-seed-default-kill',raw.replace(b'kill_switch boolean NOT NULL DEFAULT false',b'kill_switch boolean NOT NULL DEFAULT true',1),'SQL_ROUTINE_DEFAULT_AUTHORITY_DRIFT')):
        got=sc.analyze({sqlpath:changed});errs=contract_audit.audit(got,matrix,contract_audit.mapping(got,matrix))
        check(name,any(e.startswith(error) for e in errs),{'mutatedActualGitBytes':True,'expected':error})
    locks=json.loads((E/'entry-lock-plans.json').read_text(encoding='utf8'))
    check('separate39-joins-from-source-census',locks['actualProcedureJoins']==39 and locks['sourcePlanCensus']==len(plans))
    check('prior12-upgrade-hazards-reproduced',locks['priorEntriesWithUpgrades']==12)
    for p in locks['plans']:check('strongest-preacquired-'+p['entry'],not validate(p['mergedPreacquiredLocks']))
    good,ports=merged({'rankedResourceLocks':[{'table':'inv.nodes','mode':'FOR UPDATE'}]},[{'name':'prefix','lockList':[{'table':'inv.nodes','mode':'FOR SHARE'}]}]);bad=deepcopy(good);bad[0]['mode']='FOR SHARE'
    check('same-Node-old-share-then-upgrade-RED','LATE_MODE_UPGRADE' in validate(bad))
    check('same-Node-merged-update-once-GREEN',not ports and not validate(good) and good[0]['mode']=='FOR UPDATE')
    check('total-key-mode-comparator',concrete_order('inv.nodes',[['text','node_id','node-a']],'FOR SHARE')<concrete_order('inv.nodes',[['text','node_id','node-a']],'FOR UPDATE')<concrete_order('inv.nodes',[['text','node_id','node-b']],'FOR SHARE'))
    transport=inventory();check('all19-exact-transport-callers',len(transport['callers'])==19 and not transport['coverageErrors'])
    for r in transport['callers']:
        current=source_record(r['path'],r['line']);check('caller-exact-source-'+r['path']+':'+str(r['line']),current['exactLine']==r['exactLine'] and current['fileSHA256']==r['fileSHA256'] and r['methodName'] in r['exactLine'])
    check('actual-receipts-side-effect-counterexample',transport['readOnlyException']['chosenEffect']=='SIDE_EFFECT' and len(transport['readOnlyException']['proof'])==5)
    check('13-purpose-specific-reader-predicates',len({r['purposeClass'] for r in transport['catalog']['plainReaders']})==13)
    check('plain-owner-activation-no-confirmation',matrix['procedures']['b_activate_owner_contribution']['requiresNodeConfirmation'] is False)
    wrong=deepcopy(matrix);wrong['procedures']['b_activate_owner_contribution']['requiresNodeConfirmation']=True
    check('plain-confirmation-drift-RED','PLAIN_OWNER_BEHAVIOR_CHANGED' in invariants(wrong))
    plan_text=(E/'plan_specs.py').read_text(encoding='utf8')
    check('all-plain-folder-assertions-corrected','activation still requires Node folder confirmation' not in plan_text and 'owner + not-revoked only, no Node confirmation' in plan_text)
    actual_review=json.loads((E/'prior-review-manifest.json').read_text(encoding='utf8'))
    for r in actual_review:
        raw=subprocess.check_output(['git','show',r['commit']+':'+r['path']]);check('actual-prior-review-byte-ref-'+Path(r['path']).name,hashlib.sha256(raw).hexdigest()==r['sha256'])
    summary={'level':'SCHEMA_STATIC_SYMBOLIC_ONLY','source':manifest['source'],'sourceFiles':523,'allCalls':sum(classes.values()),'classes':dict(classes),
      'sourcePlanCensus':len(plans),'actualProcedureJoins':39,'criticalEntries':len(source['criticalEntries']),
      'criticalStatus':dict(Counter(p['supportStatus'] for p in source['criticalEntries'])),
      'currentAuthorityWriters':34,'symbolicCases':json.loads((E/'fixture-results.json').read_text(encoding='utf8'))['count'],
      'boundedSourceCases':json.loads((E/'source-fixture-results.json').read_text(encoding='utf8'))['passed'],
      'ownerPriorClosedRerunCases':8,'packetAssertions':len(R),'streamedSourceLedgerBytes':sum(v['bytes'] for v in manifest['ledgers'].values()),
      'displayMaskedRows':display['changedRows'],'displayRawSourceBindingsPreserved':True,
      'ownerFullAssemblerMemory':manifest['memory'],'boundedSubsetMemory':json.loads((E/'source-fixture-results.json').read_text(encoding='utf8'))['memory'],
      'allRealBindings':None,'A1_A16':'PENDING','actualNewGoCryptoPGEngineCrashConcurrencyEquipment':0,
      'independentWholeRev7Review':'PENDING via Root','implementationGrant':'NONE','obsidianApply':False,
      'grantBoundary':'Critical source closures with named unresolved ports are UNSUPPORTED; no whole B readiness/source grant, partial freeze or runtime denial inferred from static counts.'}
    (E/'packet-summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    # Large per-call PASS lists add no review value; retain coverage counters and
    # every named global/negative check. Failures raise before summary is written.
    (E/'packet-check-results.json').write_text(json.dumps({'assertions':len(R),'failed':0,'namedChecks':[r for r in R if not any(r['case'].startswith(p) for p in ('unknown-is-not-waived-','default-cannot-be-NONAUTH-','causal-closure-','truthful-support-','SQL-scope-binding-'))]},indent=2)+'\n',encoding='utf8')
    print(json.dumps(summary))
if __name__=='__main__':main()
