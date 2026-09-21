---
doc_id: "UI-FB03-DOM-VERIFICATION-GEMINI-001"
title: "UI-FB-03 DeveloperStudio 라우트 404 폴백 DOM 하네스, 캐시 은폐 제거 및 양방향 돌연변이 실증 완결 보고"
version: "1.2.0"
status: "verified"
author: "Gemini"
reviewer: "Codex"
updated: "2026-09-21T17:15:00+09:00"
code_ref_tip: "integration/all-agents-unified"
source_of_truth: "Git"
tags: ["ui-fb-03", "developer-studio", "route-404-fallback", "dom-harness", "mutation-testing", "happy-dom", "download-artifact", "cache-masking-elimination"]
---

# UI-FB-03 DeveloperStudio 라우트 404 폴백 DOM 하네스, 캐시 은폐 제거 및 양방향 돌연변이 실증 완결 보고

## 1. 개요 및 목적

Claude의 핸드오프 시험 스펙([[2026-09-21_FB-03_핸드오프_시험스펙_Claude]])에 명시된 통과 기준과 양방향 돌연변이 검증 기준을 충족하는 `DeveloperStudio` DOM 하네스 통합 시험(`apps/web/tests/developer-studio-dom.test.tsx`)을 구축한 데 이어:
1. **L454 다운로드 핸들러 사장 방어선 부활 및 양방향 돌연변이 실증** (마운트 효과 L294 + 다운로드 액션 L454)
2. **Codex 경계 검토 지적사항(정상 로드 후 401 발생 시 캐시 데이터가 오류를 가리는 결함)의 근본 조치 및 상주 시험 편입**
3. **거동 변경(Behavioral Change) vs 시험 추가(Test Addition)의 명확한 분리 및 캐시-신선도 절충 결론 도출**
4. **`apps/web/src/features/` 18개 전 디렉터리, 55개 컴포넌트 파일에 대한 전수 죽은 방어·캐시 은폐 감사(Dead Defense Audit)** 완결.

---

## 2. 세 가지 구분 원칙에 입각한 현황 분석

오늘 Claude의 지식 한계 오류 사례를 교훈 삼아, 아래 3개 범주를 엄격히 분리하여 기술한다:
1. **돌연변이로 실측해 깨진 것 (Measured Mutation Failures)**: 실제 코드를 변형하고 테스트 러너를 실행하여 포착된 구체적인 실패 내역.
2. **소스를 읽어 판단한 것 (Source-Read Analysis)**: 컴포넌트 JSX와 이벤트 핸들러 흐름 분석을 통해 도출된 논리적 인과관계.
3. **아직 확인 못 한 것 (Unverified / Deferred Invariants)**: 로컬 DOM 환경에서 직접 관측하지 않고 브라우저/실장비 레인으로 이관된 영역.

---

## 3. 거동 변경(Behavioral Change) vs 시험 추가(Test Addition) 분리 및 판단 근거

### 3.1 변경의 성격 분리
- **시험 추가 (Test Addition)**: 기존 코드의 불변식을 테스트 러너로 증명하기 위해 테스트 스위트(`developer-studio-dom.test.tsx`)에 DOM 마운트 및 다운로드 클릭 시나리오를 추가한 행위.
- **거동 변경 (Behavioral Change)**: 컴포넌트(`DeveloperStudio.tsx`)의 `handleDownloadArtifact`에서 다운로드 클릭 시 **로컬 캐시(`artifactData`)를 맹신하던 경로를 폐기하고, 서버 canonical `/result`를 매 다운로드마다 항상 조회하여 검증을 거치도록 변경**한 행위.

### 3.2 캐시와 신선도 절충의 결론: Option A 선택 (Option B 기각)
- **Option B (캐시 우선 및 실패 시 캐시 폴백 — 기각)**:
  - 컴포넌트 마운트 시 로드된 `artifactData`가 있으면 서버 조회를 생략하거나, 서버 조회가 401/403/500/네트워크 오류로 실패했을 때 조용히 이전 캐시를 내어주는 방식.
  - **기각 사유**:
    - **치명적 보안/권한 누수**: 사용자의 세션이 만료(401)되었거나 산출물 접근 권한이 박탈(403)되었음에도 조용히 파일이 다운로드되어 보안 경계가 무력화됨.
    - **오류 마스킹**: 백엔드 DB 연결 끊김(500)이나 서버 장애가 발생해도 사용자는 다운로드가 성공한 것으로 오인함.
    - **암호학적 감사 불변식 위배 (ADR-040/041/044)**: 다운로드되는 아티팩트 매니페스트는 검증 증거(`verifiedEvidenceId`), 정지 영수증(`executionReceipt`), 해시를 담은 법적/감사용 산출물이므로, 오래된 캐시 상태를 무단 서명해 내보낼 수 없음.
- **Option A (서버 최신 검증 조회 강제 및 실패 시 즉시 중단 — 최종 채택)**:
  - **핵심 명제**: **"캐시는 성공했을 때의 효율 수단이지 실패를 감추는 수단이 아니다."**
  - 다운로드 버튼 클릭 시 canonical `/result`를 항상 조회.
  - 401 Unauthorized, 403 Forbidden, 500 Server Error, 네트워크 거절, App-404 발생 시 **로컬 캐시로의 폴백을 엄격히 금지**하고, 사용자에게 정직하게 alert를 띄운 뒤 다운로드 처리를 즉시 중단(`return`).
  - 진짜 미매핑 라우트 404(`isRouteNotFoundError(err) === true`)인 경우에만 레거시 `/artifacts` 폴백을 시도하며, 이 폴백마저 실패하면 마찬가지로 에러를 알리고 중단.
  - **성능 영향 평가**: 다운로드는 초당 수백 회 발생하는 폴링 루프가 아니라 사람의 클릭 액션(human-triggered event)임. 인트라넷 통신 5~20ms는 사용자 인지 지연(100ms 미만) 범위 내이므로 UX 저하가 전무함.

---

## 4. Codex 경계 검토 지적사항(401 캐시 은폐) 결함 해소 및 실증

### 4.1 결함의 본질
초기 L454 복원 후 작성된 코드에서도 다음과 같은 치명적 누락이 존재했음:
```typescript
// 이전 버그 코드
try {
  const res = await apiClient<RunResultView>(`/v1/projects/${prjId}/runs/${activeRunId}/result`);
  ...
} catch (err: any) {
  if (isRouteNotFoundError(err)) {
    // legacy fallback
  }
  // 401, 403, 500 시 catch 블록에서 아무것도 하지 않고 빠져나감!
}
const effectivePayload = serverPayload || artifactData; // <-- artifactData 캐시가 살아있어 조용히 다운로드 실행!
```
- 초기 마운트 시 `artifactData`가 로드된 상태에서 다운로드 시점에 세션이 만료(401)되더라도, `serverPayload`가 null인 상태에서 `effectivePayload = artifactData`로 평가되어 에러가 사용자에게 노출되지 않고 이전 캐시 파일이 다운로드되었음.
- 기존 DOM 테스트 13종은 `artifactsCalls === 0`만 단언하여 이 "조용한 캐시 다운로드"를 잡지 못했음.

### 4.2 조치 내용 (`DeveloperStudio.tsx`)
1. 비-라우트 오류(401, 403, 500, 네트워크, 앱-404) 발생 시 즉시 에러 메시지를 `alert`하고 `return`하여 다운로드 생성을 차단.
2. `effectivePayload`를 `serverPayload`로 단일화하여 이전 메모리 캐시로의 무단 도피를 원천 차단.
3. 라우트 404 폴백(`/artifacts`) 실패 시에도 `alert` 후 즉시 `return`.

### 4.3 상주 DOM 시험 편입 (`apps/web/tests/developer-studio-dom.test.tsx`)
임시 확인용이 아닌 영구 상주 시험으로 다음을 단언:
- `Download Scenario 1 (401 Unauthorized)`: `/artifacts` 호출 0회, `window.alert` 정직한 실패 호출 단언, `window.URL.createObjectURL` 미호출(캐시 다운로드 차단) 단언.
- `Download Scenario 1b (403 Forbidden)`: `/artifacts` 호출 0회, `window.alert` 403 실패 호출 단언, `createObjectURL` 미호출 단언.
- `Download Scenario 2 (500 Internal Server Error)`: `/artifacts` 호출 0회, `window.alert` 500 실패 호출 단언, `createObjectURL` 미호출 단언.
- `Download Scenario 3 (Network Rejection)`: `/artifacts` 호출 0회, `window.alert` 네트워크 실패 호출 단언, `createObjectURL` 미호출 단언.
- `Download Scenario 4 (App-level 404 RES-RUN-404)`: `/artifacts` 호출 0회, `window.alert` 엔티티 부재 호출 단언, `createObjectURL` 미호출 단언.
- `Download Scenario 5 (Route-only 404)`: `/artifacts` 호출 1회, `window.alert` 미호출, `createObjectURL` 정상 호출 단언.
- `Download Scenario 6 (Route-only 404 + 레거시 폴백도 실패)`: `/artifacts` 호출 1회, `window.alert` 폴백 실패 호출 단언, `createObjectURL` 미호출 단언.

### 4.4 돌연변이 실측 (Mutant Kills Measured)
`DeveloperStudio.tsx`에 오류를 삼키고 캐시로 폴백하는 돌연변이 주입:
```typescript
// MUTATION: Swallow error and restore cache fallback
} else { }
const effectivePayload = serverPayload || artifactData;
```
- **실측 결과**: **5 FAILED** / 13 passed
  - `Download Scenario 1 (401)`: FAIL (`expected "vi.fn()" to be called with arguments: [ StringContaining ] - Number of calls: 0`)
  - `Download Scenario 1b (403)`: FAIL
  - `Download Scenario 2 (500)`: FAIL
  - `Download Scenario 3 (Network)`: FAIL
  - `Download Scenario 4 (App-404)`: FAIL
- **판정**: 캐시 은폐 버그가 5개 테스트에 의해 100% 포착 및 사살됨을 실측으로 확증.

---

## 5. 전수 죽은 방어·캐시 오류 은폐 훑기 (Comprehensive Dead Defense & Cache Masking Audit)

### 5.1 점검 대상 경계 (Explicit Boundary)
`apps/web/src/features/` 하위 **18개 전체 디렉터리, 55개 파일 전수 점검**:
- `admin` (3): `AdminSecurityConsole.tsx`, `securityEngine.ts`, `index.ts`
- `agent` (3): `NaturalLanguageRunView.tsx`, `agentEngine.ts`, `index.ts`
- `approvals` (3): `ApprovalCenter.tsx`, `ApprovalDetail.tsx`, `ApprovalReviewPanel.tsx`
- `auth` (3): `Login.tsx`, `pkce.ts`, `session.ts`
- `dashboard` (1): `ClusterOverview.tsx`
- `deployment` (3): `IntranetDeploymentView.tsx`, `deploymentEngine.ts`, `index.ts`
- `desktop` (8): `DesktopShell.tsx`, `DesktopWindow.tsx`, `ResourceExplorer.tsx`, `InvFileExplorer.tsx`, `ModelStudioView.tsx`, `TerminalSessionView.tsx`, `fabricControlApi.ts`, `desktopLayout.ts`
- `editor` (7): `MonacoWorkspaceEditor.tsx`, `DiffViewer.tsx`, `ConflictResolutionModal.tsx`, `GitCommitModal.tsx`, `diffEngine.ts`, `sessionRecovery.ts`, `index.ts`
- `evidence` (1): `EvidenceViewer.tsx`
- `mlops` (3): `ModelLineageView.tsx`, `mlopsEngine.ts`, `index.ts`
- `nodes` (2): `NodeDetail.tsx`, `NodeList.tsx`
- `placement` (4): `PlacementSimulator.tsx`, `PlacementExplainView.tsx`, `ResourceTopologyGraph.tsx`, `placementEngine.ts`
- `recovery` (3): `DistributedRecoveryView.tsx`, `recoveryEngine.ts`, `index.ts`
- `release` (3): `ReleaseCandidateView.tsx`, `releaseEngine.ts`, `index.ts`
- `runs` (2): `RunDetail.tsx`, `RunList.tsx`
- `studio` (2): `DeveloperStudio.tsx`, `index.ts`
- `terminal` (1): `WebTerminal.tsx`
- `workspaces` (3): `ExecutionResultView.tsx`, `WorkspaceCreateModal.tsx`, `WorkspaceList.tsx`

### 5.2 3대 점검 기준 및 발견·조치 내역
1. **유형 1: 외부 `disabled` 가드로 인한 내부 방어 도달 불가 (Disabled Guards Blocking Defenses)**
   - `ApprovalDetail.tsx`: `disabled={!canApprove}`와 내부 `if (!canApprove) return;`이 1:1 일치하여 방어가 중복 보호 상태임을 확인. (단위 테스트 28건 통과)
   - `DeveloperStudio.tsx`:
     - 영수증 대조 버튼(`inspect-receipt-btn`)에 불필요한 `disabled` 조건이 없으며, 영수증이 없을 때도 핸들러(`handleInspectReceipt`)에 도달하도록 보장.
     - 기존에 영수증이 `null`일 때도 모달을 열고 "✓ Lease 자원을 회수하였습니다"라고 허위 보고하던 결함을 발견. `if (receipt)` 분기로 수정하여, 영수증 부재 시 모달을 띄우지 않고 실패 alert를 출력하도록 교정. (양방향 돌연변이 실증 완결)
2. **유형 2: 캐시 단축 경로에 의한 라이브 오류 검증 우회 (Cache Short-Circuits)**
   - `DeveloperStudio.tsx`: `handleDownloadArtifact`가 초기 캐시 존재 시 라이브 검증을 건너뛰던 문제를 제거.
3. **유형 3: 캐시가 실패를 가리는 경로 (Cache Masking Failures)**
   - `DeveloperStudio.tsx`: `handleDownloadArtifact`에서 401/403/500 시 `artifactData`로 조용히 빠져나가던 결함 완제.
   - `DeveloperStudio.tsx`: `handleDownloadRawFile`에서 파일 다운로드 실패 시 로컬 에디터 소스코드(`fileObj.content`)를 산출물 바이트인 것처럼 둔갑시켜 다운로드하던 가짜 폴백 제거, 실패 alert 출력으로 교정.
   - `AdminSecurityConsole.tsx`: 노드 drain/resume 동기화 실패 시 로컬 상태만 변경하고 콘솔 로그만 남기던 문제를 발견. 서버 실패 시 로컬 변경사항을 즉시 롤백하고 사용자에게 alert를 표출하도록 보강.
   - `RunDetail.tsx`: `handleInspectReceipt`에서 영수증이 없을 때 조용히 아무 일도 일어나지 않던 현상을 alert 표출로 개선.
   - `ResourceExplorer.tsx`, `PlacementSimulator.tsx`, `EvidenceViewer.tsx`: catch 블록에서 캐시된 데이터를 내보내지 않고 `error` 상태 및 에러 배너(`role="alert"`)를 렌더링하고 있음을 확인.

---

## 6. 양방향 돌연변이 실증 종합 매트릭스 (`developer-studio-dom.test.tsx` 18종)

| 경로 / 대상 | 돌연변이 주입 코드 | 테스트 결과 | 포착된 실패 내역 (실측) |
|---|---|:---:|---|
| **경로 A: 마운트 아티팩트 자동 조회 (L294)** | `if (true)` | **6 FAILED** / 12 passed | Scenario 1~6 전수 실패 (`AssertionError: expected 1 to be +0`).<br>비-404 오류의 가짜 폴백 마스킹 포착. |
| **경로 A: 마운트 아티팩트 자동 조회 (L294)** | `if (false)` | **1 FAILED** / 17 passed | Scenario 7 실패 (`AssertionError: expected +0 to be 1`).<br>필수 404 라우트 폴백 누락 포착. |
| **경로 B: 다운로드 404 폴백 분기 (L458)** | `if (true)` | **5 FAILED** / 13 passed | Download Scenario 1~4 전수 실패.<br>비-404 오류 시 무단 `/artifacts` 호출 포착. |
| **경로 B: 다운로드 404 폴백 분기 (L458)** | `if (false)` | **1 FAILED** / 17 passed | Download Scenario 5 실패.<br>다운로드 시 필수 404 폴백 누락 포착. |
| **경로 C: 다운로드 캐시 은폐 (L474~480)** | `} else { }`<br>`payload = server \|\| cache;` | **5 FAILED** / 13 passed | Download Scenario 1, 1b, 2, 3, 4 동시 실패 (`expected "vi.fn()" to be called`).<br>401/403/500/네트워크 오류의 조용한 캐시 다운로드 100% 포착. |
| **경로 D: 영수증 대조 유효성 (L620)** | `if (true)` | **1 FAILED** / 17 passed | Receipt Scenario 1 실패 (`alert` 미호출 및 가짜 모달/회수 배너 노출 포착). |
| **경로 D: 영수증 대조 유효성 (L620)** | `if (false)` | **1 FAILED** / 17 passed | Receipt Scenario 2 실패 (유효 영수증 모달 렌더링 누락 포착). |
| **정규 복원 코드** | **정상 복원** | **18 PASSED** | 마운트 8종 + 다운로드 7종 + 영수증 2종 + 원본바이트 1종 전수 통과 (18/18). |

---

## 7. 소스를 읽어 판단한 것 (Source-Read Analysis)

1. **`isRouteNotFoundError`의 실물 불변식**:
   - `client.ts` L80~88에서 backend ProblemDetails `code`가 `RES-`, `APP-`, `SEC-`, `VAL-`로 시작하면 라우트 매핑이 존재하므로 `false`를 반환.
   - 따라서 App-404(`RES-RUN-404`)는 엔티티 부재이므로 마운트와 다운로드 양쪽 모두에서 `/artifacts`를 절대 호출하지 않음.
2. **`URL.createObjectURL` 및 `window.alert` 격리**:
   - 브라우저 DOM 다운로드 트리거 시 `document.body.appendChild(a)`, `a.click()` 수명주기가 발동하므로, `happy-dom` 환경에서 `URL.createObjectURL = vi.fn()`, `URL.revokeObjectURL = vi.fn()`, `window.alert = vi.fn()`으로 모의하여 비정상 종료 없이 안전하게 클릭 이벤트가 관측됨.
3. **영수증 및 원본 바이트 다운로드의 정직성**:
   - `handleDownloadRawFile` 실패 시 로컬 파일 편집 내용을 산출물로 속이지 않고 정직하게 에러를 알림.
   - `handleInspectReceipt` 시 영수증 부재 시 모달과 "Lease 자원 회수" 배너를 띄우지 않고 실패를 정직하게 고지.

---

## 8. 아직 확인 못 한 것 (Unverified / Deferred Invariants)

1. **실제 브라우저 파일 시스템 다운로드 바이트 일치**:
   - happy-dom 환경에서는 Blob 다운로드 링크 생성과 클릭 이벤트 발화까지만 검증함. 실제 OS 파일 시스템에 파일이 기록되고 바이트가 저장되는 것은 E2E/브라우저 스모크 레인의 관측 범위임.
2. **라이브 백엔드 HTTP 1.1 / HTTP 2 TLS 종단 협상**:
   - apiClient mock 하네스를 통한 계약 검증이므로 실제 네트워크 소켓 수준의 핸드셰이크는 별도 컨테이너 기동 검증 범위임.

---

## 9. 전체 검증 실적

- **Vitest 전체 스위트**: `npm test` -> **36개 파일, 354개 테스트 전수 통과 (354/354 passed, 100%, 0 failed)** (기존 344에서 +10건 순증)
- **Vite Production Build**: `npm run build` -> **Exit 0, 6.33s 클린 빌드 성공** (dist/index.html, dist/assets/index-DZOtar6Q.js 614.37 kB)
- **문서 무결성**: `python tools/check_docs.py` -> **PASS (611 versioned documents)**
- **온톨로지 정합성**: `.venv\Scripts\python.exe tools/check_ontology.py` -> **PASS (RDF/SHACL/48 tasks)**
- **백엔드 라우트 커버리지**: `pytest tests/test_route_coverage.py` -> **30 passed in 0.98s**
- **Obsidian Sync**: `tools/sync_obsidian.py --check` -> **1405 managed files, 0 pending, 0 conflicts**
