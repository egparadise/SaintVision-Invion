"""Rev8 owner preparation; immutable input reads, unique Evidence writes only."""
import datetime, hashlib, json, subprocess
from pathlib import Path
E = Path(__file__).resolve().parent
ROOT = next(p for p in E.parents if (p/'AGENTS.md').exists())
R7 = E.parent/'fleet5-b-contract-rev7-20261106-codex'
ROOT_VAULT = Path('D:/Project/SaintVisionI-Invion/fleet-five-orchestration-20261105/docs/vault')
BASE = '33f7c6b48883cb06d1ea7d645bdb88634eb1bca0'
SOURCE = '72028cbac903c4415d9979f980a6e0f9948e914f'
REVIEW = '97bb2f6734ee328fe86031053bb7490ab011a523'
def sha(data): return hashlib.sha256(data).hexdigest()
def write(name, value): (E/name).write_bytes((json.dumps(value, ensure_ascii=True, indent=2)+'\n').encode())
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)
def main():
    docs = ['00_Index/전체 개발 진행 현황.md','30_Development/Agent별 작업/Codex 작업 현황.md',
      '00_Index/2026-09-15 단일 가상 컴퓨터 보강 설계 인덱스.md',
      '30_Development/57.81퍼센트 이후 단일 가상 컴퓨터 보강 로드맵.md',
      '40_Governance/Agent 연속 실행과 최종 보고 정책.md','00_Index/최종 개발 계획 - 모든 개발의 지침.md',
      '40_Governance/설계 충돌 정정 및 ADR.md','40_Governance/Agent 역할과 인계 계약.md',
      '40_Governance/Git Build Obsidian 운영 절차.md','40_Governance/Agent 지속 개발 운영 규칙.md']
    receipts=[]
    for p in docs:
        raw=(ROOT_VAULT/p).read_bytes(); text=raw.decode('utf-8-sig')
        header=text.split('---',2)[1] if text.startswith('---') else '\n'.join(text.splitlines()[:10])
        receipts.append(dict(path='ROOT_READ_ONLY/docs/vault/'+p,sha256=sha(raw),frontmatter=header.strip()))
    for p in ['AGENTS.md','skills/agent-delivery/SKILL.md','skills/core-reliability/SKILL.md','docs/task-registry.json']:
        raw=(ROOT/p).read_bytes(); receipts.append(dict(path=p,sha256=sha(raw),bytes=len(raw)))
    for n in ['model.py','lifecycle.py','io_contract.py','schema.py','authority.py','catalog.py','rank_contract.py']:
        # Small symbolic proposal only; retained ledgers are referenced, never copied.
        raw=(R7/n).read_bytes().replace(b'\r\n',b'\n'); (E/n).write_bytes(raw)
    review_dir='docs/vault/30_Development/Evidence/fleet5-b-rev7-33f7-review-20261106-claude/'
    review_inputs=[]
    for n in ['review.json','reviewer_m1_rev7_attacks.py.txt','reviewer-m1-rev7-attacks-result.json','reviewer-m2-port-taxonomy-result.json']:
        raw=git('show',REVIEW+':'+review_dir+n); (E/('prior-'+n)).write_bytes(raw)
        review_inputs.append(dict(commit=REVIEW,path=review_dir+n,sha256=sha(raw),bytes=len(raw)))
    retained=[]
    for p in sorted(R7.iterdir()):
        if p.suffix=='.jsonl' or p.name in ('source-manifest.json','entry-lock-plans.json','transport-inventory.json','retained-surface-carry-forward.json'):
            raw=p.read_bytes(); retained.append(dict(path=str(p.relative_to(ROOT)).replace('\\','/'),sha256=sha(raw),bytes=len(raw)))
    write('input-receipts.json',dict(task='FLEET5-B-REV8-REVOKE-PORTCUT-20261106',orcaTask='task_a8fd2969f0b3',dispatch='ctx_6f0f8253b8a7',
        owner='Codex',reviewer='Claude independent via Root; Rev8 PENDING',rootMessage='msg_aca0d787de3d',
        base=BASE,productSource=SOURCE,rootHead=git('-C',str(ROOT_VAULT.parents[1]),'rev-parse','HEAD').decode().strip(),
        rootExpectedAtDecision='443eb3d0ec35c4e6546d3534de93d7d6c311049266e; Index443/Codex404',
        kst=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),docs=receipts,actualIndependentPriorReview=review_inputs,
        immutableRetained=retained,scope='DOCS/schema/static/symbolic; revoke_channel pilot only; no production implementation or grant',
        actualRuntimeB=0,realBindings=None,A1_A16='PENDING',partialFreeze=False,obsidianApply=False))
    print(json.dumps({'docs':[{k:r[k] for k in ('path','frontmatter') if k in r} for r in receipts[:10]],'retainedLedgers':len(retained),'reviewRead':len(review_inputs)},ensure_ascii=True))
if __name__=='__main__': main()
