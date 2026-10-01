---
doc_id: "DESIGN-S08BE-PRODUCT-CALLER-20261002"
title: "S08-BE 제품 caller 연결 설계 메모와 Codex 계약 질문 — 경계는 전부 있고 그것을 부르는 것이 없다. 빌드 실행 경로는 보안 경계이므로 이 메모는 구현하지 않고 측정·결정·계약 질문만 적는다 (카드 210)"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T06:55:59+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "d0b2a4c6"
task_ids: ["S08-BE"]
tags: ["s08-be", "buildkit", "build-adapter", "roof", "security-boundary", "contract-question", "claude"]
---

# S08-BE 제품 caller 연결 — 설계 메모와 계약 질문

## 0. 이 메모가 하는 일, 그리고 하지 않는 일

재채점 v1.10 §4-7-2가 `S08-BE`를 50에 둔 **유일한 남은 이유**는 제품 caller 부재다. `#297`·`#303`으로 **실 rootless BuildKit transport·OCI digest 재계산·실 daemon PID 결속**이 `MEASURED_PASS`가 됐고, 그런데도 그 transport는 **flag off이고 제품 경로에 닿지 않는다.**

**이 메모는 코드를 쓰지 않는다.** 빌드 실행 경로는 보안 경계다 — 임의 Dockerfile을 실행하는 daemon에 제품 요청을 넘기는 연결이고, 그 연결의 실패 모드는 "빌드가 안 된다"가 아니라 **"회수되지 않은 외부 side effect가 Evidence로 승격된다"** 다. 그래서 카드 210의 범위대로 **(1) 현재 코드에서 caller가 될 경로를 측정**하고, **(2) 그 연결이 요구하는 결정을 이름으로 적고**, **(3) CI에서 증명 가능한 범위와 아닌 범위를 나누고**, **(4) Codex에게 물을 계약 질문만** 남긴다.

**이 메모는 `S08-BE`의 점수를 바꾸지 않는다.** 설계 메모는 구현이 아니고, 재채점 규칙상 점수를 움직이는 것은 행 고유 시험의 결속이다.

기준 tree는 **train 14 후보 `d0b2a4c6`** 다. `#303`은 미착지이므로 그쪽 사실은 **그 PR의 head `2c07dde6`** 에서 인용하고 그렇게 표시한다.

## 1. 측정 — caller가 될 경로는 이미 세 단계로 설계돼 있다

코디네이터가 예시로 준 경로(**승인된 Build 요청 → `#274` admitted Build adapter dispatch → `#297` transport**)가 코드에 **그대로** 있다. 없는 것은 그 세 단계를 **부르는 제품 코드**다.

### 1-1. 세 단계와 그 줄

| 단계 | 어디 | 무엇을 하는가 |
|---|---|---|
| **입구**(없음) | — | `BuildRequest`·`BuildPlan`·`PolicyDecision` 세 쪽을 만드는 제품 코드가 **0건**(§1-3) |
| **admission** | `services/control-plane/src/inv/build_governance.py:139` `authorize_build` | tenant 일치(`AUTH-0011`/403) → project grant(`:59` `_project_authority`, `FOR SHARE`) → **kill switch**(`require_execution`, `containment.py:15`, `AUTH-0061`/409) → `enforce_decision`(정책 결정 소비) → **provider 관측 신선도**(`:69` `_provider_fresh`, `PROVIDER_FRESHNESS_SECONDS = 15`, `RES-0003`/409) → `bindingDigest` 산출 |
| **live authority** | `build_adapter.py:96` `_lock_live_build_authority` | Run 잠금(`scheduled|running|verifying`만, `RES-0005`) → resource 잠금 → `inv.resource_leases ... FOR UPDATE` → Node heartbeat `NODE_FRESHNESS_SECONDS = 15`(`:156`) → fence·recovery epoch |
| **one-shot claim** | `build_adapter.py:163` `_claim_build_dispatch` | `inv.idempotency`에 `operation='build.dispatch'`, key는 **`decisionId` 단독 digest**, 충돌 시 `IDEM-0001`/409. **commit된 claim은 절대 재생되지 않는다** — 모호한 crash는 운영자 조정까지 fail closed |
| **외부 호출** | `build_adapter.py:326` `self._transport.dispatch(admitted)` | 트랜잭션 **밖**에서 한 번 |
| **재검증·Evidence** | `build_adapter.py:327-354` → `build_governance.py:331` `finalize_build` → `:180` `revalidate_build` | 같은 검사 전부 반복 + `bindingDigest` 비교(`VERIFY-0002`/422) + Node authority 변경 시 `NODE-0033`/409. **Evidence는 반환만 하고 저장하지 않는다**(`finalize_build`는 `_build_evidence`를 return) |
| **실패·취소** | `build_adapter.py:356-367` | 어떤 예외든 `transport.cancel_and_quarantine(admitted, reason_code)` → `_record_build_quarantine`(`:220`) → **cleanup이 실패하면 `VERIFY-0022`/409로 올린다**("취소·격리가 검증되지 않았다") |
| **감사** | `build_adapter.py:44` `_audit_event` | `inv.outbox`에 **redacted** 이벤트 두 종 — `inv.build.dispatch_claimed`(`:207`), `inv.build.dispatch_quarantined`(`:231`). pre-admission 거부는 **의도적으로 Evidence를 남기지 않는다**(모듈 머리말) |

### 1-2. transport는 **모양은 맞고 두 메서드가 비어 있다**

`RootlessBuildkitTransport`(`buildkit_transport.py:264`, 605행)는 `BuildTransport` protocol(`build_adapter.py:76`)의 세 메서드를 **전부 갖고 있다**. 그런데:

| 메서드 | 상태 | 줄 |
|---|---|---|
| `observe(plan)` | **동작한다** — `measure()`의 `BuildProviderObservation`을 반환 | `:426` |
| `dispatch(admitted)` | **`RES-0006`/503으로 거부** — "product dispatch awaits cleanup and Evidence persistence binding" | `:429` |
| `cancel_and_quarantine(...)` | **`VERIFY-0022`/409로 거부** — "product cleanup is not connected" | `:437` |
| `reference_roundtrip(...)` | **실행되는 유일한 경로**(CI 참조 증거) | `:473` |

즉 **빈 것은 설계가 아니라 두 동작**이고, 둘 다 **fail-closed로 이름 붙은 거부**다. 그래서 이 연결은 "새 설계"가 아니라 **그 두 메서드의 계약을 정하는 일**이다.

### 1-3. 없는 것 — 제품 caller, 기계로 확인했다

| 측정 | 결과 |
|---|---|
| `BuildExecutionAdapter`를 생성하는 곳 | **`tests/core/test_build_adapter.py`뿐**(`:178`·`:202`·`:219`·`:229`·`:366`). `services/`·`src/`에 **0건** |
| `buildkit_transport`를 import하는 곳 | `tools/run_buildkit_rootless_roundtrip.py`와 `tests/core/test_buildkit_transport.py` **둘뿐** |
| `BuildRequest`·`BuildPlan`을 만드는 제품 코드 | **0건** — 두 이름은 `inv/generated/models.py:246`·`:276`의 **계약 모델로만** 존재한다 |
| `app.py`의 build route | **0건**(`grep build services/control-plane/src/inv/app.py` → 빈 결과) |
| 대조: 같은 모양의 **작동하는** 경로 | `ToolGateway`는 제품 코드에서 생성된다 — `shards.py:208` `ToolGateway(BoundDatabase(self.db, tenant, conn), self.profile)` |

**이것이 "경계는 있고 그것을 쓰는 것이 없다"의 전부다.** 그리고 대조 때문에 할 일이 분명하다 — **`tooling.py`의 승인 경로를 그대로 따르는 것**이 새 설계를 만드는 것보다 안전하다.

### 1-4. 따라야 할 선례 — `tooling.py`의 승인→실행 경로

`ToolGateway.claim`(`tooling.py:72`)이 이미 같은 문제를 푼다:

| 선례 | 줄 |
|---|---|
| 승인이 현재 recovery epoch에 속하는지 | `tooling.py:240` `AUTH-0031` |
| **정책 snapshot이 5초 이내인지** | `:244-253` `AUTH-0043` — `now - 5s <= policy.evaluated_at <= now` |
| 결정의 만료가 snapshot + 30초 이내이고 승인 수가 충분한지 | `:256-262` `AUTH-0043` |
| `enforce_decision`으로 action과 결정을 결속 | `:264-271` |
| **검증된 runtime이 없으면 거부** | `:272-273` `SANDBOX-0001` |

build 쪽의 caller는 이 다섯 줄과 **같은 순서**를 가져야 한다. 다른 점은 하나뿐이다 — tool 경로의 `RuntimeCapabilities.check`가 **sandbox**를 검증하는 자리에, build 경로는 **builder health 관측**을 놓는다. 그 관측이 §2의 핵심 결정이다.

## 2. 그 연결에 필요한 결정

**이미 코드가 정한 것과 아직 정해지지 않은 것을 나눈다.** 전자를 다시 정하면 regression이고, 후자가 계약 질문이다(§4).

### 2-1. flag enable 조건

지금의 enable은 **환경변수 하나**다: `TRANSPORT_ENABLE_SETTING = "INV_BUILDKIT_REFERENCE_ENABLED"`(`buildkit_transport.py:34`), `configured()`가 `!= "1"`이면 **생성 자체를 `RES-0006`/503으로 거부**(`:285-297`). 그 이름을 세팅하는 곳은 **round-trip 도구와 그 시험뿐**이고 **제품 설정(`inv` config)에는 없다**.

제품 enable이 요구하는 것으로 **코드가 이미 요구하는 것**:

| 조건 | 어디 | 값 |
|---|---|---|
| health receipt가 **보호된 파일** | `:170` `_protected_json` | symlink 금지(`O_NOFOLLOW`), `st_nlink == 1`, `≤16KB`, **`mode & 0o077 == 0`**, lstat/fstat의 dev·ino 일치 |
| receipt의 **key 집합이 정확히 일치** | `:315-358` `_health` | `schemaVersion == 1`, instance·profile·recoveryEpoch·address가 **설정값과 같아야** 하고, `rootless is True`·`privileged is False`·`hostAccess is False`·`entitlements == []`·`devices == []`·`binds == []`, `runtimeIdentity`는 `sha256:` + 64 hex |
| **관측 신선도** | `:359-363` | `0 <= age <= configuration.freshness_seconds`(기본 **15초**, `:138`), 아니면 `RES-0003`/409 |
| worker **독점** | `:380-391` | `buildctl debug workers`가 **정확히 1개**가 아니면 `RES-0006`/503 |
| 관측 digest | `:392-403` | `health + workerId + platforms`의 canonical digest. **수집 시각은 digest에서 제외**(`build_governance.py:37`의 주석과 같은 규칙) |

**아직 정해지지 않은 것 — 이것이 보안 경계의 핵심이다:**

1. **health receipt를 누가 쓰는가.** 지금은 **CI 도구가 쓰고 같은 도구가 읽는다**(`tools/run_buildkit_rootless_roundtrip.py:469-470`이 `--health-receipt`에 write). 제품에서는 **caller가 자기 입력을 쓰는 구조여서는 안 된다** — 그러면 신선도는 "호출자가 방금 적었다"는 뜻이 된다. 쓰는 주체·전달 경로·인증이 정해져야 한다.
2. **CI 완화값을 제품에서 거부해야 한다.** `isolation.seccompMode`는 `{filter, unavailable-ci-reference, unconfined-ci-reference}`를, `lsm`은 `{apparmor, selinux, unavailable-ci-reference, unconfined-ci-reference}`를, `cgroupMode`는 `{v2, unavailable-ci-reference}`를 받는다(`:348-353`). **`-ci-reference` 값들은 hosted runner의 제약을 적은 것**이고 제품 dispatch에서 받아들이면 격리 없이 빌드를 실행한다. 그 거부를 **어디에** 둘지가 결정이다(제품 config의 허용 집합 / 별도 상수 / 다른 profile id).
3. **`recoveryEpoch`의 주인.** `_provider_fresh`는 `recovery_epoch >= 1`인 int만 본다(`build_governance.py:78-79`). adapter는 **DB의 epoch**를 따로 lease 검사에 넘긴다(`build_adapter.py:290` `database_recovery_epoch=self.db.recovery_epoch`). **builder의 epoch와 DB의 epoch를 비교해야 하는지**가 정해져 있지 않다.
4. **PID 생존 재검증을 제품 조건으로 올릴지.** `#303`(head `2c07dde6`)이 그 History에 스스로 적는다 — **"PID 생존 재검증은 `tools/run_buildkit_rootless_roundtrip.py`의 CI evidence 도구 경계에만 있다. 제품 transport 조건으로 아직 연결되지 않았으므로 제품 daemon liveness 합격을 주장하지 않는다."** 올린다면 그 검사는 도구에서 transport로 옮겨야 한다.
5. **enable의 단위.** 전역 환경변수인가, tenant별인가, builder profile별인가. kill switch는 **tenant별**(`inv.tenant_controls`)이고 lease는 **resource별**이다 — enable이 전역이면 그 둘보다 거친 단위가 된다.

### 2-2. 실패·취소·회수

| 이미 정해진 것 | 어디 |
|---|---|
| 어떤 예외든 cancel → quarantine 감사 | `build_adapter.py:356-360` |
| **cleanup 실패를 삼키지 않는다** | `:361-366` `VERIFY-0022`/409 |
| commit된 claim은 **재생 없음** | `:171-179` 주석과 `IDEM-0001` |
| 외부 호출 후 live 검사 전부 반복 | `:327-339`, `build_governance.py:180` |

**아직 정해지지 않은 것:**

1. **`cancel_and_quarantine`이 실제로 무엇을 하는가.** buildctl에는 "지금 실행 중인 그 빌드"를 가리키는 식별자가 필요하다 — session id인지, 별도 프로세스 그룹인지, daemon prune인지. **회수의 완료를 무엇으로 증명하는가**(모듈이 요구하는 "authenticated physical cleanup receipt"가 이것이다).
2. **부분 export의 처리.** OCI tar가 반쯤 쓰인 상태에서 실패하면 그 파일은 Evidence가 아니다. **삭제인지 격리 보관인지**, 격리라면 누가 언제 지우는지.
3. **crash 후 운영자 조정 절차.** claim은 commit됐고 외부 상태는 알 수 없는 경우를 모듈이 **의도적으로 열어 둔다**. 그 조정이 운영 문서의 어느 절이 되는지(사용자 조치인지 agent 조치인지는 `#300`의 원칙으로 가른다).

### 2-3. 감사

| 이미 정해진 것 | 값 |
|---|---|
| 두 이벤트 | `inv.build.dispatch_claimed` · `inv.build.dispatch_quarantined`(`build_adapter.py:211`·`:231`) |
| 적는 내용 | `bindingDigest`·`resourceId`·`leaseId`·`leasedNodeId`·`reasonCode` — **redacted**, 사용자 식별자 없음 |
| pre-admission 거부 | **Evidence 없음**(private 경계) |

**아직 정해지지 않은 것:** 성공 dispatch의 **완료** 이벤트가 없다(claimed와 quarantined만 있다). Evidence가 저장되는 자리가 그 역할을 하는지, 별도 `inv.build.dispatch_completed`가 필요한지. 그리고 **AC-11/AC-12 수락 경계의 canonical denial 규칙**(`app._record_denial`)과 이 outbox 경로가 **같은 규칙 아래 있는지** — build 경계는 route가 아니라 private 경계여서 그 ratchet의 적용 대상이 아니다.

### 2-4. idempotency

**이미 정해져 있고 바꾸면 안 된다**: key는 `action_digest({"decisionId": ...})` **단독**이고, Run·lease·Node·fence는 `request_hash`(= `binding_digest`)에만 들어간다. 그래서 **같은 결정의 교차 Run 재사용은 다른 내용으로 충돌**하고(`IDEM-0001` "different content"), **같은 digest의 재시도도 거부된다**(`"already consumed"`). caller가 추가로 정할 것은 하나다 — **클라이언트가 `Idempotency-Key`를 들고 오는 공개 경로가 생기면 그 key와 이 내부 claim key의 관계**다. 두 개를 같은 것으로 다루면 외부 입력이 내부 claim을 가리키게 된다.

### 2-5. 사용자 노출 범위

지금은 **노출이 없다**(route 0건). 결정해야 할 것:

1. **공개 route를 여는지, Run 단계로만 두는지.** 후자면 사용자는 Run을 만들고 build는 그 안의 한 단계가 된다 — 노출면이 작다.
2. **거부를 얼마나 말하는지.** `#282`의 수락 route가 세운 규칙은 "**어떤 전제가 빠졌는지 말하지 않는다**"(한 문장 `SYS-0003`/503)이고, 그 이유는 전제를 말하는 것이 배포 구조를 설명하는 것이기 때문이다. build 거부도 같은 규칙을 따라야 하는지 — `RES-0006`/`RES-0003`/`AUTH-0061`은 **서로 다른 정보를 준다**.
3. **빌드 로그·OCI digest를 사용자에게 보여주는지.** daemon stdout에는 빌드 컨텍스트가 섞이고, 그것이 곧 **다른 테넌트의 것이 아님**을 보장하는 것은 worker 독점 조건뿐이다.

## 3. CI에서 증명 가능한 범위와 아닌 범위

**외부 전제(실 builder 노드 — `#300` 체크리스트 §10)와 무관하게** 나눈다. 이 구분이 중요한 이유는, "실장비가 없으니 아무것도 못 한다"가 **거짓**이기 때문이다 — 지금 hosted CI에서 증명되는 것이 이미 상당하다.

### 3-1. CI에서 증명되는 것 (이미 증명됐거나, 구현만 하면 증명된다)

| 항목 | 상태 |
|---|---|
| 실제 rootless `buildkitd`와의 왕복 | **증명됐다** — `#297` run `36917312770`(head `dd9672a3`): `verdict: MEASURED_PASS`, `buildkitd … v0.20.2`, `imageDigest sha256:645455d2…`, `cleanCheckout: true` |
| OCI archive **내부** digest 재계산 대조 | **증명됐다**(`#303` head `2c07dde6`): `oci-layout`·`index.json`·manifest·config·모든 layer blob의 size와 SHA-256 재계산, metadata digest와 일치 요구. run `36928934670`(source `ad5b25f3`), artifact `11195047135`, archive SHA-256 `a714a972…897c` |
| 실 daemon **PID 생존·identity** | **증명됐다**(같은 PR): PID 32·UID 1000·start ticks 28815·`comm == buildkitd`, 왕복 전후 동일. 단 **CI 도구 경계에서만**(§2-1-4) |
| 경로 공격·tar 함정 거부 | **증명됐다**: 절대·상위·backslash 경로, symlink/hardlink/특수 member, 중복 파일, 누락 blob, 미참조 blob, duplicate-key JSON → `VERIFY-0002`. focused **78 passed** |
| admission·lease·claim·quarantine의 **분기 전부** | **증명 가능하다** — `tests/core/test_build_adapter.py`가 이미 fake transport로 그 분기들을 돌린다. 제품 caller가 생기면 그 caller의 분기도 같은 방식으로 증명된다 |
| **CI 완화값 거부**(§2-1-2) | **증명 가능하다** — 제품 허용 집합에 `-ci-reference`가 없음을 단언하는 시험은 실장비가 필요 없다 |
| health receipt **위조 거부** | **증명 가능하다** — mode·nlink·symlink·신선도·key 집합 거부는 전부 로컬 fixture로 된다 |
| idempotency 재생 거부 | **증명됐다**(adapter 시험) |

### 3-2. CI에서 증명되지 **않는** 것

| 항목 | 왜 |
|---|---|
| **격리의 실효성** | hosted runner에서는 `seccompMode`·`lsm`이 `-ci-reference` 값으로 기록된다 — 그 완화를 적어 두는 것이 정직한 처리이고, **완화된 환경에서 격리를 증명할 수는 없다** |
| **LAN builder 운영 인수** | `#300` 체크리스트 §10. `#297`·`#303`이 스스로 `BLOCKED_EXTERNAL`이라고 적는다 |
| **물리 cleanup 영수증** | 회수가 실제로 외부 side effect를 없앴다는 증명은 그 호스트에서만 된다 |
| **다중 테넌트 동시 빌드의 worker 독점** | 지금 조건은 "worker가 정확히 1개"이고, 그것은 **한 번에 한 빌드**를 뜻한다. 동시성의 실제 거동은 실 builder에서만 |
| **장시간 daemon 수명·drain** | `S11-BE`의 long-soak 축과 같은 전제 |

**그래서 이 연결의 구현은 외부 전제를 기다리지 않아도 된다.** 기다려야 하는 것은 **합격 선언**이고, 구현과 그 fail-closed 분기의 증명은 지금 CI에서 가능하다. 다만 **격리 실효성과 cleanup 영수증이 없는 동안 flag를 제품에서 켜는 것은 안 된다** — 그것이 §4의 첫 질문이다.

## 4. Codex에게 묻는 계약 질문

빌드 실행 경로의 계약 owner는 Codex다. 아래는 **결정이 필요한 것만** 적었고, 각 질문에 **내가 기본값으로 삼을 답**을 함께 적어 둔다 — 답이 없으면 그 기본값으로 설계안을 만들겠다는 뜻이고, 구현은 승인 뒤에 한다.

1. **flag를 제품에서 켜는 전제는 무엇인가.** 내 기본값: **(가) 물리 cleanup 영수증 계약이 정해지고 `cancel_and_quarantine`이 그것을 반환하며, (나) `isolation` 허용 집합에서 `-ci-reference` 값이 제외되고, (다) health receipt를 control plane이 신뢰하는 주체가 쓰며, (라) 그 셋의 거부가 시험으로 고정된 뒤** — 그 전에는 `INV_BUILDKIT_REFERENCE_ENABLED`를 제품 설정에 **추가하지 않는다**.
2. **health receipt의 writer를 무엇으로 두는가.** 내 기본값: **builder 호스트의 node agent가 쓰고 control plane이 읽는다.** caller가 쓰는 구조는 금지. 그렇다면 그 파일의 전달 경로와 인증(mTLS node identity? `runtimeIdentity` 대조?)이 계약에 필요하다. 그리고 `recoveryEpoch`는 **DB의 epoch와 같아야 하는지** — 내 기본값은 **같아야 한다**(builder가 과거 epoch의 상태를 들고 있으면 fence가 무의미해진다).
3. **PID 생존 재검증을 제품 transport 조건으로 올리는가.** 내 기본값: **올린다** — `dispatch` 직전과 직후에 같은 PID·start ticks를 요구하고 불일치면 `VERIFY-0002`. `#303`이 그 검사를 도구에만 둔 것은 범위 때문이고 계약상의 반대는 아니라고 읽었다.
4. **`cancel_and_quarantine`의 완료를 무엇으로 증명하는가.** 내 기본값: **buildctl session/프로세스 식별자로 중단하고, 부분 export를 격리 디렉터리로 옮기고, 그 둘을 적은 서명 없는 receipt를 반환한다.** 다만 "authenticated physical cleanup receipt"라는 모듈의 표현이 **서명을 요구하는지**가 불명확하다 — 요구한다면 그 키의 주인이 계약 질문이다.
5. **성공 완료 이벤트를 추가하는가.** 내 기본값: **추가한다**(`inv.build.dispatch_completed`, redacted). 지금은 claimed와 quarantined만 있어 **성공한 dispatch가 outbox에 남지 않는다.**
6. **Evidence 저장의 주인은 caller인가.** `finalize_build`는 Evidence를 **반환만** 한다(`build_governance.py:360-369`). 내 기본값: **caller가 같은 트랜잭션 안에서 저장한다** — 반환 후 별도 트랜잭션이면 "재검증은 통과했지만 Evidence는 없는" 창이 생긴다.
7. **사용자 노출면을 어디까지 여는가.** 내 기본값: **공개 route를 열지 않는다.** build는 Run의 한 단계로만 들어가고, 거부는 `#282`의 규칙대로 **전제를 말하지 않는 한 문장**으로 줄인다.
8. **공개 `Idempotency-Key`와 내부 claim key의 관계.** 내 기본값: **분리한다** — 외부 key는 요청 수준, 내부 claim key는 `decisionId` 단독. 두 개를 합치면 외부 입력이 내부 claim을 가리킨다.
9. **`S08-BE` 75의 조건을 이 연결로 보는 것이 맞는가.** 재채점 v1.10 §4-7-2가 적은 셋(제품 경로의 import, 모듈이 적은 세 선행, 후보 tree 자신의 8 lane 중 하나에서의 측정) 중 **세 번째**가 특히 계약 질문이다 — 이 lane은 지금 opt-in이고 8 lane이 아니다. **8 lane에 넣는 것이 맞는지**, 아니면 **dispatch-only lane의 측정을 후보 tree에 결속하는 다른 방법**이 맞는지.

## 5. 이 메모가 하지 않은 것

- **코드를 쓰지 않았다.** `buildkit_transport.py`·`build_adapter.py`·`build_governance.py`는 손대지 않았다. 카드 210의 범위가 설계 메모와 계약 요청이고, 빌드 실행 경로는 승인 없이 연결할 곳이 아니다.
- **`#303`을 검토하지 않았다.** 그 PR의 사실은 **그 History가 적은 것을 그대로 인용**했고(head `2c07dde6`), 내가 재측정한 것은 **`d0b2a4c6`에 있는 코드**뿐이다. `#303`의 독립 검토는 별건이다.
- **`S08-BE`의 점수를 바꾸지 않았다.** v1.10 §4-7-2의 50 유지가 그대로다.
- **실 builder 노드를 가정하지 않았다.** §3의 구분이 그것이고, 그 전제는 `#300` 체크리스트 §10이 정본이다.
- **`inv.outbox` 소비자 쪽을 읽지 않았다.** 감사 이벤트가 어디로 흘러가 무엇이 되는지는 이 메모의 범위 밖이고, §2-3의 질문은 **이벤트의 유무**에 관한 것이다.
- **`ROOF` 네 영역 전체를 다시 세지 않았다.** 이 메모는 `S08-BE` scope 중 **BuildKit 영역의 연결**만 다룬다. GPU·kill switch·ROOF의 상태는 v1.10 §4-7-2의 측정이 최신이다.

## 6. 다음 첫 행동

1. **Codex(계약 owner)**: §4의 아홉 질문. 특히 1·2·4가 정해지면 나머지는 그 아래에서 결정된다.
2. **Claude**: 답을 받으면 **설계안**(이 메모의 §2를 결정표로 바꾼 것)을 먼저 올리고, 승인 뒤에 구현한다. 구현 범위는 §3-1의 "증명 가능한 것"에 한정하고, flag는 제품 설정에 **넣지 않는다**.
3. **코디네이터**: §4-9(이 lane을 8 lane에 넣을지)는 train 구성에 영향을 주므로 계약 답과 함께 판단이 필요하다.
