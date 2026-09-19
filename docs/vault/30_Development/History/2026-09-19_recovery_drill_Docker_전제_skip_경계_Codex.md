---
doc_id: "RECOVERY-DRILL-DOCKER-PREREQUISITE-20260919-CODEX"
title: "test_recovery_drill Docker 선행조건 skip/실패 경계"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-19T16:48:40+09:00"
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
