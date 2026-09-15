---
doc_id: "ARCH-MODEL-LOCALITY-001"
title: "모델 locality 예약과 실행 입력 경계"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-15T12:24:59+09:00"
source_of_truth: "Git"
---

# 모델 locality 예약과 실행 입력 경계

기준 [[ModelManifest 커널 계약과 저장 Catalog 경계]], ARCH-WEB-FABRIC-001 1.0.0. owner Codex, 독립 reviewer Claude 미수신.

## 데이터와 권한

`ModelLocalityStore.observe`는 정본 committed manifest를 읽고 현재 project grant, Node membership/epoch/heartbeat, contribution owner/version, DataLocation version을 확인한다. 실제 operator-configured ReadRoot에서 전체 bytes와 shard/전체 해시를 검증한다. 최초 DB 시각부터 15초만 관측으로 인정한다. 브라우저에서 전달한 verified 플래그, 절대 경로, 임의 전송률은 provider가 아니다.

현재 adapter는 `python-files@1/single-node`의 로컬 파일 입력에 한정한다. 각 Node에 전체 shard가 있어야 한다. 부분 replica, 암호화 provider 부재, 예산 초과, corrupt/missing bytes는 가용량으로 계산하지 않는다. 검사 byte 예산은 모든 Node의 실패 시도를 포함해 누적한다. 확인 실패한 replica 때문에 원본 manifest를 삭제하지 않는다.

`PlacementStore.reserve(..., model_observation=...)`는 서버 내부 계약이다. HTTP payload에 이 객체를 받는 경로는 없다. Node→Resource 잠금, 현재 project grant/ceiling, Catalog snapshot/freshness 재확인 후 기존 deterministic scheduler에 local_bytes를 제공한다. 전송률이 없고 로컬 bytes가 부족하면 후보를 거부한다. CPU/RAM 제공량과 host load는 기존 측정 경로를 따른다. GPU/collective/offload는 지원으로 표시하지 않는다.

## 원자성과 실행

기존 Lease, placement idempotency/outbox, 새로운 `inv.model_run_inputs`를 같은 트랜잭션에 commit한다. 입력 기록 실패는 예약을 포함해 rollback한다. 동일 key의 완료 응답은 현재 grant 아래 durable replay이며 파일 재읽기/새 Lease/새 실행 권한이 아니다. 다른 key로 같은 Run 입력을 바꾸는 것은 거부한다.

0040은 0039 뒤에 추가한 forward-only migration이다. tenant RLS와 SELECT/INSERT 전용 권한, immutable trigger, 기존 Run/ModelManifest/Node FK를 사용한다. 기존 migration, lease/fencing sequence는 수정하지 않는다.

관측과 실행 사이 파일은 바뀔 수 있다. 예약 성공은 bytes를 고정한 실행 승인이 아니다. 입력에 `requiresExecutionRevalidation=true`를 유지하며 ToolGateway는 모델 입력을 가진 Run을 `MODEL-0006`으로 거부한다. VF-CX-04는 실제 runtime adapter에서 bytes 입력을 고정하고 승인 digest/Node/epoch/lease/permit에 결속한 뒤 이 경계를 열어야 한다. boolean flag만 추가해 실행을 허용하지 않는다.

## 인계

Claude: Catalog는 commit/관측 결과를 표시하되 metadata 상태로 물리 검증을 대체하지 않는다. 0040 RLS/기존 migration 업그레이드 및 모델 입력 원자성을 독립 검토한다.

Gemini: placement.modelInput은 모델 ID/version/hash/mode와 관측 시각, 실행 재검증 필요 상태를 표시한다. 예약됨을 모델 실행 가능 또는 성공으로 표시하지 않는다. unavailableReplicas는 상태이며 synthetic heartbeat/GPU 수치를 생성하지 않는다.

Codex: 실제 runtime adapter/입력 고정/취소·stale permit·Node loss·재시도 시험을 이어 진행한다. 본 문서는 실제 원격 2대/5대나 ML inference 성공 증거가 아니다.
