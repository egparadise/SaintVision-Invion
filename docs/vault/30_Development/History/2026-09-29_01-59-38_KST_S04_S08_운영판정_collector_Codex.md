---
doc_id: "HIST-CODEX-S04-S08-OPERATIONAL-COLLECTOR-001"
title: "S04-DB 재전송·S08-DB 보존 운영 판정 collector"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-29T02:14:34+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S04-DB", "S08-DB"]
tags: ["s04-db", "s08-db", "evidence", "collector", "postgresql", "operational-acceptance"]
---

# S04-DB·S08-DB 운영 판정 collector

## 독립 검토 r1 정정

- PG-free와 실 PG 시험의 basename 충돌을 제거해 hosted 전체 수집이 중단되지 않도록 실 PG 파일을 `test_s04_s08_operational_evidence_real_pg.py`로 바꿨다.
- core 제품에는 `run.cancel*` audit producer가 없으므로, collector가 직접 넣은 audit fixture를 운영 취소 이력으로 간주하지 않는다. (a)~(c)가 깨끗해도 O3는 `cancelHistorySource: absent`와 함께 `NOT_OBSERVED`이며, 실제 위반이 있으면 `MEASURED_FAIL`이다. 정본 producer 또는 C1-K 결속 전에는 O3 `MEASURED_PASS`가 불가능하다.

## 범위와 결론

Claude의 판정 기준 v1.1.1(`90a2051d`, [[S04-DB_S08-DB_운영_판정_기준]])을 실행 가능한 collector로 옮겼다. `tools/collect_s04_s08_operational_evidence.py`는 운영 core PostgreSQL을 REPEATABLE READ·READ ONLY transaction으로 읽고, database system identifier+database OID+이름 hash·migration head·transaction snapshot hash·DB 시각·collector hash·commit SHA를 한 evidence에 결속한다. DSN·host·database 이름 원문·tenant/run/attempt/approval 식별자·payload·raw 오류는 출력하지 않는다.

직접 판정하는 경계는 core C1(O3)이다. `public.run_attempts` 각 행에 대해 attempt 시작 시점 이전의 최신 `approved`를 고르고, 만료·workload digest·선행 cancel audit을 전수 대조한다. `inv.approval_requests`, `recovery_epoch`, `bound_run_version`는 읽지 않고 C1-K를 별도 `NOT_OBSERVED`로 고정한다. attempt 0건은 PASS가 아니라 `NOT_OBSERVED`; 위반 사유 합계가 전체 위반과 다르면 evidence 생성 자체를 거부한다.

O1 DB 집계는 실패·stale 행을 `MEASURED_FAIL`로 보존하지만, 100건이 깨끗해도 publisher/consumer deployment identity가 없으면 `RECORDED_ONLY`다. 그 밖 O2·O4·O6·O8′·O9·O10은 producer/결정 부재, O5·O11·O12·O13은 물리·운영 자원 부재, O7은 독립 RLS collector 미결속으로 명시한다. 따라서 현재 collector의 전체 verdict는 운영 입력이 일부 있어도 `NOT_OBSERVED`이며 S04-DB·S08-DB status 승격이나 done 주장이 없다.

## 출력과 실패 경계

- JSON+Markdown은 같은 label로 생성하고 기존 파일을 덮어쓰지 않는다.
- criteria version/head/path, clean committed tree, exact 40-hex code SHA, DB identity/time/snapshot, C1-K 제외 상태와 recomputed verdict를 검증한다.
- label path traversal을 거부한다. DB 예외는 class만 stderr에 남겨 연결 정보가 되비치지 않게 한다.
- exit 0은 모든 필수 관측이 `MEASURED_PASS`일 때만 가능하고, 현재 미결속 경계가 있으므로 정상 운영 수집은 exit 3(`NOT_OBSERVED`)이 정직한 결과다. 위반은 exit 1, 입력/연결/봉투 오류는 exit 2다.

## 검증

- PG-free `tests/core/test_s04_s08_operational_evidence.py`: **7 passed**. 0행·사유 합계·core/kernel 분리·O1 거짓 PASS·criteria/clean tree/DB binding·C1-K·overwrite·secret/redacted error·unsafe label 변이를 고정했다.
- real PG `tests/core/test_s04_s08_operational_evidence.py`: valid 1, valid 뒤 later rejected 1, approval 없음·expired·digest mismatch·선행 cancel 각 1을 실제 migration DB에 넣어 `attempt 6 / valid 2 / violation 4`와 사유별 1을 확인한다. 로컬 Python 3.10은 integration conftest의 `StrEnum`을 import하지 못해 **미실행**이며, PR의 hosted Core Python 3.12에서 실행한다.
- 공개 계약·migration 변경 0. 물리 Node 전송 재개, kernel C1-K, 운영 backup/PITR, retention/GC는 계속 `NOT_OBSERVED`/`BLOCKED_EXTERNAL`이다.

재실행: `INV_AUDIT_DSN=<운영 owner DSN> python tools/collect_s04_s08_operational_evidence.py --label <안전한-label> --out-dir <evidence-dir>` (환경값은 기록하지 않는다).
