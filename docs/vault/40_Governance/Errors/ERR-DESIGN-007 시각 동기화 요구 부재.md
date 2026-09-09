---
doc_id: "ERR-DESIGN-007"
title: "ERR-DESIGN-007 시각 동기화 요구 부재"
version: "1.0.0"
status: "open"
author: "Claude"
updated: "2026-09-09T15:45:31+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# ERR-DESIGN-007 시각 동기화 요구 부재

발견: 2026-09-09T15:45:31+09:00 / Agent: Claude / 종류: design / 상태: 검토 지적, owner 판단 대기

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

이것은 문서 검토에서 발견한 문제이며 실행 중 발생한 제품 사고가 아니다.
