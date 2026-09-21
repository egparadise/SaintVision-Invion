---
doc_id: "GEMINI-INTEGRITY-WORKSPACE-EDIT-WIRING-001"
title: "WorkspaceEditView 무결성 실바이트 원천 배선 및 온디맨드 복구/검증 API 부재 반영"
version: "1.0.0"
status: "approved"
author: "Gemini"
reviewer: "Claude"
updated: "2026-09-21"
source_of_truth: "Git"
tags: ["workspace-edit-view", "integrity", "replica-repair", "capability-map", "gemini", "zero-synthesis"]
---

# WorkspaceEditView 무결성 실바이트 원천 배선 및 온디맨드 복구/검증 API 부재 반영 (VF-GM-03/04 후속)

## 1. 개요 및 배경

Claude의 백엔드 무결성·복제본 능력 지도(`2026-09-21_무결성_복제본_백엔드능력지도_Claude.md`, commit `64dd7f6`) 및 사용자 지시에 따라, 프론트엔드가 합성(fake/demo synthesis)을 완전히 멈추고 백엔드의 실제 관측·계약 능력에 정직하게 정합하도록 경계 결함을 치유했다.

1. **데모 데이터 무결성 검증 착시 해소 (`InvFileExplorer.tsx`, `DesktopShell.tsx`)**:
   - 기존에는 `DesktopShell`이 `InvFileExplorer`에 `clusterNodes`만 넘겨 마운트할 때, 인메모리 데모 파일의 본문을 해시하여 실제 SHA-256이 나오고 데모의 `contentHash`와 일치하여 허위로 `verified`가 표출되는 문제가 존재했다.
   - 실제 바이트 원천인 `WorkspaceEditView` (`/v1/projects/{p}/runs/{id}/checkouts/{cid}/files`, fixture: `contracts/fixtures/workspace-edit-view-response.json`)를 연동하고, `DesktopShell`에서 `projectId`, `runId`, `checkoutId`를 `InvFileExplorer`에 전달하도록 배선했다.
   - 실제 커널 체크아웃 바이트가 연결되지 않았거나 데모 데이터(`source !== 'kernel-checkout'`)인 경우, 검증을 엄격히 거부하고 `unverified` 상태를 유지하며 다음 안내문을 표출한다:
     `데모/미연결 데이터: 실제 저장소 바이트(WorkspaceEditView)가 연결되지 않아 무결성을 검증할 수 없습니다. (미검증 유지)`
2. **온디맨드 복구 API 부재의 정직한 표출 (`InvFileExplorer.tsx`, `ModelStudioView.tsx`)**:
   - 커널 및 saintvision에는 온디맨드로 파일 복제본이나 모델 샤드를 복구하는 클라이언트 호출 가능 실행 API가 부재하다 (`reclaim_unclaimed` 및 `require_recovery_admission`은 내부 전이 함수).
   - `onRepairReplicas` 또는 `onRepairShard` 어댑터 부재 시, 가상 정상 복제본을 합성하지 않고 정직하게 다음 에러를 표출한다 (`role="alert"`):
     - 파일 탐색기: `서버에 온디맨드 복구 실행 API가 부재하여 복구를 수행할 수 없습니다. (복구 불가 / 미수행)`
     - 모델 스튜디오: `서버에 온디맨드 샤드 복구 API가 부재하여 복구를 수행할 수 없습니다. (복구 불가 / 미수행)`
3. **Per-Shard 복제본 건강 관측 부재 및 모델 검증 라우트 부재 정직 표출 (`ModelStudioView.tsx`)**:
   - `ShardObservation`은 샤드 실행 상태만 보고하며 per-shard 복제본 위치/건강을 알 수 없다. 요약 관측 시 다음 안내문을 표출한다:
     `ℹ️ (개별 샤드 및 per-shard 복제본 건강 관측 데이터가 백엔드에 부재합니다. 실행 재검증 후 수집됩니다.)`
   - 모델 검증 라우트가 부재(내부 `model_manifest.verify`만 존재)함을 다음 공지로 명시한다:
     `무결성 상태: 검증 라우트 부재 (내부 verify만 존재) · 실행 재검증 필요 (requiresExecutionRevalidation: true)`

---

## 2. 작업 내역 및 아키텍처 배선

### 2.1 WorkspaceEditView Zero-Mock API 어댑터 신설 (`apps/web/src/shared/api/workspaceEditObservation.ts`)
- `fetchWorkspaceEditView(projectId, runId, checkoutId, signal)`:
  - 엔드포인트 `/v1/projects/{projectId}/runs/{runId}/checkouts/{checkoutId}/files` 호출.
  - 런타임 봉투 검증: `checkoutId` 일치, `revision` 정수, `sha256` 64자리 16진수 해시, `snapshot.format === 'workspace-snapshot:1'`, `snapshot.files` 배열 검증.
  - 각 스냅샷 파일의 `path`, `executable`, `sha256`, `sizeBytes`, `dataBase64` 무결성 검증.
- `mapWorkspaceFilesToInvItems(editView)`:
  - 스냅샷 파일 목록을 `InvFileItem[]`으로 변환.
  - `dataBase64` 디코딩(브라우저 `atob` 및 Node `Buffer` 호환), `source: 'kernel-checkout'` 표기, `contentHash: f.sha256`, `replicas: []` (정직한 미합성).

### 2.2 DesktopShell & InvFileExplorer 배선
- `DesktopShell.tsx`:
  - `InvFileExplorer` 마운트 시 `projectId={projectId}`, `runId={runs[0]?.id}`, `checkoutId={workspaces[0]?.id}`, `clusterNodes={nodes}` 전달.
- `InvFileExplorer.tsx`:
  - `projectId`, `runId`, `checkoutId`가 주어지면 자동으로 `fetchWorkspaceEditView`를 호출하여 커널 체크아웃 파일을 로드 (`data-testid="checkout-loading"`, `data-testid="checkout-error"`).
  - 파일 검증 시 `selectedFile.source !== 'kernel-checkout'`이면 검증 거부 및 `unverified` 유지, 에러 알림 표출.
  - `data-testid="file-source-badge"`를 통해 출처를 가시적으로 구분 (`커널 체크아웃 (WorkspaceEditView 실 바이트)` vs `로컬/데모 (실제 저장소 미연결 · 무결성 검증 유보)`).
  - `onRepairReplicas` 부재 시 `서버에 온디맨드 복구 실행 API가 부재하여 복구를 수행할 수 없습니다. (복구 불가 / 미수행)` 알림 표출.

### 2.3 ModelStudioView 공지 및 에러 갱신
- `ModelStudioView.tsx`:
  - `data-testid="model-verification-notice"` 신설: `무결성 상태: 검증 라우트 부재 (내부 verify만 존재) · 실행 재검증 필요 (requiresExecutionRevalidation: true)`
  - `data-testid="unobserved-shards-notice"` 텍스트 갱신: `(개별 샤드 및 per-shard 복제본 건강 관측 데이터가 백엔드에 부재합니다. 실행 재검증 후 수집됩니다.)`
  - `onRepairShard` 부재 시 `서버에 온디맨드 샤드 복구 API가 부재하여 복구를 수행할 수 없습니다. (복구 불가 / 미수행)` 알림 표출.

### 2.4 Ajv 2020 양방향 계약 테스트 (`apps/web/tests/workspace-edit-view-contract.test.ts`)
- `core.schema.json#/$defs/WorkspaceEditView` 대상 Ajv 2020 컴파일 및 공용 픽스처(`contracts/fixtures/workspace-edit-view-response.json`) 무결성 검증 (7 passed).
- 필수 필드 누락, non-hex sha256, 파일 sha256 누락 등 변조 거절 검증.
- `fetchWorkspaceEditView` 및 `mapWorkspaceFilesToInvItems` 런타임 가드 검증.

---

## 3. 검증 결과

### 3.1 3대 보고 카테고리 실측

#### (1) 실측된 돌연변이 실패 (Measured Mutation Failures)
1. **데모 파일 무단 검증 허용 돌연변이 (Mutation 1)**:
   - `InvFileExplorer.tsx`에서 `if (selectedFile.source !== 'kernel-checkout')` 가드를 주석 처리하여 데모 인메모리 바이트를 해시하여 통과하도록 변조.
   - 결과: `[VF-GM-03-DEMO-FILE-UNVERIFIED]` 즉시 실패.
   - 실패 텍스트: `AssertionError: expected '검증 통과 (VERIFIED)' to be '미검증 (UNVERIFIED)'`
2. **복구 API 부재 메시지 은폐/변조 돌연변이 (Mutation 2)**:
   - `onRepairReplicas` 부재 시 에러 메시지를 임의의 텍스트나 성공으로 조작.
   - 결과: `[VF-GM-03-ABSENT-REPAIR-ADAPTER]` 즉시 실패.
   - 실패 텍스트: `AssertionError: expected '...' to include '서버에 온디맨드 복구 실행 API가 부재하여 복구를 수행할 수 없습니다. (복구 불가 / 미수행)'`
3. **WorkspaceEditView sha256 계약 변조 돌연변이 (Mutation 3)**:
   - 픽스처 sha256을 32바이트 비규격 해시(`not-a-valid-hex-sha256-hash`)로 변조.
   - 결과: `rejects workspace-edit-view fixture with non-hex sha256 digest` 및 `fetchWorkspaceEditView throws when response sha256 is invalid`에서 포착.
   - 실패 텍스트: `Error: WorkspaceEditView 응답 계약 불일치`

#### (2) 소스 독해 분석 (Source-Read Analysis)
- `tests/core/test_workspace_edit_view_contract.py` 독해: `WorkspaceEditor._view()`가 반환하는 `WorkspaceEditView`의 `sha256`은 실제 체크아웃 파일들의 SHA-256 해시이며, 각 `snapshot.files[]`가 고유의 `sha256`과 `dataBase64` 바이트를 가짐을 확인.
- `apps/web/src/shared/api/workspaceEditObservation.ts`에서 이 바이트를 디코딩하고 `kernel-checkout` 태그를 부여하여 클라이언트 SHA-256 검증기가 실제 저장소 바이트를 검증할 수 있도록 배선 완료.
- 백엔드에 온디맨드 복구 엔드포인트(`POST /v1/replicas/repair` 등)가 존재하지 않는다는 Claude 능력 지도를 확인하고, 어댑터 미전달 시 이를 정직하게 안내하도록 수렴.

#### (3) 미검증/유보 불변식 (Unverified/Deferred Invariants)
- **실제 라이브 커널 백엔드 HTTP 통합 통신**: 본 작업에서는 공용 정본 Fixture(`workspace-edit-view-response.json`) 및 Vitest Ajv/DOM 단위 하네스를 통해 전수 검증함. 백엔드 워커 프로세스가 실제로 동작하는 E2E 환경에서의 네트워크 왕복 지연 및 대용량 파일(10MB+) base64 디코딩 성능 검증은 추후 E2E 클러스터 배포 환경으로 유보.
- **Model verify HTTP 엔드포인트 신설**: 현재는 백엔드 내부 verify만 존재하므로 화면에 `검증 라우트 부재`를 표시하도록 고정함. 향후 Codex가 읽기-관측 엔드포인트를 노출하면 연동 예정.

### 3.2 테스트 실행 통계
- Vitest: **from 475 to 483 (net +8 tests, 53/53 test files passed 100%)**
  - `workspace-edit-view-contract.test.ts`: 7 passed
  - `inv-file-explorer-dom.test.tsx`: 15 passed (+1 net test)
  - `model-studio-dom.test.tsx`: 12 passed
- Vite Production Build: `tsc -b && vite build` exit code 0 (3.87s, 94 modules)
- Python Core Contracts: `pytest tests/core/test_*_contract.py` 19 passed (0.84s)
- Governance Check: `check_docs.py` PASS, `check_ontology.py` PASS, `sync_obsidian.py --check` PASS
