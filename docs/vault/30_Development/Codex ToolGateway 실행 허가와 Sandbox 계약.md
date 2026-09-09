---
doc_id: "TOOL-CONTRACT-001"
title: "Codex ToolGateway 실행 허가와 Sandbox 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-09T23:38:28+09:00"
source_of_truth: "Git"
---

# Codex ToolGateway 실행 허가와 Sandbox 계약

Task tool-admission / owner Codex / reviewer Claude(pending). OUT-03/AC-03·OUT-04/AC-04의 내부 실행 허가 계약이다. [[Codex 승인 경계 계약과 인계]]의 durable dispatch를 현재 권한·정책·자원·Node·Sandbox 검증에 연결한다. S02 선행 미완료와 독립 검토 대기 상태를 유지하며 S03 전체의 격리 실행 성공이라고 표시하지 않는다.

## ADR-025 실행 허가의 일회 소비와 불확실한 실행

commandId별 immutable tool_claims 1개를 저장한다. 처음 commit한 호출만 `may_start=True`와 launch 설정을 반환한다. 같은 요청의 broker 재전달·동시 호출·서비스 재생성에서는 `may_start=False`, `launch=None`과 기존 claim 메타데이터만 반환한다. 다른 내용/Node/proof로 재사용하면 IDEM-0001이다. claim은 TTL 만료나 응답 유실로 자동 회수하지 않는다.

첫 응답이 유실됐거나 claim commit 후 실제 시작 전 crash가 나면 작업이 시작되지 않을 수 있다. 중복 부수 효과를 방지하기 위해 이 불확실성을 자동 재실행으로 해결하지 않는다. 후속 복구기는 실제 Node stop/result receipt를 조회해 확인하고 새 Run·승인·예약을 준비해야 한다. 같은 commandId의 claim을 삭제/변경해서 재실행하지 않는다. DB superuser에 대한 WORM 보장을 주장하지 않는다.

`inv.execution.claimed` outbox는 감사 알림이다. 다른 소비자가 이 이벤트만 보고 실행하거나 may_start=False를 허가로 해석하면 안 된다. claimId/commandId는 bearer credential이 아니다. 전달 경로는 후속 mTLS adapter가 인증해야 하며, Node의 durable inbox와 allocation fence·monotonic deadline 검사를 실제 시작 직전에 다시 적용해야 한다.

## 입력과 서버 검증

| 입력·경계 | 검증 |
|---|---|
| NodePrincipal | 신뢰된 mTLS/신원 adapter만 생성하는 tenant/node. 문자열 형식 검사는 인증을 대신하지 않음 |
| AuthorizedCommand | outbox payload를 DB의 approval_requests·approval_dispatches와 대조. commandId, 모든 scope, digest, policy version, epoch, expiry 일치 |
| Workload/Run | 원본 승인 digest와 일치; 현재 scheduled, 승인 직후 Run version, dispatched 상태 |
| ResourceLease | 해제되지 않은 allocation 전체의 정확한 proof; 현재 epoch·expiry; 모두 동일 authenticated Node. CPU millis와 memory bytes 합계가 Workload 자원 상한 이상 |
| Node | online, heartbeat 15초 이내·미래 아님, 측정된 clock skew ±5초, 현재 epoch |
| project grant | 요청자 can_request와 실제 모든 승인자의 can_approve 재확인. 자기 승인 제외·원래 승인 quorum 유지 |
| CurrentPolicy | 신뢰된 PDP adapter의 같은 policy version·scope·action·subject, 평가 후 5초 이내, TTL 최대 30초, deny/L3/위조 approvedBy 차단. 승인자 목록은 DB vote에서 구성. 정책 강화 시 새 승인 필요 |
| RuntimeCapabilities | 검증된 Node adapter의 현재 node/epoch/profileVersion, 30초 이내 만료와 모든 필수 capability. 클라이언트 JSON flag를 attestation으로 수용하지 않음 |
| notAfter | 승인/PDP/runtime capability/모든 lease 만료의 최솟값; 허가 생성 시 최소 1초 이상 필요. Node가 시작과 실행 중 실제 monotonic deadline을 강제해야 함 |

PDP/Node transport 호출은 DB transaction 밖에서 끝낸 snapshot만 전달한다. 네트워크 장애·검증된 snapshot 부재는 신규 claim 거부다. 잠금은 Run → Approval → Node/Resource → 정렬 grant 순서. 다른 writer는 이 순서를 거꾸로 잡지 않는다. claim INSERT와 감사 outbox INSERT는 같은 txn이며 실패 시 둘 다 rollback한다. 재전달에 대한 기존 claim 조회는 새로운 권한을 주지 않으므로 만료/취소/권한 철회 후에도 `may_start=False` 메타데이터만 관찰할 수 있다. tenant/Node 경계는 계속 확인한다.

## ADR-026 고정 Sandbox launch 프로파일

서버의 immutable profile은 version, image digest allowlist, 컨테이너 내 절대 executable allowlist, CPU/RAM/시간 상한을 고정한다. 모든 command는 컨테이너 executable+argv 배열이며 host shell 문자열로 합치지 않는다. 절대 executable allowlist의 비정규 경로·NUL·빈 인자·초과 크기와 image tag는 거부한다. 현재 프로파일은 CPU 전용이며 GPU/VRAM을 거부한다.

SandboxLaunchSpec은 network=none, UID 65532, read-only rootfs, 모든 capability 제거, no-new-privileges, privileged=false, hostAccess=false, pidsLimit=64, /workspace ephemeral 작업공간이다. host mount, Docker socket, 사용자 env/credentials, host path, 완화 flag는 계약에 없으며 unknown property도 거부한다. 실제 runtime은 filesystem/network 격리·CPU/RAM/PID 제한·monotonic deadline·durable inbox·allocation fence를 지원한다고 신뢰된 경로에서 검증돼야 한다.

이 변경은 **launch 계약 compiler와 서버 admission 구현**이다. OS/컨테이너 실행 driver를 호출하지 않으며 RuntimeCapabilities 합성 fixture 통과가 실제 커널 격리 검증은 아니다. Workspace volume 연결, GPU 장치 격리, 파일 전송과 실제 Sandbox smoke는 Node/Storage 통합 후 검증한다. claim 시 Run을 running/succeeded로 바꾸거나 자원을 반환하지 않는다. 실제 시작 ACK, 검증된 결과/Evidence와 물리 stop ACK는 기존 Run/Lease 계약을 통해 연결한다.

## 계약·검증·권한

원본 `contracts/v1alpha1/core.schema.json`의 SandboxLaunchSpec·ExecutionClaim → 생성 Python/TypeScript/Go. migration 0003은 0002 뒤의 tool_claims immutable inbox·tenant RLS·소유 FK다. runtime은 nonowner/NOBYPASSRLS, tool_claims는 SELECT/INSERT만 필요하다. 일반 테이블 GRANT 후 `REVOKE UPDATE,DELETE ON inv.tool_claims FROM inv_runtime`을 적용해야 하며 실제 운영 role 변경은 이번에 실행하지 않았다.

신규 71개 시험(단위 26·PostgreSQL 45): 위조 event·정책 deny/unavailable/강화·Node 단절/드레인/스큐·lease 만료/해제/불충분/다른 Node·Sandbox 완화/host 접근·8개 동시 재전달·유실 응답/서비스 재생성·감사 실패 rollback. 기존 101개 회귀를 포함한다. 로컬 89 passed/83 PostgreSQL skipped이며 실제 CI 증거는 검증 보고에 연결한다.

legacy enforce_decision의 L2 requiredApprovals=1 허용 틈을 코드 검토에서 발견해 2인 하한을 추가했다. 기존 ApprovalStore는 이미 2인을 강제했으므로 새 durable 승인 경로의 완화는 아니다. [[ERR-TOOL-001 정책 보조 함수의 L2 하한 누락]]과 [[RES-TOOL-001 L2 하한 강제와 회귀 검증]] 참조.

## 다음 담당

- Claude: admission lock/rollback/재전달 의미 독립 검토. 인증·PDP·Node capability adapter 연결 시 브라우저/model 값을 trusted snapshot으로 승격하지 않음. 기존 Backend 서비스와 core 두 구현의 통합은 별도 리뷰로 진행.
- Gemini: claim을 실행 완료/자원 회수 배지로 표시하지 않음. may_start=False는 새 실행 허가가 아님. actor 전환 UI는 인증을 대체하지 않으며 서버 nonce·quorum·상태를 사용. Evidence ID는 evd_, 물리 자원 반환은 stop ACK 뒤에만 표시.
- Codex: Node durable inbox·OS Sandbox driver·실제 단절/watchdog·stop ACK/결과 저장을 결합하는 후속 작업. 제품 Prompt/Context/Harness/ROOF/Graph 실행 버전은 아직 연결하지 않았으며 테스트 profile/ROOF 값은 합성이다.
