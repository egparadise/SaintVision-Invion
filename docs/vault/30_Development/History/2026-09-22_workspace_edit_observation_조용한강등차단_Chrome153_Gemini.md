---
doc_id: "HIST-2026-09-22-WS-OBS-HONESTY-001"
title: "workspaceEditObservation 조용한 강등 차단 및 Chrome 153 실측 완결"
version: "1.0.0"
status: "approved"
author: "Gemini"
updated: "2026-09-22T03:58:00+09:00"
source_of_truth: "Git"
---

# workspaceEditObservation 조용한 강등 차단 및 Chrome 153 실측 완결

## 1. 개요 및 배경

- **발견 경위**:
  - Claude의 프런트엔드 조용한 강등 전수 훑기 과정에서 Gemini 소유 영역인 `apps/web/src/shared/api/workspaceEditObservation.ts` 내 2건의 결함이 지적됨:
    1. L99 근처: `workspaceId`가 비어 있을 때 `'default-workspace'`로 채우고 파일 주소 `inv://workspaces/default-workspace/...`에 박아 존재하지 않는 가상 작업공간을 생성하는 결함.
    2. L108 근처: Base64 디코딩 실패 시 `catch { decodedContent = f.dataBase64; }`로 원본 인코딩 문자열을 디코딩된 내용인 양 둔갑시키는 결함.
  - 사용자 지침:
    - `workspaceId`가 실제로 빌 수 있는지 계약 검증을 사전 확인할 것.
    - 모르는 것을 모른다고 하지 않고 그럴듯한 기본값으로 채우는 조용한 강등을 완전히 차단할 것.
    - 실패 시 `content: undefined` 및 `decodeError`를 명시하고 화면에 `role="alert"` 경고 배너 및 `👉 [사용자 조치 필요]`를 안내하며 무결성 검증을 fail-closed로 차단할 것.
    - 이름 없는 다운로드에 `artifact.bin`을 붙이는 것은 Codex 영역이므로 손대지 말 것.
    - 돌연변이 사살(Mutation Testing) 및 실제 Google Chrome 153 브라우저 실측을 완결할 것.

## 2. 계약 사전 분석 결과

- **`workspaceId`가 실제로 빌 수 있는가?**:
  - `contracts/v1alpha1/core.schema.json`의 `$defs/WorkspaceSnapshot`:
    `required: ["format", "workspaceId", "directories", "files"]` 및 `pattern: "^wsp_[0-9A-HJKMNP-TV-Z]{26}$"`로 비어 있을 수 없음.
  - 그러나 기존 프런트엔드 클라이언트(`workspaceEditObservation.ts`)의 수동 응답 검증 가드(`fetchWorkspaceEditView`, `saveWorkspaceEditView`)에서 `typeof result.snapshot.workspaceId !== 'string' || !result.snapshot.workspaceId.trim()` 검증이 **누락**되어 있었음.
  - 따라서 계약을 준수하지 않은 서버 응답이나 악의적/빈 값이 들어왔을 때 기존 가드를 그대로 통과하여 `'default-workspace'`로 둔갑하는 **살아 있는 강등(Silent Fallback)**이었음이 규명됨.

## 3. 코드 변경 내역

1. **타입 정의 확장 (`apps/web/src/contracts/virtualFabric.ts`)**:
   - `InvFileItem` 인터페이스에 선택적 필드 `decodeError?: string;` 추가.
2. **계약 가드 및 변환 fail-closed 강화 (`apps/web/src/shared/api/workspaceEditObservation.ts`)**:
   - `fetchWorkspaceEditView` 및 `saveWorkspaceEditView`의 계약 검증에 `typeof result.snapshot.workspaceId !== 'string' || !result.snapshot.workspaceId.trim()` 가드를 추가하여 빈/누락 workspaceId 응답을 fail-closed로 즉시 거부(`throw new Error('WorkspaceEditView 응답 계약 불일치')`).
   - `mapWorkspaceFilesToInvItems`에서 `|| 'default-workspace'` 강등 코드를 영구 삭제하고, `workspaceId` 누락 시 즉시 예외 투척.
   - Base64 디코딩 실패 시 `catch { decodedContent = undefined; decodeError = 'Base64 디코딩 실패: ...'; }`로 정직하게 실패 처리.
3. **UI 및 무결성 검증 fail-closed 처리 (`apps/web/src/features/desktop/InvFileExplorer.tsx`)**:
   - 디코딩 오류 파일 선택 시 `data-testid="file-decode-error-banner"`, `role="alert"` 배너 표출:
     - `⚠️ 파일 본문 디코딩 실패 (Base64 손상 또는 미지원 형식)`
     - `👉 [사용자 조치 필요]: 원본 데이터가 손상되었거나 텍스트 디코딩이 불가능한 바이너리 파일입니다. 체크아웃을 다시 시도하거나 원본 바이너리 다운로드 경로를 사용하십시오.`
   - 무결성 검증 클릭 시 `if (selectedFile.decodeError)` 조건으로 즉시 차단하여 `status: 'error'`, `integrityError: '본문 Base64 디코딩 실패로 무결성을 검증할 수 없습니다...'`로 fail-closed 방어.

## 4. 검증 결과

### 4.1. 단위 및 통합 테스트
- `apps/web/tests/workspace-edit-view-contract.test.ts`:
  - `workspaceId 누락 시 fetchWorkspaceEditView 거부` (신규 통과)
  - `mapWorkspaceFilesToInvItems workspaceId 누락 시 예외 투척 (default-workspace 강등 금지)` (신규 통과)
  - `Base64 손상 파일 디코딩 실패 시 content=undefined 및 decodeError 설정 (조용한 둔갑 금지)` (신규 통과)
  - 총 10/10 tests passed.
- `apps/web/tests/inv-file-explorer-dom.test.tsx`:
  - `Base64 디코딩 실패 파일 선택 시 경고 배너 및 사용자 조치 안내 표출, 무결성 검증 fail-closed 차단` (신규 DOM 테스트 통과)
  - 총 20/20 tests passed.
- `apps/web` 전체: **73개 파일 646/646 tests passed (100%)**.

### 4.2. 돌연변이 사살 (Mutation Testing)
1. **돌연변이 1 (workspaceId 기본값 회귀)**:
   - `workspaceEditObservation.ts`에 `wsId || 'default-workspace'` 복원 주입 시 `workspace-edit-view-contract.test.ts` 1 failed로 사살(KILLED) 실측 후 원복.
2. **돌연변이 2 (Base64 디코딩 실패 조용한 둔갑 회귀)**:
   - `workspaceEditObservation.ts`에 `decodedContent = f.dataBase64` 복원 주입 시 2 failed로 사살(KILLED) 실측 후 원복.

### 4.3. 실제 Google Chrome 153 브라우저 실측
- 환경: Google Chrome 153.0.7070.0 (공식 빌드, Windows)
- 스크립트: `scratch/verify_workspace_edit_observation_chrome.py`
- 실측 항목:
  1. 실제 Web Desktop Shell 및 `inv:// 파일 탐색기` 진입.
  2. 정상 파일(`main.py`): 파일 URI가 `inv://workspaces/wsp_0123456789ABCDEFGHJKMNPQRS/src/main.py`로 렌더링되며 `default-workspace` 기본값 부재 확인. 무결성 검증 클릭 시 `검증 통과 (VERIFIED)` 실측.
  3. 손상 파일(`corrupted-binary.bin`): `data-testid="file-decode-error-banner"` (`role="alert"`) 표출, 텍스트 내 "파일 본문 디코딩 실패", "Base64 손상 또는 미지원 형식", "사용자 조치 필요" 렌더링 확인. 무결성 검증 클릭 시 `검증 오류 (ERROR)` 및 fail-closed 차단 실측.
- 스크린샷: `scratch/real_chrome_workspace_edit_observation.png`
- 결과 JSON: `scratch/chrome_workspace_edit_observation_acceptance_result.json` (`passed: true`, exit code 0).

### 4.4. 거버넌스 게이트 도구
- `python tools/check_frontend_integrity.py`: 82개 파일 0 violations PASS.
- `python tools/check_contract_bindings.py`: 39 fixtures / 12 serving anchors PASS.
- `python tools/check_docs.py`: 24 hashes, 712 versioned documents PASS.
- `python tools/check_doc_single_source.py --ratchet`: 18 pairs PASS.
