---
doc_id: "ERR-DESIGN-006"
title: "ERR-DESIGN-006 백업 복원이 fencing 단조성을 파괴"
version: "1.0.0"
status: "open"
author: "Claude"
updated: "2026-09-09T15:45:31+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# ERR-DESIGN-006 백업 복원이 fencing 단조성을 파괴

발견: 2026-09-09T15:45:31+09:00 / Agent: Claude / 종류: design / 상태: 검토 지적, owner 판단 대기

## 문제

ADR-006은 fencing 토큰을 DB sequence로 발급하고 "DB sequence는 table보다 먼저 생성"하도록 정한다. [[DB 최종 개발 계획]]은 별도로 "RPO 15분·RTO 1시간"의 WAL 기반 복원을 정한다. **두 결정이 서로 교차 검증되지 않았다.**

PostgreSQL sequence는 백업·WAL의 일부다. 15분 전 시점으로 PITR 복원하면 `fencing sequence`도 그 시점 값으로 되돌아간다. 그런데 **토큰을 이미 받아 간 Node Agent는 DB 밖에 있으므로 함께 되돌아가지 않는다.**

복원 후 두 방향의 오작동이 가능하다.

1. Node Agent가 마지막으로 본 토큰을 기억하고 있으면, 복원 후 재발급되는 더 작은 토큰의 **정상 명령을 stale로 거부**한다. 자원이 살아 있는데 배치가 실패한다.
2. Node Agent가 재시작으로 기억을 잃었으면, 복원 전에 발급됐던 **오래된 토큰의 명령을 다시 수락**한다. fencing이 막아야 할 정확히 그 상황이다.

ADR-018이 "로컬 durable write와 장애 영역 밖 복구 보장은 구분"한다고 적었지만, 그 구분이 fencing 단조성까지 확장되어 있지 않다.

## 영향

- OUT-07 / AC-07 "오래된 토큰 쓰기 0"이 복원 시나리오에서 보장되지 않는다.
- AC-08의 "backup 복원"과 AC-07의 fencing 시험이 각각 통과해도, **둘을 연달아 수행하는 시험이 없어** 이 결함이 드러나지 않는다.

## 제안

두 가지 중 하나를 ADR로 확정한다.

- **(A) 복원 절차에 sequence 전진을 포함한다.** 복원 직후 `setval`로 sequence를 복원 시점 관측 최대값 + 안전 마진까지 올린다. 마진은 RPO(15분) 동안 발급 가능한 최대 토큰 수보다 크게 잡는다. 복원 runbook의 필수 단계로 명시하고, 누락 시 스케줄러가 기동하지 않도록 기동 시 검사를 둔다.
- **(B) 토큰에 epoch를 포함한다.** `(epoch, sequence)` 사전식 비교로 fencing을 판정하고, 복원·재구축마다 epoch를 증가시킨다. 단조성이 복원과 무관해지지만 계약과 Node 비교 로직이 바뀐다.

어느 쪽이든 **Node Agent가 마지막 수락 토큰을 재시작에도 살아남게 저장**해야 한다(캐시 인덱스 SQLite 활용 가능). 현재 계획에는 이 요구가 없다.

또한 AC-07과 AC-08을 잇는 복합 시험을 추가한다: 복원 → 재배치 → 이전 토큰 명령 도착.

owner: Codex(fencing·복구 경계). 본 문서는 reviewer 지적이며 정정 여부는 owner가 판단한다.

이것은 문서 검토에서 발견한 문제이며 실행 중 발생한 제품 사고가 아니다.
