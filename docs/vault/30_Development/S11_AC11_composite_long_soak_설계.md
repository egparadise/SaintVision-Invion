---
doc_id: "DESIGN-S11-AC11-COMPOSITE-LONG-SOAK-001"
title: "S11 AC-11 composite long-soak 설계"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T19:59:12+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_id: "S11-BE"
acceptance_id: "AC-11"
tags: ["S11", "AC-11", "long-soak", "five-node", "evidence"]
---

# S11 AC-11 composite long-soak 설계

## 0. 결정

AC-11 `long-soak`은 storage-only 또는 hosted-only target이 아니다. 열·전원·NTP·스위치·WAN·실제 remote WS/PTY와 물리 storage soak를 **한 release SHA, 한 revision-fixed inventory, 한 24시간 물리 창**에서 결속하는 composite axis다. 결과를 보기 전 목표는 [[S11_AC11_composite_long_soak_target_v0]]에 고정했다.

이 설계·target·patch proposal은 registry를 바꾸지 않으며 실제 측정을 실행하지 않는다. 운영자 자원 제공 전 상태는 `BLOCKED_EXTERNAL(G-19/G-24)`이고, AC-11은 미완료다.

## 1. 근거와 경계

- #157 head `ec86fce6f5cade2b2ccc3abfd2ae1a7f1ef4e316`의 `S11-BE_DB_AC-11_통합_인수_설계.md:238`은 `long-soak`을 필수 8축 중 하나로 두고 `:254`에서 아직 `NOT_OBSERVED`로 기록한다.
- #185 head `33ed1b8c79d57532b92c10858241f05aff6bd8ec`의 storage 설계 `:22`, `:88`은 열·전원·NTP·스위치·WAN·원격 WS가 빠진 storage result를 reference-only로 제한하고 composite target 전 `NOT_REGISTERED`로 둔다.
- 같은 head의 `S11_ST_storage_failure_target_v0.md:29`가 물리 storage reference의 24시간·1000 operation·3 fault와 memory/FD/DB drift 한계를 고정한다. composite는 이를 복제하지 않고 child evidence로 결속한다.
- ADR-100 at `ec86fce6…`: 결과에 `registeredNodeCount=5`, `cpIndependentWorkerHostCount=4`, `cpColocatedNodeCount=1`을 기록(`:29`)하고, 5-node topology smoke와 Ubuntu 4대 timed 분모를 분리한다(`:35`, `:43`). CP host-loss latency는 external monotonic observer 없이는 unmeasured다(`:54`).
- ERR-DESIGN-007은 online Node의 미측정·비유한·`abs(clock_skew_seconds)>5`를 경계로 고정한다. `inv.leases`에도 `abs(clock_skew_seconds)<=5`가 존재한다. composite의 `maxAbsClockSkewMillis<=5000`은 이 제품 경계에서 복사한 값이다.
- S06-FE matrix at `ec86fce6…:52`, `:115`는 30초 ticket과 실제 5-node remote PTY를 아직 `UNMEASURED`로 둔다. composite는 mock/UI local echo가 아니라 canonical ticket API와 실제 TLS WebSocket만 허용한다.

## 2. 증거 구성

```text
long-soak axis envelope
├─ physical 24h report (topology, thermal, power, NTP, switch, WAN, WS)
├─ storage physical reference (#185; same SHA/inventory/window)
├─ hosted storage/drift reference (same SHA; reference-only)
├─ exact case/fault-class manifests
└─ cleanup + external observer receipts
```

상위 importer는 child verdict를 그대로 믿지 않는다. target criteria와 exact identity hash를 다시 계산하고, child artifact digest·source SHA·inventory revision·time window를 대조한다.

### 2.1 physical report

- 5개 등록 Node를 pre/post smoke에서 모두 확인한다.
- timed sample과 fault target은 Ubuntu 4대뿐이다. CP 겸임 Node는 `excludedNodeCount=1`이고 사후 필터링이 아니라 실행 전부터 대상에서 빠진다.
- external observer는 CP·switch·WAN과 다른 failure domain에 있어야 하고 UTC와 monotonic offset을 함께 남긴다.
- 60초 이하 cadence에서 physical·external coverage 각각 99% 이상을 요구한다. gap은 0으로 채우지 않고 `TELEMETRY_GAP`이다.

### 2.2 storage reference 결속

`STORAGE-01`은 #185 physical storage reference의 report/JUnit/receipt digest를 참조한다. source SHA, inventory revision, startedAt/finishedAt가 composite physical report와 같아야 한다. 24시간을 다른 날의 storage report와 합치거나 hosted case로 물리 3 fault를 대체하면 `INVALID_RUN`이다.

### 2.3 hosted drift 결속

`HOSTED-DRIFT-01`은 같은 source SHA와 target source blobs의 hosted storage fault/reference artifact다. red/failed/cancelled/deleted/missing이면 `hostedDriftReferenceFailureCount>0` 또는 `NOT_OBSERVED`로 축을 막는다. green은 제품 코드가 known hosted 경계에서 drift하지 않았다는 보조 근거일 뿐 다음을 할 수 없다.

- 물리 case identity를 executed로 채우기
- topology·열·전원·NTP·switch·WAN·WS observation 생성
- `storagePhysicalReferencePassCount` 생성
- `long-soak=MEASURED_PASS` 단독 결정

## 3. 영역별 측정

| 영역 | 관측값 | 계측 | fail-closed 조건 |
|---|---|---|---|
| 열 | sensor id, critical limit, 현재·max 온도, throttle duration | pin된 hwmon/vendor read-only provider | sensor/limit 부재, critical, throttle |
| 전원 | external source event, boot id/uptime, epoch/heartbeat, recovery seconds | PDU/UPS 또는 현장 receipt + external observer + OS | heartbeat만으로 원인 추정, observer gap, identity drift |
| NTP | source/sync state/offset, 제품 skew, resync seconds | pin된 OS time provider + DB observation | 한쪽 부재, 비유한/NULL, ±5초 초과 |
| switch | port event, path probe, mTLS/heartbeat recovery | managed switch read-only log + external probe | unmanaged 장비에서 원인 추정, recovery receipt 부재 |
| WAN | remote loss/latency/route, recovery | 별도 failure domain의 probe | loopback/same-host 대체, source SHA 불일치 |
| WS/PTY | ticket issue/reuse, TLS connect, sequence/nonce bytes, execution count | 실제 ticket API + actual WebSocket | mock/local echo, payload mismatch, duplicate/replay acceptance |
| storage | #185 exact physical fault/reference metrics | child artifact 검증 | 다른 창/SHA/inventory, hosted 대체 |

절대 온도는 장비마다 다르므로 target은 vendor critical limit 대비 5°C headroom을 사용한다. fault recovery 한도는 power 900초, NTP 300초, switch 300초, WAN 120초, WS 60초로 결과 전에 고정했다. 이 값 변경은 새 target ID/version과 registry repin 없이는 허용하지 않는다.

## 4. exact identity와 fault class

target §2의 14개 case 배열 SHA-256은 `d4638030330f8c2ba857e63976cc050bf2d631491d59472fab225142eccd49c3`, §3의 20개 fault-class 배열 SHA-256은 `62aa166b06ac2b91adef51b5af10d2d2939da5e8a9e008e2a4104b8865cfd27b`다.

case 14개 전부가 중복 없이 있어야 한다. 모든 failed sample/case는 exactly-one fault class를 가져야 하며 `UNCLASSIFIED`도 실패다. 결과를 보고 case 이름을 추가하거나 같은 case를 반복해 count를 채우면 `INVALID_RUN`이다.

## 5. registry 적용 절차

`Evidence/s11-ac11-composite-long-soak-target-patch-v0.json`은 review artifact이고 `consumableAsTargetRef=false`다. 적용은 #192와 같은 별도 `CARD-S11-AC11-LONG-SOAK-REPIN-01`에서 한다.

1. Claude가 target commit `938ad3eb1c1664890c714f6ec86f409b7dab65b9`와 blob `0bf74f90557a237b50ebdf571ed9e3dac89ea23b`를 검토한다.
2. #192 registry predecessor `7be9154f…` / blob `e8c01340…`에 target entry를 추가한다.
3. `REQUIRED_TARGET_BY_AXIS["long-soak"]`와 registry blob을 aggregator 및 모든 importer에 한 commit으로 repin한다.
4. old blob·hosted-only·case/fault-class drift·wrong topology·child mismatch 부정 시험을 먼저 고정한다.
5. target source commit을 보존하는 merge commit으로 병합한 뒤 release SHA에서 evidence를 새로 만든다.

registry patch와 importer 구현 전에는 target이 승인돼도 `NOT_REGISTERED`다. repin 뒤에도 operator resource가 없으면 `BLOCKED_EXTERNAL(G-19/G-24)`다.

## 6. 안전·롤백·현재 상태

- 이 카드에서 Node 중단, 전원/네트워크 fault, storage write, PG/Docker/browser 실행은 0건이다.
- 실제 fault card는 maintenance window, 대상, rollback, external observer, 금지 명령을 사전 승인받아야 한다. `rm`, prune, volume/key/state 교체와 보호 컨테이너 조작은 금지한다.
- docs-only rollback은 이 PR revert다. target criteria 변경은 기존 ID를 덮어쓰지 않고 새 target version으로 제안한다.
- 현재는 설계·target proposal만 있으며 `long-soak`은 PASS가 아니다.
