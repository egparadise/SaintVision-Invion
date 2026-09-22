---
doc_id: "ERR-DESIGN-008"
title: "프로젝트 배치 잠금과 관측 freshness 충돌"
version: "1.0.0"
status: "open"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-22T23:30:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["placement", "concurrency", "freshness", "postgresql", "S05-DB", "F-S05-01"]
---

# ERR-DESIGN-008 프로젝트 배치 잠금과 관측 freshness 충돌

> [!warning] 상태
> 설계 위험 가설 · 50동시 미측정 · Claude 설계 검토와 코디네이터 결정 전 구현 금지

## 문제

`PlacementStore.reserve`는 idempotency ledger와 Run을 잠근 뒤 `inv.projects`를 `FOR NO KEY UPDATE`로 잠그고, 프로젝트 limits와 후보 Node/Resource를 잠근 상태에서 권한·membership·grant·관측 freshness·제공량·활성 Lease를 확인하고 Lease·event·idempotency 응답을 한 트랜잭션으로 기록한다. 원자성과 project ceiling에는 안전하지만 같은 project의 독립 요청도 긴 project 단위 임계구역에서 직렬화한다.

Claude PR #71 검토로 기존 “50동시 `RES-0003` 실측”은 철회됐다. 최초 하네스는 `NodeResourceSnapshot` 계약을 위반해 placement 경로에 도달하지 못했고 report 호출도 TypeError였다. 교정 SHA `7569c418`의 유효 측정은 개발 PC 1대·합성 Node에서 3동시 P95 **861.651ms**, 10동시 **1,738.762ms**, 각 두 라운드 전부 성공이다. 50동시는 실행하지 않았다.

다만 코드상 위험은 남는다. project lock 뒤 현재 시각을 읽고 15초 snapshot freshness를 검사하므로 project 직렬 구간이 15초를 넘으면 후순위 요청은 `RES-0003`이 될 수 있다. 10동시가 AC-05 2초 한도에 근접해 위험 근거는 강하지만, 50동시 성공·실패·P95는 미측정이다.

## 영향

- project row만 제거해도 `project_resource_limits FOR UPDATE`가 긴 writer mutex로 남으면 병목은 사라지지 않는다.
- 잠금을 잘못 줄이면 ceiling 초과, 같은 Run의 이중 Lease, 폐기된 권한으로 예약, stale epoch fencing 발급, ledger/Lease 분리가 생길 수 있다.
- batch API는 lock 횟수를 줄일 수 있지만 “50개의 독립 요청” AC와 공개 계약을 바꾼다.
- freshness 확대는 queueing을 줄이지 않고 stale 결정을 허용해 실패만 숨길 수 있다.

## 제안

[[2026-09-22_S05_배치잠금_입도_결정제안_Codex]]에서 다음을 비교한다.

1. speculative read 뒤 짧은 commit 임계구역에서 전체 재검증 — Codex 우선 권고
2. 1~50 item all-or-nothing batch 예약 API — 공개 계약 대안
3. freshness 확대/요청 진입 시각 고정 — 기각

## 소유 경계

- owner: Codex — 커널 설계·구현·회귀시험
- reviewer: Claude — fencing/epoch·원자성·교착·RLS·5노드 검증 독립 검토
- decision: 코디네이터 — 옵션 선택과 구현 카드 배정
