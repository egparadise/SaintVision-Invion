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
| **Python >= 3.11** | 환경 | 생산자가 `enum.StrEnum`을 쓴다. 이 PC 기본 `python`은 3.10.11이고 `--help`조차 `ImportError: cannot import name 'StrEnum' from 'enum'`으로 멈춘다(실행해 확인). importer는 3.10에서도 `--help`가 돈다 |

**노드의 `sudo`가 필요한 단계는 사용자가 실행한다**(코디네이터도 agent도 노드 sudo 비밀번호를 갖고 있지 않다). 비밀은 `.work/intranet/`(untracked)에만 두고 이 문서로 옮기지 않는다.

## 2. 실행 — 전제가 갖춰진 뒤

### 2-0. 먼저 이 블록이 통과하는지 본다 (cwd와 interpreter)

```bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
test -f tools/run_ac11_composite_long_soak.py
python -c "import sys; assert sys.version_info >= (3, 11), sys.version"
python tools/run_ac11_composite_long_soak.py --help > /dev/null
python tools/import_ac11_composite_long_soak.py --help > /dev/null
echo "smoke ok: $(pwd) with python $(python -c "import sys;print(sys.version.split()[0])")"
```

**실행한 결과**(이 PC):

- 3.11 이상이 PATH에 있을 때 → `smoke ok: … with python 3.14.7`
- 기본 `python`(3.10.11)일 때 → 세 번째 줄에서 `AssertionError: 3.10.11 …`로 멈춘다. **그 assert가 먼저 멈추는 것이 이 블록의 목적**이다: 그것 없이는 생산자의 `ImportError`가 나중에 나온다.

**절대 경로를 적지 않는 이유**: 정본 checkout의 위치는 기계마다 다르고, 이 저장소에는 상위 디렉터리에 `tools/`가 없는 중간 경로가 실제로 존재한다. `git rev-parse --show-toplevel`이 그것을 묻지 않고 답한다.

### 2-1. 인벤토리를 주고 preflight만 먼저 돌린다

```bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
test -f tools/run_ac11_composite_long_soak.py   # 이 cwd가 정본 checkout인지 먼저 확인한다
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
cd "$(git rev-parse --show-toplevel)"
test -f tools/import_ac11_composite_long_soak.py
OUT=.work/ac11-long-soak
python tools/import_ac11_composite_long_soak.py \
  --report "$OUT/report.json" \
  --storage-reference "$OUT/storage-reference.json" \
  --hosted-reference "$OUT/hosted-reference.json" \
  --output "$OUT/ac11-axis-evidence.json"
```

**importer는 물리 report를 이미 받는다** — `import_report()`를 읽고 확인했다:

| 측정한 것 | 결과 |
|---|---|
| `EMITTED_AXES` | `("long-soak",)`, 봉투의 `axis`는 그 상수에서 나온다 |
| dry-run | `runPurpose == s11-ac11-composite-long-soak-dry-run`일 때만 **reference-only 분기**로 가고, 그 봉투는 `NOT_OBSERVED`(`comparableGroup: reference-only`, `topology: synthetic-five-node`) |
| 물리 report | 그 밖에는 `readiness()`로 **G-19·G-24 보유**를 확인한 뒤 **exact v1 key set 22개**를 요구한다 |
| 물리 판정 | 48개 metric을 registry criteria와 **exact set**으로 대조해 `MEASURED_PASS` / `MEASURED_FAIL` 봉투를 만들고, `targetRef`에 registry criteria를 그대로 싣는다 |
| 집계기까지 | `tests/test_import_ac11_composite_long_soak.py::test_valid_physical_report_is_accepted_by_the_ac11_aggregator`가 물리 report → 봉투 → `evaluate_axis()` → **`MEASURED_PASS`**를 고정한다 |

**그래서 이 축에 남은 것은 코드가 아니라 실측이다** — 들이는 계약은 이미 있고, 그 계약의 final report를 **생산할 수 있는 것이 없다**(§4).

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

## 4. 실제 공백 — 계약은 있고, 그 계약을 채울 생산자가 없다

**들이는 계약은 이미 정해져 있다.** `tools/import_ac11_composite_long_soak.py`의 `import_report()`가 물리 report에 요구하는 것(읽어서 적었다):

| 요구 | 내용 |
|---|---|
| key set | **exact 22개**: `schemaVersion`·`runPurpose`·`sourceRunId`·`sourceHeadSha`·`checkoutTreeSha`·`cleanCheckout`·`startedAt`·`finishedAt`·`artifactSha256`·`artifactObservedSha256`·`artifactExpiresAt`·`inventoryRevision`·`environment`·`operatorResources`·`caseIdentities`·`faultClasses`·`cases`·`metrics`·`cleanup`·`externalObserverReceipt`·`storageReferenceSha256`·`hostedReferenceSha256`. 하나 더 있거나 빠지면 거부 |
| 식별 | `runPurpose == "s11-ac11-composite-long-soak"`, `operatorResources`는 `{G-19, G-24}`의 고유 부분집합이고 **둘 다 있어야** readiness를 통과한다 |
| tree | `cleanCheckout: true`이고 `checkoutTreeSha == git tree(sourceHeadSha)` |
| 창 | `finishedAt - startedAt >= 24시간`. 짧으면 거부 |
| environment | registry의 `requiredEnvironment` 9개 값을 **그대로** 만족하고 **비어 있지 않은 `comparableGroup`** |
| case | `caseIdentities`·`faultClasses`가 pin된 목록과 exact(그 canonical sha까지), `cases`는 14개 전부·중복 없음·`PASS`/`FAIL`, FAIL은 그 identity가 허용하는 fault class만 |
| 관측자 | `externalObserverReceipt == {kind: external-monotonic-v1, inventoryRevision: 보고서의 값, coveragePpm: metrics의 값, redacted: true}` |
| 두 child reference | `storageReferenceSha256`·`hostedReferenceSha256`이 각 문서의 canonical sha와 일치하고, 두 문서가 같은 source·같은 창에 결속된 passing reference |
| metrics | registry criteria와 **exact set**(48개). `windowSeconds`·`requiredCaseCount`·`executedRequiredCaseCount`·두 reference pass count·`classificationMismatchCount`·`unclassifiedFaultCount`·`cleanupResidueCount`는 importer가 **직접 재계산해 대조**하므로 적어 넣는 값이 아니다 |
| 판정 | 48개 criteria를 operator(`eq`/`gte`/`lte`)로 평가해 `MEASURED_PASS`/`MEASURED_FAIL`. FAIL한 case가 있는데 어떤 criterion도 실패하지 않으면 **거부**한다 |

**그래서 이 절차가 기다리는 것은 계약이 아니라 그 계약을 채우는 실행이다.** 측정한 생산자 쪽 공백:

- `tools/run_ac11_composite_long_soak.py`의 `--mode physical`은 **항상** `blocked_physical_report`를 쓰고 exit 2다 — 인벤토리가 없으면 `G-19`, 인벤토리가 통과하면 `G-24`. 위 22-key final report를 쓰는 분기는 **생산자에 없다**.
- 그 분기는 **24시간 창을 실제로 돌리고 고장을 주입한 뒤에만** 의미가 있으므로, G-24 adapter와 물리 5노드가 오는 것과 같은 작업이다.

**그러므로 producer owner가 할 일은 새 계약을 정하는 것이 아니라 위 표를 그대로 채우는 것이다.** 이 절차가 그 표를 인용하는 이유도 그것이다 — importer가 정본이고, 여기 적힌 것은 그 정본을 읽은 결과다.

## 5. 이 절차가 하지 않는 것

- **축 정의를 완화하지 않는다.** `criteria`·`requiredEnvironment`를 그대로 쓴다.
- **hosted workflow를 만들지 않는다.** §0의 일곱 줄이 그 이유이고, 만들면 증거를 만들 수 없는 lane이 하나 늘 뿐이다.
- **G-24 adapter의 명령을 적지 않는다.** 이 저장소에 없는 것을 명령으로 적을 수 없다(§2-2).
- **24시간 창을 줄이지 않는다.** 짧은 창은 이 축의 측정이 아니다.
- **importer를 고치지 않는다.** 물리 계약은 이미 있고(§4), 이 절차는 그것을 인용할 뿐이다.
