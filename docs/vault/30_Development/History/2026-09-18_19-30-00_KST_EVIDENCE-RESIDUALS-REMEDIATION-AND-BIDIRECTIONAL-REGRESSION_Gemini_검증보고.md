# 2026-09-18 19:30:00 KST EvidenceViewer 성공 경로 잔여 결함 조치 및 양방향 회귀 시험 구축 검증보고

## 1. 개요
- **목적**: `EvidenceViewer.tsx`의 성공 경로(success path)에 남아 있던 잔여 결함 3건(하드코딩 `'sha256:verified'` 다이제스트 폴백, 실행 성공을 무결성 검증으로 오인한 가짜 PASS 판정, 정적 아키텍처 사양과 동적 실행 판정의 혼재)을 완전 해소하고, Vitest와 Pytest에 양방향 영구 회귀 시험을 구축함.
- **담당 Agent**: Gemini (Frontend & Ingress Owner)
- **대상 브랜치**: `integration/all-agents-unified`
- **검증 환경**: Windows 11, Node.js v22.14.0, Python 3.14.6, Vitest v3.2.7, Pytest v9.1.1

---

## 2. 잔여 결함 및 정합 조치 내역

### A. 가짜 다이제스트 폴백 `'sha256:verified'` 원천 제거
- **기존 문제**: 백엔드 응답의 `output.sha256`, `evidence.outputSha256`, `specDigest`가 누락된 경우 `|| 'sha256:verified'` 폴백이 작동하여, 실제 해시가 없음에도 사용자와 감사 로그에 "verified"라는 단어가 포함된 허위 다이제스트를 노출함.
- **조치 결과**:
  1. `manifestDigest`: `res.output?.sha256 || res.evidence?.outputSha256 || res.manifestDigest || res.stopReceipt?.outputCommitmentHash || undefined`로 변경.
  2. `specDigest`: `res.evidence?.specDigest || res.evidence?.inputSha256 || undefined`로 변경.
  3. 해시 부재 시 가짜 문자열을 합성하지 않고 `undefined`로 유지하여 누락 사실을 투명하게 드러냄.

### B. 실행 성공과 암호학적 출력 무결성 검증의 엄격한 분리
- **기존 문제**: `const integrityStatus = isVerified ? 'PASS' : isSucceeded ? 'PASS' : 'FAIL'` 로직으로 인해, 실행이 성공(`state === 'succeeded'`)하기만 하면 출력이 암호학적으로 검증(`output.verified === true`)되지 않았더라도 `PASS` 배너(`✓ 무결성 검증 통과 (PASS)`)가 부여됨. 정의되어 있던 `UNVERIFIED` 상태에 결코 도달하지 않음.
- **조치 결과**:
  1. 엄격한 3단계 분기 도입:
     ```typescript
     let integrityStatus: 'PASS' | 'FAIL' | 'UNVERIFIED';
     if (res.output?.verified === true) {
       integrityStatus = 'PASS';
     } else if (res.output?.verified === false || res.state === 'failed') {
       integrityStatus = 'FAIL';
     } else {
       integrityStatus = 'UNVERIFIED';
     }
     ```
  2. 암호학적 검증이 수행되지 않은 성공 실행은 정직하게 `UNVERIFIED`로 분류.
  3. UI에 `⚠️ 출력 무결성 미검증 (UNVERIFIED)` 전용 경고 뱃지 신설.

### C. 정적 시스템 정책 규격과 동적 실행 판정 컨테이너 물리 분리
- **기존 문제**: 1년 보존 Pin(ADR-012) 및 불변 저장소 규격이 동적 검증 뱃지와 같은 줄에 나란히 배열되어 개별 실행의 런타임 통과 결과처럼 오인될 소지가 있음.
- **조치 결과**:
  1. `동적 무결성 판정:` 레이블 아래에 동적 결과(`PASS`, `FAIL`, `UNVERIFIED`, `SEALED`)를 배치.
  2. 시스템 아키텍처 불변 사양은 독립된 파선 박스로 완전히 분리하고 **`[시스템 정책 사양]`** 헤더를 부여하여 런타임 테스트가 아닌 플랫폼 설계 사양임을 명확히 함.

---

## 3. 양방향 영구 회귀 시험 (Bidirectional Regression Tests)

### 1) Vitest (`apps/web/tests/evidence-viewer.test.ts`)
- `regression: source strictly excludes "sha256:verified" fallback and never fabricates mock digests`:
  - `EvidenceViewer.tsx` 소스 내 `'sha256:verified'` 문자열 리터럴 완전 부재 검증.
- `regression: execution success (succeeded) without cryptographic verification yields UNVERIFIED, never PASS`:
  - `state: 'succeeded'`이나 `output.verified`가 없는 실행에 대해 `integrityStatus === 'UNVERIFIED'`를 도출하며 `PASS`나 `FAIL`이 되지 않음을 단언.
- `regression: fetch failure surfaces authentic error and never renders fake PASS or synthetic toolCalls`:
  - `UNVERIFIED` 뱃지 렌더링 조건 및 `[시스템 정책 사양]` 분리 컨테이너 존재 검증.

### 2) Pytest (`tests/test_route_coverage.py`)
- `test_evidence_viewer_integrity_contract_invariants()`:
  - Python 레벨에서 `EvidenceViewer.tsx` 소스 텍스트를 파싱하여:
    1. `'sha256:verified'` 부재 단언.
    2. 허위 텔레메트리(`git.checkout`, `test.run`, `artifact.write`, `wallTimeMs`) 부재 단언.
    3. `PASS`가 `res.output?.verified === true`에 엄격히 결속되어 있으며 `UNVERIFIED` 상태가 존재하는지 단언.
    4. `[시스템 정책 사양]` 및 `출력 무결성 미검증 (UNVERIFIED)` 표기가 존재하는지 단언.

---

## 4. 검증 결과

1. **Vitest 전체 스위트**:
   - 명령: `npm --prefix apps/web test -- --run`
   - 결과: **31개 파일 307 passed / 0 failed (3.11s)** (기존 305건에서 2건 증가)
2. **Pytest 전체 스위트**:
   - 명령: `.venv\Scripts\pytest.exe tests/test_route_coverage.py tests/test_browser_smoke_boundary.py`
   - 결과: **30 passed in 5.15s** (기존 29건에서 1건 증가)
3. **문서 무결성 검사**:
   - 명령: `python tools/check_docs.py`
   - 결과: **PASS** (559 versioned documents, 24 original hashes, 48 tasks, 12 outcomes)

---

## 5. 한정 사항 및 다음 행동
- 본 조치는 프론트엔드 컴포넌트의 가짜 성공 합성 차단 및 양방향 단위/계약 수준의 정합 검증 완료 증거임.
- 실제 분산 노드 환경에서의 라이브 HTTP E2E 통신 및 실장비 2-PC 인수는 통합 운영 세션에서 수행됨.
