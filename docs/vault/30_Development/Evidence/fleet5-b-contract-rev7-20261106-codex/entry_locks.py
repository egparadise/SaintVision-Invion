"""One merged acquisition plan per entry, not prefix plus unchanged body.

Static rewrite obligation only. PostgreSQL two-session traces are NOT RUN.
"""
import json
from collections import defaultdict
from pathlib import Path
from rank_contract import CATALOG,RANK
from authority import build
from catalog import build_catalog
from normalized import load
from reconcile import mapping,audit
E=Path(__file__).resolve().parent
STRENGTH={'FOR KEY SHARE':1,'FOR SHARE':2,'FOR NO KEY UPDATE':3,'FOR UPDATE':4,'TRANSACTION_ADVISORY':4}

def concrete_order(table,typed_primary_key,mode):
    """Same proposed byte comparator for every participant, before acquisition.

    Fixed schema supplies ordered [type-tag,field-name,canonical-value] triples.
    Strongest mode is consolidated before this comparator; duplicate row identity
    is forbidden. Mode is the final deterministic serialization tiebreak only.
    """
    from model import canonical
    if table not in CATALOG or mode not in STRENGTH:raise ValueError('unknown lock class')
    return RANK[table],table.encode('ascii'),canonical(typed_primary_key),STRENGTH[mode]

def base_mode(mode):
    return next((m for m in ('FOR NO KEY UPDATE','FOR KEY SHARE','FOR UPDATE','FOR SHARE','TRANSACTION_ADVISORY') if mode.startswith(m)),None)

def merged(source,procedures):
    requirements=defaultdict(list);errors=[]
    for proc in procedures:
        for r in proc['lockList']:requirements[r['table']].append(('procedure:'+proc['name'],r['mode']))
    for r in source.get('rankedResourceLocks',[]):requirements[r['table']].append(('source:explicit/transitive',r['mode']))
    for r in source.get('writerLocks',[]):requirements[r['table']].append(('source:DML',r['mode']))
    out=[]
    for table,uses in requirements.items():
        modes=[base_mode(mode) for origin,mode in uses]
        if table not in CATALOG or any(mode is None for mode in modes):errors.append({'table':table,'uses':uses,'reason':'UNKNOWN_LOCK_OR_SESSION_ADVISORY_PORT'});continue
        mode=max(modes,key=lambda m:STRENGTH[m])
        out.append({'table':table,'rank':RANK[table],'rowKeySet':'UNION of complete DB-discovered primary keys from all procedure/source/transitive requirements; '+CATALOG[table]['key'],
          'mode':mode,'requirements':[{'origin':o,'mode':m} for o,m in uses],
          'acquire':'ONCE BEFORE ANY BODY EFFECT, canonical(rank,qualifiedTable,canonicalPKBytes)',
          'wrappedBody':'REWRITE original locks to assert-held/no reacquisition; no SHARE->UPDATE upgrade after prefix'})
    out.sort(key=lambda r:(r['rank'],r['table']))
    return out,errors

def validate(rows):
    errors=[];seen=set()
    for row in rows:
        key=(row['rank'],row['table'])
        if key in seen:errors.append('DUPLICATE_LOCK_CLASS')
        seen.add(key)
        if row['rank']!=RANK[row['table']]:errors.append('RANK_MISMATCH')
        for req in row['requirements']:
            mode=base_mode(req['mode'])
            if mode is None or STRENGTH[mode]>STRENGTH[row['mode']]:errors.append('LATE_MODE_UPGRADE')
    if rows!=sorted(rows,key=lambda r:(r['rank'],r['table'])):errors.append('ORDER_INVERSION')
    return errors

def main():
    source=load();matrix=build();mapped=mapping(source,matrix);errors=audit(source,matrix,mapped)
    assert not errors,errors
    plans={p['function']:p for p in source['functionPlans']};refs=defaultdict(set)
    for w in mapped:refs[w['function']].update(w['replacementProcedures'])
    for reader in build_catalog()['plainReaders']:
        fn='inv.'+Path(reader['path']).stem+'.'+reader['function'];refs[fn].add(reader['replacement'])
    rows=[]
    for fn,names in sorted(refs.items()):
        plan=plans.get(fn,{'function':fn,'rankedResourceLocks':[],'closureFunctions':[fn],'supportStatus':'PURE_SCHEDULER_CONSUMER_REQUIRES_TYPED_PRODUCER_AND_SELECTED_ADMISSION','remainingUnknownRefs':[]})
        plan=dict(plan);closure=set(plan.get('closureFunctions',[fn]));plan['writerLocks']=[{'table':w['table'],'mode':'FOR UPDATE'} for w in source['writers'] if w['function'] in closure]
        procs=[{'name':name,**matrix['procedures'][name]} for name in sorted(names)]
        locks,blocks=merged(plan,procs);assert not validate(locks),fn
        rows.append({'entry':fn,'sourcePlanRef':fn,'sourceClosureRefs':plan.get('closureFunctions',[fn]),
          'procedureRefs':sorted(names),'mergedPreacquiredLocks':locks,'lockPorts':blocks,
          'sourceUnknownRefs':plan.get('remainingUnknownRefs',[]),
          'status':'UNSUPPORTED_NAMED_PORTS_PENDING' if blocks or plan.get('remainingUnknownRefs') else plan['supportStatus'],
          'rewriteRequired':True,'originalBodyMayRunUnchanged':False,'actualPGTwoSessionTrace':'NOT_RUN'})
    prior=json.loads((E.parent/'fleet5-b-contract-rev6-20261106-codex/source-procedure-lock-plans.json').read_bytes())
    old=[]
    for entry in prior['plans']:
        p=entry.get('sourcePlan') or {}
        for proc in entry['proposedProcedures']:
            pm={r['table']:base_mode(r['mode']) for r in proc['lockList']}
            for r in p.get('rankedResourceLocks',[]):
                m=base_mode(r['mode']);before=pm.get(r['table'])
                if m and before and STRENGTH[m]>STRENGTH[before]:old.append({'entry':entry['sourceFunction'],'table':r['table'],'prefix':before,'body':m})
    result={'source':source['source'],'sourcePlanCensus':len(source['functionPlans']),'actualProcedureJoins':len(rows),
       'priorActualProcedureJoins':len(prior['plans']),'priorEntriesWithUpgrades':len({x['entry'] for x in old}),'priorUpgradeProof':old,
       'comparator':'(numeric rank, qualified table UTF8 bytes, full canonical primary-key bytes); rank ties deliberately retained; strongest required mode consolidated before sorting/acquiring. All participants use identical comparator.',
       'sameNodeStaticCase':'Two SHARE holders each upgrade to UPDATE can form a cycle; merged UPDATE once makes second wait before obtaining conflicting locks. Static scheduling example, NOT actual PG proof.',
       'plans':rows,'phantomRule':'persistent authority + lineage anchors before child/tombstone; same anchor and version for issuer/revoke/publication; full discovery, late earlier-rank abort/replan',
       'actualPGTwoSessionTrace':'NOT_RUN; mandatory future pinned disposable PG CI'}
    (E/'entry-lock-plans.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:result[k] for k in ('sourcePlanCensus','actualProcedureJoins','priorActualProcedureJoins','priorEntriesWithUpgrades')}))

if __name__=='__main__':main()
