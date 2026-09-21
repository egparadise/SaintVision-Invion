---
doc_id: "HIST-2026-09-22-ACTIVE-NODE-AND-EVIDENCE-INTEGRITY-GUARD"
title: "NodeResponse active 정본 계약 상태 정직한 인식·헬스 미결정 고지 및 EvidenceViewer 허위 PASS 차단·verified 게이트 복구"
version: "1.0.0"
status: "completed"
author: "Gemini"
reviewer: "Codex"
created: "2026-09-22T04:42:00+09:00"
updated: "2026-09-22T04:42:00+09:00"
source_of_truth: "Git"
branch: "integration/all-agents-unified"
---

# NodeResponse active 정본 계약 상태 정직한 인식·헬스 미결정 고지 및 EvidenceViewer 허위 PASS 차단·verified 게이트 복구

## 1. 개요 및 배경

오늘 밤 프런트엔드-백엔드 간 계약 정합 및 무결성 표시에서 두 가지 핵심 결함에 대한 즉각적 치유 및 양방향 가드 체계가 구축되었다.

1. **백엔드 `NodeResponse.status` 정본 계약 5대 상태 중 `active` 인식 정합 및 헬스 미결정 고지**:
   - 백엔드 DB CHECK 계약의 5대 상태(`enrolling`, `active`, `draining`, `lost`, `retired`) 중 화면(`nodeObservation.ts`)이 인식하지 못하고 `unknown`과 `valid: false`로 버리던 상태를 전수 대조함.
   - 대조 결과: 화면이 못 알아보던 계약 값은 정확히 1개(`active`).
   - `active`는 정상 가동 노드가 내는 명확한 계약 값이므로 이를 미지(`unknown`)로 둘러대지 않고 `active`로 인식하도록 정합함.
   - 단, `active`를 임의로 건강함(초록색)으로 앞지르지 않고, 중립 청록색(`#38bdf8`) 뱃지(`ACTIVE (활성 · 헬스 미결정)`) 및 안내 배너(`ℹ️ 계약 상태: active (정상 가동 노드 · liveness 및 헬스 초록 표기 정책은 사용자 결정 대기 중)`)로 정직하게 고지함.
   - 실제 Google Chrome 153 브라우저 실측으로 `nod_active_pacs_01` 카드 표출 및 스크린샷 증거 확보.

2. **`EvidenceViewer.tsx` 허위 `PASS` 차단 및 `verified === true` 게이트 복구**:
   - `tests/test_route_coverage.py`의 `test_evidence_viewer_integrity_contract_invariants` 실패 발생.
   - 원인: Truth Time / Query Time 작업(`597ef148`) 당시 `EvidenceViewer.tsx` 50행 부근에서 `integrityStatus` 기본값이 `'PASS'`로 초기화되고, `sealed` 및 `output.sha256`이 존재하기만 하면 `PASS`로 판정되면서 암호학적 검증(`res.output?.verified === true`) 가드가 누락됨.
   - 단순 실행 성공이나 해시 존재를 암호학적 무결성 통과(`PASS`)와 동일시하는 치명적인 허위 진술(가짜 PASS) 결함을 즉시 정정.
   - 기본값을 `UNVERIFIED`로 변경하고, 오직 `res.output?.verified === true`일 때만 `PASS`로 승격되도록 게이트 복구.
   - `sealed`이고 출력 해시(SHA-256)는 계산되었으나 암호학적 검증(`verified`)이 완료되지 않은 경우, 사실 그대로를 설명하는 안내 배너(`data-testid="evidence-unverified-notice"`) 표출.
   - 파이썬 회귀 시험(`pytest tests/test_route_coverage.py`) 30/30 통과 실측 및 프런트엔드 DOM 렌더링 가드 테스트(`apps/web/tests/evidence-viewer-integrity-guard.test.tsx`, 3/3 통과) 추가.

---

## 2. 작업 상세 내용

### 2.1 NodeResponse 5대 상태 대조 및 정합
- **계약 5대 어휘 대조 결과**:
  | 백엔드 상태 | 기존 프런트 매핑 | 수정 후 매핑 | 화면 표출 | 비고 |
  |---|---|---|---|---|
  | `enrolling` | `enrolling` | `enrolling` | `ENROLLING` (주황) | 정상 인식 유지 |
  | `active` | ❌ `unknown` (valid: false) | ✅ `active` (valid: true) | `ACTIVE (활성 · 헬스 미결정)` (청록) | 계약 미인식 결함 치유 |
  | `draining` | `draining` | `draining` | `DRAINING` (황색) | 정상 인식 유지 |
  | `lost` | `lost` (valid: false) | `lost` (valid: false) | `LOST (단절)` (적색) | 정상 인식 유지 |
  | `retired` | `retired` | `retired` | `RETIRED` (회색) | 정상 인식 유지 |
- **화면 배너 표출**:
  - `NodeList.tsx`:
    - `data-testid={`node-active-status-notice-${node.id}`}`: `ℹ️ 계약 상태: active (정상 가동 노드 · liveness 및 헬스 초록 표기 정책은 사용자 결정 대기 중)`
  - `NodeDetail.tsx`: `Heartbeat ACTIVE (계약 상태 · 헬스 미결정)`
  - `ClusterOverview.tsx`: 노드 테이블 뱃지 `ACTIVE (활성 · 헬스 미결정)`

### 2.2 EvidenceViewer 허위 PASS 차단 및 정직한 미검증 고지
- **`apps/web/src/features/evidence/EvidenceViewer.tsx`**:
  ```typescript
  // 수정 전 (허위 PASS 결함)
  let integrityStatus: 'PASS' | 'FAIL' | 'UNVERIFIED' = 'PASS';
  if (res.sealed && res.output?.sha256) {
    integrityStatus = 'PASS';
  } else if (res.outputAbsentReason) {
    integrityStatus = 'FAIL';
  } else {
    integrityStatus = 'UNVERIFIED';
  }

  // 수정 후 (정직한 verified 게이트 복구)
  let integrityStatus: 'PASS' | 'FAIL' | 'UNVERIFIED' = 'UNVERIFIED';
  if (res.output?.verified === true) {
    integrityStatus = 'PASS';
  } else if (res.output?.verified === false || res.outputAbsentReason || res.state === 'failed') {
    integrityStatus = 'FAIL';
  } else {
    integrityStatus = 'UNVERIFIED';
  }
  ```
- **중간 상태(SEALED & 해시 존재하나 암호학적 미검증) 안내 배너**:
  ```tsx
  {evidenceData.integrityVerification === 'UNVERIFIED' && (
    <div data-testid="evidence-unverified-notice" style={{ ... }}>
      {evidenceData.manifestDigest && evidenceData.immutable ? (
        <span>
          ℹ️ <strong>봉인 및 해시 계산 완료 (SEALED):</strong> 출력 해시(SHA-256)가 계산되고 실행이 봉인되었으나, 독립적 암호학적 대조(verified)가 수행되지 않아 <strong>미검증 (UNVERIFIED)</strong> 상태로 표기됩니다. (해시 존재 ≠ 무결성 검증 통과)
        </span>
      ) : (
        <span>
          ⚠️ 출력 검증 정보가 확인되지 않아 <strong>미검증 (UNVERIFIED)</strong> 상태로 유지됩니다.
        </span>
      )}
    </div>
  )}
  ```

### 2.3 거버넌스 및 규칙 반영
- **`GEMINI.md`**:
  - 화면 소스 수정 시 `pytest tests/test_route_coverage.py` 실행을 프런트엔드 착지 전 필수 게이트로 명시.
- **`AGENTS.md` & `검증검사도구_목록.md`**:
  - `pytest tests/test_route_coverage.py`를 검증 게이트 목록에 등재 (v1.2.0).

---

## 3. 검증 실측 증거

| 검증 도구 | 실행 명령 | 실측 결과 |
|---|---|---|
| **Python Route Coverage** | `.venv\Scripts\pytest tests/test_route_coverage.py` | **30 passed in 1.05s** (exit code 0) |
| **Real Chrome 153 E2E** | `.venv\Scripts\python.exe scratch/verify_active_node_status_chrome.py` | **Exit code 0, 스크린샷 획득 (`scratch/real_chrome_active_node_status.png`)** |
| **Vitest (DOM Guard)** | `npm test -- tests/evidence-viewer-integrity-guard.test.tsx --run` | **3 passed (100%)** |
| **Vitest (전체)** | `npm test -- --run` | **75 test files passed, 652 tests passed (100%)** |
| **Frontend TypeScript** | `npx tsc -b` | **오류 0건 (exit code 0)** |
| **Frontend Build** | `npm run build` | **Vite 프로덕션 번들 빌드 성공 (built in 3.73s)** |
| **Frontend Integrity** | `python tools/check_frontend_integrity.py` | **0 violations, All 7 rules passed** |
| **Contract Bindings** | `python tools/check_contract_bindings.py` | **46 fixtures, 12 serving anchors PASS** |
| **Doc Single Source** | `python tools/check_doc_single_source.py --ratchet` | **18 pairs PASS** |
| **Check Docs** | `python tools/check_docs.py` | **PASS (722 docs, 48 tasks, 12 outcomes)** |

---

## 4. 인계 사항 및 다음 조치

- **Claude / Codex 인계**:
  - 백엔드 `tests/test_route_coverage.py`의 `EvidenceViewer` 무결성 검증 가드가 초록으로 복구되어 전체 백엔드 CI 게이트가 열림.
  - `apps/web` 소스 파일 변경 시 `pytest tests/test_route_coverage.py`가 상호 검증 게이트로 작동함이 `GEMINI.md`와 `검증검사도구_목록.md`에 공식 규정됨.
