---
doc_id: "CLAUDE-LANDING-RUNBOOK-B91AB72F-001"
title: "병합 목록 착지 후 runbook — integration을 b91ab72f로 fast-forward한 직후: 먼저 exact-SHA 7 workflow green, 그 뒤에만 MERGED 전환·base 재지정·branch 정리, 되돌리기는 hard-stop 뒤 revert commit (카드 110, docs-only)"
version: "1.1.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-29T00:21:29+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "b91ab72f"
task_ids: ["S12-BE"]
tags: ["runbook", "merge-train", "landing", "integration", "ci", "rollback", "claude"]
---

# 병합 목록 착지 후 runbook (b91ab72f)

사용자가 `D:/Project/SaintVisionI-Invion/merge-land-b91ab72f.sh`를 실행해 `integration/all-agents-unified`를 **`1e8baf04` → `b91ab72f`** 로 fast-forward한 **직후**에 할 일이다. 카드 110, **docs-only** — 이 문서의 스크립트는 전부 코드 블록이고 **실행하지 않았다.** 사용자가 실행하는 것과 owner가 실행하는 것을 각 단계에 적었다. 에이전트는 병합·push를 하지 않는다.

### v1.1 — Codex 1차 검토(head `9a83f1b7`) 반영

| | 지적 | v1.1 |
|---|---|---|
| F1 | 되돌릴 수 없는 GitHub 상태 변경(간접 `MERGED`·close·branch 삭제)이 landing CI보다 앞에 있었다 | **순서를 바꿨다**: §1 exact-SHA 7 workflow green → §2 읽기 전용 확인 → §3 base 재지정·close(green 뒤에만) → §4 목록 밖 PR → §5 branch 정리(맨 마지막). red면 §6으로 가고 §3~§5는 시작하지 않는다 |
| F2 | Core 기대 `5485`가 #169의 21 test를 빼먹었다 | 착지 head의 Core 기대는 **5506 passed로 추론**(`5485 + tests/test_check_doc_path_citations.py` 21건; Backend가 같은 delta로 5182→5203인 것과 정합). **`b91ab72f`의 Core 실측은 아직 없다**고 명시하고, 첫 landing run에서 확정한다 |
| F3 | rollback이 최신 integration tip이 `b91ab72f`인지 검증하지 않아 이후 정상 변경까지 덮을 수 있었다 | `origin/integration/all-agents-unified == <LAND full SHA>`와 `git status --porcelain` 빈 값을 **hard-stop**으로 단언 |
| F4 | `git push origin --tags`가 로컬 모든 tag를 게시; `<coordinator>/classcheck.py`·`<pr-branch>`가 재현 불가 placeholder | tag는 이름별 explicit refspec + 생성 전 동일 이름 local/remote SHA 검사; re-merge는 `gh pr view`로 head를 읽어 fetch하고 `HEAD == headRefOid`를 단언, classcheck는 저장소 안의 검사(`git merge-tree` 대비 diff + `.py` 변경 0 + marker 0)로 대체 |

착지 commit의 실측(`git log -1 b91ab72f`, `git ls-remote`; Codex가 `gh pr list --state all`·`gh run view`로 재확인):

| 항목 | 값 |
|---|---|
| `b91ab72f` (full `b91ab72f1d822f67afffc26a998699797adbae62`) | `Merge PR #169 (b69bba2d8b50) into merge train`, 2026-09-28T23:28:51+09:00 |
| 첫째 부모 | `96a03486` = `origin/coord/train-ci-2305`(94 PR 합성 tree, 5 workflow + AC-11 + S11 green) |
| 둘째 부모 | `b69bba2d` = #169 head(docs 경로 인용 검사 + train tree에서 재시드한 baseline 294줄 + `tests/test_check_doc_path_citations.py` 21 test) |
| 착지 전 integration tip | `1e8baf04`(스크립트가 이 값과 다르면 중단한다) |
| 병합 목록 | **95 PR** = `sv-train-list-96a03486.sh`의 `m` 94(중복 0) + #169. 95개 head 전부 `b91ab72f`의 조상(Codex 재확인 실패 0). base가 `integration/all-agents-unified`인 것 **58**, 다른 agent branch인 것(stacked) **37** |
| 착지 tree 자체의 hosted 증거 | Backend **36436343934** success(3.12/3.14 각 `5203 passed, 49 skipped, 2 deselected`, contracts 77 PASS), Docs **36436348599** success(1006 documents, `check_doc_path_citations --ratchet` 294 broken, all in baseline, none stale) |
| 첫째 부모 tree의 hosted 증거 | Backend 36433497438(`5182 passed, 49 skipped, 2 deselected` ×2), Core 36433502535(`5485 passed, 21 skipped, 2 deselected` + CX01 20 + 하위 suite), Frontend 36433507640(Test Files **85**, Tests **838**, TS types 21), Docs 36433513422(1005 documents), Desktop 36433517878(7 passed), AC-11 36433523372(migration-rehearsal success), S11 36433528073(1 passed, verdict 검사 통과) — 전부 `workflow_dispatch`, head `96a03486` |
| 독립 검증 | Codex 카드 104 r2 코멘트(PR #207) |

`b91ab72f`와 `96a03486`의 차이는 #169 하나다: docs 검사 도구·baseline·`tests/test_check_doc_path_citations.py`(21 test). Core의 본 pytest는 이 파일을 ignore하지 않으므로 Core에도 +21이 실행된다(§1-3).

## 0. 순서 — 되돌릴 수 없는 것은 green 뒤에만

| 단계 | 무엇 | 되돌릴 수 있는가 | 언제 |
|---|---|---|---|
| §1 | 착지 push가 만든 자동 5 run 확인 + AC-11·S11 dispatch, **exact SHA** 7개 green | — | 착지 직후 |
| §2 | 95 PR 상태 읽기, head가 tree에 있는지 `merge-base` 확인 | 읽기 전용 | §1과 병행 가능 |
| §3 | stacked 37개 `gh pr edit --base`(간접 `MERGED`), 전환 안 되는 PR close | **없다** — rollback해도 `MERGED`는 돌아오지 않고 PR은 다시 열 수 없다 | **7개 green 뒤** |
| §4 | 목록 밖 열린 PR base 재지정·re-merge push·close | 재지정은 되돌릴 수 있으나 close·push는 비용이 크다 | §3 뒤 |
| §5 | `coord/train-*` branch 삭제 | tag로 고정하지 않으면 **없다** | **맨 마지막** |
| §6 | 되돌리기 | — | §1이 red이고 원인이 tree일 때. **§3~§5를 시작하지 않은 상태에서** |

## 1. exact-SHA 7 workflow green (사용자 또는 owner)

### 1-1. 무엇이 저절로 돌고 무엇을 dispatch해야 하는가

`.github/workflows/*.yml`의 `on:`(착지 tree에서 읽음):

| workflow | integration push에 자동 | 수동 dispatch |
|---|---|---|
| Backend Build (`backend.yml`) | **예** | `gh workflow run backend.yml --ref integration/all-agents-unified` |
| Core Build (`core.yml`) | **예** | `gh workflow run core.yml --ref integration/all-agents-unified` |
| Frontend Build & Test (`frontend.yml`) | **예** | `gh workflow run frontend.yml --ref integration/all-agents-unified` |
| Documentation Build (`docs.yml`) | **예** | `gh workflow run docs.yml --ref integration/all-agents-unified` |
| Auth and Desktop HTTP Browser Acceptance (`desktop-browser.yml`) | **예** | `gh workflow run desktop-browser.yml --ref integration/all-agents-unified` |
| AC-11 Migration Rehearsal (`ac11-migration-rehearsal.yml`) | **아니오**(`workflow_dispatch` + PR label) | **필수** |
| S11 Storage Failure Hosted Reference (`s11-storage-failure-hosted.yml`) | **아니오** | **필수** |

### 1-2. 명령

```bash
LAND=b91ab72f1d822f67afffc26a998699797adbae62
git fetch origin integration/all-agents-unified
[ "$(git rev-parse origin/integration/all-agents-unified)" = "$LAND" ] || { echo "integration tip is not $LAND"; exit 1; }

# 자동 5 run (push 이벤트, head = LAND)
gh run list --branch integration/all-agents-unified --event push --limit 10 \
  --json databaseId,name,status,conclusion,headSha \
  --jq '.[] | select(.headSha=="'"$LAND"'") | "\(.databaseId)\t\(.name)\t\(.status)\t\(.conclusion // "-")"'
# 수동 2 run
gh workflow run ac11-migration-rehearsal.yml --ref integration/all-agents-unified
gh workflow run s11-storage-failure-hosted.yml --ref integration/all-agents-unified
# 완료 대기는 5분 간격(secondary rate limit). 7개 전부 headSha == LAND 이고 conclusion == success 여야 다음 단계로 간다.
gh run list --branch integration/all-agents-unified --limit 20 --json databaseId,name,conclusion,headSha,event \
  --jq '.[] | select(.headSha=="'"$LAND"'") | "\(.databaseId)\t\(.name)\t\(.event)\t\(.conclusion // "-")"'
```

Docs의 push run은 `check_doc_path_citations --ratchet --base-ref $GITHUB_EVENT_BEFORE`(= `1e8baf04`, baseline 파일 없음)로 돌므로 **floor 검사는 "first introduction"으로 skip**되고 294 baseline이 그대로 통과해야 한다(#169 카드 107 코멘트의 예상과 같다). 그 다음 push부터 baseline은 shrink-only다.

### 1-3. 기대 수치

| workflow | 기대 | 근거 |
|---|---|---|
| Backend | 3.12/3.14 각 **`5203 passed, 49 skipped, 2 deselected, 0 failed`**, `PASS: 77 contract schemas match their models.` | **실측** 36436343934 (`b91ab72f`) |
| Docs | `PASS: 24 original hashes, 1006 versioned documents …`, `PASS check_doc_path_citations --ratchet: 294 broken citation(s), all in baseline, none stale` | **실측** 36436348599 (`b91ab72f`) |
| Core | core job **`5506 passed, 21 skipped, 2 deselected, 0 failed`로 추론** = `96a03486`의 `5485` + #169의 `tests/test_check_doc_path_citations.py` 21건(Backend의 +21과 같은 delta). CX01 `20 passed` + 하위 suite(`3`·`21`·`22`·`28 passed`), s01-storage-roundtrip success, **45분 예산 안**(#216 포함). **`b91ab72f`의 Core 실측은 아직 없다** — 첫 landing run이 확정값이고, 합계·skip map을 그 run에서 읽어 이 표를 고친다 | 추론; 근거 36433502535 (`96a03486`) |
| Frontend | `Test Files 85 passed (85)`, `Tests 838 passed (838)`, `PASS: 21 API response TypeScript types match their JSON Schemas.` | 36433507640 (`96a03486`; #169는 `apps/web`·`contracts` 무변경) |
| Desktop | `7 passed` | 36433517878 (`96a03486`; #169 무관) |
| AC-11 | migration-rehearsal job success; report axes `MEASURED_PASS`, reversible tail `0053_eval_suite_project_scope`·`0054_model_version_measurements`(#177·#213 포함, 0055는 착지 밖) | 36433523372 (`96a03486`; #169는 migration 무변경) |
| S11 | `1 passed`, `verdict ∈ {MEASURED_PASS, MEASURED_FAIL, NOT_OBSERVED}` 단언 통과 | 36433528073 (`96a03486`) |

**skip 수가 다르면** exact skip map(`backend.yml`·`core.yml`의 `expected_skips`)이 잡아 red가 된다 — 그것이 정상이고, 그때는 어떤 reason이 늘었는지 log에서 읽는다. 시간이 달라지는 것은 정상이다. **Core가 `5506`이 아니라 `5485`면** 21건이 실행되지 않은 것이므로 collect 설정을 조사한다.

### 1-4. red일 때

| 원인 | 조치 |
|---|---|
| 기대값 표가 틀림(예: skip map, Core 합계 추론) | 표를 고친다. §3으로 진행 가능 |
| 인프라(PyPI timeout, runner cancel) | `gh run rerun --failed <id>` 또는 재dispatch. green이 될 때까지 §3 금지 |
| 시험 실패·migration 실패 = **tree가 틀림** | **§6 되돌리기**. §3~§5는 시작하지 않았으므로 PR 상태·원격 branch는 그대로다 |

## 2. 95 PR 상태 읽기 (읽기 전용; §1과 병행 가능)

GitHub는 PR의 **head commit이 그 PR의 base branch에서 도달 가능**해지면 PR을 `MERGED`로 닫는다(indirect merge). 그래서 착지 직후 **base가 integration인 58개는 `MERGED`**, **stacked 37개는 `OPEN`**이다 — 그 base branch는 움직이지 않았고 `delete_branch_on_merge`가 `false`라 GitHub가 base를 재지정하지도 않는다(`sv-train-list-96a03486.sh`의 `r` 줄이 per-PR 병합 경로에서 하려던 일이 fast-forward 착지에서는 수행되지 않았다).

```bash
grep -oE '^m [0-9]+' D:/Project/SaintVisionI-Invion/sv-train-list-96a03486.sh | awk '{print $2}' > /tmp/train.txt
echo 169 >> /tmp/train.txt
git fetch origin integration/all-agents-unified
for n in $(cat /tmp/train.txt); do
  gh pr view "$n" --json number,state,baseRefName,headRefOid \
    --jq '"\(.number)\t\(.state)\t\(.baseRefName)\t\(.headRefOid)"'; sleep 2
done | sort -n | tee /tmp/train-state.txt
echo "MERGED: $(grep -c $'\tMERGED\t' /tmp/train-state.txt) / 95   (기대: 58, stacked 37은 OPEN)"
# head가 착지 tree에 있는지 — 하나라도 MISSING이면 착지 tree가 목록과 다르다: 중단, 코디네이터
while IFS=$'\t' read -r n state base head; do
  git merge-base --is-ancestor "$head" origin/integration/all-agents-unified && echo "ok #$n" || echo "MISSING #$n $head"
done < /tmp/train-state.txt
```

## 3. stacked 37개의 base 재지정 (owner 또는 사용자) — **§1의 7개가 green인 뒤에만**

base를 `integration/all-agents-unified`로 바꾸면 GitHub가 "head가 base에 포함됨"을 다시 평가해 `MERGED`로 전환한다(전환되지 않는 경우는 §3-1). **되돌릴 수 없다.**

```bash
# 2026-09-28 23:50 KST `gh pr list --state open --limit 200` 실측(Codex 재확인 일치): base가 integration이 아닌 train PR 37개
for n in 133 138 142 143 149 159 165 173 174 175 176 177 184 187 188 190 191 192 193 196 197 198 199 200 201 202 203 204 205 208 210 211 212 213 214 215 217; do
  gh pr edit "$n" --base integration/all-agents-unified; sleep 2
  gh pr view "$n" --json state --jq "\"#$n \(.state)\""; sleep 2
done
```

기대: 37개 전부 `MERGED`. 순서는 무관하다(모든 head가 이미 `b91ab72f` 안에 있다).

### 3-1. 전환되지 않는 PR

base 변경 뒤에도 `OPEN`이면 GitHub가 재평가하지 않은 것이다. 강제하지 않는다 — 다음 둘 중 하나를 **사용자가** 고른다: (a) `gh pr close <n> --comment "head <full sha>는 b91ab72f에 포함됨(착지 commit). 병합 목록 착지로 닫음."` (`CLOSED`로 표시되므로 착지 commit을 코멘트에 적는다), (b) 그대로 두고 코디네이터 판단. 어느 쪽이든 목록에 적는다.

## 4. 병합 목록 밖에 남는 열린 PR — base 재지정과 re-merge (§3 뒤)

`gh pr list --state open --limit 200`(2026-09-28 23:50 KST, 134개) 중 목록 밖은 다음이다. **base가 이미 병합된 branch를 가리키는 것**만 재지정 대상이다.

| PR | 현재 base | base의 운명 | 조치 |
|---|---|---|---|
| **#218** G-03 2단계 설계 | `agent/claude/g03-conformance-api-impl`(#200) | 착지에 포함 | **재지정** + re-merge |
| **#219** G-05 FE 모델 레지스트리 | `agent/claude/g04-w4-retention-pin`(#196) | 착지에 포함 | **재지정** + re-merge |
| **#221** G-03 2단계 구현(0055) | `agent/claude/g04-w3-verify-route`(#215) | 착지에 포함 | **재지정** + re-merge. #208·#216·#201 head를 이미 merge했으므로 코드 충돌은 예상되지 않고 보드만 남는다 |
| **#194** canonical 403 denial audit | `agent/claude/g04-w2-model-version-register`(#191) | 착지에 포함 | owner 확인: #184가 같은 내용(#195)을 fast-forward로 포함했다면 **superseded → close**, 아니면 재지정 |
| #220 재채점, #222 카드 106, #223 카드 108, #225 이 문서 | `integration/all-agents-unified` | — | 재지정 불필요. **re-merge만** — 보드 파일이 착지 tree와 충돌하므로 owner가 union으로 해소 |
| #140 S3 object store 설계 | `integration/all-agents-unified` | — | 목록 밖(설계 docs). 재지정 불필요, re-merge 여부는 owner |
| #115, #118, #119 | `integration/all-agents-unified` | — | 목록 밖. #115는 목록 스크립트가 "semaphore line closed — do not merge"로 적음(superseded). #118 S04-DB runner·#119 S07 five-node adapter는 코디네이터 판단 |
| #141, #145, #148 | #115 → #141 → #145 stack | 착지에 **없음** | 목록 스크립트가 superseded로 적음(#151이 대체). **close** 권고(사용자) |
| #2~#35 (25개, Codex 초기 lane) | `agent/codex/*` | 착지와 무관 | 이 runbook 범위 밖. 코디네이터 판단 |
| 카드 101 PR | — | — | 이 목록에서 **특정하지 못했다**. 코디네이터가 번호를 주면 같은 규칙을 적용한다 |

### 4-1. 재지정 명령 (owner)

```bash
for n in 218 219 221; do
  gh pr edit "$n" --base integration/all-agents-unified; sleep 2
done
# #194는 owner 확인 뒤: superseded면
#   gh pr close 194 --comment "superseded by #195 content landed via #184 (b91ab72f)"
# 아니면 gh pr edit 194 --base integration/all-agents-unified
```

### 4-2. re-merge (각 owner, 자기 branch에서, 해소만)

재지정된 PR의 diff는 이제 `integration`(=`b91ab72f`) 대비로 계산된다. branch가 착지 tree를 아직 포함하지 않으면 보드 파일(`docs/vault/00_Index/전체 개발 진행 현황.md`, `docs/vault/30_Development/Agent별 작업/<Agent> 작업 현황.md`)이 충돌한다. 규칙은 병합 목록과 같다 — **양쪽 항목 union, frontmatter는 최대 version·최신 updated, 코드 충돌은 없어야 한다**(있으면 그 PR은 재검토 대상). **stale 로컬 branch를 합치지 않도록 PR의 실제 head를 GitHub에서 읽어 단언한다.**

```bash
N=<PR 번호>
BRANCH=$(gh pr view "$N" --json headRefName --jq .headRefName)
HEAD_BEFORE=$(gh pr view "$N" --json headRefOid --jq .headRefOid)
git fetch origin "$BRANCH" integration/all-agents-unified
git switch "$BRANCH"
[ "$(git rev-parse HEAD)" = "$HEAD_BEFORE" ] || { echo "local $BRANCH != PR head $HEAD_BEFORE"; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "worktree not clean"; exit 1; }
git merge --no-ff --no-edit origin/integration/all-agents-unified   # 충돌 → 보드만 union으로 해소, 그 뒤 git add <보드 파일> && git commit --no-edit
# 해소만이었는지, 저장소 안의 검사 셋:
T=$(git merge-tree --write-tree "$HEAD_BEFORE" origin/integration/all-agents-unified | head -1)
git diff --stat "$T" HEAD                              # 충돌 hunk(marker·frontmatter 한쪽)만 있어야 한다
[ -z "$(git diff --name-only "$T" HEAD -- '*.py' '*.ts' '*.tsx' '*.yml' '*.json')" ] || { echo "non-doc file changed in resolution"; exit 1; }
git grep -n '^<<<<<<<\|^=======$\|^>>>>>>>' -- . && { echo "conflict marker left"; exit 1; }
python tools/check_docs.py
git push origin "$BRANCH"   # force 금지
```

그 뒤 PR의 hosted run(재지정 뒤 `pull_request` 이벤트가 새 base로 다시 돈다)을 인용하고 reviewer 재확인을 요청한다. #221은 Codex 조건부 승인(exact-head hosted Backend/Core green)이 걸려 있으므로 re-merge head에서 그 조건을 다시 채운다.

## 5. `coord/train-*` branch 정리 (사용자 실행, **맨 마지막**)

착지 뒤 남는 원격 branch(`git ls-remote origin 'refs/heads/coord/*'`, 2026-09-28 23:48 KST, Codex 재확인 일치):

| branch | tip | 용도 | 처분 |
|---|---|---|---|
| `coord/train-land-2330` | `b91ab72f` | 착지 commit 자체 | §1~§4가 끝난 뒤 삭제 가능(commit은 integration에 있다) |
| `coord/train-ci-2305` | `96a03486` | 5 workflow 증거 tree | run 증거는 SHA로 남지만, §1-3의 기대값 재대조와 #225 v1.1의 Core 확정이 끝난 뒤 |
| `coord/train-ci-2207` `9f1c2be4`, `-2150` `95a59b24`, `-2118` `bbd9619e`, `-2001` `ffa0e0db` | 이전 합성 tree | #220 재채점(`95a59b24` 고정)·#222(`9f1c2be4`)·#223(`96a03486`)이 인용 | 인용 문서가 SHA를 적고 있어도 **unreachable object는 GC 대상**이므로 삭제 전에 tag로 고정 |
| `coord/merge-train-20260928` | `696a869f` | 최초 train | 위와 같음 |

tag는 **이름별 explicit refspec**으로만 push한다(`--tags`는 로컬의 모든 미푸시 tag를 게시한다). 생성 전에 같은 이름의 local/remote tag가 이미 있고 다른 SHA를 가리키면 중단한다.

```bash
set -e
git fetch origin --tags
pairs="coord-train-ci-2001=ffa0e0db coord-train-ci-2118=bbd9619e coord-train-ci-2150=95a59b24 coord-train-ci-2207=9f1c2be4 coord-train-ci-2305=96a03486 coord-merge-train-20260928=696a869f coord-train-land-2330=b91ab72f"
for pair in $pairs; do
  name=${pair%%=*}; sha=$(git rev-parse "${pair#*=}^{commit}")
  if git show-ref --tags --verify --quiet "refs/tags/$name"; then
    [ "$(git rev-parse "refs/tags/$name^{commit}")" = "$sha" ] || { echo "local tag $name points elsewhere"; exit 1; }
  fi
  remote=$(git ls-remote --tags origin "refs/tags/$name" | cut -f1)
  if [ -n "$remote" ]; then
    [ "$(git rev-parse "$remote^{commit}")" = "$sha" ] || { echo "remote tag $name points elsewhere"; exit 1; }
  else
    git tag -a "$name" "$sha" -m "merge-train synthetic tree kept for citation"
    git push origin "refs/tags/$name:refs/tags/$name"      # 이 tag 하나만
  fi
done
# tag가 전부 원격에 있음을 확인한 뒤에만 branch 삭제
git push origin --delete coord/train-ci-2001 coord/train-ci-2118 coord/train-ci-2150 coord/train-ci-2207 \
                         coord/train-ci-2305 coord/merge-train-20260928 coord/train-land-2330
```

## 6. 실패 시 되돌리기 (§3~§5 시작 전에만)

원칙: **force-push 금지.** `git push origin 1e8baf04:integration/all-agents-unified`는 fast-forward가 아니라 **거부되며**, `--force`는 사용자 판단 영역이다(GitHub는 force로 되돌려도 PR의 `MERGED` 표시를 되돌리지 않는다).

**권고: revert commit 방식** — integration 위에 "tree를 `1e8baf04`로 되돌리는" commit 하나를 얹는다. 95개 merge를 `git revert -m 1`로 하나씩 되돌리는 것은 순서·충돌 때문에 현실적이지 않고, tree 복원 commit 하나가 같은 결과를 fast-forward로 만든다.

**hard-stop 두 개**: (1) 원격 integration tip이 **정확히** `b91ab72f`(full SHA)여야 한다 — 그 사이 다른 commit이 착지했으면 이 commit은 그 정상 변경까지 지운다; 그때는 **무엇을 되돌릴지 다시 결정**한다(부분 revert 또는 새 판). (2) worktree가 깨끗해야 한다.

```bash
set -e
LAND=b91ab72f1d822f67afffc26a998699797adbae62
BASE=1e8baf045c5a554209aaef601ae4883b64da50a7
git fetch origin integration/all-agents-unified
tip=$(git rev-parse origin/integration/all-agents-unified)
[ "$tip" = "$LAND" ] || { echo "integration tip is $tip, not $LAND: integration moved after landing; decide again what to revert"; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "worktree not clean"; exit 1; }
git switch -c coord/rollback-to-1e8baf04 "$LAND"
git read-tree -m -u "$BASE"                 # index·working tree를 착지 전 tree로
git commit -m "revert(integration): restore the tree of 1e8baf04 — merge-train b91ab72f rolled back (reason: <run id / failure>)"
[ -z "$(git diff --stat "$BASE" HEAD)" ] || { echo "tree differs from $BASE"; exit 1; }
git push origin HEAD:integration/all-agents-unified   # fast-forward; 원격이 그 사이 움직였으면 non-ff로 거부된다(그대로 둔다)
```

되돌린 뒤: (1) §3을 시작하지 않았으므로 stacked 37개는 여전히 `OPEN`이고 base도 그대로다 — **간접 `MERGED`가 된 58개는 GitHub에서 `MERGED`로 남는다**(다시 열 수 없다; 재착지는 새 합성 commit과 새 PR 또는 코디네이터의 목록 관리), (2) `coord/*` branch는 삭제하지 않았으므로 증거 tree가 남아 있다, (3) 실패 원인 run id와 되돌림 commit SHA를 `docs/vault/30_Development/2026-09-28 병합 목록 현황과 남은 공백.md`의 후속 판에 적는다.

## 7. 경계

- 이 문서는 **실행하지 않았다.** 모든 명령은 코드 블록이고, PR 상태·branch 목록·run 수치는 2026-09-28 23:48~23:58 KST에 `gh`·`git ls-remote`·`gh run view --log`로 읽은 값이며 Codex가 재확인했다. 착지 시점에 다시 읽으면 값이 다를 수 있다(특히 §4의 열린 PR 목록).
- **Core의 5506은 추론**이다. 첫 landing Core run이 확정값이고 그 값으로 §1-3을 고친다.
- GitHub의 "base 변경 → MERGED 자동 전환"은 공식 문서의 indirect merge 원칙이지만 **이 저장소에서 확인한 적은 없다.** §3-1이 그 경우의 처리다.
- `coord/train-*` 삭제는 사용자 결정이다. 삭제 전 tag 고정을 요구하도록 §5의 스크립트가 짜여 있다.
- 카드 101 PR을 특정하지 못했다(§4).
