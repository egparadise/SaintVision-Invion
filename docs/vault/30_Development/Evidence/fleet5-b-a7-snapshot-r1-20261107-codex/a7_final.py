"""Final serial commands. No old model/assembler/recovery suites are invoked."""
import json,sys
from pathlib import Path
from a7_record import E,R,run
STATE=Path('D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json')

def main():
    phase=sys.argv[1];attempt=sys.argv[2];rows=[]
    if phase=='proof':
        for i,name in enumerate(('a7_tests.py','a7_build.py','a7_verify.py'),1):rows.append(run(f'proof-{attempt}-{i}',[str(E/name)]))
    elif phase=='docs':
        jobs=[['tools/check_docs.py'],['tools/check_ontology.py'],['tools/sync_obsidian.py','--check','--state',str(STATE),'--conflicts-out',str(E/f'docs-{attempt}-sync-conflicts.json')],['tools/check_contract_bindings.py'],['tools/check_frontend_integrity.py'],['tools/check_doc_single_source.py','--ratchet'],['tools/check_response_freshness.py'],['tools/check_doc_path_citations.py','--ratchet','--base-ref','0e66b5ab2b5fbc131dd6e98f5d5e8930ac045148']]
        for i,args in enumerate(jobs,1):rows.append(run(f'docs-{attempt}-{i}',args,state=STATE if 'tools/sync_obsidian.py' in args else None))
    elif phase=='check':rows.append(run(f'canonical-{attempt}',[str(R/'tools/sync_obsidian.py'),'--check','--state',str(STATE),'--conflicts-out',str(E/f'canonical-{attempt}-conflicts.json')],state=STATE))
    else:raise ValueError(phase)
    (E/f'{phase}-{attempt}.json').write_bytes((json.dumps({'phase':phase,'commands':rows,'allExpectedExits':all(r['exit']==r['expectedExit'] for r in rows)},indent=2)+'\n').encode())
if __name__=='__main__':main()
