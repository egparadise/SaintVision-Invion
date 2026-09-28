---
doc_id: "CLAUDE-G03-CONFORMANCE-RECORD-DESIGN-001"
title: "G-03 2단계 설계 v1.1 — host-global record(Codex 승인)·생산 가능한 값만 계약에 넣기·report 내부 무결성 재계산·host 결속과 결정적 최신 선택·응답 shape 확정 (docs-only)"
version: "1.1.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T22:24:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "a0e807b5"
task_ids: ["S10-BE"]
tags: ["s10-be", "conformance", "adapter", "api", "persistence", "rls", "design", "claude"]
---

# G-03 2단계 설계 — conformance 실행 기록의 저장과 노출

1단계 설계는 [[G-03_conformance_결과_API_노출_설계]] v1.2이고 그 §3이 2단계를 "누가·언제 실행해 무엇이 나왔는지 기록하고 그 기록을 노출"로, §7이 "**설계 단계에서 멈추고 migration 번호를 먼저 요청**"으로 남겨 두었다. 이 문서가 그 설계다. 1단계 구현은 `#200`이고 이 문서의 base는 `#200`의 현재 head `a0e807b5`다 — 2단계가 인용하는 코드가 그 tree에만 있으므로, 인용을 실물로 확인할 수 있는 지점을 base로 골랐다.

**migration 번호는 이 카드에서 예약하지 않는다.** 구현 PR 시점에 조정자가 배정한다(1단계 §7은 "먼저 요청"이라고 적었는데, 조정자 지시가 배정 시점을 구현 PR로 옮겼다).

## 0. 결정 요약 (v1.1)

Codex 검토에서 **RLS 방향은 승인**됐고 **차단 결함 5건**이 왔다. v1.1이 그 다섯을 반영한 판이며, 무엇이 왜 바뀌었는지 먼저 적는다.

| | v1.0 | v1.1 |
|---|---|---|
| **RLS** | (c) `tenant_id` 없음·RLS 없음을 *권고* | **승인됨.** Codex가 조건으로 붙인 세 불변식을 §2-1에 계약으로 적었다 |
| **F1** 응답 shape | §4-1(단건 RECORDED)과 §4-3(목록 배열)이 **서로 모순** | **확정.** 목록은 `records[]`를 든 별 branch, 빈 기록은 1단계 7키 **그대로**, 단건은 item union. class·schema 파일명·`response_model`까지 §4-1에 못 박았다 |
| **F2** 생산 불가 값 | `installed-cli`·`hosted-ci-import`를 Literal·CHECK에 미리 넣음 | **좁혔다.** 이 단계 Literal·CHECK는 `fixture-adapter`·`in-server` **한 값씩**이고, `source_ref` column은 **넣지 않는다**. 넓히는 것은 생산자를 넣는 PR의 일이다 |
| **F3** T12 | "fixture 경로에서 `install`·`authenticate` 호출되면 실패" — **제품 경계를 잘못 잡았다** | **고쳤다.** suite는 그 두 메서드를 *반드시* 부른다(`conformance.py:206`·`:215`). 금지 대상은 **실 adapter 선택·subprocess·실 credential**이다 |
| **F4** report 무결성 | counts 합 하나 | **재계산·전수 고정.** 생산자는 실제 `ConformanceReport`에서 만들고, `checks`는 개수·이름·순서·중복·`passed && skipped`까지 고정하며, 깨진 저장 row는 **읽을 때 fail-closed** |
| **F5** host 결속 | 없음 | **`host_id`를 row·조회·index에 결속**하고 최신 선택에 tie-breaker를 둔다 |

나머지 v1.0 결정(§2-5 `detail` 제외, 요청이 suite를 돌리지 않음, import를 열지 않음, G-25 유보, migration 번호 미예약, append-only)은 승인됐고 그대로다.
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

카드의 지시는 "RLS(project/tenant 범위)"였고, v1.0은 위 근거로 (c)를 권고했다. **Codex가 (c)를 승인했다** — 1단계와 #200이 이미 `scope: "control-plane-host"`를 공개 계약으로 고정했고 project는 소유자가 아니라 읽기 경계이기 때문이다.

승인에는 **세 불변식이 조건으로 붙었고, 이 설계가 그것을 계약으로 받는다.**

1. **row에 tenant·project·user 값이나 자유 문자열을 두지 않는다.** §2-2의 column에 그런 것이 없고, `detail`을 버리는 §2-5가 자유 문자열 조건을 만족한다. `host_id`(§2-2)는 비식별 opaque 값이고 tenant와 무관하다.
2. **route는 매번 `require_project_access`를 거친다.** 1단계와 같고, 캐시·snapshot을 쓰지 않는다.
3. **직접 DB 표면은 host-global 안전 필드만 SELECT할 수 있다.** 이 table에는 그 조건을 깨는 column이 애초에 없다 — 그것이 1번과 같은 요구다.

즉 이 table이 RLS 밖에 있는 것은 "격리를 포기했다"가 아니라 **"격리할 tenant 소유물이 행 안에 없다"** 는 뜻이고, 세 불변식이 그 상태를 유지하는 장치다.

### 2-2. column (F2·F5 반영)

table 이름 `adapter_conformance_records`. `to_dict()`에서 파생한다.

| column | 형 | 왜 |
|---|---|---|
| `record_id` | `String` PK | `prefix_ULID`. `ids.py`의 `PREFIXES`에 새 kind가 필요하다(§2-6) |
| `host_id` | `String(64)` NOT NULL | **F5.** 이 기록을 만든 control-plane host의 **비식별 opaque 식별자**(§2-9). hostname·IP·경로를 담지 않는다 |
| `adapter` | `String(64)` NOT NULL | `TOOLS`의 이름. allowlist 밖 값은 저장 전에 거부한다 |
| `contract_version` | `String(32)` NOT NULL | report의 `contractVersion` — adapter가 **선언한** 값 |
| `suite_contract_version` | `String(32)` NOT NULL | suite 쪽 `CONTRACT_VERSION`. 둘이 다른 것 자체가 check 하나의 실패이므로 같은 행에 남긴다 |
| `subject` | `String(32)` NOT NULL | **무엇을 측정했는가.** 이 단계의 허용 값은 **`fixture-adapter` 하나**다 |
| `provenance` | `String(32)` NOT NULL | **어디서 왔는가.** 이 단계의 허용 값은 **`in-server` 하나**다 |
| `total`·`passed`·`failed`·`skipped` | `Integer` NOT NULL | report의 counts. **생산자가 재계산한다**(§2-8). `conformant`는 저장하지 않는다 |
| `checks` | `JSONB` NOT NULL | check별 `name`·`passed`·`skipped`만. `detail` 없음(§2-5). 개수·이름·순서까지 고정한다(§2-8) |
| `recorded_at` | `DateTime(timezone=True)` NOT NULL | 측정 시각 |
| `created_at`·`version` | 기존 table 관례와 동일 | |

**`source_ref` column은 이 단계에 넣지 않는다.** v1.0은 hosted import를 위해 nullable로 두었는데, 이 단계에 그 값을 만드는 생산자가 없으므로 **아무도 채울 수 없는 column**이 된다. import를 여는 PR이 생산자·검증·계약과 함께 추가한다.

`conformant`를 저장하지 않는 이유: `to_dict()`에서 그것은 `failed == 0 and passed > 0`의 **파생값**이다. 저장하면 counts와 어긋날 수 있는 두 번째 진실이 생긴다.

#### `CHECK` 제약 — 생산 가능한 것만 유효하다 (F2)

| 제약 | 내용 |
|---|---|
| 닫힌 값 | `subject = 'fixture-adapter'`, `provenance = 'in-server'` — **이 단계에 실제로 생산되는 값 하나씩** |
| counts | 네 값 모두 `>= 0`, 그리고 `passed + failed + skipped = total` |
| checks 개수 | `jsonb_array_length(checks) = total` — §2-8의 개수 조건을 **DB에서도** 고정 |
| host | `host_id <> ''` |

v1.0은 `installed-cli`·`hosted-ci-import`를 미리 열거했다. 그것은 **1단계가 "코드가 만들 수 없는 `RECORDED`를 schema가 광고하지 않는다"고 좁힌 원칙을 그대로 위반**한다 — 잘못 넣은 row가 reader에서 정상 RECORDED로 나가고, 공개 계약이 존재하지 않는 생산 경로를 약속한다. 그래서 두 값을 **뺐다.** G-25가 풀리는 PR과 import를 여는 PR이 각각 producer·검증·계약·CHECK를 **같은 commit에서** 넓힌다. 그때 필요한 조건도 미리 적어 둔다 — `in-server ⇒ source_ref IS NULL`, `hosted-ci-import ⇒ source_ref IS NOT NULL`, 그리고 subject×provenance 조합 allowlist를 **DB와 모델 양쪽에** 둔다.
### 2-3. index (F5 반영)

읽기 질의는 하나다 — **"이 host에서 이 adapter의 최신 기록"**. v1.0은 `(adapter, recorded_at DESC)`였는데 두 가지가 빠져 있었다.

- **host 결속**: 같은 DB를 둘 이상의 control-plane host·process가 공유하면 `(adapter, recorded_at)`만으로는 **다른 host의 기록을 현재 host의 사실로** 답한다. 응답이 `scope: "control-plane-host"`라서 그 혼합이 **보이지도 않는다.**
- **동률의 결정성**: 같은 밀리초에 두 기록이 들어오면 "최신"이 질의마다 달라질 수 있다.

그래서 index와 질의를 **`(host_id, adapter, recorded_at DESC, record_id DESC)`** 로 고정한다. `record_id`는 ULID이므로 tie-breaker로서 단조적이고, 질의와 index가 **같은 순서**를 쓴다(한쪽만 바꾸면 조용히 seq scan이 되거나 순서가 갈린다).

1단계 §7이 `#174`를 반례로 들었다("route만으로 끝나지 않고 index가 필요했다"). 그래서 이 index는 구현 PR의 migration에 **함께** 들어간다.
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

### 2-8. 저장된 report의 내부 무결성 (F4)

counts 합만 고정하면 **합이 맞는 거짓 row**가 통과한다 — `checks: []`인데 `total: 15`, 중복된 check 이름, `CHECKLIST` 밖 이름, 뒤섞인 순서, `passed: true`이면서 `skipped: true`. 그런 row는 RECORDED로 나가면서 **무엇을 측정했는지 증명하지 못한다.** 그래서 다음을 전부 고정한다.

| 불변식 | 어디서 |
|---|---|
| 생산자는 **caller가 준 dict가 아니라 실제 `ConformanceReport`에서** row를 만든다 | 생산자 |
| counts는 report의 `checks`에서 **재계산**한다(`to_dict()`의 property를 신뢰하되 값은 다시 센다) | 생산자 |
| `failed`는 독립 입력이 아니라 **`not passed and not skipped`에서 유도**한다 | 생산자 · 모델 |
| 한 check에 `passed`와 `skipped`가 **동시에 true일 수 없다** | 생산자 · 모델 · 읽기 |
| `checks`의 키는 정확히 `name`·`passed`·`skipped` | 모델 · 읽기 |
| `len(checks) == total` | 모델 · 읽기 · **DB CHECK**(§2-2) |
| `checks`의 **이름과 순서가 `CHECKLIST`와 정확히 같고 중복이 없다** | 생산자 · 읽기 |
| 위 중 하나라도 깨진 저장 row는 **RECORDED로 내보내지 않는다** — 정본 5xx로 fail-closed | 읽기 |

마지막 줄이 핵심이다. 깨진 row를 조용히 고쳐서 내보내거나 일부만 내보내면 **API가 DB보다 더 그럴듯해진다.** 읽기가 거부하면 그 행이 잘못됐다는 사실이 드러난다. 되돌리면 실패하는 시험은 §5의 T13·T14다.

`CHECKLIST`가 자라면 과거 row의 이름 집합은 그때의 목록이다. 그래서 읽기 쪽 비교 대상은 **row의 `suite_contract_version`에 해당하는 목록**이어야 하고, 이 단계에는 버전이 하나뿐이므로 현재 `CHECKLIST`와 비교한다 — **suite 계약이 올라가는 PR이 이 비교 규칙을 함께 정해야 한다**는 것을 §6에 미해결로 남긴다.

### 2-9. `host_id` — 무엇이고 무엇이 아닌가 (F5)

- **비식별**이다. hostname·IP·경로·사용자명을 담지 않는다. 배포가 한 번 정하는 **opaque 값**(예: 설정으로 주는 UUID)이고, 그 값 자체로는 host를 지목할 수 없다.
- **설정에서 온다.** 프로세스가 스스로 추론하지 않는다(추론하면 컨테이너 재시작마다 값이 바뀌어 "최신"이 끊긴다).
- **없으면 조용히 넘어가지 않는다.** 생산자는 값이 없으면 **시작하지 않고**(fail-fast), 읽기는 값이 없으면 **다른 host의 기록으로 답하지 않고** 정본 5xx로 거부한다. `NOT_OBSERVED`로 답하는 선택은 하지 않았다 — 그것은 "측정이 없다"는 뜻이고, 실제 상태는 "이 기록이 누구 것인지 말할 수 없다"이기 때문이다.

이렇게 두면 "DB당 control-plane host가 정확히 하나"라는 **배포 불변식에 의존하지 않는다.** Codex가 제시한 두 선택 중 결속 쪽을 골랐다 — 강제할 수 없는 배포 전제보다 행에 적힌 값이 낫다.

## 3. 생산자 — credential 없이 도는 것만

### 3-1. 두 후보

| 후보 | 무엇 | 대가 |
|---|---|---|
| **(A) hosted CI import** | hosted CI가 fixture/synthetic adapter에 대해 suite를 돌려 report를 artifact로 내고, 서버가 그것을 import해 한 행으로 만든다 | 서버는 **출처를 인증할 수 없다**(§3-4). 대신 실행 환경이 재현 가능하고 host에 부작용이 없다 |
| **(B) 서버 내 실행** | 서버가 fixture adapter에 대해 `run_conformance()`를 직접 부른다 | 출처 문제가 없다(서버가 자기 실행을 기록한다). 대신 **무엇을 측정한 것인지가 더 좁다** — fixture adapter는 host에 설치된 CLI가 아니다 |

`source_ref` column을 이 단계에 두지 않는 이유도 여기 있다(§2-2) — (A)를 열지 않으므로 그 값을 만드는 것이 없다.

**권고: (B)를 먼저, (A)는 나중.** 이유는 신뢰 경계다. (B)는 서버가 자기가 부른 함수의 결과를 적으므로 위조할 제3자가 없다. (A)는 `#177` N6이 실측으로 보여 준 대로, import 입력을 위조하면 통과한다. 두 경로를 동시에 열 이유가 없고, (B)만으로도 1단계의 `NOT_OBSERVED`를 벗어나기에 충분하다.

(B)를 고르면 실행 주체는 **요청이 아니다** — 1단계 §3이 금지한 것이 그것이다. 운영 명령(CLI entry point)이나 예약 작업이 부르고, 읽기 route는 기록만 읽는다. 어느 쪽이든 **요청 처리 중에는 suite를 돌리지 않는다**.

### 3-2. 무엇을 금지하는가 — v1.0이 경계를 잘못 잡았다 (F3)

v1.0은 이 절을 "실제 CLI `install`·`authenticate`를 부르지 않는다"로 쓰고, §5의 T12를 **"fixture 경로에서 `install`·`authenticate`가 호출되면 실패"** 로 적었다. **그것은 틀렸고, 정상 생산자를 막는다.**

실측: `run_conformance()`의 checklist는 **바로 그 메서드 계약을 호출해서 검사한다.**

| 확인한 것 | 출처 |
|---|---|
| `_install()`이 `adapter.install()`을 부른다 | `src/saintvision/adapters/conformance.py:206` |
| `_authenticate()`가 `adapter.authenticate(credential_ref)`를 부른다 | 같은 파일 `:215` |

즉 fixture adapter에 suite를 돌리면 fixture의 `install`·`authenticate` **stub은 반드시 호출된다.** 호출 자체를 금지하면 생산자가 실패하거나 suite 일부를 건너뛰어야 하고, 건너뛴 suite는 conformance가 아니다.

**그래서 금지 대상을 다시 정한다.** 금지되는 것은 *메서드 호출*이 아니라 **무엇을 상대로 무엇을 하는지**다.

| 금지 | 이유 |
|---|---|
| **실 adapter 선택** — `CliAdapter` 인스턴스나 `agents.BY_NAME`에서 고른 도구를 suite에 넘기는 것 | 그 순간 host의 CLI가 측정 대상이 되고, 아래 네 가지가 전부 따라온다 |
| **subprocess·실 CLI 실행** | host를 바꾸고(`install`), 시간 상한이 없고, 네트워크를 탄다 |
| **실 credential 사용** — `credential_ref`가 `conformance://dummy` 아닌 실제 자격 | 이 플랫폼이 보관하는 것이 아니다. 실 credential conformance는 **G-25 BLOCKED_EXTERNAL**이다 |
| **요청 처리 중 실행** | 1단계 §3이 금지했다. 읽기 route가 부작용을 만들고 한 호출자가 남의 측정을 촉발한다 |

그리고 **fixture stub이 무해하다는 것을 단언한다** — stub의 `install`·`authenticate`는 호출되지만 host를 바꾸지 않고(파일·패키지·환경 변수 변경 0) 외부 credential에 접근하지 않는다. 이것이 T12가 실제로 고정해야 하는 것이다.

v1.0이 적은 네 가지 금지 *이유*(credential은 G-25, `install`은 host를 바꿔 측정을 무효화, 시간 상한 없음, 한 사람이 공유 사실을 덮어씀)는 그대로 유효하다. 틀린 것은 그 이유에서 **시험 가능한 경계를 도출한 방식**이었다.

따라서 이 단계가 기록하는 것은 **fixture adapter에 대한 suite 실행**이고, `subject = "fixture-adapter"`가 행에 그것을 적는다. `installed-cli`는 **값으로도 열거하지 않는다**(§2-2, F2) — G-25가 풀리는 PR이 producer·계약·CHECK를 함께 넓힌다.
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

### 4-1. 응답 shape — exact key set까지 확정한다 (F1)

v1.0은 §4-1에서 **단건 RECORDED**(단일 `adapter`, 단일 `recordedAt`, counts)를 정의하고 §4-3에서 목록이 **배열 + 기록 없는 adapter의 NOT_OBSERVED**를 낸다고 적었다. 그 둘은 **같은 union이 아니다** — 1단계의 aggregate object, 단건 item, 섞인 배열이 서로 다른 envelope이고, 구현자가 고르는 것에 따라 schema와 FE가 갈린다. Codex 지적이 맞다. 확정한다.

**핵심 결정: 기록이 없는 adapter를 배열에 넣지 않는다.** `adapters[]`가 **대상 목록**이고 `records[]`가 **존재하는 측정**이므로, **배열에서의 부재가 곧 측정의 부재**다. 이렇게 하면 "섞인 배열"이 사라지고 per-adapter `NOT_OBSERVED` entry라는 개념도 필요 없다.

#### 목록 route

```
GET /v1/projects/{project_id}/adapters/conformance
response_model = Annotated[
    Union[ConformanceStatusResponse, ConformanceStatusRecordedResponse],
    Field(discriminator="status"),
]
```

| branch | 언제 | exact key set |
|---|---|---|
| **`ConformanceStatusResponse`** (기존 이름·기존 class 그대로) | `records`가 **비었을 때만** | `status`(`"NOT_OBSERVED"`) · `reason` · `scope` · `contractVersion` · `adapters` · `checks` · `recordedAt`(항상 `null`) — **1단계 7키에서 하나도 더하지 않고 빼지 않는다** |
| **`ConformanceStatusRecordedResponse`** (신규) | 기록이 하나 이상 | `status`(`"RECORDED"`) · `scope` · `contractVersion` · `adapters` · `checks` · `records` · `recordedAt` — **`reason`이 없다**(이유를 말할 부재가 없다) |

- `checks`는 두 branch 모두 **descriptor**(`name`·`capabilityGated`)다. 1단계와 같은 뜻·같은 형이다.
- `records[i]`의 결과별 목록은 이름이 **`outcomes`** 다 — `checks`(descriptor)와 **같은 키 이름을 쓰지 않는다.** 같은 이름에 다른 shape를 두면 소비자가 둘을 섞는다.
- 목록의 `recordedAt`은 **`records` 중 가장 최신 값**이고, 그 뜻을 "이 응답의 신선도"로 문서에 못 박는다. item의 시각은 각 `records[i].recordedAt`이다. **둘을 같은 키로 쓰지 않는다.**
- `records`는 **`adapters` 순서**를 따른다(질의 순서가 아니라 대상 목록 순서) — 응답 순서가 DB 계획에 따라 흔들리지 않게.

#### `records[i]` — `ConformanceRecordItem` (nested, 계약 파일 아님)

`adapter` · `subject` · `provenance` · `contractVersion` · `suiteContractVersion` · `total` · `passed` · `failed` · `skipped` · `outcomes` · `recordedAt`

`outcomes[j]` = `ConformanceCheckOutcome`: `name` · `passed` · `skipped`. (`detail` 없음 — §2-5.)

이 두 nested class는 이름이 `Request`/`Response`로 끝나지 않으므로 `exported()`가 별 계약 파일로 만들지 않고 **담는 계약 안에 inline으로** 나타난다 — 1단계 `ConformanceCheckDescriptor`와 같은 취급이다.

#### 단건 route

```
GET /v1/projects/{project_id}/adapters/{name}/conformance
response_model = Annotated[
    Union[AdapterConformanceNotObservedResponse, AdapterConformanceRecordedResponse],
    Field(discriminator="status"),
]
```

| branch | exact key set |
|---|---|
| `AdapterConformanceNotObservedResponse` | `status`(`"NOT_OBSERVED"`) · `reason` · `scope` · `adapter` · `contractVersion` · `checks` · `recordedAt`(`null`) |
| `AdapterConformanceRecordedResponse` | `status`(`"RECORDED"`) · `scope` · `adapter` · `subject` · `provenance` · `contractVersion` · `suiteContractVersion` · `total` · `passed` · `failed` · `skipped` · `outcomes` · `recordedAt` |

단건은 **item union을 재사용하지 않고 자기 class를 갖는다.** 이유는 wire 안정성이다 — 목록 item은 `records[]` 안에서만 뜻이 있고, 단건 응답을 그것과 같은 class로 묶으면 한쪽 요구가 다른 쪽 계약을 끌고 다닌다. 대신 **필드 이름·형은 item과 정확히 같게** 두어 소비자가 매핑을 새로 배우지 않게 한다.

#### 생성될 계약 파일

| class | 계약 파일 |
|---|---|
| `ConformanceStatusResponse` | `contracts/conformance-status-response.schema.json` — **이미 있고, 내용이 바뀌지 않는다** |
| `ConformanceStatusRecordedResponse` | `contracts/conformance-status-recorded-response.schema.json` (신규) |
| `AdapterConformanceNotObservedResponse` | `contracts/adapter-conformance-not-observed-response.schema.json` (신규) |
| `AdapterConformanceRecordedResponse` | `contracts/adapter-conformance-recorded-response.schema.json` (신규) |

**기존 이름을 그대로 두는 것이 §4-2의 고아 함정을 피하는 방법이다** — union 별칭은 `Strict` 서브클래스가 아니어서 `exported()`가 수집하지 않고, 기존 이름을 union alias로 바꿔 버리면 기존 계약 파일이 낡은 채 남는데 `--check`는 PASS한다.

#### 왜 `conformant` boolean이 없는가

1단계가 그것을 뺀 이유("boolean에는 제3의 값이 없다")는 기록이 생겨도 사라지지 않는다 — `skipped`가 있는 세계에서 하나의 boolean은 "무엇을 통과했는가"를 말하지 못한다. 필요하면 소비자가 counts로 계산하고, 계산식이 화면마다 다르면 그것이 드러나는 편이 낫다.

counts 사이의 관계와 `outcomes`의 무결성은 **응답 모델에서도** 검증한다(§2-8) — DB `CHECK`가 있어도 응답 조립에서 깨질 수 있고, 깨진 합은 "측정처럼 보이는 숫자"다.
### 4-2. 계약 gate 함정 — 실측했다

union으로 가는 방식에 따라 **gate가 통과하면서 계약 파일이 낡는다.** 두 사실을 확인했다.

1. `tools/export_schemas.py:40` `def exported()`는 **`Strict` 서브클래스이고 이름이 `Request`/`Response`로 끝나는 것**만 모은다. `Annotated[Union[...], Field(discriminator=...)]` 별칭은 `Strict` 서브클래스가 **아니므로** 수집되지 않는다.
2. `main()`은 `EXPORTED`를 순회해 비교만 한다(`tools/export_schemas.py:82`). **디스크에 남은 고아 schema 파일을 검출하지 않는다.** 그러므로 `ConformanceStatusResponse`가 수집 대상에서 빠지면 `contracts/conformance-status-response.schema.json`이 **낡은 채 남고 `--check`는 PASS**다.

`tools/check_contract_bindings.py`의 dead-contract 검사는 **report-only**이고, 그 docstring이 *"saintvision responses are anchored by FastAPI response_model … and are out of this kernel-anchor check"* 라고 적는다. 즉 이것도 막지 않는다.

**그래서 이렇게 한다.**

- 두 branch를 **각각 `Strict` 서브클래스**로 만들고 이름을 `...Response`로 끝낸다 → 둘 다 계약 파일로 생성된다.
- **기존 이름 `ConformanceStatusResponse`를 없애지 않는다.** 없애면 §4-2의 고아가 생긴다. 남기는 방법은 구현에서 둘 중 하나로 정한다 — (i) 기존 이름을 `NOT_OBSERVED` branch의 이름으로 유지, (ii) 기존 이름을 union envelope의 `Strict` 표현으로 유지. (i)이 단순하고 1단계 계약 파일이 그대로 뜻을 유지한다.
- **`exported()`의 결과 집합을 고정하는 시험**을 둔다(§5의 T7). 계약 파일이 조용히 사라지거나 고아가 되는 것을 gate 대신 시험이 잡는다.

### 4-3. 두 route의 오류 경계와 `RES-0004`

1단계는 adapter별 route를 두지 않았고 그래서 `RES-0004`도 없었다. 2단계에는 기록이 있으므로 단건이 뜻을 갖는다. shape는 §4-1에 확정했고, 여기서는 **무엇이 어떤 오류인가**만 정한다.

| 입력 | 응답 |
|---|---|
| `name`이 `BY_NAME`(`agents.py:101`) **밖** | **`RES-0004` 404.** `#205`가 `/v1/adapters/{name}`의 unknown adapter를 같은 code로 정본화했으므로 어휘가 같다 |
| `name`은 allowlist 안, **기록 없음** | **`AdapterConformanceNotObservedResponse` 200.** 404가 아니다 — "그런 adapter는 없다"와 "그 adapter의 측정이 없다"는 다른 사실이고, 합치면 두 번째가 첫 번째처럼 읽힌다 |
| 비회원·없는 project | 1단계와 같은 **`AUTH-0030` 403**, 존재 비노출 동형 |
| 무토큰 | `AUTH-MISSING-CREDENTIAL` 401 (`#195` 경계) |
| 저장 row가 §2-8을 위반 | **정본 5xx, fail-closed.** RECORDED로 내보내지 않는다 |
| `host_id` 설정 없음 | **정본 5xx** (§2-9). 다른 host의 기록으로 답하지 않고, `NOT_OBSERVED`로 위장하지도 않는다 |

권한은 두 route 모두 1단계와 같다 — `require_project_access()`, 등급(`canApprove`) 요구 없음. 읽기다.
### 4-4. 1단계 `NOT_OBSERVED`와의 호환

**바꾸지 않는 것을 명시한다.** 기록이 없을 때 목록 route의 응답은 1단계와 **필드 집합·값이 동일**하다 — `status`·`reason`·`scope`·`contractVersion`·`adapters`·`checks`·`recordedAt: null`. `#208`이 고정한 FE fixture(`reason` 문자열 byte 일치까지)가 **깨지지 않는다.**

- `recordedAt`은 1단계에서 `None` **required**였다. union에서 `NOT_OBSERVED` branch는 그 형을 유지한다 — `None`만 허용한다.
- `reason` 문자열(`conformance_status.py:65` `NOT_OBSERVED_REASON`)은 "아직 저장하지 않는다"고 말한다. 2단계가 저장하기 시작하면 **이 문장은 사실이 아니게 된다.** 그래서 2단계 구현은 이 문자열을 "이 adapter에 대한 기록이 없다"로 **갱신**해야 하고, `#208`의 fixture도 같은 PR에서 함께 바뀐다. **이것이 2단계의 유일한 FE 파괴 지점**이므로 여기 적어 둔다.
- `status` 리터럴이 넓어진다. 1단계가 `Literal["NOT_OBSERVED"]` 하나로 둔 이유는 *"코드가 만들 수 없는 `RECORDED`를 스키마가 광고하지 않는다"* 였다. 2단계는 생산자를 함께 넣으므로 그 조건이 충족된다 — **branch와 생산자가 같은 PR에 들어가야 한다**는 뜻이다.

## 5. 되돌리면 실패하는 시험 계획 (v1.1)

| # | 무엇을 고정하는가 | 되돌릴 때 실패하는 방식 | 종류 |
|---|---|---|---|
| T1 | `detail`이 저장·노출되지 않는다 | `checks`/`outcomes`에 `detail` 키를 넣으면 실패. 응답 모델이 받으면 `extra="forbid"`로 실패 | PG-free |
| T2 | counts 합 | `passed+failed+skipped != total` 응답을 만들면 실패. DB `CHECK`는 실 PG로 별도 | PG-free + 실 PG |
| T3 | `subject`·`provenance`가 required이고 **이 단계에 생산 가능한 값만** | 값을 빼거나 `installed-cli`·`hosted-ci-import`를 쓰면 실패(모델·DB 양쪽) | PG-free + 실 PG |
| T4 | RECORDED는 `recordedAt` non-null | `recordedAt: null`인 RECORDED를 만들면 실패 | PG-free |
| T5 | **기록 0개일 때 1단계와 exact key set이 같다** | 목록 응답의 키 집합·값을 **기존 계약 파일 `conformance-status-response.schema.json`과 대조**한다. 한 키라도 더하거나 빼면 실패 | PG-free |
| T6 | unknown adapter `RES-0004` / known-but-unrecorded 200 `NOT_OBSERVED` | 둘을 404로 합치면 실패 | PG-free |
| T7 | `exported()` 결과 집합과 계약 파일 목록 | 계약 파일이 사라지거나 고아가 되면 실패 — §4-2의 gate 공백을 메운다 | PG-free |
| T8 | append-only | app role로 UPDATE·DELETE를 시도하면 거부된다 | **실 PG** |
| T9 | 읽기 경계 | 비회원 403 + denial 1행(`#195`), 무토큰 401, 없는 project와 안 보이는 project가 **같은 거부** | **실 PG** |
| T10 | **최신 선택이 host별이고 결정적이다** | 다른 `host_id`의 더 최신 행을 넣어도 현재 host의 답이 바뀌지 않는다. 같은 `recorded_at` 두 행에서 `record_id` tie-breaker로 **항상 같은 행**이 나온다. index를 지우거나 tie-breaker를 빼면 실패 | **실 PG** |
| T11 | 요청이 suite를 돌리지 않는다 | route 모듈이 `run_conformance`를 import하거나 부르면 실패 | PG-free |
| **T12** | **실 adapter·subprocess·실 credential을 쓰지 않는다** (v1.0에서 고침) | 생산자가 `CliAdapter`/`agents.BY_NAME`에서 adapter를 고르면 실패. subprocess 생성이 관측되면 실패. `credential_ref`가 `conformance://dummy`가 아니면 실패. **fixture의 `install`·`authenticate`는 호출되어야 하고**, 그 stub이 host를 바꾸지 않고(파일·환경 변수 변경 0) 외부 credential을 읽지 않음을 단언한다 | PG-free |
| **T13** | **깨진 저장 row는 RECORDED로 나가지 않는다** | `checks: []`+`total: 15`, 중복 이름, `CHECKLIST` 밖 이름, 뒤섞인 순서, `passed && skipped` 각각을 저장하고 읽으면 **정본 5xx**여야 한다. 하나라도 200 RECORDED로 나가면 실패 | **실 PG** |
| **T14** | **생산자가 report에서 재계산한다** | caller가 준 counts를 그대로 쓰면 실패 — 일부러 틀린 counts를 넘겨도 저장된 행은 report에서 센 값이어야 한다. `failed`를 독립 입력으로 받으면 실패 | PG-free |
| **T15** | **`host_id` 부재가 조용히 지나가지 않는다** | 설정이 없을 때 생산자는 시작하지 않고, 읽기는 정본 5xx다. `NOT_OBSERVED`나 다른 host의 기록으로 답하면 실패 | PG-free + 실 PG |

**T11·T12·T13·T14**가 이 설계의 핵심 부정 시험이다 — 차례로 "읽기가 측정하지 않는다", "측정 대상이 fixture다", "DB가 API보다 정직하다", "숫자를 호출자가 정하지 않는다"를 고정한다.
## 6. 경계 · 미해결 (v1.1)

- **RLS는 확정됐다** — §2-1(c), Codex 승인, 세 불변식을 계약으로 받았다. v1.0의 "판단 대기"는 닫혔다.
- **`CHECKLIST`가 자랄 때의 비교 규칙**(§2-8 마지막 단락). 과거 row의 이름 집합은 그때의 목록이므로, 읽기는 row의 `suite_contract_version`에 맞는 목록과 비교해야 한다. 이 단계는 버전이 하나라 현재 목록과 비교하고, **suite 계약을 올리는 PR이 규칙을 함께 정해야 한다.**
- **보존 기간을 정하지 않았다**(§2-4). 삭제 주체가 정해지지 않았다.
- **hosted CI import(A)를 열지 않았다**(§3-1). 열려면 §3-4를 계약으로 받고 `source_ref` column·CHECK·조합 allowlist를 같은 PR에서 넓혀야 한다.
- **`installed-cli`는 값으로도 열거하지 않는다**(F2). G-25가 풀리는 PR이 producer·계약·CHECK를 함께 넓힌다.
- **`compare_reports()`(AC-10 "계약 동일")는 여전히 노출하지 않는다.** 두 adapter 기록의 비교 의미(어느 시점의 두 기록인가)는 별 카드다.
- **`NOT_OBSERVED_REASON` 문자열이 바뀐다**(§4-4). `#208` fixture와 같은 PR에서 함께 바뀐다 — 조정자가 Gemini와 같은 PR 묶음으로 조정한다고 확인했다.
- **migration 번호 미배정**(§2-7). 구현 PR에서 조정자가 배정한다. 이 단계의 migration은 table + §2-2 CHECK 4종 + §2-3 index + append-only 권한이고 **RLS policy는 만들지 않는다.**
- 실행하지 않았다: 로컬 실 PG·Docker·전체 suite. 이 문서의 실측은 전부 `git grep -n -F`·`git show`·정독이고, base는 `a0e807b5`다. v1.1에서 새로 실측한 것은 **F3의 근거**(`conformance.py:206`·`:215`가 `install`·`authenticate`를 실제로 호출한다)와 §4-2의 gate 공백 두 사실이다.
