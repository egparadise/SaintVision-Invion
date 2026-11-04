---
doc_id: "HIST-20261104-CARD303B-GEMINI"
title: "Card 303b PR #401 리뷰 피드백 전수 조치 및 클러스터 신뢰 관측 정본 배선"
version: "1.0.0"
status: "proposed"
author: "Gemini"
created: "2026-11-04T13:22:00+09:00"
updated: "2026-11-04T13:22:00+09:00"
source_of_truth: "Git"
---

# Card 303b PR #401 리뷰 피드백 전수 조치 및 클러스터 신뢰 관측 정본 배선

## 1. 작업 개요 및 배경
- **작업 ID**: `task_bc95122ad616` (Dispatch ID: `ctx_afac04406137`, Run ID: `run_e57ecd84a7bc`)
- **수행 주체**: Gemini (Frontend / Antigravity)
- **베이스 커밋**: `589d79675c1b25fc5ee0dfaa11b4047211c9933c` (PR #401 head, `agent/gemini/c303-node-cert-expiry`)
- **작업 브랜치**: `agent/gemini/c303b-frontend-evidence`
- **배경 및 지침**:
  - Claude PR #401 검토 피드백(`msg_19d294097b82`) 지적 4건(F1~F4) 및 Coordinator 정본 계약 지시(`msg_827caedbcedf`)를 전수 수용·조치.
  - Coordinator는 `inv.node_channels`의 공개 인증서 만료시각을 프로젝트 범위로 서빙하는 `GET /v1/projects/{project}/node-certificates` 계약(`ProjectNodeCertificateObservationResponse`)을 선정하였으며, 프런트엔드에 typed caller 배선 및 인증/프로젝트 전환 시 fail-closed 상태 소거, 미확인 상태 정직 노출을 요구.
  - Docker Engine API 1.52 브레이킹으로 인한 CI 브라우저 테스트 장애(`msg_a0447e0329ff`)는 Coordinator가 러너(`tools/run_vf_security_tests.py`)를 패치 중이므로 가짜 PASS로 날조하지 않고 미측정 상태를 정직하게 기록.

---

## 2. 리뷰 지적 조치 및 정본 호출 배선 상세

### 2.1 F1: 호출 계층 배선 (Caller Wiring & Visibility)
- **문제**: PR #401에서 `ResourceExplorer`에 `trust` prop을 추가했으나, `App.tsx` 및 `DesktopShell.tsx`에서 이를 상위로부터 전달하지 않아 실제 가상 데스크톱 실행 시 클러스터 신뢰 정보가 유입되지 못함.
- **조치**:
  1. `DesktopShellProps`에 `trust?: ClusterTrustSummary | null;` 추가 및 `DesktopShell.tsx` 내 `<ResourceExplorer trust={trust} ... />`로 전달 결속.
  2. `App.tsx`에 `clusterTrust` 상태(`useState<ClusterTrustSummary | null>(null)`) 신설.
  3. `nodeObservation.ts`에 Coordinator 정본 계약에 맞춘 `fetchProjectNodeCertificates(projectId)` typed 호출 함수 추가:
     - `GET /v1/projects/{project}/node-certificates` 호출.
     - `scope !== 'project-node-certificates'` 또는 데이터 이상 시 null 반환.
     - 404 RouteNotFound 시 조용히 null 반환 (미배포 환경 fail-closed).
  4. `fetchNodes`에서 노드 목록 조회와 함께 인증서 관측 결과를 병합:
     - `items` 매핑 시 `nodeId`를 대조하여 `certificateNotAfter`를 각 노드 객체에 결속.
     - `setClusterTrust(certObs?.trust ?? null);`로 정본 신뢰 객체 바인딩.
  5. 상태 소거 불변식 엄수:
     - 인증 해제 시(`resetAuthenticatedState`): `setClusterTrust(null);`
     - 프로젝트 전환 시(`chooseProject`): `setNodes([]); setClusterTrust(null);`
     - 노드 조회 실패 시(`catch`): `setNodes([]); setClusterTrust(null);`
     - 신뢰 정보 부재 시: `setClusterTrust(null);`

### 2.2 F2: 미확인 신뢰 상태의 정직한 가시화 (Unknown Trust State Visibility)
- **문제**: 종전 구현은 `trust`가 없거나 `unknown`일 때 배너와 배지를 모두 숨겨, 운영자가 클러스터 검증 여부를 전혀 알 수 없게 됨.
- **조치**:
  1. `ResourceExplorer.tsx`에 `TRUST_STATUS_CONFIG satisfies Record<ClusterTrustState, TrustStatusConfigItem>` 및 `getTrustStatusConfig` 함수 구현.
  2. `Object.hasOwn` 기반 fail-closed 검증을 적용하여 프로토타입 오염(`toString`, `constructor`, `__proto__`) 방어.
  3. 툴바 상태 배지를 상시 노출: `trust`가 없거나 `unknown`일 때 `● 신뢰 미확인` (`data-testid="trust-status-badge"`) 배지와 안내 툴팁 노출.

### 2.3 F3: 정직한 UI 문구 (Truthful Copy)
- **문제**: 자동 갱신 스케줄러(Card 304 / PR #402)가 미등록 상태임에도 UI가 '자동 갱신 창'이라고 단언하여 운영자에게 자동 처리의 허위 신뢰를 제공함.
- **조치**:
  - 상단 갱신 윈도우 배너 및 툴바 배지 문구를 `인증서 갱신 창 (스케줄러 미등록) — 만료까지 N일 N시간`으로 개정하여 스케줄러 부재 사실을 정직하게 고지.

### 2.4 F4: 엄격한 타입 위생 및 Any 캐스팅 박멸
- **문제**: `ResourceExplorer.tsx`에서 `(nodeDetail.node as any)?.certificateNotAfter` 캐스팅 사용.
- **조치**:
  - `selectedNode?.certificateNotAfter`로 교체하여 타입 안전성 확보 및 불필요한 `as any` 제거.
  - `App.tsx`에서도 `(page as any).trust`를 전면 소거하고 정본 `fetchProjectNodeCertificates` 결과로부터만 신뢰 상태를 수신.

### 2.5 타임존 및 인증 만료(401) 대응
- `formatKstDateTime`에서 `Intl.DateTimeFormat`의 `timeZone: 'Asia/Seoul'`, `hourCycle: 'h23'`를 적용하고 시간 `'24'`를 `'00'`으로 정규화. 명시적 `null`은 `'인증서 없음'`, 미확인/오류는 `'미확인'`, 만료된 인증서는 `... (만료됨)` 경고 색상(`var(--color-status-offline)`)으로 렌더링.
- 세션 유효성 만료(HTTP 401 `onUnauthorized`) 수신 시 민감 상태 즉시 소거, 가상 데스크톱 언마운트, 로그인 화면 전환 및 `[AUTH-0050]` 경고 알림(`role="alert"`) 렌더링 검증 완료.

---

## 3. 검증 결과 및 증거

### 3.1 단위 및 통합 테스트 실측
| 시험 항목 | 실행 명령 | 결과 | 비고 |
| :--- | :--- | :--- | :--- |
| 노드 인증서 만료/신뢰 단위시험 | `npm --prefix apps/web test tests/node-cert-trust-expiry.test.tsx` | 34 passed (exit 0) | 상태별 배지, 만료 경고, KST 변환, 프로토타입 방어 |
| OIDC 인증 및 데스크톱 배선 통합시험 | `npm --prefix apps/web test tests/auth-app-oidc-integration.test.tsx` | 6 passed (exit 0) | 401 세션 만료 언마운트, 정본 엔드포인트 배선, 미확인 가시화 |
| 자원 탐색기 DOM 시험 | `npm --prefix apps/web test tests/resource-explorer-dom.test.tsx` | 27 passed (exit 0) | 탭 전환, 노드 목록 및 역량 그리드 렌더링 |
| 디자인 토큰 및 명도 대비 시험 | `npm --prefix apps/web test tests/acc09-contrast-tokens.test.tsx` | 46 passed (exit 0) | 색상 리터럴 0건, 래칫 458/31 유지 |
| 전체 Vitest 스위트 | `npm --prefix apps/web test` | 100 test files, 1194 passed (exit 0) | 전수 통과 |

### 3.2 빌드 및 리포지토리 게이트 실측
- **TypeScript 타입 체크**: `cd apps/web; npx tsc -b` -> Exit 0 (0 errors).
- **프로덕션 번들 빌드**: `npm run build --prefix apps/web` -> Exit 0 (Vite v6.4.3 production bundle built in 6.22s).
- **프런트엔드 무결성 스캐너**: `$env:PYTHONUTF8="1"; py -3.14 tools/check_frontend_integrity.py` -> 93개 소스 파일 스캔, 9대 무결성 규칙 전수 충족 (0 violations, Exit 0).
- **화면-백엔드 라우트 커버리지 파이썬 게이트**: `python -m pytest tests/test_route_coverage.py` -> 41 passed in 2.59s (Exit 0).
- **계약 바인딩 게이트**: `python tools/check_contract_bindings.py` -> 56 fixtures, 20 bound types, 14 replay guards PASS (Exit 0).
- **Git 포맷 검증**: `git diff --check` -> Clean (Exit 0).

---

## 4. 잔여 과제 및 인계
1. **Coordinator 백엔드 엔드포인트 구현 대기**:
   - Coordinator가 `services/control-plane`에서 `GET /v1/projects/{project}/node-certificates` 및 canonical schema/generated type 배포 완료 후 통합 검증 가능.
2. **CI 브라우저 인프라 복구 대기**:
   - Docker Engine API 1.52 대응 러너 패치(`tools/run_vf_security_tests.py`)를 Coordinator가 진행 중이므로, 실제 컨테이너 브라우저 테스트 완료 전까지는 5-Node 운영 합격을 주장하지 않음.
