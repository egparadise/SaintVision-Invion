---
doc_id: "ERR-WORKSPACE-001"
title: "ERR-WORKSPACE-001 복구 승인 유일 제약과 체크포인트 attempt"
version: "1.0.2"
status: "review"
author: "Codex"
updated: "2026-09-10T10:28:30+09:00"
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

## HTTP 응답 종료와 영수증 조회의 시험 경합

`46abc78`의 push [Core CI 34424895888](https://github.com/egparadise/SaintVision-Invion/actions/runs/34424895888)는 Workspace 11개 통과, 전체 846개 중 845 passed/1 failure/0 error/0 skipped였다. 네트워크 timeout 시험에서 실제 취소/정지 영수증이 생긴 직후 `/v1/executions/receipts` 조회가 non-200을 받아 실패했다. PR Core 34424899432는 같은 SHA에서 통과했다.

코드의 영수증 journal 저장은 원래 HTTP handler의 응답 완료·slot 반환보다 먼저 일어난다. 응답을 의도적으로 멈추는 결정론적 Go 시험으로 이 구간의 조회가 429로 거부되고, 원래 handler가 끝난 뒤 조회가 runner에 전달됨을 확인했다. 실패 CI가 실제 반환한 HTTP status 숫자는 기존 client 진단에 없어 그 실행의 정확한 상태를 단정하지 않는다. 다만 journal 파일 존재만으로 HTTP 조회가 즉시 가능하다고 본 시험의 가정은 잘못되었다. 실패 시 자원이 반환되거나 작업을 재실행하지는 않았다.
