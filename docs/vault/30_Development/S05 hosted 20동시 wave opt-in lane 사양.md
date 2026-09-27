---
doc_id: "CODEX-S05-HOSTED-WAVE-LANE-SPEC-001"
title: "S05 hosted 20동시 wave opt-in lane 사양"
version: "1.1.0"
status: "hosted-measured-review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T08:35:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["s05", "placement", "semaphore", "hosted-ci", "benchmark", "specification"]
---

# S05 hosted 20동시 wave opt-in lane 사양

## 1. 목적과 실행 경계

[[S05 project별 bounded semaphore 사양]] §8.3의 legacy/candidate-B 20동시 각 3회 측정을 로컬 메모리 한도와 분리된 GitHub hosted runner에서 실행한다. 이 lane은 `run-s05-wave` PR label 또는 `workflow_dispatch`에서만 시작하며, 기본 PR/push CI에는 job을 추가하지 않고 Core skip map도 바꾸지 않는다.

- PostgreSQL 16 service container 하나를 사용한다.
- `legacy-1..3` 뒤 `candidate-b-1..3` 순서로 **한 번에 wave 하나만** 실행한다.
- wave마다 20 request/20 concurrency/1 round이며 20동시를 넘지 않는다.
- candidate-B는 private short-commit + tenant/project process-local semaphore N=4 + limits lock budget 500ms다.
- production flag 기본값은 off이며 lane이 운영 설정이나 migration·공개 계약을 바꾸지 않는다.
- S05-DB는 실행 뒤에도 `in_progress`이고, 결과만으로 승격하거나 AC-05를 판정하지 않는다.

## 2. 증거 구조

각 wave는 기존 `tools/placement_benchmark.py`를 별도 프로세스로 실행해 원본 JSON, pytest JUnit, 로그를 남긴다. request failure 때문에 pytest exit 1이더라도 JSON/JUnit이 존재하고 다음 불변식을 만족하면 측정 자료로 보존한다.

1. `uniqueFencingTokens=true`, `noOverbooking=true`, `acceptanceClaim=false`
2. candidate 여부와 semaphore enabled 상태 일치
3. wave 종료 뒤 semaphore registry entry/permit 잔존 0
4. report code SHA가 synthetic pull-request merge SHA가 아닌 checkout된 PR head와 일치

집계 JSON은 runner OS/arch/image, CPU 수·메모리, Python 버전, GitHub run ID/attempt와 PostgreSQL server version/default timeout/max connections를 기록한다. DSN·password·tenant/project/run 식별자는 집계 출력에 넣지 않는다. aggregate JUnit green은 **6개 측정이 완결됐다는 뜻**이며 candidate 합격을 뜻하지 않는다. candidate 판정은 JSON의 별도 `candidateDecision`과 gate별 boolean으로만 표현한다.

## 3. 판정 기준

세 조건은 사양 §8.3과 같다.

1. candidate 외부 실패 합계 `semaphore reject + 55P03 + 57014`가 legacy 이하
2. candidate 전체 요청 P95 3회 중앙값이 legacy 대비 비악화
3. candidate 성공 요청 post-acquire hold P95 3회 중앙값이 legacy 대비 비악화

하나라도 실패하면 `GATES_FAILED`다. 빠른 semaphore 503을 성공으로 바꾸어 세지 않는다. 결과와 무관하게 `promotionClaim=false`, `s05StatusAfterRun=in_progress`를 유지한다.

## 4. 비교 제한과 롤백

hosted runner의 CPU·메모리·scheduler·PostgreSQL service 환경은 개발 PC와 다르다. 따라서 hosted 수치는 독립 calibration이며 기존 로컬 수치와 합치거나 절대값으로 직접 비교하지 않는다. 같은 hosted run 안의 legacy/candidate-B 상대 비교만 판정 입력이다.

롤백은 `.github/workflows/s05-hosted-wave.yml`, `tools/run_s05_hosted_wave.py`, focused PG-free 시험을 제거하는 것으로 끝난다. 제품 flag·schema·migration에는 롤백 대상이 없다.

## 5. 첫 hosted 실행 결과

PR #141 head `60a63fbf5ee60cacd6c6212b7362a99576d9d4af`의 run [36358438372](https://github.com/egparadise/SaintVision-Invion/actions/runs/36358438372)은 `s05-hosted-wave` job을 success로 완료했다. aggregate JUnit은 1 test, failure/error/skip 0이고 6개 원본 JSON/JUnit/log를 `saintvision-s05-hosted-wave-36358438372` artifact로 보존했다.

| mode | 3회 성공/실패 | 외부 실패 합계 | 전체 요청 P95 중앙 | 성공 post-acquire hold P95 중앙 |
|---|---:|---:|---:|---:|
| legacy | 60/0 | 0 | 457.822ms | 13.131ms |
| candidate-B | 12/48 | 48(semaphore reject 48, SQL timeout 0) | 391.719ms | 16.984ms |

candidate-B 각 wave는 4/20 성공·16 semaphore reject였고 종료 뒤 registry entry/permit은 모두 0이다. gate는 외부 실패 비증가=false, 전체 요청 P95 비악화=true, 성공 hold P95 비악화=false이므로 `GATES_FAILED`다. 빠른 거절 때문에 전체 요청 P95가 낮아진 값을 성공으로 해석하지 않으며 flag 기본 off, `promotionClaim=false`, S05-DB `in_progress`를 유지한다. hosted 환경은 Ubuntu 24 runner 4 CPU/약 15.6GiB, Python 3.12.14, PostgreSQL 16.15였으며 로컬 수치와 직접 비교하지 않는다. [[2026-09-28_08-35-00_KST_S05_hosted_20동시_wave_Codex]].
