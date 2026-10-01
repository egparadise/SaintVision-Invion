---
doc_id: "HISTORY-CARD198-VF-CL-04-CIVERIFIED-REDERIVED-20261002"
title: "카드 198 — VF-CL-04의 ciVerified를 진술에서 재도출로: 거짓이던 이유가 #283로 사라졌고, 레지스트리는 그것을 혼자 알 수 없었다 (rule 7, 그리고 미선택 행의 차단 사유)"
version: "1.3.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T04:20:38+09:00"
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

## 8. r1 — rule 7의 둘째 반이 fail-open이었다

Codex의 `#295` r1이 수동 확인으로 **사실값은 맞다**(run `36851875128` success, artifact `11155274241` digest, `acceptanceClaim false`)고 적고, 그와 별개로 **규칙이 아무것도 보장하지 않는다**고 지적했다. 맞다. 제가 쓴 `ci_run_findings()`는 **문장의 모양**만 봤다 — 숫자처럼 보이는 `runId`, `conclusion: success`, 비어 있지 않은 step 목록, 16진수 `headSha`. 그 넷은 **타이핑할 수 있는 것**이다.

**제 쪽에서 재현했다.** 레지스트리만 바꾼 변이 일곱 개가 **전부 findings 0**이었다.

| 변이 | r1 전 | r1 후 |
|---|---|---|
| `runId: "99999999999"` | **통과** | `runId is '99999999999' but the receipt says '36851875128'` |
| `headSha`를 다른 40-hex로 | **통과** | `headSha is '000…' but the receipt says '40b3ec78…'` |
| `workflowPath`를 없는 workflow로 | **통과** | `is '.github/workflows/nope.yml', not …s12-acceptance-evidence.yml` |
| `requiredSteps`를 발명 | **통과** | `requiredSteps differs from the receipt` |
| artifact digest 위조 | **통과** | `artifact.digest differs from the receipt` |
| 네 개 동시 | **통과** | 4건 보고 |
| `receipt` 포인터 제거 | — | `receipt is None but the receipt says …` |

### 8-1. 고친 방법 — 사실을 파일로 만들고, 그 파일을 결속한다

**`tools/record_vf_cl_ci_receipt.py`**(신설)가 `gh api`의 **run·jobs·artifacts 세 문서**를 받아 검사하고 receipt를 쓴다. 검사는 전부 fail-closed다 — repository·workflow path·`completed/success`·opt-in event·40-hex head, **모든 job이 success이고 카드가 요구한 step이 존재하며 success**, artifact 이름이 `<prefix><head>`이고 `expired: false`이며 expiry가 미래이고 digest가 sha256. receipt는 세 입력의 **sha256**과 자기 본문의 **canonical digest**를 함께 적는다.

**checker**는 `impliesCiVerified: true`인 카드에 대해 receipt를 읽고 세 가지를 맞춘다 — receipt 자신(schema·card·digest), **manifest가 든 기대값**(어느 workflow와 어느 step이 센다, 레지스트리가 자기 기준을 고르지 못하게 manifest에 둔다), 그리고 **레지스트리 블록을 field 대 field로**. 그리고 **읽지 않고 다시 측정하는 것 하나**: run의 head가 정말 그 tree에 있는지를 `git`으로 본다.

receipt 자체를 고치는 변이도 죽는다(측정): 조용한 편집은 **digest 불일치**로, digest까지 다시 봉인한 head 위조는 **artifact 이름이 head에 묶여 있어서**, 만료는 `no longer re-checkable`로, 다른 카드의 receipt는 `the receipt is for 'VF-CL-99'`로, 파일 부재는 `FileNotFoundError`로 잡힌다.

### 8-2. rule 8 — candidate는 verification을 물려받지 않는다

`verifiedAgainst.ref`가 `coord/train11-ci-0047`(착지 전 train 후보)이므로 `candidate: true`·`reverifyAt`을 적고, **그 tree가 integration ref에 닿는 순간 보고한다** — "`25f43a25`가 `origin/integration/all-agents-unified`에 도달했다, 착지 SHA에서 재검증·재기록하라". 착지 전에는 조상이 아니므로 조용하고, 착지 후에는 재기록 전까지 빨갛다. **조상 관계가 영구 승계의 근거가 되지 않는다**는 것이 요점이다. clone이 그 ref를 모르면 "판정할 수 없다"로 적는다 — shallow 규칙과 같은 구별이다.

### 8-3. 이것이 닫지 **않는** 것

receipt의 입력은 **인증된 호출자의 `gh api`가 돌려준 것**이다. `tools/import_ac11_security_scan.py`가 선언한 것과 같은 경계이고, 숨기지 않고 producer·checker docstring과 여기에 적는다. 그것까지 닫으려면 **CI가 `actions: read`로 receipt를 만들어** artifact로 들여와야 하는데, Backend·Core lane은 `contents: read`로 돈다 — **workflow 권한 결정**이고 이 도구가 정할 일이 아니다. 그래서 다음 행동으로 남긴다.

### 8-4. 검증

| 항목 | 결과 |
|---|---|
| `tests/core/test_check_vf_cl_registry.py` | **139 passed**(r1 전 114) |
| 변이 | 레지스트리측 7종 + receipt측 5종 = **12종 전부 사망** |
| 검사기 | exit 0, `verifiedAgainst: 25f43a25` |
| producer | 실제 세 `gh api` 문서로 receipt 생성, 재생성 시 `recordedAt`만 바뀌고 **digest 불변**(digest가 `recordedAt`을 제외하는 설계가 그대로 작동) |
| 문서 gate | 3종 + `git diff --check` exit 0 |

## 9. r2 — 결속은 두 파일이 서로 맞는다는 것만 보여 준다

Codex r2가 두 가지를 측정했다. **F1**: receipt와 레지스트리에서 `runId`를 **함께** `99999999999`로 위조하고 `receiptSha256`을 다시 계산하니 checker가 **exit 0**이다. **F2**: receipt에 알 수 없는 top-level key `unexpected`를 더하고 다시 봉인하니 역시 **exit 0**이고, nested `artifact`·`inputDigests`의 key 집합은 아예 검사하지 않았다.

**둘 다 재현했다.** 그리고 F1은 **설계의 한계이지 버그가 아니다** — `canonical_digest()`는 서명이 아니므로, 편집할 수 있는 사람은 다시 계산할 수 있다. 제가 §8-1에 "조용한 편집을 닫는다"고 적은 것은 맞지만, **"조용하지 않은 편집"은 닫지 않는다**는 것을 r1에서 충분히 크게 적지 않았다.

### 9-1. 코디네이터 판단대로 — 권위가 없으면 `true`가 아니다

두 길 중 **(b)**를 받았다: 이 PR은 **strict schema**와 **"권위 없는 receipt로는 `ciVerified: true`를 만들 수 없다"는 fail-closed 규칙**만 넣고 **`ciVerified`는 `false`로 되돌린다**. 정직성이 먼저다.

| 무엇 | 어떻게 |
|---|---|
| **rule 7c** | `impliesCiVerified: true`는 **무조건 거부**다(`RegistryUnusable`). opt-out flag를 두지 않았다 — 규칙이 막으려는 주장을 다시 주장할 자리를 만드는 셈이기 때문이다. 검증 가능한 attestation이 생기는 날 **이 분기가 고쳐질 자리**다 |
| **strict schema**(F2) | receipt의 top-level key 집합이 **정확히** `RECEIPT_KEYS`여야 하고(없는 key·추가 key 양쪽), `artifact`·`inputDigests`의 key 집합도 정확해야 하며, 입력 digest 셋은 각각 sha256이어야 한다 |
| **registry** | `VF-CL-04.ciVerified: false`. `ciVerifiedRun`과 receipt는 **MEASUREMENT RECORD**로 남고(여전히 서로 결속되고 strict schema를 받는다), note가 **거짓인 이유가 바뀌었다는 것**을 적는다 — "workflow가 없다"에서 "attested가 아니다"로 |
| **manifest** | `impliesCiVerified: false`이고, 그 `false`도 **도출된 것**이다: `{"kind": "absent", "path": ".github/workflows/s12-acceptance-evidence.yml", "text": "attest-build-provenance"}`. attestation step이 생기면 이 검사가 깨지고 이 entry를 다시 보게 된다 |

**위조 생존을 시험으로 남겼다** — `test_a_forged_and_resealed_receipt_is_why_true_is_refused`는 위조된 쌍이 **findings 0**임을 단언한다. 닫지 못한 것을 "닫았다"고 적는 대신, **왜 `true`가 거부되는지의 근거**로 둔 것이다. 누군가 attestation을 넣어 그 시험이 깨지는 날이 rule 7c를 풀 수 있는 순간이다.

### 9-2. 검증

| 항목 | 결과 |
|---|---|
| `tests/core/test_check_vf_cl_registry.py` | **148 passed**(r1 139) |
| F2 probe | unknown top-level key · artifact 추가/누락 key · `inputDigests` 누락/추가 key · sha256 아닌 digest **전부 보고** |
| F1 probe | 위조+재봉인 쌍은 여전히 findings 0 — **그래서 `true`가 거부된다**(시험으로 고정) |
| 검사기 | exit 0, `verifiedAgainst: 25f43a25`, `VF-CL-04.ciVerified: false` |
| 후속 | [[VF-CL-04 ciVerified 권위 있는 receipt 계약 요청]] |

## 10. r3 — 정확한 key 집합은 그 key 안의 값에 대해 아무것도 말하지 않는다

Codex r3이 두 가지를 들었고 **둘 다 제 실수**다.

### 10-1. F1 — `recordedAt: 123`이 통과했다

strict schema를 "key 집합이 정확하다"로만 만들었다. 그런데 **두 field는 canonical digest에서 제외된다**(`receiptSha256`과 `recordedAt`) — 설계상 그렇게 해야 digest를 재계산할 수 있기 때문인데, 그 말은 **그 두 자리의 잘못된 type은 재해시조차 필요 없다**는 뜻이다. Codex가 `recordedAt`을 숫자 `123`으로 바꿨고 checker는 exit 0이었다.

이제 **16개 receipt field와 4개 artifact field 전부**에 type·format 규칙이 있다(표로 적었다 — `RECEIPT_FIELD_RULES`·`RECEIPT_ARTIFACT_RULES`). `test_every_receipt_key_is_typed`가 **그 표의 key 집합과 schema의 key 집합을 같다고 단언**하므로, 나중에 field를 더하면서 규칙을 빼먹을 수 없다.

실측(한 번에 하나, 원복 후 clean 재확인): `recordedAt: 123` · `runId`를 int로 · `event: schedule` · relation `descendant` · `requiredSteps`에 빈 문자열 · `headBranch`를 list로 · `receiptSha256` 비hex · `artifact.id`를 int로 · digest에 `sha256:` 접두 없음 · `expiresAt`을 숫자로 — **열 가지 전부 보고**된다.

### 10-2. F2 — 중복 key가 제 정정을 조용히 지웠다

`docs/vf-cl-registry-manifest.json`의 `VF-CL-04`에 **`whyCiVerified`가 두 번** 있었다(116행·128행). `json.loads`는 **마지막**을 채택하므로, r2에서 쓴 "권위가 없어서 false다"라는 새 사유가 **r1의 옛 문장으로 대체돼 사라졌다**. 원인은 제 r2 patch가 **이미 그 key를 가진 entry에 같은 key를 넣은 것**이고, JSON이 조용히 받아 준 것이다.

중복을 지우고 옛 문장 중 **아직 사실인 부분**(검사들이 세우는 literal chain)은 남은 값 안으로 합쳤다. 그리고 **같은 모양이 다시 일어나지 못하게** `object_pairs_hook`으로 중복 key를 거부한다 — manifest와 레지스트리는 `RegistryUnusable`, receipt는 **finding**이다(receipt 하나가 나쁜 것은 그 카드의 drift이고 나머지는 판정할 수 있다). shipped 세 파일을 strict loader로 읽는 회귀 시험과, `VF-CL-04`의 `whyCiVerified`가 **attestation 사유를 담고 있다**는 내용 단언도 함께 넣었다.

**읽고 쓰는 파일을 두 번 같은 방식으로 읽을 수 없으면 기록이 아니다** — 이 레지스트리가 세 번째로 가르친 같은 교훈이고, 이번에는 drift가 아니라 **내 편집이 원인**이었다.

### 10-3. 시험에서 제가 틀린 두 가지

- artifact field 변이 시험이 **git repo가 생기기 전에** receipt fixture를 불렀다(`git rev-parse HEAD` exit 128). fixture를 먼저 돌리고 그것이 쓴 파일을 고치는 순서로 바꿨다.
- `receiptSha256`을 나쁜 값으로 두는 case를 **다시 봉인하는 fixture**로 넣었다 — 봉인이 그 field를 덮어쓰므로 변이가 사라졌다. 그 한 case만 **봉인하지 않고** 파일을 직접 쓰는 시험으로 분리했다.
- `card` 형식 규칙을 `VF-CL-\d{2}`로 썼더니 fixture의 `VF-CL-0X`가 걸렸다. **identity는 따로 검사된다**(receipt의 card == 판정 중인 카드)는 것을 확인하고 형식 규칙을 두 글자 영숫자로 넓혔다 — 형식과 identity를 혼동한 것이다.
