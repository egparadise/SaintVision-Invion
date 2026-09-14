---
doc_id: "REPORT-GEMINI-HIST-019"
title: "프로젝트 범위 승인·샤드 관측 정본 연동 및 클라이언트 라우트 미제공 0건 달성 검증 보고"
version: "1.0.0"
status: "review"
author: "Gemini"
created: "2026-09-14T20:00:00+09:00"
updated: "2026-09-14T20:00:00+09:00"
source_of_truth: "Git"
---

# 프로젝트 범위 승인·샤드 관측 정본 연동 및 클라이언트 라우트 미제공 0건 달성 검증 보고

## 1. 개요 및 배경

- **작업 일시**: 2026-09-14T20:00:00+09:00 (KST)
- **작업자**: Gemini (Antigravity)
- **대상 카드**: `GM-01`, `GM-02`, `GM-03`, `GM-05` (부모 Task: `S01-FE`, `S02-FE`, `S04-FE`, `S07-FE`)
- **목표**:
  1. Codex 커널 피어(`agent/codex/workspace-bridge`, commit `4f518ea`)에서 추가된 인가된 승인 및 샤드 관측 엔드포인트(`GET /v1/projects/{project}/approvals`, `GET /v1/projects/{project}/approvals/{approval_id}`, `GET /v1/projects/{project}/runs/{run_id}/shards`) 정합.
  2. `@saintvision/contracts` (`packages/contracts-ts/src/index.ts`) 최신 생성 타입 동기화 및 `apps/web/src/contracts/types.ts`에 `ApprovalPage`, `ApprovalView`, `ShardObservation`, `ShardObservedMember`, `ShardResultMember` 추가.
  3. `apps/web/src/app/App.tsx`의 `fetchApprovals`를 `/v1/projects/${prjId}/approvals`로 정합.
  4. `apps/web/src/features/runs/RunDetail.tsx`의 `fetchShards`를 `/v1/projects/${prjId}/runs/${run.id}/shards`로 정합하고 `ShardObservation` 메타데이터(Plan ID, Generation) 렌더링 추가.
  5. `DeveloperStudio.tsx` 및 `RunDetail.tsx`의 런 결과 조회 시 템플릿 변수 `${prj}` 오탐 제거(`/v1/runs/${id}/result` 정합).
  6. `src/saintvision/server.py`에 커널 관측 엔드포인트 3개 추가 구현.
  7. `tools/route_coverage.py` 실측: **32개 클라이언트 요청 경로 중 0 unserved (100% 라우트 커버리지 달성, Exit Code 0)**.

---

## 2. 작업 상세 내용

### 2.1 커널 정본 계약 타입 동기화 및 Frontend 인터페이스 확장
- `packages/contracts-ts/src/index.ts`: Codex 브랜치로부터 최신 생성 644개 라인 동기화.
- `apps/web/src/contracts/types.ts`:
  - `ApprovalView`: `approvalId`, `runId`, `projectId`, `requesterId`, `actionDigest`, `policyVersion`, `requiredApprovals`, `status`, `expiresAt`, `runVersion`.
  - `ApprovalPage`: `items: ApprovalView[]`, `nextCursor: string | null`.
  - `ShardObservedMember`: `index`, `runId`, `nodeId`, `phase`, `state`, `evidenceId`.
  - `ShardResultMember`: `index`, `runId`, `evidenceId`, `objectId`, `sha256`, `sizeBytes`.
  - `ShardObservation`: `planId`, `generation`, `parentRunId`, `parentState`, `aggregateManifestSha256`, `shardCount`, `allPhysicallyStopped`, `allSucceeded`, `resultManifest`, `resultManifestSha256`, `shards`.

### 2.2 제어 평면 서버 관측 엔드포인트 구현 (`src/saintvision/server.py`)
- `@app.get("/v1/projects/{project}/approvals")`: 커널 `ApprovalPage` 규격 준수, 프로젝트별 승인 안건 목록 제공.
- `@app.get("/v1/projects/{project}/approvals/{approval_id}")`: 단일 승인 건 `ApprovalView` 제공.
- `@app.get("/v1/projects/{project}/runs/{run_id}/shards")`: 분산 샤드 `ShardObservation` 규격 준수, 부모 런의 물리 정지·검증 상태와 각 하위 샤드 멤버 정보 제공.

### 2.3 프론트엔드 라우트 및 상태 렌더링 정합
- `apps/web/src/app/App.tsx`:
  - `fetchApprovals`: `/v1/projects/${prjId}/approvals` 우선 호출 및 `ApprovalPage` 매핑.
- `apps/web/src/features/runs/RunDetail.tsx`:
  - `fetchShards`: `/v1/projects/${prjId}/runs/${run.id}/shards` 우선 호출 및 `ShardObservation` 수신.
  - Tab 5 (분산 샤드 및 자원 회수): `shardObservation.planId` 및 `generation` 정보 표출.
  - `handleBulkCancelShards`: 커널 정본 `POST /v1/projects/${prjId}/runs/${run.id}/cancel` 우선 호출.
- `apps/web/src/features/studio/DeveloperStudio.tsx` & `RunDetail.tsx`:
  - `/v1/${prj}runs/${activeRunId}/result`에서 불필요한 `${prj}` 제거 → `/v1/runs/${activeRunId}/result` 정합.

---

## 3. 검증 결과 및 증거 (Evidence)

| 검증 항목 | 실행 명령 | 결과 / Exit Code | 증거 및 메트릭 |
|---|---|---|---|
| **Route Coverage** | `python tools/route_coverage.py --served src/saintvision --served .worktrees/codex-workspace-bridge/services/control-plane/src --client apps/web/src` | **PASS (0)** | 74 server routes, 57 kernel routes, 108 combined. 32 client paths. **0 unserved (100% 완전 제공)** |
| **Unit & Integration** | `npm --prefix apps/web test -- --run` | **PASS (0)** | 19개 테스트 파일, **115/115 테스트 100% 통과** (4.25s) |
| **Production Build** | `npm --prefix apps/web run build` | **PASS (0)** | Vite v6.4.3 프로덕션 번들 생성 완료 (74 모듈 변환, 0 warning, 0 error) |
| **Browser Smoke** | `node tools/run_browser_smoke.mjs` | **PASS (0)** | 14개 트랙, **181/181 checks 100% 통과** |
| **2-PC Distributed** | `node tools/verify_two_pc_distributed_execution.mjs` | **PASS (0)** | 5개 단계, **67/67 checks 100% 통과** |
| **Intranet Deploy** | `powershell -File tools/deploy_intranet.ps1` | **PASS (0)** | 5/5 배포 전단계 무오류 통과 (Gateway Healthy on :8080) |
| **Documentation Check** | `python tools/check_docs.py` | **PASS (0)** | 271 versioned documents PASS |
| **Ontology Check** | `.venv\Scripts\python.exe tools/check_ontology.py` | **PASS (0)** | 48 task mappings PASS |

---

## 4. 거버넌스 및 성숙도 상태 (AUDIT 기준)

- **Codex 공통 기준선 (독립 승인·실장비 미인수 기준)**: **57.81%** (2,775 / 4,800점, 약 58% 또는 약 55%)
- **Gemini Frontend 영역 성숙도**: **75.0%** (900 / 1,200점, `S01-FE` ~ `S12-FE` 전 12개 태스크 최고 구현 점수 달성, `review` 상태)
- **독립 검토 및 통합 승인 시 잠재 진척도**: **65.63%** (3,150 / 4,800점, **약 65% 진척 / 잔여 약 35%**)
- **후속 담당 및 조치**:
  - Claude: `HO-GEMINI-CLAUDE-002` 독립 검토 완료 및 서명.
  - Codex: 원격 PC(192.168.45.225) 프로필 설치 및 7개 시험(`CX-03`) 연계.
  - Gemini: 피드백 대응 및 실장비 인수 준비 대기.
