# SaintVision Intranet Portal Web Deployment (Card 156)

## 1. 아키텍처 및 배포 토폴로지

사내망 포털 웹 애플리케이션(`apps/web`)을 노드2(object store 노드)에 안전하게 배포하기 위한 비root Nginx 정적 서빙 및 동일-origin 리버스 프록시 자산입니다.

- **서비스 도메인**: `portal.sv.lan`
- **배치 대상 노드**: 노드2 (object store 노드, Docker 지원)
- **동일 Origin 리버스 프록시 (Reverse Proxy Topology)**:
  - 브라우저 클라이언트는 동일 출처(`https://portal.sv.lan`)로 정적 자산, REST API(`/v1/`), SSE 이벤트 스트림, 터미널 WebSocket에 단일 접근합니다.
  - Nginx는 `/v1/`, SSE(`proxy_buffering off;`), 터미널 WebSocket(`Upgrade $http_upgrade`, `Connection $connection_upgrade`)을 업스트림 제어 평면(`https://control_plane`)으로 안전하게 포워딩합니다.
  - **업스트림 TLS 검증**: `proxy_ssl_verify on;`, `proxy_ssl_trusted_certificate /etc/nginx/certs/ca-bundle.crt;`, `proxy_ssl_name cp.sv.lan;`, `proxy_ssl_server_name on;`.
  - **Fail-closed 업스트림 설정**: 제어 평면 호스트가 확정되기 전이므로 `PORTAL_UPSTREAM_CP_HOST` 환경변수(예: `cp.sv.lan:443`)를 필수로 요구하며, 미설정 시 기동을 즉각 거부합니다.
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
- **정적 자산 404 분기 (L3 Invariant)**:
  - 알려진 정적 확장자(`.js`, `.css`, `.png`, `.svg`, `.ico` 등)의 누락 요청은 SPA fallback(`/index.html` 200)을 타지 않고 즉시 404를 반환합니다.
- **고정 도메인 리다이렉트 및 HTTP `/healthz` 계약**:
  - 포트 80은 고정 도메인 `https://portal.sv.lan$request_uri`로 301 영구 리다이렉트하여 Host 헤더 오염 공격을 방지합니다.
  - 포트 80의 `/healthz`는 로컬 컨테이너 런타임/오케스트레이터의 활성 프로브가 TLS 핸드셰이크 오버헤드 없이 경량 루프백 점검을 수행할 수 있도록 평문 200 OK 예외를 유지합니다.

---

## 2. 파일 구성

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

## 3. 컨테이너 수명 주기 및 안전 불변식

`portal-up.sh`는 노드2의 기존 컨테이너 및 공유 환경을 침해하지 않도록 다음 불변식을 엄격히 강제합니다:

1. **소유자 라벨 4-튜플(Tuple) 컨테이너만 교체**:
   - `ai.saintvision.service=portal`
   - `ai.saintvision.workload=intranet-portal`
   - `ai.saintvision.node=node2`
   - `ai.saintvision.instance=${PORTAL_INSTANCE:-main}`
   - 교체 대상 컨테이너가 존재할 경우 4대 라벨이 모두 일치해야만 교체하며, 하나라도 다르면 즉시 중단하고 타 컨테이너를 절대 건드리지 않습니다.
   - 유휴 컨테이너 정리 시에도 정지 상태(`status=exited`)이면서 4-튜플이 완전히 일치하는 것만 안전하게 삭제합니다.
2. **스테이징 사전 검증(Preflight Canary) 및 안전 교체**:
   - 기존 컨테이너를 중지하기 **전에**, 동일 마운트/보안 플래그의 임시 스테이징 컨테이너(`saintvision-portal-staging-$$`)를 먼저 백그라운드로 기동합니다.
   - 스테이징 컨테이너 내부에서 `nginx -t` 및 HTTPS `/healthz` 프로브(`wget --spider --no-check-certificate https://127.0.0.1/healthz`)를 사전 실측합니다.
   - 스테이징 검증 실패 시 기존 운영 컨테이너는 일체 건드리지 않고 즉시 중단 및 보존됩니다.
   - 스테이징 검증 성공 시에만 기존 컨테이너를 안전하게 교체하며, 기동 후 `RestartCount == 0` 및 프로덕션 포트 헬스체크를 검증합니다 (이중 인스턴스 L4 로드밸런서가 없는 단일 컨테이너 구조이므로 수백 ms의 교체 창이 존재할 수 있으며, 기존 서비스 보존을 최우선으로 하는 사전검증 교체 패턴입니다).
3. **비밀의 argv 및 환경변수 주입(-e) 전면 금지**:
   - 스크립트 매개변수나 `docker run` 인자에 패스워드, 토큰, 비밀키 키워드 유입을 차단합니다.
   - `docker run` 실행 시 `-e` 또는 `--env` 플래그를 일체 사용하지 않습니다.
4. **TLS 비밀키 권한 보존 및 단일 파일 읽기 전용 마운트**:
   - Card 150 PKI(#251)에서 노드2로 전달된 비밀키(`server-key.pem`)는 SSH 주체 소유의 `0400` 모드, 체인 인증서(`server-chain.pem`)는 `0600` 모드입니다.
   - **스크립트가 operator 파일 권한을 임의로 변경(`chmod`)하지 않습니다**.
   - **world-readable(0444/0666) 완화는 엄격히 금지**됩니다 (`chmod o-rwx`).
   - 비root Nginx 컨테이너가 키를 안전하게 읽는 2대 운영 방식:
     - **방식 A (권장)**: 전용 그룹 할당 및 `0440` 권한 부여 (`chgrp 101 server-key.pem; chmod 0440 server-key.pem`).
     - **방식 B**: 컨테이너 실행 UID를 호스트 키 소유자로 지정 (`PORTAL_UID="$(id -u)" PORTAL_GID="$(id -g)" bash portal-up.sh`).
   - 인증서, 비밀키, CA 번들은 디렉터리가 아닌 단일 파일 읽기 전용 바인드 마운트(`readonly`)로 컨테이너 내부(`/etc/nginx/certs/`)에 결속됩니다.
5. **사내 CA Bundle 기반 Leaf 인증서 엄격 검증**:
   - 운영 `portal-up.sh`는 사내 CA 번들로 인증서 체인을 검증(`openssl verify -CAfile`)합니다.
   - **자체 서명(self-signed) 인증서는 운영 기동 시 엄격히 거부**됩니다.
   - SAN `portal.sv.lan`, EKU `serverAuth`, Basic Constraints `CA:FALSE`, 유효기간, 공개키 해시 일치성을 전수 사전 확인합니다.
   - 로컬 스모크 및 오프라인 검증은 별도 스크립트인 [`portal-smoke-up.sh`](portal-smoke-up.sh)를 통해 격리 실행합니다.

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
# 필수: 업스트림 제어 평면 호스트 지정
export PORTAL_UPSTREAM_CP_HOST="cp.sv.lan:443"

# 인증서 디렉터리 지정 (기본값: deploy/intranet/portal/certs)
# 요구 파일: server-chain.pem, server-key.pem, ca-bundle.crt
export PORTAL_CERTS_DIR="/path/to/certs"

# 컨테이너 실행 (호스트 사용자 UID 매핑 권장)
PORTAL_UID="$(id -u)" PORTAL_GID="$(id -g)" bash deploy/intranet/portal/portal-up.sh
```

---

## 5. 인증서 의존성 및 배포 상태

- **정식 Leaf 인증서 (Card 150 Codex)**:
  - 도메인: `portal.sv.lan`
  - 알고리즘: ECDSA P-256 (prime256v1)
  - 파일 구성: `server-chain.pem` (leaf+intermediate), `server-key.pem` (0400), `ca-bundle.crt` / `ca.pem`
- **현재 노드2 전달 및 배포 상태**:
  - Card 150 증거(`docs/vault/30_Development/Evidence/card156-portal-pki-handoff.json`): **`DELIVERED_NOT_ACTIVATED`** (노드2 물리 전달 완료, 파일 모드 0400/0700 정상).
  - 현재 원격 포털 서비스는 제어 평면 업스트림 주소 확정 및 활성화 대기 상태입니다.
  - `PORTAL_UPSTREAM_CP_HOST`가 확정되면 `portal-up.sh`를 즉시 실행하여 서비스 활성화가 가능합니다.
