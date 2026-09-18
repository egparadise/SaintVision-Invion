# 2026-09-18 16:40:00 KST route_coverage 정본 도구 6개 미제공 경로 전수 감사 및 정합 보고

## 1. 개요
- **목적**: 정본 도구 `tools/route_coverage.py` 실측 시 식별된 6개 미제공 경로(`/v1/discovery/candidates{}`, `/v1/events`, `/v1/projects/{}/runs/{}/evidence`, `/v1/runs`, `/v1/runs/{}/evidence`, `/v1/workspaces`)에 대한 백엔드 서빙 여부 전수 검증, 클라이언트 호출 원인 및 런타임 오류 위험도 분석, 화면 노출 경로 vs 시스템 고의 미노출 경로 분류 정리.
- **담당 Agent**: Gemini (Frontend & Ingress Owner)
- **대상 브랜치**: `integration/all-agents-unified`

---

## 2. 6개 미제공 경로 전수 분석 및 조치 결과

| # | 식별 경로 (route_coverage) | 백엔드 실존 여부 | 클라이언트 호출 지점 및 원인 | 런타임 위험도 | 조치 및 결과 |
|---|---|---|---|---|---|
| 1 | `/v1/discovery/candidates{}` | **실존함** (`@router.get("/discovery/candidates")`, `pools.py`:86) | `fabricControlApi.ts`: `${query}`에 선행 슬래시/물음표가 조건부 결합되면서 정규화기가 `{}`로 치환한 도구 아티팩트 | **낮음** (호출 시 쿼리 파라미터로 붙으나 정적 추출기 오분석) | 조건부 삼항 리터럴 분기(`includeStale ? '/v1/discovery/candidates?includeStale=true' : '/v1/discovery/candidates'`)로 수정하여 해소 |
| 2 | `/v1/events` | **존재하지 않음** (정본 커널 SSE는 `@api.get("/v1/projects/{project}/runs/{run_id}/events")`, `app.py`:858) | `deploymentEngine.ts`: Nginx 역방향 프록시 규칙 표 및 nginx.conf 템플릿의 정적 경로 문자열 | **중간** (실제 브라우저 SSE 연결이 `/v1/events`가 아닌 프로젝트 스코프 경로를 타면서 Nginx 기본 `/v1` 프록시 규칙에 걸려 버퍼링 해제 미적용 가능성) | `deploymentEngine.ts` 프록시 규칙 및 Nginx location 정규식을 `location ~ ^/v1/projects/[^/]+/runs/[^/]+/events`로 정합하여 해소 |
| 3 | `/v1/projects/{}/runs/{}/evidence` | **존재하지 않음** (정본 증거는 `@api.get("/v1/projects/{project}/runs/{run_id}/result")`, `app.py`:396 에 번들) | `EvidenceViewer.tsx`: 레거시 엔드포인트 탐색용 1순위 trial 호출 (`/v1/projects/.../evidence`) | **중간** (매 증거 조회 시 무조건 404 실패 1회 발생 후 fallback 전환으로 인한 네트워크 낭비) | `EvidenceViewer.tsx`에서 trial 호출을 제거하고 정본 `/v1/projects/${prjId}/runs/${runId}/result`를 직접 호출하도록 단일화 |
| 4 | `/v1/runs/{}/evidence` | **존재하지 않음** | `EvidenceViewer.tsx`: 레거시 엔드포인트 탐색용 2순위 trial 호출 (`/v1/runs/.../evidence`) | **중간** (위 1순위 실패 후 연달아 404 실패 1회 추가 발생) | `EvidenceViewer.tsx`에서 trial 호출 제거로 영구 해소 |
| 5 | `/v1/runs` | **존재하지 않음** (정본 커널 실행 목록은 `@api.get("/v1/projects/{project}/runs")`) | `EvidenceViewer.tsx`: 위 2순위 `/v1/runs/${runId}/evidence`에서 `_CLIENT_HEAD` 정규식이 `${runId}` 앞부분(`/v1/runs/`)을 과잉 추출하여 합성된 경로 | **없음** (클라이언트가 실제 `/v1/runs`를 단독 호출하지 않음) | `EvidenceViewer.tsx`의 trial 호출 제거로 동시 소멸 |
| 6 | `/v1/workspaces` | **존재하지 않음** (정본 커널은 `@router.get("/projects/{project_id}/workspaces")`, `projects.py`:112) | `WebTerminal.tsx` (`/v1/workspaces/${id}/terminal-tickets`) 및 `DeveloperStudio.tsx` (`/v1/workspaces/${id}/execution-readiness`) | **없음** (클라이언트는 평면 `/v1/workspaces`를 절대 호출하지 않음; 실제 호출은 프로젝트 스코프 `/v1/projects/{p}/workspaces`) | `tools/route_coverage.py`의 `_CLIENT_HEAD` 정규식이 서브리소스 식별자 앞부분을 자르면서 생성된 순수 **도구 아티팩트**로 판명 |

---

## 3. 제어 평면 16개 경로의 화면 노출 vs 시스템 고의 미노출 분류

사용자가 질의한 제어 평면 16개 경로에 대한 UI 노출 및 시스템 데몬 전용 경로의 명확한 분류:

1. **화면(UI) 노출 완료 경로 (14개)**:
   - `GET /v1/storage/contributions`: `StorageContributionManager.tsx` 및 `AdminSecurityConsole.tsx` (기여 스토리지 목록)
   - `POST /v1/storage/contributions`: `StorageContributionManager.tsx` (신규 볼륨/디스크 기여 등록)
   - `POST /v1/storage/contributions/{id}/activation`: `StorageContributionManager.tsx` (스토리지 활성화)
   - `POST /v1/storage/contributions/{id}/deactivation`: `StorageContributionManager.tsx` (스토리지 비활성화/회수)
   - `GET /v1/storage/locations`: `StorageLocationsView.tsx` (논리 스토리지 위치 및 노드 마운트 매핑)
   - `GET /v1/pools/{id}/capacity`: `ResourceExplorer.tsx` 및 `FabricControlPlane.tsx` (풀별 용량/사용률)
   - `GET /v1/pools/{id}/placement-preview`: `ResourceExplorer.tsx` (배치 시뮬레이션 미리보기)
   - `POST /v1/pools/{id}/plans`: `ResourceExplorer.tsx` (자원 풀 계획 수립)
   - `PUT /v1/pools/{id}/members/{node_id}`: `FabricControlPlane.tsx` (풀 노드 멤버십 추가/수정)
   - `DELETE /v1/pools/{id}/members/{node_id}`: `FabricControlPlane.tsx` (풀 노드 퇴출)
   - `GET /v1/nodes/{id}`: `NodeDetailModal.tsx` 및 `NodeManager.tsx` (노드 상세 토폴로지)
   - `POST /v1/nodes/liveness-sweeps`: `FabricControlPlane.tsx` (오퍼레이터 수동 전체 활성 스윕)
   - `POST /v1/discovery/candidates/{id}/admission`: `DiscoveryCandidatesModal.tsx` (후보 노드 패브릭 정식 편입)
   - `DELETE /v1/discovery/candidates/{id}`: `DiscoveryCandidatesModal.tsx` (후보 노드 거절/삭제)

2. **고의 미노출 / 시스템 데몬 전용 경로 (2개)**:
   - `POST /v1/nodes/{id}/heartbeats`: **워커 노드 물리 데몬/백그라운드 전용**. 브라우저 SPA 사용자가 임의로 특정 노드의 심박(heartbeat)을 위조 발송하는 것은 보안 및 클러스터 상태 무결성 원칙상 금지되며, UI는 상태 관측(`GET /v1/nodes`) 및 수동 스윕 트리거(`POST /v1/nodes/liveness-sweeps`)만 노출함.
   - `POST /v1/discovery/announcements`: **디스커버리 멀티캐스트 수신 데몬 전용**. 브로드캐스트 공지는 물리/가상 머신 시동 시 데몬이 송출하는 것이며, UI는 공지 수신 결과로 적재된 후보 목록(`GET /v1/discovery/candidates`) 및 승인/거절 인터페이스만 노출함.

---

## 4. 검증 결과
1. **Vitest 전체 스위트**:
   - 명령: `npm --prefix apps/web test -- --run`
   - 결과: **31개 파일 302 passed / 0 failed (3.31s)**
2. **Pytest 경계 및 라우트 커버리지 단위 테스트**:
   - 명령: `.venv\Scripts\pytest.exe tests/test_browser_smoke_boundary.py tests/test_route_coverage.py`
   - 결과: **28 passed in 4.82s (100%)**
3. **Route Coverage 재측정**:
   - 명령: `python tools/route_coverage.py --served src/saintvision --served services/control-plane/src --client apps/web/src`
   - 결과: 미제공 6개 → **1개** (`/v1/workspaces`, `_CLIENT_HEAD` 정규식 도구 아티팩트)
4. **문서 및 온톨로지 무결성**:
   - 명령: `python tools/check_docs.py`
   - 결과: **PASS** (555 versioned documents)
