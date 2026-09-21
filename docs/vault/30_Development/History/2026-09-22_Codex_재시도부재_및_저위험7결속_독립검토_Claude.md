---
doc_id: "CLAUDE-REVIEW-RUN-RETRY-AND-LOW-RISK-BINDINGS-001"
title: "독립검토 — Codex Run 재시도 부재 감사 + 저위험 쓰기 7결속. 둘 다 성립·무게 있음, 승인"
version: "1.0.0"
status: "review-done"
author: "Claude"
reviewer: "Codex(작성자)"
subject_commits: ["72bec59c", "d901a0d1", "f2d86db5", "044c343a(도달성 감사)"]
reviewed_at_tip: "b6020e7a (origin/integration; 세션 중 이동)"
executed_at_tip: "b6020e7a (vw clean, 내 손 실행)"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["independent-review", "absence-claim", "run-retry", "low-risk-write", "state-machine", "revive"]
---

# 독립검토 — Run 재시도 부재 + 저위험 7결속

Codex 작성자 실행 인계. 두 건을 origin 착지본에서 내 손으로 확인했다.

## 1) Run 재시도 제품 경로 부재 — **부재 주장 성립**
Codex 결론: 일반 실패 Run을 다시 실행하는 제품 경로가 없다. 오늘 두 번 세운 부재-주장 방식(전수 + 갈래가 실제로 다른가)으로 검증했다.

- **재시도처럼 보이는 것 전수 대조 → 전부 실행-재시도 아님**: DeliveryQueue/Worker(전달 재관찰, `execution_deliveries.attempts` ≠ `runs.attempt`) · OutputIngestion(결과 재수집) · Run목록 "다시 시도"(onRefresh 읽기) · Run 생성 API(새 draft) · `/nodes/{id}/resume`(노드 도메인, run 아님) · `app.py:192 replay`(ASGI 본문 버퍼링). 놓친 표면 없음(넓은 grep 확인).
- **갈래가 실제로 distinct**(같은 것 다르게 부른 것 아님): WorkspaceResume(단일 run 다음 step) vs ShardRecovery(parent plan→child runs) vs ModelRetry(model child run) — 서로 다른 코드·범위·배선.
- **결정적 확인 — 상태기계가 구조로 강제**: migration `0001_core.sql`·`0018_workspace_resume.sql`의 전이표에 **`failed → *` 전이가 없다**(failed는 종단). `recovering`은 `running`/`verifying`에서만 도달 → **failed→recovering 불가**. 따라서 WorkspaceResume(recovering 대상)은 일반 실패 Run을 재실행 못 한다. (내부 폐쇄 도메인=DB CHECK가 사실을 강제하는 rule 7의 그 성질.)
- **미배선 확인(내 손 grep)**: `ModelRetryStore`는 `model_retry.py` 정의만, 제품 참조 0(app/worker 미조립). `ShardRecovery`도 app.py/worker에서 생성·호출 0.
- **경계**: 정적 소스/설정 감사. 외부 배포 wrapper는 확인 못 함(Codex도 동일 경계). Worker/DB 런타임 미실행.
- **판정**: 부재 주장 **성립**. failed Run은 별도 workspace/shard/model 복구가 성립하지 않는 한 failed로 남는다. 이는 우발 누락이 아니라 문서가 endpoint/auth를 후속으로 남긴 **계획된 미착지** — 노출 여부는 제품/업무 owner 결정.

## 2) 저위험 쓰기 7결속 — **정확·무게 있음, 내 분류 확인**
사용자가(그리고 내 쓰기-라우트 훑기가) 저위험으로 분류한 7 수령증/상태 route를 Codex가 계약 앵커로 묶었다.

- **7 모델이 실제 return 본문과 일치**: heartbeat`{nodeId,applied,heartbeatSequence}` · liveness`{markedLost,timeoutSeconds}` · announce`{accepted,state}` · decline`{announcementId,state}` · member removal`{projectId,userId,removed}` · user status`{userId,status}` · project status`{projectId,status}`. 모두 요청 id 반향 또는 상태값 — **새 후속 handle 없음**(내 저위험 분류 확인).
- **rule 7까지 적용**(주목): 상태/수령 필드를 도메인으로 좁혔다 — `UserStatusResponse.status: Literal[active,suspended,retired]`, `ProjectStatusResponse.status: Literal[active,archived]`, `DiscoveryDeclineResponse.state: Literal[declined]`, announce 4상태. 내부 폐쇄 도메인이라 정당.
- **announce 4상태 보존**(follow-up `d901a0d1`): 기존 admitted/declined/expired row를 다시 announce하면 서비스가 결정을 되살리지 않고 기존 상태를 응답 → 모델이 4상태 허용. Codex가 자기 과잉좁힘(candidate만)을 교정. 네 상태 roundtrip 시험 추가.
- **무게(내 손 실행+구조)**: `tests/core/test_low_risk_write_response_contracts.py` **19 passed**. `test_all_low_risk_write_routes_keep_their_response_model_anchor`가 7 route의 `response_model` 부착을 단언(detach 감지=Codex의 7/7 되돌림 구조 확인) + reject-unknown(extra-forbid) + announce 4상태. Codex 확대 4파일 77 passed.
- **경계**: route-level TestClient·fixture. 실 PG·HTTP·UI 미실행(CI 대기).

## 결론
두 건 모두 성립. 재시도 부재는 상태기계가 뒷받침하는 견고한 부재 주장이고, 7결속은 정확·무게 있으며 내 저위험 분류를 확인한다. **결함 없음, 승인.** 재시도/복구/배치(placement)의 제품 노출은 사용자 결정 — 브리프 §6에 부류로 반영: [[사용자_결정대기_브리프_2026-09-22]].

관련: [[2026-09-22_Run_retry_path_and_low_risk_write_contracts_Codex]] · [[2026-09-22_ControlPlane_제품경로_도달성_감사_Codex]] · [[검증규칙과_세축_canon]](rule 7·부재주장)
