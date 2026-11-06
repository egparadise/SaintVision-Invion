"""Only own new paths and exact staged manifest bindings; no runtime operations."""
import hashlib,json,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists());BASE='3cccfe4d7511180fa8fbb6f5742328c6a43d04bd'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT).decode('utf8').strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert git('rev-parse','HEAD')==BASE and git('branch','--show-current')=='agent/codex/fleet5-b-rev9f-20261107'
    assert not git('diff','--name-only') and not git('ls-files','--others','--exclude-standard')
    prefix=E.relative_to(ROOT).as_posix()+'/';history='docs/vault/30_Development/History/2026-11-07_FLEET5_B_Rev9f_FixOnly_Codex.md'
    fields=[x for x in subprocess.check_output(['git','diff','--cached','--name-status','-z'],cwd=ROOT).decode('utf8').split(chr(0)) if x];rows=list(zip(fields[::2],fields[1::2]));assert rows and all(status=='A' and (path.startswith(prefix) or path==history) for status,path in rows)
    m=json.loads((E/'proof-producer-hashes.json').read_bytes())
    for r in m['producersAndRetainedScripts']+m['originalReviewCopiesVerified']+m['artifacts']:assert sha(E/r['file'])==r['sha256']
    assert sha(ROOT/m['history']['path'])==m['history']['sha256']
    print(json.dumps({'verified':True,'base':BASE,'onlyAddedFiles':len(rows),'productOrPriorChanges':0,'scripts':len(m['producersAndRetainedScripts']),'reviewCopies':len(m['originalReviewCopiesVerified']),'manifestSHA256':sha(E/'proof-producer-hashes.json'),'actualRuntimeB':0}))
if __name__=='__main__':main()
