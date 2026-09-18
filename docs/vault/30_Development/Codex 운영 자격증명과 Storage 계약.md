---
doc_id: "CODEX-OPERATING-CONTRACT-001"
title: "Codex 운영 자격증명과 Storage 계약"
version: "1.3.0"
status: "review"
author: "Codex"
updated: "2026-09-12T01:26:09+09:00"
source_of_truth: "Git"
---

# Codex 운영 자격증명과 Storage 계약

CX-02 / owner Codex, 독립 reviewer Claude pending. 다음은 구현 기준 결정이며 운영 자격증명 발급·배포 완료가 아니다. [[운영 환경 입력과 Agent 인계]]와 함께 사용한다. 원래 [[Storage 최종 개발 계획]] 및 ADR-009/014/034/060을 유지한다.

## ADR-075 — 버전에 고정된 자격증명 참조

첫 구현 대상은 **Linux 서비스 전용 보호 파일을 읽는 provider**로 정한다. 이미 Node TLS/서명키와 Git의 보호 파일 구성이 있으므로 이 경계를 재사용하되, 공통 credential resolver가 이미 구현됐다고 보지 않는다. Windows Credential Manager/외부 Vault는 같은 인터페이스의 후속 backend이며 Windows ACL 검사 없이 파일 mode만으로 합격하지 않는다. 기존 Node/Git 설정을 이 작업에서 자동 변환하지 않는다. 초기 보호 파일 backend는 서비스 API credential 구현 대상으로 한정하며 envelope encryption KEK를 일반 평문 파일로 옮기는 결정이 아니다. KEK는 기존 OS credential store 또는 별도 Vault 경계를 유지하고 검증된 backend가 없으면 encryption.unwrap을 거부한다.

참조는 `svcred:1:<credential UUID>:<version UUID>`라는 불투명 문자열이다. 두 UUID는 소문자 canonical 형식이며 버전은 immutable이다. `contracts/credential-reference.schema.json`이 문법 정본이다. 참조 자체는 bearer 권한이 아니다. `latest`, 파일 경로, URL, 환경변수 이름이나 raw token을 받지 않는다. public HTTP에 새로운 credential 선택 권한을 추가하지 않는다.

서버 소유 registry가 tenant/project, 허용 principal 또는 실행 주체, 용도, 목적지 alias, provider 종류, 버전, enabled/만료/revoked 상태와 실제 locator를 묶는다. 호출자가 전달한 tenant/role/목적지로 registry를 덮어쓰지 않는다. 용도는 `llm.invoke`, `git.read`, `git.publish`, `storage.read`, `storage.write`, `storage.gc`, `backup.write`, `backup.restore`, `encryption.unwrap`로 분리한다. Node mTLS/서명키는 기존 인증서/채널 회수 체계를 유지하며 LLM 자격증명으로 재사용하지 않는다.

내부 인터페이스는 `resolve(reference, authenticated_context, purpose, destination_alias)`가 scoped handle을 반환하고, 승인된 adapter가 그 handle의 제한된 callback 안에서만 secret bytes를 사용하는 구조다. context에는 검증된 tenant/project/principal 및 필요한 run/승인 version이 들어간다. handle·secret의 repr/예외/JSON 직렬화는 비밀을 노출하지 않는다. callback 종료 후 참조를 버리되 Python 메모리 완전 소거를 보장한다고 쓰지 않는다. resolve 때와 외부 dispatch 직전에 현재 registry·grant·만료·revocation을 검사한다. 장시간 stream의 후속 호출도 다시 확인한다.

Linux backend 구현은 서비스 소유 절대 root를 descriptor로 고정하고 owner/mode를 확인한다. root 밖 경로·symlink·교체된 inode·비정규 파일·그룹/타인 접근·64KiB 초과를 거부하고, 검증한 descriptor에서 읽는다. 기존 `private_key()`의 lstat→별도 read만으로 TOCTOU/Windows ACL 요구를 충족했다고 주장하지 않는다. 파일/DB mapping/운영 locator는 Git·Obsidian으로 export하지 않는다.

회전은 새 immutable version을 등록·검증한 뒤 새 요청의 binding을 전환한다. old version을 자동으로 최신에 연결하지 않는다. 폐기된 버전으로 새 resolve/dispatch는 거부한다. 이미 외부 provider에 전달된 작업은 회수만으로 중단됐다고 간주하지 않으며 기존 cancel UNKNOWN/NOT_SUPPORTED 계약을 따른다. 불확실한 유료/외부 side effect는 자동 재실행하지 않는다.

감사에는 credential UUID/version, 목적, 대상 alias, 검증된 actor/run, 결정 코드, 회전/회수 시각만 허용한다. raw secret·실제 locator·presigned URL·Provider 원문 오류는 제외한다. 일반 사용자에게는 권한 있는 범위의 ready/expired/revoked/unavailable 상태만 제공한다. schema 통과나 파일 존재만으로 인증 성공을 판단하지 않는다.

## Adapter 인계와 현재 코드의 차이

`ProviderAdapter.authenticate(credential_ref: str)`는 위 문자열을 해석하는 공통 resolver에 위임한다. Claude는 resolver/provider 및 hosted adapter 연결을 구현하고 Codex는 scope/경로/회수/불확실 재시도 경계를 독립 검토한다. 참조 문법 결정은 완료했으며 실제 resolver와 provider 선택·자격증명 등록·외부 호출 인수는 남는다. SDK/모델 버전과 비용 한도는 실제 대상 선택 뒤 별도 고정한다. ADR-009에 따라 모델 선택 전 vector 차원을 정하지 않는다.

현재 `adapters/cli.py`는 로컬 사람이 이미 로그인한 CLI를 탐지하며 credential_ref를 무시한다. 이를 hosted credential provider로 간주하지 않는다. 파일 존재만으로 LOGGED_IN을 반환하는 경로는 proof가 부족하므로 Claude는 readiness에서 verified/observed/unknown을 구분해야 한다. Orca는 작업 관리, Codex/Claude/Antigravity는 개발 도구 역할이며 도구 설치가 제품 내부 AI 실행 권한을 부여하지 않는다. 공유 HOME, 개인 로그인 cache, 호스트의 전체 환경변수나 비밀 폴더를 Node에 mount하지 않는다.

## ADR-076 — 현 로컬 저장소와 운영 S3 인수 경계

현재 실행 가능한 `inv.object_store.LocalObjects`를 **제한된 Linux 파일럿의 byte provider**로 유지한다. 서비스 소유 root·inode·flock 및 실제 hash를 사용하는 기존 구현이고, 현재 단일 객체 상한은64MiB다. Workspace snapshot 내용32KiB/manifest64KiB 제약도 그대로다. 최초 계획의50GiB multipart 목표나 공유/고가용 S3가 구현됐다고 표시하지 않는다. Node 캐시, Workspace 편집 generation, byte object 정본, DB metadata, backup 목적지는 서로 다른 역할로 유지한다.

운영 S3 제품/이미지는 아직 채택하지 않는다. 예전 문서의 MinIO 이름을 운영 선정 증거로 사용하지 않는다. 제품 후보 선택에는 배포/업데이트 책임·라이선스 검토·버전 고정·사내 TLS·전용 권한·복원 실측이 필요하다. 이번에는 외부 제품 현황을 재조사하지 않았으며 특정 제품의 현재 지원 상태를 새로 단정하지 않는다. Claude는 vendor-neutral adapter와 conformance를 만들 수 있고 Codex는 제품별 실제 무결성/복구 검증 후 인수한다.

역할별 namespace를 분리한다: staging uploads, immutable artifacts/datasets/models, Evidence pins/holds, MLflow-owned artifacts, DB backups/WAL. 정책 경계는 credential prefix 권한으로도 분리하며 운영 bucket/prefix 값은 보호 설정에 둔다. GC credential은 일반 업로드/다운로드와 분리한다. MLflow prefix를 INV GC로 정리하지 않는다. tenant/project 격리는 object key 문자열만이 아니라 현재 인가·서명 발급·실제 byte 검증에서 확인한다.

업로드 init의 quota 예약→multipart→신뢰 worker 실제 SHA-256/size 검증→metadata/commit→pin 순서를 유지한다. ETag/사용자 metadata를 내용 hash로 대체하지 않는다. 불확실한 complete는 ledger로 reconcile하며 새 upload/중복 quota 차감으로 재시작하지 않는다. 읽기는 현재 권한을 확인하고 immutable version/hash를 고정한다. 외부 응답/URL 로그는 남기지 않는다.

보존 기준은 변경하지 않는다: **일반 Artifact/로그90일, Evidence 필수 참조1년 이상 pin, Dataset/Model 수동 보존, DB backup35일**. lifecycle/GC는 이 기준과 active Run/lease/pin/hold/upload ledger를 함께 검사한다. 운영 제품별 보존/복원 인수 전에는 자동 삭제 정책을 활성화하지 않는다. 사용자 원본/허용하지 않은 폴더/전체 디스크는 수집·GC하지 않는다. 민감 원문의 envelope encryption KEK는 object/backup과 다른 권한 경계의 provider에 둔다. 초기 파일럿은 합성 데이터다.

## 운영 인수 증거와 책임

| 영역 | 구현 owner / reviewer | 필수 합격 증거 |
|---|---|---|
| Credential resolver·Linux backend | Codex / Claude | 다른 tenant/project/purpose/목적지 거부, scope 재검사, 회전/회수 경합, symlink/교체 거부, 오류·trace·로그 비밀 비노출 |
| 실제 Provider Adapter 연결 | Claude / Codex | 기존 resolver 사용·stream/cancel/usage·현재 권한/오류 비노출 |
| S3 일반 adapter·업로드 서비스 | Claude / Codex | 실제 제품의 중단/재개·hash 위조·complete replay·quota·pin/GC 경합·객체/DB 합동 복원 |
| 무결성/경로/복구 판정 | Codex / Claude | TOCTOU·복원 missing/old epoch·정본 byte/권한 보존·fencing 재사용 거부 |
| readiness·복구 안내·버전 표시 | Gemini / Claude(보안 Codex) | unknown을 성공으로 표시하지 않음, secret/ref 입력 대신 권한 있는 서버 alias 선택, 실제 브라우저 여정 |
| 실제 계정/허용 폴더/도메인/저장 장비 | 운영자, Claude 설정 / Codex 검토 | [[운영 환경 입력과 Agent 인계]]의 비밀 없는 값·검증 Evidence |

이 표는 타 Agent의 작업 착수/동의/승인을 대신 기록한 것이 아니다. CI 제한과 물리 원격 profile 설치·실장비 시험은 별도다.

## 공통 executable 계약과 검증

`src/saintvision/credentials/contract.py`가 내부 Protocol 정본이다. [[Codex 자격증명 보안 검증 인계]]의39개 conformance에 실제 backend를 연결한다. 합성 모델39개+결함검출8개의 통과는 runtime provider 구현·운영 인수와 구분한다. 공개 HTTP 권한이나 모델 차원을 추가하지 않는다.


## ADR-077 — 실제 Linux/DB backend와 복원 이후 권한

사용자의 전체 과정 계속 지시에 따라 이번 backend 구현 단위를 Codex가 맡는다. Claude는 독립 reviewer 및 후속 Adapter/운영 연결 owner다. `LinuxFileCredentials`와 `PostgresCredentialRegistry`를 기존 Protocol에 연결하며 두 번째 자격증명 정본을 만들지 않는다.

0035의 credential_versions는 tenant/project별 immutable 버전 metadata(고정 basename·device/inode·SHA-256)를 저장하고 credential_grants는 subject+Run별 enabled/만료/revoked/복구 epoch를 저장한다. 둘 다 FORCE RLS와 tenant 복합 FK이며 inv_kernel에는 SELECT만 허용한다. secret bytes는 DB에 저장하지 않는다. runtime이 자신에게 grant를 발급하거나 version을 수정할 수 없다. 운영자만 보호된 별도 경로에서 version/grant를 등록한다. 버전 metadata 변경/삭제는 trigger가 거부하고, grant 회수·만료 변경은 운영자 권한이다. 운영 provisioning UI/CLI와 실제 secret 등록은 아직 별도다.

registry는 exact ref와 현재 project can_request, subject/Run/project/purpose/destination, 만료·회수, 살아 있는 Run, 현재 epoch 및 kill switch를 확인한다. 이 backend는 명시적 Run scope용이며 독립 운영 backup/KEK 발급기가 아니다. 원래 ToolGateway/승인 절차는 계속 필요하다. 허용된 조회는 inv.credential.authorized 이벤트에 식별자/목적/alias만 기록하며 byte 읽기나 외부 실행 성공 증거로 사용하지 않는다.

Linux root의 경로 각 segment를 O_NOFOLLOW directory descriptor로 열고 서비스 owner/비공개 mode와 inode를 고정한다. 파일은 등록된32hex basename만 허용하며 O_NOFOLLOW/O_NONBLOCK으로 열어 정규 파일·owner·비공개 mode·단일 hard link·1~65536bytes 및 등록 inode를 검사한다. 같은 descriptor에서 bounded read하고 SHA-256, 읽기 전후 size/mtime/ctime와 현재 이름/root identity를 대조한다. root/파일 교체와 공유 hard link를 통해 외부 파일로 바꾸는 접근은 거부한다. 정상 byte를 읽은 뒤 registry를 다시 조회하여 그 사이 commit된 회수를 확인한다.

최종 registry 확인이 해당 callback의 admission 시점이다. 그 이후 회수는 다음 admission을 막지만 이미 진행 중인 외부 효과를 소급 중지하지 않는다. DB transaction/file lock을 callback 네트워크 구간에 걸쳐 유지하지 않는다. callback은 한 번만 호출하고 예외를 raw provider 오류 없이 CredentialDenied로 매핑한다. 모델 서비스의 streaming/cancel/usage/attestation 연결은 후속 Adapter 구현이다. grant의 epoch가 다르면 복원 뒤 새 서비스도 거부하고 운영자의 명시적 재인가가 필요하다.

기존39개 conformance를 실제 Linux 파일·일회용 PostgreSQL에 연결한다. remove_version/rebind_destination 시나리오는 immutable version 파괴 대신 실제 grant 삭제/회수로 해석 불가를 만든다. outside_root는 원래 파일을 root 밖으로 옮기고 hard link를 되붙이는 실제 공격이다. 읽기 중 inode/root/내용 교체, 읽기 후 revocation commit, admission 뒤 회수, RLS/쓰기 권한/복원 epoch/kill/cancel을 추가 검증한다. 운영 키/실제 Provider 요청/Windows ACL/전체 장비 인수와는 구분한다.

실제 구현·합격 범위: [[2026-09-12_CREDENTIAL-BACKEND_Codex_검증보고]]. Linux/DB conformance39+추가9 통과; 운영 보호 등록과 외부 Provider 연결은 남는다.

## ADR-079 — 보호 운영자 등록·Run 범위 원자 회전/회수

[[Codex 자격증명 등록 회전 회수 운영 절차]]를 따른다. 기존0035에만 쓰는 운영자 CLI를 추가한다. table owner/superuser·현재 epoch·tenant/Run/project grant·불변 파일을 검증하고 register와grant를 분리한다. 같은 old grant의 경쟁 회전은 하나만 성공하며 audit/version/grant는 원자 commit한다. 폐기/만료/old epoch grant를 재활성화하지 않는다. default check는 쓰지 않고 명시적 apply만 반영하며 DSN/원문 오류는 노출하지 않는다. revoke는 지정subject/Run 범위이며 실제 Provider token/global revocation이나 secret 파일 삭제를 뜻하지 않는다. 운영 적용·독립 검토는 별도다. [[2026-09-12_CREDENTIAL-PROVISION_Codex_검증보고]].
