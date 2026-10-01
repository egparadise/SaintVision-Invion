---
doc_id: "DESIGN-S08-BE-ROOF-BUILDKIT-SINGLE-GPU-001"
title: "S08-BE ROOF·BuildKit·단일 GPU 구현 설계"
version: "1.1.0"
status: "proposed"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-01T12:42:40+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "7851412db792b4ef6c53cb92944be530d77eb2de"
task_ids: ["S08-BE"]
tags: ["s08-be", "roof", "buildkit", "gpu", "runtime-governance", "contract-first"]
---

# S08-BE ROOF·BuildKit·단일 GPU 구현 설계

## 0. 선택 근거와 범위

`S08-BE`의 정본 scope는 [[S08 운영 통제]]의 **ROOF·kill switch·BuildKit·단일
GPU**다. #264 v1.7 source head `561cd22b8e053650699d273a676538b9881c12aa`는
kill switch만 제품 경로에 있고 나머지 세 축은 구현이 없다는 이유로 이 task를 50에
유지했다. 이 문서는 구현보다 계약을 먼저 고정한다. 제품 코드, migration, registry
status와 점수는 바꾸지 않는다.

기준 tree는 아직 integration에 착지하지 않은 train 5
`7851412db792b4ef6c53cb92944be530d77eb2de`다. #264는 이 tree의 후손이 아니므로
그 문서 내용을 입력으로 읽었을 뿐 이 branch의 조상이라고 주장하지 않는다.

## 1. ROOF의 정본 의미

### 1.1 정의는 이미 있다

ROOF는 정의가 없는 약어가 아니다. [[용어 사전과 6단계 통합 모델]] §5는 이를
SaintVision 내부의 가로 통제 계층으로 정의한다.

| 글자 | 정본 의미 | S08-BE 적용 |
|---|---|---|
| R | Risk controls | 고정 정책, 승인, least privilege, deny-by-default |
| O | Observability | 결정·입력·출력 digest, 실행·정리 Evidence |
| O | Ownership and approvals | tenant/project/subject 결속, 두 사람 승인, 운영자 책임 |
| F | Failure containment and fallback | kill switch, drain, 취소, lease 회수, 안전 중단 |

ROOF는 외부 표준이나 새 monolithic service 이름이 아니다. 코드와 계약에는
`runtime-governance`, `policy`, `observability`, `recovery` 같은 표준 이름을 쓰고,
제품 설계에서만 이 네 영역의 묶음을 ROOF라 부른다. 따라서 “ROOF 구현”의 수용
기준은 `roof.py` 같은 파일의 존재가 아니라 아래 BuildKit·GPU 경로가 네 축을 모두
통과하고 정본 `PolicyDecision`과 `EvidenceEnvelope`에 결속되는 것이다.

### 1.2 현재 구현 경계

- `services/control-plane/src/inv/containment.py`의 tenant kill switch와 Node drain은
  실행 gate·취소 reconciliation을 제공한다. 이는 F와 R의 일부이지 BuildKit/GPU의
  격리·관측·회수를 자동으로 증명하지 않는다.
- `contracts/v1alpha1/core.schema.json`에는 strict `PolicyDecision`과
  `EvidenceEnvelope`가 있다. 새 경로는 이를 재사용하고 별도 느슨한 evidence 형식을
  만들지 않는다.
- `services/control-plane/src/inv/workspace_api.py`의 verified profile은 임의의
  BuildKit/GPU 능력을 인증하지 않는다고 명시한다. capability 낱말이나 discovery
  announcement만으로 실행을 열지 않는다.

## 2. 공통 불변식

BuildKit과 GPU 모두 다음 순서를 지켜야 한다.

1. strict request validation → live tenant/project access → frozen action digest → current
   policy/approval → fresh measured provider observation → resource lease/claim → dispatch.
2. 외부 호출 전 짧은 authorization transaction, 외부 호출 뒤 새 final transaction에서
   권한·policy expiry·kill switch·provider observation·lease fencing을 재검증한다.
3. dispatch permit은 tenant/project/run/node, policy/profile version, recovery epoch,
   action/plan digest, expiry를 고정한다. permit 밖 ambient environment를 권한으로 쓰지
   않는다.
4. kill switch 또는 drain 뒤 새 dispatch는 0건이어야 한다. 이미 시작된 작업은 bounded
   cancel → 실제 종료 receipt → lease/cache/workspace 정리 순서로 수렴한다.
5. provider 부재, stale/claimed-only observation, 알 수 없는 필드, 측정 누락, cleanup
   미확인은 PASS로 바꾸지 않고 `NOT_OBSERVED` 또는 기존 fail-closed ProblemDetails로
   남긴다.
6. 비밀 값, raw token, private key, registry credential은 request hash·로그·audit·
   cache key·image layer·Evidence에 들어가지 않는다.

## 3. BuildKit 결정

### D-B1. Node Docker 실행기와 분리한 rootless Build Service

기존 `services/node-agent/runtime/docker.go`는 운영자가 설정한 로컬 Unix socket에
연결하는 privileged control boundary다. workload에는 socket을 노출하지 않지만,
이를 build 사용자에게 재노출하거나 Docker-in-Docker로 감싸지 않는다.

첫 구현은 Linux 전용의 별도 rootless BuildKit service와 좁은 adapter로 한다.

- BuildKit daemon은 전용 비로그인 OS 계정과 전용 state/cache root를 사용한다.
- adapter만 전용 Unix socket에 접근한다. workspace, build container, user shell에는
  Docker/BuildKit socket을 mount하지 않는다.
- `--privileged`, `security.insecure`, `network.host`, host PID/IPC, host device, 임의
  bind mount, SSH agent forwarding은 거부한다.
- build context는 승인된 source tree의 clean commit에서 staging한 read-only bounded
  directory다. symlink·hardlink·`..`·absolute path로 root 밖을 참조하면 거부한다.
- daemon이나 socket의 부재는 다른 Docker socket fallback으로 우회하지 않는다.

### D-B2. 계약은 WorkloadSpec과 분리한다

`WorkloadSpec`은 이미 고정 image를 실행하는 계약이다. source를 image로 만드는 일을
그 schema에 과적재하지 않는다. 구현 카드에서 다음 strict schema를
`contracts/v1alpha1/core.schema.json`에 추가하고 generated bindings를 함께 갱신한다.

| 계약 | 필수 내용 |
|---|---|
| `BuildRequest` | tenant/project/workspace, clean source commit SHA와 tree SHA, context·Dockerfile의 canonical relative path, target/platform, network policy ID, cache policy ID, opaque secret reference ID 목록, timeout |
| `BuildPlan` | request/action digest, current `PolicyDecision` ID/version/expiry, builder instance·profile·recovery epoch, rootless=true, privileged=false, hostAccess=false, network policy와 허용 egress host+port digest, devices=[], binds=[], CPU/memory/storage budget와 lease/fencing, cache namespace digest, resolved immutable base image digest 목록 |
| `BuildReceipt` | plan digest, source/tree SHA, output image/config digest, SBOM·scan evidence digest, cache input/output digest, redacted network summary, started/finished timestamps, result, cleanup receipt |

모두 `additionalProperties:false`다. source branch·tag, mutable base tag, literal secret,
arbitrary build arg/environment, caller supplied output digest는 받지 않는다. 새 공개 route가
필요한지는 구현 카드에서 route inventory와 함께 결정하되, 어떤 route도 기존
`WorkloadSpec`을 build request로 해석하지 않는다.

`rootless`, `privileged`, `hostAccess`, `devices`, `binds`는 caller가 선택하는 옵션이
아니라 위 literal로 고정한다. network는 `none` 또는 policy가 고정한 allowlist profile만
허용한다. builder daemon은 bounded service CPU/memory/storage quota 안에서만 실행하고,
각 build job은 별도의 tenant+project resource budget과 lease/fencing을 소비한다. 따라서
build가 placement 바깥의 무제한 side channel이 되지 않는다. kill switch와 drain은 새
job을 거부하고 진행 job을 cancel하며, lease·cgroup·cache cleanup receipt 전에는 자원을
재사용하지 않는다.

### D-B3. network·cache·secret 정책

- network 기본은 `none`이다. dependency fetch가 필요한 profile만 hostname+port
  allowlist와 TLS trust bundle digest를 policy에 고정한다. redirect, proxy environment,
  DNS 결과 drift와 허용 밖 목적지는 거부한다.
- cache key는 tenant+project+builder instance+builder profile+recovery epoch+source tree+
  Dockerfile+resolved base digest+build args digest를 포함한다. cross-tenant import/export와
  mutable cache ref는 금지한다. cancel·cleanup 미확인 또는 epoch 변경 뒤에는 이전 key를
  quarantine하고 재사용하지 않는다.
- secret은 opaque ID만 계약에 넣고 실행 직전에 authorized provider에서 받아 BuildKit
  secret mount로만 전달한다. file/argv/env/layer/cache/log에 남지 않는 것을 부정 시험과
  output inspection으로 확인한다.
- registry push는 별도 approval action이다. build 성공이 publish 또는 deploy 승인을
  뜻하지 않는다.

### D-B4. 감사와 회수

요청·policy decision·builder claim·start·network decision·output digest·scan·cancel·
cleanup을 같은 trace로 기록한다. 출력 digest와 receipt가 다르거나 cleanup이 확인되지
않으면 성공으로 완료하지 않는다. kill switch 시 adapter는 build cancel을 보내고,
bounded deadline 안에 종료가 확인되지 않으면 builder를 quarantine하며 cache를 다른
작업에 재사용하지 않는다.

BuildKit worker는 rootless user namespace(`newuidmap`/`newgidmap` mapping 검증), seccomp,
AppArmor 또는 SELinux, no-new-privileges와 per-job cgroup quota를 동시에 적용한다. 하나라도
지원·적용 여부를 read-back하지 못하면 dispatch하지 않는다. daemon이 살아 있다는 사실만으로
job 격리나 quota가 측정됐다고 보지 않는다.

## 4. 단일 GPU 결정

### D-G1. claimed count가 아니라 측정된 device provider

`services/node-agent/discovery/announce.go`의 `gpuCount`는 admission·offer·placement를
부여하지 않는 claimed discovery다. GPU 실행의 authority로 사용하지 않는다.

`services/control-plane/src/inv/scheduler.py`는 device ID와 VRAM을 계산할 수 있지만,
`services/control-plane/src/inv/placement.py`는 measured provider가 없어 GPU 요청을
`RES-0008`로 닫고, `services/control-plane/src/inv/sandbox.py`도 `gpuCount != 0`을
거부한다. 이 두 거부는 provider와 end-to-end allocation이 준비될 때까지 유지한다.

첫 provider는 정확히 GPU 1개만 지원한다. 다음 조건을 모두 측정해야 한다.

- stable opaque device ID, vendor/model, total VRAM, compute capability
- driver와 container runtime/toolkit compatibility
- exclusive allocation capability, health, observation timestamp와 bounded freshness
- Node identity, recovery epoch, profile version, provider version과 observation digest

MIG/partition, multi-GPU, collective, Windows native GPU는 이 카드 범위 밖이며 계속
fail closed다.

### D-G2. 필요한 계약 delta

- `NodeResourceSnapshot`에 strict `gpuDevices[]` measured observation을 추가한다. 비어
  있거나 생략되면 GPU provider는 없는 것이다. announcement의 `gpuCount`로 보충하지
  않는다.
- `SandboxLaunchSpec`에 optional strict `gpuAllocation`을 추가한다. device ID, resource/
  lease ID, fencing token, observation digest, provider/profile version을 포함한다.
- 기존 `ResourceRequest.gpuCount/minVramBytes`는 유지하되 S08 adapter는
  `gpuCount in {0,1}`과 `gpuCount=0 ⇔ minVramBytes=0`을 강제한다.
- `ExecutionClaim.planDigest`가 GPU allocation을 포함한 launch plan 전체를 서명한다.
  Node는 permit의 allocation과 live provider inventory가 exact match일 때만 exact device
  request를 만든다. caller supplied `NVIDIA_VISIBLE_DEVICES` 같은 환경 값은 무시·거부한다.

Node의 Docker create 뒤 read-back은 실제 `Devices`/`DeviceRequests`가 서명된
`gpuAllocation`의 device ID·count·capability와 정확히 같을 때만 허용한다. GPU 없는 plan은
두 필드가 모두 비어 있어야 하고 `Binds`는 GPU 유무와 관계없이 항상 0이다. 불일치·추가
device·broad capability·bind가 하나라도 있으면 기존 `NODE-0024` 거부를 유지한다. 이를
위해 `services/node-agent/runtime/docker.go`의 현재 비어 있지 않은 device 거부는 임의
완화하지 않고, permit exact-match 분기에서만 좁게 대체한다.

GPU resource row와 lease는 device별이어야 한다. CPU/memory aggregate lease만 잡고
GPU를 실행하지 않는다. final commit에서 fresh observation, offer, active lease 합계,
exact device 미사용, kill switch와 recovery epoch를 재검증한다.

### D-G3. 격리·회수

- GPU launch는 non-root, cap drop, no-new-privileges, read-only rootfs, host access false를
  유지한다. `--privileged`나 broad `/dev` mount 대신 provider가 선택한 exact device만
  runtime request로 전달한다.
- 동일 device 동시 lease는 0이어야 한다. fencing token이 stale이면 Node가 거부한다.
- cancel/timeout/kill 뒤 container의 실제 종료와 provider detach receipt를 확인한 뒤에만
  device lease를 release한다. release 실패·health drift는 device/Node quarantine이다.
- 합성 provider는 placement·fencing·정리 계약을 시험할 수 있지만 실 GPU 실행 성공의
  대체 증거가 아니다.

## 5. 수용 기준

### 5.1 ROOF/kill switch

- 정책 deny/expiry/approval 부족, tenant/project drift, kill switch, draining Node가
  Build/GPU dispatch 이전에 거부되고 side effect가 0이다.
- 허용·거부·실패·cancel·cleanup이 정본 `PolicyDecision`·`EvidenceEnvelope`와 같은
  trace/digest에 묶인다.
- kill switch 중 새 실행 0, 진행 작업 bounded cancel, 미확인 작업/lease는 quarantine.

### 5.2 BuildKit

- rootless builder로 고정 source tree를 build하고 output image digest, SBOM/scan digest,
  cleanup receipt를 만든다.
- build container에서 Docker/BuildKit socket, privileged, host path/device/network를 얻는
  우회가 0이다.
- secret canary가 layer/history/cache/log/Evidence에 0건이고 cross-tenant cache hit가 0이다.
- immutable input replay는 같은 plan/output digest를 만들고, input/base/policy drift는 새
  plan 또는 거부가 된다.

### 5.3 단일 GPU

- fresh measured provider + exact offer/lease + compatible profile에서 synthetic provider
  1-GPU normal/cancel/replay/fencing 시험이 통과한다.
- provider 없음·claimed only·stale·health/runtime mismatch·VRAM 부족·중복 lease·
  gpuCount>1은 모두 launch side effect 0으로 거부한다.
- task registry의 AC-08 criterion 3인 “합성 GPU 실행 성공”은 synthetic provider의
  product implementation 증거로 충족할 수 있다. 그러나 AC-08 전체에는 Docker socket,
  approval bypass, backup/restore 등 다른 기준이 함께 있고, 실제 단일 GPU에서 device
  identity, VRAM observation, workload output, cancel, detach, 재할당을 측정하기 전에는
  S08-BE done·100이나 물리 인수 PASS를 주장하지 않는다.

## 6. 필수 부정 시험

| 축 | 되살리면 실패해야 하는 변이 |
|---|---|
| 공통 | final 권한 재검증 제거, expired policy 허용, kill switch 검사 순서 뒤집기, unknown field 허용, evidence digest 미대조 |
| BuildKit | BuildPlan literal 완화, host socket mount, privileged/host entitlement, user namespace/seccomp/LSM/cgroup 하나 제거, budget/lease 없는 job, context path escape, mutable base tag, allowlist 밖 egress/redirect/proxy, literal secret, cross-tenant cache, builder instance/epoch 없는 cache key, output digest 위조, cancel 뒤 cache 재사용 |
| GPU | announcement count로 provider 합성, stale snapshot 허용, gpuCount 2 허용, unknown/duplicate device, insufficient VRAM, runtime drift, permit과 다른 Devices/DeviceRequests read-back, Binds 허용, stale fencing, 종료 receipt 전 lease release |

PG-free에서는 schema·policy·adapter·mutation 시험을 한다. hosted에서는 rootless BuildKit과
synthetic GPU provider를 opt-in lane에서 한 job씩 실행하고 exact PR head, clean checkout,
도구/version, JUnit과 redacted Evidence를 보존한다. 기본 CI는 무거운 daemon이나 GPU를
자동 기동하지 않는다.

S08-BE 자금 귀속 시험은 새 이름으로 분리한다. Go의 Node runtime read-back/permit 시험,
BuildKit contract·adapter 시험, GPU provider 시험이 각각 S08-BE를 fund한다. 기존
`tests/core/test_sandbox_contracts.py`는 S03-BE, `tests/integration/test_containment.py`는
S07-BE 소유 증거이므로 S08-BE 합격 건수로 중복 계산하지 않는다.

## 7. 외부 전제와 판정 경계

| 항목 | 구현·hosted에서 가능 | 외부 전제 / 완료 전 판정 |
|---|---|---|
| ROOF | strict policy/evidence/kill/cancel/cleanup 결속 | 운영 alert·incident drill은 별도 인수 |
| BuildKit | hosted rootless daemon, 우회·secret·cache 부정 시험 | LAN builder 설치·운영 registry credential·운영 egress policy는 외부 운영 인수 |
| GPU | synthetic provider로 AC-08 criterion 3의 contract·placement·fencing·회수 | Linux 단일 GPU 장비, driver/toolkit, 승인 image와 operator 관측이 필요; 그 전 S08-BE 물리 인수는 `BLOCKED_EXTERNAL` |
| 5-node | 코드·inventory preflight 재사용 | 실제 5-node 성능/복구는 G-19/G-24 외부 전제 |

`NOT_OBSERVED`, `BLOCKED_EXTERNAL`, synthetic PASS를 실제 GPU/운영 BuildKit PASS로
승격하지 않는다.

## 8. 구현 순서와 리뷰 게이트

1. **계약 카드**: BuildRequest/Plan/Receipt, GPU observation/allocation schema와 generated
   bindings, strict negative tests. 공개 route·새 ProblemDetails가 필요하면 이 단계에서
   별도 계약 diff로 제시한다.
2. **BuildKit 카드**: rootless adapter, policy/evidence/cancel/cleanup, PG-free + hosted
   opt-in lane. Node Docker socket 경계는 건드리지 않는다.
3. **GPU 카드**: synthetic measured provider, device lease/fencing, launch/teardown,
   permit↔Docker read-back exact match. 기본 provider는 none이고 기존 GPU 거부를 유지한다.
4. **실장비 인수 카드**: 운영자가 준비한 단일 GPU와 LAN builder에서 exact landed SHA로
   실행한다. 여기서만 AC-08의 물리 증거를 판정한다.

Claude가 이 설계와 계약 delta를 승인하기 전 제품 코드·migration을 구현하지 않는다.
S08-BE registry는 `planned`, 점수는 50을 유지한다.
