---
doc_id: "ERR-REMOTE-WORKSPACE-20260911"
title: "REMOTE-WORKSPACE 오류와 해결"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T11:28:00+09:00"
source_of_truth: "Git"
---

# 원격 Workspace 배포 오류와 해결

- 실제 원격 PC는 mTLS 관측이 정상이지만 SSH/WinRM 포트가 닫혀 있다. 서버에서 직접 설치할 수 없어 검증된 전용 설치본을 제공했고 [[2026-09-11_REMOTE-WORKSPACE_다른PC설치안내]]의 한 번 실행 결과를 기다린다. 관측 성공을 설치/실행 성공으로 표시하지 않는다.
- 일부 계획·Docker 소스·worker 파일명을 추정해 read-only 조회가 실패했다. `rg --files`로 실제 경로를 확인해 읽었으며 파일 변경은 없었다.
- Docker 20.10의 자동 할당 subnet에서 self-test Node의 고정 IP 시작이 거절됐다. TLS 인증서의 SAN과 IP를 맞추기 위한 자체 시험 설정 문제다. 미실행 Created 상태와 전용 label을 확인한 해당 시험 컨테이너/비어 있는 network만 정리했다. 새 전용 network에서 확보한 subnet을 명시해 다시 생성하도록 수정했다. 실제 원격 Node나 기존 network는 변경하지 않았다.
- 큰 설치본 전송 시 전체 파일을 메모리에 적재하고 한 번의 socket write를 사용하던 bootstrap 응답을 256 KiB 단위 전송으로 바꿨다. WebClient로 실제 HTTP 다운로드한 111,708,260 byte의 SHA-256이 배포본과 일치했다. 기존 worker.zip·인증서 route를 보존하고 새 파일명만 추가했다.
- 사용자 또는 프로세스가 미완료 설치를 중단해도 이전 컨테이너 ID·phase를 개인 상태 경로에 남긴다. 실제 로컬 Docker에서 시작 실패를 주입하고 이전 컨테이너/키/journal 복원을 확인했다. 성공한 설치의 자동 구버전 downgrade는 새 journal 호환성을 보장할 수 없어 거부한다.
