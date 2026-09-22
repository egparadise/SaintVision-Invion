---
doc_id: "CODEX-S07-FIVE-NODE-ADAPTER-SPEC-001"
title: "S07 5노드 실 Node adapter 사양"
version: "1.1.1"
status: "proposed-review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T12:45:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S07-DB"]
tags: ["s07", "five-node", "adapter", "inventory", "read-only", "preflight"]
---

# S07 5노드 실 Node adapter 사양

> [!warning] 물리 wave 실행 권한 없음
> v1.1은 공용 inventory와 등록/mTLS read-only preflight를 `tools/five_node_lab_preflight.py`로 추출하지만 실제 이탈·복구 wave는 구현하거나 승인하지 않는다. S07-DB는 `review`이며 AC-07·5노드 인수는 미측정이다.

## 1. 목적

현재 `measure_s07_recovery.py`는 disposable PostgreSQL에 합성 measured Node를 만들고 core liveness/repair-plan 경로를 검증한다. 이 경로는 개발 회귀용 proxy로 유지하되 물리 AC-07 제품 경로로 승격하지 않는다. 물리 adapter는 먼저 실제 등록 Node가 wave 후보가 될 수 있는지만 공용 helper로 읽기 전용 판정한다.

```text
python tools/measure_s07_recovery.py --adapter five-node-lab --inventory "$LAB_INVENTORY_PATH" --dry-run --json-out "$LAB_EVIDENCE_ROOT/preflight/s07-five-node.json"
```

`--adapter synthetic`이 기본이며 기존 `--nodes`, `--repetitions`, timeout/poll/target, JSON/JUnit 실행 의미를 바꾸지 않는다. 위 S07 CLI는 여전히 제안·미구현이다. 이번 카드의 helper는 #101 placement adapter의 등록/mTLS preflight만 공용화하며 Node disruption, repair, JUnit success를 실행하지 않는다.

### F-A: 물리 AC-07 제품 경로 결정

| 후보 | 현재 제품 결속 | 실제 shard byte | 결정 |
|---|---|---|---|
| 커널 `inv` 경로 | `observation.py`가 실 heartbeat로 `inv.nodes`를 offline 전이하고 `shard_recovery.py`가 원 source plan/shard를 명시한 재실행을 만든다 | `output_ingestion.py`가 receipt의 base64 size/SHA-256을 검증해 storage object를 만들고 `shard_completion.py`가 그 byte를 다시 읽어 manifest/hash/evidence를 commit한다 | **물리 AC-07 정본으로 권고** |
| core 경로 | `saintvision.services.nodes.mark_lost_nodes`가 core Node/replica를 stale로 만들고 `locations_needing_repair`가 계획을 계산한다 | `replica_repair.py`는 assessment/plan만 하며 byte 이동을 하지 않는다. 현재 하네스 성공은 owner fixture가 verified replica row를 삽입한 proxy다 | 합성 개발 회귀만 유지 |
| bridge 신설 | 실 heartbeat를 core 테이블에 복제하는 구현이 없다 | 새 이중 정본과 순서·재시도·stale 동기화 계약이 필요하다 | 측정을 위해 선행 신설하지 않음 |

따라서 물리 감지는 `services/control-plane/src/inv/observation.py`의 heartbeat 기반 offline 전이, 복구는 `services/control-plane/src/inv/shard_recovery.py`의 fresh approval/run·source plan/shard·stop receipt·lease/fence·bounded generation, 성공은 `output_ingestion.py`와 `shard_completion.py`의 receipt-bound byte 및 manifest commit으로 판정한다. core 합성 하네스 결과를 물리 성공률에 합산하지 않는다.

현재 커널 감지 기준은 `services/control-plane/src/inv/observation.py:146`의 `heartbeat_at < clock_timestamp() - interval '60 seconds'`로 **60초가 하드코드**돼 있다. 따라서 AC-07 감지 판정은 이 구현을 바꾸거나 더 짧게 해석하지 않고 `60초 liveness timeout + observer poll 간격` 이내로 고정한다. 후속 recovery adapter는 실제 offline 전이 시각과 poll 시각을 모두 기록해야 하며 preflight의 15초 heartbeat freshness를 AC-07 timeout으로 오인하면 안 된다.

## 2. #101 inventory 정본 재사용

inventory 계약은 `tools/placement_benchmark.py`의 #101 구현을 새로 해석하거나 복제하지 않는다. strict parser와 공통 등록/mTLS read-only Node classification은 `tools/five_node_lab_preflight.py` 한 곳으로 동작 보존 추출하고 placement는 이를 import/re-export한다. S07 후속도 같은 helper를 사용해야 하며 두 parser를 따로 유지하는 방식은 금지한다.

root exact keys와 의미는 다음과 같다.

- `schemaVersion="1.0.0"`
- `revision`: revision 자체를 제외한 JSON의 UTF-8·sorted-key·compact canonical SHA-256
- `controlPlaneHostId`
- `nodes`: 1~5개. exact keys는 `nodeId`, private IPv4 `ip`, 공개 `certificateSHA256`, `profile`, `hostId`, `failureDomainId`, `coLocatedWithControlPlane`, `measurementEligible.{s05,s07}`, `exclusionReason`

Node ID·IP·certificate fingerprint·host ID는 inventory 안에서 유일해야 한다. `coLocatedWithControlPlane`은 `hostId == controlPlaneHostId`에서 다시 유도해 선언과 대조한다. 겸임 Node는 최대 1개이며 eligibility 두 값이 false, `exclusionReason=cp-host-colocation`이어야 한다. 독립 Node는 eligibility 두 값이 true, exclusion reason이 null이어야 한다. 선언만으로 독립성을 인정하지 않는다.

## 3. read-only PostgreSQL preflight

`INV_TEST_ADMIN_DSN`은 secret input으로만 받고 artifact·오류에 남기지 않는다. adapter는 transaction 첫 statement로 `SET TRANSACTION READ ONLY`를 실행하고 `SHOW transaction_read_only=on`을 확인한 뒤 다음 정본만 조회한다.

- `inv.nodes`: inventory의 모든 `nodeId` 등록, 단일 tenant, `status=online`, heartbeat, recovery epoch, clock skew
- `inv.node_channels`: enabled mTLS channel, endpoint IP, 공개 fingerprint, expiry, channel version/epoch
- `inv.node_resource_snapshots`: received time, channel version/epoch, snapshot identity, `profileVersion`, 최소 CPU/RAM 관측 완전성

identity drift는 fail closed한다. inventory fingerprint/IP/profile과 DB channel/snapshot이 다르거나 node/channel/snapshot epoch·version이 갈리거나 한 Node가 여러 tenant에 보이면 JSON readiness로 낮추지 않고 오류로 종료한다. 등록 누락도 오류다.

운영 readiness는 identity validation과 분리해 Node별 원인을 JSON에 남긴다.

- heartbeat와 resource snapshot은 DB `statement_timestamp()` 기준 15초 이내
- `abs(clock_skew_seconds) <= 5`
- channel enabled·미만료
- inventory `profile`과 snapshot `profileVersion`이 모두 정확히 `lan-workspace-v1`
- status online, resource snapshot 완전

실제 `/health` 네트워크 호출, process/container 생존, worker image digest 검증은 이 DB preflight 범위 밖이다. 물리 wave 구현 전 별도 active probe가 필요하며 DB preflight green을 Node disruption 권한으로 해석하지 않는다.

이 helper는 **등록/mTLS preflight**다. 선택한 커널 복구 경로의 wave preflight는 후속 카드에서 `inv`의 source plan/shard, terminal failed/cancelled parent, 물리 stop receipt와 lease/fence, project-node membership, output storage와 shard-completion 준비 상태를 추가로 확인해야 한다. core `nodes/data_replicas/locations_needing_repair` 테이블을 물리 preflight 정본으로 섞지 않는다.

## 4. S07 선택 규칙

all-five topology에는 ready한 겸임 Node도 포함하지만 기본 disruption 대상은 다음 술어를 모두 만족해야 한다.

```text
readiness.ready
and measurementEligible.s07 is true
and coLocatedWithControlPlane is false
```

정상 topology B에서 기대 count는 inventory/registered/ready 5, CP-colocated 1, CP-independent 4, S07 eligible/selected 4다. `topologyReady`는 다섯 Node가 모두 ready이고 host identity에서 겸임 1·독립 4가 확인될 때만 true다. `recoveryWaveReady`는 topologyReady이면서 disruption target 4개가 모두 선택될 때만 true다.

CE-4의 임시 운영 옵션은 future orchestrator의 명시적 `--allow-four-node-pilot`이며 기본값은 false다. 이 flag는 [[ADR-100 CP 호스트의 Node 겸임과 5노드 측정 경계]]의 되돌리기에 따라 겸임 Node가 cordon/disabled이고 **서로 독립인 Ubuntu Node 4대가 모두 등록·ready·eligible**일 때만 `pilotWaveReady=true`를 허용한다. 이때도 `topologyMode=four-node-pilot`, `topologyReady=false`, `recoveryWaveReady=false`, `fiveNodeAcceptanceEligible=false`를 보존해 5노드 인수로 오인하지 않는다. flag가 없거나 독립 Node가 4대 미만이면 Ubuntu 측정도 시작하지 않는다.

20회 future plan은 선택된 Ubuntu 4대에 nodeId 정렬 기준 round-robin으로 각 5회를 배정한다. 이 계획은 `plannedTargetCounts`일 뿐 preflight가 process를 멈추거나 반복을 시작하지 않는다. CP 겸임 Node는 `selectedForTopology=true`, `selectedForDisruption=false`, reason `cp-host-colocation`으로 남긴다. 사후에 겸임 표본만 지워 95% 분모를 다시 만드는 행위는 금지한다.

## 5. preflight artifact

JSON schema는 `s07-five-node-preflight:1`이며 최소한 다음을 포함한다.

- provenance: `codeSha`, integration SHA/동기·clean 여부, `inventoryRevision`, generated UTC/KST, executor
- 안전 플래그: `dryRun=true`, `databaseReadOnly=true`, `syntheticRowsCreated=false`, `heartbeatUpdated=false`, `resourceSnapshotUpdated=false`, `nodeDisrupted=false`, `repairExecuted=false`, `loadExecuted=false`, `operationalAcceptanceAssessed=false`
- topology count: inventory, physical host, registered, ready, CP-colocated, CP-independent, S07 eligible/selected/excluded
- Node별 공개 identity, host/failure-domain, co-location validation, eligibility/exclusion, readiness booleans·reason, heartbeat/snapshot age
- `topologyReady`, `recoveryWaveReady`, `allFiveNodeIds`, `disruptionTargetNodeIds`, `plannedTargetCounts`

PID/XID, tenant/project ID, DSN, token, private key, 원문 certificate, SQL parameter는 남기지 않는다. 공개 certificate SHA-256과 Node ID는 inventory provenance로 허용한다. helper는 동일 tenant 여부를 내부에서 검사하되 report에는 `tenantId`를 쓰지 않는다(F-B).

readiness false는 유효한 관측이므로 #101과 같이 JSON을 보존하고 preflight 명령 자체는 exit 0일 수 있다. 이 exit 0은 “관측 완료”일 뿐 실행 가능을 뜻하지 않는다. 후속 orchestrator는 `recoveryWaveReady is true` 또는 별도 `pilotWaveReady is true`를 실행 모드에 맞춰 강제해야 한다. schema/revision/identity/read-only 위반, DSN 부재, DB 오류는 nonzero다. `write_registration_mtls_preflight`는 validation/DB 조회 전에 목적 report를 삭제하고 성공한 현재 관측만 다시 써 stale green 재사용을 막는다(F-C).

five-node dry-run은 JUnit을 만들지 않는다. JUnit은 실제 recovery assertion이 실행됐을 때만 생성한다. 사용자가 five-node adapter에 `--dry-run` 없이 measurement knobs 또는 JUnit path를 주면 “physical recovery execution is not enabled”로 거부한다.

## 6. 구현 카드 시험

### PG-free

1. synthetic 기본 CLI와 schema v2 출력이 기존과 동일하다.
2. #101 inventory의 canonical revision, exact key, uniqueness, co-location/eligibility 규칙을 placement와 S07이 같은 함수로 검사한다.
3. five-node adapter는 inventory/dry-run/DSN을 요구하고 부하·JUnit 옵션을 거부한다.
4. CP 겸임 Node가 topology에는 포함되지만 disruption target과 20회 계획에는 절대 들어가지 않는다.
5. `lan-observe-v1`, stale heartbeat/snapshot, offline, channel disabled, clock skew는 readiness false와 정확한 reason을 낸다.
6. identity drift·등록 누락·multi-tenant는 fail closed한다.
7. 공용 helper 재수출 동일성, stale output 선삭제, `tenantId`·secret redaction을 고정한다.

### 실 PostgreSQL 단일 파일

1. disposable DB의 5개 실제-shaped 등록 row를 **읽기만** 하고 before/after table digest·row count가 같다.
2. transaction read-only를 query log 또는 connection double이 아니라 실제 `SHOW`로 확인한다.
3. topology B green shape에서 ready 5·eligible/selected 4·겸임 selected 0이다.
4. profile/heartbeat/channel/snapshot 부정 대조는 write 없이 readiness false 또는 identity error를 낸다.

실제 LAN Node, channel, heartbeat를 갱신하거나 process를 중단하는 시험은 이 구현 카드에 포함하지 않는다.

## 7. 후속 물리 실행의 별도 승인 조건

read-only preflight 구현·Claude 독립 검토·정본 inventory green 뒤에도 실제 wave는 자동 승인되지 않는다. 별도 카드가 다음을 추가해야 한다.

- 외부 monotonic observer와 Node별 active health probe
- Ubuntu 4대에 균등한 20회 disruption 실행기, 매 반복 전 선택한 topology mode의 baseline readiness 재확인
- 감지 `<=60초+poll`, stale write 0, fencing/epoch 단조성, receipt-bound output byte·storage object·ShardCompletion manifest/hash/evidence를 모두 확인한 성공률 판정
- 20회 중 19회 성공은 **시연 임계 통과**이지 “성공률 95% 증명”이 아니다. JSON/JUnit에 `19/20`, 점추정 `0.95`, 양측 95% Clopper-Pearson 하한 약 `0.751`을 함께 남기고 표본 확대 전 통계적 보장으로 표현하지 않는다(F-D)
- 이탈 유도는 inventory로 고정한 대상 Ubuntu node-agent container에 `docker stop --time <bounded>`를 사용한다. SIGTERM과 timeout 뒤 강제 종료 여부를 기록하고 volume·journal·키·인증서·state를 보존한다. `docker rm`, `prune`, host reboot, key/channel 교체, 임의 network kill은 금지한다(F-E)
- 복원은 같은 container에 `docker start`만 사용하고 동일 nodeId·certificate fingerprint·epoch/channel 결속, heartbeat/resource snapshot, 대상 topology baseline을 재확인한 뒤 다음 반복으로 간다. 실패에도 JSON/JUnit을 보존하고 소유한 container만 복원한다
- `colocated-node-process-loss`와 `correlated-cp-node-host-loss`를 기본 Ubuntu 분모와 분리. 외부 observer가 없으면 correlated scenario는 `UNMEASURED`/exit 3

## 8. 롤백과 인계

helper 추출 롤백은 placement가 직전 inline 구현을 다시 사용하도록 되돌리는 것이며 migration·DB cleanup·Node 재등록은 없다. 허용된 report 변화는 민감 식별자 `tenantId` 제거와 stale output 선삭제뿐이다. inventory validation, read-only SQL, readiness와 placement 선택 의미가 바뀌면 구현을 중단한다.

- owner: Codex — 등록/mTLS helper 추출 및 별도 승인 뒤 커널 recovery adapter 구현
- reviewer: Claude — inventory 단일 정본, read-only 무변이, CP 겸임 제외, 미측정 정직성 검토
- decision: 코디네이터 — 구현과 물리 실행 각각 별도 승인
