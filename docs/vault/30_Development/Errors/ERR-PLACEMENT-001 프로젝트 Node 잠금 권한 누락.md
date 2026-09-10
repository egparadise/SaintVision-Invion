---
doc_id: "ERR-PLACEMENT-001"
title: "ERR-PLACEMENT-001 프로젝트 Node 잠금 권한 누락"
version: "1.0.0"
status: "resolved"
author: "Codex"
updated: "2026-09-10T04:01:17+09:00"
source_of_truth: "Git"
---

# ERR-PLACEMENT-001 프로젝트 Node 잠금 권한 누락

Task execution-recovery, owner Codex, reviewer Claude(대기). 구현 `d4ffcfb4683493889fe8ebadabb581f13bea234b`의 Core #34391576304/job #102600885613에서 pytest exit 1: 8 failed, 391 passed, skip 0. Documentation #34391576386 success. 2026-09-10 03:54:59 KST CI 로그를 확인했다.

실측 배치의 project_nodes membership 재검사는 `SELECT ... FOR SHARE`를 사용한다. 최소 권한 fixture role에서 해당 테이블 UPDATE 권한을 모두 회수했으므로 PostgreSQL이 `permission denied for table project_nodes`로 거절했다. 정상·미래/누락/폐기 관측·예약 경합·rollback 시험이 이 동일 경계에서 실패했다. 잠금을 제거하거나 Node membership 변경 권한을 넓혀 우회하지 않는다.

수정 [[RES-PLACEMENT-001 고정 sentinel 권한과 변경 차단 검증]]. 실패 결과를 성공 증거에 합산하지 않는다.

수정 SHA의 [Core #34392036680](https://github.com/egparadise/SaintVision-Invion/actions/runs/34392036680) 및 [Docs #34392036686](https://github.com/egparadise/SaintVision-Invion/actions/runs/34392036686) success. Python 400개, 실패·오류·skip 0. 실제 artifact #10120154499 확인 2026-09-10T04:01:12+09:00. 상세 [[2026-09-10_04-01-17_KST_EXECUTION-RECOVERY_Codex_검증보고]]. 코드 독립 검토는 대기다.
