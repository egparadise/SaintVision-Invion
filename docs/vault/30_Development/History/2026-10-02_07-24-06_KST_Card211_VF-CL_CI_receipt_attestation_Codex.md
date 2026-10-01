---
doc_id: "HISTORY-2026-10-02-CARD211-VFCL-CI-ATTESTATION-CODEX"
title: "Card 211 VF-CL CI receipt attestation"
version: "1.1.1"
status: "in-progress"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-02T08:23:28+09:00"
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
- Claude r1 조건에 따라 artifact 보존기간을 workflow에 30일로 명시하고, 서명된 receipt라도
  `evidenceArtifact.expiresAt`이 없거나 현재 시각을 지났으면 registry true를 거부한다. registry 기록도
  같은 `expiresAt`을 복제해야 한다.
- 접근성 importer는 Python 3.11 미만을 stdin token 읽기 전에 exit 2로 거부한다.

## 검증 상태

- receipt/attestation, registry rule 7, accessibility importer focused: **265 passed**.
- exact-head hosted attested run은 구현 push 뒤 실행하며, run ID와 artifact digest는 결과가 나온 뒤 이 절에
  추가한다. 그 전에는 `ciVerified`를 올리지 않는다.
- label producer run `36940289003`은 head `8c2a703c`에서 success했다. 첫 workflow_dispatch run
  `36940396639`은 producer success 뒤 receipt step의 digest 비교에서 실패했다. `upload-artifact` output은
  64-hex, Actions API는 `sha256:<hex>`였는데 workflow가 형식을 정규화하지 않은 하네스 결함이다. 실패는
  숨기지 않고 보존하며 `sha256:${digest#sha256:}` 정규화와 회귀 시험 뒤 exact-head를 재실행한다.
