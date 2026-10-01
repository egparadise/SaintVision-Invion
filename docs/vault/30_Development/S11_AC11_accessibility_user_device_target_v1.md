---
doc_id: "TARGET-S11-AC11-ACCESSIBILITY-USER-DEVICE-V1"
title: "S11 AC-11 hosted 자동 측정 + 사용자 기기 수동 인수 target v1"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-02T05:31:32+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S11-BE", "S11-FE"]
tags: ["ac-11", "accessibility", "e2e", "manual-acceptance", "user-device"]
---

# S11 AC-11 hosted 자동 측정 + 사용자 기기 수동 인수 target v1

## 1. 입력과 신뢰 경계

이 target은 동일한 exact `sourceHeadSha`에 결속된 두 입력을 하나의 AC-11 축 Evidence로 합친다.

1. `.github/workflows/ac11-accessibility-e2e.yml`의 hosted 자동 산출물.
2. 사용자 기기에서 수행한 6개 수동 시나리오 기록. 수동 기록만으로 사람을 주장하지 않는다. importer 실행 시 `inv.identity.AccessTokens`가 access token의 서명·issuer·audience·client·만료를 검증하고, `has_fresh_interactive_auth`가 300초 freshness와 허용 AMR 조합을 판정해야 한다. 토큰은 stdin으로만 받고 저장·출력하지 않는다.

Evidence에는 subject·issuer·client·tenant의 SHA-256, 검증된 `auth_time`·AMR·token expiry와 JWKS bundle SHA-256만 남긴다. 원문 token, cookie, email, 이름, 기기 serial, 자유 서술은 금지한다. 서비스 계정과 client-credentials token은 fresh interactive auth를 충족하지 못하므로 거부한다.

## 2. 사전 등록 metric

| metric | operator | target | 실패 규칙 |
|---|---:|---:|---|
| `canonicalJourneyFailureCount` | eq | 0 | hosted canonical journey의 failure/error/skip |
| `desktopInvariantFailureCount` | eq | 0 | 9개 invariant의 false/partial/누락 |
| `contrastFailureCount` | eq | 0 | 3개 자동 대비 측정의 미달/누락 |
| `keyboardFailureCount` | eq | 0 | 자동 keyboard/focus 측정 실패 |
| `manualAcceptanceMissingCount` | eq | 0 | 동일 SHA의 strict 수동 기록이 없거나, 6개 시나리오 중 하나라도 FAIL이거나, fresh-auth 결속이 유효하지 않음 |

수동 실패를 누락과 구분해 `errorsByClass=manual-acceptance-failed`로 보존하되 target 값은 1이다. 즉 실패 기록을 제출해도 PASS로 바뀌지 않는다. importer는 producer verdict를 신뢰하지 않고 위 관측을 재계산한다.

## 3. 필수 수동 시나리오

- `ACC-MANUAL-KEYBOARD-JOURNEY`
- `ACC-MANUAL-SCREEN-READER-NAVIGATION`
- `ACC-MANUAL-SCREEN-READER-ERRORS`
- `ACC-MANUAL-FOCUS-ORDER`
- `ACC-MANUAL-ZOOM-REFLOW`
- `ACC-MANUAL-COGNITIVE-ERROR-RECOVERY`

정확히 한 번씩 있어야 하며 screen reader 제품·버전 관측이 필수다. 모든 결과가 PASS일 때만 `manualAcceptanceMissingCount=0`이다. FAIL은 측정된 실패이며, NOT_RUN·SKIP·UNKNOWN은 schema 위반이다.

## 4. 판정과 외부 경계

- provenance와 schema가 완전하고 5개 metric이 모두 목표를 만족하면 `MEASURED_PASS`.
- 유효한 입력에서 하나 이상 목표를 어기면 `MEASURED_FAIL`.
- artifact 또는 사용자 기기 실행 자체가 없으면 해당 입력은 관측되지 않은 것이며 자동 PASS로 대체하지 않는다.
- SHA·artifact digest·GitHub run metadata·scenario identity·fresh-auth 결속이 틀리면 `INVALID_RUN`.

이 축의 MEASURED 상태는 AC-11 집계 입력일 뿐 사용자 전체 인수, S11 완료 또는 점수 승격을 뜻하지 않는다.
