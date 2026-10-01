---
doc_id: "TARGET-S11-AC11-ACCESSIBILITY-USER-DEVICE-V1"
title: "S11 AC-11 hosted 자동 측정 + 사용자 기기 수동 인수 target v1"
version: "1.1.1"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-02T06:23:06+09:00"
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

## 5. v1.1 증명 범위와 수동 수행 절차

수동 기록의 `performedBy.binding=self-attested-session`은 기록 작성자의 자기 진술이다. importer가 검증하는 fresh MFA access token은 **수동 수행 뒤 import를 승인한 운영자 세션**만 증명한다. 토큰은 수동 시나리오를 실제로 수행한 사람, 기기 소유자, 또는 수행 중 세션을 증명하지 않는다. 저장소에 운영자 subject/role 정본 registry가 없으므로 caller가 제공하는 allowlist를 신뢰하지 않으며, subject는 SHA-256으로만 기록한다. 이 한계를 넘어서는 주장은 금지한다.

fresh-auth의 `auth_time`과 검증 시각은 수동 `finishedAt` 이상이어야 한다. 수동 `startedAt`은 exact-SHA hosted producer의 `finishedAt` 이상이어야 한다. 손으로 작성한 receipt는 입력 계약이 아니며, 제품 token verifier가 같은 importer 프로세스에서 만든 sealed receipt만 허용한다.

| scenarioId | 수행 단계 | PASS 기준 |
|---|---|---|
| `ACC-MANUAL-KEYBOARD-JOURNEY` | 키보드만으로 로그인 뒤 대표 탐색·조회·주요 동작을 수행한다. | 모든 조작 요소에 도달·실행 가능하고 keyboard trap이 없으며 focus가 항상 보인다. |
| `ACC-MANUAL-SCREEN-READER-NAVIGATION` | screen reader로 landmark·heading·control·status를 순서대로 탐색한다. | 이름 없는/중복되어 구분 불가능한 control이 없고 상태 변경을 인지할 수 있다. |
| `ACC-MANUAL-SCREEN-READER-ERRORS` | 시험 계정에서 validation/권한 거부를 의도적으로 발생시킨다. | 오류가 한 번 명확히 읽히고 focus가 actionable summary/control로 이동하며 비밀·raw body를 읽지 않는다. |
| `ACC-MANUAL-FOCUS-ORDER` | Tab/Shift+Tab으로 전·역방향 이동하고 modal을 열고 Escape로 닫는다. | 순서가 시각·논리 순서와 같고 modal 밖으로 새지 않으며 닫은 뒤 trigger로 복귀한다. |
| `ACC-MANUAL-ZOOM-REFLOW` | 200% zoom(또는 1280 CSS px에서 400% 동등 조건)으로 대표 화면을 사용한다. | 콘텐츠에 양방향 scroll이 필요 없고 핵심 control/text가 잘리거나 겹치지 않는다. |
| `ACC-MANUAL-COGNITIVE-ERROR-RECOVERY` | 잘못된 입력 뒤 안내에 따라 수정·재시도한다. | 안내와 오류가 수정까지 유지되고 숨은 상태 손실·중복 제출 없이 복구된다. |

template의 `NOT_RUN`은 의도적으로 schema에 통과하지 않는 안전 기본값이다. 실제 수행 후 각 결과와 `overallResult`를 `PASS` 또는 `FAIL`로 바꿔야 한다. 대소문자와 무관한 `REPLACE_WITH_`·`TODO`·`TBD`·`placeholder`, angle-bracket placeholder, secret-like 문자열, 비엄격 timestamp, 2026-10-02T00:00:00Z 이전 수동 시작은 거부한다. 지원되는 신뢰 경계는 stdin token을 받는 CLI이며 underscore-prefixed Python helper는 이미 신뢰된 같은 프로세스의 시험 seam이지 Evidence 입력 API가 아니다.
