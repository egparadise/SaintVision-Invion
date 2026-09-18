---
doc_id: "TLS-DOCKER-MOUNT-REVALIDATION-20260919-CODEX"
title: "TLS 외부 주입 Docker 마운트 재검증"
version: "1.0.0"
status: "verified"
author: "Codex"
updated: "2026-09-19T00:00:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
---

# TLS 외부 주입 Docker 마운트 재검증

## 검증

- Compose v2.15.1에서 `create_host_path: false`가 무시되는 것을 확인한 뒤, `SAINTVISION_DEV_CERT_DIR`를 Compose interpolation 필수 변수로 변경했다.
- 환경변수 미설정 상태에서 `docker compose config --quiet`는 exit 15로 실패했고 host 인증서 경로를 만들지 않았다.
- 외부 인증서 디렉터리에 기존 개발 쌍을 복사하고 `SAINTVISION_DEV_CERT_DIR`를 설정한 최소 nginx Compose에서 `docker compose up --no-start web`는 exit 0이었다.
- `docker inspect`로 두 대상이 read-only bind mount임을 확인했다.
- 임시 컨테이너, 네트워크, 외부 복사본은 검증 직후 제거했다.

## 판정

Docker 버전과 무관하게 환경변수 미설정 직접 Compose 경로가 interpolation 단계에서 중단되고, 외부 파일이 있을 때만 mount가 생성된다. `create_host_path: false`는 지원 버전의 추가 방어로 남아 있지만 단독 보장으로 사용하지 않는다. 원본 `deploy/certs` 파일 삭제 조건은 충족됐다.
