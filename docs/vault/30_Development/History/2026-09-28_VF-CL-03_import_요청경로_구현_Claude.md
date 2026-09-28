---
doc_id: "HIST-CLAUDE-VFCL03-IMPORT-REQUEST-PATH-IMPL-001"
title: "VF-CL-03 import adapter 요청 경로 구현 — 공유 정본 ProblemDetails 모듈·strict body helper·release route, Codex F-R1~F-R3 반영(운영 factory 결속·threadpool self-call·redirect 거부·streaming 상한·실 PG node 6건), PG-free 58 + 실 PG 6"
version: "1.2.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T11:58:12+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["VF-CL-03"]
tags: ["vf-cl-03", "model-registry", "import", "problem-details", "implementation", "claude"]
---

# VF-CL-03 import adapter 요청 경로 구현

승인된 설계 `#152` v1.3(head `e9e5e78e`)을 그대로 구현했다. base는 `origin/integration/all-agents-unified`(`1e8baf04`)다. 로컬 실 PG·Docker·전체 suite는 돌리지 않았고, 돌린 것은 PG-free 레인이다.

## 1. 착지한 것

| 파일 | 내용 |
|---|---|
| `src/saintvision/api/problem.py` (신규) | 정본 `ProblemDetails` 예외·응답·handler, 그리고 공유 `strict_json_object`·`require_absent_body`·`validate_strict`·`translate` |
| `src/saintvision/api/v1/model_release.py` (신규) | release route와 그 세 구간, route별 번역표 |
| `src/saintvision/api/schemas.py` | `ModelReleaseRequest`, `ModelReleaseResponse` |
| `src/saintvision/api/app.py` | canonical handler 1회 등록 (기존 handler 불변) |
| `src/saintvision/api/v1/projects.py` | `model_release.register(router)` 한 줄 |
| `src/saintvision/config.py` | `kernel_base_url`(`INV_KERNEL_BASE_URL`) |
| `contracts/model-release-{request,response}.schema.json` | `export_schemas.py` 생성물 |
| `tests/core/test_model_release_route.py` (신규) | 설계 §9의 부정 시험, 49 test |

## 2. 설계와 달라진 것 3건 — 구현하며 찾은 사실

### 2-1. 응답 타입 이름을 `ModelReleaseResult` → `ModelReleaseResponse`로 바꿨다

`tools/export_schemas.py::exported()`는 **이름이 `Request` 또는 `Response`로 끝나는 `Strict` 파생 클래스만** 수집한다. `ModelReleaseResult`라는 이름은 그 규칙에 걸리지 않아 **JSON Schema가 생성되지 않고 `--check`도 통과**한다 — 그 도구의 docstring이 스스로 "가장 조용한 실패"라고 부르는 상태다. 설계가 승인된 이름을 바꾸는 것이므로 여기 적는다. 지금은 `contracts/model-release-response.schema.json`이 생성되고 gate가 본다.

### 2-2. 요청 검증은 `validate_contract`가 아니라 Pydantic이다

설계 v1.2가 이미 지적한 대로 business 타입은 정본 `$defs`에 없으므로 `validate_contract("ModelReleaseRequest", …)`는 불가능하다. handler가 `ModelReleaseRequest.model_validate()`를 부르고 `ValidationError`를 잡아 `VAL-0003`으로 번역한다. `errors()`는 직렬화하지 않는다(필드 경로·입력 값이 들어간다). 커널 관측 검증은 정본 `$def`이므로 `validate_contract("ModelCommitObservation", …)` 그대로다.

### 2-3. route를 어디에 등록하는지가 제약이었다

`inv.business_surface.BusinessDispatch`는 `projects`·`settings`·`adapters` 세 router의 `routes`를 읽어 business 트래픽을 고른다. 그래서 (i) 새 top-level router는 business app에 등록되지만 **배포 토폴로지에서 요청이 도달하지 않고**, (ii) `projects.router.include_router(...)`도 안 된다 — 이 FastAPI 버전은 `_IncludedRouter` **지연 placeholder**를 남기므로 dispatch가 읽는 시점에 route 객체가 `routes`에 없다(실측). 그래서 `model_release.register(router)`가 `add_api_route`로 실제 route를 넣는다. 커널 소유 파일은 건드리지 않았다. 부정 시험이 세 router의 선택 목록에서 이 경로를 찾는다.

## 3. 설계대로 구현한 경계

- **세 구간**: 인증·본문 파싱(tx 없음) → 짧은 tx에서 live `require_project_access` + `canApprove` → **tx 종료** → 커널 HTTP + strict 검증(tx 없음) → 새 tx에서 권한 재확인 → parent `models` 소유 확인 → `(model_id, version)` `with_for_update()` → 관측 identity 재결속 → 기존 전제 검사 → 선언 비교 → release → 감사. 커널 호출 시점의 열린 트랜잭션 수가 **0**임을 시험이 깊이로 관측한다.
- **번역표는 route별**이다. `VAL-SCHEMA`는 이 호출 지점에서 상태 전제이므로 `GRAPH-0002` 409, 선언 불일치는 `MODEL-0009` 409, project 접근 불가는 `AUTH-0030` 403. 표에 없는 code는 `SYS-0002` 500이고, 시험이 `release_model_version` 본문을 정규식으로 읽어 **거기서 나오는 code가 표에 다 있는지** 확인한다(새 거부가 추가되면 시험이 깨진다).
- **본문 경계**: Content-Type `application/json`(415, `Content-Encoding` 존재도 415) · 8 KiB(413) · 빈 본문·invalid UTF-8·문법·nesting·duplicate key·non-finite·배열·scalar·제약 위반(422). 파싱은 커널 `inv.identity.strict_object`에 위임한다.
- **정본 body**: 10키 정확히, `about:blank`, code별 status·retryable, `inv.contracts.validate_contract` 앵커, `application/problem+json` + `no-store`.
- **값 미노출**: 불일치 이유는 `detail`에 **필드 이름만**, 감사 `detail`은 `declarationFields` 이름 배열만. `services/audit.py::redact`가 `license`·`classification`을 덮지 않는다는 것을 시험이 직접 확인한다(자동 보호가 없으므로 넣지 않는 것이 유일한 방어).
- **커널 자격증명**: 호출자의 bearer를 그대로 전달한다. 서비스 신원을 쓰면 호출자가 스스로 읽을 수 없는 commitment를 이 route가 읽어 주게 된다.

## 4. 새로 결정한 것 2건 (설계에 없던 빈칸)

1. **커널 HTTP 클라이언트가 없었다.** business 제품 코드는 커널과 DB(`project_kernel_link`)로만 이야기하고 `requirements-core.txt`에 HTTP 클라이언트가 없다(`httpx`는 test 전용). 그래서 표준 `urllib.request`로 GET 하나를 보내고 timeout 5초를 둔다. 의존성을 늘리지 않았다.
2. **`kernel_base_url`이 없으면 `SYS-0001` 503**이다. 호스트를 추측하지 않는 것이 `config.py`의 규칙이고, 커널도 미설정을 503으로 답한다(`inv/app.py:629`·`:932`). 시험은 이 경우 **fetch가 아예 일어나지 않음**도 단언한다.

## 5. 관측하지 못한 것 (정직한 경계)

- **실 PG 3건은 돌리지 않았다** — 타 tenant 404(RLS), path project 불일치가 타 tenant와 같은 404, 실패 시 `draft` 유지. 근거는 hosted Core·Backend에 둔다. PG-free 시험의 세션은 route가 부르는 호출에만 답하는 대역이라, 증명하는 것은 **route의 순서와 wire 계약**이고 데이터베이스의 행동이 아니다.
- `committed != true` 분기는 정본이 `const: true`를 박고 있어 **현재 도달 불가**다. 검증을 stub한 시험으로만 덮었고, 그 사실을 코드 주석과 시험 이름에 적었다.
- `register_model_version`·`verify_model_version`·`pin_retention`은 **여전히 HTTP 경로가 없다**. 이 카드는 승격 한 지점만 열었고 blocker의 나머지는 장부에 남는다.

## 6. 검증 증거 (실행)

- `pytest tests/core -q` → **1081 passed, 4 skipped**(72s). 신규 파일만: `tests/core/test_model_release_route.py` → **49 passed**.
- `python tools/export_schemas.py --check` → **PASS: 60 contract schemas match their models**.
- `python tools/route_coverage.py --served src --served services/control-plane/src --client apps/web/src` → **0 unserved**, exit 0.
- `python tools/check_docs.py`, `python tools/check_doc_single_source.py --ratchet` → exit 0.
- 로컬 실 PG·Docker·전체 suite **미실행**(메모리 규칙).

## 7. 다음 첫 행동

Codex 독립 검토. 검토가 끝나면 실 PG 3건을 hosted Core·Backend 결과로 확인하고, 남은 model-registry 쓰기 경로(등록·검증·pin)를 별 카드로 올린다.

## 8. v1.1 — Codex 계약·보안 검토 F-R1~F-R3 반영 (`10c89c91` 대상)

세 건 모두 타당했다. 특히 F-R1은 **운영에서 route가 항상 503**이었다는 것이므로, 요청 경로 blocker가 실제로 닫히지 않은 상태로 올린 것이다.

### 8-1. F-R1 — 운영 factory에 `kernel_base_url`이 결속되지 않았다

`services/control-plane/src/inv/business_surface.py:72`가 `Settings(database_url="configured")`만 만들어 `kernel_base_url=None`이었고, 그러면 `_observation()`이 fetch 전에 항상 `SYS-0001` 503이다. `Settings.from_env()`는 개발 helper라 배포 경로와 무관하다.

- 운영 factory가 `INV_KERNEL_BASE_URL`을 읽고, 없으면 `http://127.0.0.1:${PORT}`를 쓴다. 커널과 business가 **같은 프로세스·같은 포트**(`BusinessDispatch`)이므로 self URL은 추측이 아니라 프로세스가 바인딩하는 값 그대로다. `docker-compose.prod.yml`에도 같은 입력을 넣었다.
- **event loop 차단**도 지적대로 실재했다. 같은 프로세스 self-call에서 `urllib`을 async handler에서 직접 부르면, 그 GET을 처리해야 하는 loop가 막혀 5초 timeout으로 끝난다. fetch를 `starlette.concurrency.run_in_threadpool`로 옮겼다(커널이 이미 쓰는 방식).
- 대안으로 커널 관측 객체를 in-process로 부르는 길이 있었지만, 커널 소유 코드와 그 identity 객체를 재조립해야 하고 **커널 authorization이 관측의 유일한 관문이라는 성질을 잃는다**. 그래서 HTTP를 유지했다.
- 회귀 시험: fetcher가 **loop thread가 아닌 곳에서, running loop 없이** 실행됨을 단언한다(`run_in_threadpool`을 지우면 deadlock 대신 시험이 깨진다). 운영 factory 결속과 compose 입력도 단언한다.

### 8-2. F-R3 — caller bearer의 transport 경계

- **redirect 자동 추종**이 실재했다. Python `HTTPRedirectHandler`는 `Authorization`을 redirect 요청에 복사하므로, 커널이 다른 origin으로 30x를 내면 **호출자 bearer가 그 origin으로 간다.** `_RefuseRedirect` opener로 모든 redirect를 거부한다. 시험은 **실제 HTTP 서버**를 띄워 30x를 내고, redirect 대상이 요청을 아예 받지 못함을 확인한다.
- **무제한 read**도 실재했다. `MAX_OBSERVATION_BYTES = 65536`으로 상한+1만 읽고 넘으면 거부한다. 상한 초과·redirect 거부·scheme 위반 모두 값 비노출 `SYS-0001` 503이다.
- **invalid UTF-8이 500으로 빠진다**는 지적은 **재현되지 않았다.** `UnicodeDecodeError`는 `ValueError`의 파생이고(`UnicodeDecodeError → UnicodeError → ValueError`) `_observation()`의 catch 목록에 `ValueError`가 있으므로 이미 canonical `SYS-0001`이다. 실제 HTTP 서버가 invalid UTF-8을 내는 시험으로 그 동작을 고정했다 — 주장만 하지 않고 시험으로 남긴다.
- **요청 8 KiB가 parser 상한일 뿐이라는 지적도 맞았다.** `await request.body()`는 전부 버퍼링한 뒤에야 길이를 볼 수 있다. 공유 `read_bounded_body()`를 만들어 `request.stream()`을 읽으며 **상한을 넘는 첫 chunk에서 거부**한다(커널 ASGI 미들웨어와 같은 성질의 per-route 버전). 문서로 한계를 적는 쪽이 아니라 streaming cap을 택했다.

### 8-3. F-R2 — 실 PG node가 diff에 없었다

`tests/core/test_model_release_route.py` 하나만 올렸으므로 hosted Backend green이 실 PG 3건의 실행 증거가 아니라는 지적이 정확하다. PR 본문의 "hosted에 둔다"는 **그 시험이 존재할 때만** 참이다.

`tests/integration/test_model_release_real_pg.py`(신규, `pytest.mark.postgres`) 6 node를 추가했다 — 타 tenant model version이 같은 거부로 끝나고 행 불변 · 접근 가능한 project 아래의 타 tenant model이 404 · 같은 tenant 다른 project의 model도 **같은** 404 · 선언 불일치 후 `stage='draft'` 유지 + 감사 0행 · 양성 대조(200 `released`, 감사 1행, 선언 값 0) · `operator` 등급은 403. disposable 실 PG 단일 파일이고 로컬은 `INV_TEST_ADMIN_DSN` 부재로 skip이므로 **실행 근거는 hosted Backend JUnit**이다.

### 8-4. v1.1 검증 증거

- `pytest tests/core -q` → **1090 passed, 4 skipped**. `tests/core/test_model_release_route.py` → **58 passed**(v1.0의 49 + F-R1/F-R3 9건).
- `tests/integration/test_model_release_real_pg.py` → 로컬 **6 skipped**(DSN 부재). hosted Backend 결과를 PR에 적는다.
- `export_schemas.py --check` **60 PASS**, `route_coverage` **0 unserved**, docs gate 2종 exit 0.
- 로컬 실 PG·Docker·전체 suite **미실행**.

## 9. v1.2 — 실 PG node가 hosted에서 fixture에서 죽었다 (`91b86111` 결과)

Codex 재검토: 두 Backend matrix(3.12·3.14)가 `tests/integration/test_model_release_real_pg.py`를 **수집·실행했고 skip이 아니었다.** 그런데 6개 전부 `_seed`에서 같은 이유로 실패했다 — `new_id("code_commit")`. 정본 `src/saintvision/ids.py`의 entity kind는 **`commit`**이고 `code_commit`은 **`model_lineage`의 edge kind**다. 두 어휘를 같은 것으로 쓴 것이 내 실수다. 결과는 각 matrix `6 failed, 2987 passed, 47 skipped, 2 deselected`이고, 그래서 설계 §9의 28~30을 포함한 여섯 단언은 **제품 경로·트랜잭션 순서·롤백을 하나도 검증하지 못했다.**

- fixture가 `(lineage kind, id kind)` 쌍을 명시한다 — `("code_commit", "commit")`. 왜 다른지 주석에 적었다.
- **DB 없이 잡히는 실패였으므로 DB 없이 잡는 시험을 넣었다**: `tests/core/test_model_release_route.py`가 integration 모듈을 import해 `_seed`를 **statement만 기록하는 stub connection**으로 돌린다. id kind가 틀리면 그 자리에서 raise한다. 덧붙여 `set(LINEAGE_KINDS) - set(PREFIXES) == {"code_commit", "container_image"}`로 함정 자체를 문서화했다 — 두 lineage kind는 entity kind가 아니다.
- 이 판단은 hosted가 아니라 fixture 층의 결함이었고, 내가 실 PG를 돌리지 않는 동안 **fixture를 PG-free로 한 번도 실행하지 않은 것**이 원인이다. 앞으로 실 PG 파일을 올릴 때는 stub 실행을 같이 넣는다.

PG-free: `tests/core/test_model_release_route.py` **59 passed**(guard 1건 추가).
