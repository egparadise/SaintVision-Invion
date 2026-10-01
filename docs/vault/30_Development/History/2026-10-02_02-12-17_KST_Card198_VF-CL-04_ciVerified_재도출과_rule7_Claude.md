---
doc_id: "HISTORY-CARD198-VF-CL-04-CIVERIFIED-REDERIVED-20261002"
title: "카드 198 — VF-CL-04의 ciVerified를 진술에서 재도출로: 거짓이던 이유가 #283로 사라졌고, 레지스트리는 그것을 혼자 알 수 없었다 (rule 7, 그리고 미선택 행의 차단 사유)"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T02:16:48+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "25f43a25"
task_ids: ["S12-DB", "S12-ST"]
tags: ["vf-cl", "registry", "ci", "s12", "acceptance", "claude"]
---

# 카드 198 — 다음 카드를 고르고 착수했다

## 0. 고른 방법 — 레지스트리에 물었다

카드 198의 첫 단계는 **owner Claude의 준비된 VF-CL 카드가 남았는지**다. `docs/vf-cl-task-registry.json`과 `tools/check_vf_cl_registry.py`로 확인했다.

| 카드 | 남은 칸 | 그 칸을 닫는 것은 |
|---|---|---|
| `VF-CL-01` | `operationallyAccepted: false` | **운영 인수** — 외부 전제다 |
| `VF-CL-02` | `independentlyReviewed: false` | **Codex의 검토**(reviewer가 Codex다). 내가 할 수 없다 |
| `VF-CL-03` | `independentlyReviewed: false` | 같다 |
| **`VF-CL-04`** | **`ciVerified: false`** + `independentlyReviewed: false` | **그 거짓이 더 이상 사실이 아니다**(§1). 검토는 Codex의 것이고, **ciVerified는 내 것이다** |
| `VF-CL-05` | 둘 다 `notApplicable`로 이유가 적혀 있다 | 해당 없음 |

**새로 구현할 VF-CL 카드는 남아 있지 않다** — 다섯 장 모두 `implemented: true`·`state: review`다. 남은 것은 검토·운영 인수, 그리고 **`VF-CL-04`의 ciVerified 한 칸**이고, 그 칸만 외부 전제도 남의 일도 아니다. 그래서 그것을 골랐다.

## 1. 왜 지금 닫을 수 있나 — 거짓이던 이유가 사라졌다

레지스트리의 `ciVerifiedNote`는 `false`의 이유를 이렇게 적고 있었다.

> no workflow runs tools/collect_s12_acceptance_evidence.py, so the named acceptance observations pitr-configuration-possible and pitr-rehearsal-dry-run-observed are produced by hand and CI never re-derives them.

**지금 그 문장은 거짓이다.** `#283`이 `.github/workflows/s12-acceptance-evidence.yml`을 들여왔고 그 PR은 train 9로 착지해 `25f43a25`에 있다. 측정한 것:

| 물음 | 측정 |
|---|---|
| workflow가 tree에 있나 | `git cat-file -e 25f43a25:.github/workflows/s12-acceptance-evidence.yml` → 있다 |
| 그것이 collector를 돌리나 | 113행 `python tools/collect_s12_acceptance_evidence.py`, 136행 `python tools/check_s12_acceptance_shape.py … --expected-head "$SOURCE_HEAD_SHA"` |
| 실제로 돈 적이 있나 | run **`36851875128`**, `workflow_dispatch`, head `40b3ec78`(=`#283` 최종 head), **success**. job `s12-acceptance-evidence`의 단계가 전부 success: *Derive the AC-12 acceptance items* · *Hold the bundle to its shape and to this head* · *Record that the two named observations were derived here* · *Upload the acceptance evidence* |
| 그 head가 이 tree에 있나 | `git merge-base --is-ancestor 40b3ec78 25f43a25` → 참 |

그리고 이 플래그를 올리는 **조건을 내가 직접 적어 두었다**. 카드 185의 History는 이렇게 적는다 — "레지스트리의 `verifiedAgainst.hostedRun`이 run id와 단계 이름으로 주장을 받치는 형식을 쓰므로, 같은 형식으로 이 lane의 run을 적은 뒤에 칸을 바꾸는 것이 맞다. **플래그를 먼저 올리고 증거를 나중에 붙이는 순서는 이 레지스트리가 두 번 정정한 바로 그 실수다.**" 그 조건이 충족됐으므로, **run을 그 형식으로 적고 나서** 칸을 바꿨다.

## 2. 그런데 고치는 것만으로는 같은 일이 또 일어난다 — rule 7

이 레지스트리가 조용히 낡은 것은 **이번이 세 번째 모양**이다. `VF-CL-03`은 `implemented: partial`이 거짓이 됐고, `VF-CL-04`는 이미 merge된 PR을 기다린다고 적었고, 이제 `ciVerified`가 사라진 이유를 들고 있었다. 앞의 둘은 **rule 4**가 잡는다 — manifest의 `impliesImplemented`와 tree를 대조하므로, 되돌려 놓아도 깨진다. **`ciVerified`에는 그런 규칙이 없었다.** 그래서 고치면서 규칙을 만들었다.

**rule 7 — tree가 `ciVerified`도 결정한다. 그리고 참인 ciVerified는 자기 run을 적어야 한다.**

| 절반 | 무엇 |
|---|---|
| 재도출 | manifest가 카드마다 `impliesCiVerified`(true/false/null)와 **자기 `ciVerifiedChecks`** 를 든다. 검사가 전부 성립하면 레지스트리의 `ciVerified`는 그 값과 **같아야** 한다. `null`은 `whyCiVerified`를 **요구한다** — 아무것도 주장하지 않으면서 커버리지처럼 읽히는 칸을 만들지 않기 위해서다 |
| 증거 | `impliesCiVerified: true`인 카드는 `ciVerifiedRun`(숫자 `runId`·`conclusion: success`·단계 이름·`headSha`)을 **들어야** 한다. 이것이 카드 185의 교훈을 규칙으로 옮긴 것이다 — **플래그가 증거보다 먼저 올라가지 못한다** |

`implemented`와 달리 값이 셋이 아니라 **둘과 null**이다. 그리고 `1 is True`가 거짓이므로 **동일성으로** 비교한다 — 이 파일에서 `acceptedCards: false`가 count 0과 같다고 읽힌 적이 있다.

**rule 7이 닿지 못하는 곳을 적어 둔다.** `VF-CL-01`·`02`·`03`의 시험은 **디렉터리 단위 lane**(`pytest tests/core`)에 실려 돈다. 그 lane을 가리키는 검사는 *어느* 카드의 동작이 돌았는지 말하지 못하므로, **아무것도 주장하지 않으면서 커버리지처럼 읽힌다.** 그래서 그 셋과 `VF-CL-05`는 `impliesCiVerified: null` + `whyCiVerified`이고, 그 칸들은 **내가 새로 주장한 것이 아니라 그대로 둔 것**이다. `VF-CL-04`만 주장한다 — 자기 workflow가 자기 도구 이름을 글자로 부르는 유일한 카드이기 때문이다.

## 3. 바뀐 것

| 파일 | 무엇 |
|---|---|
| `tools/check_vf_cl_registry.py` | rule 7(재도출 + `ci_run_findings`), manifest 모양 검사(키 부재·값·빈 검사 목록·`why` 누락), docstring의 규칙 목록과 세 번째 drift 기록, 출력 `status` 문장 정정 |
| `docs/vf-cl-registry-manifest.json` | 다섯 카드 전부에 `impliesCiVerified`·`whyCiVerified`/`ciVerifiedChecks`. `VF-CL-04`는 검사 5개(workflow 존재 + collector·gate 호출 글자 + collector 안의 두 관측 이름) |
| `docs/vf-cl-task-registry.json` | `VF-CL-04.ciVerified: true` + `ciVerifiedRun` + `ciVerifiedNote` 정정(남아 있는 미검증이 무엇인지 함께), `verifiedAgainst.tree` `6fc0428b` → **`25f43a25`** 와 그 tree의 `hostedRun`(Core **`36886647197`**, CX01 세 단계 전부 success), `localUnmeasured.measuredIn`도 같은 run으로 재측정, version 1.3.1 → 1.4.0 |
| `tests/core/test_check_vf_cl_registry.py` | rule 7 시험 13개(함수 55 → 68, case **114**), 그리고 shipped pair 시험을 **값에서 관계로** 바꿨다 |

**shipped pair 시험이 왜 바뀌었나.** 그 시험은 `hostedRun.runId == "36521298082"`와 `headSha.startswith("6fc0428b")`를 글자로 고정했다. 그래서 `verifiedAgainst.tree`를 옮기면 **기록된 run이 다른 tree를 기술하는데도 통과한다.** 지금은 관계를 단언한다 — `hostedRun.headSha`가 **레지스트리 자신의 `verifiedAgainst.tree`로 시작**하고, `localUnmeasured.measuredIn`이 **그 run id를 가리킨다**. 값 대신 관계를 고정하는 쪽이 이 파일이 두 번 틀린 방향을 막는다.

## 4. 검증

| 항목 | 결과 |
|---|---|
| `tools/check_vf_cl_registry.py` | exit 0, `verifiedAgainst: 25f43a25`, `status: every implementation and ciVerified claim re-derived from the tree` |
| `tests/core/test_check_vf_cl_registry.py` | **114 passed** |
| 변이 6종 | 전부 사망 — ① `ciVerified`를 `false`로 되돌림 → `the tree shows ciVerified=True but the registry says False` ② `ciVerifiedRun` 삭제 → `names no ciVerifiedRun` ③ `conclusion: failure` → `so it shows nothing` ④ `runId: "pending"` → `which is not a run id` ⑤ 주장한 workflow 경로를 없는 파일로 → `assertion no longer holds in the tree` ⑥ `steps: []` → `names no steps` |
| 문서 gate | `check_docs`·`check_doc_single_source`·citation ratchet(base `25f43a25`)·`git diff --check` 전부 exit 0 |
| exact-head CI | Backend·Core(두 lane 모두 이 시험을 `fetch-depth: 0`로 수집한다 — 그것을 고정하는 시험이 같은 파일에 있다) |

## 5. 미선택 — 그 행들이 왜 차단됐나

카드 198의 둘째 단계(#292 v1.9.1의 75 미만 행)는 **첫 단계에서 할 일이 나왔으므로 착수하지 않았다.** 그래도 차단 사유는 측정해서 적는다. owner는 `docs/task-registry.json`에서 읽었다.

| 행 | 점수 | owner | 남은 일 | 왜 이 카드가 아닌가 |
|---|---|---|---|---|
| `S12-DB` | 50 | Claude | 복원·권한·운영 인수 | **`G-22` 실 PITR 복구**다. v1.8 §4-3-4가 `pitrPreflight.status: BLOCKED_EXTERNAL`·`restoreAttempted: false`·`measuredRpoSeconds: null`을 적는다. 외부 전제 |
| `S12-ST` | 50 | Claude | 운영 점검·제공 폴더·복구 훈련 | 같다 — 복구 훈련은 실 하드웨어다 |
| `S02-ST` | 50 | Claude | 실제 API·브라우저 여정·인증 실패 기록 | 요구 증거 셋 중 둘이 **브라우저 여정**(Gemini·live IdP)과 **운영 인증 실패 기록**이다. 코드로 닫을 조각은 카탈로그 API이고, **`VF-CL-01`이 `/storage/locations`·`/storage/resolve`를 이미 들고 있다** — 그렇다면 이 행의 50이 과소평가인지가 **v1.10 재채점의 판정**이고 구현 카드가 아니다. 임의로 점수를 움직이지 않는다 |
| `S09-ST` | 50 | Claude | diff·테스트·trace Artifact 연결, golden eval·분류별 성적·금지 행동 시험 | **외부 전제가 없다.** v1.8 §4-4-3이 eval↔artifact 결합 검색 **0건**을 적는다. 그래서 이것이 **다음 코드 카드**이고, 첫 조각을 §6에 정의해 둔다 |
| `S08-BE` | 50 | **Codex** | ROOF·BuildKit·단일 GPU | owner가 Codex다. 그리고 `#292` r1이 측정한 남은 일은 **rootless BuildKit concrete transport·daemon·lease**로 격리·보안 고난도다 — 규약대로 내가 착수하지 않는다 |
| `S12-FE` | 50→75 | **Gemini** | 내부망 HTTPS 배포·사용자 인수 | Frontend·배포는 Gemini다 |

## 6. 다음 첫 행동

1. **Codex**: 이 변경 검토 — 특히 rule 7의 경계(왜 `VF-CL-04`만 주장하고 나머지는 `null`인가)와 `ciVerifiedRun`을 **offline로** 검사하는 선택(run이 실제로 존재하는지 GitHub에 묻지 않는다 — 파일에 관한 질문에 네트워크와 토큰을 요구하지 않기 위해서다).
2. **Claude**: `S09-ST`의 첫 조각 — **eval 결과와 artifact를 잇는 결속을 제품 경로에서 읽을 수 있게 하고 금지 행동 시험을 붙이는 것**. 지금 `tests/test_context_eval.py`의 artifact-pin 3 case가 유일한 결속 증거이고(§4-4-3·§5), 제품 쪽에 그 연결을 읽는 경로가 없다. 범위·계약을 먼저 적고 착수한다.
3. **코디네이터**: `VF-CL-04`의 남은 칸은 **Codex의 독립 검토**다(`0043-retained-replicas-pin-fix-re-review-not-recorded`·`3e267b05-archive-retention-tool-not-independently-reviewed`). 내가 닫을 수 없다.
