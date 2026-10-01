---
doc_id: "HISTORY-CARD194-S12-ACCEPTANCE-RESOLVER-20261001"
title: "Card 194 S12-BE target·Evidence resolver 구현"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-10-01T23:43:41+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["History", "S12-BE", "acceptance", "evidence", "resolver", "migration-0058"]
---

# Card 194 S12-BE target·Evidence resolver 구현

## 1. 선택·적층 근거

- 기준 tree는 train 10 후보 `c41fe2da`다.
- coordinator의 migration 순서 정정에 따라 #286 `agent/claude/c187-s12-acceptance-write` head
  `faba659d`를 merge commit `e19aff84`로 먼저 적층했다. 0057도 0056의 자식이므로 0058을 0056에
  직접 연결하면 두 head가 생긴다. `0058_release_acceptance_resolver`의 `down_revision`은
  `0057_release_acceptance_quorum`이다.
- 원래 구현 owner는 Claude였지만 카드 187 P0 대응과 DB trigger·digest·RLS 경계 분리를 위해 coordinator가
  설계 owner Codex에게 구현을 교차 배정했다. reviewer는 Claude다.

## 2. 구현

1. migration 0058
   - `evidence_envelopes.envelope_sha256`과 INSERT trigger를 추가했다. caller digest는 저장하지 않고
     PostgreSQL 16 JSONB 직렬화·UTC microseconds·domain separator로 다시 계산한다.
   - owner 검증 helper와 trigger는 `SECURITY INVOKER`, `search_path=pg_catalog`, PUBLIC·`inv_app`
     직접 EXECUTE 회수로 고정했다. app은 trigger inline 식만 사용한다.
   - release manifest에 target registry version·Git blob SHA-1·file SHA-256을 한 단위로 pin한다.
   - append-only `release_evidence_bindings`는 FORCE RLS이며 app은 SELECT/INSERT만 갖는다. trigger가
     Evidence→Run→Workload project와 stored envelope digest를 다시 도출해 forged 값은 거부한다.
2. resolver·binder
   - strict checked-in registry loader가 exact file SHA와 공개 schema를 검증한다.
   - resolver는 release의 policy/target pins, binding, Evidence identity와 tenant/release/project scope를
     server-side로 다시 읽는다. caller hash는 비교 입력일 뿐 권위가 아니다.
   - legacy NULL digest와 registry pin 부재는 503 prerequisite, scope 부재는 404, drift는 409,
     `40P01`·`55P03`·`57014`는 `RES-0007/503/retryable=true`다.
3. 공개 read surface
   - `GET /v1/release-manifests/{release_id}/acceptance-evidence`는 fresh interactive human과 live
     `releases.accept`를 페이지마다 확인하고 server-bound identity만 반환한다.
   - telemetry·actor·project와 raw Evidence는 노출하지 않으며 cursor와 page size는 strict하다.
4. 의도적 비활성 경계
   - `INV_RELEASE_ACCEPTANCE_WRITE_ENABLED`는 바꾸지 않았다.
   - `AUTHORITATIVE_REFS_BOUND`도 false다. 현 sign-off projection은 실제 resolution DTO를 받지 않으므로
     상수만 true로 바꾸면 검증하지 않은 proposal까지 합격 처리한다.
   - legacy backfill receipt와 sign-off projection 결속은 후속 카드다.

## 3. 검증

| 검증 | 결과 |
|---|---|
| `python tools/migration_graph.py --head` | exit 0, 단일 head `0058_release_acceptance_resolver` |
| focused PG-free (`test_release_acceptance_resolver.py`, `test_ac11_migration_rehearsal.py`) | 31 passed, exit 0 |
| `python tools/export_schemas.py --check` | 97 schemas, exit 0 |
| `python tools/check_contract_bindings.py` | exit 0 |
| `python tools/check_docs.py` | 1077 versioned docs, exit 0 |
| `python tools/check_ontology.py` | exit 0 |
| `git diff --check` | exit 0 |

로컬 기본 Python은 3.10이고 control-plane은 `StrEnum`을 쓰므로 3.12/3.14 전용 route 시험을 로컬에서
합격했다고 기록하지 않는다. 또한 `INV_TEST_ADMIN_DSN`이 없어 real-PG 파일을 실행하지 않았다. 다음 단계는
exact-head hosted Core에서 0058 forward/downgrade/forward, forged digest overwrite, direct helper 거부,
forged binding 거부, RLS scope, discovery HTTP를 실제 PostgreSQL 16으로 검증하는 것이다.

## 4. 판정

코드·PG-free 계약은 구현됐지만 hosted Core와 Claude 독립 검토 전이다. 따라서 migration·trigger·RLS의 운영
판정은 `NOT_OBSERVED`, write enable은 off, S12 수락 완료 주장은 없다.
