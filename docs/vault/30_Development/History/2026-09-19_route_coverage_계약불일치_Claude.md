---
doc_id: "FIND-ROUTE-COVERAGE-CONTRACT-001"
title: "route_coverage 38경로 중 6 미제공 — 소스 대조 판정(3 실제 불일치 / 3 오탐)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-19T17:00:00+09:00"
source_of_truth: "Git"
tags: ["saintvision", "finding", "route-coverage", "frontend-backend-contract", "404"]
---

# route_coverage 38경로 중 6 미제공 — 소스 대조 판정

사용자가 `tools/route_coverage.py`로 클라이언트 요청 38경로 중 6이 `src/saintvision`·`services/control-plane/src` 어디에서도 미발견이라고 보고했다(아침엔 26/0). 도구는 **"Static path shapes only; dynamic prefixes may be omitted"** caveat를 단다. 그래서 도구 결과에 의존하지 않고 **실제 라우트 정의와 프론트엔드 호출을 소스로 직접 대조**하고, catch-all/`{path:path}`/`.mount`/`add_route`/`add_api_route` 등 **동적 등록이 없음을 확인**했다(grep 0). 결론: 6 중 **3은 실제 계약 불일치, 3은 도구 오탐**이다.

두 백엔드가 있다: `src/saintvision/api/v1/*`(`@router.*`, `APIRouter(prefix="/v1")`로 조립)와 `services/control-plane/src/inv/app.py`(`@api.*("/v1/...")` full path). 프론트엔드는 `apps/web`.

## A. 실제 계약 불일치 3건 — 사용자 경로에서 404

### A1. `/v1/events` (전역 SSE) — 백엔드에 전역 형태 없음
- **호출(프론트)**: `apps/web/src/features/deployment/deploymentEngine.ts:63-64`가 `/v1/events`를 SSE로 구독(`apps/web/tests/sse-stream.test.ts`, `intranet-deployment.test.ts`도 이 경로).
- **백엔드**: events 라우트는 `services/control-plane/src/inv/app.py:858 @api.get("/v1/projects/{project}/runs/{run_id}/events")` — **project·run scoped 형태만** 존재. 전역 `/v1/events`는 없다.
- **결과**: 프론트의 전역 이벤트 스트림 구독이 매칭 라우트 없이 **404**.

### A2·A3. `/v1/projects/{}/runs/{}/evidence` 및 `/v1/runs/{}/evidence` — 백엔드에 evidence 라우트 자체가 없음
- **호출(프론트)**: `apps/web/src/features/evidence/EvidenceViewer.tsx:42,45`가 `/v1/projects/${prjId}/runs/${runId}/evidence`와 `/v1/runs/${runId}/evidence`를 호출(`apps/web/tests/evidence-viewer.test.ts`도).
- **백엔드**: `evidence`를 경로로 가진 라우트가 **어느 트리에도 없다**(route 데코레이터 grep 0; `evidence`는 내부 개념 `evidence_id`/`record_evidence`/DB model/`outputSha256`으로만 등장). 실행 산출물은 `/v1/runs/{run_id}/result`(app.py:396·397), `/v1/…/artifacts`(401·402·406·407), `/v1/projects/{}/runs/{}/shards`(466)로 제공된다.
- **결과**: EvidenceViewer의 두 호출이 **404**.

## B. 영향
세 건 모두 **사용자 경로에서 404**다(프론트가 존재하지 않는 백엔드 엔드포인트를 호출). 배포/실행 화면의 이벤트 스트림과 Evidence 뷰어 기능이 실제 사용 시 실패한다.

## C. 담당과 선택지 (제품 조율 결정 — Claude 단독 구현 안 함)
고치는 방향은 두 갈래이며 어느 쪽인지는 제품 조율 결정이다:
1. **백엔드에 엔드포인트 추가**: 전역 `/v1/events` SSE, 그리고 `…/evidence` 엔드포인트(또는 `evidence`를 기존 `result`/`artifacts`/`shards`에 매핑). — **신규 백엔드 엔드포인트는 Codex 계약** 영역.
2. **프론트엔드가 기존 경로로 호출**: 이벤트를 project/run scoped로, evidence를 `result`/`artifacts`/`shards`로. — **프론트엔드는 Gemini** 영역.
- 프론트는 Gemini, 신규 백엔드 엔드포인트는 Codex 계약이므로 **Claude가 단독 구현하지 않는다**(확인·기록까지가 내 범위). 사용자가 Gemini에 전달하고, Codex 복구 시 백엔드 계약 판단을 받는다.

## D. 나머지 3건 — 실제 gap 아님 (반복 조사 방지용 사유 기록)

### D1. `/v1/discovery/candidates` — **실제로 제공됨** (도구 스캔 범위 false-negative)
`src/saintvision/api/v1/pools.py:86 @router.get("/discovery/candidates")`, 같은 파일 `:29 APIRouter(prefix="/v1")`, `src/saintvision/api/app.py:173 include_router(pools_router.router)` → 전체 경로 **`/v1/discovery/candidates` 실재**. `route_coverage`의 `served_routes`는 `_PREFIX`로 prefix를 조립하나, 이 건이 미제공으로 나온 것은 스캔 대상 트리 범위(`--served`에 `src/saintvision` 미포함) 문제로 보인다. **엔드포인트는 존재한다.**

### D2·D3. `/v1/runs`·`/v1/workspaces` (bare) — **도구 추출 아티팩트** (프론트가 bare collection을 호출하지 않음)
- 프론트는 bare `/v1/runs`·`/v1/workspaces`를 호출하지 **않는다**. 실제 호출은 id-scoped다: `apps/web/.../WebTerminal.tsx`·`deploymentEngine.ts`의 `/v1/workspaces/${id}/terminal-tickets`·`/terminals/...`, `DeveloperStudio.tsx`의 `/v1/workspaces/${id}/…`; `/v1/runs/${id}/…`.
- 이 id-scoped 경로는 백엔드에 **제공된다**: `app.py:566 /v1/workspaces/{workspace_id}/terminal-tickets`, `:579 /terminals/{session_id}`, `:730 /edit-lock`; `app.py:396–424 /v1/runs/{run_id}/result|artifacts|logs|attempts`, `:750 /v1/runs/{run_id}/bindings`.
- `route_coverage`의 `_CLIENT_HEAD`(`/v1/[^"'`]*?\$\{`)가 `/v1/workspaces/${id}/…` 같은 템플릿에서 `${` **앞부분** `/v1/workspaces`(및 `/v1/runs`)를 별도 head로 추출해 생긴 **가짜 미제공**이다. (오늘 아침 템플릿 리터럴 누락 오보와 같은 계열의 도구 한계.) **누락 엔드포인트가 아니다.**

## E. 방법과 한계
- `apps/web` 클라이언트 호출과 두 백엔드 라우트 데코레이터(+APIRouter prefix)를 직접 grep 대조. catch-all/동적 등록 부재 확인. 실제 HTTP 요청을 보낸 것은 아니며(런타임 미실행), 소스 정의 기준 판정이다.
- **인접 관찰(6건 밖, 참고)**: 프론트의 일부 id-scoped 호출이 백엔드의 project-scoped 형태와 어긋난다 — 예: `RunDetail.tsx:720`의 `/v1/runs/{id}/events`와 `api-proxy.test.ts`의 `/v1/runs/{id}/cancel`은 백엔드가 `/v1/projects/{}/runs/{}/events`·`/cancel`로만 제공한다. 이는 A1의 events 불일치와 같은 계열일 수 있으나 사용자 6건 범위 밖이므로 별도 확인이 필요하면 후속으로 본다.

## F. 다음
사용자가 A(3건)를 Gemini에 전달. Codex 복구 시 백엔드 계약 방향(엔드포인트 추가 여부) 판단. D(3건)는 조치 불필요(오탐)로 기록 종료. Claude는 확인·기록까지 수행했고 단독 구현하지 않는다.
