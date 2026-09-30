---
doc_id: "HIST-VFCL-NEXT-CARD-REGISTRY-2026-09-30"
title: "VF-CL 다음 카드 선택과 registry 정정 — 외부 전제 없는 가장 앞 카드를 고르려고 registry를 착지 tree와 대조했더니, 구현측 blocker 중 하나는 이미 닫혀 있었고 하나는 이미 병합된 PR을 기다리고 있었다. 정정하고, 같은 방식으로 다시 낡지 않도록 재도출 검사기를 붙였다. v1.1에서 검토가 두 가지를 더 찾았다 — restore drill은 **처음부터 hosted CI에서 측정되고 있었고**(exact-SHA run 36521298082, 0 skip · 20 passed) 제가 두 번 연속 외부 전제로 적었다, 그리고 검사기가 **형식만 봐서** registry를 거짓으로 만드는 편집 네 가지가 통과했다. v1.2에서 두 건을 더 닫았다 — 규칙 6이 파일 경로와 blocker 문장을 비교해서 **실제로 썼던 그 blocker 문자열을 그대로 다시 넣으면 통과**했고, 파이썬에서 `False == 0`이라 `acceptedCards: false`가 지적 0건이었다"
version: "1.2.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "user"
updated: "2026-09-30T12:10:08+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "6fc0428b"
task_ids: ["VF-CL-03", "VF-CL-04"]
tags: ["history", "vf-cl", "task-registry", "card-selection", "claude"]
---

# VF-CL 다음 카드 선택과 registry 정정 (2026-09-30)

## 0. 지시와 실제로 나온 것

지시는 "로드맵의 VF-CL 카드 중 **외부 전제 없이 진행 가능한 가장 앞 카드**를 task-registry와 대조해 고르고, 이미 착지된 것은 건너뛰고, 선택 근거를 첫 커밋 History에 기록"이었다. 순서는 storage catalog/API → `inv://` resolver → model registry/lineage → 복원·관측.

대조해 보니 **고를 카드가 없었다** — 그리고 그것이 이 작업의 결과다. registry의 구현측 blocker 넷 중 **하나는 이미 닫혀 있었고**, **하나는 이미 병합된 PR을 기다린다고 적혀 있었다**. 남은 둘은 reviewer(Codex)의 것이다. 그래서 착수한 것은 **registry 정정과, 같은 방식으로 다시 낡지 않게 하는 재도출 검사기**다.

registry는 코디네이터가 다음 카드를 고르는 근거다. 낡은 항목은 설명이 틀린 것으로 끝나지 않고 **이미 끝난 일을 하러 보내거나, 이미 끝난 기다림을 계속 기다리게** 한다.

## 1. 선택 근거 — 카드별로 무엇이 남아 있는가 (착지 `6fc0428b`)

| 카드 | registry가 적고 있던 것 | 착지 tree에서 확인한 것 |
|---|---|---|
| **VF-CL-01** storage catalog/API | blocker 0, `operationallyAccepted: false`만 | 남은 것은 **운영 인수**뿐 — 운영 데이터가 필요하므로 **외부 전제**. 제 몫 없음 |
| **VF-CL-02** `inv://` resolver | blocker 2건 | 둘 다 *"re-review not recorded"* · *"not independently reviewed"* — **reviewer(Codex)의 것**. 제가 닫을 수 없다 |
| **VF-CL-03** model registry·import adapter | `implemented: "partial"` + `import-adapter-has-no-request-path-contract` | **이미 닫혀 있다**(§2). 남은 1건은 license adapter 독립 검토 = Codex |
| **VF-CL-04** 복원·관측 | blocker 4건 | `retention-and-readiness-tools-not-wired-to-any-operational-gate`는 **이미 닫혀 있고**(§3), `...-until-pr-126`은 **blocker가 아니었다** — hosted CI가 처음부터 skip 0으로 돌리고 있었다(§4-1). 남은 2건은 Codex |
| **VF-CL-05** 독립 검토 | — | 검토 카드 자체. `notApplicable`이 이미 그렇게 적고 있다 |

즉 **구현측으로 제가 외부 전제 없이 착수할 수 있는 카드는 없다.** 그 사실을 registry가 가리고 있었으므로, 가리던 것을 고치는 것이 가장 앞에 할 일이었다.

## 2. VF-CL-03 — 요청 경로는 이미 있다

blocker는 "import adapter에 요청 경로 계약이 없다"였고, 설계 #152가 그 해소안이었다. 착지 tree에서 확인한 것:

- `src/saintvision/api/v1/model_release.py`가 존재하고, `require_exact_declaration(manifest, declared)`를 **실제로 호출**한다(`adapters/model_import.py`에서 import).
- 그 handler는 `src/saintvision/api/v1/projects.py`의 `model_release.register(router)`로 **모듈 import 시점에 mount**된다 — `add_api_route`이므로 `BusinessDispatch`가 `projects.router.routes`를 읽을 때 route 객체가 실제로 거기 있다.
- projects router에 model-registry 경로가 **6개** 있다 — `versions`(등록)·`verify`·`retention-pin`·`release`·`lineage`·dataset-digest lineage 조회. 설계가 "호출부 0건"이라고 적었던 lane 전체가 서 있다.
- 설계 v1.2가 `MODEL-0009`를 위해 요구한 `src/saintvision/api/problem.py`도 있다.

그래서 `implemented`를 `"partial"` → `true`로, 그 blocker를 `closedBlockers`로 옮겼다. **독립 검토 boolean은 건드리지 않았다** — 그것은 reviewer의 칸이다.

## 3. VF-CL-04 — retention·readiness는 이미 게이트에 물려 있다

blocker는 "retention·readiness 도구가 어떤 운영 게이트에도 연결되지 않았다"였다. 확인한 것:

`tools/collect_s12_acceptance_evidence.py`가 바로 그 게이트다. `tools/operational_readiness.py`·`tools/pitr_readiness.py`·`tools/pitr_opt_in_dry_run.py`를 실행해 각각을 **이름 있는 인수 관측**으로 바꾼다 — `pitr-configuration-possible`은 `pitr_readiness`에서, `pitr-rehearsal-dry-run-observed`는 `pitr_opt_in_dry_run`에서 온다.

retention은 **그 게이트를 통해 도달한다** — `tools/pitr_opt_in_dry_run.py`가 `pitr_archive_retention`에서 `plan`·`load_archive`·`load_backups`·`DEFAULT_DAYS`를 import하고 보고서에 `retention.as_dict()`를 담는다. "어떤 게이트에도 연결되지 않았다"는 서술은 착지 tree에서 참이 아니다.

## 4. VF-CL-04 — restore drill은 #126을 기다리는 것이 아니다

blocker가 `restore-drill-19-setup-skips-in-hosted-core-until-pr-126`이었다. **PR #126은 `9de490fd`로 병합됐다.** 그 문장을 믿고 기다리면 영원히 기다린다.

`tests/integration/test_recovery_drill.py`를 직접 돌려 확인했다(로컬, 단일 파일).

| 실행 조건 | 결과 |
|---|---|
| DSN 없음 | 1 passed, **19 skipped** — 사유는 `INV_TEST_ADMIN_DSN` 미설정 |
| **PostgreSQL DSN 공급** | 1 passed, **19 skipped** — 사유가 **바뀐다**: `CX01_CONTAINER` 미설정 **17건**, `INV_TEST_ARCHIVER_IMAGE` 미설정 **2건** |

숫자는 그대로이고 **사유만 바뀌었다** — 빠진 DSN에서 빠진 container 신원으로.

DSN을 준 실행에서 17건이 `alembic` 미설치로 error였던 것은 **제 로컬 환경 결함**이고 제품 결함이 아니다 — 설치 후 위 표의 결과가 나왔다. 그 구분을 적어 둔다.

### 4-1. 정정 — 그 blocker도 틀렸다 (v1.1)

여기서 저는 blocker를 `restore-drill-19-skips-need-CX01_CONTAINER-17-and-INV_TEST_ARCHIVER_IMAGE-2`로 다시 적고 **"여전히 열린 blocker이고 여전히 외부 전제다(container 입력은 운영자가 준다)"** 고 썼다. **그것도 틀렸다.** 검토가 정확히 그 지점을 짚었고, 확인했다.

| 확인한 것 | 결과 |
|---|---|
| hosted Core run **36521298082** | `headSha` **`6fc0428b49f28379cb4da17830d92256b55c2eb2`** — 이 registry가 주장하는 **바로 그 tree** |
| run 결론 | **success** |
| step `Create disposable CX01 PostgreSQL` | success |
| step `Run owned CX01 recovery drill evidence` | success |
| step `Require executed CX01 recovery evidence` | success |

마지막 step이 결정적이다. `core.yml`이 그 안에서 이렇게 단언한다:

```
assert skips == Counter(), f'CX01 recovery skip distribution drifted: {skips}'
assert setup_skip not in skips
assert passed == 20, f'Expected 20 passed CX01 cases, got {passed}'
```

그 step이 success라는 것은 **그 tree에서 drill이 skip 0으로 20건 통과했다**는 뜻이다. `CX01_CONTAINER`는 `core.yml`이 만든 일회용 container에서 나오고, archiver 2건은 **그 container의 image를 재사용**하므로 `INV_TEST_ARCHIVER_IMAGE`는 애초에 필요하지 않았다. 그래서 그 blocker가 기다리던 것은 **이미 다 와 있었다.**

**제가 같은 오류를 두 번 했다.** 처음에는 이미 병합된 PR을 기다린다고 적었고, 정정하면서는 hosted CI가 이미 주는 입력을 기다린다고 적었다. 두 번 다 **제 기계에서 관측되지 않은 것을 작업에 남은 것으로 옮겼다.** 원인은 하나다 — 로컬 skip을 blocker로 번역했고, hosted 증거를 대조하지 않았다.

그래서 registry에 **`localUnmeasured`**를 만들었다. blocker와 다른 항목이고, **어디서 측정되는지를 반드시 적는다**:

```json
{"what": "tests/integration/test_recovery_drill.py",
 "condition": "19 of 20 cases need a CX01 container on this host … local docker is off by memory constraint",
 "measuredIn": "hosted Core run 36521298082 at 6fc0428b …: 0 skips, 20 passed"}
```

검사기 규칙 6이 이것을 지킨다 — **같은 대상이 local gap이면서 blocker일 수 없다.**

### 4-2. 그런데 `ciVerified`는 왜 아직 false인가

drill 자체는 그 run에서 **ci-verified다.** 그래서 이 boolean이 false인 이유는 drill이 아니다. 대조해서 남은 것은 하나다 — **`tools/collect_s12_acceptance_evidence.py`를 실행하는 workflow가 없다.** `.github/workflows/` 전체에서 그 도구도, `pitr_readiness`·`pitr_opt_in_dry_run`·`operational_readiness`도 **호출되지 않는다.** 그 도구들의 단위 시험은 Core 전체 suite에서 돌지만, 그것을 **인수 관측으로 바꾸는 게이트**(§3에서 닫은 그 게이트)는 CI가 한 번도 재도출하지 않는다. 그래서 `pitr-configuration-possible`·`pitr-rehearsal-dry-run-observed`는 손으로 만든 관측이다.

`ciVerifiedNote`에 그대로 적었다. **이것이 남은 진짜 이유이고, drill은 아니다.**

## 5. 형식만 보는 검사기는 거짓을 통과시킨다 (v1.1)

검토가 검사기에 네 가지를 넣어 보고 **전부 통과하는 것**을 보여 줬다. 재현하고 고쳤다.

| 편집 | 왜 통과했나 | 지금 |
|---|---|---|
| `acceptedCards: 5`, 실제 인수 0 | 그 숫자를 **아무도 세지 않았다** | `operationallyAccepted: true` 개수와 대조, `acceptanceDenominator`도 카드 수와 대조 |
| 전 카드 `operationallyAccepted: true` | 카드 안의 다른 필드와 **모순을 보지 않았다** | 열린 blocker · `state != accepted` · `ciVerified`/`independentlyReviewed` false면 fail(`notApplicable`이 그 필드를 이름으로 면제할 때만 허용) |
| VF-CL-03을 PR 전 상태로 되돌림 | **되돌린 파일은 내부적으로 일관된다.** 자기 내용에 관한 어떤 규칙도 이것을 잡을 수 없다 | tree가 `implemented`를 결정한다 |
| VF-CL-04 retention blocker 재개방 | 같은 이유 | tree가 닫혀 있다고 보이면 열려 있다고 적을 수 없다 |

**뒤의 두 개가 어려운 모양이다.** 파일 밖에 있는 것이 필요하다. 그래서 카드별 재도출 check를 **별도 manifest**(`docs/vf-cl-registry-manifest.json`)로 옮겼다 — registry를 편집하는 것이 registry를 판정하는 기준을 함께 편집하지 못하게 하려는 것이다. 검사기는 manifest가 **없으면 돌지 않고**(exit 2), **카드 하나를 빠뜨리면** 돌지 않고, **닫힌 blocker의 check가 없으면** 돌지 않는다. **항목을 지우는 것은 침묵이 아니라 실패다.**

manifest에 아무것도 주장하지 않는 항목(`impliesImplemented: null`)은 **`why`를 반드시 적는다.** VF-CL-05가 그 경우다 — 검토 카드의 산출물은 문서이고, 파일 이름을 찾는 check는 **아무것도 단언하지 않으면서 검증된 것처럼 읽힌다.** 없는 것보다 나쁘므로, 주장하지 않는다고 적었다.

### 5-1. 규칙 6이 잡지 못한 것 (v1.2)

규칙 6은 `localUnmeasured.what`을 열린 blocker와 비교했다. **`what`은 파일 경로이고 blocker는 그것에 대한 문장이다.** 그래서 제가 실제로 썼던

```
restore-drill-19-skips-need-CX01_CONTAINER-17-and-INV_TEST_ARCHIVER_IMAGE-2
```

를 **그대로 다시 넣으면 어느 것과도 일치하지 않아 통과했다.** 검토가 그것을 재현했다. 즉 제가 두 번 한 실수를 막으려고 만든 규칙이 **그 실수의 실제 문자열은 막지 못했다.**

manifest에 카드별 **`forbiddenBlockers`** — 정정이 **폐기한 blocker id 전부** — 를 두고, 그중 하나라도 열려 있으면 drift로 본다. **manifest에 두는 이유**: 자기가 말하면 안 되는 것의 목록을 스스로 편집할 수 있는 파일은 그 말을 못 하게 된 것이 아니다. `localUnmeasured`에는 `blockerIdsThisReplaces`를 두고 **manifest가 뒷받침하지 않는 id를 주장할 수 없게** 했다 — registry가 자기 면제증을 발급하지 못한다.

VF-CL-04의 폐기 목록은 넷이다: `...-until-pr-126`(v1.1), `...-need-CX01_CONTAINER-17-...`(v1.2), `...-are-an-external-precondition`, `retention-and-readiness-tools-not-wired-to-any-operational-gate`.

### 5-2. `False == 0` (v1.2)

`acceptedCards: false`가 **지적 0건**이었다 — 파이썬에서 `False == 0`이고 인수된 카드가 0개였으므로 **숫자가 맞았다.** 그리고 `operationallyAccepted: 1`은 `is True`가 아니므로 **인수 개수에 세어지지 않으면서** 사람에게는 인수된 것으로 읽힌다. 양쪽 다 아무 말도 하지 않았다.

이제 bool 필드는 `type(x) is bool`, count는 `type(x) is int`로 본다 — `type(True) is int`가 거짓이므로 이 한 줄이 양쪽을 덮는다.

## 6. 다시 낡지 않게 — `tools/check_vf_cl_registry.py`

**아무것도 이 파일을 검사하지 않았다.** 그래서 조용히 낡었다. 재도출 검사기를 붙였고 규칙은 셋이다.

1. **모양** — 카드마다 다섯 상태 필드가 있고, `implemented`는 `true`/`false`/`"partial"` 중 하나이며, blocker는 빈 문자열이 아니다.
2. **blocker가 이미 병합된 PR을 가리키면 drift다.** `pr-<n>`·`#<n>`을 담은 blocker는 그것을 기다린다는 주장이고, history가 그 PR을 병합으로 기록하고 있으면 그 기다림은 끝났다. **#126 실수를 일반화한 규칙이 이것이다.**
3. **닫힌 blocker는 계속 닫혀 있어야 한다.** `closedBlockers` 항목이 `checks`를 들고, 검사기가 그것을 tree에서 다시 돌린다. `evidence`의 산문은 사람 몫이고, **검사기가 믿는 것은 `checks`다** — 산문만 두는 것이 지난 두 항목이 아무도 모르게 낡은 방식이었다.

검사 어휘는 셋으로 좁혔다(`references`·`absent`·`path-exists`). 넓은 어휘는 아무도 확인하지 않는 주장을 부른다. 모르는 `kind`는 **조용히 건너뛰지 않고 exit 2**다 — 아무도 돌리지 않는 검사는 없는 검사보다 나쁘다. 검사된 것처럼 읽히기 때문이다.

그리고 `verifiedAgainst.tree`가 **HEAD의 조상인지** 확인한다. 다른 tree에 대한 주장은 수치가 맞아도 여기에 대한 주장이 아니다.

**정정 전 registry로 검사기를 돌려 다섯 drift 부류가 전부 잡히는 것을 확인했다** — #126 오기재, open과 closed 동시 등재, `checks` 없는 산문, 더 이상 성립하지 않는 evidence, 조상이 아닌 tree.

## 7. 검증 (실제 수행한 것만)

| 확인 | 결과 |
|---|---|
| 검사기 부정 시험 | `tests/core/test_check_vf_cl_registry.py` **86 passed**(v1.1 54, v1.0 32) — 이하 v1.1 기준 서술은 v1.2에서 아래 행으로 갱신됐다. 원래 기록: **54 passed**(v1.0은 32. 로컬, 단일 파일 — 메모리 여유가 작아 전체 suite는 hosted CI 몫) |
| 정정된 registry | `tools/check_vf_cl_registry.py` **exit 0** |
| 정정 전 registry | 다섯 drift 부류 **전부 잡힘** |
| **검토가 준 편집 11종 (v1.2)** | 착지된 실제 registry 파일에 하나씩 적용해 **전부 잡힌다** — 앞의 6종에 **폐기된 v1.2 문자열 그대로**(exit 1) · **폐기된 v1.1 문자열**(exit 1, `#126` 규칙도 함께 발화) · `acceptedCards: false`(exit 1) · `operationallyAccepted: 1`(exit 1) · **local gap이 자기 폐기 목록을 비움**(exit 1). 적용 후 registry·manifest를 원본과 byte 단위로 대조했다 |
| **검토가 준 편집 6종** | **착지된 실제 registry 파일에** 하나씩 적용해 **전부 잡히는 것**을 확인했다 — `acceptedCards: 5`(exit 1) · 전 카드 인수(exit 1, 12건 지적) · VF-CL-03 되돌림(exit 1, `implemented`·열림·기록 삭제 3건) · retention blocker 재개방(exit 1) · drill을 다시 외부 전제로(exit 1) · **manifest 삭제(exit 2)**. 적용 후 두 파일을 원본과 **byte 단위로 대조**했다 |
| 시험이 찾아 준 제 결함 | `implemented: 1`이 통과했다 — `1 in (True, False, "partial")`이 파이썬에서 **참**이다. identity 비교로 고쳤다 |
| VF-CL-03 요청 경로 | 파일 존재·adapter 호출·`register(router)` mount·projects router의 model-registry 경로 **6개** 확인 |
| VF-CL-04 게이트 | `collect_s12_acceptance_evidence.py`가 세 도구를 실행하고 두 관측을 이름으로 내는 것, `pitr_opt_in_dry_run`이 `pitr_archive_retention`을 import해 `retention.as_dict()`를 담는 것 확인 |
| VF-CL-04 drill | `#126` 병합 커밋(`9de490fd`) 확인, DSN 유/무 두 실행으로 **19 skip의 사유가 바뀌는 것** 확인(17 + 2) |
| **VF-CL-04 drill (hosted)** | run **36521298082**의 `headSha`가 `6fc0428b49f2…`(주장한 그 tree), 결론 **success**, step `Create disposable CX01 PostgreSQL`·`Run owned CX01 recovery drill evidence`·`Require executed CX01 recovery evidence` **전부 success**. 그 마지막 step이 `skips == Counter()`·`passed == 20`을 단언하므로 **그 tree에서 skip 0 · 20 passed**다 |
| **VF-CL-04 `ciVerified`** | `.github/workflows/` 전체에서 `collect_s12_acceptance_evidence`·`pitr_readiness`·`pitr_opt_in_dry_run`·`operational_readiness` **호출 0건** 확인 — 그것이 남은 진짜 이유이고 drill은 아니다 |
| 건드리지 않은 것 | 독립 검토 boolean·그 blocker(reviewer 몫), 제품 코드, migration, 노드·Docker, sudo **0건** |

## 8. 남은 것 · 다음 첫 행동

1. **Codex**: VF-CL-02의 2건, VF-CL-03의 license adapter 1건, VF-CL-04의 2건 — 전부 독립 검토 기록이다. 그것이 닫히면 네 카드의 `independentlyReviewed`가 움직인다.
2. **사용자/운영**: VF-CL-01의 운영 인수 데이터. **VF-CL-04의 container 입력은 여기서 빠졌다** — hosted CI가 이미 준다(§4-1). 누구에게도 넘길 일이 아니었다.
3. **Claude**: 위가 들어오면 그 카드를 착수한다. 그 전까지 VF-CL 트랙에서 외부 전제 없이 제가 할 구현은 없고, 이 문서가 그 판단의 근거다.
4. **VF-CL-04 `ciVerified`를 움직이려면** `collect_s12_acceptance_evidence.py`를 실행하는 workflow step이 필요하다(§4-2). 그 게이트를 CI에 넣는 것은 workflow 변경이므로 **코디네이터 결정으로 남긴다** — 카드 159가 취소된 이유와 같은 종류의 판단이 필요하다.
5. 검사기를 문서 게이트에 붙일지도 코디네이터 결정으로 남긴다 — 지금은 손으로 돌리는 도구이고, 게이트에 넣으면 registry 편집이 CI를 막을 수 있다.

독립 검토는 Codex.
