---
doc_id: "GOV-SHARED-WORKTREE-INDEX-001"
title: "공유 worktree 다중 에이전트 커밋 규칙 — 개인 index + rev-range 검증 (셋 다 준수)"
version: "1.2.0"
status: "active"
author: "Claude"
reviewer: "Codex"
applies_to: ["Claude", "Codex", "Gemini"]
source_of_truth: "Git"
updated: "2026-09-21"
tags: ["governance", "commit", "shared-worktree", "isolated-index"]
---

# 공유 worktree 다중 에이전트 커밋 규칙

## 사고 (2026-09-21, 같은 형태 2회, 방향만 반대)
여러 에이전트가 **같은 작업 트리·같은 git index**를 공유하며 병렬로 일한다. 그래서 한 에이전트의 stage/커밋에 **다른 에이전트의 파일이 섞인다**.
- (가) Gemini가 index에 stage해 둔 미커밋 파일이 **Claude의 stage에 섞여 들어옴** — Claude의 stage-검증이 커밋 직전 잡음(하마터면 Gemini 미완성 작업이 Claude 커밋으로 올라갈 뻔).
- (나) Claude가 작성 중이던 `tests/core/test_serving_anchors.py`가 **Gemini의 커밋 `e7cbc51`에 섞여 올라감**(방향 반대). 다행히 최종본이 올라갔고 내용 동일했으나, 남의 커밋에 남의 파일이 귀속됨.
근본 원인: 공유 index. `git add`가 "내 것만" 담는다는 보장이 없다 — add한 순간과 커밋하는 순간 사이에 index가 남에 의해 바뀐다.

## 규칙 (셋 다 준수)
### R1. 커밋은 개인 index로, origin tip 위에 내 파일만 얹는다 (공유 index·HEAD 미접촉)
공유 index/워킹 HEAD를 건드리지 않고, 현재 origin tip 트리에 **내 파일만** 얹어 커밋 객체를 만들어 직접 push한다.

```bash
git fetch origin <branch> --quiet
BASE=$(git rev-parse origin/<branch>)
export GIT_INDEX_FILE="$(mktemp -u)"      # 개인 index (공유 .git/index 아님)
git read-tree "$BASE"                      # origin tip 트리로 개인 index 채움
git add <내-파일1> <내-파일2> ...          # 내 파일만 (never git add -A / git add .)
git diff --cached --name-only "$BASE"      # 반드시 육안 확인: 내 파일만인가
TREE=$(git write-tree)
COMMIT=$(git commit-tree "$TREE" -p "$BASE" -F <메시지파일>)
git push origin "$COMMIT:refs/heads/<branch>"
unset GIT_INDEX_FILE
```
- origin이 그새 움직였으면 push가 non-fast-forward로 거부된다 → `BASE`를 다시 잡아(fetch) 반복. 절대 `--force` 금지.
- 공유 워킹트리 파일은 그대로 둔다(다른 에이전트가 편집 중일 수 있음). 개인 index는 origin 트리에서 시작하므로 남의 미커밋 변경을 삼키지 않는다.

### R2. push 후 rev-range로 실제 올라간 것을 검증한다 (fast-forward를 믿지 말 것)
```bash
git show --stat --pretty=format:"parent=%p" "$COMMIT"   # 파일 목록·부모 확인
git show --name-only --pretty=format: "$COMMIT"          # 내 파일만인지, 타 파일 없는지
```
- 부모가 내가 잡은 `BASE`인지, 파일이 정확히 내 것인지 확인. **주의**: 한글 파일명은 git이 octal escape로 출력하므로, grep으로 "예상외 파일 없음"을 판정할 때 인코딩 때문에 오탐하기 쉽다 — 눈으로 파일 목록을 직접 확인하라.
- **R2-a 공유 문서엔 pre-commit drift 검사를 hard-stop으로.** 기존 파일(브리프·§0·정본 등)을 개인 index로 올릴 땐 add 전에 `git diff --name-only <내base> <BASE> -- <파일>`로 남이 그새 고쳤는지 본다. **출력만 하고 진행하면 소용없다 — 비어있지 않으면 커밋 중단(`exit`)하고 현재판에 재적용**하라. 실례(2026-09-22): S02 커밋이 stale tip(a8c979d0) 기반이라 그 사이 Codex `8b20d3e6`("close S01-DB")가 갱신한 브리프 callout을 되돌렸다(clobber). drift 검사가 **출력됐으나 스크립트가 안 멈춰** 통과했고, push 후 **R2 rev-range로 사후 발견**해 복구했다(a21e5f18). 즉 "가드가 있는데 강제 안 됨"(오늘 밤 부류). 검사는 **출력이 아니라 halt**여야 하고, R2는 사후 안전망일 뿐 pre-commit 정지를 대체하지 않는다.
- **R2-b push는 게이트의 exit code로 막는다 — 출력을 보는 것은 게이트가 아니다.** 착지 전 check_docs 등 게이트를 돌렸으면 그 **exit를 push 조건 안에 넣어라**: `CD=$?; ... ; if [ "$CD" -eq 0 ] && [ "$NOW" = "$BASE" ]; then git push ...`. **위반 = 게이트를 돌리고도 exit를 안 보고(또는 tip 비교로만 게이트하고) push하는 것.** "출력이 통과처럼 보였다"는 변명이 안 된다. 실례(2026-09-22, 2회): 문서에 위키링크 문법(메모리 슬러그·빈 대괄호 예시)을 넣어 check_docs가 exit 1이었는데 push를 tip 비교로만 게이트해 **red가 tip에 앉았다**(1d413155→d1c6992c, 44022523→2c83aa21). **R2-a와 형제**: R2-a는 drift 검사를 출력만 하고 안 멈춘 것, R2-b는 게이트를 돌려놓고 결과를 안 본 것. 둘 다 **「검사 ≠ 준수」**(검사는 했으나 그 결과가 다음 행동을 안 바꿈) 부류다 — 검사 결과는 반드시 **다음 명령의 조건**이어야 한다(printing ≠ gating).

### R3. 남이 편집 중인(=dirty) 공유 파일은 편집·stage하지 않는다
- 진행판(`docs/vault/00_Index/전체 개발 진행 현황.md`)처럼 여러 에이전트가 함께 쓰는 파일은, 남이 dirty면 손대지 않는다. 꼭 추가해야 하면 **origin 판을 읽어 append한 blob을 개인 index에 주입**한다(working tree 미접촉):
```bash
git show "$BASE:<path>" > /tmp/new && cat >> /tmp/new <<'EOF'
<append 내용>
EOF
BLOB=$(git hash-object -w /tmp/new)
git update-index --add --cacheinfo 100644,$BLOB,"<path>"   # 개인 index에만, 워킹트리 안 건드림
# append-only인지: diff <(git show "$BASE:<path>") /tmp/new  (삭제 줄 0 확인)
```

### R4. 코드 파일은 배경 sync가 먼저 가져갈 수 있다
공유 워킹트리에 새 코드 파일을 만들면, 배경 자동화/다른 에이전트가 자기 커밋에 담아 push할 수 있다(사고 (나)). 이때 내 개인-index 커밋에는 그 파일이 이미 BASE에 있어 안 담긴다. **최종본이 origin에 온전한지 diff로 확인**하라:
```bash
diff <(git show origin/<branch>:<path>) <path>   # 동일해야; 중간본이 올라갔으면 최종본으로 정리
```

### R5. 남의 파일을 고쳐야 할 때 (소유 흐려짐 방지) — 오늘 세 번째 유입의 변형
검사를 통과시키려 **다른 에이전트 소관 파일**을 고쳐야 할 때가 있다(예: Gemini가 Claude 문서의 `updated:` 누락을 보완해야 check_docs 통과). 남의 파일을 자기 커밋에 넣으면 소유가 흐려지고(오늘 사고 (가)(나)), 워킹트리에만 고치고 커밋에서 빼면 **그 수정이 떠돈다**(누가 커밋할지 불명 → 통합 검증이 워킹트리에선 통과, integration에선 실패하는 마스킹 발생). 실제로 오늘 그 보완은 소유자가 아닌 Codex 커밋 `8b8ed81`에 **우연히** 함께 올라 해소됐다 — 절차가 막은 게 아니다.
- 권장: (a) 워킹트리에만 고치지 말 것(떠돈다). (b) **소유자에게 통지**해 소유자가 자기 커밋으로 확정하게 한다(현재 통지 경로 없음 = 갭, 만들 것). (c) 급하면 R3의 blob 주입으로 **그 한 파일만** 개인 index에 담아 커밋하되 커밋 메시지에 "남의 파일 X의 누락 Y를 보완, 소유자 통지 요"를 남긴다. (d) 통합 검증자는 워킹트리가 integration과 일치하는지(working_tree_clean) 먼저 확인해 남의 미커밋 보완이 결과를 가리지 않게 한다.

### R6. 측정·검증은 clean 고정-tip 전용 워크트리에서 (커밋 규칙의 짝 — 측정 규칙)
R1~R5는 **커밋**을 덮는다. **측정**엔 규칙이 없어 오늘 여러 번 뒤처진 트리에서 재고 틀린 상태를 봤다(공유 주 워크트리가 origin tip보다 뒤처지고, 남의 파일 + 개인-index 유사-dirty 파일을 이고 있음 — [[워크트리_재고_2026-09-21_Claude]]).
- **R6-a 주 워크트리에서 측정하지 마라**: `provenance.working_tree_clean=YES`가 아니면 결과 불신. 주 트리는 뒤처지고 dirty를 이고 있어 틀린 상태를 보인다.
- **R6-b 전용 detached 워크트리를 origin tip 정확 SHA에 고정**: `git fetch` → `git -C <측정트리> checkout --detach <tip-SHA>` → `status --porcelain`이 **빈 출력** 확인 후 측정. 잰 **SHA를 결과에 명시**(tip은 세션 중 이동).
- **R6-c 짧은 경로·full checkout**: 실 파일 필요한 시험은 longpaths 짧은 경로에서 full checkout(sparse는 collection 에러).
- **R6-d 측정 워크트리는 하나로 재사용하되 소유자를 명시한다** (오늘 충돌: 감시자와 작업자가 같은 `C:/vw`를 써 checkout이 막힘 — 개인-index 커밋은 그 트리 HEAD를 안 옮겨 커밋본이 그대로 dirty/untracked로 남기 때문. 공유 트리 문제의 측정-트리 변형).
  - **소유**: `C:/vw` = **Claude 전용**. 소유자만 그 HEAD를 옮기고(`checkout --detach <tip>`) `clean`한다. 남은 그 트리를 checkout·clean하지 않는다(오늘처럼 막히거나, 개인-index로 이미 origin에 있으나 HEAD-lag로 dirty하게 보이는 파일을 날릴 위험).
  - **읽기엔 트리가 필요 없다**: 다른 사람은 `git show origin/<branch>:<path>`(origin 참조)로 읽는다 — checkout 불요.
  - **실행이 필요한 제2자**는 **별도 소유 트리**를 쓴다(예 코디네이터 실행용 `C:/run-user`). 남의 측정 트리를 공유하지 않는다. 측정 트리를 늘리면 grep 오염이 커지므로 **1인 1트리**로 제한하고 소유를 박는다.
  - **소유자 위생**: 개인-index 커밋 후 측정 트리를 `checkout --force --detach <tip>`로 재동기화해 committed-but-dirty-looking 적체를 남기지 않는다(다음 사람이 안 막히게).
- **R6-e 정리 원칙**: 형제 워크트리 삭제 전 `dirty=0` 확인. `ahead>0` 브랜치는 워크트리만 제거하고 **브랜치 ref 보존**(미병합 커밋 보유). 삭제는 소유자만. 워크트리 제거 ≠ 브랜치·커밋 삭제(제거는 체크아웃·미커밋만 버림).

## 상세 근거
`memory:integration-branch-moves-midsession`(Claude). 사고 (가)의 최초 기록·(나)의 확인은 2026-09-21 이어가기 문서. 이 규칙은 Claude가 오늘 11개 커밋을 이 방식으로 무사고 착지시킨 실증에 기반한다.
