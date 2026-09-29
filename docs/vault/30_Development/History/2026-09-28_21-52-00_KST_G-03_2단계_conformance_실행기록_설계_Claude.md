---
doc_id: "HIST-CLAUDE-G03-STAGE2-CONFORMANCE-RECORD-001"
title: "G-03 2단계 설계 — conformance 실행 기록의 저장과 노출: host 범위 사실에 tenant RLS를 씌우지 않고, credential 없는 생산자만 허용하며, RECORDED가 무엇을 측정한 것인지 말한다 (카드 95, docs-only)"
version: "1.2.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T22:56:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "a0e807b5"
task_ids: ["S10-BE"]
tags: ["s10-be", "g-03", "conformance", "persistence", "rls", "design", "claude"]
---

# G-03 2단계 설계 (카드 95)

전문은 [[G-03_conformance_실행기록_저장과_노출_2단계_설계]]다. 이 기록은 무엇을 결정했고 **어디서 카드 지시와 다른 결론이 났는지**를 남긴다.

## 1. 카드 지시와 다른 결론 하나 — RLS  *(v1.0 기록. **Codex가 승인**했다 — §10)*

카드는 "(1) … table·column·index·**RLS(project/tenant 범위)**"를 지시했다. 설계는 **tenant RLS를 두지 않는 쪽**을 권고한다. 이유는 1단계가 이미 정한 사실이다.

1단계 설계 §4-1은 conformance를 "**tenant의 데이터가 아니다**"로 정하고 응답에 `scope: "control-plane-host"`를 넣었다. path의 project는 **누가 볼 수 있는지의 경계**이고 소유자가 아니다. 이 결정 위에 tenant 소유 table을 얹으면 세 가지 중 하나가 된다.

- `tenant_id NOT NULL` → 같은 host 측정이 tenant마다 복제되고, **두 tenant가 같은 host에 대해 다른 답**을 가질 수 있다. 그 불일치를 막는 것이 없다.
- `tenant_id` nullable + host 행 NULL → RLS policy가 `NULLIF(current_setting('inv.tenant_id', true), '')::uuid` 비교이므로 **NULL 행은 아무 tenant에게도 안 보인다**(`db/rls.py`의 "unset scope fails closed"). policy가 있어도 읽을 수 없다.
- **`tenant_id` 없음, RLS 대상 아님, 읽기 경계는 route의 live membership** → 스키마가 사실과 일치한다. **권고.**

대가를 숨기지 않았다: (c)는 `TENANT_SCOPED_TABLES`에 들어가지 않으므로 **tenant 격리 시험의 대상이 아니고**, 어느 tenant의 project 구성원이든 같은 행을 읽는다. 그래서 행에 **tenant 간에 새어도 되는 것만** 담아야 한다는 제약이 따라오고, 그것이 `detail`을 버리는 이유가 된다.

판단은 Codex·조정자에게 남겼다. (a)를 택하려면 **"복제된 측정의 불일치를 무엇이 막는가"** 에 먼저 답해야 한다고 적었다.

## 2. `detail`을 저장하지도 노출하지도 않는다

`conformance.py`의 `_check()`는 예외를 `f"{type(exc).__name__}: {exc}"`로 만들어 `detail`에 넣는다. `CliAdapter` 경로에서 그 문자열의 출처는 **host의 CLI 출력**이고, host 경로·환경 변수·토큰 조각이 들어올 수 있다. §1의 (c)와 합치면 **한 tenant 구성원이 host 내부를 읽는 경로**가 된다.

`REDACTION_PROBES`는 adapter의 `redact()`를 **시험하는 입력**이고 `detail`을 세탁하는 장치가 아니다 — 그것을 sanitiser로 쓰는 설계는 하지 않았다. `checks` JSONB는 `name`·`passed`·`skipped`만 담고, 이름은 `CHECKLIST`의 닫힌 집합이라 자유 문자열이 아니다.

## 3. 생산자는 credential 없이 도는 것만  *(v1.0 기록. 금지 경계와 `installed-cli` 열거는 §10 F3·F2에서 바뀌었다)*

실제 CLI `install`·`authenticate` 금지 이유를 네 개로 나눠 적었다 — (i) credential이 필요하고 그것은 **G-25 BLOCKED_EXTERNAL**이다, (ii) `install`은 host를 바꾸므로 측정이 스스로를 무효화한다, (iii) 시간 상한이 없다, (iv) 한 tenant 구성원이 촉발한 실행이 **모든 tenant가 읽는 공유 사실을 덮어쓴다**.

그래서 2단계가 기록하는 것은 **fixture adapter에 대한 suite 실행**뿐이고, 행의 `subject` column이 그것을 적는다. `installed-cli`는 값으로 정의만 하고 **생산자가 없다** — G-25가 풀릴 때 스키마를 바꾸지 않고 구별할 수 있게 하기 위한 것이다.

**서버 내 실행(B)을 hosted CI import(A)보다 먼저 권고**했다. 신뢰 경계 때문이다: (B)는 서버가 자기가 부른 함수의 결과를 적으므로 위조할 제3자가 없다. (A)는 `#177` N6이 실측으로 보여 준 대로 **입력을 위조하면 통과**한다(probe T4가 실제로 통과시켰다). 두 경로를 동시에 열 이유가 없다.

## 4. 응답이 무엇을 측정한 것인지 말한다

RECORDED 한 행이 있으면 화면은 "측정됨"으로 읽는다. 그런데 주체가 fixture adapter라면 그것은 "설치된 `codex-cli`가 계약을 만족한다"가 **아니다.** `#204`에서 hosted reference가 물리 측정을 대체하지 못한다고 적은 것과 같은 종류의 구별이고, 여기서는 `subject`를 **required**로 내는 것이 그 문장이다.

`conformant` boolean은 응답에도 두지 않았다 — 1단계가 뺀 이유("boolean에는 제3의 값이 없다")가 기록이 생겨도 사라지지 않고, `skipped`가 있는 세계에서 하나의 boolean은 무엇을 통과했는지 말하지 못한다.

## 5. 계약 gate 함정 — 실측했다

union으로 가는 방식에 따라 **gate가 통과하면서 계약 파일이 낡는다.** 두 사실을 코드에서 확인했다.

1. `tools/export_schemas.py:40` `exported()`는 **`Strict` 서브클래스**이고 이름이 `Request`/`Response`로 끝나는 것만 모은다. `Annotated[Union[...], Field(discriminator=...)]` 별칭은 `Strict` 서브클래스가 **아니다**.
2. `main()`은 `EXPORTED`만 순회해 비교한다(`:82`). **디스크의 고아 schema 파일을 검출하지 않는다.** 그래서 모델이 수집 대상에서 빠지면 낡은 계약 파일이 남고 `--check`는 **PASS**다.

`check_contract_bindings.py`의 dead-contract 검사는 **report-only**이고 docstring이 *"saintvision responses are anchored by FastAPI response_model … and are out of this kernel-anchor check"* 라고 적는다 — 이것도 막지 않는다.

그래서 기존 이름 `ConformanceStatusResponse`를 없애지 않고, `exported()` 결과 집합을 고정하는 시험(T7)을 둔다.

## 6. 1단계와의 호환, 그리고 **유일한 FE 파괴 지점**

기록이 없을 때의 응답은 1단계와 **필드 집합·값이 동일**하다. `#208`이 고정한 fixture가 깨지지 않는다.

예외가 하나 있고 그것을 명시했다 — `NOT_OBSERVED_REASON`(`conformance_status.py:65`)은 "아직 저장하지 않는다"고 말하는데, **2단계가 저장하기 시작하면 그 문장이 사실이 아니게 된다.** 그래서 이 문자열을 "이 adapter에 대한 기록이 없다"로 갱신해야 하고, `#208`의 fixture도 **같은 PR에서** 함께 바뀐다.

또 `status` 리터럴이 넓어지므로 1단계의 원칙("코드가 만들 수 없는 값을 스키마가 광고하지 않는다")을 지키려면 **branch와 생산자가 같은 PR에** 들어가야 한다.

## 7. 시험 계획  *(v1.0 기록 — **T12는 틀렸고 §10 F3에서 고쳤다**)*

v1.0은 12개를 적고 핵심 부정 시험을 **T11**(route가 `run_conformance`를 import·호출하면 실패)과 **T12**(fixture 경로에서 `install`·`authenticate`가 호출되면 실패)로 뒀다. **T12는 제품 경계를 잘못 잡은 것이었다** — 현재 판(15개)과 고친 T12는 §10을 보라.

## 8. 검증 방법과 한계

- 인용 10개를 `git grep -n -F`·`git show`로 실물 확인했다. base를 `03c4dad1`에서 **`a0e807b5`(#200 현재 head)로 rebase한 뒤 10개를 다시 대조**해 옮겨간 둘(`CONFORMANCE_PATH` `:61`→`:60`, `ConformanceStatusResponse` `:1040`→`:1136`)을 고쳤다.
- `check_docs`·`check_doc_single_source --ratchet` exit 0.
- **실행하지 않았다**: 로컬 실 PG·Docker·전체 suite. docs-only이고 코드 변경 0, migration 0이다.
- **migration 번호를 예약하지 않았다** — 구현 PR에서 조정자가 배정한다.

## 9. 다음 첫 행동  *(v1.1에서 갱신)*

v1.1 재검토 요청을 올렸다. RLS 판단은 §10에서 닫혔으므로 승인 뒤 구현 카드는 (1) migration 번호 배정 요청, (2) branch·생산자·`NOT_OBSERVED_REASON`·`#208` fixture를 한 PR로 묶기, (3) `CHECKLIST` 버전별 비교 규칙 확정 순서다.

## 10. Codex 검토 반영 (v1.1)  *(F1~F5. v1.2가 그중 일부를 더 조였다 — §11)*

RLS는 **§2-1(c) host-global record로 승인**됐다. 승인 조건으로 붙은 세 불변식(row에 tenant·project·user 값이나 자유 문자열 없음 / route는 매번 `require_project_access` / 직접 DB 표면은 host-global 안전 필드만)을 설계가 계약으로 받았다. 차단 결함 5건은 다음과 같이 닫았다.

| | Codex 지적 | 반영 |
|---|---|---|
| **F1** | 목록 route와 union의 응답 shape가 모순 | **exact key set까지 확정.** 결정적이었던 것은 "**기록 없는 adapter를 배열에 넣지 않는다**"다 — `adapters[]`가 대상, `records[]`가 존재하는 측정이므로 **배열에서의 부재가 측정의 부재**이고, 그래서 "섞인 배열"과 per-adapter `NOT_OBSERVED` entry라는 개념이 사라진다. 기록 0개면 **1단계 7키 그대로**, 하나 이상이면 `records[]`를 든 별 branch. 단건은 자기 class 두 개. class 4개·계약 파일 4개·`response_model`까지 적었다. item의 결과 목록은 `outcomes`로 이름을 갈라 descriptor `checks`와 섞이지 않게 했다 |
| **F2** | 생산자 없는 값을 계약·CHECK가 광고 | **좁혔다.** Literal·CHECK는 `fixture-adapter`·`in-server` **한 값씩**, `source_ref` column은 **넣지 않는다**(채울 생산자가 없다). 넓히는 PR이 producer·검증·계약·조합 allowlist를 같은 commit에서 넓힌다 |
| **F3** | T12가 제품 경계를 잘못 고정 | **내 설계 오류였다.** `run_conformance()`의 checklist가 `adapter.install()`(`conformance.py:206`)·`adapter.authenticate()`(`:215`)를 **실제로 부른다** — 실측으로 확인했다. 그래서 금지 대상을 메서드 호출이 아니라 **실 adapter 선택(`CliAdapter`·`agents.BY_NAME`)·subprocess·실 credential·요청 중 실행**으로 다시 정했고, fixture stub은 **호출되어야 하며** host mutation·외부 credential 접근이 0임을 단언하도록 T12를 고쳤다 |
| **F4** | report 내부 무결성이 counts 합 하나 | **§2-8 신설.** 생산자는 caller dict가 아니라 실제 `ConformanceReport`에서 만들고 counts를 **재계산**, `failed`는 유도, `checks`는 개수·정확한 키·`CHECKLIST`와 같은 이름·같은 순서·중복 없음, `passed && skipped` 거부. `jsonb_array_length(checks) = total`을 **DB CHECK로도** 둔다. 깨진 저장 row는 읽을 때 **정본 5xx로 fail-closed**(T13) |
| **F5** | host 결속·단일 host 전제 없음 | **`host_id`를 row·조회·index에 결속**했다(§2-9). 비식별 opaque 값이고 설정에서 오며, 없으면 생산자는 시작하지 않고 읽기는 정본 5xx다(다른 host 기록으로 답하거나 `NOT_OBSERVED`로 위장하지 않는다). index·질의는 **`(host_id, adapter, recorded_at DESC, record_id DESC)`** 로 동률까지 결정적이다. 강제할 수 없는 배포 전제보다 행에 적힌 값을 골랐다 |

시험은 12개에서 **15개**가 됐다. T12를 고치고 T13(깨진 row fail-closed)·T14(생산자 재계산)·T15(`host_id` 부재)를 넣었으며, T5를 "**기존 계약 파일과 exact key set 대조**"로, T3을 "생산 가능한 값만"으로, T10을 "host별·결정적 최신 선택"으로 조였다.

**정직하게 적어 둘 것**: F3은 내가 설계에서 틀린 것이다 — 금지의 *이유* 네 개는 유효했지만 그것에서 **시험 가능한 경계를 도출한 방식**이 잘못됐고, 그대로 구현하면 정상 생산자가 실패했다. 실측(`:206`·`:215`)으로 확인한 뒤 경계를 다시 세웠다.

## 11. Codex 재검토 반영 (v1.2)

F1~F5의 **방향은 승인**됐고, "계약을 다시 갈라 놓은 모순"과 "강제되지 않은 보안 불변식" 다섯 건이 왔다. 전부 **둘 중 하나를 골라 한 곳에서만 말하라**는 성질이었다.

| | 지적 | 선택 |
|---|---|---|
| **R1** | 0-record 호환 설명과 시험이 모순 — §4-4가 "값 동일·fixture 불변"이라면서 다음 줄에서 `reason`을 바꾼다 | **shape 유지 / `reason` 값은 의도적으로 바뀜**으로 통일하고 세 주장("byte 동일"·"값 동일"·"fixture 불변")을 **삭제**했다. T5를 **T5a**(schema·키 집합·형) / **T5b**(새 `reason` 런타임 고정값 + `#208` fixture)로 나눴다 — JSON Schema에 런타임 문자열이 없으므로 schema 대조로는 값 동일성을 검증할 수 없다는 지적이 정확했다 |
| **R2** | aggregate와 item이 둘 다 `recordedAt`인데 "같은 키로 쓰지 않는다"고 적음 | aggregate `RECORDED`의 키를 **`latestRecordedAt`**(= `records[*].recordedAt`의 최대값)으로 **바꿨다.** item은 `recordedAt`, `NOT_OBSERVED` branch는 1단계 호환을 위해 `recordedAt: null`을 유지한다. 즉 aggregate `recordedAt`은 `NOT_OBSERVED` branch에만 있다 |
| **R3** | §3-4가 `source_ref` 결론을 되돌림 | 그 문장을 **삭제**했다. 결론은 한 곳 — 이 단계에 column이 **없고**, import를 여는 PR이 column·CHECK를 producer와 같은 migration에서 추가한다 |
| **R4** | `host_id` 비식별성이 서술뿐 | **강제로 바꿨다.** column을 **`uuid`** 로(그래서 hostname·IP·경로는 *표현 자체가 불가능*), config key를 **`INV_CONTROL_PLANE_HOST_ID`** 로 못 박고 startup·configuration-readiness에서 **strict UUID parsing**. 응답에는 `host_id`를 **내지 않는다**. T15(b)에 hostname·IP·경로·빈 문자열 거부 부정 시험을 넣어 이 조건을 **검사 가능**하게 했다 |
| **R5** | 두 fail-closed 경로가 "정본 5xx"뿐 | 둘 다 **`SYS-0002` · 500 · `retryable: false`** 로 정했다. `retryable: false`인 이유는 재시도로 낫지 않기 때문이고, `SYS-0002`를 빌려 쓰는 이유는 정본 표(`api/problem.py:86-87`)에 **설정 오류·내부 불변식 위반 code가 없기** 때문이다 — 그 한계를 §6 미해결로 적고, 전용 code가 생기면 두 줄을 옮긴다. detail에 row 내용·check 이름·예외 문자열·설정 값을 **싣지 않는다** |
| 문구 | "`record_id`는 ULID이므로 단조적" | **틀렸다.** `ids.py:new_ulid()`는 48비트 밀리초 뒤에 `secrets.randbits(80)`을 붙이므로 같은 밀리초 안에서 단조적이지 않다 — 실측으로 확인했다. 필요한 성질은 단조성이 아니라 **결정성**이므로 "결정적 lexical tie-breaker"로 고치고 그 이상을 주장하지 않았다 |

**이 판에서 배운 것**: v1.1의 결함 다섯 중 셋(R1·R2·R3)은 **새 결정을 적으면서 옛 문장을 지우지 않아** 생긴 자기모순이었다. 설계를 고칠 때 바뀐 결론을 **한 곳에서만** 말하도록 옛 문장을 찾아 지우는 것이 새 문장을 쓰는 것과 같은 크기의 일이다. R4는 다른 종류다 — "비식별"을 **서술**했지만 `String(64)`은 그것을 **강제하지 않았고**, 보안 조건은 서술이 아니라 형·파싱·부정 시험으로만 성립한다.
