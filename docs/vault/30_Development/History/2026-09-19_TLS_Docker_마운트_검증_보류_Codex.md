---
doc_id: "TLS-DOCKER-MOUNT-VALIDATION-20260919-CODEX"
title: "TLS 외부 주입 Docker 마운트 검증 보류"
version: "1.0.0"
status: "blocked"
author: "Codex"
updated: "2026-09-19T00:00:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
---

# TLS 외부 주입 Docker 마운트 검증 보류

## 실행 범위

- 별도 detached worktree에서 tracked 인증서 두 파일만 제거했다.
- 실행 직전 가용 메모리 약 1.9GB, Docker Server 20.10.22, Docker Compose v2.15.1을 확인했다.
- production Compose의 `up --no-start --no-deps web`는 frontend image build 단계에서 `TS2307: Cannot find module '../../../../../packages/contracts-ts/src'`로 exit 17이었다. 인증서 mount 생성 단계까지 도달하지 못했으므로 mount 판정으로 사용하지 않았다.
- 동일한 production TLS volume 정의만 둔 최소 nginx Compose를 별도로 실행했다. 인증서 파일이 없는 상태에서 `up --no-start web`가 exit 0으로 컨테이너를 만들었고, host의 두 경로에 `saintvision.crt`·`saintvision.key` 디렉터리가 생성됐다.
- 생성된 임시 컨테이너와 네트워크, 임시 디렉터리와 worktree는 제거했다. 원본 `deploy/certs`의 두 파일은 그대로 보존했다.

## 판정

현재 호스트의 Docker Compose v2.15.1에서는 `bind.create_host_path: false`가 실제 container create 경로에서 기대대로 fail-closed로 작동하지 않았다. 따라서 인증서 삭제 조건인 “부재 시 nonzero이며 host 디렉터리 미생성”을 충족하지 못했고, `git rm --cached`, 파일 삭제, `.gitignore` 추가를 수행하지 않았다.

다음 시도 조건은 (a) `create_host_path: false`를 실제로 존중하는 지원 Compose 버전을 준비하고 동일 최소 mount 시험을 exit nonzero·경로 미생성으로 통과시키거나, (b) Compose 실행 전 외부 인증서 파일을 fail-closed로 검사하는 배포 wrapper를 추가하고 그 경로를 검증하는 것이다. 조건 충족 전에는 삭제를 재시도하지 않는다.
