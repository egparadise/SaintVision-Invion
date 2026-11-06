"""Seal current proof/doc receipts; no selfacceptance or future CI invented."""
import json,sys
from a7_common import *
from a7_record import producers

def main():
    attempt=sys.argv[1];scripts=producers();receipts=[]
    for phase in ('proof','docs'):
        p=E/f'{phase}-{attempt}.json';d=json.loads(p.read_bytes());assert d['allExpectedExits'];assert len(d['commands'])==(3 if phase=='proof' else 8)
        for row in d['commands']:
            assert row['producerHashesBefore']==row['producerHashesAfter']==scripts
            assert hashlib.sha256((E/row['rawLog']).read_bytes()).hexdigest()==row['rawSHA256']
            if row['canonicalStateBefore'] is not None:assert row['canonicalStateBefore']==row['canonicalStateAfter']
        receipts.append({'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    current=json.loads((E/'a7-current-verification.json').read_bytes());assert current['finalProducerHashes']==scripts
    h=ROOT/'docs/vault/30_Development/History/2026-11-07_FLEET5_B_A7_Snapshot_R1_Codex.md'
    files=[{'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(E.iterdir()) if p.is_file() and p.name!='proof-producer-hashes.json']
    result={'base':'0e66b5ab2b5fbc131dd6e98f5d5e8930ac045148','productSource':SOURCE,'ownerTask':'task_a8fd2969f0b3','dispatch':'ctx_6f0f8253b8a7','rootMessage':'msg_35937c8787d1','files':files,'producers':scripts,'commandReceipts':receipts,'history':{'path':h.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(h.read_bytes()).hexdigest()},'status':'SOURCE_STATIC_UNRESOLVED_RUNTIME_PENDING','independentA7Review':'PENDING through Root after D04 reviewer exit/release','CIAtCommit':'one exact own Docs run follows commit/push; actual run metadata returned to Root; no future ID invented','actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING','note':'all copies of actual90cc review are historical evidence, not newly executed A7 cases; no whole B completion, grant or product code'}
    emit('proof-producer-hashes.json',result);print(json.dumps({'manifestSHA256':hashlib.sha256((E/'proof-producer-hashes.json').read_bytes()).hexdigest(),'files':len(files),'producers':len(scripts),'status':result['status']}))
if __name__=='__main__':main()
