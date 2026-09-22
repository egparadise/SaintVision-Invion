---
doc_id: "HIST-CODEX-S05-CARD25-BOUNDED-SEMAPHORE-SPEC-001"
title: "S05 Card25 project별 bounded semaphore 사양"
version: "1.2.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T14:15:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["history", "s05", "semaphore", "fail-fast", "specification"]
---

# S05 Card25 project별 bounded semaphore 사양

## 작성 결과

Card24 B′ 실험이 외부 timeout 0→49, request P95(all) 1785.486→2315.099ms, hold P95 141.932→767.708ms로 세 조건을 모두 실패한 뒤 후속 옵션 B를 docs-only로 사양화했다. 구현·시험·부하·migration·공개 계약 변경은 0건이다.

초안은 기본 lock budget 500ms와 Card24 `h≈767.708ms`를 근사식에 넣어 N=2를 제안했다. Claude 카드 28 F-1에 따라 이 확정을 철회했다. Card24는 queue observer를 켠 상태였고 실제 sampler interval이 legacy 약 21ms에서 candidate 약 67~89ms로 느려졌으며, `pg_blocking_pids`의 lock 파티션 비용이 holder 진행을 지연했을 수 있다. sampler-off 카드 16/18 candidate hold는 117~171ms였다. 따라서 767.708ms는 observer 포함 상한이고 N=2는 검토 전 fail-closed fallback일 뿐이다.

승인된 sampler-off candidate 1500×1은 SHA `6c389a1d`에서 1 passed/16.36s/exit 0, 20/20 성공, `55P03`·`57014` 0이었다. request P95/max는 2014.409/2060.953ms, limit-row wait P95/max는 1409.694/1451.526ms, hold p50/p95/max는 55.469/155.873/234.974ms였다. fencing 유일성과 no-overbooking은 true, queue/sql diagnostic은 off, disposable DB·신규 role 잔존은 0이다.

observer-on P95 767.708ms 대비 sampler-off 155.873ms는 611.835ms 작고 약 4.925배 차이다. 동일 하네스의 diagnostic on/off에서 측정이 크게 달라져 **F-1 관측자 효과는 확인**됐고 767.708ms는 관측자 포함 상한으로 유지한다. 다만 단일 wave의 나머지 변동까지 모두 `pg_blocking_pids` 하나의 비용으로 단정하지 않는다. 보수적으로 sampler-off max를 쓰면 N=4의 최장 예상 구간 `2×234.974=469.948ms`는 500ms 안이고 N=5의 `3×234.974=704.922ms`는 넘는다. 따라서 첫 candidate-B 실험값은 N=4, N=3은 reviewer 요청 시 lower arm이다. permit은 대기 queue 없이 논리적 wait budget 0ms다. candidate-B 20동시×3에서 실제 55P03과 semaphore reject를 함께 세기 전 zero-timeout은 주장하지 않는다. [[s05-card25-sampler-off-6c389a1d.json]].

Card25 종료 확인은 `inv_test_*` DB 0건, `inv_app_*` role 2건이다. role 2건은 실행 전부터 존재했고 종료 뒤에도 같아 신규 role 잔존은 0이다. Claude 카드 32는 sampler-off candidate 1500×1 재현 wave 1회를 실행 조건으로 검토한다. 재현 전에는 N=4를 구현 실험값 이상으로 승격하지 않는다.

## 핵심 경계

- canonical `(tenant_id, project_id)`별 process-local non-blocking permit이며 상한 초과는 즉시 기존 `RES-0007`/503/retryable이다.
- commit된 exact replay는 permit을 소비하지 않고 changed-body 409를 유지한다. 신규 reject는 idempotency·Lease·event 잔존 0이어야 한다.
- permit은 placement 함수 반환이 아니라 root transaction commit/rollback 뒤 반환한다. `BoundDatabase`·savepoint의 조기 release를 금지하고 cancel/exception/BaseException까지 finalizer를 요구한다.
- process P개면 전역 허용량은 최악 `P×N`이다. 전역 FIFO·공정성·multi-CP 상한·failover queue를 보장하지 않는다.
- metric은 semaphore reject와 SQL timeout을 분리하되 성능 게이트의 외부 실패 합계에는 둘 다 포함한다. 빠른 503으로 timeout을 이름만 바꿔 통과시키지 않는다.

## 예정 검증과 비주장

Claude 승인 뒤에만 PG-free 단위 시험과 disposable 실 PG focused 시험을 작성한다. legacy와 candidate-B(N=4, budget 500)를 20동시 각 3회 비교하며, 외부 실패 합계 비증가·전체 요청 P95 비악화·성공 request hold P95 비악화 세 조건을 모두 요구한다. N=3 lower arm, N=5 이상, 20동시 초과, 50동시, 물리 5노드는 승인되지 않았다.

이 문서는 B가 성공할 것이라는 결론이 아니다. N=4는 20 barrier 요청 중 최대 16개를 즉시 거절할 수 있어 성능 게이트 실패 가능성이 있다. 현재 상태는 `placementShortCommit=false`, B flag off, candidate budget 기본 500ms, S05-DB `review`다. 정본 사양은 [[S05 project별 bounded semaphore 사양]]이다.
