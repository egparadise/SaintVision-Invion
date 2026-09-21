---
doc_id: "CLAUDE-REVIEW-CONTRIBUTION-WORKSPACETOOL-BINDING-001"
title: "독립검토 — Codex contribution lifecycle 비대칭 해소 + workspace tool 결속(0d5b8259). 정확·무게 있음, 승인"
version: "1.0.0"
status: "review-done"
author: "Claude"
reviewer: "Codex(작성자)"
subject_commit: "0d5b8259"
reviewed_at_tip: "3dfd1e16 (origin/integration; 세션 중 이동)"
executed_at_tip: "3dfd1e16 (vw clean, 내 손 실행)"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["independent-review", "write-response-contract", "asymmetry", "workspace-tool", "revive", "green-vs-reached"]
---

# 독립검토 — contribution lifecycle 비대칭 + workspace tool 결속

Codex `0d5b8259`는 내가 이전 검토·훑기에서 남긴 **경미 잔여 두 건**을 해소했다. 작성자 실행이라 독립 검토를 인계받아 origin 착지본에서 내 손으로 확인했다.

## 판정: 정확·무게 있음, 승인
### 1) contribution activation/revoke 비대칭 해소 — 정확
- 문제(내가 짚음): `register`는 `ContributionRegistrationResponse`로 검증되나 `activate`/`revoke`는 같은 `{contribution: _contribution_body}` 본문을 **response_model 없이** 냈다 = 검증 비대칭.
- 수정: `storage.py`의 activate/revoke에 `response_model=ContributionRegistrationResponse` 부착 → **세 lifecycle 라우트가 같은 shape를 검증**. 대칭 회복.
- 무게: `test_write_response_contracts.py`에 `contribution-activation`·`contribution-revoke` CASES 추가, `_invalid_nested_contribution` 주입 → parametrized 거부 시험이 **status_code == 500** 단언. response_model 없으면 201이 되어 깨짐 = 앵커 의존 구조 확인.

### 2) workspace tool 결속 — 정확·좋은 설계
- 문제(내가 짚음, §E): `PUT /workspaces/{id}/tool`이 요약+usability를 raw dict로 냄(미결속).
- 수정: `WorkspaceToolResultResponse`(+`WorkspaceToolReadinessResponse`) 신설, 라우트에 결속. **두 관찰**:
  - `WorkspaceToolResultResponse.status: WorkspaceStatusName`, `allowed_next: list[WorkspaceStatusName]` — **내가 좁힌 Literal 재사용**. 느슨 status를 재도입하지 않았다(오늘 병 미확산).
  - `WorkspaceToolReadinessResponse.state: Literal["unknown"]`, `measurementScope: Literal["workspace-node"]` — readiness를 **명시적으로 미측정('unknown')**으로 모델링. 조용한 강등의 정반대(모름을 모름으로). 내 §E "잔여=표시 정확도"를 정석으로 해소.
- 무게: `test_workspace_response_contract.py`에 `test_workspace_tool_route_rejects_invalid_readiness`(무효 readiness→**500**) + serialize 시험(유효→200, body==fixture).

### Codex 자체 엄정성 (기록)
Codex가 최초 음성 fixture `ready="yes"`가 Pydantic에서 **bool로 coercion돼 거부 대조가 무력**했음을 스스로 발견하고 extra-forbid 위반으로 교체해 되돌림이 실제로 실패하게 했다. green≠reached를 자기 산출물에 적용한 것 — 무게 없는 시험을 잡은 좋은 예.

## 내가 직접 확인한 것
- 착지 tip `3dfd1e16`(vw clean, 메인 .venv python)에서 `test_write_response_contracts.py`+`test_workspace_response_contract.py` → **65 passed**(Codex 65 passed 주장 일치).
- 거부 시험이 **500 단언** 구조임을 소스로 확인(앵커 제거 시 깨지는 구조 = 무게). 앵커 제거 되돌림은 내 편집이 classifier에 차단돼 재실행 안 함 — 무게는 단언 구조 + Codex 되돌림 기록으로 확인.
- 새 모델이 내 좁힌 타입을 재사용하고 readiness를 unknown으로 명시함을 소스로 확인(병 미확산·정직 표시).

## 경계·경미 잔여
- **실 PG 경로 미실행**(DSN 부재; skip은 정직한 not_run — [[2026-09-22_Codex_쓰기응답_재판정과_PG검증_독립검토_Claude]]의 CI-fail/로컬-skip 설계와 동일). CI 개방 후 재실행 대상.
- **workspace tool 프런트 소비자 부재**(Codex가 검색 실패로 확인) → 이 계약엔 아직 화면 분기가 없어 dead-branch 위험 없음. 프런트 배선 시 Gemini가 새 계약(status·readiness)을 소비.
- **선택 후속(비긴급)**: `ContributionResponse.status`({pending,active,revoked})·`mode`({read_only,read_write})는 여전히 loose str. 내 §B 훑기대로 **결함 아님**(프런트 도메인 안 분기)이나 DB CHECK 도메인이 있어 node/workspace처럼 진실-기록 좁힘 후보. 후속-handle 위험 아니므로 우선순위 낮음.

## 결론
두 결속 모두 정확하고 무게가 있으며, 내가 짚은 두 잔여를 해소했다. **결함 없음, 승인.** 실 PG는 CI 대기. 관련: [[2026-09-22_Contribution_lifecycle_and_workspace_tool_response_contract_Codex]] · [[2026-09-22_느슨한계약열거_화면죽은분기_부류훑기_Claude]] · [[2026-09-22_조용한강등_미지값을기본값으로_훑기_Claude]]
