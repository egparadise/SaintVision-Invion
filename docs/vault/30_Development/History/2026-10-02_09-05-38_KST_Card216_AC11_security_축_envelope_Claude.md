---
doc_id: "HISTORY-CARD216-AC11-SECURITY-ENVELOPE-20261002"
title: "카드 216 — security 축 envelope: importer가 집계기에 들어가는 envelope을 내게 했다. 축은 아직 통과하지 않고, 막는 것이 더 좁아졌다"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T09:05:38+09:00"
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

**adapter가 그 값을 만들지 않았다.** 두 run이 비교 가능한지는 **어떻게 생산됐는지의 성질**이고 adapter가 정할 것이 아니다 — 지어내면 서로 다른 조건의 두 run을 adapter가 "비교 가능"으로 선언하게 된다. accessibility 쪽은 producer/importer가 `ac11-accessibility-user-device-v1`을 들고 있다. **security producer(`tools/run_ac11_security_scan.py`)가 자기 comparability group 이름을 정해 쓰는 것이 맞고, 그것이 다음 조치다.**

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

## 6. 다음 첫 행동

1. **Codex(S11 producer owner)**: `tools/run_ac11_security_scan.py`의 `environment`에 `comparableGroup`을 추가할지와 그 이름. 그 한 값이 들어오면 이 축은 집계기에서 **`NOT_OBSERVED`로 평가**되고(현재는 `INVALID_RUN`), 축이 "평가되지 않음"에서 "관측되지 않음"으로 바뀐다.
2. **Codex**: 남은 세 threat report(`SEC-DEF-001`·`SEC-RLS-001`·`SEC-VF-001`)에 producer를 둘지 — 그것이 이 축의 pass 조건이고 별도 카드다.
3. **Claude**: 이 PR의 검토 반영.
