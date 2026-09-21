---
doc_id: "VF-GM05-TERMINAL-IDE-SESSION-PTY-GEMINI-001"
title: "VF-GM-05 Terminal & Virtual IDE 세션 UX, 노드별 PowerShell/Bash 자동 매핑, 30초 PTY 티켓 격리 및 접근성 실증 보고"
version: "1.0.0"
status: "verified"
author: "Gemini"
reviewer: "Codex"
updated: "2026-09-21T18:12:00+09:00"
code_ref_tip: "integration/all-agents-unified"
source_of_truth: "Git"
tags: ["vf-gm-05", "terminal-ide-session", "pty-ticket", "powershell-bash-mapping", "monaco-workspace-editor", "observation-node-exclusion", "mutation-testing"]
---

# VF-GM-05 Terminal & Virtual IDE 세션 UX, 노드별 PowerShell/Bash 자동 매핑, 30초 PTY 티켓 격리 및 접근성 실증 보고

## 1. 개요 및 목적

사용자 기승인 트랙 지침에 따라 `VF-GM-04` (Model Studio) 완결 직후 차기 준비 완료 카드인 **`VF-GM-05` (Terminal/IDE/PowerShell/Bash session UX)**로 즉시 전환하여 구현 및 실증을 완결하였다.

본 작업의 핵심 목표:
1. **노드 OS 기반 PowerShell/Bash 자동 매핑**: 대상 노드의 운영체제(`node.os`)에 따라 Windows 노드는 `powershell`, Linux 노드는 `bash`로 자동 쉘 타입을 분기하고 헤더 및 탭 아이콘에 명시.
2. **30초 암호학적 일회용 PTY 티켓 격리 및 정직한 오류 알림**: 제어 평면(`/v1/workspaces/${workspaceId}/terminal-tickets`)을 통한 일회용 티켓 발급, 티켓 만료/권한 거부(401/403/500) 시 숨김 없는 `role="alert"` (`data-testid="terminal-error-alert"`) 표출 및 원클릭 재시도 제공.
3. **오프라인 상태 명령 전송 거절 방어 (Zero-Mock)**: PTY 세션 미연결/오프라인 상태에서 사용자가 명령을 전송할 경우 허위 종료 코드(exit 0)를 조작하지 않고 `role="alert"` (`data-testid="terminal-disconnected-cmd-alert"`) 경고 배너 표출.
4. **관측 전용 노드(Node-04) 대화형 PTY 세션 실행 원천 차단 (ADR-028 & ADR-041)**: `observationOnly: true` 또는 `schedulable: false` 노드의 세션 생성 옵션을 `disabled` 처리하고, 강제 생성 시도 시 `role="alert"` (`data-testid="terminal-session-error-alert"`) 표출.
5. **터미널 <-> Monaco IDE 모드 전환**: `data-testid="switch-mode-btn"`을 통한 PTY 터미널(`WebTerminal`)과 가상 IDE(`MonacoWorkspaceEditor`) 간 매끄러운 탭 모드 전환 지원.
6. **접근성(A11y) 강화 (WCAG AA 대응)**: 스크린리더 사용자를 위한 순수 텍스트 대체 로그 뷰(`role="region"`, `aria-label="텍스트 로그 대체 뷰"`), `role="tablist"` / `role="tab"` 내비게이션, 안전한 빈 노드 폴백 제공.

---

## 2. 세 가지 구분 원칙에 입각한 실측 현황 분석

| 구분 범주 | 구체적 검증 내용 및 실측 결과 |
|---|---|
| **1. 돌연변이로 실측해 깨진 것 (Measured Mutation Failures)** | • **Mutation 1 (관측 전용 Node-04 PTY 세션 생성 차단 가드 우회 및 false 강제 변조)**: `TerminalSessionView.tsx`에서 관측 전용 검사를 `if (false)`로 무력화했을 때, `[VF-GM-05-OBSERVATION-GUARD]` 시험에서 즉시 실패 포착.<br>&nbsp;&nbsp;`AssertionError: expected null not to be null`<br>&nbsp;&nbsp;`at tests/terminal-session-dom.test.tsx:327:30` (`expect(sessionAlert).not.toBeNull()`)<br>• **Mutation 2 (티켓 발급 실패 시 role="alert" 경고 배너 렌더링 억제 변조)**: `WebTerminal.tsx`에서 `connectionStatus === 'error'` 배너 렌더링을 `{false && ...}`로 우회했을 때, `[VF-GM-05-TICKET-RETRY]` 시험에서 즉시 실패 포착.<br>&nbsp;&nbsp;`AssertionError: expected null not to be null`<br>&nbsp;&nbsp;`at tests/terminal-session-dom.test.tsx:199:28` (`expect(errorAlert).not.toBeNull()`)<br>• **Mutation 3 (오프라인 상태 명령 전송 시 거절 알림 생략 변조)**: `WebTerminal.tsx`에서 `setDisconnectedCmdAlert`를 주석 처리했을 때, `[VF-GM-05-OFFLINE-REJECTION]` 시험에서 즉시 실패 포착.<br>&nbsp;&nbsp;`AssertionError: expected null not to be null`<br>&nbsp;&nbsp;`at tests/terminal-session-dom.test.tsx:253:26` (`expect(cmdAlert).not.toBeNull()`)<br>• **Mutation 4 (Linux 노드에 Bash 대신 PowerShell 강제 할당 변조)**: `TerminalSessionView.tsx`에서 노드 OS 무관하게 `shellType = 'powershell'`로 하드코딩했을 때, `[VF-GM-05-TAB-LIFECYCLE]` 시험에서 즉시 실패 포착.<br>&nbsp;&nbsp;`AssertionError: expected 'POWERSHELL' to be 'BASH' // Object.is equality`<br>&nbsp;&nbsp;`Expected: "BASH", Received: "POWERSHELL"`<br>&nbsp;&nbsp;`at tests/terminal-session-dom.test.tsx:400:41` (`expect(shellTypeBadge?.textContent).toBe('BASH')`) |
| **2. 소스를 읽어 판단한 것 (Source-Read Analysis)** | • `DesktopShell.tsx`에서 단순 `WebTerminal` 직결 렌더링을 다중 탭 및 노드 매핑이 통합된 `TerminalSessionView`로 승격하여 데스크톱 셸 창에서 터미널/IDE 풀 기능을 제공하도록 결속함.<br>• `nodes` 배열이 비어있는 상태에서도 `renderToStaticMarkup`이 크래시되지 않도록 완전한 `NodeItem` 속성을 갖춘 가상 기본 노드(`fallbackNode`)를 공급함과 동시에 `data-testid="terminal-empty-nodes-notice"` 고지 배너를 표시하도록 정합함.<br>• `WebTerminal.tsx`의 30초 일회용 PTY 티켓 발급 및 재연결 로직에 암호학적 mTLS 격리 배지를 추가하고 접근성 텍스트 뷰 전환 시 WCAG AA 기준을 충족함을 확인. |
| **3. 아직 확인 못 한 것 (Unverified / Deferred Invariants)** | • 실제 물리 Linux 노드의 PTY 디바이스(`/dev/pts/*`) 및 Windows ConPTY 가상 터미널 프로세스 실물 생성.<br>• 고속 네트워크 패킷 유실 시 TCP 윈도우 재전송 및 WebSocket 프로토콜 프레임 분할.<br>• 상기 커널 PTY 데몬 및 물리 소켓 동작은 백엔드 에이전트 및 브라우저 E2E 인수 레인으로 이관함. |

---

## 3. 검증 결과 및 회귀 시험 지표

### 3.1 테스트 카운트 증가 보고 (기준선 명시)
- **`apps/web/tests/terminal-session-dom.test.tsx` 신규 생성**: **10 tests 100% PASS**
  1. `[VF-GM-05-INIT-SESSION] renders initial tabs and accurately maps node OS to shell type (Catches Mutation 4)`
  2. `[VF-GM-05-TICKET-CONNECT] requests 30s one-time PTY ticket and establishes connected WebSocket state`
  3. `[VF-GM-05-TICKET-RETRY] surfaces honest role="alert" when ticket issuance fails and allows retry (Catches Mutation 2)`
  4. `[VF-GM-05-OFFLINE-REJECTION] rejects terminal command with role="alert" when disconnected without fake exit codes (Catches Mutation 3)`
  5. `[VF-GM-05-A11Y-VIEW] toggles accessible screen-reader text log view with role="region"`
  6. `[VF-GM-05-OBSERVATION-GUARD] disables observation-only Node-04 and rejects PTY session creation (Catches Mutation 1)`
  7. `[VF-GM-05-SWITCH-IDE] toggles active session between PTY terminal mode and Monaco IDE editor mode`
  8. `[VF-GM-05-TAB-LIFECYCLE] creates a new Linux Bash session tab, switches between tabs, and closes tabs`
  9. `[VF-GM-05-EMPTY-NODES] renders safe empty fallback when cluster nodes array is empty`
  10. `[VF-GM-05-RECONNECT-PTY] reconnect button issues fresh 30s ticket and restores connected status`
- **전체 Vitest 스위트**: 직전 보고 기준 **43개 파일 399 passed**에서 **44개 파일 409 passed**로 순증 (**from 399 to 409, net +10 tests**, 44개 테스트 파일 100% 합격).

### 3.2 빌드 및 거버넌스 도구 전수 합격 증거
- **웹 프로덕션 빌드 (`tsc -b && vite build`)**: Exit Code `0`, 91개 모듈 번들링 완료 (3.78s).
- **문서 무결성 검증 (`python tools/check_docs.py`)**: Exit Code `0` (PASS: 24 original hashes, 619 versioned documents, wiki links, 48 tasks, 12 outcomes, owner/reviewer/skills, dependency DAG).
- **온톨로지 검증 (`python tools/check_ontology.py`)**: Exit Code `0` (PASS: RDF parsing, defined terms, TTL/JSON-LD equivalence, 48 task mappings, positive SHACL, 4 rejected invalid fixtures, 4 competency queries, Obsidian mirrors).
- **옵시디언 동기화 검사 (`python tools/sync_obsidian.py --check`)**: Exit Code `0` (CHECK: 1411 managed files, 0 conflicts).

---

## 4. 이어서 할 다음 작업 (Next Action)

- **다음 담당**: Gemini (Antigravity)
- **다음 작업 카드**: **`VF-GM-06` (외부 HTTPS, Browser Matrix, Rollback & Real-Browser Acceptance)**
  - Nginx TLS 1.3 / 외부 HTTPS 리버스 프록시 연동 및 배포 스크립트 검증.
  - 브라우저 스모크 러너 및 웹 롤백 엔진 무결성 검증.
  - 단일 가상 컴퓨터 최종 브라우저 인수 보고서 작성.
