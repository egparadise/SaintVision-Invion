"""Final staged scope/source hashes only; no commit/push/runtime side effects."""
import hashlib,json,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists());BASE='54549b90774aab3599c0486a5217d0d1634baca8'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT).decode('utf8').strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert git('rev-parse','HEAD')==BASE
    assert git('branch','--show-current')=='agent/codex/fleet5-b-rev9e-20261107'
    assert not git('diff','--name-only')
    prefix=E.relative_to(ROOT).as_posix()+'/'
    history='docs/vault/30_Development/History/2026-11-07_FLEET5_B_Rev9e_FixOnly_Codex.md'
    raw=subprocess.check_output(['git','diff','--cached','--name-status','-z'],cwd=ROOT).decode('utf8').split(chr(0));raw=[x for x in raw if x]
    rows=list(zip(raw[::2],raw[1::2]));assert rows and len(raw)==2*len(rows)
    assert all(status=='A' and (path.startswith(prefix) or path==history) for status,path in rows),rows
    assert not git('ls-files','--others','--exclude-standard')
    m=json.loads((E/'proof-producer-hashes.json').read_bytes())
    for r in m['producersAndRetainedScripts']:assert sha(E/r['file'])==r['sha256'] and (E/r['file']).stat().st_size==r['bytes']
    for r in m['artifacts']+m['originalReviewCopiesVerified']:assert sha(E/r['file'])==r['sha256']
    assert sha(ROOT/m['history']['path'])==m['history']['sha256']
    for n,h in m['modelLifecycleFrozen'].items():assert sha(E/n)==h
    print(json.dumps({'stageVerified':True,'base':BASE,'onlyAddedFiles':len(rows),'allowedEvidencePrefix':prefix,'allowedHistory':history,'productOrPriorFileChanges':0,'manifestSHA256':sha(E/'proof-producer-hashes.json'),'producerScripts':len(m['producersAndRetainedScripts']),'reviewCopies':len(m['originalReviewCopiesVerified']),'actualRuntimeB':0,'independentReview':'PENDING'}))
if __name__=='__main__':main()
