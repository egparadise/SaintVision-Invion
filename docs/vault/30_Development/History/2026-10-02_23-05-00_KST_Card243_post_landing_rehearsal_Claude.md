---
doc_id: "HISTORY-CARD243-POST-LANDING-REHEARSAL-20261002"
title: "카드 243 — 착지 직후 runbook을 착지 없이 끝까지 한 번 돌렸다. 세 자리가 문서와 달랐고, train 27 후보의 착지 차단 사유 하나를 찾았다"
version: "1.1.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T23:30:12+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "f337f037aa3a872503a1c14f85070335575b5d3b"
task_ids: ["S11-BE", "S12-BE"]
tags: ["operations", "landing", "rehearsal", "ac11", "vf-cl", "attestation", "claude"]
---

# 카드 243 — 착지 직후 runbook 리허설

## 0. 한 줄

**`integration`을 건드리지 않고** `$LAND` 자리에 train 27 후보 SHA를 넣어 [[착지_직후_첫_행동_정본]]을 **§2부터 §6까지 실제로 실행**했다. **세 자리가 문서와 달랐고**(그 중 하나는 명령을 그대로 복사하면 **반드시 실패**한다) 고쳤다. 그리고 리허설이 **train 27 후보의 착지 차단 사유**를 찾았다 — Backend가 red이고 그 중 두 건이 내 것이었다(이미 고쳐 push했다).

**시점을 고정해 읽는다 (r2에서 분리).** 이 문서의 모든 관측은 **2026-10-02 22:30~23:07**에 **train 27 후보 `f337f037`** 에서 한 것이다. 그 뒤 `#333`이 **`0a45e336`(22:58)** 으로 0060 allowlist 정합을 고쳤고, 내가 **독립 검토로 승인**했다(그 PR의 `## 독립 검토 r3 (Claude)` 코멘트 — revision 일치·서명 15·생성기 `--check` exit 0·exact-head Backend `37016630924`·Core `37016630958` success·내 `#334` `bdf2b0fa`와의 임시 merge 180 passed). **그래서 §3의 `#333` 세 건은 '리허설 당시'의 상태**이고, 지금 남은 것은 §9가 적는 **train 28 재조립**이다.

**이것은 착지가 아니다.** `ciVerified` 같은 **착지 SHA 전용 판정은 어디에도 기록하지 않았다** — 리허설 attestation은 후보 head를 가리키므로 그것을 참 주장의 근거로 쓰면 가짜 증거가 된다.

## 1. 리허설의 치환 — 무엇을 무엇으로 바꿨나

| 문서의 값 | 리허설의 값 | 왜 |
|---|---|---|
| `$LAND` = `git ls-remote … integration/all-agents-unified` | **`f337f037aa3a872503a1c14f85070335575b5d3b`**(train 27 후보 tip) | integration을 밀지 않는다 |
| `$PREVIOUS` | **`a2d64b6193913a56448a0ef495d1b7b374de2a54`**(train 26 후보 tip) | 사슬 검사가 의미를 갖게 |
| dispatch ref `integration/all-agents-unified` | **`coord/train27a-ci-2223`** | 그 branch의 tip이 `$LAND`와 같다 |
| `post_landing_verify.py` | **`--ref coord/train27a-ci-2223`** | 그 도구에 이미 있는 flag다(§3) |
| `ac11_dispatch_in_order` | **`GUARD_DISPATCH_REF=coord/train27a-ci-2223`** | 그 helper에 이미 있는 tunable이다(§5) |
| `--expected-ref refs/heads/integration/…` | **`refs/heads/coord/train27a-ci-2223`** | attestation job이 `$GITHUB_REF`로 검증하므로 리허설 ref가 그 값이다 |

**integration tip은 리허설 전후로 `6fc0428b49f28379cb4da17830d92256b55c2eb2` 그대로다**(시작 22:30, 끝 23:0x에 각각 `ls-remote`로 읽었다).

## 2. §2 게이트 — 통과

`require_sha`가 두 값을 모두 통과시키고(40자 소문자 hex), `git merge-base --is-ancestor a2d64b61… f337f037…`가 **성립**했다(fast-forward 모양). 문서대로다.

**게이트 파일 자체도 이 tree에서 다시 돌렸다**: `tests/test_post_landing_lane_guard.py` **28 passed**(skip 0), `bash -n tools/post_landing_lane_guard.sh` exit 0, 그리고 인용된 도구 다섯 개(`post_landing_verify.py`·`record_vf_cl_ci_receipt.py`·`verify_vf_cl_ci_attestation.py`·`check_vf_cl_registry.py`·`assemble_ac11_manifest.py`)의 `--help`가 전부 돈다.

## 3. §3 여덟 lane 결속 — **두 가지를 찾았다**

`python tools/post_landing_verify.py --landed f337f037… --previous a2d64b61… --ref coord/train27a-ci-2223 --out-dir .work/post-landing-rehearsal/f337f037…`

`--dry-run`이 먼저 lane 지도를 출력했고(여덟 lane·열 job), 실제 실행은 그 head의 run을 찾거나 dispatch했다. 그 head에서 관측된 결과:

| lane | run | 결과 |
|---|---|---|
| AC-11 Accessibility E2E | `37012736511` | success |
| Portal Login Journey Harness | `37012732284` | success |
| AC-11 Security Critical High | `37012727613` | success |
| Documentation Build | `37012723116` | success |
| Auth and Desktop HTTP Browser | `37012719131` | success |
| Frontend Build & Test | `37012714543` | success |
| **Backend Build** | **`37012706073`** | **failure** |
| Core Build | `37012710473` | 리허설을 끊은 시점에 진행 중 |

**찾은 것 (가) — 이 도구는 기록을 끝에서 한 번 한다.** 내가 25분 상한으로 끊었더니 `--out-dir`에 **아무것도 남지 않았다**. 그래서 runbook에 그 사실과 `--deadline-seconds`로 기다림을 묶는 법, 그리고 **실패한 lane 자체가 §7의 사유**라는 것을 적었다.

**찾은 것 (나) — train 27 후보는 그대로 착지할 수 없다.** Backend가 red이고 **5건**이다:

| 실패 | 소유 | 원인 |
|---|---|---|
| `test_an_exception_the_reviewed_allowlist_does_not_carry_is_a_violation` | **나(`#334`)** | 카드 236이 `inv_audit_reader`에 검토된 disposition이 **없던 상태의 결과**(VIOLATIONS)를 시험에 **적어 두었다**. `#333`이 그 예외를 넣자 같은 측정이 `PASS`가 됐다 |
| `test_the_axis_now_measures_a_verdict_instead_of_observing_nothing` | **나(`#334`)** | 같은 이유로 `MEASURED_FAIL`을 기대했는데 `MEASURED_PASS` |
| `test_write_ac11_security_allowlist.py` 3건 | `#333` | **리허설 당시**(head `03ddb394` 계열) `tools/write_ac11_security_allowlist.py`가 **`reviewed definer revision differs from definer-policy.json`** 으로 거부했다. **그 뒤 `#333`이 `0a45e336`에서 고쳤고 내가 승인했다**(§0) |

**내 두 건은 고쳐 push했다**(`#334` head `bdf2b0fa`; `#333`의 세 건도 그 뒤 `0a45e336`에서 고쳐졌다 — §0): 기대값을 상수로 적지 않고 **검토된 allowlist에서 유도**한다 — allowlist가 담은 `(role, table, rule)`은 `accepted`, 담지 않은 것은 `violations`이고 verdict는 그 결과로 따라온다. 그래서 그 disposition이 들어오든 빠지든 깨지지 않고 **관계가 어긋날 때만** 깨진다. `#333`의 3건은 **보고만 했다**(내 소유가 아니다).

## 4. §4 VF-CL-04 attestation — **문서의 경로가 틀렸다**

`s12-acceptance-evidence.yml`을 후보 ref에서 dispatch했고(correlation id에 `rehearsal-`을 붙였다) **73초**에 두 job이 모두 success였다.

| 무엇 | 값 |
|---|---|
| run | **`37014838468`**(`workflow_dispatch`, head `f337f037…`) |
| job | `s12-acceptance-evidence` success → `attest-vf-cl-ci-receipt` success |
| `select_and_await`의 판정 | 그 workflow·그 head·그 event·그 correlation id의 run이 **정확히 하나**임을 확인하고 run id를 돌려줬다 |

**찾은 것 (다) — §4-3의 고정 경로는 반드시 실패한다.** 문서는 `$OUT/VF-CL-04.json`과 `$OUT/*.sigstore.json`을 넘기라고 적지만, 내려받은 artifact의 실제 내용은 이렇다:

```
<OUT>/SaintVision-Invion/SaintVision-Invion/.work/vf-cl-attestation/VF-CL-04.json
<OUT>/SaintVision-Invion/SaintVision-Invion/.work/vf-cl-attestation/verification.json
<OUT>/_temp/<임의 문자열>/attestation.json      <- bundle. *.sigstore.json이 아니다
```

그대로 실행하면 **`refused: attestation bundle is missing`** 으로 끝난다(그 출력을 실제로 받았다). 두 가지가 원인이다 — 업로드가 경로 구조를 담고 있어 파일이 `$OUT` 바로 아래에 없고, bundle 이름이 `actions/attest`의 출력인 **`attestation.json`** 이다. runbook을 **`find`로 찾아 넘기고 못 찾으면 멈추는** 형태로 고쳤다(`gh attestation verify` 예제도 같이).

고친 명령으로 다시 돌린 결과:

```
{"headSha": "f337f037aa3a872503a1c14f85070335575b5d3b",
 "receiptSha256": "7dfbeeba2ff40b1f6b1c786defee748276f5f17e8dfa2c31a9dbad1a086d3ee6",
 "runId": "37014838468", "status": "VERIFIED"}
```

`gh attestation verify`(서명·repo·signer workflow·source digest)도 **exit 0**이다.

**기록하지 않은 것 — 의도적으로.** `docs/vf-cl-ci-receipts/`·`docs/vf-cl-ci-attestations/`·`docs/vf-cl-task-registry.json`에 **아무것도 쓰지 않았다**. 그 bundle은 **후보 head**를 attest하므로 `ciVerified`의 근거가 될 수 없다 — 규칙 7은 **착지 SHA**를 요구한다. 검증 산출물은 `.work/post-landing-rehearsal/`(저장소 밖)에만 있다.

## 5. §5 AC-11 세 lane — 순서대로, 전부 success

`GUARD_DISPATCH_REF=coord/train27a-ci-2223 ac11_dispatch_in_order f337f037…`가 **5분**에 끝났다.

| 순서 | lane | run | 결과 |
|---|---|---|---|
| 1 | `ac11-security-scan.yml` | **`37015161229`** | success |
| 2 | `ac11-accessibility-e2e.yml` | **`37015301238`** | success |
| 3 | `ac11-aggregate.yml` | **`37015580035`** | success |

순서가 **지시가 아니라 실행**이라는 것이 확인됐다 — 두 producer가 각각 success로 끝난 **뒤에야** 집계기가 dispatch됐다(exit 0). 그 집계 run의 결과(artifact `11229342591`):

```
전체: INVALID_RUN · done false · 사유 = 여섯 축 absent
security-critical-high-zero : MEASURED_PASS
  threatReportVerdicts = {"SEC-DEF-001":"MEASURED_PASS","SEC-RLS-001":"MEASURED_PASS",
                          "SEC-SCAN-001":"MEASURED_PASS","SEC-VF-001":"MEASURED_PASS"}
accessibility-e2e           : MEASURED_FAIL   (수동 인수 입력이 없다)
```

**security 축이 네 threat report를 모두 `MEASURED_PASS`로 내고 축이 `MEASURED_PASS`가 된 것은 처음이다.** 그것은 이 후보가 `#333`(definer 서명 12→15, `inv_audit_reader` disposition 추가)과 `#334`(제품 쓰기 경로 audit seed)를 함께 담고 있기 때문이고, **리허설이 그 사실을 측정으로 보여 준 것**이다. 다만 위 §3의 Backend red 때문에 **이 후보가 그대로 착지하지는 못한다**.

**작은 자리 하나**: `ac11-lane-runs.tsv`에 `gh workflow run`이 출력한 **URL 줄이 섞여 들어간다**(TSV 행과 함께). 판정에는 영향이 없고 기록만 지저분해지므로 **도구를 지금 바꾸지 않고 보고한다** — `gh workflow run`의 stdout을 helper에서 버리면 되지만, 그 변경은 `tests/test_post_landing_lane_guard.py`의 가짜 `gh` 기대와 함께 봐야 한다.

## 6. §6 S08 — 읽기만 했다

`grep`으로 두 flag의 자리만 확인했다. **어떤 값도 바꾸지 않았다.** 이 tree에서 그 경로는 어차피 `#338`(카드 241)이 없어 시작점이 없다.

## 7. 그래서 고친 것과 보고한 것

| | 무엇 | 어디 |
|---|---|---|
| 고쳤다 | §4-3의 artifact 경로 — `find`로 찾고 못 찾으면 멈춘다(bundle 이름이 `attestation.json`인 것도 적었다) | `착지_직후_첫_행동_정본.md` |
| 고쳤다 | §3에 "기록은 끝에서 한 번", `--deadline-seconds`, 실패 lane은 §7의 사유 | 같은 문서 |
| 고쳤다 | 규칙 2에 **`.sh.pending`** — 검증 전 스크립트는 glob이 애초에 고르지 않는다(확인: `…-26-….sh`와 `…-27-….sh.pending`에서 26을 골랐다) | 같은 문서 |
| 보고만 → **해소됨** | `#333`의 세 시험 실패(`reviewed definer revision differs from definer-policy.json`) | 리허설 당시 보고했고, `#333`이 `0a45e336`에서 revision을 0060에 다시 결속해 고쳤다. **내가 독립 검토로 승인**(그 PR 코멘트) |
| 보고만 | `ac11-lane-runs.tsv`에 섞이는 URL 줄 | 이 문서 §5 |
| 이미 고쳐 push | 내 두 시험이 검토 결정 하나를 상수로 박아 둔 것 | `#334` head `bdf2b0fa` |

## 8. 확인하지 못한 것 / 하지 않은 것

- **착지하지 않았다.** integration tip은 리허설 전후로 같다.
- **`ciVerified`를 건드리지 않았다.** 리허설 attestation은 후보 head의 것이므로 참 주장의 근거가 아니다(§4).
- **§3을 끝까지 돌리지 못했다** — Core가 진행 중이었고 25분에서 끊었다. 그래서 `--out-dir`의 기록은 없다(그 사실이 §3의 발견이다).
- **`#333`의 실패를 고치지 않았다** — 소유가 아니다(보고만 했다). 그 PR이 `0a45e336`에서 스스로 고쳤고, **그 head의 독립 검토는 내가 따로 수행해 승인**했다 — 이 리허설의 결과가 아니라 **별 검토**다.
- **`#320` 문서의 §4-4(기록 위치)·§7(실패 분류)을 실행으로 확인하지 못했다** — 그 둘은 **실제 착지**에서만 의미가 있다(기록은 착지 SHA에 묶이고, §7은 실패한 착지의 절차다).

## 9. 다음 첫 행동

1. **코디네이터**: train 27 후보는 **Backend red였다**. 두 원인이 모두 해소됐으므로 — 내 두 건은 `#334` `bdf2b0fa`, `#333`의 세 건은 `0a45e336`(내 독립 검토 **승인**) — **train 28 재조립**이 다음이다. 그 두 head가 함께 들어가야 한다(임시 merge로 180 passed를 확인했다).
2. **Codex**: 이 PR(runbook 수정 + 검증기 encoding 수정)과 `#334`의 새 head 검토.
3. **Claude**: train 27이 재조립되면 같은 리허설을 **고친 runbook으로** 한 번 더 돌려 §4-3이 한 번에 통과하는지 확인한다(이번에는 두 번 돌렸다).
4. **Claude**: security 축이 `MEASURED_PASS`로 측정된 것은 **v1.13 재채점 이후의 변화**다 — 재조립된 train에서 재채점 v1.14를 요청받으면 그 자리에 적는다(이 문서는 점수를 바꾸지 않는다).
