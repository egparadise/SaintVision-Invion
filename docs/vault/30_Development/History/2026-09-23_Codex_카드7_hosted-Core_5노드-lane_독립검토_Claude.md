---
doc_id: "HIST-CLAUDE-REVIEW-CODEX-CARD7-FIVE-NODE-LANE-001"
title: "Codex 카드 7 독립 검토 — 21c6a026 hosted Core scoped-handle 23건 집계(artifact 직접 대조 일치) + 5노드 opt-in lane 정의(core.yml 정합·합성 adapter/물리 runner 정직 분리) + S06-DB review 유지 근거 → 승인(관찰 3)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-23T01:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["review", "codex", "card7", "hosted-ci", "five-node", "S05", "S06", "S07", "docs-only"]
---

# Codex 카드 7 독립 검토 (reviewer Claude)

대상: integration `21c6a026`(docs: [[Codex 5노드 랩 opt-in lane 정의]] 신설, S07 보고 v1.2.0, S06 구현 보고 v1.1.0) + 보고 `d6323d0f`([[2026-09-23_00-18-00_KST_Card7_hosted-Core_5노드-lane_Codex_보고]]). 검토 트리 `.worktrees/claude-rev7`(tip). 코드·계약·`core.yml` 변경 없음(파일 목록 확인). 검토는 (a) hosted artifact 직접 대조, (b) lane 정의 ↔ `core.yml` 현 구조·도구 CLI 대조, (c) S06-DB 상태 근거.

## 판정: **승인** (finding 0, 관찰 3)

## (a) hosted Core 35742655096 집계 — artifact 직접 대조

`gh run download 35742655096`(`saintvision-core-evidence`, 29 파일)에서 내가 직접 집계:

| 항목 | Codex 보고 | 내 집계 | 일치 |
|---|---|---|---|
| run | head `a4bf2cee`, success | Core Build success `a4bf2cee` 2026-09-22T14:46:29Z | ✔ |
| `core-tests.xml` SHA-256 | `965a98c8…df98bbf` | `965a98c8776ac7dd70b6ae7956493d2a600cee1b1ef15d02414ae4230df98bbf` | ✔ |
| 전체 | 3,134 tests / 35 skips / 0 fail·error | 3134 / 35 / 0 / 0 | ✔ |
| skip 분포 | 35 declared platform skips | CX01 19 · PowerShell 10 · csc 1 · browser smoke 1 · CLI 4 = 35(PR #59 ratchet과 동일) | ✔ |
| `tests.integration.test_workspace_recovery` | 12 passed / 0 skip | 12 cases, skipped 0, failed 0 | ✔ |
| `tests.integration.test_workspace_resume` | 11 passed / 0 skip | 11 cases, skipped 0, failed 0 | ✔ |
| `workspace-tests.xml` resume | 11/11 | 22 cases 중 resume 11, skipped 0, fail 0 | ✔ |

개발 PC Windows의 23 skip(`Linux scoped handles` 12 + `Linux bounded Workspace execution` 11)이 hosted Linux에서 0 skip으로 실행됐다는 서술과 일치.

## (b) 5노드 opt-in lane 정의 ↔ `core.yml`·도구

| 검증 | 결과 |
|---|---|
| `core.yml` 무변경 | `21c6a026` 파일 목록에 workflow 없음 ✔; 현 헤더(`workflow_dispatch`·push·PR `labeled`·`run-core` opt-in·concurrency group `${workflow}-${ref}`, `cancel-in-progress` main/integration 제외 = a7f2ecf2) 그대로 |
| lane 입력 | self-hosted 라벨 `[self-hosted, linux, x64, saintvision-five-node-lab]`·environment `five-node-lab`(승인)·`workflow_dispatch` 입력(code_sha 40hex·inventory_revision·image digest 4·s05/s07 파라미터) — 기존 `workflow_dispatch` 구조와 정합 |
| env·secret | 환경변수는 이름·출처만, secret은 **이름만**(`FIVE_NODE_INV_TEST_ADMIN_DSN` 등 7) — 값 0건 ✔. `INV_TEST_ADMIN_DSN`을 secret에서 주입(hosted는 service DB 리터럴) — 격리된 disposable PG 전제와 일치 |
| 명령 CLI 실존 | `placement_benchmark.py --requests --concurrency --report --junit` ✔ · `measure_s07_recovery.py --nodes --repetitions --liveness-timeout-seconds --poll-interval-seconds --target-recovery-success-rate --json-out --junit-out` ✔ · `check_remote_workspace.py --state --prepared --image --preflight-only` ✔ · `run_s06_five_node_journey.py` **부재**(문서가 "앞의 네 명령은 현재 도구의 실제 인터페이스"로 구분, 5번째는 제안) |
| 정직 분리 | "S05 기본 adapter·S07 measurement는 실 PG의 합성 node row → 5노드 runner에서 실행만 해서는 물리 증거가 아님", "S06 7-case는 WS/PTY/Git·CP/Node 재시작 미포함" 명시 ✔; S07 감지 상한 timeout+poll(F-S07-03 결정)·synthetic recovery 비승격 ✔ |
| artifact | 4개(`five-node-{manifest,s05,s07,s06}-<code_sha>`), `if: always()` 30일, 비밀 제외, 독립 reviewer 대조 후에만 AC 판정 ✔ |

## (c) S06-DB review 유지 근거
registry `S06-DB` = `review`(owner Codex, reviewer Claude, AC-06, `next_handoff: Claude`) 불변. 구현 보고 v1.1.0은 hosted Linux 23/23으로 O1을 해소하되 "물리 원격 WS/PTY/Git·CP/Node 재시작 복원 여정 미측정 → AC-06 미닫힘·review 유지"를 명시 — 내 PR #76 승인 조건과 일치. 게이트: `check_docs` PASS 836 · `check_ontology` PASS 48.

## 관찰 (비차단)
- **O1 concurrency**: lane 문서는 "동시 실행 1개"만 적고 concurrency **group 이름·`cancel-in-progress: false`** 를 명시하지 않는다. `core.yml` 현 정책은 `${workflow}-${ref}` 그룹에 non-main 취소이므로, 같은 workflow에 lane job을 넣으면 같은 ref의 후속 push가 진행 중인 물리 측정을 취소할 수 있다. 랩 lane은 별도 그룹(예: `five-node-lab`) + 취소 금지로 고정 권고.
- **O2 5번째 명령**: `run_s06_five_node_journey.py`는 아직 없다. artifact 표의 `five-node-s06-workspace`가 그 산출물에 의존하므로 명령 줄에 "(제안·미구현)"을 인라인 표기해 두면 랩 담당이 실존 도구로 오인하지 않는다.
- **O3 PYTHONPATH 구분자**: `src:services/control-plane/src`(Linux `:`) — self-hosted linux 전제와 일치하나, 문서 상단의 "개발 PC는 판정에 쓰지 않는다"와 함께 Windows에서 그대로 복붙되지 않도록 한 줄.

## 부수 조치
`.work/dev/orch/codex-worker-status.md`에 `CLAUDE-REVIEW:` 줄 기입. 코드 변경 없음(docs-only PR).
