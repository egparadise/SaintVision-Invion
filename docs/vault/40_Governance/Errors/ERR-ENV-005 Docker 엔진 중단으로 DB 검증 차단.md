---
doc_id: "ERR-ENV-005"
title: "ERR-ENV-005 Docker 엔진 중단으로 DB 검증 차단"
version: "1.0.0"
status: "open"
author: "Claude"
updated: "2026-09-09T17:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# ERR-ENV-005 Docker 엔진 중단으로 DB 검증 차단

## 증상

S02 구현의 PostgreSQL 검증용 컨테이너를 띄우려다 Docker 엔진이 응답 불능이 되었다.

1. `docker run -p 55432:5432 pgvector/pgvector:pg16` → `driver failed programming external connectivity … (iptables failed: … fork/exec /usr/sbin/iptables: resource temporarily unavailable)`
2. 포트를 바꿔 재시도 → `Bad response from Docker engine`
3. 이후 모든 `docker` 명령이 같은 오류
4. Docker Desktop 재시작(사용자 승인) 후 → `open //./pipe/docker_engine: The system cannot find the file specified`
5. `wsl --list --verbose`가 출력 없이 무응답. `vmmemWSL`·`wslservice` 프로세스는 살아 있음

## 원인 추정

WSL2 VM 안에서 프로세스 fork가 실패(EAGAIN)했고, 이것이 Docker 엔진 백엔드 중단으로 이어졌다. Docker Desktop을 재시작해도 WSL이 응답하지 않아 Linux 엔진 named pipe가 생성되지 않는다. **VM 자원 고갈로 보이나 실측하지 않았으므로 `unknown`이다.**

## 영향

- S02 코드의 PostgreSQL 의존 테스트 43건 `not_run`. RLS 격리, NULLS NOT DISTINCT, partition 라우팅, 부트스트랩 토큰 재사용 차단은 **논증과 DDL 렌더링으로만 확인**했고 실제 엔진 검증은 하지 않았다.
- **사용자의 기존 컨테이너 5개(`saintview-ohif`, `saintview-orthanc`, `saintview-orthanc-h1`, `saintview-orthanc-h2`, `saintview-db`)가 현재 정지 상태다.** 재시작 전에는 실행 중이었고 5433 포트가 응답했다. Docker Desktop 재시작으로 함께 내려갔으며, 엔진이 올라오지 않아 복구되지 않았다.

재시작은 사용자 승인 아래 수행했으나, 결과적으로 다른 프로젝트 스택이 내려간 상태를 남겼다. 이는 기록해야 할 실제 영향이다.

## 시도한 것과 하지 않은 것

| 시도 | 결과 |
|---|---|
| 포트 변경 재시도 | 실패 |
| 정체된 `docker.exe` CLI 프로세스 종료 | 엔진 복구되지 않음 |
| Docker Desktop 프로세스 종료 후 재기동 | 프로세스는 새로 뜨나 엔진 pipe 미생성 |
| 약 4분간 대기·재확인 | 복구되지 않음 |

하지 않은 것: `wsl --shutdown`, `Restart-Service LxssManager`. 두 조치 모두 **사용자의 다른 WSL 작업 전체에 영향**을 주므로 임의로 실행하지 않았다.

## 해결 대기

복구 절차와 재발 방지는 사용자 확인 후 [[오류 해결 기록 템플릿]]으로 RES-ENV-005에 기록한다. 그 전까지 S02의 DB 검증 상태는 `not_run`이며, 문서 검사 통과를 DB 검증 성공으로 표시하지 않는다.

대안 경로: `.github/workflows/backend.yml`에 PostgreSQL 16 service를 정의해 두었으므로, push 시 GitHub Actions에서 43건이 실제로 실행된다. 로컬 복구 전에도 CI 증거는 얻을 수 있다.

관련: [[Claude 영역 구현 준비]], [[오류 및 해결 인덱스]]
