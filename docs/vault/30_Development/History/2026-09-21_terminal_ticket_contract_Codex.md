---
doc_id: "WORK-TERMINAL-001"
title: "PTY terminal ticket 계약 결속 및 Gemini 화면 인계"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-21T19:12:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["terminal", "pty", "contracts", "security"]
---

# PTY terminal ticket 계약 결속 및 Gemini 화면 인계

## 범위와 결정

VF-GM-05 화면 코드에는 `workspaceId`/`sessionId`를 보내고 `ticketId`/`ptyWsUrl`을 기대하는 모양이 남아 있었다. 실제 제어 평면은 `TerminalTicketInput.commandId`를 요구하고 `TerminalTicketResult`의 `ticket`, `expiresAt`, `sessionId`, `websocketPath`를 반환한다. WebSocket 경로도 workspace/session-scoped route이며 query string은 거부하고 첫 JSON frame `{ticket}`을 인증한다. PTY 티켓 발급·wire 계약은 Codex 보안/공통 계약 소유다. 화면 상태·선택 동작은 변경하지 않았다.

기존 canonical request/response schema를 확인하고, `TerminalTicketAuthFrame`을 추가해 WebSocket 첫 프레임도 strict contract로 고정했다. `websocketPath`는 내부 workspace/session 경로와 유효 ID 형식만 허용한다. Backend WebSocket 입구가 auth frame을 같은 validator로 검사한다. Frontend의 계약 전용 `terminalTicket` adapter는 요청·응답을 canonical 타입으로 묶고, 응답 shape와 경로를 런타임 검사한다. WebSocket handshake helper는 `inv-terminal-v1` 및 첫 auth frame을 반환하며 bearer ticket을 URL에 싣지 않는다.

## Gemini 전달 대기 — 사용자 릴레이

- 빈 노드에서 PTY 티켓 발급을 시작하지 않는다. 서버 발급에는 명시적 `commandId`가 필요하므로 UI는 선택한 실행의 commandId가 있을 때만 `issueTerminalTicket(workspaceId, { commandId })`를 호출해야 한다.
- 현재 화면을 새 adapter에 연결하고, 서버 응답 `websocketPath`로 연결하며 ticket query string을 제거하고, 연결 후 첫 frame으로 adapter의 `authFrame`을 전송한다. 화면의 사용자 상태/오류/접근성 변경은 Gemini 소유다.
- 티켓 자체나 일부를 화면/로그에 출력하지 않는다. Codex 변경은 화면 컴포넌트와 브라우저 사용자 흐름을 수정하지 않았다.

## 구현·검증

- 시작: branch `agent/codex/terminal-pty-contract`, worktree `C:/Project/SaintVision-Invion/.worktrees/codex-terminal-pty-contract`, base integration `b49b38dfcd238e5fdca3ce2f665a4956b301c51a`. 앞서 완료한 ProblemDetails/NodeStopReceipt 작업 branch `agent/codex/problem-details-contract` (`2f41851cab49a8af1bfbb45dcf2717164b00aa83`)를 별도 worktree로 fast-forward하여 계약 수정도 함께 실렸다.
- 계약 구현은 commit `972855622b2f5256189989502183c33edaa16886`에 있다. 변경 목록은 canonical schema와 Python/TS/Go 생성본, 공유 terminal-ticket input/response fixture, backend WebSocket auth-frame validation, frontend adapter/Ajv test다.
- Provenance가 붙은 로컬 검증은 KST `2026-09-21 19:11:01–19:11:03`, 위 코드 SHA, Python `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe` 3.14.6, Node 24.17.0, executor Codex에서 수행했다. PostgreSQL DSN absent, Docker present, Go absent. 당시 문서 두 파일은 이 History 링크를 추가하는 중이라 working tree dirty였다. remote integration ref는 검사 시점 `64dd7f66900f`였으며 이 checkout은 그 ref보다 2 behind/5 ahead였다. 따라서 아래 결과를 integration 결과로 부르지 않는다.

| 명령 | 결과 |
|---|---|
| `.venv` Python `pytest -q tests/core/test_terminal_ticket_contract.py tests/core/test_problem_details_contract.py` | 13 passed, 0 failed, exit 0 |
| `npm --prefix apps/web test` | 53 files, 478 passed, exit 0 |
| `npm --prefix apps/web run build` | `tsc -b` + Vite build 성공, exit 0 |
| `npm run --prefix apps/web contracts:check` | 15 API response type schemas 일치, exit 0 |
| `.venv` Python `tools/check_ontology.py` | exit 0; task mappings 48 |
| `.venv` Python `tools/check_docs.py` | 첫 실행 exit 1: 이 문서가 아직 생성되지 않아 두 새 위키 링크가 깨짐. History 문서 추가 후 재실행 필요 |

계약의 실효성을 보려고 root와 packaged schema에서 `websocketPath` pattern을 제거했다. 그 변형에서 Python 시험은 외부 URL 사례에서 1 failed, Vitest는 Ajv 외부 URL 사례에서 1 failed로 각각 비정상 경로를 허용한 사실을 잡았다. pattern을 원복했다. 정상 상태 focused run은 Python 10 passed와 Vitest 8 passed였다. generator `tools/generate_contracts.py`를 실행해 Python/TS/Go와 packaged schema를 갱신했다.

## 남은 검증 경계

새 branch에서 구현 및 로컬 시험을 했으며 integration 반영·CI·Claude 독립 리뷰는 별도다. PostgreSQL DSN이 없어 API 발급의 DB 경로를 실행하지 않았다. 실제 PTY/WebSocket 연결 및 브라우저 인수는 이 작업에서 실행하지 않았다. 기존 `tests/integration/test_workspace_terminal.py`는 live ticket과 server 반환 `websocketPath`를 사용해 실제 WebSocket 첫 frame을 보내는 통합 경로를 포함하지만 이번 실행 증거는 아니다. Gemini adapter wiring이 끝난 뒤 해당 lane을 재검증한다.
