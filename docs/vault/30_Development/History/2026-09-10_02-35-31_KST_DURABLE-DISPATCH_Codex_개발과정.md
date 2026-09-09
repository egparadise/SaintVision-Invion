---
doc_id: "DEV-DURABLE-DISPATCH-001"
title: "Codex durable dispatch와 중단 복구 개발 과정"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-10T02:35:31+09:00"
source_of_truth: "Git"
---

# Codex durable dispatch와 중단 복구 개발 과정

Task durable-dispatch / branch agent/codex/durable-dispatch / owner Codex / reviewer Claude(pending). base 7d657602d3f48122c20207cfff0919755e97f959, 기존 draft PR #6. GUIDE-001/GOV-AGENT-001/GOV-GIT-001/PLAN-BACKEND/DB/STORAGE v1.0.0, ADR-INDEX v1.6.0, CONTROL-INTEGRATION-CONTRACT-001 v1.0.1, agent-delivery/core-reliability Skill v1.0.0, baseline registry v1.0.0을 입력으로 한다. 사용자 일반 구현·검증·push/report 자동 진행 지시를 유지한다.

OUT-04/06/07 → claim/permit 저장 원자성·전송 전 crash·응답 유실·다중 worker·취소의 중복 실행 0 및 물리 반환 증거 → durable permit queue, 단 한 번 start 권한, 이후 observe/cancel 전용 복구 → migration/worker/CI. peer review와 실제 운영 구성은 미완료이며 baseline task done을 선언하지 않는다.

범위는 Codex 소유의 실행 전달 상태/동시성 kernel이다. 기존 Claude/Gemini worktree를 수정하지 않는다. 큐에는 서버가 생성한 signed permit만 저장하고 이를 공개 API나 SSE에 노출하지 않는다. private signing key를 큐/로그에 저장하지 않는다. 외부 네트워크 I/O는 DB transaction 밖에 둔다. 작업을 claim하는 transaction이 permit 저장과 함께 commit하지 못하면 양쪽 모두 rollback한다.

queued → uncertain → stopped만 허용하며 uncertain을 queued로 되돌리지 않는다. 최초 전송 직전 상태를 commit하고, worker 중단/응답 유실 뒤에는 observe/cancel만 수행한다. stop receipt가 없는 실패·expiry·unknown Node intent로 Lease를 반환하지 않는다. 취소는 활성 최초 전송을 기다리지 않는 control takeover를 지원한다. 업무 plan/사용자 approval request/UI/실제 IdP·5대 장비·SLO는 이 kernel로 대체하지 않는다.

## 2026-09-10T02:42:14+09:00 구현·로컬 검증

ToolGateway 원자 enqueue, migration 0007/DB guard/RLS, worker token·일회 execute·observe/cancel 복구, 명시적 worker CLI와 17개 신규 통합 시나리오를 작성했다. 로컬 초기 pytest는 147 passed/136 skipped/16 setup errors였으며 fixture import 누락을 수정했다. 신규 17개는 isolated DB 환경이 없어 skip(exit 0); 실제 DB/Go/Docker/CLI 결과는 CI로 확인한다. [[Codex 실행 전달 대기열과 중단 복구 계약]]과 ADR-INDEX v1.7.0을 기록했다.
