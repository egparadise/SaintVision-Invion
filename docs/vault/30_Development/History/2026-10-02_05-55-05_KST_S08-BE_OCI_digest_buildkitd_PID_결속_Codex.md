---
doc_id: "HISTORY-S08-BE-OCI-DIGEST-BUILDKITD-PID-BINDING-20261002"
title: "S08-BE OCI digest와 live buildkitd PID 결속"
version: "1.2.0"
status: "review"
author: "Codex"
updated: "2026-10-02T06:41:34+09:00"
source_of_truth: "Git"
---

# S08-BE OCI digest와 live buildkitd PID 결속

## 선택 근거와 범위

- 기준은 train 14 후보 `d0b2a4c6b05674a7d8d0ca011f080f580a873b06`이다.
- [[2026-10-02_04-12-15_KST_S08-BE_rootless_BuildKit_transport_Codex]]가 이연한 두 항목,
  즉 OCI archive 내부 digest 대조와 실제 `buildkitd` PID 생존 결속만 닫는다.
- reference transport의 기본 flag off, 제품 caller 미결속, cleanup·lease release·durable Evidence
  미결속, LAN 실장비 인수 `BLOCKED_EXTERNAL` 경계는 바꾸지 않는다. S08-BE 완료나 운영 합격을
  주장하지 않는다.

## 구현과 fail-closed 경계

- `services/control-plane/src/inv/buildkit_transport.py`는 OCI tar를 실제로 열고 `oci-layout`,
  `index.json`, manifest, config, 모든 layer blob의 descriptor size와 SHA-256을 재계산한다.
  BuildKit metadata의 image/config digest는 재계산한 manifest/config digest와 같아야 한다.
- 절대·상위·backslash 경로, symlink·hardlink·특수 member, 중복 파일, 누락 blob, 중복 layer,
  미참조 blob, duplicate-key/non-finite JSON은 모두 `VERIFY-0002`로 닫힌다. 검증한 OCI tar도
  hosted artifact에 보존해 report만으로 검증을 가장하지 않는다.
- `tools/run_buildkit_rootless_roundtrip.py`는 컨테이너 `/proc`에서 이름이 정확히 `buildkitd`인
  단일 PID를 찾고 UID·start ticks·user namespace를 health receipt와 대조한다. 왕복 직전과 직후
  같은 PID/start ticks가 살아 있어야 하며, rootlesskit PID를 daemon PID로 기록하지 않는다.

## 검증 상태

- `PYTHONPATH=services/control-plane/src python -m pytest tests/core/test_buildkit_transport.py tests/core/test_buildkit_rootless_lane.py tests/test_cleanup_owned_docker_label_inventory.py -q`
  → **72 passed**, exit 0.
- `python -m compileall -q services/control-plane/src/inv/buildkit_transport.py tools/run_buildkit_rootless_roundtrip.py`
  → exit 0.
- `bash -n tools/run_buildkit_rootless_lane.sh` → exit 0.
- PR #303 hosted run `36928934670`, source `ad5b25f33addf9839c49b4f9aca272c0c7ff9e43`은
  rootless roundtrip과 measured-reference gate를 모두 통과했다. artifact `11195047135`, GitHub
  digest `sha256:a6f2970f…91af5`, 만료 `2026-10-31T21:29:05Z`다.
- report는 `MEASURED_PASS`, product dispatch false, operational acceptance false다. OCI archive
  SHA-256은 `a714a972…897c`, 검증 blob 3개(manifest/config/layer 각 1), manifest
  `sha256:f95a64bb…6387`, config `sha256:0d57d413…62f6`였다. OCI tar도 artifact에 함께 보존됐다.
- 실제 daemon은 PID 32, UID 1000, start ticks 28815, process name `buildkitd`였고 왕복 전·후
  생존·identity가 일치했다. 이는 hosted CI reference 측정이며 LAN builder 운영 인수는 계속
  `BLOCKED_EXTERNAL`, 제품 consumer·lease release·durable Evidence는 계속 미결속이다.
- 문서까지 포함한 exact head `6292ea3722b29b65df475a5e537229df7b1fd186`의 run
  `36929190888`도 실제 rootless BuildKit OCI 왕복과 measured-reference gate를 통과했다.
- PID 생존 재검증은 `tools/run_buildkit_rootless_roundtrip.py`의 CI evidence 도구 경계에만 있다.
  제품 transport 조건으로 아직 연결되지 않았으므로 제품 daemon liveness 합격을 주장하지 않는다.

## 되살림 방지

- metadata image/config digest를 정규식 형태의 다른 digest로 바꾸는 M6/M7 변이는 archive
  재계산값 불일치로 실패한다.
- 참조 layer blob 누락, receipt 이후 start ticks 변경, rootlesskit 프로세스를 buildkitd로
  대체하는 변이는 각각 focused 부정 시험으로 실패한다.
- 같은 크기의 layer byte 변조, descriptor size 변조, 미참조 blob, 복수 manifest, symlink member,
  process-mode의 non-buildkitd `comm`을 각자 독립 fixture로 거부한다. focused 결과는 **78 passed**다.
