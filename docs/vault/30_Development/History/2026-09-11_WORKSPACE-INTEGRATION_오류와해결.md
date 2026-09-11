---
doc_id: "ERR-WORKSPACE-INTEGRATION-20260911"
title: "Workspace 통합 오류와 해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T16:58:55+09:00"
source_of_truth: "Git"
---

# Workspace 통합 오류와 해결

WORKSPACE-INTEGRATION, Codex 작성, 독립 검토 pending. 최종 [[2026-09-11_WORKSPACE-INTEGRATION_Codex_검증보고]] 참조.

| 시각 KST | 재현 / 원인 | 조치와 확인 |
|---|---|---|
| 16:40 전후 | 최신 migration head 검사 1개가 0032에 고정되어 새 0033을 실패 처리 | 공개 parent 보존 assertion을 추가하고 최신 head로 수정. 기본 301개 통과 |
| 16:44 | 실제 PTY 조기 종료/웹소켓 거부. Go 단위는 invalid terminal result | Node wire registry에 CommandId/TerminalSpec/TerminalFrameInput/NodeTerminalInput/NodeTerminalResult가 없었다. 명시 등록 후 실제 3개 PTY 시험 통과 |
| 16:44 | immutable terminal ticket의 expires_at을 변경하는 시험이 DB trigger에 거부 | trigger를 약화하지 않고 실제 짧은 만료 JWT로 발급한 ticket을 기다려 검증 |
| 16:40–16:46 | PTY exec/start만 Docker v1.45 하드코딩 | 기존 apiVersion 협상 사용. API 1.41의 helper 실행과 실패 mutation 비재전송 시험 통과 |
| 16:49 | Go Linux 테스트 준비 도구가 read-only container에 docker cp 실패, 시험 없는 wire package에서 binary 부재 | 임시 시험 helper의 복사/실행 순서와 package 목록 수정. 앱 권한 변경 없음. Linux 42개와 실제 Docker 추가 시험 통과 |
| 16:54 | 두 번째 격리 시험 network 생성 실패; 오래된 빈 시험 network가 주소 pool을 차지 | labels/각 runner·DB 종료/PID 0/연결 0을 검증한 두 시험 network만 해제. 운영 network·컨테이너 보존 후 시험 재개 |
| 16:54 | 새 SHA GitHub workflow failure | job 시작 전 account payments/spending-limit annotation 확인. 계정 변경·우회·성공 표시 없이 정확한 CI 기록 유지 |

Git proposal 재요청에서 public scope 검사가 빠진 경로도 수정했다. 현재 public membership 제거 후 kernel grant가 살아 있는 실제 PostgreSQL 회귀에서 403을 확인한다. 실운영 데이터 변경으로 재현하지 않는다.

