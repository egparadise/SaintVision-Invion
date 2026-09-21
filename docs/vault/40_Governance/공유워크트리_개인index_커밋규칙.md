---
doc_id: "GOV-SHARED-WORKTREE-INDEX-001"
title: "공유 worktree 다중 에이전트 커밋 규칙 — 개인 index + rev-range 검증 (셋 다 준수)"
version: "1.0.0"
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

## 상세 근거
`memory:integration-branch-moves-midsession`(Claude). 사고 (가)의 최초 기록·(나)의 확인은 2026-09-21 이어가기 문서. 이 규칙은 Claude가 오늘 11개 커밋을 이 방식으로 무사고 착지시킨 실증에 기반한다.
