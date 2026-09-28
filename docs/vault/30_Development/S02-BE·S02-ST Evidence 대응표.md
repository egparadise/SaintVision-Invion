---
doc_id: "CLAUDE-S02-BE-ST-EVIDENCE-MAP-001"
title: "S02-BE·S02-ST Evidence 대응표 — OIDC·mTLS 등록·Heartbeat와 제공 폴더·DataLocation 카탈로그를 실제 API·브라우저 여정·인증 실패 기록(#120 collector·#125/#138 체크리스트·VF-CL-01 카탈로그·S02-FE Chrome 실측·#134 파일럿 3노드)에 file:line과 run ID로 대응, 사용자 입력 U1~U6·외부는 BLOCKED_EXTERNAL (구현 추가 0, 카드 ba)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T10:57:39+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S02-BE", "S02-ST"]
tags: ["S02-BE", "S02-ST", "AC-02", "evidence", "oidc", "mtls", "heartbeat", "storage-catalogue", "claude"]
---

# S02-BE·S02-ST Evidence 대응표 (2026-09-28, 카드 ba)

task-registry: S02-BE scope "OIDC·mTLS 등록·Heartbeat", S02-ST scope "제공 폴더·DataLocation 카탈로그", evidence 둘 다 "실제 API·브라우저 여정·인증 실패 기록", AC-02. 원칙은 #155·#160·#161·#163과 같다: 이미 있는 것을 file:line·run ID로 대응하고 공백만 골라낸다, 관측 안 된 값은 NOT_OBSERVED, 판정 논리 복제 없음. 사용자 입력·외부가 필요한 것은 **BLOCKED_EXTERNAL**로 두고 [[S02_선행입력_체크리스트_2026-09-22]]의 U1~U6에 연결한다. 결론 먼저 — **두 scope 모두 코드·시험·hosted lane과 실측 기록이 있다. 이 PR은 대응표만 담는다(구현·시험 추가 0). 남은 것은 U2 실 IdP·U3 운영 CA·U4 DNS·U5 물리 5노드·U6 Storage 제품 값(BLOCKED_EXTERNAL) 5건과 `public.audit_events` RLS(F-S02-01 별도 카드) 1건이다.**

## 0. 사용자 입력 U1~U6 (체크리스트 §0~§5)와 이 대응표의 관계

| U | 체크리스트 | 무엇 | 이 대응표에서 |
|---|---|---|---|
| U1 | §0 결정 1건 | 토폴로지 | **결정됨** `cp-colocated-plus-four-workers`(ADR-100, #134 v0.2) |
| U2 | §1 IdP(OIDC) | 실 IdP issuer·JWKS·client id | BLOCKED_EXTERNAL — 시험은 synthetic issuer/JWKS, S02-FE 실측은 Dev IdP(`.work/dev/dev_idp.py`) |
| U3 | §2 CA·mTLS | 운영 CA·Node client cert·`INV_NODE_MTLS_CA_BUNDLE` | BLOCKED_EXTERNAL — 시험은 synthetic PKI(`pki_support.py`), 파일럿은 state 내부 CA |
| U4 | §3 DNS·호스트명 | CP/portal/IdP/Node 이름 | BLOCKED_EXTERNAL(#134 A2 사용자 결정) |
| U5 | §4 물리 PC 5대 | 인벤토리·계정·허용 폴더 | BLOCKED_EXTERNAL(#134 v0.2: Ubuntu worker 3 등록·1 미등록·CP 겸임 BLOCKED, C2 폴더 사용자 결정) |
| U6 | §5 Storage 제품 값 | contribution 루트·storage-policy·아카이브 대상 | BLOCKED_EXTERNAL(체크리스트 §5) |

## 1. 인용 run·근거

| lane / 근거 | run / head | 결과 |
|---|---|---|
| Backend | **36351202242** `a0dab579`(#125 = base 집합) | 2929 passed / 47 skipped / 0 failed — `tests/test_api.py` 28·`tests/core/test_identity.py` 10·`test_node_tls.py` 8·`test_discovery_response_contract.py` 4·`tests/integration/test_storage_catalog_api.py` 8·`test_discovery_machine_credentials.py` 5·`tests/core/test_lan_storage.py` 6·`tests/test_lan_pilot_multinode.py` 13 포함 |
| Backend(#120) | **36351674808** `fc0bf0ce` | S02 collector 실PG 1회: API 28 passed·AC-02 4/4·RLS VIOLATIONS 1(E2 audit_events) → 묶음 FAIL(acceptanceClaim=false); evidence `Evidence/s02-db-acceptance/s02-acceptance-fc0bf0ceb590-20260927.*`(#120 브랜치) |
| desktop-browser | **36364528322** `30f5ca83`(#153) | pass — 실 브라우저 여정 5(quorum snapshot·stale run/revoked review·catalogue owner scope/revocation·committed model/current permission·full studio login→approval→logout), `desktop-browser.yml:57-77` 집합 고정 |
| Core | **36353272311** `bc27588d` | `lan-installer-tests.xml` 15/15(`test_lan_storage_install`+`test_workspace_upgrade`), core-tests 3253/0 failed |
| S02-FE 실측(Gemini) | [[2026-09-23_S02-FE_실제API_Chrome_로그인_Node0대_401_403_수용실측_Gemini]] · 독립검토 [[2026-09-23_PR77_S02-FE_실제API_Chrome_독립검토_Claude]] | Headless Chrome 153, 실 Uvicorn 8080·Dev IdP 8090(실 OIDC `/auth/authorize`·`/auth/token`·JWKS): 로그인 성공·Node 0대 정직 표기·미인가 프로젝트 403 `AUTH-0030`·토큰 만료 401 `AUTH-0050` 재로그인 — 정본 `Evidence/s02_fe_real_api_acceptance.json` |
| LAN 파일럿 | #134 v0.2(`28e8836e`) · [[2026-09-23_06-15-00_KST_LAN-PILOT-CP-COLOCATED_Codex_구현]] | Ubuntu worker 3 등록(online 2·offline 1, CP 관측 skew −0.05/−0.08 s), state 내부 CA로 CSR enroll(`tools/lan_pilot.py enroll`), CP 겸임 BLOCKED(API 1.41) |
| 체크리스트 | #125 v1.2(`a0dab579`) · #138(§7 configuration-readiness route) | 표면 분리: core API `/v1/health`·`/v1/readiness`(`src/saintvision/api/app.py:141~151`) vs 운영 factory `/readyz`·`/v1/session`(`inv/app.py:272,:297`) |
| VF-CL-01 | [[2026-09-15_03-10-00_KST_VF-CL-01_Claude_DataLocation재사용경계와카탈로그시험]] | DataLocation 재사용 경계·카탈로그 시험 |

## 2. 대응표

### 2.1 OIDC (S02-BE)

| 항목 | 코드 | 시험 | hosted / 실측 | 상태 |
|---|---|---|---|---|
| access token은 검증된 issuer·audience·JWKS·설정 tenant에서만 신뢰; 헤더는 신뢰에 영향 없음; JWKS 제거·만료 시 fallback 없음 | `services/control-plane/src/inv/identity.py:69 AccessTokens`(`:84 _keys`, `:115 verify`), `:41 public_subject`, `:51 trusted_file` | `tests/core/test_identity.py:19,:50,:66,:71,:83,:98` | Backend 36351202242 | 관측됨 |
| 세션 조회·readiness 표면 | `inv/app.py:297 /v1/session`, `:272 /readyz`, `:268 /healthz`; core API `/v1/health`·`/v1/readiness` | `tests/core/test_workspace_api_boundary.py` 4 · #138 configuration-readiness route 시험 | Backend | 관측됨(#138 병합 대기) |
| 실 브라우저 로그인·401/403 ProblemDetails·재로그인 | web(Gemini) + `inv/app.py` | S02-FE Chrome 4 저니(PASS 4) · desktop-browser 여정 5 | S02-FE 실측 `ae4d9003` · desktop-browser 36364528322 | 관측됨(Dev IdP) |
| 실 IdP(운영 issuer·JWKS·client) | — | — | — | **BLOCKED_EXTERNAL(U2)** |

### 2.2 mTLS 등록·Heartbeat (S02-BE)

| 항목 | 코드 | 시험 | hosted / 실측 | 상태 |
|---|---|---|---|---|
| Node 등록(bootstrap token 1회·tenant 결속·enroll 응답 형태) | `src/saintvision/api/v1/nodes.py:48 POST /nodes`(enroll) | `tests/test_api.py:144,:168,:205,:220,:230` | Backend; #120 collector `allowed-node-registration-and-read`·`bootstrap-token-replay-blocked` PASS(run 36351674808) | 관측됨 |
| Heartbeat 전진·replay 무시·파티션 착지·liveness sweep | `nodes.py:125 POST /nodes/{node_id}/heartbeats`, `:209 POST /nodes/liveness-sweeps`; 커널 `inv/app.py:561-565 /v1/projects/{project}/nodes[/…/resource-usage]` | `tests/test_api.py:326,:353,:400` · `tests/test_partitions_logic.py` | Backend | 관측됨 |
| Node channel: 인증서 identity(SPIFFE URI·epoch)·channel proof·provision/revoke | `inv/node_channels.py:58 certificate_identity`, `:84 ChannelProof`, `:104 assert_channel`, `:120 NodeChannels`, `:151 provision_channel`, `:205 revoke_channel` | `tests/core/test_node_tls.py` 8(:140 identity 검증 뒤 전송, :152 잘못된 authority 무전송, :174 redirect 미추종) · `tests/integration/test_lan_pilot_colocation_revocation.py` 1 · `test_containment.py`(channel) | Backend·Core | 관측됨 |
| discovery credential(digest-only·tenant/expiry/revocation·issuer budget 10·동시 발급 직렬화) | `tools/discovery_credential.py`, `tools/provision_credentials.py` | `tests/integration/test_discovery_machine_credentials.py` 5 · `tests/core/test_discovery_response_contract.py` 4 | Backend | 관측됨 |
| 파일럿 실 등록(CSR enroll·heartbeat·skew) | `tools/lan_pilot.py enroll/status/observe` | `tests/test_lan_pilot_multinode.py` 13 · #134 실측(status: online 2·offline 1, `inv.nodes.clock_skew_seconds`) | #134 S-1/S-2 | 관측됨(state 내부 CA) |
| 운영 CA·Node client cert·`INV_NODE_MTLS_CA_BUNDLE` | — | — | — | **BLOCKED_EXTERNAL(U3)**; #125 §2 신뢰점 분리 |
| 물리 5노드 heartbeat·mTLS | — | — | — | **BLOCKED_EXTERNAL(U5)**: 등록 3(online 2)·미등록 1·겸임 BLOCKED |

### 2.3 인증 실패 기록 (S02-BE, evidence "인증 실패 기록")

| 항목 | 코드 | 시험 | hosted / 실측 | 상태 |
|---|---|---|---|---|
| 거부·인증 실패 audit 기록(redaction, 트랜잭션 밖) | `src/saintvision/services/audit.py:47 redact`, `:66 record_event`, `:106 record_denial_out_of_band` | `tests/test_api.py:242 denials_are_recorded` · `:263,:275,:289`(타 tenant/project 차단) | Backend; #120 `authentication-failures-recorded`·`cross-tenant-project-isolation` PASS | 관측됨 |
| 인증 실패 기록 테이블의 RLS ENABLE+FORCE | — | `tools/collect_rls_evidence.py` E2 위반 1(#120 evidence) | Backend 36351674808 | **F-S02-01 별도 카드** |

### 2.4 제공 폴더 (S02-ST)

| 항목 | 코드 | 시험 | hosted / 실측 | 상태 |
|---|---|---|---|---|
| contribution 등록·활성화·목록(소유자 명시 제공, 기본 미제공) | `src/saintvision/api/v1/storage.py:65 POST /storage/contributions`, `:145 …/activation`, `:177 GET /storage/contributions` | `tests/integration/test_storage_catalog_api.py:101`(revocation) · `tests/core/test_lan_storage.py` 6 · `tests/test_storage_check_integrity.py` 13 | Backend | 관측됨 |
| 경로 안전(정규화·junction·범위 밖 거부) | `src/saintvision/storage/pathsafe.py:163/182/212`, `readroot.py:109 ReadRoot` | `tests/test_verification_readroot.py` 18 | Backend | 관측됨 |
| LAN 설치본 storage source root·installer | `tools/check_storage_bundle.py`, `check_lan_storage_readiness.py` | `tests/integration/test_lan_storage_install.py` 5 | Core 36353272311 15/15 | 관측됨(hosted Linux Docker) |
| 파일럿 실제 제공 폴더·storage-policy·Storage 제품 값 | — | — | — | **BLOCKED_EXTERNAL(U5 C2·U6)**; `inv.resources` 0행(#134 S-2) |

### 2.5 DataLocation 카탈로그 (S02-ST, VF-CL-01)

| 항목 | 코드 | 시험 | hosted / 실측 | 상태 |
|---|---|---|---|---|
| 소유자 범위 목록·비소유/타 tenant 비공개·revocation 뒤 숨김·페이지네이션·위조 cursor | `src/saintvision/api/v1/storage.py:201 GET /storage/locations`, `:227 /storage/resolve`, `:249 /storage/replica-status` | `tests/integration/test_storage_catalog_api.py:70,:87,:101,:154` | Backend | 관측됨 |
| 식별자 위조·미발급·suspension·읽기 route의 변경 미전달·URI 반향 없음 | 동일 route + `inv/business_auth.py:14 permission` | `test_storage_catalog_api.py:112,:120,:127,:147` | Backend | 관측됨 |
| 브라우저: 카탈로그 소유 범위·revocation 여정 | web + 위 route | desktop-browser `test_browser_real_catalogue_owner_scope_and_revocation` | desktop-browser 36364528322 | 관측됨(hosted runner) |
| DataLocation 재사용 경계 | VF-CL-01 History | [[2026-09-15_03-10-00_KST_VF-CL-01_Claude_DataLocation재사용경계와카탈로그시험]] | Backend | 관측됨 |

## 3. 공백 목록 (구현·시험 추가 없음)

| # | 공백 | 분류 |
|---|---|---|
| E1 | 실 IdP(issuer·JWKS·client id) — 시험·실측은 synthetic/Dev IdP | BLOCKED_EXTERNAL(U2) |
| E2 | 운영 CA·Node client cert·CA bundle | BLOCKED_EXTERNAL(U3) |
| E3 | DNS·호스트명 | BLOCKED_EXTERNAL(U4) |
| E4 | 물리 5노드(등록 3·미등록 1·겸임 BLOCKED)·계정·허용 폴더 | BLOCKED_EXTERNAL(U5) |
| E5 | Storage 제품 값(contribution 루트·storage-policy·아카이브) | BLOCKED_EXTERNAL(U6) |
| G1 | `public.audit_events` RLS ENABLE+FORCE(인증 실패 기록의 tenant 경계) | F-S02-01 별도 카드(Codex 판정) |

작은 PG-free 시험으로 메울 행동 공백 없음(OIDC 검증·등록·replay·heartbeat·channel·discovery·카탈로그 격리·audit 기록이 전부 기존 시험으로 단언). 따라서 docs-only.

## 4. 경계

로컬 실 PG·Docker·브라우저·전체 suite·무거운 명령 없음. 판정 논리 복제 없음. owner Claude / reviewer Codex / 병합 금지. worktree 재사용, branch `agent/claude/s02-be-st-evidence-map`, base `1e8baf04`. S02-BE/ST `planned` 유지(#138·#125 병합 뒤 §7 route 인용 갱신). 다음 첫 행동: Codex 검토.
