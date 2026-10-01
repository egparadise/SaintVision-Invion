---
doc_id: "HISTORY-CARD203-AC11-AGGREGATE-LANE-20261002"
title: "카드 203 — AC-11 집계기를 부르는 CI 경로와 축 manifest: 0/8은 축이 실패한 수가 아니라 아무도 부르지 않은 수였다 (카드 201 측정 포함)"
version: "1.3.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T06:18:59+09:00"
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
| `security-critical-high-zero` | ~~complete~~ → **incomplete** | **초기 판정이고 §5-2에서 정정했다.** `run_ac11_security_scan.py` → `ac11-security-scan.yml` → `import_ac11_security_scan.py`가 모두 **있다**는 것만으로 complete로 적은 것이 틀렸다 — 그 importer는 axis envelope을 내지 않는다 |
| `accessibility-e2e` | incomplete | producer와 workflow는 있고 **importer가 없다**. 집계기가 요구하는 `artifactSha256`·`artifactObservedSha256`·`artifactAvailable`·`artifactExpiresAt`는 **그 digest가 기술하는 artifact 안에 producer가 넣을 수 없다** — 그래서 증거는 있고 **받아들일 수 있는 envelope이 없다** |
| `long-soak` | incomplete | producer·importer 둘 다 있고 **workflow가 없다** — 가져올 hosted run이 없다 |
| `actual-pitr-rpo-rto-retention` | absent | `G-22` 실 PITR 복원. 예행은 `restoreAttempted: false`·RPO/RTO `null` |
| `physical-five-node-ac05-placement-load` | absent | `G-19`·`G-24` 물리 5노드 |
| `physical-five-node-failure-recovery` | absent | `G-21`·`G-24` 별도 failure domain — 예행 스크립트가 스스로 복원 cluster가 같은 호스트라고 적는다 |

**이 표는 r1 시점의 초기 판정이다.** security 행은 §5-2에서 `incomplete`로 정정됐고, 그래서 **complete는 셋이 아니라 둘**(migration 두 축)이다. 표를 지우지 않고 정정 표시를 남긴다 — 무엇을 잘못 세었는지가 §5-2의 교훈이기 때문이다(#299 r3 관찰).

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
# correlation_id는 이 한 번의 실행을 사후에 지목하기 위한 것이다. lane이 그것을
# artifact의 ac11-checkout.json에 적으므로, 로그가 만료된 뒤에도 어느 run이 어느
# tree를 읽었는지 확인할 수 있다 (#299 r2).
CID="ac11-aggregate-$LAND-$(date -u +%Y%m%dT%H%M%SZ)"
gh workflow run ac11-aggregate.yml --ref integration/all-agents-unified \
  -f source_sha="$LAND" -f correlation_id="$CID"
```

그 다음이 **그 run을 고르고 기다리고 검증하는 절차**다. r2의 `gh run list --limit 5`만으로는 **어느 줄이 내 run인지 알 수 없었다** — 그 출력에 `displayTitle`도 correlation id도 없다(#299 r3). `run-name`이 `correlation_id`이므로 `displayTitle`이 그 값이고, 그것으로 **정확히 하나**를 고른다. 아래는 같은 셸에서 이어 실행한다(`LAND`·`CID`가 위에서 정해져 있다):

```bash
set -euo pipefail
cd /d/Project/SaintVisionI-Invion
# run-name이 correlation_id이므로 displayTitle이 그 값이다. 이름으로 고르지 않으면 같은
# workflow의 다른 run(label PR event 등)을 보게 된다. 정확히 하나가 아니면 멈춘다.
RUN=$(gh run list --workflow ac11-aggregate.yml --limit 30 \
  --json databaseId,displayTitle,event,headSha \
  --jq "[.[] | select(.displayTitle == \"$CID\" and .event == \"workflow_dispatch\" and .headSha == \"$LAND\")] | if length == 1 then (.[0].databaseId | tostring) else \"\" end")
if [ -z "$RUN" ]; then
  echo "correlation_id '$CID'로 단일 workflow_dispatch run을 찾지 못했다 -- 멈춘다" >&2
  exit 1
fi
echo "run=$RUN"
# lane의 실패만 실패다. 집계기의 exit 1·2는 답이고 lane은 success로 끝난다.
gh run watch "$RUN" --interval 20 --exit-status

ART=$(gh api "repos/egparadise/SaintVision-Invion/actions/runs/$RUN/artifacts" \
  --jq "[.artifacts[] | select(.name == \"s11-ac11-aggregate-$LAND\")] | if length == 1 then (.[0].id | tostring) else \"\" end")
if [ -z "$ART" ]; then
  echo "run $RUN에 s11-ac11-aggregate-$LAND artifact가 정확히 하나가 아니다 -- 멈춘다" >&2
  exit 1
fi
OUT=$(mktemp -d)
gh api "repos/egparadise/SaintVision-Invion/actions/artifacts/$ART/zip" > "$OUT/aggregate.zip"

# 영수증이 이 run을 그 tree에 묶는지 확인한다. 하나라도 어긋나면 비영으로 끝난다.
D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe - \
  "$OUT/aggregate.zip" "$LAND" "$RUN" "$CID" <<'PY'
import json, sys, zipfile
path, land, run, cid = sys.argv[1:]
receipt = json.loads(zipfile.ZipFile(path).read("ac11-checkout.json"))
expected = {"sourceSha": land, "checkoutSha": land, "event": "workflow_dispatch",
            "runId": run, "correlationId": cid}
wrong = {k: (receipt.get(k), v) for k, v in expected.items() if receipt.get(k) != v}
if wrong:
    raise SystemExit(f"receipt does not bind this run: {wrong}")
print("receipt binds run", run, "to", land)
PY

# 그리고 판정을 읽는다. INVALID_RUN도 답이고, 그 사유가 무엇이 빠졌는지를 말한다.
D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe - "$OUT/aggregate.zip" <<'PY'
import json, sys, zipfile
archive = zipfile.ZipFile(sys.argv[1])
result = json.loads(archive.read("ac11-aggregate-result.json"))
print("verdict:", result.get("verdict"), "done:", result.get("done"))
for reason in result.get("reasons", []):
    print("  reason:", reason)
for axis in result.get("axes", []):
    print(" ", axis.get("axis"), axis.get("verdict"))
report = json.loads(archive.read("ac11-assembly-report.json"))
print("assembled:", report.get("assembledAxes"))
PY
```

**이 블록을 그대로 실행해 확인했다**(§7-2) — 이미 끝난 dispatch run을 `LAND`·`CID`로 골라, 영수증이 그 run을 그 tree에 묶는 것과 판정을 출력하고 **exit 0**으로 끝났다. `gh run watch`는 끝난 run에 대해 `has already completed with 'success'`를 출력하고 0으로 끝난다.

착지 **전** 후보 SHA에서 돌린 결과는 **그 SHA 한정**이다. 착지 뒤 같은 명령을 landed SHA로 다시 돌린다.

### 5-5. 실측 — label PR event로 lane을 **처음 돌렸다**(`workflow_dispatch` 실측은 §6-2)

**이 절의 제목은 r1에서 "exact head에서 dispatch했다"였고 틀렸다**(#299 r2가 지적했다). 아래 run의 `event`는 `pull_request`다 — dispatch는 §6-2에서 실제로 했다. 더 나쁜 것은 그 PR event의 checkout이 head가 아니었다는 것이고, 그것이 §6-1이다.

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

## 6. r2 — lane이 읽은 tree가 lane이 말한 tree가 아니었다

### 6-1. (1) `pull_request`에서 checkout이 **ephemeral merge commit**이었다

`ref: ${{ inputs.source_sha }}`는 **dispatch에서만** 값이 있다. `pull_request` event에서는 input이 없어 `ref: ''`가 되고, `actions/checkout`은 그때 event 기본값인 `refs/pull/<n>/merge`를 가져간다. run `36921695718`의 로그가 그대로 적는다:

```
HEAD is now at 030e6283 Merge 77456da49702fe26fb9d385ebf51c0f209e6d996 into aaa0b083e60c4447a97be5e05a2c7a1ada82a607
```

그래서 lane은 **저장소에 없는 tree**(`030e6283`, GitHub가 그 순간 만든 merge commit)에서 `docs/ac11-axis-sources.json`과 importer를 읽으면서, artifact 조회·envelope SHA 비교는 `SOURCE_SHA = 77456da4`에 묶고 있었다. **code SHA와 envelope SHA가 다른 run** — 이 chain 전체가 존재하는 이유가 바로 그것을 거부하는 것이다. r1의 두 run(`36921447095`·`36921695718`)의 결론은 그래서 **그 SHA에 대한 진술로 읽을 수 없다.**

조치 둘:

1. `ref: ${{ env.SOURCE_SHA }}` — checkout이 다른 모든 step과 **같은 한 값**을 쓴다. artifact 이름도 같은 값으로 통일했다. job 수준 `concurrency`·`if`에는 `env` context가 없어서 그 둘만 긴 형태를 유지하고 이유를 주석에 적었다.
2. **checkout 직후 단언 step**: `git rev-parse HEAD`가 `SOURCE_SHA`와 다르면 lane이 멈춘다. 같으면 `evidence/ac11-checkout.json`에 `sourceSha`·`checkoutSha`·`event`·`runId`·`correlationId`를 적어 **artifact에 남긴다** — 로그는 만료되고 artifact는 남으므로, 사후에 "그 run이 그 tree를 읽었다"를 확인할 수 있는 것은 후자뿐이다. 그 step은 `setup-python`보다 **앞**에 둔다(틀린 tree면 설치 전에 멈춰야 한다), 그래서 image가 보장하는 `python3`만 쓴다.

### 6-2. (2) `workflow_dispatch` 실측 — 이제 있다

`gh workflow run`으로 **실제로** 한 번 돌렸다. r1의 404는 **등록 문제**였고(dispatch 전용이면서 한 번도 돈 적 없는 workflow는 index에 없다), label PR run이 그것을 등록했으므로 이제 dispatch가 받아들여진다 — 그 인과도 이번에 측정됐다.

```
gh workflow run ac11-aggregate.yml --ref feat/claude/c203-ac11-aggregate-lane \
  -f source_sha=6d2c8f16622279a7a96274b09a43b23899fb2ee1 \
  -f correlation_id=c203-r2-dispatch-6d2c8f16-20261002T060013+0900
```

| | |
|---|---|
| run | **[36925665586](https://github.com/egparadise/SaintVision-Invion/actions/runs/36925665586)** |
| event | **`workflow_dispatch`** (branch `feat/claude/c203-ac11-aggregate-lane`) |
| `source_sha` 입력 | `6d2c8f16622279a7a96274b09a43b23899fb2ee1` |
| **실제 checkout SHA** | **`6d2c8f16622279a7a96274b09a43b23899fb2ee1`** — 단언 step이 artifact에 적었다(`ac11-checkout.json`) |
| `correlationId` | `c203-r2-dispatch-6d2c8f16-20261002T060013+0900` |
| lane 결과 | **success**(27초) |
| 집계기 | **exit 2**, `verdict: INVALID_RUN`, `done: False` |
| 조립 보고 | `assembledAxes: []`, `aggregationWillBeInvalid: true`, **8축 전부 사유와 함께** |
| artifact | `s11-ac11-aggregate-6d2c8f16622279a7a96274b09a43b23899fb2ee1` (manifest·조립 보고·집계 결과·**checkout 영수증**) |

받은 영수증 그대로:

```json
{"checkoutSha": "6d2c8f16622279a7a96274b09a43b23899fb2ee1",
 "correlationId": "c203-r2-dispatch-6d2c8f16-20261002T060013+0900",
 "event": "workflow_dispatch", "runId": "36925665586",
 "schemaVersion": "ac11-aggregate-checkout:1",
 "sourceSha": "6d2c8f16622279a7a96274b09a43b23899fb2ee1"}
```

**이것이 exact head에 대한 첫 dispatch 기록이다.** 그리고 §5-5의 두 run과 달리 **읽은 tree가 말한 tree와 같다는 증거를 자기 artifact에 들고 있다.**

### 6-3. (3) `importerEmitsAxes`를 **exact set**으로

r1은 "주장한 이름이 importer 소스에 **나타나는지**"만 봤다. 그래서 migration row에서 두 축 중 하나를 지운 변이가 **참인 문장으로 chain의 절반만 기술**하며 통과했다 — 그리고 그 chain의 importer는 **한 bundle에 두 축을 담으므로**, 절반만 주장된 행은 bundle 하나를 온전한 하나처럼 읽게 만든다.

이제 `emitted_axes(importer)`가 **importer 파일에서 읽은 집합**과 주장이 **정확히 같은지**를 본다. **importer가 없는 row는 빈 집합**이다 — producer가 축 이름을 적더라도(accessibility의 `collect_ac11_accessibility_e2e.py`가 그렇다) 그것을 envelope으로 바꾸는 것이 없으면 집계기에 들어가는 것은 없다. `importerEmitsAxes`가 답하는 질문은 "이 chain에서 집계기로 **무엇이 들어가는가**"이기 때문이다.

측정해 시험으로 박은 사실: migration importer는 **두 축**을 쓰고, security importer는 **0개**, long-soak importer는 **1개**, 없는 importer는 **0개**. 그리고 **배포된 map의 여덟 행 전부**가 자기 importer가 쓰는 집합과 같다는 일관성 시험을 더했다.

변이 4건이 새로 죽는다 — 한 축만 남긴 둘(각각 `writes ['irreversible-restore-forward', 'migration-reversible-segment']`와 `does not include this axis`로), 길이 비교를 속일 **중복**, importer 없는 row가 자기 축을 주장하는 경우. fixture 자신도 그 변이였다: `importerEmitsAxes: [axis]`로 한 축만 적고 있었고, 이제 `MIGRATION_AXES` 상수로 실제 쌍을 박아 **importer가 바뀌면 fixture가 먼저 깨진다.**

### 6-4. 검증

| 항목 | 결과 |
|---|---|
| `tests/core/test_assemble_ac11_manifest.py` | 43 → **49 passed** |
| `tests/core/test_post_landing_verify.py` | **97 passed**(trigger 집합 무변경이므로 역래칫 판단도 그대로) |
| `tests/test_aggregate_ac11_evidence.py` | **85 passed**(무변경 확인) |
| workflow | `yaml.safe_load` 통과, bash step **6개 전부 `bash -n` exit 0**, 내장 python **3개 전부 `ast.parse` 통과** |
| 실측 | dispatch run **36925665586** — event·checkout SHA·correlation id가 artifact에 남았다 |
| 문서 gate | `check_docs`·citation ratchet·`git diff --check` exit 0 |

## 7. r3 — 집합을 **문자열 검색**으로 읽은 것이 양쪽으로 틀렸다

### 7-1. (F1) `emitted_axes()`는 importer 원문의 문자열 inventory였다

r2는 "주장한 축 이름이 importer 소스에 `"그대로"` 나타나는지"로 집합을 만들었다. 그것은 **두 방향으로** 틀렸다:

- **fail-closed 쪽이 아니라 fail-wrong**: `#302`의 accessibility importer는 축 이름을 `collector.AXIS` 상수에서 가져온다. 그 파일에는 `"accessibility-e2e"` 리터럴이 없으므로 집합이 **빈 것으로 읽히고**, 그 행의 올바른 주장이 거부된다.
- **fail-open**: 코드와 무관한 주석 한 줄 `# "accessibility-e2e"` 만으로 **집합이 생긴다.** docstring도 같다.

**코디네이터 결정(두 PR 공통 계약)을 구현했다**: 모든 AC-11 importer가 모듈 최상위에

```python
EMITTED_AXES: tuple[str, ...] = (...)
```

를 선언하고, `tools/assemble_ac11_manifest.py`는 **`ast`로 그 선언만 읽는다**. 주석·docstring은 코드가 아니고 `ast`는 그것을 보지 않는다. 기존 importer 셋에 상수를 넣었다 — migration은 **두 축**(그리고 이미 있던 `set(by_name) != {...}` 비교를 `set(EMITTED_AXES)`로 바꿔 상수가 죽은 코드가 아니게 했다), long-soak은 **한 축**(`AXIS = EMITTED_AXES[0]`로 이름의 출처를 하나로), security는 **`()`** — 그 비어 있음이 §5-2의 발견이고, 이제 코드가 그것을 말한다.

**읽을 수 없으면 fail closed**다. 여기서 **빈 집합은 정당한 답**(security)이므로, "계약을 읽지 못했다"가 거기로 접혀 들어가면 둘을 구별할 수 없다. 그래서 거부한다 — 선언 없음, 두 번 선언, tuple/list 리터럴이 아님, 원소가 문자열 리터럴이 아님(선언을 읽는 것이 모듈을 실행하는 것이 되면 안 된다), AC-11에 없는 이름, 중복, parse 실패.

측정(`declared_axes` 직접 호출):

| 입력 | 결과 |
|---|---|
| migration importer | `{migration-reversible-segment, irreversible-restore-forward}` |
| security importer | `{}` — 선언된 `()` |
| long-soak importer | `{long-soak}` |
| importer 없는 행 | `{}` |
| **주석 decoy** `# "accessibility-e2e"` + `EMITTED_AXES = ()` | **`{}`** — 주석은 무시된다 |
| **docstring decoy** | **`{}`** |
| **`#302` 모양**(`from collector import AXIS`, 선언은 리터럴) | **`{accessibility-e2e}`** |
| 선언 없음 / 함수 안에만 | 거부 — `declares no module-level EMITTED_AXES` |
| 두 번 선언 | 거부 — `declares EMITTED_AXES 2 times` |
| `EMITTED_AXES = AXIS` / 값 없는 annotation | 거부 — `must be a literal tuple or list` |
| `EMITTED_AXES = (AXIS,)` | 거부 — `must be a string literal` |
| 모르는 축 / 중복 / parse 실패 | 거부 — 각각 사유 문장 |

시험 14건 추가(49 → **63 passed**): decoy 3종, 읽을 수 없는 선언 9종, tree의 모든 `tools/import_ac11_*.py`가 계약을 선언하는지, 그리고 축 map 변이 1건 — **tree에 있지만 AC-11 importer가 아닌 파일**(`tools/check_docs.py`)을 가리키는 행은 경로 검사를 통과하고 **계약 부재로** 거부된다.

### 7-2. (F2) 착지 후 dispatch에 **고르고 기다리고 검증하는** 절차가 없었다

r2는 correlation id를 **만들었지만**, 그 run을 어떻게 고르는지가 없었다. `gh run list --limit 5 --json databaseId,headSha,status,conclusion`에는 `displayTitle`도 correlation id도 없어서 **어느 줄이 내 run인지 알 수 없다.** §5-4에 실행 가능한 블록을 넣었다 — `displayTitle == CID` + `event == workflow_dispatch` + `headSha == LAND`로 **정확히 하나**를 고르고(하나가 아니면 멈춘다), `gh run watch --exit-status`로 기다리고, artifact를 내려받아 `ac11-checkout.json`의 **두 SHA·event·runId·correlationId를 전부** 대조하고, 마지막에 판정과 사유를 출력한다.

**그 블록을 그대로 실행해 확인했다.** 이미 끝난 dispatch run을 `LAND`·`CID`만으로 골라냈다:

```
run=36925665586
Run AC-11 Axis Aggregation (36925665586) has already completed with 'success'
receipt binds run 36925665586 to 6d2c8f16622279a7a96274b09a43b23899fb2ee1
verdict: INVALID_RUN done: False
  reason: missing required axes: accessibility-e2e, actual-pitr-rpo-rto-retention, ...
assembled: []
```

exit 0. 문서의 블록과 내가 실행한 파일은 **byte 단위로 같다**(`diff` 확인). `displayTitle`이 실제로 correlation id라는 것도 측정했다 — dispatch run은 `c203-r2-dispatch-6d2c8f16-...`, label PR run들은 workflow 이름 `AC-11 Axis Aggregation`이다.

### 7-3. (관찰) §1-1의 초기 표가 §5-2의 정정과 충돌했다

§1-1은 r1 시점의 표이고 security를 `complete`로 적었는데 §5-2가 그것을 `incomplete`로 정정했다. 표를 **지우지 않고** `~~complete~~ → incomplete`와 "초기 판정이고 §5-2에서 정정했다"를 적었다 — 무엇을 잘못 세었는지(파일의 존재를 셌다)가 그 절의 교훈이기 때문이다. 그리고 **complete는 셋이 아니라 둘**이라고 §1-1에도 명시했다.

### 7-4. 검증

| 항목 | 결과 |
|---|---|
| `tests/core/test_assemble_ac11_manifest.py` | 49 → **63 passed** |
| AC-11 인접 9개 suite 합산 | **316 passed** — `test_ac11_migration_rehearsal`·`test_ac11_security_scan`·`test_aggregate_ac11_evidence`·`test_collect_ac11_accessibility_e2e`·`test_import_ac11_*` 3종·`test_run_ac11_composite_long_soak`·`test_post_landing_verify` |
| §5-4 블록 | `bash -n` exit 0, **실제 실행 exit 0**, 문서 블록과 실행 파일 `diff` 일치 |
| History bash 블록 | **2개 전부 `bash -n` exit 0** |
| 문서 gate | `check_docs`·`check_doc_single_source`·citation ratchet·`git diff --check` exit 0 |
