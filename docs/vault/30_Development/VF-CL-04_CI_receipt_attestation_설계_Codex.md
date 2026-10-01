---
doc_id: "DESIGN-VF-CL-04-CI-ATTESTATION-001"
title: "VF-CL-04 CI receipt attestation 설계"
version: "1.1.0"
status: "implemented-pending-exact-head-evidence"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-02T08:16:01+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "d0b2a4c6"
tags: ["vf-cl", "ci", "attestation", "sigstore", "fail-closed"]
---

# VF-CL-04 CI receipt attestation 설계

## 1. 결정

`VF-CL-04.ciVerified=true`의 정본은 사람이 만든 JSON이나 자체 SHA-256이 아니다. 명시적
`workflow_dispatch`에서 성공한 `.github/workflows/s12-acceptance-evidence.yml`의 Evidence artifact를
GitHub Actions API로 다시 읽어 receipt를 만들고, 별도 job이 `actions/attest@v4`로 **receipt 파일 바이트**를
서명한다. `tools/verify_vf_cl_ci_attestation.py`가 GitHub/Sigstore bundle을 repository, signer workflow,
source commit, source ref와 receipt byte digest에 모두 결속한 경우에만 registry checker가 true를 허용한다.

구현만 있는 현재 tree는 `ciVerified=false`를 유지한다. 구현 commit을 실행한 attestation은 그 뒤에 추가되는
Evidence commit이나 실제 착지 SHA를 증명하지 못한다. 따라서 정본 bundle이 Git에 기록되는 순간 manifest의
`path-absent` 단언이 깨지고, exact-head 재실행·검증 뒤에만 true로 바꿀 수 있다.

## 2. 최소 권한과 trigger

- producer job은 workflow 전역 `contents: read`만 상속한다.
- 서명 job만 `contents: read`, `actions: read`, `id-token: write`, `attestations: write`,
  `artifact-metadata: write`를 갖는다.
- PR event는 서명 job에 들어갈 수 없다. 조건은 `workflow_dispatch`와 producer success의 conjunction이다.
- self-hosted runner attestation은 verifier의 `--deny-self-hosted-runners`로 거부한다.
- evidence artifact는 현재 run의 artifact id, name, head SHA, expiry, GitHub digest와 모두 일치해야 한다.
  producer와 attestation artifact의 보존기간은 `retention-days: 30`으로 명시한다.

## 3. Receipt와 검증 경계

`tools/create_vf_cl_ci_attestation_receipt.py`의 strict receipt는 repository/workflow/run/attempt/event/head/ref,
producer conclusion, 요구 단계, Evidence artifact id/name/digest/생성·만료 시각을 담는다. 중복 JSON key,
다른 run/head, 만료 여부 불명, malformed digest, PR event, 실패 producer는 exit 2다.

`tools/verify_vf_cl_ci_attestation.py`는 bundle 부재를 즉시 거부하고 `gh attestation verify`의 성공만 믿는다.
검증 결과가 SLSA provenance v1이며 subject name과 SHA-256이 receipt 파일 바이트와 정확히 같아야 한다.
repository·workflow·SHA·ref가 기대값과 다르면 네트워크 호출 전에 거부한다. 위조 receipt를 다시 hash해도
기존 bundle의 subject digest를 재사용할 수 없다.

`tools/check_vf_cl_registry.py`는 manifest가 고정한 receipt/bundle/repository/workflow/head/ref를 verifier에
넘기고, 검증된 receipt의 runId·artifact id/digest/**expiresAt**을 registry 값과 다시 대조한다. 서명이
유효해도 현재 시각이 `expiresAt` 이상이면 더는 재검증할 수 없으므로 findings다. bundle이나 네트워크 검증이
없으면 false가 아니라 **검증 불가 findings**이며 true claim은 fail closed다.

## 4. 시험과 아직 주장하지 않는 것

PG-free 시험은 최소 권한·manual trigger, current-run artifact 결속, 다른 repository/workflow/SHA/ref,
위조·재봉인 receipt, bundle 부재, signature 실패, registry field drift를 각각 죽인다. Hosted 실행은 실제
Evidence producer → receipt → OIDC attestation → verifier의 한 방향을 측정한다.

이번 카드의 hosted 성공은 해당 feature head에 대한 CI attestation 기능의 측정일 뿐이다. 그 결과만으로
`VF-CL-04.ciVerified`, AC-12 인수 완료, integration 착지 SHA 검증을 올리지 않는다. 최종 true 전환에는
착지 대상 exact SHA의 재실행, receipt와 bundle의 Git 기록, registry/manifest 갱신이 모두 필요하다.

## 5. Python 3.10 사용자 경계

카드 205 사용자 절차의 PowerShell 5.1 다운로드·ZIP 작성은 Python 3.10으로 동작하지만 importer는 지원
Python 3.12/3.14에서 agent가 실행한다. 사용자가 3.12를 설치했다고 가정하지 않으며, 두 단계를 runbook과
회귀 시험이 분리한다. importer는 Python 3.11 미만이면 argparse·파일·stdin보다 먼저 exit 2로 끝나며,
fresh-auth token을 한 byte도 읽지 않았음을 명확한 오류로 알린다.
