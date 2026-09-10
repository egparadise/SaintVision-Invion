---
doc_id: "ERR-BUSINESS-KERNEL-001"
title: "BUSINESS-KERNEL 통합 검증 오류"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T13:50:00+09:00"
source_of_truth: "Git"
---

# BUSINESS-KERNEL 오류 기록

task BUSINESS-KERNEL / owner Codex / reviewer Claude pending. 해결과 최종 재검증은 [[BUSINESS-KERNEL 통합 검증 해결]] 및 History 보고서에서 확인한다.

1. 로컬 `pytest tests/core tests/test_migrations.py`에서 기존 최신 head·downgrade 기대값이 0020에 고정돼 새 0021과 불일치했다. 첫 결과 217 passed/1 failed, 기대값을 하나 수정한 다음 좁힌 시험 22 passed/1 failed였다. 두 기대값과 합류 제거 fixture를 새 graph에 맞추되 원래 0008/0007 부모 이력 검사·cycle 거부는 유지했다. 이후 해당 23개 통과, TLS 추가 검사를 포함한 51개도 통과했다. SQLite나 skip으로 PostgreSQL 시험을 대체하지 않았다.

2. `d010392bf6edb6562cd3b72fcf67785f07c60db5`, Core push [34438155178](https://github.com/egparadise/SaintVision-Invion/actions/runs/34438155178), 2026-09-10 13:45 KST: 업무 전용 시험 15개 중 14 passed/1 failed. 큐 등록 뒤 requester 업무 membership를 철회한 시험에서 worker가 stopped 대신 uncertain을 반환했다. `_can_start`는 권한 철회를 올바르게 거부했지만, 아직 전송하지 않은 queued 명령을 observe로만 바꾸므로 Node에 없는 명령을 계속 관찰하고 Lease/편집 lock을 유지하는 경로가 남았다. 이 CI에서 전체 회귀 완료를 주장하지 않는다.

3. `a6397540ee301bbde1218e7f283fb93c34e266f7`, Core PR [34438044184](https://github.com/egparadise/SaintVision-Invion/actions/runs/34438044184), 2026-09-10 13:43 KST: 경쟁 복구 계획 시험의 mTLS heartbeat 응답이 비200으로 거부돼 NODE-0030이 발생했다. 기존 오류는 HTTP 응답 코드를 보존하지 않으므로 이 로그만으로 429라고 확정하지 않는다. 코드 검토에서 Node control slot 1개의 동시 429 응답이 관측 재시도와 구분되지 않는 점을 확인했다. 정상 인증 후 429를 반환하는 실제 TLS 시험을 추가해 그 경로를 재현했다. 기존 command 실행에 자동 재전송을 추가하는 방식으로 해결하지 않는다.

로컬 `docker info`는 daemon 정보가 없어 exit 1이었다. Linux 제품 시험은 CI에서만 실행했다. 변경된 코드로 대체된 일부 이전 SHA의 실행 중 CI는 명시적으로 취소했으며, cancellation을 시험 성공으로 계산하지 않는다. 로그의 합성 DB 접속 문자열이나 인증 material은 이 문서에 복사하지 않는다.
