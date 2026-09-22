---
doc_id: "CODEX-FIVE-NODE-LAB-LANE-001"
title: "Codex 5노드 랩 opt-in lane 정의"
version: "1.6.0"
status: "proposed"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T10:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["five-node", "lab", "workflow-dispatch", "S05", "S06", "S07", "benchmark", "NTP", "mTLS"]
---

# Codex 5노드 랩 opt-in lane 정의

이 문서는 S05/S07 opt-in 측정과 S06 원격 WS/PTY/Git 재시작 여정을 **등록 실행 Node 5개 랩**에서만 실행하기 위한 수동 lane 제안이다. v1.6는 [[ADR-100 CP 호스트의 Node 겸임과 5노드 측정 경계]]의 CP 겸임 Node 제외 규칙과 [[2026-09-22_S05_배치잠금_입도_결정제안_Codex]] v1.4를 함께 고정하고, `placement_benchmark.py`의 물리 inventory read-only dry-run 계약과 [[S07 5노드 실 Node adapter 사양]]을 연결한다. Windows Control Plane 호스트의 Docker Desktop Linux Node 1개는 all-five topology에만 포함하고, 별도 Ubuntu 물리 Node 4개만 S05 timed wave와 S07 기본 disruption 분모에 넣는다. `placementShortCommit`은 계속 기본 off이며 현재 승인 범위는 inventory-bound **legacy 20동시 선측정 계획**과 S07 read-only preflight 사양까지다. 실제 S07 adapter 구현·Node disruption과 복구 wave는 후속 승인 대상이다.

## 토폴로지 B와 수량 의미

| 구성 | 실행 Node | CP와 물리 독립 | S05 timed wave | S07 기본 disruption |
|---|---:|---:|---:|---:|
| Windows 물리 호스트: Control Plane + Docker Desktop Linux Node | 1 | 아니오 | 제외·별도 smoke만 | 제외·별도 상관 장애 drill만 |
| Ubuntu 물리 호스트 4대 | 4 | 예 | 포함 | 포함 |
| 합계 | 등록 identity 5 | CP 독립 host 4 | eligible 4 | eligible 4 |

Docker Desktop VM을 별도 물리 호스트로 세지 않는다. 다섯 Node는 서로 다른 `nodeId`·인증서·epoch을 유지하지만 겸임 Node는 CP와 전원·CPU/RAM·disk·NIC·host clock·Docker runtime 실패 영역을 공유한다. manifest는 언제나 `registeredNodeCount=5`, `physicalExecutionHostCount=5`, `cpIndependentWorkerHostCount=4`, `cpColocatedNodeCount=1`을 함께 남긴다. `docs/task-registry.json`의 5대 기준은 등록 실행 Node identity 수이므로 유지하지만 “CP와 독립적인 worker 5대”라고 해석하지 않는다. `coLocatedWithControlPlane` 선언만 신뢰하지 않고 CP와 Node의 host/machine identity·failure-domain·Docker Desktop VM parent를 preflight에서 유도해 선언값과 대조한다. 유도값이 다르면 측정을 시작하지 않는다.

## 카드 18 결정 (b)와 실행 권한

카드 18 착지 SHA `9dafbf09d084ed793301937ba7834a4ca057ba2d`의 대칭 계측은 개발 PC·합성 Node·20동시 각 1회에서 legacy 20/20, candidate 8/20을 기록했다. candidate 실패 12건은 모두 limits `FOR UPDATE`의 `55P03`이며, 대칭 post-acquire hold P95 289.365→170.766ms는 성공 survivor 표본이라 승격 근거가 아니다. 코디네이터 결정 (b)에 따라 다음 상태를 manifest와 preflight가 강제한다.

| 항목 | 현재 값 | 해제 조건 |
|---|---|---|
| 운영 기본 모드 | `legacy`, `placementShortCommit=false` | 별도 코디네이터 결정 |
| 물리 lane 최초 timed 실행 | eligible Ubuntu 4대의 legacy 20동시 × 3회 | inventory-bound adapter·all-five smoke·redaction/invariant preflight 통과 |
| candidate 20동시 | **미승인·실행 금지** | 승인된 Claude 카드 20 관찰을 반영한 큐 깊이 실측과 candidate 대기 정책에 대한 별도 승인 SHA |
| legacy/candidate 50동시 | **미승인·실행 금지** | 20동시 선행 증거 검토와 별도 50동시 승인 SHA |
| S05 상태 | `review` 유지 | 물리 증거와 독립 검토 뒤 registry owner 판정 |

Claude 카드 20은 P1/F-C1 해소, P2 SQL 귀속과 mode별 `lock_timeout` 면제 경로 없음, 결정 (b)의 근거를 승인했다. 추가 PG probe는 `lock_timeout`이 lock 대기 구간별로 다시 적용될 수 있어 얕은 legacy holder chain은 총 client elapsed가 500ms를 넘어도 획득 가능하고, speculation 뒤 같은 limits row에 깊게 줄 선 candidate는 한 구간에서 500ms를 넘어 `55P03`이 날 수 있음을 보였다. 이는 코드 건전성 검토이지 candidate 또는 50동시 실행 승인이 아니다. workflow 입력은 `decision_sha=9dafbf09...`, `candidate_authorized=false`, `fifty_authorized=false`를 기본값으로 기록하고, 승인 SHA가 없는 true 입력을 preflight에서 거부해야 한다. candidate를 다시 검토할 때는 요청 도착 timeline, holder/waiter chain, backend `wait_event`, queue depth, `log_lock_waits` 또는 동등한 server 관측을 artifact에 추가한다.

## 실행 경계와 입력

- runner: `[self-hosted, linux, x64, saintvision-five-node-lab]`, environment `five-node-lab`, concurrency group `saintvision-five-node-lab`, `cancel-in-progress: false`, 동시 실행 1개. GitHub hosted runner와 개발 PC의 합성 Node 시험은 5노드 판정에 쓰지 않는다. 같은 Windows PC가 topology B의 CP+겸임 Node로 참여할 때는 revision 고정 inventory·고유 mTLS identity·실 heartbeat/resource snapshot을 갖춘 실행만 topology evidence로 인정한다. 기존 `core.yml` job 안에 넣지 않고 별도 workflow로 분리해 일반 push가 물리 측정을 취소하지 못하게 한다.
- 공통 필수 입력: `code_sha`(40 hex), `inventory_revision`, `control_plane_image`·`node_agent_image`·`worker_image`·`postgres_image`(모두 immutable digest), `s07_repetitions=20`, `liveness_timeout_seconds=60`, `poll_interval_seconds=0.1`, `run_s06_remote=true`. inventory는 각 Node의 `hostId`·`failureDomainId`·`coLocatedWithControlPlane`·`measurementEligible.s05/s07`·`exclusionReason`을 포함해야 한다. preflight는 이 선언과 CP/Node host identity에서 유도한 co-location을 비교해 `coLocationValidation=matched|mismatch|unmeasured`로 남긴다.
- S05 필수 입력: 현재 실행 가능 기본값은 `s05_modes=legacy`, `s05_request_waves=20`, `s05_repetitions=3`, `s05_timeout_seconds=90`, `s05_candidate_setting=placementShortCommit`, `s05_candidate_default=false`, `s05_decision_sha=9dafbf09d084ed793301937ba7834a4ca057ba2d`, `candidate_authorized=false`, `fifty_authorized=false`다. candidate 또는 50을 요청하면 각각 별도 승인 SHA를 추가로 요구한다. true인데 승인 SHA가 없거나 현재 `code_sha`의 조상이 아니면 preflight 실패다.
- 환경변수: `PYTHONUTF8=1`, `PYTHONPATH=src:services/control-plane/src`, `INV_TEST_ADMIN_DSN=${FIVE_NODE_INV_TEST_ADMIN_DSN}`, `INV_S05_EXECUTOR=five-node-lab`, `INV_S07_EXECUTOR=five-node-lab`, `LAB_INVENTORY_PATH`(runner의 read-only 파일), `LAB_EVIDENCE_ROOT`(run별 빈 디렉터리). `PYTHONPATH`의 `:`는 Linux 구분자이며 Windows 개발 PC에 그대로 복사하지 않는다.
- secret 이름만 workflow에 선언한다: `FIVE_NODE_INV_TEST_ADMIN_DSN`, `FIVE_NODE_CA_PEM`, `FIVE_NODE_CONTROL_CERT_PEM`, `FIVE_NODE_CONTROL_KEY_PEM`, `FIVE_NODE_SIGNER_KEY_PEM`, 필요 시 `FIVE_NODE_REGISTRY_USERNAME`·`FIVE_NODE_REGISTRY_TOKEN`. 값·DSN·private state는 로그나 artifact에 넣지 않는다. node별 endpoint, 공개 인증서 fingerprint, OS/profile은 revision이 고정된 inventory에 두고 private key는 GitHub Environment 또는 runner secret store에서만 materialize한다.

사전 조건은 정확한 SHA의 clean checkout, digest pull·검증, 5개 등록 Node identity와 5개 물리 실행 host(Windows 1 + Ubuntu 4)의 mTLS preflight 및 `lan-workspace-v1` profile, 격리된 disposable PostgreSQL, 모든 Node의 시계 동기와 시작 전 active lease 0이다. CP 겸임 Node와 Windows CP의 시각은 둘 다 관측하되 독립 NTP 표본 두 개로 세지 않는다. timed wave 전에 `measurementEligible.s05=false`인 겸임 Node가 candidate 집합에서 제외됐음을 Explain으로 확인하고, CP host CPU/RAM/disk/NIC/Docker throttling을 같은 timeline에 기록한다. 하나라도 없으면 부하를 시작하지 않고 unavailable evidence를 남긴다. candidate 또는 50동시는 각각의 별도 승인 SHA 없이는 실행하지 않는다.

## S05-DB 5노드 실행 계획

### 물리 adapter와 동일 조건

현재 `tools/placement_benchmark.py`의 기본 `--adapter synthetic` 경로와 `--mode legacy|short-commit`, JSON schema 1.5, JUnit 출력은 기존 fixture가 만드는 합성 node row를 사용한다. v1.5는 이 기본값을 바꾸지 않고 다음 1번의 read-only preflight만 먼저 구현했다.

1. 같은 도구에 `--adapter five-node-lab --inventory "$LAB_INVENTORY_PATH"`를 추가해 실제 5개 node heartbeat/resource snapshot과 mTLS identity를 읽고 `measurementEligible.s05`를 candidate 구성 전에 적용한다.
2. 동일 JSON/JUnit schema를 내는 `tools/run_s05_five_node_benchmark.py` wrapper를 추가한다.

1번은 `--adapter five-node-lab --inventory <path> --dry-run`으로만 열려 있으며 PostgreSQL 트랜잭션이 `read only=on`임을 확인한 뒤 등록·heartbeat·resource snapshot·mTLS channel을 조회한다. 부하 실행 요청은 명시적으로 거부하고 JSON preflight만 출력한다. 2번과 물리 wave 실행은 아직 미구현이므로 v1.5 결과는 **물리 preflight**일 뿐 AC-05 물리 부하 증거가 아니다. adapter는 DB에 합성 node/resource row를 만들거나 heartbeat를 대신 갱신해서는 안 된다. timed wave 전에 CP 겸임 Node를 inventory 기준으로 cordon하거나 offer 0으로 만들어 Explain candidate에서 제외하고, 사후에 해당 샘플만 삭제해서 P95를 다시 계산하면 실패다. 매 wave는 동일 `code_sha`·inventory revision·image digest·policy version·resource offer·요청 body를 사용하고 mode만 바꾼다. 순서 편향을 보기 위해 repetition별 `legacy→candidate`, `candidate→legacy`, `legacy→candidate` 순서를 manifest에 고정한다.

#### v1.5 inventory·dry-run 계약

inventory root는 `schemaVersion`, `revision`, `controlPlaneHostId`, `nodes`만 허용한다. `schemaVersion`은 `1.0.0`이며 `revision`은 revision 필드 자체를 제외한 JSON을 UTF-8·키 정렬·공백 없는 구분자로 canonicalize한 SHA-256(`sha256:<64 lowercase hex>`)이다. `nodes`는 준비 중인 1~5개 물리 실행 host를 허용하되 all-five smoke/timed wave ready는 정확히 5개일 때만 가능하다. Node 항목의 정확한 키는 `nodeId`, private IPv4 `ip`, 공개 `certificateSHA256`, 실제 snapshot `profile`, `hostId`, `failureDomainId`, `coLocatedWithControlPlane`, `measurementEligible.{s05,s07}`, `exclusionReason`이다. node ID·IP·fingerprint·host ID는 모두 inventory 안에서 유일해야 한다.

`coLocatedWithControlPlane`은 `hostId == controlPlaneHostId`에서 유도한 값과 일치해야 한다. 겸임 Node는 `measurementEligible.s05/s07=false`, `exclusionReason=cp-host-colocation`이어야 하고, 독립 Node는 두 eligibility가 true이며 exclusion reason이 null이어야 한다. 현재 관측용 `lan-observe-v1` 같은 실제 profile도 inventory에는 기록할 수 있지만, snapshot과 일치해야 하며 `lan-workspace-v1`이 아니면 ready가 아니어서 all-five/timed 선택에 들어가지 않는다.

DB 조회는 `INV_TEST_ADMIN_DSN`만 사용하고 DSN을 report에 남기지 않는다. inventory Node가 DB에 없거나 여러 tenant에 중복 등록됐거나, endpoint IP·인증서 fingerprint·node/channel/snapshot epoch·channel version·snapshot tenant/node/profile identity가 다르면 exit nonzero다. offline/stale heartbeat, 비활성·만료 channel, stale/missing snapshot, `abs(clock_skew_seconds)>5`, workspace profile 미충족은 JSON의 Node별 `readiness.reasons`와 false ready로 남기며 heartbeat나 snapshot을 갱신하지 않는다. report는 `databaseReadOnly=true`, `syntheticRowsCreated=false`, `heartbeatUpdated=false`, `loadExecuted=false`, all-five/timed 선택 목록과 count를 반드시 포함한다.

개발 PC/파일럿 무부하 명령은 다음 한 줄이다. 이 명령의 exit 0은 DB read-only 조회와 분류 성공을 뜻하며 5노드 준비 또는 AC-05 통과를 뜻하지 않는다.

```powershell
$env:INV_TEST_ADMIN_DSN='<PG 55440 admin DSN>'; python tools/placement_benchmark.py --adapter five-node-lab --inventory '<revision-fixed inventory.json>' --dry-run --report .work/five-node-lab-preflight.json
```

### wave와 승격 게이트

| 단계 | 실행 | 통과 조건 | 실패 시 |
|---|---|---|---|
| 0 preflight | 등록 Node 5·물리 host 5·CP 독립 Ubuntu 4·NTP·mTLS·inventory·disposable PG·active lease 0 | 아래 준비표 전 항목 `ready`, 겸임 Node 표시와 비밀 redaction 0건 | 부하 미실행, unavailable JSON/JUnit과 원인만 업로드 |
| 0a all-five smoke | 5 Node 등록·heartbeat·resource snapshot·Explain 도달 | 5 identity와 certificate/epoch 경계 확인 | 기능 smoke 실패; timed wave 금지 |
| 1 legacy canary | eligible Ubuntu 4대에서 legacy 20동시 × 3회 | 각 요청 결과 기록, 겸임 Node 선택 0, overbooking 0, fencing 유일, stale epoch 수락 0, 실행 전후 active lease 기대값 일치 | 추가 wave 금지, red artifact 보존, S05 `review` 유지 |
| 2 candidate comparison | eligible Ubuntu 4대에서 candidate 20동시 × 3회 | **별도 승인 SHA가 있을 때만** 실행. legacy와 같은 입력·순서 교차·invariant, 외부 timeout 비증가 | 승인 없으면 `UNAUTHORIZED/NOT_RUN`; 실패 시 flag off 유지 |
| 3 acceptance wave | 승인된 mode의 50동시 × 3회 | **별도 50동시 승인 SHA가 있을 때만** 50/50, P95 ≤2초, 결정성, 겸임 Node 선택 0, overbooking 0, duplicate active Run 0, stale epoch 수락 0 | 승인 없으면 `UNAUTHORIZED/NOT_RUN`; 실패 시 AC-05 미달·`review` 유지 |
| 4 비교 | 승인돼 실제 실행한 mode만 비교 | candidate가 실행된 경우 post-acquire hold P95 감소 **AND** 내부+외부 `55P03/57014` 합계 비증가. 성공 survivor 수치만으로 통과 금지 | F-S05 후속 finding, flag off 유지 |

각 repetition 뒤 모든 Lease를 stop receipt로 해제해 active 0을 확인하고 observation freshness를 실제 heartbeat로 다시 채운다. 실패 요청도 index·완료 순서·지연·public code/status/retryable·cause SQLSTATE·내부 retry 횟수를 남긴다. 같은 초기 상태에서 Explain의 canonical decision 입력과 선택 node가 반복 간 같아야 결정성 통과이며, generated ID·timestamp만 제외한 canonical digest 규칙을 manifest에 기록한다.

### 필수 S05 artifact

`five-node-s05-placement-<code_sha>`에는 다음을 모두 넣는다.

- `manifest.json`: code/inventory/image/policy SHA, 실행 순서, 입력 body hash, node 공개 fingerprint, 명령과 exit code, 시작·종료 UTC/KST, 위 네 count와 Node별 host/failure-domain/co-location/measurement eligibility.
- `s05/<mode>/<wave>/<repetition>/placement.json`: 요청별 sample, Explain/snapshot/canonical decision digest, leases/fencing, no-overbooking, active before/after.
- 같은 경로의 `placement.xml`: JUnit failure/skip/error를 숨기지 않는다.
- schema 1.5의 `lockHold` p50/p95/max, `lockAcquireWait`, `legacyLockWait`, `limitRowWait`, `sqlDiagnostics`를 보존한다. acquire 값은 server wait_event 전용 시간이 아니라 SQL 호출 전후 client wall clock이므로 `serverSideLockWaitSeparatelyMeasured=false`를 유지한다. fail-fast에서는 `timeoutCount`와 `timeoutRetryCount=0`을 구분하고, parameter-free SQL template·phase·elapsed·SQLSTATE를 남긴다.
- `comparison.json`: mode·wave별 3회 중앙값, 내부와 외부 `55P03/57014`, retry 분포, authorization SHA/boolean, `eligibleNodeCount=4`·`excludedNodeCount=1`, 겸임 Node 선택 0, AC-05 항목별 pass/fail/unmeasured/not-run. candidate 미승인 상태를 legacy와 비교한 것처럼 빈 값을 0으로 채우지 않는다.
- `redaction.json`: DSN·private key·token·원문 terminal secret 탐지 0건과 검사 명령/exit code.

카드 14의 개발 PC 결과(hold P95 중앙값 1399.883→122.126ms, 요청 P95 1771.763→1697.737ms, 내부 limit-row `55P03` 0/0/0→14/10/11)는 legacy/candidate 계측 경계가 달라 hold 비교 근거에서 철회된 역사값이다. 카드 18의 대칭 결과(legacy/candidate post-acquire hold P95 289.365/170.766ms, acquire client elapsed P95 1453.658/528.705ms, 외부 timeout 0/12)가 현재 회귀 입력이며, candidate 성공 8개 survivor 표본이라 성능 통과를 뜻하지 않는다. 랩 결과가 다르면 물리 결과를 별도 증거로 남기되 개발 PC 수치를 덮어쓰지 않는다.

## S07-DB 이탈 감지·복구 실행 계획

S07의 기본 반복 분모도 CP에서 독립적인 Ubuntu 4대다. 20회 반복은 Ubuntu Node마다 5회씩 배분한다. 각 반복 전에 등록 Node 5개의 online·epoch·certificate·heartbeat를 확인하지만, disruption target은 `measurementEligible.s07=true`인 Node만 허용한다.

- `independent-worker-loss`: Ubuntu Node process/host/network 이탈. 감지 지연 ≤ `60초 + poll`, stale write 0, fencing/epoch 단조성, 실제 byte 복구 receipt와 20회 중 성공률 ≥95%를 기본 분모로 계산한다.
- `colocated-node-process-loss`: Windows는 켠 채 Docker Desktop Node process/container만 정지한다. 별도 상관 표본이며 기본 95% 분모와 합치지 않는다.
- `correlated-cp-node-host-loss`: Windows 물리 호스트를 정지하면 CP observer와 Node가 함께 사라진다. 외부 monotonic observer 또는 별도 CP가 사전에 없으면 detection/recovery는 `UNMEASURED`, JUnit skip이 아니라 failure/error 또는 도구 exit 3으로 남긴다.

artifact에는 trial별 `targetNodeId`, `hostId`, `failureDomainId`, `coLocatedWithControlPlane`, `measurementEligible`, `scenarioClass`, observer identity/clock을 넣는다. 겸임 Node와 Ubuntu 표본의 지연·성공률을 합산하지 않는다. S07의 5노드 기준은 topology preflight에 적용되며 기본 성능 분모는 `eligibleNodeCount=4`, `excludedNodeCount=1`로 정직하게 표시한다.

## 랩 준비 체크리스트 대응표

| 준비 항목 | 고정 입력·비밀 | preflight 증거 | 차단 기준 |
|---|---|---|---|
| 실행 Node 5개 / 물리 host 5대 | inventory의 node ID·host/failure-domain ID·endpoint·OS/profile·NIC·co-location·eligibility, 동일 node-agent digest | Windows CP+Docker Node 1개와 Ubuntu Node 4개, 서로 다른 실행 host identity 5개, CP/Node machine identity와 Docker parent에서 유도한 `coLocationValidation=matched`, 각 `/health`·heartbeat·resource snapshot, `lan-workspace-v1`, 공개 fingerprint | 5개 미만, Docker VM을 별도 host로 중복 계수, co-location 유도값 mismatch/unmeasured, eligibility 누락, 합성 row, offline/stale Node가 하나라도 있으면 중단 |
| 자원 기준선 | inventory revision, resource offer/policy version | node별 CPU/RAM/GPU/disk 관측과 합계, active lease 0, 격리/unschedulable 상태 | 관측 누락·offer 불일치·active 잔존·epoch 불일치 |
| NTP/시각 | NTP source 목록은 inventory, 인증정보 없음 | node별 UTC, offset, stratum, sync state, `chronyc tracking/sources` 상당의 redacted 출력 hash; Windows CP와 Docker Node 공유 host clock 표시 | unsynchronised, 허용 source 외 사용, `abs(clock_skew_seconds)>5`; 공유 clock을 독립 표본으로 중복 계수; 목표 `≤1s` 미달은 warning과 실제 값 보존 |
| CA·control cert | `FIVE_NODE_CA_PEM`, control cert/key secret 이름 | CA chain, SHA-256 fingerprint, SAN/usage, not-before/not-after, control endpoint handshake | chain/SAN/usage 불일치, 만료·미개시, key 파일 권한 초과, private material 로그 탐지 |
| node cert 5개 | runner/node secret store; inventory에는 fingerprint·expected subject만 | node ID↔subject/SAN↔fingerprint 1:1, 양방향 handshake, revoked/unknown cert 부정 대조 | 공유 cert, identity 불일치, 부정 대조 수락, cert 5개 미만 |
| 네트워크 | inventory의 허용 endpoint/port | control↔5 node reachability와 비허용 endpoint 거부, RTT 분포; 겸임 Node의 loopback/가상 NAT 경로 표시 | 필요한 경로 실패, 비허용 경로 성공, 겸임 경로를 Ubuntu LAN RTT와 혼합 |
| PostgreSQL | `FIVE_NODE_INV_TEST_ADMIN_DSN` secret 이름, immutable postgres digest | 일회용 DB 이름 hash, PG version/image digest, runtime non-owner/RLS, 시작 active 0 | ambient/운영 DB, owner/bypass role, cleanup ownership 불명 |
| checkout·images | `code_sha`와 4개 immutable digest | clean checkout, commit ancestor, pull digest equality, SBOM/provenance 위치 | tag-only·dirty tree·digest mismatch |
| evidence root | run ID별 새 `LAB_EVIDENCE_ROOT` | empty-before, owner/permission, free space, artifact retention 30일 | 기존 artifact 혼입, 쓰기 불가, secret redaction 미설정 |
| 승인·직렬화 | GitHub Environment reviewer, concurrency group | 승인 actor/time, group `saintvision-five-node-lab`, cancel false | 승인 없음, 다른 lab run active, 일반 push가 취소 가능 |

## 한 lane에서 순차 실행할 명령

```text
python tools/placement_benchmark.py --adapter five-node-lab --inventory "$LAB_INVENTORY_PATH" --dry-run --report "$LAB_EVIDENCE_ROOT/preflight/five-node-lab.json"
python tools/measure_s07_recovery.py --adapter five-node-lab --inventory "$LAB_INVENTORY_PATH" --dry-run --json-out "$LAB_EVIDENCE_ROOT/preflight/s07-five-node.json"  # 제안·미구현, preflight only
python tools/placement_benchmark.py --mode legacy --requests 20 --concurrency 20 --rounds 1 --report "$LAB_EVIDENCE_ROOT/control/s05-legacy-20.json" --junit "$LAB_EVIDENCE_ROOT/control/s05-legacy-20.xml"
python tools/run_s05_five_node_benchmark.py --inventory "$LAB_INVENTORY_PATH" --modes legacy --waves 20 --repetitions 3 --decision-sha 9dafbf09d084ed793301937ba7834a4ca057ba2d --exclude-cp-colocated --json-root "$LAB_EVIDENCE_ROOT/s05" --junit-root "$LAB_EVIDENCE_ROOT/s05"  # 제안·미구현
# candidate 또는 50동시는 별도 승인 SHA 뒤에만 입력을 확장한다. 현재 복사·실행 금지.
python tools/run_s07_five_node_recovery.py --inventory "$LAB_INVENTORY_PATH" --eligible-only --repetitions 20 --liveness-timeout-seconds 60 --poll-interval-seconds 0.1 --target-recovery-success-rate 0.95 --json-out "$LAB_EVIDENCE_ROOT/s07-recovery.json" --junit-out "$LAB_EVIDENCE_ROOT/s07-recovery.xml"  # 제안·미구현, 실제 disruption은 별도 승인
python tools/check_remote_workspace.py --state "<node-state-dir>" --prepared "<prepared.json>" --image "<worker-image-digest>" --preflight-only
python tools/check_remote_workspace.py --state "<node-state-dir>" --prepared "<prepared.json>" --image "<worker-image-digest>"
python tools/run_s06_five_node_journey.py --inventory "$LAB_INVENTORY_PATH" --code-sha "<code_sha>" --control-plane-image "<digest>" --node-agent-image "<digest>" --worker-image "<digest>" --json-out "$LAB_EVIDENCE_ROOT/s06-remote.json" --junit-out "$LAB_EVIDENCE_ROOT/s06-remote.xml"  # 제안·미구현
```

`placement_benchmark.py`의 두 명령과 `check_remote_workspace.py`의 두 명령만 현재 실제 인터페이스다. `measure_s07_recovery.py --adapter five-node-lab`, `run_s05_five_node_benchmark.py`, `run_s07_five_node_recovery.py`, `run_s06_five_node_journey.py`는 **제안·미구현**이다. 따라서 현재 `five-node-lab` 구현은 S05 inventory/DB preflight까지만 실행 가능하고 timed placement·S07 recovery wave를 실행하지 않는다. S05 control과 기존 `measure_s07_recovery.py`는 실 PostgreSQL의 합성 node row를 측정하므로, 단지 5노드 runner에서 실행해도 물리 5노드 증거가 되지 않는다. S07 adapter 후속 브랜치는 #101 inventory를 단일 정본으로 재사용하고 `measurementEligible.s07`로 CP 겸임 Node를 disruption 전에 제외하되 첫 카드는 read-only preflight만 제공한다. 실제 wave는 preflight의 선택 집합을 물리 실행기에 사전 적용하고 동일 JSON/JUnit 형식의 evidence를 제공해야 한다. S06 runner는 실제 Git commit/push 또는 격리 remote publish, PTY 명령·resize·재접속, Control Plane 재시작, 대상 Node 재시작, 새 ticket으로 resume, snapshot restore hash 일치, 중복 실행 0을 한 여정으로 증명해야 한다. 기존 `check_remote_workspace.py`의 7개 case(`python`, `ai`, 두 cancel, `failure`, `timeout`, `output-recovery`)는 선행 원격 실행 증거일 뿐 WS/PTY/Git 재시작 증거를 대신하지 않는다.

S05 → S07 → S06 순서로 한 번에 하나만 실행한다. S07의 감지 상한은 커널 predicate를 바꾸지 않고 `60초 timeout + 0.1초 poll`이며, JSON의 synthetic recovery는 물리 byte 복구 성공률로 승격하지 않는다. 실패·timeout 때도 owned DB/container만 보존 또는 정리하고 red artifact를 업로드한다.

## 증거 artifact와 판정

| artifact 이름 | 필수 내용 |
|---|---|
| `five-node-lane-manifest-<code_sha>` | code/inventory revision, 4개 image digest, 5개 Node 공개 identity·OS·host/failure-domain·co-location·eligibility, 네 topology count, 명령·exit code·UTC/KST, runner label, secret redaction 검사 |
| `five-node-s05-placement-<code_sha>` | all-five smoke + eligible Ubuntu 4대의 승인된 wave JSON/JUnit. 최초 범위는 legacy 20동시 × 3회이며 candidate/50은 승인 없으면 `NOT_RUN`으로 표시한다. request P95, Explain/canonical decision digest, 겸임 Node 선택 0, CP host utilization timeline, snapshot/fencing/no-overbooking, schema 1.5 `lockHold`·`lockAcquireWait`·mode별 wait·`sqlDiagnostics`, retry·SQLSTATE, authorization/comparison/redaction manifest |
| `five-node-s07-recovery-<code_sha>` | `s07-recovery.json/xml`, Ubuntu 4대에 균등 배분한 20회 기본 분포, 별도 co-located/correlated scenario, observer identity, timeout+poll 감지, stale write 0, 물리 shard byte 복구 receipt |
| `five-node-s06-workspace-<code_sha>` | 기존 7-case 결과, `s06-remote.json/xml`, WS/PTY transcript hash, Git remote receipt, CP/Node restart timeline, restore before/after hash |

artifact는 실패에도 `if: always()`로 30일 보존하되 private key·token·DSN·원문 terminal secret은 제외한다. 네 artifact의 SHA·run URL·exit code가 모두 있고 독립 reviewer가 내용과 inventory, CP 겸임 제외가 실제 candidate/disruption 선택 전에 적용됐는지를 대조한 뒤에만 AC-05/06/07 판단 자료로 쓴다. 이 판정은 등록 Node 5개의 topology evidence와 CP 독립 Ubuntu 4개의 수용 지표를 결합하며, 5개 독립 worker 지표라는 주장은 금지한다. legacy 20동시 계획과 결과만으로 candidate·50동시·AC-05를 승인하지 않으며, S05-DB는 `review`를 유지한다. 현재 S06-DB가 `review`인 이유는 소프트웨어 결속과 Linux hosted 회귀가 5노드 원격 WS/PTY/Git 및 CP/Node 재시작 복원 여정을 측정하지 않기 때문이다.
