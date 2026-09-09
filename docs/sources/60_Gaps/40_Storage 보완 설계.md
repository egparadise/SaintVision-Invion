---
title: Storage 보완 설계
updated: 2026-09-09
status: proposed
author: Claude
---

# Storage 보완 설계

## 이 문서가 메우는 공백

기존 설계는 `inv://` 네임스페이스와 단계적 로드맵을 정했지만, **실제로 어떻게 저장하고 읽는지가 없다**. 제품 선정, 버킷 구조, URI 해석 규칙, 업로드 프로토콜, GC가 모두 비어 있다.

가장 심각한 것은 **Dataset 지역성**이다. 데이터 지역성은 Scheduler 점수 함수에서 가장 큰 가중치를 갖는 입력이고 설계 원칙 6번("Data locality first")의 근거인데, 데이터셋 등록·복제·캐시 무효화 메커니즘이 한 줄도 설계되어 있지 않다. 이것이 없으면 Scheduler는 `data_locality` 항을 계산할 수 없다.

## 1. 제품 선정

| 용도 | 선택 | 근거 |
|---|---|---|
| Object Storage | **MinIO** | S3 호환. 온프레미스 단일 노드 배포가 간단하고, 나중에 분산 모드로 확장 가능. 기존 설계의 "S3 호환 Artifact Store" 요구를 충족 |
| Node Local Cache | 파일시스템 + SQLite 인덱스 | Node Agent가 Go 단일 바이너리이므로 외부 의존성을 늘리지 않는다 |
| 비밀·민감 원문 | MinIO 별도 버킷 + 봉투 암호화 | §7 참조 |
| 백업 대상 | MinIO 별도 버킷 (WAL 아카이브, `pg_basebackup`) | |

배포 위치는 기존 설계의 토폴로지 그대로 **Storage Node 또는 NAS 1대**다.

## 2. 버킷과 키 레이아웃

### 버킷

| 버킷 | 내용 | 버저닝 | 수명주기 |
|---|---|---|---|
| `inv-artifacts` | Run 산출물, 테스트 리포트, diff, 빌드 결과 | 켬 | 90일 후 삭제 |
| `inv-datasets` | 등록된 Dataset의 정본 사본 | 켬 | 수동 |
| `inv-models` | Model Version 바이너리 | 켬 | 수동 |
| `inv-logs` | Run 로그 번들 (압축) | 끔 | 90일 후 삭제 |
| `inv-secrets` | 암호화된 민감 원문 | 켬 | 정책별 |
| `inv-backups` | DB 백업, WAL | 끔 | 35일 |

### 키 템플릿

```
inv-artifacts/{tenant}/{projectId}/{runId}/{artifactId}[.ext]
inv-datasets/{tenant}/{datasetId}/{versionId}/{relativePath}
inv-models/{tenant}/{modelId}/{versionId}/{fileName}
inv-logs/{tenant}/{projectId}/{runId}/{stepId}.jsonl.zst
inv-secrets/{tenant}/{secretRefId}/{version}.enc
```

`{tenant}`를 최상위에 두는 이유: 테넌트 단위 IAM 정책(`arn:aws:s3:::inv-artifacts/tenant-a/*`)을 접두사로 걸 수 있고, 나중에 테넌트별로 버킷을 분리할 때 이관이 단순하다.

## 3. `inv://` URI 해석 규칙 (착수 차단 항목)

기존 설계는 `inv://datasets/echo-v3`, `inv://models/...`, `inv://artifacts/...` 네임스페이스를 정했지만 **이것을 어떻게 실제 객체로 바꾸는지**가 없다. `WorkloadSpec`의 `data.mounts[].source`가 이 URI를 쓰므로, 해석기가 없으면 Workload를 실행할 수 없다.

### 문법

```
inv://<namespace>/<name>[@<version>][/<subpath>]

namespace := datasets | models | artifacts | workspaces
name      := [a-z0-9]([a-z0-9-]*[a-z0-9])?
version   := semver | "latest"
subpath   := 슬래시로 구분된 상대 경로
```

예:
```
inv://datasets/echo-v3                    → 최신 버전 전체
inv://datasets/pacs@3.0.0                 → 고정 버전
inv://datasets/pacs@3.0.0/train           → 버전 내 하위 경로
inv://models/qwen-med@1.2.0/weights.safetensors
inv://artifacts/run_01JXXX/test-report
```

### 해석 절차

```
1. 파싱 및 검증
   - namespace 화이트리스트 확인
   - subpath 정규화 후 ".." 탈출 차단 (경로는 정규화한 절대 경로로 검증)
2. 이름 → ID 조회
   - datasets: name + tenant → dataset_id
3. 버전 해석
   - @latest 또는 생략 → 최신 active 버전으로 해석
   - **해석 결과를 RunRecord에 불변으로 기록한다**
4. 권한 확인
   - 요청 주체가 해당 Dataset에 대한 read 권한 보유 확인
   - data_class가 Restricted면 추가 정책 검사
5. DataLocation 선택
   - 대상 Node에 캐시 복제본이 있으면 그것을, 없으면 정본을 반환
6. 물리 참조 반환
   - {bucket, key, checksum, size, cached_on_node}
```

**3단계가 중요하다.** 기존 설계의 "`latest` 같은 움직이는 값만 저장하지 않는다" 원칙에 따라, `@latest`로 제출된 Workload도 실행 시점에 구체 버전으로 고정되어 `run_records.context_bundle_hash`와 함께 기록된다. 그래야 같은 Run을 재현할 수 있다.

### 해석 실패 처리

| 상황 | 오류 |
|---|---|
| 알 수 없는 namespace | `VAL-*` |
| 이름 없음 | `VAL-*` |
| 버전 없음 | `VAL-*` |
| 권한 없음 | `AUTH-*` (존재 여부를 노출하지 않도록 404가 아닌 403) |
| Checksum 없이 active 상태 | `VAL-*` — 불변 조건 "DataLocation은 Checksum과 접근 정책 없이 active가 될 수 없다" |

## 4. Dataset 지역성 (파일럿 차단 항목)

Scheduler 점수 함수의 주 입력인데 설계가 전무한 부분이다.

### 데이터 모델

```sql
CREATE TABLE datasets (
  id          inv_id PRIMARY KEY,
  tenant_id   uuid NOT NULL,
  name        text NOT NULL,
  data_class  text NOT NULL,     -- public | internal | confidential | restricted
  owner_id    inv_id NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name)
);

CREATE TABLE dataset_versions (
  id            inv_id PRIMARY KEY,
  dataset_id    inv_id NOT NULL REFERENCES datasets(id),
  version       text NOT NULL,
  checksum      char(71) NOT NULL,      -- 'sha256:' + 64
  total_bytes   bigint NOT NULL,
  file_count    integer NOT NULL,
  status        text NOT NULL DEFAULT 'staging',  -- staging | active | archived
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (dataset_id, version),
  -- 불변 조건: Checksum 없이 active 불가
  CHECK (status <> 'active' OR checksum IS NOT NULL)
);

CREATE TABLE data_locations (
  id                 inv_id PRIMARY KEY,
  dataset_version_id inv_id NOT NULL REFERENCES dataset_versions(id),
  node_id            inv_id REFERENCES nodes(id),   -- NULL이면 Object Storage 정본
  kind               text NOT NULL,   -- primary | replica | cache
  status             text NOT NULL,   -- populating | ready | stale | evicted
  local_path         text,
  bytes_present      bigint NOT NULL DEFAULT 0,
  verified_checksum  char(71),
  last_verified_at   timestamptz,
  last_accessed_at   timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (dataset_version_id, node_id)
);

CREATE INDEX idx_dataloc_lookup
  ON data_locations (dataset_version_id, status)
  WHERE status = 'ready';

CREATE INDEX idx_dataloc_eviction
  ON data_locations (node_id, last_accessed_at)
  WHERE kind = 'cache' AND status = 'ready';
```

### Scheduler가 읽는 실제 쿼리

`data_locality` 점수를 계산할 때 후보 Node별로 이 쿼리 하나를 돈다.

```sql
SELECT
    n.id AS node_id,
    COALESCE(SUM(dv.total_bytes) FILTER (
      WHERE dl.status = 'ready' AND dl.node_id = n.id
    ), 0) AS local_bytes,
    COALESCE(SUM(dv.total_bytes), 0) AS required_bytes
FROM nodes n
CROSS JOIN dataset_versions dv
LEFT JOIN data_locations dl
       ON dl.dataset_version_id = dv.id AND dl.node_id = n.id
WHERE n.id = ANY($1::text[])          -- hard filter 통과한 후보 Node
  AND dv.id = ANY($2::text[])         -- Workload가 요구하는 Dataset 버전
GROUP BY n.id;
```

점수:

```
data_locality = local_bytes / NULLIF(required_bytes, 0)      -- 0..1
estimated_transfer_time = (required_bytes - local_bytes) / effective_bps
```

`effective_bps`는 `network_links` 테이블의 측정된 대역폭에서 온다. 1GbE와 10GbE 노드가 섞인 환경에서 이 값이 배치를 크게 바꾼다.

### 복제 트리거

복제는 자동으로 무한정 하지 않는다. 기존 설계가 "기존 사용자 Folder는 명시적 제공 없이 자동 포함하지 않는다"는 비침해 원칙을 갖고 있고, 5노드 LAN에서 대형 데이터셋을 모든 노드에 복제하면 디스크와 대역폭이 낭비된다.

복제하는 경우:

1. **명시적 요청** — `WorkloadSpec.placement.preferDataLocality: true`이고 선택된 Node에 데이터가 없을 때, Run 시작 전 `populating` 단계에서 가져온다
2. **접근 빈도** — 최근 7일간 같은 Dataset 버전이 특정 Node에서 3회 이상 사용되면 캐시로 승격
3. **사전 배치** — 관리자가 `POST /v1/dataset-versions/{id}/replicas`로 지정

복제하지 않는 경우: `data_class = 'restricted'`인 Dataset은 **명시적 정책 승인 없이 복제하지 않는다.** 의료 원본이 여러 노드로 퍼지는 것을 막는다.

### 캐시 무효화

**체크섬 기반**이다. 시간 기반 TTL을 쓰지 않는다 — Dataset 버전은 불변이므로 만료 개념이 없고, 대신 "내가 가진 것이 정말 그것인가"만 확인하면 된다.

```
1. Node Agent가 캐시 사용 전 verified_checksum과 dataset_versions.checksum 비교
2. 불일치 → status = 'stale', 즉시 재다운로드
3. 주기 검증: 캐시 항목당 7일마다 백그라운드 체크섬 재계산
4. 부분 파일(bytes_present < total_bytes) → 'populating'으로 유지, ready로 승격하지 않음
```

### 캐시 축출

```
정책: LRU + 노드별 캐시 크기 상한 (기본: 제공 스토리지의 60%)

축출 대상에서 제외:
  - kind = 'primary' (정본)
  - 활성 Lease가 참조 중인 항목
  - status = 'populating'

축출 순서: last_accessed_at 오름차순
```

축출은 Node Agent가 로컬에서 판단하고 결과를 Control Plane에 보고한다. 중앙에서 지시하면 네트워크 단절 시 디스크가 가득 찬다.

### 대역폭 예약

기존 설계가 "Bandwidth 예약, 전송 Checksum, 재개 가능한 Copy 지원"을 요구한다.

- Node별 동시 전송 수 상한 (기본 2)
- 전송당 대역폭 상한 — Host 사용자 부하가 임계값을 넘으면 자동 조절. "기존 운영체제, 사용자 파일과 일상 작업을 침해하지 않는다"는 제품 경계의 구현
- Control Traffic과 Data Transfer를 논리적으로 분리 (기존 설계 그대로)

## 5. 아티팩트 전송 프로토콜

기존 설계는 "아티팩트 무결성 해시와 전송 재개", "대형 Artifact" 성능 테스트만 언급한다.

### 업로드 (Node Agent → Storage)

```
1. POST /v1/runs/{runId}/artifacts
   → {artifactId, uploadUrls: [...], partSize, expiresAt}
2. 멀티파트 업로드 (파트 크기 16MiB)
   - 각 파트를 presigned PUT으로 직접 MinIO에 전송 (Control Plane을 경유하지 않음)
   - 실패한 파트만 재시도 → 재개 가능
3. POST /v1/runs/{runId}/artifacts/{artifactId}/complete
   Body: {parts: [{partNumber, etag}], sha256, sizeBytes}
4. Control Plane이 검증
   - MinIO에서 객체 메타데이터 조회, 크기 대조
   - sha256 대조 → 불일치 시 객체 삭제 + TOOL-* 오류
5. artifacts 테이블에 기록, EvidenceEnvelope의 output.artifactRef로 연결
```

**presigned URL로 Control Plane을 우회하는 것이 핵심이다.** 대형 아티팩트가 API 서버 메모리와 대역폭을 통과하면 `P95 읽기 300ms` SLO가 무너진다.

| 항목 | 값 |
|---|---|
| 파트 크기 | 16 MiB |
| 최대 아티팩트 크기 | 50 GiB (초과 시 Dataset으로 등록 권장) |
| presigned URL TTL | 업로드 1시간 / 다운로드 15분 |
| 동시 파트 | 4 |
| 체크섬 | SHA-256 필수. 클라이언트 계산 + 서버 검증 |

### 다운로드

```
POST /v1/artifacts/{artifactId}/download-url
→ {url, expiresAt, sha256, sizeBytes}
```

권한 검사는 URL 발급 시점에 한다. presigned URL은 15분 후 만료되므로 유출되어도 노출 창이 짧다. **URL 자체를 로그에 기록하지 않는다** — 서명이 포함되어 있다.

## 6. 볼륨, GC, 쿼터

### Workspace 볼륨

기존 설계의 "ephemeral workspace와 persistent volume 분리"를 구현한다.

| 종류 | 위치 | 수명 | 용도 |
|---|---|---|---|
| ephemeral | Node 로컬 `/{invRoot}/ws/{wsId}/scratch` | Run 종료 시 삭제 | 빌드 산출물, 임시 파일 |
| persistent | Node 로컬 `/{invRoot}/ws/{wsId}/data` | Workspace 삭제 시 | 소스 코드, 설정 |
| dataset mount | 캐시 경로를 **읽기 전용 바인드 마운트** | 캐시 수명 | Dataset |

Dataset 마운트가 읽기 전용인 것이 중요하다. `WorkloadSpec`의 `mode: readOnly`를 파일시스템 층에서 강제해, 실행 중인 코드가 캐시를 오염시킬 수 없게 한다.

### GC

| 대상 | 조건 | 주기 |
|---|---|---|
| ephemeral 볼륨 | Run 종료 후 즉시 | 이벤트 기반 |
| 고아 ephemeral | 참조하는 Run이 없고 24시간 경과 | 매시 |
| 고아 아티팩트 | Object Storage에 있으나 DB 레코드 없음 | 매일 |
| 만료 아티팩트 | 90일 경과 | MinIO 수명주기 정책 |
| 축출된 캐시 | LRU 정책 | 노드별 상시 |
| 미완료 멀티파트 업로드 | 7일 경과 | MinIO 수명주기 정책 |

고아 아티팩트 GC는 **DB를 정본으로 삼는다.** Object Storage에만 있고 DB에 없는 객체를 지운다. 반대(DB에 있고 Storage에 없음)는 지우지 않고 알람을 올린다 — 데이터 유실 신호다.

### 쿼터 집행

| 축 | 한도 | 집행 지점 |
|---|---|---|
| Node 제공 스토리지 | `StorageContribution.offered` | Node Agent (쓰기 전 확인) |
| Workspace 볼륨 | 프로젝트 정책 | Node Agent (컨테이너 쿼터) |
| 프로젝트 아티팩트 총량 | 정책 | Control Plane (업로드 URL 발급 시) |
| 캐시 | 제공 스토리지의 60% | Node Agent (LRU 축출) |

## 7. StorageContribution — 사용자 폴더 등록

기존 설계의 "사용자 허용 폴더를 `StorageContribution`으로 등록", "기존 사용자 Folder는 명시적 제공 없이 자동 포함하지 않는다", "OS partition 전체를 자동 편입하지 않는다"를 구현한다.

### 등록 흐름

```
1. Host 소유자가 로컬에서 폴더 선택 (Node Agent UI 또는 설정 파일)
2. Node Agent가 검증
   - 절대 경로로 정규화
   - 차단 목록과 대조 (아래)
   - 심볼릭 링크 해석 후 재검증 — 링크로 차단 목록을 우회할 수 없게
   - 쓰기 권한 확인
3. Control Plane에 등록 요청 (L2 — 관리자 승인)
4. 승인 후 StorageContribution 활성화
```

### 기본 차단 목록

거버넌스 문서의 "호스트 홈, SSH 키, 시스템 폴더, 브라우저 프로필 기본 차단"을 구체화한다.

```yaml
denied_roots:
  windows:
    - "C:/Windows"
    - "C:/Program Files"
    - "C:/Program Files (x86)"
    - "C:/ProgramData"
    - "C:/Users/*/.ssh"
    - "C:/Users/*/.aws"
    - "C:/Users/*/.kube"
    - "C:/Users/*/AppData/Roaming/Microsoft/Credentials"
    - "C:/Users/*/AppData/Local/Google/Chrome/User Data"
    - "C:/Users/*/AppData/Roaming/Mozilla/Firefox/Profiles"
  linux:
    - "/etc"
    - "/boot"
    - "/proc"
    - "/sys"
    - "/dev"
    - "/root"
    - "/home/*/.ssh"
    - "/home/*/.aws"
    - "/home/*/.gnupg"
    - "/var/lib/docker"
rules:
  - 드라이브·파티션 루트 전체 등록 금지 (C:/, /)
  - 사용자 홈 디렉터리 자체 등록 금지 (하위 폴더는 가능)
  - 심볼릭 링크·정션 해석 후 재검증
  - 최대 등록 깊이·개수 제한
```

`WorkloadSpec.constraints.deniedPaths`의 `C:/Users/{user}/.ssh`가 예시로만 있던 것을 완전한 목록으로 확장했다.

## 8. 비밀과 민감 원문 저장소

공통 계약은 "민감한 원문과 비밀값은 Evidence에 넣지 않는다. 원문이 필요하면 **암호화된 별도 저장소**에 두고 Evidence에는 참조와 해시만 기록한다"고 요구하지만, 그 저장소의 실체가 없다.

### 구성

```
inv-secrets/{tenant}/{secretRefId}/{version}.enc
```

**봉투 암호화(envelope encryption)**:

1. 객체마다 데이터 키(DEK, AES-256-GCM) 생성
2. DEK로 원문 암호화
3. DEK 자체를 마스터 키(KEK)로 암호화해 객체 메타데이터에 저장
4. KEK는 **OS credential store 또는 Vault Adapter**에 보관 (기존 설계의 Secret Provider)

이렇게 하면 KEK 교체 시 모든 객체를 재암호화하지 않고 DEK만 재봉인하면 된다.

### 접근 규칙

- 복호화는 **정책 결정을 통과한 Run 컨텍스트에서만** 가능
- 원문은 실행 직전 대상 프로세스에 주입하고, Run 종료 시 폐기 (기존 설계 그대로)
- **환경변수보다 파일 또는 메모리 기반 주입을 우선** — 환경변수는 `/proc/{pid}/environ`과 크래시 덤프에 남는다
- 운영자는 원문을 볼 수 없어도 **참조 사용 이력은 감사할 수 있어야 한다** — `evidence_envelopes`에 `secretRef` 사용 기록만 남긴다
- 의심 유출 시 자동 폐기·회전·관련 실행 격리

## 9. 의료 데이터 (DICOM) 처리 경로

파일럿 도메인이 PACS인데 기존 설계 전체에 개인정보·의료정보 규제 언급이 없다. **규제 적용 여부는 이 문서가 판단하지 않는다.** 기술적 처리 경로만 제시한다.

### 데이터 등급

DICOM 원본은 거버넌스 문서의 **Restricted** 등급에 해당한다("비밀값, 개인정보, 의료 원본 → 격리, 강한 감사, 외부 모델 전송 기본 금지").

### 처리 경로

```
PACS/DICOM 원본
   ↓  [inv-datasets, data_class = restricted]
   ├─ 복제 금지 (명시적 정책 승인 없이 노드 간 이동 없음)
   ├─ 읽기 전용 마운트만
   ↓
비식별화 파이프라인 (별도 Run, L2 승인)
   ├─ DICOM 태그 제거·치환 (환자 ID, 이름, 생년월일, 기관명, 촬영일시)
   ├─ 번인(burned-in) 텍스트 마스킹
   ├─ UID 재생성 (원본 UID와의 매핑은 별도 암호화 저장)
   ↓
비식별 Dataset [data_class = confidential]
   └─ 여기서부터 일반 학습·평가 파이프라인 사용 가능
```

### 강제 지점

- **Context Assembler**: `data_class = restricted` 항목은 외부 모델 프로바이더로 나가는 ContextBundle에 포함하지 않는다. 기존 설계의 "컨텍스트 구성기는 데이터 등급과 모델·도구의 처리 위치를 비교하여 허용되지 않은 전송을 차단해야 한다"를 구현하는 지점이 여기다
- **Tool Gateway**: Restricted 데이터를 다루는 도구는 네트워크 egress를 차단한다
- **Scheduler**: Restricted Dataset을 요구하는 Workload는 해당 데이터가 이미 있는 Node로만 배치한다 (전송 자체를 막는다)
- **Evidence**: DICOM 원본 내용을 절대 기록하지 않는다. 참조와 해시만

### 명시적 위험 기록

기존 설계가 PACS·DICOM·MONAI·pydicom을 파일럿 전제로 삼으면서 HIPAA/GDPR/개인정보보호법/의료기기 규제를 한 번도 언급하지 않은 것은 **공백으로 기록해 둔다.** "의료기기 소프트웨어 규제 범위"는 기존 설계에서 "확장 시 재검토할 결정"으로 미뤄져 있으나, 파일럿이 실제 환자 데이터를 다룬다면 파일럿 전에 판단이 필요하다. 법무·규제 검토 항목이다.

## 10. MLflow 연동

기존 설계는 MLflow를 MLOps 후보로 정했으나 저장소 연결이 없다.

| MLflow 구성 | 연결 대상 |
|---|---|
| Tracking backend store | Control Plane PostgreSQL (별도 스키마 `mlflow`) |
| Artifact store | `inv-artifacts` 버킷의 `{tenant}/{projectId}/mlflow/` 접두사 |
| Model registry | MLflow 자체 + `model_versions` 테이블에 미러 |

MLflow의 artifact store를 같은 MinIO에 두면 INV의 아티팩트 GC 정책과 충돌할 수 있다. **MLflow 접두사는 GC 대상에서 제외**하고 MLflow 자체 수명주기를 따른다.

기존 설계의 "Model Version은 Dataset Version, Code Commit, Parameter, Runtime Image, Hardware Profile, Metrics와 Evaluation Evidence를 참조해야 승인 가능하다"는 조건은 MLflow가 아니라 `model_versions` 테이블에서 검증한다 — 배포 승인은 INV의 정책 엔진이 소유한다.

## 11. 5단계 로드맵

[[00_보완 설계 종합 요약]] §4 정본표 #10에 따라 5단계로 통합한다. 괄호는 기존 3단계 문서와의 매핑.

| 단계 | 내용 | 대응 |
|---|---|---|
| 1 | 메타데이터와 위치 카탈로그. `datasets`, `dataset_versions`, `data_locations` 등록만. 실제 전송 없음 | (1단계) |
| 2 | 읽기 전용 원격 접근. MinIO 정본에서 직접 읽기, Node 로컬 캐시 없음 | (2단계) |
| 3 | 선택적 복제와 캐시. §4의 복제 트리거·무효화·축출 전부 | (2단계) |
| 4 | Object Gateway. presigned URL, 멀티파트, 대역폭 예약 | (3단계) |
| 5 | 분산 파일시스템 Adapter 평가 (Ceph, SeaweedFS). **필요성이 검증된 뒤에만** | (3단계) |

MVP는 **3단계까지**다. 4단계의 presigned URL은 아티팩트 업로드에 먼저 필요하므로 §5는 예외적으로 앞당겨 구현한다.

## 12. 운영 점검

| 주기 | 항목 |
|---|---|
| 상시 | 캐시 사용률, 전송 대역폭, 미완료 업로드 수 |
| 매일 | 고아 아티팩트 GC 결과, 체크섬 검증 실패 건수 |
| 매주 | 백업 복원 스모크 테스트, 캐시 적중률 |
| 매월 | 버킷별 용량 추이, 수명주기 정책 적용 확인 |
| 분기 | 복원 훈련(RTO 1시간 실측), StorageContribution 재검토 |

**체크섬 검증 실패는 1건이라도 즉시 알람**을 올린다. 데이터 손상이거나 캐시 오염이며, 둘 다 학습 결과를 조용히 망친다.

## 관련 문서

- [[00_보완 설계 종합 요약]]
- [[20_Backend 보완 설계]]
- [[30_DB 보완 설계]]
- [[기술 문서]]
- [[시스템 스키마]]
- [[보안 평가 운영 가이드]]

---
> 본 문서는 Claude가 분석·설계·작성했습니다.
> 작성 일시: 2026-09-09 14:29 (Asia/Seoul)
