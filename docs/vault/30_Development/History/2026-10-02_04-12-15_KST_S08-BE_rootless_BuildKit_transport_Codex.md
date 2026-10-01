---
doc_id: "HISTORY-S08-BE-ROOTLESS-BUILDKIT-TRANSPORT-20261002"
title: "S08-BE rootless BuildKit transport와 hosted reference 왕복"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-10-02T04:12:15+09:00"
source_of_truth: "Git"
---

# S08-BE rootless BuildKit transport와 hosted reference 왕복

## 선택 근거와 범위

- 기준은 `coord/train11-ci-0047`의 `25f43a25a999568c70ecccbf5881dbc2d11f3b5e`다.
  [[2026-10-01_13-40-45_KST_S08-BE_BuildKit_계약경계_Codex]]와 PR #269·#272·#274가
  strict 계약, ROOF/admission/lease, one-shot 경계를 먼저 고정했지만 제품에는 concrete
  BuildKit transport와 consumer가 없었다. 그래서 외부 LAN builder 없이 닫을 수 있는
  Stage 1인 transport·health·fail-closed·hosted 왕복을 선택했다.
- 이번 결과는 CI reference transport다. 제품 dispatch, cleanup receipt, lease release,
  durable Evidence persistence, 운영 builder 인수는 포함하지 않는다.

## 구현

- `services/control-plane/src/inv/buildkit_transport.py`에 strict health receipt와 단일 worker
  inventory를 소비하는 `RootlessBuildkitTransport`를 추가했다. 기본은 disabled이며
  `dispatch()`와 `cancel_and_quarantine()`은 각각 `RES-0006`, `VERIFY-0022`로 닫혀 있다.
- reference 왕복은 exact clean Git commit/tree, `FROM scratch`, network none, secret·device·
  bind·privileged·host access 없음, OCI file export만 허용한다. report는 항상
  `targetKind=ci-reference`, `operationalAcceptanceAssessed=false`,
  `productDispatchEnabled=false`다.
- Docker inspect의 privileged·capability·device·bind·localhost publish·system path 경계를
  확인한다. 컨테이너 안 실제 `buildkitd`의 PID·UID·start ticks·user namespace를 읽고,
  image 인자 digest를 Docker `RepoDigests`와 대조한다. 실측값과 inspect/caller assertion은
  `fieldSources`에서 구분한다.
- BuildKit worker의 OCI platform 객체와 문자열 표현을 둘 다 strict 정규화하고 알 수 없는
  키·대문자·불완전 tuple은 거부한다.
- `.github/workflows/s08-buildkit-reference.yml`은 `workflow_dispatch` 또는 `run-buildkit`
  label에서만 실행한다. digest-pinned BuildKit v0.20.2 rootless image를 별도 job에서 띄우고
  source SHA, JSON, JUnit, daemon log를 artifact로 보존한다.

## hosted calibration과 정본 실측

초기 실패는 숨기지 않았다. run `36907402778`~`36911252167`에서 순서대로 hosted AppArmor
userns 차단, state 권한, Unix/TCP 주소, Python 의존성, container-mode PID CLI, Docker inspect
표현, worker OCI platform 표현, host `/proc` 권한 차이를 확인했다. 각 실패는 다음 run 전에
단일 원인과 되살림 시험으로 교정했다.

정본 reference 실측은 [run 36912381153](https://github.com/egparadise/SaintVision-Invion/actions/runs/36912381153),
code SHA `c4130ae42bf6e5ee190100500fd73128b566d046`, tree
`83e22c3dc75a4713993eb23345dfc1e3c026a1d5`다.

| 항목 | 결과 |
|---|---|
| job | `rootless-roundtrip` success, 37초 |
| JUnit | 1 passed / 0 failed / 0 skipped |
| verdict | `MEASURED_PASS`, `ci-reference` |
| BuildKit / RootlessKit | v0.20.2 / v2.3.4 |
| daemon | PID 33, UID 1000, 별도 user namespace, cgroup v2 |
| privilege | privileged false, hostAccess false, entitlements/devices/binds 0 |
| runtime image | `sha256:cb5bb371545222c430528556acfdf424144b69897f5deaad391bd227187e90df` |
| image/config digest | `sha256:6e22a108…f85d` / `sha256:1b654a98…a9d1` |
| OCI archive SHA-256 | `0cbba6769e9b12e0ec7d0e22fa6e6cd5cea8ae2048cdd02ddac659dde66a25d7` |
| artifact | `saintvision-s08-buildkit-reference-36912381153`, 30일 보존 |

## 검증

- `PYTHONPATH=services/control-plane/src python -m pytest tests/core/test_buildkit_transport.py tests/core/test_buildkit_rootless_lane.py tests/test_cleanup_owned_docker_label_inventory.py -q`
  → **63 passed**, exit 0.
- `python -m compileall -q services/control-plane/src/inv/buildkit_transport.py tools/run_buildkit_rootless_roundtrip.py`
  → exit 0.
- `bash -n tools/run_buildkit_rootless_lane.sh` → exit 0.
- hosted reference run `36912381153` → exit 0.

Claude 독립 검토 r1의 미래 timestamp, target platform, recovery epoch, address, security option,
owner label, running state, daemon UID, image digest 변이는 각각 단독 부정 시험으로 닫았다.
platform fixture도 hosted 실측과 같은 OCI 객체 형태로 바꿨다.

## 정직성 경계와 다음 단계

- hosted runner는 rootless user namespace를 허용하기 위해 ephemeral host sysctl을 완화하고
  daemon container의 AppArmor·seccomp를 unconfined로 실행했다. report는 이를
  `unconfined-ci-reference`와 `host-apparmor-userns-policy-relaxed`로 명시한다. 이는 운영
  격리 합격이나 보안 승인이 아니다.
- TCP는 runner localhost에만 publish되지만 TLS가 없다. 제품 연결은 Unix socket 또는 mTLS,
  live PID/start-tick 재결속, OCI archive 내부 manifest/config digest 대조, pinned base/egress,
  cleanup·lease release·Evidence persistence를 구현한 뒤 별도 판정한다.
- LAN builder와 실장비 인수는 `BLOCKED_EXTERNAL`이다. S08-BE status·점수는 변경하지 않는다.

