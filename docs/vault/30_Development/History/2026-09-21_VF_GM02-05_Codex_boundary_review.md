---
doc_id: "VF-GM02-05-CODEX-BOUNDARY-REVIEW-001"
title: "VF-GM-02~05 Codex 독립 경계 검토"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Pending independent reviewer"
updated: "2026-09-21T18:33:00+09:00"
code_ref_tip: "d0d41c30a0ee9a0106f89049654c8743c6cf030f"
source_of_truth: "Git"
tags: ["vf-gm-02", "vf-gm-03", "vf-gm-04", "vf-gm-05", "independent-review", "boundary-review"]
---

# VF-GM-02~05 Codex 독립 경계 검토

## 판정 요약

검토 기준은 integration SHA `d416fe50a2816cc3ad891d682f4e1e073a312f49`이다. Gemini 작성자 보고와 구분하여 Codex가 소스 및 집중 DOM 시험을 확인했다.

| 카드 | 깊이 | 판정 | 요약 |
|---|---|---|---|
| VF-GM-02 ResourceExplorer | 얕음 | 차단 발견 없음; 포괄 승인 아님 | 핵심 표시·액션 코드를 읽고 DOM 시험을 포함해 실행했다. 보고된 모든 mutation을 독립 재실행하지 않았다. |
| VF-GM-03 InvFileExplorer | 깊음 | **승인 보류** | 테스트된 callback 분기는 잘 고정돼 있으나 기본 해시 경로는 실제 파일 바이트를 검사하지 않고, 기본 복구 경로는 서버 없는 성공을 합성한다. DesktopShell은 파일·검증·복구 adapter를 전달하지 않는다. |
| VF-GM-04 ModelStudio | 중간 | **승인 보류** | 실제 API가 요약 관측을 반환하지만 뷰가 샤드·복제본·건강 상태를 합성한다. 응답의 `currentAvailability: unknown` 및 재검증 필요 경계를 위반할 수 있다. |
| VF-GM-05 Terminal/IDE | 깊음 | **승인 보류** | 프런트의 티켓 요청/응답/WebSocket 프로토콜이 저장소 백엔드 계약과 맞지 않는다. 빈 노드 fallback도 실제 PTY 요청을 유발한다. 백엔드 권한 검사는 fail-closed로 보이나 실제 HTTP/WS 실행은 하지 않았다. |

가장 깊게 본 VF-GM-03의 무결성·복구 경계와 VF-GM-05의 PTY 인증 경계에서는 실제 변이를 하나씩 되살려 대응 시험의 실패를 확인했다. VF-GM-04는 프런트와 canonical backend response 간 소스 대조 및 DOM 시험을 확인했다. VF-GM-02는 상대적으로 얕게 확인했다. 카드 전체 검토나 Gemini의 모든 mutation 독립 재현으로 확대 해석하지 않는다.

## 발견 사항

### VF-GM-03 — 무결성 확인과 복구는 실제 데이터/서버 결과에 묶여 있지 않음

1. `apps/web/src/features/desktop/InvFileExplorer.tsx`의 `InvFileItem`은 URI와 `contentHash` 등 메타데이터만 제공하고 파일 본문은 포함하지 않는다. 그런데 기본 검증 경로는 `calculateSha256(selectedFile.uri + selectedFile.contentHash)`를 계산한다. 이는 저장된 파일 바이트의 SHA-256이 아니다. `onVerifyIntegrity`는 선택적이며, `apps/web/src/features/desktop/DesktopShell.tsx`에서 `InvFileExplorer`를 만들 때 `initialFiles`, `onVerifyIntegrity`, `onRepairReplicas`를 모두 전달하지 않는다. 따라서 현재 DesktopShell 경로에는 검증할 파일 데이터/실제 verifier가 없다. 화면의 `VERIFIED`를 파일 무결성 증거로 볼 수 없다.
2. WebCrypto가 없는 경우 `calculateSha256`는 64개의 0을 반환한다. 비교 자체는 하지만 입력 데이터와 무관한 상수 결과이며, 이 fallback을 암호학적 검증으로 표시해서는 안 된다.
3. `onRepairReplicas`가 없으면 `handleRepairReplicas`는 깨진 복제본을 healthy로 바꾼 합성 응답을 만든다. 이 경로는 서버나 복제본을 건드리지 않고 성공 UI를 만들 수 있다. 기존 성공/부분/실패 시험은 모두 명시적인 mock callback을 주므로 이 기본 경로를 검증하지 않는다.
4. Gemini의 보고된 비교·체크섬 부재·재검증 오류·복구 실패·부분 복구 mutation은 기존 mock-backed DOM 흐름을 보호한다. Codex가 직접 `isMatch = true` 변이를 넣었을 때 `[VF-GM-03-HASH-COMPARE]`가 예상한 TAMPERED badge 대신 VERIFIED를 받아 실패했다. 이는 callback 결과의 비교 UI를 보호한다. 기본 URI+hash 입력 경로, 실제 파일 byte source, callback 미제공 시 복구 경로의 안전성을 증명하지 않는다.

**필요한 인계:** 바이트를 반환하는 실제 storage adapter 또는 검증 책임 backend를 연결하고, checksum이 없거나 bytes/verifier가 없으면 `UNVERIFIED` 또는 명시적 오류로 종료해야 한다. 복구 callback이 없으면 성공을 만들지 말고 동작을 비활성화하거나 명시적 미연결 오류를 보여야 한다. callback 부재/실패와 기본 해시 경로를 직접 고정하는 시험이 필요하다.

### VF-GM-05 — PTY 티켓 UI 계약이 현재 backend와 불일치

`apps/web/src/features/terminal/WebTerminal.tsx` 및 `apps/web/src/shared/realtime/ws-terminal.ts`를 `services/control-plane/src/inv/app.py`, `services/control-plane/src/inv/terminal.py`, `contracts/v1alpha1/core.schema.json`과 대조했다.

- 프런트는 ticket 요청 본문으로 `{workspaceId, sessionId}`를 보낸다. canonical `TerminalTicketInput`은 `commandId`만 요구하고 추가 속성을 금지한다. 서버는 그 `commandId`를 승인된 실행·현재 run/attempt·node·lease·workspace와 결속해 검증한다. 현 프런트 요청은 입력 계약을 만족하지 않아 서버 코드상 거부된다.
- 프런트는 `{ticketId, ptyWsUrl}`를 기대하고 `ticketId`를 읽는다. backend 응답은 `{ticket, expiresAt, sessionId, websocketPath}`이다. 정상 canonical 응답을 받으면 프런트의 `ticket`은 undefined가 되어 연결 경로에서 오류가 난다.
- 프런트는 `/v1/terminal/ws`로 접속하고 `WsTerminalClient`가 ticket을 URL query에 붙인다. backend WebSocket 경로는 `/v1/workspaces/{workspace_id}/terminals/{session_id}`이고 query string을 거부하며 `inv-terminal-v1` subprotocol과 첫 프레임 `{ticket}`을 요구한다. 현재 프런트 client는 그 계약을 사용하지 않는다.
- `TerminalSessionView`는 노드 목록이 비어 있으면 `online`/`schedulable`인 가상 노드를 만들고 기본 활성 PTY 세션과 `WebTerminal`을 마운트한다. 이는 “안전한 빈 화면”이 아니라 존재하지 않는 노드/세션에서 ticket 발급을 시도하는 동작이다. 해당 테스트는 빈 노드 안내만 검사하고 ticket API 호출이 없음을 단언하지 않는다.
- backend `TerminalService._current`의 승인·주체·실행 상태·epoch·lease·노드 멤버십 검사는 소스에서 확인했다. 이 검토에서 live HTTP, 인증 principal, WebSocket 또는 실제 PTY를 실행하지 않았으며 서버 우회를 주장하지 않는다. 현재 근거는 구현 간 계약 불일치와 UI false affordance다.

Codex가 observation-only guard 조건을 `if (false)`로 변이하고 실행했을 때 `[VF-GM-05-OBSERVATION-GUARD]`는 오류 alert가 없다는 assertion에서 실패했다. 기존 시험은 그 특정 UI 가드를 보호한다. 이 변이는 API payload/schema 또는 backend WebSocket 호환성을 검사하지 않는다.

**필요한 인계:** 프런트 세션이 실제 승인된 `commandId`에서 시작하게 하고, 생성된 `TerminalTicketInput/Result` 계약과 server `websocketPath`를 그대로 소비해야 한다. WS client는 query token 대신 요구 subprotocol과 첫 ticket frame을 사용해야 한다. 빈 노드에서는 active PTY와 ticket 요청이 없어야 한다. 공유 계약 fixture 또는 mock adapter conformance 시험과 요청 호출 0회 단언을 추가해야 한다.

### VF-GM-04 — summary response에서 샤드/복제본 상태를 합성

`apps/web/src/shared/api/fabricObservation.ts`의 `model()`은 canonical `ModelCommitObservation`을 받는다. backend `services/control-plane/src/inv/model_view.py`도 manifest에서 `modelId`, `version`, `format`, `totalBytes`, `shardCount`, `committed`, `currentAvailability: "unknown"`, `requiresExecutionRevalidation: true` 등의 요약을 만든다. 샤드별 replica 목록은 반환하지 않는다.

반면 `apps/web/src/features/desktop/ModelStudioView.tsx`는 `result.shards`가 없으면 shard 목록을 만들고, 각 shard를 첫 cluster node의 `healthy` replica로 채우며 기본 `status: committed`, 합성 byte range/layers/hash를 지정한다. 즉 정상 canonical summary 응답만으로 화면에 검증되지 않은 replica 건강 및 shard metadata가 나타날 수 있다. 이는 “unknown availability / revalidation required”와 모순될 수 있다. `onRepairShard` 미제공 시에도 local simulation이 healthy replica를 반환한다.

기존 `model-studio-dom` 시험의 query mock은 shards 없는 summary를 반환하는데, 현재 assertions는 manifest article만 검사한다. 생성된 matrix가 미검증 상태임을 표시하는지 또는 없음을 표시하는지 단언하지 않는다. 이번 중간 깊이 검토에서 mutation을 직접 되살리지는 않았다.

**필요한 인계:** summary 계약과 실제 shard-location/replica observation을 구분해서 표현하고, 관측되지 않은 shard·replica를 만들지 않아야 한다. 실행 재검증 전에는 health 또는 committed status를 합성하지 않아야 한다. repair adapter가 없을 때 성공 시뮬레이션을 금지해야 한다.

### VF-GM-02 — 집중된 얕은 검토

`ResourceExplorer.tsx`의 후보 목록 기본값, 성공-empty 반영, error 상태의 카드/운영 버튼 차단, discovery 액션 및 storage/pool 오류 메시지 경로를 읽었다. 네 카드의 focused DOM test를 실행했다. 이 검토에서 별도 blocking defect를 찾지 않았지만, VF-GM-02 보고서의 모든 mutation이나 live resource API를 Codex가 재실행하지 않았으므로 exhaustive approval은 아니다.

## 검증 기록

- 기준 checkout: `C:/Project/SaintVision-Invion/.worktrees/codex-run-approval-observation-contract`; branch `agent/codex/ui-gm-review`. 최종 review 기준 integration은 `d0d41c30a0ee9a0106f89049654c8743c6cf030f`; 이는 d416fe5 이후 Claude의 문서 전용 커밋이다. UI 소스 변경은 없었다. 직접 mutation 대조는 그 직전 `d416fe50a2816cc3ad891d682f4e1e073a312f49`에서 수행했다.
- 초기 잘못된 invocation은 repository root에서 `npm --prefix apps/web exec vitest ...`를 실행해 Vite alias resolution 단계에서 3 suite가 import error를 냈다. 같은 코드를 `apps/web` cwd에서 다시 돌려 환경/작업 디렉터리 문제로 분리했다.
- Baseline command (cwd `apps/web`): `python ../../tools/provenance.py --executor Codex -- npm exec vitest -- run tests/inv-file-explorer-dom.test.tsx tests/terminal-session-dom.test.tsx tests/model-studio-dom.test.tsx tests/resource-explorer-dom.test.tsx`; exit 0, 4 files/44 tests passed. Provenance: Python `C:\Python314\python.exe` 3.14.6, Node v24.17.0, Windows 11, 2026-09-21 18:26 KST; PG DSN absent, Docker/Node present.
- Direct hash-comparison mutation: `InvFileExplorer.tsx` callback comparison replaced with `isMatch = true`; provenance-wrapped `[VF-GM-03-HASH-COMPARE]` run exited 1 at `tests/inv-file-explorer-dom.test.tsx:269`, received VERIFIED instead of expected TAMPERED. Reverted immediately.
- Direct PTY observation guard mutation: condition replaced with `if (false)`; provenance-wrapped `[VF-GM-05-OBSERVATION-GUARD]` run exited 1 at `tests/terminal-session-dom.test.tsx:327` because the alert was absent. Reverted immediately.
- After mutations, `git restore` returned both source files to HEAD and `git status --short` was empty.
- Claude 문서 전용 commit이 integration에 들어온 뒤 d0d41c3 기준으로 4개 DOM 파일을 재실행했다. `apps/web` cwd에서 4 files/44 tests passed (exit 0, 18:32:01 KST). 검사는 문서 편집이 있는 worktree에서 수행했지만 소스 파일은 HEAD와 동일했다.
- `check_docs.py`는 `.venv/Scripts/python.exe` 절대 경로로 exit 0, 626 versioned docs (18:32 KST); `check_ontology.py` 같은 interpreter로 exit 0 (RDF/SHACL 포함). `sync_obsidian.py --check`는 d416fe5 시점에 1418 managed / 5 pending / 0 conflicts로 exit 0; 이 review 문서 추가 이후 동기화 검사는 아직 재실행하지 않았다.
- 최종 clean documentation-review SHA `095d3151d8b2c2408f5dbea6b6e3d585c5374b3a`에서 provenance command를 재실행했다: 네 DOM 파일 44 passed, `check_docs.py` 626 versioned docs, `check_ontology.py` RDF/SHACL, 모두 exit 0 (18:33:32 KST). Obsidian read-only check는 1419 managed / 4 pending exports / 0 conflicts로 exit 0이며 쓰기는 하지 않았다. 이 SHA는 Codex 리뷰 문서 커밋을 포함하고 UI 소스는 바꾸지 않는다.
- No full Vitest, browser, live HTTP, authenticated backend, Docker, physical node, or PTY acceptance was performed for this review. Component DOM tests are not browser or operational acceptance.

## Next actions

1. Gemini: fix VF-GM-05 request/result/WebSocket contract and make empty-node state inert; add canonical contract tests. Re-review at a fixed integration SHA.
2. Gemini: remove VF-GM-03 fabricated digest and local repair success; wire actual content/verifier and repair boundary or render these operations unavailable. Add absent-adapter negative cases.
3. Gemini: make VF-GM-04 render only actual shard/replica observations; keep unknown availability explicitly unknown, and remove repair success simulation.
4. Gemini: confirm VF-GM-02 follow-up only if later UI changes touch its action/error guards. Browser acceptance remains a separate card for all four.

Codex owns this boundary review and the canonical contract findings. Gemini owns the screen/UI changes. This review does not edit screen code and does not claim another agent's approval.
