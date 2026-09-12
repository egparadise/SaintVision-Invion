# 정본 Control Plane 설정

`saintvision.server:create_app --factory`는 `inv.app.create_configured_app`를 호출한다. `/healthz`는 프로세스 생존, `/readyz`는 공개 키 신뢰 파일·비소유자 DB 역할·tenant·복구 epoch 접근을 확인한다. Workspace가 없으면 응답의 `workspaceAdmission`은 `not_configured`이며 실행 가능 판정으로 사용하지 않는다.

Compose는 자동 DB 초기화/마이그레이션/운영 로그인 생성을 수행하지 않는다. 먼저 운영 절차에 따라 schema와 tenant, 프로젝트 권한 및 복구 epoch를 준비해야 한다. 빈 PostgreSQL을 기동하는 것만으로 서버가 준비되지 않는다. 전체 스택 운영 인수는 별도다. 현재 migration은 pgvector 확장을 활성화하지 않는다. 모델 선택 이전 임의 벡터 차원을 고정하지 않는다.

필수 환경 변수:

- `INV_RUNTIME_DSN`: `inv_kernel` 권한을 가진 배포 전용 LOGIN. schema 소유자·superuser·BYPASSRLS 금지.
- `INV_BUSINESS_DSN`: 업무 서비스용 배포 전용 SQLAlchemy DSN. kernel DSN과 독립적이다. 업무 서비스 활성화 시 해당 서비스 권한이 필요하다.
- `INV_RECOVERY_EPOCH`: DB의 `inv.control_epoch`와 조정된 UUID.
- `INV_CONFIG_VOLUME`: 검증 도구로 사전에 준비한 전용 Linux 설정 volume. `/run/saintvision`에 읽기 전용으로 마운트하며 자동 생성하지 않는다.
- `POSTGRES_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`: 배포별 비밀. Git·공유 문서·명령 출력에 넣지 않는다.

준비할 설정 디렉터리의 `api.json`의 최소 형식(아래 값은 형식 설명이며 운영 인증 자료가 아님):

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

컨테이너 UID/GID `65532:65532`가 디렉터리를 탐색하고 파일을 읽을 수 있어야 한다. Linux 설정 파일은 일반 파일이고 group/other 쓰기 권한이 없어야 한다(예: 소유자 65532, 파일 0600, 디렉터리 0700). 이 서버의 Windows bind mount는 파일이0777로 노출되어 trusted_file 검사가 실제 거부했다. 아래 전용 Linux volume 준비 경로를 사용한다. 운영 키 파일에 일괄 chmod/chown을 적용하지 않는다.

환경을 안전하게 제공한 뒤 `docker compose -f docker-compose.prod.yml config --quiet`로 필수 설정을 검증한다. 실제 기동은 별도 운영 인수 단계다. 미설정 factory가 시작을 거부하거나 `/readyz`가 비정상이면 웹 서비스의 healthy 의존 조건을 충족하지 않는다. 기존 SQLite 개발 작업대의 로그인/예시 데이터를 운영 인증으로 옮기지 않는다.


## 후보 이미지와 Workspace 인수

`docker build -f deploy/Dockerfile.backend -t saintvision-backend-candidate:<source-sha> .`로 별도 후보 이미지를 만든다. 운영 컨테이너를 교체하기 전에 격리 PostgreSQL에 migration head를 적용하고 비소유자 로그인으로 `/readyz`와 권한별 `/v1/projects`를 검증한다.

추가 Docker 시험은 `tests/integration/test_server_container.py`다. 전용 폐기 클러스터의 `INV_TEST_ADMIN_DSN`, 후보 `INV_TEST_SERVER_IMAGE`, 후보 컨테이너에서 접근할 **그 시험 DB만의** `INV_CONTAINER_TEST_DB_HOST`(포트5432)를 명시해야 한다. 다른 클러스터 주소를 넣지 않는다. 시험별 난수 컨테이너/volume만 생성·제거한다. Linux volume UID65532/0600·읽기 전용 mount 경계 시험과 Windows bind mount 인수는 별개다.

Workspace 설정에는 `workingRoot`, `nodeId`, CPU·memory의 서로 다른 resource ID, digest로 고정한 sandbox profile, `policyVersion`, Ed25519 `signingKeyFile`, 명시적 TLS CA·client certificate·private key가 모두 필요하다. `workingRoot`는 Linux의 서비스 소유 개인 디렉터리여야 하며 쓰기 가능한 전용 영속 volume으로 준비한다. 시험의 tmpfs는 운영 영속 Workspace 대체물이 아니다. 서명 키와 TLS 개인 키는 소유자만 접근 가능해야 한다. 이 키들은 앞의 공개 identity trust 파일과 별도이며, 실제 운영 키는 인증된 전용 경로로 제공한다.

`workspaceAdmission: configured`는 설정을 읽었다는 뜻이다. `executionDispatcher: external-worker-required`이면 별도 dispatcher가 여전히 필요하다. 실제 Node의 mTLS, image/profile capability, 프로젝트 Node 소속, CPU·memory resource 등록, 승인·Lease·kill switch가 검증되기 전에는 실행 가능한 Node로 표시하지 않는다. 합성 profile/TLS와 메모리 resource ID를 쓰는 후보 기동 시험은 원격 작업 실행이나 영속 복구 시험이 아니다.


## 업무 API 활성화와 영속 volume 적용

실제 업무 factory는 `INV_BUSINESS_DSN`을 읽는다. `INV_DATABASE_URL`은 이 factory의 대체 변수가 아니다. DSN은 `postgresql+psycopg://` 형식으로 제공하고 runtime과 **같은 host/port/database 및 연결 옵션**을 사용한다. 로그인은 `inv_app` 구성원이면서 `inv_kernel` 구성원이 아닌 별도 비소유자 role이어야 한다. 같은 JWT라도 등록된 public.users의 subject만 업무 계정으로 인정한다. 자동 사용자 등록이나 토큰의 임의 역할 부여는 없다.

`api.json`에 `"business": true`를 추가하면 업무 API를 활성화한다. 프로젝트가 생성되어도 `kernelLinked=false`일 수 있으며, 운영자의 계정·프로젝트 연결 전에는 Run 생성을 거부한다. Workspace 생성과 실제 실행 가능 상태는 별개다.

영속 편집 루트는 선택 overlay `docker-compose.workspace.yml`에서 `/workspaces`에 연결한다. 사전 준비된 외부 Linux volume 이름을 `INV_WORKSPACE_VOLUME`으로 지정하고 설정의 `workingRoot`를 `/workspaces`로 맞춘다. Compose가 새 volume을 자동 생성하거나 기존 폴더 소유권을 변경하지 않는다.

```powershell
docker compose -f docker-compose.prod.yml -f docker-compose.workspace.yml config --quiet
```

준비한 volume의 owner65532:65532/mode0700, 백업·복원 경로를 확인한 후 후보에 적용한다. 컨테이너 재시작 후 파일 보존은 기본 인수 조건이며, 실제 편집 API·Step/PTY·Node mount·분산 복구 인수는 추가로 필요하다.


## Windows에서 설정 volume 준비

`tools/prepare_server_config.py`는 api.json과 그 안에서 참조하는 공개 신뢰 키·Workspace 서명 키·TLS 파일만 새 Linux volume으로 옮긴다. 참조 경로는 `/run/saintvision/<파일명>` 형식이며 실제 파일은 입력 디렉터리 바로 아래에 둔다. 다른 파일이나 외부 경로는 복사하지 않는다. 후보 이미지의 **sha256 image ID**를 명시한다.

```powershell
python tools/prepare_server_config.py --directory <보호된-설정-디렉터리> --volume <새-volume-이름> --image sha256:<검증한-이미지-ID>
```

복사 바이트 hash·owner65532·0600·현재 identity 신뢰 묶음을 컨테이너에서 검증한다. 실패하면 이번에 만든 volume만 정리하고, 기존 volume·입력 파일은 보존한다. 성공 receipt의 volume 이름을 `INV_CONFIG_VOLUME`에 지정한다. 이 도구는 서버 기동·DB 수정·Workspace 실행을 하지 않는다. 설정 변경 시에도 새 volume을 검증한 후 전환하며, 기존 운영 volume을 덮어쓰지 않는다. Workspace 개인키의 실제 용도·mTLS 유효성은 후보 서버 기동/Node 연결 단계에서 별도로 검증된다.

업무 API의 인증 헤더 누락은 이제401/WWW-Authenticate: Bearer로 커널 및 실제 OIDC 거부와 일치한다. 인증된 사용자의 프로젝트 실행 권한 부족은403을 유지한다.
