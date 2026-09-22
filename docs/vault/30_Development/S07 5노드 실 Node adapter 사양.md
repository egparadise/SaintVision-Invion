---
doc_id: "CODEX-S07-FIVE-NODE-ADAPTER-SPEC-001"
title: "S07 5노드 실 Node adapter 사양"
version: "1.0.0"
status: "proposed-review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T10:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S07-DB"]
tags: ["s07", "five-node", "adapter", "inventory", "read-only", "preflight"]
---

# S07 5노드 실 Node adapter 사양

> [!warning] 구현·실행 권한 없음
> 이 문서는 `tools/measure_s07_recovery.py`에 물리 inventory를 결속하기 위한 docs-only 사양이다. 코드·DB·Node를 바꾸지 않았고, 실제 이탈·복구 wave를 승인하지 않는다. 구현과 물리 실행은 Claude 검토와 코디네이터의 별도 승인 뒤다. S07-DB는 `review`이며 AC-07·5노드 인수는 미측정이다.

## 1. 목적

현재 `measure_s07_recovery.py`는 disposable PostgreSQL에 합성 measured Node를 만들고 제품 liveness/repair-plan 경로를 검증한다. 이 경로는 유지하되, 다음 opt-in CLI를 추가해 실제 등록 Node가 물리 S07 wave를 시작할 준비가 됐는지만 읽기 전용으로 판정한다.

```text
python tools/measure_s07_recovery.py --adapter five-node-lab --inventory "$LAB_INVENTORY_PATH" --dry-run --json-out "$LAB_EVIDENCE_ROOT/preflight/s07-five-node.json"
```

`--adapter synthetic`이 기본이며 기존 `--nodes`, `--repetitions`, timeout/poll/target, JSON/JUnit 실행 의미를 바꾸지 않는다. `five-node-lab`은 첫 구현에서 `--inventory`와 `--dry-run`을 모두 요구하고 pytest, Node disruption, repair, JUnit success를 실행하지 않는다.

## 2. #101 inventory 정본 재사용

inventory 계약은 `tools/placement_benchmark.py`의 #101 구현을 새로 해석하거나 복제하지 않는다. 구현 시 strict parser와 공통 read-only Node classification을 `tools/five_node_lab_inventory.py` 같은 내부 모듈로 동작 보존 추출해 placement와 S07이 함께 사용한다. 직접 import를 택하더라도 단일 구현만 존재해야 하며 두 parser를 따로 유지하는 방식은 금지한다.

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

## 4. S07 선택 규칙

all-five topology에는 ready한 겸임 Node도 포함하지만 기본 disruption 대상은 다음 술어를 모두 만족해야 한다.

```text
readiness.ready
and measurementEligible.s07 is true
and coLocatedWithControlPlane is false
```

정상 topology B에서 기대 count는 inventory/registered/ready 5, CP-colocated 1, CP-independent 4, S07 eligible/selected 4다. `topologyReady`는 다섯 Node가 모두 ready이고 host identity에서 겸임 1·독립 4가 확인될 때만 true다. `recoveryWaveReady`는 topologyReady이면서 disruption target 4개가 모두 선택될 때만 true다.

20회 future plan은 선택된 Ubuntu 4대에 nodeId 정렬 기준 round-robin으로 각 5회를 배정한다. 이 계획은 `plannedTargetCounts`일 뿐 preflight가 process를 멈추거나 반복을 시작하지 않는다. CP 겸임 Node는 `selectedForTopology=true`, `selectedForDisruption=false`, reason `cp-host-colocation`으로 남긴다. 사후에 겸임 표본만 지워 95% 분모를 다시 만드는 행위는 금지한다.

## 5. preflight artifact

JSON schema는 `s07-five-node-preflight:1`이며 최소한 다음을 포함한다.

- provenance: `codeSha`, integration SHA/동기·clean 여부, `inventoryRevision`, generated UTC/KST, executor
- 안전 플래그: `dryRun=true`, `databaseReadOnly=true`, `syntheticRowsCreated=false`, `heartbeatUpdated=false`, `resourceSnapshotUpdated=false`, `nodeDisrupted=false`, `repairExecuted=false`, `loadExecuted=false`, `operationalAcceptanceAssessed=false`
- topology count: inventory, physical host, registered, ready, CP-colocated, CP-independent, S07 eligible/selected/excluded
- Node별 공개 identity, host/failure-domain, co-location validation, eligibility/exclusion, readiness booleans·reason, heartbeat/snapshot age
- `topologyReady`, `recoveryWaveReady`, `allFiveNodeIds`, `disruptionTargetNodeIds`, `plannedTargetCounts`

PID/XID, tenant/project ID, DSN, token, private key, 원문 certificate, SQL parameter는 남기지 않는다. 공개 certificate SHA-256과 Node ID는 inventory provenance로 허용한다.

readiness false는 유효한 관측이므로 #101과 같이 JSON을 보존하고 preflight 명령 자체는 exit 0일 수 있다. 이 exit 0은 “관측 완료”일 뿐 실행 가능을 뜻하지 않는다. 후속 orchestrator는 `recoveryWaveReady is true`를 별도 gate로 강제해야 한다. schema/revision/identity/read-only 위반, DSN 부재, DB 오류는 nonzero이며 이전 JSON을 실행 전에 삭제해 stale green 재사용을 막는다.

five-node dry-run은 JUnit을 만들지 않는다. JUnit은 실제 recovery assertion이 실행됐을 때만 생성한다. 사용자가 five-node adapter에 `--dry-run` 없이 measurement knobs 또는 JUnit path를 주면 “physical recovery execution is not enabled”로 거부한다.

## 6. 구현 카드 시험

### PG-free

1. synthetic 기본 CLI와 schema v2 출력이 기존과 동일하다.
2. #101 inventory의 canonical revision, exact key, uniqueness, co-location/eligibility 규칙을 placement와 S07이 같은 함수로 검사한다.
3. five-node adapter는 inventory/dry-run/DSN을 요구하고 부하·JUnit 옵션을 거부한다.
4. CP 겸임 Node가 topology에는 포함되지만 disruption target과 20회 계획에는 절대 들어가지 않는다.
5. `lan-observe-v1`, stale heartbeat/snapshot, offline, channel disabled, clock skew는 readiness false와 정확한 reason을 낸다.
6. identity drift·등록 누락·multi-tenant는 fail closed한다.
7. stale output 삭제와 secret/identifier redaction을 고정한다.

### 실 PostgreSQL 단일 파일

1. disposable DB의 5개 실제-shaped 등록 row를 **읽기만** 하고 before/after table digest·row count가 같다.
2. transaction read-only를 query log 또는 connection double이 아니라 실제 `SHOW`로 확인한다.
3. topology B green shape에서 ready 5·eligible/selected 4·겸임 selected 0이다.
4. profile/heartbeat/channel/snapshot 부정 대조는 write 없이 readiness false 또는 identity error를 낸다.

실제 LAN Node, channel, heartbeat를 갱신하거나 process를 중단하는 시험은 이 구현 카드에 포함하지 않는다.

## 7. 후속 물리 실행의 별도 승인 조건

read-only preflight 구현·Claude 독립 검토·정본 inventory green 뒤에도 실제 wave는 자동 승인되지 않는다. 별도 카드가 다음을 추가해야 한다.

- 외부 monotonic observer와 Node별 active health probe
- Ubuntu 4대에 균등한 20회 disruption 실행기, 매 반복 전 5대 readiness 재확인
- 감지 `<=60초+poll`, stale write 0, fencing/epoch 단조성, 실제 byte/checksum/replay receipt, 성공률 95% 판정
- failure에도 JSON/JUnit 보존, owned process만 복구, 다음 반복 전 baseline 복원
- `colocated-node-process-loss`와 `correlated-cp-node-host-loss`를 기본 Ubuntu 분모와 분리. 외부 observer가 없으면 correlated scenario는 `UNMEASURED`/exit 3

## 8. 롤백과 인계

구현 롤백은 `--adapter five-node-lab` 분기를 제거하고 synthetic 기본 경로를 그대로 유지하는 것이다. migration·DB cleanup·Node 재등록은 없다. 공용 inventory helper 추출이 #101 placement preflight의 JSON/validation을 바꾸면 구현을 중단한다.

- owner: Codex — 별도 승인 뒤 adapter/preflight 구현
- reviewer: Claude — inventory 단일 정본, read-only 무변이, CP 겸임 제외, 미측정 정직성 검토
- decision: 코디네이터 — 구현과 물리 실행 각각 별도 승인
