---
doc_id: "TARGET-S11-AC11-COMPOSITE-LONG-SOAK-001"
title: "S11 AC-11 composite long-soak target v0"
version: "1.0.0"
status: "frozen-target"
author: "Codex"
updated: "2026-09-28T19:59:12+09:00"
source_of_truth: "Git"
task_id: "S11-BE"
acceptance_id: "AC-11"
tags: ["S11", "AC-11", "long-soak", "physical-five-node", "target"]
---

# S11 AC-11 composite long-soak target v0

이 문서는 결과를 보기 전에 고정하는 `long-soak` 축의 물리 composite target이다. 이 파일 자체는 AC-11 집계기가 소비하는 registry가 아니다. Claude 독립 검토 뒤 별도 repin 카드가 정본 `docs/vault/30_Development/Evidence/s11-ac11-target-registry-v0.json`, 집계기와 모든 importer의 registry blob pin을 한 commit에서 갱신하기 전에는 측정을 시작하거나 이 target을 제출하지 않는다.

운영자가 물리 fault-injection window·전원/스위치 제어·외부 monotonic observer·원격 WAN/WS client를 제공하기 전 판정은 `BLOCKED_EXTERNAL`이고 blocker는 `G-19,G-24`다. 입력 부재를 합성 값이나 hosted 결과로 채우지 않는다.

## 1. target entry

- `targetId`: `s11-ac11-composite-long-soak-v0`
- `axis`: `long-soak`
- `requiredEnvironment`:
  - `topology=physical-five-node`
  - `registeredNodeCount=5`
  - `eligibleNodeCount=4`
  - `excludedNodeCount=1`
  - `cpIndependentWorkerHostCount=4`
  - `cpColocatedNodeCount=1`
  - `timedPopulation=cp-independent-ubuntu-four`
  - `observer=external-monotonic-v1`
  - `faultInjection=controlled-v1`
  - `windowClass=physical-24h`

CP 겸임 Node는 all-five topology smoke에는 포함하지만 timed workload·온도·fault latency·recovery 분모에서는 제외한다. post-hoc 표본 삭제는 허용하지 않는다.

### 1.1 criteria

아래 metric 전부가 있어야 하고, 하나라도 누락되면 `INVALID_RUN`이다. `skip`, `NOT_OBSERVED`, `BLOCKED_EXTERNAL`, `NOT_REGISTERED`는 PASS가 아니다.

| metric | operator | value | 의미 |
|---|---:|---:|---|
| `windowSeconds` | `gte` | 86400 | 동일 inventory·release SHA의 연속 물리 관측창 |
| `registeredNodeCount` | `eq` | 5 | 서로 다른 node identity·인증서·epoch |
| `eligibleNodeCount` | `eq` | 4 | CP 독립 Ubuntu timed 분모 |
| `excludedNodeCount` | `eq` | 1 | CP 겸임 Node |
| `cpIndependentWorkerHostCount` | `eq` | 4 | 물리 독립 worker host |
| `cpColocatedNodeCount` | `eq` | 1 | CP와 장애 영역을 공유하는 Node |
| `requiredCaseCount` | `eq` | 14 | §2 exact case universe |
| `executedRequiredCaseCount` | `eq` | 14 | 중복 없이 전부 실행 |
| `telemetryCoveragePpm` | `gte` | 990000 | 60초 이하 sampling cadence에서 유효 표본 비율 |
| `externalObserverCoveragePpm` | `gte` | 990000 | CP 장애 중에도 유지되는 별도 observer 표본 비율 |
| `minThermalHeadroomMilliC` | `gte` | 5000 | inventory에 pin한 vendor critical limit까지 최소 여유 |
| `thermalThrottleSeconds` | `eq` | 0 | eligible worker 열 throttle 누적 |
| `criticalThermalEventCount` | `eq` | 0 | critical sensor event |
| `plannedPowerFaultCaseCount` | `gte` | 2 | worker와 CP source-loss 각 1건 이상 |
| `powerRecoveryPassCount` | `gte` | 2 | 두 power case 복원·identity 재확인 |
| `maxPowerRecoverySeconds` | `lte` | 900 | 외부 monotonic observer 기준 |
| `unexpectedPowerLossCount` | `eq` | 0 | 계획 밖 reboot/source loss |
| `maxAbsClockSkewMillis` | `lte` | 5000 | 커널 적격성 경계와 같은 ±5초 |
| `clockSkewUnmeasuredSampleCount` | `eq` | 0 | online eligible worker의 NULL/비유한 표본 |
| `clockResyncPassCount` | `gte` | 1 | source loss 뒤 동기화 회복 |
| `maxClockResyncSeconds` | `lte` | 300 | 외부 monotonic observer 기준 |
| `switchFaultCaseCount` | `gte` | 2 | worker uplink와 CP uplink 각 1건 이상 |
| `switchRecoveryPassCount` | `gte` | 2 | 링크·mTLS·identity 복원 |
| `maxSwitchRecoverySeconds` | `lte` | 300 | 외부 observer 기준 |
| `wanFaultCaseCount` | `gte` | 2 | path loss와 latency/loss impairment |
| `wanRecoveryPassCount` | `gte` | 2 | 새 ticket을 포함한 remote path 복원 |
| `maxWanRecoverySeconds` | `lte` | 120 | 외부 client 기준 |
| `wsSteadySessionCount` | `gte` | 4 | eligible Ubuntu worker별 실제 session 1개 이상 |
| `wsRoundTripCount` | `gte` | 1000 | 전체 창의 sequence+nonce 검증 round trip |
| `wsReconnectPassCount` | `gte` | 1 | WAN loss 뒤 새 30초 ticket으로 재연결 |
| `maxWsReconnectSeconds` | `lte` | 60 | 외부 client 기준 |
| `wsPayloadMismatchCount` | `eq` | 0 | byte/sequence/nonce 불일치 |
| `wsDuplicateExecutionCount` | `eq` | 0 | reconnect 뒤 명령 중복 실행 |
| `unauthorizedWsReplayAcceptanceCount` | `eq` | 0 | 만료·재사용 ticket 수락 |
| `storagePhysicalReferencePassCount` | `eq` | 1 | #185의 같은 창·SHA·inventory 물리 reference |
| `hostedDriftReferencePassCount` | `eq` | 1 | 같은 code SHA의 hosted reference가 red가 아님 |
| `hostedDriftReferenceFailureCount` | `eq` | 0 | known hosted regression 없음 |
| `memoryGrowthBytes` | `lte` | 268435456 | physical storage reference와 동일 정의 |
| `fileDescriptorGrowthCount` | `lte` | 32 | physical storage reference와 동일 정의 |
| `dbConnectionGrowthCount` | `lte` | 4 | physical storage reference와 동일 정의 |
| `falseSuccessCount` | `eq` | 0 | 오류·미관측을 성공으로 기록한 수 |
| `classificationMismatchCount` | `eq` | 0 | §3 밖/오분류 fault |
| `unexpectedProcessRestartCount` | `eq` | 0 | 계획 fault 밖 CP·Node·DB·proxy restart |
| `identityDriftCount` | `eq` | 0 | node/cert/epoch/inventory revision drift |
| `committedDataLossCount` | `eq` | 0 | committed object/workspace/result 손실 |
| `staleWriteCount` | `eq` | 0 | fenced/old epoch write 수락 |
| `unclassifiedFaultCount` | `eq` | 0 | §3 exact class 밖 fault |
| `cleanupResidueCount` | `eq` | 0 | fault shaping·임시 session·test object residue |

절대 온도 하나를 모든 장비에 적용하지 않는다. 각 host의 sensor identity와 vendor critical limit를 inventory revision에 사전 pin하고 `minThermalHeadroomMilliC`를 계산한다. sensor·critical limit가 없으면 0으로 보충하지 않고 `BLOCKED_EXTERNAL` 또는 `NOT_OBSERVED`다.

## 2. exact case identity

UTF-8 JSON compact array(`ensure_ascii=false`, separators `,`/`:`), 아래 사전순 배열의 SHA-256은 `d4638030330f8c2ba857e63976cc050bf2d631491d59472fab225142eccd49c3`이다.

```json
["HOSTED-DRIFT-01/storage/reference-only","NTP-01/ubuntu-worker/source-loss","NTP-02/ubuntu-worker/resync","POWER-01/ubuntu-worker/controlled-source-loss","POWER-02/control-plane/controlled-source-loss-external-observer","STORAGE-01/eligible-four/physical-reference","SWITCH-01/ubuntu-worker/uplink-loss","SWITCH-02/control-plane/uplink-loss-external-observer","THERM-01/eligible-four/steady-load","TOP-01/all-five/registration-mtls-heartbeat","WAN-01/remote-operator/path-loss","WAN-02/remote-operator/latency-loss","WS-01/ubuntu-workers/steady-bidirectional","WS-02/ubuntu-worker/reconnect-after-wan-loss"]
```

- `TOP-01`은 5개 Node의 등록·mTLS·heartbeat·resource snapshot과 공개 inventory identity를 pre/post로 대조한다. timed 분모에는 들어가지 않는다.
- `THERM-01`은 Ubuntu 4대 timed workload 중 read-only hardware sensor를 60초 이하 간격으로 읽는다.
- `POWER-01/02`는 운영자가 승인한 source-loss window에서만 실행한다. `POWER-02`는 CP와 겸임 Node를 동시에 잃을 수 있으므로 외부 observer 없이는 실행 결과가 아니다.
- `NTP-01/02`는 OS 동기화 상태와 제품 `clock_skew_seconds`를 함께 기록한다. 한쪽만 있으면 완전한 case가 아니다.
- `SWITCH-01/02`는 managed switch의 read-only port event와 외부 observer timeline을 함께 쓴다. heartbeat 부재만으로 switch fault라고 추측하지 않는다.
- `WAN-01/02`는 Node control LAN이 아니라 별도 remote operator path를 대상으로 한다.
- `WS-01/02`는 실제 ticket API와 실제 WebSocket을 쓰고 sequence·nonce가 든 harmless command output을 byte-for-byte 대조한다. mock·로컬 echo는 허용하지 않는다.
- `STORAGE-01`은 #185 `s11-storage-soak-physical-reference-v0`의 exact identity·criteria를 재실행하지 않고 child evidence로 결속한다. child의 physical 창은 composite 창과 시작·종료, source SHA, inventory revision이 같아야 한다.
- `HOSTED-DRIFT-01`은 같은 source SHA의 hosted storage fault/reference 결과다. 실패·누락은 composite PASS를 막지만 성공은 물리 case를 하나도 대체하지 않는다.

## 3. closed fault-class universe

같은 canonicalization으로 아래 배열의 SHA-256은 `62aa166b06ac2b91adef51b5af10d2d2939da5e8a9e008e2a4104b8865cfd27b`이다.

```json
["CLOCK_SKEW_EXCEEDED","CLOCK_SYNC_UNAVAILABLE","COMMITTED_DATA_LOSS","IDENTITY_DRIFT","POWER_RECOVERY_TIMEOUT","POWER_UNEXPECTED_LOSS","PROCESS_RESTART_UNEXPECTED","STORAGE_REFERENCE_FAILED","SWITCH_PATH_UNAVAILABLE","SWITCH_RECOVERY_TIMEOUT","TELEMETRY_GAP","THERMAL_CRITICAL","THERMAL_THROTTLE","UNCLASSIFIED","WAN_PATH_UNAVAILABLE","WAN_RECOVERY_TIMEOUT","WS_CONNECT_FAILED","WS_FRAME_MISMATCH","WS_RECONNECT_TIMEOUT","WS_REPLAY_ACCEPTED"]
```

모든 failed sample/case는 정확히 하나의 class와 case identity, 최초 관측 UTC, external monotonic offset, 대상 공개 node/host alias, recovery receipt를 가져야 한다. 중복 분류·unknown key·목록 밖 class는 `INVALID_RUN`이다. `UNCLASSIFIED`는 원본 보존용 class이며 한 건이라도 있으면 `MEASURED_FAIL`이다. fault가 없었다고 빈 배열을 내는 것은 planned fault case가 부족해 `MEASURED_FAIL`이다.

## 4. 측정 방법과 신뢰 경계

| 영역 | 필수 관측 | 신뢰 경계 |
|---|---|---|
| topology | revision-fixed inventory, DB의 node/channel/resource snapshot, public cert fingerprint | private key·token·DSN·원문 hostname/IP는 artifact에 쓰지 않음 |
| thermal | Linux hwmon 또는 inventory에 pin한 vendor read-only provider의 sensor id/value/critical limit | provider나 sensor가 바뀌면 새 inventory revision; 미지원은 BLOCKED/NOT_OBSERVED |
| power | external observer/PDU·UPS event, OS boot id/uptime, DB node epoch·heartbeat | heartbeat gap만으로 source loss를 추측하지 않음 |
| NTP | `chronyc tracking -c` 또는 pin한 OS provider, Windows time status, 제품 `clock_skew_seconds` | online sample의 NULL/비유한 값을 0으로 보충하지 않음 |
| switch | managed switch read-only `ifOperStatus`/event 또는 동등한 pin된 source + external probe | unmanaged switch에서 원인 추정 금지 |
| WAN | cluster와 다른 failure domain의 remote probe가 loss/latency/route와 UTC+monotonic time 기록 | same-host/loopback 결과는 reference-only |
| WS/PTY | canonical ticket API, actual TLS WebSocket, sequence+nonce payload, server receipt | mock·브라우저 local echo·재사용 ticket 금지 |
| storage | #185 physical reference report/JUnit/receipt의 digest와 targetRef | hosted·PG-free report는 physical reference 대체 불가 |
| hosted drift | exact source SHA의 hosted artifact/run metadata와 case universe | failure는 axis를 막고 success는 physical PASS 분자 0 |

hosted child는 composite run보다 7일 이상 오래될 수 없고 `sourceHeadSha`·target source blobs가 같아야 한다. physical report의 시작·종료가 hosted run보다 앞이어도 되지만, 둘 다 registry repin commit의 후손이어야 한다. failed/cancelled/deleted artifact, merge-ref checkout, dirty checkout, 다른 SHA의 green 결과는 `INVALID_RUN`이다.

## 5. 판정과 안전

- 14개 case와 criteria가 모두 만족하고 exact fault class 집계가 맞을 때만 `MEASURED_PASS`다.
- hosted green만 있으면 `NOT_OBSERVED` 또는 `BLOCKED_EXTERNAL`이지 PASS가 아니다.
- 물리 storage reference만 green이어도 열·전원·NTP·스위치·WAN·WS가 빠졌으므로 PASS가 아니다.
- CP observer가 함께 사라지는 case에 external monotonic evidence가 없으면 latency/recovery를 만들지 않는다.
- fault injection은 승인된 maintenance window와 대상별 rollback/runbook이 있을 때만 한다. `rm`, prune, volume/key/state 교체, 보호 컨테이너 조작은 금지한다.
- 부분 실행을 다음 날 다른 inventory·SHA·창과 합쳐 24시간으로 만들지 않는다. 계획된 fault로 중단된 구간은 동일 창 안에서 external observer가 이어져야 한다.
- 운영자 자원 제공 전에는 target 등록 여부와 무관하게 `BLOCKED_EXTERNAL(G-19/G-24)`이며 AC-11 `done`을 막는다.

## 6. registry repin 선행 카드

설계 승인 뒤 `CARD-S11-AC11-LONG-SOAK-REPIN-01`을 별도로 수행한다.

1. 이 문서의 reviewed commit/path/blob을 `sourceDocument`로 하는 `s11-ac11-composite-long-soak-v0` entry를 단일 registry에 추가한다.
2. `tools/aggregate_ac11_evidence.py`의 `REQUIRED_TARGET_BY_AXIS["long-soak"]`를 새 target 하나로 고정한다.
3. registry 새 blob을 `TARGET_REGISTRY_BLOB` literal을 가진 집계기·migration importer·storage importer·새 long-soak importer 전부에 같은 commit으로 repin한다. `git grep -n -F <old-blob>` 잔여가 0이어야 한다.
4. old blob, 미등록 target, sourceDocument blob drift, hosted-only, case 13/14, duplicate case, wrong topology count, colocated Node의 timed 분모 편입, child SHA/window/inventory mismatch, unknown fault class를 부정 시험으로 거부한다.
5. target 문서 commit이 integration 조상으로 남도록 merge commit만 사용한다. squash/rebase 뒤 SHA를 지어내지 않는다.
6. repin 뒤 release SHA에서 hosted reference와 물리 run을 새로 만든다. repin 전 artifact와 envelope는 `INVALID_RUN`이다.

이 카드에서는 registry·집계기·importer를 변경하지 않고 실제 soak·fault injection을 실행하지 않는다.
