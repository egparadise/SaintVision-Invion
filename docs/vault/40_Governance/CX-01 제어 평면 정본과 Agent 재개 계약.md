---
doc_id: "CONTRACT-CX01-CANONICAL-001"
title: "CX-01 제어 평면 정본과 Agent 재개 계약"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T11:08:50+09:00"
source_of_truth: "Git"
---

# CX-01 제어 평면 정본과 Agent 재개 계약

## 개발 정본과 실행 경계

- 공유 개발 정본: `origin/integration/all-agents-unified`. CX-01 착지 작업 브랜치: `agent/codex/cx-01-canonical-landing`; 병합 완료 SHA `fe4c04cf4a40d3241ab699f0584caa71aa336154` ([PR34](https://github.com/egparadise/SaintVision-Invion/pull/34)). 검증/원격 수신은 [[2026-09-18_CX-01_정본착지_Codex]]에 고정한다.
- production entrypoint는 `saintvision.server:create_app --factory` → `inv.app.create_configured_app`다. `saintvision.demo_server`는 격리 fixture이며 배포 정본이 아니다.
- 명시적 identity/database 설정 없이 시작하지 않는다. 임의 Bearer·만료 신뢰·다른 tenant/project·폐기된 권한은 거부한다. readiness와 Workspace 실행 admission은 별도다.
- kernel `inv_kernel`과 business `inv_app`은 NOLOGIN 그룹이다. 별도 최소권한 로그인/DSN을 쓰며 business dispatch는 같은 요청의 정본 kernel 권한을 통과한다. 테스트 난수 계정을 운영 credential로 사용하지 않는다.
- migration 정본 head는 `0043_replica_retention`. 공개된 과거 migration 이력은 보존한다. ORM만 복사하면 pinned ready→stale가 기존 constraint에 막히므로 migration과 API/deps/service를 한 기준으로 가져온다.
- storage API `replay_or_reserve(..., project_id=None)`는 이 정본의 deps와 함께 사용한다. 기존 lane의 deps에 API 파일만 복사하면 호환되지 않는다. owner-scope 목록·URI 검사·stale pin 보존·cache 용량 계산도 같은 묶음이다.
- frontend는 Login→현재 프로젝트→Desktop 경로다. 토큰은 메모리에 두고 실제 `/v1/session`/project 권한을 확인한다. synthetic 기본 Node/Run/Evidence·가짜 실행 성공을 정본으로 복구하지 않는다.

## 다음 Agent의 트리거

공유 branch의 착지 SHA를 fetch하고 해당 SHA를 자신의 작업 branch에 merge한다. 충돌은 정본 인증/권한/DB 경계를 유지하며 해결한다. 필수 문서/검증 확인 후 자신의 수신 SHA를 작업판에 남긴다. 이 문서는 다른 세션을 실행하거나 수신을 대신 승인한 기록이 아니다.

| 담당 | 즉시 가능한 첫 행동 | 별도로 남는 Gate |
|---|---|---|
| Claude / CL-01·VF-CL-05 | 착지 SHA에서 canonical factory/tenant/role/migration 경계 독립 검토; storage API와 deps를 함께 반영하고 pinned node-loss/0043 재실행 | 전체 병합 독립 승인, 실제 CI |
| Claude / VF-CL-01~04 | 동일 head로 storage/catalog/locality/model service 연결 검증. registry→kernel 권한 결속은 [[모델 레지스트리와 실행 Manifest 권한 경계]] 유지 | 실제 model bytes·운영 PITR/매체; 설정 관측만으로 복구 합격 불가 |
| Gemini / GM-01·VF-GM-01~06 | 최신 App/Desktop 계약을 기준으로 실제 API 브라우저·접근성 검증; `/v1/pools` 등 미제공 surface를 성공으로 표시하지 않기 | 운영 IdP/HTTPS/실장비 여정 |
| Codex / CX-02~03·VF-CX-05 | 독립 finding 통합, 운영 설정/원격 연결 확보 후 admission·실행 시험 | CI billing, .225 원격 profile/연결, 5대·PITR |
| Orca 관리(미배정 시 Codex) | branch/code SHA·수신·CI/검토/운영 상태를 각각 집계 | 수신/검토/합격을 대신 생성하지 않음 |

## 완료 의미

사용자 승인으로 공유 개발 branch의 착지를 진행한다. main 릴리스 병합과 운영 배포는 별도이며 기존 교차 검토/CI/운영 Gate를 통과한 것으로 쓰지 않는다. 기존 48개 task done 0/48, 점수 2775/4800(57.81%, 잔여42.19%)는 재평가 증거 전까지 유지한다.
