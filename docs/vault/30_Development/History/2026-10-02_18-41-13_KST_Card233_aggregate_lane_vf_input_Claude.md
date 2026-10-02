---
doc_id: "HISTORY-CARD233-AGGREGATE-LANE-VF-INPUT-20261002"
title: "카드 233 — 집계 lane이 브라우저 artifact를 security importer에 넘긴다. 그 lane의 봉투에 SEC-VF-001이 처음으로 들어왔다"
version: "1.1.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T19:36:10+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "74035b39"
task_ids: ["S11-BE"]
tags: ["ac11", "security", "aggregate-lane", "sec-vf-001", "claude"]
---

# 카드 233 — 집계 lane의 VF 입력

## 0. 한 줄

`SEC-VF-001`은 브라우저 lane의 artifact에서 온다. importer에 그 입력을 주면 `MEASURED_PASS`인데 **집계 lane은 그것을 주지 않았다** — 셋(`--archive`·`--run-metadata`·`--artifact-metadata`)만 넘겼으므로 그 lane이 만드는 봉투에는 네 threat report 중 **하나가 아예 없었다**(`#319` r2에서 보고, v1.12 §4-9-3이 그 자리를 적었다). 이 판은 **발견 도구 하나, 문서 계약 하나, 축 map의 한 필드, lane의 한 분기**로 그것을 닫았고, 실제 집계 lane run에서 **봉투에 `SEC-VF-001: MEASURED_PASS`가 들어온 것**을 측정했다.

## 1. 네 조각

| 무엇 | 역할 |
|---|---|
| `tools/find_ac11_vf_evidence.py` | 같은 source SHA에서 브라우저 lane의 **한 증거**(§3-1)와 **정확히 하나**의 artifact를 찾아 셋을 내려받고 문서를 쓴다. **검증은 하지 않는다** |
| `--vf-evidence`(importer) | `ac11-vf-evidence:1` 문서 하나로 그 셋을 받는다. **exact key 집합**, 검토된 repository·workflow, 그리고 문서가 적은 `runId`·`artifactId`가 **그 metadata 파일의 id와 같아야** 한다 |
| `docs/ac11-axis-sources.json`의 `supplementalEvidence` | 그 축이 **두 번째 artifact를 필요로 한다는 사실**과 **누가 찾는지**를 정본 map에 적는다(exact key 셋, `complete` 사슬에만 허용) |
| `.github/workflows/ac11-aggregate.yml` | TSV 한 줄에 finder·flag·threatId를 더 실어, 있으면 finder를 돌리고 성공하면 `--vf-evidence`로 넘긴다 |

**검증을 finder에 넣지 않은 것이 설계의 핵심**이다. run·head·tree(`head_commit.tree_id`)·repository·workflow·event·conclusion·artifact 이름·bytes에서 재계산한 digest·만료는 `#319`가 importer의 `vf_report()`에 **한 번** 적어 두었고, finder가 그것을 다시 적으면 규칙이 둘이 된다. finder의 계약은 "후보가 하나임"과 "내려받음"까지다.

## 2. 못 찾으면 조용히 빠지지 않는다

finder의 exit code가 **답과 실패를 가른다**: `3`은 "이 SHA에 증거가 없다"(lane은 계속한다), `2`는 도구·환경이 실패한 것(lane이 그 사실을 적는다), `0`은 문서를 썼다. lane은 셋을 구분해 로그에 적고, 못 찾으면 `evidence/ac11-supplemental-missing.txt`에 **threat id와 사유**를 남긴다. 그 report는 **importer의 사유 문장에도 이름으로 남는다** — 봉투의 `reason`이 `no admissible report for SEC-VF-001`을 적기 때문이다. 즉 빠지는 경우에도 **이름이 남는 자리가 둘**이다.

## 3. 측정 — 실제 집계 lane run

세 lane을 이 branch의 head에서 차례로 돌렸다.

| lane | run | 결과 |
|---|---|---|
| security scan | **`36990773119`** | success |
| desktop browser (VF) | **`36990776530`** | success, artifact `11219368648` |
| **ac11-aggregate** | **`36991010286`** | success |

그 집계 lane이 만든 봉투(artifact `11219013523`의 `ac11-axes/import_ac11_security_scan.json`):

```
threatReportVerdicts: {"SEC-SCAN-001": "MEASURED_PASS", "SEC-VF-001": "MEASURED_PASS"}
observations: SEC-SCAN-001 run 36990773119 · SEC-VF-001 run 36990776530   (tree 5224217b 둘 다)
reason: no admissible report for SEC-DEF-001, SEC-RLS-001;
        refused by the canonical evaluator: SEC-DEF-001 (INVALID_RUN), SEC-RLS-001 (INVALID_RUN)
```

`SEC-VF-001`의 `vfArtifact` 블록이 적는 것: workflow `.github/workflows/desktop-browser.yml`, run `36990776530`, artifact `11219368648`, **GitHub digest == 내려받은 bytes의 재계산**, 만료 `2026-10-16T09:38:45Z`, proof의 `tests {failure 0, error 0, skipped 0, passed 6}`·`evidenceStatus complete`.

**이것이 이 카드의 결과다**: 그 lane의 봉투에 `SEC-VF-001`이 **처음으로** 들어왔고, 그 provenance는 **브라우저 run 자신의 것**이다(scan run이 아니다).

| 그 밖의 결과 | 값 |
|---|---|
| 축 verdict | `NOT_OBSERVED` — DEF·RLS가 아직 inadmissible하므로 (바뀌지 않았다) |
| `assembledAxes` | `["security-critical-high-zero"]` |
| 집계 결과 | `INVALID_RUN`, `done: false`, 사유는 **일곱 축 absent** |
| `SEC-DEF-001` | `INVALID_RUN` — 검토된 allowlist의 서명 12 vs 관측 15(카드 221 §3의 검토 공백) |
| `SEC-RLS-001` | `INVALID_RUN` — **census가 stale**이다. 이 branch는 train 22 위이고 그 수정은 **카드 234**(train 23)가 한다. 그쪽에서 hosted로 `NOT_OBSERVED`로 바뀐 것을 이미 측정했다 |

즉 **점수는 바뀌지 않는다**(`S11-BE`는 여덟 축의 재계산 PASS를 요구한다). 바뀐 것은 그 축의 네 report 중 **둘이 admissible**이 되었다는 것이고, 남은 둘은 각각 **검토 결정**과 **카드 234**다.

## 3-1. r2 재측정 — 한 head에 브라우저 run이 둘일 때

§3의 측정 다음에 `#332` r2(중복 key 거부)를 밀어 넣고 같은 세 lane을 다시 돌렸다. 그 집계 run **`36993502607`**의 봉투에서 **`SEC-VF-001`이 다시 빠졌다**. 조용히 빠지지는 않았다 — `evidence/ac11-supplemental-missing.txt`가 사유를 적었다:

```
SEC-VF-001 NOT_OBSERVED: no browser lane evidence at bf4710be…:
  expected exactly 1 successful .github/workflows/desktop-browser.yml run at bf4710be… from
  ['workflow_dispatch', 'pull_request'], found 2
```

**§2의 기계는 작동했고, §1의 규칙이 과했다.** branch를 push하면 `pull_request` run(`36993193630`)이 돌고 거기에 dispatch(`36993192700`)를 더하면 **같은 head에 성공한 run이 둘**이다. 흔한 상황이고, 그때마다 축의 네 report 중 하나가 빠진다.

**digest 동치로는 풀리지 않는다 — 그 둘을 실제로 내려받아 비교했다.**

| 무엇 | dispatch `36993192700` | pull_request `36993193630` |
|---|---|---|
| artifact digest | `sha256:6b7d5e05…` | `sha256:308d8e3d…` (24595 vs 24596 bytes) |
| `web-container-studio.png` | `42320154392e8714` | **같다** |
| `vf-desktop-browser-ci.json` | `3fdf42f4e15716e6` | 다르다 |
| 다른 필드 | `runId` uuid, `startedAt`/`finishedAt`, 그 uuid로 만든 `evidencePath`·`xmlPath`·`--junitxml`, durations가 다른 JUnit의 `xmlSha256` | 같음 |
| **보고서가 주장하는 필드** | `caseIdentitiesSha256`·`tests`·`evidenceStatus`·`exitCode`·`subprocessExitCode` | **전부 동일** |

그래서 비교 대상을 **보고서가 주장하는 것**으로 바꿨다. importer가 `VF_DECISIVE_FIELDS`로 그 다섯을 선언하고(`vf_report`가 검토 allowlist와 대조하고 기록하는 바로 그 필드들), `vf_required(spec)`가 그 둘이 어긋나면 거부하고, `vf_decisive(proof)`가 **없는 필드에 기본값을 주지 않고 이름을 들어 거부**한다. finder는 후보들의 archive에서 그 필드만 읽어 비교한다 — 전부 같으면 **가장 작은 run id**(순서 무관·재현 가능, importer가 그 run을 전부 검증한다), 하나라도 다르면 **거부**(두 관측 중 무엇을 믿을지 고르는 일은 이 도구의 일이 아니다). 후보가 1건이면 비교 대상이 없어 내려받지 않는다.

**그 규칙으로 다시 측정했다** (head `0ae51b91`, 두 후보가 실제로 존재하는 상태):

| lane | run | 결과 |
|---|---|---|
| security scan | **`36995699449`** | success (dispatch) |
| desktop browser | **`36995690211`** | success (**pull_request**), artifact `11222185284` |
| desktop browser | **`36995702374`** | success (**workflow_dispatch**), artifact `11220719855` |
| **ac11-aggregate** | **`36996015577`** | success, artifact `11222215498` |

두 artifact의 digest는 또 달랐다(`bd8d901b…` vs `099adbc7…`, 24596 vs 24593 bytes) — 그런데 결정 필드는 같았으므로 finder는 **더 작은 run id**를 골랐다:

```
threatReportVerdicts: {"SEC-SCAN-001": "MEASURED_PASS", "SEC-VF-001": "MEASURED_PASS"}
SEC-VF-001 sourceRunId 36995690211 · artifactId 11222185284
           digest == observedDigest == bd8d901b…  (bytes에서 재계산)
           tree ef604f00 · expiresAt 2026-10-16T10:30:57Z
ac11-supplemental-missing.txt: 없음
```

**결론**: 한 head에 브라우저 run이 둘이어도 봉투는 `SEC-VF-001`을 싣는다. 그리고 §6이 "코드로만 확인했다"고 적었던 **못 찾는 경로는 그 사이에 hosted에서 실측됐다**(`36993502607`) — 그 측정이 바로 이 규칙 변경을 찾아낸 것이다.

### 변이

| 변이 | 결과 |
|---|---|
| 가장 작은 run id가 아니라 도착 순서대로 고른다 | 사살 |
| 두 번째 후보만 비교한다(세 번째를 읽지 않는다) | 사살 |
| 불일치를 무시한다 | 사살 |
| 후보 1건도 비교한다(불필요한 다운로드) | 사살 |
| 뒤 후보의 artifact 개수를 확인하지 않는다 | 사살 |
| 고른 archive를 다시 내려받는다 | 사살 |
| 없는 결정 필드를 동치로 본다 | 사살 |
| 검토 필드가 선언 목록과 어긋나도 통과시킨다 | 사살 |
| 결정 mapping이 proof 전체를 흘린다 | 사살 |
| **합계** | **9/9 사살, 생존 0** |

`ordered[1:]`을 `reversed(ordered)[:-1]`로 바꾸는 변이는 **비교 집합이 같다**(거부 메시지에서 어느 run이 먼저 불리는지만 바뀐다). 등가 변이로 보고하고 사살로 세지 않았다.

**변이 harness에서 찾은 내 실수 하나**: 첫 sweep을 `--timeout 300`과 함께 돌렸는데 이 checkout에 `pytest-timeout`이 없어 **pytest가 usage error(exit 4)로 거부**했고, "exit != 0 == 사살"로 읽은 harness가 **9건 전부 사살**이라고 보고했다. baseline을 같은 명령으로 돌려 보고 알아차렸다. harness를 exit 1만 사살로 세고 4는 즉시 중단하도록 고친 뒤 다시 돌리니 **생존 2건**이 나왔고(§3-1의 셋째·다섯째 행), 그 둘에 시험을 더해 닫았다.

## 4. 시험

| 파일 | 무엇 |
|---|---|
| `tests/test_find_ac11_vf_evidence.py`(신설, **40**) | 후보가 0건·다른 head·실패·미완·승인되지 않은 event·id 없음을 **전부 거부**, 결정 필드별 **불일치 sweep**과 **누락 sweep**(각 5건), 세 번째 후보까지 비교, **digest가 달라도 수용됨**을 실제 run-local 값으로 단언, 후보 1건은 내려받지 않음, 뒤 후보의 artifact도 정확히 1개, 문서가 importer의 요구와 **정확히 같은 key 집합**, `main`이 두 후보 end-to-end(다운로드 2회·선택 run 재다운로드 없음)와 exit 0/2/3 **구분**, 그리고 **그 문서를 importer가 실제로 받아들인다** |
| `tests/test_import_ac11_security_scan.py`(신설 **28**, 전체 110) | `--vf-evidence`가 셋을 넘긴 것과 **같은 봉투**를 낸다, 필수 key 제거·여분 key·**중복 key**(모든 입력 문서의 모든 수준 자동 순회) sweep, schema·repository·workflow 위조, **문서가 적은 id와 metadata의 id가 다른 두 경우**, 없는 archive, 문서와 개별 flag를 함께 주면 거부, 그리고 **검토 필드 == `VF_DECISIVE_FIELDS`**·결정 필드 누락 sweep |
| `tests/core/test_assemble_ac11_manifest.py`(신설 4, 전체 75) | `supplementalEvidence`의 exact key, 모르는 threat id, flag가 아닌 값, tree에 없는 finder, `complete`가 아닌 사슬에 붙은 경우, 그리고 **정본 map에서 그 필드를 가진 행이 security 하나뿐** |
| 합계 | 네 suite **363 passed**(finder 40 · importer 110 · manifest 75 · aggregator 138) |

**lane의 shell도 검사했다**: 집계 lane의 shell block **여섯 개 전부 `bash -n` exit 0**(추출해 실제로 돌렸다).

## 5. 측정하다 알게 된 것

1. **`gh run list --json`에는 `path`가 없다**(이름을 거부하고 가진 열다섯을 출력한다). 그래서 finder는 `--workflow <basename>`으로 고르고, **workflow 경로 자체는 importer가** run metadata에서 검토된 allowlist와 대조한다 — 한 정의가 유지된다.
2. **Windows의 `CreateProcess`는 bare 이름에 `.exe`만 붙인다**(PATHEXT를 쓰지 않는다). 그래서 PATH에 `gh`/`gh.cmd` shim을 두는 방식은 Python subprocess에서 닿지 않고 **실제 `gh.exe`가 답한다** — run list가 빈 것이 그 증거였다. finder 시험은 그래서 두 helper를 in-process로 교체한다(그 이유를 fixture docstring에 적었다).
3. **이전 artifact로는 재측정할 수 없다** — importer 파일이 바뀌면 `#313` F-R3의 결속이 옛 artifact를 거부한다. 그래서 세 lane을 새 head에서 다시 돌렸다(카드 221·#319와 같은 패턴).

## 6. 하지 않은 것

- **검증을 finder에 복제하지 않았다**(§1).
- **AC-11 정의를 바꾸지 않았다** — `s11-security-allowlist-v0.json`도 target registry도 건드리지 않았다. `supplementalEvidence`는 **축 map**의 필드이고 그 map은 "이 chain에서 무엇이 집계기로 들어가는가"를 적는 파일이다.
- **DEF·RLS를 고치지 않았다** — 각각 검토 결정과 카드 234다.
- **~~`못 찾음`의 hosted 경로를 실측하지 않았다~~** — r2에서 실측됐다(§3-1, 집계 run `36993502607`의 `ac11-supplemental-missing.txt`). 그 측정이 §1의 "정확히 1건" 규칙이 과하다는 것을 찾아냈다.
- **event로 후보를 고르지 않았다**: "dispatch가 pull_request보다 우선" 같은 선언적 우선순위도 가능했지만, 그것은 **두 관측 중 하나를 고르는 규칙**이다. 같은 관측임을 확인한 다음 **가장 작은 run id**를 쓰는 쪽을 택했다(재현 가능하고, 무엇을 믿을지 고르지 않는다).
- **JUnit XML과 PNG를 비교에 넣지 않았다**: 봉투가 주장하는 것은 proof의 결정 필드이고, 고른 후보의 archive는 importer가 digest 재계산까지 전부 검증한다. XML의 `time`·`timestamp`는 run마다 다르므로 비교에 넣으면 **정상 상황을 거부**한다.

## 7. 다음 첫 행동

1. **Codex**: 이 PR 검토.
2. **allowlist owner**: `SEC-DEF-001`의 서명 12 vs 15 — 그것이 닫히면 이 축의 네 report 중 셋이 admissible이 된다.
3. **Claude**: 카드 234가 착지하면 같은 집계 lane run에서 `SEC-RLS-001`도 admissible해지는지 재측정.
4. **Claude**: 카드 236(빈 audit 표) — `SEC-RLS-001`의 마지막 미측정 행.
