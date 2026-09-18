# 2026-09-18 19:15:00 KST EvidenceViewer 가짜 PASS 폴백 전면 제거 및 진본 오류 표면화 검증보고

## 1. 개요
- **목적**: `EvidenceViewer.tsx`에서 fetch 실패 시 가짜 무결성 검증 통과(`integrityVerification: 'PASS'`), 합성 `specDigest`, 가짜 `toolCalls`를 생성하여 사용자에게 성공으로 오인시키던 결함을 제거하고, 실제 백엔드 오류를 정직하게 표면화함. 또한 백엔드에 존재하지 않는 per-tool 텔레메트리(`toolCalls`, `wallTimeMs`)를 스키마에서 삭제하고, 보존 및 불변 봉인 항목을 '정적 시스템 정책 규격'으로 명확히 라벨링함.
- **담당 Agent**: Gemini (Frontend & Ingress Owner)
- **대상 브랜치**: `integration/all-agents-unified`

---

## 2. 세부 문제점 및 조치 내역

### A. 가짜 무결성 통과 (Fake PASS) 폴백 전면 제거
- **기존 문제**: `EvidenceViewer.tsx`의 `fetchEvidence` catch 블록에서 백엔드 호출이 404/500/네트워크 오류로 실패했을 때, `setEvidenceData(...)`로 합성 `specDigest`, 가짜 `toolCalls`(`git.checkout`, `test.run`, `artifact.write`), `integrityVerification: 'PASS'`를 주입하고 `errorMessage`를 표면화하지 않음. 이로 인해 백엔드가 다운되었거나 오류가 발생했음에도 사용자 화면에는 `✓ 무결성 검증 통과 (PASS)` 배너가 표시되는 심각한 진실성 왜곡이 발생함.
- **조치 결과**:
  1. `catch (err: any)` 블록에서 가짜 fallback 생성을 완전히 삭제하고 `setEvidenceData(null)` 처리.
  2. 실제 오류 메시지를 `setErrorMessage(...)`로 설정하여 `role="alert"` 경고 배너와 **재시도 (Retry)** 버튼을 노출.
  3. `✓ 무결성 검증 통과 (PASS)` 배너를 `evidenceData.integrityVerification === 'PASS'`일 때만 렌더링되도록 조건부 격리. 에러 발생 시 어떠한 성공 배너도 노출되지 않음.

### B. 백엔드 미제공 `toolCalls` 및 월타임 텔레메트리 제거
- **기존 문제**: 백엔드 커널 `result_view.py` 및 `output_ingestion.py`의 `RunResultView`는 프로세스 단위 `stopReceipt.exitCode`와 출력 단위 `evidence`를 제공할 뿐, per-tool `toolCalls` 및 `wallTimeMs` 텔레메트리를 반환하지 않음. 프론트엔드가 이를 가짜 배열로 하드코딩 및 합성하고 있었음.
- **조치 결과**:
  1. `EvidenceData` 인터페이스에서 `toolCalls?: Array<{ tool: string; exitCode: number; wallTimeMs: number }>` 속성을 완전히 제거.
  2. 코드 전반에서 가짜 `toolCalls` 합성 로직을 전면 삭제.

### C. 정적 정책 규격 vs 런타임 검증 결과의 명확한 분리
- **기존 문제**: 1년 보존 Pin(ADR-012) 및 불변 저장이 이번 실행에서 실측 검증된 동적 테스트 결과인 것처럼 렌더링되어 혼동을 유발함.
- **조치 결과**:
  1. 배너 라벨을 **`정책 규격: 1년 보존 Pin (ADR-012)`** 및 **`설계 규격: 불변 단일 봉인`**으로 명시하여, 시스템 아키텍처 상의 정적 정책 사양임을 사용자에게 정직하게 전달.
  2. 실행 단위의 동적 검증 결과는 `✓ 무결성 검증 통과 (PASS)` 또는 `✗ 무결성 검증 실패 (FAIL)`로만 분리 표현.

---

## 3. 영구 회귀 시험 구축 내역 ([`apps/web/tests/evidence-viewer.test.ts`](file:///C:/Project/SaintVision-Invion/apps/web/tests/evidence-viewer.test.ts))

1. **가짜 툴 호출 부재 단언**:
   - `EvidenceViewer.tsx` 소스 코드에 `git.checkout`, `test.run`, `artifact.write`, `wallTimeMs` 문자열이 일체 존재하지 않음을 단언.
2. **진본 에러 표면화 및 가짜 PASS 차단 단언**:
   - `catch` 블록이 반드시 `setEvidenceData(null)` 및 `setErrorMessage`를 호출함을 검증.
   - `✓ 무결성 검증 통과 (PASS)`가 `evidenceData.integrityVerification === 'PASS'` 조건 하에서만 렌더링됨을 단언.
3. **정적 정책 규격 명시 단언**:
   - `정책 규격: 1년 보존 Pin (ADR-012)` 및 `설계 규격: 불변 단일 봉인` 문자열이 컴포넌트 내에 올바르게 존재하는지 검증.
4. **커널 RunResultView 완결성 검증**:
   - 실제 커널이 반환하는 `RunResultView`(`evidenceId`, `specDigest`, `outputSha256`, `policyVersion`, `stopReceipt`)가 추가 엔드포인트나 가짜 툴 없이 `EvidenceData`의 모든 필수 필드를 100% 충족함을 검증.

---

## 4. 검증 결과
1. **Vitest 전체 스위트**:
   - 명령: `npm --prefix apps/web test -- --run`
   - 결과: **31개 파일 305 passed / 0 failed (3.03s)**
2. **Pytest 전체 스위트**:
   - 명령: `.venv\Scripts\pytest.exe tests/test_route_coverage.py tests/test_browser_smoke_boundary.py`
   - 결과: **29 passed in 5.13s**
3. **문서 무결성 검사**:
   - 명령: `python tools/check_docs.py`
   - 결과: **PASS** (555 versioned documents)
4. **한정 사항 (Caveat)**:
   - 본 검증은 소스 계약 대조 및 모의/단위 테스트 수준의 정합 검증이며, 라이브 HTTP 통신을 수반한 E2E 운영 인수는 추후 통합 운영 세션에서 별도 수행됨.
