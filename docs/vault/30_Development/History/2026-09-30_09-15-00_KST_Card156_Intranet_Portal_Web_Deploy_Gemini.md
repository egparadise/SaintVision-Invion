---
doc_id: "HIST-GEMINI-CARD156-001"
title: "History: Card 156 사내망 portal 웹 배포 자산 및 비root read-only rootfs Nginx·안전 기동 검증"
version: "1.2.0"
status: "review"
author: "Gemini"
updated: "2026-09-30T09:42:00+09:00"
source_of_truth: "Git"
---

# History: Card 156 사내망 portal 웹 배포 자산 및 비root read-only rootfs Nginx·안전 기동 검증

## 1. 개요 및 배경

- **카드 번호**: Card 156 (Owner: Gemini, Reviewers: Claude, Codex)
- **작업 브랜치**: `agent/gemini/c156-intranet-portal-deploy` (Base: `origin/integration/all-agents-unified`, PR #247 최신 커밋 `2f93cbba` 병합)
- **배치 대상 도메인**: `portal.sv.lan`
- **배치 대상 노드**: 노드2 (object store 노드, Docker 지원)
- **독립 검토 의견 전수 조치 (Codex r1 7건 + Claude UI·운영 10건)**:
  1. **H1 (차단) `daemon off;` 중복 해소**:
     - `nginx.conf` 상단의 `daemon off;`를 제거하여 `Dockerfile`의 `CMD ["nginx", "-g", "daemon off;"]`와의 충돌을 원천 방지.
  2. **H5 (차단) 빌드 컨텍스트 `.dockerignore` 분리**:
     - 루트 `.dockerignore`가 Python 중심(`**` ignore)으로 구성되어 웹 빌드 자산 복사가 차단되는 문제 해소.
     - `deploy/intranet/portal/Dockerfile.dockerignore`를 추가하여 BuildKit 빌드 시 `apps/web/` 및 배포 설정이 온전히 포함되도록 화이트리스트 구성.
     - README에 `DOCKER_BUILDKIT=1 docker build -f deploy/intranet/portal/Dockerfile -t saintvision-portal:latest .` 정식 명령 명시.
  3. **H2 (인증서 기본 파일명 및 권한 보존)**:
     - #251 PKI 산출물 명세에 맞추어 기본 인증서 경로를 `server-chain.pem`(0600, leaf+intermediate) 및 `server-key.pem`(0400)으로 일치.
     - `portal-up.sh` 내부에서 운영자 파일 권한을 임의로 변경(`chmod`)하던 로직 완전 제거 (운영자 권한 0400/0600 엄격 보존).
     - 비root 컨테이너 접근은 `--user` 매핑 또는 전용 그룹(0440)을 통해 안전하게 해결.
  4. **M2 (로그 개인정보 및 토큰 보호)**:
     - `apps/web/nginx.conf` 표준과 동일하게 로그 포맷 `privacy`에서 `$request` 쿼리스트링과 `$http_referer`를 완전 제외 (`$request_method $uri $server_protocol`).
     - `/callback` 엔드포인트에 `access_log off;`를 지정하여 OAuth 일회용 인가 코드의 로그 누출을 원천 방지.
  5. **M3 (스테이징 사전 검증 및 안전 교체 패턴)**:
     - 기존 컨테이너를 먼저 삭제하지 않고, 임시 스테이징 컨테이너(`saintvision-portal-staging-$$`)를 먼저 백그라운드로 띄워 내부 `nginx -t` 및 HTTPS `/healthz` 프로브 통과를 확인.
     - 스테이징 검증 실패 시 기존 운영 컨테이너는 일체 건드리지 않고 즉시 중단 및 보존.
     - L4 이중 로드밸런서가 없는 단일 컨테이너 교체이므로 README의 '무중단' 서술을 '사전검증 안전 교체(near-zero downtime safe replacement)'로 정정.
  6. **M4 (주석 제외 토큰 기반 보안 검증기 및 면역 시험)**:
     - `tests/test_intranet_portal_deploy.py`의 `validate_portal_up_security` 검증기에 `strip_shell_comments`를 도입하여 스크립트 내 주석(`(-e forbidden)` 등)으로 인한 오탐을 원천 제거.
     - 원본 통과(positive control), 주석 면역 통과, 실제 플래그 주입/제거 시 변이 사살을 모두 엄격하게 단언.
  7. **M5 (스모크 완료 서술 정정)**:
     - 호스트 환경의 메모리 제약으로 로컬 컨테이너 런타임 실행이 미수행된 상태에서 '로컬 스모크 100% 완료'로 기재되었던 서술을 삭제 및 정정.
     - "정적 불변식 및 계약 변이 검증 100% 완료 (런타임 docker build/run/curl 검증은 노드2 실배포/CI 잡 단계에서 실측 예정)"로 정확히 명시.
  8. **L1 (Node 버전 통일)**:
     - `deploy/intranet/portal/Dockerfile` 빌더 스테이지에 `node:22-alpine` SHA256 digest를 고정하여 `apps/web/Dockerfile`과 일치.
  9. **L2 (CSP 강화)**:
     - `style-src`에서 `'unsafe-inline'`을 제거(`style-src 'self'`), `form-action 'self'` 추가.
  10. **L3 (누락 정적 자산 404 분기)**:
      - 알려진 정적 자산 확장자(`.js`, `.css`, `.png`, `.svg` 등)에 대한 정규식 location에 `try_files $uri =404;`를 적용하여 SPA fallback(`/index.html` 200 OK) 오동작 차단.
  11. **동일 Origin 리버스 프록시 토폴로지 (코디네이터 결정)**:
      - Nginx가 `/v1/`, SSE, 터미널 WebSocket을 업스트림 제어 평면(`https://control_plane`)으로 포워딩 (`proxy_ssl_verify on;`, `proxy_ssl_name cp.sv.lan;`).
      - CSP `connect-src`는 `'self'` 및 `https://idp.sv.lan`으로 엄격 한정.
      - `PORTAL_UPSTREAM_CP_HOST` 미설정 시 기동을 즉시 거부(fail-closed).
  12. **헤더 상속 무결성**:
      - [`security-headers.conf`](security-headers.conf) 스니펫을 선언하고 server 블록 및 모든 location 블록에 빠짐없이 include.
  13. **소유자 라벨 4-튜플 완전 결속**:
      - `service=portal`, `workload=intranet-portal`, `node=node2`, `instance=${PORTAL_INSTANCE:-main}`.

---

## 2. 세부 산출물 구조

```
deploy/intranet/portal/
├── Dockerfile                  # Multi-stage 비root Nginx 이미지 (node:22/nginx:1.27 sha256 고정)
├── Dockerfile.dockerignore      # 포털 빌드 전용 ignore (루트 python .dockerignore 오버라이드)
├── nginx.conf                  # 동일 origin 리버스 프록시 및 정적 서빙 설정
├── security-headers.conf       # HSTS/CSP/nosniff 공통 헤더 스니펫
├── conf.d/
│   └── upstream.conf           # 업스트림 제어 평면 정의 스니펫
├── auth-config.js              # 사내망 Keycloak IdP 연동 런타임 설정 (sv-portal)
├── portal-up.sh                # 운영 컨테이너 안전 기동/교체 스크립트 (스테이징 사전검증, 4-튜플 라벨, CA 검증)
├── portal-smoke-up.sh          # 로컬 개발/스모크 전용 기동 스크립트 (격리된 smoke 튜플)
├── portal-down.sh              # 운영 컨테이너 안전 정지 스크립트 (4-튜플 라벨 검증)
├── generate-dev-certs.sh       # 로컬 스모크용 임시 ECDSA P-256 인증서 생성기
└── README.md                   # 본 가이드
```

---

## 3. 정량 검증 결과

- **배포 정적 및 변이 사살 시험 (`pytest tests/test_intranet_portal_deploy.py`)**:
  - **23 passed 100% (0.10s)**:
    1. `test_security_headers_conf_invariants`: HSTS, strict CSP connect-src `'self'`/idp, style-src 'self' (no unsafe-inline), form-action 'self'.
    2. `test_nginx_conf_includes_security_headers_in_all_add_header_locations`: 전 location 헤더 상속 검증.
    3. `test_nginx_conf_reverse_proxy_topology`: /v1/, SSE buffering off, WS upgrade, upstream TLS 검증.
    4. `test_nginx_conf_privacy_logging`: 로그 포맷 query/referer 제외, /callback access_log off 검증.
    5. `test_nginx_conf_fixed_https_redirect_and_healthz`: 고정 domain 301 리다이렉트, /healthz 예외 검증.
    6. `test_nginx_conf_missing_static_files_404`: 누락 확장자 404 응답 검증 (L3).
    7. `test_nginx_conf_no_daemon_off`: nginx.conf 내 daemon off 부재 검증 (H1).
    8. `test_portal_up_sh_owner_label_4tuple`: 4-튜플 라벨 및 exited 한정 정리 검증.
    9. `test_portal_down_sh_owner_label_4tuple`: down 스크립트 4-튜플 검증.
    10. `test_portal_up_sh_production_ca_verification`: CA 체인, self-signed 거부, SAN, EKU, CA:FALSE 검증.
    11. `test_portal_up_sh_no_chmod_on_operator_keys`: operator 키 권한 chmod 부재 및 #251 기본 파일명 검증 (H2).
    12. `test_portal_up_sh_upstream_cp_fail_closed`: 업스트림 미설정 시 fail-closed 검증.
    13. `test_portal_up_sh_staging_preflight_and_safety`: 스테이징 컨테이너 기동, nginx -t 및 wget 프로브, 기존 컨테이너 중지 전 선행 검증 (M3).
    14. `test_portal_up_sh_no_secrets_in_docker_run`: docker run 내부 -e/--env 부재 검증.
    15. `test_portal_smoke_up_sh_isolation`: smoke 컨테이너/인스턴스/인증서 격리 검증.
    16. `test_dockerfile_pinned_image_digests`: base image SHA256 고정 및 node:22 일치 검증 (L1).
    17. `test_dockerfile_dockerignore_present_and_whitelisted`: Dockerfile.dockerignore 화이트리스트 검증 (H5).
    18. `test_positive_control`: 미변이 원본 파일의 validator 전원 통과 검증 (positive control).
    19. `test_positive_control_comment_immunity`: 주석 내 -e 키워드가 존재해도 검증기 통과 검증 (M4 면역).
    20. `test_mutation_loosening_csp_fails`: CSP 완화 시 validator 실패 검증 (변이 사살).
    21. `test_mutation_portal_up_security_flags_fail`: 보안 플래그 제거 및 환경변수 주입 시 validator 실패 검증 (변이 사살).
    22. `test_positive_control_owner_tuple`: 원본 소유자 튜플 검증기 통과 검증.
    23. `test_mutation_owner_tuple_guard_fails`: 소유자 튜플 검사 축소 시 validator 실패 검증 (변이 사살).
- **스크립트 구문 점검**: `bash -n` 4대 셸 스크립트 전원 문법 오류 0건 (exit 0).
- **TypeScript 타입 점검**: `npx tsc -b` 에러 **0건**.
- **프로덕션 번들 빌드**: `npm run build` 성공 (Vite bundle 7.82s).
- **프런트엔드 무결성 점검**: `python tools/check_frontend_integrity.py` 92개 파일 스캔, 9대 규칙 위반 **0건 (exit 0)**.
- **라우트 커버리지 점검**: `pytest tests/test_route_coverage.py` **40 passed (exit 0)**.
- **IP 주소 및 비밀 누출 점검**: 전 파일 대상 하드코딩 IP 주소 **0건**, 시크릿 유출 **0건**.

---

## 4. 인계 및 다음 단계

- **노드2 배포 상태**:
  - Leaf 인증서: 노드2 전달 완료 (`DELIVERED_NOT_ACTIVATED`).
  - 활성화 대기: `PORTAL_UPSTREAM_CP_HOST` 지정 후 `portal-up.sh` 기동 가능.
- **독립 검토 요청**: Claude (UI·테스트 축) 및 Codex (계약·보안 축) 재검토 요청.
