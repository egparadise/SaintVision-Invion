---
doc_id: "GOV-CHECK-CI-WIRING-VISIBILITY-001"
title: "검사 도구 5개 CI 배선·비용·게이트 + report-only 가시성 — 막으면 늑대소년 안 막으면 무시, 그 사이"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
checked_at_tip: "94fbf7e8"
updated: "2026-09-22"
source_of_truth: "Git"
tags: ["governance", "ci", "checks", "report-only", "ratchet", "visibility"]
---

# 검사 도구 5개 CI 배선·비용·가시성

오늘 만든 검사가 다섯(내 4 + Gemini 1). 아침 확인 뒤 셋이 늘었다. 다시 배선을 확인하고, 비용·무엇을 막나, 그리고 **report-only가 실제로 읽히는가**를 본다.

## 배선 상태 (tip `94fbf7e8`, 워크플로 소스 확인)
| 검사 | 어디서 불리나 | 게이트/리포트 |
|---|---|---|
| `check_contract_bindings.py` | **docs.yml:25** ✓(아침 문안 Codex 적용됨) | 게이트(검사1·2) + 내부 dead-contract는 report-only |
| `check_frontend_integrity.py` | **docs.yml:26** ✓ | 게이트 |
| `test_serving_anchors.py` | **pytest 스위트**(backend/core가 tests/core 수집) ✓ | 게이트(스위트) |
| `check_doc_single_source.py` | **미배선** | report-only(도구; 그 test는 스위트에 있음) |
| `check_response_freshness.py` | **미배선** | report-only |

→ **미배선 2개 = report-only 도구 둘.** (serving-anchor는 test라 pytest로 이미 돌고, test_doc_single_source·test_alarm_check도 스위트가 수집한다. 미배선인 건 explicit-run이 필요한 **스크립트 도구** 둘.)

## 비용·무엇을 막나
| 검사 | 시간(측정) | 막는 것 |
|---|---|---|
| check_contract_bindings | ~2.45s(src/services 전수 스캔) | fixture-무-시험, bound 커널응답-무-서빙앵커시험 |
| check_frontend_integrity | ~0.16s | 프런트 무결성 위반 |
| test_serving_anchors(+alarm+doc test) | 스위트 내 ~1.5s | 앵커 제거·알람 양방향·doc 중복로직 |
| check_doc_single_source | ~0.17s | (report) 살아있는 문서 중복 |
| check_response_freshness | ~0.04s | (report) 신선도 필드 부재 |
- 추가 CI 시간 **무시할 수준**(도구 <3s, test는 이미 스위트). 실패 증가 위험은 게이트 3개에만 있고 그건 백로그가 없어야 정상인 것들(0이어야 맞음)이라 늑대소년 아님.

## docs.yml 문안 (Codex — YAML은 내 소관 아님)
`check_ontology` 다음에, **report-only는 run summary로 뽑아 묻히지 않게**:
```yaml
      - name: Advisory checks (report-only, surfaced to run summary)
        run: |
          { echo '### 계약/문서/신선도 advisory'; echo '```';
            python tools/check_doc_single_source.py;
            python tools/check_response_freshness.py;
            echo '```'; } | tee -a "$GITHUB_STEP_SUMMARY"
```
`tee -a $GITHUB_STEP_SUMMARY`가 run 페이지에 렌더한다(로그 파헤치지 않아도 보임). 스텝은 exit 0이라 안 막는다.

## report-only의 진짜 문제와 "그 사이" (남은 질문)
**막지 않으면 무시(로그에 묻히면 없는 것과 같다), 막으면 늑대소년.** 사람 기억이 잊히듯 report-only도 안 읽히면 잊힌다. 둘 사이에 둘을 같이 쓴다:

1. **가시성 — 묻지 말고 요약에 띄운다**: report-only 출력을 **`$GITHUB_STEP_SUMMARY`**로(위 문안). 로그 깊숙이가 아니라 run 페이지에 보인다. "안 막지만 눈에는 띈다."
2. **래칫 — 존재가 아니라 증가를 막는다**: report-only를 **베이스라인 게이트**로. 기존 백로그엔 안 울고 **새 위반이 늘 때만** 실패:
   - check_doc_single_source: 현재 18 doc-pair를 베이스라인 → 19번째에 실패.
   - dead-contract(check_contract_bindings 내부): 현재 dead 집합 → 새 dead에 실패.
   - check_response_freshness: 현재 갭 1(ShardObservation) → 2번째 신선도-필드 부재에 실패.
   증가만 막으므로 **막을 가치 있는 것(회귀)은 막고, 백로그엔 안 우니 늑대소년 아니다.**
   - **한계(같이 적음)**: 베이스라인은 커밋된 수라, **백로그를 고칠 때 내려주지 않으면 영구 바닥**이 된다(고정이지 하향-래칫 아님). 그리고 베이스라인 수 자체가 사람이 관리하는 값 = rule 6의 "표현값"이니 검사 대상에서 유도하면 안 되고 독립 고정 + 내려주는 규율이 필요.

**정리(그 사이의 답)**: **델타는 막고, 상태는 보여준다.** 래칫이 회귀를 막고(늑대소년 회피), step-summary가 백로그를 보이게 한다(무시 회피). 어느 하나만으론 막힘-또는-무시의 딜레마를 못 벗어난다.

## 권고 우선순위
- **지금(작음, Codex)**: 미배선 2개를 위 문안으로 docs.yml에 + step-summary 출력. 즉시 "보임" 확보.
- **다음(중간, 설계)**: report-only 3개(dead-contract·doc-single-source·freshness)에 **베이스라인 래칫** 추가 — 커밋된 baseline 수 + 증가 시 실패. 하향-래칫 규율(백로그 줄면 baseline도 줄임)을 문서화. 이건 도구 로직 변경이라 명세만 남기고 착수는 지시 대기(내 레인은 3개 중 내 것 2개; dead-contract는 check_contract_bindings 내부라 내 것).

관련: [[문서검사_커버리지와_갭_Claude]] · [[계약검증_자동화대판단_검사목록]] · [[2026-09-22_시간축_자동화_가능한것과_사람몫_Claude]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
