# SaintVision Intranet Portal Web Deployment (Card 156)

## 1. 아키텍처 및 배포 토폴로지

사내망 포털 웹 애플리케이션(`apps/web`)을 노드2(object store 노드)에 안전하게 배포하기 위한 비root Nginx 정적 서빙 및 동일-origin 리버스 프록시 자산입니다.

- **서비스 도메인**: `portal.sv.lan`
- **배치 대상 노드**: 노드2 (object store 노드, Docker 지원)
- **동일 Origin 리버스 프록시 (Reverse Proxy Topology)**:
  - 브라우저 클라이언트는 동일 출처(`https://portal.sv.lan`)로 정적 자산, REST API(`/v1/`), SSE 이벤트 스트림, 터미널 WebSocket에 단일 접근합니다.
  - Nginx는 `/v1/`, SSE(`proxy_buffering off;`), 터미널 WebSocket(`Upgrade $http_upgrade`, `Connection $connection_upgrade`)을 업스트림 제어 평면(`https://control_plane`)으로 안전하게 포워딩합니다.
  - **업스트림 TLS 검증**: `proxy_ssl_verify on;`, `proxy_ssl_trusted_certificate /etc/nginx/certs/ca-bundle.crt;`, `proxy_ssl_name cp.sv.lan;`, `proxy_ssl_server_name on;`.
  - **Fail-closed 업스트림 설정**: `PORTAL_UPSTREAM_CP_HOST`는 엄격히 `cp.sv.lan:443`으로 고정 검증되며, 미설정 또는 다른 값 주입 시 기동을 즉각 거부합니다 (설정 주입 공격 차단).
  - **업스트림 연결 풀링**: `/v1/` REST API 프록시에 `proxy_http_version 1.1;` 및 `proxy_set_header Connection "";`를 적용하여 `upstream` 블록의 `keepalive 32` 연결 풀을 온전히 활용합니다.
  - **호스트 헤더 일관성**: SSE 및 WebSocket 프록시 블록에도 `proxy_set_header Host cp.sv.lan;`을 명시하여 업스트림 가상 호스트 라우팅을 보장합니다.
- **엄격한 콘텐츠 보안 정책 (CSP)**:
  - 제어 평면 API/WS가 동일 출처(`/v1/`)로 프록시되므로, 브라우저는 외부 백엔드로 직접 cross-origin 연결을 하지 않습니다.
  - 따라서 CSP는 `connect-src 'self' https://idp.sv.lan;`으로 한정됩니다 (`'self'`는 포털 API/WS, `https://idp.sv.lan`은 Keycloak OIDC 토큰 엔드포인트).
  - `style-src 'self'`, `form-action 'self'`, `frame-ancestors 'none'`, `object-src 'none'`, `base-uri 'self'`.
- **보안 헤더 상속 무결성 (Inheritance Safety)**:
  - Nginx 1.27의 특성상 location 블록에서 `add_header`를 선언하면 상위 server/http 블록의 헤더가 상속되지 않습니다.
  - 공통 보안 헤더를 [`security-headers.conf`](security-headers.conf) 스니펫으로 분리하고, server 블록 및 `add_header`를 선언하는 모든 location 블록(`/auth-config.js`, `/index.html`, `/assets/`, `/callback`, `/v1/` 등)에 빠짐없이 `include`하여 HSTS/CSP 누락을 원천 방지합니다.
- **개인정보 및 토큰 로그 보호 (Log Privacy)**:
  - 로그 포맷 `privacy`는 `$request_method $uri $server_protocol`만을 기록하며, 쿼리 스트링(`$request`)과 `$http_referer`를 일체 기록하지 않습니다.
  - `/callback` 엔드포인트는 `access_log off;`를 지정하여 일회용 인가 코드(`code=...`)가 stdout 로그에 남지 않습니다.
- **정적 자산 불변 캐싱 및 404 분기 (M1 & L3 Invariants)**:
  - 해시가 포함된 정적 자산 디렉터리는 `location ^~ /assets/` 접두사 수식어를 사용하여 이후의 정규식 location에 의한 오버라이드를 방지하고 `Cache-Control "public, immutable"` 및 1년 만료를 보장합니다.
  - `/assets/` 외부에 위치한 알려진 정적 확장자(`.js`, `.css`, `.png`, `.svg`, `.ico` 등)의 누락 요청은 SPA fallback(`/index.html` 200)을 타지 않고 즉시 404를 반환합니다 (`try_files $uri =404;`).
- **고정 도메인 리다이렉트 및 HTTP `/healthz` 계약**:
  - 포트 80은 고정 도메인 `https://portal.sv.lan$request_uri`로 301 영구 리다이렉트하여 Host 헤더 오염 공격을 방지합니다.
  - 포트 80의 `/healthz`는 로컬 컨테이너 런타임/오케스트레이터의 활성 프로브가 TLS 핸드셰이크 오버헤드 없이 경량 루프백 점검을 수행할 수 있도록 평문 200 OK 예외를 유지합니다.

---

## 2. 파일 구성

```
deploy/intranet/portal/
├── Dockerfile                  # Multi-stage 비root Nginx 이미지 (node:22/nginx:1.27 레지스트리 실재 sha256 고정)
├── Dockerfile.dockerignore      # 포털 빌드 전용 ignore (루트 python .dockerignore 오버라이드)
├── nginx.conf                  # 동일 origin 리버스 프록시 및 정적 서빙 설정 (^~ /assets/, Host cp.sv.lan)
├── security-headers.conf       # HSTS/CSP/nosniff 공통 헤더 스니펫
├── conf.d/
│   └── upstream.conf           # 업스트림 제어 평면 정의 스니펫
├── auth-config.js              # 사내망 Keycloak IdP 연동 런타임 설정 (sv-portal)
├── portal-up.sh                # 운영 컨테이너 안전 기동/교체 스크립트 (스테이징 사전검증, 4-튜플 라벨, CA 검증, sha256 실행)
├── portal-smoke-up.sh          # 로컬 개발/스모크 전용 기동 스크립트 (격리된 smoke 튜플, certs/dev/)
├── portal-down.sh              # 운영 컨테이너 안전 정지 스크립트 (4-튜플 라벨 검증)
├── generate-dev-certs.sh       # 로컬 스모크용 임시 ECDSA P-256 인증서 생성기 (certs/dev/)
└── README.md                   # 본 가이드
```

---

## 3. 컨테이너 수명 주기 및 안전 불변식

`portal-up.sh`는 노드2의 기존 컨테이너 및 공유 환경을 침해하지 않도록 다음 불변식을 엄격히 강제합니다:

1. **소유자 라벨 4-튜플(Tuple) 컨테이너만 교체**:
   - `ai.saintvision.service=portal`
   - `ai.saintvision.workload=intranet-portal`
   - `ai.saintvision.node=node2`
   - `ai.saintvision.instance=${PORTAL_INSTANCE:-main}`
   - 교체 대상 컨테이너가 존재할 경우 4대 라벨이 모두 일치해야만 교체하며, 하나라도 다르면 즉시 중단하고 타 컨테이너를 절대 건드리지 않습니다.
   - 유휴 컨테이너 정리 시에도 정지 상태(`status=exited`)이면서 4-튜플이 완전히 일치하는 것만 안전하게 삭제합니다.
2. **스테이징 사전 검증(Preflight Canary) 및 안전 교체 (M3 & M4)**:
   - 기존 컨테이너를 중지하기 **전에**, 대상 이미지 ID(`sha256:` 64hex)를 inspect로 확정하고 동일 마운트/보안 플래그의 임시 스테이징 컨테이너(`saintvision-portal-staging-$$`)를 먼저 백그라운드로 기동합니다.
   - 스테이징 컨테이너 내부에서 `nginx -t`, HTTPS `/healthz`, `/index.html`, `/auth-config.js` 프로브를 사전 실측합니다 (HTTP fallback은 원천 금지되며 HTTPS 경로만 검증).
   - 스테이징 검증 실패 시 기존 운영 컨테이너는 일체 건드리지 않고 즉시 중단 및 보존됩니다.
   - 스테이징 검증 성공 시에만 기존 컨테이너를 안전하게 교체하며, 기동 후 `RestartCount == 0` 및 안정화(sleep 1s 후 재확인)를 검증합니다 (단일 컨테이너 교체이므로 수백 ms의 전환 창이 존재할 수 있으며, 기존 서비스 보존을 최우선으로 하는 사전검증 교체 패턴입니다).
3. **비밀의 argv 및 환경변수 주입(-e/--env/--env-file) 전면 금지**:
   - 스크립트 매개변수나 `docker run` 인자에 패스워드, 토큰, 비밀키 키워드 유입을 차단합니다.
   - `docker run` 실행 시 `-e`, `--env`, `--env-file` 플래그를 일체 사용하지 않습니다.
4. **코디네이터 결정 B2/Codex3: 호스트 UID 단일화 및 불변 파일 권한**:
   - 컨테이너는 SSH 주체 호스트 UID:GID(`--user "${PORTAL_UID}:${PORTAL_GID}"`, 기본값 `$(id -u):$(id -g)`)로 실행됩니다.
   - 이미지 내 정적 HTML 파일(`/usr/share/nginx/html`)은 `root:root` 소유, 파일 `0444`, 디렉터리 `0555`로 설정되어 비밀이 아닌 공개 웹 자산으로 모든 UID에서 안전하게 읽을 수 있습니다.
   - Card 150 PKI(#251)에서 전달된 비밀키(`server-key.pem`)는 호스트 UID 소유의 `0400` 모드, 체인 인증서(`server-chain.pem`)는 `0600` 모드이며, **스크립트가 파일 권한을 임의로 변경(`chmod`)하지 않고 원본 그대로 보존**합니다.
   - Nginx 임시 경로(`/tmp/client_temp`, `/var/cache/nginx`, PID 등)는 tmpfs(1777)로 마운트되어 실행 UID로 자유롭게 쓰기가 가능합니다.
5. **사내 CA Bundle 기반 Leaf 인증서 엄격 검증 (H1)**:
   - 운영 `portal-up.sh`는 사내 CA 번들로 인증서 체인을 검증(`openssl verify -CAfile`)합니다.
   - **자체 서명(self-signed) 인증서는 DN 정규화 비교(`-nameopt RFC2253`)를 통해 주체(subject)와 발급자(issuer)가 동일한 경우 운영 기동 시 엄격히 거부**됩니다.
   - SAN `portal.sv.lan`, EKU `serverAuth`, Basic Constraints `CA:FALSE` 필수 존재 및 `CA:TRUE` 부재, 유효기간, 공개키 해시 일치성을 전수 사전 확인합니다.
   - 로컬 스모크 및 오프라인 검증은 별도 스크립트인 [`portal-smoke-up.sh`](portal-smoke-up.sh)를 통해 격리 실행합니다.
6. **영속적 상태 디렉터리 및 원자적 Upstream 설정 (M2)**:
   - `upstream.conf`는 공유 `/tmp` 대신 영속적인 전용 `0700` 상태 디렉터리(`${HOME}/.local/state/saintvision-portal/${PORTAL_INSTANCE}`)에 보관됩니다.
   - 디렉터리 심볼릭 링크 여부를 검사하고, `mktemp`를 통해 임시 파일 생성 후 원자적(`mv -f`)으로 교체하여 지시어 주입 공격을 방어합니다.
7. **불변 Image ID 실행 (M3)**:
   - 태그(`:latest`) 대신 `docker inspect`를 통해 확인된 불변 `sha256:` 64hex Image ID로 컨테이너를 직접 실행하여 태그 교체 TOCTOU 공격을 방어합니다.

---

## 4. 빌드 및 배포 명령

### 이미지 빌드

루트 `.dockerignore`는 파이썬 전용이므로, BuildKit을 통해 포털 전용 ignore 파일([`Dockerfile.dockerignore`](Dockerfile.dockerignore))을 적용하여 빌드합니다:

```bash
# 리포지토리 루트에서 실행
DOCKER_BUILDKIT=1 docker build -f deploy/intranet/portal/Dockerfile -t saintvision-portal:latest .
```

### 운영 배포 기동

```bash
# 필수: 업스트림 제어 평면 호스트 지정 (cp.sv.lan:443 고정)
export PORTAL_UPSTREAM_CP_HOST="cp.sv.lan:443"

# 인증서 디렉터리 지정 (기본값: deploy/intranet/portal/certs)
# 요구 파일: server-chain.pem (0600), server-key.pem (0400), ca-bundle.crt
export PORTAL_CERTS_DIR="/path/to/certs"

# 컨테이너 실행 (호스트 사용자 UID 매핑, B2 방식)
PORTAL_UID="$(id -u)" PORTAL_GID="$(id -g)" bash deploy/intranet/portal/portal-up.sh
```

---

## 5. 제어 평면(Control Plane) 인계 요건 (Hand-off)

- **WebSocket / API Origin 허용 목록 (`allowed_origins`)**:
  - `services/control-plane/src/inv/app.py:773-778`에 따라 제어 평면은 WebSocket 연결 및 CORS 요청 수신 시 Origin 헤더를 검증합니다.
  - 사내망 포털(`https://portal.sv.lan`)이 제어 평면의 터미널 WebSocket(`/v1/terminal/ws`, `/v1/workspaces/{id}/terminals/{terminalId}/connect`) 및 REST API를 역방향 프록시하여 정상 통신하려면, **제어 평면의 `allowed_origins` 설정에 `https://portal.sv.lan`이 반드시 포함**되어 있어야 합니다.
