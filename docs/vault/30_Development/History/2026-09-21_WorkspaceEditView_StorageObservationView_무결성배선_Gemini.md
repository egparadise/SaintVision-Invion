---
doc_id: "GEMINI-WORKSPACE-EDIT-STORAGE-OBSERVATION-001"
title: "WorkspaceEditView 실바이트 해시 검증 개통, StorageObservationView 스토리지 샘플 무결성 배선 및 엄격한 3갈래 불변식 확립"
version: "1.0.0"
status: "approved"
author: "Gemini"
reviewer: "Claude"
updated: "2026-09-21"
source_of_truth: "Git"
tags: ["integrity", "workspace-edit-view", "storage-observation", "anti-synthesis", "tri-state", "gemini"]
---

# WorkspaceEditView 실바이트 해시 검증 개통, StorageObservationView 스토리지 샘플 무결성 배선 및 엄격한 3갈래 불변식 확립

## 1. 작업 개요 및 배경

- **촉발 배경**:
  - 이전 단계에서 Gemini는 프런트엔드의 허위 무결성 합성(자체 계산 해시를 기대 해시로 되먹이거나 가짜 합격 표시)을 전면 차단하고 정직한 거절(honest refusal: 실제 커널 체크아웃 바이트 미연결 시 `unverified` 유지)을 확립함.
  - Claude가 커널의 `WorkspaceEditView`(`workspace_editor._view()`가 실제 체크아웃 바이트의 `hashlib.sha256(raw).hexdigest()`를 제공, `contracts/fixtures/workspace-edit-view-response.json`)와 `StorageObservationView`(`storage_view.result()`의 `verify_sample` 점유 증명, `contracts/fixtures/storage-observation-response.json`)를 계약에 결속함.
  - 이에 따라 사용자 지시에 의거하여 다음을 완결함:
    1. **`InvFileExplorer`의 진정한 무결성 검증(`verified` / PASS) 경로 개통**:
       `WorkspaceEditView`를 소비하여 실제 서버 체크아웃 바이트(`dataBase64` 디코딩)를 로컬 WebCrypto SHA-256으로 계산하고, 서버 기대 체크섬과 대조하는 실체적 검증을 실현함.
    2. **엄격한 3갈래(Tri-State) 불변식 유지**:
       - `calculatedSha256(actualBytes) === serverExpectedHash`일 때만 유일하게 `verified` (`PASS`) 전이.
       - 해시가 불일치하면 즉시 `mismatch` (`FAIL` / 변조 경고 배너 표출), 결코 `verified`가 되지 않음.
       - 서버 응답 실패, 기대 해시 부재, 바이트 부재, 데모 데이터인 경우 `unverified` 유지 (절대 가짜 합격 합성 금지).
    3. **`StorageObservationView` 스토리지 기여 샘플 무결성 배선**:
       `ResourceExplorer.tsx` Tab 2(스토리지)에 `StorageObservationView` 조회 어댑터(`shared/api/storageObservation.ts`)를 신설 및 배선. 서버가 정의한 불변 제약(`currentHealth: "unknown"`, `operationalAcceptanceAssessed: false`, `observation.integrityVerified: true`)을 정직하게 노출하고 임의의 `healthy` 합성을 엄격히 거부.
    4. **돌연변이 시험(Mutation Proof) 및 Before vs After 실증**:
       해시 변조, 바이트 변조, 무결성 결손 상황에서 합격 배지가 뜨지 않고 정확히 `mismatch` 또는 `unverified`로 격리됨을 DOM 하네스 시험으로 증명.
    5. **공유 워크트리 개인 index 격리 및 선별 stage 규율 준수**:
       `git add .`를 전면 금지하고 본 작업 영역(`apps/web/`, `docs/vault/`) 파일만을 선별 stage하여 타 에이전트 작업과의 혼선을 원천 방지.

---

## 2. 구현 상세 및 아키텍처 연동

### 가. `StorageObservationView` API 어댑터 및 계약 결속 (`apps/web/src/shared/api/storageObservation.ts`, `tests/storage-observation-contract.test.ts`)
- **엔드포인트**: `GET /v1/projects/{projectId}/runs/{runId}/storage-samples/{requestId}`
- **반-합성(Anti-Synthesis) 가드**:
  - `result.currentHealth !== 'unknown'` 또는 `result.operationalAcceptanceAssessed !== false`인 경우 즉시 에러 발생(`StorageObservationView 응답 계약 불일치`).
  - `status === 'recorded'`인 경우 `observation.integrityVerified === true` 및 표본 집계 필드(`sampled`, `mismatches`, `unverifiable`, `examined`, `unsampled`) 유효성 검증.
  - `status !== 'recorded'`(pending/expired)인 경우 `observation === null` 강제.
  - `projectId`, `runId`, `requestId` 중 하나라도 누락 시 네트워크 요청을 0건 발생시키고 즉시 거절.
- **계약 시험**: Ajv 2020 컴파일 검증 및 7개 계약/어댑터 시험 통과.

### 나. `ResourceExplorer.tsx` 스토리지 탭 샘플 무결성 관측 배선
- Tab 2(스토리지) 하단에 `data-testid="storage-observation-section"` 신설.
- 요청 ID 입력(`storage-sample-req-input`) 및 관측 조회 버튼(`fetch-storage-observation-btn`) 구축.
- 상위 `DesktopShell`에서 `projectId` 및 `runId`를 주입받아 컨텍스트가 없을 경우 0호출 안내 배너(`storage-observation-context-warning`) 및 버튼 비활성화.
- 관측 결과 렌더링 시 `currentHealth`를 불변 `"unknown"`으로 명시(`data-testid="storage-observation-health"`), `operationalAcceptanceAssessed`를 `false (미평가)`로 고지하여 클라이언트의 허위 건전성 합성 방지.

### 다. `InvFileExplorer.tsx` 및 `DesktopShell.tsx` 진정 무결성 검증 및 체크아웃 로드 배선
- `DesktopShell.tsx`에서 `checkoutId` prop을 수신하여 `InvFileExplorer`에 전달.
- `InvFileExplorer.tsx`의 `workspaces` 네임스페이스에 커널 체크아웃 입력 바(`workspace-checkout-bar`, `checkout-id-input`, `load-checkout-btn`)를 제공하여 임의의 체크아웃을 동적으로 로드 가능.
- `handleVerifyIntegrity()`:
  - `source === 'kernel-checkout'`인 경우 실제 파일 바이트(0바이트 빈 문자열 포함)의 클라이언트 측 WebCrypto SHA-256을 계산.
  - `calculated.toLowerCase() === selectedFile.contentHash.toLowerCase()` 일치 시에만 `status: 'verified'` (`data-testid="integrity-status-verified"`) 전이.
  - 불일치 시 `status: 'mismatch'` (`data-testid="integrity-status-mismatch"`, `data-testid="integrity-mismatch-banner"`) 전이.
  - 카탈로그 해시 부재, 본문 바이트 부재, 데모 데이터인 경우 `status: 'unverified'` (`data-testid="integrity-status-unverified"`) 유지.

---

## 3. Before vs After 무결성 검증 실증

| 시나리오 | 이전 (Before) 동작 | 이후 (After) 동작 | 검증 보장 (Guarantee) |
|---|---|---|---|
| **미연결 데모 파일 검증 시도** | 무결성 검증 불가로 영구 `unverified` 유지 (합격 불가) | 동일하게 `unverified` 유지 및 정직한 거절 에러 표출 | **불변식 보존**: 가짜 데이터에 합격증을 발행하지 않음 |
| **정본 커널 체크아웃 파일 검증** | 체크아웃 바이트가 연결되지 않아 영구 `unverified` | `WorkspaceEditView` 실바이트 로드 후 SHA-256 일치 시 **`verified` (PASS)** 전이 | **검증 통로 개통**: 실제 암호학적 해시 일치 시에만 합격 |
| **서버 해시 불일치 (변조)** | 데모 상태로 격리 | `mismatch` (TAMPERED) 경고 배너 표출, 결코 `verified` 미발생 | **변조 탐지**: 위조/변조된 체크섬 즉시 적발 |
| **본문 바이트 변조** | 데모 상태로 격리 | 바이트가 달라져 계산 해시 불일치 -> `mismatch` 전이 | **무결성 훼손 방지**: 인메모리/전송 중 변조 실시간 적발 |
| **스토리지 기여 샘플 관측** | UI 미구현 (미소비) | `currentHealth: "unknown"`, `integrityVerified: true`, 표본수 10 노출 | **반-합성 준수**: 서버 정의 unknown을 healthy로 둔갑시키지 않음 |

---

## 4. 실측 돌연변이 사살 내역 (Measured Mutation Proofs)

### 돌연변이 1: 서버 체크섬 불일치 시 합격 판정 돌연변이 (Mutation 1)
- **주입 내용**: `contracts/fixtures/workspace-edit-view-response.json`에서 파일 바이트는 `print('hello')\n`(`03e693d9...`)이나 서버 sha256은 `ffffffff...`로 불일치하는 상황.
- **포획 시험**: `[VF-GM-03-MUTATION-PROOF-HASH]`
- **실측 결과**: `integrity-status-verified`는 null이며, `integrity-status-mismatch` 및 `integrity-mismatch-banner`(`무결성 검증 실패: 계산된 해시가 카탈로그 체크섬과 불일치합니다 (변조 감지)`)가 정상 작동하여 합격 착시를 완전히 차단함 (**KILLED**).

### 돌연변이 2: 전송/메모리 상 파일 본문 바이트 변조 돌연변이 (Mutation 2)
- **주입 내용**: 기대 해시는 정상이지만, 파일 본문이 `print('hacked')\n`으로 임의 변경된 상황.
- **포획 시험**: `[VF-GM-03-MUTATION-PROOF-BYTES]`
- **실측 결과**: 계산된 SHA-256이 기대 해시와 달라져 `integrity-status-mismatch`로 전이됨 (**KILLED**).

### 돌연변이 3: 데모 파일에 대한 조기 합격 처리 돌연변이 (Mutation 3)
- **주입 내용**: `source: 'demo'`인 파일에 대해 검증 버튼 클릭 시 바이트 해시가 우연히 일치한다고 해서 verified로 통과시키는 상황.
- **포획 시험**: `[VF-GM-03-BEFORE-AFTER-VERIFY]` (Part 1)
- **실측 결과**: `selectedFile.source !== 'kernel-checkout'` 정직 거절 가드에 걸려 `미검증 (UNVERIFIED)` 유지 및 `integrity-action-error` 고지 (**KILLED**).

### 돌연변이 4: 스토리지 샘플의 currentHealth를 healthy로 합성하는 돌연변이 (Mutation 4)
- **주입 내용**: 백엔드 또는 어댑터가 `currentHealth: "healthy"`를 반환하도록 변조.
- **포획 시험**: `apps/web/tests/storage-observation-contract.test.ts`
- **실측 결과**: `StorageObservationView 응답 계약 불일치` 에러 발생 및 Ajv 스키마 유효성 검사 실패 (**KILLED**).

---

## 5. 종합 검증 실적

1. **Vitest 웹 테스트 스위트 전수 통과**:
   - 명령: `npm --prefix apps/web test -- --run`
   - 결과: **56개 테스트 파일 전수 통과 (523 / 523 passed, 100%)**
   - 신규 추가: `storage-observation-contract.test.ts` (7 passed), `inv-file-explorer-dom.test.tsx` (19 passed, net +4), `resource-explorer-dom.test.tsx` (20 passed, net +2).
2. **프로덕션 빌드 성공**:
   - 명령: `npm --prefix apps/web run build` (`tsc -b && vite build`)
   - 결과: Exit code 0 (3.32s, 96 modules transformed, dist 생성 완료).
3. **백엔드 서빙 앵커 및 계약 검증**:
   - 명령: `.venv\Scripts\python.exe -m pytest tests/core/test_serving_anchors.py tests/core/test_workspace_edit_view_contract.py tests/core/test_storage_observation_contract.py`
   - 결과: **17 passed (0.86s)**.
4. **거버넌스 및 온톨로지 무결성 검증**:
   - `python tools/check_docs.py` -> PASS (24 original hashes, 647 versioned documents, 48 tasks, 12 outcomes).
   - `.venv\Scripts\python.exe tools/check_ontology.py` -> PASS (RDF parsing, SHACL, 4 rejected invalid fixtures, 4 competency queries).
   - `python tools/sync_obsidian.py --check` -> PASS (1440 managed files, 0 conflicts).

---

## 6. 결론 및 다음 행동

- `WorkspaceEditView`의 실제 바이트 기반 SHA-256 검증이 개통되어, 허위 합성 없이도 서버의 정본 체크아웃 데이터를 바탕으로 한 진정한 `VERIFIED` 판정이 가능해짐.
- `StorageObservationView`가 `ResourceExplorer` 스토리지 기여 탭에 정식 배선되어, 점유 증명 표본 통계와 불변의 `unknown` 건전성이 사용자에게 투명하게 제공됨.
- 다음 담당: Claude / Codex (모델 verify 노출 엔드포인트 수립 및 후속 트랙 검토).
