---
doc_id: "HISTORY-2026-09-22-CODEX-FRONTEND-WIRE-CONTRACT-AUDIT"
title: "Codex 프런트 응답 계약 감사 — RunItem 후속"
version: "1.0.0"
status: "active"
author: "Codex"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
---

# 프런트 응답 계약 감사

## 범위와 판정 기준

`apps/web/src/shared/api`, `apps/web/src/features`, `apps/web/src/contracts`의 응답 소비를 정본 `contracts/*.schema.json`, `src/saintvision/api/schemas.py`, 백엔드 라우트와 대조했다. 정본 스키마가 있는 응답은 프런트 어댑터가 생성 타입을 사용해야 한다. 정본 producer가 없는 응답은 새 타입을 추측해 만들지 않고 producer·화면 소유자에게 돌린다.

## 이번에 수렴한 기존 계약

`fabricControlApi`의 다음 응답은 기존 정본 스키마와 producer가 모두 있었지만 인라인 타입을 사용하고 있었다. 스키마에서 생성한 프런트 계약 파일을 추가하고 어댑터 반환형을 바꿨다.

- `ContributionRegistrationResponse` — 등록·활성화·폐기
- `HeartbeatAcceptedResponse`
- `NodeLivenessSweepResponse`
- `DiscoveryAnnouncementResponse`
- `DiscoveryAdmissionResponse`
- `DiscoveryDeclineResponse`

`cancelKernelRun`의 버전 조회도 축약 인라인 응답 대신 정본 `ControlRunDetail`을 사용한다. 이 변경은 화면 렌더링을 수정하지 않고 계약 전용 어댑터와 타입만 다룬다.

## 정본을 만들지 않고 인계한 공백

1. **`/v1/pools` 목록**: 감사 시점에는 백엔드 GET 라우트와 정본 스키마가 없었고 `PlacementSimulator`가 이 경로를 호출하고 있었다. 이 실제 404를 닫기 위해 tenant-scoped `PoolListResponse`(poolId/projectId/name/status/memberCount)와 FastAPI 서빙 앵커를 추가했다. 화면은 아직 legacy `id`·용량 필드를 기대하므로 Gemini가 canonical adapter로 전환해야 한다. 용량은 시점이 있는 별도 `/capacity` 응답을 사용하며 목록에 합성하지 않는다.
2. **PlacementSimulator 후보 확장 필드**: 화면의 `availableCores`, `availableMemoryBytes`, `gpuCount`, `healthStatus`는 discovery 후보 producer가 반환하는 `claimed*`, `state`, `verified`와 다르다. 이는 계약 누락이 아니라 producer와 화면 어휘의 불일치다. Gemini가 화면의 정직한 미제공 상태를 결정하고, 백엔드 계약은 실제 producer가 정해진 뒤 묶어야 한다.
3. **Placement preview 직접 호출**: 정본 `placement-preview-response.schema.json`과 계약 어댑터는 이미 있다. `PlacementSimulator`가 inline generic으로 직접 호출하는 것은 화면 레인의 배선 정리 대상이며, Codex가 새 UI 동작을 바꾸지 않았다.
4. **EvidenceViewer의 `apiClient<any>`**: 정본 `RunResultView`는 존재한다. 해당 화면 파일의 타입 수렴은 Gemini에게 인계한다.

따라서 RunItem 외에 추가로 발견된 **실제 정본 누락**은 pool 목록 하나였고, 이를 백엔드 producer·스키마·서빙 앵커로 보강했다. 정본이 있던 여섯 응답도 어댑터에 연결했고, discovery 후보 확장 필드처럼 producer가 없는 모양은 추측 계약으로 만들지 않았다.

## producer 방향의 추가 판정

- Pool capacity는 이미 `totalOffered`, `spareNow`, 노드별 `offered/used/spare/measured`, `units`를 낸다. 따라서 풀 용량·사용량은 값이 없는 것이 아니라 **목록 응답에 넣지 않고 별도 읽기 모델로 유지해야 하는 값**이다.
- Discovery 후보는 `claimedCpuCores`, `claimedRamBytes`, `claimedGpuCount`, `state: candidate`, `verified: false`만 낸다. `available*`, `gpuName`, `healthStatus`는 후보 producer가 만들지 않는다.
- 등록된 노드의 capability `vendor/model/totalQuantity`와 placement preview의 `spare`는 존재하지만, 그것을 미등록 후보의 건강·가용량으로 투영할 근거는 없다.

결론적으로 노드 자원 사용량 계약 결정에는 `total/used/spare`, 단위, `measured`, 관측 시각의 의미를 포함해야 한다. 후보 화면의 `gpuName`과 `healthStatus`는 이 결정으로 자동 해결되지 않으며 Gemini가 미제공 상태로 다뤄야 한다.

## 확인

- `npm run build` (cwd `apps/web`, SHA 작업 브랜치 기준) → exit 0
- `C:\Project\SaintVision-Invion\.venv\Scripts\python.exe -m pytest -q tests/core/test_pool_placement_response_contract.py` (PYTHONPATH=src) → 24 passed, exit 0
- 변경은 `apps/web/src/contracts`의 생성 타입과 계약 전용 어댑터에 한정했다.
- 브라우저 인수와 실제 HTTP/DB 실행은 이 감사에 포함하지 않았다.

## 인계

- Gemini: PlacementSimulator를 새 `PoolListResponse`의 `poolId`/`projectId`/`status` 계약에 맞는 어댑터로 연결하고, 후보 확장 필드가 실제 화면에서 무엇을 의미해야 하는지 결정한다. placement preview 직접 호출과 EvidenceViewer `any`도 정본 어댑터로 수렴할지 검토한다.
- Codex: 정본 producer가 생기면 해당 응답을 `contracts/*.schema.json`과 생성 타입·서빙 앵커·적합성 시험에 연결한다.
