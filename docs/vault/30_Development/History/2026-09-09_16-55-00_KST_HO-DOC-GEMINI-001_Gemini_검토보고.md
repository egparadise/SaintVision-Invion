---
doc_id: "REVIEW-GEMINI-001"
title: "2026-09-09 HO-DOC-GEMINI-001 Gemini 교차 검토 보고"
version: "1.0.0"
status: "review"
author: "Gemini"
updated: "2026-09-09T16:55:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# HO-DOC-GEMINI-001 Gemini 교차 검토 보고

수신: Gemini (Antigravity) / 발신: Codex / 검토일: 2026-09-09 KST
base_sha: `b7767e13`
branch: `agent/gemini/HO-DOC-GEMINI-001`

읽은 문서와 버전: `GEMINI.md`, `AGENTS.md`, [[최종 개발 계획 - 모든 개발의 지침]] (GUIDE-001 v1.0.0), [[설계 충돌 정정 및 ADR]] (ADR-INDEX-001 v1.0.0), [[Agent 역할과 인계 계약]] (GOV-AGENT-001 v1.0.0), [[Git Build Obsidian 운영 절차]] (GOV-GIT-001 v1.0.0), [[Frontend 최종 개발 계획]] (PLAN-FRONTEND-001 v1.0.0), [[24주 통합 실행 계획]] (PLAN-ROADMAP-001 v1.0.0), [[공통 계약 요구사항과 완료 기준]], [[10_Frontend 보완 설계]] (60_Gaps/10), `docs/task-registry.json`, skills `agent-delivery` v1.0.0 / `frontend-delivery` v1.0.0.

범위: **디자인·Frontend·접근성·브라우저 검증·내부망 웹 배포**. (Backend 코어 동시성과 DB 분산 락은 Codex/Claude 소유이므로 프론트 연동 인터페이스에 한정하여 검토함).

---

## 1. 요약

Codex의 통합 기준선(PLAN-FRONTEND-001)과 Claude의 보완안(10_Frontend 보완 설계)은 기존의 미흡했던 웹 프론트엔드 방향을 SPA(React 19 + TypeScript + Vite + TanStack)로 현실화했다.

그러나 **프론트엔드 소유자(Gemini) 관점에서 실제 브라우저 런타임, 사용자 조작 안전성, 분산 상태 표시**를 정밀 분석한 결과, 아래와 같은 **핵심 보완 과제 7건 (FR-01 ~ FR-07)** 을 도출했다. 이 과제들을 해결하지 않으면 실장비 및 브라우저 E2E 환경에서 사용자 데이터 유실이나 보안 거버넌스 우회가 발생할 수 있다.

이 지적 사항들은 모두 신규 수립된 [[Gemini Frontend 상세 아키텍처 및 화면 명세]] (SPEC-FRONTEND-001)에 완전히 반영하여 해결책을 확정했다.

---

## 2. 기존 설계 검토 및 수용 사항

| 문서/항목 | 지적 및 제안 내용 | Gemini 판단 |
|---|---|---|
| ADR-001 / PLAN-FRONTEND | 11개 단일 실행 수명주기 상태 채택 | **전부 수용.** UI 필터 및 타임라인 컴포넌트에서 11개 상태(`draft` ~ `cancelled`)를 단일 Enum으로 엄격 바인딩함. |
| ADR-004 | W3C Trace Context (`traceparent`) 채택 | **전부 수용.** `X-Trace-Id` 단독 사용 대신 표준 W3C `traceparent`를 HTTP 헤더 및 에러 모달에 주입함. |
| 60_Gaps Frontend §2 | PTY는 WebSocket, Run 이벤트/로그는 SSE 이원화 | **전부 수용.** 양방향 제어(키보드/리사이즈)와 단방향 브로드캐스트의 물리적 특성에 정확히 부합함. |
| 60_Gaps Frontend §4 | 승인 화면 최우선 구현 및 안전 장치 | **전부 수용 및 강화.** One-time Nonce, 만료 카운트다운, 2인 승인 규칙, Diff 미로드 시 차단을 의무화함. |
| 60_Gaps Frontend §5 | 토큰 메모리 보관 + httpOnly 쿠키 | **전부 수용.** XSS 유출 방지를 위해 Access Token은 JS 메모리에만 두고 Refresh Token은 Secure 쿠키로 격리. |

---

## 3. Gemini 도출 프론트엔드 핵심 보완 과제 (FR-01 ~ FR-07)

### FR-01. 터미널 WebSocket 재연결 시 PTY 세션 및 스크롤백 복원 누락
- **문제**: 일시적인 네트워크 끊김이나 탭 새로고침 시 WebSocket이 닫히면 기존 터미널 화면이 백지화되고 실행 중인 명령의 출력을 잃어버린다.
- **해결 방안**: 터미널 백엔드 세션(`sid`)에 링버퍼 스크롤백 캐시(최근 5,000줄)를 보존하고, 프론트엔드가 재연결 쿼리 시 `lastSeq`를 전달하여 놓친 터미널 프레임을 xterm.js에 리플레이하도록 규약에 추가함.

### FR-02. Monaco 에디터 파일 편집 시 동시 수정 충돌 감지 부재
- **문제**: 워크스페이스 내 파일을 사용자가 Monaco 에디터로 편집 중 백그라운드 작업(Git checkout, Agent 코드 수정)이 일어날 경우, 브라우저 저장 시 최신 변경사항을 덮어써버린다.
- **해결 방안**: 파일 조회 응답에 `ETag`(SHA-256)를 포함하고, 저장 요청 시 `If-Match: {ETag}`를 전송하여 충돌 시 412 Precondition Failed와 함께 Monaco Diff 뷰어를 띄워 사용자가 병합하도록 설계함.

### FR-03. 브라우저 HTTP/1.1 환경에서 SSE 다중 연결 고갈
- **문제**: 사내 레거시 브라우저나 HTTP/1.1 프록시 환경에서는 도메인당 동시 연결 수가 6개로 제한된다. 여러 탭을 열거나 대시보드에서 다중 SSE를 열면 연결이 고갈되어 브라우저가 멈춘다.
- **해결 방안**: Nginx에서 `http2`를 의무 활성화하고, HTTP/1.1 환경 감지 시 상세 화면 1개만 SSE를 연결하며 목록 화면은 TanStack Query 5초 폴링으로 자동 다운그레이드하는 적응형 폴백 정책을 수립함.

### FR-04. Two-Person Rule 승인 시 클라이언트 자가 승인 방지 잠금
- **문제**: 2인 승인이 요구되는 고위험(L3) 작업에서 1차 승인자가 동일한 세션이나 브라우저에서 2차 승인 버튼을 연속 클릭할 수 있는 허점이 있었다.
- **해결 방안**: 승인 상세 페이로드에 `firstApprovedBy` 사용자 ID를 포함하고, 클라이언트 단에서 현재 로그인 사용자 ID와 일치할 경우 2차 승인 버튼을 완전 비활성화 및 안내 툴팁 표출 처리함.

### FR-05. 클라이언트 단 비밀 마스킹(Redaction) 심층 방어
- **문제**: 백엔드에서 비밀을 마스킹하더라도, 실시간 로그 스트림이나 프롬프트 뷰어에 개발용 토큰, AWS 키, Presigned URL 쿼리가 노출될 위험이 있다.
- **해결 방안**: DOM에 텍스트가 렌더링되거나 클립보드에 복사되기 직전 프론트엔드 유틸(`shared/utils/redact.ts`)에서 정규식 기반 2차 안전 마스킹(`***REDACTED***`)을 실행하도록 클라이언트 심층 방어를 구축함.

### FR-06. 10개 에러 코드군별 명확한 UI 행동 분기 정의
- **문제**: 백엔드 에러 코드(`VAL-*`, `AUTH-*`, `RES-*`, `BUDGET-*` 등)가 사용자에게 단순 텍스트로만 노출되면 사용자가 다음에 무엇을 해야 할지 알 수 없다.
- **해결 방안**: 각 에러 코드군마다 인라인 폼 에러, 권한 요청 모달, 대안 노드 제안 위젯, 카운트다운 재시도 배너 등 구체적인 UI 컴포넌트 매핑 테이블을 확정함.

### FR-07. 내부망 Nginx 프록시의 SSE 버퍼링 방지 및 초고속 롤백
- **문제**: 리버스 프록시 Nginx의 기본 설정은 응답을 버퍼링하므로 SSE 실시간 이벤트가 브라우저에 즉시 전달되지 않고 한꺼번에 쏟아진다.
- **해결 방안**: Nginx 설정에 `proxy_buffering off;`와 `chunked_transfer_encoding off;`를 명시하고, 배포 실패 시 10초 내에 이전 이미지 Digest로 복귀하는 `docker compose` 무중단 롤백 런북을 완성함.

---

## 4. 인계 및 다음 단계

1. **Codex에게 인계**:
   - 본 교차 검토 보고서와 [[Gemini Frontend 상세 아키텍처 및 화면 명세]]를 바탕으로 S01-FE의 승인을 요청함.
   - S01 공통 계약 및 장비 조사(S01-BE/DB/ST) 완료 시 프론트엔드 코드 부트스트랩(`apps/web`) 착수 준비 완료.
2. **Claude에게 공유**:
   - 에러 코드 포맷 및 W3C `traceparent` 헤더 스펙 정합성 확인 완료.
   - API 스키마(`OpenAPI / JSON Schema`) 파이프라인에서 TypeScript 타입 자동 생성이 제공되면 `apps/web/src/contracts/`로 즉시 연결 가능함을 통보.
