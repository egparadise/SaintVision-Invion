---
doc_id: "HISTORY-2026-10-02-CARD211-VFCL-CI-ATTESTATION-CODEX"
title: "Card 211 VF-CL CI receipt attestation"
version: "1.0.0"
status: "in-progress"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-02T07:24:06+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "d0b2a4c6"
tags: ["history", "vf-cl", "ci", "attestation"]
---

# Card 211 VF-CL CI receipt attestation

## 선택 근거

`#295`는 `ciVerified=false`를 유지한 이유를 “offline receipt와 자체 digest는 위조 후 다시 봉인할 수 있다”로
고정했고, 권위 있는 CI attestation을 후속으로 남겼다. 외부 서비스 자격이나 물리 장비 없이 GitHub-hosted
runner에서 닫을 수 있으므로 train 14 후보 `d0b2a4c6` 위에 `#295`와 `#302`를 순서대로 stack했다.

## 구현

- `.github/workflows/s12-acceptance-evidence.yml`: workflow_dispatch-only attestation job, job 수준 최소 권한,
  current-run Evidence artifact download/API 대조, `actions/attest@v4`, exact source verifier를 추가했다.
- `tools/create_vf_cl_ci_attestation_receipt.py`: runner 환경과 Actions API에서만 권위 receipt를 만든다.
- `tools/verify_vf_cl_ci_attestation.py`: bundle·GitHub identity·source SHA/ref·receipt bytes를 fail closed로 검증한다.
- `tools/check_vf_cl_registry.py`: 검증된 attestation만 true를 허용한다. 구현만 있는 tree에는 authoritative
  bundle이 없으므로 manifest와 registry는 false를 유지한다.
- 카드 205의 사용자 Windows Python 3.10 단계는 download/ZIP까지만 담당하고, importer는 agent의 지원
  Python 3.12/3.14에서 실행하도록 `#302`에 선반영했다.

## 검증 상태

- `tests/test_vf_cl_ci_attestation.py`: receipt/attestation/workflow 권한 경계 focused PASS.
- `tests/core/test_check_vf_cl_registry.py`: rule 7 fail-closed와 shipped manifest 회귀를 검증 중이다.
- exact-head hosted attested run은 구현 push 뒤 실행하며, run ID와 artifact digest는 결과가 나온 뒤 이 절에
  추가한다. 그 전에는 `ciVerified`를 올리지 않는다.
