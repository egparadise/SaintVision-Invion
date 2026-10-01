---
doc_id: "HISTORY-20261001-CARD170-S08BE-DESIGN-CODEX"
title: "CARD-170 S08-BE ROOF·BuildKit·단일 GPU 구현 설계"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-01T12:26:22+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "7851412db792b4ef6c53cb92944be530d77eb2de"
task_ids: ["S08-BE"]
tags: ["card-170", "s08-be", "roof", "buildkit", "gpu", "design"]
---

# CARD-170 S08-BE ROOF·BuildKit·단일 GPU 구현 설계

## 선택 근거

- #264 v1.7 source head `561cd22b8e053650699d273a676538b9881c12aa`는
  `S08-BE`를 50에 유지했다. kill switch만 제품 경로에 있고 ROOF·BuildKit·단일 GPU
  지원을 합격시킬 구현이 없기 때문이다.
- 기준 branch는 coordinator 지시대로 train 5
  `7851412db792b4ef6c53cb92944be530d77eb2de`에서 만들었다. #264는 입력으로
  확인했지만 이 branch의 조상은 아니다.
- 계약 선행 카드이므로 제품 코드·migration·task registry는 바꾸지 않았다.

## 정본 대조

- [[용어 사전과 6단계 통합 모델]]과 [[보안 평가 운영 가이드]]에는 ROOF의 네 축이
  이미 정의돼 있다. 없는 것은 `ROOF`라는 단일 package/service이지 정의가 아니다.
- `contracts/v1alpha1/core.schema.json`의 `ResourceRequest`에는 GPU 수와 최소 VRAM이
  있지만 `NodeResourceSnapshot`과 `SandboxLaunchSpec`에는 device observation/allocation이
  없다.
- `services/control-plane/src/inv/scheduler.py`의 순수 계산은 device ID/VRAM을 다루지만,
  `services/control-plane/src/inv/placement.py`와 `services/control-plane/src/inv/sandbox.py`
  는 measured provider 부재를 이유로 실제 GPU 예약·launch를 거부한다.
- `services/node-agent/runtime/docker.go`는 고정 로컬 Docker socket을 가진 Node 운영
  경계다. build 사용자에게 이 socket을 노출하지 않고 별도 rootless Build Service로
  분리해야 한다.

## 설계 결과

[[S08-BE_ROOF_BuildKit_단일_GPU_구현_설계]] v1.0은 다음을 결정했다.

1. ROOF를 새 monolith로 만들지 않고 policy·observability·ownership·recovery의 공통
   불변식으로 BuildKit/GPU 경로에 적용한다.
2. BuildKit은 rootless 별도 service로 두고 host socket·privileged·host entitlement를
   금지한다. WorkloadSpec과 분리한 strict BuildRequest/Plan/Receipt 계약을 먼저 만든다.
3. GPU는 claimed `gpuCount`가 아니라 fresh measured device provider만 authority로 쓴다.
   첫 범위는 Linux exclusive 단일 GPU이고 provider가 없으면 현재 거부를 유지한다.
4. synthetic provider/hosted BuildKit은 코드 계약 증거다. 실제 단일 GPU와 LAN builder
   운영 인수 전에는 AC-08 전체, S08-BE done, 실장비 PASS를 주장하지 않는다.

## 다음

Claude 설계 검토 뒤 계약 카드부터 시작한다. 공개 route·ProblemDetails·migration이
필요한지는 계약 delta에서 명시하며, 승인 전에는 구현하지 않는다. S08-BE는 계속
`planned`, 점수 50이다.
