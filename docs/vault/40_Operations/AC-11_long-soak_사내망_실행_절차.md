---
doc_id: "RUNBOOK-AC11-LONG-SOAK-INTRANET-V1"
title: "AC-11 long-soak 사내망 실행 절차 — 24시간 물리 5노드 창, hosted로는 만족할 수 없는 축"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T09:20:16+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "97b18077"
task_ids: ["S11-BE"]
tags: ["ac11", "long-soak", "intranet", "runbook", "s11", "claude"]
---

# AC-11 long-soak — 사내망 실행 절차

## 0. 이 절차가 있는 이유 — hosted로는 정의를 만족할 수 없다

이 축의 정본은 target registry의 **`s11-ac11-composite-long-soak-v0`** 이고, 그 `criteria`·`requiredEnvironment`가 요구하는 것 중 **hosted runner가 줄 수 없는 것**이 다음이다(카드 217에서 정본을 읽어 대조했다).

| 정의가 요구하는 것 | hosted | 이유 |
|---|---|---|
| `windowSeconds >= 86400` | **불가** | 24시간이고 GitHub job 한도는 6시간이다. 86,400초 > 21,600초 |
| `requiredEnvironment.topology: physical-five-node`, `windowClass: physical-24h`, registered 5 / eligible 4 / excluded 1, `cpColocatedNodeCount: 1` | **불가** | 물리 호스트 다섯 대와 CP 겸임 한 대를 요구한다 |
| `minThermalHeadroomMilliC >= 5000`, `thermalThrottleSeconds == 0`, `criticalThermalEventCount == 0` | **불가** | hosted VM은 열 여유를 노출하지 않는다 |
| `plannedPowerFaultCaseCount >= 2`, `powerRecoveryPassCount >= 2`, `maxPowerRecoverySeconds <= 900`, `unexpectedPowerLossCount == 0` | **불가** | runner의 전원을 끊고 복구를 관측할 수 없다 |
| `switchFaultCaseCount >= 2`, `wanFaultCaseCount >= 2`와 각 복구 한도 | **불가** | 네트워크 fabric을 제어하지 않는다 |
| `externalObserverCoveragePpm >= 990000`, `observer: external-monotonic-v1` | **불가** | 관측자가 측정 대상 집단 **밖**에 있어야 한다 |
| `faultInjection: controlled-v1` | **불가** | 이 저장소가 소유하지 않는 **G-24 fault-control adapter**다 |

**축을 낮춰 맞추지 않는다.** 그래서 hosted workflow를 만들지 않았고, `docs/ac11-axis-sources.json`의 long-soak 행은 `chain: incomplete`·`workflow: null`로 두고 그 사유를 적었다.

**생산자 자신이 같은 말을 한다** — 이 PC에서 실제로 실행한 명령과 그 답이다:

```bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
OUT=".work/ac11-long-soak/preflight-$(date +%s)"
mkdir -p "$OUT"
python tools/run_ac11_composite_long_soak.py --mode physical \
  --source-run-id 36951113824 \
  --report-output "$OUT/report.json" \
  --evidence-output "$OUT/evidence.json"
```

→ **exit 2**, 그리고 report는 이렇게 적는다:

| 필드 | 값 |
|---|---|
| `runPurpose` | `s11-ac11-composite-long-soak-physical-preflight` |
| `verdict` | **`BLOCKED_EXTERNAL`** |
| `blocker` | **`G-19`** |
| `reason` | `five-node inventory is missing; no physical action was started` |
| `execution` | `{"started": false, "physicalActions": false}` |
| `referenceOnly` · `acceptanceClaim` | `true` · `false` |

**물리 동작을 시작하기 전에 멈춘다** — 인벤토리가 없으면 아무것도 하지 않는 것이 이 생산자의 설계이고, `execution.started: false`가 그것을 기록한다. `--source-run-id`는 report에 그대로 적히는 식별자이므로 이 시도를 묶을 run id를 쓰면 된다(위 번호는 내가 쓴 값이다).

**출력 경로가 이미 있으면 생산자가 거부한다** — `error: output paths must not already exist`(exit 2)로 멈춘다. 그래서 위 블록은 매번 새 디렉터리를 만든다. 지난 report를 덮어쓰지 않는 것이 이 도구의 설계이고, **덮어쓰기를 피하려고 경로를 재사용하지 않는 것이 운영자의 일**이다.

## 1. 선행 조건 — 사람이 갖춰야 하는 것

| 전제 | 상태 | 어디 |
|---|---|---|
| 물리 5노드(worker 4 + CP 겸임 1) | **사용자 조치** | `#300` 체크리스트 §7(`U-A`: node4 공급 + node5 CP 겸임 blocker 해소) |
| 5노드 인벤토리 실측값 | **사용자 조치** | 같은 §7. 생산자가 `--inventory`로 읽는다 |
| G-24 fault-control adapter(전원·switch·WAN 고장 주입) | **외부 자산** | 이 저장소에 없다. 그것이 오기 전에는 `--mode physical`이 BLOCKED_EXTERNAL로 멈춘다 |
| 외부 monotonic 관측자 | **외부 자산** | `observer: external-monotonic-v1` — 측정 대상 밖의 호스트 |
| 24시간 창 | 운영 결정 | 그 시간 동안 노드를 다른 작업에 쓰지 않는다 |

**노드의 `sudo`가 필요한 단계는 사용자가 실행한다**(코디네이터도 agent도 노드 sudo 비밀번호를 갖고 있지 않다). 비밀은 `.work/intranet/`(untracked)에만 두고 이 문서로 옮기지 않는다.

## 2. 실행 — 전제가 갖춰진 뒤

### 2-1. 인벤토리를 주고 preflight만 먼저 돌린다

```bash
set -euo pipefail
cd /d/Project/SaintVisionI-Invion
INV="${INV:?5노드 인벤토리 JSON 경로를 INV로 export하고 다시 실행}"
RUN="${RUN:?이 실행을 묶을 run id를 RUN으로 export하고 다시 실행}"
OUT=.work/ac11-long-soak
mkdir -p "$OUT"
python tools/run_ac11_composite_long_soak.py --mode physical \
  --inventory "$INV" \
  --source-run-id "$RUN" \
  --report-output "$OUT/report.json" \
  --evidence-output "$OUT/evidence.json" \
  --junit "$OUT/junit.xml" || code=$?
echo "producer exit ${code:-0}"
```

**exit 2이고 `blocker`가 적혀 있으면 그 blocker가 아직 열린 것이다** — 인벤토리가 통과하면 그다음 blocker(G-24 adapter)가 나온다. **blocker가 바뀌는 것이 진척이고, 그 전에 다음 단계로 가지 않는다.**

### 2-2. 24시간 창을 돌린다

G-24 adapter가 붙은 뒤에만 가능하다. 그 adapter의 호출 방법은 **이 저장소에 없으므로 여기에 명령을 적지 않는다** — adapter가 들어오는 PR의 운영 문서를 따른다. 창 동안 요구되는 것은 §0 표의 criteria 전부이고, 특히 **고장 주입 케이스 수**(전원 2 이상, switch 2 이상, WAN 2 이상)와 **복구 시간 한도**는 창 안에서 관측돼야 한다.

### 2-3. 두 reference를 함께 모은다

importer는 **네 인자를 모두 요구한다** — 실제 `--help` 출력이 그렇다:

```bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
python tools/import_ac11_composite_long_soak.py --help
```

→ `--report`, `--storage-reference`, `--hosted-reference`, `--output` 네 개가 모두 `required`다. 두 reference는 criteria의 `storagePhysicalReferencePassCount == 1`·`hostedDriftReferencePassCount == 1`에 대응하고, **그것 없이는 importer가 봉투를 쓰지 않는다.**

### 2-4. 축 envelope으로 들인다

```bash
set -euo pipefail
cd /d/Project/SaintVisionI-Invion
OUT=.work/ac11-long-soak
python tools/import_ac11_composite_long_soak.py \
  --report "$OUT/report.json" \
  --storage-reference "$OUT/storage-reference.json" \
  --hosted-reference "$OUT/hosted-reference.json" \
  --output "$OUT/ac11-axis-evidence.json"
```

**importer가 축 envelope을 내는 것은 dry-run report에 대해서다** — 읽어서 확인했다:

| 측정한 것 | 결과 |
|---|---|
| `EMITTED_AXES` | `("long-soak",)`, 봉투의 `axis`는 그 상수에서 나온다 |
| 받는 report | **`runPurpose`가 `s11-ac11-composite-long-soak-dry-run`이 아니면 거부**한다(`tools/import_ac11_composite_long_soak.py:242`) |
| 그 봉투의 판정 | `verdict: NOT_OBSERVED`, reason `synthetic dry-run is reference-only and cannot satisfy the physical target`, `environment.comparableGroup: reference-only` |
| 물리 창 report | **분기가 없다.** 생산자가 `--mode physical`에서 BLOCKED_EXTERNAL로 멈추므로 물리 report는 **아직 존재하지 않는 문서**다 |

**그래서 이 축에 남은 것은 실행만이 아니다** — 물리 창 report를 들이는 importer 분기도 없다. 그 분기를 지금 쓰면 **아무도 만들 수 없는 문서의 모양을 발명하는 것**이 되므로, 이 절차는 그 분기가 무엇을 요구해야 하는지를 §5에 질문으로 남긴다.

### 2-5. 집계기에 넣는다

착지된 tree에서 그 envelope을 모아 조립기·집계기에 넣는 절차는 **카드 203 History §5-4**가 정본이다(`#299`). 그 lane이 envelope 디렉터리를 읽어 manifest를 쓰고 8축을 재계산한다.

## 3. 확인할 관측

| 보는 것 | 통과 조건 |
|---|---|
| 생산자 exit | 0(창이 끝났고 판정이 나왔다). 2는 **아직 전제가 열려 있다** |
| `windowSeconds` | **>= 86400** |
| 고장 주입 | 전원·switch·WAN **각 2건 이상**과 각 복구 pass 수, 복구 시간 한도 통과 |
| 외부 관측자 coverage | `externalObserverCoveragePpm >= 990000` |
| 누수 지표 | `memoryGrowthBytes <= 268435456`, `fileDescriptorGrowthCount <= 32`, `dbConnectionGrowthCount <= 4` |
| 정합 지표 | `falseSuccessCount`·`classificationMismatchCount`·`committedDataLossCount`·`staleWriteCount`·`unclassifiedFaultCount`·`cleanupResidueCount` **전부 0** |
| 등록 case | `requiredCaseCount` == **14**, `executedRequiredCaseCount` == **14** — 등록된 14개 case가 **전부** 실행돼야 한다. 하나라도 빠지면 창을 다시 돈다 |
| WS 세션 | `wsRoundTripCount` >= **1000**, `wsSteadySessionCount` >= **4**, `maxWsReconnectSeconds` <= **60**, `wsDuplicateExecutionCount`·`wsPayloadMismatchCount`·`unauthorizedWsReplayAcceptanceCount` **전부 0** |
| 시계 | `maxAbsClockSkewMillis` <= **5000**, `clockResyncPassCount` >= **1**, `maxClockResyncSeconds` <= **300**, `clockSkewUnmeasuredSampleCount` == **0** |
| 관측 범위 | `telemetryCoveragePpm` >= **990000**(외부 관측자 coverage와 별개 지표다) |
| 두 reference | `storagePhysicalReferencePassCount` == **1**, `hostedDriftReferencePassCount` == **1**, `hostedDriftReferenceFailureCount` == **0** |
| 동일성 | `identityDriftCount` == **0**, `unexpectedProcessRestartCount` == **0** |
| 집계기 | 이 축이 `MEASURED_PASS`로 재계산되는지. `NOT_REGISTERED`·`NOT_OBSERVED`면 그 사유가 무엇이 빠졌는지 말한다 |

**이 표의 값은 전부 target registry에서 읽은 것이다** — `docs/vault/30_Development/Evidence/s11-ac11-target-registry-v0.json`의 `s11-ac11-composite-long-soak-v0` `criteria` 48개 항목이고, 집계기가 그 registry를 Git에서 직접 읽어 비교한다. **정본의 숫자를 여기에 옮겨 적은 것이지 여기서 정하는 것이 아니다.**

## 4. 물리 importer 분기에 필요한 계약 질문 (소유자: S11 target/producer owner)

물리 창 report를 받을 분기는 **그 report가 무엇을 담는지가 정해진 뒤에** 쓰는 것이 맞다. 지금 정해지지 않은 것:

1. **물리 report의 `runPurpose`와 `environment`**: dry-run은 `synthetic-*`·`comparableGroup: reference-only`를 pin한다. 물리 창은 registry의 `requiredEnvironment`(`topology: physical-five-node`, `observer: external-monotonic-v1`, `faultInjection: controlled-v1`, `windowClass: physical-24h`, `timedPopulation: cp-independent-ubuntu-four`)를 그대로 쓰는가, 그리고 **comparability group 이름**은 무엇인가.
2. **48개 criteria 값을 report의 어디에 싣는가**: dry-run은 case universe와 `casePlans`를 담는다. 물리 창은 측정값(창 길이·고장 주입 수·복구 시간·누수 지표·WS 지표·시계 지표)을 **어떤 키로** 담는가. 집계기의 일반 경로(`observations`)인가, 축 전용 모양인가.
3. **두 reference의 결속**: `storagePhysicalReferencePassCount`·`hostedDriftReferencePassCount`가 1이어야 하는데, 물리 창에서도 dry-run과 같은 두 reference 문서를 쓰는가.
4. **중단된 창의 처리**: 24시간 중 고장 주입이 실패해 창이 끊기면 `NOT_OBSERVED`인가 `MEASURED_FAIL`인가. 정본에 그 구분이 없다.

**이 질문들이 닫히기 전에 분기를 쓰면 추측을 코드로 고정하는 것이고, 그 추측은 아무도 반증할 수 없다**(생산자가 물리 report를 낼 수 없으므로).

## 5. 이 절차가 하지 않는 것

- **축 정의를 완화하지 않는다.** `criteria`·`requiredEnvironment`를 그대로 쓴다.
- **hosted workflow를 만들지 않는다.** §0의 일곱 줄이 그 이유이고, 만들면 증거를 만들 수 없는 lane이 하나 늘 뿐이다.
- **G-24 adapter의 명령을 적지 않는다.** 이 저장소에 없는 것을 명령으로 적을 수 없다(§2-2).
- **24시간 창을 줄이지 않는다.** 짧은 창은 이 축의 측정이 아니다.
- **물리 importer 분기를 추측으로 쓰지 않는다.** §4의 질문이 닫힌 뒤에 쓴다.
