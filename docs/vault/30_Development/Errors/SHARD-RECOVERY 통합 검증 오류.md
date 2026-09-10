---
doc_id: "ERR-SHARD-RECOVERY-001"
title: "SHARD-RECOVERY 통합 검증 오류"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T13:05:06+09:00"
source_of_truth: "Git"
---

# SHARD-RECOVERY 통합 검증 오류

2026-09-10 12:49 KST, 초기 코드 `abf95491d4fb9fde88d4a2b97146956b6d93501c`, Core CI push `34434581798`, PR `34434584972`가 복구 전용 첫 시험에서 실패했다. 기존 Workspace 전용 20개는 통과했고 새 샤드 첫 시험은 1 failure였다. 전체 suite는 fail-fast로 실행되지 않았으므로 전체 합격으로 계산하지 않는다.

오류는 `inv.guard_shard_recovery()`의 source shard SQL 별칭 `old`가 PostgreSQL 트리거의 내장 `OLD` 레코드와 충돌한 `AmbiguousColumn`이다. migration 자체는 적용됐지만 실제 lineage INSERT에서 함수 본문을 실행할 때 드러났다. 실패 위치는 새 승인 소비·예약·claim·queue를 담은 바깥 트랜잭션 안이며 이 예외를 삼켜 성공 응답으로 바꾸지 않는다. raw 실패 artifact는 CI에 보존하고 이 문서에는 인증 정보가 포함될 수 있는 전체 traceback을 복제하지 않는다.

12:53 KST, `f31254608e7b663120f24ece894f0486fee35c30` PR Core CI `34434849182`는 경쟁하는 두 준비 계획의 Node 관측에서 응답 역전이 발생했다. 최신 heartbeat가 먼저 commit되면 이전 응답은 기존 보호 규칙에 따라 `NODE-0050 / 409`로 거부된다. 이 요청을 새 nonce로 다시 관측하는 제한된 재시도가 없었다. 전용 suite는 8건 중 7 pass/1 failure에서 종료했다. 같은 SHA push에서 전용 16개가 통과한 것만으로 이 경합을 해결됐다고 처리하지 않았다.

로컬 초기 `tools/check_docs.py`는 새 History front matter의 JSON 문자열 인용 및 필수 metadata 누락으로 exit 1이었다. metadata를 수정한 뒤 최초 코드 commit 이전에 재검사했다. 첫 Obsidian `--check`는 Gemini가 추가한 인덱스 2행을 외부 변경으로 감지해 exit 1, 쓰기 0이었다. 별도 source SHA와 원본 bytes/hash를 보존하고 Git의 두 보고서와 내용을 대조해 수용했다. 합격과 재검사 결과는 [[SHARD-RECOVERY 통합 검증 해결]] 및 최종 검증 보고서로 연결한다.

재검증: [[2026-09-10_13-05-06_KST_SHARD-RECOVERY_Codex_검증보고]], `3835b198884970840ce11ec92493bbadf60744b2`에서 전체 941 passed·새 샤드 전용 19개 passed, failure/error/skip 0. Core CI 34435221408 success, 오류 재현 기록과 수정 SHA를 함께 보존한다.
