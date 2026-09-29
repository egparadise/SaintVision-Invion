---
doc_id: "HIST-CODEX-20260930-CARD150"
title: "사내망 PKI와 LAN pilot 재수립"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-09-30T08:18:49+09:00"
source_of_truth: "Git"
---

# 사내망 PKI와 LAN pilot 재수립

## 수행 범위

- 기준 source `6fc0428b49f28379cb4da17830d92256b55c2eb2`에서 새 branch
  `agent/codex/card150-intranet-pki-lan`을 만들었다. 과거
  `.work/lan-5node/node1`은 읽거나 재사용하지 않았다.
- 최초 PKI 구현의 Ed25519 Web chain과 `rootOffline=true` 주장은 독립 검토에서
  철회했다. HTTPS용 root/intermediate/leaf는 ECDSA P-256으로 다시 만들고,
  root key가 운영자 PC에 남아 있어 `rootOffline=false`로 기록했다. root
  passphrase는 online CA directory 밖의 별도 operator-private 파일로 옮겼다.
- 로컬 Docker Desktop은 사용하지 않았다. 최초 원격 PostgreSQL trust 후보는
  독립 검토에서 수용 불가로 판정했다. 최종 v5 candidate는 SCRAM, admin/runtime
  분리 credential, 전용 user-defined network, loopback publish를 사용한다.
  기존 후보 3개는 stop했고 data·volume은 보존했다.
- Node private key는 `.143`과 `.210`의 `prepare-worker.sh`가 로컬 생성했다.
  CP로 가져온 것은 CSR뿐이며 private key export는 0건이다.
- 자체감사에서 encrypted intermediate와 password를 pilot state에 함께
  복제한 경계를 제거했다. public chain만 pin하고 후속 enrollment가 중앙 CA
  key/password/chain을 매번 명시하도록 fail-closed로 바꿨다.
- 같은 감사에서 `status`/`observe` snapshot의 tenant ID·epoch·nonce 출력을
  제거하고 profile·capacity·관측 시각만 남겼다. configured 3, observed 2라는
  과거 state 관측은 보존하지만, v5 DB로 아직 rebind하지 않아 현재 pilot DB
  readiness는 `BLOCKED`다.

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

- 독립 검토 수정 후 PG-free focused run은 `tests/test_intranet_pki.py`
  **5 passed**, `tests/test_lan_pilot_multinode.py` **22 passed**다. 두 DB shell
  script의 `bash -n`과 `git diff --check`도 exit 0이다.
- 첫 hosted Backend 3.12/3.14는 제품 시험 5,610건 뒤 새 persistent label
  `ai.saintvision.lan-pilot`의 cleanup 정책 미분류 1건으로 실패했다. 이를
  age-prunable owner가 아닌 persistent runtime label로 명시하고 focused
  회귀를 통과시켰다.
- 실제 `.143`: Docker 29.1/API 1.52, 12 CPU,
  `MemAvailable=12,406,200 KiB`; `.210`: Docker 29.8/API 1.56, 12 CPU,
  `MemAvailable=14,036,016 KiB`.
- `.222`: 12 CPU, `MemAvailable=13,575,632 KiB`, Docker socket permission
  denied. 사용자 명령은 `sudo usermod -aG docker saintvision-invion3`이며
  Codex는 sudo를 실행하지 않았다.
- 공개 redacted evidence:
  `docs/vault/30_Development/Evidence/card150-intranet-pki-lan-pilot.json`.

## 독립 검토 조치

| Finding | 조치와 현재 판정 |
|---|---|
| F1 / worker DB 경계 | trust를 폐기하고 v5에서 no/wrong credential 거부, admin/runtime 양성, SCRAM HBA, 전용 network 1개, loopback publish를 실측했다. active state 이관 전이므로 BLOCKED다. |
| F2 Web PKI | HTTPS chain을 ECDSA P-256으로 분리했고 CP/IdP leaf 두 장을 Web PKI verifier로 검증했다. Node mTLS Ed25519 hierarchy는 별도다. |
| F3 root custody | passphrase를 CA directory 밖으로 분리하고 `rootOffline=false`, `operatorIsolated=true`로 정정했다. |
| F4 issuing key | pilot state에는 public chain만 남고 issuing key/password는 중앙 private 위치에서 매 enrollment마다 명시한다. |
| F5 CRL | revoke와 refresh 재서명을 시험했다. 애플리케이션 배포·강제는 없어 `distributionEnforced=false`다. |
| F6 image | prebuilt inspect image ID와 archive config digest가 같아야 하며 불일치 음성 시험을 추가했다. |
| F7 음성 시험 | password 조건과 loopback 조건을 각각 독립적으로 깨뜨리는 시험으로 교정했다. |
| F8 provenance / worker source | agent image source와 CP tooling commit을 분리하고 도구 4개의 SHA-256을 Evidence에 결속했다. |
| F9 stateGeneration | 출처가 불명확한 값을 제거하고 redacted operator-state digest 및 count만 남겼다. |
| F10 rotation | 최대 6일 Node leaf 자동 회전은 미구현 blocker로 명시했다. |
| worker 공개 Evidence | private IP·hostname·Node ID·certificate fingerprint를 제거하고 ordinal·count·status·digest만 남겼다. 회귀 시험이 이를 강제한다. |

## 남은 입력

Card 152가 확정한 CP와 IdP 이름으로 새 ECDSA P-256 HTTPS leaf를 발급했다.
두 leaf의 파일 수준 Web PKI 검증은 통과했지만 실제 TLS 종단에 배포하지
않았으므로 HTTPS issuer는 미측정이다. certificate fingerprint와 private
network identity는 공개 Evidence에 싣지 않는다.
Card 152 inventory의 필수값 71개 완성과 `.222` docker group 활성화,
네 번째 Ubuntu worker 제공,
Windows CP 동거 worker Docker API 1.45 이상이 남았다. 이 셋이 없으면
5-node readiness는 계속 BLOCKED다. 또한 v5 SCRAM DB로 pilot state를
이관하거나 새로 만들기 전까지 DB 경계 역시 BLOCKED다.
