# 통합 코드 독립 검토 — Claude

- 작성자: Claude · **검토자: 미지정 (Codex 인계 필요)**
- 기준: `agent/codex/account-kernel-integration` (`2398dcc`) 위의 `review/claude-account-results`
- 방법: Codex 브랜치에서 분기 → 남은 작업 추가 → 실PostgreSQL 실행 (CI는 계정 제한으로 미실행, 지시대로 유지)

---

## 1. Codex가 제 코드에서 찾아낸 결함 — 네 건, 전부 실재

`149b565 fix(api): integrate account services with scoped administration and execution`가 제 계정 작업을 고쳤습니다. **넷 다 진짜 결함이고, 넷 다 제 것입니다.** 받아들이기 전에 각각 직접 확인했습니다.

### (a) `PUT /v1/users/{id}/status`에 권한 검사가 **전혀** 없었습니다 — 심각

제 `set_user_status`는 `acting_user_id`조차 받지 않았습니다. 라우트는 principal의 tenant만 넘겼습니다. 즉 **그 tenant의 로그인한 아무나가 아무 사용자나 정지**시킬 수 있었습니다. owner 전원을 정지시키면 tenant 전체가 잠깁니다.

제가 바로 그 파일 상단에 "정지는 즉시 커널에 반영된다"고 써 놨습니다. **맞습니다 — 그래서 더 나빴습니다.** 누구나 부를 수 있는 즉효 스위치였습니다.

Codex의 수정: `inv.business_admin_grants` + `business_admin_allowed` definer 함수. **프로젝트 owner 권한이 tenant 관리 권한을 주지 않습니다** — 그 구분이 제게 아예 없었습니다.

### (b) 마지막 owner 검사가 check-then-act 경합

제 `_owner_count` → 쓰기 사이에 잠금이 없었습니다. **서로 다른 두 owner를 동시에 강등하면 둘 다 count==2를 보고 둘 다 성공해 owner가 0이 됩니다** — 그 규칙이 막으려던 바로 그 결과입니다.

제가 이 부류의 실수를 heartbeat에서 이미 한 번 했고 고쳤는데, **여기서 다시 했습니다.** Codex의 `lock_project`(FOR UPDATE)가 직렬화합니다.

### (c) 프로젝트 보관이 일방통행

`set_project_status` → `require_administrator` → `canAdminister`는 `projectStatus == 'active'`를 요구합니다. 그래서 **보관은 되고 해제는 영원히 불가능**했습니다. Codex의 `allow_archived` 예외가 맞습니다.

### (d) 제 definer 함수가 tenant를 넘어 읽혔습니다

migration 0024의 `project_kernel_link`는 `p_tenant_id`를 호출자에게서 받아 **믿었습니다.** SECURITY DEFINER 함수는 소유자로 실행되므로 **RLS를 우회합니다.** 호출자가 아무 tenant id나 넘겨 다른 tenant의 프로젝트 링크 상태를 알 수 있었습니다.

`node_by_certificate`에서는 이 부류를 조심했으면서(정확 일치, 3컬럼) 여기서는 **호출자가 준 tenant를 신뢰할 수 있다고 가정**해 놓쳤습니다. 0027이 `current_setting('inv.tenant_id')` 바인딩으로 닫았습니다.

**같은 구멍이 제 `subject_kernel_link` 초안에도 있었습니다.** 아직 어디에도 병합되지 않아서, 이번에 **처음부터 올바른 형태로** 다시 썼습니다(0028). 신규 `run_committed_outputs`(0029)도 같습니다 — 그쪽은 **파일 내용을 반환하는 경로**라 더 중요합니다.

---

## 2. 제가 Codex 도구에서 찾은 결함 — 두 건

### (e) `check_migration_upgrade.py`가 head를 문자열로 고정

```python
assert conn.execute("SELECT version_num FROM alembic_version").fetchall() == [
    ("0027_business_api_guards",)
]
```

**누가 revision을 추가하는 순간 낡습니다** — 그리고 실패가 "마이그레이션 경로 깨짐"으로 읽힙니다. 업그레이드가 동작함을 증명하는 도구가 가장 하지 말아야 할 실패 방식입니다. 이 저장소에서 **하드코딩 목록이 낡은 다섯 번째** 사례입니다. `migration_graph.chain()`에서 유도하게 고쳤습니다.

### (f) 그 도구는 **매 실행마다 아홉 번째에서 실패하고 있었습니다**

진짜 원인은 `ModuleNotFoundError: No module named 'saintvision'`. 도구가 `saintvision.ids`를 import하는데 `src`를 `sys.path`에 넣지 않습니다. pytest는 `pyproject`에서 경로를 주지만 **pytest가 띄우는 subprocess는 그걸 물려받지 않습니다.**

그리고 자격증명 유출을 막는 진단 억제(그 자체는 옳습니다)가 **평범한 ModuleNotFoundError를 "migration validation failed"로 바꿔놓았습니다.** 고치고 나니 9개 prior 전부 통과합니다:

```
PASS: 0018_workspace_resume / 0010_canonical_resource_units / 0019 / 0020 /
      0021 / 0022 / 0023 / 0025_workspace_start / 0025_workspace_tool_choice
```

---

## 3. 이번에 추가한 것

**결과·다운로드 API.** `public.artifacts`에는 **바이트 저장소와의 연결이 없습니다** — 아무것도 그 테이블을 쓰지 않고, 행 하나를 파일로 해소할 수 없습니다. 그래서 그걸 나열하면 **불가능한 다운로드를 제안**하게 됩니다.

실제로 존재하는 것은 커널의 `inv.result_commitments`(run → object → content_hash → evidence)입니다. 다운로드는 그쪽을 읽고, 바이트는 `inv.object_store.LocalObjects`를 통해 나옵니다 — **읽으면서 다시 해시해 기록된 digest와 대조**합니다. 어긋나면 다운로드가 실패합니다. **어긋난 바이트를 내주면 Evidence가 이미 누군가 사본을 가진 것에 대한 거짓말이 됩니다.**

`public.artifacts`가 비어 있다는 사실 자체가 지적 사항입니다(§5).

**운영 프로비저닝 도구** `tools/provision_account.py`. `execution-readiness`가 "운영자가 고쳐야 함"이라고 말하는 것들을 실제로 고치는 명령입니다. **API가 아닙니다** — 두 링크가 어떤 프로젝트가 실행 가능하고 누가 승인할 수 있는지를 정하고, 웹 프로세스가 스스로에게 그걸 줄 수 없어야 하기 때문입니다. 한 사용자가 **이미 다른 subject에 매핑되어 있으면 거부**합니다(1:1이 2인 승인의 근거라, 조용히 갈아끼우면 그게 무너집니다).

---

## 4. 검증

CI는 계정 제한으로 실행되지 않았고 지시대로 그대로 뒀습니다. 로컬 실PostgreSQL:

| 명령 | 결과 |
|---|---|
| `pytest test_account_integration test_results test_projects test_settings test_login test_migrations` | **96 passed** |
| `python tools/check_migration_upgrade.py` | **9/9 PASS** (고치기 전 8/9) |
| `python tools/export_schemas.py --check` | **19 contracts** 일치 |
| `python tools/migration_graph.py --head` | `0029_run_outputs` |

---

## 5. 남은 지적 사항

- **`public.artifacts`에 바이트 연결이 없습니다.** 모델은 `inv://artifacts/<runId>/<artifactId>` 주소를 문서화하지만 그걸 해소할 열도 코드도 없고 아무것도 그 테이블에 쓰지 않습니다. 다운로드를 커널의 committed output으로 붙인 이유이며, 두 표현 중 하나는 정리되어야 합니다.
- **원격 실행은 아직 검증되지 않았습니다.** 192.168.45.225는 관측 전용입니다. 여기 어떤 것도 원격 실행이 동작함을 보이지 않습니다.
- **복원 리허설·부하 시험 미수행.**
- 작성자와 검토자가 분리되어야 하므로 **이 문서는 승인이 아닙니다.** Codex의 독립 검토가 필요합니다 — 특히 0028·0029 definer 함수 두 개와 `check_migration_upgrade` 수정.

---

## 6. 2차 검토 — `agent/codex/result-observation` (`c9dea3f`)

### 긴급: 제 수정 전 초안이 그대로 실려 있습니다 — **tenant 간 정보 유출**

그 브랜치의 `migrations/versions/0026_subject_kernel_link.py`는 **제 미수정 초안**입니다. `current_setting('inv.tenant_id')` 바인딩이 없습니다.

SECURITY DEFINER 함수는 소유자로 실행되어 **RLS를 우회**하므로, 호출자가 `p_tenant_id`에 아무 tenant나 넣으면 **다른 tenant의 사용자가 승인 주체로 등록돼 있는지** 알 수 있습니다.

읽어서 주장하는 대신 **실제로 재현했습니다**:

```
session tenant : A
asked about    : tenant B's user
  their 0026 -> True    <-- reads across tenants
  fixed 0028 -> False   <-- bound to the session scope
```

**제 버그를 Codex가 물려받은 것**이고, 지금 통합을 향해 가고 있습니다. 수정본은 제 `0028_subject_kernel_link`에 있습니다 — 차이는 한 줄입니다:

```sql
AND p_tenant_id = nullif(pg_catalog.current_setting('inv.tenant_id', true), '')::uuid
```

같은 이유로 신규 `run_committed_outputs`(0029)와 `apply_resource_offer`(0030)도 처음부터 바인딩해 두었습니다. **0030은 쓰기 경로**라 더 중요합니다.

### 확인한 사항

`result_view.py`(275줄)와 `test_business_results.py`(397줄)는 제 `results.py` 위에 커널 쪽 정본 view를 얹은 것으로 보입니다. 두 구현이 같은 개념을 다루므로 **어느 쪽이 정본인지 정해야 합니다** — 제 쪽은 `public` 권한 검사와 "없는 값은 null+reason", 그쪽은 커널 기록입니다. 중복은 이번이 세 번째이고(handoff, binding에 이어), 매번 Codex 쪽이 커널 기록에 더 가까웠습니다.

---

## 7. 자원 제공량 연결 (신규)

**`public.resource_offers`와 `inv.resources.offered`가 연결돼 있지 않았습니다.** 커널은 lease를 주기 전에 `inv.resources.offered`를 검사하고, 제 설정 API는 `public.resource_offers`를 씁니다. 즉 **운영자가 화면에서 제공량을 낮춰도 스케줄러가 읽지 않는 숫자만 바뀌고**, 기계는 주인이 방금 그만 받으라고 한 일을 계속 받았습니다.

migration 0030이 커널 자신의 규칙으로 적용합니다:

- `offered <= capacity` — 커널이 **관측한** 용량을 넘을 수 없습니다(제 쪽 capability 검사와는 다른 사실이고, 둘 다 성립해야 합니다).
- `offered >= 반납되지 않은 lease 합` — **커널의 규칙이고 제가 문서에 쓴 것보다 엄격합니다.** 저는 "낮춘 제공량은 새 예약에만 적용되고 진행 중 작업은 반납까지 돈다"고 썼는데, 커널은 **아예 거부**합니다. 주인이 이제 허용하지 않는 양을 계속 붙들고 있지 않겠다는 것이고, 그쪽이 맞습니다. 문구를 고쳤습니다.

커널이 **관측한 적 없는 노드**는 거부가 아니라 보고입니다 — 실행용으로 등록되지 않은 기계에 주인이 의사를 기록하는 것은 정상 상태입니다.
