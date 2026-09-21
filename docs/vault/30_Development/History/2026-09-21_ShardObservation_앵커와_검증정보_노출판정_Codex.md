---
doc_id: "CODEX-SHARD-MODEL-OBSERVATION-001"
title: "ShardObservation serving anchor and model observation exposure decision"
version: "1.0.1"
status: "active"
author: "Codex"
reviewer: "pending"
mapped_at_sha: "b08b2273995a96cefccaaa55709b13c8c78e9b08"
updated: "2026-09-21T19:54:00+09:00"
source_of_truth: "Git"
tags: ["shards", "contract", "model-verification", "lineage", "boundary"]
---

# ShardObservation 앵커 및 모델 관측 노출 판정

## ShardObservation 백엔드 앵커

`ShardRuntime._status`가 `/v1/projects/{project}/runs/{run_id}/shards` 응답을 만들고 반환하기 전에 `validate_contract("ShardObservation", result)`를 호출한다. 기존 공유 fixture와 스키마 결속에 실제 서빙 경계 검증을 추가했다. 응답 상태가 계약 enum을 벗어나면 서비스가 응답을 내보내지 않고 `DomainError`로 중단한다.

회귀 시험은 가짜 DB 경계에서 유효하지 않은 shard state를 반환하게 하고, 실제 `_status` 경로가 계약 검증을 호출해 `VAL-0002`로 거부하는지 확인한다. 호출을 제거한 되돌림 대조에서 이 시험은 `DID NOT RAISE DomainError`로 실패했다. 이는 호출 경로 및 검증 결과를 고정한다.

작성자 로컬 검증: `tests/core/test_shard_observation_contract.py` 6 passed. 테스트는 PostgreSQL/Docker 없이 실행된다. 독립 검토는 미완료다.

## Discovery tenant 경계 확인 및 보강

Claude의 `85868a7` 문서에서 발견한 기존 경로는 `POST /v1/discovery/announcements`가 `X-Inv-Tenant`를 인증 확인 없이 `tenant_scope`와 후보 기록 함수에 직접 전달했다. handler 시그니처에 `get_principal`이 없었고 Node Agent wire 시험은 `Authorization`이 비어 있음을 기대했다. 발표는 실제 Node 생성/등록 권한을 주지 않는 후보 row였지만 임의 tenant에 후보를 심거나 tenant별 후보 한도(500)를 소진하는 cross-tenant write/DoS가 가능했다.

수정은 요청 인증 principal을 요구하고 header tenant가 principal tenant와 다르면 `AUTH-TENANT-SCOPE` 403으로 DB factory/session 생성 전에 거부한다. Node Agent `inv-discover`는 tenant 인증 bearer credential을 `INV_DISCOVERY_BEARER_TOKEN` 환경에서만 읽어 전송하며 토큰을 인자나 로그로 내보내지 않는다. 운영 환경에 그 credential을 주입하는 일은 별도 provisioning 필요다. Gemini 소유 `ResourceExplorer`의 하드코딩 tenant UUID는 이 검증을 통과하지 않으므로 실제 세션 tenant로 바꿔야 한다. UI 수정은 이 커밋에 포함하지 않는다.

### 설계 변경 및 신규 노드 부트스트랩 영향 확인 (2026-09-21)

이 변경은 기존 설계의 단순 결함 수정이 아니라 의도적 익명 discovery 결정을 뒤집는다. 직전 구현은 미등록 기계가 먼저 공지할 수 있는 유일한 경로를 무인증으로 열어 두되, 후보 행만 만들고 승인·실행 권한·플랫폼 세부정보는 주지 않는다는 이유로 최소 권한으로 기록했다. 그 설계는 네트워크에 연결된 누구나 임의 tenant 후보를 만들고 후보 한도(tenant당 500)를 소진할 수 있게 한다. 새 경계는 이 cross-tenant 후보 주입 및 자원 고갈 가능성을 줄이고, 공지 tenant가 인증 identity의 tenant임을 보장한다. 대가는 최초 공지 전에 미등록 Node에 자격증명이 있어야 한다는 것이다.

**확인된 부트스트랩 상태:** `inv-discover`는 `INV_DISCOVERY_BEARER_TOKEN`을 `Authorization: Bearer`로 보낸다. API의 `get_principal`은 앱에 설정된 verifier로 이를 검증하고, 실제 설정 경로는 OIDC access token 검증과 활성 business user 매핑을 기대한다. 저장소에서 이 discovery 전용 bearer를 발급하는 route/CLI/자동화, Node service identity를 IdP에 등록하는 절차, secret manager에 배포·회전하는 구체적 운영 절차를 찾지 못했다. 현재 Node runbook도 토큰을 secret manager/service environment로 “주입”하라고만 하며 발급 단계를 제공하지 않는다. `POST /v1/discovery/candidates/{id}/admission`은 이미 후보가 생긴 뒤 인증된 사람의 승인으로 one-time **enrollment bootstrap token**을 발급한다. 그것은 최초 공지용 `INV_DISCOVERY_BEARER_TOKEN`이 아니므로 신규 미등록 기계의 선행 자격증명을 해결하지 않는다. 코드상 `/v1/auth/token` 발급 route도 없다. 이는 저장소 및 문서 조사 결과이며, 조직 IdP/외부 secret manager에 별도 수동 절차가 있을 가능성은 배제하지 않는다.

**기능 영향:** 현재 변경 상태에서는 유효한 tenant-mapped OIDC access token을 미리 주입한 Node만 discovery 공지를 할 수 있다. 그런 토큰을 갖지 않은 새 Node는 후보로 발견되지 않으며 이후 admission/enrollment 절차에도 도달할 수 없다. 따라서 문서화된 기존 “미등록 기계가 먼저 공지” 흐름은 인증 bootstrap 선행조건이 정의될 때까지 운영상 막혀 있다. 이번 TestClient 증명은 서버의 tenant 거부를 검증했을 뿐 실제 IdP 발급, 무인증 새 Node 온보딩, 운영 secret 전달은 검증하지 않았다.

**소유자와 다음 결정:** Codex가 scoped machine/discovery credential의 발급·검증 계약(tenant binding, 최소 scope, 만료·회전·폐기, 감사)을 설계하고, Identity/운영 담당자가 IdP 발급 및 secret manager/service deployment 전달 절차를 확정해야 한다. 그 전까지 운영 문서상 신규 무인증 Node onboarding은 차단/미지원으로 표시한다. 임시 anonymous endpoint를 다시 열지 않는다. 기능을 임시로 살리려면 승인된 대안으로 별도 일회용 tenant-bound discovery credential을 마련해야 한다. 임의 사용자 access token을 장기 Node 자격증명으로 재사용하는 것은 지원 절차로 간주하지 않는다.

증거: FastAPI `TestClient`로 실제 route에 인증 principal A + header tenant B 요청을 보내 403과 `record_announcement` 미호출을 확인한다. 인증 없이 header만 보낸 요청은 401이다. tenant 비교 guard를 제거한 되돌림 대조에서는 mismatch 시험이 500/403 불일치로 실패했고, 복구 후 discovery+shard targeted suite 8 passed다. Go compiler/test runner는 이 호스트에 없어 Node Agent 변경을 실행 검증하지 못했다. PostgreSQL DSN도 없어 DB-backed 후보 저장과 운영 credential 발급은 미실행이다.

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

소스 대조는 `model_commit.py`, `model_locality.py`, `model_view.py`, migration `0039_model_manifest.py`, SaintVision `services/lineage.py`, API router 목록과 Claude 인계 문서를 대상으로 했다. 모델 검증이나 lineage endpoint는 추가하지 않았고, discovery 기존 route의 tenant authorization은 보강했다. DB-backed model/locality와 discovery 저장 통합 및 SaintVision API 운영 시험, Go build와 브라우저 인수는 실행하지 않았다.
