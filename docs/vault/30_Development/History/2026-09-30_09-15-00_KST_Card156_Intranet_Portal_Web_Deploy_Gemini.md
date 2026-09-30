---
doc_id: "HIST-GEMINI-CARD156-001"
title: "History: Card 156 사내망 portal 웹 배포 자산 및 비root read-only rootfs Nginx·안전 기동 검증"
version: "1.3.0"
status: "review"
author: "Gemini"
updated: "2026-09-30T10:05:00+09:00"
source_of_truth: "Git"
---

# History: Card 156 사내망 portal 웹 배포 자산 및 비root read-only rootfs Nginx·안전 기동 검증

## 1. 개요 및 배경

- **카드 번호**: Card 156 (Owner: Gemini, Reviewers: Claude, Codex)
- **작업 브랜치**: `agent/gemini/c156-intranet-portal-deploy` (Base: `origin/integration/all-agents-unified`, PR #247 최신 커밋 `2f93cbba` 병합)
- **배치 대상 도메인**: `portal.sv.lan`
- **배치 대상 노드**: 노드2 (object store 노드, Docker 지원)
- **독립 검토 r2 및 코디네이터 지침 전수 조치 (Codex '수정 요청 유지' + Claude r2 '변경 요청')**:
  1. **코디네이터 결정 B2 / Codex 3 (호스트 UID:GID 단일화 방식 B 확정)**:
     - 컨테이너 `--user`를 SSH 주체의 호스트 `uid:gid`(`PORTAL_UID="$(id -u)"`, `PORTAL_GID="$(id -g)"`)로 실행하여 방식 B로 단일화.
     - 컨테이너 이미지 내부의 정적 html(`/usr/share/nginx/html`)은 비시크릿이므로 `root:root` 소유 0444(파일)/0555(디렉터리)로 고정.
     - Nginx 임시 경로(`/tmp/client_temp` 등) 및 PID 파일(`/tmp/nginx.pid`)은 tmpfs 마운트로 호스트 uid 쓰기 권한 확보.
     - #251 파일 권한(`server-key.pem` 0400, `server-chain.pem` 0600)을 일체 변경하지 않음 (이전 `chgrp 101` 방식 A 완전 제거).
  2. **B1 [차단] Docker Hub 레지스트리 실재 Base Digest 고정**:
     - `docker buildx imagetools inspect` 명령으로 레지스트리 인덱스 digest를 실측 확인(조회 시각: 2026-09-30T09:54:00+09:00):
       - `node:22-alpine` $ightarrow$ `sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402`
       - `nginx:1.27-alpine` $ightarrow$ `sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10`
     - `Dockerfile`에 해당 실재 digest를 엄격하게 고정.
  3. **H1 self-signed 검사 정규화 및 CA 제약**:
     - OpenSSL `-nameopt RFC2253` 및 `sed -e 's/^subject= *//'` / `sed -e 's/^issuer= *//'`로 prefix 차이를 제거한 DN 정규화 비교 도입 (`subj_dn == issuer_dn` 검증).
     - 기본 제약조건 `CA:FALSE` 존재 필수 요구 및 `CA:TRUE` 거부.
     - 사내 루트 CA 지문 allowlist(#249) 결속 검증.
  4. **M2 전용 상태 디렉터리 격리 및 업스트림 fail-closed**:
     - `upstream.conf` 생성 경로를 예측 가능한 `/tmp` 대신 전용 `0700` 상태 디렉터리(`~/.local/state/saintvision-portal/${PORTAL_INSTANCE}`)로 격리하고 `mktemp` 및 `mv -f` 원자적 교체 적용.
     - `PORTAL_UPSTREAM_CP_HOST`를 `cp.sv.lan:443`으로 엄격 한정하고 불일치 시 fail-closed 즉시 기동 중단.
  5. **L1 호스트 헤더 전달 및 HTTP/1.1 연결**:
     - `nginx.conf`의 SSE 및 터미널 WebSocket location에 `proxy_set_header Host cp.sv.lan;` 명시.
     - `/v1/` location에 `proxy_http_version 1.1;` 및 `proxy_set_header Connection "";` 추가하여 keepalive 활성화.
  6. **M1 정적 자산 캐싱 우선순위 보존**:
     - `location ^~ /assets/` 접두사 일치 지정자를 사용하여 정규식 location보다 우선하도록 보장하고 `Cache-Control: public, immutable` 및 `expires 1y;` 엄격 보존.
  7. **M3 불변 Image ID 해석 및 실행 결속**:
     - `docker image inspect --format '{{.Id}}'`를 통해 `sha256:[0-9a-f]{64}` 정규식 검증으로 고유 Image ID를 추출.
     - `PORTAL_IMAGE_DIGEST` 설정 시 exact match 검증 및 해당 불변 Image ID로 컨테이너 실행 결속(태그 TOCTOU 방지).
  8. **M4 엄격한 HTTPS 사전 프로브 및 안정화 검증**:
     - 스테이징 사전 프로브에서 HTTP fallback을 완전 제거하고 엄격한 HTTPS 프로브(`/healthz`, `/index.html`, `/auth-config.js`) 적용.
     - 운영 컨테이너 실행 후 1초 안정화 대기 및 `RestartCount == 0` 재확인.
  9. **H2 변이 8종 전수 사살 시험 구축**:
     - `tests/test_intranet_portal_deploy.py`에 전용 테스트 케이스를 신설하여 8대 생존 변이 및 비소유 컨테이너 보존을 전수 검증 (33 passed 100%).
  10. **L2 보안 검증기 강화**:
      - `docker run` 내 `--env-file` 주입 거부, CSP 내 `script-src 'unsafe-inline'` 거부, `frame-ancestors *` 거부 검증기 추가.
  11. **L3 개발 인증서 기본 경로 일치**:
      - `generate-dev-certs.sh` 기본 출력 경로를 `certs/dev/`로 일치시키고 운영 `portal-up.sh`에서 레거시 `portal.crt`/`portal.key` 폴백 완전 제거.
  12. **제어 평면 인계 사항 문서화**:
      - 제어 평면(`app.py:773-778`)의 `allowed_origins`에 `https://portal.sv.lan`이 등록되어야 WebSocket 및 API 리버스 프록시가 정상 허용됨을 README에 명시.

---

## 2. 세부 산출물 구조

```
deploy/intranet/portal/
├── Dockerfile                  # Multi-stage 비root Nginx 이미지 (node:22/nginx:1.27 sha256 고정, root:root 0444/0555 정적 자산)
├── Dockerfile.dockerignore      # 포털 빌드 전용 ignore (루트 python .dockerignore 오버라이드)
├── nginx.conf                  # 동일 origin 리버스 프록시(^~ /assets/ immutable, Host 전파) 및 정적 서빙
├── security-headers.conf       # HSTS/CSP/nosniff 공통 헤더 스니펫
├── conf.d/
│   └── upstream.conf           # 업스트림 제어 평면 정의 스니펫
├── auth-config.js              # 사내망 Keycloak IdP 연동 런타임 설정 (sv-portal)
├── portal-up.sh                # 운영 컨테이너 안전 기동/교체 스크립트 (UID:GID 방식B, 0700 상태 디렉터리, DN 정규화, Image ID 결속)
├── portal-smoke-up.sh          # 로컬 개발/스모크 전용 기동 스크립트 (격리된 smoke 튜플)
├── portal-down.sh              # 운영 컨테이너 안전 정지 스크립트 (4-튜플 라벨 검증)
├── generate-dev-certs.sh       # 로컬 스모크용 임시 ECDSA P-256 인증서 생성기 (certs/dev/)
└── README.md                   # 배포 가이드 및 제어 평면 인계 문서
```

---

## 3. 정량 검증 결과

- **배포 정적 및 변이 사살 시험 (`pytest tests/test_intranet_portal_deploy.py`)**:
  - **33 passed 100% (0.13s)**:
    1. `test_security_headers_conf_invariants`: HSTS, strict CSP connect-src `'self'`/idp, style-src 'self', form-action 'self', script-src/frame-ancestors L2 불변식.
    2. `test_nginx_conf_includes_security_headers_in_all_add_header_locations`: 전 location 헤더 상속 검증.
    3. `test_nginx_conf_reverse_proxy_topology`: /v1/, SSE buffering off, WS upgrade, upstream TLS, Host cp.sv.lan 전파(L1) 검증.
    4. `test_nginx_conf_assets_caching_immutable`: ^~ /assets/ 접두사 및 immutable 캐싱 우선순위 검증 (M1).
    5. `test_nginx_conf_privacy_logging`: 로그 포맷 query/referer 제외, /callback access_log off 검증.
    6. `test_nginx_conf_fixed_https_redirect_and_healthz`: 고정 domain 301 리다이렉트, /healthz 예외 검증.
    7. `test_nginx_conf_missing_static_files_404`: 누락 확장자 404 응답 검증.
    8. `test_nginx_conf_no_daemon_off`: nginx.conf 내 daemon off 부재 검증.
    9. `test_portal_up_sh_owner_label_4tuple`: 4-튜플 라벨 및 exited 한정 정리 검증.
    10. `test_portal_down_sh_owner_label_4tuple`: down 스크립트 4-튜플 검증.
    11. `test_portal_up_sh_production_ca_verification`: CA 체인, RFC2253 DN 정규화 self-signed 거부(H1), SAN, EKU, CA:FALSE/TRUE 검증.
    12. `test_portal_up_sh_no_chmod_on_operator_keys`: operator 키 권한 chmod 부재 및 #251 기본 파일명 검증.
    13. `test_portal_up_sh_upstream_cp_fail_closed_and_state_dir`: 엄격한 cp.sv.lan:443 fail-closed 및 0700 상태 디렉터리 원자적 생성 검증 (M2).
    14. `test_portal_up_sh_image_id_enforcement`: 64-hex sha256 고유 Image ID 해석 및 실행 결속 검증 (M3).
    15. `test_portal_up_sh_staging_preflight_and_safety`: 스테이징 엄격 HTTPS 프로브(/healthz, /index.html, /auth-config.js) 및 RestartCount 안정화 검증 (M4).
    16. `test_portal_up_sh_no_secrets_in_docker_run`: docker run 내부 -e/--env/--env-file 부재 검증 (L2).
    17. `test_portal_smoke_up_sh_isolation`: smoke 컨테이너/인스턴스/인증서 격리 검증.
    18. `test_generate_dev_certs_sh_defaults_to_certs_dev`: certs/dev/ 기본 디렉터리 검증 (L3).
    19. `test_dockerfile_pinned_image_digests`: 레지스트리 실재 SHA256 digest 고정 및 root:root 0444/0555 권한 검증 (B1, B2).
    20. `test_dockerfile_dockerignore_present_and_whitelisted`: Dockerfile.dockerignore 화이트리스트 검증.
    21. `test_positive_control`: 미변이 원본 파일의 validator 전원 통과 검증.
    22. `test_positive_control_comment_immunity`: 주석 내 키워드 면역 검증.
    23. `test_mutation_loosening_csp_fails`: CSP 완화 시 validator 실패 검증 (script-src/frame-ancestors 포함).
    24. `test_mutation_portal_up_security_flags_fail`: 보안 플래그 제거 및 환경변수 주입 시 validator 실패 검증 (--env-file 포함).
    25. `test_positive_control_h2_invariants`: H2 8대 불변식 양성 대조군 검증.
    26. `test_mutation_1_v1_proxy_ssl_verify_off_fails`: 변이 1 사살 (/v1 proxy_ssl_verify off).
    27. `test_mutation_2_ws_proxy_ssl_verify_off_fails`: 변이 2 사살 (WS proxy_ssl_verify off).
    28. `test_mutation_3_ca_true_false_check_removed_fails`: 변이 3 사살 (CA:TRUE/CA:FALSE 검사 제거).
    29. `test_mutation_4_chain_verify_removed_fails`: 변이 4 사살 (인증서 체인 검증 제거).
    30. `test_mutation_5_owner_tuple_instance_removed_fails`: 변이 5 사살 (소유자 튜플 instance 검사 제거).
    31. `test_mutation_6_upstream_fail_closed_exit_removed_fails`: 변이 6 사살 (업스트림 fail-closed exit 제거).
    32. `test_mutation_7_preflight_nginx_t_failure_ignored_fails`: 변이 7 사살 (스테이징 nginx -t 실패 시 exit 제거).
    33. `test_mutation_8_assets_immutable_removed_fails`: 변이 8 사살 (/assets immutable 헤더 제거).
    34. `test_portal_up_preserves_non_matching_containers`: 비소유 컨테이너 미접촉 및 보존 검증.
- **스크립트 구문 점검**: `bash -n` 4대 셸 스크립트 전원 문법 오류 0건 (exit 0).
- **TypeScript 타입 점검**: `npx tsc -b` 에러 **0건**.
- **프로덕션 번들 빌드**: `npm run build` 성공 (Vite bundle 7.82s).
- **프런트엔드 무결성 점검**: `python tools/check_frontend_integrity.py` 92개 파일 스캔, 9대 규칙 위반 **0건 (exit 0)**.
- **계약 바인딩 점검**: `python tools/check_contract_bindings.py` 55개 픽스처 전수 커버리지 **PASS (exit 0)**.
- **라우트 커버리지 점검**: `pytest tests/test_route_coverage.py` **40 passed (exit 0)**.
- **IP 주소 및 비밀 누출 점검**: 전 파일 대상 하드코딩 IP 주소 **0건**, 시크릿 유출 **0건**.

---

## 4. 인계 및 다음 단계

- **노드2 배포 상태**:
  - Leaf 인증서: 노드2 전달 완료 (`DELIVERED_NOT_ACTIVATED`).
  - 활성화 조건: 제어 평면 `allowed_origins`에 `https://portal.sv.lan` 등록 후 `portal-up.sh` 기동.
- **독립 검토 요청**: Claude (UI·테스트 축) 및 Codex (계약·보안 축) 재검토 요청.
