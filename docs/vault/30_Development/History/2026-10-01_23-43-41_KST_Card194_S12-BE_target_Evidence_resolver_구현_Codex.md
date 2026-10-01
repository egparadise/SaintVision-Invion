---
doc_id: "HISTORY-CARD194-S12-ACCEPTANCE-RESOLVER-20261001"
title: "Card 194 S12-BE target·Evidence resolver 구현"
version: "1.0.4"
status: "review"
author: "Codex"
updated: "2026-10-02T01:26:38+09:00"
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
- 구현 commit `2a77130b` 뒤 #286이 `795db3c2`로 이동해 이를 merge commit `fe066c06`으로 다시
  따라갔다. 후속 delta는 0057 downgrade 순서 교정 한 파일이며 0058 head와 구현 파일에는 충돌이 없다.
- #286의 review 후속 `eab809d4`는 merge `42e54011`, policy·manifest pin 불변성을 추가한
  `9ff6a105`는 merge `596def53`으로 따라갔다. 마지막 충돌은 API 파일 하나였고 #291 resolver 오류
  번역과 #286의 out-of-band denial audit를 모두 보존했다. 0057은 manifest·policy pin, 0058은
  target-registry pin을 서로 다른 INVOKER trigger로 고정하므로 중복되지 않는다.
- #286 r3 문서 후속 `37db674f`는 자동 tree와 동일한 merge `f2b589d1`으로 다시 따라갔다. 제품·migration
  변경은 없고 Card 187 History 한 파일만 갱신됐다.
- 원래 구현 owner는 Claude였지만 카드 187 P0 대응과 DB trigger·digest·RLS 경계 분리를 위해 coordinator가
  설계 owner Codex에게 구현을 교차 배정했다. reviewer는 Claude다.

## 2. 구현

1. migration 0058
   - `evidence_envelopes.envelope_sha256`과 INSERT trigger를 추가했다. caller digest는 저장하지 않고
     PostgreSQL 16 JSONB 직렬화·UTC microseconds·domain separator로 다시 계산한다.
   - owner 검증 helper와 trigger는 `SECURITY INVOKER`, `search_path=pg_catalog`, PUBLIC·`inv_app`
     직접 EXECUTE 회수로 고정했다. app은 trigger inline 식만 사용한다.
   - digest는 extension 없이 PostgreSQL 16의 `pg_catalog.sha256(bytea)`를 사용하고, row helper는
     실제 의존성에 맞춰 `STABLE`로 고정했다.
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
| release acceptance/resolver PG-free 묶음 | 73 passed, real-PG 40 skipped, exit 0 |
| migration focused head·pin 회귀 | 150 passed, exit 0 |
| AC-11 aggregator | 85 passed, exit 0 |
| `python tools/export_schemas.py --check` | 97 schemas, exit 0 |
| `python tools/check_contract_bindings.py` | exit 0 |
| `python tools/check_docs.py` | 1077 versioned docs, exit 0 |
| `python tools/check_ontology.py` | exit 0 |
| `git diff --check` | exit 0 |

첫 exact-head Core run `36879319911`은 migration upgrade 단계에서
`migration_revision_mismatch`로 실패했다. 0058은 SECURITY DEFINER를 추가하지 않지만
`tools/definer-policy.json`의 graph revision도 새 head를 가리켜야 한다. policy function 집합은 바꾸지 않고
revision만 0058로 올렸으며, INVOKER Evidence 함수가 policy에 잘못 등록되지 않는 회귀 시험을 추가했다.

Claude r1의 binding 0건 오류 경계, resolver criterion 결속, release target pin 불변성은 `e0505648`에서
고쳤고 `be1bb8d7`에서 helper `STABLE`·FORCE RLS 회귀 단언을 보강했다. Claude r2는 코드와 시험을
조건부 승인했고 남은 조건은 exact-head Core green 하나다.

`be1bb8d7`의 Backend/Core는 기존 0052~0054 resume 시험이 과거 Alembic version에서 `upgrade head`를
호출해 이미 존재하는 0058 객체를 다시 만들고 공유 DB를 과거 revision으로 남기는 문제로 실패했다.
`93a42a26`은 graph head·definer blob pin을 0058에 맞췄고, `09fd39a3`은 각 probe가 자기 migration만
재실행한 뒤 공유 DB version을 0058로 복원하도록 했다.

`596def53` Backend 3.12 run `36888765842`는 7018 passed·51 skipped·2 failed를 기록했다. 첫 실패는
#286의 의도된 커밋형 409 전이가 canonical exception handler를 통과하지 않아 route에서 감사하는 유일한
예외인데 기존 `test_no_route_records_a_denial_itself`가 이를 전역 금지한 결합 충돌이었다. 둘째 실패는
0054 downgrade 보호 시험이 공유 DB의 현재 `0058` head를 과거 `0054`로 단언한 순서 의존이었다.
`ed46b2b9`은 직접 route 감사자를 `release_acceptance.py`의 `refused.transitioned` 1곳으로만 허용하고,
downgrade 거부 전후에 `0058` 전체 head 보존·finally upgrade를 단언한다. PG-free canonical audit는
19 passed, migration 파일은 `py_compile` 및 `git diff --check`를 통과했다. 최종 hosted Core만 PASS
근거가 될 수 있으므로 이 문서 commit 뒤 exact-head run 결과는 PR #291 코멘트에 남긴다.

로컬 기본 Python은 3.10이고 control-plane은 `StrEnum`을 쓰므로 3.12/3.14 전용 route 시험을 로컬에서
합격했다고 기록하지 않는다. 또한 `INV_TEST_ADMIN_DSN`이 없어 real-PG 파일을 실행하지 않았다. 다음 단계는
exact-head hosted Core에서 0058 forward/downgrade/forward, forged digest overwrite, direct helper 거부,
forged binding 거부, RLS scope, discovery HTTP를 실제 PostgreSQL 16으로 검증하는 것이다.

## 4. 판정

코드·PG-free 계약과 Claude r2 코드 검토는 통과했지만 exact-head hosted Core가 진행 중이다. 따라서
migration·trigger·RLS의 운영 판정은 아직 `NOT_OBSERVED`, write enable은 off, S12 수락 완료 주장은 없다.
