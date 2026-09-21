---
doc_id: "CLAUDE-MODEL-VERIFY-LINEAGE-RECOMMENDATION-001"
title: "모델 verify HTTP 노출 권고 + 모델 lineage 관측 실태 (Codex 인계 재료)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
mapped_at_sha: "64dd7f6"
updated: "2026-09-21T19:24:00+09:00"
source_of_truth: "Git"
tags: ["model", "verify", "lineage", "recommendation", "codex-handoff", "boundary"]
---

# 모델 verify HTTP 노출 권고 + 모델 lineage 실태

능력지도([[2026-09-21_무결성_복제본_백엔드능력지도_Claude]])에서 남긴 경계 질문 2개를 실측·권고로 정리한다. Codex 인계 재료.

## A. 모델 verify를 HTTP로 노출할 것인가

### 현재 실태 (실측)
- 진짜 능력: `inv/model_manifest.py:112 verify(manifest, snapshots)` — 모델 바이트 검증. **내부 호출만**(`model_commit.py:83`, `model_locality.py:188`). HTTP 라우트 없음.
- 프런트가 지금 볼 수 있는 유일한 신호: `ModelCommitObservation.requiresExecutionRevalidation:true`(결속됨). 즉 "커밋됐고 아직 실행-재검증 안 됨"만 표시 가능. **"지금 검증됨/무결"을 표시할 수단이 없다.**
- 그래서 화면은 "재검증 필요"만 말할 수 있다.

### "재검증 필요"만으로 사용자에게 충분한가 — 아니다
- 정직하지만 불완전하다: 사용자는 "미검증"은 알지만 (1) 검증 결과(무엇이 몇 개 일치/불일치)를 못 보고 (2) 검증을 촉발할 방법도 없다. 진짜 검증이 서버에 있는데 노출을 안 하면 실능력을 낭비한다.

### 권고 (2안 분리 — 읽기 노출은 추천, 온디맨드 재검증 트리거는 신중)
1. **[추천] 마지막 검증 결과의 읽기 관측 노출**: 저장된 검증 상태를 **다시 해싱하지 않고 읽어서** 반환. 응답 모양은 `RecordedStorageObservation` 패턴을 그대로(그게 이미 verify_sample 결과를 이렇게 노출함):
   - `modelId, version, manifestHash, verifiedAt(nullable), integrityVerified(bool), verifiedShards/examined/mismatches/unverifiable(int counts), verifierEpoch, status(enum: verified|failed|not-run)`.
   - 이러면 화면이 "재검증 필요" 대신 실제 "검증됨(N/N shard 일치, verifiedAt)" 또는 "불일치 M건" 또는 "미실행"을 정직하게 표시. **합성 없이** 실 데이터.
2. **[신중] 온디맨드 재검증 트리거(POST)**: 모델 바이트를 다시 해시 → 비용·보안(신뢰 경계) 결정. 운영자/보안 판단 필요. 기본은 노출하지 않기를 권고.

### 누가 만드나
- verify 자체는 워커·모델 registry·신뢰 경계 인접 → **엔드포인트+앵커 신설은 Codex**(replica-repair/verify_sample 서명 등 보안 인접을 Codex가 소유하는 것과 동일 결). 검증 결과가 이미 영속되면 읽기-관측은 모델-view라 앵커 생긴 뒤 **내가 계약 결속**(ShardObservation/ReplicaObservation과 같은 분담). 영속 안 돼 있으면 영속화도 Codex 모델 레인.
- 즉: **Codex가 읽기-관측 엔드포인트+`ModelVerificationView`(가칭) 앵커를 만들면, 내가 fixture+계약시험으로 양면 결속.**

## B. 모델 lineage 관측 — 실태 (내 능력지도의 "가능"을 정정)
능력지도에 "모델 lineage 관측 = Claude 레인(가능)"이라 적었으나 **실측으로 정정한다**(호출경로 추적):
- **커널 `ModelLineage` $def 없음.** 커널에 서빙 lineage 응답·앵커 없음.
- 백엔드 lineage 데이터는 **saintvision 레이어에만**: `src/saintvision/db/models/lineage.py:241 class ModelLineage(Base)` + `src/saintvision/services/lineage.py`(쓰기/질의). **HTTP 엔드포인트 없음**(saintvision api에 lineage 라우트 0).
- 프런트 `apps/web/src/features/mlops/ModelLineageView.tsx`는 **로컬 `MlopsManager.getLineages()`**에서 받는다 → `mlopsEngine.ts`의 **하드코딩 `INITIAL_LINEAGES`**(가짜 eval 점수 `evalAccuracy:0.812` 등 포함). **전량 프런트 합성.**
- 결론: **모델 lineage는 결속 대상이 아니다**(서빙 앵커 없음). 커널 패턴으로 묶을 것이 없고, 실 데이터는 saintvision(Codex 레이어)에 내부로만 존재.

### 권고
- 합성을 멈추려면 saintvision `services/lineage.py` 위에 **lineage 관측 읽기 엔드포인트**를 신설해야 한다. 소관 = **saintvision 계약 레이어 = Codex**(replica/storage-location/pool 계약맵과 동일 레이어). 앵커 생기면 계약 결속은 조율.
- 그전까지 **Gemini**: `ModelLineageView`의 하드코딩 `INITIAL_LINEAGES`를 "백엔드 lineage 데이터 없음(미노출)"으로 표시. 가짜 eval 점수/deployed 상태 합성 금지.

## 이번 커밋에서 내가 결속 (내 레인 ①)
- **StorageObservationView** (스토리지 샘플 무결성): `contracts/fixtures/storage-observation-response.json` + `tests/core/test_storage_observation_contract.py`(**5 passed**: fixture↔계약 · envelope 11 + RecordedStorageObservation 10 load-bearing · **currentHealth const "unknown"·operationalAcceptanceAssessed const false·integrityVerified const true 반-합성 가드**). 양방향(Python VAL-0002 + Ajv). 앵커 `storage_view.py:101`. (프런트 미배선 — 앵커 있으나 미소비, 배선 시 계약 잠김.)

관련: [[2026-09-21_무결성_복제본_백엔드능력지도_Claude]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
