---
doc_id: "CODEX-S05-LEGACY-STAIRCASE-LANE-SPEC-001"
title: "S05 legacy 동시성 계단 hosted lane 사양"
version: "1.3.1"
status: "hosted-measured-review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T10:08:35+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["s05", "placement", "legacy", "hosted-ci", "benchmark", "staircase"]
---

# S05 legacy 동시성 계단 hosted lane 사양

## 1. 목적과 opt-in 경계

[[S05 bounded admission 후속 결정 제안]] v1.2에 따라 legacy가 hosted PostgreSQL 16에서 처음 degrade하는 concurrency를 찾는다. `.github/workflows/s05-legacy-staircase.yml`은 `run-s05-legacy-staircase` PR label 또는 수동 `workflow_dispatch`에서만 실행되며 기본 PR/push CI와 skip map에 영향을 주지 않는다.

- rung은 `20→35→50`, 각 3 wave, wave는 한 번에 하나씩 순차 실행한다.
- 한 rung의 세 wave를 모두 마친 뒤 degrade를 판정하며, 첫 degrade 뒤 높은 rung은 실행하지 않는다.
- candidate/short-commit/semaphore/B-prime arm은 실행하지 않는다. Card47 integration base에는 #115의 semaphore 제품 코드와 flag 자체가 없다.
- 공개 계약·migration·registry status 변경은 없다. S05-DB는 `in_progress`, 승격과 AC-05 판정은 없다.

## 2. DB 격리와 실행 증거

각 wave는 `tools/placement_benchmark.py`를 별도 프로세스로 실행한다. pytest session fixture가 `inv_test_<uuid>` DB와 전용 runtime role을 만들고 migration head를 적용한 뒤 강제 삭제한다. 보고서에는 DB 이름 대신 SHA-256 fingerprint만 기록한다.

lane은 다음을 fail closed로 확인한다.

1. wave 전후 hosted service의 `inv_test_%` DB 수가 0이다.
2. 실행된 모든 wave의 DB fingerprint가 서로 다르다. 즉 rung별 새 DB보다 강한 wave별 새 DB다.
3. `codeSHA`는 synthetic merge SHA가 아니라 checkout한 PR head와 정확히 같다.
4. schema 1.7 legacy report에 `projectSemaphore` 증거가 없어야 하고 `uniqueFencingTokens=true`, `noOverbooking=true`, `acceptanceClaim=false`다.
5. wave별 JSON·JUnit·redacted log와 aggregate JSON·JUnit을 artifact로 14일 보존한다.

runner OS/arch/image, CPU·메모리, Python·PostgreSQL 버전, service default timeout/max connections를 기록한다. DSN·password·DB 이름·tenant/project/run 식별자는 aggregate에 넣지 않는다. hosted 수치는 환경 고유 calibration이므로 개발 PC 수치와 직접 합치거나 절대값 비교하지 않는다.

현재 wave JSON/JUnit의 `scope`는 `tests/integration/test_placement_benchmark.py`가 하드코딩한 `development-PC; one synthetic measured-node row; pre-five-node-lab`이라는 낡은 라벨이다. 실제 Card46·Card47 실행은 GitHub hosted runner에서 수행됐으며, 다음 계단 실행 전 topology 환경값을 wave report까지 전달·검증하는 후속 보강이 필요하다.

## 3. 사전 degrade 기준

각 rung의 세 wave가 완결된 뒤 다음 중 하나면 첫 degrade다.

1. `55P03+57014`가 한 wave라도 1건 이상 — 세 wave **최대값** 판정
2. request P95 all 세 wave 중앙값이 `2000.000ms` 초과 — 세 wave **중앙값** 판정

최대값과 중앙값 혼용은 의도적이다. 기준 1은 드문 timeout을 숨기지 않고, 기준 2는 대표 누적 지연을 본다. 기준 2는 개별 SQL `statement_timeout=2000ms`와 별개인 요청 전체 누적 경로 기준이다. 여러 statement가 각각 2초 전에 끝나도 전체 요청 지연은 2초를 넘을 수 있다. `2000.000ms` 동률은 degrade가 아니며 측정 뒤 기준을 바꾸지 않는다.

hold P95/max와 legacy lock-wait P95/max는 진단으로만 기록한다. workflow/service/pull/setup/cleanup/fingerprint 실패는 제품 degrade가 아니라 `INVALID_RUN`이며 수치를 판정에 쓰지 않는다.

## 4. 결과 결정과 롤백

- 20/35/50에서 degrade: 해당 rung까지 보존하고 같은 concurrency candidate(W=0, N 후보) 비교는 별도 설계·승인을 받는다.
- 50까지 degrade 없음: 측정한 hosted 범위에서 semaphore가 풀 문제가 없으므로 semaphore 라인을 닫고 legacy를 확정한다.
- 어느 결과든 semaphore 제품 코드는 추가하지 않고 S05-DB `in_progress`, 승격 없음은 유지한다.

aggregate JUnit green은 측정 완결만 뜻하며 성능 합격을 뜻하지 않는다. 판정은 JSON의 `DEGRADE_AT_<N>` 또는 `NO_DEGRADE_THROUGH_50_CLOSE_SEMAPHORE_LINE`으로 별도 기록한다.

롤백은 신규 workflow·runner·focused 시험과 integration report의 redacted DB fingerprint 필드를 제거하는 것으로 끝난다. 제품 경로·계약·migration에는 롤백 대상이 없다.

## 5. hosted 실행 결과

PR #148 측정 head `3a1790ff3431706e81a2ba258eb0b26ea456ed31`의 run [36362386530](https://github.com/egparadise/SaintVision-Invion/actions/runs/36362386530)은 success다. artifact `saintvision-s05-legacy-staircase-36362386530`(ID `10945399201`)은 wave별 JSON/JUnit/log 27개와 aggregate JSON/JUnit을 보존한다. aggregate JUnit은 1 test, failure/error/skip 0이다.

| rung | 성공/실패 | P95 all 3회 | 중앙 | hold P95 중앙 | lock-wait P95 중앙 | timeout 최대 |
|---:|---:|---|---:|---:|---:|---:|
| 20 | 60/0 | 416.581 / 411.382 / 385.452ms | 411.382ms | 11.353ms | 212.943ms | 0 |
| 35 | 105/0 | 699.641 / 739.044 / 705.026ms | 705.026ms | 12.642ms | 438.854ms | 0 |
| 50 | 150/0 | 993.279 / 990.625 / 985.117ms | 990.625ms | 12.260ms | 561.842ms | 0 |

`55P03=0`, `57014=0`, request P95 all 중앙은 모두 2000ms 이하라 세 rung 모두 degrade=false다. 9개 wave fingerprint는 전부 유일하고 잔존 DB는 0이며 candidate 실행은 0이다. 사전 결정에 따라 `NO_DEGRADE_THROUGH_50_CLOSE_SEMAPHORE_LINE`으로 bounded semaphore 라인을 닫는다.

환경은 Ubuntu 24 hosted runner(image `20260920.314.1`), 4 CPU, 약 15.6GiB, Python 3.12.14, PostgreSQL 16.15, max connections 100이다. 로컬 수치와 직접 비교하지 않는다. S05-DB `in_progress`, 승격 없음이다.

첫 run `36362223316`은 fingerprint report의 Python import 누락으로 첫 wave JSON 전에 fail closed한 `INVALID_RUN`이며 어떤 수치도 쓰지 않는다.

정본 run `36362386530`은 #115 제품 tree(flag off, root-transaction lifecycle 포함)를 측정했다. integration tree의 legacy 수치는 run `36363327477`뿐이며, 그 c50 request P95 all 중앙값 `1558.406ms`의 2000ms gate까지 여유는 `441.594ms`다.

## 6. Card47 clean-base 재구성

#115와 #141은 병합하지 않는다는 코디네이터 결정에 따라 integration `1e8baf04` 위에서 제품 semaphore 의존을 제거했다. 가져온 최소 benchmark 변경은 schema 1.7 report에 DB 이름 대신 SHA-256 fingerprint·비노출·일회용 lifecycle 3필드를 더한 것뿐이다. `db.py`, `placement.py`, public contract, migration, `tools/placement_benchmark.py`는 integration base와 동일하다.

Card47 hosted run의 목적은 새 PR lane이 clean base에서도 같은 legacy 명령으로 실행된다는 **실행 호환성 확인**이다. `runPurpose=clean-integration-base-execution-compatibility`, `canonicalDecisionEvidenceRunId=36362386530`, `mayReplaceCanonicalDecision=false`를 JSON/JUnit에 고정한다. 새 수치로 위 §5의 정본 결론을 소급 변경하지 않는다.

PR #151 clean-base run [36363327477](https://github.com/egparadise/SaintVision-Invion/actions/runs/36363327477)은 9개 wave·aggregate JUnit을 success로 완료했다. 20/35/50 성공은 60/60·105/105·150/150, timeout 최대는 모두 0, P95 all 중앙은 665.154/1109.917/1558.406ms다. fingerprint 9개 유일·잔존 0이고 `semaphoreProductCodePresent=false`다. 이는 실행 호환성 확인일 뿐 §5 Card46 정본 수치와 직접 비교하거나 결론을 교체하지 않는다. artifact ID `10946163808`, 보존 JSON SHA-256 `1538dc3b303955f22f96f1cc7284df0822f2014b730eed8ad5ddaadd19f677c1`.

정본 run `36362386530`은 #115 제품 tree(flag off, root-transaction lifecycle 포함)를 측정했고, integration tree의 legacy 수치는 run `36363327477`뿐이다. integration c50의 2000ms gate 여유는 `441.594ms`이므로 정본 run의 더 큰 여유를 integration 경로 여유로 인용하지 않는다.
