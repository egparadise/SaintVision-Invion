---
doc_id: "TEST-SKIP-ASSERTION-BOUNDARY-CODEX-001"
title: "pytest skip BaseException assertion boundary 보강"
version: "1.0.0"
status: "review"
author: "Codex"
base_commit: "8c15e1a"
source_of_truth: "Git"
updated: "2026-09-19T19:12:00+09:00"
tags: ["pytest", "skip", "BaseException", "test-boundary"]
---

# pytest skip assertion 경계 보강

## 발견과 수정

`pytest.skip.Exception`은 `Exception` 하위가 아닌 `BaseException` 하위다. 따라서 예상 실패를 `pytest.raises(ExpectedFailure)`로만 감싸면 대상이 skip을 내는 순간 그 예외가 기대형을 벗어나도 test report에서 `SKIPPED`가 될 수 있다. Claude의 `ExceptionGroup` 정리 시험도 그룹 안에 skip이 섞이는 경우를 별도로 지켜야 했다.

재사용 context manager `tests/raises_no_skip.py`의 `raises_without_skip`은 기대 예외를 확인하고, 직접 또는 `BaseExceptionGroup` 내부에서 발견한 pytest skip을 즉시 실패로 바꾼다. `tests/conftest.py`에는 환경 의존이 없는 pure/monkeypatch 전용 네 모듈에 한해 report-level no-skip 불변식을 추가했다: `test_recovery_drill_prerequisites.py`, `test_db_login_teardown.py`, `test_vf_docker.py`, `test_credential_conformance.py`. `test_check_kernel_docker_hygiene.py`에는 실제 Docker lane skip이 있으므로 파일 전체 가드는 걸지 않고 두 실패 기대 구간만 wrapper를 쓴다. 두 `tests/integration` 파일에도 전체 불변식은 적용하지 않는다. 해당 파일들은 PostgreSQL·Linux 선행조건 skip을 유지하고 실패 기대 단언에만 wrapper를 쓴다.

## 일곱 파일 적용 범위

| 파일 | 변경 |
|---|---|
| `tests/test_recovery_drill_prerequisites.py` | 기존 pytest.raises 19곳 중 의도된 skip 확인 7곳은 보존, 실패 기대 12곳을 `raises_without_skip`으로 전환. helper 자체의 직접/중첩 skip 검증 2개를 추가했으며, 테스트 자신도 모듈 불변식으로 skip이 실패가 된다. |
| `tests/integration/test_credential_backend.py` | CredentialDenied/DB 제약 위반을 기대하는 6곳을 감쌌다. Linux 파일 backend 및 PostgreSQL 전제 skip은 유지. |
| `tests/test_db_login_teardown.py` | dispose, DROP ROLE, ExceptionGroup 실패 기대 3곳을 감쌌다. 모듈 전체 skip 금지. |
| `tests/test_check_kernel_docker_hygiene.py` | `ckd.checked`의 RuntimeError 기대 2곳을 감쌌다. 실제 `docker_host` 시험의 환경 skip은 유지. |
| `tests/test_vf_docker.py` | 본문 실패 보존과 KeyboardInterrupt 기대 2곳을 감쌌다. 모듈 전체 skip 금지. |
| `tests/test_credential_conformance.py` | deliberate-fault와 secret-chain 실패 기대 2곳을 감쌌다. 순수 model 테스트의 전체 skip 금지. |
| `tests/integration/test_recovery_drill.py` | ledger rollback의 RuntimeError 기대 1곳을 감쌌다. 플랫폼/PostgreSQL 전제 skip은 유지. |

저장소 전체 탐색에서 명시적으로 `pytest.skip`을 호출하는 실제 테스트 helpers는 이 범위의 시험 계층에 있었다. `tools/` 아래 pytest 문자열은 주석/로그 등이며 실제 `pytest.skip()` 호출이 아니었다. 이 변경은 제품 코드를 수정하지 않는다.

## 실행과 되돌림 대조

- 인터프리터: `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe`.
- 순수/monkeypatch 파일: `.venv\Scripts\python.exe -m pytest -q -rs tests/test_recovery_drill_prerequisites.py tests/test_db_login_teardown.py tests/test_vf_docker.py tests/test_credential_conformance.py tests/test_check_kernel_docker_hygiene.py` — **83 passed / 0 failed / 2 deselected**, 0 skip, exit 0. Deselected는 기본 `not docker_host` marker 경계다.
- 통합 파일: `.venv\Scripts\python.exe -m pytest -q -rs tests/integration/test_credential_backend.py tests/integration/test_recovery_drill.py` — **1 passed / 66 reasoned skips / 0 failed / 0 errors**, exit 0. 이 Windows 세션에서 Linux credential backend와 `INV_TEST_ADMIN_DSN`이 없어 통합 본문이 건너뛰어졌다. 이 결과는 통합 동작의 실행 증거가 아니다.
- 회귀 suite는 건드리지 않고 각 pure module에 임시 direct `pytest.skip()` test를 추가했다. 네 모듈 모두 `1 failed / 0 skipped`가 됐고 실패 메시지에 `Unexpected skip in ...`가 포함됐다. 임시 test를 제거했다.
- 대상 코드가 skip을 던지는 음성 대조: recovery archiver 분류기의 unclassified AssertionError를 `pytest.skip()`으로 바꿨고 원 test `test_running_archiver_without_ready_or_error_marker_is_unclassified_failure`가 **failed**로 기록됐다. `db_login` fake dispose, `ckd.checked`, `vf_docker` 본문 실패 경로, credential conformance deliberate-fault를 각각 임시 skip 주입했을 때 해당 test들도 모두 **failed, not skipped**였다. 모든 임시 변경은 원복했다.
- 두 integration 파일은 DB/Linux 선행조건이 충족되지 않아 원 본문 주입을 돌리지 않았다. 각 파일에 fixture-free 임시 assertion probe를 넣어 wrapper를 사용하면 pass, plain `pytest.raises`로 되돌리면 정당한 module-wide skip 정책 아래 `1 skipped`가 되는 것을 실행해 대조했고 임시 probe를 제거했다.
- Final verification at 2026-09-19 19:14 KST: the pure/monkeypatch command above remained **83 passed / 0 skip / 2 deselected**; the integration command remained **1 passed / 66 reasoned skips / 0 failed / 0 errors** because this host is Windows and no `INV_TEST_ADMIN_DSN` was supplied. `.venv\\Scripts\\python.exe tools/check_docs.py` and `tools/check_ontology.py` both exit 0; `git diff --check` exit 0. Initial `tools/sync_obsidian.py --check` had emitted an uncaught conflict traceback; after the remote diagnostic update, rerun exited 1 with a grouped report of 675 unmanaged destination collisions (655 no-baseline, 12 destination-edited, 8 both-diverged), no writes, and no `--apply` to avoid overwriting external edits.
- One initial pytest invocation mixed files from `tests/` and `tests/integration/` in one command and produced 18 `postgres` fixture-not-found setup errors due conftest selection/shadowing. This was a test invocation error, not a product result. Running the integration files together under their own nested conftest immediately afterward resolved fixture collection; the artifact is the `1 passed / 66 reasoned skips` invocation above. The initial 18-error command is excluded from product/test totals.

## 검토 한계

이 실행은 Windows에서 skip-report 경계를 테스트했고 Linux backend 및 PostgreSQL 통합 assertion은 실행하지 않았다. DB를 띄우지 않은 상태에서 integration fixture skip은 예상된 선행조건 결과다. Docker live test, CI, 운영 인수는 범위 밖이다.
