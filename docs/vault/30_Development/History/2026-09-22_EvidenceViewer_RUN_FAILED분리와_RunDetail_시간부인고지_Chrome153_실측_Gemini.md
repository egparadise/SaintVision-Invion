---
doc_id: "HIST-2026-09-22-EVIDENCE-RUN-FAILED-AND-RUNDETAIL-TIMES"
title: "EvidenceViewer RUN_FAILED 상태 분리 및 RunDetail 시간 부인 고지 Chrome 153 실측"
version: "1.0.0"
status: "completed"
author: "Gemini"
reviewer: "Codex"
created: "2026-09-22T08:25:00+09:00"
updated: "2026-09-22T08:25:00+09:00"
source_of_truth: "Git"
branch: "integration/all-agents-unified"
---

# EvidenceViewer RUN_FAILED 상태 분리 및 RunDetail 시간 부인 고지 Chrome 153 실측

## 1. 개요 및 배경

사용자의 두 가지 핵심 지적에 따라 결함 치유 및 브라우저 실측을 수행했다:

1. **실행 실패(`state === 'failed'`)와 출력 무결성 검증 실패(`FAIL`)의 엄격한 분리**:
   - 기존 구현에서는 실행이 실패하여 산출물이 아예 생성되지 않은 상태에서도 화면이 "출력 무결성 검증 실패 (FAIL)" 뱃지를 표출하고 있었다.
   - 실행 실패는 프로세스 비정상 종료(exitCode != 0, OOMKilled, 타임아웃 등)이며 출력이 부재한 상태이다. 이를 "출력 무결성 검증 실패(데이터 위조/손상)"로 둔갑시키는 것은 심각한 사실 왜곡이자 공포 조장이다.
   - 따라서 독립 상태인 **`RUN_FAILED` (`✗ 실행 실패 · 출력 부재`)**를 신설하고 명확한 안내 배너로 분리했다.

2. **죽은 분기(`res.output.verified === false`)의 계약적 맥락 명시**:
   - 백엔드 계약(`core.schema.json`)에서 `ResultOutputMetadata.verified`는 `"const": true`이므로 정상 서버는 `false`를 반환할 수 없다. (서버는 저장소 손상 시 HTTP 500 `VERIFY-0023`으로 fail-closed 차단)
   - 프런트엔드의 `false` 검사는 계약 완화(향후 boolean 확장) 및 위조 주입 방어를 위한 방어적 분기(Dead Branch)임을 코드에 명시했다.

3. **RunDetail 시간 표시 및 부인 고지 문장 브라우저 실측**:
   - `RunDetail.tsx`의 긴 시간 부인 고지("실행 완료 시각이 로그 캡처 시각이 아니다" 등)가 실제 Google Chrome 153에서 잘리거나 겹치지 않고 온전히 읽히는지 Blink 엔진에서 실측했다.

---

## 2. 작업 내용 및 구현

### 2.1 `EvidenceViewer.tsx` 상태 분리

- `EvidenceData.integrityVerification` 유니온 타입을 4대 상태로 확장:
  - `'PASS' | 'FAIL' | 'UNVERIFIED' | 'RUN_FAILED'`
- 상태 판정 및 배너 표출 우선순위 정립:
  1. `res.output && res.output.verified === false`: `FAIL`
     - 뱃지: `✗ 출력 무결성 검증 실패 (FAIL)` (적색)
     - 배너: `data-testid="evidence-failed-warning"` (암호학적 해시 불일치 / 산출물 손상 경고)
  2. `res.state === 'failed'`: `RUN_FAILED`
     - 뱃지: `✗ 실행 실패 · 출력 부재 (RUN_FAILED)` (자주색)
     - 배너: `data-testid="evidence-run-failed-notice"` ("저장소 출력물 손상이 아닌 프로세스 비정상 종료로 산출물이 부재합니다")
  3. `res.output?.verified === true`: `PASS`
     - 뱃지: `✓ 출력 무결성 검증 통과 (PASS)` (녹색)
     - 배너: `data-testid="evidence-verified-policy"`
  4. 그 외: `UNVERIFIED`
     - 뱃지: `⚠️ 출력 무결성 미검증 (UNVERIFIED)` (호박색)
     - 배너: `data-testid="evidence-unverified-notice"`

### 2.2 Vitest DOM 가드 보강 (`apps/web/tests/evidence-viewer-integrity-guard.test.tsx`)

- Test 3: `state === 'failed'`일 때 `RUN_FAILED` 뱃지와 실행 실패 배너가 표출되고 `FAIL` 배너는 없음을 단언.
- Test 4 (신설): `res.output.verified === false`일 때 `FAIL` 뱃지와 위조 경고 배너가 표출됨을 단언.
- 결과: **4/4 passed 100%**.

### 2.3 검속 도구 확장 (`tools/run_real_browser_acceptance.py`)

- 총 8대 시나리오로 확장:
  - `--scenario rundetail-times`: 헤더 3대 시간, Tab 2 실시간 SSE 로그 시간 부인 고지, Tab 3 산출물 시간 부인 고지, Tab 5 분산 샤드 원장 시간 부인 고지 전수 검속.
  - `--scenario evidence-run-failed`: 실행 실패(`state: 'failed'`) 시 `RUN_FAILED` 표출 및 `PASS`/`FAIL` 부재 검속.
- Uvicorn 테스트 앱에 `ResultView.logs` 및 `Control.shards` 라우트 바인딩 완료.

---

## 3. 실제 브라우저(Google Chrome 153) 실측 결과

- **`rundetail-times` 시나리오**:
  - `scratch/real_chrome_rundetail_header_times.png`: 헤더 3대 시간(생성, 상태갱신, 완료) 겹침 없이 한 줄 렌더링 확인.
  - `scratch/real_chrome_rundetail_tab2_logs_freshness.png`: 괄호 설명("실시간 로그 캡처나 화면 갱신 시각이 아닙니다") 잘림 없이 완결 표출 확인.
  - `scratch/real_chrome_rundetail_tab3_artifacts_freshness.png`: 산출물 설명("파일 다운로드 또는 화면 조회 시각이 아닙니다") 깨끗하게 표출 확인.
  - `scratch/real_chrome_rundetail_tab5_shards_freshness.png`: 샤드 설명("단일 공통 스냅샷이나 조회 시각이 아닙니다") 및 ADR-028/041 배너 계층 정합 확인.
- **`all-evidence` 4대 무결성 시나리오**:
  - `evidence-verified`: `✓ 출력 무결성 검증 통과 (PASS)` 실측.
  - `evidence-unverified`: `⚠️ 출력 무결성 미검증 (UNVERIFIED)` 실측.
  - `evidence-run-failed`: `✗ 실행 실패 · 출력 부재 (RUN_FAILED)` 실측 (`scratch/real_chrome_evidence_run_failed.png`).
  - `evidence-failed`: `✗ 출력 무결성 검증 실패 (FAIL)` 실측 (`scratch/real_chrome_evidence_failed.png`).
- 전체 8대 시나리오 JSON: `scratch/chrome_real_uvicorn_acceptance_result.json` (`passed: true`).

---

## 4. 게이트 검증 실측치

- `pytest tests/test_route_coverage.py`: 30 passed in 1.00s.
- `cd apps/web && npx tsc -b && npm run build`: exit code 0 (타입 오류 0건, Vite 빌드 성공).
- `python tools/check_frontend_integrity.py`: 82개 파일 0 violations (PASS).
- `python tools/check_contract_bindings.py`: 46 fixtures / 12 anchors PASS.
- Vitest: **75개 파일 653/653 passed 100%**.
- `python tools/check_docs.py`: PASS.
- `python tools/check_doc_single_source.py --ratchet`: PASS.
