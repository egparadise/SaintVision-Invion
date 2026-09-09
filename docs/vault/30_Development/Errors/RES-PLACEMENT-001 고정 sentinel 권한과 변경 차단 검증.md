---
doc_id: "RES-PLACEMENT-001"
title: "RES-PLACEMENT-001 고정 sentinel 권한과 변경 차단 검증"
version: "1.0.0"
status: "resolved"
author: "Codex"
updated: "2026-09-10T04:01:17+09:00"
source_of_truth: "Git"
---

# RES-PLACEMENT-001 고정 sentinel 권한과 변경 차단 검증

[[ERR-PLACEMENT-001 프로젝트 Node 잠금 권한 누락]]의 수정이다. owner Codex / reviewer Claude(대기). 수정 SHA `ee7132cd8e59d264bd81e1cb3d3d96e81f56d63e`.

test runtime role에 기존 project_grants와 같은 방식의 `UPDATE(lock_sentinel)`만 추가했다. Node membership의 enabled/identity 수정이나 INSERT/DELETE는 계속 거절한다. 새 회귀 시험은 실제 예약 성공 뒤 enabled 변경·삭제가 permission denied이고, sentinel=false가 CHECK로 거절되는지 검사한다. 배포 role의 동일 설정 요구도 [[Codex 결과 확정과 Workspace 복구 및 배치 계약]]에 명시했다.

로컬 pytest exit 0, 171 passed/229 skipped. Linux DB 전체 재검증은 위 수정 SHA의 CI와 최종 History에서 확인한다. 로컬 skip을 합격으로 세지 않는다.

수정 SHA의 [Core #34392036680](https://github.com/egparadise/SaintVision-Invion/actions/runs/34392036680) 및 [Docs #34392036686](https://github.com/egparadise/SaintVision-Invion/actions/runs/34392036686) success. Python 400개, 실패·오류·skip 0. 실제 artifact #10120154499 확인 2026-09-10T04:01:12+09:00. 상세 [[2026-09-10_04-01-17_KST_EXECUTION-RECOVERY_Codex_검증보고]]. 코드 독립 검토는 대기다.
