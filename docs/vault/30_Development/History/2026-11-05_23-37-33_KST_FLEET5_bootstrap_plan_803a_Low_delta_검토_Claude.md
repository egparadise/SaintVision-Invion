---
doc_id: "HISTORY-FLEET5-20261105-BOOTSTRAP-PLAN-803A-LOW-DELTA-REVIEW-CLAUDE"
title: "2026-11-05 FLEET5 bootstrap plan 803ad270 Low 조건 C1~C3 delta 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T23:37:33+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "a471ce19"
task_ids: ["FLEET5-SETUP-INTEGRATION-20261105"]
tags: ["fleet5", "independent-review", "bootstrap", "plan", "claude"]
---

# bootstrap plan 803a Low delta 검토

Orca task `task_667a078e2dc3`, dispatch `ctx_9fd4c380b503`. [[2026-11-05_23-03-41_KST_FLEET5_legacy_bootstrap_plan_9e8e_검토_Claude]]에서 붙인 Low 조건 C1~C3을 닫는 delta `9e8e8c2f..803ad270`만 판정한다.

- 앞선 `9e8` plan ACCEPT(`a471ce19`)는 그대로다. 다시 돌리거나 이름을 바꾸지 않는다.
- code, contract, runtime CI, 운영 수락이 아니다.
- **관측 시각:** 23:34:48~23:37:33 KST. 첫 fetch 호출과, 작성 전 마지막 delta 확인의 shell `date` 출력이다.

## 대상과 방식

- **대상:** `agent/codex/fleet5-consecutive-leaf-rotation-20261105`의 `803ad270562b1b75e44d26f9e14b965c714ab519`
  - 18개 문서, +1595/−139. non-docs는 0개. plan History는 v1.0.3
  - 새 파일: `803ad270:docs/vault/30_Development/Evidence/fleet5-legacy-capability-bootstrap-plan-20261105/m2-v2-body-golden-fixtures.json`과 `m2-v2-body-golden-validation.json`
- **읽은 방식:** Git object만 읽었다. 작성자 checkout은 건드리지 않았다.
- **실행:** 내 script만 썼다(main `.venv` 3.14.7 `-B -I`). owner harness는 쓰지 않았다.
- plan Docs 42045613505은 root가 확인했다고 알려 왔다. 나는 다시 확인하지 않았다.

## 독립 확인

| 항목 | 결과 |
|---|---|
| artifact hash | **22/22** 다시 계산했고 같다 |
| owner schema case | **31/31** |
| 내 변형 | bool 뒤집기 44개, null 채우기 53개를 **모두 거부**한다. 새 barrier 5개(`secondBinaryMigrationAllowed`, `legacySchedulerReRegistrationAllowed`, `globalOuterSignatureNormalizationAllowed`, `blanketAsciiIdentifierRestrictionAllowed`, `bodyTransportNewlineIncludedInSignature`)도 true로 바꾸면 모두 거부한다 |
| binding | target 30개, root 18개, member 이름 60개. member envelope 2개는 null |
| acceptance | 40개. A01~A36은 내용이 그대로다. A37(C1), A38(C3), A39와 A40(C2)이 더해졌다. **FUTURE, NOT RUN** |
| schema | required에서 빠진 것이 없고, `additionalProperties`는 여전히 false다 |
| 바뀌지 않은 파일 | observer·image, inspect, runtime inventory, root G2, source case, parameter 계약 |
| 실제 Go와 native 실행 | 0회 |

### M2 v2 body golden

내 Python으로 Go `encoding/json`의 `Marshal(map[string]any)`을 따로 흉내 냈다.

- key는 UTF-8 byte 순서로 정렬하고 compact로 쓴다.
- `"`, `\`, `\n`, `\r`, `\t`, `\b`, `\f`는 짧게 escape한다. 나머지 control 문자는 소문자 `\u00XX`로 쓴다.
- `<>&`는 `<`, `>`, `&`으로, U+2028과 U+2029도 escape한다.
- 비 ASCII는 raw UTF-8로 두고 정규화하지 않는다.

결과:

- **B01~B05 (양성):** 5/5. body bytes, SHA256, v2 domain prefix, domain+body bytes와 SHA256, 입력 문서 parse와 SHA256을 모두 재현했다. body에는 newline이 없고, transport newline은 서명에 들어가지 않는다.
- **B06~B10 (음성):** 5/5. 입력 SHA256이 같다. 내 엄격한 분류기가 같은 이유에 이른다: invalid-utf8, unpaired-high-surrogate, unpaired-low-surrogate, overlong-utf8, raw-unescaped-json-nul. canonical 출력은 모두 null이고, harness 판정 bytes와 SHA256을 재현했다.

### E04~E07

- 이제 정확한 입력 hex와 SHA256이 공개됐다(4/4).
- 내 분류기가 같은 이유에 이른다: missing-terminal-nul, invalid-utf8, embedded-argv-nul, unpaired-surrogate.
- canonical 출력이 없는 이유: 거부된 입력에는 표준형이 없다.
- harness 판정 `{reason,result}` bytes와 SHA256을 재현했다. 이 판정은 서명 대상이 아니라고 표시돼 있다.
- golden body digest와 argv JSON·raw cmdline digest는 겹치지 않는다.

## C1~C3 처리

- **C1 — plan 수준에서 해결.**
  - fence 필수 entrypoint 목록에 `Register-LeafRenewalTask.ps1`, `Invoke-ScheduledLeafRenewal.ps1`, `tools/scheduled_leaf_renewal.py`가 DENIED로 들어갔다.
  - 끝난 상태를 포함한 모든 표지 단계에서 등록, 재등록, 호출, 실행을 막는다.
  - 비활성화된 ID 3개 밖에 새로 등록된 task도 허가되지 않은 실행 경로이고 G9 HOLD다.
  - closure(`b5b8ca68`) 항목이 DENIED이고, G9 목록에 명시됐고, barrier가 false이고, A37이 있다.
- **C2 — plan 수준에서 해결.** 원하는 contract이며 Go로 돌려 보지는 않았다.
  - root가 고른 v2 BODY는 `nodeSignature`를 뺀 닫힌 typed body의 Go `json.Marshal(map)` 결과다.
  - 엄격한 UTF-8과 Unicode를 요구하고, 대체 문자로 바꾸는 정규화는 허용하지 않는다.
  - HTML 문자와 U+2028/U+2029를 escape한다.
  - body에는 newline이 없다. transport newline은 서명 밖이다.
  - 전용 Python v2 verifier는 같은 bytes를 내야 하며 `ensure_ascii`를 쓰지 않는다. 일괄 ASCII 제한도 없다.
  - v1 기록과 바깥 receipt·CP commit 표준형은 그대로 둔다.
  - golden을 내가 따로 재현했다. A39와 A40이 있다.
- **C3 — plan 수준에서 해결.**
  - journal이나 seal이 있는 Node에서 두 번째 migration(새 migration ID나 target)은 따로 검토한 설계가 나올 때까지 DENY다.
  - predecessor를 지우거나, 바꾸거나, 회전하거나, 덧붙이지 않는다. 표지도 초기화하지 않는다.
  - 첫 plan의 정확한 resume과 승인된 normal:3 renewal은 두 번째 migration과 다르다.
  - barrier가 false이고 A38이 있다.
- **이어받은 규칙:** R1, R2, R4, N1, N2는 `803`에서 더해지기만 했다. 빠진 제약도, 느슨해진 schema required도 없다. 알려진·알 수 없는 consumer, label만 있는 consumer, 세 번째 consumer, 두 번째 migration을 막는 장치는 그대로다.

## 참고

- B03은 `\b`와 `\f`의 짧은 escape를 기대한다. Go `encoding/json`은 Go 1.22부터 이렇게 낸다.
  - repository `go.mod`는 go 1.23이고, Core CI는 `setup-go` 1.27.1이며, `Dockerfile.node.remote`는 golang을 digest로 고정한다.
  - 앞으로의 Go golden 실행(A39)은 정확한 toolchain을 기록해야 한다.
- Go `Marshal`은 잘못된 UTF-8을 실패시키지 않고 U+FFFD로 바꾼다. 그래서 producer가 marshal 전에 검증해야 한다. plan이 이를 요구하고, A39가 증명해야 한다.
- P0 호환 `msg_03604b3e6bed`와 C2 전달 `msg_bb65618c0b49`는 root가 전달한 planning message다. 내가 검증하지 않았다.

## 판정

| 구분 | 판정 |
|---|---|
| **`803` Low delta** | **ACCEPT.** C1, C2, C3이 plan 수준에서 해결됐다. 새 발견은 없다 |
| plan 전체 | `9e8` plan ACCEPT(`a471ce19`)는 그대로다. `803` 뒤로 남은 Low 조건은 없다 |
| implementation | 없다. 수락하지 않는다 |
| contract | M2 v2 wire와 표준 body, migration journal, common fence, runtime inventory는 binding이 null인 제안이다. 수락하지 않는다 |
| P0 | `6c0fc4ad` NOT ACCEPTED. 고친 source·process P0는 아직 공개되지 않았다. code 검토는 따로 한다 |
| runtime CI | 없음. 실제 Go 실행 0회, future case 40개 NOT RUN |
| 운영 | HOLD. target 30개, root 18개, member binding이 모두 null이다 |
| physical | 없음 |

## 다음 첫 행동과 담당

- **root:** `803` Low delta ACCEPT를 반영한다. plan owner가 기다리는 `msg_b661a20575b9`는 root가 판단해 처리한다. HOLD를 유지한다.
- **Codex(plan owner):** root가 범위를 정한 뒤에만 다음 문서 단계로 간다.
- **`ctx_6f0f8253b8a7`:** v2 executable field와, toolchain을 기록한 Go/Python golden 실행을 담은 고친 P0를 낸다.
- **Claude:** 고친 P0 code가 오면 검토한다.
