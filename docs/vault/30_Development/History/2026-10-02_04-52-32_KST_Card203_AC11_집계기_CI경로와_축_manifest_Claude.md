---
doc_id: "HISTORY-CARD203-AC11-AGGREGATE-LANE-20261002"
title: "카드 203 — AC-11 집계기를 부르는 CI 경로와 축 manifest: 0/8은 축이 실패한 수가 아니라 아무도 부르지 않은 수였다 (카드 201 측정 포함)"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T04:54:23+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "aaa0b083"
task_ids: ["S11-BE"]
tags: ["ac11", "ci", "aggregator", "axis-manifest", "s11", "claude"]
---

# 카드 203 — 집계기를 부를 수 있게 만들었다

## 0. 카드 201의 측정 — 조건에 맞는 행이 없었다

카드 201은 "#292 표에서 75 미만이고 남은 일이 외부 전제가 아닌 Claude 소유 행"을 고르라고 했다. **그런 행이 없다.** 정본 48행 표(§3)를 파싱해 읽은 결과다 — 이전 카드 198의 조사는 §4-3-5·§4-4-3의 **과거 절**을 현재 값으로 읽은 것이었고, 그것이 틀렸다.

| 행 | 점수 | 남은 것 | 외부 |
|---|---:|---|---|
| `S03-ST` | 50 | 실 Node→CP 전송·볼륨 마운트 | **G-24** |
| `S12-DB` | 50 | 운영 PITR 적용·복원 인수 | **G-22** |
| `S12-ST` | 50 | 제공 폴더 실값·복구 훈련 운영 인수 | **G-20·G-22** |
| `S03-DB`·`S10-DB`·`S10-ST` | 75 | 운영 인수·운영 판정 기준 | **—**(그러나 100은 운영 인수를 요구한다) |
| `S02-BE`·`S02-DB`·`S02-ST`·`S09-DB`·`S09-ST`·`S10-BE` | 75 | live IdP·실 등록 흐름·브라우저 여정·eval 운영 판정·실 adapter | G-15·17·18·20·24·25·26 |

**정정 둘**: `S02-ST`와 `S09-ST`는 **50이 아니라 75**다(v1.7 §4-4-3이 두 행을 정정했다). 그리고 `S09-ST`의 scope인 **diff·테스트·trace artifact pin은 이미 구현돼 있다** — `src/saintvision/services/records.py`의 docstring이 스스로 `(S09-DB, S09-ST)`라고 적고 `ARTIFACT_ROLES`에 `diff`·`test_report`·`trace`가 있다.

eval↔artifact 연결을 새로 만드는 것도 검토했고 **접었다**: 새 relation = migration이고, 그 번호는 `#286`의 미착지 `0057` 다음이어야 해서 이 카드가 미착지 PR 위에 쌓이게 되는데 카드가 지정한 base는 `25f43a25`였다. **만들지 않고 멈추고** 측정을 보고했다.

## 1. 코디네이터가 정한 범위 — 집계기를 부르는 경로

`tools/aggregate_ac11_evidence.py`는 8축을 재계산하고 **한 번도 호출된 적이 없다**. 재채점 v1.8 §4-5-3이 recomputed PASS를 0/8로 적는 이유가 그것이다 — **축이 실패한 수가 아니라 아무도 부르지 않은 수**다. 이 카드가 그 차이를 코드로 만든다.

### 1-1. 축 manifest — `docs/ac11-axis-sources.json`

8축 각각에 대해 **producer → workflow → importer** 경로를 적는다. 값은 tree에서 읽어 측정했다.

| 축 | chain | 이유 |
|---|---|---|
| `migration-reversible-segment` · `irreversible-restore-forward` | **complete** | `run_ac11_migration_rehearsal.py` → `ac11-migration-rehearsal.yml` → `import_ac11_migration_rehearsal.py`(두 축을 한 importer가 낸다) |
| `security-critical-high-zero` | **complete** | `run_ac11_security_scan.py` → `ac11-security-scan.yml` → `import_ac11_security_scan.py` |
| `accessibility-e2e` | incomplete | producer와 workflow는 있고 **importer가 없다**. 집계기가 요구하는 `artifactSha256`·`artifactObservedSha256`·`artifactAvailable`·`artifactExpiresAt`는 **그 digest가 기술하는 artifact 안에 producer가 넣을 수 없다** — 그래서 증거는 있고 **받아들일 수 있는 envelope이 없다** |
| `long-soak` | incomplete | producer·importer 둘 다 있고 **workflow가 없다** — 가져올 hosted run이 없다 |
| `actual-pitr-rpo-rto-retention` | absent | `G-22` 실 PITR 복원. 예행은 `restoreAttempted: false`·RPO/RTO `null` |
| `physical-five-node-ac05-placement-load` | absent | `G-19`·`G-24` 물리 5노드 |
| `physical-five-node-failure-recovery` | absent | `G-21`·`G-24` 별도 failure domain — 예행 스크립트가 스스로 복원 cluster가 같은 호스트라고 적는다 |

**없는 축을 조용히 빼지 않는다.** `incomplete`·`absent`는 **이유를 반드시 적어야** 하고(검사가 강제한다), 그 문장이 집계기의 `INVALID_RUN`을 읽을 수 있게 만드는 것이다.

### 1-2. 조립기 — `tools/assemble_ac11_manifest.py`

envelope 디렉터리를 읽어 집계기의 manifest를 쓴다. **거부하는 것**: 다른 SHA의 envelope, `artifactObservedSha256 != artifactSha256`, 만료, `artifactAvailable`이 거짓, 한 축에 두 envelope, 모르는 축, **입력의 중복 JSON key**(`json.loads`가 마지막을 채택하므로 읽는 사람마다 다르게 읽히는 파일은 증거가 아니다 — `#295` r3에서 배운 것을 여기에 바로 넣었다).

**조용히 빼는 대신 이름을 적는다**: 모아지지 않은 축은 `absentAxes`에 사유와 함께 적히고 manifest는 그대로 쓰인다. 두 답은 다른 질문에 답한다 — 조립기는 **무엇을 모으지 못했나**, 집계기는 **증거가 무엇을 말하나**. 축을 빼면 `INVALID_RUN`이 더 작은 PASS처럼 보이게 된다.

importer의 zip flag(`--artifact-zip` vs `--archive`)도 manifest가 든다. 처음에는 lane에서 둘을 차례로 시도하게 썼다가 지웠다 — **실패하면 다른 flag로 재시도하는 것은 진짜 거부를 재시도로 바꾼다.**

### 1-3. lane — `.github/workflows/ac11-aggregate.yml`

`workflow_dispatch` 전용, 입력은 `source_sha`(40-hex 강제)와 `correlation_id`. 권한은 **`contents: read` + `actions: read`** 이고, 후자가 이 lane이 따로 있는 이유다 — 다른 run의 artifact를 읽어야 하는데 `contents: read`로는 못 한다.

**push trigger를 두지 않았다.** 두 이유가 있고 둘 다 실질적이다: push로 integration을 받는 workflow는 `tools/post_landing_verify.py`에 lane을 **빚지고**(`test_post_landing_verify.py`의 역래칫이 그것을 단언한다), 그리고 이 lane은 **다른 lane의 artifact를 읽으므로** 그들이 돌기 전에는 할 말이 없다. 또 집계는 **한 exact SHA**에 관한 것이어서 push마다 돌리면 아무도 묻지 않은 tree에 대한 `INVALID_RUN`이 쌓인다.

역래칫은 **고치지 않아도 통과한다**(97 passed) — dispatch 전용은 lane을 빚지지 않는다. 그 판단을 우연에 두지 않고 **시험으로 적었다**: `test_the_aggregate_workflow_is_dispatch_only_and_so_owes_no_landing_lane`이 trigger 집합과 권한을 단언한다. `DISPATCH_ONLY_WORKFLOWS`에 넣지 **않았다** — 그 목록은 **lane이 있는** workflow의 예외 목록이고, 그 자신의 시험이 "빠뜨림의 주차장이 되지 말 것"을 경고한다.

## 2. 검증

| 항목 | 결과 |
|---|---|
| `tests/core/test_assemble_ac11_manifest.py` | **32 passed**(신설) |
| `tests/core/test_post_landing_verify.py` | **97 passed** — 역래칫이 새 workflow를 받아들인다 |
| `tests/test_aggregate_ac11_evidence.py` | **85 passed**(무변경 확인) |
| 조립기 실행 | 빈 디렉터리로 돌려 **8축 전부 absent**와 사유를 출력하고 manifest를 썼다 |
| workflow | `yaml.safe_load` 통과, bash step **5개 전부 `bash -n` exit 0**, 내장 python block **2개 전부 `ast.parse` 통과** |
| 문서 gate | `check_docs`·`check_doc_single_source`·citation ratchet·`git diff --check` exit 0 |

## 3. 이 카드가 **하지 않은** 것

- **집계기를 실제로 실행해 PASS를 만들지 않았다.** 5축에 받아들일 수 있는 envelope이 없으므로 지금 이 lane을 돌리면 결과는 `INVALID_RUN`이고, 그것이 **정직한 답**이다. 그 사실을 시험으로 고정했다(`test_the_aggregation_of_this_tree_cannot_be_valid_yet`) — 누군가 그것을 가능하게 만드는 날 바꿔야 하는 단언이 그것이다.
- **accessibility importer를 만들지 않았다.** 축 정의가 아니라 **누락된 연결**이고 별도 카드다.
- **long-soak workflow를 만들지 않았다.** 같은 이유다.
- **AC-11 축 정의를 바꾸지 않았다.** `REQUIRED_AXES`·`REQUIRED_TARGET_BY_AXIS`는 손대지 않았다. 축 정의를 바꿔야 하는 판단이 생기면 AC-11 owner(Codex)에게 계약 질문으로 올린다.

## 4. 다음 첫 행동

1. **Codex**: 이 변경 검토. 특히 (a) 축 manifest가 축 정의를 **기술**만 하고 바꾸지 않는지, (b) `incomplete` 두 축(accessibility importer·long-soak workflow)을 별도 카드로 두는 판단, (c) dispatch 전용이 역래칫에 대해 옳은 선택인지.
2. **코디네이터**: 이 lane을 train 12 후보 SHA에서 한 번 dispatch할지. 결과는 `INVALID_RUN`일 것이고 그것이 **0/8이 왜 0/8인지를 도구가 말한 첫 기록**이 된다.
3. **Claude**: accessibility importer 카드(그 축만 complete로 바뀐다).
