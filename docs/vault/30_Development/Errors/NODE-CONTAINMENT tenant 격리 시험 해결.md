---
doc_id: "FIX-NODE-CONTAINMENT-TENANT-001"
title: "NODE-CONTAINMENT tenant 격리 시험 해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T15:23:28+09:00"
source_of_truth: "Git"
---

# 두 격리 조건을 실제 DB fixture로 검증

[[NODE-CONTAINMENT tenant 격리 시험 오류]]를 `tests/integration/test_dispatch_queue.py`에서 수정했다. 미등록 UUID는 AUTH-0060 거부를 명시적으로 검증한다. RLS 조회에는 기존 실제 PostgreSQL fixture가 별도로 등록한 `env.other`를 사용해 다른 tenant의 execution delivery가 0개인지 확인한다. 이후 내용 변경·재실행·가짜 종료·worker token 교체·삭제를 거부하는 기존 불변성 검증은 유지한다.

제품의 tenant barrier나 RLS 정책은 바꾸지 않았다. 이 시험 수정이 포함된 새 SHA의 전체 CI를 실행하고 실제 통과 수치·CI ID·Evidence는 NODE-CONTAINMENT History 보고서와 PR17 인계에 기록한다. 초기 실패를 skip/제외하거나 기존 전용 시험 통과로 대체하지 않는다. owner Codex, reviewer Claude pending.
