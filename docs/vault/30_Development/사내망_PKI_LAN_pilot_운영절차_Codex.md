---
doc_id: "OPS-INTRANET-PKI-LAN-001"
title: "사내망 PKI와 LAN pilot 운영 절차"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-09-30T08:18:49+09:00"
source_of_truth: "Git"
---

# 사내망 PKI와 LAN pilot 운영 절차

## 1. 범위와 불변식

이 절차는 [[외부 전제 인수 준비 패키지]] §2-0·§2-2·§5의 U3/G-17과
G-19/G-24 입력을 사내 LAN에서 준비한다. agent image 기준 source는
`6fc0428b49f28379cb4da17830d92256b55c2eb2`이고, CP 도구는 Evidence의 별도
`controlPlaneToolingCommit` 및 파일별 SHA-256에 결속한다.

- 비밀번호·private key·token은 Git, 콘솔, PR, 공개 Evidence에 넣지 않는다.
  운영자 private material은 ignored `.work/intranet/` 아래에만 둔다.
- HTTPS Web PKI와 Node mTLS PKI를 분리한다. 한쪽의 key·CRL·신뢰점을 다른
  용도로 재사용하지 않는다.
- Node key는 `deploy/lan/prepare-worker.sh`가 각 Node에서 생성한다. CP로
  이동하는 것은 CSR뿐이다.
- 이 PC의 Docker Desktop과 다른 프로젝트 컨테이너는 사용하거나 변경하지
  않는다. 원격 PostgreSQL과 image build는 지정 Ubuntu host에서 수행한다.
- inventory가 5개 실 Node로 완성되고 active pilot state가 hardened DB에
  결속되기 전에는 readiness를 PASS로 기록하지 않는다.

## 2. HTTPS와 Node mTLS CA

### 2.1 HTTPS Web PKI

`tools/intranet_pki.py`는 브라우저·Windows·Python Web PKI 검증기가 받는
ECDSA P-256 root, issuing intermediate, service leaf를 만든다. root 10년,
intermediate 3년, service leaf 90일이며 서명 hash는 SHA-256이다. root key
passphrase는 online CA directory 밖의 operator-private 파일이어야 한다.
현재 root key는 같은 운영자 PC의 별도 경로에 있으므로 metadata와 공개
Evidence의 `rootOffline`은 거짓이다. 물리 offline 보관을 수행하기 전에는
offline root라고 부르지 않는다.

```powershell
python tools/intranet_pki.py `
  --ca-dir D:\Project\SaintVisionI-Invion\.work\intranet\https-ca `
  init `
  --root-password-file D:\Project\SaintVisionI-Invion\.work\intranet\offline-secrets\https-root-key.pass
python tools/intranet_pki.py `
  --ca-dir D:\Project\SaintVisionI-Invion\.work\intranet\https-ca `
  issue-server --hostname cp.sv.lan --address 192.168.45.74 `
  --output D:\Project\SaintVisionI-Invion\.work\intranet\https-cp
python tools/intranet_pki.py `
  --ca-dir D:\Project\SaintVisionI-Invion\.work\intranet\https-ca `
  issue-server --hostname idp.sv.lan --address 192.168.45.143 `
  --output D:\Project\SaintVisionI-Invion\.work\intranet\https-idp
```

2026-09-30 실측에서 두 leaf 모두 `cryptography.x509.verification`의 server
verifier를 통과했다. 이는 파일 수준 검증이며 TLS 종단 배포나 live issuer
검증이 아니다. private key는 operator-private 경로 밖으로 내보내지 않았다.

`revoke`는 serial을 registry에 추가하고 CRL을 재서명한다. `refresh-crl`은
`nextUpdate`를 갱신한다. 현재 애플리케이션은 CRL을 배포·강제하지 않으므로
`distributionEnforced=false`다. 긴급 HTTPS 폐기는 service leaf 및 배포 trust
bundle 교체를 함께 수행해야 하고, CRL 파일 생성만으로 완료 처리하지 않는다.

### 2.2 Node mTLS

Node mTLS는 별도 Ed25519 hierarchy와 public chain pin을 유지할 수 있다.
pilot state에는 public chain만 두며 issuing key와 password는 중앙
operator-private 위치에 남긴다. 외부 CA mode의 `enroll`은 `--ca-key`,
`--ca-key-password-file`, `--ca-chain` 세 값을 매번 요구한다. Node channel의
monotonic version/disable이 1차 폐기 경계이고 CRL은 보조 기록이다. 최대 6일
Node leaf의 자동 회전은 아직 구현되지 않았으므로 readiness blocker다.

## 3. 원격 PostgreSQL과 image 결속

`deploy/lan/prepare-pilot-database.sh`는 별도 container/network에 PostgreSQL을
만들고 `127.0.0.1`에만 publish한다. host/local 인증은 `scram-sha-256`이며,
admin과 `inv_lan_runtime`의 무작위 credential 및 한 줄 pgpass를 지정한
operator-private directory에 생성한다. URI 안 password와 passwordless
접속은 금지한다.

`deploy/lan/verify-pilot-database.sh`는 다음을 모두 검사한다.

- 무 credential 및 잘못된 credential 거부
- admin과 runtime credential 수락 및 role identity 일치
- HBA가 SCRAM이고 container가 정확히 한 dedicated user-defined network만 사용
- publish address가 loopback

실측한 v5 candidate는 위 조건을 모두 만족했다. 과거 trust candidate 세
개는 정확한 owner label을 확인한 뒤 stop했고 volume과 data는 삭제하지
않았다. active pilot state는 아직 v5에 rebind하지 않았으므로 판정은
`MEASURED_PASS_CANDIDATE_BLOCKED_MIGRATION`이다. `lan_pilot.py bind-db-auth`는
같은 음성·양성 검사를 반복한 뒤에만 보존 state를 새 passfile DSN에 결속한다.
그 이관을 실제 수행하기 전에는 pilot DB가 ready라고 기록하지 않는다.

원격 prebuilt Node image는 exact Git archive로 빌드한다. `bundle`은 inspect
JSON의 image ID가 archive의 config digest와 정확히 같고 layer·runtime·tag가
일치할 때만 받는다. old source image나 이름만 같은 image는 거부한다.

## 4. CSR·enrollment·관측

각 Node는 source-IP별 worker archive SHA-256을 operator 값과 비교한 뒤
`prepare-worker.sh`를 실행한다. CSR common name은 미리 배정된 Node ID와
정확히 같아야 하고 extension은 0개여야 한다. CP의 `enroll --csr`가 SPIFFE
identity, Node IP SAN, serverAuth EKU를 선택하고 DB channel에 certificate
identity를 pin한다. Node는 별도 전달된 leaf file SHA-256을 검증한 뒤
`finish-worker.sh`를 실행한다.

실측은 worker 3개 configured, 2개 enrolled/observed, 1개 host permission
block이다. CP 동거 worker는 Docker API 1.41로 요구치 1.45보다 낮고, 네 번째
독립 Ubuntu worker도 아직 없다. 공개 Evidence에는 worker ordinal과 상태,
집계 count만 두고 IP·hostname·Node ID·certificate fingerprint를 싣지 않는다.

## 5. readiness 입력과 정직한 판정

HTTPS 검증의 `--http-ca-bundle`은 ECDSA Web PKI trust chain을, Node 검증의
`--ca-bundle`은 별도 Node mTLS public chain을 가리킨다. 둘을 바꾸어 쓰지
않는다.

```powershell
python tools/s01_readiness_preflight.py `
  --base-url https://cp.sv.lan `
  --settings-url https://cp.sv.lan/v1/operations/configuration-readiness `
  --http-ca-bundle D:\Project\SaintVisionI-Invion\.work\intranet\https-ca\intermediate\certs\ca-chain.pem `
  --inventory D:\Project\SaintVisionI-Invion\.work\intranet\inventory.json `
  --state D:\Project\SaintVisionI-Invion\.work\intranet\lan-pilot-6fc0428b-v2 `
  --ca-bundle D:\Project\SaintVisionI-Invion\.work\intranet\ca\intermediate\certs\ca-chain.pem `
  --storage-evidence dist/s01-storage-roundtrip.json `
  --storage-attestation D:\Project\SaintVisionI-Invion\.work\intranet\storage-attestation.json `
  --output dist/s01-readiness.json
```

현재 inventory는 필수값 71개가 비어 `BLOCKED/inventory-values-missing`이고,
두 probe는 DB 접근 전에 `BLOCKED/inventory-not-ready`다. 정확히 5개 leaf 및
inventory identity, 5개 current heartbeat/profile/capacity, hardened active DB,
live HTTPS가 모두 확인될 때까지 `node-certificate-chain`과
`pilot-capability-match`는 PASS가 아니다. 공개 Evidence는
`docs/vault/30_Development/Evidence/card150-intranet-pki-lan-pilot.json`이다.
