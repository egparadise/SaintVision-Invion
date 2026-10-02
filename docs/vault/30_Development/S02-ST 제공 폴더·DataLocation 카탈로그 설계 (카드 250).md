---
doc_id: "CLAUDE-S02-ST-CATALOG-DESIGN-250"
title: "S02-ST 제공 폴더·DataLocation 카탈로그 설계 (카드 250) — 측정 먼저: 카탈로그 표·route·`inv://` resolver·시험은 **이미 있고**(`src/saintvision/api/v1/storage.py:81~284`, `data_locations`·`storage_contributions` FORCE RLS, 통합 8 + 계약 3 case) 정본 재채점은 S02-ST를 **75**로 적는다(v1.7 정정). 외부 전제 없이 닫을 수 있는 공백은 셋이다 — (1) 카탈로그에 **project 차원이 없다**(두 표에 `project_id` 열이 없고 RLS 정책이 tenant 전용이라 AC-02의 '다른 project 정보 접근 차단'을 DB가 강제하지 못한다), (2) **읽기는 소유자 범위인데 쓰기는 tenant 범위**다(`activate_contribution`·`revoke_contribution`이 소유자를 보지 않는다), (3) **kernel(inv) 쪽 카탈로그 읽기 표면이 없다**. 이 문서는 그 셋의 계약·migration(0062 예약)·RLS·인증 실패 기록·시험 계획만 담는다. 구현 0줄, 브라우저 화면은 Gemini 몫"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-10-03T04:55:56+09:00"
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
| **M1** | **두 표에 `project_id` 열이 없다** | `src/saintvision/db/models/storage.py`의 `StorageContribution`(`contribution_id`·`tenant_id`·`node_id`·`declared_path`·`normalized_path`·`mode`·`status`·`capacity_bytes`·`available_bytes`·`registered_by_user_id`·`registered_at`·`revoked_at`·`version`)과 `DataLocation`(`location_id`·`tenant_id`·`contribution_id`·`uri`·`kind`·`relative_path`·`byte_size`·`checksum_sha256`·`verified_at`·`ready`·`retention_pinned_until`·`catalogued_at`·`version`) 열 전수 |
| **M2** | **project 범위 RLS 정책이 없다** | 0001의 정책은 `tenant_id = <setting>` 한 조건뿐이다(§1-1). 그래서 **AC-02의 "다른 project 정보 접근 차단"을 카탈로그에서는 DB가 강제하지 않는다** — Node 쪽은 kernel의 project route가 따로 강제한다 |
| **M3** | **쓰기 경로가 소유자를 보지 않는다** | `src/saintvision/services/storage.py:94 activate_contribution`·`:106 revoke_contribution`의 인자는 `tenant_id`·`contribution_id`뿐이고 `_load_contribution`도 그 둘로 찾는다. 읽기는 `:250`·`:282`에서 `registered_by_user_id == reader_user_id`를 건다. route에도 권한 의존이 없다(`src/saintvision/api/v1/storage.py:37 APIRouter(prefix="/v1", tags=["storage"])`에 `dependencies=` 없음, `src/saintvision/api/app.py:222 include_router(storage_router.router)`) → **같은 tenant의 다른 주체가 남의 제공 폴더를 활성화·철회할 수 있다** |
| **M4** | **kernel(`services/control-plane/src/inv/`)에 카탈로그 읽기 표면이 없다** | kernel의 storage 표면은 `services/control-plane/src/inv/app.py:517 GET /v1/projects/{project}/runs/{run_id}/storage-samples/{request_id}` 하나(관측 표본)이고 `services/control-plane/src/inv/storage_view.py`·`services/control-plane/src/inv/storage_commit.py`가 그 뒤다. `DataLocation` 목록·resolve는 kernel에 없다 |
| **M5** | **`kind`가 계약에서 열린 문자열이다** | `contracts/data-location-response.schema.json`의 `kind`는 `{"type":"string"}`뿐이다. 제품이 쓰는 값은 최소 `model`이 확인된다(`src/saintvision/api/v1/model_verify.py:253`의 `kind='model'`) |
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
| **D1** | 카탈로그에 **project 결속**을 주고 RLS를 tenant+project로 좁힌다(M1·M2) | 장비·사용자 입력이 필요 없다. project·member 표는 이미 있다(0001) |
| **D2** | **쓰기 경로를 소유자/역할 범위로** 좁힌다(M3) | 같은 tenant 안의 권한 경계이고 외부 자산이 없다 |
| **D3** | kernel에 **읽기 전용 project 카탈로그 표면**을 둔다(M4) | kernel은 이미 project 단위 권한·거부 기록을 갖고 있다 |
| **D4** | 계약의 `kind`를 **열거로 좁히고** 두 세대의 계약 경계를 문서화한다(M5) | 계약 파일과 시험만 바뀐다 |
| **D5** | 카탈로그 거부가 **project 표적**을 남기게 한다(M6) | D1·D3이 경로에 project를 들이면 기존 중앙 경로가 자동으로 적는다 |

## 3. 설계안 (구현 0줄 — 이 PR은 이 문서만 담는다)

### 3-1. 계약 추가안

**두 세대를 섞지 않는다.** 카탈로그의 기존 응답 계약은 core API 세대(`contracts/*.schema.json`)이고 거기 있는 필드·`additionalProperties:false`는 **그대로 둔다**(이미 hosted 시험이 고정한다). kernel 쪽 D3의 읽기 표면은 kernel 세대(`contracts/v1alpha1/core.schema.json`)에 `$defs`로 **새로** 적는다.

```
contracts/v1alpha1/core.schema.json  $defs 추가안 (이름·필드는 제안이고 Codex 검토 대상)

StorageContributionView      required: apiVersion, kind(const "StorageContributionView"),
                             tenantId, projectId, contributionId, nodeId, mode, status,
                             registeredAt           additionalProperties: false
  mode   enum: ["read_only","read_write"]          (요청 계약의 정규식과 같은 집합)
  status enum: ["pending","active","revoked"]      (services/storage.py:83/101/116에서 측정한 전이)

DataLocationView             required: apiVersion, kind(const "DataLocationView"),
                             tenantId, projectId, locationId, contributionId, uri,
                             locationKind, relativePath, byteSize, ready
                             additionalProperties: false
  locationKind enum: ["model", ...]                 (§3-1-1)
  uri          pattern: 제품이 쓰는 inv:// 형태를 pathsafe.parse_uri에서 유도

DataLocationPage             required: apiVersion, kind(const "DataLocationPage"), items, nextCursor
  items     array of DataLocationView, uniqueItems: true
  nextCursor string | null                          (cursor는 서버가 서명·검증한다 — 기존 route의 위조 cursor 거부 시험과 같은 규칙)
```

`kind`를 바깥 문서 종류 이름으로 쓰는 것이 kernel 계약의 관례이므로(`WorkloadSpec`의 `kind` const `Workload`, `BuildRequest`의 const `BuildRequest`), **DataLocation의 분류는 `locationKind`로 옮겨 적는다** — 같은 이름 두 뜻을 피한다.

#### 3-1-1. `locationKind` 열거를 무엇으로 할지는 **측정으로 정한다**

지금 tree에서 확인되는 값은 `model` 하나뿐이다(M5). 열거를 억측으로 넓히지 않고, 구현 카드가 **실제로 쓰이는 값을 전수 조사해** 그 집합으로 고정한다(값이 하나면 하나로 고정하고, 늘 때마다 계약을 올린다 — 카드 226·228에서 쓴 "계약 밖 값은 UNKNOWN으로 강등" 규칙과 같은 방향).

### 3-2. 표와 RLS (migration **0062** 예약 — 0061은 `#343`)

**선택지 둘을 적고 하나를 권한다.**

| | A. 두 표에 `project_id` 열을 더한다 | B. 결속 표 `storage_contribution_projects`를 새로 만든다 |
|---|---|---|
| RLS | 기존 `…_tenant_isolation` 정책을 `tenant_id` + `project_id ∈ (현재 주체의 project)`로 교체 | 카탈로그 표의 정책은 그대로 두고 결속 표에만 정책을 건다 → **읽기마다 join**이 필요하고 join을 빠뜨리면 조용히 전 tenant가 보인다 |
| 기존 행 | **backfill 결정이 필요하다**(아래) | 기존 행은 결속이 없는 상태로 남는다 — "결속 없음 = 아무 project도 못 본다"로 두면 **현재 소유자 조회가 깨진다** |
| 불변성 | 한 제공 폴더가 한 project에 속한다는 단순한 사실을 표가 직접 든다 | 한 폴더를 여러 project에 줄 수 있다 — 지금 제품에 그 요구가 **측정되지 않았다** |
| 권함 | **A를 권한다** | 요구가 측정되면 그때 B로 옮긴다(A → B는 가역적이다) |

**A의 미결 결정(Codex 판단 요청)**: 기존 행의 `project_id`를 (가) `NOT NULL` + backfill 값을 사용자/코디네이터가 지정, (나) nullable로 두고 `NULL`은 "project 미결속"으로서 **어떤 project 범위 조회에도 보이지 않게**, 셋 중 하나를 고른다. **나를 권한다** — 조용히 보이게 하는 선택지는 두지 않는다(fail-closed). 그리고 0062는 **가역**이어야 한다(downgrade 왕복 시험). 단, 0047이 세운 선례대로 **보안 축소를 되돌리는 downgrade는 쓰지 않는다** — 열을 지우되 회수한 권한은 복원하지 않는다.

정책 모양(제안):

```
ALTER TABLE storage_contributions ADD COLUMN project_id text;      -- 0062 (nullable, 위 (나))
ALTER TABLE data_locations        ADD COLUMN project_id text;       -- 동일
-- 두 표의 project_id는 (tenant_id, project_id) 로 projects 를 참조한다.
-- data_locations.project_id 는 자기 contribution 의 project_id 와 같아야 한다(CHECK 또는 복합 FK).
DROP POLICY data_locations_tenant_isolation ON data_locations;
CREATE POLICY data_locations_tenant_project_isolation ON data_locations FOR ALL TO inv_app
  USING  (tenant_id = <tenant setting> AND project_id = <project setting>)
  WITH CHECK (tenant_id = <tenant setting> AND project_id = <project setting>);
-- storage_contributions 동일. ENABLE + FORCE 는 이미 켜져 있으므로 유지한다.
```

**주의로 적어 둘 것**: 지금 코드는 project 설정을 session에 넣지 않는다(0001의 정책이 tenant 하나만 보기 때문이다). 그래서 **설정 이름·주입 지점**(요청 경계에서 `SET LOCAL`)이 구현 카드의 첫 작업이고, 그것 없이 정책만 바꾸면 **모든 카탈로그 조회가 0행**이 된다 — 그 실패가 조용하지 않도록 **0행과 거부를 구분하는 시험**을 같이 넣는다(§3-4의 T5).

### 3-3. 인증 실패 기록 경로

**새 경로를 만들지 않는다.** 거부를 쓰는 자리는 `src/saintvision/api/app.py:135` 하나이고 그 docstring이 그렇게 선언한다. 설계는 **그 경로가 카탈로그 거부에서 무엇을 적는지**만 정한다.

| 무엇 | 지금 | 이 설계에서 |
|---|---|---|
| `action` | route가 선언한 `denial_action` 또는 `METHOD <template>` | 새 kernel route는 **자기 `denial_action`을 선언한다**(경로에 식별자를 넣지 않는 바운드 문자열) |
| `target` | 경로의 `project_id`가 올바를 때만 `("project", …)` | D3의 kernel route가 `/v1/projects/{project}/…` 형태이므로 **project 표적이 자동으로 남는다**(M6 해소). core API route는 경로에 project가 없으므로 **그대로 비워 둔다** — 쿼리 문자열을 표적으로 승격하지 않는다(그 docstring의 "caller text that is not one is not recorded anywhere"와 같은 규칙) |
| tenant 없는 거부 | `0047`의 `public.record_auth_denial`(SECURITY DEFINER) | **변경 없다.** 새 definer 함수를 만들지 않는다(만들면 `definer-policy.json`과 AC-11 definer 축의 서명 집합을 건드린다 — 이 카드의 범위 밖) |
| 실패 처리 | fail-closed(기록 실패 시 500) | 유지. 카탈로그 거부가 기록 없이 성공처럼 끝나는 분기를 새로 만들지 않는다 |

### 3-4. 시험 계획

| # | 시험 | 종류 | 무엇을 거부하게 하는가 |
|---|---|---|---|
| T1 | 계약 shape: 새 `$defs` 세 개가 `additionalProperties:false`이고 required 집합이 §3-1 그대로 | PG 없음 | 필드 추가·이름 변경 |
| T2 | `locationKind`·`mode`·`status` 열거가 **제품이 쓰는 값의 집합과 같다**(코드에서 유도해 비교) | PG 없음 | 계약 밖 값의 조용한 승격 |
| T3 | **교차 project 읽기 0행**: tenant 같고 project 다른 주체가 목록·resolve·replica-status를 호출하면 행이 없고 **404의 존재 신탁이 없다** | 실 PG | M2 |
| T4 | **교차 project 쓰기 거부**: 다른 project 주체의 활성화·철회가 거부되고 **행 상태가 바뀌지 않는다** | 실 PG | M3·M2 |
| T5 | **project 설정 누락은 거부이고 빈 목록이 아니다** | 실 PG | §3-2의 조용한 0행 |
| T6 | 소유자 아닌 같은 project 주체의 활성화·철회 판정(§3-2의 결정에 따라 허용/거부 중 하나로 **고정**) | 실 PG | M3 |
| T7 | `NULL project_id` 행이 **어떤 project 범위 조회에도 보이지 않는다** | 실 PG | §3-2 (나) |
| T8 | 0062 **downgrade 왕복**과 "보안 축소는 복원하지 않는다" | 실 PG | 0047의 선례 |
| T9 | 카탈로그 거부가 **감사 행 하나**를 남기고 kernel route의 거부에는 **project 표적**이 있다 | 실 PG | M6·§3-3 |
| T10 | 기존 8 + 3 case가 **그대로 통과**한다(계약·소유자 범위·revocation·위조 cursor) | 기존 | 회귀 |

**변이 계획**: T3·T4·T7의 단언을 지우는 변이, 정책에서 `project_id` 조건을 빼는 변이, `NULL` 행을 보이게 하는 변이, 거부 기록을 지우는 변이를 각각 하나씩 넣어 **전부 죽는지** 확인한다(한 번에 하나, 매 회 원복·바이트 대조 — 카드 243·249에서 쓴 방식이고 복원은 `newline=""`로 byte 동일하게 한다).

**hosted 전제**: Backend(3.12·3.14)와 Core의 실 PG lane이 green이어야 하고, `tools/collect_rls_evidence.py`의 census가 **표 수 변화를 알아차린다** — 0062는 census pin을 한 칸 올리므로 그 repin을 같은 PR에 넣는다(카드 234에서 쓴 규칙).

### 3-5. 범위 경계

- **브라우저 화면은 Gemini 몫**이다(VF-GM-03 `File Explorer와 inv:// UX`). 이 설계는 화면이 필요한 값을 **계약으로만** 적는다 — 목록·페이지네이션·소유 범위·revocation 상태·`locationKind`.
- **바이트 전송·materialization은 이 카드가 아니다**(VF-CL-02). `resolve`가 바이트 접근을 주지 않는다는 지금의 경계를 유지한다.
- **model registry·lineage는 VF-CL-03**이고 `kind='model'` 위치의 생산자는 그쪽이다.

## 4. 이 문서가 하지 않은 것

- **구현·migration·계약 파일을 고치지 않았다**(docs-only). 0062는 **예약**이고 파일을 만들지 않았다.
- **project 설정 주입 지점을 코드로 고르지 않았다** — §3-2의 주의로만 적었다.
- **`locationKind` 열거를 확정하지 않았다** — 측정으로 정하도록 §3-1-1에 규칙만 적었다.
- **기존 8 + 3 case를 내가 다시 돌리지 않았다** — 이 PR은 문서뿐이고, §3-4의 T10이 구현 카드에서 그 역할을 한다.
- **S02-ST의 점수를 올리지 않았다** — 설계는 점수가 아니다(§1-1의 rubric). 재채점은 구현이 착지한 뒤의 별 카드 몫이다.
