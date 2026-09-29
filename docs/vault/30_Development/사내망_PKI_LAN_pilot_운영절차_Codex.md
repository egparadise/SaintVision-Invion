---
doc_id: "OPS-INTRANET-PKI-LAN-001"
title: "사내망 PKI와 LAN pilot 운영 절차"
version: "1.0.2"
status: "review"
author: "Codex"
updated: "2026-09-30T00:44:29+09:00"
source_of_truth: "Git"
---

# 사내망 PKI와 LAN pilot 운영 절차

## 1. 범위와 불변식

이 절차는 [[외부 전제 인수 준비 패키지]] §2-0·§2-2·§5의 U3/G-17과
G-19/G-24 입력을 사내 LAN에서 준비한다. Control Plane은 Windows
`192.168.45.74`, Ubuntu worker는 `192.168.45.143`, `.210`, `.222`다.
기준 source는 `6fc0428b49f28379cb4da17830d92256b55c2eb2`다.

- 비밀번호·private key·token은 Git, 콘솔, PR, 증거 JSON에 넣지 않는다.
  운영자 private material은 `D:/Project/SaintVisionI-Invion/.work/intranet/`
  아래에만 둔다.
- root key는 intermediate 발급·교체 때만 사용한다. pilot과 Node는 root
  key에 접근하지 않는다.
- Node key는 `deploy/lan/prepare-worker.sh`가 각 Node에서 생성한다. CP로
  이동하는 것은 CSR뿐이다.
- 이 PC의 Docker Desktop과 다른 프로젝트 컨테이너는 사용하거나
  변경하지 않는다. PostgreSQL과 image build는 `.143`에서 실행하고 CP는
  SSH tunnel·bootstrap·observer만 담당한다.
- inventory가 5개 실 Node로 완성되기 전에는 readiness를 PASS로 기록하지
  않는다.

## 2. CA 계층·유효기간·폐기

`tools/intranet_pki.py`가 Ed25519 root와 issuing intermediate를 만든다.
root는 10년, intermediate는 3년, CP HTTPS leaf는 90일, pilot Node leaf는
기존 fail-closed bootstrap 정책대로 최대 6일이다. private key는 암호화된
PKCS#8이고 passphrase 파일과 분리한다. chain 순서는 intermediate, root다.
pilot state에는 public chain만 pin하며 intermediate key·password를 복제하지
않는다. 후속 `enroll`은 중앙 CA의 세 입력을 다시 명시해야 한다.

```powershell
.venv\Scripts\python.exe tools/intranet_pki.py `
  --ca-dir D:\Project\SaintVisionI-Invion\.work\intranet\ca init
```

Card 152의 확정 DNS 이름을 받은 뒤 CP HTTPS leaf를 발급한다. 이름을
추정해 먼저 발급하지 않는다.

```powershell
.venv\Scripts\python.exe tools/intranet_pki.py `
  --ca-dir D:\Project\SaintVisionI-Invion\.work\intranet\ca `
  issue-server --hostname cp.sv.lan --address 192.168.45.74 `
  --output D:\Project\SaintVisionI-Invion\.work\intranet\cp
```

Card 152 보안 검토에서 `idp.sv.lan` HTTPS issuer의 인증서 owner 공백을
확인해 같은 intermediate로 별도 server leaf를 발급했다. SAN은
`idp.sv.lan`과 `192.168.45.143`이며 CP leaf에 다른 서비스 이름을 섞지
않는다. fingerprint는 공개 evidence에 남겼지만 TLS 종단 배포와 live HTTPS
issuer 검증 전에는 IdP 준비 완료로 세지 않는다.

폐기는 두 층이다. 먼저 `lan_pilot.py revoke-node-certificate`로 private
state를 fail-closed 표시하고 DB channel version을 올려 disable한다. 이어
같은 public leaf를 `intranet_pki.py revoke`에 넘겨 intermediate CRL을
갱신한다. bootstrap을 재시작해 메모리의 source-IP allowlist에서도 제거한다.
Node 컨테이너 stop만 하거나 CRL만 만드는 것은 완전한 폐기가 아니다.

## 3. Docker Desktop 없는 CP 경로

`deploy/lan/prepare-pilot-database.sh`는 digest-pinned PostgreSQL을 원격
loopback에만 publish한다. 비밀번호 없는 DB는 LAN에 노출하지 않고 operator
SSH tunnel만 통과한다. source archive는 Git `HEAD`에서 만들고
`deploy/lan/Dockerfile.node.remote`로 `.143`에서 빌드한다. `bundle`은 원격
`docker save` archive와 `docker image inspect` JSON의 config digest, layer,
runtime, tag를 다시 대조한다.

원격 실행은 다음 형태를 사용한다. sudo와 비밀 전달은 없다.

```bash
ssh -i C:/Users/inviz/.ssh/sv-lan-ed25519 \
  saintvision-invion@192.168.45.143 bash -s \
  -- postgres@sha256:<verified-digest> saintvision-card150-pilot-db-v2 55442 <<'EOF'
set -euo pipefail
# deploy/lan/prepare-pilot-database.sh의 검토된 본문
EOF
```

최종 fresh state는 bootstrap `18083`, Node publish `18444`를 처음부터
identity에 넣었다. 기존 pilot의 `18443` 점유를 발견한 첫 state는 port를
소급 변경하지 않았고 acceptance에서 제외했다.

## 4. CSR·enrollment·관측

각 Node는 source-IP별 worker archive SHA-256을 operator 값과 비교한 뒤
`prepare-worker.sh`를 실행한다. CSR common name은 미리 배정된 Node ID와
정확히 같아야 하고 extension은 0개여야 한다. CP의 `enroll --csr`가 leaf의
SPIFFE identity, Node IP SAN, serverAuth EKU를 선택하고 DB channel에
fingerprint를 pin한다. Node는 독립 전달된 leaf file SHA-256을 확인한 뒤
`finish-worker.sh`를 실행한다.

외부 CA mode의 `enroll`에는 `--ca-key`, `--ca-key-password-file`,
`--ca-chain`을 중앙 `.work/intranet/ca` 경로로 모두 넘긴다. 하나라도 빠지거나
init 때 pin한 chain과 다르면 발급 전에 실패한다.
`status`와 `observe`의 snapshot 출력은 tenant ID, recovery epoch, nonce를
제거하고 profile·capacity·관측 시각만 보여 준다.

2026-09-30 00:08 KST 실측은 다음과 같다.

| 주소 | Docker | CSR/leaf | mTLS heartbeat·snapshot | 판정 |
|---|---:|---:|---:|---|
| `192.168.45.143` | API 1.52 | 완료 | 완료 | measured partial |
| `192.168.45.210` | API 1.56 | 완료 | 완료 | measured partial |
| `192.168.45.222` | socket permission denied | 미실행 | 미관측 | blocked |

`.222`에서 사용자가 실행할 정확한 명령은 다음 하나다. 실행 뒤 반드시
로그아웃·재로그인하고 `docker version`이 성공하는지 먼저 확인한다.

```bash
sudo usermod -aG docker saintvision-invion3
```

Windows CP 동거 worker는 Docker API 1.41이라 요구치 1.45에 미달한다.
Docker Desktop을 이 카드에서 변경하지 않는다. 또한 topology B의 네 번째
Ubuntu worker 주소·hardware 값이 아직 없으므로 5개 Node 판정은
`BLOCKED_EXTERNAL`이다.

## 5. readiness 입력과 정직한 판정

Card 152가 만든 inventory와 DNS/hosts 적용 뒤 정본 명령은 다음이다.
`--state`와 `--ca-bundle`은 이미 준비됐다. 2026-09-30 확인한 inventory는
5행을 갖지만 필수값 71개가 비어 있어 `lint_inventory`가
`BLOCKED/inventory-values-missing`을 냈다. 따라서 두 probe 모두 DB 접근 전에
`BLOCKED/inventory-not-ready`를 냈으며 현재 결과를 PASS로 세지 않는다.

```powershell
.venv\Scripts\python.exe tools/s01_readiness_preflight.py `
  --base-url https://cp.sv.lan `
  --settings-url https://cp.sv.lan/v1/operations/configuration-readiness `
  --http-ca-bundle D:\Project\SaintVisionI-Invion\.work\intranet\ca\intermediate\certs\ca-chain.pem `
  --inventory D:\Project\SaintVisionI-Invion\.work\intranet\inventory.json `
  --state D:\Project\SaintVisionI-Invion\.work\intranet\lan-pilot-6fc0428b-v2 `
  --ca-bundle D:\Project\SaintVisionI-Invion\.work\intranet\ca\intermediate\certs\ca-chain.pem `
  --storage-evidence dist/s01-storage-roundtrip.json `
  --storage-attestation D:\Project\SaintVisionI-Invion\.work\intranet\storage-attestation.json `
  --output dist/s01-readiness.json
```

`node-certificate-chain`은 정확히 5개 leaf와 inventory fingerprint가 모두
일치해야 PASS다. `pilot-capability-match`는 read-only DB transaction에서 5개
Node의 certificate, `lan-observe-v1`, CPU·memory capacity가 inventory와 모두
일치해야 PASS다. 이번 실측은 2개만 만족하므로 전체 S01 인수를 완료했다고
기록하지 않는다. 공개 증거는
`docs/vault/30_Development/Evidence/card150-intranet-pki-lan-pilot.json`이며,
DSN·tenant·epoch·nonce·private key는 포함하지 않는다.
