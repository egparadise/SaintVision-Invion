---
doc_id: "HIST-CODEX-S11-ST-HOSTED-REFERENCE-001"
title: "S11-ST hosted 10-case reference lane"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T18:47:20+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_id: "S11-ST"
acceptance_id: "AC-11"
---

# S11-ST hosted 10-case reference lane

## 구현과 경계

- PR #204는 #193 final head `18392300` 위에 #173 S3 observation과 #187 G-02 archive executor를 merge commit으로 결속했다. 공개 HTTP 계약·migration·task registry 상태는 바꾸지 않았다.
- `.github/workflows/s11-storage-failure-hosted.yml`은 `run-s11-storage` label 또는 `workflow_dispatch`에서만 실행되고, exact PR head와 full history를 checkout한다. job-level concurrency는 `cancel-in-progress: false`이며 기본 CI와 skip map을 바꾸지 않는다.
- MinIO는 digest 고정 이미지와 `127.0.0.1` publish만 사용한다. archive probe는 digest 고정 PostgreSQL 컨테이너를 비공개 internal network에서 실행하고 port를 publish하지 않는다. GitHub secret은 0개이며 owner label이 붙은 disposable container·network만 정리한다.
- `tools/run_s11_storage_failure_hosted.py`는 frozen hosted subset 10개와 identity SHA `0509d94a6648106868ef1ec602af2bed5bbd02b17cec3a4c5ffbf6178ef24a33`을 실행한다. archive `/bin/false`·`/bin/true`, PostgreSQL quota, S3 507·body/size/metadata/partial·ambiguous put의 실제 제품 표면을 수집한다.
- `tools/import_s11_storage_failure_hosted_evidence.py`는 exact key·case order·source tree/blob·clean checkout·JUnit digest·환경·redaction·metric 관측 분모를 fail-closed로 검증한다. 제품 finding은 지우지 않고 `MEASURED_FAIL`로 보존하지만 malformed·failed/cancelled run은 import 오류다.

## 실행 결과

- 첫 hosted run `36399940041`, head `677ce456`: failure. `inv.storage_budgets`의 실제 composite primary key `(tenant_id, project_id)`에 단일 `project_id` conflict target을 사용한 하네스 결함이었다. 측정 결과로 사용하지 않았다.
- run `36400113385`와 `36400962763`은 workflow success였지만, Claude 검토에서 BAK verifier·archive byte, S3/CAP loss·residue·quota 수치가 실행 결과가 아닌 상수/동어반복임이 확인됐다. 따라서 당시 `finding 0`·`MEASURED_PASS` 주장은 판정 근거에서 철회한다.
- 관측형 producer/importer head `35ba1187`의 run `36405288098`은 실제 `pg_stat_archiver`, internal network inspect, provider HEAD, DB row·budget, PUT count와 동시 barrier를 기록했다. 그 실행에서 `OBJ-02`가 DB CHECK에 먼저 막힌 하네스 결함도 finding으로 보존했고 결과를 최종 판정에 쓰지 않았다.
- 교정 head `51fada85`의 run `36405534113`, job `108873230357`은 10 case를 모두 실행했다. exact 오류 표면은 **10/10 일치**, classification mismatch 0, false success 0, unexpected error 0, quota overshoot 0, committed object loss 0이다. 다만 `OBJ-04` ambiguous PUT과 success-partial에서 cleanup 전 provider partial object가 각각 1개(합 2) 실제 관측되어 verdict는 **`MEASURED_FAIL`**이다. cleanup 뒤 residue는 0이다. S3 prefix listing 없이 확인할 수 없는 temp-residue 5개는 0으로 채우지 않고 `NOT_OBSERVED`로 보존했다.
- 환경: Python 3.12.14, PostgreSQL `16.15 (Debian 16.15-1.pgdg13+2)`, MinIO digest `sha256:72b4794d…c629`, archive image digest `sha256:1a6ab3f5…4b54`, loopback-only MinIO, internal archive network, published archive port 0, GitHub secret 0.
- 정본 artifact `10962202766`, name `s11-storage-hosted-51fada856183a7b50c29b11a0647b7cecfee637d`, digest `sha256:9ab687af12b0ec5ad028e19fc54a879e65f2cfaf15822dfde73107a10a37d6fd`, 만료 `2026-10-28T09:46:44Z`다. 새 offline importer로 zip SHA-256, GitHub run/artifact JSON, source run/head, artifact name/expiry, raw JSON·JUnit·저장 reference 재계산을 교차검증했고 exit 0이었다. 이 importer는 GitHub API를 인증하지 않으므로 canonical repository에서 `gh api`로 받은 입력끼리의 불일치만 검출한다.
- 같은 head의 기본 Backend 3.12 run `36400962757`은 전용 환경변수 없이 hosted integration case를 수집해 `INV_S11_STORAGE_REPORT`를 읽는 opt-in 경계 결함으로 failure였다. 전용 lane 밖에서는 `run only through S11 Storage Failure Hosted Reference opt-in lane`으로 skip하고, Backend/Core exact skip distribution에 각 1건을 등록했다. 누락 시 실패하는 PG-free 회귀 시험을 추가했다.

## 판정

- 결과는 `referenceOnly=true`, `axis=null`, `targetRef=null`이다. AC-11 필수 축이나 long-soak을 통과시키지 않고 S11-ST는 `planned`를 유지한다.
- 실제 5노드·별도 장애 영역·운영 archive·장시간 soak은 실행하지 않았으며 계속 `BLOCKED_EXTERNAL`/`NOT_REGISTERED`다.
- 로컬 PostgreSQL·Docker·전체 suite는 실행하지 않았다. 로컬에서는 hosted evidence 단일 파일 **38 passed**, 관련 PG-free 묶음 **80 passed / 2 opt-in skipped**, PITR 단일 파일 **5 passed**, YAML parse, `check_docs`와 `git diff --check`를 확인했다. 실제 MinIO·PostgreSQL 행위는 위 hosted run만 판정 근거로 썼다.
- opt-in 경계 hotfix를 포함한 최종 PR head의 동일 lane·Backend 재실행 식별자는 PR #204 코멘트에 기록한다.
