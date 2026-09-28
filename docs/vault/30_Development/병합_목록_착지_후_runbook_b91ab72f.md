---
doc_id: "CLAUDE-LANDING-RUNBOOK-B91AB72F-001"
title: "병합 목록 착지 후 runbook — integration을 b91ab72f로 fast-forward한 직후: MERGED 확인, 남는 열린 PR의 base 재지정, train branch 정리, 5 workflow + AC-11 + S11 재실행과 기대 수치, 되돌리기 (카드 110, docs-only)"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T23:58:03+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "b91ab72f"
task_ids: ["S12-BE"]
tags: ["runbook", "merge-train", "landing", "integration", "ci", "claude"]
---

# 병합 목록 착지 후 runbook (b91ab72f)

사용자가 `D:/Project/SaintVisionI-Invion/merge-land-b91ab72f.sh`를 실행해 `integration/all-agents-unified`를 **`1e8baf04` → `b91ab72f`** 로 fast-forward한 **직후**에 할 일이다. 카드 110, **docs-only** — 이 문서의 스크립트는 전부 코드 블록이고 **실행하지 않았다.** 사용자가 실행하는 것과 owner가 실행하는 것을 각 단계에 적었다. 에이전트는 병합·push를 하지 않는다.

착지 commit의 실측(`git log -1 b91ab72f`, `git ls-remote`):

| 항목 | 값 |
|---|---|
| `b91ab72f` | `Merge PR #169 (b69bba2d8b50) into merge train`, 2026-09-28T23:28:51+09:00 |
| 첫째 부모 | `96a03486` = `origin/coord/train-ci-2305`(94 PR 합성 tree, 5 workflow + AC-11 + S11 green) |
| 둘째 부모 | `b69bba2d` = #169 head(docs 경로 인용 검사 + train tree에서 재시드한 baseline 294줄) |
| 착지 전 integration tip | `1e8baf04`(스크립트가 이 값과 다르면 중단한다) |
| 착지 후 GitHub 기대 | 병합 목록 **95 PR**(`sv-train-list-96a03486.sh`의 `m` 94 + #169) |
| 착지 tree 자체의 hosted 증거 | Backend **36436343934** success(3.12/3.14 각 `5203 passed, 49 skipped, 2 deselected`, contracts 77 PASS), Docs **36436348599** success(1006 documents, `check_doc_path_citations --ratchet` **294 broken, all in baseline, none stale, floor unchanged**) |
| 첫째 부모 tree의 hosted 증거 | Backend 36433497438(`5182 passed, 49 skipped, 2 deselected` ×2, contracts 77), Core 36433502535(`5485 passed, 21 skipped, 2 deselected` + CX01 20 + 하위 suite), Frontend 36433507640(Test Files **85**, Tests **838**, TS types 21), Docs 36433513422(1005 documents), Desktop 36433517878(7 passed), AC-11 36433523372(migration-rehearsal success), S11 36433528073(1 passed, verdict 검사 통과) — 전부 `workflow_dispatch`, head `96a03486` |
| 독립 검증 | Codex 카드 104 r2 코멘트(PR #207) |

`b91ab72f`와 `96a03486`의 차이는 #169 하나(docs 검사 도구·baseline·시험 21건)이므로, 착지 tree의 Core·Frontend·Desktop·AC-11·S11 기대값은 첫째 부모의 실측과 같다(§4).

## 1. GitHub가 95 PR을 MERGED로 표시했는지 확인

GitHub는 PR의 **head commit이 그 PR의 base branch에서 도달 가능**해지면 PR을 자동으로 `MERGED`로 닫는다. 그래서 착지 직후의 결과는 두 종류로 갈린다 — **base가 `integration/all-agents-unified`인 58개**는 즉시 `MERGED`가 되고, **base가 다른 agent branch인 37개(stacked)**는 그 base branch가 움직이지 않았으므로 **`OPEN`으로 남는다**(`delete_branch_on_merge`가 `false`라 GitHub가 base를 재지정하지도 않는다 — `sv-train-list-96a03486.sh`의 `r` 줄이 per-PR 병합 경로에서 하려던 일이 fast-forward 착지에서는 아직 수행되지 않았다).

### 1-1. 목록과 상태를 한 번에 (사용자 또는 owner, 읽기 전용)

```bash
# 95개: 목록 스크립트의 m 줄 94개 + #169
grep -oE '^m [0-9]+' D:/Project/SaintVisionI-Invion/sv-train-list-96a03486.sh | awk '{print $2}' > /tmp/train.txt
echo 169 >> /tmp/train.txt
for n in $(cat /tmp/train.txt); do
  gh pr view "$n" --json number,state,baseRefName,headRefOid \
    --jq '"\(.number)\t\(.state)\t\(.baseRefName)\t\(.headRefOid[0:8])"'
  sleep 2   # GitHub secondary rate limit
done | sort -n | tee /tmp/train-state.txt
echo "MERGED: $(grep -c $'\tMERGED\t' /tmp/train-state.txt) / 95"
grep -v $'\tMERGED\t' /tmp/train-state.txt || echo "all merged"
```

기대: 1단계 직후 `MERGED` **58**, 나머지 **37**은 `OPEN`이고 전부 base가 `integration/all-agents-unified`가 **아니다**(§1-2에서 닫는다). 착지 뒤 pinned head가 tree에 있는지는 `git merge-base --is-ancestor <headRefOid> b91ab72f`로 95개 전부 확인할 수 있다 — 하나라도 실패하면 착지 tree가 목록과 다른 것이므로 **중단**하고 코디네이터에게 알린다.

```bash
git fetch origin integration/all-agents-unified
for n in $(cat /tmp/train.txt); do
  h=$(gh pr view "$n" --json headRefOid --jq .headRefOid); sleep 2
  git merge-base --is-ancestor "$h" origin/integration/all-agents-unified && echo "ok #$n" || echo "MISSING #$n $h"
done
```

### 1-2. stacked 37개의 base 재지정 (owner 또는 사용자)

base를 `integration/all-agents-unified`로 바꾸면 GitHub가 "head가 base에 포함됨"을 다시 평가해 `MERGED`로 전환한다(전환되지 않는 경우는 §1-3).

```bash
# 2026-09-28 23:50 KST `gh pr list --state open --limit 200` 실측: base가 integration이 아닌 train PR 37개
for n in 133 138 142 143 149 159 165 173 174 175 176 177 184 187 188 190 191 192 193 196 197 198 199 200 201 202 203 204 205 208 210 211 212 213 214 215 217; do
  gh pr edit "$n" --base integration/all-agents-unified; sleep 2
  gh pr view "$n" --json state --jq "\"#$n \(.state)\""; sleep 2
done
```

기대: 37개 전부 `MERGED`. 순서는 무관하다(모든 head가 이미 `b91ab72f` 안에 있다).

### 1-3. 전환되지 않는 PR

base 변경 뒤에도 `OPEN`이면 GitHub가 재평가하지 않은 것이다. 강제하지 않는다 — 다음 둘 중 하나를 **사용자가** 고른다: (a) `gh pr close <n> --comment "head <sha>는 b91ab72f에 포함됨(착지 commit). 병합 목록 착지로 닫음."` (닫힘은 `MERGED`가 아니라 `CLOSED`로 표시된다 — 기록의 정직성을 위해 코멘트에 착지 commit을 적는다), (b) 그대로 두고 코디네이터 판단. 어느 쪽이든 목록에 적는다.

## 2. 병합 목록 밖에 남는 열린 PR — base 재지정과 re-merge

`gh pr list --state open --limit 200`(2026-09-28 23:50 KST, 134개) 중 목록 밖은 다음이다. **base가 이미 병합된 branch를 가리키는 것**만 재지정 대상이다.

| PR | 현재 base | base의 운명 | 조치 |
|---|---|---|---|
| **#218** G-03 2단계 설계 | `agent/claude/g03-conformance-api-impl`(#200) | 착지에 포함 | **재지정** + re-merge |
| **#219** G-05 FE 모델 레지스트리 | `agent/claude/g04-w4-retention-pin`(#196) | 착지에 포함 | **재지정** + re-merge |
| **#221** G-03 2단계 구현(0055) | `agent/claude/g04-w3-verify-route`(#215) | 착지에 포함 | **재지정** + re-merge. 이 PR은 #208·#216 head도 이미 merge했으므로 코드 충돌은 예상되지 않고 보드 3파일만 남는다 |
| **#194** canonical 403 denial audit | `agent/claude/g04-w2-model-version-register`(#191) | 착지에 포함 | owner 확인: #184가 같은 내용(#195, canonical 403 denial audit)을 fast-forward로 포함했다면 **superseded → close**, 아니면 재지정 |
| #220 재채점, #222 카드 106, #223 카드 108 | `integration/all-agents-unified` | — | 재지정 불필요. **re-merge만** — 보드 파일(진행 현황·Claude 작업 현황)이 착지 tree와 충돌하므로 owner가 union으로 해소 |
| #140 S3 object store 설계 | `integration/all-agents-unified` | — | 목록 밖(설계 docs). 재지정 불필요, re-merge 여부는 owner |
| #115, #118, #119 | `integration/all-agents-unified` | — | 목록 밖. #115는 목록 스크립트가 "semaphore line closed — do not merge"로 적음(superseded). #118 S04-DB runner·#119 S07 five-node adapter는 코디네이터 판단 |
| #141, #145, #148 | #115 → #141 → #145 stack | 착지에 **없음** | 목록 스크립트가 superseded로 적음(#151이 대체). **close** 권고(사용자) |
| #2~#35 (25개, Codex 초기 lane) | `agent/codex/*` | 착지와 무관 | 이 runbook 범위 밖. 코디네이터 판단 |
| 카드 101 PR | — | — | 이 목록에서 **특정하지 못했다**(`gh pr list --search "카드 101"`는 PR 번호 101과 무관 항목만 반환). 코디네이터가 번호를 주면 위 규칙(base가 병합된 branch면 재지정 + re-merge)을 그대로 적용한다 |

### 2-1. 재지정 명령 (owner)

```bash
for n in 218 219 221; do
  gh pr edit "$n" --base integration/all-agents-unified; sleep 2
done
# #194는 owner 확인 뒤: superseded면
#   gh pr close 194 --comment "superseded by #195 content landed via #184 (b91ab72f)"
# 아니면 gh pr edit 194 --base integration/all-agents-unified
```

### 2-2. re-merge (각 owner, 자기 branch에서, 해소만)

재지정된 PR의 diff는 이제 `integration`(=`b91ab72f`) 대비로 계산된다. branch가 착지 tree를 아직 포함하지 않으면 보드 3파일(`docs/vault/00_Index/전체 개발 진행 현황.md`, `docs/vault/30_Development/Agent별 작업/<Agent> 작업 현황.md`)이 충돌한다. 규칙은 병합 목록과 같다 — **양쪽 항목 union, frontmatter는 최대 version·최신 updated, 코드 충돌은 없어야 한다**(있으면 그 PR은 재검토 대상).

```bash
git switch <pr-branch>
git fetch origin integration/all-agents-unified
git merge --no-ff --no-edit origin/integration/all-agents-unified   # 충돌 → 보드만 union으로 해소
# 해소만이었는지: merge-tree 대비 diff는 충돌 hunk(marker·frontmatter 한쪽)뿐이어야 한다
git diff --stat "$(git merge-tree --write-tree <pr-head-before> origin/integration/all-agents-unified | head -1)" HEAD
python <coordinator>/classcheck.py "$(git rev-parse HEAD)"   # ok
git push origin <pr-branch>   # force 금지
```

그 뒤 PR의 hosted run(재지정 뒤 `pull_request` 이벤트가 새 base로 다시 돈다)을 인용하고 reviewer 재확인을 요청한다. #221은 Codex 조건부 승인(exact-head hosted Backend/Core green)이 걸려 있으므로 re-merge head에서 그 조건을 다시 채운다.

## 3. `coord/train-*` branch 정리 (사용자 실행)

착지 뒤 남는 원격 branch(`git ls-remote origin 'refs/heads/coord/*'`, 2026-09-28 23:48 KST):

| branch | tip | 용도 | 처분 |
|---|---|---|---|
| `coord/train-land-2330` | `b91ab72f` | 착지 commit 자체 | 착지 확인 뒤 삭제 가능(commit은 integration에 있다) |
| `coord/train-ci-2305` | `96a03486` | 5 workflow 증거 tree | **run 증거가 SHA로 남으므로** 삭제해도 증거는 유지된다. 단 §4의 기대값 재대조가 끝난 뒤 삭제 |
| `coord/train-ci-2207` `9f1c2be4`, `-2150` `95a59b24`, `-2118` `bbd9619e`, `-2001` `ffa0e0db` | 이전 합성 tree | #220 재채점(`95a59b24` 고정)·#222(`9f1c2be4` 분석 tree)가 인용 | 인용 문서가 SHA를 적고 있으므로 삭제해도 문서는 유효하다. 다만 **재현이 필요하면 SHA를 `git fetch origin <sha>`로 받을 수 없을 수 있다**(unreachable object는 GC 대상) — 삭제 전에 `git tag coord-train-ci-2207 9f1c2be4` 같은 **tag로 고정**하기를 권고 |
| `coord/merge-train-20260928` | `696a869f` | 최초 train | 위와 같음 |

```bash
# 사용자만. 삭제 전 tag로 고정(권고), 그 뒤 branch 삭제. force 아님.
for pair in "coord-train-ci-2001 ffa0e0db" "coord-train-ci-2118 bbd9619e" "coord-train-ci-2150 95a59b24" \
            "coord-train-ci-2207 9f1c2be4" "coord-train-ci-2305 96a03486" "coord-merge-train-20260928 696a869f"; do
  set -- $pair; git tag -a "$1" "$2" -m "merge-train synthetic tree kept for citation"; done
git push origin --tags
git push origin --delete coord/train-ci-2001 coord/train-ci-2118 coord/train-ci-2150 coord/train-ci-2207 \
                         coord/train-ci-2305 coord/merge-train-20260928 coord/train-land-2330
```

## 4. integration에서 5 workflow + AC-11 + S11 재실행과 기대 수치

### 4-1. 무엇이 저절로 돌고 무엇을 dispatch해야 하는가

`.github/workflows/*.yml`의 `on:`(착지 tree 기준):

| workflow | integration push에 자동 | 수동 dispatch |
|---|---|---|
| Backend Build (`backend.yml`) | **예** | `gh workflow run backend.yml --ref integration/all-agents-unified` |
| Core Build (`core.yml`) | **예** | `gh workflow run core.yml --ref integration/all-agents-unified` |
| Frontend Build & Test (`frontend.yml`) | **예** | `gh workflow run frontend.yml --ref integration/all-agents-unified` |
| Documentation Build (`docs.yml`) | **예** | `gh workflow run docs.yml --ref integration/all-agents-unified` |
| Auth and Desktop HTTP Browser Acceptance (`desktop-browser.yml`) | **예** | `gh workflow run desktop-browser.yml --ref integration/all-agents-unified` |
| AC-11 Migration Rehearsal (`ac11-migration-rehearsal.yml`) | **아니오**(`workflow_dispatch` + PR label) | **필수** `gh workflow run ac11-migration-rehearsal.yml --ref integration/all-agents-unified` |
| S11 Storage Failure Hosted Reference (`s11-storage-failure-hosted.yml`) | **아니오** | **필수** `gh workflow run s11-storage-failure-hosted.yml --ref integration/all-agents-unified` |

```bash
# 착지 push가 만든 5개 run 확인
gh run list --branch integration/all-agents-unified --event push --limit 10 \
  --json databaseId,name,status,conclusion,headSha --jq '.[] | "\(.databaseId)\t\(.name)\t\(.status)\t\(.conclusion // "-")\t\(.headSha[0:8])"'
# 나머지 둘은 dispatch
gh workflow run ac11-migration-rehearsal.yml --ref integration/all-agents-unified
gh workflow run s11-storage-failure-hosted.yml --ref integration/all-agents-unified
# 완료 대기는 5분 간격(secondary rate limit)
```

Docs의 push run은 `check_doc_path_citations --ratchet --base-ref $GITHUB_EVENT_BEFORE`(= `1e8baf04`, baseline 파일 없음)로 돌므로 **floor 검사는 "first introduction"으로 skip**되고 294 baseline이 그대로 통과해야 한다(#169 카드 107 코멘트의 예상과 같다). 그 다음 push부터 baseline은 shrink-only다.

### 4-2. 기대 수치 (합성 tree 실측 인용 — 이 값과 다르면 조사)

| workflow | 기대 | 근거 run |
|---|---|---|
| Backend | 3.12/3.14 각 **`5203 passed, 49 skipped, 2 deselected, 0 failed`**, `PASS: 77 contract schemas match their models.` | **36436343934** (`b91ab72f` 자체) |
| Docs | `PASS: 24 original hashes, 1006 versioned documents …`, `PASS check_doc_path_citations --ratchet: 294 broken citation(s), all in baseline, none stale` | **36436348599** (`b91ab72f` 자체) |
| Core | core job: **`5485 passed, 21 skipped, 2 deselected, 0 failed`** + CX01 `20 passed` + 하위 suite(`3 passed`·`21 passed`·`22 passed`·`28 passed`); s01-storage-roundtrip job success. **45분 예산 안**(#216 포함) | 36433502535 (`96a03486`; #169는 core 무변경) |
| Frontend | `Test Files 85 passed (85)`, `Tests 838 passed (838)`, `PASS: 21 API response TypeScript types match their JSON Schemas.` | 36433507640 (`96a03486`; #169는 FE 무변경) |
| Desktop | `7 passed` | 36433517878 |
| AC-11 | migration-rehearsal job success; report axes `MEASURED_PASS`, reversible tail은 `0053_eval_suite_project_scope`·`0054_model_version_measurements`(#177·#213 포함, 0055는 착지 밖) | 36433523372 |
| S11 | `1 passed`, `verdict ∈ {MEASURED_PASS, MEASURED_FAIL, NOT_OBSERVED}` 단언 통과 | 36433528073 |

같은 tree에서 같은 수가 나와야 한다. **skip 수가 다르면** exact skip map(`backend.yml`의 `expected_skips`)이 잡으므로 Backend가 red가 된다 — 그것이 정상이고, 그때는 어떤 reason이 늘었는지 log에서 읽는다. 시간이 달라지는 것은 정상이다.

## 5. 실패 시 되돌리기

원칙: **force-push 금지.** `git push origin 1e8baf04:integration/all-agents-unified`는 fast-forward가 아니라 **거부되며**, `--force`는 사용자 판단 영역이다(그리고 GitHub는 force로 되돌려도 PR의 `MERGED` 표시를 되돌리지 않는다).

**권고: revert commit 방식** — integration 위에 "tree를 `1e8baf04`로 되돌리는" commit 하나를 얹는다. 95개 merge를 `git revert -m 1`로 하나씩 되돌리는 것은 순서·충돌 때문에 현실적이지 않고, tree 복원 commit 하나가 같은 결과를 fast-forward로 만든다.

```bash
git fetch origin
git switch -c coord/rollback-to-1e8baf04 origin/integration/all-agents-unified   # = b91ab72f
git read-tree -m -u 1e8baf04                 # index·working tree를 착지 전 tree로
git commit -m "revert(integration): restore the tree of 1e8baf04 — merge-train b91ab72f rolled back (reason: <run id / failure>)"
git diff --stat 1e8baf04 HEAD | tail -1      # 기대: 0 files changed (tree 동일)
git push origin HEAD:integration/all-agents-unified   # fast-forward, force 아님
```

되돌린 뒤: (1) 95 PR은 GitHub에서 `MERGED`로 남는다 — 다시 착지하려면 **새 합성 commit**(train)을 만들고 같은 절차를 반복한다(PR을 재오픈할 수 없으므로 새 PR 또는 코디네이터의 목록 관리), (2) §2에서 재지정한 PR들은 base가 integration이므로 diff가 다시 커진다 — 재지정을 되돌릴 필요는 없다, (3) 실패 원인 run id와 되돌림 commit SHA를 `docs/vault/30_Development/2026-09-28 병합 목록 현황과 남은 공백.md`의 후속 판에 적는다.

**부분 실패의 판단 기준**: §4-2의 7개 중 하나라도 red면 원인을 먼저 읽는다. exact skip map 불일치·docs 인용 baseline stale처럼 **tree는 맞고 기대값 표가 틀린** 경우는 되돌리지 않고 표를 고친다. 시험 실패·migration 실패처럼 **tree가 틀린** 경우만 되돌린다.

## 6. 경계

- 이 문서는 **실행하지 않았다.** 모든 명령은 코드 블록이고, PR 상태·branch 목록·run 수치는 2026-09-28 23:48~23:58 KST에 `gh`·`git ls-remote`·`gh run view --log`로 읽은 값이다. 착지 시점에 다시 읽으면 값이 다를 수 있다(특히 §2의 열린 PR 목록).
- GitHub의 "base 변경 → MERGED 자동 전환"은 문서화된 동작이지만 **이 저장소에서 확인한 적은 없다.** §1-3이 그 경우의 처리다.
- `coord/train-*` 삭제는 사용자 결정이다. 삭제 전 tag 고정을 권고했을 뿐 요구하지 않는다.
- 카드 101 PR을 특정하지 못했다(§2).
