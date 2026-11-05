---
doc_id: "GOV-FLEET5-LEGACY-HOLD-20261105"
title: "FLEET5 기존 normal-v1 갱신 실행 보류와 재개 조건"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-05T21:34:54+09:00"
source_of_truth: "Git"
execution_gate: "active-hold"
---

# 기존 갱신 실행 보류

실제 Linux Go Journal/Authority 시험에서 중간 정책과 최종 정책이 같은 버전으로 발행되면 최종 정책이 `NODE-0041`로 거부됨을 확인했다. 정상 cycle은 두 번 시도해 0번 완료했다. 공개 source03·executorB5의 Go 코드와 정상 정책 생성 함수도 해당 시험의 코드와 일치한다. 현재 Node가 정상 관측되거나 정책 hash가 저장된 floor와 일치하는 사실은 다음 normal-v1 갱신의 안전성을 증명하지 않는다.

이전 지시문을 실행할 수 있는 자동 항목이 활성 상태로 남지 않도록 Root는 2026-11-05 **21:14:42 KST**에 아래 세 Orca 항목만 비활성화하고 다시 조회했다. 변경된 저장 필드는 `enabled`와 `updatedAt`뿐이다. 예약 정의·시각·timezone·prompt·precheck·workspace·provider는 보존했다. 항목과 실행 이력은 삭제하지 않았고 `RunNow`를 호출하지 않았다.

| 보존한 항목 | 원래 예약 시각(KST) | 확인한 enabled |
|---|---|---|
| `286d975e-75e2-4e54-b1fb-2805f7d68959` | 2026-11-08 14:20 | false |
| `a3a9e396-3b48-4aaa-8b73-f8377670f968` | 2026-11-09 12:15 | false |
| `3e08faa1-4e85-4877-8b13-5645178b41b8` | 2026-11-10 08:00 | false |

이 조치는 이전 갱신의 자동 호출만 막는다. 개발·검증 에이전트와 CI는 계속 진행한다. Node·Docker·Control Plane을 정지하거나 재시작하지 않았으며, 기존 guard source/config/pins·claim·lock·clock·window와 Windows Task Scheduler 및 보안 설정도 바꾸지 않았다. 이전 감사가 기록한 “세 일정 변경 없음”은 이 조치 전의 관측으로 보존한다.

## 실행 경계

기존 normal-v1 및 해당 경로를 호출하는 이전 guard/plan의 실행은 보류한다. 남아 있는 과거 프롬프트나 수동 후속 요청은 읽기 전용 평가와 HOLD 보고만 수행한다. 예약 시각 도래, 기존 승인, 현재 floor 일치 또는 문서 CI 성공을 실행 허가로 바꾸지 않는다. 정당한 관측·자료 보존과 개발 검증은 계속할 수 있다.

기존 항목을 자동으로 다시 활성화하지 않는다. 새 Go 이미지에 관측 CLI가 추가되더라도 옛 바이너리·producer·plan이 함께 수정되는 것은 아니다. 새 observer를 옛 실행 파일 옆에 두어 same-executable 검증을 우회하거나 unsigned host snapshot을 생산용 M2 관측으로 사용하는 경로도 허용하지 않는다.

## 교체 계획의 필수 조건

1. 실제 floor를 바인딩하고 정책을 P+1/P+2, 채널을 C+1로 갱신하는 제한적 P0 구현이 실제 Linux 두 정상 cycle 및 거부·실패 경계 시험을 통과하고 독립 코드 검토를 받아야 한다.
2. 새 source/binary/image/helper/guard/plan의 정확한 provenance와 CI가 고정돼야 한다. 아직 게시되지 않은 값은 null/HOLD로 두며 예상 hash를 만들지 않는다.
3. 기존 observe profile·허용 workload image·키/인증서/CA·정책·채널·상태 volume·journal/floor를 보존하는 명시적 capability bootstrap 계획과 새 helper가 G1-G10을 충족해야 한다. 현재 공개 helper에는 이 binary-only 교체 경로가 없다.
4. `--image`의 permit/workload 의미와 실제 Go runtime image를 별도 계약으로 다룬다. 새 per-Node runtime inventory 및 consumer가 검토되기 전에는 기존 CP 필드의 의미를 다시 쓰지 않는다.
5. 소유권이 고정된 cutover 전 관측과 새 실행 파일의 mTLS·서명된 M2 관측이 일치해야 한다. pin/CAS 또는 출판 intent 이후에는 실제 증거 없이 이전 파일·바이너리로 자동 복귀하지 않는다.
6. Root가 독립 검토된 새 갱신/guard 계획을 실제 유효기간·동작 창·현재 상태에 다시 바인딩한 뒤 후속 실행 방식을 결정한다. 기한을 놓치거나 partial/unknown 상태이면 별도 검토된 복구까지 BLOCK으로 유지하며 clock·claim·floor·DB version을 우회하지 않는다.

이는 실행 가능한 bootstrap이나 신규 배포의 수락이 아니다. 근거와 시각별 변경은 [[2026-11-05_기존5대_오케스트레이션_착수_Codex]], `legacy-renewal-scheduler-hold.json`, `native-go-confirmation-and-p0-implementation.json`을 따른다. 새 5대 초기화·leaf 발급·운영 인수 및 전체 프로그램 완료 판정은 별도다.
