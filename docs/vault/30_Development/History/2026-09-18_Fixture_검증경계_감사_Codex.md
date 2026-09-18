---
doc_id: "HIST-FIXTURE-BOUNDARY-AUDIT-001"
title: "Fixture 검증 경계 표본 감사"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T14:58:22+09:00"
source_of_truth: "Git"
---

# Fixture 검증 경계 표본 감사

base a68efaa, task 검증경계 후속감사 우선순위3, owner Codex(검증계약), reviewer Claude(미검토), branch agent/codex/model-registry-binding. agent-delivery1.1.0/core-reliability1.0.0 적용. 공통판1.0.97/Codex1.0.64/지도1.3.0 기준으로 착수했다.

## 집계 수정의 사용자 독립 실행 수신

ad0f90c에 --collect-only 실제 CLI 실행: exit2, subprocessExitCode null, evidenceStatus rejected-mode를 사용자 확인. 고유 디렉터리 두 개 verify-aggfix-3f8511d5…/verify-aggfix2-3f396b6b… 생성도 사용자 확인. 이 두 실행은 서로 다른 prefix이며 같은 prefix 재사용 실측은 작성자의 기존 회귀 시험 근거와 구분한다. 동일 prefix에도 UUID 격리가 적용된다는 소스 논거를 별도로 유지한다. 사용자의 첫 pipeline tail exit0은 측정 오류로 정정되어 도구 결과로 인용하지 않는다. VB-AGG-01/02는 작성자 검증+사용자 명시 경로 독립 실행, Claude 소스 검토 대기다.

## 범위와 방법

tests/conftest.py, tests/integration/conftest.py, tests/db_login.py, tests/credential_conformance.py를 읽고 실제 호출자 test_database_login_isolation.py/test_credential_conformance.py/test_credential_backend.py를 대조했다. credential_provision의 예외 단언과 계약 문서를 추가 표본 확인했다. 전수 시험 의미 감사가 아니다.

Evidence/verification-boundary-audit/fixture-audit.py는 원본 fixture.__wrapped__와 context manager를 호출하며 DB 연결/engine/provider 경계만 합성한다. 실제 SQL 문자열·cleanup 호출 여부를 기록하고 temp 파일을 사용했다. Docker/실제PG/운영 자격증명/CI 실행0. fixture-results.json에 11관측. 기존 credential 모델 시험은 실제 backend 인수가 아니다.

## VB-FIX-01 / P2 — setup 부분 성공 이후 cleanup 미진입

tests/integration/conftest.py postgres: autocommit CREATE DATABASE와 CREATE ROLE이 try/finally보다 앞에 있다. CREATE DATABASE 성공 후 CREATE ROLE에서 오류를 주입하니 generator 종료까지 DROP DATABASE 호출0이었다. DB 생성은 별도 autocommit이므로 role 실패로 DB가 rollback되지 않는다. setup은 ERROR로 끝나며 PASS 위장은 아니다. 실패 환경에서 일회용 DB를 누적시킬 수 있는 fixture 자원 정리 결함이다. 실제 PostgreSQL에서 권한 실패/디스크 압박을 재현한 것은 아니며 이번 호스트 압박의 원인이라고 하지 않는다.

수정 조건: 첫 자원 할당 전 cleanup 구조에 진입하고 성공적으로 생성한 DB/role의 소유권을 각각 추적한다. 생성 실패한 이름이나 타 실행 자원을 삭제하지 않는다. DB 제거 실패가 role 정리 시도까지 무조건 건너뛰지 않게 결과를 분리하되 원래 setup 실패와 정리 실패를 모두 보존한다. 정상·첫생성 실패·DB성공/role실패·migration실패·teardown실패 음성 대조 필요. 다음 구현 owner Claude(테스트 fixture), Codex 계약 재검토. 이번 감사는 미수정 finding이다.

## VB-FIX-02 / P3 — dispose 실패가 role 정리를 건너뜀

tests/db_login.py application_test_engine finally는 engine.dispose() 다음 DROP ROLE을 실행한다. dispose에 RuntimeError, 본문에 AssertionError를 주입하니 DROP ROLE0이며 최종 RuntimeError의 __context__에 원래 AssertionError가 남았다. 따라서 원래 오류가 완전히 사라졌다거나 PASS/skip으로 둔갑했다고 하지 않는다. synthetic disposal failure에 대한 정리 보강 필요이며 정상 SQLAlchemy driver에서 빈번한 장애라고 주장하지 않는다.

수정 조건: engine 해제와 본인 role 제거를 각각 시도하고 원래 오류·cleanup 오류를 함께 보존한다. KeyboardInterrupt/SystemExit를 무조건 삼키는 방식 금지. 실제PG의 활성 연결/권한 제약 때문에 DROP ROLE이 실패할 수도 있으므로 시도와 제거 성공을 구분한다. 다음 Claude 구현, Codex 재검토. 이번 감사에서 미수정.

## 오탐 제외와 정상 실패 경계

- root/integration DSN 부재는 각각 local skip, CI fail을 원본 fixture 호출로 확인(4관측). dummy DB나 PASS 반환 없음. 로컬 환경에서 DB시험3건 skip을 성공 수에 넣지 않았다.
- credential mutation은 pytest.raises(CredentialDenied) 바깥이다. mutate가 CredentialDenied를 던지면 expected denial로 흡수되지 않고 전파됨을 확인했다. backend/test 관련 denies는 특정 예외 유형을 사용한다. 이번 표본에서 setup 예외를 통과로 바꾸는 새 경로는 발견하지 못했다.
- remove_version은 grant DELETE, rebind_destination은 grant enabled=false와 동일 SQL이라는 관측은 맞다. 그러나 [[Codex 운영 자격증명과 Storage 계약]]이 immutable version 파괴 대신 grant 삭제/회수로 해석 불가를 만드는 의미를 명시한다. [[Codex 자격증명 보안 검증 인계]]의 action 의미와 대조해 새 finding에서 제외했다. 이 시험을 물리 version 삭제나 destination 문자열 변경 검증으로 확대 해석하지 않는다.
- db_login의 CREATE ROLE/GRANT는 owner_engine.begin() 트랜잭션 내부다. integration의 autocommit 부분할당 문제를 이 경로에도 똑같이 있다고 일반화하지 않는다.
- 기존 deliberate-fault 모델 시험은 잘못된 context/read-before-auth/revocation/filesystem/retarget/secret representation/callback retry를 실패시킨다. 모델 경계이며 실제 Linux file/PG 인수와 별개다.

## 실행 기록과 인계

`python .../fixture-audit.py . .../fixture-results.json`: 최종 exit0, 11관측. 보강 첫 실행은 감사 코드가 CredentialDenied에 잘못된 생성자 인자를 전달해 TypeError/exit1; 인자 없는 실제 API로 고쳐 재실행했다. 제품 결함/환경 실패로 분류하지 않는다.

`python -m pytest -q tests/test_credential_conformance.py tests/test_database_login_isolation.py`: exit0, 47 passed / 3 skipped, 0.09초. DSN 부재로 실제DB login3건 미실행. 기존 사용자의 disposable DB 제공 이력을 부정하는 것이 아니라 이 명령에 DSN을 설정하지 않은 오프라인 감사 범위다.

다음 Claude: VB-AGG-01/02 독립 소스 검토 및 두 fixture finding 구현 검토. 다음 Codex: 수정본의 오류 보존·자원 소유권/정리 결과 재검토. CI 결제/gh 인증·운영 인수0/5·image business-kernel-role 미검증 유지. 새 외부 조건 없이 동일 image lane 반복하지 않았다.
