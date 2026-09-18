---
doc_id: "HIST-FIXTURE-A5401A7-REVIEW-001"
title: "Fixture a5401a7 재검토"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T15:08:56+09:00"
source_of_truth: "Git"
---

# Fixture a5401a7 재검토

base828ba42, reviewed a5401a7, owner Codex(review), implementation Claude, branch agent/codex/model-registry-binding. agent-delivery1.1.0/core-reliability1.0.0 적용. 감사 종합3bb3622/지도1.4.0 이후 갱신이다. 사용자 정상진행 승인 유지.

## 결론

VB-FIX-01 원래 부분할당/독립정리 결함은 소스·합성 회귀 기준 해소로 판정한다. 실제PG fixture 통합 경로는 이번에 실행하지 않았다. VB-FIX-02의 dispose 실패 후 DROP 생략은 해소됐지만 dispose+DROP 동시 실패의 오류보존 잔여가 있어 전체 수정 완료 선언은 보류한다. a5401a7 또는 Claude 브랜치 전체를 integration에 병합하지 않았다. PITR 신규0da140e도 fetch로 도착 확인했으나 이 fixture 검토가 PITR 검토를 대신하지 않는다.

## 9시험 범위 대조

| 시험 | 포함 여부/실제 경계 |
|---|---|
| 정상 생성·정리 | db_provision 1건, callable 호출순서/양쪽drop |
| 첫 DB 생성 실패 | 1건, 어떤drop도 미호출 |
| DB성공/role실패 | 1건, DB만drop |
| migration 실패 | prepare 실패1건, 양쪽drop; 실제Alembic/SQL 아님 |
| teardown DB drop 실패 | 1건, role도시도/오류전파 |
| 본문 오류 | 1건, helper gen.throw 원래오류 보존 |
| 본문+DB drop 실패 | 1건, cleanup 오류.__context__ 원래오류 |
| login 정상 teardown | 1건, fake engine dispose/role drop |
| login 본문+dispose 실패 | 1건, DROP성공/원래본문 context |

다섯 요청 조건은 모두 포함된다. 다만 **실제 DB 시험은 0건**이다. 파일 docstring도 No real database를 명시하고, connection/engine 또는 생성·정리 callable을 fake로 주입한다. 사용자의 DSN 설정9passed는 독립 실행으로 유효하나 실제PG16 생성/삭제·grant·migration 성공 증거로는 확장하지 않는다. Codex가 `git show a5401a7:tests/<file>`로4파일을 .work/review-a5401a7에 추출하고 `python -m pytest --noconftest -q .../test_db_provision.py .../test_db_login_teardown.py` 실행: exit0,9passed,0.36초. 사용자9와 합산18로 쓰지 않는다. 본문 gen.throw는 helper 경계이며 pytest fixture teardown 자체가 본문 exception을 generator에 주입한다는 뜻도 아니다.

## VB-FIX-02-R1 / P3 — dispose+DROP 동시 실패 시 dispose 오류 누락

원본 a5401a7 db_login.application_test_engine에 body AssertionError, engine.dispose RuntimeError, DROP ROLE ValueError를 주입했다. CREATE ROLE/GRANT/DROP ROLE 호출은 모두 관측됐으나 최종 chain은 **ValueError(drop) → AssertionError(body)**였고 RuntimeError(dispose)는 없었다. dispose_error를 저장한 뒤 DROP에서 예외가 발생하면 마지막 raise dispose_error에 도달하지 않는다. 전체 실행은 nonzero이며 PASS 위장이 아니다. 원래 누수 방지 경로가 다시 무력화됐다는 뜻도 아니다; DROP은 시도됐다. 기존 수정 조건인 원래오류+cleanup오류 모두 보존의 잔여다.

Evidence/verification-boundary-audit/fixture-a5401a7-review.json에 주입/관측을 남겼다. 재현은 대상commit의 db_login과 test_db_login_teardown FakeOwnerEngine/FakeEngine/_Raw를 import한 뒤 create_engine=FakeEngine(True), _Raw.execute에서 DROP ROLE에 ValueError를 주입하고 with 본문에 AssertionError를 발생시키는 방식이다. 실제PG/driver장애 재현 아님.

다음 Claude: dispose와 DROP 결과를 각각 모아 두 오류를 ExceptionGroup 등으로 노출하면서 본문 오류도 context 또는 명시적 구조로 보존. 본문 유무×dispose 실패×DROP 실패 조합, 단독DROP 실패 및 양쪽성공 대조를 추가. KeyboardInterrupt/SystemExit를 무조건 삼키지 않는다. db_provision의 양쪽drop동시실패 ExceptionGroup 분기도 현재9건에는 없어 추가 대조 권장(이번에 그 분기의 결함을 재현한 것은 아님). 생성명/소유권 보호는 유지한다.

## 11e9f44 독립 소스 검토 수신

Claude 7e3de2a의 실제 diff를 확인했다. operator INV_API_CONFIG에서만 읽는 registry policy, strict shape/중복거부, fail-closed·config 비노출, 공유 Database 결속에 대해 **sound / finding 없음** 독립 소스 검토 기록이다. 상태 지도와 최신 진행판의 '11e9f44 독립검토대기'를 해소한다. Codex 작성자46시험, Claude 소스검토, CI/운영인수는 별도 유지한다. 검토 문서 수신으로 실제 운영설정 인수를 완료하지 않는다.

감사1~5 종합은 이미 [[검증 경계 감사 종합과 잔여 범위]]에 있으며 이번 판정으로 FIX상태를 갱신했다. 다음Claude FIX02-R1 수정, Codex 재검토 및 도착PITR0da140e 별도검토. Docker/PG/CI/운영실행0. registry검토 문서와 fixture브랜치 전체 미착지는 구분한다.
