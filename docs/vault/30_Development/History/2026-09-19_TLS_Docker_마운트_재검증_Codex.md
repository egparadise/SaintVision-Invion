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

잔여 조건도 명시한다. 환경변수가 설정됐지만 파일이 없는 경로는 Compose v2.15에서 디렉터리로 바뀔 수 있으므로, `deploy_intranet.ps1` preflight를 통하지 않은 직접 Compose 실행은 사용하지 않는다. 기본 `./deploy/certs` 폴백은 제거됐고, 환경변수 미설정은 이제 의도적으로 실패한다.

## 후속 상태 정정

위 내용은 `7c804ed` 시점의 설정을 기록한 역사 스냅샷이다. 후속 커밋 `02ed2ee`는 `deploy_intranet.ps1`의 미설정 폴백을 `deploy/certs`로 복구하고, 결정된 `certDir`를 `SAINTVISION_DEV_CERT_DIR`로 Compose에 전달했다. 현재 코드는 미설정 시 폴백이 있으며, 환경변수를 필수로 보는 직접 Compose 계약과 스크립트 경로를 구분해야 한다. 02ed2ee 재검증은 사용자 독립 실행으로 확인됐고, 이 문서의 과거 문구를 현재 동작 설명으로 인용하지 않는다.
