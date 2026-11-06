---
doc_id: "PORTAL-REFRESH-FLEET-UI-20261106-GEMINI"
title: "포털 텔레메트리 주기 조회 안정화 및 정직한 게이트웨이·신원 관측"
version: "1.0.0"
status: "active"
author: "Gemini"
updated: "2026-11-06T20:10:00+09:00"
source_of_truth: "Git"
---

# 포털 텔레메트리 주기 조회 안정화 및 정직한 게이트웨이·신원 관측

## 1. 개요 및 배경

- **Task**: `PORTAL-REFRESH-FLEET-20261106` (Task ID: `task_9d814a8270e1`, Dispatch ID: `ctx_d855f1849f6b`)
- **담당 및 역할**: Gemini via Antigravity (프런트엔드 바운디드 구현 및 단위/CI 검증 전담; Root 배포 및 인프라 소유).
- **작업 환경**: Worktree `D:/Project/SaintVisionI-Invion/portal-refresh-fleet-ui-20261106`, branch `agent/gemini/portal-refresh-fleet-ui-20261106`.
- **기준 베이스**: Root 정본 `53683020e3cfaf79ec4662f9a79b8b4dae28a628` (Index 1.0.453 / Codex 1.0.414).

### 제기된 문제 및 원인 분석

1. **포털(http://127.0.0.1:3100/studio 및 /dashboard) 5초 주기 깜빡임/플리커 현상**:
   - `App.tsx`의 5초 주기 `fetchNodes`, `fetchRuns`, `fetchApprovals`, `fetchWorkspaces` 호출 시 매번 `setNodesState('loading')`을 실행함.
   - `ClusterOverview.tsx`에서 노드가 0대일 때 `nodesState === 'success' || nodesState === 'idle'`인 경우에만 빈 클러스터 안내 카드(`cluster-overview-empty-state`)를 렌더링하고, `'loading'` 중에는 하단 메트릭/게이지 카드 연산 블록으로 떨어져 DOM을 교체했다가 수백 ms 뒤 다시 빈 카드 컴포넌트로 언마운트/리마운트되는 깜빡임이 반복 발생함.
2. **게이트웨이 오프라인 오표기 (Gateway: Offline 빨간색 표시)**:
   - 포털 상단 `Header.tsx`에서 `/v1/health`를 polling하고 있었으나, FastAPI 백엔드(`services/control-plane/src/inv/app.py`)는 `/healthz` 및 `/readyz`를 서빙하며 `/v1/health` 경로를 등록하지 않아 `HTTP 404 Not Found`가 반환됨.
   - 3100 포트의 Vite SPA 프록시를 통해 8080 백엔드로 전달된 HTTP 404 응답은 제어 평면 게이트웨이와의 전송 계층 통신이 정상이고 응답 왕복 지연시간(RTT)이 실측되는 상태임에도, 종전 코드가 단순 `res.ok`가 아니면 전부 `online: false`로 단정하여 빨간색 Offline을 표시함.
   - 또한 초기 상태가 `{ online: true, rttMs: 8 }`로 하드코딩되어 실제 미관측 상태를 은폐하고 있었음.
3. **사용자 신원 표기 문제**:
   - OIDC 인증 후 세션의 사용자 이름에 64자리 해시 형태의 subject ID(`oidc:3f790914...`)가 헤더 알약에 그대로 길게 노출됨.
4. **실제 리소스 관측과 정직성 원칙 (5대 위조 금지)**:
   - 현재 데모 LAN pilot DB에는 등록된 노드가 실제로 0대(`nodes.length === 0`)임. 지침에 따라 5/5대 가짜 자원, 허위 타임스탬프, 조작된 지표를 위조하지 않고, 정상 0대 빈 스냅샷을 백그라운드 갱신 중에도 안정적으로 유지함.

---

## 2. 소스 수정 내역 및 계약 정합

1. `apps/web/src/shared/ui/Header.tsx`:
   - 초기 게이트웨이 상태를 정직한 미관측 상태 `{ online: null, rttMs: null }`로 초기화하고 UI에 "확인 중..." 및 `status-unknown` 점으로 표출.
   - 게이트웨이 체크 시 제어 평면으로부터의 HTTP 2xx, 401, 404 응답을 전송 계층 연결 확인으로 판정하고 실제 실측된 RTT(ms)를 표출함. 네트워크 단절(`catch`) 시에만 Offline 표시.
   - `formatUserDisplayName` 헬퍼 함수를 추가하여 64자리 긴 `oidc:...` 해시를 `사용자 (3f790914…)` 형식으로 정제.
2. `apps/web/src/features/dashboard/ClusterOverview.tsx`:
   - 빈 클러스터 안내 렌더링 조건 안정화: `nodes.length === 0`일 때 백그라운드 갱신 중에도 패널이 언마운트되거나 메트릭 카드로 전환되지 않도록 함.
   - 초기 조회 실패(`nodesState === 'error' && nodes.length === 0 && !lastFetchedAt`) 시에만 에러 배너를 표출하고, 이전 성공 관측이 있는 백그라운드 실패 시에는 관측 스냅샷을 유지함.
   - 엄밀한 AST 스타일 속성 수(76) 및 `border-subtle` 토큰 수(487)를 100% 보존.
3. `apps/web/src/app/App.tsx`:
   - `fetchNodes`, `fetchRuns`, `fetchApprovals`, `fetchWorkspaces` 함수에 `isBackground = false` 인자 도입.
   - 초기 마운트 및 수동 재시도 시에는 `false`로 호출하여 로딩 스피너 및 에러를 갱신하고, 5초 주기 백그라운드 인터벌에서는 `true`로 호출하여 진행 중인 화면의 불필요한 깜빡임을 제거함.
   - 백그라운드 조회 실패 시 기존 관측 노드 목록을 `setNodes([])`로 강제 소거하지 않음으로써 truthful stale observation 유지.
4. `apps/web/src/features/auth/session.ts`:
   - OIDC 토큰 클레임(`preferred_username`, `name`, `email`)에서 사용자 표시명을 우선 추출하고, 없는 경우 `사용자 (${subjectId.slice(5, 13)}…)` 형태로 정제하여 `user.name`에 바인딩.
5. `apps/web/tests/portal-refresh-fleet-ui.test.tsx`:
   - 12개 정밀 단위 시험 신설:
     - 0대 노드 빈 스냅샷의 연속 백그라운드 폴링 안정성 (DOM 언마운트 및 메트릭 플리커 차단 실측)
     - 초기 로딩 상태 대 백그라운드 갱신 상태 분리
     - 백그라운드 폴링 실패 시 stale 관측 데이터 유지
     - 조회 실패 후 재시도 성공 시 정상 회복
     - 미관측 게이트웨이 초기 정직 고지 ("확인 중...")
     - 200/401/404 전송 계층 응답에 대한 실제 RTT 실측 및 온라인 표출
     - 네트워크 에러 시 정직한 Gateway Offline 표출
     - 긴 OIDC 식별자 및 정상 사용자명 포맷팅 검증

---

## 3. 검증 실측 결과 (명령어 및 Exit Code)

모든 검증은 명령 실행 즉시 `$LASTEXITCODE`를 확인하여 0을 실측함.

| 단계 | 실행 명령어 | Exit Code | 실측 결과 요약 |
|---|---|---|---|
| 신설 단위 시험 | `npx vitest run apps/web/tests/portal-refresh-fleet-ui.test.tsx` | 0 | 12 passed (100% 성공) |
| 전체 Vitest 스위트 | `npx vitest run` | 0 | 103 test files passed, 1,230 tests passed |
| TypeScript 타입 검사 | `npx tsc -b apps/web/tsconfig.json` | 0 | 0 errors |
| 프로덕션 번들 빌드 | `npm run build` (`tsc -b && vite build`) | 0 | built in 10.73s, `dist/assets/index-ByuU2oRk.js` (1,295.20 kB) 생성 |
| 프런트엔드 무결성 | `python tools/check_frontend_integrity.py` | 0 | 94 files scanned, 9 rules satisfied (0 violations) |
| 계약 바인딩 | `python tools/check_contract_bindings.py` | 0 | 57 fixtures, 21 bound types, 14 replay guards PASS |
| 라우트 커버리지 | `pytest tests/test_route_coverage.py` | 0 | 41 passed in 1.46s |
| 문서 정합성 | `python tools/check_docs.py` | 0 | 24 original hashes, 1259 versioned documents PASS |
| Obsidian 동기화 점검 | `python tools/sync_obsidian.py --check --state ...` | 0 | 2826 managed files, 0 conflicts, no writes |
| 동기화 상태 해시 | `Get-FileHash .../obsidian-sync-state.json` | 0 | `4DA58376256FBB6C4570D291CB1B33DDE55DBD5ED2B3CE22295609E1743CAB7A` (불변) |

---

## 4. GitHub Actions CI 검증 결과

- **대상 브랜치**: `agent/gemini/portal-refresh-fleet-ui-20261106`
- **동결 커밋 SHA**: `3a83707688f43570a7eaf9008989794979b3eb9f`

| 워크플로 명 | Run ID | Job ID(s) | 상태 | 결론 | 비고 |
|---|---|---|---|---|---|
| Documentation Build | `42207943051` | `127859155285` | completed | **success** | docs, check_docs, contract_bindings, frontend_integrity 전원 통과 |
| Frontend Build & Test | `42207931409` | `127859117188`<br>`127859117510` | completed | **success** | frontend (ESLint, Vitest 103/103, tsc, build), Portal Container Hardened Smoke 전원 통과 |
| Portal Login Journey Harness | `42207878338` | `127858939110` | completed | **success** | portal-login-harness 전원 통과 |

### 생성된 빌드 아티팩트

1. `saintvision-web-dist`:
   - Artifact ID: `13498400518`
   - 크기: 1,115,545 bytes
   - SHA256 Digest: `3458bea031691fe11cfa69337f1e9e6857d220897a62f8f9d3d4966ebd94f4ce`
2. `saintvision-portal-release`:
   - Artifact ID: `13497735996`
   - 크기: 25,975,981 bytes
   - SHA256 Digest: `b1eb936141856dd676af72bde5f71769200243558fc7d3a6a68257f8066b489a`

---

## 5. 제약 준수 및 인계 상태

- **라이브 서비스 격리**: 3100, 8080, 8443 데몬 및 r5 환경 일체 재시작·간섭 없음.
- **5대 위조 배제**: demo LAN pilot DB의 정직한 0대 노드 상태 유지 및 허위 리소스 주입 없음.
- **권한 및 삼상 게이트 보존**: 인증 및 에러 게이트 우회 없음, 정상 OIDC 흐름 준수.
- **Chrome Host 접근 금지**: CDP 또는 사용자 브라우저 프로필 간섭 없음, CI 및 로컬 헤드리스 검증에 국한.
- **독립 리뷰 상태**: `PENDING` (Claude 독립 검토 요청용 동결 후보 준비 완료).
- **운영 배포 상태**: `NOTRUN` (Root 관리자 소유권 보존, 배포 미실행 정직 고지).
