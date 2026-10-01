---
doc_id: "HISTORY-2026-10-02-CARD205-AC11-ACCESSIBILITY-MANUAL"
title: "Card 205 AC-11 사용자 기기 접근성 수동 인수 importer"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-02T05:40:06+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "9d9389a110eb7bc62351f261ae28e9482c8149ad"
task_ids: ["S11-BE", "S11-FE"]
tags: ["ac-11", "accessibility", "manual-acceptance", "evidence", "fresh-auth"]
---

# Card 205 AC-11 사용자 기기 접근성 수동 인수 importer

## 1. 선택 근거

#300 계약 검토에서 `tools/collect_ac11_accessibility_e2e.py`가
`manualAcceptanceMissingCount=1`을 항상 기록하고, 사용자가 실제 기기 인수를 수행해도 동일
SHA Evidence에 합칠 importer가 없음을 확인했다. 이는 train 13 후보 `9d9389a1`에서 물리
5노드나 추가 CP 호스트 없이 코드와 사용자 기기 절차로 닫을 수 있는 가장 앞 AC-11 공백이다.

## 2. 사전 등록과 registry

- 결과를 보기 전에 `S11_AC11_accessibility_user_device_target_v1.md`, strict JSON Schema,
  사용자 템플릿과 runbook을 commit `94970b00`에 고정했다.
- target source document blob은 `d3869f371f64fb8b76e2d5223583543e5e35092c`다.
- canonical registry commit은 `139fd976`, blob은
  `a645b8e8f5985a5cdf8eb66511ffb55c65bc1493`다.
- `accessibility-e2e`는 `s11-accessibility-user-device-v1` target만 허용한다. migration과
  long-soak importer pin도 같은 registry blob으로 함께 재고정했다.

## 3. 신뢰 경계

`tools/import_ac11_accessibility_evidence.py`는 다음을 모두 fail closed로 검사한다.

1. canonical repository/workflow, completed success run, exact `sourceHeadSha`와 numeric run ID.
2. exact artifact name, unexpired GitHub artifact metadata, ZIP SHA-256과 exact member set.
3. producer target·payload digest·5개 metric identity와 hosted 단계의 manual missing=1.
4. 수동 session의 exact 6 scenario, screen reader 관측, exact SHA, 전체 결과 재계산.
5. stdin access token을 제품 `AccessTokens`로 검증하고 canonical fresh-auth predicate로 300초
   freshness와 `mfa` 또는 `pwd+(otp|hwk|swk)`를 검증. 토큰은 출력·Evidence·argv·환경 변수에
   남기지 않고 subject/tenant/issuer/client와 JWKS의 SHA-256만 남긴다.

수동 기록이 없거나 FAIL이면 metric은 1이다. schema·SHA·provenance drift는 import 거부이며,
all PASS와 verified human receipt가 함께 있을 때만 0이다. 이것은 AC-11 한 축의 측정이지 전체
release 수락 또는 S11 완료가 아니다.

## 4. #299·#300 결속

#299는 기준 branch에 아직 없으므로 코드를 임의 merge하지 않았다. 대신
`docs/ac11-axis-sources-accessibility-patch-v1.json`에 `chain=complete`, importer,
`--archive`, artifact prefix/member, emitted axis와 envelope shape를 exact row로 기록했다.
#300은 [[AC-11_사용자_기기_접근성_수동_인수_절차]]의 템플릿·GitHub metadata 다운로드·
stdin token import 명령을 인용할 수 있다.

## 5. 검증

```text
python -m pytest tests/test_import_ac11_accessibility_evidence.py tests/test_collect_ac11_accessibility_e2e.py tests/test_aggregate_ac11_evidence.py tests/test_import_ac11_migration_rehearsal.py tests/test_import_ac11_composite_long_soak.py -q
157 passed

python -m py_compile tools/collect_ac11_accessibility_e2e.py tools/import_ac11_accessibility_evidence.py tools/aggregate_ac11_evidence.py
exit 0

python tools/import_ac11_accessibility_evidence.py --help
exit 0

python tools/check_docs.py
PASS / exit 0

python tools/check_doc_path_citations.py --ratchet --base-ref origin/coord/train13-ci-0436
PASS / 새 결함 0 / exit 0

python tools/check_contract_bindings.py
PASS / exit 0
```

부정 대조군은 가짜·다른 SHA, scenario 누락·중복, unknown key, stale/forged performer receipt,
pwd 단독, duplicate JSON key를 포함한다. 실제 사용자 기기 수행과 실제 access token import는
아직 없으므로 운영 수동 인수 결과는 `NOT_OBSERVED`다.
