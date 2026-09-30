---
doc_id: "HIST-CODEX-CARD156-PORTAL-PKI-20260930"
title: "portal.sv.lan TLS 인증서 발급과 노드2 인계"
version: "1.0.1"
status: "review"
author: "Codex"
updated: "2026-09-30T09:23:57+09:00"
source_of_truth: "Git"
---

# portal.sv.lan TLS 인증서 발급과 노드2 인계

## 결과

Card 150의 ECDSA P-256 HTTPS hierarchy와 `tools/intranet_pki.py`로
`portal.sv.lan` service leaf를 발급했다. 대상은 private inventory에서 object
store provider로 관측된 `node2.sv.lan`이며 실제 주소와 SSH 계정은 공개 기록에서
제외했다. 인증서는 DNS SAN과 대상 private-address SAN, serverAuth EKU를 가지며
로컬 Web PKI verifier와 대상 호스트의 OpenSSL chain 검증을 모두 통과했다.

대상에는 새 버전 전용 디렉터리
`<node-home>/.local/share/saintvision-intranet/tls/portal.sv.lan-20260930T001206Z`
를 만들었다. 디렉터리는 `0700`, private key는 `0400`이고 둘의 owner가 SSH
주체와 같은지 확인했다. certificate fingerprint는 issuer 출력과 일치하며 전송
staging은 제거했다. 기존 object-store container·설정·서비스는 변경하지 않았다.
따라서 상태는 `DELIVERED_NOT_ACTIVATED`이고 DNS, HTTPS 종단, 브라우저 접속은
아직 미측정이다.

공개 redacted evidence는
`docs/vault/30_Development/Evidence/card156-portal-pki-handoff.json`이다. private
key, credential, private address, 운영자 계정은 기록하지 않았다.
HTTPS service leaf fingerprint는 public certificate의 인계 무결성 식별자로만
기록했다. Node/topology identity fingerprint를 공개하지 않는 정책과 구분한다.

## 운영자 사본과 폐기

운영자 사본은 ignored operator-private 저장소에 ACL을 제한해 유지한다.
[[사내망_PKI_LAN_pilot_운영절차_Codex]]의 정책과 같이 후속 leaf가 대상에서
활성화되고 이전 leaf 폐기 절차가 끝나기 전에는 지우지 않는다. 현재 CRL 배포가
강제되지 않으므로 CRL 파일 재서명만으로 폐기 완료를 주장하지 않는다. 긴급
폐기는 대상 leaf 교체와 실제 배포 trust boundary 교체를 함께 확인해야 한다.

## cp.sv.lan 배치 계획

`cp.sv.lan` ECDSA P-256 leaf는 operator-private 저장소에 이미 있고 파일 수준
Web PKI 검증을 통과했다. 그러나 CP 호스트는 확정되지 않았으므로 전송하지
않았고 `BLOCKED_HOST_SELECTION`으로 둔다. 호스트가 정해지면 현재 leaf의 SAN이
선택한 주소와 일치하는지 먼저 검사한다. 다르면 기존 key/certificate를 억지로
복사하지 않고 같은 CA에서 새 leaf를 발급한다. 확정 대상에서는 portal과 동일한
`0700` directory, `0400` key, owner 확인, fingerprint·chain 검증, staging 제거
절차를 적용한다.

## 실제 검증

- 발급 결과: ECDSA P-256, `portal.sv.lan`, 90일 profile, 공개 fingerprint 고정.
- 로컬 `cryptography.x509.verification`: DNS identity와 chain 통과.
- 대상: directory `0700`, key `0400`, owner 일치, fingerprint 일치, OpenSSL
  chain 검증 통과, staging 잔존 0.
- 운영자 사본: Git 미추적, ACL 격리 확인.
- 하지 않은 것: 서비스 활성화, DNS 적용, live TLS·브라우저 probe, CP leaf 전송,
  기존 container 또는 이 PC Docker 변경.
