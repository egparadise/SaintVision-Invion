---
doc_id: "HISTORY-CARD233-AGGREGATE-LANE-VF-INPUT-20261002"
title: "카드 233 — 집계 lane이 브라우저 artifact를 security importer에 넘긴다. 그 lane의 봉투에 SEC-VF-001이 처음으로 들어왔다"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T18:41:13+09:00"
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
| `tools/find_ac11_vf_evidence.py` | 같은 source SHA에서 **정확히 하나**의 브라우저 lane run과 **정확히 하나**의 artifact를 찾아 셋을 내려받고 문서를 쓴다. **검증은 하지 않는다** |
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

## 4. 시험

| 파일 | 무엇 |
|---|---|
| `tests/test_find_ac11_vf_evidence.py`(신설, 22) | 선택이 0건·2건·다른 head·실패·미완·승인되지 않은 event·id 없음을 **전부 거부**(고르지 않는다), 문서가 importer의 요구와 **정확히 같은 key 집합**, `main`이 셋을 쓰고 문서를 남기며 exit 0/2/3을 **구분**, 그리고 **그 문서를 importer가 실제로 받아들인다** |
| `tests/test_import_ac11_security_scan.py`(신설 12) | `--vf-evidence`가 셋을 넘긴 것과 **같은 봉투**를 낸다, 필수 key를 하나씩 제거하는 sweep, 여분 key, schema·repository·workflow 위조, **문서가 적은 id와 metadata의 id가 다른 두 경우**, 없는 archive, 그리고 **문서와 개별 flag를 함께 주면 거부** |
| `tests/core/test_assemble_ac11_manifest.py`(신설 4) | `supplementalEvidence`의 exact key, 모르는 threat id, flag가 아닌 값, tree에 없는 finder, `complete`가 아닌 사슬에 붙은 경우, 그리고 **정본 map에서 그 필드를 가진 행이 security 하나뿐** |
| 합계 | 네 suite **325 passed** |

**lane의 shell도 검사했다**: 집계 lane의 shell block **여섯 개 전부 `bash -n` exit 0**(추출해 실제로 돌렸다).

## 5. 측정하다 알게 된 것

1. **`gh run list --json`에는 `path`가 없다**(이름을 거부하고 가진 열다섯을 출력한다). 그래서 finder는 `--workflow <basename>`으로 고르고, **workflow 경로 자체는 importer가** run metadata에서 검토된 allowlist와 대조한다 — 한 정의가 유지된다.
2. **Windows의 `CreateProcess`는 bare 이름에 `.exe`만 붙인다**(PATHEXT를 쓰지 않는다). 그래서 PATH에 `gh`/`gh.cmd` shim을 두는 방식은 Python subprocess에서 닿지 않고 **실제 `gh.exe`가 답한다** — run list가 빈 것이 그 증거였다. finder 시험은 그래서 두 helper를 in-process로 교체한다(그 이유를 fixture docstring에 적었다).
3. **이전 artifact로는 재측정할 수 없다** — importer 파일이 바뀌면 `#313` F-R3의 결속이 옛 artifact를 거부한다. 그래서 세 lane을 새 head에서 다시 돌렸다(카드 221·#319와 같은 패턴).

## 6. 하지 않은 것

- **검증을 finder에 복제하지 않았다**(§1).
- **AC-11 정의를 바꾸지 않았다** — `s11-security-allowlist-v0.json`도 target registry도 건드리지 않았다. `supplementalEvidence`는 **축 map**의 필드이고 그 map은 "이 chain에서 무엇이 집계기로 들어가는가"를 적는 파일이다.
- **DEF·RLS를 고치지 않았다** — 각각 검토 결정과 카드 234다.
- **`못 찾음`의 hosted 경로를 실측하지 않았다**: 이 run에서는 finder가 **찾았다**. 찾지 못하는 경로는 시험 네 건(0건·2건·artifact 0건·artifact 2건)과 exit code 구분으로 고정했고, lane이 그때 무엇을 적는지는 코드로만 확인했다.

## 7. 다음 첫 행동

1. **Codex**: 이 PR 검토.
2. **allowlist owner**: `SEC-DEF-001`의 서명 12 vs 15 — 그것이 닫히면 이 축의 네 report 중 셋이 admissible이 된다.
3. **Claude**: 카드 234가 착지하면 같은 집계 lane run에서 `SEC-RLS-001`도 admissible해지는지 재측정.
