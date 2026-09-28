---
doc_id: "HIST-CODEX-S11-ST-HOSTED-REFERENCE-001"
title: "S11-ST hosted 10-case reference lane"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-28T18:00:00+09:00"
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

- 첫 hosted run `36399940041`, head `677ce456`: failure. `inv.tenant_budgets`의 실제 composite primary key `(tenant_id, project_id)`에 단일 `project_id` conflict target을 사용한 하네스 결함이었다. 측정 결과로 사용하지 않았다.
- 수정 commit `3fe6a7a1`은 composite key upsert와 그 회귀 시험만 바꿨다. hosted run `36400113385`, job `108855700633`: success.
- raw/reference 결과: 10/10 case exact surface 일치, finding 0, classification mismatch 0, false success 0, unexpected error 0, quota overshoot 0, committed object loss 0, partial/temp/cleanup residue 0. `MEASURED_PASS`다.
- 환경: Python 3.12.14, PostgreSQL `16.15 (Debian 16.15-1.pgdg13+2)`, MinIO digest `sha256:72b4794d…c629`, archive image digest `sha256:1a6ab3f5…4b54`, loopback-only MinIO, internal archive network, published archive port 0, GitHub secret 0.
- artifact `10960190326`, name `s11-storage-hosted-3fe6a7a12f27e61ecdebe1c018a94929b8558f63`, digest `sha256:6202aafd06908ff09be5df75655bfb0a05e6a54c67b620c767fe145ce9518e9e`, 만료 `2026-10-28T08:54:49Z`다.

## 판정

- 결과는 `referenceOnly=true`, `axis=null`, `targetRef=null`이다. AC-11 필수 축이나 long-soak을 통과시키지 않고 S11-ST는 `planned`를 유지한다.
- 실제 5노드·별도 장애 영역·운영 archive·장시간 soak은 실행하지 않았으며 계속 `BLOCKED_EXTERNAL`/`NOT_REGISTERED`다.
- 로컬 PostgreSQL·Docker·전체 suite는 실행하지 않았다. 로컬에서는 `tests/test_s11_storage_failure_hosted_evidence.py` 28 passed, py_compile, YAML parse, `git diff --check`만 수행했다.
- 이 문서 commit은 측정 코드 뒤의 docs-only delta다. 최종 PR head의 동일 lane 재실행 run과 artifact 식별자는 PR #204 코멘트에 기록하고, 그 이후에는 코드를 바꾸지 않는다.
