---
doc_id: "ERR-WORKSPACE-001"
title: "ERR-WORKSPACE-001 복구 승인 유일 제약과 체크포인트 attempt"
version: "1.0.1"
status: "review"
author: "Codex"
updated: "2026-09-10T10:01:00+09:00"
source_of_truth: "Git"
---

# 복구 승인과 checkpoint attempt 정합성

WORKSPACE-RESUME, owner Codex, reviewer Claude pending. 첫 구현 `37c6e18`의 [Core CI 34422112701](https://github.com/egparadise/SaintVision-Invion/actions/runs/34422112701)는 831개 시험 중 5 failure, 0 error, 0 skipped였다. 새 복구 승인이 기존 `approval_requests_tenant_id_run_id_key`에 거절되었다. 기존 0002 migration의 Run당 승인 한 건 제약과 새로운 recovery approval 경로가 충돌했다. 이 SHA는 통합 합격이 아니다.

고정 시험은 실제 fresh approval·결과 복구·실패 admission/cancel·Node symlink/overflow 시나리오다. 모두 새 승인 INSERT에서 동일 UniqueViolation이 발생했으며 제품 성공을 기록하지 않았다. 오류 원문과 수정 경로는 [[RES-WORKSPACE-001 새 승인 버전과 이전 checkpoint 복구 정합화]]에서 연결한다.

추가 코드 검토에서 checkout의 source attempt를 항상 현재 RunAttempt와 같게 요구하면, 새 checkpoint 없이 중단된 재개 attempt가 이전 checkpoint를 사용할 수 없음을 확인했다. 실제 checkpoint 원본 attempt와 현재 recovery attempt를 별도 필드로 기록하도록 보완했다.

로컬 migration 시험 최초 호출은 packages/contracts-go 디렉터리에서 실행되어 대상 파일을 찾지 못했다. 올바른 worktree 루트에서 다시 실행하여 17개 통과·exit 0을 확인했다. 잘못된 명령은 검증 성공으로 집계하지 않는다.

## 최종 통합 중 관측 실패

`44e56ba`의 push [Core CI 34423220828](https://github.com/egparadise/SaintVision-Invion/actions/runs/34423220828)는 Workspace 11개 모두 통과, 전체 846개 중 845 passed/1 failure/0 error/0 skipped였다. `test_real_timeout_stops_before_resource_release`에서 cleanup의 최초 Docker Inspect가 실패해 `NODE-0027: execution uncertain`을 반환했다. 같은 SHA의 PR Core 34423223960은 통과했지만 실패 실행을 지우거나 합격으로 집계하지 않는다. 당시 로그가 하위 daemon 오류를 보존하지 않아 구체적인 transport timeout/일시적 absence 여부는 단정하지 않는다.

코드 검토 결과 cleanup의 4초 예산 안에서도 첫 일시적 읽기 실패에 즉시 중단하고 있었다. 이를 보완하는 관측 재시도는 [[RES-WORKSPACE-001 새 승인 버전과 이전 checkpoint 복구 정합화]]에 기록한다. 기존 실패는 정지 증거가 없어 자원을 반환하지 않은 안전한 보류이며, 미인가 재실행이나 잘못된 완료 증거가 발생했다는 뜻은 아니다.
