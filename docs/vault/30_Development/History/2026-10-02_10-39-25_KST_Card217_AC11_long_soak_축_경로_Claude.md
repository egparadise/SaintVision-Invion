---
doc_id: "HISTORY-CARD217-AC11-LONG-SOAK-PATH-20261002"
title: "카드 217 — long-soak 축: hosted로는 정의를 만족할 수 없다. 축을 낮추지 않고, 사내망 절차와 막는 것의 이름을 남겼다"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T10:57:05+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "7183aaff"
task_ids: ["S11-BE"]
tags: ["ac11", "long-soak", "intranet", "runbook", "s11", "claude"]
---

# 카드 217 — long-soak 축의 경로

## 0. 한 줄

판정은 **(b)** 다. 정본이 요구하는 것은 **물리 5노드에서 24시간**이고 hosted runner의 job 한도는 6시간이며, 열·전원·switch·WAN·외부 관측자·고장 주입은 hosted VM이 **줄 수 없는 것**이다. **축을 낮춰 맞추지 않았다** — hosted workflow를 만들지 않고, 사내망 실행 절차와 `axis-sources`의 사유를 남겼다. **[§7-1에서 정정]** 처음 판에서 "importer에 물리 report 분기가 없다"고 썼는데 **틀렸다** — 분기는 있고 집계기까지 `MEASURED_PASS`로 간다. 실제 공백은 **그 계약을 채울 생산자와 24시간 실측**이다.

## 1. 정본이 요구하는 것 — registry에서 읽었다

| 읽은 것 | 값 |
|---|---|
| target | `s11-ac11-composite-long-soak-v0`(`REQUIRED_TARGET_BY_AXIS["long-soak"]`) |
| criteria | **48개 항목** |
| `requiredEnvironment` | `topology: physical-five-node`, `windowClass: physical-24h`, `registeredNodeCount 5` / `eligibleNodeCount 4` / `excludedNodeCount 1`, `cpIndependentWorkerHostCount 4`, `cpColocatedNodeCount 1`, `timedPopulation: cp-independent-ubuntu-four`, `observer: external-monotonic-v1`, `faultInjection: controlled-v1` |
| sourceDocument | `docs/vault/30_Development/S11_AC11_composite_long_soak_target_v0.md` @ `938ad3eb`, blob `0bf74f90` |

**정본의 pin이 tree에서 그대로다**: registry blob `eeb43dc2` == 집계기가 pin하는 값, sourceDocument blob `0bf74f90` == tree의 값, `938ad3eb`는 HEAD의 ancestor. 즉 **이 축이 막힌 이유는 provenance 문제가 아니다**(security 축에서 발견한 pin drift와 대조된다 — `#313`).

## 2. (a)인가 (b)인가 — hosted로 만들 수 있는지 대조했다

| 정의가 요구하는 것 | hosted | 이유 |
|---|---|---|
| `windowSeconds >= 86400` | **불가** | 86,400초 > GitHub job 한도 21,600초 |
| `topology: physical-five-node`, `windowClass: physical-24h`, 5/4/1, `cpColocatedNodeCount 1` | **불가** | 물리 호스트 다섯 대와 CP 겸임 한 대 |
| `minThermalHeadroomMilliC >= 5000`, `thermalThrottleSeconds == 0`, `criticalThermalEventCount == 0` | **불가** | hosted VM은 열 여유를 노출하지 않는다 |
| `plannedPowerFaultCaseCount >= 2`, `powerRecoveryPassCount >= 2`, `maxPowerRecoverySeconds <= 900`, `unexpectedPowerLossCount == 0` | **불가** | runner의 전원을 끊고 복구를 관측할 수 없다 |
| `switchFaultCaseCount >= 2`, `wanFaultCaseCount >= 2`와 각 복구 한도 | **불가** | 네트워크 fabric을 제어하지 않는다 |
| `externalObserverCoveragePpm >= 990000`, `observer: external-monotonic-v1` | **불가** | 관측자가 측정 대상 집단 **밖**에 있어야 한다 |
| `faultInjection: controlled-v1` | **불가** | 이 저장소가 소유하지 않는 **G-24 fault-control adapter** |

**생산자 자신이 같은 말을 한다** — 이 PC에서 실제로 실행했다(`--mode physical`, `--source-run-id 36951113824`, 새 출력 디렉터리):

- **exit 2**, `runPurpose: s11-ac11-composite-long-soak-physical-preflight`
- `verdict: BLOCKED_EXTERNAL`, `blocker: G-19`, `reason: five-node inventory is missing; no physical action was started`
- `execution: {"started": false, "physicalActions": false}`, `referenceOnly: true`, `acceptanceClaim: false`

**물리 동작을 시작하기 전에 멈춘다.** 인벤토리가 통과하면 다음 blocker(G-24)가 나오고, **blocker가 바뀌는 것이 진척**이다. 출력 경로가 이미 있으면 `error: output paths must not already exist`로 거부하는 것도 실행해서 확인했다(처음 호출이 그렇게 멈췄다).

**그래서 hosted workflow를 만들지 않았다.** 만들면 증거를 만들 수 없는 lane이 하나 늘 뿐이고, 축의 `criteria`를 hosted가 만족할 수 있는 수준으로 낮추는 것은 **이 축의 측정이 아니다**.

## 3. 남긴 것

| 산출물 | 내용 |
|---|---|
| `docs/vault/40_Operations/AC-11_long-soak_사내망_실행_절차.md` | §0 hosted 불가 근거(위 표), §1 사람이 갖출 전제(물리 5노드·인벤토리·G-24·외부 관측자·24시간 창), §2 실행(preflight → 창 → 두 reference → import → 집계), §2-0 smoke, §3 확인할 관측(**registry criteria에서 옮긴** 창 길이·고장 주입·복구 한도·누수·정합·등록 case 14개·WS·시계·telemetry·두 reference), §4 **이미 있는 물리 importer 계약의 요구 표와 측정한 생산자 공백**(§7-1에서 정정), §5 하지 않는 것 |
| `docs/ac11-axis-sources.json` | long-soak 행의 `reason`을 측정한 사유로 교체(`chain: incomplete`·`workflow: null` 유지) |
| `tests/core/test_assemble_ac11_manifest.py` | 래칫 시험 **3건**(§7-3) — registry에서 읽은 정본 값, 행의 `incomplete`·`workflow: null`과 사유, `readiness()`를 실제로 호출하는 물리 import 경로 |

**절차의 셸 블록 다섯 개는 전부 `bash -n` 통과**한다(§2-0 smoke 포함, §7-2). §0 블록은 `<RUN_ID>` 같은 placeholder가 아니라 **내가 실제로 실행한 명령**이다(placeholder는 `bash -n`에서 리다이렉션으로 읽혀 깨졌고, 그래서 지웠다).

## 4. importer — **[§7-1에서 전면 정정됨]**

처음 판의 이 절은 "물리 report 분기가 없다"고 적었고 **그것이 틀렸다**. `import_report()`의 dry-run 분기(`_import_reference_only_dry_run`) 한 곳만 읽고 함수 전체를 읽지 않은 것이 원인이다. 정확한 측정은 §7-1에 있다 — 요약하면: **물리 분기가 있고, exact 22-key v1 report를 받아 48개 metric을 registry criteria와 대조해 `MEASURED_PASS`/`MEASURED_FAIL` 봉투를 만들며, 그 봉투가 집계기에서 `MEASURED_PASS`가 되는 것을 기존 시험이 고정한다.**

실제 공백은 **생산자**다: `--mode physical`은 항상 blocked preflight report를 쓰고 exit 2다(§2에서 실행한 그 결과).

## 5. 검증

| 항목 | 결과 |
|---|---|
| `tests/core/test_assemble_ac11_manifest.py` | 63 → **66 passed**(§7-3에서 3건으로 강화) |
| 절차의 셸 블록 | **5개** 전부 `bash -n` exit 0, §2-0은 실제 실행 |
| 생산자 실행 | `--mode physical` exit 2, `BLOCKED_EXTERNAL`/`G-19`(§2) |
| `check_docs.py` | exit 0(1091 문서) |
| `check_doc_path_citations.py --ratchet` · `git diff --check` | exit 0 |

**미측정**: 물리 창 자체(전제가 외부), 24시간 실부하, 고장 주입, 집계기에서 이 축의 `MEASURED_PASS`. hosted workflow는 **의도적으로 만들지 않았다**.

## 6. 다음 첫 행동

1. **Codex(S11 producer owner)**: 절차 §4의 표 — **importer가 이미 요구하는 22-key final report**를 생산자가 채우는 분기. 계약은 정해져 있고, 그 분기는 24시간 창을 실제로 돌리는 것과 같은 작업이다.
2. **사용자**: 물리 5노드(node4 공급 + node5 CP 겸임)와 5노드 인벤토리 — `#300` 체크리스트 §7의 `U-A`. 그것이 오면 생산자의 blocker가 `G-19`에서 `G-24`로 바뀌는 것을 절차 §2-1로 확인한다.
3. **외부**: G-24 fault-control adapter와 외부 monotonic 관측자. 이 저장소에 없다.
4. **Claude**: 이 PR의 검토 반영.

## 7. #315 r1 — Codex 수정 요청 3건 (head `020f5dc6`)

### 7-1 F-R1 — "물리 importer 분기가 없다"는 내 측정이 틀렸다

**지적이 맞다.** `tools/import_ac11_composite_long_soak.py`의 `import_report()`를 **전체를 읽고** 다시 측정했다:

| 측정 | 결과 |
|---|---|
| dry-run | `runPurpose == s11-ac11-composite-long-soak-dry-run`일 때만 `_import_reference_only_dry_run()`으로 간다 — 내가 읽은 `:242`는 **그 helper 안**이었다 |
| 물리 | 그 밖에는 `readiness()`로 `operatorResources`가 `{G-19, G-24}`를 **둘 다** 담는지 확인한 뒤, **exact 22-key v1 report**를 요구한다 |
| 검증 | `runPurpose == s11-ac11-composite-long-soak`, clean tree(`checkoutTreeSha == git tree`), **창 >= 24시간**, registry `requiredEnvironment` 9개 값 + 비어 있지 않은 `comparableGroup`, exact 14 case·fault class(canonical sha까지), external observer receipt, storage/hosted child reference 두 개, **metrics가 registry criteria와 exact set(48)** |
| 판정 | criteria를 operator로 평가해 `MEASURED_PASS`/`MEASURED_FAIL` 봉투 + `targetRef`(registry criteria 그대로) + `observations` |
| 집계기까지 | `tests/test_import_ac11_composite_long_soak.py::test_valid_physical_report_is_accepted_by_the_ac11_aggregator`가 물리 report → 봉투 → `evaluate_axis()` → **`MEASURED_PASS`**를 고정한다. 이 경로는 **base `7183aaff`에도 이미 있었다** |

**어쩌다 틀렸나**: `grep`으로 `runPurpose`를 찾아 **첫 일치 지점**(dry-run helper 내부)을 읽고 그것을 함수의 입구로 착각했다. 함수의 입구는 `import_report()`이고 거기서 dry-run은 **분기 하나**다. 파일을 위에서 아래로 읽지 않은 것이 원인이고, 같은 commit의 래칫 시험 주석이 `The importer is ready; what is missing is the run.`이라고 적어 **내 문서와 내 시험이 서로 모순됐다** — 그 모순이 보였어야 했다.

**정정한 곳**: 절차 §2-4(실제 importer 동작 표), 절차 §4(계약 질문 → **이미 있는 계약의 요구 표** + 측정한 생산자 공백), `axis-sources` 사유, History §0·§4, PR 본문.

**실제 공백을 다시 측정했다** — `run_ac11_composite_long_soak.py`의 `--mode physical`은 세 갈래 모두 `blocked_physical_report`를 쓰고 exit 2다: 인벤토리 없음 → `G-19`, 인벤토리 preflight 실패 → `G-19`, 인벤토리 통과 → `G-24`. **22-key final report를 쓰는 분기가 생산자에 없다.** 그래서 producer owner가 할 일은 **새 계약을 정하는 것이 아니라 importer가 이미 요구하는 표를 채우는 것**이고, 절차 §4가 그 표를 인용한다.

### 7-2 F-R2 — `cd` 두 곳이 이 checkout의 repo root가 아니었다

**확인했다**: `/d/Project/SaintVisionI-Invion`에는 `tools/`가 없다(`test -f tools/run_ac11_composite_long_soak.py` → ABSENT). 정본 checkout은 그 아래다.

- §2-1·§2-4를 `cd "$(git rev-parse --show-toplevel)"` + `test -f`로 통일했다(§0·§2-3과 같은 방식).
- **smoke 블록(§2-0)을 새로 넣고 실행했다**: cwd 확인 → interpreter 확인 → 두 도구 `--help`. 결과는 `smoke ok: … with python 3.14.7`.
- **그 과정에서 전제 하나를 더 측정했다**: 이 PC 기본 `python`은 **3.10.11**이고 생산자는 `enum.StrEnum`을 쓰므로 `--help`조차 `ImportError: cannot import name 'StrEnum' from 'enum'`으로 멈춘다. smoke 블록의 version assert가 **그보다 먼저** 멈춘다. importer는 3.10에서도 `--help`가 돈다. 절차 §1에 전제로 적었다(Codex가 `tests/test_run_ac11_composite_long_soak.py`를 집계하지 못한 것도 같은 원인이다).

### 7-3 F-R3 — 래칫이 축 완화를 막지 못했다

문자열 네 조각과 `EMITTED_AXES`만 보던 시험을 **registry를 읽는 구조적 시험**으로 바꿨다:

| 시험 | 무엇을 읽는가 |
|---|---|
| `test_the_registered_long_soak_target_is_not_lowered_to_fit_a_hosted_runner` | canonical registry에서 target을 찾아 **criteria 48개**, `windowSeconds >= 86400`, 14 case 두 지표, observer coverage, 전원·switch·WAN 고장 수와 복구 한도, 열 두 지표, **`requiredEnvironment` 10개 값 전체**를 exact 비교 |
| `test_the_long_soak_row_stays_incomplete_and_says_why` | `axis-sources` 행이 `incomplete`·`workflow: null`이고 사유가 네 근거를 담는지 |
| `test_the_physical_import_path_exists_and_both_operator_resources_are_required` | `readiness()`를 **실제로 호출**해 자원 0개 → `BLOCKED_EXTERNAL`/`G-19,G-24`, `{G-19}` → `G-24`, 둘 다 → `NOT_OBSERVED(physical run not supplied)`, 그리고 `TARGET_ID`·`REQUIRED_RESOURCES`·`DRY_RUN_PURPOSE`·`EMITTED_AXES` |

**완화 변이 10건 전부 사살**:

| 변이 | 죽은 시험 |
|---|---|
| 24시간 창 → 1시간 | not-lowered |
| criterion 하나 삭제(48 → 47) | not-lowered |
| topology → `hosted` | not-lowered |
| observer → synthetic | not-lowered |
| faultInjection → no-op | not-lowered |
| eligible 노드 4 → 1 | not-lowered |
| 전원 고장 2건 → 0건 | not-lowered |
| 행이 `chain: complete` 주장 | row-stays-incomplete |
| 행이 hosted workflow 지정 | row-stays-incomplete |
| importer가 G-24 요구를 버림 | physical-import-path |

**원본 복원 확인.** 래칫 주석의 `The importer is ready; what is missing is the run.`은 **이제 사실과 맞는다**(§7-1) — 그래서 지우지 않고 시험을 그 문장에 맞게 강화했다.

### 7-4 검증

| 항목 | 결과 |
|---|---|
| `tests/core/test_assemble_ac11_manifest.py` | 64 → **66 passed** |
| `tests/test_import_ac11_composite_long_soak.py` + `tests/test_run_ac11_composite_long_soak.py` | **54 passed**(venv Python 3.14; 기본 3.10에서는 생산자 쪽이 import되지 않는다 — §7-2) |
| 완화 변이 | **10/10 KILLED** |
| 절차의 셸 블록 | **5개**(smoke 추가) 전부 `bash -n` exit 0, §2-0은 실제로 실행 |
| `check_docs.py` · `check_doc_path_citations.py --ratchet` · `git diff --check` | exit 0 |
