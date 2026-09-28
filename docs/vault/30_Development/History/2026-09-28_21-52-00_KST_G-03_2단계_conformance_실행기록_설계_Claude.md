---
doc_id: "HIST-CLAUDE-G03-STAGE2-CONFORMANCE-RECORD-001"
title: "G-03 2단계 설계 — conformance 실행 기록의 저장과 노출: host 범위 사실에 tenant RLS를 씌우지 않고, credential 없는 생산자만 허용하며, RECORDED가 무엇을 측정한 것인지 말한다 (카드 95, docs-only)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T21:52:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "a0e807b5"
task_ids: ["S10-BE"]
tags: ["s10-be", "g-03", "conformance", "persistence", "rls", "design", "claude"]
---

# G-03 2단계 설계 (카드 95)

전문은 [[G-03_conformance_실행기록_저장과_노출_2단계_설계]]다. 이 기록은 무엇을 결정했고 **어디서 카드 지시와 다른 결론이 났는지**를 남긴다.

## 1. 카드 지시와 다른 결론 하나 — RLS

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

## 3. 생산자는 credential 없이 도는 것만

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

## 7. 시험 계획

12개를 표로 적었고 핵심 부정 시험은 **T11**(route가 `run_conformance`를 import·호출하면 실패)과 **T12**(fixture 경로에서 `install`·`authenticate`가 호출되면 실패)다. 나머지는 계약·권한·append-only·index다.

## 8. 검증 방법과 한계

- 인용 10개를 `git grep -n -F`·`git show`로 실물 확인했다. base를 `03c4dad1`에서 **`a0e807b5`(#200 현재 head)로 rebase한 뒤 10개를 다시 대조**해 옮겨간 둘(`CONFORMANCE_PATH` `:61`→`:60`, `ConformanceStatusResponse` `:1040`→`:1136`)을 고쳤다.
- `check_docs`·`check_doc_single_source --ratchet` exit 0.
- **실행하지 않았다**: 로컬 실 PG·Docker·전체 suite. docs-only이고 코드 변경 0, migration 0이다.
- **migration 번호를 예약하지 않았다** — 구현 PR에서 조정자가 배정한다.

## 9. 다음 첫 행동

Codex 계약·보안 검토. 승인 뒤 구현 카드는 (1) migration 번호 배정 요청, (2) §1의 RLS 판단 확정, (3) branch·생산자·`NOT_OBSERVED_REASON`·`#208` fixture를 한 PR로 묶는 순서다.
