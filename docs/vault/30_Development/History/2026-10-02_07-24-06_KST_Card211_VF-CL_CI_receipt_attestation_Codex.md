---
doc_id: "HISTORY-2026-10-02-CARD211-VFCL-CI-ATTESTATION-CODEX"
title: "Card 211 VF-CL CI receipt attestation"
version: "1.3.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-02T10:25:52+09:00"
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
- exact-head label producer run `36940633798`은 head `c8466697b156d896e62a1446281bf5410a37e2ef`에서
  success했다. 같은 head의 workflow_dispatch run `36940757636`은 producer와 attestation job 모두
  success했고, receipt 내부 run/head/ref/workflow와 verifier의 Sigstore identity가 일치했다.
- digest 정규화를 receipt 생성기로 옮긴 executable head `e470c0902534a1e0ae6de643be4db3b03fe2576b`의
  workflow_dispatch run `36950676320`도 producer 44초·attestation 16초로 success했다. receipt 생성,
  `actions/attest`, 저장소 verifier, artifact upload 네 단계가 모두 success였고, 내려받은 bundle을
  `gh attestation verify`와 `tools/verify_vf_cl_ci_attestation.py`로 다시 검증해 exit 0과 `VERIFIED`를
  확인했다. receipt 내부 `receiptSha256`은
  `57dd282ea06174c20f01b2dc27881cdfe79e0ef361221f6d73ee96641edddad1`, attested file subject digest는
  `1449b024791daf401db20d949875e6e952b64a316c0012038f697480adff3de9`다.
- 이 run의 Evidence artifact `11204020983`은 digest
  `sha256:d64933813a129fb439d3a591b8908db2122d27029a4294e6d9436ae3e0314465`, 만료 시각
  `2026-11-01T01:23:51Z`다. attestation artifact `11204100906`은 digest
  `sha256:ac761635bb38d65bf1f5204eb298f3b0345b253aa5b87666e48b1ba98bb2919e`, 만료 시각
  `2026-11-01T01:24:12Z`다. 새 bundle member 경로는 `_temp/wAaG3T/attestation.json`이다.
- Evidence artifact `11200122628`은 digest
  `sha256:5615eba6779b020e4aa03d45b5fb68e1ff488c8a802f9408d4fe63bfd7e29025`, 만료 시각
  `2026-10-31T23:26:34Z`다. attestation artifact `11200405399`는 digest
  `sha256:efa66df4f8a7319f7720639b1bf955227a20d43831110d764d79e4e026482905`, 만료 시각
  `2026-10-31T23:27:03Z`다. `verification.json`은 repository, workflow, branch ref, exact head,
  GitHub-hosted runner와 receipt subject digest를 모두 검증했다. 다운로드한 artifact ZIP의 Sigstore
  bundle member 경로는 `_temp/VMTJin/attestation.json`이고 receipt와 verification member는 각각
  `SaintVision-Invion/SaintVision-Invion/.work/vf-cl-attestation/VF-CL-04.json`과
  `SaintVision-Invion/SaintVision-Invion/.work/vf-cl-attestation/verification.json`이다.
- 이 run은 feature head의 attestation machinery를 측정한 것이다. landing SHA의 권위 증거가 아니므로
  `VF-CL-04.ciVerified=false`와 registry 상태는 유지한다.
- label producer run `36940289003`은 head `8c2a703c`에서 success했다. 첫 workflow_dispatch run
  `36940396639`은 producer success 뒤 receipt step의 digest 비교에서 실패했다. `upload-artifact` output은
  64-hex, Actions API는 `sha256:<hex>`였는데 workflow가 형식을 정규화하지 않은 하네스 결함이다. 실패는
  숨기지 않고 보존했다. 후속에서는 셸 문자열 비교를 제거하고 receipt 생성기가 raw 64-hex와
  `sha256:<hex>`를 단일 정본 형식으로 정규화한 뒤 Actions API digest와 대조하도록 고정했다.
