---
doc_id: "REPORT-APPROVAL-BOUNDARY-001"
title: "Codex 승인 경계 구현 검증 및 인계 보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-09T23:03:51+09:00"
source_of_truth: "Git"
---

# Codex 승인 경계 구현 검증 및 인계 보고

승인 내용·actor·scope·expiry·epoch를 고정하고 nonce/vote/audit/outbox/Run 전이를 원자적으로 처리하는 내부 서버 계약을 구현했다. 동일 내용 동시 재시도는 commandId 1개를 반환한다. 신뢰된 인증/PDP·실제 명령 소비자·장비 실행은 후속이며 S04 전체 완료를 뜻하지 않는다.

- Task approval-boundary / OUT-04·AC-04 / owner Codex / reviewer Claude(pending).
- base `33833dda70207cee39e73fb097140f9ad8abf3ad`; 구현 `73e8774035a6a8677e5dfd317b444c6fa60a331f`.
- branch `agent/codex/approval-boundary`; core-foundation PR #1 위에 쌓인 독립 작업 브랜치.
- 시작·입력 doc/version/scope: [[2026-09-09_22-25-39_KST_APPROVAL-BOUNDARY_Codex_개발과정]].
- 계약 [[Codex 승인 경계 계약과 인계]] APPROVAL-CONTRACT-001 v1.0.0, ADR-INDEX-001 v1.2.0(ADR-024), JSON Schema v1alpha1, migration 0002, agent-delivery/core-reliability Skill v1.0.0.
- 개발 Prompt: 사용자 후속 개발 및 critical 외 승인 자동 진행 지시. 제품 Prompt/Context/Harness/ROOF/Graph 버전은 미연동이고 `roof:test:1`은 합성 시험 값이다.

## 실제 검증

| 명령·환경 | exit | 실제 결과 |
|---|---|---|
| Windows Python `pytest -q --junitxml=.work/approval-local-tests.xml` | 0 | 63 passed / PostgreSQL 38 skipped |
| CI Python 3.12/PostgreSQL 16 `pytest --junitxml=dist/core-tests.xml` | 0 | **101 tests / failures 0 / errors 0 / skipped 0** |
| Alembic upgrade head | 0 | CI 고유 테스트 DB에 0001·0002 실제 적용; 비owner/NOBYPASSRLS runtime으로 시험 |
| generate_contracts.py + generated git diff --exit-code | 0 | Python/TypeScript/Go 생성 계약 일치 |
| python -m build services/control-plane --outdir dist | 0 | wheel/sdist 빌드 |
| go test ./... | 0 | 생성 Go 계약 컴파일; 실제 Node 실행 시험 아님 |
| TypeScript 5.9.3 tsc --noEmit --strict | 0 | 생성 TypeScript 계약 검사 |
| check_docs.py / check_ontology.py / test_sync.py / git diff --check | 0 | 문서·48작업 DAG·RDF/SHACL·동기화 보호 통과 |
| git push -u origin agent/codex/approval-boundary | 0 | 원격 작업 브랜치 저장 |

기존 66개 회귀에 신규 35개(입력 10개·PostgreSQL 25개)가 추가됐다. 신규 DB 시험은 L2 2인 조건·L3/위조 승인 거부, requester 자기 승인, 권한 철회, 다른 tenant/project, nonce 재발급/actor 귀속/만료, 같은 표 8개 동시 재시도, 다른 두 승인자의 동시 투표, dispatch 8개 동시 재시도, 원문 nonce/command 미저장, changed content, 취소/복원 epoch, 승인 만료와 audit 실패 후 전체 rollback을 포함한다.

- Core Build [34360662284](https://github.com/egparadise/SaintVision-Invion/actions/runs/34360662284): 동일 구현 SHA / success.
- Documentation Build [34360662521](https://github.com/egparadise/SaintVision-Invion/actions/runs/34360662521): 동일 구현 SHA / success.
- Artifact `10107718153` (`saintvision-core-evidence`), archive SHA-256 `d1eb61ae240aca8ef838d2965f630af651403e56b15b0499b99e1b9c8ab3b3e7`.
- 원본 JUnit [[approval-73e8774-tests.xml]], SHA-256 `cab6add093f0ae3719f1100b6f827518122d4a98796cdb824719e8a4536e2e3b`.
- 기계 판독 provenance [[approval-73e8774-provenance.json]]. CI 아티팩트 만료 이후에도 위 증거를 Git/Obsidian에 보존한다.

## 오류와 한계

초기 pytest 동명 파일 수집 실패(exit 1)는 [[ERR-APPROVAL-001 승인 테스트 수집 충돌]]과 [[RES-APPROVAL-001 테스트 모듈 분리와 재검증]]에 기록했다. 수정 후 CI는 첫 실행에서 통과했다. Windows sandbox 초기화와 이전 Docker 자원 실패 자체는 복구했다고 주장하지 않는다.

실제 OIDC/PDP 서비스, HTTP 승인 API, 브라우저, broker 소비자, Node/장비 부수 효과 검증은 미수행이다. outbox의 durable 단일 등록은 실제 외부 명령의 exactly-once 보장이 아니다. S01~S03 선행 및 독립 검토를 완료로 올리지 않았다.

## 동기화와 검토 인계

보고서 포함 Obsidian export 및 최종 commit CI는 후속 실제 결과로 확인한다. 자기 SHA를 본문에 다시 쓰는 순환 갱신은 하지 않으며 최종 SHA의 Actions 링크가 증거다.

- Claude: 승인 트랜잭션·DB 권한·PDP 신뢰 입력 독립 검토, 인증/업무 API adapter 연동.
- Gemini: ApprovalDecisionInput·ApprovalView·challenge 계약 수신, 브라우저 claim 위조 방지와 nonce 메모리 취급 UI 연결.
- Codex: 검토 지적 반영 및 ToolGateway/Sandbox·consumer inbox·현재 정책/epoch/Node fence 검증 결합.

검토용 PR과 문서 인계이며 다른 Agent의 실제 검토·수신을 수행했다고 표시하지 않는다. main merge와 운영 배포는 하지 않았다.

## 빌드 산출물 SHA-256

- `core-tests.xml`: `cab6add093f0ae3719f1100b6f827518122d4a98796cdb824719e8a4536e2e3b`
- `saintvision_control_plane-0.1.0-py3-none-any.whl`: `c2693f3391c183ba780cf21798384b4f7d4413a1754f1e2403517e2090ae00a8`
- `saintvision_control_plane-0.1.0.tar.gz`: `440722fe129f30d88904c8e315247c169d311a5a131655ccf828a8c6bd0d4681`

## Obsidian 실제 동기화

- 2026-09-09T23:06:58+09:00 `python tools/sync_obsidian.py --check --state ../../.work/obsidian-sync-state.json`: exit 0, `CHECK: 108 managed files, 18 pending exports, 0 conflicts. No writes.`.
- 2026-09-09T23:06:58+09:00 `python tools/sync_obsidian.py --apply --state ../../.work/obsidian-sync-state.json`: exit 0, `EXPORTED: 18 files; all 108 destination hashes match. Unmanaged files untouched.`.

위 실제 결과를 포함한 보고서를 다시 export하고 hash 일치를 확인한다. 공유 state를 사용하며 외부 동시 편집/미관리 파일은 덮어쓰지 않는다. 최종 보고서 hash는 PR 인계에 기록한다.
