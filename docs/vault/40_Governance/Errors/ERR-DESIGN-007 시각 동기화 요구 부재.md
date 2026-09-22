---
doc_id: "ERR-DESIGN-007"
title: "ERR-DESIGN-007 시각 동기화 요구 부재"
version: "2.0.0"
status: "accepted"
author: "Claude"
updated: "2026-09-22T17:25:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# ERR-DESIGN-007 시각 동기화 요구 부재

발견: 2026-09-09T15:45:31+09:00 / Agent: Claude / 종류: design / 상태: **채택(accepted) — 2026-09-22 결정 #7 선택지 A**(코디네이터, 사용자 위임). 아래 「개정 규격」이 정본이며 원문 제안(§제안)은 이력으로 남긴다.

## 문제

제품의 여러 안전·합격 조건이 **서로 다른 기계의 시계**에 의존하는데, 시각 동기화 요구가 어느 문서에도 없다. 24개 원문, 보완 5개, 최종 계획, ADR 전체를 통틀어 NTP·시계 스큐·단조 시계에 대한 서술이 확인되지 않는다.

시계에 의존하는 항목:

| 항목 | 근거 문서 | 의존하는 시계 |
|---|---|---|
| Lease `expiresAt` 판정 | ADR-005/006, [[DB 최종 개발 계획]] | Control Plane DB와 Node |
| Node 이탈 감지 ≤60초 | 합격 기준, AC-07 | Control Plane과 Node heartbeat |
| 승인 만료·일회용 nonce | ADR 인증 계약, [[Frontend 최종 개발 계획]] | Control Plane과 브라우저 |
| presigned URL 만료(업로드 1시간/다운로드 15분) | [[Storage 최종 개발 계획]] | Control Plane과 object store |
| 이벤트 전달 P95 ≤5초 측정 | [[Backend 최종 개발 계획]] | 서버와 브라우저 |
| Evidence `timestamp` 순서 | ADR-008 | 기록 주체 전부 |

전제는 "기존 Windows/Linux PC 5대"다. 사용자 소유 PC는 시계 관리가 보장되지 않으며, Windows 기본 동기화 주기는 느슨하다. 스큐가 수십 초면 다음이 발생한다.

- Node의 로컬 시계가 앞서면 Lease를 **조기 종료**해 정상 작업이 죽는다.
- Node의 시계가 뒤처지면 만료된 Lease를 계속 유효로 보고 **자원을 붙잡는다**. [[ERR-DESIGN-005 Lease 만료와 실제 자원 반환 동일시]]와 겹쳐 과예약이 된다.
- heartbeat 시각이 미래로 기록되면 이탈 감지가 지연되어 AC-07의 60초를 넘긴다.
- Evidence의 시간 순서가 뒤집혀 사고 조사에서 인과를 재구성할 수 없다.

## 영향

AC-05, AC-07, AC-04(승인 만료), AC-11(SLO 실측)이 모두 영향을 받는다. 특히 측정 지표가 스큐로 오염되면 **SLO 위반인지 시계 문제인지 구분할 수 없다.**

## 제안

S01-BE 또는 S01-DB의 계약에 다음을 추가한다.

1. **NTP 동기화를 Node 등록 전제조건으로 둔다.** Node Agent가 등록·heartbeat 시 로컬 시각을 함께 보고하고, Control Plane이 수신 시각과의 차이로 스큐를 계산한다.
2. **허용 스큐 한도를 정한다.** 초기값 제안 ±5초. 초과 노드는 `quarantined` 또는 스케줄 후보에서 제외하고 사용자에게 원인을 표시한다. 한도는 파일럿 실측으로 조정한다.
3. **Node는 만료를 절대 시각으로 판단하지 않는다.** Control Plane이 발급 시 `expiresAt`(절대)과 `ttlSeconds`(상대)를 함께 주고, Node는 수신 시점 기준 **로컬 monotonic clock**으로 잔여 시간을 재는 것을 정본으로 한다. 절대 시각은 교차 검증용으로만 쓴다.
4. **스큐를 관찰 지표로 노출한다.** `node_clock_skew_seconds`를 heartbeat마다 기록하고 한도 근접 시 경고한다.
5. S01의 5노드 조사표에 **시각 동기화 소스와 현재 스큐**를 미확인 값 목록의 항목으로 추가한다.

owner: Codex(S01 계약·장비 조사). 3번의 Node 측 구현은 Go Node Agent 범위다. 본 문서는 reviewer 지적이며 정정 여부는 owner가 판단한다.

## 개정 규격 (v2.0.0, 2026-09-22 채택 — 결정 #7 A)

개정안 원문·결함 분석·정합표는 [[2026-09-22_노드_시각_스큐_알람_ERR-DESIGN-007_규격개정안_Gemini]](Gemini). 채택으로 규격이 된 조항만 여기 둔다(규칙 5: 유효한 것은 한 곳). 구현 기록은 [[2026-09-22_결정7_시각스큐알람_활성화_구현_Claude]].

### 제1조 (목적)
Node와 Control Plane 간 시각 편차(clock skew) 허용 한계를 정하고, 시계 이상 노드의 작업 격리와 운영자 통지 절차를 확립하여 분산 임대(Lease)·스케줄링·이탈 감지의 무결성을 보장한다.

### 제2조 (스큐 측정 원칙)
1. Control Plane은 heartbeat 프로브를 수신할 때마다 Node 보고 시각과 서버 `clock_timestamp()`의 차이를 초 단위 `inv.nodes.clock_skew_seconds`(numeric)로 갱신한다.
2. `heartbeat_at`에는 Node 보고 시각이 아니라 서버 `clock_timestamp()`를 기록한다(`inv/observation.py`). 따라서 원문의 "미래 시각 heartbeat로 이탈 감지 지연" 실패 모드는 현 구현에서 발생하지 않는다([[설계 미결 3건 구현 영향 분석]] §3).

### 제3조 (런타임 적격성 가드 — 커널 정본)
1. 커널(`inv.scheduler`·`inv.placement`·`inv.leases`·`inv.containment`·`inv.dispatch`·`inv.tooling`)은 `clock_skew_seconds IS NULL`, 비유한 값, `abs(clock_skew_seconds) > 5.0` 중 하나면 그 노드를 스케줄링·배치·임대·실행 준비 적격에서 즉시 제외한다.
2. 이 ±5초 가드는 상시 유지하며 완화·우회하지 않는다. ±5초의 파일럿 장비 보정은 **이 규격의 개정 사유**이지 가드 해제 사유가 아니다.

### 제4조 (운영 알람 규격)
1. 알람명 `Node 시각 스큐 한도 초과` · 심각도 **P2** · 1차 대응 **인프라**(백업 Backend 운영) · 통지 **기록 채널** · **자동 조치 없음** · 근무 시간 내 대응(온콜 없음) — [[알람 라우팅과 대응 주체]]와 동일.
2. 트리거: `status='online'`인 노드 중 제3조 1항의 조건(미측정·비유한·`abs > 5.0`)에 해당하는 노드가 1대 이상이면 `firing=true`. 판정 술어는 커널 가드와 **동일한 한 함수**(`tools/alarm_check.py` `skew_outside_limit`)로 두어 알람과 가드가 어긋날 수 없게 한다.
3. 해제: 후속 heartbeat에서 `abs(clock_skew_seconds) <= 5.0`이 기록되면 다음 평가에서 즉시 `firing=false`(래치 없음).
4. offline/draining/quarantined 노드는 이 알람의 대상이 아니다(이탈 알람 관할).

### 원문 제안 중 채택하지 않은 것
- 제안 1(NTP를 Node 등록 하드 전제조건으로): 파일럿 5대(사용자 소유 PC)에서 강제 불가 → 채택 안 함. 스큐 측정·가드·알람으로 대체.
- 제안 3(Node 측 monotonic TTL 정본): 만료는 Control Plane DB의 `clock_timestamp()`가 통제하므로 불필요 → 채택 안 함.
- 제안 5(5노드 조사표에 시각 동기화 소스 항목): S01-ST 인수 입력에 남아 있음(별도).

## 구현 상태 판정 (Codex, 2026-09-22 — 채택 전 기록)

커널은 `clock_skew_seconds`가 없거나 비유한 값이거나 절댓값 5초 초과인 노드를 scheduler, placement, lease, containment 및 readiness 적격성에서 제외한다. 이 런타임 가드는 이미 운영 코드이므로 되돌리지 않는다. 되돌리면 스큐가 큰 노드가 배치·실행 경로에 진입할 수 있다.

이 구현 사실만으로 이 문서의 전체 제안이 채택된 것은 아니다. ±5초의 적정성은 파일럿 장비 측정으로 확인되지 않았고, NTP 전제·사용자 설명·알람 전달 및 담당 경로도 완결되지 않았다. 따라서 **런타임 적격성 가드는 유지**, **GOV-ALERT-001 시각 스큐 알람은 계속 governance-gated**로 판정한다. 알람 활성화는 장비 스큐 기준을 보정하고 채널·담당 및 대응 절차를 정한 뒤 별도 결정한다. 이 기록은 현재 구현과 미결 거버넌스를 분리하며 ERR-DESIGN-007 전체를 Accepted로 변경하지 않는다.

이것은 문서 검토에서 발견한 문제이며 실행 중 발생한 제품 사고가 아니다.
