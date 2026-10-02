---
doc_id: "HISTORY-CARD221-AC11-SECURITY-THREAT-PRODUCERS-20261002"
title: "카드 221 — security 축의 나머지 세 threat report를 배선했다. 축은 NOT_OBSERVED로 평가되고, 막는 것이 코드에서 세 개의 검토 결정으로 바뀌었다"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T12:06:03+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "7301c6a7"
task_ids: ["S11-BE"]
tags: ["ac11", "security", "threat-reports", "rls", "definer", "s11", "claude"]
---

# 카드 221 — 세 threat report의 producer

## 0. 한 줄

집계기는 네 threat report를 요구하고 producer는 하나였다. 도구는 전부 있었고 없던 것은 **그 출력을 집계기가 읽는 모양으로 기록하는 경로**다. 그 경로를 만들었고 hosted lane에서 실측했다 — **봉투가 세 report를 담는다**: `SEC-SCAN-001` **MEASURED_PASS**, `SEC-VF-001` **MEASURED_PASS**(브라우저 lane의 자기 증명에서), `SEC-RLS-001` **NOT_OBSERVED**(한 행의 identity를 확인할 수 없다). `SEC-DEF-001`은 측정은 됐지만(`matches_reviewed_policy`, 15 함수, unsafe 0) **검토 집합과 정확히 같지 않아 evaluator가 거부**한다. 축은 **`NOT_OBSERVED`로 평가**되고, **막는 것이 코드에서 세 개의 검토 결정으로 바뀌었다.**

## 1. 무엇을 만들었나

### 1-1. producer — `tools/run_ac11_security_threat_reports.py`

`INV_TEST_ADMIN_DSN`으로 **disposable migrated database**를 만들어(collector가 자기 증거를 모을 때 쓰는 그 방식) 두 도구를 돌리고 두 report를 쓴다.

| 묶는 것 | 내용 |
|---|---|
| `SEC-DEF-001` | `check_definer_functions.audit()`의 `status`·`functions`·`unsafe`와 CLI가 돌려줄 `exitCode` |
| `SEC-RLS-001` | collector의 `violations`·`accepted`·`unmeasured`·`roles`·`ground_truth`·`verdict`와 **그 CLI 자신의 exit 매핑**(`{PASS:0, VIOLATIONS:1, UNMEASURED:3}`을 읽어 쓴다) |
| `toolFiles` | 실제로 돈 파일의 git blob을 **이 checkout에서 측정**해 담는다. 집계기가 그것을 source tree와 자기 pin에 대조하므로, 움직인 도구는 조용히 수용되지 않고 거부된다 |
| `baselineAccepted` | **검토된 allowlist의 dispositions**(3건). collector의 baseline 파일은 S02-DB lane용 superset(4건)이라 그것을 쓰면 모든 report가 `INVALID_RUN`이다 |
| fail-closed | 관측하지 못하면 `status: unavailable`·`exitCode: 2`로 적는다 — 빈 통과 inventory가 되지 않는 것이 이 도구의 전부다 |

**role 모집단을 고르지 않았다.** collector의 `DEFAULT_ROLES`(8개)를 읽는다. 측정으로 확인한 것: **두 role만 보면 이 tree의 `UNMEASURED`가 `PASS`로 바뀐다** — identity를 확인할 수 없는 그 한 행이 `inv_cancel_bridge_owner`의 것이고 짧은 목록은 그 role을 묻지 않는다. **덜 물어서 얻은 판정은 이 축의 측정이 아니다**(시험으로 고정했다).

### 1-2. importer — 네 report를 담고, 판정은 집계기의 것을 쓴다

- artifact의 두 member(`s11-ac11-security-definer.json`·`s11-ac11-security-rls.json`)를 읽고, **같은 run·같은 source head·같은 tree**가 아니면 거부한다(봉투에는 run id와 artifact digest가 하나씩이다).
- `--vf-evidence`로 **브라우저 lane의 자기 증명**을 받아 `SEC-VF-001`을 만든다. 그 lane은 검토된 allowlist가 tool file로 pin하는 workflow이므로, long-soak importer의 child reference와 같은 모양으로 digest·head에 결속한다.
- **판정은 `evaluate_definer`·`evaluate_rls`·`evaluate_vf`를 직접 호출해 정한다.** 두 번째 의견을 갖지 않는 것이 `#313` r2에서 배운 것이고, 여기서는 그것이 더 중요하다 — 세 report의 규칙은 집계기 안에만 있다.
- evaluator가 `INVALID_RUN`이라 부른 report는 **이름과 함께 빼고 `reason`에 적는다**. 담으면 봉투 자신이 `INVALID_RUN`이 되고, 그러면 운영자는 **어느 report가 왜 안 되는지** 알 수 없다.
- 그래서 `#313` r2의 "재계산할 수 없는 report는 거부" 규칙이 **더 강한 것으로 대체됐다** — 이제 그 report들은 *평가되고*, 빈 row 넷은 `INVALID_RUN`으로 이름이 불려 빠지며, **pass는 여전히 불가능하다**(그 시험을 그대로 유지했다).

### 1-3. lane — postgres service와 producer step

`ac11-security-scan.yml`에 postgres service(`postgres:16`, 이 runner의 throwaway 비밀번호)와 `requirements-test.txt` 설치, producer step, 두 member의 provenance·redaction 검증을 더했다. **그 step은 lane을 실패시키지 않는다** — `NOT_OBSERVED`와 `MEASURED_FAIL`은 답이고, 기존 critical/high gate는 그대로다. 검증 step은 두 report가 **연결 재료를 담지 않는지**(`inv_test_only`·`postgresql://`·`password=`) 직접 확인한다.

## 2. 실측 — hosted lane

| 단계 | 결과 |
|---|---|
| dispatch | **run `36958341672`**, head **`688fe672`**, `workflow_dispatch`, **success** |
| artifact | **`11207061070`**, API digest == 내려받은 bytes의 sha256, member **4개**(scan json·junit·definer json·rls json) |
| `SEC-DEF-001` | `exitCode 0`, `status matches_reviewed_policy`, **15 함수**, `unsafe 0` |
| `SEC-RLS-001` | `exitCode 3`, `verdict UNMEASURED`, violations **0**, accepted **9**, unmeasured **1** — `inv_cancel_bridge_owner` / `public.audit_events` / 규칙 `E4`(`ctid` 거부 42501, `occurred_at` 읽기 불가) |
| importer (VF 증거 없이 먼저) | exit 0. 봉투가 **두 report를 담는다**(SCAN·RLS), `SEC-DEF-001`은 **`INVALID_RUN`으로 이름이 불려 빠지고**, `SEC-VF-001`은 absent |
| `SEC-VF-001` | 브라우저 lane을 같은 head에서 dispatch했다 — **run `36958633624`**, artifact `11207615096`, `exitCode 0`·`subprocessExitCode 0`·`evidenceStatus complete`·`tests {0,0,0,6}`·identity hash가 **검토된 pin과 일치**. `evaluate_vf` → **`MEASURED_PASS`** |
| 봉투 verdict | **`NOT_OBSERVED`**, reason: `no admissible report for SEC-DEF-001; refused by the canonical evaluator: SEC-DEF-001 (INVALID_RUN); SEC-RLS-001 recomputes NOT_OBSERVED`. `threatReportVerdicts`는 세 값(SCAN PASS·VF PASS·RLS NOT_OBSERVED) |
| 조립기 → 집계기 | `assembledAxes: ["security-critical-high-zero"]`, **축 `NOT_OBSERVED`**. run 수준 `INVALID_RUN`은 나머지 일곱 축 absent뿐 |

**그리고 네 번째 report가 들어오는 순간을 측정했다** — 검토 집합과 같은 definer report를 더해 `_security_observations`를 직접 불렀더니 **`INVALID_RUN`**이고, 원인은 하나뿐이다: `SEC-VF-001`의 `.github/workflows/desktop-browser.yml` pin(`0cd345aa`)이 tree(`bb5708a8`)와 다르다. 집계기는 **네 report가 다 있을 때만** 그 pin을 tree와 대조하므로(`#313` F-R3와 같은 구조), **이 drift는 잠복이고 세 번째 결정이 닫히는 순간 축을 `INVALID_RUN`으로 만든다.**

**로컬에서 같은 측정을 먼저 했고 결과가 같다**(이 PC의 disposable DB, 15 함수·unsafe 0, UNMEASURED 1행).

## 3. 막는 것 — 코드가 아니라 **세 개의 검토 결정**

| # | 무엇이 막는가 | 왜 코드가 아닌가 |
|---|---|---|
| 1 | `definerPolicySignatures`가 **12**인데 checker의 policy와 live catalogue는 **15**다. `evaluate_definer`의 exit-0 분기는 관측 집합이 검토 집합과 **정확히 같기**를 요구하므로 `SEC-DEF-001`은 `INVALID_RUN`이다. 빠진 셋: `public.model_version_measurement(text)`, `public.record_auth_denial(...)`, `public.record_kernel_run_cancel(...)` | **어느 privileged function이 검토됐는지**가 security 내용이다. `923d83c9`가 policy를 `0058` head에 맞추면서 늘었고 AC-11 allowlist는 따라가지 않았다 |
| 2 | `secVf001.workflow`가 pin한 브라우저 lane blob을 **`0f614152`가 옮겼다**(`#313` F-R3에서 dependency/SAST workflow pin을 옮긴 **같은 commit**이다). **지금은 보이지 않는다** — `evaluate_vf`는 report의 `toolFiles`를 allowlist pin과만 대조하므로 `MEASURED_PASS`이고, tree와의 대조는 집계기가 **네 report가 다 있을 때** 한다. 즉 **1번이 닫히는 순간 축이 `INVALID_RUN`이 된다**(§2에서 측정) | **기계적 회전으로 고칠 수 없다** — AC-11 target registry가 **이 allowlist 파일의 blob을 target의 `sourceDocument`로 pin**하므로(`c62cb671`의 `ff2f9966`), 파일을 고치면 registry pin이 깨지고 그것을 고치는 것은 **AC-11 정의를 움직이는 것**이다. 카드가 금지한 것이 그것이다 |
| 3 | RLS의 **확인할 수 없는 한 행**(`inv_cancel_bridge_owner` / `public.audit_events` / `E4`) | 이것은 pin이 아니라 **측정**이다. 닫는 길은 둘 — 그 role에 identity 읽기를 주거나, 그 행을 **검토된 예외**로 받아들이는 것. 둘 다 결정이다 |

**내가 회전한 pin은 하나뿐이다** — 집계기의 `RLS_FILES` baseline pin(`c96f4f60`이 2026-09-28에 파일을 옮겼다). 그것은 검토 내용이 아니라 도구 pin이고, 회전하지 않으면 `SEC-RLS-001`이 `INVALID_RUN`이라 **측정 자체가 보이지 않는다**. 그리고 dependency/SAST allowlist의 importer·workflow pin은 이 PR이 그 두 파일을 바꿨으므로 같이 회전했다(`#313`에서 세운 절차).

## 4. 래칫

| 시험 | 고정하는 것 |
|---|---|
| `test_the_definer_and_rls_tool_pins_match_the_files_this_checkout_has` | 집계기의 DEF/RLS 네 pin이 tree와 같은지. `c96f4f60`이 지나간 자리를 다음에는 시험이 잡는다 |
| `test_the_reviewed_security_allowlist_still_describes_this_tree` | **남은 두 검토 공백을 측정값으로 고정**한다 — 12 vs 15와 빠진 세 서명, 브라우저 lane pin의 불일치, 그리고 **나머지 VF pin 네 개는 일치한다는 것**. 어느 쪽이든 닫히면 **이 시험이 실패해** 숫자·사유·History를 함께 갱신하게 만든다 |
| `test_the_scan_allowlist_pins_the_files_this_checkout_actually_has` | (`#313`에서) dependency/SAST 세 pin과 집계기의 allowlist pin |

## 5. 변이 사살 — 9/9

| 변이 | 죽은 시험 |
|---|---|
| 관측 못 한 definer를 pass로 | `test_without_a_database_both_reports_are_unavailable_rather_than_passing` |
| 연결 실패를 깨끗한 inventory로 | `test_an_unreachable_database_is_also_unavailable` |
| role 모집단을 8 → 2로 | `test_the_boundary_is_measured_over_the_collector_s_own_role_population` |
| 검토된 dispositions 대신 collector baseline을 | `test_the_rls_report_states_the_reviewed_baseline_it_was_judged_against` |
| evaluator가 거부한 report를 그대로 담음 | `test_four_threat_rows_with_nothing_measured_still_cannot_become_a_pass` |
| 브라우저 증거의 검토 필드 확인 제거 | `test_browser_lane_evidence_that_is_not_the_reviewed_one_is_refused` |
| 다른 run의 database report 수용 | `test_a_database_report_from_another_run_is_refused` |
| MEASURED_FAIL이 NOT_OBSERVED에 밀림 | `test_a_failure_outranks_an_unobserved_report_in_the_same_envelope` |
| RLS baseline pin을 낡은 값으로 | `test_the_definer_and_rls_tool_pins_match_the_files_this_checkout_has` |

**9건 모두 KILLED, 원본 복원 확인.** 처음에는 여덟 번째가 **살아남았다** — fail 시험의 fixture에 `NOT_OBSERVED`가 없어 두 분기를 바꿔도 결과가 같았다. 둘이 함께 있는 경우(definer unavailable + RLS violations)를 시험으로 추가해 사살했다.

## 6. 검증

| 항목 | 결과 |
|---|---|
| `tests/test_import_ac11_security_scan.py` | 33 → **48 passed** |
| `tests/test_run_ac11_security_threat_reports.py` | **10 passed**(신설, DB 없이 도는 fail-closed 경계) |
| `tests/test_aggregate_ac11_evidence.py` · `tests/test_ac11_security_scan.py` · `tests/core/test_assemble_ac11_manifest.py` · `tests/core/test_post_landing_verify.py` | 무변경 통과 |
| lane | `yaml.safe_load` 통과, bash step **6개** 전부 `bash -n` exit 0, inline python `ast.parse` 통과 |
| 실 PG | **로컬 disposable DB와 hosted postgres service 둘 다에서 실측**(§2) |
| `check_docs.py` · `check_doc_path_citations.py --ratchet` · `git diff --check` | exit 0 |

## 7. 측정하지 못한 것 / 하지 않은 것

- **`MEASURED_PASS`를 보지 못했다.** §3의 세 결정이 열려 있다. 축은 `NOT_OBSERVED`이고 그것이 정직한 값이다.
- **AC-11 정의를 손대지 않았다.** `REQUIRED_AXES`·target registry·`s11-security-allowlist-v0.json`(= target의 `sourceDocument`) 어느 것도 바꾸지 않았다. 바꾼 것은 집계기의 **도구 pin 하나**와 dependency/SAST allowlist의 pin 둘이다.
- **축을 낮추지 않았다.** role 모집단을 줄이면 이 tree는 PASS가 되지만 그 길을 막았다(§1-1).
- **네 report가 함께 통과하는 봉투를 보지 못했다.** 세 개는 실측으로 들어왔고 네 번째(definer)는 검토 결정을 기다린다. 그리고 그 결정이 닫히면 **잠복한 VF pin drift가 축을 `INVALID_RUN`으로 만든다** — 그래서 §3의 1번과 2번은 **같이** 닫아야 하는 한 쌍이고, 그 사실이 이 카드가 측정으로 알아낸 것 중 가장 쓸모 있는 것이다.

## 8. 다음 첫 행동

1. **Codex / allowlist owner**: §3의 세 결정. 1번(세 privileged function)과 2번(브라우저 lane pin)은 **같은 파일**이고, 그 파일이 target의 `sourceDocument`이므로 **registry pin까지 함께 움직이는 변경**이다 — 그 설계를 정하는 것이 다음 카드다.
2. **Claude**: 그 결정이 오면 pin·사유·래칫 시험을 한 번에 갱신한다. 코드는 더 필요하지 않다.
3. **Codex(S02-DB owner)**: RLS의 확인 불가 행 — identity 읽기 부여 또는 검토된 예외.
