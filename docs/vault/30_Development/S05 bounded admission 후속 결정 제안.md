---
doc_id: "CODEX-S05-BOUNDED-ADMISSION-DECISION-001"
title: "S05 bounded admission 후속 결정 제안"
version: "1.2.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T16:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["s05", "placement", "admission", "semaphore", "decision"]
---

# S05 bounded admission 후속 결정 제안

> [!summary] 코디네이터 결정
> **W=450ms를 포함한 모든 permit wait `W>0` arm은 실행하지 않는다. 세 판정 gate는 바꾸지 않고, 다음 측정은 legacy(flag off)만 20→35→50 동시로 높여 실제 degrade 지점을 찾는다.** 첫 degrade 지점이 확인될 때만 candidate(W=0) 비교 arm을 별도로 제안한다. 50동시까지 degrade가 없으면 semaphore 라인을 "현 hosted 부하에서 불필요"로 닫고 legacy를 확정한다. flag 기본 off, S05-DB `in_progress`, 승격 없음은 유지한다.

## 1. 확정된 입력

hosted Card39 run [36359052826](https://github.com/egparadise/SaintVision-Invion/actions/runs/36359052826)은 같은 runner 안에서 legacy와 candidate-B를 비교했다. 측정 제품 SHA는 PR #115 `08f4a6a9…`다.

| 입력 | legacy | candidate-B, N=4·wait 0ms |
|---|---:|---:|
| 20동시×3 성공 | 60/60 | 12/60 |
| semaphore reject / SQL timeout | 0 / 0 | 48 / 0 |
| request P95 all 중앙 | 401.090ms | 350.460ms |
| request P95 success 중앙 | 401.090ms | 361.228ms |
| post-acquire hold P95 중앙 | 12.428ms | 12.232ms |
| permit hold P95, wave별 | n/a | 99.531 / 94.159 / 99.295ms |
| permit hold max, wave별 | n/a | 99.531 / 94.159 / 99.295ms |

candidate는 wave마다 허용 표본이 4개뿐이라 nearest-rank P95와 max가 같다. 따라서 이후 산술에서 hosted 관측치는 P95라는 모호한 `h`가 아니라 **`h_obs_max=99.531ms`**로 쓴다. 로컬 Card25의 별도 관측은 **`h_local_max=234.974ms`**이며 hosted 값과 합치지 않는다. 낮은 candidate P95 all은 48건의 빠른 거절 효과이므로 개선으로 세지 않는다.

## 2. Claude F1~F6 검토와 결정

### F1·F5 — max 기준과 기호 정정

N=4에서 20 요청을 다섯 cohort로 모두 받아들이려면 마지막 cohort가 네 구간을 기다린다. wait budget `W`가 허용하는 구간당 최대값을 **`h_limit(W)=W/4`**로 정의한다.

| 항목 | 값 | 해석 |
|---|---:|---|
| Card39 hosted `h_obs_max` | 99.531ms | 즉시 거절 16건이 존재한 n=4 관측 max |
| W=450ms의 `h_limit(W)` | 112.500ms | `W/4`; `h_obs_max` 대비 여유 12.969ms(약 13%) |
| W=450ms에서 관측 max를 단순 반복한 마지막 대기 | 398.124ms | `4×99.531`; W>0 arm의 안전성 증거가 아님 |
| Card25 local `h_local_max` | 234.974ms | 다른 환경·다른 arm의 max; hosted 예측에 대입 금지 |

W=450 예측은 나머지 16건이 즉시 거절된 상태의 `h_obs_max`를 20건 생존 상태로 외삽하므로 20/20을 보장하지 않는다. `h_obs_max`가 13%만 커져도 `h_limit(450)`을 넘는다. v1.0의 "permit hold P95 상한"과 `h`/`h_max` 혼용은 철회한다.

### F2 — 현재 구현에서 W>0은 transaction/row-lock 위험을 만든다

현재 candidate는 루트 트랜잭션 안에서 `approvals._ledger()`가 `inv.idempotency ... FOR UPDATE`를 수행한 뒤 project permit을 얻는다. `lock_timeout` 설정도 permit 획득 뒤다. 따라서 W>0 대기는 statement timeout의 보호를 받지 않는 idle-in-transaction 구간이며 다음 위험이 있다.

- 서로 다른 key라도 connection/worker를 W 동안 점유한다.
- 같은 key replay는 선행 요청의 idempotency row lock에 막혀 별도 `55P03`/`57014`를 만들 수 있다.
- limit-row 도착 분산은 `55P03`을 줄일 수 있지만, 그 개선이 replay 잠금·pool 점유 위험을 상쇄하지 않는다.
- replay-before-permit과 wait-outside-transaction을 동시에 보존하려면 별도 설계가 필요하다. 설정 rollback만으로 충분한 작은 변경이라고 주장하지 않는다.

따라서 permit 위치·공정성·queue cap·취소·단조 시계·외부 timeout 관계를 먼저 설계하지 않은 W>0 구현과 측정은 금지한다.

### F3 — gate 2는 모든 W>0에서 구조적으로 실패한다

Card39 candidate success P95는 361.228ms다. 두 번째 cohort를 허용하는 순간 관측 max 한 구간만 더해도 `361.228+99.531=460.759ms`로 legacy P95 401.090ms를 넘는다. 즉 성공 수를 늘리면서 request P95 all 비악화를 지키는 W>0은 현재 근거 안에 존재하지 않는다.

결과가 정해진 W=450 arm은 실행하지 않는다. 데이터를 본 뒤 gate를 바꾸지 않으며, 세 gate를 다음처럼 유지한다.

1. `externalFailureCount(candidate) ≤ externalFailureCount(legacy)` — admission reject 포함
2. request P95 all 중앙 비악화
3. 성공 hold P95 중앙 비악화

### F4 — 20동시 legacy에는 admission이 풀 문제가 없다

Card39 legacy는 60/60 성공, 외부 실패 0, SQL timeout 0, P95 all 401.090ms였다. 이 조건에서 admission은 순수 비용이다. 따라서 다음 질문은 "W가 얼마인가"가 아니라 **legacy가 어느 hosted 부하에서 처음 degrade하는가**다.

### F6 — 진단 분리는 유지하고 fail-open은 금지한다

`admissionRejectCount`와 `sqlTimeoutCount(55P03+57014)`는 계속 분리 기록한다. 그러나 합계 `externalFailureCount` 비증가를 blocking gate로 유지한다. retry 수렴 시간·시도 상한·최종 성공률 SLO가 정해지기 전에는 retryable 503을 성공으로 세지 않는다.

## 3. 선택지 판정

### (a) bounded permit wait W>0 — 기각, 실행 금지

게이트 2가 모든 W>0에서 확정 실패하고 현재 permit 위치가 idempotency row lock을 잡은 채 대기하게 하므로 W=450 arm을 포함해 실행하지 않는다.

### (b) N 조정 — 보류

wait 0ms의 완전 동시 barrier에서 빠른 거절은 구조적으로 `20−N`이다. N=20은 상한 보호를 없앤다. legacy가 degrade하는 지점을 찾기 전에 N을 높이지 않는다.

### (c) B′ lock budget 복귀 — 기각 유지

Card24 observer-on B′=1500ms는 세 조건을 모두 실패했고 Card25 sampler-off는 단일 로컬 wave다. hosted legacy degrade 지점 없이 실패한 방향으로 돌아가지 않는다.

### (d) 빠른 거절과 SQL timeout 분리 — 진단용 채택, gate 완화 금지

분리 계측은 병목 분류에 쓰되 합계 외부 실패 gate는 그대로 blocking이다.

### (e) legacy-only hosted staircase — 다음 측정으로 채택

다음 카드는 Card39와 같은 opt-in hosted PostgreSQL 16 lane에서 **legacy(flag off)만** 20→35→50 동시 순서로 실행한다. lane 구현과 실행은 이 v1.1 승인 뒤 별도 카드다.

## 4. legacy staircase 사전 등록

### 실행 순서

- 각 wave는 별도 pytest session이 만든 새 일회용 DB를 사용한다. 따라서 rung마다 새 DB라는 하한보다 강하게 9개 wave가 모두 서로 다른 DB fingerprint를 가져야 하며 wave 전후 `inv_test_%` 잔존은 0이어야 한다.
- 한 rung의 세 wave를 끝낸 뒤 아래 degrade 기준을 판정한다. degrade면 더 높은 rung은 실행하지 않는다.
- 제품 SHA, runner OS/CPU, PostgreSQL 버전과 `lock_timeout=500ms`·`statement_timeout=2000ms`, wave별 JSON/JUnit을 artifact로 보존한다.
- candidate, permit wait, B′ arm은 이 lane에서 실행하지 않는다. 제품 flag는 off다.

### 실행 전 고정한 degrade 기준

다음 중 하나면 해당 concurrency를 **첫 degrade 후보**로 판정한다.

1. 세 wave 중 하나라도 `externalFailureCount = 55P03 + 57014 > 0`
2. 세 wave의 request P95 all 중앙값이 **2000.000ms 초과**

기준 1은 드문 timeout 한 건도 숨기지 않도록 세 wave의 **최대값(any wave)**을 쓰고, 기준 2는 지연의 대표값을 보도록 세 wave의 **중앙값**을 쓴다. 이 혼용은 의도적이다. 기준 2는 단일 SQL의 `statement_timeout=2000ms`와 같은 숫자를 쓰지만, 여러 statement·트랜잭션 경계를 포함한 **요청 전체 누적 경로 전용 기준**이다. 그러므로 개별 statement가 2초 전에 끝나 `57014=0`이어도 요청 P95 all 중앙값은 2초를 넘을 수 있다. 측정 뒤 임계나 집계 방식을 바꾸지 않는다.

hold P95/max와 legacy lock-wait P95/max는 반드시 기록하지만 degrade trigger는 아니다. workflow/service-container/pull/setup 실패는 제품 degrade가 아니라 `INVALID_RUN`이며 같은 rung 재실행에는 별도 코디네이터 승인이 필요하다.

### 결과에 따른 다음 결정

- 20 또는 35에서 degrade: 해당 rung에서 중단하고 같은 concurrency의 candidate(W=0, N 후보) 비교 사양을 세 gate와 함께 별도 제안한다.
- 50에서 degrade: 50의 세 wave까지 보존하고 같은 concurrency candidate 비교를 별도 제안한다.
- 50까지 degrade 없음: 측정한 hosted 범위에서 admission이 풀 문제가 없으므로 semaphore 라인을 닫고 legacy(+기존 fail-fast)를 확정한다. flag는 off로 남긴다.

첫 degrade 후보는 candidate 승격이나 AC-05 판정이 아니다. candidate 비교·50 초과·5노드 측정은 각각 별도 승인 대상이다.

## 5. 불변식·경계·결정 기록

- 공개 route/schema/ProblemDetails, migration, registry 상태 변경 0.
- exact replay/changed-body 409, fencing/epoch, RLS, no-overbooking 불변식은 후속 candidate 비교에서도 유지한다.
- 세 판정 gate는 유지하며 측정 뒤 재정의하지 않는다.
- flag 기본 off, S05-DB `in_progress`, 운영 활성화·승격 없음이다.
- v1.1은 docs-only이고 wave·제품·workflow 변경을 포함하지 않는다.

결정 기록:

- [x] (a) W=450 포함 W>0 arm 실행 안 함
- [x] (d) 진단 분리 + 합계 외부 실패 blocking gate 유지
- [x] (e) legacy-only 20→35→50 hosted staircase를 다음 별도 카드로 채택
- [x] flag off·S05 `in_progress`·승격 없음

근거: [[S05 project별 bounded semaphore 사양]], [[S05 hosted 20동시 wave opt-in lane 사양]], [[2026-09-23_12-20-00_KST_S05_Bprime_구현_교정실험_Codex]], [[2026-09-23_13-28-00_KST_S05_bounded_semaphore_사양_Codex]], [[2026-09-28_08-35-00_KST_S05_hosted_20동시_wave_Codex]], [[2026-09-28_09-00-00_KST_S05_bounded_admission_후속결정_Codex]].
