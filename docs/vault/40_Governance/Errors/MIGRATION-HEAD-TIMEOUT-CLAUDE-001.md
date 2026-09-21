---
doc_id: "MIGRATION-HEAD-TIMEOUT-CLAUDE-001"
title: "migration-head 시험 고정 타임아웃 — 도달/미도달 구분으로 처리. 별도 항목"
version: "2.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-21T21:30:00+09:00"
source_of_truth: "Git"
tags: ["saintvision", "test-reliability", "timeout", "reached-vs-not-reached", "migration", "resource-leak", "cleanup"]
---

# migration-head 시험 고정 타임아웃 (별도 항목)

`tests/test_account_integration.py::test_published_migration_heads_upgrade_without_rewriting`가 **오늘 두 번 연속 같은 이유로 실패**했다(마무리 회귀 배치 + 격리 재실행). 모두 `subprocess.TimeoutExpired`, 180초 고정 타임아웃이다. 이것을 부하 탓으로 넘기면 안 되는 이유: **호스트가 한가하면 통과·바쁘면 실패하면, 실패해도 사람이 "또 부하겠거니" 넘기게 되고 언젠가 진짜 결함도 같은 이유로 무시된다.** 오늘 우리가 계속 막아온 "신호가 의미를 잃는" 형태와 같다. 그래서 처리했다.

## 측정 — 부하가 아니라 타임아웃이 너무 짧았다
도구 `check_migration_upgrade.py`를 **한가할 때** 직접 측정: **3m20s(≈200s), exit 0**(마이그레이션 정상). 즉 **180s 여유가 음수(-20s)** — 도구가 구조적으로 ~200s인데 타임아웃이 180s다. 부하 의존 flakiness가 아니라 **타임아웃이 단순히 짧은 것**이다. (지난 40e921b에선 격리 <180s였는데 지금 ~200s — 마이그레이션 수 60개 불변·도구 불변이니 호스트/디스크가 느려진 결과.)

## 구조 — O(published priors), 매번 전체 재실행
도구는 `for prior in priors:` 각 published prior마다 **새 disposable DB를 만들고 그 prior→head 전체 마이그레이션을 replay**한다. priors·revisions가 늘면 시간이 늘어난다(구조적). 따라서 **타임아웃을 늘리는 것만으로는 근본 해법이 아니다**(언젠가 또 넘는다).

## 처리 — 도달/미도달 구분 (오늘 전반에 쓴 원칙)
타임아웃은 그 시험이 검증하려던 것이 **틀렸다는 증거가 아니라 도달하지 못한 것**이다. 진짜 마이그레이션 결함은 도구가 **non-zero exit**로 끝난다(budget 훨씬 이전). 그래서 두 신호를 분리했다(`test_account_integration.py`):
- **non-zero exit → FAIL**(진짜 결함, 기존대로).
- **TimeoutExpired → 이유보이는 SKIP**(미도달, 실패 아님): "…did not complete within Ns and never reached its assertions — incomplete run, not a migration defect."
- budget는 `INV_MIGRATION_CHECK_TIMEOUT`로 **조정 가능·기본 600s**(idle ~200s의 3배 여유).

이로써 **timing은 PASS(완료) 또는 SKIP(미완)만 내고 절대 오도하는 FAIL을 내지 않는다.** FAIL은 진짜 결함(non-zero exit) 전용이 되어, 부하로 실패가 둔갑하거나 진짜 결함이 부하로 치부되는 일이 사라진다.

## 검증 — 부하·한가 양쪽 일관
- **한가**: 기본 600s → **PASS**(211s).
- **부하**(CPU 4프로세스): → **PASS**(324s, 여전히 <600). idle과 같은 PASS = 일관.
- **강제 타임아웃**(`INV_MIGRATION_CHECK_TIMEOUT=5`): → **SKIP**(이유 명시), FAIL 아님.
- 즉 환경에 따라 PASS↔FAIL로 갈리던 것이 이제 **PASS로 일관**(극단·미래 성장 시에만 정직한 SKIP). 고친 것이 진짜다.

## 남은 권고 (Codex, 도구 소유)
budget 상향은 구조적 증가에 대한 stopgap이다. **근본은 도구를 incremental하게**(매번 전체 replay 대신 head만/증분, 또는 priors 표본화) 만드는 것이다. 그때까지 skip-on-timeout이 성장을 정직히 흡수한다. 진행 상황(도구가 prior마다 출력하는 `PASS: <prior> -> …`) 기반으로 멈춤(hang) vs 느림을 구분하는 것도 후속 개선안이다.

## 별도 항목 기록
오늘 **두 번 재현**(회귀 배치 + 격리). 지난 회귀(40e921b)에선 격리 통과였으나 **이번엔 격리에서도 초과**(도구 ~200s > 180s). 코드 회귀 아님(마이그레이션·도구 불변) — 고정 타임아웃이 도구 구조적 런타임에 못 미친 것. 처리 완료·검증 완료.

---

# v2.0.0 — Codex 독립 검토 발견: skip 경로가 정리 책임을 새로 만든다 (처리·검증 완료)

Codex가 v1.0.0 수정(FAIL→SKIP)을 독립 검토하며 승인을 보류하고 **타당한 결함**을 지적했다. 내가 소스로 확정하고 재현했다.

## 발견 — 타임아웃 경로에서 자식·일회용 DB가 회수되지 않는다 (소스 확정 + 재현)
`check_migration_upgrade.py`는 각 prior마다 DB를 만들고(`tools/check_migration_upgrade.py:68` `name = "inv_upgrade_test_" + uuid4().hex`, 49자) **자식 안의 `finally`(L178)** 에서 `DROP DATABASE WITH (FORCE)`로 정리한다. 그런데 타임아웃을 감지해 죽이는 것은 **부모 pytest**이고, `subprocess.run(timeout=)`은 Windows에서 `TerminateProcess`를 부르므로 **자식의 finally가 돌 기회가 없다.** 즉 타임아웃이 나면 그 실행이 만든 DB가 남는다.
- **직접 재현**(일회용 PG, budget 15s, 옛 방식 그대로): 타임아웃 후 `inv_upgrade_test_<hex>` **DB 1개 잔존**, 고아 python(alembic 손자) 프로세스 잔존.
- **왜 v1.0.0과 직결되나**: v1.0.0 전에는 타임아웃이 FAIL이라 최소한 빨간불이었다. SKIP으로 바꾼 순간 **조용**해져서 누수가 생겨도 아무도 모른다. 오늘 내내 잡아온 "신호를 정직하게 만들려다 다른 신호를 지운" 형태가 여기서 재현된다. **수정 방향(도달/미도달) 자체는 옳다**(되돌리지 않음). 다만 **SKIP으로 바꾸는 순간 정리 책임이 생긴다.**

## 추가로 확정한 손자 프로세스 문제
자식은 `alembic upgrade`를 **손자 subprocess로 띄우고 기다린다**(L87). 자식만 죽이면 **손자 alembic이 고아로 남아 in-flight DB에 연결을 계속 쥔다** → 그 DB는 backend가 살아 있어 "내 누수"인지 "동시 실행이 쓰는 중"인지 구분 불가. 그래서 정리 전에 **프로세스 트리 전체**를 죽여야 소유 구분이 깨끗해진다.

## 처리 — 부모가 트리를 죽이고 소유 표시로 회수 (Docker cleanup과 동일 원칙)
`tests/test_account_integration.py`에서 `subprocess.run`을 `Popen`+`communicate(timeout)`로 바꾸고, `TimeoutExpired`에서:
1. `_terminate_process_tree(proc)` — Windows `taskkill /F /T /PID`(트리), POSIX `os.killpg(SIGKILL)`. 손자까지 죽여 **이후 살아있는 `inv_upgrade_test_` backend는 전부 남의 것**임을 보장.
2. `_reclaim_orphaned_upgrade_databases(admin_dsn)` — admin DSN으로 붙어 `inv_upgrade_test_` DB를 회수하되 가드:
   - **소유**: 접두사 `inv_upgrade_test_` + 길이 49 + hex 접미사 검증(다른 fixture의 `inv_backend_test_`는 절대 미접촉).
   - **liveness**: `pg_stat_activity`에 backend가 있으면 건드리지 않음(**동시 실행이 쓰는 DB 보호**).
   - **나이 하한**(`pg_stat_file`로 age 측정, 기본 5s·`INV_MIGRATION_RECLAIM_MIN_AGE` 조정): 동시 실행의 create→connect 순간(막 만든 DB)을 보호. `pg_stat_file` 불가 시 liveness-only로 **정리를 건너뛰지 않고** 사유에 명시.
3. **조용한 skip 방지**: 회수/잔존 개수를 skip 사유에 넣는다 — 예: `Orphaned-database cleanup: reclaimed 1, left 0`.
- **옵션 2(자식 정중 종료)를 안 쓴 이유**: Windows `TerminateProcess`는 유예를 안 주고, Python 자식에 CTRL_BREAK를 DDL 도중 보내는 것은 불안정하며, 어차피 backstop이 필요하므로 **부모 회수가 견고한 1차 수단**이다.

## 검증 — 타임아웃 유발 후 남는지, 정리 후 안 남는지 (일회용 PG, 실측)
- **누수 재현(옛 방식)**: budget 15s 강제 타임아웃 → `inv_upgrade_test_<hex>` **1개 잔존**.
- **새 동작(실제 pytest 테스트)**: budget 15s → **SKIP**, 사유 `Orphaned-database cleanup: reclaimed 1, left 0`. 이후 upgrade DB **0개**, 고아 alembic 없음(트리 kill로 python 6→4).
- **가드 4종(헬퍼 직접 시험)**: ① live backend 보유 DB → **미삭제, `1 in-use` 보고** ② 연결 종료 후 → **회수** ③ 타 접두사 `inv_backend_test_` → **미접촉** ④ `min_age=3600` 갓 만든 DB → **미삭제, `1 too-new` 보고**. **ALL GUARDS PASSED.**
- **정상 경로 무결**: 단일 prior 성공 실행 → `PASS`, exit 0, 자식 finally가 자기 DB 정리(잔존 0). 즉 정상 완료 시 `assert proc.returncode == 0` 통과, 누수 0.
- **Docker 기준선 복원**: 검증용 일회용 PG는 `docker rm -f -v`로 철거, 컨테이너 48/볼륨 79/네트워크 11 = 기준선 그대로.

## Codex가 준 추가 정보 (반영)
- 증가량은 prior 개수에만 비례하지 않고 **각 prior에서 head까지 적용**되므로 대략 **P×R**로 는다(주석을 `O(published priors x revisions-to-head)`로 정정).
- prior 목록은 자동 생성이 아니라 **고정 목록**이라(도구 L32~63) 새 revision이 추가돼도 검사 케이스가 자동으로 늘지는 않는다.
- 211s·324s 두 측정만으로는 **600s 초과 시점을 예측할 수 없다** — 언제 또 부족해질지 지금 단정하지 않는다. skip-on-timeout이 그 불확실성을 정직히 흡수하고, 근본 해법은 여전히 **도구를 incremental하게**(Codex, 도구 소유) 만드는 것이다.

## 인계
발견자 Codex(승인 보류 타당), 처리·검증 Claude. `tests/`는 Claude 소유라 직접 처리했다. 도구(`check_migration_upgrade.py`)의 incremental화는 Codex 소유로 남는다 — 그때 이 회수 로직은 타임아웃이 드물어지며 자연히 덜 쓰이지만, backstop으로 유지한다. reviewer: Codex 경계 재검토.
