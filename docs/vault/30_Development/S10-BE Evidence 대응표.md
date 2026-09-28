---
doc_id: "CLAUDE-S10-BE-EVIDENCE-MAP-001"
title: "S10-BE Evidence 대응표 — 두 Provider adapter(contract·reference·CLI 4종)·MLflow·승인 배포(record_deployment·approval digest)·commitment route·lineage query(#158 설계)·S10-FE(#144·#146)를 기존 코드·시험·hosted run에 file:line과 run ID로 대응, MLflow는 adapter·계약·설정·시험 부재(내부 IMPLEMENTATION/DESIGN GAP), CLI 4종 실바이너리 적합성은 runner 미provision(CI_LANE_GAP/NOT_OBSERVED), 실 계정·CX-02 운영 인수만 BLOCKED_EXTERNAL (구현 추가 0, 카드 bc)"
version: "1.2.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T11:12:21+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S10-BE"]
tags: ["S10-BE", "AC-10", "evidence", "adapter", "provider", "mlflow", "deployment", "lineage", "claude"]
---

# S10-BE Evidence 대응표 (2026-09-28, 카드 bc)

task-registry S10-BE: scope "두 Provider adapter·MLflow·승인 배포", evidence "Adapter conformance·lineage query·배포 digest", AC-10. 원칙은 #155·#160·#161·#163·#164와 같다: 이미 있는 것을 file:line·run ID로 대응하고 공백만 골라낸다, 관측 안 된 값은 NOT_OBSERVED, 판정 논리 복제 없음. 결론 먼저 — **adapter contract·conformance·승인 배포·commitment route는 코드·시험·hosted run이 있다. MLflow 연동은 코드에 존재하지 않는다(`git grep -i mlflow` → src·services·tools·tests·requirements 0건, 문서 7건만) → **내부 제품 공백(G1a IMPLEMENTATION/DESIGN GAP, owner 결정 필요)**이며, 구현 뒤 실제 endpoint·credential 운영 실측만 외부 대기(G1b). CLI 4종 실바이너리 적합성은 hosted runner에 바이너리를 provision하지 않아 skip → **CI_LANE_GAP/NOT_OBSERVED**(우리가 코드·CI로 만들 수 있음); 실 로그인 계정·CX-02 credential로 하는 운영 인수만 BLOCKED_EXTERNAL. 원칙: 우리가 코드로 만들 수 있는 것은 BLOCKED_EXTERNAL로 강등하지 않는다. lineage query는 #158 설계(route 미구현). 이 PR은 대응표만 담는다(구현·시험 추가 0).**

## 0. 인용 run·근거

| lane / 근거 | run / head | 결과 |
|---|---|---|
| Backend | **36351202242** head `a0dab579b188`(#125 = base 집합; `gh run view --json headSha`) | 3.12·3.14 각각 **2929 passed / 47 skipped / 2 deselected / 0 failed** — `tests/test_adapters.py` 24·`test_cli_adapters.py` 20·`test_cli_output_boundary.py` 6·`test_eval_execution.py` 14·`test_lineage.py` 23·`test_model_registry.py` 14·`test_deployment_guard.py` 4·`tests/core/test_registry_policy_exact_match.py` 10·`test_model_commit_observation_contract.py` 3·`tests/integration/test_model_view.py` 7·`test_model_commit.py` 9 포함. Backend skip 47에 CLI 4종 "is not installed on this machine" 포함 |
| Core | **36353272311** head `bc27588d2139` | main `core-tests.xml` **3236 passed / 17 skipped / 2 deselected / 0 failed**(skip 미합산) — exact map에 `claude/codex/gemini/antigravity is not installed on this machine` 각 1(`core.yml:227-233`): 실 CLI 바이너리 없이는 실행되지 않음이 hosted에서 선언됨 |
| desktop-browser | **36364528322** head `30f5ca839923` | 여정 5 중 `test_browser_real_committed_model_and_current_permission`(commitment 관측 브라우저 여정) pass |
| 로컬 실 PG(참고) | `f0f0c790` | S10 14파일 228 passed([[2026-09-22_계보모델불변_컨텍스트eval_교차증거_실PG_S09_S10_Claude]]); #127 collector가 `deployment-digest-and-approval` 12 케이스로 매핑 |
| S10-DB lineage 조회 API 설계 | PR #158 `40d75ae7`(docs) | forward trace·dataset-digest reverse lookup·ProblemDetails 공유 모듈 — **route 미구현**(설계 v1.1) |
| S10-FE | PR #144 `ee094e73`(매트릭스 v1.0.2, docs) · PR #146 `90757539`(apps/web 수정) | #146: adapter conformance 표기를 "미측정(모의/정적 예시·검증 아님)"으로 정직화(실제 conformance API 부재), mock deployment 정정, commitment panel 결속 |

## 1. 대응표

### 1.1 두 Provider adapter — contract·conformance

| 항목 | 코드 | 시험 | hosted | 상태 |
|---|---|---|---|---|
| Provider 계약(capability·cancel tri-state·attestation·usage·install report) | `src/saintvision/adapters/contract.py:38 Capability`, `:52 CancelOutcome`, `:69 AttestationResult`, `:103 RunHandle`, `:125 CollectResult`, `:145 Attestation`, `:177 ProviderAdapter(Protocol)`, `:216 stream_or_collect` | `tests/test_adapters.py:44 satisfies_the_protocol`, `:360 canonical_request_is_provider_neutral` | Backend 36351202242 | 관측됨 |
| conformance 러너(계약 버전·멤버·probe·install·redaction·capability 주장·cancel·attest digest·credential 반향·오류 코드·usage·handle/result model 일치) | `adapters/conformance.py:52 Check`, `:62 ConformanceReport`, `:121 run_conformance`, `:170~:202` 개별 검사 | `tests/test_adapters.py:37,:48,:106,:121,:136,:152,:168,:186,:203,:219,:229,:243,:263,:280,:298` | Backend | 관측됨 |
| 두 적합 adapter가 같은 계약에 같은 답(divergence 탐지·빈 비교는 pass 아님) | `conformance.py`(비교) | `test_adapters.py:315 two_conformant_adapters_answer_the_same_contract`, `:330`, `:356` | Backend | 관측됨 |
| reference adapter·redaction(비밀 형태 제거·멱등·multiline key) | `adapters/reference.py:55 recognised_secrets`, `:68 redact_text`, `:82 ReferenceAdapter` | `test_adapters.py:64,:70,:77,:84` · `tests/test_context_redaction.py` 9 | Backend | 관측됨 |
| CLI provider 4종(claude-code·codex-cli·gemini-cli·antigravity)의 계약 적합·제품 adapter가 install을 수행하지 않음(`:88`)·login 상태·출력 수집/한도/redaction·cancel unknown·nonzero exit≠완료·검증 불가 명시 | `adapters/agents.py:47-99 TOOLS`, `:104 adapter_for`, `:111 readiness`; `adapters/cli.py:117 CliTool`, `:194 CliAdapter`; `process_output.py:41/73` | `tests/test_cli_adapters.py` 20(:69 계약 적합, :88, :98, :122, :144, :172, :194, :221, :236, :254, :284, :301, :314, :332, :348, :396, :403) · `test_cli_output_boundary.py` 6 | Backend | 관측됨(모의 프로세스) |
| **실 CLI 바이너리로 적합성 실행**(`:373 the_tool_definitions_match_what_the_tools_actually_offer[tool]`) | 동일 | `test_cli_adapters.py:382 skip "… is not installed on this machine"` | Core/Backend에서 4건 **skip 선언**(`shutil.which` 부재) | **CI_LANE_GAP / NOT_OBSERVED**(hosted runner에 바이너리 미provision — CI로 메울 수 있음, G5); 실 로그인 계정·CX-02 credential 운영 인수만 **BLOCKED_EXTERNAL**(E1) |
| adapter readiness route | `src/saintvision/api/v1/adapters.py:35 GET /adapters`, `:64 GET /adapters/{name}`(`agents.readiness()` 노출) | `test_cli_adapters.py:415`(`agents.readiness()` 직접) — **HTTP route 레벨 시험 없음** | Backend | 관측됨(로직) / NOT_OBSERVED(HTTP 표면) — G2 |
| conformance 결과의 API 노출 | 없음(#146이 FE에서 "실제 adapter conformance API 부재 → 미측정"으로 정직화) | — | — | **설계 대상** — G3 |
| model import adapter 정확 일치 | `adapters/model_import.py:50 compare_declaration`, `:80 require_exact_declaration` | `tests/core/test_registry_policy_exact_match.py` 10 | Backend | 관측됨(요청경로 결속은 #152 설계) |

### 1.2 MLflow

| 항목 | 코드 | 시험 | hosted | 상태 |
|---|---|---|---|---|
| MLflow 실접속·등록·tracking | **없음** — `git grep -i mlflow -- src services tools tests requirements*.txt pyproject.toml` 0건(문서 7건만) | 없음 | — | **G1a IMPLEMENTATION/DESIGN GAP**(adapter·계약·설정·시험 부재 — 내부 제품 공백, owner 결정 필요) → 구현 뒤 **G1b BLOCKED_EXTERNAL**(실제 MLflow endpoint·credential 운영 실측) |

### 1.3 승인 배포 (record_deployment·approval digest)

| 불변식 | 코드 | 시험 | hosted | 상태 |
|---|---|---|---|---|
| 배포 digest는 모델 버전에서(caller 아님) | `src/saintvision/services/lineage.py:454 record_deployment`, `:534 deployed_digest=version.content_sha256` | `tests/test_lineage.py:526` · `test_model_registry.py:450` | Backend | 관측됨 |
| 승인은 정확 content(approval.subject_sha256 == version.content_sha256)·유효 시각·approved 결정만 | `lineage.py:507-514`(`AUTH_APPROVAL_DIGEST_MISMATCH`) | `test_lineage.py:543,:648` · `test_deployment_guard.py:43 approval_time_and_cached_revocation_are_checked` | Backend | 관측됨 |
| released만 배포·활성 1(partial unique)·재배포 supersede·동시 첫 배포 1건 | `lineage.py:494`, `migrations/versions/0004_s10_lineage.py:277 uq_deployments_one_active_per_environment` | `test_lineage.py:576,:590,:620` · `test_model_registry.py:509` · `test_deployment_guard.py:62,:106,:118` | Backend | 관측됨 |
| FE 배포 표시 | #146(mock deployment 정정) | `apps/web/tests/*`(Gemini lane) | desktop-browser | 관측됨(FE 범위) |
| 승인 배포 HTTP route(business lane) | **없음** — `record_deployment` 호출부 0건(#152 §1과 같은 lane) | — | — | **설계 대상**(카드 ar/#152·#158 lane) — G4 |

### 1.4 commitment route·lineage query

| 항목 | 코드 | 시험 | hosted | 상태 |
|---|---|---|---|---|
| 커널 commitment 관측 route(권한·손상 manifest 거부·tenant 격리·method 405) | `services/control-plane/src/inv/app.py:449 GET /v1/projects/{project}/models/{model_id}/versions/{version}/commitment`, `inv/model_view.py`, `model_commit.py` | `tests/integration/test_model_view.py` 7 · `test_model_commit.py` 9 · `tests/core/test_model_commit_observation_contract.py` 3 | Backend·Core | 관측됨 |
| FE commitment panel ↔ route 결속 | #146 `apps/web/src/shared/api/modelCommitmentObservation.ts`, `ModelLineageView.tsx` | `apps/web/tests/model-lineage.test.ts` · 브라우저 여정 `test_browser_real_committed_model_and_current_permission` | desktop-browser 36364528322 | 관측됨 |
| lineage query(forward trace·dataset-digest reverse lookup) | 서비스 `lineage.py:343 trace_model`(시험 `test_lineage.py:297,:316,:340`, `test_model_registry.py:238`) — **HTTP route 미구현** | 서비스 레벨만 | Backend | 관측됨(서비스) / **설계 대상 #158 v1.1**(route) |

## 2. 공백 목록 (구현·시험 추가 없음)

| # | 공백 | 분류 | 이유 / 처리 |
|---|---|---|---|
| G1a | MLflow adapter·계약·설정·시험 부재(문서에만 언급) | **IMPLEMENTATION/DESIGN GAP**(내부) | 우리가 코드로 만들 수 있는 것 — owner 결정(연동 여부·범위) 뒤 설계·구현 카드 |
| G1b | 구현 뒤 실제 MLflow endpoint·credential로 하는 운영 실측 | **BLOCKED_EXTERNAL** | G1a 이후에만 성립; 외부 서비스·credential |
| G2 | `GET /v1/adapters` route의 HTTP 레벨 시험 없음(`agents.readiness()` 로직 시험만) | NOT_OBSERVED(HTTP 표면) | 작은 시험이지만 app principal 의존성 주입이 필요해 이 카드(docs-only, 메모리 0.9GB)에서는 만들지 않음 — 후속 소카드 |
| G3 | conformance 결과의 API 노출 없음(#146이 FE에서 "미측정"으로 정직화) | **설계 대상** | 새 route·계약 필요(#158 lineage read API와 같은 lane) |
| G4 | 승인 배포·lineage query business route 부재 | **설계 대상** | #158(lineage read API v1.1)·카드 ar·#152 lane |
| G5 | CLI 4종 실바이너리 적합성(`test_the_tool_definitions_match_what_the_tools_actually_offer`)이 hosted에서 `shutil.which` 부재로 skip | **CI_LANE_GAP / NOT_OBSERVED** | hosted runner에 바이너리 provision(설치 step 또는 pinned 이미지)으로 메울 수 있음 — exact map의 skip 4를 실행 4로 전환하는 CI 카드 |
| E1 | 실 로그인 계정·CX-02 credential로 하는 CLI provider 운영 인수 | **BLOCKED_EXTERNAL** | 계정·credential 경계(G5와 분리) |

작은 PG-free 불변식 시험으로 메울 행동 공백은 없다(계약·conformance·승인 digest·활성 배포 1·commitment 관측이 전부 기존 시험으로 단언); G1a·G5는 코드/CI 카드 범위라 이 docs-only 카드에서 만들지 않는다.

## 3. 경계

로컬 실 PG·Docker·CLI 실행·전체 suite·무거운 명령 없음(메모리 0.9GB; `git grep`·`sed`·`ls`만). 판정 논리 복제 없음. owner Claude / reviewer Codex / 병합 금지. worktree 재사용, branch `agent/claude/s10-be-evidence-map`, base `1e8baf04`. S10-BE `planned` 유지. 다음 첫 행동: Codex 검토 → G1a MLflow owner 결정(코디네이터) → G5 CI provision 카드 → G3/G4는 #158 lane.
