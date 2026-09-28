---
doc_id: "HIST-CODEX-S11-ST-PGFREE-IMPORTER-001"
title: "S11-ST PG-free fault evidence producer와 importer"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-28T16:17:14+09:00"
source_of_truth: "Git"
task_id: "S11-ST"
reviewer: "Claude"
---

# S11-ST PG-free fault evidence producer와 importer

## 구현

- `tools/run_s11_storage_failure_pg_free.py`는 frozen universe 22개와 PG-free subset 12개의 identity SHA를 코드 상수로 고정한다.
- Linux 실행에서 LocalObjects corruption·size·write/fsync/ENOSPC/EDQUOT 8건과 retention/backup 4건을 실행한다. 제품 finding이 있어도 12개와 cleanup을 끝내고 raw JSON·JUnit에 실패를 보존한다.
- `tools/import_s11_storage_failure_evidence.py`는 report exact key, source tree와 producer/injector blob, UTC 시각, tier hash, exact identity 순서, actual surface 닫힌 enum, content digest, JUnit identity·failure 대응, secret-bearing key/value를 불신 검증한다.
- 출력은 `referenceOnly=true`, `axis=null`, `targetRef=null`인 reference evidence다. PG-free 결과를 AC-11 축 PASS로 승격하지 않는다.
- stage-1 aggregator는 `eq 0` count metric에서 `value == failureCount`를 강제해 forged zero value를 `INVALID_RUN`으로 거부한다. 그 밖 metric kind는 importer가 raw receipt에서 직접 도출한다.

## 정직한 측정 경계

- Windows 로컬에서는 Linux LocalObjects 경로를 실행하지 않았다. pure closed-contract와 importer 변이 31건, retention/backup 실제 fault 4건만 실행했다.
- hosted Backend Linux에서는 같은 시험 파일이 실제 12-case executor를 실행한다. 현재 코드의 Local raw `OSError` 5건은 `MEASURED_FAIL` reference로 기대하며, green은 finding을 숨긴다는 뜻이 아니라 expected raw finding count와 JUnit 일치를 뜻한다.
- PostgreSQL·Docker·전체 suite는 로컬에서 실행하지 않았다. hosted 10-case producer와 lane, physical evidence는 별도 카드다.

## 검증

- `python -m pytest -q tests/test_s11_storage_failure_evidence.py`: 31 passed, exit 0.
- `python -m pytest -q tests/test_aggregate_ac11_evidence.py`: 56 passed, exit 0.
- `python -m py_compile` 두 새 tool: exit 0.
- `check_docs`, `check_ontology`, `check_contract_bindings`, `check_doc_single_source --ratchet`, `git diff --check`는 모두 exit 0이다.

## provenance

- implementation commit: `06718b5967e3a6e34c34770ea8aa09ec4448e266`
- parent stack: PR #192 / head `88567849`
- frozen tier hashes: universe `5d700981…34fd9`, PG-free `f69d161e…8799`, hosted `0509d94a…4a33`.
