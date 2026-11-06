"""One-time Rev9b preparation; unique own History/Evidence only."""
import datetime,hashlib,json,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists());R9=E.parent/'fleet5-b-rev9-t1-20261106-codex'
VAULT=Path('D:/Project/SaintVisionI-Invion/fleet-five-orchestration-20261105/docs/vault')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    docs=['00_Index/전체 개발 진행 현황.md','30_Development/Agent별 작업/Codex 작업 현황.md','00_Index/2026-09-15 단일 가상 컴퓨터 보강 설계 인덱스.md','30_Development/57.81퍼센트 이후 단일 가상 컴퓨터 보강 로드맵.md','40_Governance/Agent 연속 실행과 최종 보고 정책.md','00_Index/최종 개발 계획 - 모든 개발의 지침.md','40_Governance/설계 충돌 정정 및 ADR.md','40_Governance/Agent 역할과 인계 계약.md','40_Governance/Git Build Obsidian 운영 절차.md','40_Governance/Agent 지속 개발 운영 규칙.md']
    read=[]
    for p in docs:
        raw=(VAULT/p).read_bytes();t=raw.decode('utf-8-sig');read.append({'path':'ROOT_READ_ONLY/docs/vault/'+p,'sha256':hashlib.sha256(raw).hexdigest(),'frontmatter':t.split('---',2)[1].strip()})
    for p in ['AGENTS.md','skills/agent-delivery/SKILL.md','skills/core-reliability/SKILL.md','docs/task-registry.json']:read.append({'path':p,'sha256':sha(ROOT/p)})
    scripts=['model.py','lifecycle.py','io_contract.py','schema.py','authority.py','catalog.py','rank_contract.py','bounded_analysis.py','analysis_rules.py','mutation_fixture.py','t1_provenance.py','t1_build.py','model_tests.py','analysis_rule_tests.py','t1_tests.py','retained_probes.py','pending_contracts.py','edge_categories.py','packet_checks.py','run_checks.py','measured_run.py','terminal_claim_regression.py']
    copied=[]
    for n in scripts:(E/n).write_bytes((R9/n).read_bytes().replace(b'\r\n',b'\n'));copied.append({'file':n,'source':'Rev9@3daf1a0d','sha256':sha(R9/n)})
    # Raw older reviewer scripts are copied without changing a byte.
    for p in R9.glob('prior-*'):
        if p.is_file():(E/p.name).write_bytes(p.read_bytes())
    review='a7e9f9d7ca7803533bccf84f443591cbcd2bd5dc';prefix='docs/vault/30_Development/Evidence/fleet5-b-rev9-3daf-review-20261106-claude/'
    paths=subprocess.check_output(['git','diff-tree','--no-commit-id','--name-only','-r',review],cwd=ROOT).decode().splitlines();reviews=[]
    for path in paths:
        if not path.startswith(prefix) or path.endswith('.gitattributes'):continue
        n=path[len(prefix):];raw=subprocess.check_output(['git','show',review+':'+path],cwd=ROOT);(E/('rev9-review-'+n)).write_bytes(raw);reviews.append({'commit':review,'path':path,'sha256':hashlib.sha256(raw).hexdigest()})
    retained=json.loads((R9/'input-receipts.json').read_bytes())['immutableRetained']
    for p in ['t1-mark-offline-closure.json','targeted-category-delta.json','producer-order.json','pending-interface-contracts.json']:
        retained.append({'path':str((R9/p).relative_to(ROOT)).replace('\\','/'),'sha256':sha(R9/p),'bytes':(R9/p).stat().st_size})
    d={'task':'FLEET5-B-REV9B-FIX-ONLY-20261106','orcaTask':'task_a8fd2969f0b3','dispatch':'ctx_6f0f8253b8a7','owner':'Codex','reviewer':'Actual independent Claude through Root; Rev9b PENDING','rootMessage':'msg_b6b4813cb5c2','base':'3daf1a0d24c220586474a4b376609e62960b8ca6','productSource':'72028cbac903c4415d9979f980a6e0f9948e914f','rootHeadAtRead':subprocess.check_output(['git','-C',str(VAULT.parents[1]),'rev-parse','HEAD']).decode().strip(),'scope':'Fix-only DOCS/schema/static/symbolic. Terminal projection/tenant guard, exhaustive constructor census/local helper, bounded use-site allowlists; no A7 or runtime grant.','kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'docs':read,'copiedProducers':copied,'actualPriorReview':reviews,'immutableRetained':retained,'actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING','partialFreeze':False}
    (E/'input-receipts.json').write_bytes((json.dumps(d,ensure_ascii=True,indent=2)+'\n').encode());print(json.dumps({'rootBoards':[r['frontmatter'] for r in read[:2]],'copiedProducers':len(copied),'actualReviewInputs':len(reviews)}))
if __name__=='__main__':main()
