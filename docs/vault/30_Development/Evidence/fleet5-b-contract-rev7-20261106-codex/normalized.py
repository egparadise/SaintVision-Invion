"""Small referenced JSONL ledgers. No duplicated transitive callsite payloads.

Consumers may stream one ledger or selected entries. The immutable 74MB Rev6
ledger is referenced by SHA, never copied or treated as a passing baseline.
"""
import hashlib,json
from pathlib import Path
E=Path(__file__).resolve().parent
KEYS=('sourceFiles','records','writers','classifiedCalls','transactionBoundaries','unknownEdges','sqlScopeIssues','functionPlans','criticalEntries','valueConstructorProofs','unknownSqlWriters')

def publish(result):
    functions=sorted({c['function'] for c in result['classifiedCalls']}|{t for c in result['classifiedCalls'] for t in c['targets']}); fids={f:i for i,f in enumerate(functions)}
    paths=sorted(x['path'] for x in result['sourceFiles']);pids={p:i for i,p in enumerate(paths)}
    reasons=sorted({c['reason'] for c in result['classifiedCalls']});rids={r:i for i,r in enumerate(reasons)}
    prior=json.loads((E.parent/'fleet5-b-contract-rev6-20261106-codex/source-procedure-lock-plans.json').read_bytes())
    named={'inv.shard_recovery.ShardRecovery.prepare'}|{p['sourceFunction'] for p in prior['plans']}|{p['function'] for p in result['functionPlans'] if p.get('criticalEntry') or p['function'] in ('saintvision.api.v1.nodes.post_heartbeat','saintvision.api.v1.nodes.enroll_node','saintvision.api.v1.storage.register_contribution')}
    manifest={'namedGrantEntries':sorted(named),'functionDictionary':functions,'pathDictionary':paths,'reasonDictionary':reasons,'source':result['source'],'format':'rev7-referenced-jsonl:1','analysis':'STATIC_ONLY',
       'producerHashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (E/n for n in ('source_analysis.py','source_semantics.py','graph_policy.py','normalized.py','rank_contract.py','plan_specs.py','writer_semantics.py','transport_inventory.py','catalog.py','io_contract.py'))},
       'ledgers':{},'modelTables':result['modelTables'],'authorityDDLDefaults':result.get('authorityDDLDefaults'),'oldRev6':{'commit':'ee97c27a5d135a4059256124290731cd2b791193','calls':47608,'unprovenBacklog':29573,'bytes':74373915,'sha256':'19944f326147bf0d83784534231de8434eab5268355fb796f3239772f8d6ae9d'},
       'grantBoundary':'Only named entry with fully resolved source closure and exact merged procedure mapping can be considered; UNSUPPORTED entries carry named ports. No whole B readiness or implementation grant from counts.',
       'actualRuntimeB':0,'typeSets':result.get('typeSets',{}),'memory':result.get('memoryMetrics',{})}
    for key in KEYS:
        file=E/(key+'.jsonl');count=0;h=hashlib.sha256();size=0
        with file.open('wb') as stream:
            for row in result.get(key,[]):
                if key=='classifiedCalls':row={**{k:v for k,v in row.items() if k in ('id','line','column','endLine','endColumn','spelling','inferredTarget','receiverType','possibleReceiverTypes','classification','blocksGrant','exactLine','resolutionComplete')},'functionRef':fids[row['function']],'pathRef':pids[row['path']],'targetRefs':[fids[f] for f in row['targets']],'reasonRef':rids[row['reason']]}
                elif key=='unknownEdges':row={'callRef':row['id'],'affectedEntryRefs':[fids[f] for f in row['affectedEntryIDs']],'blocksGrant':True,'futureWork':'resolve exact type/source or named mediated port; HOLD for affected grant','unreachableExemption':False}
                elif key=='functionPlans':
                    row={k:v for k,v in row.items() if k not in ('unknownIDs','missingPorts','concreteEntryContracts')}
                    if row['function'] not in named:
                        ids=row['remainingUnknownRefs'];row['remainingUnknownRefs']={'graphClosureOf':row['function'],'count':len(ids),'sha256':hashlib.sha256(json.dumps(sorted(ids)).encode()).hexdigest(),'resolution':'BFS exact callees + localUnknownIDs + SQL issues; no absence/exemption claim'}
                        row['closureFunctions']={'graphClosureOf':row['function']}
                        row['rankedResourceLocks']={'deriveFrom':'exact closure records/writers; no joined procedure grant for this graph node'}
                raw=(json.dumps(row,separators=(',',':'),ensure_ascii=True)+'\n').encode();stream.write(raw);h.update(raw);count+=1;size+=len(raw)
        manifest['ledgers'][key]={'file':file.name,'rows':count,'bytes':size,'sha256':h.hexdigest()}
    manifest['classificationCounts']=dict(__import__('collections').Counter(c['classification'] for c in result['classifiedCalls']))
    manifest['planCounts']=dict(__import__('collections').Counter(p['supportStatus'] for p in result['functionPlans']))
    manifest['oldBaselineAccounting']='Immutable Rev6 counts are comparison denominators only; no old UNRESOLVED call is exempt. Stable path/line/column IDs and full current census permit joins; newly resolved and still-unresolved classes are counted.'
    (E/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'normalizedBytes':sum(x['bytes'] for x in manifest['ledgers'].values()),'counts':{k:v['rows'] for k,v in manifest['ledgers'].items()},'classes':manifest['classificationCounts']}))

def rows(key):
    manifest=json.loads((E/'source-manifest.json').read_text(encoding='utf8'));item=manifest['ledgers'][key];h=hashlib.sha256();count=0
    with (E/item['file']).open('rb') as stream:
        for raw in stream:
            h.update(raw);count+=1;r=json.loads(raw)
            if key=='classifiedCalls':
                r.update(function=manifest['functionDictionary'][r.pop('functionRef')],path=manifest['pathDictionary'][r.pop('pathRef')],targets=[manifest['functionDictionary'][i] for i in r.pop('targetRefs')],reason=manifest['reasonDictionary'][r.pop('reasonRef')]);r['method']=r['spelling'].split('.')[-1]
            yield r
    assert count==item['rows'] and h.hexdigest()==item['sha256'],('ledger integrity',key)

def load():
    m=json.loads((E/'source-manifest.json').read_text(encoding='utf8'))
    # Only compact rows needed for reconciliation and per-entry locks; calls can
    # be consumed serially by review tools through rows('classifiedCalls').
    d=dict(source=m['source'],modelTables=m['modelTables'],authorityDDLDefaults=m.get('authorityDDLDefaults'),**{k:list(rows(k)) for k in ('sourceFiles','records','writers','functionPlans','criticalEntries','unknownSqlWriters')})
    for p in d['functionPlans']:p['unknownIDs']=p['remainingUnknownRefs']
    return d
