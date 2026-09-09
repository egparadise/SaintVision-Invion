---
doc_id: "CONTROL-INTEGRATION-CONTRACT-001"
title: "Codex Control API 인증과 Node 관측 계약"
version: "1.0.1"
status: "review"
author: "Codex"
updated: "2026-09-10T02:26:01+09:00"
source_of_truth: "Git"
---

# Codex Control API 인증과 Node 관측 계약

Task control-integration / owner Codex / reviewer Claude(pending), base 31f423679107ddc55c9d05566959d6aa69a36e2d. 기존 Core와 Claude CRUD 사이의 보안·동시성 adapter다. Claude 069ae9f/Gemini c323f55 구현 전체를 병합하거나 승인한 기록이 아니다.

## ADR-031 Resource server와 프로젝트 권한

AccessTokens는 운영자가 제공한 issuer/audience/tenant/client allowlist와 최대 7일 유효 public JWKS bundle을 사용한다. RS256만 허용하고 typ at+jwt, signature, issuer, 단일 audience, iat/exp/nbf, 최대 1시간 수명, client_id/jti/sub, inv.api scope를 검증한다. 중복 JSON 키·비정규 base64url·JWT header의 jku/crit/알고리즘 변경은 거절한다. 키 선택은 로컬 trust bundle에서만 하며 discovery/공격자 URL/OS 인증 fallback을 사용하지 않는다. JWKS는 요청마다 읽으므로 교체·폐기·만료가 다음 검증에 반영된다. 이 offline bundle은 운영자 소유 파일이며 과거 파일을 운영자가 복구했을 때까지 막는 외부 anti-rollback 저장소는 별도다.

principal은 configured tenant와 issuer/sub hash로 고정하고 JWT tenant/roles 또는 X-Subject 헤더로 만들지 않는다. project_grants의 현재 can_request/can_approve/enabled를 매 작업/재요청마다 검사한다. 다른 issuer의 같은 sub는 다른 actor다. grant 발급 및 project_nodes 공유 설정은 운영자 역할만 쓴다. OAuth IdP의 실제 사용자 로그인/PKCE/MFA·인증서 발급은 운영 연결 단계이며 합성 발급기를 운영 IdP로 표시하지 않는다.

/v1/projects 및 프로젝트별 runs 생성/목록/상세/cancel, nodes 목록, approvals challenge/decision, runs events를 제공한다. 취소는 Run 상태/버전/멱등 ledger/cancel_requested outbox를 같은 transaction에 저장하며 resourceReleasePending을 구분한다. 임의 상태 변경·사용자가 제출한 policy/approval actor·signed permit/receipt 저장 endpoint는 제공하지 않는다. 실행 계획/업무 CRUD의 나머지는 owner adapter로 연결한다.

입력은 실제 수신 기준 64KiB/5초, 중복 민감 헤더와 모호한 JSON 거절, 명시적 Origin 허용, bearer header만 사용한다. 문제 응답은 내부 SQL·DSN·원시 입력을 포함하지 않는다. inv-control-plane entry point는 명시적 config/DSN/epoch 없이 시작하지 않고 loopback에만 바인딩한다. LAN HTTPS ingress와 실제 IdP는 별도다. /readyz의 ready는 인증된 Control API의 준비 상태이며 executionDispatcher 미설정을 함께 표시한다.

## ADR-032 이벤트 재연결·현재 Node 관측·원격 정지

migration 0006의 outbox sequence는 Run 행 잠금 아래 발급해 같은 Run의 commit 순서와 일치시킨다. 전역 sequence/created_at만으로 late commit을 건너뛰지 않는다. 이벤트 내용은 immutable이고 published_at만 수정한다. SSE cursor는 epoch:runId:sequence이며 다른 scope 또는 미래 cursor는 거절한다. 25초 스트림 뒤 새 bearer로 재연결하고 1초마다 현재 token/JWKS와 grant를 다시 확인한다. 전송 event는 ID/type/run/sequence의 허용 필드뿐이며 raw outbox payload/argv/permit은 내보내지 않는다. baseline stream은 보존 중인 outbox이며 GC·retention gap protocol은 별도다.

Node /v1/heartbeats는 기존 mTLS의 현재 CP 허용 정책 아래 난수 nonce와 Node tenant/ID/epoch/profile/server time을 응답한다. Control Plane은 DB issued_at의 10초 일회 nonce, 현재 channel, scope, 양 끝 기준 5초 clock bound, 최신 probe 발급 순서를 검증한 transaction만 heartbeat를 갱신한다. offline만 online으로 복원하며 draining/quarantined는 관측으로 해제하지 않는다. 60초 경과 감지는 행 잠금과 현재 timestamp를 다시 검사하고 Lease는 반환하지 않는다. 이는 Agent 생존/identity 관측이며 GPU/Docker capability 실측을 대체하지 않는다.

/v1/executions/cancel은 별도 제어 슬롯에서 같은 서명 permit을 검증한 뒤 active execution context를 취소하고 정지/삭제/receipt를 기다린다. 실행 슬롯이 점유되어도 취소가 들어간다. 기존 intent가 없으면 실행도 생성하지 않고 성공 영수증도 만들지 않는다. 취소 직전 전송이 아직 Node에 도착하지 않은 경우는 불확실로 남으며 물리 정지 확인 전 Lease 반환을 하지 않는다. Node timeout 및 후속 observation/cancel로 회수한다. 취소 지연 10초는 시험 표본의 결과를 따로 보고하며 운영 SLO로 일반화하지 않는다.

## 검증·다음 인계

로컬 Python 138 passed / PostgreSQL·Linux 통합 136 skipped; Windows Go 및 Linux cross-build를 수행했다. 실제 API/JWT/PostgreSQL·Go race·mTLS/Docker 통합 숫자는 CI 원본과 History 보고서에서 확인한다. 공통 JSON Schema의 EmptyRequest/RunCancelInput/NodeProbeInput/NodeProbeResult에서 생성물을 재생성한다.

Claude: 검증 identity와 기존 OIDC placeholder/등록 inventory를 연결하되 certificateFingerprint 입력을 key 소유 증거로 승격하지 않는다. 현재 inv 스키마와 Claude 별도 SQLAlchemy 모델의 ID·상태·epoch/량 단위 변환은 명시적 migration/adapter 검토가 필요하다. Gemini: JWT/local UI persona·SSE·취소 releasePending을 실제 API에 연결하고 시뮬레이션 성공을 운영 Evidence로 표시하지 않는다. 교차 검토 pending.

공식 근거: [RFC 9068 access-token validation](https://www.rfc-editor.org/rfc/rfc9068.html), [PyJWT API](https://pyjwt.readthedocs.io/en/stable/api.html). PyJWT 2.13.0을 명시적으로 고정했다.

## 오류 및 요청 상관관계 계약

ProblemDetails 정본 Schema와 Python/TS/Go 생성물을 추가했다. 모든 오류는 code/category/retryable/traceId/causeRef/evidenceId 및 RFC 형태의 type/title/status/detail을 갖는다. 실제 원인·Evidence 참조가 없으면 null로 두며 추측 ID를 발급하지 않는다. traceId는 업무 ID와 별개다. 지원하는 version 00 traceparent의 정상 trace ID는 유지하고 server span ID는 새로 발급한다. 0 ID·중복·잘못된 길이·지원하지 않는 version은 새 trace로 대체하고 외부 문자열을 반사하지 않는다. unknown flags는 sampled bit만 보존한다. 오류·성공·capacity 초과 응답에 같은 trace 헤더를 넣는다. 이 상관관계 헤더는 인증·Evidence 권한이 아니며 OTel span 수집기 설치 완료를 의미하지 않는다.

기준: [W3C Trace Context](https://www.w3.org/TR/trace-context/). 입력은 process당 64개 동시 요청·32KiB headers·64KiB body·5초 수신 기한으로 제한한다. 공개 ingress의 배포별 제한은 별도 설정이다.

최종 실제 증거: [[2026-09-10_02-31-57_KST_CONTROL-INTEGRATION_Codex_검증보고]]. Python 283개 및 Go 57 leaf case 통과. 다른 Agent 수정 요청: [[Codex 교차 코드 검토 - 인증과 실측 Evidence 정합성]].
