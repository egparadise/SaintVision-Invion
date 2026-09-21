---
doc_id: "HIST-GEMINI-2026-09-22-APPROVAL-REVIEW-CHROME"
title: "ApprovalReviewPanel 비동기 전이와 Google Chrome 153 실측 수용 보고"
version: "1.0.0"
status: "approved"
author: "Gemini"
updated: "2026-09-22T03:30:00+09:00"
source_of_truth: "Git"
---

# ApprovalReviewPanel 비동기 전이와 Google Chrome 153 실측 수용 보고

- 작업 일시: 2026-09-22T03:30:00+09:00
- 배정: Gemini (Frontend & Browser Acceptance Owner)
- 검토 대상/기준: [[전체 개발 진행 현황]], [[Gemini 작업 현황]], [[설계 충돌 정정 및 ADR]], [[Frontend 최종 개발 계획]]
- 브랜치/커밋: `integration/all-agents-unified`

---

## 1. 배경 및 사용자 요청

1. **`.gitignore`에 `scratch/` 등록 및 보안 주의사항 명시**:
   - 로컬 브라우저 실측 스크립트, 스냅샷 스크린샷 이미지, JSON 결과 등이 git index에 추가되는 위험을 차단하기 위해 `.gitignore`에 `scratch/` 등록.
   - 실제 서버/운영 환경 검증 시 일회용 부트스트랩 토큰이나 일회용 비밀 등 자격증명이 표출되는 화면은 스크린샷(이미지)으로 저장하지 않아야 함을 검증 스크립트 상단에 명시.
2. **헤더 대소문자 wire 규격 확인 보고**:
   - `apps/web/src/shared/api/runArtifactObservation.ts`가 wire 상의 소문자 `x-content-sha256` 헤더를 안전하게 읽는지 확인 요구.
   - 확인 결과: Fetch API의 네이티브 `res.headers` 인스턴스(`.get('x-content-sha256')`)로 직접 조회하므로 HTTP 표준(RFC 7230/9110)에 따라 wire 상의 대소문자 표기에 구애받지 않고 100% 안전하게 판독함을 확인.
3. **남은 구현 범위 중 사용자 체감 핵심 컴포넌트 실측 수용**:
   - **선정 컴포넌트**: `ApprovalReviewPanel` (승인 검토 패널) 비동기 fetch 전이 및 승인 확정 인터랙션.
   - **선정 이유**: 기존 `approval-review.test.tsx`가 `renderToStaticMarkup` SSR에서 `reviewedAction` props 주입에만 의존하여 실제 `ApprovalReviewPanel`의 비동기 fetch 전이(`fetchApprovalReview` → `setLoaded` → `reviewedAction` 주입 → 승인 확정 버튼 활성화 게이트)가 미커버 상태였으며, 실제 거버넌스 승인 센터에서 사용자가 위험 작업의 스냅샷/명령 인자를 직접 검토하고 승인 버튼을 누르는 핵심 유저 저니를 Chrome 153 브라우저에서 직접 실측하기 위함.

---

## 2. 단위 테스트 보강 및 돌연변이 사살 (DOM Test & Mutation)

1. **`apps/web/tests/fixtures/approval-review.ts` resilient URL path 보강**:
   - `happy-dom` 환경의 URL 스키마 이슈 방지를 위해 `getFixturePath` 패턴 적용.
2. **`apps/web/tests/approval-review-panel-dom.test.tsx` 신규 작성 (4/4 passed)**:
   - **Test 1 (Loading State)**:
     - `fetchApprovalReview` 대기 중 `role="status"` "승인할 작업 내용을 조회하고 있습니다." 표출 확인.
     - 승인 버튼이 안전하게 비활성화(`disabled=true`)되어 있음을 단언.
   - **Test 2 (Success Transition & Command Argument Escaping)**:
     - 비동기 로드 완료 후 `승인할 작업 스냅샷` 헤더 및 `<pre>` 태그 내 명령어 인자 배열(`["echo", "two words", "<script>"]`)이 안전하게 이스케이프되어 렌더링됨을 확인.
     - 정책 다이제스트(`cccc...cccc`) 렌더링 확인.
     - `actionDigest`가 일치하여 승인 버튼이 활성화(`disabled=false`)되고 클릭 시 `onApprove` 콜백이 올바른 인자(`approvalId`, `nonce`, `reviewedAction`)로 호출됨을 단언.
   - **Test 3 (Failure Transition & Recovery)**:
     - `fetchApprovalReview` 거부 시 `role="alert"` "검토 내용을 확인하지 못했습니다. 승인이 보류됩니다." 에러 표출.
     - 승인 버튼 `disabled=true` 유지 확인.
     - `다시 조회` 버튼 클릭 시 로딩 상태로 재진입하여 정상 복구됨을 검증.
   - **Test 4 (Tamper Boundary Guard)**:
     - 다이제스트 불일치 또는 위조 발생 시 승인 버튼이 안전하게 차단(`disabled=true`)됨을 단언.
3. **돌연변이 사살 실측 (Mutation KILLED)**:
   - `ApprovalReviewPanel.tsx` L31에서 `reviewedAction`을 위조 다이제스트로 강제 주입하는 결함을 도입하자 Test 4가 즉시 실패(KILLED, `AssertionError: expected false to be true`)함을 실측하고 원복.

---

## 3. 실제 Google Chrome 153 브라우저 실측 수용

- **실행 환경**:
  - Google Chrome 153.0.7070.0 (공식 빌드 64비트, Blink 엔진)
  - Vite dev server (포트 3005)
  - Python Playwright 헤드리스 브라우저 러너 (`scratch/verify_approval_review_chrome.py`)
- **실측 시나리오 및 결과**:
  1. **정본 계약 fixture 결속**: `contracts/fixtures/approval-review-response.json` 정본 데이터를 직접 로드하여 모킹.
  2. **SSO 콜백 및 인증 저니**: PKCE 콜백(`/callback`)을 거쳐 `/studio` 진입.
  3. **승인 센터 네비게이션**: 상단 헤더의 `승인 센터` 탭 버튼을 클릭하여 `ApprovalCenter` 마운트 확인 (`거버넌스 승인 센터 (S04-FE)` 표출).
  4. **비동기 스냅샷 렌더링 검증**:
     - `GET /v1/projects/.../approvals/.../review`가 비동기 호출되어 `ApprovalReviewPanel`에 `승인할 작업 스냅샷` 렌더링.
     - 명령어 인자 `["echo", "two words", "<script>"]`가 Chrome DOM `<pre>`에 정확히 이스케이프되어 표출됨을 확인.
     - 정책 다이제스트 `cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc` 렌더링 확인.
  5. **Blink 엔진 승인 확정 버튼 활성화 실측**:
     - `actionDigest`가 결속되어 `canApprove`가 참으로 평가되고 `승인 확정` 버튼이 활성화(`disabled=false`)됨을 Blink 렌더러에서 직접 실측.
  6. **안전한 스냅샷 화면 캡처**:
     - 민감 자격증명이 없는 공개 검토용 작업 스냅샷 화면 캡처 완료 (`scratch/real_chrome_approval_review_snapshot.png`).
  7. **승인 확정 Wire Roundtrip 완결**:
     - `승인 확정` 버튼 클릭 시 Chrome 네이티브 Fetch를 통해 `POST .../challenge` (nonce 발급) → `POST .../decision` (승인 확정) → 신선한 목록 갱신(`/approvals`, `/runs`)이 차례대로 호출되어 왕복 완결됨을 확인 (`challenge_called: true, decision_called: true`).
  8. **결과 JSON 생성**:
     - `scratch/chrome_approval_review_acceptance_result.json` (`passed: true`).

---

## 4. 품질 및 무결성 게이트 검증 결과

1. **`npm test` (apps/web)**:
   - **72개 테스트 파일 636 passed 100% 통과** (순증 +1 파일, +4 passed).
2. **`python tools/check_frontend_integrity.py`**:
   - 82개 프런트엔드 프로덕션 소스 파일 검사 완료, 0 violations (PASS).
3. **`python tools/check_contract_bindings.py`**:
   - 38 fixtures / 12 serving anchors PASS.
4. **`python tools/check_docs.py`**:
   - 24 original hashes, 707 versioned documents, 48 tasks, 12 outcomes PASS.
5. **`python tools/check_doc_single_source.py --ratchet`**:
   - 18 pairs PASS.

---

## 5. 인계 사항

- Gemini 쪽 `ApprovalReviewPanel` 비동기 fetch 전이 및 Chrome 153 실측 수용 완료.
- 다음 담당: Claude 독립 검토 또는 후속 VF-GM 보강 트랙 진행.
