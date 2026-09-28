---
doc_id: "HIST-CLAUDE-2026-09-28-G02-LIVE-ARCHIVER-IMPL"
title: "G-02 live archiver hosted 실행 구현 (2단계) — _recovery_capability(dsn=None, *, execute=None) 실행자 주입, docker_exec_settings_executor(공유 SQL 상수·fail-closed), 시험 2 케이스를 docker exec 경로로(격리·port 미publish 유지, CX01 fixture 전제 제거), Backend CX01 map 19→17 + 이미지 env, Core focused gate 18/2→20/0, PG-free 되돌림 시험 (카드 54 2단계, PR #181 위 stack + #159 head 5e206aa4 merge)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T14:44:26+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "5490de3c"
task_ids: ["S12-ST"]
tags: ["G-02", "recovery", "rpo", "hosted", "claude"]
---

# G-02 구현 (2026-09-28, 카드 54 2단계)

설계 [[G-02 live archiver hosted 실행 설계 v1.0]] v1.1(PR #181, Codex 승인 head 5490de3c) 그대로. base는 #181 branch에 **#159 head `5e206aa4`(#126 Core CX01 gate 포함)를 merge**한 것 — core.yml focused gate를 실측 기준으로 고치기 위함(설계 §7). 병합은 #159·#181 뒤.

## 1. 바뀐 것

| 파일 | 내용 |
|---|---|
| `tools/recovery_drill.py` | `_CAPABILITY_SETTING_NAMES`(고정 7)·**`_CAPABILITY_SETTINGS_SQL`**(접기 CASE를 담은 단일 SQL 상수; 이름은 literal 인라인) · `_settings_from_rows`(7개 전부·그 밖 없음, 아니면 RuntimeError) · `psycopg_settings_executor(dsn)`(기본, 오늘의 `_conn` 경로) · `docker_exec_settings_executor(container, user, run, timeout)`(`docker exec <c> psql -X -At -F <tab> -v ON_ERROR_STOP=1 -U postgres -d postgres -c <SQL>`; exit≠0·timeout·OSError·기형 줄·누락 이름 → **RuntimeError**, 메시지에 exit code·누락 이름만, stdout/stderr 미노출) · **`_recovery_capability(dsn=None, *, execute=None)`**: execute 없으면 dsn 필수(기본 실행자), 있으면 dsn 무시; 판정·dict 모양 변경 0. 호출자 `tools/recovery_drill.py:778`(드릴 본체) 변경 0 |
| `tests/integration/test_recovery_drill.py` | `_exec_sql(name, sql)` 전송 helper(판정 없음) · `archiver_image` fixture(`INV_TEST_ARCHIVER_IMAGE` → 없으면 `CX01_CONTAINER`의 이미지 → 둘 다 없으면 고정 사유 skip) · 2 케이스가 `args` 대신 `archiver_image`를 받음(장벽 1 제거) · `--internal` 생성·`Internal is True` 단언 유지 + **`HostConfig.PortBindings` 비어 있음 단언 추가**(port 미publish) · readiness·`pg_switch_wal`·`pg_stat_archiver` 폴링을 `_exec_sql`로 · capability는 `drill._recovery_capability(execute=drill.docker_exec_settings_executor(name))` · `_classify_archiver_connection_failure`의 `hostPortPublished=False` skip 분기 삭제 → ready인데 probe 실패는 **AssertionError**(장벽 2 제거) |
| `tests/test_recovery_drill_prerequisites.py` | "ready + 포트 없음 = skip" 시험을 "= AssertionError(in-container probe still failed)"로 |
| `tests/test_recovery_capability_executor.py` (신규, PG-free) | 실행자 주입 시 `_conn` 미호출·dsn 무시 · execute/dsn 둘 다 없음 ValueError · docker exec 인자·공유 SQL·fold 값 · 원문 명령 문자열이 report·오류 메시지에 없음 · 실패 6형(exit 1·timeout·FileNotFound·이름 누락·기형 줄·미지 이름) → RuntimeError · 누락을 기본값으로 안 만듦 · 시험 파일이 `rpo_bound_from`을 호출하지 않음 · live 케이스 소스가 `args`·`psycopg.connect`를 쓰지 않고 `docker_exec_settings_executor`·`--internal`을 쓰며 `-p`가 없음(정적) |
| `.github/workflows/backend.yml` | job env `INV_TEST_ARCHIVER_IMAGE: postgres:16` 1줄 · exact skip-map `'CX01_CONTAINER is unset; …'` **19 → 17** |
| `.github/workflows/core.yml` | focused gate "Require executed CX01 recovery evidence": `internal_network_reason` 상수 삭제, `skips == Counter()`, `passed == 20`(18/2 → **20/0**). main-suite exact map 불변 |

## 2. 로컬 검증(가벼운 명령만)

- `tests/test_recovery_capability_executor.py` 전부 passed; `tests/test_recovery_drill_prerequisites.py`는 내 변경 시험 passed(같은 파일의 `test_unknown_spawn_error_is_not_hidden_as_environment_skip` 1건은 **변경 전 base에서도 이 PC에서 실패** — 이 PR과 무관, hosted에서 확인).
- Docker·실 PG 없음 → live 케이스 2건의 실제 실행은 **hosted에서만**(NOT_OBSERVED until run): Backend 양 버전(exact map 17 gate 통과·이 2 케이스 passed) + Core `run-core`(focused gate 20/0). run ID는 PR 코멘트로.

## 3. 되돌리면 실패하는 것(설계 §6 ↔ 시험)

실행자 무시 → `test_the_injected_executor_is_used…`; 원문 반환 → `test_the_archive_command_text_never_reaches_the_report` + live `archive_command not in json.dumps`; 실패 삼킴 → `test_every_executor_failure_raises…`; port publish → live `PortBindings` 단언·정적 `-p` 부재; skip 분기 부활 → prerequisites 시험; CX01 전제 복귀 → Backend map 17 gate + 정적 `args` 부재; 장벽 2 복귀 → Core gate 20/0; 판정 복제 → 정적 `rpo_bound_from` 부재.

owner Claude / reviewer Codex / 병합 금지. branch `agent/claude/g02-live-archiver-impl`, force-push·`git add -A` 없음.
