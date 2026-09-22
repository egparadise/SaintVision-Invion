---
doc_id: "HIST-CLAUDE-S02-DB-RLS-EVIDENCE-COLLECTOR-001"
title: "S02-DB API↔PG 인증·RLS 경계 Evidence collector(tools/collect_rls_evidence.py) — 역할 5종×테이블 142×GUC 4상태 실측, 자기시험 16 실 PG, 발견 1(public.audit_events RLS 없음)·수용 예외 3 (카드 r)"
version: "1.3.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-23T00:25:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["S02-DB", "rls", "tenant-isolation", "evidence", "collector", "security-definer", "real-postgres", "codex-review"]
---

# S02-DB RLS / 인증 경계 Evidence collector (카드 r)

[[2026-09-22_21-55-00_KST_review_done_차단지도_Codex]] "Claude 몫 1순위" — API↔PG 인증·RLS Evidence collector. 브랜치 `agent/claude/s02-rls-evidence`, reviewer Codex. **계약 변경 없음**, registry status 불변(S02-DB `review` 유지, self-close 없음).

## 1. 산출물

| 파일 | 내용 |
|---|---|
| `tools/collect_rls_evidence.py` | owner DSN(`INV_AUDIT_DSN`/`--dsn`) 또는 `--disposable`(`INV_TEST_ADMIN_DSN`으로 일회용 DB 생성→alembic head→tenant 2개+project 2개 seed→측정→DROP)로 역할별 경계를 수집. 역할마다 `SET LOCAL ROLE` 후 `public`·`inv` 스키마 모든 테이블에 대해 권한(테이블/컬럼), RLS enabled/forced, 적용 정책, **실제 보이는 행 수**를 `inv.tenant_id` 4상태(미설정·tenant A·미지 tenant·비UUID)로 측정하고 superuser 기준값(전체/A/타 tenant)과 대조. SECURITY DEFINER 함수는 owner·`proconfig`·EXECUTE grant를 역할별로 기록. 모든 프로브는 트랜잭션 롤백(측정 DB 무변경). |
| `tools/rls-boundary-baseline.json` | 검토된 예외 3건(역할·테이블·규칙·사유·도입 migration). 예외는 evidence의 "Accepted exceptions" 표에 사유와 함께 노출된다(숨김 아님). |
| `tests/test_collect_rls_evidence.py` | 순수 13(E1~E6 각각 강제, baseline 매칭, compact, 비밀 가드, 렌더) + 실 PG 3(경계 실측·부정 대조군·CLI exit code). |
| `docs/vault/30_Development/Evidence/rls-boundary/rls-disposable-head-20260922.{md,json}` | head `0046` 일회용 DB 실측 산출물(DSN·비밀 0건, 자동 가드가 DSN/비밀번호 포함 시 쓰기 거부). |

기대(위반 → exit 1): E1 측정 역할은 SUPERUSER/BYPASSRLS 아님 · E2 tenant_id 있는 읽기 가능 테이블은 RLS enabled+forced · E3 GUC 미설정 시 0행(또는 거부) · E4 tenant A 설정 시 타 tenant 0행 · E5 미지 tenant 0행 · E6 DEFINER 함수 PUBLIC EXECUTE 없음. Exit 2 = 관측 불가(연결 실패; 자격증명 포함 메시지 억제). JUnit 없음, exit code만.

재실행 한 줄: `python tools/collect_rls_evidence.py --disposable --out-dir docs/vault/30_Development/Evidence/rls-boundary` (환경 `INV_TEST_ADMIN_DSN`, 값 미기재) / 기존 DB: `INV_AUDIT_DSN=<owner dsn> python tools/collect_rls_evidence.py --out-dir <dir>`.

## 2. 실측 (2026-09-22 22:40 KST, PG 16.15 127.0.0.1 컨테이너, 일회용 DB, dev DB 무접촉)

| 항목 | 결과 |
|---|---|
| 자기시험 | `tests/test_collect_rls_evidence.py` **16 passed**(실 PG 3 포함, 57s) — 분리 실행 1레인 |
| 표준 실행 `--disposable` | roles 5 · tables 142 · definer functions 12 · **accepted 9** · **violation 1** → exit 1 |
| 역할 속성 | `inv_app`/`inv_kernel`/`inv_discovery_issuer`/`inv_discovery_issuer_guard` NOLOGIN·NOSUPERUSER·NOBYPASSRLS; **`inv_runtime_dev`는 이 서버에 존재**(LOGIN, member_of `inv_kernel`, super/bypass 아님) |
| GUC | `current_setting('inv.tenant_id', true)` 미설정 값 `None`; 비UUID 값은 RLS 테이블에서 **22P02 거부**(행 노출 없음) |
| inv_app · public RLS 테이블 | `projects` 기준 2/1/1 → 미설정 0 · A 1 · 타 tenant 0 · 미지 0 (정책 `*_tenant_isolation[ALL]`, on+forced) |
| inv_app · 커널 테이블 | `inv.model_manifests` 등 권한 없음(프로브 생략) — 카드 2·3 검토와 일치 |
| inv_kernel · public | 컬럼 grant만(`S(col),U(col)`; `storage_kernel_tenant`/`kernel_tenant_isolation` 정책, on+forced) — `projects` 2/1/1 → 미설정 0 · A 1 · 타 0 |
| DEFINER 12 | 전부 `search_path=pg_catalog(,public)`; PUBLIC EXECUTE 0; `model_location_readiness(text[])`·`model_registry_snapshot` → `inv_kernel`만; `consume_discovery_issue_budget` owner `inv_discovery_issuer_guard` |
| 부정 대조군(시험) | RLS 없는 `public.rls_probe_unscoped`(tenant 2건, inv_app SELECT)를 만들면 E2·E3·E4·E5가 그 테이블에 잡히고(미설정 2행·타 tenant 1행), DROP 후 사라짐 → collector가 실제로 검사한다는 증거 |
| 조건 | Codex 50동시 placement 부하 레인(같은 서버, 별도 일회용 DB)은 이 실행 **전에 종료**(22:38); collector에 시간 단언 없음 — evidence `condition` 줄에 기록 |

## 3. 발견 (Codex 검토 요청)

- **F1 `public.audit_events` — inv_app SELECT,INSERT 인데 RLS 없음(E2)**: `0001_s02_baseline` "append-only for the application role"로 SELECT+INSERT를 주면서 RLS를 켜지 않았고 `tenant_id`는 nullable. inv_app 세션의 결함 하나로 타 tenant 감사 행이 읽힌다. 일회용 DB에는 행이 0이라 E3~E5는 침묵했지만 dev/운영에는 행이 있다. 조치 후보: (a) `ENABLE+FORCE RLS` + `tenant_isolation` 정책(`tenant_id IS NULL` 행의 소유를 먼저 정의) 또는 (b) inv_app의 SELECT 회수(쓰기 전용) — 보안 결정이라 Codex. 이 항목은 자기시험에 **pin**되어 있어(`[("E2","inv_app","public.audit_events")]`), 수정 migration이 착지하면 시험이 의도적으로 실패해 갱신을 요구한다.
- **관찰 1 `public.tenants` 전 tenant 열람(수용 예외)**: 0001이 inv_app에 SELECT를 준 설계. tenant 등록부라 tenant_id 범위가 성립하지 않아 baseline에 넣었으나, `slug/display_name` 열거 가능성은 설계 확인 대상.
- **관찰 2 `inv_discovery_issuer_guard` → `discovery_credential_issue_budgets` 전 tenant 읽기(수용 예외)**: 0045 예산 트리거용 NOLOGIN 역할. 사유를 baseline에 명시.
- **관찰 3 `inv_runtime_dev`**: 저장소 어디에도 정의가 없는 서버 로컬 역할(dev 컨테이너 부트스트랩?). `inv_kernel` 멤버·LOGIN. 정의 출처를 `개발환경_이전_절차서` 또는 compose에 고정해야 재현 가능.

## 4. 남은 것 / 후속
- 이 도구는 collector이지 CI 게이트가 아니다. F1이 닫히면 exit 0이 되고, 그때 `backend.yml`의 report-only 단계로 배선하는 것은 별도 카드.
- 운영 DB(실 IdP·물리 Node, U2~U5)에 대한 실행은 `INV_AUDIT_DSN` 모드로 그대로 가능 — S02-DB done 판정은 그 실측 뒤(자기 닫힘 없음).
- 컬럼 grant 테이블은 `count(*)`가 허용되지만 컬럼 단위 노출 폭은 `privileges.select="column"`으로만 기록한다(어느 컬럼인지는 미기록 — 필요 시 확장).

## 5. Codex 검토 반영 (v1.1.0 → v1.3.0, PR #68 코멘트 4건)

| # | Codex finding | 조치 | 검증 |
|---|---|---|---|
| 1 | 컬럼 SELECT 역할의 E4 false negative — `tenant_id <> A` 프로브가 42501로 거부되면 `rows>0`만 보는 E4가 침묵 | E4가 **owner 기준값**도 본다: 역할이 tenant A GUC로 보는 행 수가 superuser의 tenant A 행 수보다 크면 위반(거부된 프로브의 sqlstate를 detail에 기록). 직접 프로브 결과가 있으면 그것을 우선 | 순수 시험 `test_e4_uses_owner_truth_when_foreign_probe_is_denied`(Codex가 든 `A visible=2 / truth A=1 / foreign denied 42501` → E4); 실 PG 부정 대조군에 `rls_probe_colpriv`(`GRANT SELECT(note)`만, tenant_id 없음) 추가 → `privileges.select="column"`, 프로브 `denied 42501`, **E4 검출** — 18 passed |
| 2 | evidence `git_sha=b5a7f969`가 collector가 없는 커밋을 가리킴 | `provenance` 블록: HEAD SHA + **collector/baseline 파일 content sha256** + `uncommitted_sources`(수집 시점에 dirty였던 소스 목록). 커밋 전에 생성되는 evidence는 content hash가 정체성이며, 그 사실을 note로 명시. MD 머리에도 표기 | `test_provenance_records_content_hashes_and_head`; 재생성 evidence의 collector/baseline sha256 = 커밋된 파일의 sha256(검토자가 `sha256sum`으로 대조 가능) |

| 3 | **row-swap false negative** — E4가 개수 팽창만 잡아 "타 tenant 행이 같은 수의 A 행을 대체"(visible A=1, truth A=1, foreign 프로브 42501)를 놓침 | E4를 **행 정체성 대조**로 변경: 같은 REPEATABLE READ 스냅샷 안에서 owner가 tenant A 행 집합의 fingerprint(`md5(string_agg(ctid ORDER BY ctid))`)를 만들고, `SET LOCAL ROLE` 뒤 역할이 GUC=A로 보는 집합의 fingerprint와 비교. ctid를 못 읽는 컬럼 권한 역할은 읽을 수 있는 컬럼 투영 fingerprint로 대조(`method: projection`, 약함을 명시). 둘 다 불가면 `unverifiable` → E4 위반(fail-closed), baseline 사유가 있을 때만 수용. 직접 foreign 프로브·개수 비교는 보조로 유지 | 순수 `test_e4_catches_same_count_row_swap_and_unverifiable_identity`; 실 PG 부정 대조군 `rls_probe_swap`(역전 정책 `USING (tenant_id <> A)` + `SELECT(note)`만): 역할 A=1행·owner A=1행·foreign 프로브 42501인데 **identity DIFFERENT(projection) → E4 검출**; head 실측에서 142 테이블 × 역할 identity 결과 `same (ctid)` 217·`same (projection)` 20·`DIFFERENT` 2 = 둘 다 baseline 수용 `public.tenants`. **19 passed** |

| 4 | **non-unique projection false negative** — 읽을 수 있는 컬럼 값 투영이 유일하지 않으면 같은 값의 A/B 행 swap이 동일 fingerprint로 통과 | 값 투영 방식 **폐기**. 정체성은 `ctid` 또는 `tenant_id`+**완전한 PK**(`method: pk`)뿐. 둘 다 못 읽으면 `unverifiable` → 위반이 아니라 **`unmeasured`**로 기록, verdict **UNMEASURED·exit 3**(PASS 금지), baseline E4 수용 시만 제외 | 순수 `test_unverifiable_identity_is_unmeasured_never_pass`·`test_e4_catches_same_count_row_swap_by_identity`; 실 PG `rls_probe_swap`을 PK+**동일 note 값**으로 재구성(값 투영이면 충돌하는 Codex 사례) → `pk` 불일치 E4 검출, `rls_probe_colpriv`(PK 없음) → unmeasured 1. **19 passed**. head 실측 identity same(ctid) 217·same(pk) 20·DIFFERENT 2(tenants 수용)·unverifiable 0 |

재실행 결과(tip `a4bf2cee` 재기준, 일회용 DB): 자기시험 **19 passed**, `--disposable` roles 5 · tables 142 · accepted 9 · violation 1(`audit_events`, 변동 없음) → exit 1.
