---
doc_id: "FIX-SHARD-RECOVERY-001"
title: "SHARD-RECOVERY 통합 검증 해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T13:05:06+09:00"
source_of_truth: "Git"
---

# SHARD-RECOVERY 통합 검증 해결

최종 보고서 commit의 Go 취소 시험 실패를 추가로 수정했다. fake engine의 실제 Start 직후 callback에서 cancel을 호출한다. `ProcessStarted=true`, start/stop/remove 각각 1회, 취소 reason과 receipt 조건을 유지·강화했다. 고정 100ms 타이머는 제거했으며 production Runner는 변경하지 않았다. Windows에서는 Linux 대상 test binary를 교차 컴파일하고 실제 Go race 실행은 최종 CI로 확인한다. 이 검증 코드 보완을 포함한 최종 SHA/CI/artifact는 PR #15에 기록한다.

[[SHARD-RECOVERY 통합 검증 오류]]의 SQL 문제는 `f312546`에서 별칭을 `source_member`로 바꿔 수정했다. 동시에 target plan의 shard_count 일치와 현재 epoch의 새 running 부모를 DB trigger에서 확인했다. 미배포 draft의 새 migration 0020만 정정했고 기존 0019 이하 history는 그대로 유지했다. 새 SHA의 실제 복구·전체 CI가 통과하기 전에는 해결 검증을 완료했다고 쓰지 않는다.

동시 관측 경합은 `3835b198884970840ce11ec92493bbadf60744b2`에서 수정했다. `Out-of-order heartbeat`만 retryable 409로 구분하며 제한 runtime에서 새 nonce로 총 3회까지만 관측한다. 늦은 응답을 수용하는 방향으로 검증을 약화하지 않았다. 실제 mTLS 응답 사이에 새 관측을 먼저 commit하는 결정론적 시험 2건(한 번 역전 뒤 성공·3회 상한)과 다른 epoch 응답 403의 재시도 금지 1건을 추가해 전용 시험은 총 19개다. 실제 실행 세대 상한 3과 관측 재시도 3은 별개의 제한이다.

문서 front matter 수정 뒤 `tools/check_docs.py`와 `tools/check_ontology.py`는 exit 0이었다. 로컬 핵심 테스트 198개가 실행됐다. Obsidian의 추가 보고서는 Git `92c43b1d4e9338216367285f2d43d9f36cbcda7f`와 대조하여 그대로 보존했다. `Evidence/shard-recovery-sync-proposals.json`에 외부 index 원본 base64·hash·출처를 기록했다. 해당 보고의 UI/배포 합격 주장은 Gemini 작성자 보고이며 이번 Codex 실행 시험이나 독립 인수 결과에 포함하지 않는다. 수용 뒤 sync check는 248개 파일, pending 10, conflict 0이었고 실제 최종 apply는 검증 보고서에 기록한다.

재검증: [[2026-09-10_13-05-06_KST_SHARD-RECOVERY_Codex_검증보고]], `3835b198884970840ce11ec92493bbadf60744b2`에서 전체 941 passed·새 샤드 전용 19개 passed, failure/error/skip 0. Core CI 34435221408 success, 오류 재현 기록과 수정 SHA를 함께 보존한다.
