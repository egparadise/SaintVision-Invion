"""Seal FINAL R2 bytes and bounded proof/docs receipts, no selfacceptance."""
import json,sys
from a7_common import *
from a7_record import producers
def main():
    attempt=sys.argv[1];docs_attempt=sys.argv[2] if len(sys.argv)>2 else attempt;scripts=producers();receipts=[]
    for phase,count in (('proof',3),('docs',8)):
        phase_attempt=docs_attempt if phase=='docs' else attempt
        p=E/f'{phase}-{phase_attempt}.json';d=json.loads(p.read_bytes());assert len(d['commands'])==count and d['allExpectedExits']
        for row in d['commands']:
            assert row['producerHashesBefore']==row['producerHashesAfter']==scripts
            assert hashlib.sha256((E/row['rawLog']).read_bytes()).hexdigest()==row['rawSHA256']
            if row['canonicalStateBefore'] is not None:assert row['canonicalStateBefore']==row['canonicalStateAfter']
        receipts.append({'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    verification=json.loads((E/'r2-current-verification.json').read_bytes());assert verification['finalProducerHashes']==scripts
    h=ROOT/'docs/vault/30_Development/History/2026-11-07_FLEET5_B_A7_Snapshot_R2_Codex.md'
    files=[{'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(E.iterdir()) if p.is_file() and p.name!='proof-producer-hashes.json']
    result={'base':'1550453d1f072a87fd9a7baa53d4fe4ce8a98d5d','productSource':SOURCE,'ownerTask':'task_a8fd2969f0b3','dispatch':'ctx_6f0f8253b8a7','rootMessage':'msg_e051a19e0010','files':files,'producers':scripts,'commandReceipts':receipts,'history':{'path':h.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(h.read_bytes()).hexdigest()},'status':'SOURCE_STATIC_UNRESOLVED_RUNTIME_PENDING','original19ObligationsUnchanged':True,'independentR2Review':'PENDING through Root after actual D04 CODE reviewer exit/release','CIAtCommit':'One exact own manual Docs follows commit/push; actual ID returned to Root, no second CI commit/amendment','actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING','note':'Actual7a80 ten review originals and historical49rows/INFO are preserved, not new executed coverage. R2 fixes existing census guard coverage only; no full caller/runtime/product/source inclusion grant or whole-B completion.'}
    emit('proof-producer-hashes.json',result);print(json.dumps({'manifestSHA256':hashlib.sha256((E/'proof-producer-hashes.json').read_bytes()).hexdigest(),'files':len(files),'producersAndInherited':len(scripts),'status':result['status']}))
if __name__=='__main__':main()
