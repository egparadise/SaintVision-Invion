---
doc_id: "HIST-VF-PITR-BOUNDARY-001"
title: "PITR 설정 관측의 비밀출력과 인수 경계"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-18T10:20:12+09:00"
source_of_truth: "Git"
---

# PITR 설정 관측의 비밀출력과 인수 경계

- 사용자 모든과정자동진행 승인 지속. owner Codex/reviewer Claude, task VF-CX-01/05후속; basef00341e, branch agent/codex/vf-pitr-boundary. 공통판1.0.89/Codex/VF판 확인,agent-delivery/core-reliability 적용. 시작2026-09-18T10:20:12+09:00.
- Claude 신규4commit 8d207d6/521766c/1834ee3/afb2465 수신,각작성자보존 cherry-pick. shard finding철회수신. 모델ID/version 동일성이 권한·불변결속을 대신하지 않는 기존계약은 유지한다.
- 점검: archive_command 원문출력, 설정만으로 --require-pitr 성공, archive_library 미처리. 실제복구증거와 설정후보를 분리하고 출력비밀경계를 보강한다.
- 공식근거: https://www.postgresql.org/docs/16/continuous-archiving.html 및 runtime-config-wal.html. command/library 둘중하나 가능, 연속WAL+basebackup 필요, no-op명령은WAL연속성을파괴한다.

## 구현과 확인

- Claude 원본 대상 신규 회귀 4 failed/exit 1을 재현했다. 명령 원문 제거, archive_library 지원, known no-op 구분, 설정 관측과 복구 증거 분리, 환경변수 DSN 입력, 읽기전용/autocommit 격리로 수정했다.
- CLI 추가 시험에서 argparse가 --dsn을 --dsn-env로 축약 수용하는 문제를 확인하고 allow_abbrev=False로 정정했다. 최종 경계 시험 11 passed/exit 0.
- 명령: `VF_EVIDENCE_PREFIX=vf-pitr-boundary-final python tools/run_vf_security_tests.py tests/test_pitr_readiness.py tests/test_pitr_boundary.py tests/test_model_registry.py tests/test_deployment_guard.py`. Windows + 격리 PostgreSQL16, 40 passed/0 skipped/exit 0; 소유 컨테이너 제거. 서버 이미지 실행 시험은 포함하지 않는다.
- 운영 관측: `python tools/pitr_readiness.py --dsn-env INV_PITR_DSN --require-pitr --json`, exit 1(의도한 인수 차단). archive_mode off, command disabled, library unset, wal_level replica; pitrVerified false. 운영 설정 변경 없음.
- Evidence: `30_Development/Evidence/vf-pitr-boundary/`. 비밀 DSN·명령 원문·dump·private log는 게시하지 않는다.
- 모델 registry option A 방향과 안정 ID 시험은 수신했다. tenant/project/manifestHash/registryVersionId/content의 명시적 권한 결속은 구현된 것으로 인정하지 않는다.
- 다음 담당: Claude 수정본 독립검토; Codex 실제 PITR 증거/CI가 확보될 때 재검증. CI·독립검토·운영인수 미완료, 사용자 승인은 지속 유효.
