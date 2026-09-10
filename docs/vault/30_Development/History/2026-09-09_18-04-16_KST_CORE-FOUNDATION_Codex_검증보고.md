---
doc_id: "REPORT-CORE-FOUNDATION-001"
title: "Codex core-foundation 구현 검증 및 인계 보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-09T18:04:16+09:00"
source_of_truth: "Git"
---

# Codex core-foundation 구현 검증 및 인계 보고

Task core-foundation / S01-BE·DB·ST 준비, OUT-01 / AC-01. owner Codex, reviewer Claude. 작성자 자체 검증과 CI 성공이며 독립 코드 검토는 pending이다. S01 장비/IdP/TLS/Storage 확인 및 S02~S12 제품 통합 완료를 뜻하지 않는다.

- branch: `agent/codex/core-foundation`
- base: `3c53e90`(Claude 준비 보고까지 반영)
- implementation: `c36f41d442746ef78a6b9c1355b1ac1f45193ca2`; 초기 구현 `e6336a7ab086a730a746f4382331aa48dc007d62`
- Context/Skill/scope 및 시작 시각: [[2026-09-09_16-26-00_KST_CORE-FOUNDATION_Codex_개발과정]]
- 계약: v1alpha1 JSON Schema, Python/TS/Go generated types; migration 0001_core; Ontology 0.2.0 task projection; ADR-INDEX-001 v1.1.0 및 CORE-CONTRACT-001 v1.0.0.
- Prompt 사용자 Obsidian 계획 분석·Codex 개발 요청, Agent Codex, Skill agent-delivery/core-reliability v1.0.0. 제품 Prompt/Context/Harness/ROOF/Graph 실행 버전은 후속 통합이며 이번 개발 검증의 실행 버전으로 꾸미지 않았다.

## 구현 내용

결정론적 Scheduler, 물리 정지 ACK 전까지 점유 유지하는 Lease, 복원 epoch와 stale proof 차단, PostgreSQL Run/attempt/checkpoint/Evidence/outbox 원자 처리, RLS·복합 소유 FK, 멱등 응답 저장, 정책 스키마 검증, Storage URI/경로 preflight/실제 byte checksum, 생존 전용 FastAPI shell을 구현했다.

Claude CR-01~12와 Gemini FR-01~07에 대한 판단·수정 요청·미구현 경계를 [[Codex 핵심 기반 계약과 검토 회신]]에 정리했다. 다른 Agent의 미커밋 코드는 수정하지 않았다.

## 실제 검증

| 명령·환경 | exit | 결과 |
|---|---|---|
| Windows `.venv` `python -m pytest -q` | 0 | 53 passed, PostgreSQL 13 skipped; Docker newosproc 실패로 로컬 DB 미실행 |
| CI Python 3.12 + PostgreSQL 16 `python -m pytest --junitxml=dist/core-tests.xml` | 0 | **66 tests, failures 0, errors 0, skipped 0** |
| `python tools/generate_contracts.py` + generated `git diff --exit-code` | 0 | 단일 원본 생성물 일치 |
| `python -m build services/control-plane --outdir dist` | 0 | wheel/sdist 생성 |
| `go test ./...` (contracts-go) | 0 | Go 생성 패키지 컴파일; Go 제품 Node 실행 시험 아님 |
| TypeScript 5.9.3 `tsc --noEmit --strict` | 0 | 생성 타입 검사 |
| `python tools/check_docs.py` | 0 | 문서 링크·원문 hash·owner/reviewer·48 작업 DAG |
| `python tools/check_ontology.py` | 0 | RDF/SHACL/JSON-LD 동형·48 상태/담당 매핑·4 negative fixtures·4 competency queries |
| `python tools/test_sync.py` | 0 | 동기화 보호 3개 시험 |
| `git diff --check` / `git push` | 0 | origin 작업 브랜치 저장 |

PostgreSQL 13개 사례에는 50개 독립 connection 경합(성공 1개/용량 초과 없음), divisible 합계·다자원 rollback, 동시 멱등 재요청, 만료/취소 후 점유 유지, stop ACK, checkpoint 재연결·attempt 복구, RLS·cross-tenant FK, lock timeout rollback, 미측정/초과 스큐, 복원 epoch 차단, Evidence/state/outbox rollback, broker ACK 이후 실패의 중복·consumer inbox가 포함된다. 실제 Node 프로세스·PITR·5대 PC·브라우저 성능 시험은 아직 아니다.

- Core Build: [34331695971](https://github.com/egparadise/SaintVision-Invion/actions/runs/34331695971) / 동일 SHA / success.
- Documentation Build: [34331696095](https://github.com/egparadise/SaintVision-Invion/actions/runs/34331696095) / 동일 SHA / success.
- Artifact ID: `10096051251` (`saintvision-core-evidence`), zip SHA-256 `a4ac80f0ba96b79f392285b99dd6adb807dde047c88f3404a2c0927672e5896a`.
- 원본 JUnit: [[core-c36f41d-tests.xml]]. 파일 SHA-256 `8ae38120d7c50f2b086644847a04b39c47a1288e2090b65c2effb150dd56a4b3`. Artifact 보존 기간 종료 이후에도 이 XML을 Git/Obsidian에 보존한다.

## 산출물 SHA-256

- `core-tests.xml`: `8ae38120d7c50f2b086644847a04b39c47a1288e2090b65c2effb150dd56a4b3`
- `saintvision_control_plane-0.1.0-py3-none-any.whl`: `0f1dfecf138b16dca1ae9db01601d94acf68816c343c69f3f4da03552366a287`
- `saintvision_control_plane-0.1.0.tar.gz`: `e7da09565c927619c033cadcd069e4d79f766fc9cda29d0378d1bdb58d3a706d`

## 오류·해결

초기 4개 입력 검증 실패, registry/Ontology 상태 불일치, 외부 Obsidian 동시 수정, 첫 Core CI migration 구문 실패를 재현하고 수정했다. [[ERR-CORE-001 초기 검증 및 실행 환경 실패]]와 [[RES-CORE-001 입력 검증 수정과 CI 대체 검증]] 참조. GitHub 로그 다운로드는 cross-host redirect에 인증 헤더를 전달하지 않도록 로컬 조회 도구를 수정했다.

## 동기화·인계

Obsidian export 실제 결과는 아래와 같다. 보고서 후속 commit의 CI는 해당 commit의 Actions가 증거이며 자기 SHA를 다시 본문에 쓰지 않는다.

- Claude: transaction/epoch/receipt/tenant 경계와 생성 계약 독립 코드 검토, P7 snapshot 보완, 업무 서비스 adapter 연결.
- Gemini: v1alpha1 생성 타입 연결, FR 회신의 경로·서버 승인·rollback 정정 후 검토. Frontend 관련 보고의 실장비 값/검증 주장은 Codex 확인 전 그대로 승인하지 않는다.
- Codex 다음: S01 실제 장비 인벤토리·IdP·DNS/TLS·Storage 제품 확정과 소비자 검토를 반영한 다음 TaskCard. 기본 구현 공개 mutation·운영 배포는 하지 않았다.
- 외부 메신저/이메일 발송 없음. 문서 및 작업 브랜치 인계 준비, 실제 수신 pending.

## Obsidian 실제 동기화

- 2026-09-09T18:10:27+09:00 `python tools/sync_obsidian.py --check --state ../../.work/obsidian-sync-state.json`: exit 0, `CHECK: 101 managed files, 16 pending exports, 0 conflicts. No writes.`.
- 같은 state로 `--apply`: exit 0, `EXPORTED: 16 files; all 101 destination hashes match. Unmanaged files untouched.`. `.obsidian`·미관리 파일 보존.
- 마지막 충돌은 Gemini가 같은 Frontend 링크를 별칭으로 정정한 1행이었다. 변경을 그대로 Git에 받아 hash 확인 후 동기화했다.
- 위 결과를 포함한 보고서도 최종 export와 hash 일치 검사를 수행한다.
