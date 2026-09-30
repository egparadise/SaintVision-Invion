# SaintVision Intranet Portal Web Deployment (Card 156)

## 1. 개요 및 배치 아키텍처

사내망 포털 웹 애플리케이션(`apps/web`)을 정적 SPA로 번들링하여 전용 Nginx 컨테이너로 서빙하는 배포 자산입니다.

- **서비스 도메인**: `portal.sv.lan`
- **배치 대상**: 노드2 (object store 노드, Docker 지원)
- **보안 격리 수준**:
  - 비root 사용자 실행 (UID:GID 101:101 `nginx:nginx`)
  - 읽기 전용 루트 파일시스템 (`--read-only`)
  - 모든 리눅스 기능 제거 (`--cap-drop ALL`)
  - 권한 상승 방지 (`--security-opt no-new-privileges`)
  - 임시 파일/소켓/버퍼는 tmpfs(`/tmp`, `/var/cache/nginx`, `/var/run`)로 격리
- **통신 및 전송 계층 보안 (HTTPS Only)**:
  - HTTP(80) $\rightarrow$ HTTPS(443) 301 리다이렉트
  - TLS 1.2 및 TLS 1.3 한정 활성화 (`ssl_protocols TLSv1.2 TLSv1.3;`, 레거시 SSL/TLS1.0/1.1 원천 차단)
  - HSTS 1년 보장 (`Strict-Transport-Security "max-age=31536000; includeSubDomains" always;`)
- **엄격한 콘텐츠 보안 정책 (CSP)**:
  - `connect-src`: `https://idp.sv.lan` 및 `https://cp.sv.lan` 전용 허용 (비암호화 HTTP 및 외부 출처 차단)
  - `frame-ancestors 'none'`, `object-src 'none'`, `base-uri 'self'`
- **SPA 라우팅 및 캐시 관리**:
  - SPA Fallback: `try_files $uri $uri/ /index.html;`
  - `/auth-config.js` 및 `/index.html`: `Cache-Control "no-cache, no-store, must-revalidate"` (배포 즉시 반영)
  - `/assets/`: `Cache-Control "public, immutable"` 및 1년 만료 (Vite content-hash 자산)

---

## 2. 파일 구성

```
deploy/intranet/portal/
├── Dockerfile             # Multi-stage 비root Nginx 컨테이너 빌드 명세
├── nginx.conf             # 보안 강화 Nginx 리버스 프록시 / 정적 서빙 설정
├── auth-config.js         # 사내망 Keycloak IdP 연동 런타임 설정 (sv-portal)
├── portal-up.sh           # 컨테이너 실행 및 안전 교체 스크립트 (소유자 라벨 한정)
├── portal-down.sh         # 컨테이너 안전 정지 및 정리 스크립트
├── generate-dev-certs.sh  # 로컬 개발 및 스모크 테스트용 임시 ECDSA 인증서 생성기
└── README.md              # 본 가이드
```

---

## 3. 컨테이너 수명 주기 및 안전 불변식

`portal-up.sh`는 노드2의 기존 컨테이너 및 공유 환경을 침해하지 않도록 다음 불변식을 엄격히 강제합니다:

1. **소유자 라벨 컨테이너만 교체**:
   - 라벨 `ai.saintvision.service=portal`을 가진 컨테이너만 점검, 교체, 정지합니다.
   - 대상 이름(`saintvision-portal`)의 컨테이너가 존재하더라도 소유자 라벨이 다르면 즉시 중단하고 타 컨테이너를 절대 건드리지 않습니다.
2. **비밀의 argv 및 환경변수 주입(-e) 전면 금지**:
   - 스크립트 매개변수나 `docker run` 인자에 패스워드, 토큰, 비밀키를 포함할 수 없습니다.
   - `-e` 또는 `--env`를 통한 민감 정보 주입을 원천 배제합니다.
3. **TLS 인증서/비밀키의 단일 파일 읽기 전용 마운트**:
   - 인증서와 비밀키는 디렉터리 통째 쓰기 권한이 아닌, 파일 단위 단일 읽기 전용 바인드 마운트(`readonly`)로만 컨테이너 내부(`/etc/nginx/certs/`)에 전달됩니다.
   - 실행 전 비밀키와 인증서의 공개키 SHA-256 해시 일치성을 사전 검증합니다.

---

## 4. 인증서 의존성 및 배포 상태

- **정식 Leaf 인증서 요건**:
  - 도메인: `portal.sv.lan`
  - 알고리즘: ECDSA P-256 (prime256v1)
  - 발급 주체: 사내 PKI CA (Card 150 Codex 담당)
- **현재 진행 상태**:
  - Nginx 설정, Dockerfile, 기동/정지 스크립트, 정적 검증 시험(19 passed), 로컬 번들 빌드: **완료 및 검증 통과**
  - Card 150 정식 인증서 노드2 물리 전달: **도착 대기 (BLOCKED)**
  - Card 150에서 발급된 `portal.crt` 및 `portal.key`가 노드2의 마운트 디렉터리에 배치되면 즉시 `portal-up.sh`를 통해 무중단 기동 가능합니다.
  - 로컬 스모크 테스트는 `bash generate-dev-certs.sh`로 생성된 임시 자체 서명 인증서로 독립 검증할 수 있습니다.
