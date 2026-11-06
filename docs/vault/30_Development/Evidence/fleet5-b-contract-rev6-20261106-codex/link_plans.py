"""Join actual source reader/writer plans to exact proposed procedure lock lists."""
import json
from pathlib import Path
from collections import defaultdict
from authority import build
from catalog import build_catalog
from rank_contract import CATALOG
from reconcile import mapping,audit
from source_analysis import dump

E=Path(__file__).resolve().parent


def main():
    source=json.loads((E/'source-analysis.json').read_bytes());matrix=build();mapped=mapping(source,matrix)
    assert not audit(source,matrix,mapped)
    catalog=build_catalog();refs=defaultdict(set)
    for w in mapped:refs[w['function']].update(w['replacementProcedures'])
    for reader in catalog['plainReaders']:
        candidates=[p['function'] for p in source['functionPlans'] if p['path']==reader['path'] and p['function'].endswith('.'+reader['function'])]
        if not candidates:
            # Pure scheduler has no DB row locks of its own. Its fixed producer
            # snapshot and final admission are explicit, never a fabricated SQL site.
            candidates=['inv.'+Path(reader['path']).stem+'.'+reader['function']]
        for fn in candidates:refs[fn].add(reader['replacement'])
    plans={p['function']:p for p in source['functionPlans']};rows=[]
    for fn,procedures in sorted(refs.items()):
        p=plans.get(fn)
        rows.append(dict(sourceFunction=fn,sourcePlan=p,proposedProcedures=[dict(name=name,lockList=matrix['procedures'][name]['lockList'],
            transitionPredicate=matrix['procedures'][name]['transitionPredicate']) for name in sorted(procedures)],
            status=p['supportStatus'] if p else 'PURE_SCHEDULER_TYPED_SNAPSHOT_PRODUCER_AND_FINAL_ADMISSION_BINDING',
            normativeLocks='per-procedure numeric lists, never original lexical order or coarse legacy English prefix',
            scope='full persisted Node/lineage/operation/resource set from actual query sites; all earlier-rank discovery before locks; changed scope abort/replan, no effects'))
    dump(E/'source-procedure-lock-plans.json',dict(source=source['source'],canonicalRanks=CATALOG,plans=rows,
        newBReaderProcedures=[dict(**r,lockList=matrix['procedures'][r['replacement']]['lockList']) for r in catalog['newBReaders']],
        absentRowPredicate='every issuer/publication/revoke locks SAME persistent authority+lineage anchors/version BEFORE child/tombstone rows; no unlocked no-tombstone phantom'))
    dump(E/'authority-matrix.json',matrix);dump(E/'reader-io-catalog.json',catalog)
    print(json.dumps({'sourceProcedurePlans':len(rows),'readers':len(catalog['plainReaders']),'ioKinds':len(catalog['ioKinds']),'canonicalTables':len(CATALOG)}))


if __name__=='__main__':main()
