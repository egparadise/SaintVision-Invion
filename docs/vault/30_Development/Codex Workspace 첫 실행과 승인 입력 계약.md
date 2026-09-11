---
doc_id: "CONTRACT-WORKSPACE-START-001"
title: "Codex Workspace 첫 실행과 승인 입력 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T10:50:00+09:00"
source_of_truth: "Git"
---

# Workspace 첫 실행과 승인 입력 계약

owner Codex / reviewer Claude 대기. ADR-063은 실행 이력이 없는 새 Run의 입력 고정·첫 attempt·원자 admission을 정의한다. [[Codex Workspace 공개 API와 실행 커널 통합 계약]]의 복구 API와 [[Codex 업무 binding과 실행 커널 연결 계약]]의 기존 checkout binding을 보완한다.

## 첫 실행의 의미

새 Run은 draft/version 1/attempt 0으로 생성한다. 최초 입력을 준비하면서 같은 트랜잭션에서 validated → planned → awaiting_approval로 전이한다. 과거 실패·checkpoint·checkout·복구 attempt를 만들지 않는다. 실제 시작을 Node가 확인해야 attempt 1이 된다. 입력 준비·승인·queue 접수는 실행 성공이 아니다.

입력은 요청자가 제출한 canonical WorkspaceSnapshot bytes다. 서버의 기존 경로를 읽거나 사용자 폴더를 mount하지 않는다. snapshot은 최대 64 KiB, 실제 파일 내용 합계는 32 KiB, HTTP 전체 요청은 기존 64 KiB 한도이며 경로·대소문자 충돌·파일별 길이/hash·정규 base64를 검사한다. 따라서 파일명/메타데이터 크기에 따라 허용 파일 내용은 더 작아진다. 대형 저장소·대규모 데이터셋 전송은 이 API 범위가 아니다.

서버는 불변 `workspaceStart`에 startId/stepId/입력 SHA/크기와 선택 Node ID·CPU/메모리 자원 ID·profileVersion·policyVersion을 넣는다. 요청자가 선택한 targetNodeId와 설치된 runtime의 Node가 다르면 거부하며 대체 Node로 자동 변경하지 않는다. 이 전체 Workload digest가 승인 대상이다. Node·resource·버전이 승인 후 달라지면 enqueue가 실패한다. 새 대상은 새 Run/새 승인이 필요하다.

## Claude와 Gemini가 연결할 API

기존 인증과 현재 project grant를 그대로 사용한다. 사용자 subject는 검증된 token에서 얻고 요청 body의 requestedBy나 역할을 신뢰하지 않는다. 운영 사용자·IdP·project/workspace 생성 및 권한 mapping은 Claude 서비스가 제공한다.

| 순서 | API | 입력/응답 |
|---|---|---|
| 1 | `POST /v1/projects/{project}/runs` | 기존 API. Idempotency-Key로 draft Run 생성 |
| 2 | `POST /v1/projects/{project}/runs/{run}/start/prepare` | WorkspaceStartPrepareInput: startId(UUID), stepId, expectedVersion, targetNodeId, workload, snapshotBase64. 응답 201: startId, 고정 workload, approval, 현재 run |
| 3 | 기존 `/v1/projects/{project}/approvals/{approval}/challenge` 및 `/decision` | 현재 권한 있는 서로 다른 두 승인자, nonce·내용 digest·만료 검증. fixture 승인자를 운영 사용자로 추가하지 않음 |
| 4 | `POST /v1/projects/{project}/runs/{run}/start/enqueue` | startId, approvalId, prepare 응답의 expectedVersion. 응답 202: accepted true, runId, commandId. 원래 입력을 제출한 requester만 가능 |
| 5 | `GET /v1/projects/{project}/runs/{run}/starts/{startId}` | 실제 Run·approval·파일별 SHA/크기 목록. 파일 내용/base64는 반환하지 않음 |
| 6 | 기존 Run 조회·events·cancel | 화면은 실제 서버 state와 command/receipt/Evidence에 따라 표시. 실패 응답에 임의 Run ID를 생성하지 않음 |

`workload`에는 apiVersion/kind/workloadId/tenantId/projectId/workspaceId/resources/imageDigest/command/timeoutSeconds를 제공한다. 브라우저가 workspaceStart/workspaceResume·policy·lease·서명키를 넣으면 거부한다. 모든 쓰기 요청은 같은 의도의 재시도에 같은 Idempotency-Key를 쓴다. 예제 ID·이미지·승인자를 운영 설정값으로 복사하지 않는다.

## 업무 metadata와 운영 연결

업무 project로 등록되어 있으면 inv와 public의 현재 권한 교집합을 검사한다. public Run/Workspace/workload와 inv.business_runs mapping이 모두 같은 tenant/project/Workspace이며, Workspace ready·작업 spec/hash가 현재 승인 의도와 같아야 한다. mapping이 없으면 독립 kernel Run으로 우회하지 않는다. metadata 생성/mapping은 업무 서비스가 소유한다.

처음 제출하는 파일의 사본은 기존 checkout 편집 lock을 만들지 않는다. 이후 로컬 편집은 이미 고정한 입력을 바꾸지 않는다. UI는 제출한 사본의 SHA와 현재 편집본을 구분해야 한다. public.runs.state는 업무 metadata이며 실제 실행 상태는 inv Run에서 조회한다. 기존 resumption binding API와 첫 실행 handle(startId)을 혼용하지 않는다.

## 예약·전달·복구

Node 관측은 DB 트랜잭션 밖에서 수행한다. 이후 현재 requester/approver 권한·업무 intent·Run 버전·Node membership·runtime 고정값·kill/drain·제공량을 재검사한다. 승인 소비·Lease 예약·ToolGateway claim·서명 queue 등록은 하나의 트랜잭션이다. 중간 실패는 전부 rollback한다. 첫 입력이 있는 Run의 별도 approval dispatch/Lease 예약/claim 경로는 차단한다.

이미 accepted된 동일 enqueue는 현재 접근 권한을 확인한 뒤 기존 commandId를 반환한다. Node 관측을 다시 요구하거나 실행을 재전송하지 않는다. queue 이전 취소는 예약/Node 실행 없이 끝나고, queue 이후 취소는 실제 Node의 미실행 tombstone 또는 물리 정지 receipt가 와야 예약을 반환한다.

Go launch의 workspaceMode는 initialized, WorkspaceInput은 startId를 사용한다. restored는 resumeId를 사용하며 두 ID를 함께 넣을 수 없다. 기존 Node/이미지는 새 입력을 거부하므로 새 계약을 지원하는 agent/supervisor 이미지와 명시적 profile을 함께 배포해야 한다. 실제 workload에는 Docker socket·host bind·network를 제공하지 않는다.

stdout/stderr와 수정 Workspace snapshot은 동일 startId/stepId/입력 SHA에 묶인다. 실제 출력 bytes 검증과 파일 checkpoint/pin·Evidence·Run 완료를 연결하며 checkpoint 없이 최초 성공을 기록할 수 없다. 출력 publication만 중단되면 기존 receipt로 다시 확정하며 재실행하지 않는다. GPU·분산 학습·optimizer 중간 상태의 재학습 복구는 별도 범위다.

## Migration과 검증 범위

현재 추적된 Alembic head 0023_containment_approvals 다음에 forward-only `0025_workspace_start`를 추가한다. 기존 migration/데이터를 수정하지 않는다. 과거 설계 문서에서 0024 번호를 언급했지만 현재 Git main/작업 checkout에는 해당 revision이 없으므로 가상의 predecessor를 만들지 않는다. 다른 브랜치의 0024를 통합할 때는 실제 graph를 별도 검토한다.

실행 기록과 남은 운영 연결은 [[2026-09-11_FIRST-RUN_Codex_검증보고]]를 따른다. 독립 테스트 identity/DB/PKI의 통과가 실제 사용자/원격 PC 설치·운영 인수 완료를 의미하지 않는다.
