---
doc_id: "HIST-GEMINI-CARD156-001"
title: "History: Card 156 사내망 portal 웹 배포 자산 및 비root read-only rootfs Nginx·안전 기동 검증"
version: "2.0.0"
status: "review"
author: "Gemini"
updated: "2026-09-30T12:54:00+09:00"
source_of_truth: "Git"
---

# History: Card 156 사내망 portal 웹 배포 자산 및 비root read-only rootfs Nginx·안전 기동 검증

## 1. 개요 및 배경

- **카드 번호**: Card 156 (Owner: Gemini, Reviewers: Claude, Codex)
- **작업 브랜치**: `agent/gemini/c156-intranet-portal-deploy` (Base: `origin/integration/all-agents-unified`, PR #247 최신 커밋 `2f93cbba` 병합)
- **배치 대상 도메인**: `portal.sv.lan`
- **배치 대상 노드**: 노드2 (object store 노드, Docker 지원)
- **독립 검토 r5 조치 (Codex 계약·보안 축 + Claude UI·운영 축 '변경 요청' 전수 반영)**:
  1. **R5-H1 [운영/보안] 운영 docker run 실패 감지, 자동 롤백 및 백업 보호, 사전 포트 점검**:
     - `portal-up.sh`: `docker run` 실행을 `if ! docker run ...; then rollback_production; return 1; fi`로 감싸 run 실패(exit 125 등) 시 즉시 롤백 진입.
     - 컨테이너 swap 구간(`docker rename` 직후)에 `trap rollback_production INT TERM`을 설치하여 예기치 않은 인터럽트/시그널 시 백업 복구.
     - `validate_environment`에 사전 포트 점검 추가: `docker ps --filter publish`를 통해 대상 포트(80/443)가 다른 컨테이너에 의해 점유되어 있는지 사전 검증.
     - stale cleanup 로직에서 `*-backup-*` 이름 컨테이너를 영구 제외하여 이전 실행의 백업이 자동 삭제되는 위험 차단.
     - `rollback_production` 복구 완료 문구 출력 전 `State.Running==true` 및 컨테이너 이름 일치 검증 추가.
  2. **R5-M1 [문서 정정] 루트 CA DER 지문 allowlist 정정 및 Card 150 해시 구분**:
     - README 및 History에 기재되었던 `92455f1b...`가 Card 150 신뢰 번들 파일 해시(`trustBundleDigestSHA256`)였음을 명시하고, `portal-up.sh`가 요구하는 루트 CA 인증서 자체의 SHA-256 DER 지문(`openssl x509 -in root.crt -noout -fingerprint -sha256 | sed 's/.*=//; s/://g' | tr '[:upper:]' '[:lower:]'`) 산출 명령 및 placeholder로 정정.
  3. **R5-M2 [실측 검증] 잔여 변이 격리 사살 5대 독립 롤백 시험 및 시퀀스 순서 엄격 단언**:
     - `test_intranet_portal_deploy.py` 내 `test_behavioral_fake_docker_swap_...` 스위트를 5종으로 분리:
       1) `test_behavioral_fake_docker_swap_docker_run_failure_triggers_rollback` (docker run exit 125)
       2) `test_behavioral_fake_docker_swap_not_running_triggers_rollback` (State.Running=false)
       3) `test_behavioral_fake_docker_swap_healthz_probe_failure_triggers_rollback` (healthz 실패)
       4) `test_behavioral_fake_docker_swap_index_probe_failure_triggers_rollback` (index.html 실패)
       5) `test_behavioral_fake_docker_swap_auth_config_probe_failure_triggers_rollback` (auth-config.js 실패)
     - 각 시험에서 `docker stop broken -> docker rm -f broken -> docker start backup -> docker rename backup saintvision-portal` 호출의 정확한 순서와 백업 인스턴스 이름 일치 단언.
  4. **R5-M3 [CI 파이프라인] Hosted 런타임 비공허 TLS 1.1 거부, 전체 CSP 일치, SSE 비버퍼링, 롤백 실측, DNS 전제 문서화**:
     - `.github/workflows/frontend.yml`:
       - TLS 1.1: `openssl s_client -tls1_1 -cipher 'DEFAULT:@SECLEVEL=0'`을 사용하여 클라이언트 제약을 풀고 서버 측 alert 거부 실측.
       - CSP: `security-headers.conf` 정본과 전체 문자열 일치 단언.
       - SSE: 목 서버에서 2초 지연을 두고, 클라이언트가 `--max-time 1.2` 내에 첫 이벤트를 즉시 수신하는지 검증 (`proxy_buffering off` 실측).
       - CI 롤백 단계: 2회차 `portal-up.sh`를 기동하여 롤백 발동 및 이전 정상 컨테이너 복원 실측.
       - README: 내부 DNS 미구성 환경을 위한 `PORTAL_ADD_HOSTS` 문서화.
  5. **R5-L1 [테스트 격리] Windows Git Bash dev certs 수정 및 임시 cert 디렉터리 격리**:
     - `generate-dev-certs.sh`: `req.cnf` 서브셸 생성 방식을 적용하여 `MSYS_NO_PATHCONV=1` 없이 Linux 및 Windows Git Bash 양쪽 완벽 지원.
     - `portal-smoke-up.sh`: `PORTAL_DEV_CERTS_DIR` 지원, smoke 테스트 시 임시 디렉터리로 격리하여 소스 트리 오염 원천 차단.
  6. **R5-L2 [빌드 명세] Dockerfile 패키지 버전 제약 문구 정정**:
     - `Dockerfile` 내 `'curl>=8' 'openssl>=3'` 주석을 "하한 제약(minimum version constraints)"으로 정정하고 빌드 변이는 최종 Docker config Image ID(.Id)로 봉인됨을 명시.
  7. **R5-L3 [문서 정정 및 stub 가드] 과장 문구 정정 및 Fake Docker Stub PATH 강제**:
     - '무중단 swap' -> '안전 컨테이너 교체 (이전 컨테이너 정지 및 새 컨테이너 기동 간 짧은 전환 간격 존재)' 정정.
     - Fake docker 테스트 시작 시 `command -v docker`가 stub 경로인지 assert하여 호스트 바이너리 폴스루 원천 차단.
     - 라벨 오기(R4-H1/R4-L4) 정정.
     - Codex r5 config Image ID(`PORTAL_IMAGE_ID`) 개명 및 승인 출처 계약 명시.
- **독립 검토 r4 조치 (Codex 계약·보안 축 + Claude UI·운영 축 '변경 요청' 전수 반영)**:
  1. **R4-H1 [핵심/보안] 비밀키 0400 권한 엄격 강제 및 PORTAL_GID != 0 강제**:
     - `stat -c '%a'` 실측을 통해 비밀키 퍼미션 모드가 정확히 `0400`이어야만 실행 허용 (chmod를 통한 임의 변경 금지, 0644/0440/0600 등 fail-closed 즉시 거부).
     - `PORTAL_GID=0` 기동 시 즉시 거부 (fail-closed).
     - `Dockerfile` 런타임 패키지 버전 제약 고정 (`RUN apk add --no-cache 'curl>=8' 'openssl>=3'`).
     - OCI 이미지 다이제스트 증명 봉인(CI 빌드 attestation 또는 서명된 릴리스 레코드에서 가져온 sha256 고정 다이제스트) 명시.
  2. **R4-L2 [권한 축소] 불필요한 NET_BIND_SERVICE 기능 제거**:
     - 최신 Docker 컨테이너 네트워크 네임스페이스의 비특권 포트 바인딩 지원에 따라 `portal-up.sh` 및 `portal-smoke-up.sh`에서 `--cap-add NET_BIND_SERVICE`를 전면 제거.
  3. **R4-M1 [운영 안정성] 비파괴적 컨테이너 스왑 및 자동 롤백(Rollback) 구현**:
     - 기존 운영 컨테이너를 먼저 삭제하지 않고, 임시 백업 이름(`${CONTAINER_NAME}-backup-${rand_suffix}`)으로 rename 및 stop하여 포트 80/443 점유를 해제하면서 원본을 보존.
     - 신규 컨테이너를 `${CONTAINER_NAME}`으로 기동하고 1초 안정화 및 HTTPS 사전 프로브(`/healthz`, `/index.html`, `/auth-config.js`) 수행.
     - 신규 컨테이너 기동 또는 사후 검증 실패 시 자동 롤백 함수(`rollback_production`)가 발동하여 깨진 컨테이너를 stop/rm하고 보존된 백업 컨테이너를 원상태로 rename 및 start 복구.
     - 모든 프로브가 완벽히 성공한 이후에만 보존된 백업 컨테이너를 안전하게 제거.
  4. **R4-M2 [문서화] README 루트 CA 지문 예시 갱신**:
     - README 내 루트 CA 지문 예시를 Card 150/151 사내 공개 신뢰 번들의 실제 SHA-256 해시(`92455f1b778130334da43b0eee977357b5ae498eb1005bc29ecc6c3afb7192ba`)로 갱신.
  5. **Cross-Platform OpenSSL 정규화**:
     - Git Bash 우회 표기(`//CN=...`)가 Linux 환경에서 빈 subject를 유발하는 문제를 해소하기 위해 `export MSYS_NO_PATHCONV=1` 설정 후 표준 `/CN=...` 경로를 사용하도록 `generate-dev-certs.sh` 및 테스트 환경 전면 정규화.
  6. **R4-H2 [실측 검증] 6대 잔여 생존 변이 전수 사살 행동 시험 및 Fake Docker 스위트 완비**:
     - (d) 외래 CA 서명 리프 체인 검증 해제 사살: 허용된 CA 번들로 타 사설 CA 서명 리프 검증 시 즉시 거부 (`test_behavioral_pki_leaf_signed_by_different_ca_fails`).
     - (e) 인스턴스 라벨 비교 제거 사살: fake docker에서 instance만 다른 컨테이너 존재 시 무단 변경 방지 및 미접촉 보존 (`test_behavioral_fake_docker_instance_mismatch_preserved`).
     - (h) 업스트림 검사 return 1 -> true 변이 사살: 키 모드/소유자 등 다른 조건이 완벽한 상태에서도 `UPSTREAM_CP_HOST` 불일치가 독립적으로 차단됨을 실측 (`test_behavioral_environment_upstream_mismatch_independent_fail`).
     - (o) 스테이징 /index.html 프로브 반환 제거 사살: 정적 파일 프로브 실패 시 스테이징 컨테이너 cleanup trap 발동 실측 (`test_behavioral_fake_docker_staging_index_html_probe_failure`).
     - (t) 비밀키 소유자 UID 검사 해제 사살: `stat -c %u != PORTAL_UID` 시 독립적 fail-closed 실측 (`test_behavioral_environment_key_owner_mismatch_rejected`).
     - (u) 스왑 사후 HTTPS 프로브 반환 제거 사살: 프로브 실패 시 롤백 발동 및 이전 컨테이너 복원 실측 (`test_behavioral_fake_docker_swap_https_probe_failure_triggers_rollback`).
     - 스테이징 docker run 이름 충돌 시 stop/rm 0회 보존 시험 (`test_behavioral_fake_docker_staging_preexisting_conflict_no_stop_or_rm`).
     - 비밀키 퍼미션 모드 400/0400 통과 및 0644/0440/0600 거부 실측 (`test_behavioral_environment_key_mode_fail_closed`).
     - GID=0 거부 실측 (`test_behavioral_environment_root_gid_rejected`).
     - 총 48개 테스트 전원 통과 실측 (`pytest tests/test_intranet_portal_deploy.py`: 48 passed 100%, 40.35s).
  7. **R4-L4 Hosted 런타임 CI 파이프라인 보강**:
     - `.github/workflows/frontend.yml`의 `portal-runtime-smoke`에 목 업스트림 REST(`/v1/session`), SSE(`/events`), WebSocket 핸드셰이크(`101 Switching Protocols`) 응답 추가.
     - curl을 통해 실제 해시된 정적 자산 200 OK + `Cache-Control: public, immutable` 응답 및 비존재 자산 404 응답 실측.
     - CSP 헤더 값 및 `connect-src 'self' https://idp.sv.lan` 실측.
     - 레거시 TLS 1.1 핸드셰이크 거부 (`curl --tlsv1.1 --tls-max 1.1` fail-closed) 실측.

- **독립 검토 r3 조치 (Codex 계약·보안 축 + Claude UI·운영 축 '변경 요청' 전수 반영)**:
  1. **R3-H1 [핵심/보안] 루트 CA allowlist 필수화 및 다중 루트 탐지/중간 CA 검증**:
     - `PORTAL_ALLOWED_ROOT_FINGERPRINTS`를 필수 환경변수로 전환 (미설정 시 fail-closed 기동 거부).
     - `openssl x509 -in bundle.crt`의 단일 인증서만 검사하는 한계를 해소하기 위해 `awk` 기반으로 CA 번들을 개별 인증서로 분할.
     - 번들 내 자체서명(RFC2253 DN 정규화 `subj == issuer`) 루트 인증서를 전수 탐색하여 루트 인증서 개수가 정확히 1개(0개 또는 2개 이상 시 즉시 거부)임을 강제.
     - 해당 1개 루트의 SHA-256 지문을 공백 구분 allowlist와 매칭 검증.
     - 번들 내 중간 CA 인증서들이 해당 허용된 루트 CA에 의해 서명 및 검증되는지 `openssl verify -CAfile`로 검증.
  2. **R3-M1 [보안] PORTAL_IMAGE_DIGEST 필수화**:
     - `PORTAL_IMAGE_DIGEST`를 운영 필수 환경변수로 전환 (미설정 시 fail-closed 즉시 거부).
     - `^sha256:[0-9a-f]{64}$` 정규식 일치 및 `docker image inspect` 이미지 ID와의 엄격한 일치를 강제하여 태그 변조/TOCTOU 원천 차단.
  3. **R3-M2 [보안] Root UID 실행 거부 및 키 소유권 검증**:
     - `PORTAL_UID=0` 또는 `PORTAL_GID=0` 기동 시 즉시 거부 (fail-closed).
     - `Dockerfile` 런타임 베이스에 기본 비root 계정 `USER 101:101` 유지 (호스트 `--user`가 이를 오버라이드).
     - `stat -c '%u' "$KEY_FILE"`을 실측하여 비밀키 소유자 UID와 `PORTAL_UID`가 일치하는지 명시적 검증.
  4. **R3-M3 [안전성] 스테이징 cleanup trap 및 smoke 격리 강화**:
     - `trap staging_cleanup EXIT INT TERM` 등록을 통해 사전 검증 실패, 스크립트 에러, 인터럽트 시 스테이징 컨테이너가 잔류하지 않고 즉시 정리되도록 보장.
     - `portal-smoke-up.sh`에 전체 4-튜플 라벨(`service`, `workload`, `node`, `instance`) 일치 여부를 검증하여 다른 컨테이너 훼손 방지.
     - 스모크 기본 실행 UID/GID를 호스트 실행 주체(`PORTAL_UID:-$(id -u)`)로 일치.
  5. **R3-L1 [무결성] 사전 검증 프로브 내 불완전 플래그 제거**:
     - 사전 검증 프로브에서 `--no-check-certificate`를 완전히 배제하고, 마운트된 사내 CA 번들과 `--resolve portal.sv.lan:443:127.0.0.1`을 사용하는 검증된 curl HTTPS 프로브 수행.
  6. **R3-L2 [문서화] README 터미널 웹소켓 경로 및 필수 변수 갱신**:
     - 제어 평면 실제 라우트에 맞추어 README 내 WebSocket 경로를 `/v1/terminal/ws` 및 `/v1/workspaces/{id}/terminals/`로 정정.
     - 필수 환경변수 `PORTAL_ALLOWED_ROOT_FINGERPRINTS` 및 `PORTAL_IMAGE_DIGEST` 사용법 상세 기술.
  7. **R3-H2 [실측 검증] 실제 OpenSSL PKI 행동 시험 및 Fake Docker 스위트 구축**:
     - `portal-up.sh`를 모듈형 함수(`validate_environment`, `validate_ca_bundle_and_allowlist`, `validate_leaf_certificate`, `validate_image_and_digest`, `validate_owner_tuple`, `run_staging_preflight`, `swap_and_launch_production` 등)로 분리.
     - 실제 Git Bash OpenSSL 3.2.3을 구동하여 12종의 PKI 동작 시험(정상 통과, allowlist 불일치 거부, 공격자 루트 거부, 다중 루트 번들 거부, 루트 부재 번들 거부, 유효하지 않은 중간 CA 거부, 자체서명 리프 거부, CA:TRUE 리프 거부, CA:FALSE 누락 리프 거부, serverAuth 누락 거부, SAN 불일치 거부, 키 불일치 거부)을 실측.
     - PATH 앞단에 fake docker stub을 주입하여 비소유 라벨 보존 및 스테이징 실패 시 `docker rm -f` cleanup trap 동작을 실측.
     - `nginx.conf` 내 location 레벨 AST 파싱을 통해 `proxy_pass`를 포함하는 모든 location 블록에 `proxy_ssl_verify on;`이 존재하는지 구조적 검증.
     - 배포 스위트 `pytest tests/test_intranet_portal_deploy.py` 38건 전원 통과 (38 passed 100%).
  8. **Hosted 런타임 CI 구축**:
     - `.github/workflows/frontend.yml`에 `portal-runtime-smoke` 작업 신설.
     - GitHub Actions 호스팅 러너에서 Docker BuildKit 빌드, 목 HTTPS 업스트림 기동, 사내 CA/Leaf 인증서 발급, `portal-up.sh` 실행, curl 301 리다이렉트·/healthz·보안헤더·/assets/ 불변 캐시·`nginx -t` 검증 및 `portal-down.sh` 정리 파이프라인 수행.

---

## 2. 세부 산출물 구조

```
deploy/intranet/portal/
├── Dockerfile                  # Multi-stage 비root Nginx 이미지 (node:22/nginx:1.27 sha256 고정, curl/openssl 도구 포함, USER 101:101)
├── Dockerfile.dockerignore      # 포털 빌드 전용 ignore (루트 python .dockerignore 오버라이드)
├── nginx.conf                  # 동일 origin 리버스 프록시(^~ /assets/ immutable, Host 전파) 및 정적 서빙
├── security-headers.conf       # HSTS/CSP/nosniff/X-XSS-Protection 공통 헤더 스니펫
├── conf.d/
│   └── upstream.conf           # 업스트림 제어 평면 정의 스니펫
├── auth-config.js              # 사내망 Keycloak IdP 연동 런타임 설정 (sv-portal)
├── portal-up.sh                # 운영 컨테이너 안전 기동/교체 스크립트 (모듈형 함수, 루트 allowlist 필수, 다중루트 탐지, Image Digest 필수, UID 0 거부, staging trap)
├── portal-smoke-up.sh          # 로컬 개발/스모크 전용 기동 스크립트 (호스트 UID, 4-튜플 라벨 검증)
├── portal-down.sh              # 운영 컨테이너 안전 정지 스크립트 (4-튜플 라벨 검증)
├── generate-dev-certs.sh       # 로컬 스모크용 임시 ECDSA P-256 인증서 생성기 (certs/dev/, Windows Git Bash 호환 //C=)
└── README.md                   # 배포 가이드, 필수 환경변수 목록 및 제어 평면 인계 문서
```

---

## 3. 정량 검증 결과

- **배포 통합 및 행동 검증 시험 (`pytest tests/test_intranet_portal_deploy.py`)**:
  - **48 passed 100% (40.35s)**:
    0. 6대 생존 변이 전수 사살 (d: 외래 CA 서명 리프 거부, e: instance 불일치 컨테이너 미접촉 보존, h: upstream 불일치 독립 거부, o: staging /index.html 실패 trap, t: key owner 불일치 거부, u: swap post-launch HTTPS probe 실패 자동 롤백 및 이전 컨테이너 복원 실측).
    1. `test_security_headers_conf_invariants`: HSTS, strict CSP connect-src 'self'/idp, style-src 'self', form-action 'self', X-XSS-Protection "0" 검증.
    2. `test_nginx_conf_includes_security_headers_in_all_add_header_locations`: 전 location 헤더 상속 검증.
    3. `test_nginx_conf_reverse_proxy_topology`: /v1/, SSE buffering off, WS upgrade, upstream TLS, Host cp.sv.lan 전파 검증.
    4. `test_nginx_conf_assets_caching_immutable`: ^~ /assets/ 접두사 및 immutable 캐싱 우선순위 검증.
    5. `test_nginx_conf_privacy_logging`: 로그 포맷 query/referer 제외, /callback access_log off 검증.
    6. `test_nginx_conf_fixed_https_redirect_and_healthz`: 고정 domain 301 리다이렉트, /healthz 예외 검증.
    7. `test_nginx_conf_missing_static_files_404`: 누락 확장자 404 응답 검증.
    8. `test_nginx_conf_no_daemon_off`: nginx.conf 내 daemon off 부재 검증.
    9. `test_nginx_conf_all_proxy_locations_have_ssl_verify_on`: location 레벨 proxy_ssl_verify on 구조적 검증 (R3-H2).
    10. `test_mutation_proxy_ssl_verify_missing_or_off_fails`: proxy_ssl_verify 누락/off 변이 사살 검증.
    11. `test_portal_up_sh_owner_label_4tuple`: 4-튜플 라벨 및 exited 한정 정리 검증.
    12. `test_portal_down_sh_owner_label_4tuple`: down 스크립트 4-튜플 검증.
    13. `test_portal_smoke_up_sh_owner_label_4tuple`: smoke 4-튜플 검증.
    14. `test_portal_smoke_up_sh_host_uid`: smoke 호스트 UID 기본값 검증.
    15. `test_portal_up_sh_mandatory_root_ca_allowlist`: 루트 CA allowlist 필수화 검증 (R3-H1).
    16. `test_portal_up_sh_mandatory_image_digest`: Image Digest 필수화 검증 (R3-M1).
    17. `test_portal_up_sh_root_uid_rejected`: UID=0 거부 검증 (R3-M2).
    18. `test_portal_up_sh_key_owner_match`: 키 파일 소유자 UID 검증 (R3-M2).
    19. `test_portal_up_sh_staging_preflight_and_safety`: staging trap 및 strict TLS curl 프로브 검증 (R3-M3, R3-L1).
    20. `test_dockerfile_default_user_101`: Dockerfile 기본 USER 101:101 검증 (R3-M2).
    21. `test_behavioral_pki_valid_chain_passes`: 실제 Git Bash OpenSSL 정상 CA 번들 및 리프 통과 행동 검증.
    22. `test_behavioral_pki_missing_allowlist_fails`: allowlist 누락 거부 행동 검증.
    23. `test_behavioral_pki_attacker_root_fails`: 공격자 루트 거부 행동 검증.
    24. `test_behavioral_pki_multi_root_bundle_fails`: 번들 내 다중 루트 탐지 거부 행동 검증.
    25. `test_behavioral_pki_no_root_bundle_fails`: 번들 내 루트 부재 거부 행동 검증.
    26. `test_behavioral_pki_invalid_intermediate_fails`: 유효하지 않은 중간 CA 거부 행동 검증.
    27. `test_behavioral_pki_self_signed_leaf_fails`: 자체 서명 리프 거부 행동 검증.
    28. `test_behavioral_pki_ca_true_leaf_fails`: CA:TRUE 리프 거부 행동 검증.
    29. `test_behavioral_pki_missing_ca_false_fails`: CA:FALSE 부재 리프 거부 행동 검증.
    30. `test_behavioral_pki_missing_server_auth_fails`: serverAuth 누락 거부 행동 검증.
    31. `test_behavioral_pki_wrong_san_fails`: SAN 불일치 거부 행동 검증.
    32. `test_behavioral_pki_key_mismatch_fails`: 인증서-키 쌍 불일치 거부 행동 검증.
    33. `test_behavioral_environment_root_uid_rejected`: PORTAL_UID=0 기동 거부 행동 검증.
    34. `test_behavioral_environment_upstream_mismatch_rejected`: cp.sv.lan:443 외 업스트림 거부 행동 검증.
    35. `test_behavioral_image_digest_mandatory_rejected`: digest 누락 거부 행동 검증.
    36. `test_behavioral_fake_docker_non_matching_owner_labels_preserved`: 비소유 라벨 컨테이너 미접촉 행동 검증.
    37. `test_behavioral_fake_docker_staging_trap_cleanup`: 스테이징 오류 시 trap rm -f 정리 행동 검증.
    38. `test_behavioral_fake_docker_smoke_non_matching_owner_labels_preserved`: smoke 비소유 라벨 컨테이너 미접촉 행동 검증.
    39. `test_behavioral_environment_key_mode_fail_closed`: 비밀키 퍼미션 모드 0400 엄격 fail-closed 검증 (R4-H1).
    40. `test_behavioral_environment_root_gid_rejected`: PORTAL_GID=0 기동 거부 검증 (R4-H1).
    41. `test_behavioral_fake_docker_staging_index_html_probe_failure`: staging index.html 프로브 실패 시 cleanup trap 실측 (R4-H2-o).
    42. `test_behavioral_environment_key_owner_mismatch_rejected`: 키 파일 소유자 UID 불일치 fail-closed 실측 (R4-H2-t).
    43. `test_behavioral_pki_leaf_signed_by_different_ca_fails`: 외래 CA 서명 리프 체인 검증 거부 실측 (R4-H2-d).
    44. `test_behavioral_fake_docker_instance_mismatch_preserved`: instance 불일치 컨테이너 미접촉 보존 실측 (R4-H2-e).
    45. `test_behavioral_environment_upstream_mismatch_independent_fail`: upstream 불일치 독립 fail-closed 실측 (R4-H2-h).
    46. `test_portal_up_sh_no_cap_add_net_bind_service`: portal-up.sh 내 NET_BIND_SERVICE 부재 단언 (R4-L2).
    47. `test_portal_smoke_up_sh_no_cap_add_net_bind_service`: portal-smoke-up.sh 내 NET_BIND_SERVICE 부재 단언 (R4-L2).
    48. `test_behavioral_image_id_mismatch_different_image_with_same_tag_rejected`: 동일 태그 다른 이미지 ID 기동 거부 실측 (Codex r5).
    49. `test_behavioral_fake_docker_swap_docker_run_failure_triggers_rollback`: swap 중 docker run 실패(exit 125/포트 충돌) 시 자동 롤백 및 백업 복원 실측 (R5-H1).
    50. `test_behavioral_fake_docker_swap_not_running_triggers_rollback`: State.Running=false 시 롤백 및 백업 복원 실측 (R5-M2, Mutation R6).
    51. `test_behavioral_fake_docker_swap_healthz_probe_failure_triggers_rollback`: /healthz 프로브 실패 시 롤백 및 백업 복원 실측 (R5-M2, Mutation u).
    52. `test_behavioral_fake_docker_swap_index_probe_failure_triggers_rollback`: /index.html 프로브 실패 시 롤백 및 백업 복원 실측 (R5-M2, Mutation R4).
    53. `test_behavioral_fake_docker_swap_auth_config_probe_failure_triggers_rollback`: /auth-config.js 프로브 실패 시 롤백 및 백업 복원 실측 (R5-M2, Mutation R5).
- **단위/통합 테스트 전수 통과 실측**: `pytest tests/test_intranet_portal_deploy.py` **53 passed (100%)**.
- **Docker 라벨 인벤토리 검증 점검**: `pytest tests/test_cleanup_owned_docker_label_inventory.py` 통과 (포털 서비스 메타데이터 라벨 `service`, `workload`, `role`, `instance` 4종을 `NON_CLEANUP_LABELS`로 정확히 분류, 1 passed exit 0).
- **Stub 실행 스크립트 실행 권한 보정 및 가드**: `tests/test_intranet_portal_deploy.py` 내 임시 생성되는 stub 스크립트(`bin/stat`, `bin/docker`)에 대해 `os.chmod(..., 0o755)`를 부여하고, fake docker 테스트 시작 시 `command -v docker`가 stub 경로인지 assert하여 호스트 바이너리 폴스루 원천 차단.
- **스크립트 구문 점검**: `bash -n` 4대 셸 스크립트 전원 문법 오류 0건 (exit 0).
- **TypeScript 타입 점검**: `npx tsc -b` 에러 **0건**.
- **프로덕션 번들 빌드**: `npm run build` 성공 (Vite bundle).
- **프런트엔드 무결성 점검**: `python tools/check_frontend_integrity.py` 통과 (exit 0).
- **계약 바인딩 점검**: `python tools/check_contract_bindings.py` 통과 (exit 0).
- **라우트 커버리지 점검**: `pytest tests/test_route_coverage.py` **40 passed (exit 0)**.
- **IP 주소 및 비밀 누출 점검**: 전 파일 대상 하드코딩 IP 주소 **0건**, 시크릿 유출 **0건**.

---

## 4. 인계 및 다음 단계

- **노드2 배포 상태**:
  - Leaf 인증서: 노드2 전달 완료 (`DELIVERED_NOT_ACTIVATED`).
  - 활성화 조건: 제어 평면 `allowed_origins`에 `https://portal.sv.lan` 등록 후 `portal-up.sh` 기동.
- **독립 검토 요청**: Claude (UI·운영 축) 및 Codex (계약·보안 축) r5 재검토 요청.
