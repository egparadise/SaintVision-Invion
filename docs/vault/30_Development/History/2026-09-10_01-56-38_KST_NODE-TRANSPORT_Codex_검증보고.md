---
doc_id: "REPORT-NODE-TRANSPORT-001"
title: "Codex Node mTLS 전달과 인증서 권한 검증 보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T01:56:38+09:00"
source_of_truth: "Git"
---

# Codex Node mTLS 전달과 인증서 권한 검증 보고

Control Plane의 서명된 permit을 Go Node에 mTLS로 전달하고 실제 Docker 정지 영수증을 현재 인증서 권한과 함께 자원 반환 transaction에 연결했다. 인증서 폐기/교체 중에는 실행을 취소하거나 반환을 거절하며, 응답을 잃어도 재시작 후 관찰 전용 호출로 새 실행 없이 영수증을 회수한다.

- task node-transport, OUT-02/AC-02·OUT-03/AC-03·OUT-04/AC-04, owner Codex / reviewer Claude(pending).
- branch `agent/codex/node-transport`, base `75e22940ca9807f603d4787619f9c8e9599e31dd` (#4 node-runtime 위의 작업).
- implementation `59baad93cbe2f11c7b758b0ee668b8fbd67ce8ac`, commit·push exit 0. 시작 doc/version/scope: [[2026-09-10_01-34-14_KST_NODE-TRANSPORT_Codex_개발과정]].
- 계약 [[Codex Node mTLS 전달과 인증서 권한 계약]] NODE-TRANSPORT-CONTRACT-001 v1.0.0, ADR-029/030(ADR-INDEX-001 v1.5.0), migration 0005, JSON Schema v1alpha1 및 생성 Python/TS/Go·Node embedded schema.
- Skill agent-delivery/core-reliability v1.0.0, Go 1.27.1, jsonschema/v6 v6.0.2, cryptography 50.0.1. 개발 Prompt는 사용자 남은 작업 진행 및 critical 외 승인 자동 지시다.
- 제품 Prompt/Context/Harness/ROOF/Graph/Agent 버전 연결은 미완료다. 기존 합성 permit·FROM scratch Go probe와 일회 CA/TLS leaf를 사용했다. 실제 사용자 장비/운영 개인키를 바꾸지 않았다.

## 구현과 검증 범위

TLS 1.3의 CA/hostname/EKU/단일 tenant·Node·epoch URI/leaf pin을 요청 전 확인한다. Node도 CP 인증서 소유와 현재 allowlist를 확인하며 헤더 주장은 인증으로 사용하지 않는다. 명시적 CA, 연결/본문/시간 제한, generic 오류, 재연결/redirect 금지, SSLKEYLOGFILE 영향 차단을 적용했다.

버전형 peer policy의 hash/version floor를 durable journal에 저장해 재시작 후 rollback을 거절한다. old+new → new 겹침 교체, live connection의 현재 정책 재검사와 활성 실행 취소, server leaf hot reload를 검증했다. 기존 TLS CA root 및 Ed25519 permit signing key 교체는 후속이다.

DB node_channels는 운영자 CAS·감사·tenant RLS로 관리한다. runtime의 설정 쓰기를 막고 stop receipt를 저장할 때 current Node epoch/channel version/지문/expiry를 다시 잠근 상태로 확인한다. receipt에 channel_version/peer_sha256을 함께 남기며 모든 lease 반환/outbox가 같은 transaction이다. 네트워크 중 DB lock을 유지하지 않는다.

관찰 endpoint는 기존 intent만 회수·정리하며 처음 보는 유효 permit도 실행하지 않는다. timeout/응답 유실은 자원 반환 근거가 아니고 실제 Node stop receipt가 필요하다. Run은 scheduled이며 exit 0을 application success Evidence로 사용하지 않는다.

## 실제 명령과 합격 증거

| 명령·환경 | exit | 확인 결과 |
|---|---|---|
| Windows Go test ./... / Linux cross-build·runtime test compile | 0 | 실제 TLS unit 및 Linux 코드·시험 컴파일 |
| Windows pytest -q --junitxml=.work/transport-local-tests.xml | 0 | 114 passed / 121 skipped; 이후 DB 통합 2건 추가는 CI에서 실행 |
| CI Go 1.27.1 go test -race -json ./... | 0 | **22 top-level / 55 leaf cases, failures 0 / test skips 0** |
| CI Python 3.12 + PostgreSQL 16 + Linux Docker pytest | 0 | **237 tests / failures 0 / errors 0 / skipped 0** |
| CI inv-node·probe·supervisor + FROM scratch Docker image build | 0 | 실제 CPU 합성 격리 image 및 Go Node 생성 |
| CI Alembic upgrade head (pytest fixture) | 0 | 고유 합성 DB에 0001~0005 실제 적용 |
| 계약 regenerate + git diff --exit-code / wheel·sdist / Go contracts / TS strict | 0 | schema drift 없음 및 패키지 빌드 |

기존 Python 194 + 신규 43(실제 Python TLS 경계 25 + PostgreSQL/Go/mTLS/Docker 통합 18)이다. Go leaf 55는 parent/subtest를 중복 합산하지 않았다. 테스트 없는 4개 command/helper package-level skip은 test case skip과 구분했다.

신규 통합 18개는 정상 remote execution과 인증 metadata, 관찰 비실행, 응답 유실 뒤 Node 재시작, client timeout 취소, 잘못된 CP CA/URI/expiry/EKU/pin 5건, live CP 폐기와 새 peer 회수, channel 폐기와 receipt commit 경쟁·Node leaf 교체, 재시작 policy rollback, runtime 권한·tenant RLS, 동시 CAS, audit failure rollback, receipt/outbox failure rollback, graceful Node server shutdown, 다른 command 응답 거절을 포함한다. Python TLS 25개와 Go unit는 추가로 request 전 잘못된 서버 검증, 느린 response와 재연결 금지, 기존 TLS connection 폐기, framing/JSON/정책 경계를 확인했다.

- Core Build [34379287327](https://github.com/egparadise/SaintVision-Invion/actions/runs/34379287327): 동일 구현 SHA / success.
- Documentation Build [34379287316](https://github.com/egparadise/SaintVision-Invion/actions/runs/34379287316): 동일 구현 SHA / success.
- artifact `10115267609`, 원본 확인 `2026-09-10T01:55:08+09:00`.
- 원본 JUnit [[transport-59baad9-tests.xml]], Go JSON [[transport-59baad9-unit.jsonl]], archive/산출물 hash와 출처 [[transport-59baad9-provenance.json]].
- 개발 중 발견/대응은 별도 [[ERR-TRANSPORT-001 TLS fixture와 연결 종료 경계 검토]] → [[RES-TRANSPORT-001 엄격한 인증서와 원 socket 기한 집행]].

## 남은 계약과 인계

Claude: TLS/channel/receipt transaction 독립 검토와 기존 enrollment/heartbeat/capability adapter 통합. `src/saintvision/services/nodes.py` 입력 certificateFingerprint만으로 inventory active를 설정하는 경로는 실제 TLS 소유 증거가 아니므로 execution channel로 자동 승격하지 않는다. 현재 읽기 범위의 한정 소스 검토이며 Claude 전체 구현·CI 검토 완료가 아니다. 사용자 OIDC와 Node mTLS principal, UUID epoch/ID mapping, 운영자 승인 경계를 연결해야 한다.

Codex 다음: 인증된 public 업무 API·outbox dispatcher/cancel·상태/Evidence adapter의 동시성 계약과 Backend/Frontend 인계 검토. Gemini: backend의 stop/exit/application success 구분을 실제 UI와 연결. owner별 독립 검토·수신은 pending이다.

**확인 범위는 Linux CPU 합성 CA/PostgreSQL/Docker다.** 운영 CA 발급·bootstrap/IdP/DNS·secret manager/Windows ACL·Windows/GPU/5대 장비·public API·Artifact/application Evidence·자동 dispatch는 미완료다. CRL/OCSP/CA 자동 갱신을 구현했다고 주장하지 않는다. 네트워크·폐기 감지 설정값은 운영 SLO 실측값이 아니다. 사용자 Docker/WSL 또는 운영 인증서를 변경하지 않았다. baseline 48 task 및 S02/S03 전체를 done으로 올리지 않는다.

Obsidian 외부 관리 파일 10개와 신규 S11-FE 보고 1개는 [[외부 인계 제안 수신과 정본 동기화 복구]]에 수신 hash와 검증 한계를 기록했다. 기존 Codex ADR·증거를 보존하고 새 보고는 저자 주장의 미검증 제안으로 수용했다. 정본은 docs/vault이며 원문 docs/sources는 보존했다.

마지막 보고서 commit의 Actions는 해당 SHA로 별도 확인해 draft PR에 남긴다. 보고서 자체 SHA를 문서에 되쓰는 순환 갱신은 하지 않는다. 실제 문서 검사·Obsidian 동기화는 아래 실행 기록에 추가한다.

## 산출물 SHA-256

- `inv-node`: `ccbff3e31aeb3bdccb4eb0a144ec289f72e4b97918eea2d31623aeb1bb6e3bfd`
- `node-unit.jsonl`: `03a0d7a79061577e924d0369fccbf948abccf92465598c49afa223bb64881c8e`
- `core-tests.xml`: `58fa490cb3d46d23d757e5ca64c68d5ad552d6b1d0bf0da75c24b31b40bfb9a6`
- `saintvision_control_plane-0.1.0-py3-none-any.whl`: `657af17b0b0598d3d1cd9fdb577d2cd03a4586950c25add7d1d62450952b7e54`
- `saintvision_control_plane-0.1.0.tar.gz`: `1c7db9631fd296b740fcc19363f1b78e5a1cf7f7e11db4e11cf6ce20735d6d7d`

## 2026-09-10T01:56:59+09:00 보고서 포함 로컬 문서 검사

- 프로젝트 requirements 환경의 `python tools/check_docs.py`: exit 0; 24 original hashes, 104 versioned documents, wiki links, 48 tasks, 12 outcomes, owner/reviewer/skills, dependency DAG PASS.
- `python tools/check_ontology.py`: exit 0; RDF/TTL/JSON-LD, task mappings, positive SHACL, invalid fixtures 4개 거절, competency query 4개, Obsidian mirrors PASS.
- `python tools/test_sync.py`: exit 0; 3 tests OK. `git diff --check`: exit 0. 문서 검사는 제품/장비 시험과 별도로 기록한다.

## Obsidian 실제 동기화

- 2026-09-10T01:57:00+09:00 `python tools/sync_obsidian.py --check --state .work/transport-obsidian-sync-state.json`: exit 0; `CHECK: 148 managed files, 20 pending exports, 0 conflicts. No writes.`.
- 2026-09-10T01:57:00+09:00 `python tools/sync_obsidian.py --apply --state .work/transport-obsidian-sync-state.json`: exit 0; `EXPORTED: 20 files; all 148 destination hashes match. Unmanaged files untouched.`.

이 실제 결과를 포함한 보고서도 다시 export하고 전체 파일 hash 일치를 확인한다. 최종 보고서 SHA-256은 PR 인계에 기록한다. 작업별 state로 확인 이후 발생한 다른 Agent 편집을 보호하며 공유 state를 무조건 덮어쓰지 않는다.
