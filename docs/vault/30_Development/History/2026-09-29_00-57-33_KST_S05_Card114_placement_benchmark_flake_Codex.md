---
doc_id: "HIST-CODEX-S05-CARD114-PLACEMENT-FLAKE-001"
title: "S05 Card114 c50 부하 측정과 일반 suite 격리"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-29T00:57:33+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["history", "s05", "placement", "concurrency", "ci", "flake"]
---

# S05 Card114 c50 부하 측정과 일반 suite 격리

## 범위

- base: `1e8baf045c5a554209aaef601ae4883b64da50a7`
- 구현 SHA: `eff23b81ad59b561510779edb9c536b3f553175b`
- PR: `#227` (`agent/codex/card114-placement-flake`)
- owner/reviewer: Codex / Claude

일반 Backend/Core 수집에서 사전 등록된 c50 부하 측정이 우연히 실행되지 않도록 opt-in 경계를 고정했다. 제품 배치 코드, 500 ms lock timeout, c50 요청 수, timeout 0 합격 기준, `RES-0007` 매핑은 바꾸지 않았다. `tools/placement_benchmark.py`만 `INV_PLACEMENT_BENCHMARK=1`을 주입하며, 일반 수집은 정확한 사유 `run only through tools/placement_benchmark.py`로 1건 skip한다. Backend/Core workflow는 그 사유와 개수를 exact skip ratchet으로 감시한다.

## 원인 분류

문제 run `36417671462`의 실제 placement 실패는 Python 3.12 job `108912675915`이다. c50 한 회에서 성공 16, `55P03` 실패 34였지만 `activeAfterRounds`는 `expectedActiveAfterRounds`와 정확히 같았고 최종 active reservation은 0이었다. 정상 lock hold는 약 9~12 ms였으나 한 holder가 647.338 ms를 점유했고, 그 뒤 직렬 대기 요청이 500 ms budget을 넘었다. Python 3.14의 placement case는 통과했고 그 job의 실패는 별도 retention fixture였다. 따라서 “Python 3.14에서 cpu=160이 잔존했다”는 최초 분류는 틀렸고, cpu=160은 그 round의 기준 active 값이었다.

로컬 사전 반복은 같은 c50 시험을 10회 실행해 **10/10 실패**했다. 각 성공/실패는 `5/45`, `19/31`, `23/27`, `17/33`, `23/27`, `38/12`, `48/2`, `25/25`, `23/27`, `23/27`이었고 매번 cleanup 뒤 active는 0이었다. 구현 뒤 explicit CLI도 기준을 완화하지 않고 성공 22/실패 28(`57014`)로 exit 1을 냈다. 즉 수정은 부하 실패를 숨기지 않고, 일반 suite와 명시적 측정 lane의 책임만 분리한다.

## 검증

| 검증 | 결과 |
|---|---|
| focused PG-free regression | 20 passed, exit 0 |
| 일반 직접 수집 | 1 skipped, exact reason 일치 |
| explicit c50 CLI | 22 success / 28 `57014`, exit 1(엄격 판정 유지) |
| `python tools/check_docs.py` | 893 documents, exit 0 |
| `python tools/check_contract_bindings.py` | 54 fixtures / 19 types / 25 sites / 14 replay guards, exit 0 |
| `PYTHONUTF8=1 python tools/check_frontend_integrity.py` | 83 files, 0 violations, exit 0 |
| `python tools/check_ontology.py` | PASS, exit 0 |
| `python tools/check_doc_single_source.py --ratchet` | 18 pairs, exit 0 |
| YAML parse / `git diff --check` | exit 0 |
| `python tools/sync_obsidian.py --check` | exit 1: 재사용 worktree의 기존 unmanaged destination 충돌 4건(`전체 개발 진행 현황`, Codex/Claude/Gemini 작업판). write·`--apply` 0건, 정본 sync는 코디네이터 인계 |
| Backend run `36444394600` | exact head, Python 3.12/3.14 각각 2929 passed / 48 skipped / 2 deselected, skip ratchet green |
| Backend run `36446063302` | exact head 반복, Python 3.12/3.14 각각 2929 passed / 48 skipped / 2 deselected, skip ratchet green |
| Core run `36444412973` | exact head, 3234 passed / 37 skipped / 2 deselected, exact skip ratchet green |

Backend 두 run의 green은 일반 suite 격리의 반복 증거이지 c50 합격 증거가 아니다. 해당 1건은 두 run 모두 skip이다.

## 검토 조건과 합격 경계

Claude 카드 116은 head `eff23b81`을 조건부 승인했다. 구현과 원인 분류는 승인했지만 hosted c50 실행 경로가 이 tree에 없다는 조건을 남겼다. 선택지 (b)를 적용한다.

- 이 PR head의 hosted c50은 **`NOT_OBSERVED`** 다.
- 현재 Backend/Core green은 c50 pass로 세지 않으며 S05 상태를 올리지 않는다.
- PR `#151`의 전용 S05 executor가 먼저 착지해야 `tools/placement_benchmark.py`의 엄격 c50을 hosted에서 다시 실행할 수 있다.
- runner class(vCPU와 PostgreSQL 동거 여부)는 c50/500 ms 임계치와 함께 사전 등록해야 한다.
- 이 카드는 `review`이며 self-close하지 않는다. 다음 담당은 Claude 재확인과 코디네이터의 병합 순서(`#151` 뒤 `#227`) 확정이다.
