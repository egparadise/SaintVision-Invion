---
doc_id: "HIST-CLAUDE-LOWRISK7-CODE-REVIEW-001"
title: "독립 검토 — Codex 저위험 쓰기 계약 7건: 기록 대 코드 대조(전부 tip에 live·무게 확인)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["independent-review", "codex", "response-contract", "record-vs-code", "doc-only-commit", "non-vacuous"]
---

# 독립 검토 — 저위험 쓰기 계약 7건: 기록 대 코드

`f2d86db5`는 **문서 전용 커밋**이라 저위험 쓰기 응답 계약 7건을 완료로 기록만 했다. "기록이 있다 ≠ 코드가 있다"이며, 오늘 tip이 수십 번 이동·병합됐으므로 그 7건이 **지금 tip 코드에 실제로 살아 있는지**를 대조했다(문서 전용 커밋의 완료 기록은 코드 위치를 대조한다 — [[doc-only-commit-verify-the-code]]). Codex 큐 밖(검토는 내 역할).

## Provenance

- 검토 tip: origin/integration `ce300cf5`. 계약 코드 최종 커밋 `d901a0d1`(announcement 4상태 fix; 7건 벌크는 그 앞 커밋들)은 **tip과 worktree HEAD `712d9560` 모두의 조상임을 확인**(`git merge-base --is-ancestor`) — 병합 중 소실 없음. 내 문서 전용 커밋은 코드에 무영향이라 in-place 실행 = tip.
- 인터프리터 `.venv/Scripts/python.exe`(py3.14.6, pytest 9.1.1), cwd `C:\Project\SaintVision-Invion`. 순수 스키마·라우트 단위(PG/HTTP/CI 불요).

## 기록의 7건 (f2d86db5 문서에서 읽음)

| # | route | response model | fixture |
|---|---|---|---|
| 1 | POST /nodes/{node_id}/heartbeats | HeartbeatAcceptedResponse | heartbeat-accepted-response.json |
| 2 | POST /nodes/liveness-sweeps | NodeLivenessSweepResponse | node-liveness-sweep-response.json |
| 3 | POST /discovery/announcements | DiscoveryAnnouncementResponse | discovery-announcement-response.json |
| 4 | DELETE /discovery/candidates/{announcement_id} | DiscoveryDeclineResponse | discovery-decline-response.json |
| 5 | DELETE /projects/{project_id}/members/{user_id} | ProjectMemberRemovalResponse | project-member-removal-response.json |
| 6 | PUT /users/{user_id}/status | UserStatusResponse | user-status-response.json |
| 7 | PUT /projects/{project_id}/status | ProjectStatusResponse | project-status-response.json |

## 대조 결과 — 7건 전부 tip 코드에 live (기록 == 코드)

- **모델**: 7개 전부 `saintvision.api.schemas`에서 import 성공.
- **라우트 결속**: 7개 전부 정확한 경로+메서드의 데코레이터에 `response_model=schemas.<Model>` 부착 확인 — nodes.py:128/212, pools.py:50/296, settings.py:136/169/208. 각 경로·모델 짝이 기록 표와 정확히 일치.
- **fixture**: 7개 전부 `contracts/fixtures/`에 존재.
- **회귀 시험**: `tests/core/test_low_risk_write_response_contracts.py` **19 passed**. 앵커 `test_all_low_risk_write_routes_keep_their_response_model_anchor`가 살아있는 FastAPI route 객체의 `response_model`이 정확히 그 모델인지 단언 + fixture roundtrip(7) + extra-forbid reject-unknown(7).
- **하나도 누락 없음** — "기록엔 완료, 코드 없음"의 나쁜 가짜 초록은 이번엔 없다.

## 무게 (되돌림 — present ≠ guarded)

앵커의 감지력을 내 손으로 확인했다: 7건 각각의 살아있는 route `response_model`을 메모리에서 None으로 떼자 앵커 단언이 **7번 모두 실패를 감지(KILLED)**했고, 복원하면 다시 성립했다(baseline 7/7 hold → 각 detach 감지 → restore ok). extra-forbid strict성은 reject-unknown 시험 통과가 증명한다.

## 도구 caveat (정직)

첫 `grep 'response_model=<Model>'`이 빈 결과였다 — 코드가 `response_model=schemas.<Model>`(schemas. 접두)라 정규식이 못 잡은 것. **빈 출력은 깨진 도구지 발견이 아니다**([[empty-output-is-not-evidence]]) — 넓혀서 결속을 확인한 뒤에야 판정했다.

## 판정

**7건 전부 기록과 코드가 일치하고, 결속이 tip에 live하며, 앵커가 무게를 가진다.** 이 7건은 독립 검토 완료. 한계: 선언 앵커(라우트 객체의 response_model)와 fixture 계약 검증까지이며, 실제 HTTP 직렬화·PG·브라우저 인수는 이 단순 응답 변경 범위 밖(f2d86db5 문서도 동일 명시). ModelRetry 제품 노출 여부는 사용자/업무 owner 결정(감사의 별개 항목).
