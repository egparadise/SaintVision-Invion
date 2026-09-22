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

1. **`/v1/pools` 목록**: 현재 백엔드에 해당 GET 라우트와 정본 스키마가 없다. `PlacementSimulator`가 이 경로를 호출하지만, producer가 없는 응답 타입을 새로 만들면 존재하지 않는 계약을 고정하게 된다. 백엔드 producer와 화면 요구를 먼저 결정해야 한다.
2. **PlacementSimulator 후보 확장 필드**: 화면의 `availableCores`, `availableMemoryBytes`, `gpuCount`, `healthStatus`는 discovery 후보 producer가 반환하는 `claimed*`, `state`, `verified`와 다르다. 이는 계약 누락이 아니라 producer와 화면 어휘의 불일치다. Gemini가 화면의 정직한 미제공 상태를 결정하고, 백엔드 계약은 실제 producer가 정해진 뒤 묶어야 한다.
3. **Placement preview 직접 호출**: 정본 `placement-preview-response.schema.json`과 계약 어댑터는 이미 있다. `PlacementSimulator`가 inline generic으로 직접 호출하는 것은 화면 레인의 배선 정리 대상이며, Codex가 새 UI 동작을 바꾸지 않았다.
4. **EvidenceViewer의 `apiClient<any>`**: 정본 `RunResultView`는 존재한다. 해당 화면 파일의 타입 수렴은 Gemini에게 인계한다.

따라서 RunItem 외에 추가로 발견된 **실제 정본 누락**은 이번 감사 범위에서 확인되지 않았다. 정본이 있던 여섯 응답은 어댑터에 연결했고, producer가 없는 두 경로는 추측 계약으로 만들지 않았다.

## 확인

- `npm run build` (cwd `apps/web`, SHA 작업 브랜치 기준) → exit 0
- 변경은 `apps/web/src/contracts`의 생성 타입과 계약 전용 어댑터에 한정했다.
- 브라우저 인수와 실제 HTTP/DB 실행은 이 감사에 포함하지 않았다.

## 인계

- Gemini: PlacementSimulator의 `/v1/pools` 및 후보 확장 필드가 실제 화면에서 무엇을 의미해야 하는지 결정하고, placement preview 직접 호출과 EvidenceViewer `any`를 정본 어댑터로 수렴할지 검토한다.
- Codex: 정본 producer가 생기면 해당 응답을 `contracts/*.schema.json`과 생성 타입·서빙 앵커·적합성 시험에 연결한다.
