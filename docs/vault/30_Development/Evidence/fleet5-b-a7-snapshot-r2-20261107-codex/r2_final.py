"""Serial bounded fix-only commands, canonical CHECK only, no broad replay."""
import json,sys
from pathlib import Path
from a7_record import E,R,run
STATE=Path('D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json')
def main():
    phase,attempt=sys.argv[1:3];rows=[]
    if phase=='red':rows.append(run(f'red-{attempt}',[str(E/'r2_tests.py'),'--exact-only'],expected=1))
    elif phase=='proof':
        for i,name in enumerate(('r2_tests.py','a7_build.py','r2_verify.py'),1):rows.append(run(f'proof-{attempt}-{i}',[str(E/name)]))
    elif phase=='docs':
        jobs=[['tools/check_docs.py'],['tools/check_ontology.py'],['tools/sync_obsidian.py','--check','--state',str(STATE),'--conflicts-out',str(E/f'docs-{attempt}-sync-conflicts.json')],['tools/check_contract_bindings.py'],['tools/check_frontend_integrity.py'],['tools/check_doc_single_source.py','--ratchet'],['tools/check_response_freshness.py'],['tools/check_doc_path_citations.py','--ratchet','--base-ref','1550453d1f072a87fd9a7baa53d4fe4ce8a98d5d']]
        for i,args in enumerate(jobs,1):rows.append(run(f'docs-{attempt}-{i}',args,state=STATE if 'tools/sync_obsidian.py' in args else None))
    elif phase=='check':rows.append(run(f'canonical-{attempt}',[str(R/'tools/sync_obsidian.py'),'--check','--state',str(STATE),'--conflicts-out',str(E/f'canonical-{attempt}-conflicts.json')],state=STATE))
    else:raise ValueError(phase)
    (E/f'{phase}-{attempt}.json').write_bytes((json.dumps({'phase':phase,'commands':rows,'allExpectedExits':all(r['exit']==r['expectedExit'] for r in rows)},indent=2)+'\n').encode())
if __name__=='__main__':main()
