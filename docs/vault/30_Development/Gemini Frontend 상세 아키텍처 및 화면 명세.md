---
doc_id: "SPEC-FRONTEND-001"
title: "Gemini Frontend 상세 아키텍처 및 화면 명세"
version: "1.0.0"
status: "review"
author: "Gemini"
updated: "2026-09-09T16:55:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "frontend", "design-tokens", "s01-fe"]
---

# Gemini Frontend 상세 아키텍처 및 화면 명세

이 문서는 SaintVision-Invion의 **Frontend·디자인·웹 배포 소유자인 Gemini(Antigravity)** 가 수립한 프론트엔드 상세 아키텍처와 전체 화면 상태 명세다. [[최종 개발 계획 - 모든 개발의 지침]], [[Frontend 최종 개발 계획]], [[공통 계약 요구사항과 완료 기준]]을 기반으로 하며, S01-FE의 완료 기준(AC-01)을 만족한다.

---

## 1. 프론트엔드 기술 스택 및 구조

### 1.1 기술 스택

| 계층 | 기술 | 역할 및 선정 근거 |
|---|---|---|
| 프레임워크 | React 19 + TypeScript (strict) | 컴포넌트 모델, 기존 사내 검증 스택 정합성 |
| 빌드 및 번들러 | Vite 6 | 빠른 HMR, Rollup 기반 최적화 프로덕션 번들 |
| 라우팅 | TanStack Router | 완전 타입 안전 라우팅, 검색 파라미터 및 경로 파라미터 검증 |
| 서버 상태 | TanStack Query v5 | 캐싱, 윈도우 포커스 리페치, SSE 연동 무효화, 백그라운드 폴링 폴백 |
| 클라이언트 상태 | Zustand v5 | 터미널 탭/세션, 레이아웃 분할비율, 테마, 임시 폼 드래프트 |
| 터미널 렌더러 | xterm.js 5.x + FitAddon + WebLinksAddon | 고성능 PTY 스트리밍 렌더링 |
| 코드 편집기 | Monaco Editor | 워크스페이스 파일 편집 및 변경 diff 렌더링 |
| 폼 및 유효성 검증 | React Hook Form + Zod | JSON Schema 계약 기반 Zod 스키마로 백엔드와 검증 일치 |
| 스타일링 | Tailwind CSS v4 + CSS Custom Properties | 디자인 토큰 기반 라이트/다크 테마 |
| 단위/컴포넌트 테스트 | Vitest + Testing Library | 상태 전이, 훅, 폼 분기, 이벤트 링버퍼 단위 검증 |
| E2E/시각 테스트 | Playwright | 로컬 Compose 풀스택 기반 종단간 시나리오 및 테마 스냅샷 검증 |

### 1.2 디렉터리 아키텍처 (`apps/web`)

```
apps/web/
├── public/
│   ├── favicon.ico
│   └── locales/               # 다국어 JSON (ko, en)
│       ├── ko/
│       └── en/
├── src/
│   ├── app/                   # Provider 래퍼, 전역 설정
│   │   ├── App.tsx
│   │   ├── router.tsx
│   │   └── query-client.ts
│   ├── contracts/             # JSON Schema에서 자동 생성된 TS 타입 (수정 금지)
│   │   ├── api.generated.ts
│   │   └── events.generated.ts
│   ├── features/              # 기능 도메인별 분리
│   │   ├── auth/              # OIDC PKCE, 세션 상태, 401 인터셉터
│   │   ├── nodes/             # 노드 인벤토리, Capability, 상태 상세
│   │   ├── projects/          # 프로젝트 및 워크스페이스 관리
│   │   ├── workspaces/        # Monaco 파일 에디터, diff
│   │   ├── terminal/          # xterm.js, WebSocket PTY 세션
│   │   ├── runs/              # Run 목록, 4개 탭 상세(타임라인/로그/Artifact/Explain)
│   │   ├── approvals/         # 승인 대기/상세, diff, 카운트다운, Two-Person 룰
│   │   ├── audit/             # 불변 감사 로그 조회
│   │   └── settings/          # AI 도구 및 시스템 설정
│   ├── shared/
│   │   ├── api/               # fetch 래퍼, W3C traceparent 주입, 에러 파싱
│   │   ├── realtime/          # SSE 링버퍼 클라이언트, WS 티켓 관리자
│   │   ├── tokens/            # 디자인 토큰 CSS 변수 맵
│   │   ├── ui/                # 디자인 시스템 공통 컴포넌트
│   │   │   ├── Button.tsx
│   │   │   ├── Modal.tsx
│   │   │   ├── Skeleton.tsx
│   │   │   ├── ErrorState.tsx
│   │   │   ├── EmptyState.tsx
│   │   │   └── RiskBadge.tsx
│   │   └── utils/             # 날짜(UTC→로컬), 포맷팅, 안전 마스킹
│   ├── main.tsx
│   └── index.css              # 디자인 토큰 CSS 변수 선언
├── nginx.conf                 # 프로덕션 내부망 리버스 프록시 설정
├── Dockerfile                 # 멀티스테이지 정적 SPA 빌드 이미지
└── vite.config.ts
```

---

## 2. 디자인 토큰 시스템 (Design Tokens)

CSS 커스텀 프로퍼티를 원천으로 하며, 의미 기반(semantic) 네이밍과 라이트/다크 모드, 색각 이상 대응 이중 코딩(색상 + 아이콘/텍스트)을 의무화한다.

### 2.1 색상 및 테마 토큰

```css
:root {
  /* Surface & Background */
  --color-bg-canvas: #f8fafc;
  --color-bg-surface: #ffffff;
  --color-bg-subtle: #f1f5f9;
  --color-border-subtle: #e2e8f0;
  --color-border-strong: #cbd5e1;

  /* Typography */
  --color-text-primary: #0f172a;
  --color-text-secondary: #475569;
  --color-text-muted: #64748b;
  --color-text-inverse: #ffffff;

  /* Primary Brand */
  --color-brand-primary: #2563eb;
  --color-brand-hover: #1d4ed8;
  --color-brand-subtle: #dbeafe;

  /* Status Colors */
  --color-status-online: #16a34a;
  --color-status-degraded: #d97706;
  --color-status-offline: #dc2626;
  --color-status-neutral: #64748b;

  /* Risk Grades (L0~L3) */
  --color-risk-l0: #059669; /* 조회·읽기 전용 */
  --color-risk-l1: #2563eb; /* 격리 쓰기 */
  --color-risk-l2: #d97706; /* 외부 영향 가능 */
  --color-risk-l3: #dc2626; /* 인프라·보안 경계 위험 */

  /* Spacing & Radius */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-6: 1.5rem;
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
}

[data-theme='dark'] {
  --color-bg-canvas: #090d16;
  --color-bg-surface: #111827;
  --color-bg-subtle: #1f2937;
  --color-border-subtle: #374151;
  --color-border-strong: #4b5563;

  --color-text-primary: #f9fafb;
  --color-text-secondary: #e5e7eb;
  --color-text-muted: #9ca3af;
  --color-text-inverse: #0f172a;

  --color-brand-primary: #3b82f6;
  --color-brand-hover: #60a5fa;
  --color-brand-subtle: #1e293b;

  --color-status-online: #22c55e;
  --color-status-degraded: #f59e0b;
  --color-status-offline: #ef4444;
  --color-status-neutral: #9ca3af;

  --color-risk-l0: #10b981;
  --color-risk-l1: #3b82f6;
  --color-risk-l2: #f59e0b;
  --color-risk-l3: #ef4444;
}
```

### 2.2 위험 등급(Risk Level) 및 색각 이상 대응

위험 등급은 단순 배경색으로만 식별하지 않고, 반드시 **아이콘 + 텍스트 라벨 + WCAG AA(4.5:1 이상) 명도 대비**를 결합한다:
- **L0 (안전)**: `[아이콘: 방패 체크]` + "L0 · 읽기 전용"
- **L1 (경미)**: `[아이콘: 정보 원]` + "L1 · 격리 실행"
- **L2 (주의)**: `[아이콘: 경고 삼각]` + "L2 · 승인 필요 (단일 승인)"
- **L3 (위험)**: `[아이콘: 위험 팔각]` + "L3 · 고위험 (2인 승인/기본 차단)"

---

## 3. 전체 13개 화면 및 상태 명세

### 3.1 공통 5대 화면 상태 규약

모든 화면 컴포넌트는 단일 정상 화면뿐만 아니라 아래 5개 상태를 명시적으로 분기 구현한다.
1. **Loading (로딩)**: 전면 블로킹 스피너 금지. 해당 화면 레이아웃에 맞춘 Skeleton UI를 제공한다.
2. **Empty (빈 상태)**: 빈 테이블/공백 화면 금지. 왜 비어 있는지와 사용자가 즉각 취할 수 있는 Action Button(CTA)을 배치한다 (예: Node 0대 → "Node Agent 설치 가이드" 모달 링크).
3. **Error (오류)**: 원인을 알 수 없는 흰 화면이나 모호한 메시지 금지. 안전한 사용자 메시지 + 내부 에러 코드 (`RES-0003` 등) + W3C `traceId` + [오류 복사] 버튼을 제공한다.
4. **Forbidden (권한 없음, 403)**: 빈 목록으로 속이지 않고, 해당 기능을 위해 필요한 RBAC 권한 명칭(예: `run:write`, `approval:decide`)과 관리자 요청 경로를 안내한다.
5. **Partial Failure (부분 실패)**: 전체 화면 크래시를 방지하고, 성공한 파티션 데이터는 유지하며 실패한 위젯만 인라인 재시도 배너로 격리한다.

---

### 3.2 13개 화면 상세 테이블

| 번호 | 라우트 경로 | 화면 명칭 | 주 API 및 데이터 소스 | 실시간 전송 | 최소 권한 | 5대 상태 정의 및 주요 인터랙션 |
|---|---|---|---|---|---|---|
| 01 | `/login` | 로그인 화면 | `POST /v1/auth/token` | None | 익명 | • Loading: IdP 리다이렉트 스켈레톤<br>• Empty: N/A<br>• Error: IdP 인증 실패 및 네트워크 오류 코드 안내<br>• PKCE 플로우, 세션 만료 시 리다이렉트 |
| 02 | `/` | 클러스터 개요 | `GET /v1/resource-graph` | SSE (`cluster.stats`) | `project:read` | • 5개 노드 자원 게이지 (CPU/GPU/RAM/VRAM/Storage)<br>• Partial: 일부 노드 메트릭 수집 지연 시 경고 뱃지 표시 |
| 03 | `/nodes` | Node 인벤토리 | `GET /v1/nodes` | SSE (`node.state`) | `node:read` | • 노드 목록, 상태(Online/Degraded/Offline), 하트비트 시각<br>• Empty: "등록된 Node가 없습니다. 에이전트 등록 명령 복사" |
| 04 | `/nodes/{nodeId}` | Node 상세 정보 | `GET /v1/nodes/{id}`<br>`GET /v1/resources/snapshot?nodeId=` | SSE (`node.lease`) | `node:read` | • Capability, 하드웨어 사양, 활성 Lease, Snapshot 타임라인<br>• Error: 만료되었거나 이탈한 노드 명시 |
| 05 | `/projects` | 프로젝트 목록 | `GET /v1/projects` | None | `project:read` | • 프로젝트 카드 목록, 소유자, 활성 워크스페이스 수<br>• Empty: "프로젝트 생성" CTA 버튼 |
| 06 | `/projects/{id}/workspaces` | Workspace 목록·생성 | `GET/POST /v1/workspaces` | SSE (`workspace.state`) | `workspace:write` | • 격리 워크스페이스 목록, 상태, 사용 자원 한도<br>• 폼: 템플릿 선택, 허용 노드 선택, 네트워크 정책 설정 |
| 07 | `/workspaces/{id}/editor` | 파일 편집기 및 Diff | `GET/PUT /v1/workspaces/{id}/files` | None | `workspace:write` | • Monaco Editor 파일 트리 탐색<br>• 저장 시 ETag 충돌 방지 및 실시간 외부 변경 알림 |
| 08 | `/workspaces/{id}/terminal` | 웹 터미널 | WS `/v1/workspaces/{id}/terminals/{sid}` | WebSocket (PTY) | `workspace:exec` | • xterm.js 기반 양방향 PTY 셸<br>• 30초 1회용 티켓 인증, 세션 재연결, 텍스트 대체 로그 링크 |
| 09 | `/runs` | Run 목록 | `GET /v1/runs?cursor=&status=` | SSE (`run.state`) | `run:read` | • 11개 상태 필터, 프로젝트/노드 필터, 검색<br>• Empty: "실행된 Run이 없습니다" |
| 10 | `/runs/{runId}` | Run 상세 (4개 탭) | `GET /v1/runs/{id}`<br>`GET /v1/runs/{id}/explain` | SSE (`run.log`, `run.state`) | `run:read` | • 탭1: 상태 전이 타임라인<br>• 탭2: SSE 스트리밍 실시간 로그<br>• 탭3: 아티팩트 다운로드<br>• 탭4: 자원 배치 Explain |
| 11 | `/runs/{runId}/evidence` | 증거(Evidence) 패키지 | `GET /v1/runs/{id}/evidence` | None | `audit:read` | • 실행 무결성 해시, 입력/출력 검증, 불변 증거 JSON 뷰어<br>• Forbidden: 감사 권한 필요 403 안내 |
| 12 | `/approvals` | 승인 대기 목록 | `GET /v1/approvals?status=pending` | SSE (`approval.created`) | `approval:decide` | • 긴급도/만료 임박순 정렬 승인 대기 카드<br>• Empty: "대기 중인 승인 요청이 없습니다" (정상 상태) |
| 13 | `/approvals/{approvalId}` | **승인 상세 (최우선)** | `GET /v1/approvals/{id}`<br>`POST /v1/approvals/{id}/decide` | SSE (`approval.updated`) | `approval:decide` | • 명령/도구 diff, 반경, 비용, 롤백 유무, 카운트다운 타이머<br>• Two-Person Rule 1/2 승인 상태 및 자가 승인 방지 |

---

## 4. 핵심 화면 상세 설계: 승인 시스템 (`/approvals/{id}`)

승인 화면은 거버넌스 정책(L2/L3)의 핵심 관문이며, "승인 없는 L2/L3 실행 0건" 보장을 위한 최우선 구현 대상이다.

### 4.1 화면 레이아웃 및 필수 노출 필드

```
+-----------------------------------------------------------------------------------+
|  [위험 등급 배지: L2 · 주의]   승인 요청: APR-20260909-0042        [남은 시간: 04:32]  |
+-----------------------------------------------------------------------------------+
| 1. 실행 대상: Workspace [ws-saint-pilot] on Node [Node-02 (Windows GPU)]          |
|    실행 명령/도구: git.push --force (사전 정의 도구: git.deploy)                   |
| 2. 예상 비용: 잔여 예산 50,000 KRW 중 2,400 KRW 소모 예상                          |
| 3. 영향 반경: [프로젝트 격리 경계 내부] / [네트워크 격리 유지]                      |
| 4. 롤백 계획: [!WARNING] 자동 롤백 스크립트 없음 (수동 복구 필요) - 붉은색 경고 표시 |
+-----------------------------------------------------------------------------------+
| [Unified Diff 뷰어]                                                               |
|   @@ -14,4 +14,5 @@                                                               |
|   - const API_ENDPOINT = "http://internal-test";                                  |
|   + const API_ENDPOINT = "https://prod-secure.local";                             |
+-----------------------------------------------------------------------------------+
| 정책 엔진 재계산 근거: Rule #402 (외부 엔드포인트 변경 감지되어 L2로 상향됨)         |
| Two-Person Rule 상태: [V] 1차 승인: usr_admin_01 (2026-09-09 16:40:12)            |
|                      [ ] 2차 승인 대기 중 (1차 승인자는 2차 승인 불가)              |
+-----------------------------------------------------------------------------------+
|  [반려 (사유 입력 모달)]                 [승인 확정 (일회성 Nonce 포함)]          |
+-----------------------------------------------------------------------------------+
```

### 4.2 승인 안전장치 및 클라이언트 인터랙션 규칙

1. **Diff 미로드 시 승인 완전 차단**: Diff 로딩 실패 또는 부분 유실 시 승인 버튼은 `disabled` 상태를 유지하며 "Diff 로딩 실패로 인해 승인할 수 없습니다" 경고를 띄운다.
2. **One-Time Nonce 발급**: 승인 상세 화면 진입 시 발급된 `approvalNonce`를 `POST /v1/approvals/{id}/decide` 페이로드에 필수 동봉한다. 네트워크 지연 등으로 인한 더블 클릭 시 2회차 요청은 즉각 거절된다.
3. **만료 카운트다운 및 타이머 동기화**: 서버의 `expiresAt` 시각과 클라이언트 시계 차이를 서버 핑으로 보정하며, 남은 시간 60초 미만 시 붉은색 점멸 경고를 노출한다. 0초 도달 시 모든 버튼은 비활성화된다.
4. **Two-Person Rule (상호 견제)**: 정책상 2인 승인이 요구되는 경우, 로그인한 사용자가 1차 승인자 ID와 일치하면 2차 승인 버튼이 비활성화되고 "다른 승인자의 검토가 필요합니다" 툴팁이 노출된다.
5. **롤백 부재 시 시각적 경고**: `spec.rollbackPlan`이 비어 있는 경우 붉은색 아웃라인 배너로 "주의: 자동 롤백 절차가 정의되지 않았습니다"를 명시한다.

---

## 5. 실시간 전송 아키텍처 및 복원력

### 5.1 SSE (Server-Sent Events) 아키텍처

- **목적**: Run 상태 전이, 실시간 로그 스트리밍, 승인 이벤트 브로드캐스팅.
- **연결 엔드포인트**: `GET /v1/runs/{runId}/events` (W3C Trace Context 및 Bearer 헤더 포함).
- **중복 제거 (Client Deduplication)**: 이벤트 버스의 At-Least-Once 특성으로 인한 중복 수신을 방지하기 위해 클라이언트 메모리에 최근 1,000개의 `eventId` 링 버퍼를 유지하고, 이미 처리된 ID는 무시한다.
- **재연결 전략**: 네트워크 단절 시 지수 백오프 + 지터(1s → 2s → 4s ... 최대 30s)로 재연결을 시도하며, 요청 헤더에 `Last-Event-ID`를 전달해 유실 구간을 보충한다.
- **HTTP/1.1 폴백**: 클라이언트 환경이 HTTP/2를 지원하지 않아 도메인당 최대 6개 연결 제한에 걸릴 경우, 활성 SSE 연결은 Run 상세 화면 1개로 제한하고 나머지 목록 화면은 TanStack Query 5초 폴링으로 자동 폴백한다.
- **클라이언트 지연 실측 (SLO P95 ≤ 5초)**: 이벤트 수신 시 페이로드의 `occurredAt`과 수신 시각 간의 차이를 계산하여 `run_event_delivery_lag_ms` 메트릭을 수집한다.

### 5.2 WebSocket (PTY 터미널) 아키텍처

- **목적**: 대화형 웹 터미널 셸 (`/workspaces/{id}/terminal`).
- **인증 방식**: WebSocket 브라우저 API는 커스텀 헤더를 지원하지 않으므로, 연결 직전 `POST /v1/workspaces/{id}/terminals` REST 호출로 30초 유효 1회용 `ticket`을 발급받아 쿼리 파라미터(`?ticket=...`)로 전달한다. Access Token을 URL에 직접 노출하지 않는다.
- **윈도우 리사이즈**: 브라우저 윈도우 변경 시 xterm.js의 FitAddon과 연동하여 `{ type: "resize", cols: 120, rows: 40 }` JSON 제어 프레임을 백엔드로 전송(`SIGWINCH`).
- **접근성 대체 뷰**: xterm.js는 스크린리더 지원이 제한적이므로, 시각 장애 사용자 및 터미널 렌더링 실패 환경을 위해 순수 텍스트 로그 스트림 뷰(`GET /v1/runs/{id}/logs`)로 전환할 수 있는 접근성 토글을 제공한다.

---

## 6. 오류 처리 및 보안 전파 규약

### 6.1 W3C `traceparent` 전파

모든 프론트엔드 API 호출(`fetch`)은 `shared/api/client.ts` 인터셉터를 거치며 표준 W3C Trace Context 헤더를 주입한다:
`traceparent: 00-{traceId}-{spanId}-01`

서버 오류(4xx, 5xx) 반환 시 응답 헤더 및 바디의 `traceId`를 추출하여 사용자에게 인라인 복사 버튼과 함께 노출한다.

### 6.2 에러 코드군별 대응 UI 맵

| 코드 접두사 | 분류 | UI 표출 방식 및 사용자 조치 가이드 |
|---|---|---|
| `VAL-*` | 입력값 검증 오류 | 해당 입력 폼 필드 하단에 붉은색 인라인 메시지 노출 및 포커스 이동 |
| `AUTH-*` | 인증/권한 부족 | 필요한 RBAC 권한 명칭 안내 및 재로그인/권한 신청 버튼 제공 |
| `CTX-*` | 컨텍스트 만료/불일치 | "화면 데이터가 오래되었습니다" 안내 배너 및 [새로고침] 액션 |
| `TOOL-*` | 도구 실행 실패 | 도구 재시도 가능 여부(`retryable`) 플래그에 따라 [재시도] 버튼 노출 |
| `RES-*` | 자원 부족 (VRAM/RAM) | 요구 자원량과 현재 노드 가용량을 그래프로 비교 표시하고 대안 노드 제안 |
| `NET-*` | 네트워크 지연/단절 | 사용자 개입 없는 백그라운드 재연결 스피너 및 카운트다운 표시 |
| `SEC-*` | 보안 정책 차단 | 세부 공격 벡터나 시스템 내부는 감추고 "보안 정책에 의해 차단되었습니다"만 노출 |
| `BUDGET-*` | 비용/예산 초과 | 초과된 금액 내역 표시 및 추가 예산 승인 요청 링크 제공 |

---

## 7. 내부망 HTTPS 배포 및 웹 롤백 명세

### 7.1 내부망 Nginx 리버스 프록시 구성 (`nginx.conf`)

SPA 정적 파일 제공과 API/SSE/WebSocket 게이트웨이를 동일 오리진에서 서비스하여 CORS 이슈를 차단한다.

```nginx
server {
    listen 443 ssl http2;
    server_name saintvision.local;

    ssl_certificate     /etc/ssl/certs/saintvision.crt;
    ssl_certificate_key /etc/ssl/private/saintvision.key;
    ssl_protocols       TLSv1.2 TLSv1.3;

    # SPA Static Bundle
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;

        # HTML은 항상 캐시 재검증 (배포 즉시 반영)
        add_header Cache-Control "no-cache, must-revalidate";
    }

    # 정적 에셋 (JS, CSS, Font) - 캐시 버스팅
    location /assets/ {
        root /usr/share/nginx/html;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API Gateway
    location /v1/ {
        proxy_pass http://api-gateway:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    # SSE Event Streaming (버퍼링 완전 비활성화)
    location /v1/runs/events {
        proxy_pass http://api-gateway:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
        proxy_read_timeout 24h;
    }

    # WebSocket Terminal
    location /v1/workspaces/terminals {
        proxy_pass http://api-gateway:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_read_timeout 3600s;
    }
}
```

### 7.2 컨테이너 이미지 및 무중단 롤백 절차

1. **불변 이미지 태깅**: 모든 프론트엔드 빌드는 Git Commit SHA 및 이미지 Digest(SHA-256)로 태깅된다 (예: `ghcr.io/egparadise/saintvision-web:sha-d74e82e@sha256:abc...`).
2. **Zero-Secret 빌드 원칙**: 프론트엔드 빌드 아티팩트(`dist/`) 내에 일체의 서버 시크릿, IdP 클라이언트 시크릿, 내부망 프라이빗 키가 포함되지 않도록 빌드 타임 환경변수를 엄격히 차단한다.
3. **인스턴트 롤백 (Instant Rollback)**:
   - 프로덕션 배포 시 직전 배포 태그(`PREVIOUS_IMAGE_DIGEST`)를 보존한다.
   - 웹 장애 발생 시 아래 단일 명령으로 10초 이내에 이전 정본 컨테이너로 즉시 롤백한다:
   ```bash
   docker compose -f docker-compose.prod.yml stop web
   docker compose -f docker-compose.prod.yml up -d --no-deps web
   ```
4. **브라우저 스모크 검증 (Smoke Verification)**:
   - `/` 진입 및 로그인 페이지 렌더링 정상 여부 (HTTP 200)
   - `/assets/index-[hash].js` 로드 성공 여부
   - 브라우저 콘솔 자바스크립트 오류 0건
   - 텍스트 대비 WCAG AA 충족 검사 통과

---

## 8. S01-FE 합격 판정 기준 및 검증 추적

| 검증 항목 | 합격 기준 (AC-01) | 본 명세서 반영 위치 |
|---|---|---|
| 사용자 여정 정의 | 로그인, 인벤토리, 워크스페이스, 터미널, Run 추적, 승인까지 13개 화면 정의 완료 | §3.2 화면 상세 테이블 |
| 디자인 토큰 체계 | CSS 커스텀 프로퍼티 기반 라이트/다크, L0~L3 위험 색각 보정 체계 수립 | §2 디자인 토큰 시스템 |
| 5대 공통 화면 상태 | Loading, Empty, Error, Forbidden, Partial Failure 규격화 | §3.1 공통 5대 상태 |
| 승인 화면 안전장치 | One-time Nonce, 만료 카운트다운, Two-Person Rule, 롤백 경고, Diff 필수화 | §4 승인 상세 설계 |
| 실시간 전송 복원력 | SSE 링버퍼 중복제거, HTTP/1.1 폴백, WebSocket 1회용 티켓 인증 | §5 실시간 전송 아키텍처 |
| 내부망 배포 및 롤백 | Nginx 버퍼링 해제, 불변 Digest 배포, 10초 롤백 스크립트 | §7 배포 및 롤백 명세 |
