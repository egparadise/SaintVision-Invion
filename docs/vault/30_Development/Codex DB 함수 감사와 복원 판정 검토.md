---
doc_id: "CONTRACT-DEFINER-AUDIT-001"
title: "Codex DB 함수 감사와 복원 판정 검토"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-09-11T18:43:33+09:00"
source_of_truth: "Git"
---

# Codex DB 함수 감사와 복원 판정 검토

CX-01 / SECURITY-AUDIT-INTEGRITY. owner Codex, 독립 reviewer Claude pending. 기준은 [[최종 개발 계획 - 모든 개발의 지침]]·[[DB 최종 개발 계획]]·[[Codex 실제 실행 결과 조회 계약]].

## ADR-072 — 현재 적용 함수의 보수적 감사

`tools/check_definer_functions.py`를 유일한 DB definer 감사 진입점으로 유지한다. Claude 9995122의 초기 도구를 보강한다. 다른 이름의 중복 감사 구현을 만들지 않는다.

- `tools/definer-policy.json` v1은 c5f2154의 0033 적용 결과 9개 함수의 전체 schema/인자형 시그니처·`pg_get_functiondef` SHA-256·직접 EXECUTE role을 고정한다. source의 담당 검토와 실제 역할 시험에 연결하는 기준이며 독립 승인 자체는 아니다.
- 7개 inv_app 공개 함수와 2개 폐기 reader/offer 함수를 구분한다. 폐기 함수의 inv_app/PUBLIC 재부여, grant option, 다른 schema/overload·인자 없는 신규 definer, 알려진 함수의 누락/SECURITY INVOKER 전환도 review_required다.
- 정의 전체를 비교하므로 주석 속 setting, 사용하지 않는 setting 조회, 바뀐 검색 경로·언어·인자/반환 형태를 부분 문자열로 승인하지 않는다. `node_by_certificate`의 예외는 정확한 하나의 정의·시그니처이며 같은 이름 전체를 허용하지 않는다.
- inv_app/inv_kernel의 superuser/BYPASSRLS, 신뢰 schema(public/inv/pg_catalog) CREATE, 함수 owner role을 맡을 수 있는 membership을 거부한다. 직접 개별 운영 로그인 전체의 권한 감사나 DB superuser에 대한 방어를 뜻하지 않는다.
- 하나의 read-only/repeatable-read snapshot에서 catalog를 조회하며 감사 대상 함수는 실행하지 않는다. 시스템 schema를 제외한 사용자 schema를 조사한다. migration 불일치·필수 함수/role 누락은 합격 불가. 연결/권한/정책 파일/조회 실패는 unavailable(exit 2)이며 빈 성공 목록으로 바꾸지 않는다.
- CLI는 INV_AUDIT_DSN 환경 변수를 권장하며 --dsn도 유지한다. 예외 원문의 SQL/DSN/토큰은 출력하지 않는다. exit 0은 **기준 catalog와 일치**, exit 1은 **검토 필요**, exit 2는 **관측 불가**다. 전체 tenant 안전/복원 성공이라 표현하지 않는다.
- 기존 `check_migration_upgrade.py`는 각 공개 prior→head→head 경로에서 감사도 통과해야 한다. 격리 Docker source copy에 도구와 정책을 포함한다.

정책 갱신은 새 migration을 별도 DB에 적용한 정의를 읽고 의미·권한·교차 tenant 동작을 검토한 뒤 source와 함께 commit한다. 운영 대상의 hash를 자동 학습하여 mismatch를 없애는 기능은 제공하지 않는다. PostgreSQL 버전의 정의 출력 차이도 검토 후 반영한다.

## 검토 회신과 범위

Claude 9995122의 감사: 보안 정의/권한 비교로 보강. 같은 SHA의 recovery_drill은 실제 잘못된 백업 실패를 합격 처리했으므로 **수정 요청**이다. CL-03의 구현 owner는 Claude, Codex는 고위험 판정/epoch·fencing 계약과 수정본을 검토한다.

Gemini f50310e의 파일 버튼/Node 표시 개선을 확인했으나, fixture handler는 없는 파일에 생성 문자열을 200으로 반환한다. raw fetch에는 공통 JWT 헤더가 없고, kernel의 `X-Content-SHA256` 대조가 없다. 코딩 과제는 여전히 24 true/6 false로 생성된다. GM-01/04에 수정 요청하며 이 버전을 실결과·AC-09 인수로 승인하지 않는다. 이 조회는 local fixture/소스 검토이며 실제 2-PC 검증이 아니다.

실제 결과 정본은 `inv.app`의 인증된 `/v1/runs/{run_id}/artifacts/content?path=...`→ResultView다. 새로운 fixture reader를 이를 대체하는 구현으로 통합하지 않는다. 없는 파일/권한/바이트 검증 실패는 오류로 유지한다.

오류와 재현: [[2026-09-11_SECURITY-AUDIT-INTEGRITY_오류와해결]]. 검증·전달 기록은 [[2026-09-11_SECURITY-AUDIT-INTEGRITY_Codex_검증보고]].

공식 근거: [PostgreSQL 16 CREATE FUNCTION](https://www.postgresql.org/docs/16/sql-createfunction.html), [Row Security Policies](https://www.postgresql.org/docs/16/ddl-rowsecurity.html), 2026-09-11 확인. SECURITY DEFINER는 owner 권한으로 실행하며 RLS 우회 여부는 superuser/BYPASSRLS 및 table ownership/FORCE RLS에 달린다. 선언 하나로 항상 우회한다고 단정하지 않는다.

## 18:08 이후 수정본 인수 메모

Claude c28cdff는 과거 invalid backup/empty DB 허위 성공을 실제 재시험에서 거부했다. 남은 _passed의 측정값/restore exit 판정과 전체 복원 범위는 [[2026-09-11_SECURITY-AUDIT-INTEGRITY_Codex_검증보고]]를 따른다. 과거 9995122 finding을 수정본에도 미수정이라고 전파하지 않는다. Gemini f50310e의 결과/평가 finding은 유지한다.

## ADR-073 — 복원 도구의 정본 연결과 보수적 판정

`tools/recovery_drill.py`는 Claude dee31e5(복원 구현 0581964)의 도구를 이어받은 **하나의 진입점**이다. 일반 복원 기능 owner는 Claude, 이번 판정/무결성 통합 변경 owner는 Codex이며 Claude의 독립 검토를 요청한다. `_definer_rules.py`의 SQL 패턴 판별을 ADR-072 정책과 나란히 합격 판정기로 두지 않는다. 정책 정의/EXECUTE/migration이 모두 일치해야 이후 DB 역할 probe를 실행한다.

- 실제 pg_restore nonzero, target에서 완전히 빠진 테이블, 읽기 실패, digest·권한·RLS·소유자 불일치는 합격 불가다. 원본 객체 owner/권한을 복원하며 `--no-owner`나 `--no-privileges`로 오류를 숨기지 않는다.
- public/inv 양쪽 role로 두 tenant와 빈 scope를 읽는다. 임의 고유 ID를 임시 삽입하고 항상 transaction rollback한다. 역할명은 SQL Identifier로 인용하며 superuser/BYPASSRLS를 거부한다.
- 현재 정책 9개와 table inventory/count·9개 Evidence 테이블 내용 digest를 검증한다. 전체 table content/DDL/trigger의 보안 증명은 아니다. `contentDigestScope`에 대상이 나온다.
- RPO는 복원 시작 시각−백업 recovery point다. 새 dump는 시작 시각을 보수적인 recovery point로 사용한다. 파일 mtime은 사용하지 않고, timezone 미상·미래·음수/NaN/Infinity·미측정은 합격 불가다. RTO는 DB 생성부터 함수/권한/tenant/fencing 확인 종료까지 잰다.
- source의 전/후 발급 상한과 target의 `last_value/is_called`를 비교해 **다음 발급값**이 이미 관측한 토큰보다 커야 한다. 도구가 sequence/epoch/Node를 자동으로 변경하거나 운영 제출을 재개하지 않는다.
- CLI 종료와 기록은 같은 `_passed`를 사용한다. 실제 pilot 서비스의 `rpo_seconds/rto_seconds` 인자를 사용하며 DB에 저장하는 정수 초는 올림한다. 따라서 900.01초를 900초로 내려 RPO 목표 합격으로 기록하지 않는다. 복원 기능 합격과 `met_targets`는 구분한다.
- DSN은 `INV_RECOVERY_{SOURCE,ADMIN,CONTAINER,RECORD}_DSN`을 사용한다. 하위 pg client의 password는 argv에서 제거해 해당 프로세스 환경으로 전달하며 예외 원문/SQL/행 데이터는 공용 출력에 남기지 않는다. 로그에 비밀을 기록한 뒤 정규식으로 지우는 방식에 의존하지 않는다.
- `scope=database_rehearsal`, `operationalRecoveryVerified=false`, `notVerified`를 보고서와 DB notes에 보존한다. `serviceResumed`는 호환 필드이며 DB role probe 결과다. 실제 HTTP 로그인·업무 재개를 뜻하지 않는다.

이 도구는 신뢰된 백업과 미리 role이 준비된 격리 복원 환경에서 사용한다. 비교 중 source 쓰기는 중지되어야 한다. 같은 클러스터에서 role을 관측한 것은 별도 클러스터의 role 복원 훈련이 아니다. 객체 바이트·Node journal/epoch·PITR·쓰기 동시성·운영 로그인·실장비 작업 재개는 CL-03/CX-07 잔여다. CLI exit 0만으로 전체 인수 완료를 주장하지 않는다.

공식 근거(2026-09-11 확인): [PostgreSQL pg_restore](https://www.postgresql.org/docs/16/app-pgrestore.html), [Sequence functions](https://www.postgresql.org/docs/16/functions-sequence.html), [Docker exec environment](https://docs.docker.com/reference/cli/docker/container/exec/). 위 문서의 정의와 로컬 실행 증거를 구분한다.

착수/범위: [[2026-09-11_RECOVERY-INTEGRATION_Codex_착수]]. 검증·진행도와 다음 인계는 작업 후 History에 추가한다.
