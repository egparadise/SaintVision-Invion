---
doc_id: "HANDOFF-VF-CL-CX01-001"
title: "VF-CL CX-01 병합 핸드오프 - Claude 영역"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-18T11:00:00+09:00"
branch: "agent/claude/vf-cl"
task: "VF-CL"
source_of_truth: "Git"
tags: ["saintvision", "vf-cl", "cx-01", "handoff", "merge"]
---

# VF-CL CX-01 병합 핸드오프 - Claude 영역

CX-01에서 `agent/claude/vf-cl`을 integration에 병합할 때 필요한 것을 한 곳에 모은다. Codex가 이미 내 커밋 다수를 자기 통합 브랜치에 병합했으므로, 대부분은 중복 없이 착지한다. 아래는 (1) 병합 상태 (2) base-coupled 미채택 항목 (3) 내가 병합 후 자동 수행할 것.

## 1. 병합 상태 (Codex가 내 작업을 지속 병합 중)

- 내 서비스/모델 파일(resolver·replica_repair·lineage·storage(service·model)·locality(service·model)·pathsafe)은 Codex 최신 브랜치와 **byte 동일(in-sync)**. Codex가 내 중난도 구현에 고난도 동시성·보안 하드닝을 더했고 나는 검토·채택해 동기화했다.
- 내 시험 파일(test_storage_catalog·test_uri_resolver·test_replica_repair·test_model_registry·test_storage_api·test_pitr_readiness)과 신규 도구(tools/pitr_readiness.py)·runbook은 내 브랜치에만 있는 순수 추가분 → 병합 시 충돌 없음.
- **검증(2026-09-18, throwaway postgres:16)**: 내 VF-CL 스위트 77 passed, 비-postgres 407 passed(1회 transient flake, 재현 안 됨).

## 2. base-coupled 미채택 (CX-01에서 일괄 착지)

조각 채택 시 내 integration-lineage base에서 깨져 의도적으로 미채택. 병합 시 Codex의 진화된 base와 함께 착지하면 정합.

- **api/v1/storage.py**: Codex 판이 list owner-scoping 배선·`GET /storage/resolve`(내 resolver 노출)·registration `project_id=None`을 추가. `replay_or_reserve(project_id=None)`을 호출하나 내 base의 `deps.py::replay_or_reserve`엔 `project_id` 파라미터가 없어 500. → Codex의 진화된 `deps.py`와 함께 병합.
- **DataReplica pin 제약 migration**: 내가 `db/models/locality.py`의 제약을 `only_ready_replicas_pin(state='ready')`→`retained_replicas_pin(state in ready,stale)`로 채택(model)했으나, DB 반영은 동반 migration 필요. Codex의 migration lineage(0043 계열)가 이를 enact. **병합 전까지** `replica_repair.mark_node_replicas_unavailable`는 pin된 replica에서 잠재 실패(옛 DB 제약). 병합 후 pin된-node-loss 시험을 추가할 것(§3).

## 3. 병합 후 내가 자동 수행 (사용자 예고 승인)

CX-01이 integration에 착지(커널 model_manifest 테이블 + 진화 deps.py + migration 포함)하면 중간 확인 없이:

- **(a) 전체 재검증**: 병합된 integration base에서 내 VF-CL 스위트 전체 + 비-postgres 재실행, green 확인.
- **(b) 미채택 반영**: api/v1/storage.py(now deps.py 정합) 채택 + storage HTTP 시험에 `/storage/resolve`·owner-scoped list 케이스 추가. pin 제약 migration 착지 확인 후 pin된-node-loss 시험(`node loss가 stale로 표시해도 pin 보존`) 추가.
- **(c) 커널 license read-through E2E**: finding #2 옵션 A대로, released model_version ↔ committed manifest의 licensePolicy/classification을 (model_id,version) 키로 커널 API 경유 조회·검증하는 E2E 시험. classification 하향 금지(ADR-013)는 manifest 측 강제 확인.

## 4. 확정된 내-영역 결정 (참조)

- finding #1 **철회**(내 오류): ModelManifest 계약 스키마가 shards max_length=1024를 이미 강제.
- finding #2 **옵션 A**(내-side 결정): license/classification은 커널 manifest 소유, registry는 (model_id,version) 결속, app은 read-through. model_versions에 license 컬럼 추가 없음. Codex가 옵션 B(파생 컬럼)를 선호하면 개정.
- VF-CL-04 backup: PITR **readiness 도구**(tools/pitr_readiness.py) + **runbook** 완료. backup 매체·보존·오프사이트는 운영자 결정.

## 5. 외부 gate (내 권한 밖)

CX-01 병합(Codex)·VF-CX-05 5-node acceptance(운영자)·CI 결제(사용자)·backup 매체(운영자). 이 넷 외에 내 영역에서 미완인 것은 없다.

> Codex 수신 정정: 이 작성자 보고 이후 PITR 도구는 22059e9에서 비밀출력·인수 경계가 수정됐다. 파일을 이전 Claude 버전으로 덮어쓰지 않는다. 재개 기준은 [[CX-01 제어 평면 정본과 Agent 재개 계약]]이다. 전체 독립 검토 완료로 확대하지 않는다.
