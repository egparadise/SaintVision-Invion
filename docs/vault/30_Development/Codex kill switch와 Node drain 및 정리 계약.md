---
doc_id: "CODEX-NODE-CONTAINMENT-001"
title: "Codex kill switch와 Node drain 및 정리 계약"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-09-10T15:13:00+09:00"
source_of_truth: "Git"
---

# 실행 차단·Node drain·주기 정리

task NODE-CONTAINMENT, S07-BE/DB·S08-BE/DB 부분 범위. owner Codex, reviewer Claude pending. base PR16 `990f3f3a89cef6f6e8c7dd1236d8f2518041fc4f`, branch `agent/codex/node-containment`, draft PR17. [[Codex 업무 binding과 실행 커널 연결 계약]]의 실제 실행·영수증·Evidence 계약을 보존한다.

## ADR-053: tenant 실행 barrier와 현재 operator 권한

`0022_node_containment`은 기존 canonical history 뒤의 forward-only migration이다. `inv.tenant_controls`, `node_controls`, `operator_grants`, `containment_requests`에 FORCE RLS를 적용한다. 기존 tenant/Node에는 version 0의 기본 제어 행을 만들고 이후 등록에도 trigger로 동일 행을 만든다. epoch·LOGIN·operator grant는 자동 발급하지 않는다. inv_app에 inv 실행 권한을 확대하지 않는다.

모든 runtime transaction은 기존 recovery epoch 확인 후 **tenant control SHARE → 기존 Run/Project/Node/Resource/Grant 규약**을 따른다. kill/clear는 처음부터 tenant control UPDATE 잠금을 사용하며 SHARE 잠금을 뒤늦게 승격하지 않는다. network I/O는 transaction 밖이다. kill 응답이 확정되면 그 뒤의 새 예약·승인 dispatch·claim·최초 전송·running/verifying/succeeded 전이는 차단된다. 이전 transaction에서 이미 전송을 예약한 command는 불확실한 실행으로 취소하고 실제 영수증을 기다린다. barrier 전에 확정한 결과는 소급 취소하지 않는다.

HTTP는 기존 JWT에서 tenant와 issuer-qualified subject를 가져온다. 현재 `inv.operator_grants`의 enabled 및 can_contain/can_resume를 확인하며, 일반 Project requester/approver 권한이나 client role 필드로 운영자 권한을 만들지 않는다. 운영자는 검증한 주체를 별도 신뢰 provisioning으로 등록한다. runtime은 grant 권한 열을 수정할 수 없다. replay/read도 현재 운영자 권한이 필요하다.

kill/clear/drain/resume는 expectedVersion과 Idempotency-Key, 제한된 reasonCode를 사용한다. actor·operation·Node·입력 digest와 최종 응답을 한 transaction의 불변 `containment_requests`에 기록한다. 같은 키의 다른 내용은 거부하고, 중복 처리로 version을 재증가시키지 않는다. 응답 유실 후 재시도는 원래 응답이며 현재 상태는 GET으로 확인한다.

## ADR-056: 제어 변경도 L2의 2인 승인 적용

[[20_Backend 보완 설계]]의 Node drain L2 분류와 [[보안 평가 운영 가이드]]의 명시적 승인·만료 요구를 적용한다. 초기 operator-only 구현은 최종 계약이 아니며 [[NODE-CONTAINMENT 승인 경계 검토 오류]]에 기록했다. 모든 kill/clear/drain/resume는 요청자를 제외한 서로 다른 두 사람의 승인이 필요하다. 긴급 상황이라고 암묵적인 승인 예외나 알람 기반 자동 kill을 만들지 않는다. 안전한 사전 승인은 최대 5분의 정확한 제어 범위·version에만 유효하다.

후속 `0023_containment_approvals`는 0022를 재작성하지 않고 operator의 검증된 person_id·can_approve와 불변 제어 Approval/투표·일회 nonce를 추가한다. person_id는 tenant 내 UNIQUE이며 등록 후 변경할 수 없다. 기존 operator에 사람 identity나 승인 권한을 자동 할당하지 않고, person_id가 없는 grant는 사용을 거부한다. 사람 매핑과 역할 변경은 신뢰 provisioning만 가능하다.

제안은 operation/Node/제어 version/tenant gate version/recovery epoch/요청자 identity/reason의 digest 및 DB 기준 5분 만료를 고정한다. 두 승인자는 현재 can_approve 권한과 서로 다른 person_id가 있어야 하며 요청자는 투표할 수 없다. 각 투표는 주체에 결합된 60초 이내 nonce와 정확한 contentDigest를 사용하고 한 번만 소비한다. 거절은 terminal이며 재투표로 뒤집지 않는다.

실제 적용 직전 현재 requester/voter 권한·사람 identity·만료·epoch·gate/Node version을 다시 확인한다. 승인 소비·제어 변경·불변 감사 응답은 같은 transaction에서 확정하거나 전부 rollback한다. approvalId는 실제 consumed_request_id와 연결되며 가짜 ID나 한 표만으로 제어할 수 없다. 이미 접수된 kill의 취소 정리는 승인자의 후속 권한 철회와 별개로 계속된다. 정리 worker는 새로운 제어 결정을 만들지 않는다.

## ADR-054: drain과 물리 종료 확인

tenant kill switch는 활성 Run을 취소할 durable intent다. latch는 재시작이나 운영자 권한 철회로 사라지지 않는다. 새로운 Run 생성을 차단하고, worker가 기존 nonterminal Run을 한 번에 하나씩 cancelled로 전이한다. 신규 실행과 늦은 성공 확정은 barrier에서 거부한다. 읽기·Node 관측·취소·실제 영수증 수집은 유지한다.

Node drain은 같은 Node 잠금 아래 status를 draining으로 바꿔 새 예약/claim/최초 전송을 차단한다. 미발급 예약과 queued 명령은 취소·회수 대상으로 처리하고, 이미 network 실행이 진행 중인 Run은 기존 deadline 내 종료·결과 확정을 기다린다. heartbeat 복구는 draining을 online으로 덮어쓰지 않는다. quarantined 또는 다른 epoch의 Node를 drain/resume로 우회 복구하지 않는다.

최초 전송 예약 뒤 Node 상태나 kill 상태가 바뀌어 **network 호출 전** preflight가 거부된 경우에만 내부 not_sent 증거를 표시한다. worker는 이를 같은 command의 cancel로 바꾸고 실제 Node tombstone을 받아 정리한다. network 호출 뒤 오류에는 이 증거를 부여하지 않으며 관측·취소로 불확실성을 해소한다. not_sent는 HTTP 입력이 아니며 그 자체로 Lease를 반환하지 않는다.

kill clear는 해당 tenant의 미종료 Run·미반환 Lease·미완료 delivery가 모두 0일 때만 별도 can_resume 권한으로 가능하다. Node resume은 draining 상태 및 해당 Node 관련 정리 완료에 더해 현재 epoch/유효 channel/version과 최근 15초 이내 mTLS resource snapshot·heartbeat, clock skew를 확인한다. clear/resume는 기존 취소 Run이나 명령을 재실행하지 않는다. 실제 작업 재실행에는 기존 새 Run/새 승인 계약을 적용한다.

## ADR-055: 제한된 정리와 독립 취소 처리

기존 delivery service에 한 번에 한 Run을 선택하는 SKIP LOCKED reconciliation을 연결한다. kill 대상, drain의 미시작 작업, 만료된 미발급 예약, 이전에 취소됐지만 정리가 남은 미발급 예약을 검사한다. Run/자원 잠금 뒤 상태와 Lease를 다시 확인해 동시 worker가 같은 반환·감사를 반복하지 않는다. claim 또는 RunAttempt가 한 번이라도 있으면 비실행 증명으로 반환하지 않는다. old epoch 예약은 pending으로 보존하며 이미 취소된 old epoch 행을 반복 선택해 다른 정리를 굶기지 않는다.

worker CLI는 실행 처리 2개와 취소 전용 처리 5개로 제한한다. 실행 HTTP가 대기 중이어도 취소 경로가 남는다. 취소 전용 경로는 새 execute를 예약할 수 없고 결과 파일 publication도 수행하지 않는다. 모든 프로세스/처리 경로는 동일한 durable queue token·만료·멱등 receipt 규약을 공유한다. Python thread 수만으로 5대의 취소 지연 SLO 달성을 주장하지 않는다.

Node 단절은 물리 종료 증거가 아니다. control 응답의 activeLeases/pendingDeliveries/unsettledRuns와 settled를 함께 표시한다. Node가 돌아오면 같은 command를 취소/관측하고 실제 영수증 뒤 정확한 Lease를 반환한다. 영구 단절·old epoch·기존 transient claim에 필요한 운영 reconciliation을 새 실행이나 가짜 영수증으로 대체하지 않는다. bounded Node deadline은 기존 독립 supervisor 계약을 유지한다.

## 공개 API와 화면 인계

| 경로 | 의미 |
|---|---|
| POST /v1/operations/containment-approvals | ContainmentProposalInput으로 내용 고정, 5분 Approval 생성 |
| GET /v1/operations/containment-approvals/{approvalId} | 고정 내용·digest·만료·실제 승인 상태 |
| POST /v1/operations/containment-approvals/{approvalId}/challenge | 다른 승인자의 일회 nonce 발급 |
| POST /v1/operations/containment-approvals/{approvalId}/decision | ContainmentDecisionInput으로 고정 내용 승인/거절 |
| GET /v1/operations/kill-switch | tenant 제어 version, latch와 실제 정리 수치 |
| POST /v1/operations/kill-switch | ContainmentInput; 202는 durable 차단·취소 요청 접수 |
| POST /v1/operations/kill-switch/clear | ContainmentInput; 별도 재개 권한과 실제 정리 완료 필요 |
| GET /v1/nodes/{nodeId}/control | Node status/control version과 실제 정리 수치 |
| POST /v1/nodes/{nodeId}/drain | ContainmentInput; 202는 drain 접수 |
| POST /v1/nodes/{nodeId}/resume | ContainmentInput; 정리·현재 인증 관측 뒤 online 전이 |

정본은 core JSON Schema의 ContainmentInput/View/Result 및 제어 Approval 계약과 생성 Python/TS/Go다. ContainmentInput에는 실제 approvalId가 필수다. expectedVersion은 control version이며 Run version과 다르다. reasonCode는 maintenance/incident/operator_request다. 응답의 requestId·approvalId를 불변 감사 기록과 연결한다. 임의 HTML 상태나 토글만으로 cluster 정지를 표시하지 않는다.

Gemini는 기존 관리자 화면의 모의 kill 상태를 위 API에 연결하고 요청 접수/물리 종료 대기/정리 완료/명시적 재개를 구분해야 한다. 이 API는 OS 전체 방화벽이나 사용자 프로세스를 조작하지 않는다. 기존 승인된 sandbox의 network=none 정책과 제어 중단을 화면에서 혼동하지 않는다.

Claude는 독립 코드/DB/권한 검토, 신뢰 operator provisioning, 운영 서비스 설치·감사 조회/알림·Node 단절 및 epoch 복원 절차를 인수한다. Codex는 후속 editor/PTY/remote Git·Workspace Node 이전·Windows/GPU/BuildKit·Context/RO와 실제 5대 부하/장애/복구 검증을 이어간다. 전체 ROOF·보안 Sprint·운영 배포 완료를 뜻하지 않는다.
