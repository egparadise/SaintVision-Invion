---
doc_id: "ERR-MODEL-CHANNEL-CAS-001"
title: "원격 모델 시험의 channel CAS fixture 누락"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T12:48:07+09:00"
source_of_truth: "Git"
---

# 원격 모델 시험의 channel CAS fixture 누락

8c347b7의 tests/integration/test_model_remote_runtime.py는 DB DSN 부재로6건 모두skip이었고 integration착지를보류했다. 사용자 disposable PostgreSQL16에서 첫실행3passed/3failed: 채널 disable/인증서만료를 설정하는 UPDATE에 version 증가가 없어 기존 inv.channel_monotonic이 CheckViolation을 발생시켰다.

분류: 테스트 준비 결함. 실제DB에서 CAS제약이 작동한 것이며, 실패3건은 목표제품 보안단언에 도달하지 않았다. version=version+1을 함께 수정하는 정상 채널변경을 주입하도록 고쳤다. 운영 코드/migration/보안제약을 완화하지 않는다.

수정후 파일별실PG결과는 [[2026-09-18_원격모델권한결속_Codex]]에 연결한다. 최초실패는 Evidence/model-registry-binding/remote-authority-pg-initial.json에 보존한다. 작성자 Codex, 독립검토 Claude 대기.

수정 후 동일파일6passed/0failed/0skip(exit0), 사용자제공PG16에서확인. tests/integration/test_model_runtime.py도23passed/0skip. 실제채널변경이CAS제약을통과한뒤원격읽기중무커밋·승인후실행거부단언이검증됐다. 제품코드변경없이시험준비를수정한결과다. 독립검토는별도대기.
