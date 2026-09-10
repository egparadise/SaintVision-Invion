---
doc_id: "REPORT-TOOL-ADMISSION-001"
title: "Codex ToolGateway 실행 허가 검증 및 인계 보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-09T23:47:26+09:00"
source_of_truth: "Git"
---

# Codex ToolGateway 실행 허가 검증 및 인계 보고

승인된 command를 현재 PDP·project 권한·Node·Lease·고정 Sandbox profile에 대조하고 commandId별 신규 실행 허가를 한 번만 발급하는 ToolGateway admission을 구현했다. 같은 command의 8개 동시 요청 중 하나만 launch 설정을 받으며, 재전달/응답 유실/서비스 재생성으로 새로운 실행 권한을 만들지 않는다.

- task tool-admission / OUT-03·AC-03, OUT-04·AC-04 / owner Codex / reviewer Claude(pending).
- branch `agent/codex/tool-admission`, base `0fbf66e2487cfdea54de66aadcb8c8b646335591` (#2 위의 작업).
- implementation `ce59e633d72fc16ab4b57e06d0c5066e89c95ce8`; 시작·입력 doc/version·scope: [[2026-09-09_23-23-12_KST_TOOL-ADMISSION_Codex_개발과정]].
- 계약: [[Codex ToolGateway 실행 허가와 Sandbox 계약]] TOOL-CONTRACT-001 v1.0.0, ADR-025/026(ADR-INDEX-001 v1.3.0), migration 0003, JSON Schema v1alpha1·생성 Python/TS/Go, Skill agent-delivery/core-reliability v1.0.0.
- 개발 Prompt는 사용자 후속 개발 및 critical 외 일반 승인 자동 진행 지시다. 제품 Prompt/Context/Harness/ROOF/Graph/Agent 실행 버전은 미연동이며 `roof:test:1`, `restricted:test:1`은 합성 fixture다.

## 실제 검증

| 명령·환경 | exit | 결과 |
|---|---|---|
| Windows pytest -q --junitxml=.work/tool-local-tests.xml | 0 | 89 passed / PostgreSQL 83 skipped |
| CI Python 3.12 + PostgreSQL 16 pytest --junitxml=dist/core-tests.xml | 0 | **172 tests / failures 0 / errors 0 / skipped 0** |
| Alembic upgrade head | 0 | 고유 합성 DB에 0001·0002·0003 실제 적용 |
| generate_contracts.py + generated git diff --exit-code | 0 | Python/TS/Go 원본·생성물 정합 |
| python -m build services/control-plane --outdir dist | 0 | wheel/sdist 빌드 |
| go test ./... (contracts-go) | 0 | 생성 계약 컴파일, 실제 Node 시험 아님 |
| TypeScript 5.9.3 tsc --noEmit --strict | 0 | 생성 TypeScript 검사 |
| check_docs.py / check_ontology.py / test_sync.py / git diff --check | 0 | 문서·48작업 DAG·RDF/SHACL·동기화 보호 검사 |
| git push -u origin agent/codex/tool-admission | 0 | 원격 독립 작업 브랜치 저장 |

신규 71개(단위 26·실제 PostgreSQL 45)와 기존 101개 회귀다. 위조 command payload, 단일 claim 동시성, crash/응답 유실 후 재허가 금지, 현재 정책 deny/부재/강화/과거·미래 snapshot, 권한 철회, 다른 tenant/Node, 정확한 live proof 집합, CPU/RAM 부족, Node drain/단절/heartbeat/스큐, lease 만료/해제, runtime capability 누락, Sandbox host 접근/격리 완화, 취소/epoch, outbox 실패 시 claim rollback을 검사했다. raw argv는 durable claim/outbox에 저장하지 않는다.

- Core Build [34364959828](https://github.com/egparadise/SaintVision-Invion/actions/runs/34364959828): 동일 SHA / success.
- Documentation Build [34364959844](https://github.com/egparadise/SaintVision-Invion/actions/runs/34364959844): 동일 SHA / success.
- Artifact `10109499266`, archive SHA-256 `62c8e80d78362c1ce4217eba6ee872a137a3ec12b1283b921ed56a90603b30f7`.
- 원본 JUnit [[tool-ce59e63-tests.xml]], SHA-256 `27959fe58e32b872fd2b5bfb4efff4e1c1c2e127f102abfb6929578fcca0bfc2`.
- 기계 판독 출처 [[tool-ce59e63-provenance.json]]. 위 증거를 Git/Obsidian에 보존한다.

## 수정과 한계

정책 보조 함수의 L2 2인 하한 누락을 수정하고 순수 함수/DB 회귀를 추가했다. [[ERR-TOOL-001 정책 보조 함수의 L2 하한 누락]] → [[RES-TOOL-001 L2 하한 강제와 회귀 검증]]. 기존 durable ApprovalStore는 이미 2인을 강제했다.

**실제 OS/컨테이너 격리 driver, Node mTLS, 장비 명령, 물리 stop ACK 시험은 미수행**이다. RuntimeCapabilities 테스트 값은 합성이며 OS 격리의 attestation 증거가 아니다. claim 성공은 실제 실행 성공이 아니고 Run은 scheduled, 물리 Lease는 유지한다. 실행 성공·실장비 AC-03/S04 완료로 표시하지 않는다. 불확실한 외부 부수 효과를 자동 재시도하지 않는 대신 미실행 상태가 남을 수 있어 후속 Node reconciliation이 필요하다.

## 문서 동기화와 다른 Agent 인계

[[외부 인계 제안 수신과 정본 동기화 복구]]에 이전 Codex 기록이 빠진 외부 사본과 새 보고 9건의 수신 hash를 기록했다. 기존 검증/ADR/회신과 새로운 문서 제안을 함께 보존했다. 외부 작성자의 구현·CI·브라우저·시각 주장을 이 작업의 독립 검증으로 승격하지 않았다. 원문 docs/sources 및 다른 Agent의 업무 코드는 수정하지 않았다.

작업별 `.work/tool-obsidian-sync-state.json`으로 확인한 snapshot만 export한다. 실제 동기화 결과는 아래 기록한다. 자기 SHA를 보고서에 다시 쓰는 순환 갱신은 하지 않으며 마지막 보고서 commit의 Actions가 해당 SHA 증거다.

- Claude: ToolGateway 승인·권한·Node/Resource lock·crash 처리 독립 검토, 인증/PDP/runtime adapter 계약 수신 pending.
- Gemini: claim/exit code/취소를 성공 또는 물리 자원 회수로 표시하지 않도록 서버 계약 반영; 코드 수신·검토 pending.
- Codex: 두 Backend 구현 및 Frontend 인계 코드 검토, 실제 Node inbox/Sandbox/watchdog/stop ACK 연결. S01 장비/IdP/DNS/TLS/Storage 확인이 선행으로 남는다.

main merge·운영 배포 및 타 Agent 독립 검토를 수행하지 않았다.

## 빌드 산출물 SHA-256

- `core-tests.xml`: `27959fe58e32b872fd2b5bfb4efff4e1c1c2e127f102abfb6929578fcca0bfc2`
- `saintvision_control_plane-0.1.0-py3-none-any.whl`: `e9bf90fce427d7ae0b544077dc9899d98af2f6028ac226c69627d907f4a2b052`
- `saintvision_control_plane-0.1.0.tar.gz`: `2328aba39b6d29961b17d0b3a15f73b88266dcdfa2c40e828900b4293f390d68`

## Obsidian 실제 동기화

- 2026-09-09T23:48:42+09:00 `python tools/sync_obsidian.py --check --state .work/tool-obsidian-sync-state.json`: exit 0; `CHECK: 125 managed files, 18 pending exports, 0 conflicts. No writes.`.
- 2026-09-09T23:48:43+09:00 `python tools/sync_obsidian.py --apply --state .work/tool-obsidian-sync-state.json`: exit 0; `EXPORTED: 18 files; all 125 destination hashes match. Unmanaged files untouched.`.

이 실제 결과를 포함한 보고서도 다시 export하고 전체 파일 hash 일치를 확인한다. 최종 보고서 SHA-256은 PR 인계에 기록한다. 작업별 state로 확인 이후 발생한 다른 Agent 편집을 보호하며 공유 state를 무조건 덮어쓰지 않는다.
