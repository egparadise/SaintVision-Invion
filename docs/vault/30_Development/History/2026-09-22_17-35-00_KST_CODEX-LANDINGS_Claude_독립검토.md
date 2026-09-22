---
doc_id: "CLAUDE-CODEX-LANDINGS-REVIEW-20260922-002"
title: "Codex 착지 독립 검토(Claude=검토자) — 881f2911·1312e295·eceac8cf·dcf2b947·2aa80899·36d3ee9b·b6b20ab9 + 후속 4b2204d7·2e803cd6·7509f667; 49330d04 CI 확정(backend/core 취소)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T17:35:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "7509f667"
impl_sha: "(문서 전용)"
tags: ["independent-review", "codex", "ci", "claude", "revival", "mutation"]
---

# Codex 착지 독립 검토 (2026-09-22, 17:35 KST)

PR #37(`396bfa1e`)의 검토는 Antigravity(Gemini)가 수행한 것이라 Codex↔Claude 교차검토 쌍이 아니다. 그 보고("4건 모두 SOUND")는 참고만 하고 **내가 실제로 수행한 검증만** 아래에 적는다. 측정 트리: Claude 전용 detached 워크트리 `D:\Project\sv-measure-claude`, **SHA `49330d04`**(7건 전부 포함, porcelain 0)에서 시험·도구·변이 실행, 후속 3건은 **SHA `7509f667`**(porcelain 0)로 재고정해 실행. 실 PG `saintvision-invion-dev-pg`(.env `INV_TEST_ADMIN_DSN`, disposable DB만). 단일 파일 단위, PowerShell `Start-Process` 분리, 순차.

## 1. 커밋별 판정 표

| 커밋 | 내용 | 내가 수행한 검증(명령·결과) | 판정 |
|---|---|---|---|
| `881f2911` fix(ci): first hosted runs attributable | 워크플로 `workflow_dispatch`·PYTHONUTF8·requirements-docs 설치·**skip 분포 ratchet**(core.yml, 11사유 정확 건수 Counter) · pool 스키마 2건 재생성 · credential wrong-owner fixture · vf_evidence 시험 · provision_credentials 거부 분류 | `tools/export_schemas.py --check` → **PASS 58/58 exit 0**(d01c931a에서 exit 1이던 것 해소 확인) · `tests/test_vf_evidence.py` **22 passed** · `tests/core/test_credential_provision_cli.py` **14 passed** · `tests/integration/test_credential_backend.py` **48 skipped**("Actual Linux file backend", Windows — 미도달, 정직) · core.yml diff 정독 | **sound**(단, §2 F-A 관찰) |
| `1312e295` test(kernel): EvidenceEnvelope 무게 5자리 | test_postgres 3건(results·runs·shard_completion) + storage_commit·storage_view 앵커 시험 | 실 PG: `tests/integration/test_postgres.py` **16 passed** · `test_storage_commit.py` **24 passed** · `test_storage_view.py` **19 passed**. **되살림(변이) 3건**: `results.py:52`·`runs.py:165`·`shard_completion.py:139`의 `validate_contract("EvidenceEnvelope", …)`를 각각 `pass`로 바꾸고 해당 시험 단독 실행 → **셋 다 1 failed(exit 1)**, 복원 후 porcelain 0. 앵커를 지우면 시험이 깨진다 = **무게 있음(비공허)**. 이것이 내 어제 "EvidenceEnvelope 앵커5·시험0" 구멍의 실제 해소 확인 | **sound** |
| `eceac8cf` feat(contracts): resource usage·download canons | core.schema.json +169, 생성물 Python/TS/Go, fixture, 결정제안 2건, ADR | `tests/core/test_decided_resource_and_download_contracts.py` **9 passed** · `tools/check_contract_bindings.py` **exit 0** · `tools/generate_contracts.py` 재실행 → 내용 diff 0(`models.py` 줄끝 CRLF/LF만) = 생성물 원천과 정합 · **Go**: `packages/contracts-go` `go build ./... && go vet ./...` **exit 0**, `services/node-agent` **exit 0**(go1.27.0 — 이 PC 첫 Go 검증에 새 계약 포함) · TS 타입은 measure 트리에 node_modules 없어 **미실행**(Codex 자기검증 16 passed 수용, 내 실행 아님) | **sound** |
| `dcf2b947` feat(verification): fixture producer reachability | `tools/check_fixture_reachability.py` + 자기시험 + docs.yml report-only 단계 | `tests/test_check_fixture_reachability.py` **2 passed** · 도구 직접 실행 **exit 0**(schema-only 2건 보고: terminal-ticket-result·workspace-edit-view) · docs.yml은 `continue-on-error: true` + step summary = **report-only, 게이트 아님**(도구 목록 문서와 일치) | **sound** |
| `2aa80899` fix(ci): backend skip ratchet | backend.yml "No PostgreSQL test was skipped" → 사유별 정확 건수 Counter(10사유) | 정독. 의도: skip을 통과로 세지 않고 **보이는 증거로 고정**, 새 skip이 생기면 job 실패(ratchet). PG 이미지 13건은 backend에서 `INV_TEST_ROLE_GUARD_IMAGE` 설정으로 실행되므로 목록에 없음 = 정합. 내 Windows 전수(142 skip)와는 플랫폼이 달라 대조 불가 — **hosted backend 실행이 아직 한 번도 완주하지 않아 이 ratchet의 실제 일치 여부는 미관측**(§3) | **sound(정적)·미관측(런타임)** |
| `36d3ee9b` fix: restore Codex contract·CI guards | rdflib 고정, core 시험 4파일, credential wrong-owner를 `docker run --rm --network none` 일회용 컨테이너로, studio/desktop 브라우저 인수, shard_parent·storage_commit 앵커, AGENTS.md 게이트 예시(R2-b), ontology-regeneration 9커밋 복원 | `tests/core/test_evidence_envelope_serving.py`+`test_serving_anchors.py`+`test_workload_spec_input_anchors.py` **15 passed** · `test_credential_provision_cli.py` 14(위) · `tests/integration/test_shard_parent.py` **5 skipped**("Real Linux Docker runtime explicitly enabled only in isolated CI" — 정직) · `test_storage_commit.py` 24(위) · `check_ontology.py` **exit 0**(48 task mappings; 어제 RED였던 ontology stale 해소 확인) · AGENTS.md diff: 세미콜론 체인 금지·`$LASTEXITCODE`/`rc=$?` 예시 = 내 R2-b와 정합 · `provision_credentials.py` diff 정독(§2 F-A) · 브라우저 2파일은 **미실행**(Windows, Chromium 레인 opt-in) | **sound**(F-A 관찰) |
| `b6b20ab9` docs: Codex R1 landing 기록 | 진행판·Codex 작업판·History | `check_docs.py` **exit 0**(49330d04 정확 트리, 768 docs). 내용 대조: "36d3ee9b 부모 2aa80899·24경로"를 `git show --stat`로 확인 = 기록과 일치 | **sound** |
| 후속 `4b2204d7` fix(ci): integration cancel-in-progress 해제 | 5 워크플로 `cancel-in-progress`를 integration 브랜치에서 false로 | 정독. **원인 대응이 맞다**: 49330d04의 Backend/Core가 바로 이 설정 때문에 취소됐다(§3). 이후 tip은 큐잉되어 완주 가능 | **sound** |
| 후속 `2e803cd6` fix(ci): owned probe already-absent | `vf_docker.cleanup_owned`가 `No such object` 를 확정 부재로 취급(좁은 정규식) | `tests/test_vf_docker.py`(7509f667) **passed**(아래 합계 14) · 정규식 `\bNo such (object|volume|network):` 는 daemon 오류(i/o timeout 등)와 구분됨 — 내 R5-01 분류(확정 부재 vs 조회 실패)와 일치 | **sound** |
| 후속 `7509f667` test(migrations): child diagnostics 보존 | 내 어제 F1 finding("diagnostics withheld") 해소: 자식 stdout/stderr 꼬리 12줄, URL/`password=` 비밀 마스킹, 2400자 상한 + 마스킹 시험 | `tests/test_migration_prerequisite.py`+`tests/test_vf_docker.py` **14 passed, exit 0**(7509f667). 마스킹 정규식 정독: URL `user:pw@`와 `password=…` 둘 다 처리, 실패 phase(PASS 라인)는 보존 | **sound — F1 해소** |

합계(실 PG·단일 파일, 49330d04): 22+14+16+24+19+9+2+15 = **121 passed / 0 failed**, skip 53(48 Linux 파일 백엔드 + 5 Linux Docker 런타임, 전부 정직 게이팅). 7509f667: 14 passed. 변이 3/3 KILLED.

## 2. Finding (Codex 레인 전달 — escalation으로 보고)

- **F-A (낮음, provision_credentials.py — 36d3ee9b/881f2911)**: manifest 검증 블록의 `except Exception: raise ProvisioningDenied()`가 **프로그래밍 오류(TypeError/AttributeError 등)까지 "거부(exit 2)"로 분류**한다. fail-closed 자체는 옳으나, 내부 결함이 정책 거부로 위장되면 어제 정리한 "조용한 강등" 부류(미지 상태를 그럴듯한 값으로)다. 제안: 입력 검증 예외를 명시 튜플(ValueError·KeyError·TypeError-from-schema·ValidationError)로 좁히거나, 그대로 두되 마스킹된 진단을 stderr에 남겨 분류 가능하게. 파일 읽기 블록의 `OSError→Denied`는 의도가 주석으로 정당화돼 있어 관찰만.
- **F-B (정보, run_vf_security_tests.py safe evidence)**: 49330d04 브라우저 인수 실패 1건의 **케이스 이름이 safe evidence에 없다**(`failedTestClasses: [tests.integration.test_desktop_browser]`만; 로그에도 nodeid 없음). nodeid는 비밀이 아니므로 `failedCaseIds`를 포함하면 CI red를 레인에 귀속할 수 있다. 지금은 "test_desktop_browser 2건 중 1건 실패"까지만 귀속 가능(브라우저 레인 = Gemini/Codex, 케이스 미상).

## 3. 49330d04 CI 확정 기록

| workflow | run | 결과 | 귀속 |
|---|---|---|---|
| Documentation Build | 35704293597 | **success** | — |
| Backend Build | 35704293593 | **cancelled** | `cancel-in-progress` 그룹 취소: 17:22~17:26에 5커밋(5b12e76c·2e803cd6·4b2204d7·7b251bd6·7509f667)이 연속 push되며 in-flight run이 지워짐(동결 해제 17:19 후 3~7분). 코드 실패 아님. 4b2204d7가 integration에서 취소를 끔 → 7509f667 run이 첫 완주 후보 |
| Core Build | 35704293585 | **cancelled** | 동상 |
| Auth and Desktop HTTP Browser Acceptance | 35704293580 | **failure**: 5 passed / 1 failed / 0 skipped, `failedTestClasses=[tests.integration.test_desktop_browser]`, evidenceStatus partial | 브라우저 레인(Gemini/Codex). 케이스명 미상(F-B). Codex 로컬 Edge 6/6과 hosted Chromium 5/6 불일치 = 환경차 가능성 |

따라서 **hosted backend의 PG no-skip 결과는 여전히 0 관측**(d01c931a는 export drift, 8859a9cb/49330d04는 취소). 7509f667 runs(35704819299 backend·35704819294 core, pending)가 첫 관측이며 결과 읽기는 다음 사이클.

## 4. 하지 않은 것 (정직)
- TS 계약 타입 검사·vitest·브라우저 2파일: measure 트리에 node_modules/Chromium 없음 → Codex 자기검증 수용(내 실행 아님).
- Linux 전용 credential 파일 백엔드·shard_parent Docker 런타임: Windows라 skip(hosted core가 자리).
- ontology-regeneration 9커밋 복원(merge 23235bbb)의 내용 검토는 `check_ontology` exit 0으로 생성물 정합만 확인, 커밋별 정독은 안 함.

## 다음 첫 행동 / 담당
- Codex: F-A 좁히기 여부 결정, F-B nodeid 노출. 7509f667 backend/core 결과 나오면 ratchet 일치 여부 확인.
- Claude: 7509f667 CI 결과 읽기·triage(다음 사이클).
