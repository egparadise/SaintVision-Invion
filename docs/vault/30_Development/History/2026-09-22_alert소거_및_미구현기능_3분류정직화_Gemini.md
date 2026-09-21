# 2026-09-22 브라우저 alert() 18개소 전소 및 3분류(오류·성공·미구현) 정직화 작업 기록 (Gemini)

- **작성자**: Gemini (Frontend & Design Lane)
- **일시**: 2026-09-22 01:20 KST
- **작업 브랜치**: `integration/all-agents-unified`
- **목표**: 프론트엔드 전역의 브라우저 블로킹 다이얼로그 `alert()` 잔여 18개소 전면 소거 및 웹 접근성(WAI-ARIA `role="alert"` / `role="status"`) 정합, 기계적 치환 금지 및 3대 분류 판정 완결.
  1. **Zero Alert Invariant**: `apps/web/src` 전역에서 브라우저 블로킹 `alert(` 호출 0건 달성 (정적 분석 불변식 검증).
  2. **Class 1 (오류 알림)**: 백엔드 API 호출 실패, 권한 부족, 컨텍스트 부재 등 ➔ WAI-ARIA `role="alert"` 인라인 배너로 전환하여 스크린 리더 및 단위 테스트 단언 가능화.
  3. **Class 2 (성공/완료 알림)**: 산출물 다운로드 완료, 복구 단계 준비 완료, 영수증 수신 완료 ➔ WAI-ARIA `role="status"` 인라인 피드백 배너로 전환.
  4. **Class 3 (미구현 고지 / 뒤가 없는 기능 / 동작 불가 가드)**: 누르기 전에 알 수 있도록 사전에 버튼 비활성화(`disabled={true}`, `title`, `aria-describedby`)하고 `role="status"` 인라인 상태/안내로 정직화.
  5. **Class 3(화면에 있으나 백엔드 구현이 없거나 조건 미충족인 기능) 전수 집계 및 보고**: 총 4개소 식별 및 정합 완료.

---

## 1. 18개소 전수 감사 및 3대 분류 판정 매트릭스

| 대상 파일 | 라인 | 기존 alert 호출 내용 | 판정 분류 | 정직화 처리 내용 |
| :--- | :--- | :--- | :--- | :--- |
| `App.tsx` | L251 | `alert('승인 처리 실패: ...')` | **Class 1 (오류)** | 전역 인라인 에러 배너 `app-global-action-error` (`role="alert"`) 표출 및 닫기 버튼 제공 |
| `App.tsx` | L266 | `alert('승인 반려 실패: ...')` | **Class 1 (오류)** | 전역 인라인 에러 배너 `app-global-action-error` (`role="alert"`) 표출 |
| `App.tsx` | L278 | `alert('취소를 확인하지 못했습니다...')` | **Class 1 (오류)** | 전역 인라인 에러 배너 `app-global-action-error` (`role="alert"`) 표출 |
| `NodeList.tsx` | L85 | `onAction={() => alert('Agent 설치 가이드: python -m saintvision.agent --bootstrap')}` | **Class 3 (미구현/가짜액션)** | 허위 팝업 소거, 버튼을 "Node Agent 설치 안내/접기" 토글로 전환하고 인라인 부트스트랩 안내 영역 `node-agent-install-guide` (`role="status"`) 및 명령어 복사 피드백 제공 |
| `DeveloperStudio.tsx` | L437 | `alert('실행 진행 중인 작업의 아티팩트는 다운로드할 수 없습니다...')` | **Class 3 (동작불가 가드)** | 실행 중(`state === 'running'`) 시 다운로드 버튼 사전 비활성화(`disabled`), title에 "실행 완료 후 활성화" 사전 안내 명시, 프로그래밍 호출 시 `studio-action-notice` (`role="status"`) 안내 |
| `DeveloperStudio.tsx` | L445 | `alert('선택된 프로젝트가 없어 아티팩트를 다운로드할 수 없습니다.')` | **Class 1 (오류/컨텍스트 부재)** | `studio-action-notice` (`role="alert"`, `type: 'error'`) 표출 |
| `DeveloperStudio.tsx` | L464 | `alert('서버로부터 유효한 실행 결과 아티팩트를 수신하지 못했습니다...')` | **Class 1 (오류/수신 실패)** | `studio-action-notice` (`role="alert"`, `type: 'error'`) 표출 |
| `DeveloperStudio.tsx` | L476 | `alert('레거시 산출물 목록이 비어 있거나 산출물을 찾을 수 없습니다.')` | **Class 1 (오류/결과 부재)** | `studio-action-notice` (`role="alert"`, `type: 'error'`) 표출 |
| `DeveloperStudio.tsx` | L481 | `alert('레거시 아티팩트 목록 조회 실패: ...')` | **Class 1 (오류/조회 실패)** | `studio-action-notice` (`role="alert"`, `type: 'error'`) 표출 |
| `DeveloperStudio.tsx` | L486 | `alert('산출물 검증 및 다운로드 요청 실패: ...')` | **Class 1 (오류/요청 실패)** | `studio-action-notice` (`role="alert"`, `type: 'error'`) 표출 |
| `DeveloperStudio.tsx` | L494 | `alert('서버로부터 유효한 실행 결과 아티팩트를 수신하지 못했습니다...')` | **Class 1 (오류/유효성 실패)** | `studio-action-notice` (`role="alert"`, `type: 'error'`) 표출 |
| `DeveloperStudio.tsx` | L529 | `alert('아티팩트 다운로드 실패: ...')` | **Class 1 (오류/네트워크 예외)** | `studio-action-notice` (`role="alert"`, `type: 'error'`) 표출 |
| `DeveloperStudio.tsx` | L542 | `alert('실행 진행 중인 작업의 산출물 파일은 다운로드할 수 없습니다...')` | **Class 3 (동작불가 가드)** | 실행 중(`state === 'running'`) 시 원시 파일 바이트 다운로드 버튼 사전 비활성화(`disabled`), title에 "실행 완료 후 활성화" 사전 안내 명시, 프로그래밍 호출 시 `studio-action-notice` (`role="status"`) 안내 |
| `DeveloperStudio.tsx` | L554 | `alert('선택된 프로젝트가 없어 파일을 다운로드할 수 없습니다.')` | **Class 1 (오류/컨텍스트 부재)** | `studio-action-notice` (`role="alert"`, `type: 'error'`) 표출 |
| `DeveloperStudio.tsx` | L581 | `alert('산출물 파일 바이트 다운로드 실패: ...')` | **Class 1 (오류/바이트 다운로드 실패)** | `studio-action-notice` (`role="alert"`, `type: 'error'`) 표출 |
| `DeveloperStudio.tsx` | L626 | `alert(err.problem?.detail || ...)` | **Class 1 (오류/재개 준비 실패)** | `studio-action-notice` (`role="alert"`, `type: 'error'`) 표출 |
| `DeveloperStudio.tsx` | L655 | `alert('물리 정지 영수증(NodeStopReceipt) 조회 실패: 해당 실행(...)의 영수증이 아직 발행되지 않았거나...')` | **Class 3 (백엔드 미발행 안내)** | 치명적 오류가 아닌 영수증 미발행/미보관 상태 안내이므로 `studio-action-notice` (`role="status"`, `type: 'info'`) 인라인 안내로 정직화 |
| `DeveloperStudio.tsx` | L660 | `alert('물리 정지 영수증(NodeStopReceipt) 조회 실패: ...')` | **Class 1 (오류/API 예외)** | `studio-action-notice` (`role="alert"`, `type: 'error'`) 표출 |

---

## 2. Class 3 (미구현 / 뒤가 없는 기능 / 사전 차단 대상) 전수 집계 보고

화면에 액션 UI가 존재하나 백엔드 라우트가 없거나, 조건 미충족으로 동작할 수 없는데 기존에 브라우저 alert 팝업을 띄우던 대상은 **총 4개소**로 집계됨:
1. **`NodeList.tsx` L85 (Node Agent 부트스트랩 안내)**:
   - *문제점*: 빈 상태 화면에서 버튼을 누르면 라우트 이동이나 모달 없이 alert 창으로 CLI 명령어를 띄우는 허위 액션.
   - *정직화*: 버튼을 누르지 않아도 "아래 설치 안내를 확인하세요"를 명시하고, 버튼 클릭 시 alert 대신 인라인 상태 영역(`data-testid="node-agent-install-guide"`, `role="status"`)이 토글되어 `python -m saintvision.agent --bootstrap` 명령어와 클립보드 복사 피드백을 제공.
2. **`DeveloperStudio.tsx` L437 (실행 중 아티팩트 결과 다운로드 시도)**:
   - *문제점*: 백엔드에 아직 결과 아티팩트가 생성되지 않은 running 상태인데 다운로드를 눌러 alert를 마주하게 함.
   - *정직화*: 버튼에 `disabled={... || currentRun?.state === 'running'}`를 적용하고 `title="실행 진행 중인 작업의 아티팩트는 다운로드할 수 없습니다 (실행 완료 후 활성화)"`를 명시하여 누르기 전에 차단 사유를 안내.
3. **`DeveloperStudio.tsx` L542 (실행 중 원시 파일 바이트 다운로드 시도)**:
   - *문제점*: 실행 중인 작업의 원시 산출물 파일은 백엔드에 없는데 클릭 후 alert를 띄움.
   - *정직화*: 버튼에 `disabled={... || currentRun?.state === 'running'}`를 적용하고 `title="실행 진행 중인 작업의 산출물 파일은 다운로드할 수 없습니다 (실행 완료 후 활성화)"`를 명시하여 사전 차단.
4. **`DeveloperStudio.tsx` L655 (NodeStopReceipt 영수증 미발행/서버 미보관 상태)**:
   - *문제점*: 영수증이 아직 발행되지 않은 정상적인 진행/종료 대기 상태를 조회 실패 alert로 팝업 처리.
   - *정직화*: 치명적 에러 팝업 대신 인라인 안내 배너(`studio-action-notice`, `role="status"`)로 "물리 정지 영수증(NodeStopReceipt) 안내: 영수증이 아직 발행되지 않았거나 서버에 보관되어 있지 않습니다"를 차분하게 안내.

---

## 3. 세부 파일 구현 및 정합

### A. `apps/web/src/app/App.tsx`
- `const [actionError, setActionError] = useState<string | null>(null);` 추가.
- `handleApprove`, `handleReject`, `handleCancelRun` 핸들러에서 실패 시 `alert(...)` 대신 `setActionError(...)` 호출.
- 포털 뷰 및 `DesktopShell` 모드 상단에 전역 에러 배너 `app-global-action-error` (`role="alert"`) 및 닫기 버튼 렌더링.

### B. `apps/web/src/features/nodes/NodeList.tsx`
- `showInstallGuide`, `copiedGuide` 상태 추가.
- `EmptyState`에서 `alert(...)` 호출 액션 소거.
- 인라인 부트스트랩 가이드 `node-agent-install-guide` (`role="status"`) 및 클립보드 복사 버튼/피드백(`node-agent-copy-feedback`) 구현.

### C. `apps/web/src/features/studio/DeveloperStudio.tsx`
- `const [studioActionNotice, setStudioActionNotice] = useState<{ type: 'error' | 'status' | 'info'; message: string } | null>(null);` 추가.
- 4-Step Stepper 네비게이션 바로 아래에 모든 단계에서 접근 가능한 공통 배너 `studio-action-notice` (`role={type === 'error' ? 'alert' : 'status'}`) 렌더링 및 닫기 버튼 구비.
- 14개 alert 호출부를 Class 1(오류 -> error), Class 2(성공 -> status), Class 3(안내 -> info/status)으로 전수 치환.
- 다운로드 버튼 3종(`artifact-action-download-btn`, `artifact-raw-download-btn`, `artifact-meta-download-btn`)에 running 상태 및 digest 부재 시 사전 비활성화 사유를 명시하는 honest title 제공.

### D. 테스트 스위트 정합
1. **`apps/web/tests/alert-elimination-and-unimplemented-audit.test.tsx` 신규 작성**:
   - `apps/web/src` 전역 정적 분석: alert 호출 0건 불변식 단언 (M23 사살).
   - NodeList 빈 상태 인라인 안내 및 복사 피드백 단언.
   - DeveloperStudio 실행 중 다운로드 사전 비활성화 단언 (M24 사살).
   - DeveloperStudio 영수증 미발행 시 `role="status"` 인라인 안내 단언.
   - DeveloperStudio 복구 Step 준비 성공 시 `role="status"` 성공 피드백 단언.
   - App 로그인 세션 주입 후 전역 승인 반려 실패 시 `role="alert"` 인라인 배너 단언.
2. **`apps/web/tests/developer-studio-dom.test.tsx` 기존 8개 테스트 정합**:
   - 기존 `window.alert` 호출 단언을 `studio-action-notice` 배너 렌더링 및 WAI-ARIA role (`alert`/`status`) 단언으로 마이그레이션.

---

## 4. 검증 결과 및 증거 (Evidence)

1. **단위 테스트**:
   - `npm --prefix apps/web test tests/alert-elimination-and-unimplemented-audit.test.tsx`: 6 passed (100%).
   - `npm --prefix apps/web test tests/developer-studio-dom.test.tsx`: 18 passed (100%).
   - `npm --prefix apps/web test` (전체 스위트): **68 passed out of 68 test files (613 passed out of 613 tests, 100%)**.
2. **프로덕션 빌드**:
   - `npm --prefix apps/web run build`: `tsc -b && vite build` exit code 0.
3. **무결성 및 온톨로지**:
   - `python tools/check_frontend_integrity.py`: 80개 프로덕션 소스 검사 0 violations.
   - `python tools/check_docs.py`: 24 original hashes, 683 versioned docs, 48 tasks, PASS.
   - `.venv/Scripts/python tools/check_ontology.py`: RDF parsing, positive SHACL, 4 competency queries PASS.
