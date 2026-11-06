---
doc_id: "PORTAL-REFRESH-FLEET-UI-20261106-GEMINI"
title: "포털 텔레메트리 주기 조회 안정화 및 정직한 게이트웨이·신원 관측"
version: "1.1.0"
status: "active"
author: "Gemini"
updated: "2026-11-06T20:36:00+09:00"
source_of_truth: "Git"
---

# 포털 텔레메트리 주기 조회 안정화 및 정직한 게이트웨이·신원 관측

## 1. 개요 및 배경

- **Task**: `PORTAL-REFRESH-FLEET-20261106` (Task ID: `task_9d814a8270e1`, Dispatch ID: `ctx_d855f1849f6b`)
- **담당 및 역할**: Gemini via Antigravity (프런트엔드 바운디드 구현 및 단위/CI 검증 전담; Root 배포 및 인프라 소유).
- **작업 환경**: Worktree `D:/Project/SaintVisionI-Invion/portal-refresh-fleet-ui-20261106`, branch `agent/gemini/portal-refresh-fleet-ui-20261106`.
- **기준 베이스**: Root 정본 `53683020e3cfaf79ec4662f9a79b8b4dae28a628` (Index 1.0.453 / Codex 1.0.414).
- **1차 동결 후보**: `3a83707688f43570a7eaf9008989794979b3eb9f`
- **Root 피드백 반영 동결 후보**: `2d87d7aa3af1e35e5980ab340d132df56ce52c66`

### 제기된 문제 및 원인 분석

1. **포털(http://127.0.0.1:3100/studio 및 /dashboard) 5초 주기 깜빡임/플리커 현상**:
   - `App.tsx`의 5초 주기 `fetchNodes`, `fetchRuns`, `fetchApprovals`, `fetchWorkspaces` 호출 시 매번 `setNodesState('loading')`을 실행함.
   - `ClusterOverview.tsx`에서 노드가 0대일 때 `nodesState === 'success' || nodesState === 'idle'`인 경우에만 빈 클러스터 안내 카드(`cluster-overview-empty-state`)를 렌더링하고, `'loading'` 중에는 하단 메트릭/게이지 카드 연산 블록으로 떨어져 DOM을 교체했다가 수백 ms 뒤 다시 빈 카드 컴포넌트로 언마운트/리마운트되는 깜빡임이 반복 발생함.
2. **게이트웨이 오프라인 오표기 (Gateway: Offline 빨간색 표시)**:
   - 포털 상단 `Header.tsx`에서 `/v1/health`를 polling하고 있었으나, FastAPI 백엔드(`services/control-plane/src/inv/app.py`)는 `/healthz` 및 `/readyz`를 서빙하며 `/v1/health` 경로를 등록하지 않아 `HTTP 404 Not Found`가 반환됨.
   - 또한 초기 상태가 `{ online: true, rttMs: 8 }`로 하드코딩되어 실제 미관측 상태를 은폐하고 있었음.
3. **사용자 신원 표기 문제**:
   - OIDC 인증 후 세션의 사용자 이름에 64자리 해시 형태의 subject ID(`oidc:3f790914...`)가 헤더 알약에 그대로 길게 노출됨.
4. **실제 리소스 관측과 정직성 원칙 (5대 위조 금지)**:
   - 현재 데모 LAN pilot DB에는 등록된 노드가 실제로 0대(`nodes.length === 0`)임. 지침에 따라 5/5대 가짜 자원, 허위 타임스탬프, 조작된 지표를 위조하지 않고, 정상 0대 빈 스냅샷을 백그라운드 갱신 중에도 안정적으로 유지함.

---

## 2. Root 피드백 검토 및 조치 내역 (R-UI-M1, R-UI-M2)

Root 코디네이터 메시지(`msg_53f39f9a6bf2`)에서 지적된 2가지 핵심 계약 불일치를 해결함:

### R-UI-M1: 표준 제어 평면 `/healthz` 계약 준수 및 SPA HTML 200 오판 차단
- **지적 사항**: 기존 코드가 `/v1/health`(FastAPI 404)를 호출하고 있었으며, Vite/nginx SPA 라우팅의 fallback에 따른 `text/html` 200이나 401/404를 정상 응답으로 잘못 수용할 위험이 있었음. 또한 헤더 기본값이 5/5 노드를 가정하는 문제.
- **조치 내역** (commit `0fa827e8`):
  1. `Header.tsx`: 제어 평면 표준 정본 경로인 `/healthz`를 호출하도록 수정. 응답 헤더 `Content-Type: application/json` 포함 여부 및 본문 JSON 파싱 결과 `data.status === 'ok'` 여부를 엄격히 검증. SPA fallback HTML 200, 401, 404, 503 및 비정상 응답을 Fail-Closed로 거부하여 오프라인 판정.
  2. 게이트웨이 및 클러스터 카운트 기본값: 초기 및 미관측 상태는 `null`("확인 중...", unknown 도트)로 처리하고, 실제 0대 관측 시 0/0으로 정직 표기(5/5 위조 금지).
  3. `vite.config.ts`: Vite 개발 서버(`server.proxy`) 및 프로덕션 프리뷰 서버(`preview.proxy`)에 `'/healthz'` 리버스 프록시 규칙 등록 (`target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8080'`).
  4. `nginx.conf`: HTTPS 443 포트 블록에 `/healthz` 업스트림(`http://control-plane:8080`) 프록시 패스를 추가(컨테이너 liveness를 위한 기존 HTTP 80 평문 'OK' 로컬 응답은 보존).

### R-UI-M2: 빈 클러스터(0대) 주기 갱신 실패 시 정직한 Stale 경고 표출
- **지적 사항**: `ClusterOverview.tsx`에서 노드가 0대일 때 무조건 빈 성공 카드로 렌더링되어, 이전에 0대를 정상 관측했더라도 이후 백그라운드 갱신이 실패(`nodesState === 'error'` with `lastFetchedAt`)했을 때 실패 사실이 사용자에게 은폐되는 문제. 또한 초기 진입 시(`!lastFetchedAt && nodesState !== 'success'`) "정상 조회 결과: 0대"로 둔갑하지 않아야 함.
- **조치 내역** (commit `2d87d7aa`):
  1. `ClusterOverview.tsx`:
     - 이전에 0대 노드를 성공적으로 관측했으나 백그라운드 갱신이 실패한 경우(`nodesState === 'error' && lastFetchedAt`), 기존 빈 상태 카드를 안정적으로 유지(DOM 언마운트/플리커 방지)하되 상단에 명시적인 `cluster-stale-warning` (`role="alert"`) 배너 및 재시도 버튼을 렌더링하고, 현재 표시가 과거 스냅샷 시점의 데이터임을 명시.
     - 초기 미관측 상태(`!lastFetchedAt && (nodesState === 'idle' || nodesState === 'loading')`)에서는 "정상 조회 결과: 0대"라는 허위 성공 문구를 표출하지 않고 "클러스터 노드 정보를 확인하고 있습니다..."로 정직 표기.
     - `acc09-contrast-tokens.test.tsx`의 엄격한 AST 스타일 속성 수(76) 및 토큰 불변식을 100% 준수하여 테스트를 통과함.
  2. `App.tsx`:
     - 프로젝트 전환 시 이전 비동기 응답이 새로운 프로젝트 스코프를 오염시키지 않도록 `scopeRef` 및 `activeProject` 펜스 적용.
     - 안건 승인/반려 시 권한 및 안건 목록이 stale/error 상태일 때 작업을 Fail-Closed로 차단하는 가드 적용.

---

## 3. 검증 실측 결과 (명령어 및 Exit Code)

모든 검증은 명령 실행 즉시 `$LASTEXITCODE`를 확인하여 0을 실측함.

| 단계 | 실행 명령어 | Exit Code | 실측 결과 요약 |
|---|---|---|---|
| 신설 단위 시험 | `npx vitest run apps/web/tests/portal-refresh-fleet-ui.test.tsx` | 0 | 20 passed (100% 성공) |
| 전체 Vitest 스위트 | `npx vitest run` | 0 | 103 test files passed, 1,238 tests passed |
| TypeScript 타입 검사 | `npx tsc -b` | 0 | 0 errors |
| 프로덕션 번들 빌드 | `npm run build` (`tsc -b && vite build`) | 0 | built in 4.84s, `dist/assets/index-VJNRr0e6.js` (1,296.67 kB) 생성 |
| 프런트엔드 무결성 | `python tools/check_frontend_integrity.py` | 0 | 94 files scanned, 9 rules satisfied (0 violations) |
| 계약 바인딩 | `python tools/check_contract_bindings.py` | 0 | 57 fixtures, 21 bound types, 14 replay guards PASS |
| 라우트 커버리지 | `pytest tests/test_route_coverage.py` | 0 | 41 passed in 2.90s |
| 문서 정합성 | `python tools/check_docs.py` | 0 | 24 original hashes, 1260 versioned documents PASS |
| Obsidian 동기화 점검 | `python tools/sync_obsidian.py --check --state ...` | 0 | 2828 managed files, 0 conflicts, no writes |
| 동기화 상태 해시 | `Get-FileHash .../obsidian-sync-state.json` | 0 | `DCFDB284A97FB048592E857DA5F80AEDE2811E82EB93FEAA4D1DFB7446660629` (불변) |

---

## 4. GitHub Actions CI 검증 결과

- **대상 브랜치**: `agent/gemini/portal-refresh-fleet-ui-20261106`
- **1차 커밋 SHA**: `3a83707688f43570a7eaf9008989794979b3eb9f`
- **최종 동결 커밋 SHA**: `2d87d7aa3af1e35e5980ab340d132df56ce52c66`

### 2차 CI 실행 결과 (최신 동결 후보 `2d87d7aa` 기준)

| 워크플로 명 | Run ID | Job ID(s) | 상태 | 결론 | 비고 |
|---|---|---|---|---|---|
| Documentation Build | `42211247163` | `127870134953` | completed | **success** | docs, check_docs, contract_bindings, frontend_integrity 전원 통과 |
| Frontend Build & Test | `42211235450` | `127870096841`<br>`127870097238` | completed | **success** | frontend (ESLint, Vitest 103/103, tsc, build), Portal Container Hardened Smoke 전원 통과 |
| Portal Login Journey Harness | `42207878338` | `127858939110` | completed | **success** | portal-login-harness 전원 통과 |

### 생성된 빌드 아티팩트 (`42211235450`)

1. `saintvision-web-dist`:
   - Artifact ID: `13499835128`
   - 크기: 1,116,712 bytes
   - SHA256 Digest: `375cec90c8ec66fe2880a8f954d7264324ae95d1925710858fe99fb1f35936fe`
2. `saintvision-portal-release`:
   - Artifact ID: `13499830407`
   - 크기: 25,978,805 bytes
   - SHA256 Digest: `65ecbb17516ab4e044921282774d5bb3df60b38d016ede65deea4c995eae499f`

---

## 5. 제약 준수 및 인계 상태

- **라이브 서비스 격리**: 3100, 8080, 8443 데몬 및 r5 환경 일체 재시작·간섭 없음.
- **5대 위조 배제**: demo LAN pilot DB의 정직한 0대 노드 상태 유지 및 허위 리소스 주입 없음.
- **권한 및 삼상 게이트 보존**: 인증 및 에러 게이트 우회 없음, 정상 OIDC 흐름 준수.
- **Chrome Host 접근 금지**: CDP 또는 사용자 브라우저 프로필 간섭 없음, CI 및 로컬 헤드리스 검증에 국한.
- **독립 리뷰 상태**: `PENDING` (Claude 독립 검토 요청용 동결 후보 `2d87d7aa` 준비 완료).
- **운영 배포 상태**: `NOTRUN` (Root 관리자 소유권 보존, 배포 미실행 정직 고지).
