---
doc_id: "HIST-BUSINESS-WORKSPACE-ERROR-20260912"
title: "2026-09-12 BUSINESS-WORKSPACE Codex 오류해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T23:30:03+09:00"
source_of_truth: "Git"
---

# 실제 후보에서 확인한 연결 문제

1. 업무 factory는 INV_BUSINESS_DSN을 읽는데 Compose가 INV_DATABASE_URL만 전달했다. 실제 변수로 정정했다.
2. 시험 runtime에 connect_timeout이 있고 business URL에는 없어 동일 연결 대상 검사로 초기 business2개 기동 거부(6pass/2fail). 모든 비credential 연결 옵션을 일치시켰다. guard는 완화하지 않았다.
3. 업무 무토큰403/등록되지 않은 사용자401과 커널 무토큰401이 달랐다. 시험 기대값 조정 과정에서2차/3차 각각1pass/2fail을 확인했다. 실제 업무 무토큰을401로 정정하고401에 WWW-Authenticate: Bearer를 포함했다. 프로젝트 권한403은 유지한다.
4. Windows 호스트 파일 bind mount는 실제 Linux UID65532에서 fileUid0/mode0777로 관측돼 trusted_file이 거부(exit1)했다. 전용 Linux volume 준비 도구로 해결한다. 기존 volume은 덮어쓰지 않고 owner65532/file0600·현재신뢰·바이트hash를 검증한다.
5. Docker 재시작 후 임시 호스트 포트가 바뀌어 이전 URL을 검사하던 영속Workspace 시험이 실패했다. 재시작 후 실제 포트를 재조회한다. 작업 중 실행된 통합시험은6fail/14pass: 포트시험1개 및 실행 시작 후 변경된 Compose와 이미 로딩된 이전 요구변수 간 차이5개였다. 최종 commit에서 파일을 고정해 다시 검증한다. 이 중간 실행은 합격 증거로 사용하지 않는다.

수정 도구/배포 경계17개는 별도 통과했다. 공개 증거에 credential·개인키·토큰을 넣지 않으며, 합성 시험용 원본만 전용 임시 경로/volume에 사용했다. 운영 파일과DB는 미변경.
