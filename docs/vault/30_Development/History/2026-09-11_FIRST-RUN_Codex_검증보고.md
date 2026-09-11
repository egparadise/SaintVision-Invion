---
doc_id: "HIST-FIRST-RUN-REPORT-20260911"
title: "FIRST-RUN Codex 검증보고"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-11T10:50:00+09:00"
source_of_truth: "Git"
---

# FIRST-RUN 검증보고

Task FIRST-RUN, owner Codex / reviewer Claude 대기. [[2026-09-11_FIRST-RUN_Codex_착수]]와 [[Codex Workspace 첫 실행과 승인 입력 계약]]을 따른다. 작업 중 시험으로 최초 실행 25개 + 기존 업무 연결 16개, 총 41개가 실제 Linux/PostgreSQL/Go/Docker에서 통과했다. Python core 260개와 Windows Go 전체 패키지 시험도 exit 0이다. 확정 SHA의 통합 결과와 전달 기록은 후속 기록한다.

실제 첫 Python/CPU 학습은 기존 실행 없이 draft에서 승인 후 attempt 1로 시작했다. 입력 준비 실패·승인 누락·등록 실패·중복 enqueue·실행 전/queue 후 취소·권한/자원/Node 변경·출력 저장 재개를 검사했다. 사용자/PKI는 독립 시험 fixture이며 현재 운영 계정 또는 다른 물리 PC로 실행한 결과가 아니다.

운영 IdP와 프로젝트/Workspace/mapping 생성은 Claude, 실제 API를 사용하는 화면과 지적 수정은 Gemini, 원격 profile 설치 후 실제 실행·복구와 GPU 경계 검증은 Codex의 다음 작업이다. main 병합 및 독립 검토는 수행하지 않았다. 오류 기록은 [[2026-09-11_FIRST-RUN_오류와해결]]이다.
