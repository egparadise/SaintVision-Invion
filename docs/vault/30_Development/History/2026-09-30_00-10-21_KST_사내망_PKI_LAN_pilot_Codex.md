---
doc_id: "HIST-CODEX-20260930-CARD150"
title: "사내망 PKI와 LAN pilot 재수립"
version: "1.0.2"
status: "review"
author: "Codex"
updated: "2026-09-30T00:37:05+09:00"
source_of_truth: "Git"
---

# 사내망 PKI와 LAN pilot 재수립

## 수행 범위

- 기준 source `6fc0428b49f28379cb4da17830d92256b55c2eb2`에서 새 branch
  `agent/codex/card150-intranet-pki-lan`을 만들었다. 과거
  `.work/lan-5node/node1`은 읽거나 재사용하지 않았다.
- `tools/intranet_pki.py`로 offline root 10년, issuing intermediate 3년,
  암호화 PKCS#8 key, chain, 빈 CRL을 만들었다. 공개 fingerprint와 만료일만
  증거에 남겼다.
- 로컬 Docker Desktop은 사용하지 않았다. `.143`의 별도 PostgreSQL
  컨테이너는 remote loopback에만 publish했고 CP에서는 passwordless SSH
  tunnel로 접속했다. Node image도 `.143`에서 exact Git source archive로
  빌드한 뒤 archive/config/layer/runtime 결속을 검증했다.
- Node private key는 `.143`과 `.210`의 `prepare-worker.sh`가 로컬 생성했다.
  CP로 가져온 것은 CSR뿐이며 private key export는 0건이다.

## 실측 결과

첫 fresh state는 기존 보존 pilot이 `18443`을 점유한 사실을 Node start에서
발견했다. 그 state의 두 leaf와 실패한 컨테이너를 성공 증거로 사용하지
않았고, DB·bootstrap·tunnel은 stop하되 state·DB volume은 삭제하지 않았다.
immutable `nodePort`를 소급 변경하지 않고 두 번째 fresh state를 `18444`로
처음부터 만들었다.

두 번째 state에서 `.143`과 `.210`의 archive SHA, CSR CN, leaf file SHA,
intermediate 서명, DB channel fingerprint를 대조했다. 두 Node 컨테이너는
각각 running이 됐고 `observe --once`가 2026-09-30 00:08 KST에 두 Node의
mTLS heartbeat와 `lan-observe-v1` snapshot을 commit했다. `.222`는 Docker
socket permission denied라 CSR·leaf·heartbeat를 실행하지 않았다.

현재 실측은 configured 3, enrolled 2, observed 2다. CP 동거 worker는 Docker
API 1.41이라 건드리지 않았고, 네 번째 Ubuntu worker 값도 없다. 그러므로
Card 152 inventory는 5행을 갖지만 필수값 71개가 비어 있었다. 정본
`lint_inventory`는 `BLOCKED/inventory-values-missing`, 두 readiness probe는
각각 `BLOCKED/inventory-not-ready`를 반환했다. 5-node
`node-certificate-chain`과 `pilot-capability-match`의 입력 경로는 준비됐지만
판정은 `BLOCKED_EXTERNAL`이며 S01 완료 증거가 아니다.

## 검증

- Python 3.14 venv:
  `tests/test_intranet_pki.py`, `tests/test_lan_pilot_multinode.py`,
  `tests/test_s01_readiness_preflight.py` focused run **68 passed**. Black 검사와
  compileall도 exit 0이다.
- 실제 `.143`: Docker 29.1/API 1.52, 12 CPU,
  `MemAvailable=12,406,200 KiB`; `.210`: Docker 29.8/API 1.56, 12 CPU,
  `MemAvailable=14,036,016 KiB`.
- `.222`: 12 CPU, `MemAvailable=13,575,632 KiB`, Docker socket permission
  denied. 사용자 명령은 `sudo usermod -aG docker saintvision-invion3`이며
  Codex는 sudo를 실행하지 않았다.
- 공개 redacted evidence:
  `docs/vault/30_Development/Evidence/card150-intranet-pki-lan-pilot.json`.

## 남은 입력

Card 152가 `cp.sv.lan`을 확정해 DNS+IP SAN CP HTTPS leaf를 발급했다. leaf
SHA-256은 `317368f916f725770cbdbf9b3a78023827ba6912c75a8bbd954f61af135615c9`,
만료는 2026-12-29 00:15 KST다. #250 검토에서 확인한 IdP TLS owner 공백을
닫기 위해 `idp.sv.lan`+`.143` SAN leaf도 발급했다. SHA-256은
`9d334908bb3be6fe1deb44b2085117137b59c94bedf77563945b518bde0dfc38`, 만료는
2026-12-29 00:36 KST이며 아직 배포하지 않아 HTTPS issuer는 미측정이다.
Card 152 inventory의 필수값 71개 완성과 `.222` docker group 활성화,
네 번째 Ubuntu worker 제공,
Windows CP 동거 worker Docker API 1.45 이상이 남았다. 이 셋이 없으면
5-node readiness는 계속 BLOCKED다.
