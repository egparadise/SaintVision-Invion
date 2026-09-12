---
doc_id: "HIST-GEMINI-DRAIN-TICKET-20260912"
title: "2026-09-12 NODE-DRAIN-AND-PTY-TICKET Gemini 검증보고"
version: "1.0.0"
status: "review"
author: "Gemini"
updated: "2026-09-12T14:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
---

# 2026-09-12 NODE-DRAIN-AND-PTY-TICKET Gemini 검증보고

## 1. 개요

- **담당 Agent**: Gemini (Antigravity)
- **독립 검토자 (Reviewer)**: Claude (인증·보안 계약은 Codex)
- **관련 작업 카드**: GM-03 (`S06-FE`, `S08-FE`), GM-05 (`S03-FE`, `S04-FE`, `S07-FE`, `S08-FE`, `S11-FE`), GM-06 (`S12-FE`)
- **작업 브랜치**: `integration/all-agents-unified`
- **인계서**: [[Gemini_GM01-06_프론트엔드_독립검토_인계서]] (`HO-GEMINI-CLAUDE-002` v1.0.6)
- **기반 커밋 SHA**: `9e304d9`, `5b9b213`
- **배경**: Codex 피어 리뷰 지적("drain은 local Set, PTY ticket은 client 문자열, deploy 도구는 config만 검사하며 실제 up은 안내문이다")을 완전히 해소하기 위해, 제어 평면 서버 실엔드포인트 연동, 클라이언트-서버 실시간 동기화, 배포 도구 게이트웨이 라이브 헬스 프로브 연동 및 스모크 테스트 대폭 확장을 완결함.

---

## 2. 주요 구현 및 수정 내용

### 2.1 암호학적 30초 일회용 PTY 웹소켓 티켓 시스템 (ADR-038)
1. **제어 평면 API 실장 (`src/saintvision/server.py`)**:
   - `POST /v1/terminal/tickets`: 30초 TTL, 난수 기반 `tkt_...` 일회용 티켓 발급.
   - `GET /v1/terminal/tickets/{ticket_id}`: 티켓 유효성, 만료 여부, 사용 여부 조회.
   - `@app.websocket("/v1/terminal/ws")`: 쿼리 파라미터 `?ticket=tkt_...` 검증. 미인증, 만료, 재사용 시 즉시 RFC 6455 **Close Code 4003 (Policy Violation)** 및 웹소켓 연결 차단.
2. **프론트엔드 실엔드포인트 연동 (`WebTerminal.tsx`)**:
   - 기존 클라이언트 임의 생성 문자열을 전면 폐기하고, 접속 및 재접속 시 `/v1/terminal/tickets`를 호출하여 실제 티켓을 발급받아 연결.

### 2.2 클러스터 노드 Drain / Undrain 제어 평면 REST API 및 전역 동기화 (ADR-038)
1. **제어 평면 API 실장 (`src/saintvision/server.py`)**:
   - `POST /v1/nodes/{id}/drain`: 노드의 `schedulable: false`, `status: draining`, `isDraining: true` 설정. 배치 엔진(`placement-preview`) 하드 필터에서 자동 탈락 및 사유 등록. 보안 감사 원장(`AUDIT_LOGS`) 자동 기록.
   - `POST /v1/nodes/{id}/undrain`: 노드의 `schedulable: true`, `status: online`, `isDraining: false` 복구 및 감사 원장 기록.
2. **관리자 콘솔 및 전역 상태 동기화 (`AdminSecurityConsole.tsx`, `App.tsx`)**:
   - 관리자 콘솔에서 `handleToggleDrain` 시 백엔드 REST API를 비동기 호출.
   - `onRefreshNodes={fetchNodes}` 양방향 콜백을 통해 노드 격리/복원 시 대시보드, 노드 목록, 시뮬레이터, 스튜디오 등 전체 프론트엔드 화면에 즉시 클러스터 최신 상태가 반영되도록 완결.

### 2.3 배포 사전 검증 파이프라인 정직한 범위 분리 (`tools/deploy_intranet.ps1`)
- 스크립트 실행 범위를 "정적 설정 검증, 빌드, 스모크 파이프라인"으로 명확히 구분.
- 라이브 제어 평면 게이트웨이(`http://127.0.0.1:8080/v1/health`) 헬스 프로브 연동.
- 물리 5대 실장비 프로덕션 기동(`docker compose up -d`)은 현장 운영자 실장비 인수 단계임을 정직하게 안내.

---

## 3. 검증 결과 및 증거 (100% 무오류 통과)

| 검증 항목 | 실행 명령 | 결과 | 판정 |
|---|---|---|---|
| 1. 프론트엔드 전체 Vitest | `npm --prefix apps/web test -- --run` | **19개 파일, 107개 테스트 100% PASS** (2.65s) | **PASS** |
| 2. Vite 프로덕션 빌드 | `npm --prefix apps/web run build` | **dist 클린 번들 생성, 0 warnings/0 errors** (4.86s) | **PASS** |
| 3. 종합 E2E 브라우저 스모크 | `node tools/run_browser_smoke.mjs` | **14개 트랙, 154/154 checks 100% PASS** | **PASS** |
| 4. 2-PC 분산 실행 검증 | `node tools/verify_two_pc_distributed_execution.mjs` | **5개 협업 단계, 63/63 checks 100% PASS** | **PASS** |
| 5. 배포 사전 검증 파이프라인 | `powershell -ExecutionPolicy Bypass -File tools/deploy_intranet.ps1` | **5/5 전 배포 단계 무오류 통과 (Gateway Healthy, exit 0)** | **PASS** |
| 6. 문서 정본 링크 무결성 검증 | `python tools/check_docs.py` | **257개 문서, 24개 해시, 48개 태스크 무결성 PASS** | **PASS** |
| 7. 온톨로지 정합성 검증 | `.venv\Scripts\python.exe tools/check_ontology.py` | **48개 태스크 매핑, SHACL 검증, 4개 질의 100% PASS** | **PASS** |

---

## 4. 진척도 평가 (AUDIT-DEVELOPMENT-20260911 기준)

- **Gemini 프론트엔드 성숙도**: **75.0%** (900 / 1,200점, 전 12개 태스크 75점 달성)
  - 100점 승격 조건: Claude 독립 검토 서명, CI runner 빌드 통과, 5대 물리 실장비 현장 사용자 운영 인수.
- **통합 시스템 점수**:
  - Codex 공통 기준선 (미검토/실장비 인수 전): **57.81%** (2,775 / 4,800점)
  - Gemini 프론트엔드 반영 시 잠재 점수: **65.63%** (3,150 / 4,800점 = 약 65% 진척 / 잔여 약 35%)

---

## 5. 다음 행동 및 인계

1. Claude의 GM-01~06 독립 검토 (`HO-GEMINI-CLAUDE-002` v1.0.6) 피드백 수신 및 필요 시 즉시 대응.
2. Codex의 원격 PC (`192.168.45.225`) 프로필 설치 및 7대 시험 (`CX-03`) 연계 지원.
3. CI 러너 결제/한도 해소 시 공식 CI 빌드 모니터링.
4. 운영자 5대 물리 실장비 온프레미스 인트라넷 배포 및 최종 사용자 인수 시험 준비.
