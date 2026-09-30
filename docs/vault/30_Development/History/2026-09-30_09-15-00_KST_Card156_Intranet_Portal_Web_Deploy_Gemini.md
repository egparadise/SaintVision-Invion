---
doc_id: "HIST-GEMINI-CARD156-001"
title: "History: Card 156 사내망 portal 웹 배포 자산 및 비root read-only rootfs Nginx·안전 기동 검증"
version: "1.0.0"
status: "review"
author: "Gemini"
updated: "2026-09-30T09:15:00+09:00"
source_of_truth: "Git"
---

# History: Card 156 사내망 portal 웹 배포 자산 및 비root read-only rootfs Nginx·안전 기동 검증

## 1. 개요 및 배경

- **카드 번호**: Card 156 (Owner: Gemini, Reviewers: Claude, Codex)
- **작업 브랜치**: `agent/gemini/c156-intranet-portal-deploy` (Base: `origin/integration/all-agents-unified`, PR #247 최신 커밋 `2f93cbba` 병합)
- **배치 대상 도메인**: `portal.sv.lan`
- **배치 대상 노드**: 노드2 (object store 노드, Docker 지원)
- **목적**:
  1. `apps/web` 정적 빌드 산출물을 고신뢰·비root 환경에서 안전하게 서빙하는 배포 디렉터리(`deploy/intranet/portal/`) 구축.
  2. Nginx 설정(`nginx.conf`): 비root 실행(UID:GID 101:101), 읽기 전용 루트 파일시스템(`--read-only`), HTTPS 전용(HTTP 80 $\rightarrow$ HTTPS 443 301 리다이렉트), TLS 1.2+ 한정, HSTS(1년), 엄격한 CSP(`connect-src`는 `https://idp.sv.lan`과 `https://cp.sv.lan`만 허용), SPA fallback, `/auth-config.js` 노캐시.
  3. 런타임 OIDC 설정(`auth-config.js`): `https://idp.sv.lan/realms/saintvision` 및 `sv-portal` 클라이언트.
  4. 다단계 빌드 컨테이너 명세(`Dockerfile`): 비root Nginx 이미지, 정적 자산 번들링, 파일 권한 최소화.
  5. 컨테이너 수명 주기 스크립트(`portal-up.sh`, `portal-down.sh`):
     - 소유자 라벨(`ai.saintvision.service=portal`) 일치 컨테이너만 안전하게 교체·정리 (타 서비스 보호).
     - 비밀의 argv 및 환경변수(`-e`/`--env`) 주입 엄격 차단.
     - TLS 인증서 및 비밀키를 단일 파일 읽기 전용 바인드 마운트(`readonly`)로 격리.
     - 컨테이너 보안 강화: `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`, `--tmpfs`.
  6. 정적 검증 및 변이(Reversibility) 시험 스위트(`tests/test_intranet_portal_deploy.py`, 19 passed) 신설.
  7. **원격 물리 배포 상태**: Card 150(Codex)의 `portal.sv.lan` ECDSA P-256 정식 Leaf 인증서 발급·전달 대기로 원격 물리 배포는 `BLOCKED` 표기, 설정·컨테이너·시험·로컬 스모크 검증은 100% 완료.

---

## 2. 세부 구현 내역

### 1) 보안 강화 Nginx 설정 (`deploy/intranet/portal/nginx.conf`)
- **비root 및 Read-Only Rootfs 환경**:
  - `pid /tmp/nginx.pid;`로 설정하여 비root 사용자가 `/var/run` 쓰기 권한 없이도 기동 가능.
  - `client_body_temp_path`, `proxy_temp_path`, `fastcgi_temp_path`, `uwsgi_temp_path`, `scgi_temp_path`를 모두 `/tmp` 하위로 지정하여 컨테이너 루트 파일시스템이 읽기 전용(`--read-only`)이어도 문제없이 작동.
- **HTTPS Only 및 HTTP 301 리다이렉트**:
  - 포트 80 서버 블록에서 `server_name portal.sv.lan;` 명시 및 `return 301 https://$host$request_uri;` 강제.
  - 포트 443 서버 블록에서 `listen 443 ssl;` 명시.
- **TLS 1.2+ 한정 및 순방향 비밀성 암호군**:
  - `ssl_protocols TLSv1.2 TLSv1.3;` (SSLv2, SSLv3, TLS 1.0, TLS 1.1 차단).
  - `ssl_prefer_server_ciphers on;` 및 ECDHE 계열 최신 GCM/ChaCha20 암호군 한정.
- **보안 헤더 및 엄격한 CSP**:
  - HSTS: `Strict-Transport-Security "max-age=31536000; includeSubDomains" always;` (1년 보장).
  - CSP: `connect-src https://idp.sv.lan https://cp.sv.lan;`로 한정하여 비암호화 HTTP 및 승인되지 않은 외부 출처 통신 차단.
  - `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`.
- **SPA Fallback 및 캐시 무결성**:
  - `location / { try_files $uri $uri/ /index.html; }`
  - `/auth-config.js` 및 `/index.html`: `Cache-Control "no-cache, no-store, must-revalidate"`로 설정하여 배포 변경 시 브라우저 캐시 오염 방지.
  - `/assets/`: `Cache-Control "public, immutable"` 및 1년 캐싱 (Vite content-hash 자산).

### 2) 런타임 OIDC 설정 (`deploy/intranet/portal/auth-config.js`)
- `apps/web/public/auth-config.js` 계약에 맞추어 사내망 Keycloak IdP 연동:
  - `issuer: 'https://idp.sv.lan/realms/saintvision'`
  - `clientId: 'sv-portal'`
  - `scope: 'openid inv.api'`
  - `redirectUri: 'https://portal.sv.lan/callback'`

### 3) Multi-stage 비root 컨테이너 명세 (`deploy/intranet/portal/Dockerfile`)
- Stage 1 (`node:20-alpine`): `apps/web` 의존성 설치 및 프로덕션 번들 빌드 (`npm run build`).
- Stage 2 (`nginx:1.27-alpine`):
  - 비root 사용자(UID:GID `101:101`, `nginx:nginx`)로 전환.
  - `/tmp`, `/var/cache/nginx`, `/var/run` 디렉터리 권한 사전 구성.
  - 정적 자산 권한을 읽기 전용(`550`)으로 설정.
  - 표준 소유자 라벨 부여:
    - `LABEL ai.saintvision.service="portal"`
    - `LABEL ai.saintvision.role="web-portal"`
    - `LABEL ai.saintvision.node="node2"`
    - `LABEL ai.saintvision.workload="intranet-portal"`

### 4) 안전 기동 스크립트 (`deploy/intranet/portal/portal-up.sh`)
- **소유자 라벨 격리**:
  - `OWNER_LABEL="ai.saintvision.service=portal"`
  - 대상 컨테이너가 존재할 경우 라벨을 검사하여 동일 소유자 라벨일 때만 안전하게 교체하고, 타 컨테이너는 절대 수정/삭제하지 않고 오류 종료.
  - 노드 내 잔존하는 동일 라벨의 유휴 컨테이너만 필터링하여 정리.
- **비밀 argv 및 환경변수 주입 차단**:
  - 스크립트 실행 인자(`$@`)에 패스워드, 토큰, 비밀키 키워드 및 `-e`/`--env` 플래그 유입 시 즉각 거부.
  - `docker run` 실행 시 `-e` 플래그 0건 보장.
- **단일 파일 읽기 전용 TLS 마운트**:
  - 인증서와 비밀키를 디렉터리가 아닌 단일 파일 바인드 마운트(`readonly`)로 격리:
    - `--mount "type=bind,source=${CERT_FILE_ABS},target=/etc/nginx/certs/portal.crt,readonly"`
    - `--mount "type=bind,source=${KEY_FILE_ABS},target=/etc/nginx/certs/portal.key,readonly"`
  - 실행 전 인증서와 비밀키의 공개키 SHA-256 해시 일치성을 사전 검증.
- **컨테이너 보안 프로파일**:
  - `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`, `--user 101:101`, `--tmpfs` mounts.

### 5) 안전 정지 스크립트 (`deploy/intranet/portal/portal-down.sh`)
- `ai.saintvision.service=portal` 소유자 라벨을 검증한 뒤 포털 컨테이너를 안전하게 정지 및 삭제.

### 6) 로컬 스모크 인증서 생성기 (`deploy/intranet/portal/generate-dev-certs.sh`)
- 사내 PKI CA의 정식 인증서 전달 전 로컬 스모크 테스트 및 오프라인 검증을 위해 임시 ECDSA P-256 (`prime256v1`) 자체 서명 인증서(`SAN: DNS:portal.sv.lan`)를 생성.
- `LOCAL SMOKE TEST ONLY` 명시.

---

## 3. 검증 결과

### 1) 단위 및 정적 검증 시험 (`tests/test_intranet_portal_deploy.py`)
- **19 passed (100%)**:
  1. `test_nginx_conf_exists_and_non_empty`: 설정 파일 실재 및 크기 검증.
  2. `test_nginx_conf_non_root_and_readonly_rootfs`: PID `/tmp/nginx.pid` 및 5대 temp 경로 `/tmp` 검증.
  3. `test_nginx_conf_https_only_and_redirect`: 포트 80 $\rightarrow$ 443 301 리다이렉트 및 포트 443 ssl 검증.
  4. `test_nginx_conf_tls_protocols_and_ciphers`: TLS 1.2/1.3 필수, SSLv2/SSLv3/TLS1.0/TLS1.1 차단, ECDHE 암호군 검증.
  5. `test_nginx_conf_hsts_header`: HSTS 헤더 존재, max-age >= 31536000, includeSubDomains 검증.
  6. `test_nginx_conf_csp_connect_src_strict`: CSP connect-src가 오직 `https://idp.sv.lan`과 `https://cp.sv.lan`만 허용함을 검증.
  7. `test_nginx_conf_spa_fallback_and_cache_control`: SPA try_files, /auth-config.js 및 /index.html no-cache, /assets/ immutable 검증.
  8. `test_portal_auth_config_js_contract`: OIDC issuer 및 clientId 계약 검증.
  9. `test_dockerfile_hardened_profile`: multi-stage, USER 101:101, 소유자 라벨 3종 검증.
  10. `test_portal_up_sh_exists_and_executable`: 실행 권한 및 strict bash 옵션 검증.
  11. `test_portal_up_owner_label_filter_only`: 소유자 라벨 컨테이너 한정 교체 검증.
  12. `test_portal_up_no_secrets_in_argv_or_env`: 비밀 argv 및 -e 플래그 부재 검증.
  13. `test_portal_up_tls_key_single_file_readonly_mount`: 키/인증서 해시 검증 및 단일 파일 readonly 바인드 마운트 검증.
  14. `test_portal_up_read_only_rootfs_and_capabilities`: --read-only, --cap-drop ALL, --security-opt, --tmpfs 검증.
  15. `test_portal_down_sh_owner_label`: 소유자 라벨 기반 컨테이너 정지 검증.
  16. `test_mutation_loosening_csp_fails`: CSP 완화(외부 도메인, HTTP, idp/cp 누락) 시 즉시 실패 (변이 사살).
  17. `test_mutation_removing_hsts_fails`: HSTS 누락 및 유효기간 축소 시 즉시 실패 (변이 사살).
  18. `test_mutation_enabling_legacy_tls_fails`: TLS 1.0/1.1 허용 시 즉시 실패 (변이 사살).
  19. `test_mutation_portal_up_security_flags_fail`: 보안 플래그 제거 및 환경변수 주입 시 즉시 실패 (변이 사살).

### 2) 웹 프런트엔드 빌드 및 무결성 검증
- `apps/web` TypeScript 점검: `npx tsc -b` 타입 에러 **0건**.
- `apps/web` 프로덕션 빌드: `npm run build` 성공 (Vite bundle 7.82s).
- 프런트엔드 무결성 점검: `python tools/check_frontend_integrity.py` 92개 파일 스캔, 9대 규칙 위반 **0건 (exit 0)**.
- 라우트 커버리지 점검: `pytest tests/test_route_coverage.py` **40 passed (exit 0)**.

---

## 4. 인계 및 다음 단계

- **원격 노드2 배포 상태**:
  - Card 150(Codex tab)의 `portal.sv.lan` ECDSA P-256 Leaf 인증서 발급 대기로 인해 원격 물리 배포는 **`BLOCKED`**로 표기.
  - 인증서 파일이 노드2에 배치되면 `portal-up.sh`를 즉시 실행하여 운영 개시 가능.
- **독립 검토 요청**:
  - Claude (UI·테스트 축) 및 Codex (계약·보안 축) 검토 요청.
