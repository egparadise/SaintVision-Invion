---
doc_id: "CODEX-WORKSPACE-API-001"
title: "Codex Workspace 공개 API와 실행 커널 통합 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T12:12:00+09:00"
source_of_truth: "Git"
---

# Workspace 공개 API와 실행 커널 통합

Task WORKSPACE-API, owner Codex, independent reviewer Claude pending. S03-BE 및 S06-BE/DB/ST, OUT-03/06/07과 AC-03/06/07 후속이다. PR #13은 #12 위의 draft다. GUIDE-001/GOV-AGENT-001/GOV-GIT-001/task-registry 및 agent-delivery/core-reliability v1.0.0, ADR-044/045를 따른다. 실행 결과는 History의 고정 SHA와 artifact를 기준으로 판단한다.

## ADR-046: 실행 상태의 권위와 원자적 공개 admission

실행 Run·Approval·Lease·Evidence의 공개 API는 `inv` kernel의 행을 읽고 변경한다. `public` 업무 테이블과 메모리 fixture를 동시에 실행 권위로 사용하지 않는다. public schema의 Context/Pool 등 보완 서비스 통합 및 기존 중복 11개 개념의 이관은 별도 작업이다. 현재 변경은 public 데이터를 inv로 복사하거나 자동 이관하지 않는다.

`inv.app`의 실제 JWT resource-server 인증, 현재 project grant, tenant RLS, recovery epoch, 요청 크기/Origin/멱등성 경계를 재사용한다. 브라우저가 policy decision·승인자 목록·Node 인증·lease/fence·서명키를 제공할 수 없다. 입력은 고정할 checkout/Step/Workload 의도와 Run version이다. GPU·host access·네트워크·privileged 실행은 이 제한 profile에서 허용하지 않는다.

prepare는 private working-root lock 아래 동일 transaction에서 현재 권한·Run version·물리 자원 반환을 확인하고 실제 파일 snapshot과 새 approval을 함께 생성한다. 실패하면 frozen row와 approval 모두 rollback된다. 모든 협력 editor writer는 같은 root lock을 사용해야 한다. 다른 writer의 동작을 API가 대신 정지시켰다고 주장하지 않는다. 이후 편집은 frozen 입력에 영향을 주지 않는다.

enqueue는 프로젝트 권한을 검사한 후 mTLS nonce probe를 수행한다. 네트워크 I/O 중에는 실행 transaction을 유지하지 않는다. 마지막 transaction에서 Run version·현재 요청자/승인자 권한·승인 quorum/expiry·epoch·Node/자원을 재검사하고 approval dispatch·lease·claim·서명 permit queue를 함께 확정한다. 등록 실패는 승인 소비와 새 예약을 모두 되돌린다. 네트워크 전 멱등 ledger의 빈 slot은 남을 수 있지만 실행 권한이나 자원은 없다.

API는 `202 accepted`만 반환한다. DB는 `scheduled` 상태이며 Node/worker가 실제 실행을 시작한 뒤 `running`으로 바뀐다. 미승인은 기존 AUTH-0031 계약의 403이다. 현재 version/멱등 내용 충돌은 409다. 응답을 잃은 재요청은 같은 command의 관찰이며 Node가 offline이어도 재실행하지 않는다. replay에서도 현재 프로젝트 권한을 확인한다.

## Claude·Gemini 연결 계약

모든 mutation은 `Authorization: Bearer ...`, `Content-Type: application/json`, ASCII `Idempotency-Key`가 필요하다. 식별자는 공통 schema 형식을 따르며 기존 demo의 `run_01` 같은 임의 문자열을 사용할 수 없다. tenant는 서버에 고정한 JWT 검증 설정에서 얻는다.

| 경로 | 요청·응답 계약 | 동작 |
|---|---|---|
| POST `/v1/projects/{project}/runs/{run}/resume/prepare` | WorkspacePrepareInput → WorkspacePrepareResult | `checkoutId,resumeId,stepId,workload,expectedVersion`; 201 및 새 approval/Run version |
| GET `/v1/projects/{project}/runs/{run}/resumptions/{resume}` | WorkspaceResumptionView | 고정 Workload·실제 파일 path/size/hash·현재 approval/Run; 파일 본문 미포함 |
| POST `/v1/projects/{project}/approvals/{approval}/challenge` | EmptyRequest → ApprovalChallenge | distinct approver의 짧은 nonce |
| POST `/v1/projects/{project}/approvals/{approval}/decision` | ApprovalDecisionInput → ApprovalView | `decision,nonce,actionDigest`; 두 승인자의 개별 JWT·멱등 key |
| POST `/v1/projects/{project}/runs/{run}/resume/enqueue` | WorkspaceEnqueueInput → WorkspaceEnqueueResult | `resumeId,approvalId,expectedVersion`; 202 및 실제 commandId |
| GET `/v1/projects/{project}/runs/{run}` 및 `/events` | 기존 Control API | 실제 DB 상태, 자원 반환 pending, commit 순서 SSE |

요청/응답 정본은 `contracts/v1alpha1/core.schema.json`, Python/TS/Go는 생성본이다. prepare가 돌려준 새 Run version을 enqueue에 사용한다. approval vote는 Run version을 증가시키지 않는다. GET은 저장된 현재 상태를 조회하며 prepare/accepted replay의 과거 응답을 현재 실행 상태로 간주하지 않는다.

Gemini의 화면·브라우저 fixture 및 기존 `/v1/runs/...` 경로는 이 project-scoped 계약에 연결해야 한다. 서버에서 승인이 실패한 뒤 화면만 승인/실행으로 전환하는 fallback과 무작위 heartbeat를 실측으로 표시하는 부분은 제거 대상이다. 이번 통합의 Frontend 변경은 기존 타입/미사용 변수 빌드 오류 수정이다. 실제 브라우저 실행 여정 완료를 뜻하지 않는다.

## ADR-047: 배포 진입점과 migration 연결

`saintvision.server:create_app --factory`는 명시적 설정으로 `inv.app.create_configured_app`을 생성한다. 예전 seeded 메모리 서버는 `saintvision.demo_server`로 이동했다. production은 demo로 자동 fallback하지 않으며 설정 누락이면 시작을 거부한다. Docker image는 Python 3.12, 비root UID/GID 65532, inv source/전체 requirements를 포함하고 proxy-header 신뢰를 기본 차단한다. build context는 허용한 소스만 포함한다.

0019 merge revision은 공개된 Codex `0018_workspace_resume`와 Claude `0010_canonical_resource_units`의 부모를 변경하지 않고 합친다. empty DB 및 양쪽 기존 head에서 통합 head로 upgrade, 반복 upgrade를 시험한다. backward downgrade는 거부하며 검증된 restore와 forward fix를 사용한다. 운영 DB에 적용한 기록은 아직 없다.

0019의 `inv_kernel`은 비특권 NOLOGIN 그룹 역할이다. 운영자는 별도의 NOBYPASSRLS/non-owner LOGIN에 membership을 부여하고 비밀 저장소에서 연결 정보를 공급한다. epoch·project 권한·Node 인증 channel의 권위 있는 열은 runtime에서 변경하지 못한다. immutable Evidence/승인 기록은 수정·삭제를 허용하지 않는다. kernel 통합 시험은 별도 시험용 GRANT 목록 대신 실제 migration 그룹 권한을 사용한다.

## 운영 설정과 제한

`INV_API_CONFIG`는 operator-owned JSON 파일 경로이며 기존 `identity`, 선택적 `allowedOrigins`, 선택적 `workspace`를 받는다. DB/epoch는 `INV_RUNTIME_DSN`, `INV_RECOVERY_EPOCH`다. workspace가 없으면 일반 Control API만 제공하고 재개 요청은 503이다. workspace 객체는 다음 항목을 모두 명시한다.

- `workingRoot`: 기존 복원 checkout의 private Linux absolute root. 서비스 UID 소유이며 협력 writer만 접근한다.
- `nodeId`, `resources`: 등록된 Node와 `cpu`,`memory` 자원 ID. CPU 단위는 millicores, memory 단위는 bytes다. public ram/disk 자동 이름 변환이나 pool 배치로 간주하지 않는다.
- `profile`: SandboxProfile의 `version`, `images`(sha256 고정 digest 배열), `executables`(절대 container 경로 배열), 선택적 max_cpu_millis/max_memory_bytes/max_timeout_seconds.
- `policyVersion`: 운영자가 승인한 제한 Workspace 정책 버전. 고정 L2·distinct 2인 승인·10분 approval이며 admission에서는 30초 이하의 새 정책 snapshot을 사용한다. 일반 OPA/ROOF 전체 평가기를 대체하지 않는다.
- `signingKeyFile`: Node trust에 등록된 Ed25519 private key 파일. HTTP로 전달하지 않으며 private 권한이 필요하다.
- `tls`: NodeTLSClient의 `ca_file`, `certificate_file`, `key_file`, 선택적 timeout. endpoint/peer pin은 기존 DB channel 등록을 사용한다.

probe는 현재 mTLS 신원·epoch·profile을 확인한다. profile은 설치한 제한 Node agent에 대한 운영자의 신뢰 설정이며 heartbeat만으로 Windows/GPU/BuildKit 격리 능력을 인증하지 않는다. 각 Node는 launch 시 실제 제한을 다시 적용한다.

실행 worker는 별도 `INV_WORKER_CONFIG`의 tenantId/tls/outputRoot로 기동해야 한다. readiness는 API 설정을 확인하며 worker 가동/운영 인수를 보장하지 않는다. tenant/project/현재 grant·Node channel·resource·기존 recovering Run/checkout은 선행 설정이다. 이번 API는 첫 Run 계획 생성, checkout 공개 편집/PTY 세션, 기존 public 데이터 이관을 새로 구현하지 않는다.

한도는 ADR-044/045의 파일 총합 32 KiB, manifest 64 KiB, 제한 sandbox timeout, 최초 포함 최대 3 attempt다. API body는 기존 64 KiB 이내다. 대용량·장시간 실행·PTY·remote Git·샤드 재실행/다중 Node/collective·5대 장비는 별도다.

Claude: 독립 보안/transaction/DB 검토 및 public 보완 서비스의 권위·ID·단위 이관 설계. Gemini: 새 계약을 사용하는 실제 인증·승인·조회 화면과 브라우저 검증. Codex: 이어서 shard retry/교체·다중 Node 및 운영 복구를 구현한다. 외부 메시지 발송이나 다른 Agent의 검토 완료를 대신 기록하지 않는다.
