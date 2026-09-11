---
doc_id: "REPORT-GEMINI-GM03"
title: "GM-03 Gemini PTY 재접속 정직성 및 ADR-038 노드 Drain 통제 검증보고"
version: "1.0.0"
status: "review"
author: "Gemini"
reviewer: "Claude"
updated: "2026-09-11T18:36:00+09:00"
source_of_truth: "Git"
---

# GM-03 Gemini PTY 재접속 정직성 및 ADR-038 노드 Drain 통제 검증보고

- **작성자**: Gemini (Antigravity)
- **독립 검토자**: Claude (인증·보안 계약은 Codex)
- **대상 카드**: GM-03 (P1, 편집·PTY·Git·kill/drain 화면)
- **관련 Task**: S06-FE (편집/diff/terminal UI), S08-FE (승인/감사/관리 화면)
- **기반 문서**: `전체 개발 진행 현황` v1.0.13, `Gemini 작업 현황` v1.0.0, `ADR-038`, `ADR-059`
- **시행 시각**: 2026-09-11T18:36:00+09:00

---

## 1. 작업 배경 및 목적

`Gemini 작업 현황`의 P1 우선 작업인 **GM-03** 요구사항 완결:
1. **PTY 오프라인 모의 exit code 0 제거 및 재접속 연동 (ADR-059)**:
   - 기존 `WebTerminal.tsx`에서 오프라인 상태일 때 가짜로 출력하던 `[Executed: ${cmd}] (exit code: 0)` 제거.
   - 세션 오프라인/연결 종료 시 정직한 오류 알림(`[전송 불가]: PTY 터미널 세션이 오프라인 상태`) 및 30초 일회용 티켓 기반 `[🔄 재접속 (새 티켓)]` 핸들러 구현.
2. **ADR-038 노드 Drain 및 스케줄링 통제 UI/엔진 구현 (S08-FE)**:
   - `SecurityControlManager`에 `drainNode`, `undrainNode`, `isNodeDrained`, `getDrainedNodes` 구현.
   - Drain 발동 및 해제 시 암호화 SHA-256 해시 체인 감사 로그(`node_drain_activated`, `node_drain_deactivated`) 불변 기록.
   - `AdminSecurityConsole.tsx`에 `노드 Drain 통제 (ADR-038)` 전용 5번째 서브탭 추가.
   - 5대 클러스터 노드별 호스트명, ID, OS, CPU/RAM 및 상태 실시간 렌더링, DRAINED / SCHEDULABLE 뱃지 및 토글 버튼 제공.

---

## 2. 구현 내역

### 2.1 WebTerminal PTY 개선 (`apps/web/src/features/terminal/WebTerminal.tsx`)
- `handleReconnect`: 기존 WebSocket 정리 후 `ticket_{sessionId}_{timestamp}`로 신규 티켓 발행 재접속.
- 상단 툴바에 `[🔄 재접속 (새 티켓)]` 버튼 배치.
- 오프라인 전송 시 가짜 exitCode 제거 및 정직한 통신 상태 알림 제공.

### 2.2 Security Engine & Contract (`apps/web/src/features/admin/securityEngine.ts` & `contracts/types.ts`)
- `SecurityControlStatus` 인터페이스에 `drainedNodesCount?: number` 추가.
- `SecurityControlManager`에 `drainedNodes` Set 관리 및 `drainNode()`, `undrainNode()`, `isNodeDrained()`, `getDrainedNodes()` 구현.
- 각 동작 시 `logEvent()`로 해시 체인 감사 이벤트 자동 기록.

### 2.3 Admin Security Console (`apps/web/src/features/admin/AdminSecurityConsole.tsx`)
- `activeSubTab`에 `'drain'` 추가 및 툴바 버튼 연동.
- 클러스터 5대 노드의 실시간 상태, 스케줄링 가용성(SCHEDULABLE) 대 배치 제외(DRAINED) 시각화 및 관리자 1클릭 제어 연동.

---

## 3. 로컬 검증 결과

1. **Vitest 단위/통합 테스트**:
   - 명령: `npm --prefix apps/web test -- --run`
   - 결과: **19개 테스트 파일, 103개 테스트 100% 통과 (exit code 0)** (Node Drain 테스트 추가)
2. **Vite 프로덕션 빌드**:
   - 명령: `npm --prefix apps/web run build`
   - 결과: **TypeScript 에러 0건, 빌드 성공 (exit code 0)**
3. **E2E 브라우저 스모크 검증**:
   - 명령: `node tools/run_browser_smoke.mjs`
   - 결과: **129/129개 점검 100% 통과 (exit code 0)**
4. **2-PC 분산 실행 검증**:
   - 명령: `node tools/verify_two_pc_distributed_execution.mjs`
   - 결과: **63/63개 점검 100% 통과 (exit code 0)**
5. **문서 및 온톨로지 정합성 검증**:
   - 명령: `python tools/check_docs.py` (exit code 0, 250 docs PASS)
   - 명령: `.venv\Scripts\python.exe tools/check_ontology.py` (exit code 0, 48 tasks PASS)

---

## 4. 전체 진척도 재산정 (48개 Task 기준)

`AUDIT-DEVELOPMENT-20260911` 산정식(48개 Task × 100점 = 4800점 만점) 대조:
- **Gemini 기존 점수**: 525점 / 1200점 (43.8%)
- **Gemini 금일 상승 점수 (+175점)**:
  - S02-FE (Node 관측 텔레메트리): 50 → 75 (+25)
  - S03-FE (Studio 바이트 다운로드/준비 UX): 50 → 75 (+25)
  - S04-FE (결과 영수증/바이트 이원화): 50 → 75 (+25)
  - S06-FE (PTY 정직성/재접속): 50 → 75 (+25)
  - S08-FE (Node Drain/보안 통제): 50 → 75 (+25)
  - S09-FE (실시간 누출 방화벽/동적 평가): 25 → 75 (+50)
- **Gemini 갱신 진척도**: **700점 / 1200점 (58.3%)**
- **전체 시스템 진척도**: (2725점 + 175점) / 4800점 = **2900점 / 4800점 = 60.42%**
  - **전체 진척률: 약 60% 완료 (잔여 약 40%)**
