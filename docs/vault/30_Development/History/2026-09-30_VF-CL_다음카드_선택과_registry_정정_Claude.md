---
doc_id: "HIST-VFCL-NEXT-CARD-REGISTRY-2026-09-30"
title: "VF-CL 다음 카드 선택과 registry 정정 — 외부 전제 없는 가장 앞 카드를 고르려고 registry를 착지 tree와 대조했더니, 구현측 blocker 중 하나는 이미 닫혀 있었고 하나는 이미 병합된 PR을 기다리고 있었다. 정정하고, 같은 방식으로 다시 낡지 않도록 재도출 검사기를 붙였다"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "user"
updated: "2026-09-30T09:48:23+09:00"
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
| **VF-CL-04** 복원·관측 | blocker 4건 | `retention-and-readiness-tools-not-wired-to-any-operational-gate`는 **이미 닫혀 있고**(§3), `...-until-pr-126`은 **사유가 틀렸다**(§4). 남은 2건은 Codex |
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

숫자는 그대로이고 **사유만 바뀌었다** — 빠진 DSN에서 빠진 container 신원으로. 그래서 blocker를 `restore-drill-19-skips-need-CX01_CONTAINER-17-and-INV_TEST_ARCHIVER_IMAGE-2`로 다시 적었다. 이것은 여전히 열린 blocker이고 여전히 **외부 전제**다(container 입력은 운영자가 준다). 다만 무엇을 기다리는지가 이제 맞다.

DSN을 준 실행에서 17건이 `alembic` 미설치로 error였던 것은 **제 로컬 환경 결함**이고 제품 결함이 아니다 — 설치 후 위 표의 결과가 나왔다. 그 구분을 적어 둔다.

## 5. 다시 낡지 않게 — `tools/check_vf_cl_registry.py`

**아무것도 이 파일을 검사하지 않았다.** 그래서 조용히 낡었다. 재도출 검사기를 붙였고 규칙은 셋이다.

1. **모양** — 카드마다 다섯 상태 필드가 있고, `implemented`는 `true`/`false`/`"partial"` 중 하나이며, blocker는 빈 문자열이 아니다.
2. **blocker가 이미 병합된 PR을 가리키면 drift다.** `pr-<n>`·`#<n>`을 담은 blocker는 그것을 기다린다는 주장이고, history가 그 PR을 병합으로 기록하고 있으면 그 기다림은 끝났다. **#126 실수를 일반화한 규칙이 이것이다.**
3. **닫힌 blocker는 계속 닫혀 있어야 한다.** `closedBlockers` 항목이 `checks`를 들고, 검사기가 그것을 tree에서 다시 돌린다. `evidence`의 산문은 사람 몫이고, **검사기가 믿는 것은 `checks`다** — 산문만 두는 것이 지난 두 항목이 아무도 모르게 낡은 방식이었다.

검사 어휘는 셋으로 좁혔다(`references`·`absent`·`path-exists`). 넓은 어휘는 아무도 확인하지 않는 주장을 부른다. 모르는 `kind`는 **조용히 건너뛰지 않고 exit 2**다 — 아무도 돌리지 않는 검사는 없는 검사보다 나쁘다. 검사된 것처럼 읽히기 때문이다.

그리고 `verifiedAgainst.tree`가 **HEAD의 조상인지** 확인한다. 다른 tree에 대한 주장은 수치가 맞아도 여기에 대한 주장이 아니다.

**정정 전 registry로 검사기를 돌려 다섯 drift 부류가 전부 잡히는 것을 확인했다** — #126 오기재, open과 closed 동시 등재, `checks` 없는 산문, 더 이상 성립하지 않는 evidence, 조상이 아닌 tree.

## 6. 검증 (실제 수행한 것만)

| 확인 | 결과 |
|---|---|
| 검사기 부정 시험 | `tests/core/test_check_vf_cl_registry.py` **32 passed**(로컬, 단일 파일 — 메모리 여유가 작아 전체 suite는 hosted CI 몫) |
| 정정된 registry | `tools/check_vf_cl_registry.py` **exit 0** |
| 정정 전 registry | 다섯 drift 부류 **전부 잡힘** |
| 시험이 찾아 준 제 결함 | `implemented: 1`이 통과했다 — `1 in (True, False, "partial")`이 파이썬에서 **참**이다. identity 비교로 고쳤다 |
| VF-CL-03 요청 경로 | 파일 존재·adapter 호출·`register(router)` mount·projects router의 model-registry 경로 **6개** 확인 |
| VF-CL-04 게이트 | `collect_s12_acceptance_evidence.py`가 세 도구를 실행하고 두 관측을 이름으로 내는 것, `pitr_opt_in_dry_run`이 `pitr_archive_retention`을 import해 `retention.as_dict()`를 담는 것 확인 |
| VF-CL-04 drill | `#126` 병합 커밋(`9de490fd`) 확인, DSN 유/무 두 실행으로 **19 skip의 사유가 바뀌는 것** 확인(17 + 2) |
| 건드리지 않은 것 | 독립 검토 boolean·그 blocker(reviewer 몫), 제품 코드, migration, 노드·Docker, sudo **0건** |

## 7. 남은 것 · 다음 첫 행동

1. **Codex**: VF-CL-02의 2건, VF-CL-03의 license adapter 1건, VF-CL-04의 2건 — 전부 독립 검토 기록이다. 그것이 닫히면 네 카드의 `independentlyReviewed`가 움직인다.
2. **사용자/운영**: VF-CL-04의 `CX01_CONTAINER`·`INV_TEST_ARCHIVER_IMAGE`, VF-CL-01의 운영 인수 데이터.
3. **Claude**: 위가 들어오면 그 카드를 착수한다. 그 전까지 VF-CL 트랙에서 외부 전제 없이 제가 할 구현은 없고, 이 문서가 그 판단의 근거다.
4. 검사기를 문서 게이트에 붙일지는 코디네이터 결정으로 남긴다 — 지금은 손으로 돌리는 도구이고, 게이트에 넣으면 registry 편집이 CI를 막을 수 있다.

독립 검토는 Codex.
