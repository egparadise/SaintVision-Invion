---
doc_id: "REPORT-NODE-RUNTIME-001"
title: "Codex Linux Node 격리 실행과 정지 반환 검증 보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T01:16:02+09:00"
source_of_truth: "Git"
---

# Codex Linux Node 격리 실행과 정지 반환 검증 보고

승인된 ToolGateway claim을 Ed25519 permit으로 Go Node에 전달하고, durable inbox·allocation fencing·제한된 Docker 컨테이너·독립 PID 1 watchdog으로 실제 실행/정지한다. 정지와 container 삭제를 확인한 영수증만 Control Plane의 전체 lease 반환 트랜잭션에 반영한다. Node 에이전트를 강제로 종료한 실제 합성 시험에서도 workload가 기한에 스스로 멈추고 재시작 시 중복 실행 없이 영수증을 회수했다.

- task node-runtime, OUT-03/AC-03·OUT-04/AC-04, owner Codex / reviewer Claude(pending).
- branch `agent/codex/node-runtime`, base `85a8747a92efd56d14ed7fdfcba85fe03f60463f` (#3 tool-admission 위의 작업).
- implementation `98d02be8528c3a09c5d38239fd8fcce93affa39e` / commit·push exit 0. 시작·입력 doc/version·scope: [[2026-09-10_00-04-32_KST_NODE-RUNTIME_Codex_개발과정]].
- 계약 [[Codex Node 실행 격리와 정지 영수증 계약]] NODE-RUNTIME-CONTRACT-001 v1.0.0, ADR-027/028(ADR-INDEX-001 v1.4.0), migration 0004, JSON Schema v1alpha1, 생성 Python/TS/Go + Node embedded schema.
- Skill agent-delivery/core-reliability v1.0.0, Go 1.23.12 portable 도구, jsonschema/v6 v6.0.2, cryptography 50.0.1. 개발 Prompt는 사용자 후속 개발 및 critical 외 승인 자동 진행 지시다.
- 제품 Prompt/Context/Harness/ROOF/Graph/Agent 실행 버전은 미연동이다. `roof:test:1`·`restricted:node-test:1`·FROM scratch Go probe는 합성 fixture이며 실제 의료 원본/사용자 장비를 사용하지 않았다.

## 실제 명령과 합격 증거

| 명령·환경 | exit | 확인 결과 |
|---|---|---|
| Windows Go unit tests / Linux test cross-compile·build | 0 | 서명/정책 회귀 및 Linux 코드·시험 컴파일 |
| Windows pytest -q --junitxml=.work/node-local-tests.xml | 0 | 89 passed / PostgreSQL·Linux 실행 105 skipped |
| CI go test -race -json ./... | 0 | **14 top-level / 37 leaf case, failures 0 / test skips 0** |
| CI Python 3.12 + PostgreSQL 16 + Linux Docker pytest | 0 | **194 tests / failures 0 / errors 0 / skipped 0** |
| CI static inv-node·probe·inv-supervisor build / FROM scratch docker build | 0 | 실제 CPU 합성 격리 image와 Go Node 생성 |
| CI Alembic upgrade head | 0 | 0001~0004 migration을 고유 합성 DB에 실제 적용 |
| 계약 regenerate + git diff --exit-code / Python package / TS strict / contracts-go | 0 | 원본·생성물 drift 없음, wheel/sdist·Go·TS 빌드 |
| check_docs.py / check_ontology.py / test_sync.py / git diff --check | 0 | 문서·48 task DAG·RDF/SHACL·동기화 보호 검사 |

Python 기존 172개 회귀 + Node 신규 22개(실제 컨테이너 16·DB signer 6)다. Go 14개 top-level 아래 leaf case 37개는 별도이며 parent/subtest를 중복 합산하지 않았다. 테스트 없는 command/helper 4개 패키지의 Go package-level 표시는 테스트 생략으로 합산하지 않는다. 명령/helper의 실제 동작은 Docker 통합 시험에서 검증했다.

실제 격리 probe는 UID 65532, CapEff=0, NoNewPrivs=1, loopback만 존재, Docker socket 부재, root 쓰기 거절, /workspace 쓰기 허용, cgroup CPU/memory/PID 제한을 검사했다. Unicode argv의 Python 서명→Go bytes hash 대조, exit 7, timeout, CLI SIGTERM, Node SIGKILL 뒤 독립 timer의 exit 124 및 recover, signature 변조 무효, 8개 동시 receipt 처리, outbox 실패 시 receipt/전체 release rollback, scope/claim/plan/fence 변경 거절과 만료 lease stop 반환도 통과했다.

- Core Build [34373543925](https://github.com/egparadise/SaintVision-Invion/actions/runs/34373543925): 동일 구현 SHA / success.
- Documentation Build [34373543859](https://github.com/egparadise/SaintVision-Invion/actions/runs/34373543859): 동일 구현 SHA / success.
- artifact `10112992275`; 확인 시각 `2026-09-10T01:07:22+09:00`.
- 원본 JUnit [[node-98d02be-tests.xml]], 원본 Go JSON [[node-98d02be-unit.jsonl]], 출처와 artifact archive hash [[node-98d02be-provenance.json]].

## 설계 보강과 남은 범위

[[ERR-NODE-001 JSON 중첩 경계와 실행 종료 경쟁 검토]] → [[RES-NODE-001 중첩 제한과 삭제 후 정지 확인]]. fsync 시간이 기한을 늘리지 않게 하고, delayed start가 stopped 관찰 뒤 실행되는 경쟁을 container 삭제 후 ACK로 차단했다. ambiguous create·unknown stop·receipt 디스크 실패는 자동 재실행/자원 반환을 하지 않으며 수동 조사 상태가 남을 수 있다.

확인 범위는 **Linux CPU Docker 합성 실행**이다. Windows·GPU·5대 실장비·mTLS/PKI bootstrap/rotation·인증된 transport·운영 재해 복구·Artifact 업로드는 미완료다. key는 synthetic 메모리 생성이며 공개키만 Node에 전달했다. 신뢰된 image content ID allowlist와 local Unix socket이 전제이고 일반적인 악성 Docker daemon/host 침해 방어를 주장하지 않는다. raw 출력은 수집 기능 전까지 폐기한다.

exit 0/정지 receipt는 application success Evidence가 아니며 Run은 scheduled를 유지한다. 실제 Node stop receipt 전에는 lease를 반환하지 않는다. UI cancel의 즉시 전달/Run running 및 Evidence 검증 adapter는 후속이다. S03/S04 전체, 운영 배포, independent review done으로 표시하지 않는다.

## 인계 및 기록 보존

Claude: 서명·journal·물리 stop/삭제·lease/outbox 경계 독립 검토, authenticated Node transport와 key/capability/PDP adapter 연결. Gemini: stop/exit/app success 구분과 실제 서버 계약 연결. Codex 다음 영역: 인증/복구 adapter 계약 및 쌓인 Backend/Frontend 인계 코드 검토. S01 장비/IdP/DNS/TLS/Storage 확인은 선행으로 남는다.

[[외부 인계 제안 수신과 정본 동기화 복구]]에 10개 외부 관리 문서 차이와 S05~S10 보고 6건을 미검증 제안으로 수신·보존했다. 원 저자 주장·시각·시험 수를 Codex 실측으로 승격하지 않았다. 이 작업은 다른 Agent 코드·원문 docs/sources·main을 변경하지 않았다. 작업별 `.work/node-obsidian-sync-state.json`으로 확인된 snapshot만 export한다.

보고서 자신의 commit SHA를 다시 쓰는 순환 갱신은 하지 않는다. 마지막 보고서 commit은 해당 SHA의 GitHub Actions를 별도로 확인하고 PR 인계에 연결한다. 실제 Obsidian sync 결과는 아래에 기록한다.

## 빌드 산출물 SHA-256

- `core-tests.xml`: `6ece0a3a6bb1861ca63e5e72c2c564b1106fa09f573f0c10ac6e4b3d40519f01`
- `inv-node`: `2ed9c70201851cc9676dd231553bc7555bb5b3a8da89624bd59eee0648e9d8c9`
- `node-unit.jsonl`: `f02e651461d07ed02242df0e42fe2d9b7acd477207a1fbab8772870bb8c2f0bf`
- `saintvision_control_plane-0.1.0-py3-none-any.whl`: `9789867a951a56f89ea6b31bf851f46e58aa29ae8931e049d9fe471d0a1c3ccb`
- `saintvision_control_plane-0.1.0.tar.gz`: `68c0617553376018c0842582989afde56d61e81c2e6ae19011b64c6b1f232f5b`

## Obsidian 실제 동기화

- 2026-09-10T01:21:57+09:00 `python tools/sync_obsidian.py --check --state .work/node-obsidian-sync-state.json`: exit 0; `CHECK: 139 managed files, 19 pending exports, 0 conflicts. No writes.`.
- 2026-09-10T01:21:57+09:00 `python tools/sync_obsidian.py --apply --state .work/node-obsidian-sync-state.json`: exit 0; `EXPORTED: 19 files; all 139 destination hashes match. Unmanaged files untouched.`.

이 실제 결과를 포함한 보고서도 다시 export하고 전체 파일 hash 일치를 확인한다. 최종 보고서 SHA-256은 PR 인계에 기록한다. 작업별 state로 확인 이후 발생한 다른 Agent 편집을 보호하며 공유 state를 무조건 덮어쓰지 않는다.
