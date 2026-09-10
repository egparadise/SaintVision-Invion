---
doc_id: "RES-WORKSPACE-001"
title: "RES-WORKSPACE-001 새 승인 버전과 이전 checkpoint 복구 정합화"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T09:49:00+09:00"
source_of_truth: "Git"
---

# 새 승인 버전과 이전 checkpoint 복구 정합화

[[ERR-WORKSPACE-001 복구 승인 유일 제약과 체크포인트 attempt]]의 후속. migration 0018은 기존 approval ID·quorum·digest·immutable 이력을 유지하며 UNIQUE를 `(tenant_id,run_id,bound_run_version)`으로 바꾼다. 동일 version의 중복 승인은 차단하고 다음 recovery version은 별도 승인·nonce·dispatch로 처리한다. 과거 migration 원본은 수정하지 않는다.

새 checkout에는 `sourceAttempt`(재개 직전 attempt)와 `checkpointAttempt`(복원 원본 attempt)를 연결한다. 총 실행은 최초 포함 3 attempt까지, 새 lease/claim/queue는 원자 생성한다. 원본을 만든 attempt가 오래됐다는 이유로 최신 승인을 건너뛰거나 오래된 실행 권한을 되살리지 않는다.

새 경로를 실제 PostgreSQL/mTLS/Docker/Git으로 먼저 검증하도록 CI에 focused 시험을 배치했다. 전체 통합 시험·실제 성공 SHA 및 CI/증거는 최종 WORKSPACE-RESUME 검증보고에 기록한다. 이 해결 설계 문서만으로 교차 검토나 제품 인수가 완료된 것은 아니다.
