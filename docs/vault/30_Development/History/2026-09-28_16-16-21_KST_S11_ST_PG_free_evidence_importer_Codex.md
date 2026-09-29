---
doc_id: "HIST-CODEX-S11-ST-PGFREE-IMPORTER-001"
title: "S11-ST PG-free fault evidence producer와 importer"
version: "1.2.2"
status: "review"
author: "Codex"
updated: "2026-09-28T21:56:36+09:00"
source_of_truth: "Git"
task_id: "S11-ST"
reviewer: "Claude"
---

# S11-ST PG-free fault evidence producer와 importer

## 구현

- `tools/run_s11_storage_failure_pg_free.py`는 frozen universe 22개와 PG-free subset 12개의 identity SHA를 코드 상수로 고정한다.
- Linux 실행에서 LocalObjects corruption·size·write/fsync/ENOSPC/EDQUOT 8건, retention interruption 2건, backup artifact 2건을 실행한다. backup은 별도 `verify_backup_artifact.py`가 tar 구조와 `PG_VERSION`·`backup_label`·`global/pg_control`을 검사하며 verifier blob도 source head에 결속한다.
- 후속 merge `e1dd5075`로 #198의 receipt/journal retention 제품 경로를 결속했다. BAK-02는 수작업 plan이나 raw `OSError` 재라벨이 아니라 제품 `retention.plan`과 `RetentionApplyPartial`을 호출하고, before/after 보존 집합·journal receipt를 대조한다. registered Local object boundary 보정은 `f9274465`에 있다.
- `OBJ-04/local/write-enospc`는 `os.open`이 아니라 실제 `stream.write`에서 ENOSPC를 주입한다. write/file-fsync 실패 뒤 불완전 canonical·temp·cleanup residue와 quota overshoot를 관측하며 양수는 표면 일치와 무관하게 `MEASURED_FAIL`이다. directory-fsync 실패가 rename 뒤 남긴 exact canonical byte는 허용 상태이며 raw `OSError` 분류 불일치는 별도 finding이다.
- `BAK-03/local/backup-exit0-truncated`는 문자열 상수가 아니라 필수 PostgreSQL member를 갖춘 유효 tar의 `global/pg_control` data 구간을 절단한다. verifier는 member 누락, 비숫자 `PG_VERSION`, label 줄 누락, 8191-byte control, 상위 경로 member, 중복 member를 모두 fail-closed로 거부한다.
- `tools/import_s11_storage_failure_evidence.py`는 report exact key, source tree와 producer/injector/verifier blob, UTC 시각, tier hash, exact identity 순서, actual surface 형식, content digest, JUnit identity·failure 대응, secret-bearing key/value를 불신 검증한다. well-formed 공개 code와 양의 errno가 기대 표 밖이면 import 오류로 숨기지 않고 classification finding으로 보존한다.
- residue·quota·committed-loss 수치는 실제 관측한 case만 합산하고 관측 case 수를 같이 낸다. 관측하지 않은 metric은 `0`이 아니라 `null`이다.
- raw/reference evidence shape 변경을 `schemaVersion=1.1.0`으로 올려 과거 1.0.0과 혼동하지 않는다.
- 출력은 `referenceOnly=true`, `axis=null`, `targetRef=null`인 reference evidence다. PG-free 결과를 AC-11 축 PASS로 승격하지 않는다.
- stage-1 aggregator는 `eq 0` count metric에서 `value == failureCount`를 강제해 forged zero value를 `INVALID_RUN`으로 거부한다. 그 밖 metric kind는 importer가 raw receipt에서 직접 도출한다.

## 정직한 측정 경계

- Windows 로컬에서는 Linux LocalObjects 경로를 실행하지 않았다. pure closed-contract, importer 변이, retention interruption 2건, backup verifier invalid/valid 구조 시험만 실행했다.
- hosted Backend Linux에서는 같은 시험 파일이 실제 12-case executor를 실행한다. 최종 head의 run `36418968755`는 actual LocalObjects 8건, osError finding 0건, reference `MEASURED_PASS`를 기록했고 Backend 3.12/3.14가 모두 green이다. 이는 PG-free reference의 통과이며 물리 storage나 AC-11 축 PASS가 아니다.
- PostgreSQL·Docker·전체 suite는 로컬에서 실행하지 않았다. hosted 10-case producer와 lane, physical evidence는 별도 카드다.

## 검증

- `python -m pytest -q tests/test_s11_storage_failure_evidence.py`: 53 passed, exit 0.
- `python -m pytest -q tests/test_aggregate_ac11_evidence.py`: 56 passed, exit 0.
- `python -m py_compile` producer·importer·backup verifier: exit 0.
- `check_docs`, `check_ontology`, `check_contract_bindings`, `check_doc_single_source --ratchet`, `git diff --check`는 모두 exit 0이다.

## provenance

- initial implementation commit: `06718b5967e3a6e34c34770ea8aa09ec4448e266`; Claude r1 보강 commit은 `655261ff7634b4ce6cc7c5bc46dfa613fed0390d`, r2 C1~C2 보강 commit은 `e5a490cea6bd98aff20fbdb8f88c1e7af76ba7db`다.
- parent stack: PR #192 / head `88567849`
- frozen tier hashes: universe `5d700981…34fd9`, PG-free `f69d161e…8799`, hosted `0509d94a…4a33`.
