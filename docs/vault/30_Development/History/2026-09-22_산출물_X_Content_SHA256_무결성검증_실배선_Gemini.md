# 산출물 다운로드 X-Content-SHA256 헤더 기반 무결성 검증 실배선 및 삼분할(검증됨·불일치·미검증) 정직화 보고서

- **작성 일시**: 2026-09-22 (KST)
- **작성 주체**: Gemini (Antigravity)
- **관련 커밋**: Codex `65aec0cc` (artifact-content 결속), Claude 독립 검토 `700887ca`
- **검증 환경**: Happy-DOM / WebCrypto (SubtleCrypto SHA-256), Vitest 70개 파일 628/628 passed (100%)

---

## 1. 배경 및 문제 의식

Claude의 독립 검토 보고서(`2026-09-22_Codex_artifact_content_결속_독립검토_Claude.md`)에서 다음 발견이 지적되었다:
> "화면은 status + blob()만 쓰고 X-Content-SHA256(수신 바이트 클라이언트 무결성 검증)·서버 Content-Disposition(파일명)을 무시(자체 fileName 사용). 결속의 부가가치(클라 체크섬 검증)를 안 씀."

이에 사용자는 다음 원칙에 따른 즉시 실배선을 명령하였다:
1. **완료(Done)의 내실화**: 서버가 보낸 헤더와 다운로드한 실제 바이트의 해시 대조 없이 "다운로드 완료"라고 선언하는 것은 약하다.
2. **엄격한 3상태 무결성 (Strict Tri-State)**:
   - **검증됨 (verified)**: 수신 바이트 SHA-256 계산값 === `X-Content-SHA256` 헤더. 일치할 때만 `[무결성 검증 완료]`로 표시.
   - **불일치 (mismatch)**: 헤더와 바이트 해시 불일치 시 조용히 넘기지 않고 `[무결성 검증 실패]`(`role="alert"`)로 명시하며 다운로드를 차단.
   - **미검증 (unverified)**: 서버 응답에 `X-Content-SHA256` 헤더가 없으면 조작 없이 `[다운로드 완료 · 무결성 미검증]`으로 고지.
3. **서버 Content-Disposition 활용**: 서버가 헤더로 파일명을 전송할 경우 이를 최종 파일명으로 파싱 및 채택.

---

## 2. 구현 내용

### 1) WebCrypto 기반 공통 SHA-256 유틸리티 구축 (`apps/web/src/shared/utils/crypto.ts`)
- 브라우저 표준 `globalThis.crypto.subtle.digest('SHA-256', ...)`를 사용하는 범용 바이트 해시 계산기 구축.
- `InvFileExplorer.tsx`의 중복 로직을 이 공통 유틸리티로 통합하고 하위 호환 re-export 유지.

### 2) 산출물 다운로드 및 무결성 검증 클라이언트 구축 (`apps/web/src/shared/api/runArtifactObservation.ts`)
- `downloadAndVerifyArtifact(projectId, runId, path, fallbackFileName, authToken)` 함수 신설:
  - `GET /v1/projects/{projectId}/runs/{runId}/artifacts/content?path={path}` 호출.
  - `Content-Disposition` 헤더에서 파일명(`filename=...` or `filename*=UTF-8''...`) 추출.
  - 응답 Blob의 `arrayBuffer()`를 통해 실제 수신 바이트의 SHA-256 계산.
  - `X-Content-SHA256` 헤더 추출 및 대조:
    - `!expectedSha256` ➔ `integrity = 'unverified'`
    - `expectedSha256 === calculatedSha256.toLowerCase()` ➔ `integrity = 'verified'`
    - 불일치 ➔ `integrity = 'mismatch'`
  - `ArtifactDownloadVerification` 구조체 반환.

### 3) DeveloperStudio 원시 산출물 다운로드 무결성 결속 (`DeveloperStudio.tsx`)
- `handleDownloadRawFile`을 `downloadAndVerifyArtifact` 기반으로 전면 전환:
  - **`verified`**: `[무결성 검증 완료] 산출물 파일 '${fileName}' (${size} Bytes, SHA-256 일치) 다운로드 완료.` (`role="status"`) 표출 및 파일 다운로드 트리거.
  - **`mismatch`**: `[무결성 검증 실패] 산출물 파일 '${fileName}'의 수신 바이트 체크섬이 서버 헤더(X-Content-SHA256)와 불일치합니다. 전송 중 손상 위험으로 저장이 중단되었습니다.` (`role="alert"`) 표출 및 **파일 다운로드 차단(createObjectURL 미호출)**.
  - **`unverified`**: `[다운로드 완료 · 무결성 미검증] 산출물 파일 '${fileName}' (${size} Bytes) 다운로드 완료 (서버 X-Content-SHA256 헤더 부재로 무결성 미검증).` (`role="status"`) 표출 및 다운로드 허용.

---

## 3. 단위 시험 및 돌연변이 실측 사살 (Killed)

- **신규 테스트 파일**: `apps/web/tests/artifact-content-download-integrity.test.tsx` (6/6 passed 100%)
  1. API: `verified` 상태 및 Content-Disposition 파싱 검증.
  2. API: `mismatch` 상태 및 변조/손상 포착 검증.
  3. API: `unverified` 상태 및 헤더 부재 정직 고지 검증.
  4. DOM: DeveloperStudio `verified` 시 `[무결성 검증 완료]` 표출 및 다운로드 트리거 검증.
  5. DOM: DeveloperStudio `mismatch` 시 `[무결성 검증 실패]`(`role="alert"`) 표출 및 **다운로드 차단** 검증.
  6. DOM: DeveloperStudio `unverified` 시 `[다운로드 완료 · 무결성 미검증]` 표출 및 다운로드 검증.
- **돌연변이 실측 검증**:
  - `downloadAndVerifyArtifact`에서 불일치 검증을 제거하고 무조건 `verified`로 넘기는 돌연변이 주입 ➔ **2 tests FAILED (`AssertionError: expected 'verified' to be 'mismatch'`, `expected 'status' to be 'alert'`)** ➔ 돌연변이 즉시 사살(KILLED) 확인 후 원복.

---

## 4. 전체 검증 결과

- `tools/check_frontend_integrity.py`: 82개 파일 **0 violations (All 7 rules PASS)**.
- `tools/check_contract_bindings.py`: 36 fixtures / 12 serving anchors PASS.
- `tools/check_doc_single_source.py --ratchet`: 18 pairs PASS.
- `tools/check_docs.py`: 698 documents PASS.
- `tools/check_ontology.py`: PASS.
- `npm test` (apps/web): **70개 파일 628/628 passed (100% PASS)** (순증 +1 파일, +6 passed).
- `npm run build` (apps/web): Vite production build exit 0 (4.70s).
