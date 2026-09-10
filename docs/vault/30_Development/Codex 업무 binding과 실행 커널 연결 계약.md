---
doc_id: "CODEX-BUSINESS-KERNEL-001"
title: "Codex 업무 binding과 실행 커널 연결 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T13:57:52+09:00"
source_of_truth: "Git"
---

# 업무 binding과 실행 커널 연결

owner Codex, reviewer Claude pending. task BUSINESS-KERNEL, S03/S04/S06/S11 부분 인계다. PR14 `c06f59c87c16ebbbc32459a3116ee9144e9cd6bf`의 업무 흐름을 PR15 `4290467fec203c0e8f290bd816c5d30ca1bd34bd`의 실제 실행 커널에 맞춰 구현한다. [[PR14 업무 연결과 실행 커널 통합 선행 검토]]의 보안·무결성 경계를 해결하며, PR14 전체 Git merge나 타 Agent 독립 검토 완료를 뜻하지 않는다.

## ADR-050: binding의 권위는 실제 실행 기록

`public.execution_bindings`는 Run·편집 lock·실제 resumption·새 Approval의 불변 참조다. 변경 가능한 `state` 열이 없다. 응답의 frozen/approved는 실제 approval, queued/executing은 실제 delivery, settled는 실제 정지 영수증과 결과 확정에서 계산한다. `run` 필드는 `inv.runs`의 현재 상태다. `public.runs.state`는 자동 실행 정본으로 취급하거나 클라이언트 입력으로 동기화하지 않는다.

`executing`은 전달 처리가 진행 중이라는 뜻이며 Node가 실행을 수신했다는 확인과 구분한다. `deliveryPhase=uncertain`이면 전송을 예약했지만 물리 실행 여부가 아직 확인되지 않은 상태다. `executionConfirmed`는 실제 stop receipt의 processStarted가 확인된 경우만 true다. 화면은 불확실한 전달을 확정된 물리 실행으로 표현하지 않는다.

`public.workspace_edit_locks`는 서버가 실제 checkout 파일을 읽어 계산한 hash/크기·epoch·Run version·소유 주체를 고정한다. prepare에서 다시 캡처한 바이트가 다르면 resumption/approval/binding을 모두 rollback한다. prepare는 두 명의 서로 다른 승인자가 필요한 새 Approval을 같은 transaction에서 만든다. 기존 public approval의 `apv_`를 일괄 `apr_`로 바꾸지 않는다. 실제 kernel Approval ID만 새 binding에 연결한다.

enqueue 직전 현재 업무 scope·requester/voter 권한·Run version·approval·Node membership·policy·epoch를 검사한다. mTLS 관측 중에는 DB 잠금을 보유하지 않으며, 관측 후 최종 transaction에서 다시 검사한다. 승인 소비·Lease·fence·claim·queue가 한 번에 확정되거나 전부 rollback한다. 연결된 Run의 독립 prepare/dispatch/reserve/claim 우회는 내부 admission 표시가 없으면 거부한다.

실행 전 취소하고 command가 발급되지 않았다면 영수증을 꾸미지 않고 lock을 해제할 수 있다. command가 있으면 실제 stop receipt·미반환 Lease 부재가 필요하며, 성공은 해당 command의 result completion/Evidence까지 필요하다. Run 종료와 마지막 Lease 반환 시 DB trigger가 이 조건을 다시 확인하고 자동 해제한다. 이 정리에는 철회된 requester의 권한을 재사용하지 않는다. 수동 release/reconcile은 현재 Project 권한과 lock 소유자를 확인한다.

파일 snapshot은 불변 입력을 제공한다. 편집 lock은 제품 writer가 따라야 하는 서비스 계약이다. 현재 임의 외부 편집기·PTY를 OS 수준에서 정지시켰다는 보장은 하지 않는다. stop과 prepare 사이 외부 파일 변경은 hash 불일치로 거부하며, prepare 후 승인된 실행은 고정 바이트만 사용한다. 후속 editor/PTY writer도 같은 Workspace 잠금 규약을 적용해야 한다.

## ADR-051: 명시적 identity 연결과 forward migration

canonical 기존 `0008_node_certificate_lookup`, `0009_idempotency_and_inbox_scope`, `0010_canonical_resource_units`와 `0019_workspace_api_integration` merge, `0020_shard_recovery`를 유지하고 `0021_business_kernel`을 추가한다. 빈 DB 및 canonical 0018·0010·0019·0020에서 upgrade/replay를 시험한다.

PR14의 별도 실험 graph `0019_node_certificate_lookup → 0020_idempotency_and_inbox_scope → 0021_canonical_resource_units → 0022_inv_application_grants → 0023_execution_handoff → 0024_initial_recovery_epoch`는 그대로 병합하지 않는다. 그 실험 graph를 이미 적용한 DB를 canonical head로 자동 stamp/변환하지 않는다. 운영 이관은 실제 revision/schema/data를 보존한 별도 변환 계획·backup 검증이 필요하다. 이 작업은 운영 DB나 기존 업무 approval ID를 수정하지 않았다.

운영자는 검증한 기존 행을 사용해 아래 연결을 등록한다. HTTP는 연결을 생성하거나 토큰의 role claim으로 권한을 부여하지 않는다.

| 연결 | 불변 식별자와 검사 |
|---|---|
| inv.business_projects | 같은 tenant/project의 public Project와 inv Project; enabled와 현재 public active 상태 |
| inv.business_subjects | `oidc:` + SHA-256(JSON `[issuer,sub]`)와 public user ID; tenant 안에서 subject와 user 모두 UNIQUE, identity 변경/삭제 거부·disable 허용 |
| inv.business_runs | 같은 Run ID의 public/inv 행과 Workspace; 현재 public Run→Workload/Workspace→Project 일치 확인 |

연결된 Project의 모든 Control/Approval 경계는 기존 `inv.project_grants`와 현재 `public.project_members` 권한의 교집합을 사용한다. requester 역할은 owner/maintainer/operator, approver는 owner/approver다. 사용자 suspended/retired, project archived, mapping disabled, membership 삭제·변경을 현재 transaction에서 거부한다. 한 사람을 두 OIDC subject로 중복 매핑해 두 표로 계산하지 않는다. kernel 전용 미연결 Project는 기존 grant 계약을 유지한다.

`inv_kernel`은 NOLOGIN/nonowner/NOBYPASSRLS 그룹을 유지한다. 업무 identity/membership는 필요한 열의 SELECT와 CHECK 고정 sentinel UPDATE만 부여한다. mapping INSERT/identity UPDATE, public Run state UPDATE, epoch UPDATE는 부여하지 않는다. `inv_app`에는 inv schema 접근을 확대하지 않으며 새 public lock/binding은 SELECT만 가능하다. 모든 새 tenant 행은 FORCE RLS를 적용한다. epoch·LOGIN secret은 migration에서 생성하거나 변경하지 않는다.

## ADR-052: 최초 전송 전 권한 상실은 취소 영수증으로 정리

queued 명령의 현재 승인·권한·fence가 무효라면 Run을 failed로 전이하고 Node cancel 경로로 미수신 tombstone 또는 정지 영수증을 얻는다. 미수신 명령을 observe로만 반복하지 않는다. Lease와 편집 lock은 영수증과 정확한 자원 반환을 확인할 때까지 유지한다. cancel 전달이 불확실하면 계속 같은 command를 취소하며 execute로 돌아가지 않는다. 이미 전송 예약을 한 일반 crash는 기존 관찰 복구를 유지한다.

Node heartbeat/snapshot의 인증된 429는 관측 전용 retryable 오류로 구분한다. 현재 관측은 superseded 응답과 capacity 응답에만 새 nonce로 총 3회(재시도 간격 10/20ms) 제한을 적용한다. 인증·epoch 거부와 실행 요청은 자동 재전송하지 않는다. 이는 전체 실행의 최대 3세대와 별개의 관측 상한이다.

## 공개 API

기존 production `saintvision.server:create_app → inv.app.create_configured_app`에서 제공한다. operator Workspace 설정이 있어야 한다. 실제 JWT와 현재 DB 권한을 사용하며 client policy/Node key/lease/epoch를 받지 않는다. request/response의 정본은 core JSON Schema와 생성 Python/TS/Go다.

| 경로 | 계약 |
|---|---|
| GET /v1/projects/{project}/permission | 현재 업무 역할과 kernel grant를 확인한 권한 |
| POST /v1/workspaces/{workspace}/edit-lock | BusinessEditLockInput: projectId, runId, checkoutId, expectedVersion; 서버 캡처 hash 반환 |
| POST /v1/runs/{run}/bindings | BusinessBindingInput: projectId, lockId, prepare(WorkspacePrepareInput); 새 실제 Approval 포함 BusinessBindingView |
| POST /v1/projects/{project}/approvals/{approval}/challenge, /decision | 기존 nonce·distinct voter 계약으로 투표 |
| POST /v1/bindings/{binding}/approval | BusinessApprovalInput의 ID가 실제 현재 quorum인지 확인만 함. 임의 approval 부착·승인 생성이 아님 |
| POST /v1/bindings/{binding}/enqueue | EmptyRequest; binding에서 실제 resume/approval/version을 가져와 원자 등록. accepted는 실행 시작과 별도 |
| GET /v1/bindings/{binding} | 실제 kernel 상태, command/attempt/stopReceipt/Evidence, releasedAt·resourceReleasePending |
| POST /v1/bindings/{binding}/reconcile | EmptyRequest; 안전 조건 재확인 후 해제, 실제 상태 반환 |
| DELETE /v1/edit-locks/{lock} | 현재 requester이자 lock owner만 수동 해제, 멱등 ledger 적용 |
| POST /v1/bindings/{binding}/state | 현재 scope 확인 후 거부. 클라이언트 상태 제출은 실행 권위가 아님 |

중요 mutation에는 Idempotency-Key가 필요하다. read와 approval 확인은 새로운 승인/부수 효과를 만들지 않는다. PR14의 client hash/version/resume 주장만 기록하는 FreezeInputsRequest와 저장되는 BindingStateRequest는 이 계약으로 대체한다. frontend는 변경한 Schema에 맞춰 통합해야 한다.

## 인계와 남은 범위

실행 증거는 같은 SHA CI Artifact 및 History 보고서에 기록한다. 로컬 Windows에 실제 Linux Docker daemon이 연결되지 않아 Linux 시험은 CI에서 수행한다. CI Node는 합성 데이터와 한 호스트의 별도 프로세스이며 실제 5대 운영 장비 검증과 다르다.

실제 구현·검증 결과는 [[2026-09-10_13-57-52_KST_BUSINESS-KERNEL_Codex_검증보고]], 실패와 수정은 [[BUSINESS-KERNEL 통합 검증 오류]] 및 [[BUSINESS-KERNEL 통합 검증 해결]]에 연결한다.

Claude: 이 새 경계 독립 검토, public CRUD→연결 등록을 수행하는 신뢰 provisioning service, production 업무 router 조합, PR14 실험 DB를 사용하는 환경이 있을 경우 실제 schema/data 이관 계약, 준비한 뒤 방치된 approval/lock의 TTL 운영 정리. 현재 존재하지 않는 첫 Run/checkout/editor 연결을 완료로 표시하지 않는다.

Gemini: 실제 권한→edit-lock→binding→두 승인→enqueue→kernel 상태/Evidence 표시, state 제출 제거, 자동 lock 해제와 권한 철회 화면·브라우저 검증.

Codex: kill switch/drain·주기 reconciliation, editor/PTY/remote Git·대용량/Node 간 Workspace 이전, Windows/GPU/BuildKit·Context/RO·5대 부하/장애/복구 검증. 현재 변경만으로 전 Sprint 또는 운영 인수를 done으로 올리지 않는다.
