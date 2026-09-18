---
doc_id: "HIST-RESULT-OBSERVATION-REPORT-20260911"
title: "RESULT-OBSERVATION Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-11T13:56:19+09:00"
source_of_truth: "Git"
---

# 실제 실행 결과·준비 상태 통합 검증

[[2026-09-11_RESULT-OBSERVATION_Codex_착수]]의 base 2398dcc 위에 Claude 97fc1fa를 f595d32로 가져와 검토했다. Codex 구현 코드 `8b97c6a1e7dd3bcb7e7b9fb25173dec758f2e7b7`를 `agent/codex/result-observation`에 push했다. 원저자 코드는 보존했고, Codex 변경의 독립 reviewer는 Claude 대기다. 운영 배포나 main 병합은 수행하지 않았다.

## 구현 결과

- 실행 화면용 결과/파일/로그/attempt API가 public CRUD 상태 대신 현재 inv Run/attempt/Node receipt/확정 Evidence를 읽는다. public Run이 없는 첫 실행도 조회한다.
- 파일 다운로드는 실제 receipt 출력의 해시·크기를 다시 검증하고 승인된 입력과 연결된 Workspace snapshot에서 정확한 path만 꺼낸다. 실제 API 바이트·해시·크기를 비교했다. 경로 탈출·없는 파일·권한 없는 접근은 거부한다.
- draft/실패/실행 전 취소·출력 수집 복구 대기 상태를 구분한다. processStarted 영수증과 성공 Evidence는 별도다. 로그 미리보기에는 redaction을 적용한다.
- 업무 준비 상태를 /v1 경로에 연결하고 현재 subject/계정/멤버십/kernel request grant를 확인한다. CP 로컬 CLI를 원격 준비 상태로 사용하지 않는다. 미관측 Node는 unknown이며 실행 권한을 자동 부여하지 않는다.
- 0026_subject_kernel_link와 0027_business_api_guards 이력을 수정하지 않고 0028 merge에서 tenant guard를 보강했다. 과거 11개 revision의 upgrade/replay·기존 sentinel 데이터와 도구 선택 값 보존을 검사했다.
- 결과 JSON Schema를 정본으로 Python/TS/Go 타입을 생성했다. 운영 문서의 NOLOGIN 그룹·복구 완료 오인 문구도 정정했다.

계약은 [[Codex 실제 실행 결과 조회 계약]]/ADR-066·067, 실패 과정은 [[2026-09-11_RESULT-OBSERVATION_오류와해결]]이다.

## 검증 증거

| 명령/범위 | 실제 결과 |
|---|---|
| `python -m pytest tests/core tests/test_migrations.py -q --tb=short --junitxml=.work/result-core.xml` | clean 8b97c6a, 290 passed, exit 0 |
| `python tools/check_kernel_docker.py --go C:/Project/SaintVision-Invion/.work/node-toolchain-1.27.1/go/bin/go.exe --prepare-only` | clean 8b97c6a 준비, dirty=false |
| 아래 격리 통합 명령 | 262 passed, 실패/오류/skip 0, exit 0, 2026-09-11T04:55:51.488029+00:00 |
| `python tools/generate_contracts.py` / `python tools/export_schemas.py --check` | 생성 성공, 업무 19개 schema 일치, 각각 exit 0 |
| Go `go test ./...` (packages/contracts-go) | compile 성공, test file 없음, exit 0 |
| 로컬 TypeScript `tsc --noEmit --strict packages/contracts-ts/src/index.ts` | exit 0 |

위 Python은 `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe`다. Node와 시험 DB는 로컬 Docker에 생성한 합성 identity/입력만 사용했다. API·DB 권한 검사는 실제 JWT와 PostgreSQL 제한 role을 사용한다. GitHub CI·운영 IdP·실제 다른 PC·GPU 인수와 구분한다.

```text
python tools/check_kernel_docker.py --prepared .work/sv-kernel-5b1569c3f2a2/prepared.json --tests tests/test_business_results.py tests/test_result_readiness.py tests/test_account_integration.py tests/test_projects.py tests/test_settings.py tests/test_login.py tests/test_api.py tests/test_pools.py tests/test_migrations.py tests/test_contracts.py tests/integration/test_result_observation.py tests/integration/test_account_production.py tests/integration/test_workspace_start.py tests/integration/test_business_handoff.py tests/integration/test_containment.py
```

[통합 Evidence](../Evidence/result-observation-8b97c6a.json)의 SHA-256은 `3fbd50e3991835ca6168cd5a556d3e3c0f00d8e0261b56382aef3dce5690f772`다. 실제 runner/DB 종료도 기록했다. [기본/DB 검사](../Evidence/result-observation-8b97c6a-core.json), [CI 관측](../Evidence/result-observation-8b97c6a-ci.json), [원격 관측](../Evidence/result-observation-live.json)을 함께 보존한다. private pytest.log/config/개인키는 공개하지 않는다.

CI는 코드 push 뒤 자동 실행을 확인했으나 계정 결제/spending 제한으로 job 시작 전 차단됐다. [Backend 34563825936](https://github.com/egparadise/SaintVision-Invion/actions/runs/34563825936), [Core 34563825811](https://github.com/egparadise/SaintVision-Invion/actions/runs/34563825811), [Docs 34563825842](https://github.com/egparadise/SaintVision-Invion/actions/runs/34563825842). 계정 설정을 바꾸거나 반복 재실행하지 않았다.

## 다음 작업과 전달 상태

| owner | 다음 행동 |
|---|---|
| Codex | 실제 worker 설치 결과 확인 후 원격 7개 실행·취소·복구 인수. 이후 Node 도구 관측/허용 실행 프로필 계약과 다중 Node/GPU 검증 |
| Claude | 8b97c6a 독립 검토, 실제 IdP/subject/project provisioning·Workspace 파일 준비·public 제공량과 kernel 자원 연결. 운영 시작/복구 절차의 실제 배포 인수 |
| Gemini | 새 결과·다운로드·준비 상태 API와 현재 start/prepare→승인→start/enqueue 연결. 임의 수치/heartbeat 제거 후 실제 브라우저 검증 |

원격 192.168.45.225는 최신 관측에서도 관측 전용 profile이며 실행 설치 확인은 대기 중이다. [[2026-09-11_REMOTE-WORKSPACE_다른PC설치안내]]의 설치 결과가 필요하다. 운영 Node/DB/계정/kill switch/일반 제출/웹 배포를 변경하지 않았다. 이 보고와 계약은 Git/Obsidian 인계 자료이며 다른 Agent에게 직접 메시지를 보낸 것은 아니다. CI·독립 검토·실장비 인수가 남아 전체 task를 done으로 표시하지 않는다.

13:56 KST `python tools/check_docs.py`는 원문 24개/버전 문서 229개/48 task 검사를 통과했고 `python tools/check_ontology.py`도 RDF/SHACL/추적성 검사를 통과했다(각 exit 0). `git diff --check`는 exit 0이었다. `python tools/sync_obsidian.py --check --state .work/result-sync-state.json`은 358개 관리 파일/14개 반영 대기/충돌 0, exit 0이었다. 코드 이후 변경은 문서/Evidence뿐이다.

이어 `python tools/sync_obsidian.py --apply --state .work/result-sync-state.json`은 14개 파일 반영/358개 목적지 해시 일치, exit 0이었다. 같은 `--check`에서 반영 대기 0/충돌 0, exit 0을 확인했다. 이 전달 기록 추가분도 같은 절차로 반영한다. 다음 reviewer는 Claude, 실제 원격 시험 owner는 Codex다.
