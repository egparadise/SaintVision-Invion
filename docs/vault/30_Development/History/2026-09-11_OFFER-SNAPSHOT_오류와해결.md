---
doc_id: "HIST-OFFER-SNAPSHOT-ERRORS-20260911"
title: "2026-09-11 OFFER-SNAPSHOT 오류와해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T23:56:33+09:00"
source_of_truth: "Git"
---

# 2026-09-11 OFFER-SNAPSHOT 오류와해결

## F1 실험 전제 오류

초기 계획은 release가 resource lock 없이 완료된다는 Claude 보고를 전제로 했다. 실제 API를 중단시킨 뒤 release를 동기로 부르면 RES-0007 Transaction contention으로 실패했다. 이는 제공량 1000/900 불일치가 아니다.

원인: release → _locked_lease → lock_resources 경로를 빠뜨린 전제. d14db0a와 현재 모두 같은 잠금이 존재한다. 기존 API·SQL을 바꾸지 않고 두 작업을 별도 thread로 실행하고 pg_blocking_pids로 대기 관계를 관찰하도록 시험을 수정했다. 기록량/적용량 1000/1000과 최종 lease 해제를 확인했다.

## 회귀가 보호 누락을 잡는지 검증

private worktree에서 그 잠금 호출 한 줄만 임시 제거한 변이는 exit 1, “Release bypassed the offer's resource locks”로 실패했다. finally에서 원본 bytes를 복구하고 git diff로 제품 변경 없음 확인 후 고정 SHA 시험 36개가 통과했다. 변이/초회 실패를 현재 제품 결함 수나 통과 수에 합치지 않는다.

## 외부 차단

같은 SHA GitHub CI 6개 모두 시작 전 계정 제한 annotation. local PostgreSQL 통과는 CI와 동등하지 않다. 운영자 계정 조치 후 같은 SHA 재실행이 필요하다. 전체 카드 done/main 병합/원격 인수로 표시하지 않는다.
