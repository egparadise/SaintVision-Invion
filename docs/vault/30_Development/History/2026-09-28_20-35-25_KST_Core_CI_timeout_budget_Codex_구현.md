---
doc_id: "HIST-CODEX-CORE-CI-TIMEOUT-001"
title: "Core CI 합친 tree 시간 예산 보정"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T20:35:25+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["CARD-92"]
tags: ["ci", "core", "timeout", "hosted-evidence"]
---

# Core CI 합친 tree 시간 예산 보정

## 1. init

- TaskCard: 카드 92
- base: `1e8baf045c5a554209aaef601ae4883b64da50a7`
- branch: `agent/codex/core-ci-timeout-budget`
- owner/reviewer: Codex / Claude
- 범위: `.github/workflows/core.yml`의 `core` job 시간 상한만 보정한다. `s01-storage-roundtrip`의 독립 10분 상한, 시험 명령, skip gate, build, Go, TypeScript gate는 바꾸지 않는다.

## 2. 실패가 아니라 예산 소진이라는 근거

합친 tree `coord/train-ci-2001`의 Core run `36413452211`, head `ffa0e0dbcc32b0499611b04a80245ed36128b9ca`는 job 시작 `11:04:35Z`부터 정확히 25분 뒤 취소됐다.

| 관측 | UTC 구간 | 경과 |
|---|---|---:|
| 필수 준비·통합 단계 | `11:04:35` → `11:14:46` | 10분 11초 |
| 본 pytest | `11:14:46` → `11:29:47` | 15분 01초 뒤 job 상한 취소 |
| 취소로 미실행 | skip ratchet, package build, Go test, TypeScript compile | 결과 없음 |

비교 가능한 성공 Core run `36394425209`는 총 23분 53초였고, pytest만 12분 38초였다. 합친 tree는 Backend 기준 개별 PR 약 3300건에서 4616 passed까지 증가했고, 15분을 받은 Core pytest도 끝나지 않았다. 따라서 25분은 정상 시험의 실패 여부를 판정하기 전에 증거 수집을 끊는다.

## 3. 결정

`core` job의 `timeout-minutes`를 25에서 45로 올린다. 45분은 관측된 필수 선행 10분 11초 뒤 확장된 pytest와 후속 네 gate가 쓸 수 있는 약 34분 49초를 주되, hung job을 무제한 방치하지 않는 bounded 상한이다.

- `faulthandler_timeout=45`는 개별 Python test 정지의 stack dump 경계이므로 job budget과 역할이 달라 유지한다.
- pytest 병렬화는 공유 PostgreSQL·Docker·고정 포트·컨테이너 위생 경계를 바꾸므로 이 작은 CI 보정에서 도입하지 않는다.
- `s01-storage-roundtrip`은 별도 job이며 10분 상한을 유지한다. 이 base에는 아직 그 후속 job이 없지만 변경 diff는 `core` 한 hunk뿐이므로 병합 목록에서 추가된 job을 건드리지 않는다.

## 4. 검증과 현재 상태

- YAML parse 및 `jobs.core.timeout-minutes == 45`: exit 0
- `git diff --check`: exit 0
- `python tools/check_docs.py`: push 전 실행
- hosted Core: PR에 `run-core` label을 붙여 동일 head에서 실행하고 run ID·완주 시간·pytest 합계를 후속 기록한다.

현재 상태는 구현 완료·hosted 재측정 대기이며, Core 성공이나 합친 tree 완주를 아직 주장하지 않는다. 다음 담당은 Claude 독립 검토와 코디네이터의 병합 목록 배치다.
