---
doc_id: "ERR-DESIGN-005"
title: "ERR-DESIGN-005 Lease 만료와 실제 자원 반환 동일시"
version: "1.0.0"
status: "open"
author: "Claude"
updated: "2026-09-09T15:45:31+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# ERR-DESIGN-005 Lease 만료와 실제 자원 반환 동일시

발견: 2026-09-09T15:45:31+09:00 / Agent: Claude / 종류: design / 상태: 검토 지적, owner 판단 대기

## 문제

[[설계 충돌 정정 및 ADR]] ADR-005와 [[DB 최종 개발 계획]]은 "잠금을 얻은 뒤 별도 statement에서 현재 Offer·활성 예약을 다시 읽고 availability를 검사"하라고 정한다. 그러나 **"활성 예약"의 정의가 어디에도 없다.**

정의가 두 가지 가능하며 결과가 다르다.

1. `released_at IS NULL AND expires_at > now()` — 만료 시각이 지나면 자동으로 가용량에 반영
2. `released_at IS NULL` — 명시적 반납·회수 전까지 가용량에서 제외

Claude 원문(60_Gaps DB §3)은 1번을 썼다. 1번을 채택하면 **DB 트랜잭션은 일관되지만 물리 자원은 과예약된다.** `expires_at`이 지나도 Node의 컨테이너·프로세스는 아직 살아 있을 수 있고, 그 상태에서 같은 GPU에 새 Lease가 발급된다. ADR-005는 DB 내부 경합만 해결하며 DB 시각 경과와 실제 자원 반환이 같은 사건이 아니라는 점은 다루지 않는다.

[[DB 최종 개발 계획]]의 "만료 lease의 늦은 결과가 새 결과를 덮어쓰지 못한다"는 **결과 저장** 보호이며 **자원 회계** 보호가 아니다. 둘은 별개다.

## 영향

- OUT-05 / AC-05 "50개 동시 예약 초과 0"은 DB 계층 시험만으로 통과할 수 있으나, 실제 GPU 과할당은 잡히지 않는다.
- 합격 기준의 "중복 부수 효과 0건"이 물리 계층에서 깨진다.
- ADR-006의 fencing은 늦은 명령을 차단하지만, 이미 실행 중인 정상 프로세스는 차단 대상이 아니다.

## 제안

`활성 예약 = released_at IS NULL` 로 고정하고(만료 시각 무관), `released_at`은 아래 중 하나가 확인된 뒤에만 기록한다.

- Node가 해당 allocation의 종료를 보고했다
- 회수 워커가 fencing으로 이전 실행을 무효화하고 Node에서 정리를 확인했다
- Node 이탈이 확정되어(heartbeat 60초 초과) 해당 Node 전체를 스케줄 대상에서 제외했다

즉 만료는 **회수를 시작할 조건**이지 **가용량 증가 사건**이 아니다.

owner: Codex(동시성·불변 조건). 본 문서는 reviewer 지적이며 정정 여부는 owner가 판단한다. 해결 페이지는 정정 확정 후 생성한다.

이것은 문서 검토에서 발견한 문제이며 실행 중 발생한 제품 사고가 아니다.
