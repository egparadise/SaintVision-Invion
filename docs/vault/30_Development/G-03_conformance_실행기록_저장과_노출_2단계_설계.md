---
doc_id: "CLAUDE-G03-CONFORMANCE-RECORD-DESIGN-001"
title: "G-03 2단계 설계 — conformance 실행 기록의 저장과 노출: host 범위 사실을 tenant RLS로 소유한 척하지 않고, credential 없는 생산자만 허용하며, RECORDED branch가 무엇을 측정한 것인지 말한다 (docs-only)"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T21:52:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "a0e807b5"
task_ids: ["S10-BE"]
tags: ["s10-be", "conformance", "adapter", "api", "persistence", "rls", "design", "claude"]
---

# G-03 2단계 설계 — conformance 실행 기록의 저장과 노출

1단계 설계는 [[G-03_conformance_결과_API_노출_설계]] v1.2이고 그 §3이 2단계를 "누가·언제 실행해 무엇이 나왔는지 기록하고 그 기록을 노출"로, §7이 "**설계 단계에서 멈추고 migration 번호를 먼저 요청**"으로 남겨 두었다. 이 문서가 그 설계다. 1단계 구현은 `#200`이고 이 문서의 base는 `#200`의 현재 head `a0e807b5`다 — 2단계가 인용하는 코드가 그 tree에만 있으므로, 인용을 실물로 확인할 수 있는 지점을 base로 골랐다.

**migration 번호는 이 카드에서 예약하지 않는다.** 구현 PR 시점에 조정자가 배정한다(1단계 §7은 "먼저 요청"이라고 적었는데, 조정자 지시가 배정 시점을 구현 PR로 옮겼다).

## 0. 결정 요약

1. **기록은 host 범위 사실이다.** tenant가 소유하지 않는다. 그래서 table에 `tenant_id`를 두지 않고, **RLS로 격리하지 않는다** — 격리할 tenant 데이터가 없기 때문이다. 읽기 경계는 1단계와 같이 **route의 live membership**이다(§2-1). 이것은 카드가 지시한 "RLS(project/tenant 범위)"와 다른 결론이므로, 대안 두 개와 함께 근거를 적고 판단을 Codex·조정자에게 남긴다.
2. **생산자는 credential 없이 도는 것만이다.** 실제 CLI `install`·`authenticate` 호출은 금지한다(§3-2). 그래서 RECORDED 한 행은 "**이 suite가 fixture adapter에 대해 이렇게 나왔다**"이고 "설치된 `claude-code`가 계약을 만족한다"가 **아니다.** 응답이 그 차이를 말한다(§3-3).
3. **증거 출처는 인증되지 않는다.** import 경로를 고르면 서버는 report의 출처를 검증할 수 없다 — `#177` N6과 같은 신뢰 경계이고, 문서로 적는 것 말고는 닫히지 않는다(§3-4).
4. **응답은 `status`로 구별되는 discriminated union**이고 `NOT_OBSERVED` branch는 **1단계와 byte 단위로 같다**(§4-4). RECORDED branch는 non-null `recordedAt`·counts·report를 **required**로 갖는다.
5. **계약 gate에 함정이 하나 있다** — `exported()`는 `Strict` 서브클래스만 찾고 `--check`는 고아 schema 파일을 검출하지 않는다. union으로 바꾸는 방식에 따라 gate가 **통과하면서** 계약 파일이 낡는다(§4-2).
6. `detail` 자유 문자열은 **저장도 노출도 하지 않는다**(§2-5). CLI 출력과 예외 문자열이 들어오는 자리이고, host 범위 기록은 모든 tenant의 project 구성원이 읽는다.

## 1. 실측 — 1단계가 남긴 자리

전부 `git grep -n -F`·정독으로 확인했다. 경로와 줄 번호는 base `a0e807b5` 기준이고, rebase 뒤 인용 10개를 전부 다시 대조해 옮겨간 둘(`conformance_status.py`의 `CONFORMANCE_PATH`, `schemas.py`의 `ConformanceStatusResponse`)을 고쳤다.

| 사실 | 출처 |
|---|---|
| 생산자는 있고 저장이 없다 | `src/saintvision/adapters/conformance.py:145` `def run_conformance(` |
| 기록 shape는 이미 정해져 있다 | 같은 파일 `def to_dict(self)` — *"The shape recorded as AC-10 evidence."* |
| check 이름의 단일 정본 | 같은 파일 `class CheckSpec`, `CHECKLIST` |
| 1단계 route | `src/saintvision/api/v1/conformance_status.py:60` `CONFORMANCE_PATH = "/projects/{project_id}/adapters/conformance"` |
| 1단계 응답 모델 | `src/saintvision/api/schemas.py:1136` `class ConformanceStatusResponse(Strict)` — `status: Literal["NOT_OBSERVED"]`, `recorded_at: None` **required** |
| 읽기 등급은 membership | `src/saintvision/services/projects.py` `def require_project_access(` — 존재 비노출 거부 동형 |
| host 범위 어휘가 이미 있다 | `src/saintvision/api/v1/adapters.py` `measurementScope: "control-plane-host"`, 1단계 응답 `scope: Literal["control-plane-host"]` |
| 대상 adapter 목록 | `src/saintvision/adapters/agents.py:99` `TOOLS`, `:101` `BY_NAME` |
| 실 credential conformance는 막혀 있다 | 1단계 §10 — `credential_ref` 기본값 `"conformance://dummy"`, 실제 credential은 **G-25 BLOCKED_EXTERNAL** |

`to_dict()`가 내는 키는 `adapter`·`contractVersion`·`total`·`passed`·`failed`·`skipped`·`conformant`·`checks[{name, passed, skipped, detail}]`이다. 2단계의 column과 응답은 **이 shape에서 파생**되고 새로 발명하지 않는다.

## 2. 저장 — table·column·index·RLS

### 2-1. 먼저 풀어야 하는 것: host 범위 사실을 tenant RLS로 격리할 수 있는가

1단계가 **명시적으로** 정한 것이 있다(§4-1): conformance는 tenant 데이터가 **아니고**, path의 project는 **누가 볼 수 있는지의 경계**이며 소유자가 아니다. 응답의 `scope: "control-plane-host"`가 그 말을 한다. 2단계에서 table을 그리면 이 결정이 스키마와 충돌한다.

| 후보 | 결과 | 판단 |
|---|---|---|
| (a) `tenant_id NOT NULL` + 표준 tenant RLS | 같은 host 측정이 **tenant마다 복제**된다. 두 tenant가 같은 host에 대해 **다른 답**을 가질 수 있고, 그 불일치를 아무것도 막지 않는다. "conformance는 project마다 다르지 않다"는 1단계 결정과 정면으로 어긋난다 | **권고하지 않음** |
| (b) `tenant_id` nullable + host 행은 NULL | RLS policy는 `NULLIF(current_setting('inv.tenant_id', true), '')::uuid` 비교이므로 **NULL 행은 어떤 tenant에게도 보이지 않는다**(`src/saintvision/db/rls.py`의 *"unset scope fails closed"*). 즉 policy가 있어도 host 행을 읽을 수 없어 RLS를 끄거나 우회해야 한다 — `audit_events`가 nullable `tenant_id`를 갖고 **app role의 SELECT를 뺀** 이유와 같은 구조다 | **권고하지 않음** |
| **(c) `tenant_id` 없음. RLS 대상 아님. 읽기 경계는 route의 live membership** | 스키마가 사실과 일치한다 — 이 행은 host에 관한 것이고 누구의 것도 아니다. 격리는 **읽을 수 있는 사람**에만 필요하고 그것은 이미 `require_project_access()`가 한다(1단계와 동일) | **권고** |

(c)를 고를 때 **정직하게 적어야 하는 대가**가 있다. `TENANT_SCOPED_TABLES`에 들어가지 않으므로 이 table은 **tenant 격리 시험의 대상이 아니고**, 어느 tenant의 project 구성원이든 같은 행을 읽는다. 그래서 **행의 내용이 tenant 간에 새어도 되는 것만**이어야 한다 — 그것이 §2-5에서 `detail`을 버리는 이유다.

카드의 지시는 "RLS(project/tenant 범위)"였다. 위 근거로 (c)를 권고하되, 조정자·Codex가 (a)를 원하면 **"복제된 측정의 불일치를 무엇이 막는가"** 를 함께 정해야 한다고 적어 둔다. 그 질문에 답이 없으면 (a)는 스키마가 거짓말을 하게 된다.

### 2-2. column

table 이름 `adapter_conformance_records`. `to_dict()`에서 파생한다.

| column | 형 | 왜 |
|---|---|---|
| `record_id` | `String` PK | `prefix_ULID`. `ids.py`의 `PREFIXES`에 새 kind가 필요하다(§2-6) |
| `adapter` | `String(64)` NOT NULL | `TOOLS`의 이름. allowlist 밖 값은 저장 전에 거부한다 |
| `contract_version` | `String(32)` NOT NULL | report의 `contractVersion`. adapter가 선언한 값이고 suite가 구현한 값과 다를 수 있다 — 그 불일치가 곧 check 하나의 실패다 |
| `suite_contract_version` | `String(32)` NOT NULL | suite 쪽 `CONTRACT_VERSION`. 둘을 같은 행에 적어야 "무엇에 대해 판정했는지"가 남는다 |
| `subject` | `String(32)` NOT NULL | **무엇을 측정했는가** — `fixture-adapter` \| `installed-cli`. §3-3 |
| `provenance` | `String(32)` NOT NULL | **어디서 왔는가** — `in-server` \| `hosted-ci-import`. §3-1 |
| `total`·`passed`·`failed`·`skipped` | `Integer` NOT NULL, `>= 0` | report의 counts. `conformant`는 **저장하지 않는다**(§2-3) |
| `checks` | `JSONB` NOT NULL | check별 `name`·`passed`·`skipped`만. `detail` 없음(§2-5) |
| `recorded_at` | `DateTime(timezone=True)` NOT NULL | 측정 시각. 응답 `recordedAt`의 원본 |
| `source_ref` | `String(200)` NULL | import일 때 hosted run/artifact 식별자. 신뢰 경계는 §3-4 |
| `created_at`·`version` | 기존 table 관례와 동일 | |

`conformant`를 저장하지 않는 이유: `to_dict()`에서 그것은 `failed == 0 and passed > 0`의 **파생값**이다. 저장하면 counts와 어긋날 수 있는 두 번째 진실이 생긴다. 응답에서 필요하면 counts에서 계산한다.

`CHECK` 제약으로 고정할 것: counts 비음수, `passed + failed + skipped == total`, `subject`·`provenance`가 각각 닫힌 집합. 마지막 것은 오타가 조용히 새 범주를 만드는 것을 막는다.

### 2-3. index

읽기 질의는 하나다 — **"이 adapter의 최신 기록"**. 1단계 §7이 이미 `(tenant_id, adapter, recorded_at DESC)`를 예고했고, `tenant_id`가 없어지므로 **`(adapter, recorded_at DESC)`** 다.

1단계 §7이 `#174`를 반례로 들었다("route만으로 끝나지 않고 index가 필요했다"). 그래서 이 index는 구현 PR의 migration에 **함께** 들어간다. index 없이 route를 먼저 넣는 순서는 택하지 않는다.

### 2-4. append-only

이 기록은 **관측의 진술**이다. 고쳐 쓸 이유가 없고, 고쳐 쓸 수 있으면 "그때 이렇게 나왔다"가 보장되지 않는다. 그래서 `APPEND_ONLY_TABLES`(`src/saintvision/db/models/__init__.py:233`)에 넣는다 — `evidence_envelopes`·`run_records`와 같은 이유다. app role은 INSERT·SELECT만 갖고 UPDATE·DELETE를 갖지 않는다.

보존 기간은 정하지 않는다 — 삭제 주체가 정해지지 않았고, 정하지 않은 보존을 스키마에 적으면 지키지 않는 약속이 된다. 이것은 §6의 미해결로 남긴다.

### 2-5. `detail`은 저장하지도 노출하지도 않는다

`to_dict()`의 check에는 `detail` 자유 문자열이 있고, `_check()`가 **예외를 문자열로 만들어** 거기 넣는다(`f"{type(exc).__name__}: {exc}"`). `CliAdapter` 경로에서 그 문자열의 출처는 **host의 CLI 출력**이다.

- host 경로·환경 변수·토큰 조각이 예외 메시지에 들어올 수 있다.
- §2-1(c)에 따라 이 행은 **모든 tenant의 project 구성원**이 읽는다.
- 그러므로 `detail`을 저장하면 **한 tenant의 구성원이 host의 내부를 읽는 경로**가 생긴다.

`conformance.py`의 `REDACTION_PROBES`는 **adapter의 `redact()`를 시험하는 입력**이고 `detail`을 세탁하는 장치가 아니다. 그것을 sanitiser로 쓰는 설계는 하지 않는다.

그래서 `checks` JSONB는 `name`·`passed`·`skipped`만 담는다. 실패 원인을 사람이 봐야 할 때는 생산자 쪽 로그(운영자 권한)에서 보고, API는 **무엇이 실패했는지(이름)** 까지만 말한다. 이름은 `CHECKLIST`의 닫힌 집합이므로 자유 문자열이 아니다.

### 2-6. id kind

`src/saintvision/ids.py:29` `PREFIXES`에 새 kind가 필요하다(`"conformance_record": "cfr"` 형태). `new_id()`는 알 수 없는 kind에 `ValueError`를 내므로, 추가하지 않으면 생산자가 시작되지 않는다 — 조용히 실패하지 않는다.

### 2-7. migration

번호는 **구현 PR에서 조정자가 배정**한다. 이 설계는 예약하지 않는다. migration이 할 일은 table 생성 + `CHECK` 제약 + §2-3 index + append-only 권한이고, **RLS policy는 만들지 않는다**(§2-1(c)). downgrade는 table drop으로 가역이다 — 관측 기록을 지우는 것이 되므로, 되돌릴 이유가 "잘못 배포했다" 하나임을 migration docstring에 적는다.

## 3. 생산자 — credential 없이 도는 것만

### 3-1. 두 후보

| 후보 | 무엇 | 대가 |
|---|---|---|
| **(A) hosted CI import** | hosted CI가 fixture/synthetic adapter에 대해 suite를 돌려 report를 artifact로 내고, 서버가 그것을 import해 한 행으로 만든다 | 서버는 **출처를 인증할 수 없다**(§3-4). 대신 실행 환경이 재현 가능하고 host에 부작용이 없다 |
| **(B) 서버 내 실행** | 서버가 fixture adapter에 대해 `run_conformance()`를 직접 부른다 | 출처 문제가 없다(서버가 자기 실행을 기록한다). 대신 **무엇을 측정한 것인지가 더 좁다** — fixture adapter는 host에 설치된 CLI가 아니다 |

**권고: (B)를 먼저, (A)는 나중.** 이유는 신뢰 경계다. (B)는 서버가 자기가 부른 함수의 결과를 적으므로 위조할 제3자가 없다. (A)는 `#177` N6이 실측으로 보여 준 대로, import 입력을 위조하면 통과한다. 두 경로를 동시에 열 이유가 없고, (B)만으로도 1단계의 `NOT_OBSERVED`를 벗어나기에 충분하다.

(B)를 고르면 실행 주체는 **요청이 아니다** — 1단계 §3이 금지한 것이 그것이다. 운영 명령(CLI entry point)이나 예약 작업이 부르고, 읽기 route는 기록만 읽는다. 어느 쪽이든 **요청 처리 중에는 suite를 돌리지 않는다**.

### 3-2. 실제 CLI `install`·`authenticate`를 부르지 않는 이유

`run_conformance()`는 `CHECKLIST`의 각 `spec.run(adapter, credential_ref)`를 부르고, 그 안에 adapter의 `install`·`authenticate`·`run`·`collect`·`cancel`이 있다. `CliAdapter`에서 이것은 **host의 CLI 프로세스를 구동**하는 일이다(1단계 §3의 실측).

금지 이유를 네 개로 나눠 적는다.

1. **credential이 필요하다.** `authenticate`는 실제 자격 증명을 요구하고, 그 자격 증명은 이 플랫폼이 보관하는 것이 아니다. 실 credential conformance는 **G-25 BLOCKED_EXTERNAL**이다(1단계 §10). 없는 자격으로 호출하면 측정이 아니라 **실패를 기록**하는 것이고, 그 실패를 "adapter가 계약을 위반했다"로 읽으면 거짓이다.
2. **부작용이다.** `install`은 host를 바꾼다. 기록을 만들기 위해 host 상태를 바꾸는 측정은 스스로를 무효화한다.
3. **경계 없는 시간.** CLI 프로세스는 네트워크를 타고, 상한이 없다.
4. **다른 사람의 host를 건드린다.** 한 tenant의 구성원이 촉발한 실행이 모든 tenant가 읽는 host 기록을 바꾼다 — §2-1(c)의 공유 범위와 합치면 **한 사람이 공유 사실을 덮어쓸 수 있다**는 뜻이 된다.

따라서 2단계가 기록하는 것은 **fixture adapter에 대한 suite 실행**뿐이다. `subject = "fixture-adapter"`가 그것을 행에 적는다. `installed-cli`는 값으로 정의해 두지만 **G-25가 풀릴 때까지 아무 생산자도 그것을 쓰지 않는다** — 열거만 하고 쓰지 않는 값을 두는 이유는, 그때 스키마를 바꾸지 않고 구별할 수 있게 하는 것이다.

### 3-3. 그래서 응답이 무엇을 측정했는지 말해야 한다

이것이 이 설계에서 가장 틀리기 쉬운 지점이다. RECORDED 한 행이 있으면 화면은 "conformance 측정됨"으로 읽는다. 그런데 그 측정의 주체가 fixture adapter라면, 그것은 **suite가 스스로에 대해 통과했다**는 말에 가깝고 "설치된 `codex-cli`가 계약을 만족한다"가 **아니다.**

`#204`에서 같은 종류의 구별을 이미 했다 — hosted reference는 물리 측정을 대체하지 못하고, 그 문장이 없으면 green이 과대 해석된다. 여기서는 `subject`가 그 문장이다. 응답은 `subject`를 **required**로 내고, FE 문구는 `fixture-adapter`일 때 "설치된 CLI"라고 말하지 않는다. 이 대응은 `#146`·`#208`이 정한 어휘와 함께 FE 카드에서 확정한다.

### 3-4. 증거 출처 인증 한계 (`#177` N6과 같은 신뢰 경계)

(A) hosted CI import를 나중에 열 때의 경계를 미리 적는다. `#177`에서 실측으로 확인된 형태다.

- importer가 GitHub API를 **직접 조회하지 않고** run·artifact JSON을 **호출자에게서 입력받으면**, JSON의 출처는 검증되지 않는다. digest는 zip byte와 결속되지만, **JSON과 zip을 둘 다 위조하면 통과한다**(`#177` probe T4가 실제로 통과시켰다).
- `repository`·`workflow` 결속이 없으면 다른 fork의 실제 run도 통과한다(`#177` 관찰 2, probe T5).
- 따라서 import 경로는 **적어도** (i) 서버가 스스로 조회하거나, (ii) run 식별자·repository·workflow·artifact digest를 모두 결속하고, (iii) 그래도 남는 한계를 문서에 적어야 한다.

**2단계는 (B)만 열기 때문에 이 경계를 열지 않는다.** `source_ref`는 nullable로 두고 (B)에서는 NULL이다. (A)를 여는 카드가 이 §을 계약으로 받아 닫아야 한다.

## 4. 노출 — RECORDED branch

### 4-1. 모양

`status`를 discriminator로 하는 두 branch다.

```
status = "NOT_OBSERVED"   -> 1단계와 동일한 필드 집합 (§4-4)
status = "RECORDED"       -> recordedAt(non-null) + counts + checks + subject + provenance
```

RECORDED branch의 required 필드:

| 필드 | 형 | 왜 required |
|---|---|---|
| `status` | `Literal["RECORDED"]` | discriminator |
| `scope` | `Literal["control-plane-host"]` | 1단계와 같은 어휘. 기록이 생겼어도 소유자는 생기지 않는다 |
| `recordedAt` | non-null aware datetime | 1단계가 `None`으로 고정한 자리의 반대. **null 불가** — RECORDED인데 시각이 없으면 기록이 아니다 |
| `adapter` | `str` | 어느 adapter의 기록인지 |
| `contractVersion`·`suiteContractVersion` | `str` | §2-2의 두 값 |
| `subject` | `Literal["fixture-adapter","installed-cli"]` | §3-3. **이것이 없으면 응답이 과대 해석된다** |
| `provenance` | `Literal["in-server","hosted-ci-import"]` | §3-1 |
| `total`·`passed`·`failed`·`skipped` | `int >= 0` | counts. 1단계가 counts를 뺀 이유의 반대 — 여기서는 측정이 있으므로 숫자가 뜻을 갖는다 |
| `checks` | `list[{name, passed, skipped}]` | `detail` 없음(§2-5) |

`conformant` boolean은 **응답에도 두지 않는다.** 1단계가 그것을 뺀 이유("boolean에는 제3의 값이 없다")는 기록이 생겨도 사라지지 않는다 — `skipped`가 있는 세계에서 하나의 boolean은 "무엇을 통과했는가"를 말하지 못한다. 소비자가 필요하면 counts로 계산하고, 계산식이 화면마다 다르면 그것이 드러나는 것이 낫다.

counts 사이의 관계(`passed + failed + skipped == total`)는 **응답 모델에서도 검증**한다. DB의 `CHECK`가 있어도 응답 조립에서 깨질 수 있고, 깨진 합은 "측정처럼 보이는 숫자"이므로 조용히 나가면 안 된다.

### 4-2. 계약 gate 함정 — 실측했다

union으로 가는 방식에 따라 **gate가 통과하면서 계약 파일이 낡는다.** 두 사실을 확인했다.

1. `tools/export_schemas.py:40` `def exported()`는 **`Strict` 서브클래스이고 이름이 `Request`/`Response`로 끝나는 것**만 모은다. `Annotated[Union[...], Field(discriminator=...)]` 별칭은 `Strict` 서브클래스가 **아니므로** 수집되지 않는다.
2. `main()`은 `EXPORTED`를 순회해 비교만 한다(`tools/export_schemas.py:82`). **디스크에 남은 고아 schema 파일을 검출하지 않는다.** 그러므로 `ConformanceStatusResponse`가 수집 대상에서 빠지면 `contracts/conformance-status-response.schema.json`이 **낡은 채 남고 `--check`는 PASS**다.

`tools/check_contract_bindings.py`의 dead-contract 검사는 **report-only**이고, 그 docstring이 *"saintvision responses are anchored by FastAPI response_model … and are out of this kernel-anchor check"* 라고 적는다. 즉 이것도 막지 않는다.

**그래서 이렇게 한다.**

- 두 branch를 **각각 `Strict` 서브클래스**로 만들고 이름을 `...Response`로 끝낸다 → 둘 다 계약 파일로 생성된다.
- **기존 이름 `ConformanceStatusResponse`를 없애지 않는다.** 없애면 §4-2의 고아가 생긴다. 남기는 방법은 구현에서 둘 중 하나로 정한다 — (i) 기존 이름을 `NOT_OBSERVED` branch의 이름으로 유지, (ii) 기존 이름을 union envelope의 `Strict` 표현으로 유지. (i)이 단순하고 1단계 계약 파일이 그대로 뜻을 유지한다.
- **`exported()`의 결과 집합을 고정하는 시험**을 둔다(§5의 T7). 계약 파일이 조용히 사라지거나 고아가 되는 것을 gate 대신 시험이 잡는다.

### 4-3. 단건 route와 `RES-0004`

1단계는 adapter별 route를 두지 않았고 그래서 `RES-0004`도 없었다("기록이 없으면 adapter마다 다를 것이 없다", 1단계 docstring). 2단계에는 기록이 있으므로 단건이 뜻을 갖는다.

```
GET /v1/projects/{project_id}/adapters/{name}/conformance
```

- `name`이 `BY_NAME`(`agents.py:101`) 밖이면 **`RES-0004` 404**. `#205`가 `/v1/adapters/{name}`의 unknown adapter를 같은 code로 정본화했으므로 어휘가 일치한다.
- `name`은 allowlist 안이지만 **기록이 없으면** `RES-0004`가 아니라 **`status: "NOT_OBSERVED"` 200**이다. "그런 adapter는 없다"와 "그 adapter의 측정이 없다"는 다른 사실이고, 404로 합치면 두 번째가 첫 번째처럼 읽힌다.
- 목록 route(`.../adapters/conformance`)는 1단계 path를 유지하고, adapter별 최신 기록의 배열 + 기록 없는 adapter의 `NOT_OBSERVED`를 함께 낸다. 기록이 하나도 없으면 **1단계와 같은 응답**이다(§4-4).
- 권한은 1단계와 같다 — `require_project_access()`, 존재 비노출, `AUTH-0030` 403. 등급(`canApprove`)은 요구하지 않는다. 읽기다.

### 4-4. 1단계 `NOT_OBSERVED`와의 호환

**바꾸지 않는 것을 명시한다.** 기록이 없을 때 목록 route의 응답은 1단계와 **필드 집합·값이 동일**하다 — `status`·`reason`·`scope`·`contractVersion`·`adapters`·`checks`·`recordedAt: null`. `#208`이 고정한 FE fixture(`reason` 문자열 byte 일치까지)가 **깨지지 않는다.**

- `recordedAt`은 1단계에서 `None` **required**였다. union에서 `NOT_OBSERVED` branch는 그 형을 유지한다 — `None`만 허용한다.
- `reason` 문자열(`conformance_status.py:65` `NOT_OBSERVED_REASON`)은 "아직 저장하지 않는다"고 말한다. 2단계가 저장하기 시작하면 **이 문장은 사실이 아니게 된다.** 그래서 2단계 구현은 이 문자열을 "이 adapter에 대한 기록이 없다"로 **갱신**해야 하고, `#208`의 fixture도 같은 PR에서 함께 바뀐다. **이것이 2단계의 유일한 FE 파괴 지점**이므로 여기 적어 둔다.
- `status` 리터럴이 넓어진다. 1단계가 `Literal["NOT_OBSERVED"]` 하나로 둔 이유는 *"코드가 만들 수 없는 `RECORDED`를 스키마가 광고하지 않는다"* 였다. 2단계는 생산자를 함께 넣으므로 그 조건이 충족된다 — **branch와 생산자가 같은 PR에 들어가야 한다**는 뜻이다.

## 5. 되돌리면 실패하는 시험 계획

| # | 무엇을 고정하는가 | 되돌릴 때 실패하는 방식 | 종류 |
|---|---|---|---|
| T1 | `detail`이 저장·노출되지 않는다 | `checks` JSONB에 `detail` 키를 넣으면 실패. 응답 모델이 `detail`을 받으면 `extra="forbid"`로 실패 | PG-free |
| T2 | counts 합 | `passed+failed+skipped != total` 응답을 만들면 실패. DB `CHECK`는 실 PG로 별도 | PG-free + 실 PG |
| T3 | `subject`가 required이고 닫힌 집합 | `subject`를 빼거나 목록 밖 값을 쓰면 실패 — §3-3의 과대 해석 방지가 시험으로 고정된다 | PG-free |
| T4 | RECORDED는 `recordedAt` non-null | `recordedAt: null`인 RECORDED를 만들면 실패 | PG-free |
| T5 | 기록 없음은 1단계와 동일 | `NOT_OBSERVED` 응답의 **필드 집합과 값**을 1단계 계약 파일과 대조. 한 필드라도 바뀌면 실패 | PG-free |
| T6 | unknown adapter는 `RES-0004`, 기록 없는 known adapter는 200 `NOT_OBSERVED` | 둘을 합치면(404로 통일) 실패 | PG-free |
| T7 | `exported()` 결과 집합 | 계약 파일이 사라지거나 고아가 되면 실패 — §4-2의 gate 공백을 메운다 | PG-free |
| T8 | append-only | app role로 UPDATE·DELETE를 시도하면 거부된다 | **실 PG** |
| T9 | 읽기 경계 | 비회원 403 + denial 1행(`#195` 경계), 무토큰 401. 없는 project와 안 보이는 project가 **같은 거부** | **실 PG** |
| T10 | index가 질의를 받는다 | "이 adapter의 최신" 질의가 §2-3 index를 쓰는지 확인. 1단계 §7이 `#174`를 반례로 든 지점 | **실 PG** |
| T11 | 요청이 suite를 돌리지 않는다 | route가 `run_conformance`를 import하거나 부르면 실패 — 1단계가 `conformance_status.py`에서 지킨 성질을 2단계에서도 지킨다 | PG-free |
| T12 | 생산자는 실제 CLI를 부르지 않는다 | fixture adapter 경로에서 `install`·`authenticate`가 호출되면 실패(호출 기록 stub) | PG-free |

T11·T12가 이 설계의 **핵심 부정 시험**이다. 나머지는 계약이지만 이 둘은 §3-2의 금지가 코드에서 유지되는지를 본다.

## 6. 경계 · 미해결

- **§2-1의 RLS 결론이 카드 지시와 다르다.** (c)를 권고하고 근거를 적었다. (a)를 택하려면 "복제된 측정의 불일치를 무엇이 막는가"에 먼저 답해야 한다. 이 판단은 Codex·조정자의 것이다.
- **보존 기간을 정하지 않았다**(§2-4). 삭제 주체가 정해지지 않았다.
- **hosted CI import(A)를 열지 않았다**(§3-1). 열려면 §3-4를 계약으로 받아야 한다.
- **`installed-cli` subject는 값만 정의하고 생산자가 없다** — G-25가 풀릴 때까지.
- **`compare_reports()`(AC-10 "계약 동일")는 여전히 노출하지 않는다.** 1단계 §10이 "두 adapter의 실행 기록이 있어야 성립한다"고 했고, 2단계가 기록을 만들지만 비교의 의미(어느 시점의 두 기록을 비교하는가)는 별 카드다.
- **`NOT_OBSERVED_REASON` 문자열이 바뀐다**(§4-4). `#208` fixture와 같은 PR에서 함께 바뀌어야 한다.
- **migration 번호 미배정**(§2-7). 구현 PR에서 조정자가 배정한다.
- 실행하지 않았다: 로컬 실 PG·Docker·전체 suite. 이 문서의 실측은 전부 `git grep -n -F`·`git show`·정독이고, base는 `a0e807b5`다.
