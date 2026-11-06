"""One-time Rev9 preparation. Unique Evidence only; never run after editing."""
import datetime,hashlib,json,subprocess
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=next(p for p in E.parents if (p/'AGENTS.md').exists())
R8=E.parent/'fleet5-b-rev8-revoke-portcut-20261106-codex'
VAULT=Path('D:/Project/SaintVisionI-Invion/fleet-five-orchestration-20261105/docs/vault')
def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    docs=['00_Index/전체 개발 진행 현황.md','30_Development/Agent별 작업/Codex 작업 현황.md',
      '00_Index/2026-09-15 단일 가상 컴퓨터 보강 설계 인덱스.md','30_Development/57.81퍼센트 이후 단일 가상 컴퓨터 보강 로드맵.md',
      '40_Governance/Agent 연속 실행과 최종 보고 정책.md','00_Index/최종 개발 계획 - 모든 개발의 지침.md',
      '40_Governance/설계 충돌 정정 및 ADR.md','40_Governance/Agent 역할과 인계 계약.md','40_Governance/Git Build Obsidian 운영 절차.md','40_Governance/Agent 지속 개발 운영 규칙.md']
    read=[]
    for p in docs:
        raw=(VAULT/p).read_bytes();t=raw.decode('utf-8-sig');read.append({'path':'ROOT_READ_ONLY/docs/vault/'+p,'sha256':hashlib.sha256(raw).hexdigest(),'frontmatter':t.split('---',2)[1].strip()})
    for p in ['AGENTS.md','skills/agent-delivery/SKILL.md','skills/core-reliability/SKILL.md','docs/task-registry.json']:
        read.append({'path':p,'sha256':sha(ROOT/p)})
    copied=[]
    for n in ['model.py','lifecycle.py','io_contract.py','schema.py','authority.py','catalog.py','rank_contract.py','bounded_analysis.py']:
        raw=(R8/n).read_bytes().replace(b'\r\n',b'\n');(E/n).write_bytes(raw);copied.append({'path':str((R8/n).relative_to(ROOT)).replace('\\','/'),'sha256':sha(R8/n)})
    review='0440d1cabcb74ce24d9b43c95970dae795957952';rp='docs/vault/30_Development/Evidence/fleet5-b-rev8-6a65-review-20261106-claude/'
    reviews=[]
    for n in ['review.json','reviewer_tf_released_claim_probe.py.txt','reviewer-tf-released-claim-probe-result.jsonl.txt','reviewer_m2_rule_mutations.py.txt','reviewer-m2-rule-mutations-result.json','reviewer_m1_l2_rev8_attacks.py.txt','reviewer-m1-l2-rev8-attacks-result.json','reviewer-category-triage-result.json']:
        raw=subprocess.check_output(['git','show',review+':'+rp+n],cwd=ROOT);(E/('prior-'+n)).write_bytes(raw);reviews.append({'commit':review,'path':rp+n,'sha256':hashlib.sha256(raw).hexdigest()})
    retained=[]
    for r in json.loads((R8/'input-receipts.json').read_bytes())['immutableRetained']:
        assert sha(ROOT/r['path'])==r['sha256'];retained.append(r)
    for n in ['critical-edge-categories.json','pilot-closure.json','writer-census-delta.json','pending-interface-contracts.json','transport-delta.json']:
        retained.append({'path':str((R8/n).relative_to(ROOT)).replace('\\','/'),'sha256':sha(R8/n),'bytes':(R8/n).stat().st_size})
    d={'task':'FLEET5-B-REV9-T1-20261106','orcaTask':'task_a8fd2969f0b3','dispatch':'ctx_6f0f8253b8a7','owner':'Codex','reviewer':'Actual independent Claude via Root; Rev9 PENDING','rootMessage':'msg_78b82487362a',
      'base':'6a65665819d7479073189c524abf585636c3079d','productSource':'72028cbac903c4415d9979f980a6e0f9948e914f','rootHeadAtRead':subprocess.check_output(['git','-C',str(VAULT.parents[1]),'rev-parse','HEAD']).decode().strip(),
      'scope':'DOCS/schema/static/symbolic only. Matched-claim terminal/protected cleanup split, hints, hardened A1/A2, narrow T1/A8/mark_offline. A7 deferred. No grants.',
      'kst':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'docs':read,'copiedSymbolicInputs':copied,'actualPriorReview':reviews,'immutableRetained':retained,
      'actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING','partialFreeze':False,'ObsidianApply':False}
    (E/'input-receipts.json').write_bytes((json.dumps(d,ensure_ascii=True,indent=2)+'\n').encode())
    print(json.dumps({'docs':[r['frontmatter'] for r in read[:2]],'retainedHashed':len(retained),'actualReviewFiles':len(reviews)}))
if __name__=='__main__':main()
