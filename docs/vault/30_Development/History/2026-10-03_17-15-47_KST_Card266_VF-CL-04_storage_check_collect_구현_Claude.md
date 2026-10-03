---
doc_id: "HISTORY-CARD266-VF-CL-04-STORAGE-CHECK-COLLECT-20261003"
title: "카드 266 — 서명된 폴더 점검을 돌리는 제품 경로를 설계대로 구현했다. ledger 응답이 쓰기와 같은 transaction에서 커밋되고, 저장된 응답은 지금 권한이 있는 주체에게만 돌아간다"
version: "1.2.1"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-03T21:14:40+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "9e9a551c"
task_ids: ["S12-ST", "S12-DB", "S02-ST"]
tags: ["vf-cl-04", "storage-check", "idempotency", "concurrency", "replica-repair", "claude"]
---

# 카드 266 — VF-CL-04 storage check 실행 경로 구현

## 0. 한 줄

`#358`(카드 263) 설계가 Codex r8 승인(`e14aa8ce`)이고 **그 설계가 구현 계약**이었다. 사슬은 전부 있었고 **그것을 돌리는 것이 없었다** — `StorageSampleStore`를 생성하는 코드가 저장소 전체에서 시험 한 곳뿐이었고, 그래서 AC-12 인수 항목 `contributed-folders-checked`가 폴더 0개일 때 `PASS`, 1개부터는 영원히 `FAIL`이었다. 이제 **공개 write surface 하나**(`POST /v1/projects/{project}/runs/{run_id}/storage-samples`)가 세 단계로 그것을 돌리고, **ledger 응답이 다섯 쓰기와 같은 transaction에서 커밋되며**, **저장된 응답은 지금 권한이 있는 주체에게만** 돌아간다. **r3 기준** 시험 **70**(collect 32 + HTTP 9 + startup 5 + repair route 6 + replica 18), 변이 **22개 중 21 사살 + 1 equivalent(사유 기록)**(runner와 결과가 tree에 있다), migration **0건**(`0065` 비움). r2에서 고친 차단 다섯과 **측정이 뒤집은 전제 하나**는 §9다.

## 1. 무엇이 들어갔는가

| 자리 | 내용 |
|---|---|
| `services/control-plane/src/inv/storage_commit.py` | `accept()`를 **셋으로** 쪼갰다 — `bound_envelope`(transaction 밖에서 복사·검증·해시) · `locked_sample_authority`(잠그고 판정, **아무것도 쓰지 않는다**) · `apply_sample`(다섯 행을 쓰고, **아무것도 판정하지 않는다**). `accept()`는 **기존 호출자를 위한 wrapper**로 동작 불변 |
| `services/control-plane/src/inv/storage_check_collect.py` (새 파일) | `derive_request_id`(고정 namespace UUIDv5 + `\x1f` 구분자) · `StorageCheckCollector`(세 단계) · `_authority`(replay 전에 보는 셋) · `configured_storage_sample_collector`(운영자 mTLS 자산에서만 구성) |
| `services/control-plane/src/inv/app.py` | 공개 route 하나 + `storage_sample_collector`·`denial_engine` 주입 + **`DomainError` handler가 AUTH·SEC 거부를 공유 recorder로 기록**(이전에는 감사 0행) |
| `services/control-plane/src/inv/business_surface.py` | business engine을 `app.state.denial_engine`으로 노출(반환 타입 불변 — 기존 호출자 5곳 그대로) |
| `src/saintvision/api/denial_recorder.py` (새 파일) | `create_app` 안의 closure였던 denial recorder를 **module 수준 정본 하나**로. 두 collaborator만 인자이고 규칙은 한 곳 |
| `src/saintvision/services/replica_repair.py` | `project_id`를 **세 함수의 권위 입력**으로. `(tenant_id, project_id)` 둘 다 거르고 **`0062` legacy NULL 제외** |
| `src/saintvision/api/v1/storage_project.py` + 계약 2 | `GET /v1/projects/{project_id}/storage/replica-repair-plan` — 정책 수와 관측 ready 수를 **둘 다** 돌려주고 복사 원본 node를 말하며 `repairPerformed`는 literal `false` |

## 2. 세 단계가 왜 세 단계인가

kernel transaction은 **network I/O를 금지한다**(`db.py:211`). 그래서 node 호출을 transaction 안에 둘 수 없고, node 응답이 `observedAt`과 **서명**을 담으므로 **두 요청이 같은 봉투를 받는다는 보장이 없다**(같은 초 안에서는 실제로 같다 — §9-4의 정정). ledger 응답이 쓰기와 다른 transaction에 있으면 같은 key 동시 요청 둘 중 하나가 **`IDEM-0001`**을 받는다 — 멱등이 막아야 할 바로 그 일이다.

| 단계 | transaction | 하는 일 |
|---|---|---|
| **1. pre-I/O** | 하나 | ledger 행 `ON CONFLICT DO NOTHING` → `FOR UPDATE` → hash 비교 → **현재 권한 재검사** → `response` 있으면 **그 자리에서 replay(node 미호출)** → 없으면 `_scope` 뒤 pending request 생성 → **커밋** |
| **2. node I/O** | **없다** | `storage_sample(...)` 6초. 실패는 `NODE-0050`·`NODE-0030`이고 **아무것도 쓰지 않는다** |
| **3. final** | 하나 | idempotency `FOR UPDATE` → **현재 권한 재검사** → `response` 있으면 **방금 받은 봉투를 버리고 replay** → 없을 때만 `locked_sample_authority` + `apply_sample` + **ledger `_save`를 같은 transaction에서** |

`accept()`를 쪼갠 이유가 그 마지막 칸이다 — **카드 261이 `record_deployment`에 한 것과 같은 분할이고 이유도 같다**: 잠금 뒤에 결정이 바뀔 수 있으면 쓰기 직전에 다시 읽을 자리가 있어야 한다.

## 3. 저장된 응답보다 권한이 먼저다

두 replay 분기 **모두** 권한을 먼저 읽는다. 선례가 그 순서다 — `ApprovalStore.request()`(`approvals.py:219-223`)와 `ModelCommit.commit()`(`model_commit.py:78-91`)이 `_ledger` → `_grant` → `return prior`다.

| 사유 | 공개 | denial 감사 |
|---|---|---|
| project grant·`can_request` 부재, **project archive** | **`AUTH-0030` 403** | **+1** |
| contribution 없음·다른 tenant·**소유권 변경**·**비활성** | **`RES-0004` 404**(하나로 수렴) | **없음** |

가르는 기준은 **그 답이 무엇을 알려 주는가**다. project는 호출자가 경로로 지목했으니 알려 주는 것이 없고, contribution 쪽 네 경우를 구별해 주면 **남의 contribution id가 존재한다**는 신탁이 된다.

**Run의 active·version은 replay에서 다시 요구하지 않는다** — Run 상태는 "새 관측을 적어도 되는가"이고 replay는 아무것도 적지 않는다. 선례의 replay 분기도 `lock_run`을 부르지 않는다.

## 4. 설계에 없던 둘 — 적어 둔다

1. **kernel에는 감사 경로가 아예 없었다.** 설계 r4에서 "kernel handler에 단일 recorder 연결"을 구현 범위로 적었고, 실제로 붙여 보니 필요한 것은 **engine 하나**였다 — `record_denial_out_of_band`는 `inv_app` role의 SQLAlchemy engine을 받고, 그 engine은 이 process에서 `configured_business`가 만드는 것 하나뿐이다. 그래서 그것을 `app.state.denial_engine`으로 노출했다(반환 타입을 바꾸면 기존 호출자 5곳이 깨진다).
2. **recorder의 collaborator 둘을 인자로 남겼다.** closure를 그대로 module로 옮기면 `app_module.record_denial_out_of_band`·`audit_action`을 patch하는 **기존 시험 9파일 11자리**가 전부 뚫린다. 규칙은 한 곳에 두고 **두 collaborator만** 인자로 받게 해서 각 앱의 handler가 자기 이름을 넘기게 했다 — 정본은 하나, 시험 seam은 그대로다.

## 5. 실제 검증 증거 (r1 시점 — **현재 수치는 §9-3**)

| 무엇 | 결과 |
|---|---|
| collect surface (실 PG, 실제 서명) | **17 passed** |
| repair plan route (실 PG) | **6 passed** |
| `replica_repair` 서비스 (실 PG) | **16 passed** |
| kernel storage·model 회귀 | **67 passed**, 29 skipped(Docker lane) |
| recorder를 patch하는 기존 시험 | **252 + 48 passed** |
| `configured_business` 사용 시험 | **16 passed** |
| **변이** | **10/10 KILLED** |
| 계약·문서 gate | `export_schemas --check` PASS(103) · `check_docs` PASS · `git diff --check` 깨끗 |

### 변이가 내 시험의 공백 둘을 찾았다 — 숨기지 않는다

처음 돌렸을 때 **둘이 살아남았고 둘 다 코드가 아니라 내 시험의 문제**였다.

* **3단계 권한 검사를 빼도 죽지 않았다.** 모든 철회 시험이 **재시도 전에** 철회해서 1단계가 잡았고, 3단계가 "저장된 응답 + 철회된 권한"으로 도달한 적이 없었다. **설계가 이름까지 적어 둔 schedule을 내가 안 쓴 것**이다 — 한 요청을 node 호출 안에서 멈추고, 두 번째가 완주해 응답을 저장하고, 그 뒤 grant를 철회하고, 그제서야 첫 요청을 풀어 **3단계 replay가 거부**되는 것을 단언한다.
* **contribution 소유자 비교를 빼도 죽지 않았다.** 비활성·없음만 덮고 **소유권 변경**을 안 썼다. 지금은 폴더를 다른 user에게 넘긴 뒤 같은 key가 **node 호출 0회**로 `RES-0004`를 받는 것을 단언한다.

둘을 더한 뒤 10/10이었고, r2에서 변이가 **18개로 늘어 18/18**이다(§9-3).

## 6. migration

**없다.** `0065`는 비워 둔다. 설계 r4·r8이 정한 그대로 — `storage_checks`의 `mismatch_count <= sampled_count`는 `0005`에 이미 있고, `request_id`는 **파생**이라 열이 필요 없고, repair route의 project 결속은 `0062`의 열에 조건을 더하는 질의의 일이다.

## 7. 남은 문제 / 이 카드 밖

* **주기성은 닫지 않았다.** `pilot.py`의 `stale_after_days=7`보다 자주 누군가 요청해야 하고 그 "누군가"는 **운영자**다. 자동 주기는 principal 위임 설계가 선행이고 별 카드다(설계 §5-1-3가 그렇게 적었다).
* **운영 측 선행 둘**: node agent의 `--storage-policy` 승인 파일과, API process의 `storageSample` mTLS 설정. 둘 중 하나라도 없으면 **503이고 행을 적지 않는다** — "관측 불가"를 건강으로 바꾸지 않는다.
* `contributed-folders-checked`의 **빈 모집단 PASS**(설계 §5-1-4)는 수집기 쪽 변경이고 이 카드에 넣지 않았다 — 설계가 구현 순서를 §5-1 → §5-3 → §5-2로 권했고 이 카드는 그 첫째·둘째다.
* **고난도 동시성**이므로 검토는 Codex다.

## 8. 다음

exact-head Backend/Core/security green 뒤 **'검토 기준 head' 코멘트 1회**. 검토는 Codex.

## 9. r2 — Codex r1의 차단 다섯, 그리고 측정이 뒤집은 전제 하나

### 9-1. 다섯 가지

| | 무엇이었나 | 고친 것 |
|---|---|---|
| **F1** | `storageSample`이 strict top-level 허용 집합에 없어 **넣으면 startup 거부, 빼면 route가 항상 503**인 dead branch였다 | 허용 키에 넣고, 그 block도 **알 수 없는 키를 거부**하도록 strict하게 |
| **F2** | contribution에 **project 경계가 전혀 없었다** — 같은 tenant 소유자가 다른 project 또는 NULL legacy 카탈로그 폴더를 수집할 수 있었다 | §9-2 |
| **F3** | pre-I/O가 **한 transaction이 아니었다** — `db.transaction`이 자기 connection을 열므로 outer tx 안의 `issue()`가 pending을 **먼저 커밋**하고, 이후 실패 시 pending만 남았다 | `locked_issue(conn, …)`를 뽑아 **같은 connection·tx**에서 ledger와 함께 커밋. `issue()`는 기존 호출자용 wrapper |
| **F4** | kernel이 **identity를 pin하지 않아** 인증된 거부가 `anonymous`·tenant 없음으로 기록되고, recorder가 읽는 `path_params["project_id"]`와 route의 `{project}`가 어긋나 **project도 없었다** | 검증 **뒤** identity를 pin, route를 recorder 계약 이름으로, **collector만 구성되고 recorder가 없으면 startup 거부** |
| **추가** | `business_permission`을 `linked=True` 없이 불러 **kernel-only project에서 None → `granted["userId"]` 500** | `linked=True`로 **fail-closed `AUTH-0030`**, 그 project 모양을 만드는 부정 시험 추가 |
| **F5** | 실행 증거 부족 — HTTP 시험 0건, 변이 runner가 tree에 없음 | §9-3 |

### 9-2. F2를 고칠 **자리**는 측정이 정했다

경계가 필요한 것은 `data_locations.project_id`인데 **kernel role이 그 열을 읽을 수 없다.** 추정이 아니라 head에서 쟀다.

```
has_column_privilege('inv_kernel','public.data_locations','project_id','SELECT') -> False
has_column_privilege('inv_app',   'public.data_locations','project_id','SELECT') -> True
```

`0062`(내 카드 253)가 열을 더하면서 **GRANT를 바꾸지 않았고**, kernel의 column 단위 grant 일곱 개에 그 열이 없다. 그래서 **kernel의 손을 넓히지 않고** 카탈로그의 주인인 app role 연결에서 그 한 질문만 묻는다(그 읽기는 RLS 아래이므로 tenant GUC를 세운다). 규칙은 **전부 아니면 거부**다 — 이 project에 **하나 이상** 있고 **밖에 하나도 없어야** 하며 **NULL은 밖**이다.

**한계도 적었다** — 그런데 그 서술 자체가 r3에서 **틀린 것으로 판명됐다**(§10-1): 그 읽기는 다른 transaction이지만, **폴더 행을 먼저 잠그면** 제품의 catalogue 쓰기가 같은 행을 잡으므로 경계는 고정된다. r2의 모양은 잠금보다 **먼저** 물어서 실제 경쟁이 있었다. 양쪽 phase에서 확인하고 쓰기 경로의 잠금은 그대로지만, 잠글 수 있게 만드는 길은 셋(열 GRANT, definer 함수 — **definer 수가 움직여 AC-11 검토 집합을 건드린다**, surface를 app으로 이동)이고 **고르는 것은 이 카드의 몫이 아니다**.

### 9-3. 증거

| 무엇 | 결과 |
|---|---|
| collect surface (실 PG·실제 서명) | **28 passed** |
| **HTTP route** (실 PG, 실제 app·recorder 배선) | **11 passed** |
| repair plan route · `replica_repair` | **6 · 16 passed** |
| kernel 회귀(storage·transport·model·control·account·resolver) | **52 passed**, 27 Docker skip |
| denial recorder 계열 | **73 passed** |
| **변이** | **18/18 KILLED** — runner와 결과가 **tree에 있다**(`tools/test_c266_mutations.py`, `Evidence/c266-mutation-results.json`) |

HTTP 시험이 드는 것: 201·replay 200 · **인증된 거부가 정확히 1행**(실 actor·tenant·project·bounded action·trace, action에 식별자 없음) · 없음은 **denial 0행** · 불가 셋(`NODE-0030`·`NODE-0050`·`RES-0007`)이 각각 **ProblemDetails 10 key 정확히·`storage_checks` 0행·denial 0행** · strict body와 필수 key 422 · **감사 쓰기 실패가 단정한 403으로 포장되지 않는다**.

**변이 둘이 처음에 살아남았고 둘 다 시험 공백이었다** — (i) 일부만 migrate된 폴더(`project_id` 일부 NULL)를 안 써서 "NULL은 밖"을 지워도 죽지 않았고, (ii) phase 1이 `locked_issue`를 쓰는지는 **커밋 자체를 실패시키지 않으면 외부에서 구별되지 않아** source 수준으로 단언했다 — 그 시험이 스스로 그렇다고 적는다.

### 9-4. 측정이 뒤집은 전제

설계와 나(그리고 r5의 논의)가 공유한 전제는 "두 요청이 **같은 봉투를 받지 않는다**"였다. **틀렸다** — `observedAt`이 **초 단위**이고 서명이 결정론적이므로 **같은 초 안의 두 표본은 byte 단위로 같다**(실측). 세 단계가 존재하는 이유는 "항상 다르다"가 아니라 **"초가 넘어가면 다르다"**이고, 시험이 양쪽을 단언한다. 같은 초에서는 응답 hash 비교만으로도 우연히 맞아 보이기 때문에, 빠른 시험에서 괜찮아 보이고 운영에서 깨지는 모양이다.

## 10. r3 — Codex r2의 셋

### 10-1. F1은 한계가 아니라 **경쟁이었다**

r2까지 나는 cross-connection 경계 읽기를 "잠글 수 없는 한계"로 적어 두었다. **그것이 틀렸다** — final phase가 catalogue 읽기를 끝낸 **뒤에** Run·contribution을 잠갔으므로, 그 사이에 폴더의 location을 다른 project로 옮기는 commit이 들어오면 collect가 **거부 없이 check를 기록**했다(Codex r2의 probe).

**고친 것은 connection이 아니라 순서다.** `_locked_boundary`가 `_scope`로 **Run과 contribution 행을 `FOR UPDATE`로 잡고 그다음에** catalogue를 묻는다. 두 phase 모두 **replay 분기보다 먼저** 그것을 지난다 — 저장된 답도 project를 떠난 폴더에 대해서는 돌아가지 않는다.

cross-connection 읽기가 **안전한 이유**도 이제 단언한다: 제품의 catalogue 쓰기가 **같은 contribution 행을 먼저 `FOR UPDATE`로 잡는다**(`src/saintvision/services/storage.py:350 locked_contribution`, `src/saintvision/api/v1/storage_project.py`가 그것을 쓴다). 그래서 잠금을 든 동안 그 폴더의 location은 들어오거나 나갈 수 없다. **잠금이 그 읽기를 안전하게 만드는 것이고, 읽기 혼자서는 처음부터 안전하지 않았다.**

시험 셋: 잠금을 든 동안 이동을 시도하는 **mid-flight schedule**(가능한 결과가 "이동 먼저 → 거부"와 "collect 먼저 → 이동은 뒤에" 둘뿐이고, "떠난 폴더에 대한 check 기록"은 없다) · **replay 분기의 같은 경쟁** · 질문이 두 phase 모두에서 잠금 아래에 남아 있다는 **source 수준 단언**(그 시험이 스스로 그렇게 적는다).

### 10-2. F2 — 감사 실패는 **정확히 500**

Boundary가 임의 예외를 `SYS-0001` 503으로 바꾸므로 감사 쓰기 실패가 503으로 나갔고, **내 시험이 (500, 503) 둘 다 허용해서** 되돌려도 통과했다. handler가 **500을 명시**하고(거부 자신의 코드는 떨어뜨려 실패에서 판정을 읽을 수 없게) 시험이 **정확히 500**과 body에 `AUTH-0030` 없음을 단언한다 — "관측 불가"의 세 503과 **다른 답**이다. 공유 불변식은 `tests/integration/test_canonical_denial_audit_real_pg.py`의 그것이다.

### 10-3. F3 — 운영 구성으로 실제 기동

`create_configured_app()` + settings 파일 + **실제 test PKI** + business surface로 기동해 **route 등록**을 단언하고, 인증된 요청이 collector 자신의 거부(`AUTH-0030`)에 도달하는 것까지 본다. 그리고 기동이 **거부되어야 하는** 넷 — block의 알 수 없는 키 · `business` 없는 `storageSample` · 읽을 수 없는 TLS 자산 · (변이로) 허용 집합에서 `storageSample` 제거 — 가 각각 **영구 503으로 degrade하지 않고 startup에서 실패**한다.

### 10-4. 변이 22개 — 21 사살 + 1 equivalent

**M2를 equivalent로 선언했고 사유를 측정했다**: phase 3에서 그것이 지우는 호출 뒤에 `_locked_boundary`가 오고, 그 `_scope`가 **같은 grant와 같은 소유권을 잠금 아래에서 다시 본다**(`storage_commit.py:48-49`의 `_grant`·`permission(..., linked=True)`). 그래서 동작이 바뀌지 않고 어떤 시험도 둘을 구별할 수 없다. 집합에서 지우지 않고 남긴 이유는, 그 줄을 다음에 옮길 사람이 이 메모를 봐야 하기 때문이다.
### 10-5. `08fd8844`의 Backend red — 인용 래칫, 그리고 내가 게이트를 **너무 일찍** 돌렸다

`08fd8844`에서 Backend(3.12·3.14 동일)가 하나 떨어졌다: `tests/test_check_doc_path_citations.py::test_real_vault_ratchet_is_green`, 새로 깨진 인용 **2건**.

```
+ 30_Development/Agent별 작업/Claude 작업 현황.md || services/storage.py locked_contribution  [path does not exist]
+ 30_Development/History/2026-10-03_17-15-47_KST_..._Claude.md || services/storage.py locked_contribution  [path does not exist]
```

둘 다 **§10-1에서 내가 쓴 줄**이다. 실재 경로는 `src/saintvision/services/storage.py:350`인데 **`src/saintvision/` 접두사를 뺀 꼴**로 적었다. 그 꼴이 그냥 틀린 이름으로 끝나지 않는 이유는 스캐너를 재 보면 나온다 — `CITATION_ROOTS`(`tools/check_doc_path_citations.py:68`)에 **`services`가 들어 있고** 저장소 루트에 실제로 그 디렉터리가 있으므로(`services/control-plane`), 접두사가 빠진 토큰이 **저장소 경로로 읽혀** "없는 경로"가 된다. 같은 문장의 `storage_project.py`는 루트에 `api`가 없어 애초에 경로로 읽히지 않았지만 그것도 전체 경로(`src/saintvision/api/v1/storage_project.py`)로 고쳤다.

그리고 **이 절을 처음 쓸 때 같은 함정을 한 번 더 밟았다**: 실패를 설명하려고 틀린 경로를 **inline code span에 그대로 인용**했더니 래칫이 그 인용을 새 깨진 인용으로 다시 셌다. 측정으로 규칙을 확인했다 — fenced block은 `strip_fenced_blocks`(`:83`)가 떼어내므로 위 코드 블록의 인용은 세지 않고, 검사 대상은 **inline span**(`_SPAN` `:74`)뿐이다. 그래서 틀린 꼴의 인용은 코드 블록 안에만 남겼다.

**원인은 순서다**: r3 작업에서 래칫을 돌린 **뒤에** 이 두 문단을 썼다. 그래서 직전 코멘트의 "인용 래칫 PASS"는 **그 두 줄을 포함하지 않은 상태**의 측정이었다 — 통과를 보고한 명령이 보고 대상의 최종 상태를 보지 않았다. 카드 261에서 caller sweep을 `head`로 자른 것과 같은 모양의 실수다: 측정이 대상의 전부를 덮는지 확인하지 않았다.

baseline은 **늘리지 않았다**(새 발명을 floor로 올리지 않는다). 문서 두 줄을 고쳐서 닫았고, CI와 같은 명령으로 재측정했다:

```
python tools/check_doc_path_citations.py --ratchet --base-ref 9e9a551cd25b9a237d5d439c317854d927a5640d
PASS check_doc_path_citations --ratchet: 290 broken citation(s), all in baseline, none stale, floor unchanged.   exit 0
python -m pytest tests/test_check_doc_path_citations.py -q   ->  20 passed, 1 skipped
```

(한 skip은 Windows에서 symlink 생성 권한이 없어서이고 이 수정과 무관하다.)
