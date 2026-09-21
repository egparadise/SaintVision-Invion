---
doc_id: "CODEX-SHARD-MODEL-OBSERVATION-001"
title: "ShardObservation serving anchor and model observation exposure decision"
version: "1.0.0"
status: "active"
author: "Codex"
reviewer: "pending"
mapped_at_sha: "b08b2273995a96cefccaaa55709b13c8c78e9b08"
updated: "2026-09-21T19:38:00+09:00"
source_of_truth: "Git"
tags: ["shards", "contract", "model-verification", "lineage", "boundary"]
---

# ShardObservation 앵커 및 모델 관측 노출 판정

## ShardObservation 백엔드 앵커

`ShardRuntime._status`가 `/v1/projects/{project}/runs/{run_id}/shards` 응답을 만들고 반환하기 전에 `validate_contract("ShardObservation", result)`를 호출한다. 기존 공유 fixture와 스키마 결속에 실제 서빙 경계 검증을 추가했다. 응답 상태가 계약 enum을 벗어나면 서비스가 응답을 내보내지 않고 `DomainError`로 중단한다.

회귀 시험은 가짜 DB 경계에서 유효하지 않은 shard state를 반환하게 하고, 실제 `_status` 경로가 계약 검증을 호출해 `VAL-0002`로 거부하는지 확인한다. 호출을 제거한 되돌림 대조에서 이 시험은 `DID NOT RAISE DomainError`로 실패했다. 이는 호출 경로 및 검증 결과를 고정한다.

작성자 로컬 검증: `tests/core/test_shard_observation_contract.py` 6 passed. 테스트는 PostgreSQL/Docker 없이 실행된다. 독립 검토는 미완료다.

## 모델 바이트 검증 HTTP 노출 결정

**현재는 마지막 모델 무결성 결과를 HTTP로 노출하지 않는다. 온디맨드 재검증 endpoint도 추가하지 않는다.** 조사 근거:

- `inv.model_manifests`에는 불변 manifest와 hash, source run, recovery epoch, `committed_at`이 저장되지만 검증 결과 이력/카운트 테이블은 없다.
- `model_commit.py`는 커밋 직전에 실제 바이트를 확인하지만 그 작업 결과는 manifest commitment로만 이어진다. 이를 “현재 무결성 검증 결과”로 노출하면 그 뒤 복제본 바이트가 바뀌어도 오래된 커밋 검증이 현재 상태처럼 보인다.
- `model_locality.py`의 검증은 실제 replica snapshot을 읽고 검증하지만 결과 객체가 요청 중 메모리에만 있고 actor·tenant·project·recovery epoch에 묶인다. 이는 저장된 최신 검증 결과가 아니며 배치/선택된 placement 범위에 대한 일회성 관측이다.
- 이미 있는 commitment 관측의 `requiresExecutionRevalidation: true`는 보수적이고 정직한 상태다. 이 상태를 현재 검증 성공으로 덮어쓰지 않는다.

추후 읽기 관측을 열려면 먼저 검증 receipt를 지속 저장해야 한다. 최소 설계에는 관측 주체/tenant/project/model/version, manifest hash, recovery epoch, 확인 시각, 검증 대상 replica 및 shard 수, mismatch/unverifiable 구분, 실패 사유의 비밀 비노출 규칙, 동시 검증 간 최신성 규칙과 보존 정책이 필요하다. 그 뒤 조회 endpoint와 계약 앵커를 추가한다. 이 결정은 바이트 재검증 능력을 부정하지 않으며, 현재 저장되지 않은 결과를 꾸며서 반환하지 않기 위한 경계다.

## 모델 lineage HTTP 노출 결정

**현재는 lineage endpoint를 추가하지 않는다.** SaintVision `trace_model`은 실제 저장된 lineage를 읽지만 HTTP adapter가 없고, 해당 API의 사용자/tenant/project authorization 및 공개 가능한 필드 범위를 연결하는 계약이 아직 없다. 이 서비스 결과에는 dataset URI, evaluation 정보 등 사용자에게 노출할 범위를 별도 결정해야 하는 값이 포함된다. 내부 서비스가 있다는 것만으로 전부를 wire 응답으로 내보내지 않는다.

UI는 이 결정을 반영해 실제 backend 응답이 없는 상태를 “미노출/사용 불가”로 보여야 하며 합성 eval 점수, lineage edge 또는 deployed 상태를 사실처럼 표시해서는 안 된다. 실제 노출을 재검토할 때는 프로젝트 멤버십/tenant 범위, 필드 공개 정책, missing/dangling 표현을 포함한 정본 응답 모델과 계약 시험을 먼저 만들고 그 뒤 route를 추가한다.

## 근거 범위

소스 대조는 `model_commit.py`, `model_locality.py`, `model_view.py`, migration `0039_model_manifest.py`, SaintVision `services/lineage.py`, API router 목록과 Claude 인계 문서를 대상으로 했다. 모델 검증이나 lineage endpoint는 추가하지 않았다. DB-backed model/locality와 SaintVision API 시험 및 브라우저 인수는 실행하지 않았다.
