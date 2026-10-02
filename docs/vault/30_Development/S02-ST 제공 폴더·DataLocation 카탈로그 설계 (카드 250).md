---
doc_id: "CLAUDE-S02-ST-CATALOG-DESIGN-250"
title: "S02-ST 제공 폴더·DataLocation 카탈로그 설계 (카드 250) — 측정 먼저: 카탈로그 표·route·`inv://` resolver·시험은 **이미 있고**(`src/saintvision/api/v1/storage.py:81~284`, `data_locations`·`storage_contributions` FORCE RLS, 통합 8 + 계약 3 case) 정본 재채점은 S02-ST를 **75**로 적는다(v1.7 정정). 외부 전제 없이 닫을 수 있는 공백은 셋이다 — (1) 카탈로그에 **project 차원이 없다**(두 표에 `project_id` 열이 없고 RLS 정책이 tenant 전용이라 AC-02의 '다른 project 정보 접근 차단'을 DB가 강제하지 못한다), (2) **읽기는 소유자 범위인데 쓰기는 tenant 범위**다(`activate_contribution`·`revoke_contribution`이 소유자를 보지 않는다), (3) **kernel(inv) 쪽 카탈로그 읽기 표면이 없다**. 이 문서는 그 셋의 계약·migration(0062 예약)·RLS·인증 실패 기록·시험 계획만 담는다. 구현 0줄, 브라우저 화면은 Gemini 몫. **r2(Codex r1)**: 거부 기록이 있는 앱은 core 하나뿐이므로(kernel의 `DomainError` handler는 `problem()`만 반환한다) 새 읽기 표면을 **core 앱의 `/v1/projects/{project_id}/storage/…`** 로 확정하고 계약도 core 세대에 둔다, project GUC는 `require_project_access` 통과 뒤 의존성 계층이 세운다, RLS 교체는 **Phase 2로 분리**한다(0062는 열만 더하고 정책을 바꾸지 않으므로 가역), `kind`는 정본 **4값**에 그대로 결속한다. **r3(Codex r2)**: `project_id`를 만드는 제품 경로가 **0건**이므로(제공 폴더 등록은 스스로 tenant 전체라고 적고 location을 만드는 제품 호출자는 없다) 결속을 **`data_locations` 한 표**로 줄이고 **그 열을 채우는 project 범위 쓰기 route를 같은 카드에 묶었다**, 읽기 권위는 `canRequest`∨`canApprove`·쓰기는 `canRequest`·활성화/철회는 **행 소유자 하나**로 확정했다(archived project는 boolean이 false이므로 예외 부재를 승인으로 쓰지 않는다), census repin이 필요하다던 문장은 **거짓이어서 정정했다**"
version: "1.2.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-10-03T05:42:55+09:00"
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

**확정**: 새 project 범위 카탈로그 읽기 표면은 **core 앱**에 둔다. 경로는 `/v1/projects/{project_id}/storage/contributions`·`…/locations`·`…/resolve`·`…/replica-status`다. 근거는 셋이다 — (1) 카탈로그 서비스·표·기존 route가 모두 core 앱이다, (2) 거부 기록이 거기 있다, (3) recorder가 **경로의 `project_id`만** 표적으로 적으므로(`src/saintvision/api/app.py:133-136`) 이 경로 모양이면 **표적이 코드 변경 없이 남는다**(M6 해소).

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

**Phase 2 — 별 migration(0063 이후, 별 카드)**
- **모든** reader가 project GUC를 세우게 된 뒤에(기존 owner 범위 route를 project 범위로 옮기거나 폐기한 뒤) 정책을 교체한다:
  `USING/WITH CHECK (tenant_id = current_setting('inv.tenant_id') AND project_id = current_setting('inv.project_id'))`.
- **그때까지 DB 강제는 tenant 하나**이고, project 경계는 **앱 계층 + 시험**이 든다. 이 문서는 그 사실을 숨기지 않는다 — AC-02의 "다른 project 차단"이 **DB 불변식이 되는 시점은 Phase 2**다.
- 전환 중 두 모드를 한 정책에 담는 타협(`project_id IS NULL OR …`)은 **쓰지 않는다** — 그러면 미결속 행이 모든 project에 보인다.

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
| T1 | 계약 shape: 새 네 파일이 `additionalProperties:false`이고 required가 **기존 required + `projectId`** 그대로 | PG 없음 | 필드 추가·이름 변경 |
| T2 | `kind` 열거가 **세 자리에서 같다** — 계약 파일, `src/saintvision/db/models/storage.py:32 LOCATION_KINDS`, DB CHECK `kind_allowed`(네 값). `mode`·`status`도 같은 방식으로 상수와 비교 | PG 없음(CHECK는 실 PG) | 계약 밖 값의 조용한 승격, 세 자리의 drift |
| T3 | **교차 project 읽기 0행**: tenant 같고 project 다른 주체의 목록·resolve·replica-status가 행을 내지 않고 **존재 신탁도 없다**(`require_project_access`의 같은 거부) | 실 PG | M2를 앱 계층에서 |
| T4 | **교차 project 쓰기 거부**: 다른 project 주체의 활성화·철회가 거부되고 **행 상태가 바뀌지 않는다** | 실 PG | M3·M2 |
| T5 | **project GUC는 `require_project_access` 통과 뒤에만 세워진다** — 검사를 건너뛰면 GUC가 비어 있고, 그 상태의 project 범위 조회는 **거부이고 빈 목록이 아니다** | 실 PG | §3-2의 권위 주체와 조용한 0행 |
| T6 | 소유자 아닌 **같은 project** 주체의 활성화·철회가 **거부**된다(§3-4-2의 결정) — 그리고 그 거부가 `effective_permission`의 boolean을 **읽어서** 나온 것이지 예외 부재가 아니다 | 실 PG | M3 |
| T7 | `project_id IS NULL` 행이 **어떤 project 범위 조회에도 보이지 않는다**(owner 범위 조회에서는 그대로 보인다) | 실 PG | Phase 1의 fail-closed와 무회귀 |
| T8 | 0062 **downgrade 왕복**: 열 목록이 이전과 같고 `pg_policies`·`relforcerowsecurity`가 **변하지 않는다**(§3-4-1) | 실 PG | 가역성과 "정책을 건드리지 않았다" |
| T9 | 카탈로그 거부가 **감사 행 하나**를 남기고, **core 앱의** `/v1/projects/{project_id}/storage/…` 거부에는 **project 표적**이 있다(`AUTH-0030`은 감사 범주 `AUTH`다) | 실 PG | M6·§3-0·§3-3 |
| T10 | 기존 8 + 3 case가 **그대로 통과**한다(계약·소유자 범위·revocation·위조 cursor) | 기존 | 회귀 |
| T11 | kernel에는 새 route가 **없다**(그 앱에 거부 기록이 없다는 §3-0의 이유) | PG 없음 | 표면이 조용히 kernel로 새는 것 |

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

**변이 계획**: T3·T4·T7의 단언을 지우는 변이, 새 route의 `WHERE project_id` 조건을 빼는 변이, `require_project_access` 호출을 지우는 변이(그러면 T5가 울어야 한다), `NULL` 행을 보이게 하는 변이, 거부 기록을 지우는 변이를 각각 하나씩 넣어 **전부 죽는지** 확인한다(한 번에 하나, 매 회 원복·바이트 대조 — 카드 243·249에서 쓴 방식이고 복원은 `newline=""`로 byte 동일하게 한다).

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
