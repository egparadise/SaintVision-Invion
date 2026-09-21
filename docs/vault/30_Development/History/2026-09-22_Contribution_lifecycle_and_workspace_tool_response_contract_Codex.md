---
doc_id: "CODEX-CONTRIBUTION-WRITE-CONTRACT-002"
title: "Contribution lifecycle 비대칭 및 workspace tool 쓰기 응답 결속"
version: "1.0.0"
status: "implementation-verified-review-pending"
author: "Codex"
reviewer: "pending"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["write-response-contract", "fastapi", "mutation", "provenance"]
---

# Contribution lifecycle 비대칭 및 workspace tool 응답 결속

## 범위와 판단

기준 코드 SHA는 `1381e2c2147d3f0846aef44277745d21bbb5d0ed` (`integration/all-agents-unified`, `C:/Project/SaintVision-Invion`)이다. 이 검증 시점 원격 integration은 `9b6e9a4abc2d`였고 로컬은 한 커밋 뒤처져 있었다. 트리는 다른 작업자의 프런트엔드·계약 변경으로 dirty였으며 해당 파일은 건드리지 않았다.

`register_contribution`, `activate_contribution`, `revoke_contribution`은 각각 같은 `{contribution: ContributionResponse}` 본문을 반환한다. `_contribution_body`가 각 필드를 동일한 `ContributionResponse` 생성자로 검증하고, `ContributionRegistrationResponse`가 그 객체를 strict wrapper로 감싼다. 그러므로 활성화와 철회에도 등록과 같은 FastAPI `response_model`을 붙였다. 현재 응답 모델의 lifecycle `status`는 `str`이며, 이 변경은 응답 shape를 정렬하고 미래의 필드 drift를 차단한다.

남은 raw-dict 쓰기 중 별도로 선택한 것은 `PUT /v1/workspaces/{workspace_id}/tool`이다. 이것은 Workspace 요약과 `toolReadiness`를 함께 돌려주므로 기존 `WorkspaceSummaryResponse`만 붙이면 추가 readiness 필드를 필터링한다. 별도 strict `WorkspaceToolResultResponse`와 `WorkspaceToolReadinessResponse`를 만들었다. `state="unknown"`, `measurementScope="workspace-node"`는 실제 반환의 의미를 보존한다. 프런트의 소비 어댑터는 검색에서 찾지 못했으므로 이 작업은 backend 계약/route에 한정한다.

Claude의 위험 재판정 기준으로 남은 단순 수령증·상태 응답은 새 후속 요청의 handle이나 입력을 만들지 않는다. 이 작업은 그 전체 저위험 목록을 완료로 표시하지 않는다. 현재 미결속 저위험 응답은 heartbeat, liveness sweep, discovery announcement/decline, member removal, user status, project status다. Workspace tool과 Contribution activation/revoke는 이번 변경으로 결속했다. 커널/control-plane write는 별도 계약 레인이다.

## 검증 증거

Provenance 래퍼 `python tools/provenance.py -- ...`의 출력에 인터프리터 절대 경로 `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe`, 실행 위치, SHA, dirty 상태, 원격 대비 상태, KST 시각, 환경 게이트를 남겼다.

- 2026-09-22 03:33:51 KST: `tests/core/test_write_response_contracts.py tests/core/test_workspace_response_contract.py -q` → exit 0, **65 passed**, 2 deprecation warnings.
- 같은 시각대: `tools/export_schemas.py --check` → exit 0, **49 schemas** 일치.
- 같은 시각대: `tools/check_contract_bindings.py` → exit 0, **39 fixtures** test 참조, 12 kernel-serving response anchors 검사 통과. WorkspaceTool 응답은 FastAPI response_model serving 경로로 검사기에 의해 live로 인식됨.
- Contribution route anchor 되돌림: `activate_contribution`에서 response_model만 제거 → 해당 invalid-response 시험 exit 1 (1 failed); `revoke_contribution`도 같은 변형에서 exit 1 (1 failed). 각각 원복했다.
- Workspace tool route anchor 되돌림: `response_model`을 임시 제거 → `test_workspace_tool_route_rejects_invalid_readiness`가 200을 받아야 할 500과 달라져 exit 1 (1 failed). 원복했다.
- 최신 원격 base `f14ba9aed40b49607acd4db214f252c806de46d0`의 별도 worktree에서도 세 제거 변형이 각각 exit 1 (1 failed)이고, 원복 후 focused suite 65 passed임을 다시 확인했다.
- 2026-09-22 03:34:47 KST: service tool-choice 시험과 두 계약 시험 파일 재실행 → exit 0, **65 passed, 1 skipped**. 유일한 skip은 `tests/test_projects.py:388`, `INV_TEST_ADMIN_DSN is absent; PostgreSQL tests not run`. 따라서 service DB 경로는 이번에 실측하지 않았다.
- 2026-09-22 03:42:07–03:42:19 KST, cleanly based on `f14ba9aed40b49607acd4db214f252c806de46d0`: provenance로 `tools/check_docs.py` exit 0 (24 original hashes, 711 versioned documents), `tools/check_ontology.py` exit 0, `tools/sync_obsidian.py --check` exit 0 (1512 managed, 4 pending exports, 0 conflicts, no writes), `git diff --check` exit 0. Obsidian pending 네 건은 적용하지 않았다.
- 초기 잘못된 검증 selector `test_a_supported_tool_can_be_chosen`는 실제 시험 이름과 달라 pytest exit 4/collection error였다. 정확한 `test_the_tool_choice_is_recorded_on_the_workspace`로 다시 실행했고 결과는 위와 같다.
- 초기 음성 fixture는 `ready="yes"`를 사용했으나 Pydantic이 이를 bool로 coercion해 거부 대조가 되지 않았다. fixture를 strict `extra-forbid` 위반으로 바꿨고, route anchor 제거 대조는 이를 실제로 실패시켰다.
- `git diff --check` → exit 0.

## 경계

실행 검증은 route-level FastAPI TestClient와 service/fixture 대역 및 로컬 프로젝트 단위 시험이다. 실 PostgreSQL 경로는 DSN 부재로 실행되지 않았다. 독립 검토와 CI는 pending이며 작성자 실행으로만 기록한다. 이 작업에서 브라우저 인수, 프런트 배선, Obsidian `--apply`는 하지 않았다.

## 다음 행동

1. Codex: 남은 단순 raw-dict 쓰기 7개를 별도 위험/비용으로 정리하고 결속할 범위를 정한다. 사용자가 이미 분류한 대로 후속 handle을 내지 않는 수령증·상태 응답이므로 우선순위는 후속-handle 응답보다 낮다.
2. Claude: 고정 통합 SHA에서 이번 두 route family의 모델·본문 정합성을 독립 검토한다.
3. CI/실 PostgreSQL: CI 개방 뒤 DB-backed workspace-tool와 contribution lifecycle 경로를 재실행한다.
