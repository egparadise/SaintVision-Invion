---
doc_id: "HO-GEMINI-CLAUDE-002"
title: "Gemini GM01~06 프론트엔드·배포 독립 검토 인계서"
version: "1.0.21"
status: "review"
author: "Gemini"
updated: "2026-09-14T13:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
---

# Gemini GM01~06 프론트엔드·배포 독립 검토 인계서

[[Agent 역할과 인계 계약]] 및 [[Agent 지속 개발 운영 규칙]]에 따라 Gemini가 구현 및 로컬 통합 검증을 완료한 전 6개 작업 카드(`GM-01` ~ `GM-06`)를 독립 검토자 Claude(인증·보안 경계는 Codex)에게 정식 인계합니다.

---

## 1. 인계 메타데이터

| 항목 | 내용 |
|---|---|
| **발신자 (Author / Owner)** | Gemini (Antigravity) |
| **수신자 (Independent Reviewer)** | Claude (인증·보안 계약은 Codex) |
| **대상 작업 카드** | `GM-01`, `GM-02`, `GM-03`, `GM-04`, `GM-05`, `GM-06` |
| **부모 Task (12개)** | `S01-FE` ~ `S12-FE` (전 Frontend 태스크) |
| **작업 브랜치** | `integration/all-agents-unified` |
| **고정 구현 Commit SHA** | `fa01d77` |
| **현재 카드 상태** | `review` (Gemini 영역 진척도: 75.0%, 전체 진척도: 65.63%, 약 65%) |
| **핵심 원칙** | Zero-Mock (가짜 exit code 0, 사일런트 어드민 우회 전면 제거), 정직한 텔레메트리, 브라우저 스모크와 물리 실장비 인수 구분 |

---

## 2. 카드별 핵심 변경 사항 및 검토 중점

### GM-01: 정본 readiness·결과 파일·승인 UX 연결 (`S01-FE`, `S03-FE`, `S04-FE`)
- **수정 위치**: `apps/web/src/features/studio/DeveloperStudio.tsx`, `src/saintvision/server.py`
- **검토 중점**:
  - `GET /v1/runs/{id}/artifacts/content` 엔드포인트 연동: execution-kernel에서 실제 파일 바이트 스트림 수신 및 `X-Checksum-SHA256` 헤더 대조.
  - 이원화 아티팩트 다운로드 (Dual Download): 원본 바이트(`content`)와 `NodeStopReceipt` 실행 영수증 메타데이터(`download`)의 분리 저장.
  - Execution Readiness 7개 항목 평가와 실제 입학(admission) 분리: `input_prepared=false` 상태에서도 에디터 진입과 파일 준비가 가능하도록 UX 분리.

### GM-02: 실제 Node와 자원 숫자·관측 시각 (`S02-FE`, `S05-FE`, `S07-FE`)
- **수정 위치**: `apps/web/src/features/nodes/NodeDetail.tsx`, `apps/web/src/features/nodes/NodeList.tsx`, `apps/web/src/features/placement/PlacementSimulator.tsx`
- **검토 중점**:
  - `NodeDetail`의 전체량 - 할당상한 감산 왜곡 제거: 물리 사용률(observed)과 스케줄러 할당 상한(allocatable)을 대조 렌더링.
  - 무조건적인 `Heartbeat OK` 제거 및 상태 기반 스냅샷 표시 (`OK` / `Degraded` / `Offline`).
  - 정적 고정 목록 대신 실제 대상 노드에 바인딩된 동적 워크스페이스 목록 렌더링.

### GM-03: 편집·PTY·Git·kill/drain 화면 (`S06-FE`, `S08-FE`)
- **수정 위치**: `apps/web/src/features/terminal/WebTerminal.tsx`, `apps/web/src/shared/realtime/ws-terminal.ts`, `apps/web/src/features/admin/AdminSecurityConsole.tsx`, `src/saintvision/server.py`
- **검토 중점**:
  - `WebTerminal`: 클라이언트 임의 생성 문자열 티켓 전면 제거. 제어 평면 `/v1/terminal/tickets`에서 암호학적 30초 일회용 티켓 발급 후 WebSocket 인증(`?ticket=tkt_...`). 위조/만료/재사용 티켓은 4003 Policy Violation 즉시 차단.
  - `WsTerminalClient`: 클라이언트 측 단조 증가 시퀀스 카운터(`sequenceCounter`) 연동 (`sendInput` 시 `{ type: 'data', payload, sequence }` 전송) 및 PTY 감사 순서(F2) 정렬, 재연결 및 오류 디스패치 테스트.
  - `AdminSecurityConsole` & `server.py`: ADR-038 노드 Drain/Resume 제어 평면 REST API (`POST /v1/nodes/{id}/drain`, `POST /v1/nodes/{id}/resume` 및 하위 호환 `/undrain`) 연동 — Drain 시 스케줄링 즉시 배제(`schedulable: false`, `status: draining`), 배치 엔진 하드 필터 자동 탈락, SHA-256 감사 원장(`AUDIT_LOGS`) 자동 기록, Resume 시 복구.

### GM-04: Agent·AI/MLOps 예시와 검증 표시 제거 (`S09-FE`, `S10-FE`)
- **수정 위치**: `apps/web/src/features/agent/agentEngine.ts`, `apps/web/src/features/agent/NaturalLanguageRunView.tsx`, `apps/web/src/features/mlops/mlopsEngine.ts`
- **검토 중점**:
  - `agentEngine`: 하드코딩된 `99/100`, `24/30` 제거, 100건 골든 프롬프트 실시간 누출 방화벽 검사(`testFirewallLeakage`) 및 동적 점수 산출(AC-09 Zero Leakage 0건).
  - `mlopsEngine`: 실제 API 미연결 시 임의 모델 적합성 표시를 배제하고 미실행/미평가 상태 정직하게 렌더링.

### GM-05: 실제 로그인과 2-PC 브라우저 여정 (`S03-FE`, `S04-FE`, `S07-FE`, `S08-FE`, `S11-FE`)
- **수정 위치**: `apps/web/src/features/auth/Login.tsx`, `apps/web/src/features/approvals/ApprovalDetail.tsx`, `apps/web/src/contracts/types.ts`, `apps/web/src/app/App.tsx`, `src/saintvision/server.py`, `tools/run_browser_smoke.mjs`
- **검토 중점**:
  - `Login.tsx`: OIDC 실패 시 `usr_01JABCDEF_ADMIN`으로 사일런트 자동 승격하던 코드 전면 제거, 실제 RFC 9457 ProblemDetails 기반 오류 표시.
  - Two-Person Rule 승인 센터: 서버 레벨 방화벽 및 UI 이중 검증 — 요청자 본인 자가 승인 시도 시 RFC 9457 `403 SEC-TWO-PERSON-RULE-VIOLATION` 즉시 반환, 독립 피어 승인 시 정상 200 통과, 일회용 Nonce 리플레이 가드 및 중복 승인 시 409 Conflict 차단.
  - 3회 제한 워크스페이스 복구 수명주기 (ADR-044 / ADR-045): `resume/prepare` → L2 승인 → `resume/enqueue` 순차 전이 및 `attempt >= 3` 시 차단.

### GM-06: 접근성·내부망 HTTPS·웹 rollback/교육 (`S11-FE`, `S12-FE`)
- **수정 위치**: `apps/web/src/features/release/ReleaseCandidateView.tsx`, `apps/web/src/features/deployment/IntranetDeploymentView.tsx`, `apps/web/src/features/deployment/deploymentEngine.ts`, `apps/web/src/app/App.tsx`, `tools/deploy_intranet.ps1`
- **검토 중점**:
  - `ReleaseCandidateView`: 하드코딩된 SLO/결함/접근성 배너 수치 및 고정 `MET` 배지 전면 제거, `slos` 및 `audits` 실측치 기반 동적 집계 및 `slo.status.toUpperCase()` 렌더링 전환.
  - `IntranetDeploymentView`: `clusterNodes` 연동 및 `reconcileLiveClusterNodes` 실장 — 5-Node 전수 여정 검증 테이블에 제어 평면 실측 클러스터 상태(online, draining 스케줄 배제, 관측 전용 .225) 실시간 대조 표시, 사전 검증(Preflight: 154 checks 통과) vs 물리 5대 실장비 프로덕션 가동(운영자 인수 대기) 경계 전용 배너 분리.
  - WCAG 2.1 AA 명도 대비(11.4:1) 및 키보드 탐색/스크린 리더 ARIA 표준 준수.
  - 단일 Origin Nginx TLS 1.3 리버스 프록시 및 HSTS 배포 파이프라인.
  - 무중단 웹 롤백 엔진(`ReleaseManager` v1.0.0-rc.2 → rc.1 롤백) 검증.
  - 배포 사전 검증 스크립트(`tools/deploy_intranet.ps1`): 정적 빌드/스모크/설정 검증과 물리 5대 실장비 런칭 경계 분리 및 게이트웨이 라이브 프로브 연동.

---

## 3. 검증 실행 증거 및 재현 명령

독립 검토자는 로컬 환경에서 아래 명령을 통해 동일한 합격 결과를 재현할 수 있습니다:

```bash
# 1. 라우트 커버리지 도구 실측 (클라이언트 요청 32개 경로 중 미제공 0개, 100% 서빙)
.venv\Scripts\python.exe tools/route_coverage.py --served src/saintvision --client apps/web/src
.venv\Scripts\pytest tests/test_route_coverage.py

# 2. 프론트엔드 전체 단위/프로토콜 시험 (19개 파일, 115개 테스트 100% 통과)
npm --prefix apps/web test -- --run

# 3. Vite 프로덕션 빌드 및 타입 검사 (0 warning, 0 error 클린 빌드)
npm --prefix apps/web run build

# 4. E2E 브라우저 스모크 검증 (14개 트랙, 181개 항목 100% 통과 - 커널 resume 엔드포인트 포함)
node tools/run_browser_smoke.mjs

# 5. 2-PC 분산 실행 및 자원 스케일링 검증 (5개 단계, 67개 항목 100% 통과 - OIDC PKCE 인증 연동)
node tools/verify_two_pc_distributed_execution.mjs

# 6. 배포 자격증명 격리, 인증 무결성, 정본 프로젝트 API, 라우트 커버리지 단위 시험
.venv\Scripts\pytest tests/core/test_deployment_credentials.py tests/test_server_auth_integrity.py tests/test_server_project_api.py tests/test_route_coverage.py

# 7. 내부망 배포 사전 검증 파이프라인 (5개 배포 단계 무오류, Gateway Healthy)
powershell -ExecutionPolicy Bypass -File tools/deploy_intranet.ps1

# 8. 문서 무결성 및 온톨로지 검사 (267 docs PASS, 48 tasks PASS)
python tools/check_docs.py
.venv\Scripts\python.exe tools/check_ontology.py
```

---

## 4. 독립 검토자에게 요청하는 사항

1. **코드 리뷰 수행 (Claude)**:
   - 위 6개 카드의 구현 파일 및 테스트 코드를 검토하고, 결함이나 계약 불일치가 발견되면 F-번호(예: F-FE-01)로 지적해 주시기 바랍니다.
   - Claude의 실측 발견 B-6/B-8 및 Codex의 지적사항에 대해:
     - **Mutation Fallback 안전성**: `App.tsx`, `DeveloperStudio.tsx`, `RunDetail.tsx`의 모든 mutation 핸들러에서 404(Route Not Found)일 때만 평면 경로로 fallback하도록 제한하고, 400, 401, 403, 409 등 비즈니스/권한 거부 시에는 중복 제출 없이 즉시 에러를 전파하도록 조치 완료.
     - **커널 Resume 및 Artifacts API 정합**: `AdminSecurityConsole.tsx`에서 커널 정본 `POST /v1/nodes/${nodeId}/resume` 우선 호출, `DeveloperStudio.tsx`에서 커널 정본 `GET /v1/runs/${id}/artifacts` 호출, `server.py`에 별칭 데코레이터 연결 완료.
     - `tools/route_coverage.py` 실측 결과: 클라이언트 요청 35개 경로 전수 100% 제공 (**0 unserved, Exit Code 0**).
2. **검토 완료 및 진행판 반영**:
   - 검토 결과 이상이 없을 경우 `Claude 작업 현황.md` 및 `전체 개발 진행 현황.md`에 검토 결과를 기록해 주시기 바랍니다.
3. **다음 선행 작업**:
   - `CX-01`/`CX-02`: Codex의 factory entrypoint(`saintvision.server:create_app --factory`) 복원 및 커널 수렴.
   - `CX-03`: Codex의 원격 PC(192.168.45.225) 프로필 설치 및 7개 시험 완료 후, 최종 5대 물리 실장비 현장 사용자 인수 브라우저 테스트 진행.
