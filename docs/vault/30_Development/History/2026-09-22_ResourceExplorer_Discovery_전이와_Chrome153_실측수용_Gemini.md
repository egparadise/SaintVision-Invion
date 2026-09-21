---
doc_id: "GEMINI-RESOURCE-EXPLORER-DISCOVERY-CHROME153-001"
title: "ResourceExplorer 디스커버리 전이 실측과 Google Chrome 153 브라우저 수용 완결 — Gemini"
version: "1.0.0"
status: "active"
author: "Gemini"
reviewer: "Codex"
checked_at_tip: "275af02c"
updated: "2026-09-22T03:15:00+09:00"
source_of_truth: "Git"
tags: ["frontend", "discovery-candidates", "resource-explorer", "chrome153", "real-browser", "mutation-testing", "contract-binding"]
---

# ResourceExplorer 디스커버리 전이 실측과 Google Chrome 153 브라우저 수용 완결

## 1. 개요 및 착수 배경

### (1) Codex Uvicorn Wire 헤더 대소문자 확인 결과
- **확인 사실**: `apps/web/src/shared/api/runArtifactObservation.ts` (L83, L109)는 Fetch API의 네이티브 `res.headers` 인스턴스를 사용함.
- `Headers.get('x-content-sha256') || res.headers.get('X-Content-SHA256')` 형태로 조회하며, HTTP 스펙상 `Headers.get()`은 case-insensitive하게 동작함.
- 중간에 plain object(`{}`)로 변환하여 대소문자를 가리는 결함이 없으므로, Uvicorn wire 상에서 소문자 `x-content-sha256`으로 도착하더라도 100% 안전하게 읽힘을 확인 완료함.

### (2) Claude 독립 검토 인계 사항 및 착수 항목 선정
- Claude 독립 검토(`2026-09-21_UI_static_markup감사_Claude독립검토.md`):
  - `fabric-control-plane.test.tsx`가 `renderToStaticMarkup` SSR에서 props 주입으로만 렌더링을 검증하여, `ResourceExplorer.tsx`의 실제 `useEffect` 비동기 fetch 전이(`loadDiscoveryCandidates`) 결함을 전혀 잡지 못함.
  - 기존 DOM 테스트(`resource-explorer-dom.test.tsx`)는 정본 계약 fixture(`contracts/fixtures/discovery-candidates-response.json`)가 아닌 임의 shape의 mock 객체(`state: 'pending'`)를 사용하여 mock-계약 간 괴리가 존재함.
- **선정 항목**: `ResourceExplorer.tsx`의 Discovery Candidates (Tab 5) 및 Storage Contributions (Tab 1) 비동기 전이(effect → state → render)의 정본 계약 결속 및 실제 Google Chrome 153 브라우저 마운트 실측 수용.
- **선정 이유 (한 줄)**: 지금까지 `renderToStaticMarkup`의 props 주입으로만 덮여 있어 `setCandidates([])` 같은 실제 비동기 전이 결함을 잡지 못하던 화면 핵심 영역(가상 패브릭)이며, 백엔드 라우트(`GET /v1/discovery/candidates`) 및 계약 fixture가 실재하고 확립된 Chrome 153 실측 인프라로 즉시 눈으로 렌더링과 승인/거부 컨트롤을 확인할 수 있기 때문.

---

## 2. DOM 단위 테스트 보강 및 돌연변이(Mutation) 사살

### (1) 정본 계약 Fixture 바인딩 테스트 추가
- `apps/web/tests/fixtures/discovery-candidates.ts`:
  - `happy-dom` 환경에서 URL 스키마 이슈 없이 정본 계약 fixture(`contracts/fixtures/discovery-candidates-response.json`)를 안전하게 읽을 수 있도록 resilient path resolution 적용.
- `apps/web/tests/resource-explorer-dom.test.tsx`:
  - `it('proves canonical contract fixture binding: renders exact wire candidate and admission controls with state="candidate"')` 추가.
  - 정본 계약 와이어 상의 `state: 'candidate'` 속성을 가진 후보 노드(`fixture-node`, `192.0.2.41`, `8C · 32 GB · 1 GPU`)가 실제 DOM에 렌더링되고, 승인 버튼(`승인 & 토큰 발급`)과 거부 버튼이 노출되며, 클릭 시 부트스트랩 토큰 발급 모달(`admission-result-modal`)이 나타나는지 단언.

### (2) 돌연변이(Mutation) 검증 결과: 4개 시험 동시 사살 (KILLED)
- **변형 주입**: `ResourceExplorer.tsx` L330의 `setCandidates(res?.items || [])`를 `setCandidates([])`로 변경 (후보 목록 유실 회귀).
- **실측 결과**:
  ```
  FAIL tests/resource-explorer-dom.test.tsx (4 failed, 21 passed)
  - proves success-with-data transition: KILLED
  - proves candidate -> empty re-query transition: KILLED
  - proves candidate -> error re-query transition: KILLED
  - proves canonical contract fixture binding: KILLED
  ```
- 변형 원복 후 25개 테스트 100% 합격 복구 확인.

---

## 3. Google Chrome 153 실제 브라우저 실측 수용

- **실행 환경**:
  - 브라우저: Google Chrome 153.0.7070.0 (Official Build, Windows x64)
  - 런타임: Playwright (`.venv\Scripts\python.exe`)
  - 웹 서버: Vite 6.4.3 (Port 3005)
- **검증 스크립트**: `scratch/verify_discovery_chrome.py`
- **수행 및 실측 증거**:
  1. **PKCE 세션 인증 및 대시보드 진입**: `window.__SAINTVISION_CONFIG__` 주입 후 `/callback` 완료.
  2. **가상 패브릭 탭 진입**: 상단 헤더의 `가상 패브릭 (CX-01)` 클릭하여 `ResourceExplorer` 마운트 확인 (`내 컴퓨터 (SaintVision Virtual Computer)`).
  3. **디스커버리 탭 (Tab 5) 비동기 전이 실측**:
     - `GET /v1/discovery/candidates` 네트워크 호출.
     - Chrome Blink 엔진에서 `fixture-node` 카드, IP `192.0.2.41`, `ann_contract_fixture_01`, `CANDIDATE` 뱃지, `자체 보고: linux · 8C · 32 GB · 1 GPU`, `승인 & 토큰 발급`, `거부` 버튼 렌더링 확인.
     - **스크린샷**: `scratch/real_chrome_discovery_candidates.png`
  4. **승인 버튼 상호작용 및 일회용 부트스트랩 토큰 발급 실측**:
     - `승인 & 토큰 발급 (POST /candidates/ann_contract_fixture_01/admission)` 클릭.
     - Chrome 뷰포트에 `🎉 일회용 부트스트랩 토큰 발급 완료 (Bootstrap Token Minted)` 모달 렌더링 및 `btk_chrome_153_verified_token_777` 표출 확인.
     - **스크린샷**: `scratch/real_chrome_discovery_admission_minted.png`
  5. **스토리지 기여 원장 탭 (Tab 2) 비동기 전이 실측**:
     - `GET /v1/storage/contributions`, `GET /v1/storage/locations` 호출 및 `C:\SaintVision\StorageData` 테이블 렌더링 확인.
     - **스크린샷**: `scratch/real_chrome_storage_contributions.png`
  6. **검증 결과 JSON**: `scratch/chrome_discovery_acceptance_result.json` (`passed: true`).

---

## 4. 검증 게이트 통과 지표

- `npm test` (apps/web): 71 files, **632 passed** (0 failed).
- `python tools/check_frontend_integrity.py`: 82 files, **0 violations** (All 7 rules satisfied).
- `python tools/check_contract_bindings.py`: 38 fixtures referenced, 12 serving-anchors bound (**PASS**).
- `python tools/check_docs.py`: 705 versioned documents, 48 tasks, 12 outcomes (**PASS**).

---

## 5. 인계 사항
- `ResourceExplorer.tsx`의 Discovery 및 Storage 비동기 전이가 단위 DOM 테스트 및 Google Chrome 153 실제 브라우저 양 레인에서 100% 실측 수용됨.
- 다음 단계: Claude / Codex 레인의 백엔드 신선도 잔여 필드 노출 및 자원 사용량 읽기 계약 진행과 연계.
