"""Only changed packet/category checks after exact initial Docs publication."""
import datetime,hashlib,json,subprocess,sys,time
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
def write(p,x):p.write_bytes((json.dumps(x,indent=2)+'\n').encode())
def main():
    original=E/'proof-producer-hashes-at-8b8af.json'
    if not original.exists():original.write_bytes((E/'proof-producer-hashes.json').read_bytes())
    commands=[]
    for i,n in enumerate(('edge_categories.py','packet_checks.py'),1):
        cmd=[sys.executable,'-B',str(E/'measured_run.py'),str(E/n)];log=E/f'followup-checks-{i}.log';t=time.monotonic()
        with log.open('wb') as stream:r=subprocess.run(cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        commands.append({'command':cmd,'expectedExit':0,'actualExit':r.returncode,'seconds':round(time.monotonic()-t,3),'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'log':log.name,'sha256':hashlib.sha256(log.read_bytes()).hexdigest()})
        write(E/'followup-checks.json',{'commands':commands,'reason':'Final packet inspection: attach exact nested SQL scope source, separate ContextVar/constructor/result analysis obligations from shared owner, link actual SQL function body dependencies','initialPublication':{'sha':'8b8af7876fd4656efb8958e6f646111f6bc45d75','Docs':42176380292,'job':127755688389,'status':'SUCCESS; superseded by final corrected head'},'unchangedProofCommands':'Original fourteen expected exits retained; only these two changed proof producers rerun','actualRuntimeB':0,'independentReview':'PENDING through Root'})
        print(json.dumps(commands[-1]),flush=True)
        if r.returncode:print(log.read_text(encoding='utf8',errors='replace')[-3000:]);raise SystemExit(1)
    files=sorted(p for p in E.iterdir() if p.suffix=='.py' or p.name in ('contract.schema.json','authority-matrix.json','reader-io-catalog.json','pilot-closure.json','writer-census-delta.json','pending-interface-contracts.json','critical-edge-categories.json','transport-delta.json'))
    write(E/'proof-producer-hashes.json',{'base':'33f7c6b48883cb06d1ea7d645bdb88634eb1bca0','productSource':'72028cbac903c4415d9979f980a6e0f9948e914f','scope':'Final corrected producers; original executed producer hashes retained separately at8b8af; followup-checks covers changed category/packet producers','files':[{'file':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],'actualRuntimeB':0})
if __name__=='__main__':main()
