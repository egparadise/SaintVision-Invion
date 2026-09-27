---
doc_id: "HIST-CODEX-S05-HOSTED-20-WAVE-20260928-001"
title: "S05 hosted legacy candidate-B 20동시 wave"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T08:45:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["history", "s05", "placement", "semaphore", "hosted-ci", "benchmark"]
---

# S05 hosted legacy/candidate-B 20동시 wave

## 실행 경계

- PR: [#141](https://github.com/egparadise/SaintVision-Invion/pull/141), stacked base PR #115 head `08f4a6a9`
- 실행 code SHA: `60a63fbf5ee60cacd6c6212b7362a99576d9d4af`
- 측정 대상 제품 SHA: PR #115 head `08f4a6a95d08f28e90bea300d32b2f657f3cf656`
- hosted run: [36358438372](https://github.com/egparadise/SaintVision-Invion/actions/runs/36358438372), `s05-hosted-wave` success
- artifact: `saintvision-s05-hosted-wave-36358438372`
- 순서: legacy 1~3 뒤 candidate-B 1~3, 각 20 request/20 concurrency/1 round, 겹침 없이 순차 실행
- candidate-B: short-commit, tenant+project process-local semaphore N=4, limits lock budget 500ms
- 로컬 실 PG·Docker·전체 suite는 메모리 긴급 규칙에 따라 실행하지 않았다.

## 환경

| 항목 | 값 |
|---|---|
| runner | Ubuntu 24 (`ubuntu24`, image `20260920.314.1`), X64, CPU 4, MemTotal 16,373,444KiB |
| Python | 3.12.14 |
| PostgreSQL | 16.15, server_version_num 160015, max_connections 100 |
| service default timeout | lock 0, statement 0 |
| benchmark transaction timeout | lock 500ms, statement 2000ms |

hosted runner 수치는 개발 PC 수치와 직접 합치거나 절대값 비교하지 않는다. 이 run 안의 legacy/candidate-B 상대 비교만 사용한다.

## 원자료

| wave | 성공/실패 | 외부 실패 | semaphore reject | SQL timeout | P95 all | P95 success | hold P95 | permit hold P95 | 종료 registry entry/permit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| legacy-1 | 20/0 | 0 | 0 | 0 | 470.774ms | 470.774ms | 13.050ms | n/a | 0/0 |
| legacy-2 | 20/0 | 0 | 0 | 0 | 457.822ms | 457.822ms | 14.814ms | n/a | 0/0 |
| legacy-3 | 20/0 | 0 | 0 | 0 | 433.176ms | 433.176ms | 13.131ms | n/a | 0/0 |
| candidate-B-1 | 4/16 | 16 | 16 | 0 | 398.630ms | 409.622ms | 20.729ms | 112.743ms | 0/0 |
| candidate-B-2 | 4/16 | 16 | 16 | 0 | 387.150ms | 398.020ms | 16.984ms | 111.734ms | 0/0 |
| candidate-B-3 | 4/16 | 16 | 16 | 0 | 391.719ms | 402.497ms | 12.968ms | 105.068ms | 0/0 |

candidate wave의 pytest exit 1은 16개 request failure를 원본 JUnit에 보존한 결과다. aggregate JUnit은 6개 wave 증거가 모두 생성·검증됐음을 뜻하는 1 test, failure/error/skip 0이며 후보 승격 판정과 분리했다.

## 3조건 판정

| 조건 | legacy | candidate-B | 판정 |
|---|---:|---:|---|
| 외부 실패 합계 | 0 | 48 | FAIL |
| 전체 요청 P95 3회 중앙값 | 457.822ms | 391.719ms | PASS |
| 성공 post-acquire hold P95 3회 중앙값 | 13.131ms | 16.984ms | FAIL |

결론은 `GATES_FAILED`다. candidate-B의 낮은 P95 all은 48건의 빠른 semaphore reject가 포함된 결과이므로 성공률 또는 AC-05 개선으로 해석하지 않는다. flag 기본값은 off, `promotionClaim=false`, S05-DB는 `in_progress`를 유지하며 50동시·5노드·운영 활성화로 승격하지 않는다.

## 게이트와 다음 인계

- PG-free focused: `tests/test_s05_hosted_wave.py` 14 passed/exit 0
- Black, workflow YAML parse, `check_docs`, contract bindings, ontology, single-source ratchet, diff: exit 0
- reviewer Claude가 lane의 판정 분리, 원자료 완결성, fast reject 해석을 검토한다.

관련 사양: [[S05 hosted 20동시 wave opt-in lane 사양]], [[S05 project별 bounded semaphore 사양]].
