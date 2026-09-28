---
doc_id: "CLAUDE-G02-LIVE-ARCHIVER-HOSTED-DESIGN-001"
title: "G-02 live archiver hosted 실행 설계 v1.0 — 권고안 (a) docker exec probe: 격리 네트워크 불변·port publish 금지, _recovery_capability(dsn)를 실행자 주입으로, 두 장벽(CX01 fixture·내부 네트워크 도달성) 제거, exact skip-map 19→17, 판정 논리 미복제 (카드 54, docs-only)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T13:54:47+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S12-ST"]
tags: ["G-02", "recovery", "rpo", "archiver", "hosted", "design", "claude"]
---

# G-02 live archiver hosted 실행 설계 v1.0 (2026-09-28, 카드 54)

> [!note] 범위
> PR #179 §3-2의 G-02(운영 점검 live archiver 2 케이스가 hosted에서 항상 skip). 코디네이터 권고안 **(a) `docker exec` probe**를 설계한다. docs-only. G-01은 Claude tab 소관이라 건드리지 않는다. migration 없음(#179 §4 확정).

## 0. 실측으로 확인한 현재 상태

대상 케이스는 `tests/integration/test_recovery_drill.py:487` `test_live_archiver_configuration_cannot_certify_operational_rpo`의 parametrize 2건(`archive_command` = `/bin/true`, `/bin/false`).

**hosted에서 skip되는 이유는 두 겹이다.** #179 §3-2는 두 번째 장벽(내부 네트워크 도달성)만 적었는데, 첫 번째 장벽이 먼저 걸린다.

| 순서 | 장벽 | 근거(실측) |
|---|---|---|
| 1 | **`args` fixture의 CX01 소유 컨테이너 전제** — `tests/integration/test_recovery_drill.py:32` `args(postgres)`가 `resolve_owned_postgres_container()`를 호출하고, `tests/recovery_drill_prerequisites.py:22`가 `CX01_CONTAINER` 미설정 시 skip | hosted Backend run 36377166070(#172 head bda7ef86)의 `-rs` 목록: `[2] tests/integration/test_recovery_drill.py:488: CX01_CONTAINER is unset; container identity/ownership cannot be verified`. exact skip-map(`.github/workflows/backend.yml:161`, `.github/workflows/core.yml:173`)이 이 사유를 **19**로 고정하고 있고, 그 19 중 2가 이 케이스다 |
| 2 | **내부 네트워크 도달성** — 컨테이너를 `docker network create --internal`(`test_recovery_drill.py:497`)에 붙이고 port를 publish하지 않으므로 host의 `psycopg.connect(dsn)`(`:541`)이 닿지 못한다. `_classify_archiver_connection_failure`(`:106`)가 `hostPortPublished=False`를 확인하면 정직하게 skip(`:191-197`) | 장벽 1이 걸려 hosted에서는 아직 관측되지 않았다(NOT_OBSERVED). 로컬 CX01 환경에서만 관측된 사유이며 #179 §3-2가 인용한 것이 이것이다 |

따라서 **장벽 1만 풀면 장벽 2에서 skip 2가 그대로 남고, 장벽 2만 풀면 hosted에서는 아무것도 바뀌지 않는다.** 둘 다 풀어야 skip 2 → 실행 2가 된다.

이 케이스가 `args`에서 실제로 쓰는 것은 두 가지뿐이다(`git grep -n -F "args.docker" -- tests/integration/test_recovery_drill.py` 결과 그대로):

```
tests/integration/test_recovery_drill.py:448:            args.docker,
tests/integration/test_recovery_drill.py:492:    base = json.loads(subprocess.check_output(["docker", "inspect", args.docker]))[0]
```

`:492`는 archiver 컨테이너를 띄울 **이미지 이름**(`base["Image"]`)을 얻기 위해서만 CX01 컨테이너를 inspect한다(`:448`은 다른 시험). 즉 이 케이스는 CX01 컨테이너의 정체성·소유권 검증이 필요한 시험이 아니라 "PostgreSQL 이미지 하나"가 필요한 시험이다.

## 1. 결정 — 권고안 (a) `docker exec` probe

- **격리는 그대로**: `docker network create --internal`(`:497`)과 `Internal is True` 단언(`:503`)은 바꾸지 않는다. **port publish 금지**(`-p` 추가 없음). 격리가 `archive_command` 실패를 의미 있게 만드는 장치라는 #179의 판단을 유지한다.
- **질의는 컨테이너 안에서**: host가 컨테이너에 접속하는 대신 `docker exec <name> psql …`로 컨테이너 안의 `psql`이 로컬 소켓으로 질의한다. 호스트 도달성이 필요 없어진다.
- **판정 함수는 인자 모양만 바꾼다**: `tools/recovery_drill.py:470` `_recovery_capability(dsn)`은 지금 `_conn(dsn)`(`:121`, psycopg)으로 직접 질의한다. 이를 **실행자(executor)를 주입**받게 바꾸고, 기본 실행자는 지금과 같은 psycopg 경로로 둔다. 판정 로직(`rpo_bound_from`, `:444`)과 결과 dict의 모양은 변경 0.
- **CX01 전제 제거**: 이 케이스는 `args` 대신 이미지 이름만 받는 작은 fixture를 쓴다. hosted에서는 워크플로가 이미 쓰는 서비스 이미지(`postgres:16`; `backend.yml`·`core.yml`의 `services.postgres.image`)를 환경변수로 넘긴다. CX01 컨테이너가 있으면(로컬) 그 이미지를 그대로 쓴다.

## 2. 바뀌는 시그니처

```python
# tools/recovery_drill.py (:470)  — 현재
def _recovery_capability(dsn: str) -> dict[str, Any]: ...

# 제안
SettingsExecutor = Callable[..., dict[str, str]]   # 인자: 읽을 pg_settings name 목록(Sequence of str)
#   입력: 읽을 pg_settings name 목록(고정 상수 7개; 외부 입력 아님)
#   출력: {name: setting} — archive_command/archive_library 값은 원문이 아니라 'configured'/'not configured'로 이미 접힌 값
#   (지금 SQL의 CASE 절과 같은 접기. 자격증명이 들어갈 수 있는 원문은 어느 실행자도 반환하지 않는다)

def _recovery_capability(dsn: str | None = None, *, execute: SettingsExecutor | None = None) -> dict[str, Any]:
    # execute가 None이면 지금과 동일: psycopg_settings_executor(dsn) (dsn 필수)
    # execute가 주어지면 dsn은 무시된다 (둘 다 None이면 ValueError)

def psycopg_settings_executor(dsn: str) -> SettingsExecutor:      # 기본 실행자 = 오늘의 SQL 그대로 (_conn(dsn))
def docker_exec_settings_executor(container: str, *, user: str = "postgres", run=subprocess.run) -> SettingsExecutor:
    # docker exec <container> psql -X -At -F '	' -U <user> -d postgres -c "<같은 SQL, name 목록은 상수라 literal 인라인>"
    # 결과 줄을 name	setting으로 파싱; 예상 이름 외 줄·파싱 실패·exit≠0 → RuntimeError (아래 §5)
```

- `_recovery_capability`의 **본문 판정은 그대로**: `settings = execute(names)` 한 줄이 `with _conn(dsn) … fetchall()` 블록을 대신하고, 그 아래 `rpo_bound_from(settings)`·dict 구성은 변경 없다.
- 접기(`CASE WHEN name IN ('archive_command','archive_library') …`)는 **SQL 안에 남는다**(두 실행자가 같은 SQL 문자열 상수 `_SETTINGS_SQL`을 공유). 시험이 접기를 흉내 내지 않는다.

## 3. 기존 호출자 (git grep -n -F "_recovery_capability" -- tools tests src services, 그대로 복사)

```
tests/integration/test_recovery_drill.py:544:        capability = drill._recovery_capability(dsn)
tests/integration/test_recovery_drill.py:569:            {"recoveryCapability": drill._recovery_capability(dsn)}, 900
tools/recovery_drill.py:470:def _recovery_capability(dsn: str) -> dict[str, Any]:
tools/recovery_drill.py:778:    report["recoveryCapability"] = _recovery_capability(args.source)
```

- `tools/recovery_drill.py:778`(드릴 본체, host DSN) → **변경 없음**(위치 인자 `dsn` 호환).
- `tests/integration/test_recovery_drill.py:544`, `:569`(이 케이스) → `drill._recovery_capability(execute=drill.docker_exec_settings_executor(name))`.
- 그 밖에 `:541`의 readiness 대기(`psycopg.connect`)와 `:557-573`의 `pg_switch_wal`/`pg_stat_archiver` 폴링도 host 접속이므로 같은 `docker exec psql` 경로로 옮긴다(시험 helper `_exec_sql(name, sql)`; 이 helper는 **전송만** 하고 판정하지 않는다). `_classify_archiver_connection_failure`(`:106`)는 readiness 실패 분류에 그대로 쓰되, `hostPortPublished=False` skip 분기(`:191-197`)는 **더 이상 도달하지 않는 경로**가 되므로 삭제한다(§6 되돌림 시험이 이를 잡는다).

## 4. hosted에서 skip 2 → 실행 2가 되는 조건

| 조건 | 어디서 충족 | 실패 시 |
|---|---|---|
| Docker CLI + 데몬(`docker run/exec/network`) | ubuntu 러너 기본; Backend·Core 둘 다 `docker` 사용 가능(`core.yml`은 이미 `docker run`으로 MinIO를 띄움) | skip(사유 문자열 고정, §5) |
| PostgreSQL 이미지 이름 | 새 env `INV_TEST_ARCHIVER_IMAGE`(워크플로가 `postgres:16`으로 설정; 서비스 컨테이너와 같은 이미지). 로컬은 CX01 컨테이너의 `Image`로 대체 | 둘 다 없으면 skip(사유 고정) |
| 내부 네트워크 생성 가능 | `docker network create --internal` — 러너에서 가능(권한 있음) | skip(기존 `:502` 사유 유지) |
| 컨테이너 안 `psql` | `postgres:16` 이미지에 포함 | 없으면 실패(AssertionError; skip 아님 — 이미지 계약 위반) |

워크플로 변경(2단계, 최소·Codex 검토): `backend.yml`·`core.yml`에 `INV_TEST_ARCHIVER_IMAGE: postgres:16` 한 줄, exact skip-map `'CX01_CONTAINER is unset; …': 19` → **17**(두 파일). 다른 값 변경 없음. Core는 `run-core` label로 실행.

## 5. fail-closed — 관측 못 하면 NOT_OBSERVED, 0이나 PASS 금지

- `docker_exec_settings_executor`: `docker exec` exit≠0, timeout, 출력 파싱 실패, 기대 이름 7개 중 누락 → **RuntimeError**(원문·stderr는 메시지에 넣지 않음; exit code와 누락 이름만). `_recovery_capability`는 이를 잡지 않는다 → 시험은 **실패**(skip 아님)하고, 드릴 CLI(`:778`)는 기본 실행자라 영향 없음.
- 설정을 읽지 못한 상태에서 `operationalRpoVerified=False`·`archivingConfigured=False`를 "관측"으로 적지 않는다: 값이 없으면 dict를 만들지 않는다(예외).
- 시험의 readiness 대기가 30초 안에 끝나지 않으면 `_classify_archiver_connection_failure`가 startup 실패를 AssertionError로 분류(기존)하고, 그 분류가 불가하면 역시 AssertionError. skip은 §4 표의 전제 부재 두 가지뿐이며 사유 문자열은 exact skip-map에 고정된다.
- Evidence 표기: hosted에서 실행되면 S12-ST/S02 지도의 이 두 케이스는 CI_LANE_GAP → **실행·통과/실패**로 바뀐다. label 없이 Core가 돌지 않은 run은 NOT_OBSERVED 그대로.

## 6. 되돌리면 실패하는 시험(2단계에서 추가)

| 되돌림(변이) | 잡는 시험 |
|---|---|
| `_recovery_capability`가 `execute`를 무시하고 `_conn(dsn)`을 다시 쓴다 | PG-free: `execute=`에 기록용 실행자를 주고 `dsn=None` → 실행자 호출 1회·psycopg 미호출(monkeypatch `_conn`이 AssertionError) |
| `docker_exec_settings_executor`가 archive_command 원문을 돌려준다 | PG-free(가짜 `run`): 출력에 `archive_command	configured`만 허용, 원문 명령 문자열이 결과 dict 어디에도 없음 — 지금 `:547` 단언(`archive_command not in json.dumps(capability)`)과 같은 축 |
| exit≠0/파싱 실패를 빈 dict로 삼킨다 | PG-free(가짜 `run` exit 1 / 이름 누락) → RuntimeError, dict 없음 |
| 시험이 port publish로 돌아간다 | 기존 `net.get("Internal") is True` 단언 유지 + 새 단언: `docker inspect <name>`의 `HostConfig.PortBindings`가 비어 있음 |
| `hostPortPublished=False` skip 분기가 살아난다 | 기존 `test_classify_…` 계열(`:106` helper 시험)에서 "ready + 포트 없음"이 skip이 아니라 **AssertionError**(도달 불가는 이제 설계 위반)로 바뀐 것을 단언 |
| CX01 전제가 다시 붙는다 | hosted exact skip-map 17: 19로 되돌리면 워크플로 단언 `actual_skips == expected_skips`가 실패 |
| 판정 로직을 시험에 복제 | 시험은 `capability[...]` 값만 단언하고 `rpo_bound_from`을 호출·재구현하지 않는다(코드 리뷰 항목; `git grep -n -F "rpo_bound_from" -- tests`가 시험 파일에서 0건이어야 함 — 현재 0건) |

## 7. 2단계 구현 PR 범위(이 설계 위 stack)

`tools/recovery_drill.py`(실행자 2 + 시그니처), `tests/integration/test_recovery_drill.py`(케이스 2를 docker exec 경로로, 이미지 fixture, skip 분기 삭제), PG-free 시험 파일 1(실행자·되돌림), `backend.yml`·`core.yml`(env 1줄 + skip-map 19→17). **migration 없음**; 필요해지면 멈추고 번호를 요청한다. 증거: hosted Backend 양 버전 + Core(`run-core`) run ID, 이 케이스 2건의 실행·결과 줄, skip-map 17 통과.

## 8. 경계

- 시험이 `docker exec`로 얻는 것은 **설정 값과 `pg_stat_archiver` 카운터**뿐이며, 운영 RPO를 "인증"하는 방향의 변화는 없다(단언은 그대로 "인증 불가").
- owner Claude / reviewer Codex(worker) / 병합 금지. worktree 재사용, branch `agent/claude/g02-live-archiver-design`, base `1e8baf04`, force-push 없음. 시각은 `date`.
