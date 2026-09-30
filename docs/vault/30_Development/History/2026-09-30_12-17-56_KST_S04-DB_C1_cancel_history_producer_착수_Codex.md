---
doc_id: "HISTORY-20260930-CARD159-S04-C1-CANCEL-PRODUCER-CODEX"
title: "Card 159 S04-DB C1 core 취소 이력 producer 착수"
version: "1.0.0"
status: "in_progress"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-30T12:17:56+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "6fc0428b49f28379cb4da17830d92256b55c2eb2"
task_ids: ["S04-DB"]
tags: ["card-159", "s04-db", "c1", "cancel", "audit", "fail-closed"]
---

# Card 159 S04-DB C1 core 취소 이력 producer 착수

## 선택

- 카드: **CARD-159 — S04-DB C1 core 취소 이력 producer**.
- 기준 branch와 SHA: `origin/integration/all-agents-unified` @
  `6fc0428b49f28379cb4da17830d92256b55c2eb2`.
- 부모 task: **S04-DB** (`review`, owner Codex, reviewer Claude).

## 다음 카드로 고른 이유

`docs/task-registry.json`과
`docs/vault/30_Development/57.81퍼센트 이후 단일 가상 컴퓨터 보강 로드맵.md`,
그리고 `docs/vault/30_Development/S04-DB_S08-DB_운영_판정_기준.md`를
대조했다. S04-DB는 고난도 Codex 범위 중 가장 앞선 sprint이고, 기존 C1
collector는 approval·expiry·workload digest를 전수 판정하지만 core 제품에
정본 취소 audit producer가 없어 깨끗한 결과도 `NOT_OBSERVED`로 내린다.

이 공백은 추가 PC·CP hostname·물리 Node 없이 현재 제품 transaction과
hosted PostgreSQL에서 닫을 수 있다. 뒤의 S05 동시성·S07 분산 복구·S08 PITR
카드는 각각 물리 5노드 또는 별도 장애 영역 의존이 남아 있으므로, 먼저
S04의 취소 상태 전이와 append-only audit 원장을 원자적으로 결속한다.

## 사전 결정

1. 첫 non-terminal → `cancelled` 전이만
   `public.audit_events.action='run.cancel.requested'` 1행을 같은 transaction에
   기록한다.
2. 이미 취소된 run의 replay는 상태와 기존 audit를 그대로 반환하며 새 audit를
   만들지 않는다.
3. audit insert가 실패하면 취소 상태 전이도 commit되지 않아야 한다.
4. evidence에는 tenant/run/user ID나 detail 원문을 내보내지 않고 집계만 남긴다.
5. producer 코드의 존재는 운영 배포 identity나 과거 row coverage의 증거가
   아니다. 따라서 배포 SHA와 관측 시작 시각이 독립적으로 결속되기 전의 clean
   C1은 `RECORDED_ONLY`이며 `MEASURED_PASS`로 승격하지 않는다.
6. C1-K의 execution-time epoch history처럼 producer가 없는 경계는 계속
   `NOT_REGISTERED`/`NOT_OBSERVED`로 남긴다. CARD-159가 그 값을 합성하지 않는다.

## 구현·검증 계획

- 제품 service에 actor·trace를 명시적으로 받는 canonical cancel audit producer를
  추가한다.
- PG-free 단일 파일에서 action 상수, 1회 기록, replay 중복 방지, audit 오류 전파,
  collector exact binding 변이를 고정한다.
- hosted PostgreSQL 단일 파일에서 상태와 audit의 원자성·RLS 경계를 확인한다.
- 기존 S04/S08 collector는 source를 `absent`에서 canonical action으로 바꾸되,
  배포 결속 전 clean 결과는 `RECORDED_ONLY`로 제한한다.
- 공개 HTTP/JSON 계약과 migration은 변경하지 않는다. S04-DB는 `review`를 유지한다.

