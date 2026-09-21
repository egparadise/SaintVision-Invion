---
doc_id: "HIST-GEMINI-20260922-016"
title: "Workspace status 'active' 죽은 분기 소거, 백엔드 5대 계약(ready/provisioning/suspended/deleting/deleted) 정합 및 Chrome 153 실측 완결"
version: "1.0.0"
status: "approved"
author: "Gemini"
created: "2026-09-22T03:02:00+09:00"
updated: "2026-09-22T03:02:00+09:00"
source_of_truth: "Git"
---

# Workspace status 'active' 죽은 분기 소거, 백엔드 5대 계약 정합 및 Chrome 153 실측 완결

## 1. 작업 배경 및 인계 상황
- **Claude 백엔드 계약 좁힘 인계 (`CLAUDE-WS-SUMMARY-STATUS-ENUM-001`)**:
  - Claude가 백엔드 `WorkspaceSummaryResponse`의 `status`를 느슨한 `string`에서 `WorkspaceStatusName = Literal["provisioning","ready","suspended","deleting","deleted"]` 5대 열거형으로 좁힘.
  - 이로 인해 `DeveloperStudio.tsx`의 `wsp.status === 'active'` 분기가 TS2367 (no overlap) 죽은 코드로 드러남.
  - 백엔드 DB(migration 0002)와 커널은 `ready`가 정상 준비 완료 상태이며 `'active'`라는 상태를 일절 반환하지 않음.
  - 결과적으로 실제 정상 가동 준비가 완료된 `ready` 작업공간이 초록색이 아닌 **회색**으로 죽어 표시되는 심각한 시각적/의미적 왜곡 결함이 발생하고 있었음.
- **Claude 착지 대기**:
  - Gemini가 프론트엔드의 죽은 분기를 정합해야 Claude의 백엔드 5파일 좁힘 패치가 integration `tsc`를 깨뜨리지 않고 착지할 수 있음.

---

## 2. 상태 어휘 전수 감사 및 5대 상태 정합

단순히 `wsp.status === 'active'` 2줄을 기계적으로 바꾸는 것에 그치지 않고, 프론트엔드 전역의 작업공간 상태 어휘를 전수 감사하여 백엔드 계약과 완전 정합함:

1. **`DeveloperStudio.tsx` ([`DeveloperStudio.tsx`](file:///C:/Project/SaintVision-Invion/apps/web/src/features/studio/DeveloperStudio.tsx#L1084-L1115))**:
   - `wsp.status === 'active'` 가짜 상태 비교 완전 소거.
   - 백엔드 5대 상태에 대한 스타일 맵 구축:
     - `ready`: 초록색 (`rgba(46, 160, 67, 0.2)` 배경, `#3fb950` 글자, `rgba(46, 160, 67, 0.4)` 테두리).
     - `provisioning`: 경고 주황/노랑 (`rgba(210, 153, 34, 0.2)` 배경, `#d29922` 글자).
     - `suspended`: 중립 회색 (`rgba(139, 148, 158, 0.2)` 배경, `var(--color-text-muted)` 글자).
     - `deleting`: 위험 빨강 (`rgba(248, 81, 73, 0.2)` 배경, `#f85149` 글자).
     - `deleted`: 음소거 회색.
   - `data-testid={`studio-wsp-status-${wsp.workspaceId}`}` 결속.
2. **`WorkspaceList.tsx` ([`WorkspaceList.tsx`](file:///C:/Project/SaintVision-Invion/apps/web/src/features/workspaces/WorkspaceList.tsx#L81-L93))**:
   - 기존에 `ready`가 파란색, `active`가 초록색으로 왜곡되어 있던 어휘를 정정:
     - `ready`: `준비 완료 (Ready)`, 초록색 (`rgba(16, 185, 129, 0.15)`, `var(--color-brand-success, #34d399)`).
     - `deleting`, `deleted` 신규 등록.
     - `active`, `terminating`, `reclaimed`는 레거시 호환 폴백으로 유지.
3. **`types.ts` ([`types.ts`](file:///C:/Project/SaintVision-Invion/apps/web/src/contracts/types.ts#L81-L90))**:
   - `export type WorkspaceStatusName = 'provisioning' | 'ready' | 'suspended' | 'deleting' | 'deleted';` 정본 타입 선언 및 `WorkspaceItem.status`에 결속.
4. **`developer-studio.test.ts` ([`developer-studio.test.ts`](file:///C:/Project/SaintVision-Invion/apps/web/tests/developer-studio.test.ts#L389))**:
   - 백엔드 `execution_readiness.py` L119 `the workspace status is 'ready'` 계약과 일치하도록 mock detail의 `'active'`를 `'ready'`로 정합.

---

## 3. 실제 Google Chrome 153 (Blink 엔진) 실측 수용

색상이 올바르게 나오는지 눈으로 확인하라는 사용자 지침에 따라 실제 Chrome 153에서 실측을 수행함:

- **검증 환경**: Google Chrome 153 (`chrome.exe`), Vite 3005 포트, Python Playwright.
- **Chrome Blink 엔진 계산 스타일 (`window.getComputedStyle`) 실측 결과**:
  ```json
  {
    "ready": {
      "id": "wsp_ready_pacs",
      "text": "ready",
      "color": "rgb(63, 185, 80)",
      "backgroundColor": "rgba(46, 160, 67, 0.2)",
      "borderColor": "rgba(46, 160, 67, 0.4)",
      "borderWidth": "1px"
    },
    "provisioning": {
      "id": "wsp_prov_dicom",
      "text": "provisioning",
      "color": "rgb(210, 153, 34)",
      "backgroundColor": "rgba(210, 153, 34, 0.2)",
      "borderColor": "rgba(210, 153, 34, 0.4)",
      "borderWidth": "1px"
    },
    "suspended": {
      "id": "wsp_susp_bench",
      "text": "suspended",
      "color": "rgb(156, 163, 175)",
      "backgroundColor": "rgba(139, 148, 158, 0.2)"
    },
    "deleting": {
      "id": "wsp_del_cleanup",
      "text": "deleting",
      "color": "rgb(248, 81, 73)",
      "backgroundColor": "rgba(248, 81, 73, 0.2)"
    }
  }
  ```
- **실 브라우저 관측 판정**:
  - `ready` 작업공간 `PACS Accelerated Inference (Ready)` 뱃지가 **Blink 엔진에서 실측 `rgb(63, 185, 80)` (`#3fb950`) 초록색** 및 `rgba(46, 160, 67, 0.2)` 배경으로 선명하게 렌더링됨을 육안 확인.
  - 스크린샷 아티팩트 보존: `scratch/real_chrome_workspace_ready_green.png`.

---

## 4. 게이트 통과 지표
- **단위/통합 테스트**: Vitest **71개 파일 631/631 passed 100%** (순증 +1 파일, +3 passed, exit 0)
  - 신규 DOM 테스트: `apps/web/tests/developer-studio-workspace-status.test.tsx` (3/3 passed).
- **TypeScript 빌드 (`tsc -b`)**: exit 0 (에러 0건).
- **프로덕션 번들 빌드 (`vite build`)**: exit 0 (3.72s).
- **정직성 스캐너 (`check_frontend_integrity.py`)**: 82개 파일 **0 violations (7대 규칙 PASS)**.
- **계약 바인딩 검사 (`check_contract_bindings.py`)**: 38 fixtures / 12 serving anchors PASS.
- **문서 무결성 (`check_docs.py`)**: PASS (703 versioned documents).
