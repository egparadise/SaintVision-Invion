---
doc_id: "HISTORY-CARD217-AC11-LONG-SOAK-PATH-20261002"
title: "카드 217 — long-soak 축: hosted로는 정의를 만족할 수 없다. 축을 낮추지 않고, 사내망 절차와 막는 것의 이름을 남겼다"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T10:39:25+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "7183aaff"
task_ids: ["S11-BE"]
tags: ["ac11", "long-soak", "intranet", "runbook", "s11", "claude"]
---

# 카드 217 — long-soak 축의 경로

## 0. 한 줄

판정은 **(b)** 다. 정본이 요구하는 것은 **물리 5노드에서 24시간**이고 hosted runner의 job 한도는 6시간이며, 열·전원·switch·WAN·외부 관측자·고장 주입은 hosted VM이 **줄 수 없는 것**이다. **축을 낮춰 맞추지 않았다** — hosted workflow를 만들지 않고, 사내망 실행 절차와 `axis-sources`의 사유를 남겼다. 그리고 준비하라던 importer는 **읽어보니 물리 report 분기가 없었다**: 그 분기를 추측으로 쓰지 않고 계약 질문으로 남겼다.

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
| `docs/vault/40_Operations/AC-11_long-soak_사내망_실행_절차.md` | §0 hosted 불가 근거(위 표), §1 사람이 갖출 전제(물리 5노드·인벤토리·G-24·외부 관측자·24시간 창), §2 실행(preflight → 창 → 두 reference → import → 집계), §3 확인할 관측(**registry criteria에서 옮긴** 창 길이·고장 주입·복구 한도·누수·정합·등록 case 14개·WS·시계·telemetry·두 reference), §4 물리 importer 분기 계약 질문, §5 하지 않는 것 |
| `docs/ac11-axis-sources.json` | long-soak 행의 `reason`을 측정한 사유로 교체(`chain: incomplete`·`workflow: null` 유지) |
| `tests/core/test_assemble_ac11_manifest.py` | 래칫 시험 1건 — 이 행이 `incomplete`·`workflow: null`이고 사유에 `86400`·`physical-five-node`·`external-monotonic-v1`·`G-24`가 있어야 하며, importer의 `EMITTED_AXES`가 `{"long-soak"}`라는 것 |

**절차의 셸 블록 네 개는 전부 `bash -n` 통과**한다. §0 블록은 `<RUN_ID>` 같은 placeholder가 아니라 **내가 실제로 실행한 명령**이다(placeholder는 `bash -n`에서 리다이렉션으로 읽혀 깨졌고, 그래서 지웠다).

## 4. 정정 — "importer는 준비돼 있다"가 아니었다

카드는 (b)에서 **runbook과 importer만 준비**하라고 했다. importer를 읽고 측정한 결과:

| 측정한 것 | 결과 |
|---|---|
| `EMITTED_AXES` | `("long-soak",)` ✓, 봉투의 `axis`가 그 상수에서 나온다 |
| 받는 report | **`runPurpose`가 `s11-ac11-composite-long-soak-dry-run`이 아니면 거부**(`tools/import_ac11_composite_long_soak.py:242`) |
| dry-run 봉투 | `runPurpose: ac11-axis-evidence`, `verdict: NOT_OBSERVED`, reason `synthetic dry-run is reference-only and cannot satisfy the physical target`, `environment.comparableGroup: reference-only`, `topology: synthetic-five-node` |
| **물리 창 report 분기** | **없다** |
| CLI | `--report`·`--storage-reference`·`--hosted-reference`·`--output` 네 개가 모두 required(실제 `--help` 출력) |

**그 분기를 지금 쓰지 않았다.** 물리 report는 생산자가 BLOCKED_EXTERNAL로 멈추므로 **아직 존재하지 않는 문서**이고, 그 모양을 내가 정하면 **아무도 반증할 수 없는 추측을 코드로 고정**하는 것이다(생산자가 그 문서를 낼 수 없으므로 시험도 내 가정을 되읽을 뿐이다). 대신 절차 §4에 계약 질문 네 개를 남겼다: 물리 report의 `runPurpose`·`environment`와 comparability group 이름, 48개 criteria 값을 싣는 키(집계기 일반 `observations` 경로인지), 두 reference의 결속, **중단된 창의 판정**(`NOT_OBSERVED`인지 `MEASURED_FAIL`인지 — 정본에 그 구분이 없다).

## 5. 검증

| 항목 | 결과 |
|---|---|
| `tests/core/test_assemble_ac11_manifest.py` | 63 → **64 passed**(래칫 1건 신설) |
| 절차의 셸 블록 | 4개 전부 `bash -n` exit 0 |
| 생산자 실행 | `--mode physical` exit 2, `BLOCKED_EXTERNAL`/`G-19`(§2) |
| `check_docs.py` | exit 0(1090 문서) |
| `check_doc_path_citations.py --ratchet` · `git diff --check` | exit 0 |

**미측정**: 물리 창 자체(전제가 외부), 24시간 실부하, 고장 주입, 집계기에서 이 축의 `MEASURED_PASS`. hosted workflow는 **의도적으로 만들지 않았다**.

## 6. 다음 첫 행동

1. **Codex(S11 target/producer owner)**: 절차 §4의 계약 질문 네 개 — 그 답이 물리 importer 분기의 입력이다.
2. **사용자**: 물리 5노드(node4 공급 + node5 CP 겸임)와 5노드 인벤토리 — `#300` 체크리스트 §7의 `U-A`. 그것이 오면 생산자의 blocker가 `G-19`에서 `G-24`로 바뀌는 것을 절차 §2-1로 확인한다.
3. **외부**: G-24 fault-control adapter와 외부 monotonic 관측자. 이 저장소에 없다.
4. **Claude**: 이 PR의 검토 반영.
