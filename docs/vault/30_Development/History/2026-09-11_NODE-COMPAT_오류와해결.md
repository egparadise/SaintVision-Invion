---
doc_id: "ERR-NODE-COMPAT-20260911"
title: "NODE-COMPAT 오류와 해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T09:28:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["error", "node", "recovery"]
---

# NODE-COMPAT 오류와 해결

| 실제 현상 | 원인과 처리 | 결과 |
|---|---|---|
| 재부팅 후 3000/18082/18100 listener 없음 | 서비스가 대화 세션에서만 시작되었음. 기존 DB를 보존해 재시작하고 현재 Windows 사용자 로그인 Startup shortcut 등록 | 현재 서비스 정상, 실제 다음 재부팅 시험은 미실시 |
| Node API 1.45와 서버 최대 1.41 불일치 | Linux daemon 최소/최대 버전 안에서 1.41~1.45 협상, 격리 설정 생략 금지 | 실제 API 1.41에서 정상/출력/실패/timeout 통과 |
| 구형 local log driver 설정 호환성 | bounded json-file 512 KiB/1개로 변경, create 후 readback 확인 | 정상 출력과 실제 SHA-256 검증 통과 |
| PowerShell의 dotted Go test 인자 전달이 `-test`로 분리됨, exit 2 | 테스트 실행 전에 실패. Python subprocess argv 배열로 전달하는 `tools/check_node_docker_compat.py` 추가 | 실제 Linux 시험 실행됨 |
| 첫 실제 시험에서 fail/sleep 출력 존재 단언 실패, exit 1 | 기존 계약은 정상 종료만 output commitment 수집. 시험의 기대가 계약과 달랐음 | 실패 영수증/물리 종료/재실행 금지를 확인하도록 시험 수정. 정상 stdout/stderr 시험 추가 |
| 최초 코드 조회 경로 일부 오기 | `internal/runtime` 대신 실제 `runtime`, workdir에 중복 prefix 사용 | `rg --files`/실제 경로로 재조회, 데이터 수정 없음 |
| 다른 PC SSH 22 timeout | 원격 관리 셸 접근 경로 없음. mTLS 관측은 별도로 정상 | 사용자에게 해당 PC의 제한 실행 시험 설치 스크립트 인계. 설치 결과 대기 |

실패한 시험 컨테이너와 로그는 보존했다. 실제 업무 DB/인증서/Node identity/epoch를 초기화하거나 다른 업무 컨테이너를 정지하지 않았다. [[2026-09-11_NODE-COMPAT_Codex_검증보고]]에서 합격 증거와 미완료 범위를 구분한다.
