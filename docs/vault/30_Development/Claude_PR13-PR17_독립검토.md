# PR #13·#15·#16·#17 독립 검토 — Claude

- 검토자: Claude
- 대상: #13 workspace-api, #15 shard-recovery, #16 business-kernel, #17 node-containment (적층 draft)
- 방법: 최신 Codex head(`dac2559`)에서 분기하여 **중복되지 않은 Claude 작업만 얹고 실행**
- 결과 브랜치: `review/claude-pr13-pr17` (`c3c88da`)
- 검증: Backend Build **success** (795 passed, skip 0), Core Build **success**, Documentation Build **success**

---

## 먼저: 제 PR #14가 틀린 부분

검토는 지적으로 시작하는 게 아니라 **제가 틀린 것을 인정하는 것으로** 시작해야 합니다. `0021_business_kernel.sql`의 첫 두 줄이 제 작업에 대한 Codex의 판단입니다:

```sql
-- PR14's business concepts, connected to canonical inv execution records.
-- No old revision renaming, automatic epoch roll, public approval-ID rewrite,
-- LOGIN credential creation, or broad inv grants to inv_app.
```

다섯 항목 전부 제가 한 것이고, **네 개는 Codex가 옳습니다.**

### 1. 마이그레이션 재번호는 틀렸습니다 — merge revision이 맞습니다

제가 PR #14에서 갈래를 푼 방식은 제 `0008`·`0009`·`0010`을 `0019`~`0021`로 **재번호하고 재지정**하는 것이었습니다. Codex는 대신 두 부모를 갖는 merge revision을 만들었습니다:

```python
revision = "0019_workspace_api_integration"
down_revision = ("0018_workspace_resume", "0010_canonical_resource_units")
```

그 파일의 docstring이 제 방식에 대한 정확한 반박입니다: **"Do not rewrite already published revision parents."**

제 방식은 이미 적용된 revision 식별자를 바꿉니다. `0008_node_certificate_lookup`을 적용한 데이터베이스는 재번호 후 **체인에 존재하지 않는 `alembic_version` 값**을 갖게 됩니다. CI는 매번 새 DB라 통과했고, 실제 배포에서는 업그레이드 경로가 끊깁니다. **어느 쪽도 움직이지 않는 Codex의 해법이 맞습니다.**

### 2. `inv_kernel`이 `inv_app` 확대보다 낫습니다

정책 자체는 **제 0022와 문장 단위로 동일**합니다 — 같은 GRANT, 같은 REVOKE, `control_epoch`의 `UPDATE(singleton)`, sentinel 컬럼까지. 우리는 몇 시간 간격으로 같은 fixture 정책을 스키마로 독립적으로 옮겼습니다.

차이는 **역할 이름**이고, 그게 설계 차이입니다. 저는 `inv_app`(public이 이미 쓰는 role)에 부여했습니다 — 한 커넥션이 이음매를 건너게 하려고. Codex는 별도 `inv_kernel` 그룹 role을 만들고 `inv_app`의 inv 접근을 **넓히지 않았습니다.**

Codex가 옳습니다. 업무 웹 프로세스와 실행 커널은 폭발 반경이 다릅니다. 같은 role을 쓰면 **업무 API 침해가 곧 실행 커널 권한**입니다. 그리고 Codex의 방향이 더 좋습니다 — 커널이 public을 **컬럼 단위 SELECT로** 읽습니다:

```sql
GRANT SELECT(tenant_id,project_id,user_id,role_code) ON public.project_members TO inv_kernel;
GRANT UPDATE(released_at) ON public.workspace_edit_locks TO inv_kernel;
```

신뢰의 방향이 "업무 API가 실행을 구동한다"가 아니라 "실행 커널이 업무 사실을 읽는다"입니다. 제 `core_gateway.py`는 전자를 전제하고 있었습니다.

### 3. 업무 handoff는 중복이고, Codex 쪽이 더 잘 연결되어 있습니다

`public.workspace_edit_locks`와 `public.execution_bindings` — **같은 이름, 같은 스키마, 같은 개념을 양쪽이 만들었습니다.** 제 것은 `resume_id`·`checkout_id`가 외래키 없는 맨 UUID였습니다. Codex 것은 실제로 참조합니다:

```sql
FOREIGN KEY(tenant_id,resume_id) REFERENCES inv.workspace_resumptions,
FOREIGN KEY(tenant_id,approval_id) REFERENCES inv.approval_requests
```

즉 **존재하지 않는 resumption이나 승인을 가리키는 binding이 저장될 수 없습니다.** 제 것은 그걸 서비스 코드로만 막았습니다. 여기에 `workspace_api.py`(310줄)와 `test_business_handoff.py`(473줄)가 붙어 있습니다.

**제 `handoff.py`·`core_gateway.py`·`api/v1/execution.py`·`db/models/handoff.py`와 마이그레이션 0022~0025는 철회합니다.**

### 4. approval ID 재작성과 epoch 자동 시드도 철회합니다

`apv_`→`apr_` 재작성은 이미 발행된 식별자를 바꾸는 것이고, 재번호와 같은 종류의 잘못입니다. epoch는 `0001_core.sql`이 "Operator provisions a fresh epoch outside the DB backup before runtime starts"라고 명시하고 있었습니다 — 운영자 절차이지 마이그레이션이 대신할 일이 아닙니다.

**다만 이건 남습니다**: 그 운영자 절차가 실행되지 않으면 실행 커널의 모든 트랜잭션이 LEASE-0004로 실패합니다. 배포 문서에 명시적 단계로 있어야 하고, 없으면 첫 배포에서 발견됩니다.

### 5. `migration_graph.py`는 Codex가 고쳤습니다

제 도구는 merge revision의 튜플 `down_revision`을 정규식으로 읽지 못해 `revision or down_revision not declared`로 죽습니다. Codex가 `str | tuple[str, ...] | None`로 확장하고 docstring의 "linear chain"을 "acyclic graph with one integrated head"로 일반화했습니다. 제 전제가 틀렸고 그쪽이 고쳤습니다.

---

## 남은 지적 사항

### A. Backend Build가 다시 양쪽 절반을 함께 돌리지 않습니다 — 재발

```yaml
run: python -m pytest -q --strict-markers --ignore=tests/core --ignore=tests/integration ...
```

PR #14 검토의 지적 #3이 그대로 돌아왔습니다. 그러면 **각 절반이 자기 컨테이너에서 통과하고 이음매는 아무도 시험하지 않습니다.**

이번 브랜치에서 되돌렸고, `tools/node_dependent_tests.py`가 import 그래프에서 제외 목록을 계산합니다. **손으로 쓴 목록이었다면 여기서 낡았을 겁니다** — 13개였던 것이 이 브랜치에서 17개가 됐고, `test_business_handoff`·`test_containment`·`test_shard_recovery`·`test_workspace_api`를 **편집 없이** 스스로 집어냈습니다.

결과: Backend Build가 795개를 한 PostgreSQL에서 통과. skip 0.

### B. 인증 없는 mock이 여전히 설치 패키지 안에 있습니다 — 부분 해결

PR #13이 `server.py`를 `demo_server.py`로 옮기고 `server.py`를 진짜 factory로 만들었습니다. **가장 가능성 높은 사고를 없앴습니다** — 운영자가 뻔한 이름에 uvicorn을 겨누는 것.

그래도 `demo_server.py`는 설치되는 패키지 안에 남아 있고, `POST /v1/approvals/{id}/approve`는 여전히 자격 증명 매개변수가 없습니다. `tests/test_package_surface.py`를 새 이름으로 옮겨 경계를 명시했습니다.

---

## 검토했고 문제 없음

- **merge revision이 실제로 동작합니다.** 빈 DB에서 head까지, 반복 upgrade, 역전 가능한 꼬리 — 이 브랜치의 Backend Build에서 전부 통과.
- **RLS와 컬럼 단위 권한이 새 테이블 전부에 걸려 있습니다.** `business_projects`·`business_subjects`·`business_runs` 모두 ENABLE+FORCE+정책, `guard_business_identity`/`guard_business_binding`/`guard_business_unlock`은 PUBLIC에서 EXECUTE 회수.
- **`inv.business_subjects`의 OIDC 매핑이 단사(injective)입니다** — `UNIQUE(tenant_id,user_id)`. 한 업무 user를 여러 투표자로 매핑할 수 없으니, 2인 승인이 한 사람의 두 신원으로 채워지지 않습니다.

---

## Claude 쪽에서 이번에 가져온 것

Codex 스택에 없고 대체되지도 않은 것만:

- **eval 실행기와 게이트 수정** — `finish_eval_run`은 "위반 없고 전부 **기록됨**", `score_report`는 "위반 없고 전부 **통과함**"을 게이트로 봤습니다. 통과도 실패도 아닌 결과가 나오기 전엔 차이가 안 보이는데, `errored`가 생기자 **전부 타임아웃인 run이 게이트를 통과했습니다.** 제공자 장애가 깨끗한 합격으로 읽혔을 상황입니다. `gate_passed`에 한 번만 정의했습니다.
- `tools/node_dependent_tests.py`와 Backend Build 시험 범위 (지적 A)
- 패키지 표면 가드 (지적 B)
- 유도식 계약 export — 한 번도 발행된 적 없던 응답 계약 2개를 찾았습니다.
