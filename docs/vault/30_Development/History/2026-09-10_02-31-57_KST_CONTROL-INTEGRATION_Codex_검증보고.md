---
doc_id: "REPORT-CONTROL-INTEGRATION-001"
title: "Codex 인증 API와 Node 관측 및 취소 검증 보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T02:31:57+09:00"
source_of_truth: "Git"
---

# Codex 인증 API와 Node 관측 및 취소 검증 보고

Task control-integration / OUT-02·04·07 / owner Codex / reviewer Claude(pending). branch agent/codex/control-integration, base `31f423679107ddc55c9d05566959d6aa69a36e2d`, 구현 `87600e9e4b5edb90a85517ebeb6c617614fbd765`. 입력 GUIDE/GOV-AGENT/GOV-GIT/PLAN-BACKEND/DB/STORAGE v1.0.0, ADR-INDEX v1.6.0, CONTROL-INTEGRATION-CONTRACT-001 v1.0.1, agent-delivery/core-reliability Skill v1.0.0. 소유자 경계를 유지하고 peer 검토를 대신 승인하지 않았다.

## 구현 결과

- RS256 access token resource server: 운영 설정의 tenant/issuer/audience/client/public JWKS만 신뢰, token 수명·scope·표준 claim 검증, live 키 폐기, 모호한 JSON/header 거절. 현재 DB project grant를 요청·재시도·SSE마다 확인한다.
- 프로젝트 runs 생성/목록/상세/cancel, nodes 목록, approvals challenge/decision, SSE API. Run cancel·버전·멱등 응답·outbox를 한 transaction에 저장한다. resourceReleasePending으로 물리 반환을 구별한다.
- outbox sequence를 Run 행 잠금 아래 발급해 late commit을 건너뛰지 않는 epoch/run/sequence cursor를 구현했다. raw outbox payload/permit/argv를 SSE에 노출하지 않는다. 스트림은 25초로 제한하고 token/권한을 재검증한다.
- mTLS Node probe의 10초 nonce·현재 channel·epoch·발급 순서·시계 오차를 transaction에서 검증한다. stale sweep은 잠금 후 최신 heartbeat를 재확인하고 Lease를 반환하지 않는다. offline 복원과 draining/quarantined 유지를 구분한다.
- 활성 실행 슬롯과 별도 취소 제어 슬롯. 동일 서명 permit의 실제 실행을 중단하고 Docker stop/delete receipt 뒤에만 Lease를 반환한다. 모르는 command 취소는 실행/영수증을 새로 만들지 않는다.
- process 64 요청, 32KiB headers, 64KiB body/5초 수신 기한, 명시적 Origin, 안전한 ProblemDetails와 traceparent. 일반 예외의 DB DSN/내부 입력은 공개하지 않는다. CLI는 명시적 config 없으면 종료하며 loopback 바인딩이다.

## 실제 검증

2026-09-10T02:30:59+09:00 GitHub artifact #10116671709에서 확인했다.

| 검증 | 실제 결과 | 근거 |
|---|---|---|
| Python 전체 | 283 tests, failures/errors/skipped 모두 0 | [[integration-87600e9-tests.xml]] |
| Linux Go race | 24 top-level / 57 leaf cases, failures/test skips 0 | [[integration-87600e9-unit.jsonl]] |
| 실제 Node 통합 | 신규 mTLS 관측/취소 6건; 기존 transport 18건 포함 | Python JUnit |
| HTTP/DB 신규 | create 멱등 경합·project 격리·grant 철회·2인 JWT 승인·outbox late commit·SSE 재연결·generic 오류 7건 | Python JUnit |
| 인증/HTTP 단위 | JWT 및 입력 경계/trace 33건 | Python JUnit |
| Core Build | success | [#34382890931](https://github.com/egparadise/SaintVision-Invion/actions/runs/34382890931) |
| Documentation Build | success | [#34382890802](https://github.com/egparadise/SaintVision-Invion/actions/runs/34382890802) |

Core CI는 Ubuntu, PostgreSQL 16, 실제 Go mTLS/Docker CPU workload, 일회 합성 CA/JWT를 사용했다. Schema 재생성 drift, wheel/sdist, Go 및 TypeScript 계약 검사도 통과했다. Go의 test file 없는 cmd/wire/probe package 표시를 실제 test skip으로 세지 않았다. 새 cancel 표본은 10초 미만을 assertion했으며 운영 P95 SLO를 측정한 것은 아니다.

로컬 초기 전체 Python 138 passed/136 skipped, 후속 JWT/HTTP 단위 33 passed, Windows Go test ./... 및 Linux cross-build exit 0. 로컬에서 건너뛴 PostgreSQL/Linux 시험은 위 CI에서 모두 실행했다. 사용자 Docker/WSL 재시작이나 기존 컨테이너 변경은 하지 않았다.

문서/ontology/check-sync 및 교차 검토 재현 명령 결과는 후속 실행 기록과 [[Codex 교차 코드 검토 - 인증과 실측 Evidence 정합성]]에 기록한다. 재현은 고정 peer 소스 11개를 사용한 한정 검토이며 P1/P2 10건 request_changes다. 해당 Agent의 수신 확인과 수정은 pending이다.

## 제한과 다음 담당자

- 이 단계의 API 준비 상태는 authenticated-control-api다. 실행 계획/approval request/서명 permit queue/dispatch·자동 heartbeat poll/sweep daemon, Artifact 성공 Evidence, 업무 CRUD/Frontend 연결은 후속이다. 테스트에서 trusted worker가 명시적으로 NodeDelivery를 호출했으며 자동 dispatcher가 동작했다고 주장하지 않는다.
- Resource server는 실제 IdP 로그인/PKCE/MFA가 아니다. 운영 CA/IdP·JWKS rollback protection·Windows ACL·GPU·실장비 5대·backup/storage제품·LAN HTTPS 배포/OTel collector는 미검증이다. CLI의 실 환경 비밀/config 값을 만들어 채우지 않았다.
- 취소가 실행 요청보다 먼저 Node에 도착해 intent가 없으면 불확실로 남는다. 물리 정지 증거 전 Lease 반환은 금지하고 deadline/후속 관찰로 해결한다. probe/outbox retention GC도 별도다.
- Claude는 core 독립 검토와 업무/identity schema adapter, CR-INT-01~03/09를 수정한다. Gemini는 CR-INT-04~08/10과 실제 API·권한·SSE·취소 화면 연결을 맡는다. Codex는 [[Codex 잔여 개발 작업과 합격 증거]]의 durable dispatch/reconciliation·Storage/Checkpoint 후속을 이어간다.

기존 draft #5 위에 draft PR을 작성하며 main에 병합하지 않는다. baseline 48 task 또는 S02/S04/S07 제품 전체를 done으로 표시하지 않는다. 외부 S12 보고는 저자 주장과 수신 hash를 보존하고 모의 SLO·Smoke·CA·교육·인수 값을 실측 Evidence로 승인하지 않았다. 기존 Codex ADR/보고·ontology projection을 유지했다.

[[ERR-CONTROL-001 Heartbeat fixture와 오류 계약 누락]] 및 [[RES-CONTROL-001 비실행 검증과 추적 오류 응답]]으로 최초 실패와 해결을 구분한다. 원본 provenance는 [[integration-87600e9-provenance.json]].

## 산출물 SHA-256

- `core-tests.xml`: `25eb48bafaa45a884526d7ebda7a4f84e5d6d6d7e61981b26aca2e86b1fba83b`
- `inv-node`: `cbd7083b0fe5e9c812bd70030f0f80d2982988386e9c6b160d30664c06540808`
- `node-unit.jsonl`: `f37ca9ebff5b739ba0489e309cdfcfaed154ab48b97ce75446b8030fa4d26cc2`
- `saintvision_control_plane-0.1.0-py3-none-any.whl`: `777a5e2d596e49aaf3b208c017467c9a480589b12c739d778ecf9bbe2ac14a7c`
- `saintvision_control_plane-0.1.0.tar.gz`: `4a19dc5cf0a99340f501292a7aa2cb097f213e025f799e9b65a6706a5bf71285`

최종 보고서 commit은 별도 same-SHA Actions로 검증하고 PR 본문에 남긴다. 보고서 자신의 SHA를 본문에 계속 되쓰는 순환 갱신은 하지 않는다.

## 2026-09-10T02:32:34+09:00 로컬 문서·동기화 검사

`python tools/check_docs.py`: exit 0, 원문 24 hash/문서 112개/task 48/outcome 12/링크·owner·DAG 통과. `python tools/check_ontology.py`: exit 0, RDF/SHACL/쿼리·projection 통과. `python tools/test_sync.py`: exit 0. `git diff --check`: exit 0. 실제 export는 아래 기록한다.

## Obsidian 실제 동기화

- 2026-09-10T02:32:35+09:00 `python tools/sync_obsidian.py --check --state .work/integration-obsidian-sync-state.json`: exit 0; `CHECK: 160 managed files, 24 pending exports, 0 conflicts. No writes.`.
- 2026-09-10T02:32:35+09:00 `python tools/sync_obsidian.py --apply --state .work/integration-obsidian-sync-state.json`: exit 0; `EXPORTED: 24 files; all 160 destination hashes match. Unmanaged files untouched.`.

이 실제 결과를 포함한 보고서도 다시 export하고 전체 파일 hash 일치를 확인한다. 최종 보고서 SHA-256은 PR 인계에 기록한다. 작업별 state로 확인 이후 발생한 다른 Agent 편집을 보호하며 공유 state를 무조건 덮어쓰지 않는다.
