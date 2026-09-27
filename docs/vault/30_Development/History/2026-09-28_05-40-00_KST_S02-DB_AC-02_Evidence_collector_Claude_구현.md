---
doc_id: "HIST-CLAUDE-2026-09-28-S02-DB-AC02-EVIDENCE-COLLECTOR"
title: "S02-DB AC-02 acceptance Evidence collector 구현 — 고정 SHA 1e8baf04에서 API↔PG 인증·격리 시험 4조항(28 passed)과 RLS 경계 collector(VIOLATIONS 1 = 기존 E2 public.audit_events)를 한 번에 실행해 redacted JSON/MD로 묶음, U2~U5 UNMEASURED"
version: "1.1.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T06:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S02-DB"]
tags: ["S02-DB", "AC-02", "evidence", "collector", "RLS", "token-replay", "tenant-isolation", "claude"]
---

# S02-DB AC-02 acceptance Evidence collector (2026-09-28, 카드 13)

차단 지도 [[2026-09-22_21-55-00_KST_review_done_차단지도_Codex]]의 Claude 1순위 "고정 SHA API↔PG token replay/RLS/tenant 격리 acceptance runner와 redacted Evidence 묶음"을 구현했다. 입력은 카드 5 패키지 [[2026-09-22_18-25-00_KST_S02-DB_S03-DB_검토인계패키지_Claude]] §A-1의 AC-02↔증거 대조표이며, 시험은 새로 쓰지 않고 **기존 `tests/test_api.py`와 `tools/collect_rls_evidence.py`를 그대로 재사용**한다. 공개 계약·registry·ontology 변경 0.

## 1. 만든 것

| 파일 | 내용 |
|---|---|
| `tools/collect_s02_acceptance_evidence.py` | 한 번의 호출로 (a) `tests/test_api.py`를 JUnit으로 실행해 카드 5 대조표의 16 케이스를 AC-02 4조항에 매핑(조항 `pass`는 매핑된 케이스 전부 `passed`일 때만; skipped/missing → `not_run`, 실패 → `fail`), (b) `collect_rls_evidence.py --disposable`을 실행해 역할별 RLS 경계 verdict(PASS/VIOLATIONS/UNMEASURED/UNAVAILABLE)를 받고, (c) `tools.provenance.collect`의 SHA·branch·integration 거리·clean 플래그와 collector 자체 sha256을 붙여 JSON+Markdown으로 쓴다. U2~U5는 항상 `UNMEASURED`·값 없음, `acceptanceClaim=false` 고정, 브라우저 인수는 `not_in_scope`. 실행 전 같은 label의 이전 산출물을 삭제(stale green 방지), DSN·비밀번호가 텍스트에 있으면 쓰기 거부. exit 0 PASS / 1 FAIL / 2 UNAVAILABLE / 3 NOT_RUN |
| `tests/test_collect_s02_acceptance_evidence.py` | PG-free 19: 매핑 16 케이스가 `tests/test_api.py`에 실재·중복 없음(AST), JUnit 파싱(parameter 제거·실패 문구 미보존), 조항 규칙 5, verdict 규칙 7(skip/UNMEASURED는 절대 PASS 아님), 외부 대기 UNMEASURED·값 없음, 비밀 가드, stale 삭제, stub 러너 end-to-end. `postgres` 마커 1: 실 PG 전체 파이프라인 1회(로컬 DSN 없으면 skip, CI는 fail) |
| `docs/vault/30_Development/Evidence/s02-db-acceptance/s02-acceptance-1e8baf045c5a-20260927.{json,md}` + `…-rls.{json,md}` | 아래 §2의 실측 산출물(redacted) |

## 2. 실 PG 실행 1회 (고정 SHA, 단일 invocation, detached)

- 환경: worktree `.worktrees/claude-card13` **`1e8baf04`**(= integration tip, `integration_sha` 동일, `content_clean_diff=true`; `working_tree_clean_status=false`는 실행 시점에 collector·시험 2파일이 **미커밋(untracked)** 이었기 때문이며 `modified_paths=[]`), Python 3.14 venv, PostgreSQL 16 dev 컨테이너의 disposable DB(pytest 세션용 `inv_backend_test_*` 1개 + RLS collector용 `inv_rls_*` 1개, 순차, 종료 후 DROP), 가용 메모리 2.4GB, 05:30:57~05:33:17 KST.
- 실행 시점 collector 내용 해시 `sha256 c0253d904bd81f3bde5a0848ee001bb158001ed7201a4237dafa2240c6a71a55`(§4의 사후 수정 전).
- 명령·결과:

| 단계 | 명령 | 결과 |
|---|---|---|
| API↔PG | `pytest -q -p no:cacheprovider -rs tests/test_api.py --junitxml=…`(collector 내부) | **28 passed / 0 failed / 0 skipped**, exit 0, 59.5s, junit sha256 `f9525f6579e889b8…`(`.work/`, 미커밋) |
| AC-02 조항 | 허용 Node 등록·조회(4) · 토큰 재사용 차단(4) · 타 tenant/project 차단(7) · 인증 실패 기록(1) | **4/4 pass** (16/16 passed) |
| RLS 경계 | `collect_rls_evidence.py --disposable`(역할 5 · 테이블 142 · DEFINER 12) | **VIOLATIONS 1**, accepted 9, unmeasured 0, exit 1 |
| 묶음 verdict(측정분) | — | **FAIL**(RLS 1건 때문), `acceptanceClaim=false`, collector exit 1 |

- 유일한 위반: **E2 `inv_app` `public.audit_events` — tenant_id를 가진 읽기 가능 테이블에 RLS enabled+forced 없음**. 이는 2026-09-22 `b988ca7a`의 [[rls-disposable-head-20260922]] 증거와 **같은 1건**이고 baseline(`tools/rls-boundary-baseline.json`)에 의도적으로 넣지 않은 미해결 finding이다. 즉 이번 run은 회귀가 아니라 **기존 열린 결함을 묶음 verdict에 정직하게 반영**한 것이다. `test_api.py::test_denials_are_recorded`가 "거부 기록은 tenant가 없을 수 있어 RLS가 숨긴다"고 owner 엔진으로 읽는 설계와 맞물린 항목이므로, 해소는 별도 카드(**F-S02-01**): (a) `audit_events`에 RLS enable+force + NULL tenant 행을 시스템 역할만 읽는 정책, 또는 (b) 설계 근거를 적어 baseline 수용 — 둘 중 하나를 Codex 검토로 결정. collector는 어느 쪽이든 그대로 재실행해 verdict가 바뀌는지 보여 준다.
- U2 실 IdP, U3 CA, U4 DNS, U5 물리 Node mTLS/heartbeat: **UNMEASURED**, 값 미기재(외부 대기). 브라우저 인수: 브라우저 레인.
- 비밀 검사: 산출 4파일에 DSN·비밀번호·`postgresql://`·disposable DB 이름 없음(RLS collector 내부 guard + 본 도구 guard). 단 **내가 `--note`로 넣은 문구에 로컬 listener `127.0.0.1:55432`가 남았다** — 비밀은 아니나 다음 run부터 note에 host/port를 쓰지 않는다(§4).

## 3. 자기 시험·게이트

- `tests/test_collect_s02_acceptance_evidence.py`: **19 passed / 1 skipped**(postgres 케이스는 로컬 DSN 미설정으로 skip — 실 PG는 §2의 CLI 1회로 갈음, 두 번째 PG 실행은 하지 않음; hosted **Backend** 전체 pytest(`backend.yml`)가 이 파일을 수집해 CI 조건으로 실행/실패 표시하며, Core는 label 없이는 skip — Codex 비차단 정정 반영).
- `py_compile` exit 0. 문서·계약 게이트는 PR 본문에 exit code로 기록.

## 4. 실행 뒤 도구 수정 2건(산출물은 실행 당시 그대로 보존)

- `rlsBoundary.evidenceJson` 상대 경로를 POSIX(`/`)로 기록하도록 수정 — 이번 산출 JSON/MD에는 Windows `\` 경로가 남아 있음.
- provenance에 `collectorSha256`(collector 파일 내용 해시)을 추가 — 이번 산출물에는 없으므로 §2에 해시를 직접 적었다.
- note 문구에 host/port를 쓰지 않는다(도구 변경 아님, 운용 규칙).

## 6. Codex 수정 요청 반영 (05:55 KST, PR #120 코멘트 5859666651)

| 항목 | 조치 | 검증 |
|---|---|---|
| **F-R1** 매핑 밖 API 실패가 overall PASS로 승격(fail-open) | `overall_verdict`가 API suite 전체를 fail-closed로 본다: `status != complete` 또는 `exitCode != 0` 또는 JUnit failed/error > 0 → **FAIL**(아무것도 실행되지 않았을 때만 NOT_RUN) | 되살림 시험 `test_unmapped_api_failure_fails_the_bundle_even_when_every_clause_passes`(매핑 16 pass + 매핑 밖 1 failed + RLS PASS → FAIL) + `test_incomplete_api_suite_is_never_pass`(status failed / exit 1) |
| **F-R3** RLS artifact에 disposable DB 이름·tenant UUID 2개·host:port 잔존 | 권고안 (a): `redact_text`/`assert_redacted`/`redact_rls_artifacts` — collector가 쓴 RLS JSON/MD를 그 자리에서 placeholder(`inv_rls_<redacted>`, `inv_backend_test_<redacted>`, `<uuid:redacted>`, `<host:port:redacted>`)로 다시 쓰고(JSON 유효성 유지, raw/redacted sha256 둘 다 기록), 본 묶음 JSON/MD도 쓰기 전 `assert_no_secrets`+`assert_redacted`를 통과해야 하며, `--note`는 같은 placeholder 치환을 거친다. guard 계약을 docstring에 명시(DSN/password는 거부, 위 식별자는 치환, 그 외 자유 문자열은 미검사, 실패 문구 미보존) | 회귀 `test_rls_artifacts_are_rewritten_with_placeholders`, `test_note_is_redacted_and_unredacted_text_refuses_write`; 재실행 산출 4파일 grep: `inv_rls_*` 0, UUID 0, `IPv4:port` 0, `postgresql://` 0 |
| **F-R2** evidence를 만든 collector가 도달 가능한 blob 아님 | 위 수정을 **`fc0bf0ce`로 커밋한 clean head**에서 단일 invocation을 다시 실행(05:50:23~05:52:47 KST, note에 host/port 없음). 기존 `…1e8baf045c5a-20260927.*` 4파일은 소급 덮어쓰지 않고 그대로 보존(당시 그대로: 비대칭 provenance·미redaction 상태의 첫 실행 기록) | 새 묶음 `s02-acceptance-fc0bf0ceb590-20260927.{json,md}` + `-rls.{json,md}`: `codeSha=fc0bf0ce`, `working_tree_clean_status=true`, `content_clean_diff=true`, `provenance.collectorSha256=5e07d1ac…` = `git show fc0bf0ce:tools/collect_s02_acceptance_evidence.py`의 sha256, RLS `collectorSha256=d540c8e9…` = 같은 head의 `collect_rls_evidence.py` sha256, `rlsBoundary.redacted=true`(raw `57cd6a7a…` → redacted `b86b838a…`) |
| 비차단 | "hosted Core" → hosted **Backend**(`backend.yml` 전체 pytest가 수집, Core는 label 없이 skip)로 §3 정정 | — |
| F-S02-01 | 이 PR에서 하지 않음. Codex 판정(baseline 수용 기각, RLS ENABLE+FORCE + 별도 audit writer/reader 역할 + 시험 4종)은 별도 구현 카드로 Claude tab이 진행 | — |

재실행 결과(측정분): API **28 passed / 0 failed**(exit 0, 59.125s), 4/4 조항 pass; RLS **VIOLATIONS 1**(동일 E2 `public.audit_events`) → 묶음 **FAIL**, `acceptanceClaim=false`, U2~U5 UNMEASURED. PG-free 자기 시험 **24 passed / 1 skipped**.

## 5. 경계·다음

- 이 묶음은 S02-DB `review`의 입력이지 AC-02 종료가 아니다(`acceptanceClaim=false`). U2~U5와 브라우저 red 해소는 외부·타 레인.
- 다음 첫 행동: (1) Codex가 PR을 검토하고 F-S02-01 해소 방식을 결정, (2) Claude는 차단 지도 S03-DB 행(제한 컨테이너 출력 bytes/hash·금지 명령 거부·lease 회수·Evidence ID runner) 설계 1쪽을 새 worktree `.worktrees/claude-s03-runner`에서 시작.
