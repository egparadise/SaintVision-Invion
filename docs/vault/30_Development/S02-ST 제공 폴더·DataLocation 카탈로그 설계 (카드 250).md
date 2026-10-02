---
doc_id: "CLAUDE-S02-ST-CATALOG-DESIGN-250"
title: "S02-ST 제공 폴더·DataLocation 카탈로그 설계 (카드 250) — 측정 먼저: 카탈로그 표·route·`inv://` resolver·시험은 **이미 있고**(`src/saintvision/api/v1/storage.py:81~284`, `data_locations`·`storage_contributions` FORCE RLS, 통합 8 + 계약 3 case) 정본 재채점은 S02-ST를 **75**로 적는다(v1.7 정정). 외부 전제 없이 닫을 수 있는 공백은 셋이다 — (1) 카탈로그에 **project 차원이 없다**(두 표에 `project_id` 열이 없고 RLS 정책이 tenant 전용이라 AC-02의 '다른 project 정보 접근 차단'을 DB가 강제하지 못한다), (2) **읽기는 소유자 범위인데 쓰기는 tenant 범위**다(`activate_contribution`·`revoke_contribution`이 소유자를 보지 않는다), (3) **kernel(inv) 쪽 카탈로그 읽기 표면이 없다**. 이 문서는 그 셋의 계약·migration(0062 예약)·RLS·인증 실패 기록·시험 계획만 담는다. 구현 0줄, 브라우저 화면은 Gemini 몫. **r2(Codex r1)**: 거부 기록이 있는 앱은 core 하나뿐이므로(kernel의 `DomainError` handler는 `problem()`만 반환한다) 새 읽기 표면을 **core 앱의 `/v1/projects/{project_id}/storage/…`** 로 확정하고 계약도 core 세대에 둔다, project GUC는 `require_project_access` 통과 뒤 의존성 계층이 세운다, RLS 교체는 **Phase 2로 분리**한다(0062는 열만 더하고 정책을 바꾸지 않으므로 가역), `kind`는 정본 **4값**에 그대로 결속한다. **r3(Codex r2)**: `project_id`를 만드는 제품 경로가 **0건**이므로(제공 폴더 등록은 스스로 tenant 전체라고 적고 location을 만드는 제품 호출자는 없다) 결속을 **`data_locations` 한 표**로 줄이고 **그 열을 채우는 project 범위 쓰기 route를 같은 카드에 묶었다**, 읽기 권위는 `canRequest`∨`canApprove`·쓰기는 `canRequest`·활성화/철회는 **행 소유자 하나**로 확정했다(archived project는 boolean이 false이므로 예외 부재를 승인으로 쓰지 않는다), census repin이 필요하다던 문장은 **거짓이어서 정정했다**. **r4(Codex r3)**: 쓰기 route가 **contribution 소유자**를 보게 계약으로 고정하고(존재 신탁 없는 같은 거부 + 자기 `audit_action`으로 감사), 요청 계약을 `kind`별 `oneOf`로 strict하게 적고 `projectId`를 본문에서 금지하고, idempotency를 tenant+경로 project+operation+canonical body에 결속해 같은 key·같은 body는 exact replay·같은 key·다른 body는 `GRAPH-0002` 409로 고정했다(route의 `TRANSLATION` 표가 내부 `GRAPH_IDEMPOTENCY_CONFLICT`를 그것으로 바꾼다 — `IDEM-0001`은 kernel 계열이라 쓰지 않는다). **r5(Codex r4)**: 소유자·`active` 검사를 **`FOR UPDATE`로 잠근 행에서** 하도록 잠금 순서 아홉 줄을 정본으로 적고(READ COMMITTED에서 단순 read는 철회 경쟁을 막지 못한다) 거부 감사를 **`CanonicalProblem.audit_action`** 에 담는 실행 형태로 고쳤고, `Idempotency-Key`를 **필수**로(`_require_idempotency_key`, 없으면 `VAL-REQUEST` 422) 하고 translation-table coverage 시험을 더했으며, T14·T15의 기대를 같은 fixture 순서와 행 수로 명시했다. **r6(Codex r5)**: 내부 `RES-CONTRIBUTION-NOT-FOUND`는 `^[A-Z]+-[0-9]{4}$`를 통과하지 못하므로 공개 문제를 `legacy_not_found_problem`의 **`RES-0004` 404 strict body + `audit_action`**(dataclasses.replace)으로 만들도록 변환을 고정하고, 권한을 **세 번**(1차 · advisory lock 뒤 replay 전 · 행 잠금 뒤 삽입 직전) 재검사하게 하고(두 선례의 같은 규율, 재검사는 `bounded_lock_wait` 안), T18을 **두 schedule**로 쪼갰다"
version: "1.5.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-10-03T06:22:56+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "ab2829d955398d686bc8b96b1f12b82c1914df10"
task_ids: ["S02-ST"]
tags: ["S02-ST", "AC-02", "storage-catalogue", "data-location", "rls", "design", "claude"]
---

# S02-ST 제공 폴더·DataLocation 카탈로그 설계 (카드 250)

**구현 0줄.** 이 문서는 train 32 후보(`coord/train32b-ci-0444`)에서 **측정한 것**과, 그 위에서 **외부 전제 없이** 닫을 수 있는 범위의 계약·표·RLS·인증 실패 기록·시험 계획을 적는다. 브라우저 화면은 Gemini 몫이므로 **API·계약까지만** 적는다. 이미 있는 대응표 [[S02-BE·S02-ST Evidence 대응표]]와 같은 원칙이다 — 있는 것을 `path:line`으로 대응하고 **공백만** 골라낸다.

## 0. 결론 먼저

1. **카드가 적은 "v1.14에서 50에 묶인 S02-ST"는 정본과 다르다.** [[2026-09-28 48 task 진행률 재채점]]은 **v1.7(카드 168)에서 S02-ST를 50 → 75로 정정**했고 그 뒤 판에서도 75다(그 문서 §4-4-1의 행: "`S02-ST` | Claude | 50 | **75** | **+25** | v1.7 정정"). v1.14(카드 249)가 다시 센 행도 S08-BE·S11-BE 둘이고 S02-ST는 건드리지 않았다. **그래서 이 카드의 목표는 50 → 75가 아니라 75의 내용을 넓히고 100의 조건을 분리하는 것**이다.
2. **VF-CL-01("storage catalog/API, migration, DataLocation 재사용")은 이미 산출물이 있다** — [[57.81퍼센트 이후 단일 가상 컴퓨터 보강 로드맵]] §VF-CL 표의 그 줄이고, 구현·시험·History가 tree에 있다(§1). CLAUDE.md의 우선순위 첫 항목을 "없으니 만든다"로 읽으면 틀린다.
3. **외부 전제 없이 닫을 수 있는 공백은 셋**이다 — project 차원 부재, 읽기/쓰기 범위 비대칭, kernel 쪽 읽기 표면 부재(§2-3). 셋 다 우리 코드 안이고 사용자·장비·IdP를 요구하지 않는다.
4. **100은 이 카드로 닫히지 않는다** — S02-ST의 `evidence_required`는 "실제 API·브라우저 여정·인증 실패 기록"이고 셋 다 관측 기록이 있는데(§2-1), rubric의 100이 요구하는 **필수 운영 인수**가 U2~U6(실 IdP·운영 CA·DNS·물리 5노드·Storage 제품 값)에 묶여 있다(§2-2).

## 1. 측정 — train 32 후보 `ab2829d9`에서 무엇이 있고 무엇이 없는가

### 1-1. 있는 것

| 무엇 | 위치 | 비고 |
|---|---|---|
| 제공 폴더 등록 | `src/saintvision/api/v1/storage.py:80-85`(데코레이터 `:80`, 경로 `:81`, 핸들러 `:85 register_contribution`) `POST /v1/storage/contributions` | `Idempotency-Key` 직렬화(`:94`), 경로 정규화 |
| 활성화 / 철회 | `:181` `POST …/{contribution_id}/activation`, `:196` `DELETE …/{contribution_id}` | 철회는 **행을 지우지 않는다**(`src/saintvision/services/storage.py:106-119`의 주석: 무엇이 참조됐는지의 기록을 지우지 않는다) |
| 제공 폴더 목록 | `:212` `GET /v1/storage/contributions` | tenant + **소유자** 범위, cursor 페이지네이션 |
| DataLocation 목록 | `:234` `GET /v1/storage/locations` | tenant + 소유자 + `contributionId`·`kind`·`readyOnly` 필터 |
| `inv://` 해석 | `:260` `GET /v1/storage/resolve` → `src/saintvision/services/resolver.py:37 resolve_location`, 파서 `src/saintvision/storage/pathsafe.py:289 parse_uri`(`:272 ParsedUri`) | **바이트 접근을 주지 않는다**(route docstring), 미발급 URI는 존재 신탁 없이 404 |
| 복제 상태 | `:284` `GET /v1/storage/replica-status` | "기록된 상태"이고 현재 바이트 가용성이 아님을 docstring이 적는다 |
| 표 | `storage_contributions`·`data_locations` (`src/saintvision/db/models/storage.py:38`, `:102`) | `data_locations`는 `(tenant_id, location_id)`·`(tenant_id, uri)` unique, `(tenant_id, contribution_id)` FK, `(tenant_id, kind)` index |
| RLS | `migrations/versions/0001_s02_baseline.py:455-477` | 두 표 모두 `TENANT_SCOPED` → `ENABLE` + **`FORCE ROW LEVEL SECURITY`** + `…_tenant_isolation` 정책(`USING/WITH CHECK tenant_id = <setting>`) |
| 계약(응답) | `contracts/data-location-response.schema.json`(required `locationId`·`contributionId`·`uri`·`kind`·`relativePath`·`byteSize`·`ready`, `additionalProperties:false`), `contracts/data-location-page-response.schema.json`, `contracts/contribution-{request,response,page-response,registration-response}.schema.json` | 요청 계약의 `mode`는 `^(read_only\|read_write)$` |
| 경로 안전 | `src/saintvision/storage/pathsafe.py:163/182/212`, `src/saintvision/storage/readroot.py:109 ReadRoot` | 정규화·junction·범위 밖 거부 |
| 시험 | `tests/integration/test_storage_catalog_api.py` **8 case**, `tests/core/test_storage_list_response_contract.py` **3 case**(v1.7이 75의 근거로 센 파일) | 소유자 범위·비소유 비공개·revocation 뒤 숨김·위조 cursor·위조 식별자·suspension |
| 인증 실패 기록 | `src/saintvision/api/app.py:135 record_denial_out_of_band` — **거부를 쓰는 유일한 자리**(그 docstring이 그렇게 선언한다), `src/saintvision/services/audit.py:128` | fail-closed(쓰기 실패 시 500으로 끝나고 거부를 성공으로 위장하지 않는다), tenant 없는 거부는 `0047_audit_events_isolation.py:116 public.record_auth_denial`(SECURITY DEFINER) |
| 과거 산출물 | [[2026-09-15_03-10-00_KST_VF-CL-01_Claude_DataLocation재사용경계와카탈로그시험]] | VF-CL-01의 DataLocation 재사용 경계·카탈로그 시험 |

### 1-2. 없는 것 (측정으로 확인)

| # | 없는 것 | 어떻게 확인했나 |
|---|---|---|
| **M1** | **두 표에 `project_id` 열이 없다**(r3: 그래서 결속은 `data_locations` 한 표에만 둔다 — §3-2-1) | `src/saintvision/db/models/storage.py`의 `StorageContribution`(`contribution_id`·`tenant_id`·`node_id`·`declared_path`·`normalized_path`·`mode`·`status`·`capacity_bytes`·`available_bytes`·`registered_by_user_id`·`registered_at`·`revoked_at`·`version`)과 `DataLocation`(`location_id`·`tenant_id`·`contribution_id`·`uri`·`kind`·`relative_path`·`byte_size`·`checksum_sha256`·`verified_at`·`ready`·`retention_pinned_until`·`catalogued_at`·`version`) 열 전수 |
| **M2** | **project 범위 RLS 정책이 없다** | 0001의 정책은 `tenant_id = <setting>` 한 조건뿐이다(§1-1). 그래서 **AC-02의 "다른 project 정보 접근 차단"을 카탈로그에서는 DB가 강제하지 않는다** — Node 쪽은 kernel의 project route가 따로 강제한다 |
| **M3** | **쓰기 경로가 소유자를 보지 않는다** | `src/saintvision/services/storage.py:94 activate_contribution`·`:106 revoke_contribution`의 인자는 `tenant_id`·`contribution_id`뿐이고 `_load_contribution`도 그 둘로 찾는다. 읽기는 `:250`·`:282`에서 `registered_by_user_id == reader_user_id`를 건다. route에도 권한 의존이 없다(`src/saintvision/api/v1/storage.py:37 APIRouter(prefix="/v1", tags=["storage"])`에 `dependencies=` 없음, `src/saintvision/api/app.py:222 include_router(storage_router.router)`) → **같은 tenant의 다른 주체가 남의 제공 폴더를 활성화·철회할 수 있다** |
| **M4** | **kernel(`services/control-plane/src/inv/`)에 카탈로그 읽기 표면이 없다** | kernel의 storage 표면은 `services/control-plane/src/inv/app.py:517 GET /v1/projects/{project}/runs/{run_id}/storage-samples/{request_id}` 하나(관측 표본)이고 `services/control-plane/src/inv/storage_view.py`·`services/control-plane/src/inv/storage_commit.py`가 그 뒤다. `DataLocation` 목록·resolve는 kernel에 없다 |
| **M5** | **계약의 `kind`가 열린 문자열이다**(정본은 넷인데 계약이 그것을 적지 않는다) | `contracts/data-location-response.schema.json`의 `kind`는 `{"type":"string"}`뿐이다. **정본 집합은 코드에 있다** — `src/saintvision/db/models/storage.py:32`의 `LOCATION_KINDS = ("dataset", "model", "artifact", "workspace")`와 같은 파일 `:117-120`의 `CheckConstraint("kind IN ('dataset','model','artifact','workspace')", name="kind_allowed")`, 그리고 `src/saintvision/storage/pathsafe.py:236-266`의 namespace별 grammar다. **r1은 이 상수를 놓치고 "확인되는 값은 `model` 하나"라고 적었다 — r2에서 정정한다**(§3-1-1) |
| **M6** | **거부 기록에 project 표적이 없다** | `src/saintvision/api/app.py:133-136`은 경로의 `project_id`가 올바른 식별자일 때만 `("project", project_id)`를 표적으로 적는다. 카탈로그 route 경로에는 `project_id`가 없으므로 카탈로그 거부는 **action·reason_code만 남고 표적이 비어 있다** |

## 2. S02-ST의 75/100 요구 증거 분해

`docs/task-registry.json`의 S02-ST: scope **제공 폴더·DataLocation 카탈로그**, `evidence_required` **실제 API·브라우저 여정·인증 실패 기록**, `acceptance_ids` **AC-02**. AC-02 기준(`outcomes` OUT-02): **허용 Node 등록·조회 성공, 토큰 재사용 차단, 다른 project 정보 접근 차단**.

### 2-1. 이미 관측된 것 (75의 내용)

| 요구 증거 | 관측 | 근거 |
|---|---|---|
| 실제 API | 카탈로그 route 6개 + 통합 8 case·계약 3 case, hosted Backend | §1-1, [[S02-BE·S02-ST Evidence 대응표]] §2.4·§2.5 |
| 브라우저 여정 | `test_browser_real_catalogue_owner_scope_and_revocation`(카탈로그 소유 범위·revocation) | 그 대응표 §2.5의 desktop-browser 인용 |
| 인증 실패 기록 | 중앙 거부 기록 경로와 그 시험, `audit_events` RLS(0047) | §1-1, 그 대응표 §2.3 |

### 2-2. 100을 막는 것 — 전부 외부 (이 카드로 닫히지 않는다)

U2 실 IdP·U3 운영 CA·U4 DNS·U5 물리 5노드(제공 폴더 실물)·U6 Storage 제품 값(contribution 루트·storage-policy·아카이브 대상). 그 대응표 §3의 E1~E5와 같고, 사용자 몫은 [[사용자 조치 단일 체크리스트]]가 정본이다. **rubric의 100은 "필수 운영 인수"를 요구하므로 코드로는 닫히지 않는다.**

### 2-3. 외부 전제 없이 닫을 수 있는 범위 — 이 설계의 대상

| # | 무엇 | 왜 지금 가능한가 |
|---|---|---|
| **D1** | 카탈로그에 **project 결속**을 준다 — **Phase 1**은 `data_locations`의 열과 앱 계층 경계(0062) **그리고 그 열을 채우는 쓰기 route**, **Phase 2**가 RLS 정책을 tenant+project로 교체한다(M1·M2, §3-2·§3-2-1) | 장비·사용자 입력이 필요 없다. project·member 표는 이미 있다(0001) |
| **D2** | **쓰기 경로를 소유자/역할 범위로** 좁힌다(M3) | 같은 tenant 안의 권한 경계이고 외부 자산이 없다 |
| **D3** | **core 앱에** project 범위 읽기 표면(`/v1/projects/{project_id}/storage/…`)을 둔다 — r1은 kernel에 두자고 했는데 **측정이 그것을 뒤집었다**(kernel에는 거부 기록이 없다, §3-0). M4(kernel 표면 부재)는 사실로 남고 그 해소는 recorder가 선행인 **별 카드**다 | 거부 기록·카탈로그 서비스·표가 모두 core 앱에 있다 |
| **D4** | 계약의 `kind`를 **정본 4값에 결속**하고(이름은 바꾸지 않는다) 두 세대의 계약 경계를 문서화한다(M5) | 계약 파일과 시험만 바뀐다 |
| **D5** | 카탈로그 거부가 **project 표적**을 남기게 한다(M6) | D1·D3이 경로에 project를 들이면 기존 중앙 경로가 자동으로 적는다 |

## 3. 설계안 (구현 0줄 — 이 PR은 이 문서만 담는다)

### 3-0. 어느 앱에 두는가 — **core 앱**으로 확정한다 (r2, Codex F1)

r1의 §3-3은 "kernel route가 생기면 project 표적이 자동으로 남는다"고 적었다. **그것은 틀렸다** — 측정하면 두 앱의 거부 기록이 다르다.

| 앱 | 거부 기록 | 측정 |
|---|---|---|
| **core 앱**(`src/saintvision/`) | **있다.** `src/saintvision/api/app.py:107 _record_denial`이 `create_app` 안의 closure이고, 그 docstring이 **"The single audit point for a refused request"** 라고 선언한다. 두 예외 handler(legacy `InvError`·정본)가 그것을 부르고 **route는 스스로 기록하지 않는다**(route는 거부가 되돌리는 transaction 안이다). 감사 범주는 `:105 DENIAL_CATEGORIES = ("AUTH", "SEC")` | `src/saintvision/api/app.py:104-150` |
| **kernel**(`services/control-plane/src/inv/`) | **없다.** `DomainError` handler는 `problem(error, request.state.trace_id)` 하나를 반환하고 감사에 아무것도 쓰지 않는다 | `services/control-plane/src/inv/app.py:267-269` |

그래서 **읽기 표면을 kernel에 두면 거부 기록이 사라진다** — AC-02의 세 번째 증거("인증 실패 기록")를 새 표면에서 잃는다. kernel에 recorder를 새로 만드는 것은 kernel의 감사 모델·AC-11 definer 집합을 건드리는 **별 카드**다.

**확정**: 새 project 범위 카탈로그 읽기 표면은 **core 앱**에 둔다. 경로는 **`/v1/projects/{project_id}/storage/locations`**(읽기·쓰기)와 `…/locations/resolve`·`…/locations/replica-status`다 — **contribution 경로는 두지 않는다**(r4 정정: 제공 폴더는 tenant 전체이고 project로 묶지 않는다, §3-2-1). 근거는 셋이다 — (1) 카탈로그 서비스·표·기존 route가 모두 core 앱이다, (2) 거부 기록이 거기 있다, (3) recorder가 **경로의 `project_id`만** 표적으로 적으므로(`src/saintvision/api/app.py:133-136`) 이 경로 모양이면 **표적이 코드 변경 없이 남는다**(M6 해소).

**그 결과 r1의 계약 제안 위치도 바뀐다** — route가 core 앱이면 응답 계약은 **core 세대**(`contracts/*.schema.json`, 기존 카탈로그 응답과 같은 자리)다. `contracts/v1alpha1/core.schema.json`은 kernel 계약이므로 **건드리지 않는다**. r1 §3-1이 v1alpha1에 적자고 한 것은 kernel route를 가정한 결과였고, 그 가정이 측정으로 깨졌다.

### 3-1. 계약 추가안 (r2 정정 — core 세대에 둔다)

기존 파일(`contracts/data-location-response.schema.json` 등)은 **그대로 두고**, project 범위 표면의 응답만 새 파일로 더한다. 이름·필드는 제안이고 Codex 검토 대상이다.

```
contracts/project-data-location-response.schema.json        (DataLocationResponse + projectId)
contracts/project-data-location-page-response.schema.json   (items + nextCursor)

(r3: contribution 쪽 파일은 두지 않는다 — 제공 폴더는 tenant 전체이고 project로 묶지 않는다(§3-2-1).
 location 응답이 contributionId 를 참조로 들고 있으므로 화면은 그것으로 폴더를 가리킨다.)

공통 규칙 (기존 파일과 같게)
  additionalProperties: false
  required 는 기존 required + "projectId"
  kind 는 기존 이름을 유지한다 (§3-1-1)
```

`kind`를 `locationKind`로 바꾸자던 r1의 제안은 **철회한다** — 그 제안은 kernel 계약(`kind`가 문서 종류)에 넣을 때만 필요했고, core 세대에서는 `kind`가 이미 **위치 분류**라는 한 가지 뜻으로 쓰인다. 이름을 바꾸면 기존 소비자·시험·DB CHECK 이름(`kind_allowed`)과 어긋난다.

#### 3-1-1. `kind` 열거는 **정본 4값에 정확히 결속한다** (r2, Codex F3)

r1은 "제품이 쓰는 값은 최소 `model`이 확인된다"고 적고 열거를 측정으로 정하자고 했다. **그 측정은 이미 코드에 있었고 내가 모듈 상수를 놓쳤다.** 정본은 넷이다.

| 권위 | 값 |
|---|---|
| `src/saintvision/db/models/storage.py:32` | `LOCATION_KINDS = ("dataset", "model", "artifact", "workspace")` |
| 같은 파일 `:117-120` | `CheckConstraint("kind IN ('dataset','model','artifact','workspace')", name="kind_allowed")` — **DB가 이미 강제한다** |
| `src/saintvision/storage/pathsafe.py:236-266` | `build_uri`의 문법이 `dataset`·`model`(`name@version`)과 `artifact`(`run_id`+`artifact_id`)와 `workspace`를 **각각 다른 grammar**로 만들고, `:289 parse_uri`가 그 역이다 |

**확정**: 새 계약의 `kind`는 `enum: ["artifact","dataset","model","workspace"]`로 **그 넷 그대로** 적는다(좁히지 않는다). 그리고 **열거가 세 자리와 같은지 시험으로 고정한다** — 계약 파일, `LOCATION_KINDS`, DB CHECK가 서로 어긋나면 실패한다(§3-4의 T2). 넷 중 하나가 늘면 세 자리를 같은 PR에서 함께 올린다.

### 3-2. 표와 RLS — **2단계로 쪼갠다** (r2, Codex F2)

r1은 0062 하나에서 열을 더하고 정책을 교체하려 했다. **측정하면 그럴 수 없다.**

| 측정 | 값 |
|---|---|
| session이 세우는 GUC | **둘뿐**이다 — `TENANT_GUC = "inv.tenant_id"`(`src/saintvision/db/session.py:27`), `ACTOR_GUC = "inv.user_id"`(`:43`). 둘 다 `SET LOCAL`로 **열린 transaction 안에서만** 세우고(`:55-69`, `:78-99`), 값은 **inline 전에 검증**한다(tenant는 `uuid.UUID(value)`) |
| 누가 세우는가 | 의존성 계층이다 — `src/saintvision/api/deps.py:72`(`get_session`)·`:91`(`get_write_session`)이 **검증된 principal의 tenant**로 `tenant_scope`를 연다. "There is no code path that sets it at session level"가 그 docstring이다 |
| project GUC | **없다** |
| 기존 `/v1/storage` route | **project selector가 없다**(§1-1의 여섯 route 전부) |

그래서 **정책을 tenant+project로 바꾸는 순간, project GUC를 세울 수 없는 기존 reader는 전부 0행**이 된다. 단계로 나눈다.

**Phase 1 — `0062` (이 설계가 예약한 번호, 구현 카드가 만든다)**
- **`data_locations`에만** `project_id` 열을 **nullable**로 더하고 `(tenant_id, project_id)` → `projects` 참조를 건다. **`storage_contributions`에는 열을 더하지 않는다** — 이유는 §3-2-1이다(r3 정정: r1·r2는 두 표에 더하려 했다).
- **정책은 바꾸지 않는다.** 기존 `…_tenant_isolation`이 그대로 남는다.
- 새 project 범위 route가 **앱 계층에서** `WHERE project_id = :project`를 걸고, `project_id IS NULL` 행은 **어떤 project 조회에도 포함하지 않는다**(fail-closed).
- 기존 owner 범위 route는 **그대로 동작한다** — 정책이 안 바뀌었으므로 회귀가 없다.

**Phase 1의 권위 주체**(Codex F2의 질문): 새 route는 **먼저** `project_service.require_project_access(session, tenant_id=…, project_id=…, user_id=…)`를 부른다(`src/saintvision/services/projects.py:204-223` — `project_members`를 읽고, **존재 여부를 구분하지 않는 같은 거부**를 `AUTH-0030`으로 낸다). **그 검사를 통과한 뒤에만** 새 `project_scope(session, project_id)`가 `PROJECT_GUC = "inv.project_id"`를 `SET LOCAL`로 세운다 — 값은 `is_id(project_id, "project")`로 검증한 **경로 값**이고, **호출자가 보낸 쿼리·본문을 직접 넣지 않는다**(`tenant_scope`·`actor_scope`가 세운 규율과 같다. `ACTOR_GUC`의 docstring이 그 이유를 적는다: 인자는 호출자의 주장이다).

#### 3-2-1. `project_id`를 **만드는** 제품 경로 — 없다. 그래서 무엇이 그것을 정하는지 확정한다 (r3, Codex r2 F2-1)

측정부터 적는다. **카탈로그의 쓰기 쪽에는 project가 없고, locations 쪽은 제품 호출자 자체가 없다.**

| 측정 | 값 |
|---|---|
| 제공 폴더 등록의 의미 | **tenant 전체**다. `src/saintvision/api/v1/storage.py:114-117`이 그렇게 적는다 — "Registering a contribution is tenant-wide: a folder belongs to a node, not a project." idempotency 기록도 `project_id=None`이다(`:104`, `:117`, `:175`) |
| 요청 계약 | `contracts/contribution-request.schema.json`의 required는 `nodeId`·`declaredPath`뿐이고 project 필드가 **없다**(`additionalProperties:false`라 보내도 거부된다) |
| 등록 서비스 | `src/saintvision/services/storage.py:47-91 register_contribution`에 project 인자가 **없다** |
| **location을 만드는 제품 경로** | **0건**이다. `DataLocation(...)`을 만드는 자리는 `src/saintvision/services/storage.py:167` 하나이고 그 함수(`:122 catalogue_location`)를 부르는 것은 **시험뿐**이다(`tests/test_storage_catalog.py` 5곳). route·CLI·scheduler 0건 |

즉 0062가 열을 더해도 **아무도 그 열을 채우지 않는다** — Codex r2의 지적대로 새 route는 영구히 빈 결과가 된다. 이 모양은 v1.13·v1.14가 `S08-BE`에서 센 것과 같다(API와 시험은 있고 **제품 진입점이 0건**). 그래서 이 설계는 **열을 더하는 카드와 그 열을 채우는 카드를 같은 카드로 묶는다**.

**확정 1 — 결속의 자리는 `data_locations`다.** 제공 폴더는 제품이 스스로 "node의 것이고 project의 것이 아니다"라고 적었으므로 그 의미를 바꾸지 않는다. project가 붙는 것은 **그 폴더 안의 항목(location)** 이다. 그래서 `storage_contributions`에는 열을 더하지 않고, project 범위 읽기 표면도 **contribution 목록을 project로 주지 않는다** — contribution은 `contributionId` **참조**로만 나타난다(§3-1의 계약도 그에 맞춰 location 쌍으로 줄인다).

**확정 2 — project는 서버가 경로에서 정한다(본문에서 받지 않는다).** 구현 카드는 project 범위 **쓰기** route를 같이 만든다:

```
POST /v1/projects/{project_id}/storage/locations        (core 앱, §3-0)
  1. require_project_access(...)            -> AUTH-0030, 존재 신탁 없음
  2. permission["canRequest"] 가 true 인지 확인            (§3-4-2)
  3. project_scope(session, project_id)     -> SET LOCAL inv.project_id  (검증된 경로 값)
  4. catalogue_location(..., project_id=<경로 값>)
```

- `project_id`는 **경로 값**이고, 본문에 project 필드를 두지 않는다(`additionalProperties:false`가 그것을 거부한다).
- 그 route가 없는 동안에는 **읽기 route도 내보내지 않는다** — 빈 표면을 먼저 만들지 않는다.
- contribution이 tenant 전체이므로, 이 route는 **그 contribution이 자기 tenant의 것이고 `active`인지**를 기존 `catalogue_location`의 검사로 확인한다(`src/saintvision/services/storage.py:145-147`의 `status != "active"` 거부).

**확정 3 — 이미 있는 행의 결속은 별도 route이고, 선택이다.** 제품에는 location 행을 만드는 경로가 없으므로 **지금 tree에 결속할 과거 행이 없다**. 파일럿 DB에 행이 있다면 `POST /v1/projects/{project_id}/storage/locations/{location_id}/assignment`를 둔다 — **`canAdminister`(owner 하나)** 를 요구하고, `NULL → project` **한 방향만** 허용하며(project → 다른 project 재할당 금지), 감사에 남는다. 이것은 **사용자 데이터가 있을 때만** 만든다(없는 것을 위해 미리 만들지 않는다).

#### 3-2-2. 쓰기 route는 **contribution 소유자**를 본다 (r4, Codex r3 F1)

측정: `catalogue_location`은 **소유자를 보지 않는다.**

| 무엇 | 측정 |
|---|---|
| contribution 적재 | `src/saintvision/services/storage.py:300-304 _load_contribution`은 **tenant만** 본다(`tenant_id` 불일치면 `RES-CONTRIBUTION-NOT-FOUND`) |
| 그 뒤 검사 | `:142-146`의 `status != "active"` 거부와 `byte_size < 0` 거부뿐이다 — `registered_by_user_id`는 **어디에도 없다** |
| 읽기 쪽 | 같은 파일 `:250`·`:282`가 `registered_by_user_id == reader_user_id`를 건다 |

즉 §3-2-1의 쓰기 route를 project `canRequest`만으로 열면, **같은 tenant의 operator가 남의 contribution id로 그 폴더의 항목을 자기 project에 결속·노출**할 수 있다(Codex r3 F1). 읽기보다 쓰기가 느슨한 M3와 같은 모양이 카탈로그 경로에서 한 번 더 나온다.

**확정 — 소유자 검사를 계약으로 고정한다.** `POST /v1/projects/{project_id}/storage/locations`의 순서는 이렇게 고정한다:

```
 1. _require_idempotency_key(header)              -> 없거나 형식 위반이면 VAL-REQUEST 422 (§3-2-3)
 2. require_project_access(...)                   -> AUTH-0030, 존재 신탁 없음        [1차]
 3. permission["canRequest"] 가 true 인지 확인                                        [1차]
    -- 여기서 끝내지 않는다. 아래 두 번을 더 본다(r6).
 4. serialise_idempotent_write(... project_id=<경로 값>)   -- 자원 행보다 **먼저**
 5. require_project_access(...) + canRequest **재검사**                               [2차]
    -- advisory lock 을 기다리는 동안 membership revoke·project archive 가 커밋될 수 있다.
       replay 판단보다 **먼저** 본다: 권한을 잃은 호출자에게 저장된 성공을 되돌려주지 않는다.
 6. replay_or_reserve(...)                         -> 저장된 응답이 있으면 그대로 반환
 7. contribution 행을 **FOR UPDATE 로 잠그고**, 그 **잠긴 행에서**
      tenant_id == principal.tenant_id
      registered_by_user_id == principal.user_id
      status == "active"
    세 조건을 검사한다. 하나라도 아니면 **같은 거부**를 낸다(§3-2-2-1)
 8. require_project_access(...) + canRequest **재검사**                               [3차]
    -- 행 잠금을 기다리는 동안에도 같은 일이 일어날 수 있다. **삽입 직전**에 본다.
 9. project_scope(...) -> SET LOCAL inv.project_id   (검증된 경로 값)
10. catalogue_location(..., project_id=<경로 값>)   -- 같은 transaction, 같은 잠긴 행
11. store_idempotent_response(...)
```

**세 번 보는 이유는 이 저장소가 이미 적어 둔 것과 같다**(r6, Codex r5 F2). `src/saintvision/api/v1/eval_runs.py:11-14`가 자기 route에 대해 **"the grade is `canApprove` … and it is re-checked **immediately before** the adapter runs -- not only at the start of the request. A membership revoked while the request was waiting for its idempotency lock must not be able to buy anything"** 라고 적고, `src/saintvision/api/v1/model_release.py:414-423`은 그 구조를 세 span으로 적는다 — **"one atomic transaction that re-checks the permission it no longer holds and re-reads the ledger under the serialisation point"**. 이 route는 돈을 쓰지 않지만 **다른 project에 데이터를 노출**하므로 같은 규율을 받는다.

**재검사는 반드시 `bounded_lock_wait` 안이다** — `effective_permission`이 user 행을 **`FOR SHARE`** 로 읽으므로(`src/saintvision/services/settings.py:162`의 `with_for_update={"read": True}`), 누군가 그 행에 `FOR UPDATE`를 들고 있으면 한계 없이 기다린다. 두 선례가 같은 이유로 `bounded_lock_wait`를 건다(`eval_runs.py:230-240`, `model_release.py:427-432`). 초과는 `SYS-0001/503`이다.

**잠금 순서는 이 아홉 줄이 정본이다**(r5). 기존 규율과 어긋나지 않는다 — `serialise_idempotent_write`의 docstring이 "Every write route takes this lock **before** any resource row"로 그 순서를 이미 고정하고 있고(`src/saintvision/api/deps.py:105-135`), 이 route의 자원 행은 contribution 하나다.

- **거부의 모양 (r6에서 정정)**: 소유자가 아닌 경우와 존재하지 않는 경우를 **구분하지 않는다**. 다만 **내부 코드와 공개 코드가 다르다** — r4·r5는 "둘 다 `RES-CONTRIBUTION-NOT-FOUND`로 답한다"고 적었는데 그것을 **그대로 `CanonicalProblem`에 넣으면 `ValueError`** 다. 측정: 공개 코드는 `_CODE = ^[A-Z]+-[0-9]{4}$`(`src/saintvision/api/problem.py:76`)를 `__post_init__`(`:148-150`)에서 강제하므로 `RES-CONTRIBUTION-NOT-FOUND`는 **정규 코드가 아니다**.
- **그래서 변환을 고정한다**: 서비스가 던지는 내부 `InvError(RES_CONTRIBUTION_NOT_FOUND)`를 route가 **공개 문제로 바꾼다**. 그 코드는 이미 `LEGACY_NOT_FOUND_CODES`에 있고(`src/saintvision/api/problem.py:110-118`) `legacy_not_found_problem`(`:197-206`)이 그것을 **고정된 strict body**로 바꾼다 — `CanonicalProblem(RES_NOT_FOUND, 404, "No such resource.", retryable=False)`, 즉 **`RES-0004` 404**(`:94`). 그 helper의 결과에는 `audit_action`이 **없으므로**, route는 `dataclasses.replace(problem, audit_action=<이 route의 bounded action>)`로 그 필드만 더해 raise한다(동등한 명시 생성도 같다). **내부 코드는 `CanonicalProblem` 생성자에 도달하지 않는다.**
- **두 경우의 body가 같다는 것이 신탁 없음의 내용이다** — 비소유자와 없는 id 모두 `RES-0004` 404 `"No such resource."`·`retryable=false`이고, 다른 것은 `traceId`뿐이다.
- **그래도 감사에 남는다**: 그 거부는 `RES` 범주 404이므로 `src/saintvision/api/problem.py:219-229 is_audited_denial`의 첫 규칙(AUTH·SEC 401/403)에 걸리지 않는다. 걸리는 것은 **두 번째 규칙**이고, 그 규칙이 보는 것은 route metadata가 아니라 **`CanonicalProblem.audit_action` 필드**다(`:144`, handler가 `:244-251`에서 `request.state.denial_action`으로 옮긴다). 위 `dataclasses.replace`가 바로 그 필드를 채운다.
- **위임은 지금 만들지 않는다.** project 역할이 소유권을 대신하지 않는다. 위임이 필요해지면 **저장된 허가 행**(예: `storage_contribution_delegations`)과 그 자신의 route·감사로 하고, 그때까지 **소유자 하나**다. 암묵적 위임(역할·project 멤버십)은 금지한다.

**왜 단순 read로는 부족한가 (r5, Codex r4 F1).** 트랜잭션 격리는 READ COMMITTED다. 소유자·`active`를 **잠기지 않은 행**에서 읽으면, 그 읽기와 `catalogue_location` 사이에 **철회가 커밋될 수 있고** `catalogue_location`의 재조회(`src/saintvision/services/storage.py:142-144`)는 그 새 snapshot을 보지만 **두 읽기 사이의 경쟁을 막지는 못한다** — 운 나쁜 교차에서는 철회된 폴더에 location이 생긴다. 그래서 `FOR UPDATE`로 **그 행을 잠근 뒤** 검사하고, 같은 transaction 안에서 삽입한다. 철회 쪽(`:106-119 revoke_contribution`)이 같은 행을 갱신하므로 둘 중 하나는 반드시 기다린다: 철회가 먼저면 잠금 해제 뒤 우리가 `status != "active"`를 보고 거부하고, 우리가 먼저면 철회는 location이 생긴 뒤에 커밋된다(그리고 그것은 **철회가 카탈로그 행을 지우지 않는다**는 기존 의미와 일치한다 — `:108-112`의 주석).

행 잠금은 이 저장소에 이미 쓰는 수단이다(`src/saintvision/services/discovery.py:107`·`:289`·`:405`, `src/saintvision/services/discovery_credentials.py:68`·`:133`의 `with_for_update()`). `storage.py`에는 아직 없다(측정: 0건) — 그래서 **이 route가 그 첫 사용처**다. 대기는 기존 `bounded_lock_wait`의 `lock_timeout` 예산 안이고 초과는 `SYS-0001/503`이다.

**감사의 형태(r5에서 고치고 r6에서 끝냈다).** 실행 형태는 **route metadata가 아니라 `CanonicalProblem`의 필드**이고, 그 문제 객체는 **공개 코드 `RES-0004`로 만든 뒤 `audit_action`만 더한 것**이다 — 위 §3-2-2의 네 줄이 그 변환을 적는다. 시험은 그 거부에서 `audit_events` 행이 **정확히 하나** 생기는지를 본다(T12·T9).

부정 시험은 T12·T13·**T18-a/b/c**(철회 두 schedule)·**T21·T22**(대기 중 권한 소실)다.

**Phase 2 — 별 migration(0063 이후, 별 카드)**
- **모든** reader가 project GUC를 세우게 된 뒤에(기존 owner 범위 route를 project 범위로 옮기거나 폐기한 뒤) 정책을 교체한다:
  `USING/WITH CHECK (tenant_id = current_setting('inv.tenant_id') AND project_id = current_setting('inv.project_id'))`.
- **그때까지 DB 강제는 tenant 하나**이고, project 경계는 **앱 계층 + 시험**이 든다. 이 문서는 그 사실을 숨기지 않는다 — AC-02의 "다른 project 차단"이 **DB 불변식이 되는 시점은 Phase 2**다.
- 전환 중 두 모드를 한 정책에 담는 타협(`project_id IS NULL OR …`)은 **쓰지 않는다** — 그러면 미결속 행이 모든 project에 보인다.

#### 3-2-3. 새 POST의 요청 계약과 idempotency (r4, Codex r3 F2)

**요청 계약** — 새 파일 하나를 더한다. 기존 카탈로그 계약과 같은 규율(`additionalProperties:false`)이고, **`projectId`는 본문에 두지 않는다**(경로에서만 온다 — 그래서 속성에 없고 `additionalProperties:false`가 보낸 것을 거부한다).

```
contracts/project-data-location-request.schema.json
  additionalProperties: false
  required: ["contributionId", "kind", "relativePath", "byteSize"]
  contributionId : string (InvId)
  kind           : enum ["artifact","dataset","model","workspace"]      (§3-1-1 의 정본 4값)
  relativePath   : string (minLength 1)   -- 경로 안전 검사는 서비스가 한다(pathsafe)
  byteSize       : integer, minimum 0                                   (서비스 :145-146 과 DB CHECK 와 같은 하한)
  name, version, runId, artifactId, workspaceId : kind 별로만 허용(아래)

  kind 별 식별자 (oneOf) — src/saintvision/storage/pathsafe.py:242-266 의 build_uri 문법과 1:1
    dataset | model : name + version 필수,  runId·artifactId·workspaceId 금지
    artifact        : runId + artifactId 필수, name·version·workspaceId 금지
    workspace       : workspaceId 필수,       name·version·runId·artifactId 금지
```

`oneOf`를 쓰는 계약은 `contracts/`에 **아직 없다**(측정: 0건). 그래서 이것이 첫 사례이고, 이유는 **URI를 만들 수 없는 요청을 edge에서 거부**하기 위해서다 — 지금은 `build_uri`가 `ValueError`를 던지고 route가 그것을 `VAL-SCHEMA`로 바꾼다(`src/saintvision/services/storage.py:163-165`). 계약이 먼저 거부하면 그 경로가 **문서화된 거부**가 된다.

**idempotency** — 새로 만들지 않고 **이미 있는 두 원시 함수**를 그대로 쓴다.

| 무엇 | 확정 |
|---|---|
| 직렬화 | `serialise_idempotent_write(session, tenant_id=…, endpoint=ENDPOINT, idempotency_key=…, project_id=<검증된 경로 project>)`를 **자원 행보다 먼저** 잡는다 — 그 docstring이 "Every write route takes this lock **before** any resource row"라고 잠금 순서를 고정한다(`src/saintvision/api/deps.py:105-135`) |
| 결속 | `replay_or_reserve(...)`가 `(tenant_id, project_id, endpoint, idempotency_key)`로 조회하고 본문은 `request_digest(payload)`로 비교한다(`:164-205`) → **tenant + 검증된 경로 project + operation + canonical body**에 결속된다. 본문에 project 필드가 없으므로 ledger의 `project_id`는 **경로 값만**이다 |
| `ENDPOINT` | `"POST /v1/projects/{project_id}/storage/locations"` — **식별자 없는 bounded template**(감사 action과 같은 규율) |
| 같은 key·같은 body | 저장된 응답을 **그대로** 돌려준다(status·body 동일). **두 번째 location도, 두 번째 감사 행도 만들지 않는다** |
| 같은 key·다른 body | 서비스 쪽 내부 코드는 `GRAPH_IDEMPOTENCY_CONFLICT`(`src/saintvision/errors.py:141`)이고 **공개되는 코드는 `GRAPH-0002` 409**다(r5 정정) — route가 자기 `TRANSLATION` 표에 `GRAPH_IDEMPOTENCY_CONFLICT: (GRAPH_PRECONDITION, 409, False)`를 적고 `problem.py:258-281 translate`가 그것을 바꾼다. 선례는 `src/saintvision/api/v1/model_release.py:144-150`의 같은 줄이고, `GRAPH_PRECONDITION`은 `src/saintvision/api/problem.py:96`에서 `"GRAPH-0002"`다. **`IDEM-0001`은 kernel 계열이라 쓰지 않는다** |
| 표의 빈칸 | `translate`는 선언되지 않은 코드를 **`SYS-0002` 500**으로 바꾸고 그 docstring이 "A test enumerates the codes each route can reach and requires the table to cover them"이라고 적는다. 그래서 이 route도 **translation-table coverage 시험**을 갖는다(T19) — 선례는 `tests/core/test_eval_run_route.py:660`·`tests/core/test_context_bundle_route.py:365`·`tests/core/test_conformance_status_route.py:953` |
| **key는 필수다** | `Idempotency-Key`가 없으면 진행하는 **legacy 동작을 빌리지 않는다**(r5). `_require_idempotency_key`(`src/saintvision/api/v1/eval_runs.py:131-143`, `model_release.py:130`이 재사용한다)를 **edge에서** 부른다 — `None`이거나 `IDEMPOTENCY_KEY_PATTERN`(`[A-Za-z0-9._:-]{1,128}`, `eval_runs.py:86`)에 맞지 않으면 **`VAL-REQUEST` 422**다. 그 docstring이 이유를 적는다: "Required on every write in this lane (IDEM-1)" |
| exactly-once | 쓰기 route는 `get_write_session`(`src/saintvision/api/deps.py:76-100`)의 **한 transaction** 안이고 `bounded_lock_wait`가 걸린다 → location insert·ledger 기록·감사가 같은 경계에서 커밋되거나 함께 사라진다 |
| key 없음 | **거부**다(위 줄). `replay_or_reserve`가 key 없음을 `None`으로 넘기는 기존 동작은 **이 route에 도달하지 않는다** — edge에서 이미 422로 끝난다. 부정 시험은 T20(없음·빈 값·129자·허용 밖 문자) |

시험은 T14·T15·T16·**T19**(표 커버리지)·**T20**(key 필수)이다.

### 3-3. 인증 실패 기록 경로 (r2 정정)

**새 기록 경로도, 새 SECURITY DEFINER 함수도 만들지 않는다.** route를 core 앱에 두므로(§3-0) 거부는 기존 단일 지점이 적는다.

| 무엇 | 확정 |
|---|---|
| 기록 지점 | `src/saintvision/api/app.py:107 _record_denial` 하나. route는 스스로 적지 않는다 |
| 감사되는 범주 | `AUTH`·`SEC`(`:105`). `require_project_access`의 거부는 `AUTH-0030`이므로 **그 범주에 들어간다** |
| project 표적 | `:133-136`이 **경로의 `project_id`** 를 읽으므로 `/v1/projects/{project_id}/storage/…` 모양이면 코드 변경 없이 남는다. 쿼리 문자열은 표적으로 **승격하지 않는다** |
| tenant 없는 거부 | `0047`의 `public.record_auth_denial`(SECURITY DEFINER) 그대로. 새 definer 0건 |
| kernel | 건드리지 않는다. kernel에 recorder가 없다는 사실(§3-0)은 **별 카드의 문제**로 남긴다 |

### 3-4. 시험 계획

**Phase 1(이 설계가 예약한 0062) 기준이다.** 정책 교체는 Phase 2이므로 그 시험은 Phase 2 카드가 든다 — 여기서 그 둘을 섞지 않는다.

| # | 시험 | 종류 | 무엇을 거부하게 하는가 |
|---|---|---|---|
| T1 | 계약 shape: **새 세 파일**(응답 2 + 요청 1)이 `additionalProperties:false`이고, 응답 required는 **기존 required + `projectId`**, 요청 required는 §3-2-3 그대로이며 **요청에 `projectId`가 없다** | PG 없음 | 필드 추가·이름 변경, 본문으로 project를 주입하려는 시도 |
| T2 | `kind` 열거가 **세 자리에서 같다** — 계약 파일, `src/saintvision/db/models/storage.py:32 LOCATION_KINDS`, DB CHECK `kind_allowed`(네 값). `mode`·`status`도 같은 방식으로 상수와 비교 | PG 없음(CHECK는 실 PG) | 계약 밖 값의 조용한 승격, 세 자리의 drift |
| T3 | **교차 project 읽기 0행**: tenant 같고 project 다른 주체의 목록·resolve·replica-status가 행을 내지 않고 **존재 신탁도 없다**(`require_project_access`의 같은 거부) | 실 PG | M2를 앱 계층에서 |
| T4 | **교차 project 쓰기 거부**: 다른 project 주체가 §3-2-1의 location 쓰기 route를 부르면 `require_project_access`의 거부로 끝나고 **행이 생기지 않는다**(판정 축은 `effective_permission`의 `canRequest`다 — 활성화·철회는 T6의 다른 축이다) | 실 PG | M2 |
| T5 | **project GUC는 `require_project_access` 통과 뒤에만 세워진다** — 검사를 건너뛰면 GUC가 비어 있고, 그 상태의 project 범위 조회는 **거부이고 빈 목록이 아니다** | 실 PG | §3-2의 권위 주체와 조용한 0행 |
| T6 | 소유자 아닌 주체의 **활성화·철회**가 거부된다 — 판정 축은 **행의 `registered_by_user_id`** 하나이고 `effective_permission`이 아니다(§3-4-2: 제공 폴더는 project의 것이 아니다). 같은 project 멤버여도 거부되고 **행 상태가 바뀌지 않는다** | 실 PG | M3 |
| T7 | `project_id IS NULL` 행이 **어떤 project 범위 조회에도 보이지 않는다**(owner 범위 조회에서는 그대로 보인다) | 실 PG | Phase 1의 fail-closed와 무회귀 |
| T8 | 0062 **downgrade 왕복**: 열 목록이 이전과 같고 `pg_policies`·`relforcerowsecurity`가 **변하지 않는다**(§3-4-1) | 실 PG | 가역성과 "정책을 건드리지 않았다" |
| T9 | 카탈로그 거부가 **감사 행 하나**를 남기고, **core 앱의** `/v1/projects/{project_id}/storage/…` 거부에는 **project 표적**이 있다(`AUTH-0030`은 감사 범주 `AUTH`다) | 실 PG | M6·§3-0·§3-3 |
| T10 | 기존 8 + 3 case가 **그대로 통과**한다(계약·소유자 범위·revocation·위조 cursor) | 기존 | 회귀 |
| T11 | kernel에는 새 route가 **없다**(그 앱에 거부 기록이 없다는 §3-0의 이유) | PG 없음 | 표면이 조용히 kernel로 새는 것 |
| T12 | **같은 tenant의 비소유자**와 **없는 `contributionId`** 가 **byte 단위로 같은 공개 body**를 받는다 — `RES-0004` 404 `"No such resource."`·`retryable=false`, 다른 것은 `traceId`뿐이다. 둘 다 **location이 생기지 않고** 각각 **denial audit 행이 정확히 1**이다 | 실 PG | §3-2-2 |
| T13 | project 역할(`canRequest`·`canAdminister`)이 **소유권을 대신하지 않는다** — 역할을 올려도 T12의 결과가 같다 | 실 PG | §3-2-2의 암묵적 위임 금지 |
| T14 | **같은 key·같은 body**는 저장된 응답을 그대로 돌려주고 **location·ledger·audit가 각 1행**이다(fixture 순서: ① 성공 1회 ② 같은 key·같은 body 재요청) | 실 PG | §3-2-3 exactly-once |
| T15 | **같은 key·다른 body**는 **`GRAPH-0002` 409**이고 **추가 행이 0**이다 — T14와 **같은 fixture 순서**(① 성공 1회로 location·ledger·audit 각 1행을 만든 뒤 ② 같은 key·다른 body를 보낸다)로, 그 뒤 location **1**·ledger **1**·audit **1**이 그대로이고 **최초 location의 상태·`project_id`가 불변**이다 | 실 PG | §3-2-3 |
| T16 | ledger의 `project_id`가 **경로 값**이다 — 본문에 `projectId`를 넣으면 계약이 먼저 거부한다(T1) | 실 PG | 본문 주입 |
| T17 | `kind`별 식별자 조합이 **계약에서** 거부된다(`dataset`에 `runId`, `artifact`에 `name` 등) | PG 없음 | §3-2-3의 `oneOf` |
| T18-a | **철회 선점**: 철회 transaction이 contribution 행을 먼저 잠그고 커밋하면, 기다렸던 POST는 **거부**이고 **location 0**이다 | 실 PG | §3-2-2의 `FOR UPDATE` |
| T18-b | **POST 선점**: POST가 먼저 잠그면 **201·location 1**이고 철회는 그 뒤에 커밋된다(카탈로그 행은 그대로 남는다 — 철회의 기존 의미) | 실 PG | 같음 |
| T18-c | 두 schedule 어느 쪽에서도 **철회 commit 뒤에 새 insert가 없다** | 실 PG | 같음 |
| T21 | **idempotency lock 대기 중 membership revoke**: 1차 판정 뒤 lock을 기다리는 동안 멤버십이 사라지면 **2차 재검사가 거부**하고(저장된 성공을 replay하지 않는다) location 0·denial audit 1이다 | 실 PG | §3-2-2의 [2차] |
| T22 | **행 잠금 대기 중 project archive**: 3차 재검사가 거부한다 — `effective_permission`은 archived에서 **예외 없이 false 셋**을 주므로 route가 **boolean을 읽어야** 걸린다(§3-4-2) | 실 PG | §3-2-2의 [3차] |
| T19 | 이 route의 `TRANSLATION` 표가 **그 호출이 낼 수 있는 모든 내부 코드를 덮는다**(없으면 `SYS-0002` 500이 된다) | PG 없음 | §3-2-3 |
| T20 | `Idempotency-Key`가 **없거나** 빈 값·129자·허용 밖 문자면 **`VAL-REQUEST` 422**이고 **아무 행도 생기지 않는다** | 실 PG | §3-2-3의 key 필수 |

### 3-4-1. `0062`의 downgrade — SQL 수준 불변식 (r2, Codex F4)

Phase 1이 정책을 바꾸지 않으므로 **0062는 완전히 가역이다.** 왕복 뒤 상태를 SQL로 적는다.

| 단계 | SQL 수준 결과 | 왕복 시험이 보는 것 |
|---|---|---|
| upgrade | **`data_locations`에만** `project_id text NULL` 추가와 `(tenant_id, project_id)` 참조(r3: contribution 표를 건드리지 않으므로 두 표를 맞추는 CHECK도 없다). **정책·GRANT·ENABLE/FORCE는 건드리지 않는다** | `pg_policies`의 두 정책이 **이름·식까지 동일**, `relrowsecurity`·`relforcerowsecurity` 둘 다 여전히 true |
| downgrade | 그 참조와 열을 **지운다**. **정책은 그대로 둔다**(바꾼 적이 없다) | 열 목록이 0062 이전과 **정확히 같고**, `pg_policies`·`relforcerowsecurity`가 **변하지 않았다** |
| 데이터 | downgrade는 `project_id` 값을 잃는다. 다시 upgrade하면 전부 `NULL`이고 **미결속 = 어떤 project 조회에도 안 보인다** → 되돌림이 **노출을 늘리지 않는다**(fail-closed 방향) | 재-upgrade 뒤 project 범위 조회가 0행이고 owner 범위 조회는 그대로 |

**Phase 2는 반대로 비가역이다** — 0047이 세운 선례(보안 축소를 downgrade가 복원하지 않는다)를 따라, 정책을 tenant+project로 바꾼 migration의 downgrade는 **더 느슨한 정책을 복원하지 않는다**(그 자리에서 멈추거나, 교체된 정책을 유지한다). 그 판단과 시험 기대 상태는 **Phase 2 카드**가 적는다. 이 문서는 0062에 대해서만 가역을 약속한다.

#### 3-4-2. 읽기·쓰기 권위를 각각 명시한다 (r3, Codex r2 F2-2)

`require_project_access`가 돌려주는 `effective_permission`은 boolean 셋이다(`src/saintvision/services/settings.py:181-186`): `canRequest`(역할 `owner`·`maintainer`·`operator`, `:73`), `canApprove`(`owner`·`approver`, `:77`), `canAdminister`(`owner`, `:80`). **그 셋은 project·user·membership 세 행 중 하나라도 아니라고 하면 전부 false**가 되고(`:167-173`) **예외는 던지지 않는다** — archived project가 바로 그 경우다. 그래서 규칙을 먼저 적는다.

> **예외가 없다는 것은 승인이 아니다.** 모든 route는 자기 권위 boolean을 **읽어서** 참인지 확인한다. `require_project_access`가 통과했다는 사실만으로 진행하는 분기를 두지 않는다.

| 동작 | 권위 | 왜 |
|---|---|---|
| project 범위 **읽기**(locations 목록·resolve·replica-status) | `canRequest` **또는** `canApprove` | 카탈로그를 읽는 것은 일을 요청하거나 승인하는 사람의 일이다. 두 집합의 합은 `owner`·`maintainer`·`operator`·`approver`다 |
| project 범위 **쓰기**(location을 project에 넣는 §3-2-1의 route) | `canRequest` | 일을 요청할 수 있는 사람이 그 project의 입력을 등록한다. 승인자만인 역할(`approver`)에게 쓰기를 주지 않는다 |
| **과거 행 결속**(§3-2-1 확정 3의 선택 route) | `canAdminister` | project 소속을 바꾸는 것은 설정 변경이다(`owner` 하나) |
| 제공 폴더 **활성화·철회** | **그 행의 소유자**(`registered_by_user_id == principal.user_id`) **하나** | 이것이 M3의 결정이다 — **같은 project의 비소유자도 거부**한다. 제공 폴더는 project의 것이 아니라 **tenant 전체의, 그 사람의 폴더**이고(`src/saintvision/api/v1/storage.py:114-117`) project 멤버십은 남의 폴더에 대한 권한을 주지 않는다. 관리자 우회가 필요해지면 **그때 자기 감사 route로** 만든다(암묵적 권한으로 주지 않는다) |

**`viewer` 역할은 위 세 boolean 전부 false다**(`:66-70`의 역할 목록에 있고 세 집합 중 어디에도 없다). 그래서 이 설계에서 **`viewer`는 project 범위 카탈로그를 읽지 못한다.** 그것을 바꾸려면 새 boolean(예: `canView`)이 필요하고 그것은 **이 카드의 범위가 아니다** — 제품 결정이므로 여기서 조용히 넓히지 않고 사실로 적어 둔다.

**변이 계획**: T3·T4·T7의 단언을 지우는 변이, 새 route의 `WHERE project_id` 조건을 빼는 변이, `require_project_access` 호출을 지우는 변이(그러면 T5가 울어야 한다), `NULL` 행을 보이게 하는 변이, 거부 기록을 지우는 변이, **`registered_by_user_id` 검사를 지우는 변이**(T12가 울어야 한다), **idempotency 직렬화를 자원 행 뒤로 옮기는 변이**와 **본문 digest 비교를 지우는 변이**(T14·T15), **`FOR UPDATE`를 지우는 변이**(T18), **`_require_idempotency_key` 호출을 지우는 변이**(T20), **`TRANSLATION`에서 `GRAPH_IDEMPOTENCY_CONFLICT` 줄을 지우는 변이**(T19), **2차 재검사를 지우는 변이**(T21), **3차 재검사를 지우는 변이**(T22), **공개 문제를 내부 코드로 만드는 변이**(T12 — 그 변이는 `ValueError`로 끝나므로 500이 되고 시험이 그것을 잡는다)를 각각 하나씩 넣어 **전부 죽는지** 확인한다(한 번에 하나, 매 회 원복·바이트 대조 — 카드 243·249에서 쓴 방식이고 복원은 `newline=""`로 byte 동일하게 한다).

**hosted 전제**: Backend(3.12·3.14)와 Core의 실 PG lane이 green이어야 한다. **r3 정정 — 0062는 census repin이 필요 없다**: `tools/collect_rls_evidence.py:495-500`의 `table_census`는 그 schema들의 **`pg_class` 표 집합**이고, Phase 1은 **열만 더하므로 표 집합이 변하지 않는다**. r2까지 적혀 있던 "census pin을 한 칸 올린다"는 **거짓이었다**(Codex r2의 정정). 표를 더하는 것은 §3-2-1 확정 3의 선택 route도 아니고 Phase 2도 아니므로, census repin은 **이 설계 어디에도 필요하지 않다**.

### 3-5. 범위 경계

- **브라우저 화면은 Gemini 몫**이다(VF-GM-03 `File Explorer와 inv:// UX`). 이 설계는 화면이 필요한 값을 **계약으로만** 적는다 — 목록·페이지네이션·소유 범위·revocation 상태·`kind`(정본 4값).
- **바이트 전송·materialization은 이 카드가 아니다**(VF-CL-02). `resolve`가 바이트 접근을 주지 않는다는 지금의 경계를 유지한다.
- **model registry·lineage는 VF-CL-03**이고 `kind='model'` 위치의 생산자는 그쪽이다.

## 4. 이 문서가 하지 않은 것

- **구현·migration·계약 파일을 고치지 않았다**(docs-only). 0062는 **예약**이고 파일을 만들지 않았다.
- ~~**project 설정 주입 지점을 코드로 고르지 않았다**~~ → **r2에서 확정했다**: `require_project_access` 통과 뒤 의존성 계층이 `SET LOCAL`로 세우고 호출자 입력을 직접 넣지 않는다(§3-2). **다만 그 코드를 쓰지는 않았다** — 이 PR은 여전히 구현 0줄이다.
- ~~**`locationKind` 열거를 확정하지 않았다**~~ → **r2에서 확정했다**: `kind`는 정본 4값(`artifact`·`dataset`·`model`·`workspace`)에 그대로 결속하고 이름도 바꾸지 않는다(§3-1-1). r1이 그 상수를 놓친 것이 이 줄의 원인이었다.
- **기존 8 + 3 case를 내가 다시 돌리지 않았다** — 이 PR은 문서뿐이고, §3-4의 T10이 구현 카드에서 그 역할을 한다.
- **S02-ST의 점수를 올리지 않았다** — 설계는 점수가 아니다(§1-1의 rubric). 재채점은 구현이 착지한 뒤의 별 카드 몫이다.
