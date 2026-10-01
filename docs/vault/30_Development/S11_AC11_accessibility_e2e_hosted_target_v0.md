---
doc_id: "TARGET-S11-AC11-ACCESSIBILITY-E2E-HOSTED-V0"
title: "S11 AC-11 accessibility-e2e hosted 측정 target v0"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-01T13:09:22+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "7851412db792b4ef6c53cb92944be530d77eb2de"
task_ids: ["S11-BE", "S11-FE"]
tags: ["ac-11", "accessibility", "e2e", "hosted", "target", "browser"]
---

# S11 AC-11 accessibility-e2e hosted 측정 target v0

## 0. 선택 근거

[[S11-BE_DB_AC-11_통합_인수_설계]]의 필수 8축과 현재 tree를 대조했다. 이 카드는
이미 구현된 migration·security 측정기를 중복하지 않고, 외부 물리 자원 없이 hosted에서
실제 측정할 수 있으나 AC-11 집계 입력이 없던 `accessibility-e2e`를 선택한다.

| 필수 축 | 기존 측정 수단 | 외부 전제 | 이 카드 |
|---|---|---|---|
| migration-reversible-segment | `tools/run_ac11_migration_rehearsal.py`와 opt-in lane | 없음 | 중복 구현 안 함 |
| irreversible-restore-forward | 같은 migration rehearsal의 restore-forward | 없음 | 중복 구현 안 함 |
| actual-pitr-rpo-rto-retention | readiness·same-host rehearsal은 참고 전용 | 별도 장애 영역·운영 archive·주간 반복 | `BLOCKED_EXTERNAL` |
| physical-five-node-ac05-placement-load | 합성 hosted rung은 참고 전용 | eligible Node 4 + CP 동거 제외 1 | `BLOCKED_EXTERNAL` |
| physical-five-node-failure-recovery | 합성 recovery는 참고 전용 | 물리 전원·네트워크·디스크 장애 | `BLOCKED_EXTERNAL` |
| long-soak | target/importer는 있으나 물리 composite report 필요 | 24시간 5노드·외부 observer | `BLOCKED_EXTERNAL` |
| security-critical-high-zero | `tools/run_ac11_security_scan.py`와 opt-in lane | credential 없음 | 이미 측정 수단 존재 |
| accessibility-e2e | desktop browser journey와 invariants producer는 있으나 AC-11 collector 없음 | 자동 부분은 hosted 가능; 최종 사용자 장비 인수는 외부 | **이 카드에서 측정** |

선행 기준 SHA는 train 5 `7851412db792b4ef6c53cb92944be530d77eb2de`다. 점수,
task status와 AC-11 완료 판정은 이 target의 범위가 아니다.

## 1. 입력과 동일 SHA 결속

hosted collector는 동일한 full `sourceHeadSha`에서 다음 두 자동 입력을 요구한다.

1. `.github/workflows/desktop-browser.yml`의 정본 VF invocation이 만든 browser proof와
   private case identity. 정본 journey는 정확히 5개이며 failure/error/skip이 없어야 한다.
2. `tools/run_real_browser_acceptance.py --scenario desktop-ui-invariants`가 만든
   `desktop_ui_invariants.json`. 정확히 9 invariant와 DOM contrast 3건을 요구한다.

각 입력의 SHA-256, source head, 시작·종료 시각, runner 환경과 clean checkout을 기록한다.
raw JUnit, screenshot, parameter 값, URL query, token·cookie는 정본 Evidence JSON에 넣지
않는다. 알 수 없는 key·중복 identity·count 불일치는 `INVALID_RUN`이다.

## 2. 사전 등록 metric

| metric | operator | target | 분모와 실패 규칙 |
|---|---:|---:|---|
| `canonicalJourneyFailureCount` | eq | 0 | 정본 journey 5개; failure/error/skip 각 1건을 실패 1건으로 센다 |
| `desktopInvariantFailureCount` | eq | 0 | invariant 9개; `false`, `PARTIAL`, 누락을 실패로 센다 |
| `contrastFailureCount` | eq | 0 | DOM computed-style contrast 3개; AA 미달·누락을 실패로 센다 |
| `keyboardFailureCount` | eq | 0 | Alt+Tab navigation과 modal Escape+trigger focus 복원 2개 |
| `manualAcceptanceMissingCount` | eq | 0 | 같은 SHA의 사용자 장비 키보드·스크린리더 인수 1건; hosted-only run은 1 |

마지막 metric은 미관측 수동 인수를 자동 PASS로 바꾸지 않기 위한 fail-closed 분모다.
따라서 이 카드의 hosted run은 자동 결함 또는 수동 인수 부재를 정직하게
`MEASURED_FAIL`로 만들 수 있으며, 그것도 측정 수단이 작동한 결과다. 동일 SHA의 정식
수동 인수 producer/importer가 생기기 전에는 `MEASURED_PASS`, AC-11 done, S11-BE 점수
승격을 주장하지 않는다.

## 3. verdict

- 입력과 provenance가 완전하고 다섯 metric이 모두 목표를 만족하면 `MEASURED_PASS`.
- 입력과 provenance가 완전하지만 목표 위반이 하나 이상이면 `MEASURED_FAIL`.
- browser 실행·report가 없거나 도구 자체가 실행되지 않았으면 `NOT_OBSERVED`.
- source/tree·identity·digest·count·schema가 불일치하면 `INVALID_RUN`.
- 수동 인수 report가 없다는 사실은 이 target에서는 관측된 completeness failure이며
  `manualAcceptanceMissingCount=1`; 자동 PASS로 세지 않는다.

## 4. 부정 시험

- journey 하나 누락·추가·skip, private identity digest 불일치
- invariant 하나 누락, `PARTIAL`을 PASS로 변환, summary count 위조
- contrast result 하나 누락 또는 ratio/threshold 불일치
- modal dismiss만으로 focus 복원을 PASS 처리
- source SHA·tree SHA drift, dirty checkout, report digest drift
- 수동 인수 없이 missing count를 0으로 기록
- producer verdict를 집계 결과로 그대로 신뢰

## 5. 실행 경계

workflow는 `workflow_dispatch` 또는 명시 label에서만 실행하고 PR head를 exact checkout한다.
job concurrency는 `cancel-in-progress:false`, credential은 0, artifact는 30일 보존한다.
기본 frontend/backend/Core job과 skip map은 바꾸지 않는다. 로컬·물리 5노드와 수치를
직접 비교하지 않으며, 이 카드에서 score·registry task status를 바꾸지 않는다.

## 6. 자동화 범위와 미측정 항목

- canonical browser 입력은 물리 test case 6건이다. `test_full_studio_login_project_approval_and_logout`의 두 parameter case를 하나의 논리 journey로 묶으므로 논리 journey는 5건이다. collector는 물리 case의 정확한 multiplicity와 JUnit 결과를 함께 검증한다.
- desktop invariant producer가 자동 측정하는 접근성 범위는 computed-style 대비 3건과 keyboard/focus 2건뿐이다.
- ACC-01~09 전체, 화면낭독기 발화, 사용자 장비 키보드 흐름, 인지 접근성은 이 hosted 자동화로 측정하지 않는다. 같은 SHA의 별도 producer/importer가 생기기 전에는 `manualAcceptanceMissingCount=1`을 유지한다.
- `MEASURED_PASS` 또는 `MEASURED_FAIL`은 위 자동화 범위에만 적용하며 사용자 접근성 인수 완료나 AC-11 전체 완료를 뜻하지 않는다.
