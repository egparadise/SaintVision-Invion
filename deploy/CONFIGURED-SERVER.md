# 정본 Control Plane 설정

`saintvision.server:create_app --factory`는 `inv.app.create_configured_app`를 호출한다. `/healthz`는 프로세스 생존, `/readyz`는 공개 키 신뢰 파일·비소유자 DB 역할·tenant·복구 epoch 접근을 확인한다. Workspace가 없으면 응답의 `workspaceAdmission`은 `not_configured`이며 실행 가능 판정으로 사용하지 않는다.

Compose는 자동 DB 초기화/마이그레이션/운영 로그인 생성을 수행하지 않는다. 먼저 운영 절차에 따라 schema와 tenant, 프로젝트 권한 및 복구 epoch를 준비해야 한다. 빈 PostgreSQL을 기동하는 것만으로 서버가 준비되지 않는다. 현재 Compose PostgreSQL 이미지는 확장 요구까지 검증된 배포 패키지가 아니며 전체 스택 운영 인수는 별도다.

필수 환경 변수:

- `INV_RUNTIME_DSN`: `inv_kernel` 권한을 가진 배포 전용 LOGIN. schema 소유자·superuser·BYPASSRLS 금지.
- `INV_DATABASE_URL`: 업무 서비스용 배포 전용 SQLAlchemy DSN. kernel DSN과 독립적이다. 업무 서비스 활성화 시 해당 서비스 권한이 필요하다.
- `INV_RECOVERY_EPOCH`: DB의 `inv.control_epoch`와 조정된 UUID.
- `INV_CONFIG_DIRECTORY`: 사전에 만든 호스트 설정 디렉터리. `/run/saintvision`에 읽기 전용으로 마운트한다. 없는 디렉터리를 자동 생성하지 않는다.
- `POSTGRES_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`: 배포별 비밀. Git·공유 문서·명령 출력에 넣지 않는다.

`INV_CONFIG_DIRECTORY/api.json`의 최소 형식(아래 값은 형식 설명이며 운영 인증 자료가 아님):

```json
{
  "identity": {
    "tenant_id": "11111111-1111-4111-8111-111111111111",
    "issuer": "https://identity.example.invalid/realm",
    "audience": "saintvision-api",
    "client_ids": ["approved-web-client"],
    "jwks_file": "/run/saintvision/jwks.json"
  },
  "allowedOrigins": ["https://studio.example.invalid"]
}
```

`jwks.json`은 관리자가 검증한 공개 RSA 키만 포함하는 로컬 신뢰 묶음이다. `{ "issuer": "동일 issuer", "expiresAt": 정수 Unix 시각, "keys": [RS256 공개 JWK] }` 형식이며 만료는 현재부터 7일 이내다. 실제 issuer/audience/client와 키 출처를 확인한 뒤 배포한다. 개인 키를 서버 설정 디렉터리에 넣지 않는다. 네트워크에서 임의 키를 자동 신뢰하지 않는다.

컨테이너 UID/GID `65532:65532`가 디렉터리를 탐색하고 파일을 읽을 수 있어야 한다. Linux 설정 파일은 일반 파일이고 group/other 쓰기 권한이 없어야 한다(예: 소유자 65532, 파일 0600, 디렉터리 0700). Windows Docker bind mount의 실제 접근 권한은 후보 컨테이너에서 별도로 확인해야 한다. 운영 키 파일에 일괄 chmod/chown을 적용하지 않는다.

환경을 안전하게 제공한 뒤 `docker compose -f docker-compose.prod.yml config --quiet`로 필수 설정을 검증한다. 실제 기동은 별도 운영 인수 단계다. 미설정 factory가 시작을 거부하거나 `/readyz`가 비정상이면 웹 서비스의 healthy 의존 조건을 충족하지 않는다. 기존 SQLite 개발 작업대의 로그인/예시 데이터를 운영 인증으로 옮기지 않는다.
