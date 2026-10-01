---
doc_id: "HISTORY-CARD203-AC11-AGGREGATE-LANE-20261002"
title: "카드 203 — AC-11 집계기를 부르는 CI 경로와 축 manifest: 0/8은 축이 실패한 수가 아니라 아무도 부르지 않은 수였다 (카드 201 측정 포함)"
version: "1.1.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T05:22:00+09:00"
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

## 5. r1 — AC-11 owner 검토가 셋을 막았고, 하나는 제 분류가 틀린 것이었다

### 5-1. (1) migration 두 축이 **실제 lane에서 유실**됐다

`import_ac11_migration_rehearsal.py`는 `runPurpose: "ac11-migration-rehearsal-import"` 하나에 **`axes` 배열**을 담아 쓴다(그 배열의 각 행은 `runPurpose: "ac11-axis-evidence"`를 갖춘 제대로 된 envelope다). 내 `read_envelopes()`는 **단일 envelope만** 읽고 나머지는 `continue`로 넘겼다 — 즉 **artifact가 있어도 두 축이 조용히 사라졌다.** 이 모듈의 docstring이 "조용히 빼지 않는다"고 적은 바로 그 실패다.

고친 것 둘:
- **bundle 모양을 읽는다.** `BUNDLE_PURPOSES`에 속하면 `axes` 행을 꺼내 각각 기록하고, 행의 `runPurpose`가 axis envelope이 아니면 **거부**한다.
- **모르는 `runPurpose`는 무시하지 않고 거부한다.** 무시가 바로 이 유실을 숨긴 동작이었다. 시험 `test_a_file_this_tool_cannot_read_is_refused_rather_than_ignored`가 그 변경 자체를 적는다.

### 5-2. 그러면서 **security 분류가 틀린 것을 찾았다**

`import_ac11_security_scan.py`는 producer의 report를 그대로 돌려준다 — `runPurpose: "s11-ac11-security-scan"`이고 **`axis` field가 없다.** 집계기는 `runPurpose == "ac11-axis-evidence"`와 `REQUIRED_AXES`의 `axis`를 요구한다. 그래서 이 축은 **importer가 있는데도 받아들일 수 있는 envelope이 없다.**

`complete`로 적은 근거가 "producer·workflow·importer가 다 있다"였고, **"importer가 있다"는 "importer가 axis envelope을 낸다"와 다르다.** `security-critical-high-zero`를 **`incomplete`로 정정**하고 사유에 그 측정을 적었다. 그 report를 axis envelope으로 바꾸는 adapter가 필요하고, 그것은 후속 카드다.

그래서 **complete는 3축이 아니라 2축**이다. 그 수를 시험이 들고 있다.

### 5-3. (2) 축 manifest를 strict로

| 변이 | r1 전 | r1 후 |
|---|---|---|
| unknown top-level key | **통과** | `top-level key set is not exact; unexpected ['unexpected']` |
| `repository: "attacker/repo"` | **통과** | `the axis sources name repository 'attacker/repo'` |
| `importerEmitsAxes: ["invented-axis"]` | **통과** | `names something that is not an axis` |
| `envelopeMember: "does-not-exist.json"` | **통과** | `<workflow> does not name 'does-not-exist.json'` |
| `envelopeShape` 발명 | — | `envelopeShape is 'whatever'` |
| `importerEmitsAxes`가 자기 축을 뺌 | — | `does not include this axis` |
| `purpose` 공백 | — | `must be a non-empty string` |
| complete인데 shape이 받아들일 수 없음 | — | `needs an admissible envelopeShape` |

**`importerEmitsAxes`를 importer 자신의 source에 결속했다** — 거기 적힌 축 이름이 importer(또는 producer)가 실제로 쓰는 이름이어야 한다. 그 검사가 security의 오분류를 **자동으로** 잡는다(그 importer는 어떤 축 이름도 쓰지 않는다). **`envelopeMember`는 zip 안의 member라 tree에 없지만**, 그것을 올리는 workflow가 이름을 적으므로 거기서 확인한다. `repository`는 고정한다 — 다른 저장소를 적을 수 있는 축 manifest는 lane을 남의 run으로 보낼 수 있다.

### 5-4. (3) 착지 후 재실행 절차와 lane 판단

**`#294` runbook을 건드리지 않았다**(승인됐고 train 12에 들어 있다). 대신 두 가지를 이 PR에 둔다.

**`post_landing_verify`에 lane을 추가하지 않는다.** 이유 둘: (가) 그 도구의 역래칫은 **push로 integration에 닿는** workflow만 다루고 이 lane은 dispatch 전용이라 `LANES`에 들어가지 않는다 — 넣으면 역래칫의 양방향 동치가 깨진다. (나) 이 lane은 **다른 lane의 artifact를 읽으므로** 그들이 끝나기 전에는 할 말이 없다. 착지 증명에 넣으면 착지 판정이 "아직 모른다"를 기다리게 된다.

**착지 후 절차**(이 문서가 정본이고 lane의 마지막 step이 같은 문장을 출력한다):

```bash
set -euo pipefail
cd /d/Project/SaintVisionI-Invion
LAND=$(git ls-remote origin refs/heads/integration/all-agents-unified | cut -f1)
printf '%s' "$LAND" | grep -Eq '^[0-9a-f]{40}$' || { echo "tip을 읽지 못했다" >&2; exit 1; }
# 1) #294 runbook §1을 먼저 끝낸다 -- 여덟 lane이 그 SHA에서 녹색이어야 이 lane이 읽을 artifact가 있다.
# 2) 그 뒤 이 lane을 그 SHA에서 dispatch한다.
gh workflow run ac11-aggregate.yml --ref integration/all-agents-unified -f source_sha="$LAND"
gh run list --workflow ac11-aggregate.yml --limit 5   --json databaseId,headSha,status,conclusion
```

착지 **전** 후보 SHA에서 돌린 결과는 **그 SHA 한정**이다. 착지 뒤 같은 명령을 landed SHA로 다시 돌린다.

### 5-5. 실측 — 새 lane을 exact head에서 한 번 dispatch했다

**먼저 측정된 것은 실패였다.** `workflow_dispatch` 전용이고 한 번도 돈 적 없는 workflow는 GitHub의 workflow index에 없어서

```
HTTP 404: workflow ac11-aggregate.yml not found on the default branch
```

로 거부된다. `ac11-security-scan.yml`도 `main`에 없지만 dispatch가 되는 이유는 **label PR trigger로 이미 등록돼 있기** 때문이다. 그래서 같은 모양을 더했다 — `pull_request: [labeled, synchronize, reopened]`에 `run-ac11-aggregate` label gate, PR event에서는 그 PR의 head SHA를 쓴다. **`push` trigger는 여전히 없으므로 §5-4의 역래칫 판단은 그대로다.**

그 뒤 label을 붙여 **실제로 돌렸다**.

| | |
|---|---|
| run | **[36921447095](https://github.com/egparadise/SaintVision-Invion/actions/runs/36921447095)** (`pull_request`, head `9b26dbf9`) |
| lane 결과 | **success** — 열세 step 전부 success |
| 집계기 | **exit 2**, `verdict: INVALID_RUN`, `done: False` |
| 조립 보고 | `assembledAxes: []`, `aggregationWillBeInvalid: true`, **8축 전부 사유와 함께 이름이 적혔다** |
| artifact | `s11-ac11-aggregate-9b26dbf9f56da9819c9c43308036be2cb71d8853` (manifest·조립 보고·집계 결과) |

**이것이 0/8이 왜 0/8인지를 도구가 말한 첫 기록이다.** 그 run의 로그에 여덟 줄이 그대로 남는다 — migration 두 축은 "이 SHA에서 rehearsal을 dispatch하고 importer를 돌려라", security는 "importer가 axis envelope을 내지 않는다", long-soak은 "workflow가 없다", accessibility는 "importer가 없다", 나머지 셋은 `G-22`·`G-19/24`·`G-21/24`.

lane이 **success**인 것은 의도된 것이다 — 집계기의 exit 0·1·2는 모두 **답**이고, lane의 실패는 집계기가 돌지 못한 경우뿐이다.

### 5-6. 검증

| 항목 | 결과 |
|---|---|
| `tests/core/test_assemble_ac11_manifest.py` | 32 → **43 passed** |
| `tests/core/test_post_landing_verify.py` | **97 passed**(역래칫 무변경) |
| 변이 | 축 manifest 8종 전부 사망(위 표), bundle 3종(행의 runPurpose·빈 axes·모르는 purpose) |
| 조립기 | bundle 하나로 **두 축**이 manifest에 들어가는 것을 시험이 단언한다 |
