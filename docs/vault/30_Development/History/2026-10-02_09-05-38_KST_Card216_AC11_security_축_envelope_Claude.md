---
doc_id: "HISTORY-CARD216-AC11-SECURITY-ENVELOPE-20261002"
title: "카드 216 — security 축 envelope: importer가 집계기에 들어가는 envelope을 내게 했다. 축은 아직 통과하지 않고, 막는 것이 더 좁아졌다"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T10:31:52+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "097da87d"
task_ids: ["S11-BE"]
tags: ["ac11", "security", "axis-envelope", "importer", "s11", "claude"]
---

# 카드 216 — security 축이 집계기에 닿았다

## 0. 한 줄

`#299`가 security 축을 `incomplete`로 둔 이유는 **"importer가 axis envelope을 내지 않는다"** 였다. 그 adapter를 썼고, **실제 run artifact로 측정했다** — 집계기가 이 축을 **처음으로 평가한다**. 통과하지는 않는다. 막는 것이 **두 개로 좁아졌고 둘 다 이름이 있다.**

## 1. 무엇을 바꿨나

`tools/import_ac11_security_scan.py`가 producer의 report를 그대로 돌려주는 대신 **axis envelope으로 적응(adapt)** 한다. `#302`의 accessibility importer를 그대로 따랐다 — `EMITTED_AXES` 선언, `runPurpose: "ac11-axis-evidence"`, 검토된 target registry pin, 이미 측정해 둔 artifact digest 결속.

| 항목 | 값 |
|---|---|
| `EMITTED_AXES` | `("security-critical-high-zero",)` — 전에는 `()` 였고 그 비어 있음이 `#299` r1의 발견이었다. **두 번 선언**이 되어 내 strict 검사가 먼저 잡았다(`declares EMITTED_AXES 2 times`); 낡은 쪽을 지웠다 |
| envelope | `runPurpose`·`axis`·`verdict`·`sourceRunId`·`sourceHeadSha`·`checkoutTreeSha`·`artifactSha256`·`artifactObservedSha256`·`artifactAvailable`·`artifactExpiresAt`·`cleanCheckout`·`runConclusion`·`startedAt`·`finishedAt`·`environment`·`targetRef`·`observations`·`cleanup`·`scanArtifact` |
| `targetRef` | `s11-security-critical-high-zero-v0`, registry commit `0ee9542a`·blob `eeb43dc2`(집계기가 pin하는 검토된 blob과 동일) |
| threat report | producer의 report가 **그 자체로 `SEC-SCAN-001` threat report**다(`threatId`를 최상위에 들고 있다). 합성하지 않고 **그 한 건을 한 건으로** 싣는다 |

**verdict를 adapter가 정하는 이유**: 집계기는 이 축에 **네 개의 threat report**(`SEC-DEF-001`·`SEC-RLS-001`·`SEC-VF-001`·`SEC-SCAN-001`)를 요구하고, 하나라도 없으면 `NOT_OBSERVED`로 재계산한다. 그리고 envelope의 verdict가 재계산값과 다르면 **`INVALID_RUN`**(`producer verdict contradicts recomputed evidence`)이다. 그래서 세 개가 없을 때 adapter가 **`NOT_OBSERVED`를 선언하고 없는 것을 이름으로 적는다** — 부분 스캔이 pass로 읽히는 길을 닫는 것이 이 한 줄이다. 넷이 다 오면 producer의 verdict를 통과시킨다.

**없는 셋은 측정했다**: `SEC-DEF-001`·`SEC-RLS-001`·`SEC-VF-001`을 쓰는 곳은 저장소 전체에서 **집계기의 기대 목록뿐**이고 producer가 **0건**이다(`grep -rl --include=*.py tools/ services/`).

## 2. 실측 — 실제 run artifact로 돌렸다

| 단계 | 결과 |
|---|---|
| 입력 run | **`36943527856`**(`ac11-security-scan.yml`, `workflow_dispatch`, head **`097da87d`** = 이 카드의 base, conclusion success) |
| artifact | **`11200951947`** `s11-ac11-security-097da87d76f7bb95f27666c03a3ed5c9fbc9895c`, `expired: false` |
| importer | **exit 0**. `runPurpose: ac11-axis-evidence`, `axis: security-critical-high-zero`, `verdict: NOT_OBSERVED`, `reason: "no producer emits SEC-DEF-001, SEC-RLS-001, SEC-VF-001"`, `artifactSha256 == artifactObservedSha256 == e97dc51b…`, `artifactExpiresAt 2026-10-31T23:58:54Z` |
| 조립기 | **`assembledAxes: ["security-critical-high-zero"]`** — 이 축이 manifest에 들어간 **첫 기록**이다(나머지 일곱은 absent) |
| 집계기 | **축을 평가한다.** 결과는 `INVALID_RUN`이고 사유는 **`environment.comparableGroup is required`** 한 줄 |

**그 마지막 한 줄이 이 카드가 남긴 것이다.** producer의 `environment`는 `runnerImage`·`topology`·`evidenceClass`·`credentialsRequired`·`externalServicesRequired`를 쓰고 **`comparableGroup`을 쓰지 않는다**(실제 artifact에서 읽었다). 집계기는 모든 축 envelope에 그것을 요구한다(`aggregate_ac11_evidence.py:334`).

**[§7-1에서 정정 — 이 단락의 결론은 틀렸다.]** **adapter가 그 값을 만들지 않았다.** 두 run이 비교 가능한지는 **어떻게 생산됐는지의 성질**이고 adapter가 정할 것이 아니다 — 지어내면 서로 다른 조건의 두 run을 adapter가 "비교 가능"으로 선언하게 된다. accessibility 쪽은 producer/importer가 `ac11-accessibility-user-device-v1`을 들고 있다. **security producer(`tools/run_ac11_security_scan.py`)가 자기 comparability group 이름을 정해 쓰는 것이 맞고, 그것이 다음 조치다.**

## 3. manifest

`docs/ac11-axis-sources.json`의 security 행: `chain: incomplete → complete`, `importerEmitsAxes: [] → ["security-critical-high-zero"]`, `envelopeShape: "not-an-axis-envelope" → "axis-evidence"`, `reason: null`. **`complete`는 chain에 대한 것이고 verdict에 대한 것이 아니다** — 그 구분을 파일의 `note`에 적었고, 위 집계기 사유도 함께 적었다.

`#299`의 strict 검사가 전부 그대로 적용된다 — `importerEmitsAxes`는 importer 소스의 `EMITTED_AXES`와 **exact set**으로 비교되고(ast), `complete` 행은 admissible `envelopeShape`을 요구한다.

## 4. 검증

| 항목 | 결과 |
|---|---|
| `tests/test_import_ac11_security_scan.py` | 9 → **12 passed**(신설 3: envelope 적합성과 `NOT_OBSERVED` 사유, 네 report가 다 오면 producer verdict 통과, 등록되지 않은 threat id 거부) |
| `tests/core/test_assemble_ac11_manifest.py` | **통과** — `emitted_axes`가 security에서 한 축을 읽는 것과 배포된 map의 complete 집합이 **넷**이라는 것으로 갱신 |
| `tests/test_aggregate_ac11_evidence.py` · `tests/test_ac11_security_scan.py` · `tests/core/test_post_landing_verify.py` | 무변경 통과(역래칫 포함) |
| 합산 | 위 다섯 suite **271 passed** |
| `check_docs.py` · `git diff --check` | exit 0 |

**fixture 하나를 고쳤다**: `tests/test_import_ac11_security_scan.py`의 producer report stub이 provenance 필드까지만 들고 있어서 adapter가 threat report를 찾지 못했다. 실제 producer가 쓰는 것(`threatId`·`runPurpose`·`verdict`·`startedAt`·`finishedAt`·`environment`·counts)으로 채웠다 — stub이 실제보다 가난했던 것이고, adapter는 **찾지 못하면 거부**한다.

## 5. 측정하지 못한 것

- **`MEASURED_PASS`를 보지 못했다.** 네 threat report 중 셋에 producer가 없으므로 이 축의 pass는 이 카드의 범위가 아니다.
- **`comparableGroup`을 고치지 않았다.** producer의 환경 서술이고 그 이름은 소유자가 정한다(§2).
- **집계기 8축 전체를 통과시키지 못했다.** 나머지 일곱 축의 상태는 `#299`의 축 manifest가 적는 그대로다.
- **AC-11 축 정의를 손대지 않았다.** `REQUIRED_AXES`·`REQUIRED_TARGET_BY_AXIS`·네 threat ID 집합 모두 그대로다.
- **hosted CI에서 이 변경으로 lane을 다시 돌리지 않았다.** 위 측정은 **이 PC에서 실제 artifact로** 한 것이고, lane 재실행은 PR의 CI가 답한다.

## 6. 다음 첫 행동 (초기 판정 — §7-7에서 갱신)

1. **Codex(S11 producer owner)**: `tools/run_ac11_security_scan.py`의 `environment`에 `comparableGroup`을 추가할지와 그 이름. 그 한 값이 들어오면 이 축은 집계기에서 **`NOT_OBSERVED`로 평가**되고(현재는 `INVALID_RUN`), 축이 "평가되지 않음"에서 "관측되지 않음"으로 바뀐다.
2. **Codex**: 남은 세 threat report(`SEC-DEF-001`·`SEC-RLS-001`·`SEC-VF-001`)에 producer를 둘지 — 그것이 이 축의 pass 조건이고 별도 카드다.
3. **Claude**: 이 PR의 검토 반영.

## 7. #313 r1 — Codex 변경 요청 3건 (head `626cbc5c`)

### 7-0 한 줄

세 건 전부 같은 뿌리였다 — **"들어갔다"와 "수용됐다"를 구분하지 않은 것**. 집계기는 이 축을 평가하기 **전에** 공통 봉투 단계에서 거부하고 있었고, 그 상태를 `complete`로 적었다. 이제 **실제 artifact로 `NOT_OBSERVED`까지 간다**.

### 7-1 F-R1 — comparability group: adapter가 정하지 않는다던 판단이 틀렸다

**재현**: 실제 producer 모양(실제 artifact에서 읽은 다섯 환경 키, `payload` 안의 count)으로 봉투를 만들어 `evaluate_axis()`에 넣었다 — `importer verdict = NOT_OBSERVED`, **`aggregator verdict = INVALID_RUN`**, 사유 `environment.comparableGroup is required` 한 줄. Codex probe와 같은 결과이고, 그것을 시험으로 고정했다(`test_the_envelope_this_adapter_writes_is_admissible_to_the_aggregator`, 실제 repository git).

**§2의 판단이 틀렸다**: "adapter가 comparability group을 지어내면 안 된다"고 썼지만 **tree의 다른 두 importer가 이미 그렇게 한다** — `tools/import_ac11_accessibility_evidence.py`가 `ac11-accessibility-user-device-v1`을, `tools/import_ac11_migration_rehearsal.py`가 `hosted-ubuntu-postgres16-migration-rehearsal`을 **importer 상수로** 선언한다. 읽고 확인했고, 그 전례를 따랐다.

**다만 이름만 붙이지 않는다**: 등록된 target의 `requiredEnvironment`(`topology: hosted`, `evidenceClass: security-tools-v0`)를 **먼저 확인하고** 거기에 맞는 report에만 붙인다. 맞지 않으면 **라벨을 바꿔 붙이지 않고 거부**한다(`test_an_environment_outside_the_registered_lane_is_refused_not_relabelled`). group 이름은 **소속을 확인한 집합의 이름**이고, 그 확인이 없으면 비교 가능성은 주장이 된다. producer가 다른 group을 쓰고 있으면 덮어쓰지 않고 거부한다.

### 7-2 F-R2 — 실측 없는 PASS: importer는 재계산할 수 없는 것에 답하지 않는다

r1은 `{"threatId": ...}` 네 개와 최상위 `MEASURED_PASS`를 그대로 통과시켰다. 두 가지를 바꿨다.

| 바뀐 것 | 내용 |
|---|---|
| 재계산할 수 없는 report | `RECOMPUTABLE_THREAT_IDS = (SEC-SCAN-001,)`. DEF/RLS/VF row가 오면 **판정을 추측하지 않고 거부**한다 — 그 판정은 네 producer의 결과를 실제 결합하는 경로의 것이고, 이 importer는 artifact 한 개를 받는다 |
| scan report | `payloadSha256`로 payload를 결속한 뒤 **직접 재계산**: `criticalCount`·`highCount`, 네 개의 finding inventory(`unallowlisted`·`expired`·`staleAllowlist`·`severityMismatch`), 두 scanner의 실행(`scannerExitCodes` 정확히 둘, 0/1), scanner version·scan input 존재 |

**producer의 주장과 자기 payload가 다르면 거부한다** — `criticalCount: 1`인데 `MEASURED_PASS`라고 적힌 report는 들어오지 못한다. **측정된 실패는 숨지 않는다**: 세 report가 없으면 집계기는 그 뒤를 보지 못하므로(그래서 봉투 verdict는 `NOT_OBSERVED`여야 한다) `scanRecomputed`와 reason에 **그 수치를 적는다**(`criticalCount=2, highCount=1`). scanner가 둘 다 돌지 않았으면 그 역시 pass가 아니다.

### 7-3 F-R3 — artifact가 새 importer에 결속되지 않았다: pin이 tree와 달라져 있었다

producer의 `toolFiles`는 **검토된 allowlist의 세 pin을 그대로 복사**한다(`tools/run_ac11_security_scan.py:477`). 그 pin을 tree와 대조했다:

| 파일 | allowlist pin (r1) | 실제 tree | 옮긴 commit |
|---|---|---|---|
| producer | `87d142e0` | `87d142e0` ✓ | — |
| workflow | `84dea5d4` | `b1b37265` | **`0f614152`**(#262 r3, 2026-10-01) |
| importer | `86617533` | `095af3d8` | **`8933b6bd`**(#299 r3, 내 commit) 이후 카드 216 |

집계기는 모든 report의 `toolFiles` blob을 source tree와 대조하지만 **네 threat report가 다 있을 때만** 거기까지 간다. 그래서 이 drift는 **세 producer가 오는 순간 `INVALID_RUN`이 될 잠복 결함**이었고 아무도 보지 못했다. 셋을 했다:

1. **pin을 실측값으로 회전**하고 allowlist `verifiedAt`을 갱신, 집계기의 `SCAN_ALLOWLIST_BLOB`을 새 allowlist blob(`74cb88b3`)으로 회전.
2. **importer가 자기 실행 blob을 직접 확인**한다 — 자기 bytes로 git blob을 계산해 report가 pin한 importer blob과 다르면 **봉투를 쓰지 않고 거부**한다. 집계기가 나중에 할 검사를 import 시점에 fail-closed로 당긴 것이다.
3. **집계기가 봉투의 `importerFile`을 확인**한다(`path`는 상수 pin, `blob`은 source tree와 대조). **누락된 report 때문에 `NOT_OBSERVED`로 빠지기 전에** 검사하므로, 지금(한 report)도 실제로 강제된다.
4. **래칫 시험**: allowlist의 세 pin이 이 checkout의 파일과 같은지, 그리고 집계기의 allowlist pin이 그 파일과 같은지. `0f614152`가 지나간 자리를 다음에는 시험이 잡는다.

### 7-4 실측 — exact head에서 lane을 다시 돌렸다

| 단계 | 결과 |
|---|---|
| dispatch | **run `36949022989`**(`ac11-security-scan.yml`, `workflow_dispatch`, head **`626cbc5c`** = 이 PR head, conclusion **success**) |
| artifact | **`11203590183`** `s11-ac11-security-626cbc5c…`, `expired: false`, API digest `bf8b3dcc…` = 내려받은 bytes의 sha256 |
| report의 pin | `b1b37265`(workflow)·`b89c9206`(importer)·`74cb88b3`(allowlist) — **회전된 값이 실제 artifact에 들어왔다** |
| importer | **exit 0**, `verdict NOT_OBSERVED`, `reason "no producer emits SEC-DEF-001, SEC-RLS-001, SEC-VF-001"`, `scanRecomputed MEASURED_PASS`, `importerFile {tools/import_ac11_security_scan.py, b89c9206…}`, `comparableGroup ac11-security-dependency-sast-hosted-v1` |
| 조립기 | `assembledAxes: ["security-critical-high-zero"]`, 나머지 일곱 absent |
| 집계기 | **축 verdict `NOT_OBSERVED`** (r1: `INVALID_RUN`). run 수준 `INVALID_RUN`은 **`missing required axes` 일곱 줄뿐** — 설계된 fail-closed다 |

**그래서 `chain: complete`가 측정으로 뒷받침된다** — 이 파일이 말하는 complete는 "admissible envelope이 있다"이고, 이제 집계기가 **이 축을 평가한다**.

### 7-5 변이 사살 — 8/8

| 변이 | 죽은 시험 |
|---|---|
| adapter가 group 선언을 멈춤 | `test_the_envelope_this_adapter_writes_is_admissible_to_the_aggregator` |
| lane 요구 확인 없이 라벨 | `test_an_environment_outside_the_registered_lane_is_refused_not_relabelled` |
| 재계산 못 하는 report를 다시 통과 | `test_four_threat_rows_this_importer_cannot_recompute_cannot_become_a_pass` |
| producer 주장과 payload 대조 제거 | `test_a_scan_verdict_that_contradicts_its_own_payload_is_refused` |
| 측정된 실패를 reason에서 지움 | `test_a_measured_failure_is_carried_with_the_recomputed_detail_rather_than_hidden` |
| importer가 자기 blob 확인 안 함 | `test_an_artifact_pinned_to_a_different_importer_blob_is_refused` |
| 집계기가 `importerFile` 요구 안 함 | `test_security_envelope_must_name_an_importer_the_source_tree_contains` |
| workflow pin을 낡은 값으로 되돌림 | `test_the_scan_allowlist_pins_the_files_this_checkout_actually_has` |

**8건 모두 KILLED, 원본 복원 확인.**

### 7-6 검증

| 항목 | 결과 |
|---|---|
| `tests/test_import_ac11_security_scan.py` | 12 → **27 passed** |
| `tests/test_aggregate_ac11_evidence.py` | 85 → **86 passed** |
| `tests/test_ac11_security_scan.py` · `tests/core/test_assemble_ac11_manifest.py` · `tests/core/test_post_landing_verify.py` | **174 passed**(무변경, 역래칫 포함) |
| 합산 | **287 passed** |
| `git diff --check` | exit 0 |

**fixture를 실제 producer 모양으로 바꿨다**: r1 stub은 환경에 `comparableGroup`을 들고 있었고(실제 producer는 쓰지 않는다) count를 최상위에 두었다(실제는 `payload` 안). **stub이 실제보다 풍부했던 것**이 집계기가 거부하는 importer와 시험이 합의한 이유다 — 카드 216의 §4에서 한 번 고친 것과 같은 종류이고, 이번에는 세 군데였다.

### 7-7 남은 것 / 측정하지 못한 것

- **`MEASURED_PASS`는 여전히 이 카드의 범위가 아니다.** 세 threat report에 producer가 없고, importer는 이제 **그 셋에 대해 답하지 않는다**(추측하지 않는 것이 7-2의 내용이다).
- **네 report가 다 오는 경로**는 그 producer들을 두는 카드의 것이고, 그때 `RECOMPUTABLE_THREAT_IDS`를 그 재계산과 함께 넓히는 것이 올바른 순서다.
- **producer는 자기 pin을 검증하지 않는다** — allowlist의 세 pin을 복사하면서 tree와 같은지 확인하지 않는다. 그래서 `0f614152` 이후의 run들이 tree에 없는 blob을 pin으로 담은 report를 냈다 — 카드 216이 쓴 run `36943527856`이 그중 하나다. producer owner에게 남기는 관찰이고, 이 PR은 importer·집계기·래칫에서 fail-closed로 막았다.
- **AC-11 축 정의는 그대로다.** `REQUIRED_AXES`·`REQUIRED_TARGET_BY_AXIS`·네 threat ID 집합 어느 것도 바꾸지 않았다. 추가한 것은 **더 엄격한 결속**뿐이다.

## 8. #313 r2 — N1: 재계산기를 두 개 두지 않는다 (코드 `3ae6b316`)

r1에서 F-R1·F-R3는 해소됐고, F-R2가 부분 해소로 남았다. 지적은 정확했다 — §7-2가 "직접
재계산"이라고 쓴 것이 **count 두 개와 inventory 네 개의 길이**뿐이었다.

### 8-1 재현 — 실제 artifact bytes로

run `36951113824`의 실제 report payload를 변형하고 `payloadSha256`을 다시 계산해(위조자가
해야 하는 일을 그대로) importer에 넣었다:

| probe | 변형 | r1 importer | 지금 |
|---|---|---|---|
| 0 | 없음 | `MEASURED_PASS` | `MEASURED_PASS` |
| 1 | HIGH finding row 한 줄 추가, `criticalCount`·`highCount`는 0 유지 | **`MEASURED_PASS`** | **거부** — `counts, summary-finding-counts` |
| 2 | `scannedPythonFiles: []`, bandit `scannedFileCount: 0`, `auditedDependencies: []`, pip-audit `dependencyCount: 0`, 두 exit 0 | **`MEASURED_PASS`** | **거부** — `audited-dependencies, scanned-python-files` |

### 8-2 조치 — 같은 주장을 검사하는 함수를 하나로

`aggregate_ac11_evidence.py`의 payload 산술을 **`scan_payload_invariants()`** 로 뽑고,
`evaluate_security_scan()`과 importer가 **그 한 함수를 읽는다**. 검증기가 둘이면 갈라지고,
갈라진 결과가 이 결함이었다.

그 함수가 묶는 것:

| 묶는 것 | 내용 |
|---|---|
| finding row | exact key 여섯 개, `findingId` 고유·정렬, severity ∈ {CRITICAL, HIGH}, pip-audit은 HIGH만 |
| count | row에서 센 CRITICAL·HIGH 수 == `criticalCount`·`highCount` |
| summary | `bandit.highFindingCount` == bandit row 수, `pip-audit.findingCount` == pip-audit row 수 |
| exit code | summary에서 **파생**된다 — pip-audit은 findingCount>0이면 1, bandit은 low+medium+high>0이면 1 |
| coverage | bandit이 읽은 **파일 목록**(정렬·고유·`.py`, **비면 거부**) == `scannedFileCount`, pip-audit이 audit한 **dependency 목록**(정렬·고유, **비면 거부**) == `dependencyCount` |
| inventory | 네 목록의 모양(정렬·고유·문자열) |

allowlist 비교와 Git provenance(`scanInputs` object id, requirements pin, `git ls-tree`와의
파일 목록 대조)는 **집계기만 물을 수 있으므로 집계기에 남는다**. importer는 모순된 payload를
`NOT_OBSERVED`로 넘기지 않고 **거부**한다 — "관측되지 않음"은 producer의 unavailable 경로가
말하는 것이고, 완결됐다고 적힌 report가 자기와 어긋나면 읽을 수 없는 증거다.

### 8-3 실측 — 다시 exact head에서

| 단계 | 결과 |
|---|---|
| dispatch | **run `36951113824`**, head **`3ae6b316`**, `workflow_dispatch`, success |
| artifact | **`11203836829`** `s11-ac11-security-3ae6b316…`, 미만료, API digest `6892dc8a…` = 내려받은 bytes |
| artifact의 pin | importer `1d358cf9`(= 실행 blob), workflow `b1b37265`, allowlist `67e80df8`(= 집계기 상수) |
| 실제 payload | `scannedPythonFiles` **207개 목록**, `auditedDependencies` **41개**, critical 0 / high 0, bandit low 16·medium 4 → exit 1, pip-audit findingCount 0 → exit 0 |
| importer | exit 0, `NOT_OBSERVED`, `scanRecomputed MEASURED_PASS` |
| 조립기 → 집계기 | `assembledAxes: ["security-critical-high-zero"]`, **축 `NOT_OBSERVED`**, run 수준은 `missing required axes` 일곱 줄뿐 |

### 8-4 변이 사살 — 7/7

| 변이 | 죽은 시험 |
|---|---|
| importer가 모순된 payload를 무시 | `test_a_finding_row_the_counts_do_not_admit_is_refused` |
| count를 row에서 재계산하지 않음 | 같은 시험 |
| bandit이 읽은 파일 0을 허용 | `test_a_scan_that_read_nothing_is_not_a_pass[bandit-read-no-files]` |
| pip-audit이 audit한 dependency 0을 허용 | `test_a_scan_that_read_nothing_is_not_a_pass[pip-audit-read-no-dependencies]` |
| summary가 row와 달라도 통과 | `test_a_summary_that_disagrees_with_the_finding_rows_is_refused` |
| exit code를 summary에서 파생하지 않음 | `test_a_scanner_exit_code_that_contradicts_its_summary_is_refused` |
| 집계기가 공유 재계산을 읽지 않음 | `test_security_scan_registered_shape_guards_are_mutation_sensitive`(집계기 자신의 변이 시험) |

**빈 coverage는 scanner별 단독 변이로 각각 사살한다** — 처음엔 두 scanner를 함께 비우는
probe 하나만 두었더니 **각 검사를 하나씩 지워도 시험이 살아남았다**(다른 쪽이 여전히
실패해서). 시험을 scanner별로 쪼갰다.

### 8-5 검증

| 항목 | 결과 |
|---|---|
| `tests/test_import_ac11_security_scan.py` | 27 → **33 passed** |
| `tests/test_aggregate_ac11_evidence.py` | **86 passed** — 집계기 리팩터가 의미를 바꾸지 않았다는 증거다(변이 민감도 시험 포함) |
| 인접 포함 5 suite | **293 passed** |
| `check_docs.py` · `check_doc_single_source.py` · `check_doc_path_citations.py --ratchet` · `git diff --check` | exit 0 |

**fixture를 또 실제 모양으로 고쳤다**: `scannedPythonFiles`는 **수가 아니라 파일 목록**이고,
모든 summary 수치가 그 목록의 산술이다. r1 fixture는 수(120)를 넣고 있었다 — stub이 실제와
다른 세 번째 자리이고, 그래서 **실제 artifact로 재측정하는 것이 유일한 확인**이다.

### 8-6 남은 것

- **pin 회전이 두 번 일어났다**(importer 파일이 바뀔 때마다). 래칫 시험이 그것을 강제하고,
  이 PR의 마지막 head에서 lane을 다시 돌린 artifact가 그 pin을 담고 있다.
- **`MEASURED_PASS`는 여전히 범위 밖이다** — 세 threat report에 producer가 없다.
