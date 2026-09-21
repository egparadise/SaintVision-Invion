---
doc_id: "UI-FB03-DOM-VERIFICATION-GEMINI-001"
title: "UI-FB-03 DeveloperStudio 라우트 404 폴백 DOM 하네스 및 양방향 돌연변이 실증 완결 보고"
version: "1.1.0"
status: "verified"
author: "Gemini"
reviewer: "Codex"
updated: "2026-09-21T16:45:00+09:00"
code_ref_tip: "c0436f6"
source_of_truth: "Git"
tags: ["ui-fb-03", "developer-studio", "route-404-fallback", "dom-harness", "mutation-testing", "happy-dom", "download-artifact"]
---

# UI-FB-03 DeveloperStudio 라우트 404 폴백 DOM 하네스 및 양방향 돌연변이 실증 완결 보고

## 1. 개요 및 목적

Claude의 핸드오프 시험 스펙([[2026-09-21_FB-03_핸드오프_시험스펙_Claude]])에 명시된 통과 기준과 양방향 돌연변이 검증 기준을 충족하는 `DeveloperStudio` DOM 하네스 통합 시험(`apps/web/tests/developer-studio-dom.test.tsx`)을 구축한 데 이어, 사용자의 438/454행(`handleDownloadArtifact`) 방어선 실증 질의에 따라 **(1) 마운트 효과 경로(L294)**뿐만 아니라 **(2) 사용자 아티팩트 다운로드 액션 경로(L454)**에 대해서도 완전한 양방향 돌연변이 실측 증명을 완결하였다.

---

## 2. 세 가지 구분 원칙에 입각한 현황 분석

오늘 Claude의 지식 한계 오류 사례를 교훈 삼아, 아래 3개 범주를 엄격히 분리하여 기술한다:
1. **돌연변이로 실측해 깨진 것 (Measured Mutation Failures)**: 실제 코드를 변형하고 테스트 러너를 실행하여 포착된 구체적인 실패 내역.
2. **소스를 읽어 판단한 것 (Source-Read Analysis)**: 컴포넌트 JSX와 이벤트 핸들러 흐름 분석을 통해 도출된 논리적 인과관계.
3. **아직 확인 못 한 것 (Unverified / Deferred Invariants)**: 로컬 DOM 환경에서 직접 관측하지 않고 브라우저/실장비 레인으로 이관된 영역.

---

## 3. L454 다운로드 핸들러 방어선 실측 및 결함 해소

### 3.1 1차 돌연변이 실측 (초기 상태의 공백 확인)
사용자의 지시에 따라 기존 테스트 스위트 상태에서 `DeveloperStudio.tsx` L454(`if (isRouteNotFoundError(err))`)를 변형하여 측정함:
- **`if (true)` 주입 실측**: `npm test` 결과 **344 passed, 0 failed** (아무것도 깨지지 않음).
- **`if (false)` 주입 실측**: `npm test` 결과 **344 passed, 0 failed** (아무것도 깨지지 않음).
- **실측 판정**: L454의 방어 코드는 컴포넌트에 존재하였으나, 이를 행사하는 시험 시나리오가 전무하여 양방향 돌연변이가 전혀 감지되지 않는 상태였음이 100% 실측으로 입증됨.

### 3.2 소스 분석을 통한 원인 규명
소스를 정밀 추적한 결과:
1. `handleDownloadArtifact`가 `let effectivePayload: any = artifactData; if (!effectivePayload) { ... }` 구조로 작성되어, 초기 마운트 시 `artifactData`가 캐시되어 있으면 서버 프로브(L440~464)를 아예 건너뛰고 있었음.
2. 반대로 `artifactData`가 `null`인 경우, UI 버튼에 `disabled={... || !artifactData?.outputHash}` 가드가 걸려 있어 사용자가 다운로드 버튼을 클릭할 수 없는 상태였음.
3. 결과적으로 L454는 캐시 존재 시에는 우회되고, 캐시 부재 시에는 클릭 불가로 인해 **실행 불가능한 사장 코드(Dead Code)** 상태였음.

### 3.3 해결 및 다운로드 사용자 액션 DOM 하네스 구축
1. **`DeveloperStudio.tsx` 정합**:
   - `handleDownloadArtifact` 실행 시 서버로부터 최신 ResultView(`/v1/projects/${prjId}/runs/${activeRunId}/result`)를 우선 조회하도록 복원.
   - `/result` 조회 실패 시 `isRouteNotFoundError(err)`를 평가하여 진짜 미매핑 404인 경우에만 `/artifacts` 폴백을 시도하고, 401/500/네트워크/앱404 오류 시에는 폴백을 엄격 차단한 뒤 로컬 캐시 `artifactData`를 사용하도록 정합.
   - 영수증 다운로드 버튼에 `data-testid="artifact-meta-download-btn"` 및 `data-testid="artifact-action-download-btn"`를 부여.
2. **DOM 하네스 내 다운로드 전용 시험 5종 신설 (`developer-studio-dom.test.tsx`)**:
   - 초기 마운트 성공 후 렌더된 다운로드 버튼(`artifact-meta-download-btn`)을 `act()` 블록 내에서 실제 `downloadBtn.click()`으로 발동.
   - 다운로드 프로브 시점의 5개 시나리오 검증:
     - `Download Scenario 1 (401 Unauthorized)`: `/artifacts` 호출 0회.
     - `Download Scenario 2 (500 Internal Server Error)`: `/artifacts` 호출 0회.
     - `Download Scenario 3 (Network Rejection)`: `/artifacts` 호출 0회.
     - `Download Scenario 4 (App-level 404 RES-RUN-404)`: `/artifacts` 호출 0회 (엔티티 부재는 폴백 차단).
     - `Download Scenario 5 (Route-only 404 Not Found)`: `/artifacts` 호출 정확히 1회 (레거시 호환 폴백).

---

## 4. 양방향 돌연변이 실증 매트릭스 (2개 경로 전수 증명)

### 4.1 경로 A: 마운트 아티팩트 자동 조회 효과 (L294)

| 돌연변이 주입 코드 | 테스트 결과 | 포착된 실패 내역 (실측) |
|---|:---:|---|
| **L294 `if (true)`** | **6 FAILED** / 7 passed | Scenario 1~6 전수 실패 (`AssertionError: expected 1 to be +0`).<br>비-404 오류가 가짜 폴백으로 마스킹되는 회귀 100% 포착. |
| **L294 `if (false)`** | **1 FAILED** / 12 passed | Scenario 7만 실패 (`AssertionError: expected +0 to be 1`).<br>필수 404 라우트 폴백 누락 회귀 100% 포착. |
| **L294 정규 복원** | **13 PASSED** | 마운트 시나리오 8종 전수 통과. |

### 4.2 경로 B: 사용자 다운로드 액션 프로브 (L454)

| 돌연변이 주입 코드 | 테스트 결과 | 포착된 실패 내역 (실측) |
|---|:---:|---|
| **L454 `if (true)`** | **4 FAILED** / 9 passed | Download Scenario 1~4 전수 실패 (`AssertionError: expected 1 to be +0`).<br>다운로드 시 비-404 오류(401, 500, 네트워크, 앱-404)의 무단 `/artifacts` 호출 100% 포착. |
| **L454 `if (false)`** | **1 FAILED** / 12 passed | Download Scenario 5만 실패 (`AssertionError: expected +0 to be 1`).<br>다운로드 시 필수 404 라우트 폴백 누락 100% 포착. |
| **L454 정규 복원** | **13 PASSED** | 다운로드 시나리오 5종 및 마운트 시나리오 8종 전수 통과 (13/13). |

---

## 5. 소스를 읽어 판단한 것 (Source-Read Analysis)

1. **`isRouteNotFoundError`의 실물 불변식**:
   - `client.ts` L80~88에서 backend ProblemDetails `code`가 `RES-`, `APP-`, `SEC-`, `VAL-`로 시작하면 라우트 매핑이 존재하므로 `false`를 반환.
   - 따라서 App-404(`RES-RUN-404`)는 엔티티 부재이므로 마운트와 다운로드 양쪽 모두에서 `/artifacts`를 절대 호출하지 않음.
2. **`URL.createObjectURL` 및 `window.alert` 격리**:
   - 브라우저 DOM 다운로드 트리거 시 `document.body.appendChild(a)`, `a.click()` 수명주기가 발동하므로, `happy-dom` 환경에서 `URL.createObjectURL = vi.fn()`, `URL.revokeObjectURL = vi.fn()`, `window.alert = vi.fn()`으로 모의하여 비정상 종료 없이 안전하게 클릭 이벤트가 관측됨.

---

## 6. 아직 확인 못 한 것 (Unverified / Deferred Invariants)

1. **실제 브라우저 파일 시스템 다운로드 바이트 일치**:
   - happy-dom 환경에서는 Blob 다운로드 링크 생성과 클릭 이벤트 발화까지만 검증함. 실제 OS 파일 시스템에 파일이 기록되고 바이트가 저장되는 것은 E2E/브라우저 스모크 레인의 관측 범위임.
2. **라이브 백엔드 HTTP 1.1 / HTTP 2 TLS 종단 협상**:
   - apiClient mock 하네스를 통한 계약 검증이므로 실제 네트워크 소켓 수준의 핸드셰이크는 별도 컨테이너 기동 검증 범위임.

---

## 7. 전체 검증 실적

- **Vitest 전체 스위트**: `npm test` -> **36개 파일, 349개 테스트 전수 통과 (349/349 passed, 100%, 0 failed)** (기존 344에서 +5건 순증)
- **Vite Production Build**: `npm run build` -> **Exit 0, 4.02s 클린 빌드 성공** (dist/index.html, dist/assets/index-rD3Fd9zW.js 614.27 kB)
- **문서 무결성**: `python tools/check_docs.py` -> **PASS (611 versioned documents)**
- **온톨로지 정합성**: `tools/check_ontology.py` -> **PASS (RDF/SHACL/48 tasks)**
- **백엔드 라우트 커버리지**: `pytest tests/test_route_coverage.py` -> **30 passed in 1.04s**
- **Obsidian Sync**: `tools/sync_obsidian.py --check` -> **1403 managed files, 0 pending, 0 conflicts**
