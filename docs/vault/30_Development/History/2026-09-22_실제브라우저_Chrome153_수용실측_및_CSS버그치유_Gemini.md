---
doc_id: "HIST-GEMINI-20260922-015"
title: "실제 브라우저(Real Chrome 153) 실측 수용 및 산출물 다운로드 무결성 3상태 검증과 CSS 버그 치유"
version: "1.0.0"
status: "approved"
author: "Gemini"
created: "2026-09-22T02:49:00+09:00"
updated: "2026-09-22T02:49:00+09:00"
source_of_truth: "Git"
---

# 실제 브라우저(Real Chrome 153) 실측 수용 및 산출물 다운로드 무결성 3상태 검증과 CSS 버그 치유

## 1. 작업 배경 및 목적
- **대역(jsdom)에서 실제 브라우저(Real Browser)로의 승격**:
  - 기존 628개 단위 테스트는 Vitest와 jsdom 환경에서 실행되었으며, 이는 브라우저의 대역(Mock)일 뿐 레이아웃 엔진(Blink)이나 네이티브 파일 다운로드 I/O 파이프라인을 온전히 대변하지 못한다.
  - 특히 `URL.createObjectURL`과 `<a download>` 클릭을 통한 파일 저장 파이프라인은 단위 테스트에서 함수 호출 스파이로만 검증되었을 뿐, 실제 브라우저 프로세스에서 다운로드가 발생하는지 검증된 바 없다.
  - 사용자 지침에 따라 시스템에 설치된 실제 Google Chrome 153과 Python Playwright를 결합하여 실제 브라우저 수용 검증을 수행하고, 화면 깨짐 및 3상태 다운로드 무결성을 실측한다.

---

## 2. 브라우저 실측 중 포착된 치명적 결함 및 치유

### [포착된 결함] jsdom이 잡지 못했던 17개 탭 헤더 가로 압축 붕괴 CSS 버그
- **현상**:
  - 1280×800 해상도의 실제 Chrome 153 브라우저에서 `/studio` 진입 시, 상단 헤더의 `<nav>` 내 17개 탭 버튼(`대시보드`, `디벨로퍼 스튜디오`, `작업공간`, `실행 목록` 등)이 가로 10~15px 폭으로 극단적으로 찌그러지며 한글 글자가 세로 1글자씩 기괴하게 깨져 아래로 쏟아져 내리는 심각한 렌더링 붕괴 포착.
- **원인**:
  - `apps/web/src/shared/ui/Header.tsx`의 `<nav>` 및 탭 버튼 스타일에 `whiteSpace: 'nowrap'` 및 `overflowX: 'auto'`, `flexShrink: 0` 속성이 누락되어 flex 레이아웃 엔진이 17개 요소를 강제로 줄여버림. jsdom은 CSS 렌더링 엔진이 없으므로 이 문제를 전혀 포착할 수 없었음.
- **치유 (`apps/web/src/shared/ui/Header.tsx`)**:
  - `<nav>`에 `overflowX: 'auto'`, `flex: 1`, `minWidth: 0`, `scrollbarWidth: 'none'` 적용.
  - 각 탭 `<button>`에 `whiteSpace: 'nowrap'`, `flexShrink: 0` 적용.
  - 우측 사용자/노드 요약 컨테이너에 `flexShrink: 0`, `whiteSpace: 'nowrap'` 결속하여 말끔한 1줄 가로 스크롤 레이아웃으로 완벽 복원.

---

## 3. 산출물 다운로드 무결성 3상태 Chrome 153 실측 완결

실제 Chrome 153을 가동하고 `page.expect_download()` 이벤트를 감시하여 실측한 결과는 다음과 같다:

| 상태 | 시나리오 | Chrome 153 관측 결과 | 파일 I/O 결과 | WAI-ARIA 배너 |
| :--- | :--- | :--- | :--- | :--- |
| **Case A (`verified`)** | 응답 바이트 SHA-256과 `X-Content-SHA256` 헤더 일치 | Chrome `download` 이벤트 1건 정상 발생 | `verified_model.bin` (45B) 로컬 디스크 저장 완료 (해시 일치) | `[무결성 검증 완료]` (`role="status"`) |
| **Case B (`mismatch`)** | 바이트 해시 불일치 (전송 중 변조/손상) | Chrome `download` 이벤트 **0건 (완전 차단)** | 파일 저장 안 됨 (I/O 0회) | `[무결성 검증 실패]` (`role="alert"`) |
| **Case C (`unverified`)** | 서버 응답에 `X-Content-SHA256` 누락 (조용한 강등 시도) | Chrome `download` 이벤트 **0건 (완전 차단)** | 파일 저장 안 됨 (I/O 0회) | `[무결성 검증 실패 · 필수 헤더 누락]` (`role="alert"`) |

### 실측 보존 아티팩트
- JSON 종합 결과: `scratch/real_browser_acceptance_results.json`
- 실제 Chrome 다운로드 바이너리 파일: `scratch/chrome_downloaded_verified.bin` (45 Bytes, SHA-256 `9f835f...` 일치)
- 실 브라우저 스크린샷 5종:
  - `stage0_raw_login.png`: 미설정 상태 브라우저 원시 진입 시 안전한 차단 및 alert 배너
  - `stage2_studio_step4.png`: Developer Studio Step 4 진입 화면 (CSS 치유 후)
  - `caseA_verified_notice.png`: Case A 검증 완료 배너
  - `caseB_mismatch_notice.png`: Case B 불일치 차단 배너
  - `caseC_downgrade_blocked_notice.png`: Case C 조용한 강등 차단 배너

---

## 4. 정직한 검증 경계 분리 (확인한 것 vs 확인하지 못한 것)

1. **확인한 것 (100% 실제 브라우저 실측)**:
   - Google Chrome 153 네이티브 렌더링 엔진(Blink) 및 CSS flex 레이아웃 계산.
   - Chrome 네이티브 WebCrypto API (`window.crypto.subtle.digest('SHA-256', ...)`) 실행 속도 및 일치성.
   - Chrome 네이티브 파일 다운로드 파이프라인 (`createObjectURL`, `<a download>`, `click()`, 디스크 I/O).
   - WAI-ARIA `role="status"` / `role="alert"` 스크린 리더 친화적 인라인 배너 렌더링.
2. **확인하지 못한 것 (정직한 경계 분리)**:
   - 본 테스트는 로컬 환경에 백엔드 포트 8080 서버가 가동 중이지 않은 상태에서 수행되었으므로, 네트워크 계층은 Playwright의 라우트 모의 주입을 통해 백엔드 스키마 계약(`core.schema.json`, `projects`, `session`, `runs`, `artifacts`)을 준수하는 응답을 브라우저에 공급함.
   - 실제 백엔드 8080 프로세스와의 종단간(End-to-End) 물리 통신은 백엔드 서버 가동 후 추가 검증이 필요함.

---

## 5. 게이트 통과 지표
- **단위/통합 테스트**: Vitest **70개 파일 628/628 passed 100%** (exit code 0)
- **프론트엔드 정직성 스캐너**: `tools/check_frontend_integrity.py` 82개 파일 **0 violations (7대 규칙 PASS)**
- **계약 바인딩 검사**: `tools/check_contract_bindings.py` 38 fixtures / 12 serving anchors PASS
- **문서 무결성**: `tools/check_docs.py` PASS
- **프로덕션 번들 빌드**: `tsc -b && vite build` exit code 0 (4.85s)
