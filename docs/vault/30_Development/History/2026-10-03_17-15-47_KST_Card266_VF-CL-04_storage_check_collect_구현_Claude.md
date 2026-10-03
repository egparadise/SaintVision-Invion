---
doc_id: "HISTORY-CARD266-VF-CL-04-STORAGE-CHECK-COLLECT-20261003"
title: "카드 266 — 서명된 폴더 점검을 돌리는 제품 경로를 설계대로 구현했다. ledger 응답이 쓰기와 같은 transaction에서 커밋되고, 저장된 응답은 지금 권한이 있는 주체에게만 돌아간다"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-03T17:15:47+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "9e9a551c"
task_ids: ["S12-ST", "S12-DB", "S02-ST"]
tags: ["vf-cl-04", "storage-check", "idempotency", "concurrency", "replica-repair", "claude"]
---

# 카드 266 — VF-CL-04 storage check 실행 경로 구현

## 0. 한 줄

`#358`(카드 263) 설계가 Codex r8 승인(`e14aa8ce`)이고 **그 설계가 구현 계약**이었다. 사슬은 전부 있었고 **그것을 돌리는 것이 없었다** — `StorageSampleStore`를 생성하는 코드가 저장소 전체에서 시험 한 곳뿐이었고, 그래서 AC-12 인수 항목 `contributed-folders-checked`가 폴더 0개일 때 `PASS`, 1개부터는 영원히 `FAIL`이었다. 이제 **공개 write surface 하나**(`POST /v1/projects/{project}/runs/{run_id}/storage-samples`)가 세 단계로 그것을 돌리고, **ledger 응답이 다섯 쓰기와 같은 transaction에서 커밋되며**, **저장된 응답은 지금 권한이 있는 주체에게만** 돌아간다. 시험 **39**(새 route 6 + collect 17 + replica 16), 변이 **10/10 사살**, migration **0건**(`0065` 비움).

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

kernel transaction은 **network I/O를 금지한다**(`db.py:211`). 그래서 node 호출을 transaction 안에 둘 수 없고, node 응답이 `observedAt`과 **서명**을 담으므로 **두 요청이 같은 봉투를 받지 않는다**. ledger 응답이 쓰기와 다른 transaction에 있으면 같은 key 동시 요청 둘 중 하나가 **`IDEM-0001`**을 받는다 — 멱등이 막아야 할 바로 그 일이다.

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

## 5. 실제 검증 증거

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

둘을 더한 뒤 **10/10**이다.

## 6. migration

**없다.** `0065`는 비워 둔다. 설계 r4·r8이 정한 그대로 — `storage_checks`의 `mismatch_count <= sampled_count`는 `0005`에 이미 있고, `request_id`는 **파생**이라 열이 필요 없고, repair route의 project 결속은 `0062`의 열에 조건을 더하는 질의의 일이다.

## 7. 남은 문제 / 이 카드 밖

* **주기성은 닫지 않았다.** `pilot.py`의 `stale_after_days=7`보다 자주 누군가 요청해야 하고 그 "누군가"는 **운영자**다. 자동 주기는 principal 위임 설계가 선행이고 별 카드다(설계 §5-1-3가 그렇게 적었다).
* **운영 측 선행 둘**: node agent의 `--storage-policy` 승인 파일과, API process의 `storageSample` mTLS 설정. 둘 중 하나라도 없으면 **503이고 행을 적지 않는다** — "관측 불가"를 건강으로 바꾸지 않는다.
* `contributed-folders-checked`의 **빈 모집단 PASS**(설계 §5-1-4)는 수집기 쪽 변경이고 이 카드에 넣지 않았다 — 설계가 구현 순서를 §5-1 → §5-3 → §5-2로 권했고 이 카드는 그 첫째·둘째다.
* **고난도 동시성**이므로 검토는 Codex다.

## 8. 다음

exact-head Backend/Core/security green 뒤 **'검토 기준 head' 코멘트 1회**. 검토는 Codex.
