---
doc_id: "S08-BE-NODE-QUARANTINE-001"
title: "S08-BE node-agent durable quarantine channel"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-10-02T12:16:40+09:00"
source_of_truth: "Git"
base_sha: "63ef20c4df9455eaae05758ff18d00ad46e5ff0f"
reviewer: "Claude"
---

# 목적

`services/control-plane/src/inv/build_execution.py`는 dispatch 뒤 검증 실패 때 원래 오류를 보존하면서
Node quarantine을 요청한다. 기존 `NodeAgentReceipts.quarantine_node()`는 `VERIFY-0022`만 발생시켜
durable reconciliation 채널이 없었고, 제품 dispatch는 `RES-0006`으로 fail closed였다. 이 문서는
Node가 복구 의무를 기록했다고 확인할 수 있는 최소 채널을 고정한다.

# 공개 계약과 전송 경계

- `contracts/v1alpha1/core.schema.json`의 `BuildQuarantineRequest`와
  `BuildQuarantineReceipt`가 strict wire 계약이다. unknown field, 대문자 UUID, scope/session 불일치,
  잘못된 reason code를 거부한다.
- control-plane은 기존 `services/control-plane/src/inv/node_transport.py`의 인증된 TLS 1.3,
  certificate pin, no-proxy, no-redirect, one-connection 경계를 재사용해
  `POST /v1/builds/quarantine`만 호출한다.
- Node는 `tenantId`, `nodeId`, `recoveryEpoch`를 자신의 trusted config와 대조한다. 응답 전에 private
  journal 파일을 write → fsync → atomic rename → directory fsync 순서로 기록한다.
- `requestId`가 idempotency key다. 같은 내용의 재전송은 최초 `recordedAt`을 보존한
  `replayed=true` receipt를 반환한다. 같은 key의 다른 내용은 `NODE-0015`로 거부하고 최초 기록을
  덮어쓰지 않는다.
- control-plane은 응답이 불확실해도 같은 scope/session/reason 요청의 최초 requestId와 requestedAt을
  process lifetime 동안 보존해 다음 호출이 새 사건으로 기록되지 않게 한다.
- control-plane은 request의 모든 identity/scope/session/reason/time 필드를 receipt와 exact 대조하며
  `writerKind=node-agent`, `durable=true`도 다시 확인한다.

# 원자성·원인 보존

1. journal final path는 완성된 JSON이 fsync된 뒤에만 보인다. 중간 파일은 응답 권위가 아니다.
2. 동일 process의 동시 요청은 mutex로 직렬화되고, Node journal의 단일-process lock이 restart 경계를
   보호한다.
3. quarantine 실패가 원래 dispatch/cleanup 경합 원인을 덮지 않는다. 제품 service는 원래
   `DomainError`를 유지하고 reconciliation channel 오류를 별도 fail-closed 조건으로 취급한다.
4. receipt의 `reasonCode`는 최초 원인의 code를 보존한다. 새 호출자가 문구나 비밀값을 전달할 필드는
   없다.

# 비주장 경계

- durable receipt는 quarantine·cleanup·lease release가 이미 끝났다는 증거가 아니다. 후속 operator
  reconciliation의 입력이다.
- concrete BuildKit 제품 caller와 설정 enable은 이 카드 범위 밖이다. quarantine client와 pinned
  channel proof가 함께 주입되지 않으면 `records_durable_quarantine=false`이고 dispatch는 계속
  fail closed다.
- 실제 LAN builder Node 인수와 물리 장애 복구는 `NOT_OBSERVED`다. S08-BE 상태·점수·완료 판정은
  바꾸지 않는다.

# 검증

- Python: strict contract, client/request/receipt exact binding, 잘못된 authority 입력과 non-durable
  receipt 거부.
- Go: mTLS route, journal privacy, exact replay, conflicting replay, wrong identity, 동시 8요청에서
  최초 1건+replay 7건.
- Linux-only journal 시험은 hosted Core `run-core`에서 실행한다. 로컬 Windows Go는 runtime/transport
  compile과 platform-independent transport 시험만 증명한다.

# Claude r1 보강

- quarantine identity는 `buildSessionId`뿐 아니라 `leaseId`, `resourceId`, `decisionId`,
  `bindingDigest`, `daemonIdentity`, `recoveryEpoch`를 포함한다. replay key도 이 전체 authority를
  포함하므로 한 Node의 서로 다른 lease generation이나 daemon 패자는 합쳐지지 않는다.
- 제품 dispatch 직전 fresh nonce를 mTLS Node에 보내 tenant·Node·epoch·5초 freshness를 exact
  대조한다. 런타임 도달 불가이면 adapter 호출 전 `RES-0006`으로 거부하고 control-plane의
  `inv.nodes.status`를 `quarantined`로 바꾸며 redacted outbox marker를 같은 transaction에 남긴다.
- post-dispatch 실패에서는 Node journal과 control-plane scheduling fence를 독립적으로 시도한다.
  어느 secondary quarantine 호출이 실패해도 최초 `VERIFY-0002`, `VERIFY-0022`, `LEASE-0002`
  원인을 덮지 않는다.
- placement와 final build admission은 기존대로 `inv.nodes.status='online'`을 요구하므로 위 fence가
  새 build 배정을 막는다. marker는 복구 완료가 아니라 reconciliation 의무다.
