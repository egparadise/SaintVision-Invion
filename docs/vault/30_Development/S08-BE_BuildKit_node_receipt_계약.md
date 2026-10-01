---
doc_id: "DESIGN-S08-BE-BUILDKIT-NODE-RECEIPTS-001"
title: "S08-BE BuildKit node receipt와 dispatch 완료 계약"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-02T08:38:37+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "e8f2eb56c7dde99a5aacda4fed9ca0d9205d7ac5"
task_ids: ["S08-BE"]
tags: ["s08-be", "buildkit", "contract", "node-mtls", "cleanup", "audit"]
---

# S08-BE BuildKit node receipt와 dispatch 완료 계약

## 0. 결정과 범위

[[2026-10-01_13-40-45_KST_S08-BE_BuildKit_계약경계_Codex]]와 PR #306의 제품 caller 측정은 caller를
연결하기 전에 node가 작성하는 health/cleanup 입력과 완료 감사 사건을 먼저 고정하라고
요구했다. 이 PR은 그 공개 계약만 정의한다. 제품 config, caller, route, transport dispatch,
DB migration은 구현하지 않는다. `INV_BUILDKIT_REFERENCE_ENABLED`는 CI reference 전용이고
`INV_BUILDKIT_PRODUCT_ENABLED`도 아직 제품 설정에 추가하지 않는다.

## 1. 인증 경계

두 receipt의 `writerKind`는 항상 `node-agent`다. 실제 구현은 node mTLS에서 인증한 identity와
`nodeId`를 결속한 뒤 control plane의 `0600`, no-symlink 파일로 materialize해야 한다. schema
통과만으로 인증됐다고 보지 않는다. caller나 control plane이 스스로 쓴 JSON, `-ci-reference`
isolation, `caller-asserted` field source는 제품 입력이 아니다.

### 1.1 `BuildProviderHealthReceipt`

필수 결속은 다음과 같다.

| 분류 | 필드 / 값 |
|---|---|
| version·writer | `schemaVersion=build-provider-health-receipt:1`, `writerKind=node-agent` |
| authority | `nodeId`, `builderInstanceId`, `builderProfileId`, `recoveryEpoch`, `observedAt` |
| daemon | `runtimeIdentity=sha256:<64hex>`, `daemonIdentity.{pid,processUid,processStartTicks,comm=buildkitd}` |
| isolation | rootless true, privileged/hostAccess false, 빈 entitlements/devices/binds, user namespace, seccomp filter, AppArmor/SELinux, no-new-privileges, cgroup v2 |
| provenance | strict `fieldSources`; node proc/runtime/host read-back만 허용 |

receipt의 `recoveryEpoch`는 정수 fencing token이 아니라 UUID control epoch다. 구현 비교는
`nodeId == leasedNodeId`와 `receipt.recoveryEpoch == inv.control_epoch.epoch ==
inv.leases.recovery_epoch`를 요구한다. 기존 `BuildPlan.recoveryEpoch` 정수는 lease fencing token
부분이라 이 UUID 비교에 사용하지 않는다.
identity/epoch/격리 불일치는 `RES-0006/503/retryable=true`, stale `observedAt`은 기존
`RES-0003/409`, dispatch 전후 daemon identity drift는 `VERIFY-0002/422`다.

### 1.2 `BuildPhysicalCleanupReceipt`

필수 필드는 version/writer, `buildSessionId`, node/resource/lease/epoch, 같은 daemon identity,
`stopResult=stopped|already-absent`, partial export disposition(`quarantined|purged|null`), cache
disposition, builder claim/cgroup release와 `verifiedAt`이다. `null`은 partial export가 애초에
없었다는 뜻이고, 관측하지 않았다는 뜻으로 쓰지 않는다.

`buildSessionId`는 caller 입력이 아니라 control plane이 plan compilation 때 새 UUID로 발급해
`BuildPlan.buildSessionId`에 넣고 durable build claim/evidence와 결속한다. legacy plan의 호환성을
위해 이 선행 계약에서는 plan 필드가 optional이지만, concrete transport enable 경로는 plan에
필드가 없거나 physical receipt와 다르면 fail closed한다.

기존 활성 제품 경로의 호환성을 위해 선행 계약 단계에서는 `BuildCleanupReceipt`의
`physicalReceipt`와 `physicalReceiptDigest`를 함께 있을 때만 허용한다(둘 중 하나만 있는 상태는
계약 위반). 두 필드가 없는 legacy receipt는 이 계약 PR에서만 계속 유효하다. 카드 214 구현은
concrete BuildKit transport를 enable하기 전에 두 필드를 제품 검증에서 반드시 요구하며, 그
전까지 transport 기본값은 disabled다. 별도 `BuildPhysicalCleanupReceipt` 자체의 모든 필드는
항상 필수다.
digest는 저장소 정본 `inv.policy.action_digest(physicalReceipt)`다. 즉 digest 필드를 포함하지 않는
physical receipt를 키 정렬·compact separator·NaN 거부 JSON으로 직렬화한 SHA-256 소문자
64-hex다. 현재 strict receipt vocabulary는 ASCII만 허용한다. 구현은 중복된
cache/claim/cgroup/verified 값의 exact 일치도 검사한다.
하나라도 관측·대조할 수 없으면 `VERIFY-0022/409`, lease 미해제, node quarantine이다.

## 2. 완료 감사 계약

`BuildAuditEvent.event`의 public 값은 `dispatch_completed`다. durable outbox event type은
`inv.build.dispatch_completed`다. strict `BuildDispatchCompletedPayload`는 다음 여섯 필드만
허용한다: `decisionId`, `bindingDigest`, `resourceId`, `leaseId`, `evidenceId`,
`evidenceDigest`. daemon stdout, topology, socket/path, subject, token, secret은 허용하지 않는다.

제품 caller는 final authority 재검증 뒤 **한 transaction**에서 Evidence INSERT, physical
cleanup digest 검증, kernel lease release와 이 outbox event를 commit해야 한다. schema는 그
입력/출력 모양만 고정하며 원자성 구현은 카드 214 범위다.

## 3. 영속과 migration 결정

새 table/column은 만들지 않는다. canonical physical receipt와 digest는 기존 `inv.evidence`의
`BuildReceipt` 일부로 저장하고, 성공 사건은 기존 `inv.outbox` 문자열 event type을 쓴다.
이 경계로 원자성을 구현할 수 없다는 실증 전에는 0059를 요청하지 않는다.

## 4. 부정 시험과 인수 경계

- writer를 control-plane으로 바꾸기, node/ID 형식 훼손, daemon comm 변경, CI isolation과
  caller-asserted source, unknown field, 누락 field는 모두 `VAL-0002`다.
- cleanup stop/disposition/claim/cgroup, canonical digest 형식과 완료 payload의 redacted exact
  key set을 고정한다.
- schema와 Python/TypeScript/Go/generated schema는 같은 commit에서 생성한다.
- 이는 제품 실행 또는 node mTLS 왕복 증거가 아니다. 카드 214는 이 계약 위에 stack하고,
  물리 LAN builder 인수 전 제품 enable·S08-BE 완료를 주장하지 않는다.
