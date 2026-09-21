---
doc_id: "HIST-GEMINI-20260922-WS-STATUS-001"
title: "WorkspaceItem 잉여 어휘 소거 및 WorkspaceList 5대 상태 정직화와 Chrome 153 실측 수용"
version: "1.0.0"
status: "approved"
author: "Gemini"
reviewer: "Claude"
measured_at_tip: "23f76b91"
updated: "2026-09-22T04:33:00+09:00"
source_of_truth: "Git"
tags: ["workspace", "enum-tightening", "dead-branch", "chrome153", "mutation-testing", "gemini"]
---

# WorkspaceItem 잉여 어휘 소거 및 WorkspaceList 5대 상태 정직화와 Chrome 153 실측 수용

## 1. 개요 및 배경

Claude의 부류 훑기([[2026-09-22_느슨한계약열거_화면죽은분기_부류훑기_Claude]] §C 권고)에 따라, 프런트엔드가 백엔드 계약보다 풍부한 status 어휘를 상상하여 유지하던 휴면 잉여 어휘를 정리하고, 화면 컴포넌트가 백엔드 정본 계약 5상태에만 엄격히 결속되도록 정합했다.

- **원형의 문제**:
  - `apps/web/src/contracts/types.ts`의 `WorkspaceItem.status`가 `WorkspaceStatusName | 'active' | 'terminating' | 'reclaimed' | string`으로 느슨하게 열려 있어, 백엔드에는 존재하지도 않는 가상의 상태(`active`, `terminating`, `reclaimed`)를 허용하고 있었다.
  - `apps/web/src/features/workspaces/WorkspaceList.tsx`에는 "레거시 상태 호환"이라는 명목으로 `active`, `terminating`, `reclaimed` 분기가 살아 있어 죽은 코드가 양산되고 있었다.
  - `apps/web/tests/workspace-execution.test.ts`에서는 `sampleWorkspace.status: 'active'`, 그리고 자원 회수 단언에서 `status: 'reclaimed'`를 주입하고 단언하는 허구의 상태 검증이 방치되어 있었다.

## 2. 작업 내용

1. **`WorkspaceItem.status` 타입 좁힘 (`apps/web/src/contracts/types.ts`)**:
   - `status: WorkspaceStatusName;`로 좁힘 (`WorkspaceStatusName = 'provisioning' | 'ready' | 'suspended' | 'deleting' | 'deleted'`).
   - 잉여 멤버(`active`, `terminating`, `reclaimed`, `string`) 완전 소거.
2. **`WorkspaceList.tsx` 5대 계약 정직화**:
   - `statusConfig`의 타입을 `Record<WorkspaceStatusName, ...>`로 명시하고 죽은 레거시 분기(`active`, `terminating`, `reclaimed`)를 영구 제거.
   - 혹시라도 알 수 없는 상태가 유입될 경우 조용히 기본값이나 다른 상태로 둔갑하지 않고 `미확인 상태 (${wsp.status})` 뱃지로 표출.
3. **`workspace-execution.test.ts` 계약 정합**:
   - `sampleWorkspace.status`를 백엔드 정상 가동 상태인 `'ready'`로 교정.
   - 자원 회수 시 가상의 `'reclaimed'` 대신 계약에 존재하는 회수 완료 상태 `'deleted'`로 정합.
4. **신규 회귀 방어 테스트 작성 (`apps/web/tests/workspace-list-5state-contract.test.tsx`)**:
   - 5대 계약 상태(`ready`, `provisioning`, `suspended`, `deleting`, `deleted`)가 정확한 한글 라벨과 색상으로 렌더링됨을 단언.
   - 가상 레거시 어휘(`회수/삭제됨 (Reclaimed)`)가 화면에 부재함을 단언.
   - 미확인 미래 확장 상태(`migrating_cluster`) 유입 시 조용한 강등 없이 `미확인 상태 (migrating_cluster)`로 표출됨을 단언.

## 3. 검증 결과

### 3.1. 돌연변이 사살 (Mutation Testing)
- `tests/workspace-execution.test.ts`에 `'active'` 주입 시: `error TS2322: Type '"active"' is not assignable to type 'WorkspaceStatusName'`로 **즉시 사살 (KILLED)**.
- `tests/workspace-execution.test.ts`에 `'reclaimed'` 주입 시: `error TS2322: Type '"reclaimed"' is not assignable to type 'WorkspaceStatusName'`로 **즉시 사살 (KILLED)**.

### 3.2. 실제 Google Chrome 153 (Blink 엔진) 실측 수용
- `scratch/verify_workspace_list_status_chrome.py` 구동:
  - 실제 Chrome 153 브라우저에서 `/callback` 인증을 거쳐 `Workspaces (S03)` 탭으로 진입.
  - `GET /v1/projects/prj_pacs_core/workspaces` 응답의 6개 카드에 대해 실측:
    1. `ready`: `준비 완료 (Ready)` 뱃지 (초록) 실측.
    2. `provisioning`: `프로비저닝 중 (Provisioning)` 뱃지 (주황) 실측.
    3. `suspended`: `일시 중단 (Suspended)` 뱃지 (회색) 실측.
    4. `deleting`: `삭제 중 (Deleting)` 뱃지 (빨강) 실측.
    5. `deleted`: `삭제됨 (Deleted)` 뱃지 (회색) 실측.
    6. `unknown_future_status`: `미확인 상태 (unknown_future_status)` 뱃지 실측 (조용한 둔갑 원천 차단).
  - 안전한 스크린샷 증거: `scratch/real_chrome_workspace_list_5states.png`.
  - 실측 결과 레코드: `scratch/chrome_workspace_list_acceptance_result.json` (`passed: true`).

### 3.3. 정규 게이트 검증
- `npx tsc -b`: exit code 0 (오류 0건).
- `npm run build`: exit code 0 (3.37s, Vite 번들 생성 성공).
- Vitest: **74개 파일 648/648 passed 100%** (순증 +1 파일, +2 passed).
- `check_frontend_integrity.py`: 82개 파일 0 violations (PASS).
- `check_contract_bindings.py`: 46 fixtures / 12 serving anchors PASS.
- `check_docs.py`: 24 hashes, 721 versioned documents PASS.
- `check_doc_single_source.py --ratchet`: 18 pairs PASS.
