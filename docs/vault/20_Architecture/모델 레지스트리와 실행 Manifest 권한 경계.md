---
doc_id: "ARCH-MODEL-REGISTRY-BOUNDARY-001"
title: "모델 레지스트리와 실행 Manifest 권한 경계"
version: "1.9.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-22T20:06:08+09:00"
source_of_truth: "Git"
---

# 모델 레지스트리와 실행 Manifest 권한 경계

## VF-CX-02 / VF-CL-03 결정

현재 두 저장 구조를 유지한다. 목적과 권한이 다르며 이름·버전·checksum이 같다는 이유로 자동 결속하지 않는다. 영구 분리 결정이 아니라 명시적 결속 계약과 검증이 생길 때까지의 경계다.

| 구조 | 책임 | 보증하지 않는 것 |
|---|---|---|
| public.models/model_versions/lineage | S10 모델 등록·업무 버전·평가/승인 추적 | 커널 manifest 존재, 현재 bytes 일치, 실행 permit |
| inv.model_manifests/model_shard_locations | tenant/project/model/version별 불변 실행 manifest, source Run 및 DataLocation 버전 참조, 커밋 당시 full-byte 검증 | S10 released 상태, 현재 복제본 가용성, 새 실행 권한 |

inv_app의 커널 테이블 권한을 확장하지 않는다. 공개 조회가 필요하면 커널의 현재 사용자·프로젝트 인가를 거친 API로 최소 메타데이터를 제공한다. 커밋 요약 GET은 아래1.1.0에 정의한다. ModelVersion의 명시적 불변 결속은 아래1.4.0 내부 worker service로 제공한다. HTTP·runtime permit 연결은 아직 없다.

## 정책 필드와 후속 결속 합격 조건

- 커널 manifest의 licensePolicy/classification은 이미 존재하며 manifest digest에 포함되는 불변 선언이다. licensePolicy 문자열은 라이선스 허가를 자체 증명하지 않는다.
- Claude의 registry 정책 필드는 업무 metadata로 추가할 수 있으나 커널 값이나 기존 커밋을 자동 수정하지 않는다. 두 값이 다르거나 결속이 없으면 UI는 연결 미확인으로 표시한다.
- 후속 명시적 결속은 현재 tenant/project 인가, registry의 정확한 version ID, 커널 (tenant,project,model,version,manifest_sha256), 내용 식별 및 정책 적합성 검증을 요구한다. 결속 레코드의 불변성·동시 변경 방어·최소 권한을 별도 migration/시험으로 검토한다.
- 식별자/URI 문법이 두 체계에서 다를 수 있으므로 문자열 동등성이나 URI 해석만으로 FK 관계를 만들지 않는다. checksum 일치도 정책/권한 승인을 대체하지 않는다.
- 등록/결속/조회와 실행 인가는 별도다. 실행은 현재 승인·lease/fence·Node와 bytes 재검증을 유지한다.

## 독립 검토 정정

Claude 5189365의 shard 상한 finding은 reviewed SHA d6d9d87에서도 JSON Schema의 maxItems=1024와 manifest_copy 첫 단계 validate_contract에 의해 이미 거부된다. 1025개는 DB CHECK까지 도달하기 전에 VAL-0002/422가 된다. 런타임에 중복 상수를 추가하지 않고 경계 회귀시험으로 보호한다. shard_index 0..1023과 일치한다.

0039 이전 분기 문제는 현재 후보116e6e5의 단일0043 migration 체인에서 확인한다. 운영DB의 upgrade 완료를 의미하지 않는다. 기존 Claude 검토의 storage ready 상태와 locality verified_nodes는 동등하지 않다. 후자는 현재 Node/epoch/프로젝트·bytes 검증 등 추가 조건을 요구하므로 ready 행만으로 실행 가능을 표시하지 않는다.

실제 검증과 인계: [[2026-09-15_VF-MODEL-REVIEW_Codex]]. 후속 변경의 독립 재검토는 Claude, API·결속 구현은 Codex/Claude 각 owner 카드로 진행한다.


## 커밋 요약 조회 (1.1.0)

GET /v1/projects/{project}/models/{model_id}/versions/{version}/commitment

- canonical inv.app 경로다. storage business router나 inv_app 직접SQL을 통해 kernel 테이블을 열지 않는다. 별도 worker root/verifier 설정이 필요 없다.
- 현재 검증 principal의 tenant·subject로 kernel can_request grant와 linked business project/user/member의 요청권한을 교차 확인한다. project link가 없는 legacy fallback은 허용하지 않는다. SHARE 잠금을 기존 grant→business 순서로 transaction 종료까지 유지한다.
- model_id는 ModelId Schema, version은 불변문법/64자 상한이며 latest/current/head를 거부한다. 최신버전 자동선택은 하지 않는다.
- 현재권한없음403, 인증없음/위조401, 유효한scope에 해당model/version 없음404. 저장된manifest Schema/연속shard/전체길이·digest 불일치는409 MODEL-0001, 저장원문을 오류에 반사하지 않는다.
- 응답은 ModelCommitObservation Schema다. projectId/modelId/version/manifestHash/sourceRunId/committedAt/commitRecoveryEpoch/format/totalBytes/shardCount/licensePolicy/classification/committed=true를 제공한다.
- currentAvailability=unknown, requiresExecutionRevalidation=true. committedAt은 DB의 과거커밋시각이고commitRecoveryEpoch도 당시epoch다. 조회시각/현재epoch·새bytes검증으로 표시하지 않는다. 과거node상태나만료lease가조회기록을새실행허가로바꾸지않는다.
- 저장JSON의자체일관성과기록된digest를대조한다. 데이터베이스관리자의원문+digest동시위조를독립서명으로검증하는API는아니다.
- shard/replica 상세/nodeId/locationId/root경로/keyRef/worker설정은응답에없다. HTTP cache-control:no-store를유지한다. 조회로commit/idempotency/Run상태/실파일을변경하지않는다.
- licensePolicy는불변선언이지실제라이선스허가판정이아니다. 공개ModelVersion자동결속/배포/다운로드/현재실행가능판정은여전히후속이다.

검증및인계: [[2026-09-15_VF-MODEL-OBSERVATION_Codex]]. Gemini Model Studio는정확한project/model/version을선택해과거커밋요약으로표시하고실행가능배지를이응답만으로만들지않는다.


## S10 배포 기록 승인·동시성 (1.2.0)

record_deployment는신뢰된내부호출자가제공한timezone-aware now의배포사실을등록하는metadata service다. 물리배포·kernel실행permit·현재프로젝트인가를대신하지않고새HTTP경로를열지않는다.

- 같은tenant/model_version에FOR UPDATE를획득한뒤stage와digest를읽는다. ORM identity cache를populate_existing으로새로고친다. 기존deployment행이없는최초동시등록도직렬화된다.
- 이어같은tenant approval을FOR SHARE로재조회해결정/digest및 decided_at <= now < expires_at을검사한다. 미래승인·만료시각포함·거절결정은수용하지않는다. now는기록대상시각이며현재실행권한만료검사의대체가아니다.
- 같은tenant/version/environment의기존active행은모두superseded로바꾸고새active행하나를같은transaction에기록한다. 기존0004의부분고유index도같은범위의active중복을거부한다. 다른version/environment의상태는바꾸지않는다.
- 기존DB고유제약은유지하며service잠금은동시등록이고유제약예외로실패하지않고직렬대체되도록한다. 원시SQL직접쓰기권한이나운영DB정리를추가하지않았다. 운영사용자·승인scope·실제배포성과확인은별도kernel절차가필요하다.

실제실패재현/동시transaction검증은 [[2026-09-15_VF-DEPLOYMENT-GUARD_Codex]]. Claude독립재검토대상이다.


## Claude option A 수신 판정 (1.3.0)

1834ee3의 model_id/version/URI 안정성 시험과 정책선언 소유자를 kernel로 유지하는 방향을 수신했다. 이는 registry→kernel의 권한있는 명시적 결속을 구현하거나 증명한 것이 아니다. 동일 model/version은 프로젝트·tenant·manifestHash·registryVersionId·내용 식별을 생략하는 join key로 사용하지 않는다. public registry와 kernel은 기존 현재권한 API 경계를 유지한다. 자동read-through/배포인가를 추가하지 않았고 UI는 정확한 project/model/version의 과거관측만 제공한다. ModelManifestStore 내부 직접접근을 사용자권한검증의대체로사용하지않는다.


## 명시적 registry 결속 (1.4.0, VF-CX-02)

`ModelRegistryBindingStore.bind(principal, project, registry_version_id, model_id, version, manifest_hash=...)`는 명시적 identity의 불변 기록이다. 사용자 입력에서 policy를 받는 HTTP경로는 없고 운영자설정 `RegistryBindingPolicy`가 필수다.

- tenant/project는 현재 kernel can_request와 linked business 사용자/프로젝트 권한을 모두 확인한다. 재호출도 권한을 다시 확인한다.
- kernel manifest의 Schema·자체model/version·canonical SHA256과 호출자의 정확한hash를 대조한다. registry는 이름/version으로 자동검색하지 않고 정확한model_version_id로 선택한다. 두 체계의 model/version 문자열이 달라도 같은project·contentHash·totalBytes가 명시적으로 확인되면 결속할 수 있다.
- registry는 released, verified_at <= DB현재시각, retention_pinned_until > DB현재시각을 요구한다. licensePolicy/classification은 운영자허용 pair와 비교하고 policy version/내용hash도 불변 기록한다. 이 pair 허용은 법적라이선스검토/현재실행승인의 대체가 아니다.
- `public.model_registry_snapshot`은 명시tenant와 현재 inv.tenant_id가 일치할 때만 같은tenant/project/정확한version의 최소필드를 반환한다. public.models/model_versions의 SHARE잠금을 트랜잭션종료까지 유지해 stage/프로젝트/내용의 동시변경을 막는다. kernel에는 함수EXECUTE만 추가하고 public registry 전체SELECT/UPDATE는 추가하지 않는다. PUBLIC/inv_app EXECUTE 없음, 고정pg_catalog search_path.
- 0044의 inv.model_registry_bindings는 tenant RLS·FK·UPDATE/DELETE불가, tenant/project/registryVersionId당1개의 불변결속이다. 동시동일호출은 같은결과로 수렴하고 다른manifest 또는 policy로 재결속하면409 MODEL-0008. 정책전환/재결속은 별도새계약 없이 자동덮어쓰지 않는다.
- 응답 executionAuthorized=false/requiresExecutionRevalidation=true. 기존 manifest 관측조회와도 별도다. DB에 기록이 있다는 것만으로 retired/권한철회/정책변경을 무시할 수 없다.

### VF-CX-03 후속 입력 경계

현재 LocalModelObservation/ModelRuntimeStore/WorkloadSpec에는 registryBinding을 전달하지 않는다. 이 작업은 **실행권한을 구성할 identity 기반**을 구현한 것이며 end-to-end registry 실행인가 완료가 아니다. 후속에서는 binding을 정확한Run/예약/frozen manifest에 결속하고 승인대상 digest에 포함한 뒤, dispatch 시점의 현재policy/registry lifecycle/권한과기존fence·Node·bytes를 같은순서로 재검사해야 한다. 선택적 필드로 추가한 뒤 검사를 생략하는 호환경로를 두지 않는다.

### 원격 provider 후속 범위

현재 ConfiguredModelVerifier는 운영자소유 local ReadRoot만 지원한다. 사용자URL이나 registry URI를 네트워크경로로 자동해석하지 않는다. 원격provider의 최소계약은 기존 NodeChannels의 tenant/node/epoch/channelVersion/endpoint/certificate 고정, 트랜잭션밖의 제한된mTLS 스트림·byte/hash검증, 트랜잭션안의 channel/Location/권한 재확인이다. 임의redirect·무제한읽기·caller의verified플래그는 허용하지 않는다. provider완료/장비인수는 아직 미구현·미검증이며 .225의외부권한대기와 구분한다.

구현/실제PG증거와 다음담당: [[2026-09-18_모델레지스트리_명시결속_Codex]].

원격 읽기 공통 기반: inv.node_chunk.verified_chunk는 기존 NodeTransfer와 후속 provider가 공유할 bounded 응답 검증이다. Schema·encoded 길이 상한을 decode 전에 확인하고 요청 nonce/offset/size/digest, 정확한 bytes 길이·hash·canonical Base64를 검사한다. 빈/EOF초과 범위는 거부한다. 이 함수는 인증·channel 검증·전체 object hash·DB현재권한 재검사를 대신하지 않는다. NodeTransfer에 연결했으나 모델 원격 provider 자체는 아직 연결하지 않았다. 오프라인79시험통과, 실PG/장비 인수는 별도다.


## 원격 읽기 컴포넌트 (1.5.0)

ConfiguredRemoteModelReader는 명시 NodeTLSClient/ChannelProof/LocationSnapshot으로 unencrypted 32KiB 이하 모델을 읽는다. replica최대8개, 기존 TLS호출별40초상한·무재시도. tenant/epoch/채널/위치·manifest identity 사전검사, nonce/범위/길이/각replica와전체hash 검증을 수행한다. caller URL/relative_path 해석, 디스크저장, 실행인가 없음. 불변 RemoteModelBytes에 채널·위치snapshot을 보존해 후속 DB재검사 입력을 제공한다.

read component는 구현했으나 remote provider의 현재권한 DB통합과 ModelRuntimeStore 연결은 미구현이다. 기존 로컬 경로는 그대로이며 자동원격fallback이 없다. 후속 trusted worker가 snapshot 전 권한확인과 읽기 후 channel/Location/policy/registry/fence 재검사를 구현해야 실행에 연결할 수 있다. 106오프라인시험(합성loopback mTLS 포함), 실장비 인수 아님. [[2026-09-18_원격모델읽기_Codex]].


## 원격 권한 재검사와 frozen 입력 결속 후보 (1.6.0)

ModelRuntimeStore의 명시 remote reader 경로를 구현했다. 기존 Run/Node/resource/grant/Location capture 뒤 현재채널을 고정하고, 네트워크밖 transaction 경계 전후 snapshot을 비교한다. 채널 provenance는 불변 runtime locations와 model/source.json의 hash로 서로 결속하고 전체 snapshot inputSha256를 통해 기존 workload 승인digest에 포함한다. 원문 endpoint/relative_path를 실행 환경에 제공하지 않는다. 채널marker 일부삭제/전체삭제/변조의 local fallback은 거부한다. 원격 sourceMode를 idempotency payload에 포함한다.

승인 요청은 현재 business permission·channel, delivery/claim은 기존 Node/resource잠금 뒤 Node/Location/현재권한·channel·fence를 재검사한다. 네트워크는 DBtransaction 밖이며 implicit retry나 자동로컬fallback이 없다. RegistryVersion/policy/lifecycle 실행결속은 별도 남은 구현이다.

최초132오프라인통과/29실PG미실행으로보류했던후보를사용자제공PG16에서재검증했다. 신규원격6+기존runtime23+인접registry/locality/retry50=79passed/0skip, CAS fixture3건수정후모두통과. DB검증보류를해제하고integration반영판정, 독립검토/CI/운영인수는별도대기다. [[2026-09-18_원격모델권한결속_Codex]].


## 호출자 트랜잭션의 registry 재검사 (1.6.2)

ModelRegistryBindingStore.revalidate(conn, ...)는 이미 생성된 불변 결속만 허용한다. bind와 같은 현재 project/business 권한·manifest hash·운영자 policy·registry released/verified/retention 조건을 적용한다. 정확한 registryVersionId와 manifest identity를 요구하며 새 결속을 만들거나 기존 값을 수정하지 않는다. registry SHARE 잠금은 호출자 트랜잭션 종료까지 유지한다. 신뢰된 kernel 트랜잭션 안에서만 호출하며 network I/O를 포함하지 않는다.

실제 PG16에서 신규 7건과 기존 binding 16건을 파일별로 검증했다. 아직 ModelRuntimeStore/승인/dispatch에 연결하지 않았으므로 실행권한 결속 완료는 아니다. 다음 단계는 frozen binding hash와 Run 입력 결속, 현재 policy를 포함한 승인/delivery/claim 재검사다. [[2026-09-18_Registry_트랜잭션재검사_Codex]].


## Registry 실행권한 연결 (1.7.0)

기존 1.6.x의 후속 항목을 trusted worker 경로에 구현했다. 운영자는 Database에 명시 RegistryBindingPolicy를 주고 ModelRuntimeStore.prepare에 정확한 registry_version_id를 전달한다. BoundDatabase는 같은 policy를 전달한다. policy 설정 시 registry ID/기존 결속 누락은 거부하며, 명시 ID를 주었는데 policy가 없을 때도 거부한다. 이름·URI·hash로 자동 registry 조회하지 않는다.

읽기 전후 현재 결속/권한/registry stage·verified·retention·policy를 검사하고, canonical binding을 고정 model/registry.json에 포함한다. 전체 snapshot hash가 WorkloadSpec.modelInput.inputSha256와 action_digest에 들어가므로 승인 뒤 binding을 바꾸면 같은 승인으로 사용할 수 없다. 기존 immutable snapshot/schema를 재사용하며 DDL 변경은 없다.

승인 요청, ApprovalStore.dispatch(재호출 포함), DeliveryQueue, ToolGateway.claim은 현재 결속과 frozen bytes를 비교한다. 현재 registry SHARE 잠금은 각 실행 gate 트랜잭션 종료까지 유지한다. policy를 없애서 registry 입력을 kernel-only로 바꾸는 경로는 없다. policy 활성화 뒤 과거 미결속 입력도 거부된다. 승인 요청의 기존 replay는 과거 수신 결과일 뿐 새로운 실행인가가 아니며 dispatch/claim은 항상 다시 검사한다.

policy 미설정의 기존 kernel-only 실행은 registry 승인이라고 표시하지 않는다. 공개 HTTP 설정/운영자 정책 배포는 별도이며 모든 trusted worker가 일관된 현재 policy를 제공해야 한다. 실제 Node 실행/실장비 인수는 이 PG 검증 범위 밖이다. [[2026-09-18_Registry_실행권한결속_Codex]].


## 운영자 설정 연결 (1.8.0)

INV_API_CONFIG의 modelRegistryPolicy를 생산 factory가 읽어 승인/dispatch와 공유하는 Database에 전달한다. trusted_file의 크기·파일 경계와 strict_object의 중복JSON키 거부를 그대로 적용한다. 아래는 문법 예시이며 운영 허용 결정을 제공하지 않는다.

```json
{
  "modelRegistryPolicy": {
    "version": "operator-policy:1",
    "allowed": [
      {"licensePolicy": "synthetic-example", "classification": "internal"}
    ]
  }
}
```

기존 identity 등 필수 설정과 함께 사용한다. policy가 없으면 기존 kernel-only 모드, 존재하지만 잘못되면 시작 거부다. null/빈allowed/중복pair/unknown key는 fail-closed다. 실제 registry-bound 입력은 기존대로 현재 typed policy가 없는 프로세스에서 거부된다. trusted worker도 configured_registry_policy로 동일 정책을 파싱할 수 있다.

정책 변경은 프로세스별 시작 설정이며 전역 hot reload가 아니다. 모든 worker/승인/delivery 프로세스의 같은 정책 배포·구프로세스 종료는 운영 책임이다. 이 코드 변경은 운영 허용pair 선정·정책 rollout·실장비 배포를 수행하지 않는다. e2908a5 실행결속의 Claude sound 검토는 수신했으며 이번 설정 연결의 독립 검토는 별도다. [[2026-09-18_Registry_운영정책설정_Codex]].


## 실행 Manifest 해석 조회 (1.9.0, VF-CL-02 option c)

`GET /v1/projects/{project}/models/{model_id}/versions/{version}/execution-manifest`는 비즈니스 resolver가 커널 manifest를 직접 SQL로 읽지 않고 해석할 수 있게 하는 project-scoped 최소 projection이다. 기존 `/commitment` 응답과 의미는 바꾸지 않는다.

- 현재 principal의 kernel `can_request`와 linked business project permission을 먼저 교차 확인한다. 다른 tenant/project는 기존 commitment와 같은 비노출 정책으로 `AUTH-0030`/403, 권한 있는 scope의 미존재 model/version은 `MODEL-0004`/404다.
- 응답 `ModelExecutionManifestObservation`은 `manifestHash`, 원문의 연속 `ModelShard[]`, `shardIndex → {locationId, locationVersion}` 최소 매핑, 관측시각, 현재 `readyNodes`, 매핑별·전체 `materialisable`, 원문 `licensePolicy`/`classification`을 strict하게 제공한다. 공개 registry가 정책 선언을 보유할 경우 소비자는 두 선언을 exact-match해야 하며 이 문자열 자체는 법적 허가가 아니다.
- manifest의 shard 연속성·digest와 `inv.model_shard_locations`의 전체 집합을 대조한다. shard 또는 mapping 누락·추가·변조는 부분 응답 없이 `MODEL-0001`/409다.
- 현재 catalog location version이 다르거나 verified ready replica가 없으면 해당 매핑은 `readyNodes=[]`, `materialisable=false`다. 빈 배열을 성공으로 올리지 않으며 전체 `materialisable`은 모든 shard가 하나 이상의 materialisable mapping을 가질 때만 true다.
- `executionAuthorized=false`, `requiresExecutionRevalidation=true`다. 이 조회는 permit, approval, lease, fence, frozen input 또는 실제 bytes 재검사를 만들거나 대체하지 않는다.
- `inv_kernel`과 `inv_app`의 table SELECT 권한은 넓히지 않는다. migration 0046의 `public.model_location_readiness(text[])` SECURITY DEFINER 함수만 현재 `inv.tenant_id`에 묶인 location version과 ready node ID를 반환하며 PUBLIC/`inv_app` EXECUTE는 없다. 원시 경로·contribution·key·endpoint는 응답하지 않는다.
