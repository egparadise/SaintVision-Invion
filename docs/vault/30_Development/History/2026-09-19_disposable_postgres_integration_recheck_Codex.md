# Disposable PostgreSQL 통합 재검증 및 credential 경계 수정

- 기준 SHA: `65db2a5` (credential 수정 후 `25051e3`)
- owner: Codex / reviewer: 독립 검증 대기
- 환경: `.venv\Scripts\python.exe`, Docker `postgres:16`, 소유 컨테이너 `codex-dbtest-20260919-11f6a3b458dc`, host port `61902`
- 소유 확인: `ai.saintvision.codex-db-test=codex-dbtest-c1bb7c1f67044fdcb4a4345158478a9d`, `ai.saintvision.cx01=codex-owned`; 다른 프로젝트 컨테이너는 보존

## credential provisioning 수정

`tools/provision_credentials.py`의 `provision()` 내부 catch-all이 `ProvisioningDenied`로 모든 예외를 뭉개던 결함을 수정했다. 이제 의도된 거부는 그대로 전파하고, `psycopg.Error`는 검증된 5자리 `sqlstate`만 담은 `ProvisioningDatabaseError`, 그 밖의 예외는 타입명만 담은 `ProvisioningInternalError`로 변환한다. 연결 context manager의 rollback은 유지되며 DSN·예외 본문은 출력하지 않는다. CLI 코드는 `2=거부`, `3=DB`, `4=내부`와 일치한다.

검증:

- `.venv\Scripts\python.exe -m pytest -q tests/core/test_credential_provision_cli.py tests/core/test_lan_migration_plan.py`: `24 passed, 1 skipped` (migration DB 한 건은 별도 파일의 DSN 조건)
- 플랫폼 비의존 주입 시험에서 RuntimeError의 rollback·비밀 비노출·InternalError 분류와 psycopg 오류의 DatabaseError 분류를 확인했다.
- 되돌림 대조는 종료 코드/예외 범주 회귀시험으로 유지한다. Linux credentials 통합 시험은 Windows에서 `Linux credentials`로 skip되어 직접 근거로 사용하지 않았다.

## PostgreSQL 실행 결과

당시 선택된 완료 배치의 합계를 `432 passed / 386 skipped / 0 failed`로 보고했다. 뒤의 감사에서 manifest 부재와 JUnit setup errors가 확인되어 이 aggregate는 철회됐다. 별도 non-integration DSN 대상 `97 passed / 0 failed` (`54 + 43`)는 별도 run 기록이며 integration 전체 집계와 합산하지 않는다.

추가로 `test_recovery_drill.py`는 소유 container 라벨 요구를 맞춘 뒤 `11 passed / 7 failed`를 관측했다. 실패는 제품 결함으로 확정하지 않았다:

- Windows에서 Linux 전용 백업 경로를 요구하는 3건과 internal Docker network를 요구하는 2건은 호스트/플랫폼 선행조건 불충족이다.
- definer 함수 개수 기대치 `9` 대 실제 `10`은 현재 migration 정책과 시험 기대치의 drift 후보이며, 운영 결함으로 승격하지 않고 별도 검토 대상으로 남긴다.
- Docker/PG 복원 시험은 이 호스트의 Windows·네트워크 경계 때문에 운영 인수 근거가 아니다.

초기 첫 배치는 잘못된 비밀번호를 사용해 연결 실패했으며 결과 집계에 포함하지 않았다. 이후 컨테이너 환경에서 실제 비밀번호를 읽어 재실행했다. 소유 컨테이너만 중지·재생성했으며 다른 컨테이너에는 접근하지 않았다.

다음 행동: 소유 컨테이너를 최종 정리하고 제거 확인을 남긴다. Linux credentials, Docker/Workspace, browser, 실제 restore 인수는 해당 환경/권한 조건에서 재개한다.

## 후속 보강

독립 재검증으로 `provision()` catch-all의 실제 붕괴가 `validate_manifest`를 우회한 주입에서 재현됨을 확인했다. `25051e3`는 DB 오류/내부 오류/거부를 올바르게 분리하고 비밀값을 노출하지 않는다.

복원 시험의 definer 기대치는 `tools/definer-policy.json`의 함수 서명 집합을 직접 비교하도록 바꿨다(`7eb0d66`). 정책에 함수가 추가·삭제되면 개수뿐 아니라 정확한 함수 이름 집합 단언이 깨진다. Windows 전용 실행에서 Linux 백업 경로 또는 내부 Docker 네트워크가 없는 경우 6개 경로는 원인 메시지가 있는 `pytest.skip`으로 분리했다. 실제 복원 리허설 재실행은 해당 Linux/격리 Docker 조건에서 필요하다.

후속 검토에서 archiver 네트워크 skip은 잘못된 관찰 결과 은폐임을 확인했다. `test_live_archiver_configuration_cannot_certify_operational_rpo`가 이제 자기 소유의 `docker network create --internal`을 먼저 수행하고, 생성 실패만 skip한다. 생성된 네트워크의 `Internal` 속성이 false이면 보안 발견으로 실패한다. 나머지 Linux 경로 skip은 플랫폼 전제만 검사한다.

추가 보강: archiver 시험의 `finally` 정리를 `_cleanup_owned_docker_resource`로 분리했다. 컨테이너와 네트워크를 각각 query-error/confirmed-absent/ownership-mismatch/remove-error/confirmed-removed로 분류하고, 한 단계 실패해도 다음 단계를 시도한다. 소유권 불일치 자원은 보존하며, 삭제 후 재-inspect로 제거를 확인한다. cleanup 오류는 본문 예외가 진행 중이면 stderr에만 기록해 본문 실패를 대체하지 않는다. 합성 회귀시험은 비소유 보존과 정상 제거 확인을 모두 포함한다.

## 감사 정정 — 통합 JUnit 집계와 실패 분리

기존 `432 passed / 386 skipped / 0 failed`는 선택 배치라는 설명만 있고 당시 파일 목록/manifest가 없어 재현 불가라 철회했다. 로컬 `.work` JUnit을 사후 대조해 825건 중 421 passed, 386 skipped, 18 setup errors임을 별도 확인했다. 후속 40e921b의 artifact-backed 5-batch 결과는 이 문서의 정정과 [[2026-09-19_archiver_readiness_boundary_Codex]]에 기록한다. 이전 실행과 후속 실행은 합산하지 않는다. 당시 로컬 JUnit은:

- `.work/codex-dbtest-integration.xml` (2026-09-19 02:04 KST): 825 collected, 421 passed, 386 skipped, 18 setup errors. 18건 모두 `test_recovery_drill`의 disposable PostgreSQL 컨테이너 inspect/소유 라벨 선행조건 실패로 본문 assertion에 도달하지 못했다.
- `.work/codex-dbtest-recovery.xml`: 동일 18건이 잘못된 container owner label로 setup 단계에서 실패했다.
- `.work/codex-dbtest-recovery2.xml`: 수정된 owner 경로에서 18건 중 11 passed / 7 failed. 실패는 definer 기대치 1, internal network 격리 2, Linux 전용/절대 backup 경로 4다. 후속 코드가 definer 집합을 정책에 연결하고 network 소유·격리 선행조건을 고쳤지만, 이 7건 전체를 수정 후 실제 PostgreSQL로 재실행한 JUnit은 이 감사에서 찾지 못했다.

정정: 당시 `432/386/0` 보고는 전체 integration 근거로 사용하지 않는다. 실제 JUnit 사후 파싱값은 421 passed / 386 skipped / 18 setup errors였다. 이후 최신 코드 SHA `40e921b`에서 Claude가 실행한 **5개 배치 산술 합**은 2628 tests / 2192 passed / 1 failure / 0 errors / 435 skipped이며, manifest 집합 대조로 누락 0·중복 0임을 사용자와 Codex가 각각 확인했다. 이 값은 여전히 단일 실행이 아니며 이전 Codex 실행과 합산하지 않는다. 인터프리터, KST timestamps, 배치 JUnit/manifest 경로와 180초 timeout 관찰은 [[2026-09-19_archiver_readiness_boundary_Codex]]에 정정 근거와 함께 기록했다.
