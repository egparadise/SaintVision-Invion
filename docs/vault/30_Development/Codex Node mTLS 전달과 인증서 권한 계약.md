---
doc_id: "NODE-TRANSPORT-CONTRACT-001"
title: "Codex Node mTLS 전달과 인증서 권한 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T01:49:58+09:00"
source_of_truth: "Git"
---

# Codex Node mTLS 전달과 인증서 권한 계약

Task node-transport / owner Codex / reviewer Claude(pending), base `75e22940ca9807f603d4787619f9c8e9599e31dd`, branch agent/codex/node-transport. [[Codex Node 실행 격리와 정지 영수증 계약]]의 로컬 실행을 Control Plane → Go Node mTLS 호출과 현재 권한에 묶인 반환 트랜잭션으로 확장한다. S02 등록 CRUD와 S03 전체 완료가 아닌 Codex 보안 경계 보완이다.

## ADR-029 양방향 TLS와 Node 실행의 인증 경계

Python NodeDelivery는 운영자 관리 DB binding에서 endpoint와 Node leaf certificate 지문을 읽고, TLS 1.3으로 Node에 연결한다. OS trust store/proxy/redirect를 자동 사용하지 않으며 명시적 CA, hostname, server EKU, leaf의 단일 URI, 지문을 검증한 뒤에만 signed permit을 보낸다. 실패와 timeout은 불확실한 전달이며 자동 재연결·재실행·자원 반환을 하지 않는다. HTTP Connection close로 socket이 response로 이전되어도 timer가 원 socket을 종료하도록 보존한다. DNS 해석의 OS resolver 시간은 별도이며 운영 P95를 실측했다고 주장하지 않는다.

Node server는 명시적 client CA와 clientAuth EKU·단일 Control Plane URI·현재 지문 allowlist를 요구한다. TLS 1.3 최소, session ticket 비활성화, HTTP/1.1, private TLS key 파일, 최대 16개 연결과 1개 execution, header/body/time 제한을 적용한다. 헤더의 Node ID나 proxy 인증 문자열은 권한이 아니다. 정상 TLS 검증 뒤에도 요청마다 다시 검사하고 실행 중 100ms 주기로 peer 정책 만료/폐기를 감지해 context를 취소한다. 이 주기는 설정이며 운영 취소 지연 SLO가 아니다. 이미 승인된 in-flight 작업은 감지/정리까지 짧게 지속될 수 있다.

- Node URI: `spiffe://saintvision.ai/tenant/{tenantUUID}/node/{nodeId}/epoch/{epochUUID}`.
- Control Plane URI: `spiffe://saintvision.ai/tenant/{tenantUUID}/control-plane/epoch/{epochUUID}`.
- 자체 고정 URI 계약이며 SPIFFE 인증 인프라/SPIRE 통합을 구현했다는 뜻이 아니다.
- `POST /v1/executions`: 기존 SignedNodePermit; 성공 응답 NodeExecutionResult(duplicate, receipt, cleanupPending=false).
- `POST /v1/executions/receipts`: 같은 permit으로 기존 intent/receipt만 조회·정리한다. fresh permit이라도 intent가 없으면 거절하며 새 container를 만들지 않는다. 장기 경과 뒤에도 기존 서명/내용/scope 검증을 유지하고 실행 기한은 재발급하지 않는다.
- 오류는 credential·raw request·argv를 포함하지 않는 problem JSON이며 CP는 원격 오류 body를 그대로 외부에 노출하지 않는다.

Node root signal은 HTTP BaseContext와 활성 실행을 취소한다. server는 graceful shutdown의 정지 처리를 기다리고 종료한다. 정지·삭제·receipt fsync는 이전 ADR-028을 유지한다. 강제 종료는 독립 PID 1 deadline과 재시작 reconciliation으로 보완한다.

## ADR-030 인증서 교체·폐기와 반환 시점의 현재 권한

NodePeerPolicy는 version/tenant/node/epoch/expiresAt/clientFingerprints(0~2)를 갖는다. 빈 지문 집합은 전체 거절이다. 운영자가 원자 파일 교체로 old+new → new의 겹침 교체를 수행한다. trust CA는 시작 시 명시적으로 고정하며 자동 다운로드/CRL/OCSP 조회는 하지 않는다. Node는 private durable journal의 peer-policy version+원본 hash floor를 fsync한다. 낮은 version, 같은 version의 다른 내용, 손상·만료·누락은 fail closed이고 재시작도 floor를 초기화하지 않는다. live TLS 연결의 다음 요청도 최신 policy를 검사한다.

Node 서버 leaf cert/key는 다음 TLS handshake에 다시 읽어 hot reload한다. private key는 Linux regular 0600/0400 파일을 요구하고 symlink 및 과도한 파일 크기를 거절한다. 인증서와 key가 교체 중 불일치하면 handshake가 실패한다. Python CP client는 새 인증서로 새 instance를 구성해 교체한다. 이 기능은 TLS 인증서 교체이며 Ed25519 permit signing key 다중 버전 교체/CA bootstrap은 후속이다. Windows ACL 검증·운영 PKI 발급/secret manager는 미구현이다.

migration 0005의 node_channels는 tenant/node/epoch/version/endpoint/certificate hash+expiry/enabled를, node_channel_audit는 변경 이력을 저장한다. 운영자 전용 connection의 provision_channel은 인증서 DER에서 scope/expiry/hash를 계산하고 Node 잠금 뒤 expected_version CAS로 변경한다. revoke_channel도 같은 Node→channel 순서와 CAS·감사 삽입을 한 transaction으로 처리한다. runtime role은 채널/감사 INSERT·UPDATE·DELETE가 없고 channel lock_sentinel UPDATE만 허용한다. 이는 SELECT FOR SHARE를 위한 권한이며 실제 sentinel 변경은 version trigger가 거절한다. public 관리 endpoint는 없다.

네트워크 호출 중 DB lock을 잡지 않는다. response의 claim/command/tenant/project/run/Node/epoch/plan/allocations를 원 요청과 대조하고, Run→Node→channel→Resource 순으로 권한을 재확인한 transaction에서 stop receipt/전체 lease 반환/outbox를 저장한다. node epoch 또는 channel version/지문/enable/expiry가 변하면 반영하지 않는다. 인증에 사용한 channel_version과 peer_sha256을 불변 receipt 행에 함께 남긴다. 이미 폐기된 Node 인증서로 진행된 호출은 완전한 종료 응답이어도 권한 확인 없이 자원을 반환할 수 없다. 새 운영자 인증서 binding으로 기존 receipt를 관찰해 회수할 수 있다.

첫 실행 호출은 fresh online Node를 요구하고, observation-only 호출은 offline/draining 관측 상태여도 유효한 epoch/certificate binding과 실제 TLS를 확인한다. offline을 자원 해제 근거로 사용하지 않는다. Run은 여전히 scheduled이고 exit 0은 application success Evidence가 아니다.

## 운영 구성과 인계

`inv-node --serve`는 기존 tenant/node/epoch/profile/image/executable/state/public-key 설정에 `--tls-cert`, `--tls-key`, `--client-ca`, `--peer-policy`를 추가한다. 기본 listen은 127.0.0.1:8443이며 운영 LAN 노출은 확인한 주소로 별도 구성한다. operator registry의 HTTPS origin과 인증서 IP/DNS SAN이 일치해야 한다. 테스트는 loopback과 일회 합성 CA만 사용한다. CA·TLS 개인키는 Git/CI artifact/Obsidian에 저장하지 않는다.

Claude 영역의 `src/saintvision/services/nodes.py`를 읽은 한정 검토: certificateFingerprint 입력이 있으면 inventory status를 active로 만들지만 이는 TLS key 소유 증거가 아니다. 이 필드를 본 execution channel로 자동 승격하지 않는다. 등록/heartbeat의 OIDC verifier는 별도이며 운영자 승인·실제 TLS probe·core epoch/ID 매핑 adapter를 통합해야 한다. 해당 영역의 전체 코드/CI/브라우저 독립 검토를 완료한 것은 아니다.

검증 목표는 actual PostgreSQL + Python mTLS + Go + Docker 전체 경로, 잘못된 CA/URI/EKU/pin/만료, 기존 TLS 폐기, 인증서 교체/rollback, 느린 응답과 timeout, 응답 유실·재시작·observation 비실행, channel 변경 경쟁/CAS/RLS/권한/rollback이다. 실제 숫자와 CI ID는 History 검증보고에서 확인한다. 운영 CA/IdP·DNS·5대 장비·Windows/GPU·Artifact 검증·공개 업무 API·independent review는 별도다.

공식 근거: [Go crypto/tls](https://pkg.go.dev/crypto/tls#Config)의 검증 callback/ClientAuth, [Go HTTP request context](https://pkg.go.dev/net/http#Request.Context), [Python SSLContext](https://docs.python.org/3/library/ssl.html#ssl.SSLContext). Go 1.27.1 portable archive는 공식 go.dev SHA-256 `a3911b5e0e1b1053f25ed0675f4c1c6aad1e2bfcf253df2b9be4caabd2edd95d`와 일치하고 CI도 1.27.1로 고정한다.

실제 구현·CI 증거: [[2026-09-10_01-56-38_KST_NODE-TRANSPORT_Codex_검증보고]]. Python 237개(실제 mTLS/Go/Docker/PostgreSQL 통합 포함)와 Go 55 leaf case 통과. 독립 검토·운영 PKI/업무 API·장비는 pending.
