---
doc_id: "GEMINI-VF-BOUNDARY-REMEDIATION-001"
title: "VF-GM-03·04·05 Codex 경계 결함 치유, 미관측 상태 날조 배제 및 ModelCommitObservation 프론트 계약 결속 완결"
version: "1.0.0"
status: "approved"
author: "Gemini"
reviewer: "Codex"
frontend_owner: "Gemini"
updated: "2026-09-21T19:55:00+09:00"
timezone: "Asia/Seoul"
bound_at_sha: "2c473f4"
source_of_truth: "Git"
tags: ["boundary-review-fix", "zero-fabrication", "contract-binding", "pty", "integrity", "model-studio"]
---

# VF-GM-03·04·05 Codex 경계 지적 치유 및 ModelCommitObservation 계약 결속

Codex의 독립 경계 검토(`agent/codex/ui-gm-review`, 커밋 `cce4c20`, 문서 `2026-09-21_VF_GM02-05_Codex_boundary_review.md`)에서 지적된 3대 결함 형태(미관측 상태의 프론트엔드 임의 날조, 어댑터 부재 시 로컬 성공 시뮬레이션 조작, 계약-모의 드리프트)를 근원적으로 치유하고, Claude가 백엔드에서 결속한 `ModelCommitObservation` 공유 픽스처를 프론트엔드 Ajv 계약 시험으로 양방향 결속했다.

---

## 1. 3대 결함 형태 치유 구현 요약

### Priority 1 (VF-GM-05 PTY Protocol & TerminalSessionView)
1. **PTY 일회용 티켓 요청/응답 정합**:
   - `TerminalTicketInput`: strictly `{ commandId: UUID }` (`additionalProperties: false`). 기존의 임의 `{ workspaceId, sessionId }` 페이로드를 완전 제거하고 `commandId` 단일 페이로드로 전송.
   - `TerminalTicketResult`: `{ ticket, expiresAt, sessionId, websocketPath }` 수신 처리.
2. **WebSocket 연결 규격 정합**:
   - URL 쿼리 파라미터(`?ticket=...`) 완전 제거.
   - 서브프로토콜 `['inv-terminal-v1']` 명시.
   - 연결 직후(`ws.onopen`) 첫 번째 프레임으로 `{ ticket: oneTimeTicket }` 인증 JSON 전송.
3. **빈 노드 목록 가상화 방어 (Zero-Fabrication)**:
   - `nodes.length === 0`일 때 가상 노드(`fallbackNode: Node-01 (Virtual)`)를 합성하여 가상 PTY 세션을 띄우고 티켓 API를 무단 호출하던 동작을 전면 제거.
   - 노드 목록이 비어있을 경우 조기 반환하여 `data-testid="terminal-empty-nodes-notice"` / `data-testid="terminal-no-nodes-notice"` 안내 배너만 렌더링하고, 활성 터미널 세션 수 = 0, PTY 마운트 = 0, 티켓 API 호출 = 0을 보장.

### Priority 2 (VF-GM-03 InvFileExplorer Byte Verification & Repair Honesty)
1. **실제 바이트 기반 해시 검증**:
   - 기존의 `selectedFile.uri + selectedFile.contentHash` 순환 해싱을 전면 폐기.
   - `onVerifyIntegrity` 어댑터가 있으면 서버 실측 해시를 수신하고, 없을 경우 실제 파일 본문 바이트(`selectedFile.content`)가 존재할 때만 클라이언트 WebCrypto SHA-256을 계산.
   - 바이트 본문과 검증 어댑터가 둘 다 부재할 경우, 절대 임의 검증을 통과시키지 않고 즉시 `unverified` 상태 유지 및 명시적 거절 에러(`파일 본문 바이트(content) 또는 검증 어댑터가 부재하여 무결성을 검증할 수 없습니다.`) 표출.
2. **WebCrypto 부재 시 64개 0 반환 금지**:
   - `globalThis.crypto?.subtle?.digest` 미지원 환경에서 64개 `0`(`'000000...'`)을 유효 해시로 반환하던 결함을 제거하고 명시적 `Error('WebCrypto API가 지원되지 않아 무결성을 검증할 수 없습니다.')` 발생.
3. **복제본 복구 로컬 성공 시뮬레이션 제거**:
   - `onRepairReplicas` 어댑터가 없을 때 로컬에서 `healthy` 복제본을 합성해 성공 배너를 띄우던 시뮬레이션을 전면 제거.
   - 어댑터 부재 시 `repairError: '서버 복구 어댑터(onRepairReplicas)가 연결되지 않아 복구를 수행할 수 없습니다.'`를 `role="alert"`로 표출.

### Priority 3 (VF-GM-04 ModelStudio Summary Honesty & Repair Adapter)
1. **요약 관측치(`ModelCommitObservation`)로부터 샤드 날조 금지**:
   - `ModelCommitObservation` 응답(15개 필드 요약)에 `shards`가 없을 때 가상 샤드 ID, byteRange, 레이어, 정상 복제본을 합성하던 로직을 전면 제거.
   - `result.shards`가 존재하지 않을 경우 `modelManifest`를 null로 유지하고 `data-testid="unobserved-shards-notice"` 배너(`(개별 샤드 및 복제본 위치 관측 데이터가 없습니다. 실행 재검증 후 수집됩니다.)`) 표출.
2. **정직한 가용성 상태 표출**:
   - `result.currentAvailability === 'unknown'` 또는 `requiresExecutionRevalidation: true`일 때 기존의 `현재 가용성: 관측 완료 · 분산 패브릭 연동` 하드코딩 문구를 폐기하고 `현재 가용성: 알 수 없음 (unknown) · 실행 재검증 필요 (requiresExecutionRevalidation: true)`를 표출.
3. **샤드 복구 로컬 성공 시뮬레이션 제거**:
   - `onRepairShard` 어댑터 부재 시 로컬에서 복제본을 정상으로 둔갑시키던 시뮬레이션을 전면 제거하고 `error: '서버 샤드 복구 어댑터(onRepairShard)가 연결되지 않아 복구를 수행할 수 없습니다.'` 경고 표출.

### 타입 정합 및 계약 결속
- `apps/web/src/contracts/types.ts`: `RunLogView`, `RunAttemptObservation`, `RunAttemptList`, `TerminalTicketInput`, `TerminalTicketResult`를 생성 타입(`packages/contracts-ts/src/index`)으로부터 직접 import & re-export하여 수기 드리프트를 근원적으로 제거.
- `apps/web/tests/model-commit-observation-contract.test.ts` 신설: Claude가 커널 계약에 결속한 `model-commit-observation-response.json` 픽스처를 프론트엔드 Ajv 2020으로 검증하고 `fabricObservation.model`의 런타임 가드 5건을 실측 검증.

---

## 2. 3대 보고 범주 (Partitions)

### (1) 실측 돌연변이 사살 및 단언 오류 문구 (Measured Mutation Failures)

#### Mutation 1: TerminalSessionView 빈 노드 시 PTY 조기 반환 가드 무력화
- **변형 내용**: `if (!nodes || nodes.length === 0)` 가드를 주석 처리하여 빈 노드일 때도 기본 가상 노드로 세션을 생성하고 `WebTerminal`을 마운트하도록 변형.
- **포착 시험**: `tests/terminal-session-dom.test.tsx > [VF-GM-05-EMPTY-NODES]`
- **실측 단언 오류**:
  ```text
  AssertionError: expected "spy" to not have been called, but called 1 times
  ❯ tests/terminal-session-dom.test.tsx:463:23
     461|     // Invariant: empty nodes MUST NOT mount active terminal or make ticket API calls
     462|     expect(container.querySelector('[data-testid="active-terminal-container"]')).toBeNull();
     463|     expect(apiSpy).not.toHaveBeenCalled();
  ```
- **결과**: **KILLED** (빈 노드 배열 전달 시 티켓 발급 API 0회 호출 불변식 증명 완료).

#### Mutation 2: InvFileExplorer 바이트 부재 시 미검증 거절을 허위 verified로 변조
- **변형 내용**: `InvFileExplorer.tsx`의 `handleVerifyIntegrity`에서 바이트 및 어댑터 부재 시 `status: 'unverified'` 대신 `status: 'verified'`로 조작.
- **포착 시험**: `tests/inv-file-explorer-dom.test.tsx > [VF-GM-03-ABSENT-BYTES-REFUSAL]`
- **실측 단언 오류**:
  ```text
  AssertionError: expected '검증 통과 (VERIFIED)' to be '미검증 (UNVERIFIED)'
  - Expected: "미검증 (UNVERIFIED)"
  + Received: "검증 통과 (VERIFIED)"
  ❯ tests/inv-file-explorer-dom.test.tsx:611:26
  ```
- **결과**: **KILLED** (본문 바이트나 검증 어댑터 없이는 절대 verified로 전이되지 않음을 증명).

#### Mutation 3: InvFileExplorer WebCrypto 부재 시 64개 0 반환 복원
- **변형 내용**: `calculateSha256`에서 에러 throw 대신 `'0'.repeat(64)` 반환으로 복원.
- **포착 시험**: `tests/inv-file-explorer-dom.test.tsx > [VF-GM-03-WEBCRYPTO-ABSENT]`
- **실측 단언 오류**:
  ```text
  AssertionError: expected promise to be rejected with 'WebCrypto API가 지원되지 않아 무결성을 검증할 수 없습니다.', but resolved to '0000000000000000000000000000000000000000000000000000000000000000'
  ❯ tests/inv-file-explorer-dom.test.tsx:694:7
  ```
- **결과**: **KILLED** (가상 해시 조작 차단 및 엄격한 예외 발생 증명).

#### Mutation 4: ModelStudioView 요약 관측 시 unknown 가용성 대신 허위 관측 완료 표출
- **변형 내용**: `currentAvailability === 'unknown'` 조건 분기를 무시하고 `'현재 가용성: 관측 완료 · 분산 패브릭 연동'`을 무조건 렌더링.
- **포착 시험**: `tests/model-studio-dom.test.tsx > [VF-GM-04-SUMMARY-HONESTY]`
- **실측 단언 오류**:
  ```text
  AssertionError: expected '현재 가용성: 관측 완료 · 분산 패브릭 연동' to include '알 수 없음 (unknown)'
  ❯ tests/model-studio-dom.test.tsx:516:30
     515|     expect(availStatus).not.toBeNull();
     516|     expect(availStatus?.textContent).toContain('알 수 없음 (unknown)');
  ```
- **결과**: **KILLED** (커널 요약 응답의 unknown 가용성이 화면에 정직하게 반영됨을 증명).

#### Mutation 5: ModelStudioView 샤드 복구 어댑터 부재 시 성공 시뮬레이션 복원
- **변형 내용**: `handleRepairShard`에서 `!onRepairShard` 가드를 제거하고 로컬 성공 시뮬레이션을 다시 실행.
- **포착 시험**: `tests/model-studio-dom.test.tsx > [VF-GM-04-ABSENT-REPAIR-ADAPTER]`
- **실측 단언 오류**:
  ```text
  AssertionError: expected null not to be null
  ❯ tests/model-studio-dom.test.tsx:551:28
     550|     const repairError = container.querySelector('[data-testid="shard-repair-error"]');
     551|     expect(repairError).not.toBeNull();
  ```
- **결과**: **KILLED** (어댑터 부재 시 가짜 복구 성공 조작 원천 차단 증명).

---

### (2) 소스 판독 분석 (Source-Read Analysis)

1. **`services/control-plane/src/inv/terminal.py:105-145` 및 `core.schema.json#/$defs/TerminalTicketInput`**:
   - `TerminalTicketInput`은 스키마 상 `required: ["commandId"]`, `additionalProperties: false`로 못 박혀 있음.
   - `TerminalTicketResult`는 `required: ["ticket", "expiresAt", "sessionId", "websocketPath"]`이며, `ticket`은 64자리 hex 문자열임.
   - `services/control-plane/src/inv/app.py:566-615`의 WebSocket 핸들러는 쿼리스트링 존재 시 즉시 4403으로 종료하며, `subprotocols=["inv-terminal-v1"]` 협상 및 첫 프레임 200바이트 이하의 strict JSON `{"ticket": "..."}` 인증을 요구함.
   - 프론트엔드의 `ws-terminal.ts` 및 `WebTerminal.tsx`가 이 제어 평면 커널 규약에 100% 일치하도록 재배선됨.
2. **`services/control-plane/src/inv/model_view.py:56` 및 `ModelCommitObservation`**:
   - `/v1/projects/{p}/models/{m}/versions/{v}/commitment` 엔드포인트는 `validate_contract("ModelCommitObservation", result)`를 통과한 15개 필드 메타데이터만 반환함.
   - 이 응답에는 `shards` 필드가 일체 없으며, `currentAvailability: "unknown"`, `requiresExecutionRevalidation: true`가 load-bearing 상수로 박혀 있음.
   - `ModelStudioView.tsx`가 이 사실을 정직하게 수용하여, `shards`가 없을 때는 샤드 매트릭스를 표출하지 않고 `(개별 샤드 및 복제본 위치 관측 데이터가 없습니다. 실행 재검증 후 수집됩니다.)` 안내 배너만 렌더링하도록 정정됨.

---

### (3) 미검증/유예된 불변식 (Unverified/Deferred Invariants)

1. **실제 커널 PTY 양방향 바이트 스트리밍**:
   - 로컬 테스트 환경에서는 happy-dom 및 `MockWebSocket`을 통해 프로토콜 준수(서브프로토콜, 첫 인증 프레임, 시퀀스 번호 증분, 티켓 페이로드)를 단언함.
   - 실제 Linux/Windows 호스트 상의 OS PTY 데몬 프로세스 스폰 및 xterm.js 렌더링은 Docker Host / Node-Agent가 가동되는 E2E 환경에서 검증됨.
2. **WebCrypto 하드웨어 가속**:
   - 브라우저 표준 `crypto.subtle.digest`를 호출함을 확인하였으나, 초당 수 기가바이트 대용량 모델 파일의 스트리밍 해싱 성능은 브라우저 실제 환경에서 실측되어야 함.

---

## 3. 종합 검증 수치 및 빌드 결과

- **Vitest**: **52개 파일 475 passed 100%**
  - 진행 경과: **from 464 to 475 (net +11 tests 순증)**
    - `tests/terminal-session-dom.test.tsx`: 10 passed (PTY 티켓/웹소켓 규격, 빈 노드 0회 호출 가드)
    - `tests/inv-file-explorer-dom.test.tsx`: 10 -> 14 passed (+4 tests: 바이트 부재 거절, 본문 바이트 실측 해싱, 복구 어댑터 부재 거절, WebCrypto 부재 예외)
    - `tests/model-studio-dom.test.tsx`: 10 -> 12 passed (+2 tests: 요약 관측치 미관측 샤드 정직 표출, 샤드 복구 어댑터 부재 거절)
    - `tests/model-commit-observation-contract.test.ts`: 5 passed (신규 파일: Ajv 스키마 검증, 필드 누락/enum 거절, fabricObservation 런타임 가드 5건)
    - `tests/ws-terminal.test.ts`: 3 passed (서브프로토콜 및 첫 인증 프레임 정합)
    - `tests/desktop-layout.test.tsx`: 16 passed (데스크톱 윈도우 마운트 검증)
- **Production Web Build (`tsc -b && vite build`)**: **exit code 0 in 3.41s** (93 modules transformed, 0 lint/type errors).
- **Pytest Contract Tests**: **11 passed in 0.58s** (`test_model_commit_observation_contract.py`, `test_run_result_contract.py`, `test_run_attempt_contract.py`).
- **문서 및 온톨로지 정합성**:
  - `python tools/check_docs.py`: **PASS** (629 versioned documents, 24 original hashes, 48 tasks, 12 outcomes, DAG 유효)
  - `python tools/check_ontology.py`: **PASS** (RDF/SHACL 검사, 48 task mappings, 4 competency queries 통과)
  - `python tools/sync_obsidian.py --check`: **PASS** (1422 managed files, 0 conflicts)
