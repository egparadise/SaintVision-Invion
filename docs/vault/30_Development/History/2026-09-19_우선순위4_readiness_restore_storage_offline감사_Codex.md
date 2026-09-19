---
doc_id: "PRIORITY4-OFFLINE-BOUNDARY-AUDIT-20260919-CODEX"
title: "우선순위 4 readiness·restore·storage offline 경계 감사"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-19T02:20:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
---

# 우선순위 4 readiness·restore·storage offline 경계 감사

## 범위

`tools/operational_readiness.py`, `storage_check.py`, `rehearse_independent_restore.py`, `rehearse_lan_upgrade.py`와 보고서 생성·소비 경계를 확인했다. 실제 복원·운영 DB·LAN 실행은 하지 않았다. 기존 대조 실행과 이번 소스 판정을 분리한다.

## 판정

### PR4-01 — stale LAN report 재사용 가능성 / P2 후보

`rehearse_lan_upgrade.py`는 rehearsal 성공 뒤 `args.output.write_text(...)`로 보고서를 기록하지만, 실행 시작 시 기존 output을 거부하지 않는다. 반대로 rehearsal 본문이나 cleanup에서 예외가 나면 main은 exit 2를 반환하고 새 보고서를 쓰지 않는다. 따라서 기존 성공 JSON이 같은 경로에 남아 있으면 후속 소비자가 현재 실행의 결과로 오인할 수 있다.

- **소스 확인:** 기존 output 보호는 없고, 보고서에는 `startedAt`·`completedAt`·scope가 있으나 소비자가 이를 현재 run과 대조하는 공통 guard는 저장소에서 확인하지 못했다.
- **실패 주입 확인:** 기존 성공 output을 둔 상태에서 rehearsal 실패를 주입하면 exit 2이고 이전 파일은 보존된다는 기존 감사 증거가 있다. 이는 stale 파일이 남는 사실을 실증하지만, 실제 소비자가 오인하는 장면까지 재현한 것은 아니다.
- **수정 계약:** 고유 run output을 강제하거나 기존 파일이 있으면 시작 전에 거부한다. 실패 시 별도 실패 receipt를 새 경로에 원자적으로 기록하고, 소비자는 run nonce/code SHA/startedAt를 확인하지 않은 JSON을 성공 증거로 읽지 않는다.

### PR4-02 — independent restore cleanup 오류가 보고서 생성을 가릴 수 있음 / P2 후보

`rehearse_independent_restore.py`는 `RehearsalFailure`를 잡아 sanitized report를 쓰는 경로가 있지만, `finally`의 `docker inspect`·`docker rm -f` 예외가 그 예외를 대체할 수 있다. 성공 본문 뒤 cleanup이 실패해도 main의 일반 예외 경로는 report를 쓰지 않고 exit 2만 출력한다. cleanup 상태가 본문 결과와 별도 보고서로 보존되지 않는다.

- **소스 확인:** cleanup 결과 필드 `disposableClusterRemoved`는 성공적으로 제거된 경우에만 기록된다. query 실패·remove 실패·ownership mismatch의 구분과 보존 receipt가 없다.
- **실패 주입 확인:** 이번 감사에서는 실제 Docker/cleanup 장애 주입을 하지 않았다. 기존 독립 restore 시험은 기존 output 거부와 backup 경계를 확인하지만 cleanup 동시 실패를 검증하지 않는다. 따라서 런타임 결과가 아니라 소스 후보로 유지한다.
- **수정 계약:** 본문 판정과 cleanup 판정을 분리하고, query-error·remove-error·ownership-mismatch·confirmed-removed를 모두 sanitized JSON에 기록한다. cleanup 예외가 본문 실패/성공 보고서를 대체하지 않아야 하며, output은 새 경로에 원자적으로 보존한다.

### PR4-03 — offline 선행조건 표면화 / finding 없음

`storage_check.py`는 DSN 부재·잘못된 인자를 exit 2로 거부하고, 예외 시 “no operational record was written”을 출력한다. 빈 sample은 `sampleHealthy=false`와 exit 1로 흐르며 운영 인수·Node binding을 true로 만들지 않는다.

`operational_readiness.py`는 acceptance evidence가 없거나 불완전하면 exit 1, DB에 접근할 수 없으면 `operational_readiness_unavailable`와 exit 2를 사용한다. 두 도구 모두 offline/미완료를 성공으로 세는 소스 경로는 확인하지 못했다. 다만 이번 실행은 DSN 없이 readiness/storage 관련 5 passed / 30 skipped였고, 실제 PostgreSQL 경계는 실행하지 않았다.

## 검증 범위

- 소스 추적: 위 네 도구와 관련 test/report 소비 경로.
- 기존 실행 증거: stale output 실패 주입은 exit 2와 이전 파일 보존까지 확인됐으나 소비자 오인 미재현.
- 이번 실행: `python -m pytest -q tests/test_operational_readiness.py tests/test_storage_check_integrity.py` → **5 passed / 30 skipped**, DSN 부재로 DB 시험 미실행.
- 정정: 앞선 실행은 시스템 `C:\Python314\python.exe`를 사용해 `cryptography`가 없어 collection에 실패했다. 프로젝트 인터프리터 `.venv/Scripts/python.exe`로 다시 실행한 결과 두 파일은 **29 passed**(기존 24개 + 새 회귀 5개)다. 앞선 실행 불가는 제품 상태가 아니라 잘못된 인터프리터 기록이었다.
- 구현 원복 대조에서 기존 테스트만은 24 passed였고, 새 회귀시험을 원복 코드와 함께 수집하면 새 helper(`_cleanup_owned`, `failure_report_path`)가 없어 collection 단계에서 실패했다. 따라서 새 경계시험이 수정된 구현에 결속돼 있음을 확인했다.
- 실제 Docker/PostgreSQL restore, LAN report consumer, cleanup fault injection, 운영 인수는 미확인이다.

## 다음 담당

- Gemini/Claude: PR4-01 report provenance와 PR4-02 cleanup receipt 구현 검토.
- Codex: 수정본의 stale/cleanup 음성 대조와 evidence 보존 재검토.
- 운영 복원·LAN 인수는 승인·격리 조건이 충족될 때 별도 수행한다.

## 구현 및 재검증

`rehearse_lan_upgrade.py`는 기존 성공 output과 기존 failure receipt를 시작 시 거부하고, 실패 시 `<stem>.failure<suffix>`를 새 파일로 생성한다. `rehearse_independent_restore.py`는 cleanup을 본문 결과와 분리해 `confirmed-removed`, `confirmed-absent`, `query-error`, `remove-error`, `ownership-mismatch`를 기록하며 cleanup 오류가 본문 report를 대체하지 않는다. 새 회귀시험은 기존 output 보존, failure receipt, remove/query/ownership 대조, 본문 실패 보고서 보존을 포함한다.

`.venv/Scripts/python.exe -m pytest -q tests/test_independent_restore.py tests/core/test_lan_restore_upgrade.py` → **30 passed**. 수정 전 원복 코드와 새 시험을 대조하면 새 helper가 없어 collection 단계에서 실패했다. 실제 Docker/PostgreSQL 복원은 실행하지 않았다.

## 감사 정정 — 인터프리터 및 되돌림 대조 강도

초기 항목의 `python -m pytest ... tests/test_operational_readiness.py tests/test_storage_check_integrity.py` 기록은 실행 파일을 고정하지 않아 당시 interpreter provenance를 확정할 수 없다. 2026-09-19 감사자가 `.venv\Scripts\python.exe -m pytest -q tests/test_operational_readiness.py tests/test_storage_check_integrity.py`로 다시 돌려 **5 passed, 30 skipped, exit 0**을 확인했다. 모든 skip은 `INV_TEST_ADMIN_DSN` 부재로 PostgreSQL 본문이 실행되지 않은 사유다. 현재 수정 후 두 restore/LAN 파일은 `.venv\Scripts\python.exe -m pytest -q tests/test_independent_restore.py tests/core/test_lan_restore_upgrade.py`로 **30 passed, exit 0**을 재확인했다.

앞서 기록한 수정 전 대조는 새 helper import가 없어 collection 단계에서 실패한 것이다. 이는 “원복 상태에서 시험이 실행되어 제품 불변식을 반증했다”는 assertion-level 되돌림 대조가 아니다. 근거 강도는 collection-level 결속 확인이며, 본문 동작을 원복해 새 assertion이 실패하는 대조는 미수행으로 유지한다. 실제 Docker/PostgreSQL 복원·cleanup fault injection·운영 인수도 미검증이다.
