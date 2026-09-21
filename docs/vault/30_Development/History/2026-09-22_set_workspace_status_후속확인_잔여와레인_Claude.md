---
doc_id: "CLAUDE-SET-WS-STATUS-FOLLOWUP-001"
title: "set_workspace_status 후속 확인 — Codex가 닫음; 잔여 1건(WorkspaceSummaryResponse 느슨 타입)은 프런트 TS 재생성 불가로 미착수·권고; artifact-content은 커널=Codex"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
checked_at_tip: "dabfc40d"
updated: "2026-09-22"
source_of_truth: "Git"
tags: ["contract", "workspace-status", "followup", "lane", "verify-boundary"]
---

# set_workspace_status 후속 확인

내가 다음 착수로 적었던 set_workspace_status는 **이미 Codex가 결속**(`827777e`). "목록에 있다고 아직 안 된 것은 아니다"를 확인했다.

## 닫힌 것 (Codex 827777e, 검증)
- `WorkspaceStatusResponse` 스키마(+`contracts/workspace-status-response.schema.json`+fixture) 신설, 라우트에 `response_model=WorkspaceStatusResponse`.
- `status: WorkspaceStatusName`, `allowed_next: list[WorkspaceStatusName]` — `WorkspaceStatusName = Literal["provisioning","ready","suspended","deleting","deleted"]`로 제한.
- 실 PG에서 provisioning→ready 전이 및 다음 전이 집합 확인(Codex). → **닫힘.** allowedNext 로직은 `WORKSPACE_TRANSITIONS`(단일 소스)에서 계산되어 상태기계와 일치.

## 잔여 1건 (내 레인, 그러나 미착수 — 검증 경계)
- **무엇**: `WorkspaceSummaryResponse`(create_workspace·list_workspaces가 쓰는, 내가 결속한)는 **같은 의미의 필드를 아직 느슨하게** 둔다 — `status: str`, `allowed_next: list[str]`. 형제 `WorkspaceStatusResponse`는 `WorkspaceStatusName`으로 엄격. **같은 필드가 한 응답엔 엄격, 다른 응답엔 느슨** = 비대칭. create/list 응답에 비-lifecycle 값이 새면 안 잡힌다.
- **안전성 확인**: DB CHECK `status IN ('provisioning','ready','suspended','deleting','deleted')`(migration 0002)로 도메인이 정확히 그 5 → 좁혀도 500 위험 없음. 백엔드 재생성 검증됨: `export_schemas.py` 재생성 후 `--check` **PASS**(46 schemas), 스키마에 enum 반영, schemas.py import OK.
- **왜 미착수(오늘의 규율)**: 스키마를 좁히면 **프런트 생성 TS도 재생성**해야 게이트(`contracts:check`)를 통과한다. 그런데 vw의 `apps/web/node_modules`에 **`json-schema-to-typescript` 부재**(`ERR_MODULE_NOT_FOUND`)라 **TS 재생성·검증을 여기서 못 한다.** 반쪽만(스키마만) 올리면 생성 TS가 stale → 프런트 게이트 적색. **못 돌리는 검증을 안고 올리지 않는다**(오늘 계속 지킨 원칙) → 변경 되돌리고 vw clean 복귀.
- **권고(작은 코디네이트)**: 백엔드 2줄(`WorkspaceSummaryResponse.status→WorkspaceStatusName`, `allowed_next→list[WorkspaceStatusName]`) + `export_schemas.py` 재생성 + **node_modules 완전한 환경에서 `contracts:generate` + `contracts:check` + tsc**. 도메인 안전(DB CHECK 5)이라 코드 위험은 낮고, 프런트 tsc만 확인하면 된다. 내 레인(백엔드 스키마)이나 TS 검증 환경이 필요 = Gemini 환경 또는 완전 체크아웃에서 마무리.

## artifact-content은 왜 Codex인가 (가져올 수 있나 확인)
- 라우트 `GET /v1/runs/{run_id}/artifacts/content`는 **커널**(`services/control-plane/src/inv/app.py:414`). 계약·서빙이 커널이라 **Codex 레인**(CLAUDE.md: 커널·고난도는 Codex). → **내 레인 아님**, 가져오지 않는다. Codex가 신선도·제공량으로 바쁘면 순서만 뒤로.

## 다음 (레인별, 작은 것부터)
- **Claude(내 레인)**: 위 WorkspaceSummaryResponse 타입 정합 — TS 검증 환경 확보 시 마무리(작음). 그 외 saintvision write 결속은 [[2026-09-22_쓰기응답_잔여위험_재판정_Claude]] 참조(대부분 MED/자체검증).
- **Codex**: 신선도 4필드(진행 중)·node 사용량 계약·artifact-content 결속·Go/PG.
- **Gemini**: 화면 배선(오늘 정직화 완료분 외).

관련: [[2026-09-21_작업공간생성_백엔드경로_점검_Claude]] · [[2026-09-22_쓰기응답_잔여위험_재판정_Claude]] · [[2026-09-22_미구현목록_백엔드대조_남은구현범위_Claude]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
