---
doc_id: "CLAUDE-MODEL-COMMIT-OBSERVATION-CONTRACT-001"
title: "ModelCommitObservation 계약 결속 — 앵커 있는 소비O 응답 (드리프트 없음·생성타입 모범)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
frontend_owner: "Gemini"
updated: "2026-09-21T19:40:00+09:00"
timezone: "Asia/Seoul"
bound_at_sha: "d0d41c3"
source_of_truth: "Git"
tags: ["contract-binding", "model-lineage", "anchor", "no-drift"]
---

# ModelCommitObservation 계약 결속

"다른 커널 `_checked`/`validate_contract` 응답 결속" 방향(사용자 선택 2). run-result류와 동일 패턴.

## 왜 이 대상 (앵커·소비 코드 확인)
- **앵커가 응답에 실제로 걸림**(이름 유사 아님, 코드 확인): `services/control-plane/src/inv/model_view.py:56`가 서빙 직전 `validate_contract("ModelCommitObservation", result)` — `result`는 `/v1/projects/{p}/models/{m}/versions/{v}/commitment`로 반환되는 응답.
  - 대조 제외: `ModelManifest`는 앵커가 **manifest 검증 워커**(`model_manifest.py:27 manifest_copy`)에 걸린 것이지 서빙 응답이 아니라 이 패턴 대상 아님. `NodeStopReceipt`는 이름충돌(별도 문서).
- **소비 실재**: `apps/web/src/shared/api/fabricObservation.ts:36` `get<ModelCommitObservation>(.../commitment)` — 실제 fetch 어댑터 + 런타임 가드(projectId/modelId/version/committed/currentAvailability/requiresExecutionRevalidation 대조).
- **미결속**: model fixture 없었음. **내 레인**: model_view = result_view의 형제(view 응답), CLAUDE.md VF-CL "model registry/lineage" 트랙. Codex 모델 worktree 현재 model 계약 dirty 없음(비겹침, 추가 파일만).

## 내가 결속한 것 (SHA d0d41c3 위)
- `contracts/fixtures/model-commit-observation-response.json` — model_view가 생산하는 15필드 응답에 충실.
- `tests/core/test_model_commit_observation_contract.py` — **3 passed**: fixture↔커널계약(`validate_contract`; model_view가 도는 그 검증) · **15필드 전부 load-bearing** · classification enum(public|internal|restricted) 강제.
- 변형 **양방향**: Python `validate_contract`(VAL-0002) + 일회용 Ajv(`#/$defs/ModelCommitObservation`) 둘 다 15필드 제거·enum 위반 거부.

## 드리프트: **없음** (생성-타입 모범 사례)
프런트가 수기 타입이 아니라 **생성 타입을 import**한다: `import type { ModelCommitObservation } from 'packages/contracts-ts/src'`. 생성 타입(index.ts:1082)은 15필드 스키마와 정확 일치(`committed:true`·`currentAvailability:"unknown"`·`requiresExecutionRevalidation:true` const 좁힘 포함). → **드리프트 클래스가 없다.** 이것이 드리프트 훑기 문서에서 권고한 패턴의 실제 모범 사례다([[2026-09-21_수기타입_계약_드리프트_전수훑기_Claude]]).

## Gemini 인계 (가벼움 — 타입 수정 불필요)
- 타입은 이미 생성-타입 사용이라 정합 작업 없음. 남은 것: 원하면 `model-commit-observation-response.json`을 `#/$defs/ModelCommitObservation`에 대조하는 프런트 Ajv 계약 시험 추가(run-approval-observation-contract.test.ts 형태). 필수는 아님 — 이미 컴파일-타임 생성타입 + 런타임 가드로 방어됨.
- 공유 진행판 담당 기록은 Gemini 편집 중(dirty)이라 미기입 — **ModelCommitObservation=Claude(계약)** 항목 착지 후 반영 요.

관련: [[2026-09-21_수기타입_계약_드리프트_전수훑기_Claude]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
