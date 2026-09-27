---
doc_id: "CODEX-S05-BOUNDED-ADMISSION-DECISION-001"
title: "S05 bounded admission 후속 결정 제안"
version: "1.0.0"
status: "proposed"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T09:00:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S05-DB"]
tags: ["s05", "placement", "admission", "semaphore", "decision"]
---

# S05 bounded admission 후속 결정 제안

> [!summary] 권고
> **(a) N=4를 유지하고 bounded permit wait 450ms를 실험 arm으로 추가하며, (d) 빠른 admission reject와 SQL timeout을 별도 gate로 분리하되 기존 외부 실패 합계 gate는 유지한다.** 이는 운영 활성화 결정이 아니라 다음 hosted 20동시×3 wave 하나를 승인하기 위한 제안이다. flag 기본 off, S05-DB `in_progress`, 50동시·5노드·승격 금지는 유지한다.

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

낮은 candidate P95 all은 48건의 빠른 거절 효과라 개선으로 세지 않는다. 아래 산술은 hosted 관측 상한 `h=99.531ms`를 한 permit cohort의 근사 시간으로 사용한 **반증 가능한 예측**이다. 분산·DB 경합·scheduler 비용이 일정하다는 보장은 없다.

## 2. 선택지와 예상값

### (a) permit wait budget을 0ms보다 크게 둔다 — 권고 실험값 450ms

N=4에서 20개 barrier 요청은 최대 5개 cohort다. `W` 안에 끝나는 cohort 수를 `1+floor(W/h)`로 근사하면 다음과 같다.

| W | 예상 성공/빠른 거절 | 마지막 허용 cohort 대기 | 성공 P95 거친 상한 |
|---:|---:|---:|---:|
| 0ms | 4/16 | 0ms | 관측 361.228ms |
| 100ms | 8/12 | 99.531ms | 약 461ms |
| 200ms | 12/8 | 199.062ms | 약 560ms |
| 300ms | 16/4 | 298.593ms | 약 660ms |
| 450ms | 20/0 | 398.124ms | 약 759ms |

450ms는 `4×99.531=398.124ms`에 약 52ms 여유를 둔 값이다. 외부 실패 0을 만들 가능성은 있으나 legacy P95 401.090ms보다 느려질 가능성이 높다. 따라서 이는 성공을 기대한 승격 arm이 아니라 **성공률과 지연의 실제 교환비를 한 번에 반증하는 arm**이다. budget 만료는 기존 `RES-0007`/503/retryable이고 공개 계약은 바꾸지 않는다.

다음 wave가 20/20이 아니거나 P95 all 중앙이 legacy보다 악화되면 이 선택지는 기각한다. 20/20이어도 permit wait P95/max, cancellation cleanup, registry 잔존 0과 불변식이 모두 필요하다.

### (b) N을 조정한다 — 이번 결정에서는 보류

wait 0ms와 완전 동시 barrier를 그대로 두면 산술상 빠른 거절은 `20−N`이다.

| N | 예상 성공/빠른 거절 | 의미 |
|---:|---:|---|
| 4 | 4/16 | Card39 실측과 정확히 일치 |
| 8 | 8/12 | 외부 실패 gate는 여전히 실패 |
| 12 | 12/8 | 외부 실패 gate는 여전히 실패 |
| 16 | 16/4 | 외부 실패 gate는 여전히 실패 |
| 20 | 20/0 | admission 상한의 보호 효과가 사실상 사라짐 |

로컬 Card25 sampler-off 한 wave의 `h_max=234.974ms`에서는 N=4의 깊은 구간 `2h=469.948ms<500ms`, N=5는 `3h=704.922ms>500ms`였다. 이 값은 hosted와 직접 비교할 수 없지만 N 확대가 limit-row `55P03`을 다시 만들 수 있다는 위험 경계다. 다음 hosted wave에서 N만 높여 성공률을 맞추는 것은 DB 보호 목표를 훼손하므로 선택하지 않는다.

### (c) B′ lock budget으로 복귀한다 — 기각

로컬 Card24 observer-on B′=1500ms는 3회 합계 11/60 성공, `55P03` 49, P95 all 1785.486→2315.099ms, hold P95 141.932→767.708ms로 세 조건을 모두 실패했다. Card25 sampler-off 단일 wave는 20/20·timeout 0이었지만 P95 all 2014.409ms, hold P95/max 155.873/234.974ms였고 단일 로컬 wave다.

관측자 효과 때문에 두 결과가 갈렸으므로 hosted B′ 1500ms×3은 기전을 반증할 수 있다. 그러나 이미 실패한 방향으로 정책을 되돌릴 근거는 아니며 Card42의 다음 wave로 선택하지 않는다. `statement_timeout=2s`와 맞닿는 1900ms arm도 제외한다.

### (d) gate 1을 빠른 거절과 timeout으로 분리한다 — 진단용 채택, 완화는 금지

Card39를 분리하면 SQL timeout gate는 `0≤0`으로 통과하지만 admission reject는 `48>0`, 비율 80%로 실패한다. 분리 자체는 병목이 DB timeout인지 admission 정책인지 보여 주지만, admission reject를 제외하면 12/60 성공 후보가 green이 되는 fail-open이다.

따라서 다음 report는 `admissionRejectCount`와 `sqlTimeoutCount(55P03+57014)`를 각각 gate로 내되, 합계 `externalFailureCount` 비증가를 계속 blocking gate로 유지한다. client retry 수렴 시간·시도 상한·최종 성공률의 계약과 SLO가 별도 결정되기 전에는 retryable 503을 성공으로 바꾸어 세지 않는다.

## 3. 다음 hosted wave가 반증할 것

Claude 검토와 코디네이터 결정 뒤에만 다음 한 arm을 실행한다.

- legacy(flag off) 20동시×3 뒤 candidate(N=4, permit wait 450ms, lock budget 500ms) 20동시×3, 한 wave씩 순차 실행
- JSON/JUnit: all/success P95, permit wait/hold P50·P95·max, admission reject, `55P03`, `57014`, in-use/queue depth, cancellation/release cause, registry residue
- 통과 조건: `externalFailureCount(candidate)≤legacy`, P95 all 중앙 비악화, 성공 hold P95 중앙 비악화, 불변식 전부 true
- 반증: 성공 20/20 미달, P95 all 악화, SQL timeout 재등장, permit/registry 잔존, replay·fencing·RLS·no-overbooking 회귀 중 하나라도 발생

예측은 candidate 20/20·외부 실패 0, P95 all 약 759ms다. **따라서 외부 실패 조건은 좋아질 수 있으나 P95 조건은 실패할 가능성이 높다.** 실측이 이를 뒤집으면 queueing 모델 또는 `h` 안정성 가정이 틀린 것이다. hosted runner 수치는 로컬 Card24/25나 물리 5노드 AC-05와 직접 합치지 않는다.

## 4. 불변식·롤백·결정 요청

- 공개 route/schema/ProblemDetails 변경 0. timeout 표면은 계속 `RES-0007`/503/retryable다.
- tenant+project 격리, exact replay/changed-body 409, fencing/epoch, RLS, no-overbooking, root transaction 종료 뒤 release를 보존한다.
- process-local 한계와 multi-CP에서 최악 `P×N`은 그대로다. global FIFO나 운영 공정성을 주장하지 않는다.
- rollback은 permit wait 설정을 0ms로 되돌리고 flag를 off로 유지하는 것이다. migration·DB cleanup은 없다.

결정 요청:

- [ ] 권고 승인: (a) N=4/W=450ms 실험 + (d) 분리 계측/합계 blocking gate
- [ ] 대안: (b) N 조정 — 승인 N과 위험 수용 근거 필요
- [ ] 대안: (c) hosted B′ 1500ms 재검증 — semaphore 실험보다 우선할 이유 필요
- [ ] 보류: legacy/flag off 유지, 추가 wave 없음

근거: [[S05 project별 bounded semaphore 사양]], [[S05 hosted 20동시 wave opt-in lane 사양]], [[2026-09-23_12-20-00_KST_S05_Bprime_구현_교정실험_Codex]], [[2026-09-23_13-28-00_KST_S05_bounded_semaphore_사양_Codex]], [[2026-09-28_08-35-00_KST_S05_hosted_20동시_wave_Codex]].
