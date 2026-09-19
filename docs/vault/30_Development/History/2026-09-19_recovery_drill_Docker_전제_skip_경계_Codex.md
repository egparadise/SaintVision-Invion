---
doc_id: "RECOVERY-DRILL-DOCKER-PREREQUISITE-20260919-CODEX"
title: "test_recovery_drill Docker 선행조건 skip/실패 경계"
version: "1.1.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-19T17:24:47+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
---

# test_recovery_drill Docker 선행조건 skip/실패 경계

## 기준과 원인

- 기준 코드: integration `066c801`; 원 JUnit 기록은 `.work/codex-dbtest-integration.xml`, `.work/codex-dbtest-recovery.xml`, `.work/codex-dbtest-recovery2.xml`.
- `codex-dbtest-integration.xml`: recovery drill을 요구하는 18개 test case가 모두 `docker inspect 127.0.0.1`의 `No such object`로 setup error였다. `CX01_CONTAINER`가 비어 있었고 fixture가 PostgreSQL DSN의 TCP host를 Docker 컨테이너 이름으로 잘못 대체했다. TCP 주소는 container identity가 아니다.
- `codex-dbtest-recovery.xml`: 컨테이너 inspect는 성공했지만 fixture가 `ai.saintvision.cx01` 또는 `ai.saintvision.kernel-test`만 허용했다. 실제 disposable test container는 `ai.saintvision.codex-db-test`와 `ai.saintvision.created-by=codex`로 소유를 표시했다. 이는 외부 컨테이너가 아니라 알려진 자체 시험 자원인데 오래된 allowlist가 이를 거부했다.
- 따라서 관측된 두 setup 오류 원인은 각각 **컨테이너 identity 미설정/미발견**과 **자체 disposable DB 라벨 계약의 누락**이다. 이 18건은 platform 또는 Docker network 오류가 아니었다. Windows/Linux 개인 백업 경로는 개별 test가 명시적 Linux skip을 내며, owned internal network 생성 실패도 별도 사유의 skip으로 처리한다. 만들어진 network가 `Internal != true`이면 skip이 아니라 assertion 실패다.
- `codex-dbtest-recovery2.xml`의 7 assertion failures는 위 setup error와 다른 결과다. 후속 수정 후 재실행 결과로 혼합하거나 과거 18건과 합산하지 않는다.

## 변경

`tests/integration/test_recovery_drill.py`는 `CX01_CONTAINER`가 명시되지 않으면 DSN host를 컨테이너 이름으로 쓰지 않고 이유가 보이는 skip을 낸다. Docker CLI 부재, configured container 부재, daemon 접근 실패, inspect timeout, 권한 거부도 각각 구체적인 skip 사유다. 설정된 이름이 실제 컨테이너이고 소유 증거가 없거나 검사 응답이 손상/예상 밖이면 skip으로 숨기지 않고 실패시킨다.

허용 소유 증거는 `ai.saintvision.cx01`, `ai.saintvision.kernel-test`, 또는 `ai.saintvision.codex-db-test`와 `ai.saintvision.created-by=codex` 쌍이다. 알려진 disposable 컨테이너는 이를 통해 진행한다. 그 외 라벨은 foreign/unowned 가능성이 있으므로 drill 실행을 거부한다. 라벨 mismatch는 전제 미충족 skip으로 처리하지 않는다.

## 이번 변경의 검증

- `.venv\Scripts\python.exe -m pytest -q tests/test_recovery_drill_prerequisites.py` → **11 passed**, exit 0. 누락 identity, 미존재 컨테이너, Docker CLI/daemon/권한 조건의 reasoned skip과 자체 라벨 통과 및 미소유 라벨 실패를 mock inspect 경계에서 검증했다. integration `args` fixture를 직접 호출해 identity 미설정이 setup error가 아니라 skip으로 전파되는 것도 확인했다. 알려진 소유 라벨에서 helper 다음의 marker가 실행되는 로컬 시험은 통과했다. 이는 helper/fixture gate 근거이지 `drill.rehearse()`의 실제 PostgreSQL 실행 근거는 아니다.
- `.venv\Scripts\python.exe -m pytest --collect-only -q tests/integration/test_recovery_drill.py` → **19 collected**, exit 0. 그중 공용 `args` fixture를 요구하는 복구 test는 18개이며, 별도의 cleanup helper test 1개는 이 fixture를 쓰지 않는다.
- `.venv\Scripts\python.exe tools/check_docs.py` → **PASS**, 579 versioned documents; `tools/check_ontology.py` → **PASS**; `git diff --check` → exit 0.
- Python compile check: `tests/recovery_drill_prerequisites.py`, `tests/integration/test_recovery_drill.py` 성공.
- 이 변경 후 PostgreSQL을 이용한 18개 본문 실행은 아직 수행하지 않았다. Claude의 기존 전체 회귀가 진행 중이므로 Docker/PostgreSQL 작업과 경합하지 않도록 기다린다. 전체 회귀 결과가 도착하면 **수정 전 기준선**에서 18건이 어떻게 분류됐는지를 JUnit으로 대조하고, 종료 후 명시적 소유 container로 recovery drill을 실행해 본문 진입/결과를 별도 증거로 남긴다.

## 남은 확인과 담당

Codex: Claude 전체 회귀 종료 후, 적법하게 소유가 확인된 disposable PostgreSQL container와 `CX01_CONTAINER`를 지정해 수정 후 18개 recovery cases를 실행한다. 누락/부재 환경에서는 같은 18개 fixture cases가 setup error가 아니라 개별 reasoned skips로 나타나는지, 기존 container가 있으나 미소유 라벨이면 실패하는지, 알려진 own label이면 본문이 실제 실행되는지 결과 JUnit과 명령에서 확인한다. CI, 운영 DB, 다른 프로젝트 container는 사용하지 않는다.

## 2026-09-19 post-fix 실DB 실행 및 cleanup-label backstop

### 기준선의 귀속

- Claude 1차 회귀는 사용자 보고상 checkout `53f81ba`에서 실행됐고, 사용자 보고 집계는 `2180 passed / 2 failed / 18 errors / 417 skipped`였다. 해당 집계에는 JUnit artifact가 없어 **전수 집계로 확정하지 않는다**. `53f81ba`(커밋 시각 03:17:18 KST)는 `aeec9b3`(16:49:32 KST)보다 앞선 SHA다. 보고된 checkout SHA 기준으로 해당 실행은 수정 전이다. 실제 pytest 프로세스 시작 시각은 artifact가 없어 독립 대조할 수 없다.
- 사용자가 전한 별도 재실행의 `8 passed`는 setup 문제가 사라졌다는 사용자 보고로만 기록하며, 본 문서의 Codex 실행 수치와 합산하지 않는다.

### Codex 실행 기록

- 실행 날짜: 2026-09-19 KST. 전용 컨테이너는 `codex-recovery-3292177c0a28`, PostgreSQL 16, 임시 data 경로는 tmpfs, loopback 임의 host port. owner labels는 `ai.saintvision.codex-db-test=<container>` 및 `ai.saintvision.created-by=codex`. 실행 뒤 `docker inspect`가 `No such object`를 반환해 해당 임시 컨테이너 부재를 확인했다. Docker daemon은 cleanup 직후 한 차례 I/O timeout을 반환했으므로 확인을 재시도해 부재를 확정했다.
- Interpreter: `C:\Project\SaintVision-Invion\.venv\Scripts\python.exe` 9.1.1.
- 전제 미충족 실행: `INV_TEST_ADMIN_DSN`은 disposable PG를 가리키고 `CX01_CONTAINER`는 unset. 명령은 `.venv\Scripts\python.exe -m pytest -q tests/integration/test_recovery_drill.py --junitxml=.work/recovery-aeec9b3-no-identity.xml`, exit 0. JUnit 파일 시각 17:18:03 KST: 19 tests, 1 passed (standalone cleanup-helper test), 18 skipped, 0 failures, 0 errors. 18개의 skip 사유는 모두 `CX01_CONTAINER is unset`; DSN host에서 container 이름을 추정하지 않았다.
- 소유 전제 충족 실행: 같은 disposable PG, `CX01_CONTAINER=codex-recovery-3292177c0a28`, 명령은 `.venv\Scripts\python.exe -m pytest -q tests/integration/test_recovery_drill.py --junitxml=.work/recovery-aeec9b3-owned.xml`, exit 1. JUnit 파일 시각 17:19:58 KST: 19 tests, 13 passed, 4 skipped, 2 failures, 0 errors. 18개 DB/owner fixture test 중 12개 본문이 통과했고 4개는 Linux private-backup/rollback 전제 때문에 명시 skip됐다. 나머지 2개 `test_live_archiver_configuration_cannot_certify_operational_rpo[/bin/true|/bin/false]`는 별도 internal-network archiver fixture의 readiness timeout에서 실패했다. 이 두 건은 제품 assertion 결과가 아니다. 근본 원인은 이 실행만으로 확정하지 않으며 후속 환경/fixture 진단 대상이다.
- 별도 소유 경계 시험: `.venv\Scripts\python.exe -m pytest -q tests/test_recovery_drill_prerequisites.py`는 해당 시험군에 포함되어 11건 통과했다. 사용자도 aeec9b3의 여섯 시나리오를 독립 행동 검증했고, missing/absent/daemon unavailable은 서로 다른 skip이며 unowned/unknown inspect는 failure라고 보고했다. 그 사용자 실행은 Codex JUnit에 합산하지 않는다.

### cleanup label allowlist gap

- 소스 코드 라벨 literal 전수 스캔에서 cleanup allowlist에 없던 `ai.saintvision.rpo-test`와 `ai.saintvision.rpo-network`를 찾았다. 이 라벨을 가진 recovery archiver 컨테이너와 격리 네트워크는 fixture teardown이 비정상 종료할 때 cleanup backstop에 보이지 않았다.
- `tools/cleanup_owned_docker.py`의 `OWNERSHIP_LABELS`에 두 라벨과 기타 임시 테스트 자원 라벨을 추가했다. 현재 literal 26개는 cleanup eligible 17개와 runtime/metadata 보존 9개로 명시 분류된다. `config`는 private material을 보관할 수 있는 명시적 volume에 쓰이므로 정리 허용하지 않는다. `node`, `pilot`, `command`, `storage-replace`, `upgrade`, `supervisor`, `output`, `created-by`도 cleanup 소유권으로 취급하지 않는다.
- `tests/test_cleanup_owned_docker_label_inventory.py`가 Git 추적 파일 중 Python/PowerShell/shell/JS/MJS/YAML 소스 전체를 훑어 literal label 전체가 allowlist 또는 명시 보존 set에 분류되는지 확인한다. `rpo-test`를 allowlist에서 임시 제거한 음성 대조에서 시험은 exit 1로 실패했고, 복구 후 cleanup/recovery 경계 시험은 17 passed였다.
- 이 스캔은 Git 추적 소스의 literal label 문자열에 대한 정적 인벤토리이며, 런타임에서 조합되는 문자열이나 저장소 밖에서 만든 자원까지 증명하지 않는다. 실제 자원 삭제는 수행하지 않았다.

### 아직 남은 것

- Claude의 `--junitxml` 전체 회귀 재실행은 진행 중이며 산출물은 아직 확인하지 않았다. 사용자가 보고한 2180/2/18/417 집계는 artifact가 도착할 때까지 확정 집계로 인용하지 않는다.
- 이 Codex 실행은 수정 후 `test_recovery_drill` setup errors가 사라짐을 실제 JUnit으로 확인했다. 전체 파일은 archiver readiness 두 건 때문에 깨끗한 pass가 아니며, 그 원인을 제품 결함이나 Docker 환경 중 하나로 섣불리 단정하지 않는다.
