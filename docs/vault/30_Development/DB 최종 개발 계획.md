---
doc_id: "PLAN-DB-001"
title: "DB 최종 개발 계획"
version: "1.0.0"
status: "baseline"
author: "Codex"
updated: "2026-09-09T15:10:54+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# DB 최종 개발 계획

책임: **Claude; 동시성·불변 조건 Codex**. 공통 기준은 [[최종 개발 계획 - 모든 개발의 지침]], 주차별 작업은 [[24주 통합 실행 계획]]을 따른다.


## 모델과 Migration

PostgreSQL을 상태 정본으로 사용한다. Claude의 물리 테이블 목록을 출발점으로 users/roles/projects/workspaces, nodes/resources/offers/snapshots, workloads/runs/run_attempts/steps/checkpoints, leases/allocations, context, approvals/evidence/outbox/inbox, dataset/model 메타데이터를 구현한다. 미작성 FK 대상·생성 순서는 S01 ERD와 첫 Alembic migration에서 검증한다.

주요 ID는 prefix+ULID text, tenant는 UUID, traceId는 32자리 hex 문자열이다. 공통 시간은 UTC timestamptz, 사람 기록은 KST다. 엔티티 version 정수와 계약 SemVer를 구분한다. nullable device_index·정본 node_id의 unique는 NULL 중복까지 막는 제약을 사용한다.

## Lease와 실행 불변 조건

각 예약 트랜잭션은 node 행 → resource ID 오름차순으로 `SELECT FOR UPDATE` 잠금을 획득한다. 잠금을 얻은 뒤 별도 statement에서 현재 Offer·활성 예약을 다시 읽고 availability를 검사해 예약한다. Offer 변경·node drain·갱신·반납도 같은 순서로 잠근다. 여러 자원은 전부 성공하거나 전부 rollback한다. 한 자원만 예약해도 잠금을 생략하지 않는다.

fencing sequence를 table보다 먼저 생성한다. allocation slice별 토큰·lease 상태·expiresAt을 Node와 결과 저장 경계에서 검증한다. 만료 lease의 늦은 결과가 새 결과를 덮어쓰지 못한다. RunAttempt에는 재시도마다 snapshot/placement/fence/구성 버전이 남는다.

Evidence INSERT + 성공 전이 + outbox는 하나의 트랜잭션이다. 성공은 검증 결과와 필요한 Evidence가 모두 있을 때만 허용한다. Evidence app role은 UPDATE/DELETE 불가, 감사 운영 role은 별도이며 DB superuser까지 완전 WORM이라고 주장하지 않는다.

## 권한·검색·보존

tenant 테이블은 ENABLE/FORCE RLS, WITH CHECK, 비owner app role, transaction-local tenant scope를 사용한다. project 권한도 서비스·조회 경계에서 검증한다. 다른 tenant 자원 FK가 연결되지 않도록 composite ownership 제약을 둔다.

Context는 lexical+metadata+권한/TTL 필터부터 시작한다. versioned item과 실제 redacted snapshot/hash를 보존한다. mutable item ID만 보존해서 재현 가능하다고 주장하지 않는다. pgvector는 필요성·모델·차원이 검증된 후 migration한다.

Evidence/audit는 1년, 자원 snapshot·일반 로그는 90일, RunRecord·release lineage는 프로젝트 수명 동안 보존한다. Evidence 참조 Artifact의 보존 pin을 Storage와 함께 검사한다. partition 생성은 월간 관리 작업으로 자동화하고 실패·용량 알람을 둔다.

## 복구·검증

일일 base backup, 지속 WAL, 35일 보존, 별도 장애 영역 대상. RPO 15분·RTO 1시간 목표를 매주 restore smoke와 파일럿 전체 복원으로 확인한다. 불가역 migration은 억지 downgrade 대신 검증된 backup restore·forward fix 계획을 명시한다.

동일 잔여 자원 1개에 독립 connection 50개를 동시에 예약해 1개만 성공하는지 검사한다. divisible resource는 합계가 Offer 이하인지 검사한다. Offer 변경·동시 갱신·DB 재시작·중복 outbox·RLS 우회·증거 저장 실패를 시험한다. 읽기/예약 성능과 lock wait도 보고한다.
