---
doc_id: "RECOVERY-ARCHIVER-BOUNDARY-CODEX-001"
title: "Recovery archiver readiness failure 분류와 40e921b JUnit 집계 정정"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-19T18:56:00+09:00"
base_commit: "100caa4b1350fb3cff09cf3c8de2c28d57e80238"
implementation_commit: "95b371a"
source_of_truth: "Git"
tags: ["recovery", "docker", "junit", "evidence-boundary"]
---

# Recovery archiver readiness 경계

## 1. Claude 40e921b 전체 회귀 산출물 대조

Claude 작성 실행과 Codex의 사후 재파싱을 구분한다. Claude의 원본 자료는 `Evidence/regression-40e921b-20260919-1755/`에 있다. 각 배치 JUnit의 `tests`, `failures`, `errors`, `skipped`와 timestamp를 읽었고 `passed = tests - failures - errors - skipped`로 산출했다.

| 순서 | 배치 | tests | passed | failures | errors | skipped | JUnit timestamp (KST) |
|---|---|---:|---:|---:|---:|---:|---|
| 1 | core | 631 | 628 | 0 | 0 | 3 | 17:59:10 |
| 2 | rootA | 504 | 489 | 1 | 0 | 14 | 18:01:57 |
| 3 | rootB | 667 | 653 | 0 | 0 | 14 | 18:11:29 |
| 4 | intA | 428 | 255 | 0 | 0 | 173 | 18:19:50 |
| 5 | intB | 398 | 167 | 0 | 0 | 231 | 18:24:06 |
| **5배치 산술 합** | **단일 실행 아님** | **2628** | **2192** | **1** | **0** | **435** | **17:59–18:24** |

### 실행 조건과 범위

- checkout SHA: `40e921b`; 이 SHA는 `aeec9b3`를 포함한다.
- Python: `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe`.
- 실행 형식: `<인터프리터> -m pytest <해당 배치의 manifest 파일 집합> -p no:cacheprovider -q --junitxml=<해당 JUnit 경로>`. 개별 집합은 `manifest-1-core.txt`부터 `manifest-5-intB.txt`까지가 고정한다.
- 실제 PostgreSQL: 일회용 PostgreSQL 16과 마스킹된 `INV_TEST_ADMIN_DSN`; `CX01_CONTAINER`는 설정하지 않은 실행이다.
- 시간은 JUnit `testsuite.timestamp` 기준 KST다. 디렉터리 이름의 `1755`는 실행 timestamp가 아니다.
- 결과는 다섯 개 분할 실행의 산술 합이다. 단일 pytest 세션의 결과라고 인용하지 않는다.

### Manifest 완결성 대조

- `manifest-0-full-collect-only.txt`: 177개 시험 보유 파일.
- 5개 실행 manifest: 합계 187개 경로, 합집합 187개, 배치 간 중복 0개.
- full collect 경로 중 배치 합집합에 빠진 파일: 0개.
- 배치 manifest에만 추가로 잡힌 10개는 pytest support 모듈이며 시험 보유 파일이 아니다: `tests/conftest.py`, `tests/credential_conformance.py`, `tests/db_login.py`, `tests/db_provision.py`, `tests/integration/conftest.py`, `tests/jwt_support.py`, `tests/model_support.py`, `tests/pki_support.py`, `tests/recovery_drill_prerequisites.py`, `tests/vf_docker.py`.
- 따라서 합집합 차이는 시험 누락이나 중복 계수가 아니다.

### 실패와 이전 집계의 정정

- 유일한 실패는 `tests.test_account_integration::test_published_migration_heads_upgrade_without_rewriting`. JUnit은 `subprocess.TimeoutExpired`(180초)를 기록한다. Claude는 격리 재실행이 exit 0이었다고 보고했으나, 전체 실행 산출물 자체가 증명하는 것은 180초 timeout 한 건이다. 제품 결함으로 단정하지 않고 부하 민감한 고정 timeout 관찰로 남긴다.
- 18개의 recovery fixture setup error는 이 실행에서 errors 0으로 바뀌었다. `aeec9b3`가 `CX01_CONTAINER` 미설정/소유 확인 불가를 오류가 아니라 이유가 명시된 skip으로 분리한 결과다. 이 전체 회귀에서 실제 상태는 18 skips다.
- `432 passed / 386 skipped / 0 failed`는 정확한 배치 manifest가 없던 앞선 Codex 선택 배치 집계라서 전체 결과로 철회한다. 그때 보존된 원본 XML의 실제 수치는 825 tests, 421 passed, 386 skipped, 18 errors였다. 새로 수신된 40e921b 자료는 JUnit 5개와 manifest 6개를 갖춰 범위를 대조했으므로 별도 근거다. 두 실행은 합산하지 않는다.
- Claude의 이전 `2180 / 2 / 18 / 417`은 JUnit 없는 터미널 요약이며 SHA도 `53f81ba`다. 이 40e921b JUnit 결과로 최신 전체 회귀 근거를 대체하며, 두 수치 간 차이를 같은 실행의 delta로 해석하지 않는다.

## 2. Archiver readiness 실패 분류 변경과 실측

기존 `Owned archiver not ready` 단언은 접속 재시도 timeout 뒤 컨테이너의 실제 상태를 구분하지 않았다. 새 `_classify_archiver_connection_failure`는 소유 라벨을 확인한 뒤 Docker inspect의 status/running/restarting/restartCount/exitCode/port binding과 `docker logs --tail 200`을 읽는다.

- 컨테이너가 종료됐거나 restarting 상태/재시작 이력이 있으면 실패한다. exit code와 FATAL/PANIC/ERROR 로그 진단을 메시지에 포함하며 credential-like 값은 가린다.
- inspect/logs 실행 또는 파싱 실패, ownership mismatch, ready/error 어느 쪽도 판별할 수 없는 상태는 실패한다. 미확실함을 환경 skip으로 세지 않는다.
- 현재 시험이 만든 internal 네트워크에서 컨테이너가 안정적으로 running이고 PostgreSQL ready 로그가 있으며 HostConfig에 게시 포트가 없으면, 호스트 pytest에서 컨테이너 이름으로 접근할 전제가 없으므로 사유를 포함한 skip이다.
- ready 로그가 있지만 host port binding이 있으면 skip하지 않고 실패한다.

### 실제 양성 경로: 실행 중 + 준비 완료 + 호스트 경로 없음

- KST 2026-09-19 18:45:41 시작, JUnit duration 69.315초, exit 0.
- 명령: `.venv\Scripts\python.exe -m pytest -q -rs tests/integration/test_recovery_drill.py::test_live_archiver_configuration_cannot_certify_operational_rpo --junitxml=.work/archiver-classification-verified-270d9156e645.xml`.
- 환경: `INV_TEST_ADMIN_DSN`은 고유 소유 라벨이 붙은 일회용 PG16을 가리켰고 `CX01_CONTAINER=codex-archiver-final-270d9156e645`를 명시했다. DB 컨테이너는 loopback ephemeral host port `55126`, 메모리 512 MiB 상한, 데이터 tmpfs로 생성했다. secret 값은 보존하지 않았다.
- `/bin/true`와 `/bin/false` 각 parameter의 접속 시도는 30초 내 성공하지 않았다. 그 뒤 두 경우 모두 helper의 실제 Docker inspect와 logs 결과는 `status=running`, `Running=True`, `Restarting=False`, `RestartCount=0`, `ExitCode=0`, PostgreSQL-ready log marker present, `HostConfig.PortBindings` 비어 있음이었다.
- 따라서 두 parameter 모두 JUnit `<skipped>`로 기록됐다. 이 호스트의 Docker internal-network/host-Python 경계 문제라는 판정은 실제 관찰과 일치한다. PostgreSQL 기동 실패나 제품 RPO 판정으로 세지 않는다.
- JUnit 보존본: [`archiver-readiness-classification-20260919-184541.xml`](../Evidence/archiver-readiness-classification-20260919-184541.xml).

### 실제 음성 경로: PostgreSQL 시작 오류

- 같은 Docker host에서 PostgreSQL 16 컨테이너에 존재하지 않는 startup parameter를 주입했다. 실제 inspect는 `Status=exited`, `Running=False`, `Restarting=False`, `RestartCount=0`, `ExitCode=1`이었다.
- Docker logs의 PostgreSQL `FATAL` 진단을 확인했다. 분류기는 `pytest.skip`이 아니라 실패를 내고 종료 코드 및 진단을 기록했다.
- 소유 라벨을 재확인한 뒤 컨테이너 제거 exit 0, exact-name inspect로 부재를 확인했다. 이 negative-control 기록은 [`archiver-readiness-dead-container-negative-control-20260919.txt`](../Evidence/archiver-readiness-dead-container-negative-control-20260919.txt).

### 분류기 회귀 검증

`.venv\Scripts\python.exe -m pytest -q tests/test_recovery_drill_prerequisites.py` — 19 passed, exit 0. 테스트는 running+ready+no host port의 reasoned skip, exited/FATAL의 failure, ready 뒤 오류 로그가 있어도 실패, 재시작 횟수, published host port, inspect/logs nonzero와 spawn timeout을 각각 다룬다.

컨테이너 자원 cleanup 뒤 `docker info`는 48 containers(3 running/45 stopped), volume 79, network 11이었다. 시험의 `sv-rpo-*` containers/networks는 실행 전후 모두 0. 사용 소유 일회용 PG와 실제 dead-container control은 각각 `docker rm -f -v` 및 사후 inspect로 제거 확인했다. `saintvision-lan-db-bff1a31d`, `saintview-orthanc`, `saintview-orthanc-h1`, `saintview-orthanc-h2`는 삭제·재시작하지 않았다. `saintview-orthanc`는 사후에도 기존 `Exited (255) 8 days ago` 상태였다.

이 자료는 Windows 호스트의 Docker 20.10.22에서 수행한 테스트 fixture 경계 확인이다. Linux 실행 환경, 실제 운영 PITR, 서비스 RPO 보증, production acceptance를 의미하지 않는다.

## 문서 검증

- `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe tools/check_docs.py`: exit 0, 24 original hashes와 582 versioned documents 포함 구조 검증 통과.
- 같은 인터프리터로 `tools/check_ontology.py`: exit 0, ontology·Obsidian mirror 검증 통과.
- `tools/sync_obsidian.py --check`: exit 1, 외부 Obsidian 수정 또는 관리되지 않는 충돌 경로 675건을 보고하고 쓰기 없이 중단했다. 최신 외부 편집을 덮지 않기 위해 `--apply`는 실행하지 않았다.
- `.venv/Scripts/python.exe -m pytest -q tests/test_recovery_drill_prerequisites.py`: exit 0, 19 passed. `git diff --check`: exit 0.
