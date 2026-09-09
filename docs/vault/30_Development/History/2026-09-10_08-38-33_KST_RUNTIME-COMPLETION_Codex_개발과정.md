---
doc_id: "HIST-RUNTIME-COMPLETION-001"
title: "Runtime completion Codex 개발과정"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-10T08:38:33+09:00"
source_of_truth: "Git"
---

# Runtime completion Codex 개발과정

Task ID: RUNTIME-COMPLETION. Owner Codex, reviewer Claude (독립 검토 pending).
작업 브랜치 `agent/codex/runtime-completion`, base `720b8ee8f4f53436d6316a138896fc6930617b58`, Codex 병합 대상 `39bd9e97819deaca66eab0368910a7b446cbd4e1`.
GUIDE·역할·Git 운영·agent-delivery·core-reliability v1.0.0, ADR v1.10.0 기준. S03/S04/S07 실행·복구 및 S05 예약 계약 후속이다. 기존 Sprint 전체를 done 처리하지 않는다.

사용자 요청 범위: 통합 검토, 실행 전 취소와 계획 등록 실패 예약 반환, 실제 Node 출력/Evidence, 샤드 부모/복구, writable Workspace 재개. 후속 Windows/GPU/BuildKit·Context/RO·5대 실장비 합격은 별도 증거가 필요하다.

합격 조건: 동일 SHA PostgreSQL/Linux Docker 통합 CI, 늦은 실행·재시작·취소 경쟁에도 중복 시작이나 거짓 정지 증명 없음, 출력 실제 바이트 해시와 Evidence의 연결, Git push/build/report/보수적 Obsidian 동기화. 실제 peer review 전 review 완료를 주장하지 않는다.

초기 통합: 소스 충돌 0, 문서 충돌 5개. Gemini 원저자 History의 BOM 차이만 제거하고, 두 브랜치의 인계/실행 기록을 보존했다. 기존 통합 브랜치에 커밋되어 있던 인계 문서의 충돌 표식도 제거했다. 이전 통합 보고의 운영 완료 주장은 이번 실행 증거로 간주하지 않는다.

1차 구현: Node의 미수신 명령 취소 tombstone → fsync → `not_started` receipt. 같은 command의 지연 Execute와 재시작 Recover는 tombstone을 재사용한다. 이미 create intent가 있는 불확실한 실행은 계속 실제 정지 증명이 필요하다. `containerId=""`, `processStarted=false`, `exitCode=-1` 조합은 JSON Schema에서 `not_started`에만 허용한다.

1차 구현: 발급된 tool claim/실행 attempt가 전혀 없는 Run만 Run lock 하에서 cancelled로 고정하고, 별도 immutable `reservation_aborts` ledger 및 FK를 통해 예약을 반환한다. Node 정지 receipt를 꾸미지 않는다. 샤드 admission의 savepoint 실패는 같은 바깥 transaction에서 미발급 예약을 회수한다. 이미 커밋된 claim의 충돌 재요청은 회수 대상이 아니다.

통합 검증에서 발견한 오류: 최신 Codex migration 0007~0013은 Alembic offline mode에서 driver connection을 요구했다. 전체 DDL을 그대로 출력하도록 보완해 offline migration 시험 17개가 통과했다. DB fixture는 각각 새 disposable DB만 생성하고, 두 DSN 환경변수를 해당 DB로 고정한다. 기존 DB의 public schema를 지우지 않는다.

로컬 명령 및 결과: `python -m pytest -q -o addopts= --tb=short --junitxml=.work/local-tests.xml` exit 0, 358 passed / 439 skipped. 이 Windows 환경의 skip은 Linux/실DB 미실행이며 제품 합격이 아니다. `go test ./...` (services/node-agent) exit 0, Windows 가능 패키지만 검증. `python tools/check_docs.py`, `python tools/check_ontology.py` exit 0. Linux race·Docker·실DB는 CI 대기.

다음: Linux 통합 CI 오류 수정 → 실제 출력 수집·전달/검증 → 샤드 부모/복구 → Workspace 재개. Push SHA/CI ID/동기화 결과는 검증보고에 추가한다.
