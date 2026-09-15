---
doc_id: "ARCH-MODEL-RUNTIME-001"
title: "모델 실행 입력과 대체 Node 복구 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-15T12:55:38+09:00"
source_of_truth: "Git"
---

# 모델 실행 입력과 대체 Node 복구 계약

owner Codex, reviewer Claude 미수신. 기준 ARCH-WEB-FABRIC-001 1.0.0, [[ModelManifest 커널 계약과 저장 Catalog 경계]], [[모델 locality 예약과 실행 입력 경계]]. VF-CX-04는 별도 실행기를 만들지 않고 기존 승인/서명 permit/Go Node journal/출력 Evidence 경로를 사용한다.

## 순서

1. `ModelLocalityStore.observe`와 `PlacementStore.reserve`가 확인한 Node와 Lease에 모델 입력을 결속한다.
2. `ModelRuntimeStore.prepare(principal, project, run_id, workload, proofs, key=...)`는 현재 권한·Run·Node·Catalog·fence를 확인하고 트랜잭션 밖에서 실제 bytes를 freeze한다. 돌아와 같은 상태를 재확인하고 immutable DB snapshot과 완성된 WorkloadSpec을 commit한다. 파일 수집 또는 권한 검증 실패는 frozen input을 만들지 않는다.
3. 반환된 WorkloadSpec의 `modelInput`에는 run/model/version/manifest hash, input UUID와 snapshot SHA/크기, Node, adapter/version/mode가 있다. 기존 ApprovalStore가 이 전체 action digest에 독립 승인자를 결속한다. 다른 요청자에게 frozen input을 넘겨 같은 승인을 대신 사용하지 않는다.
4. ToolGateway는 모델 입력이 있는 Run에서 reference 누락/교체를 거부하고, 현재 권한·원래 reservation fence·Node·Catalog snapshot을 검사한다. 검증된 bytes만 기존 initialized Workspace launch에 넣는다. Node는 원래 서명·epoch·deadline·fence·durable inbox·isolated container 검사를 그대로 수행한다.
5. DeliveryQueue는 실제 전송 직전에도 모델 저장소/권한/Node/fence를 확인한다. 출력은 기존 OutputIngestion이 실제 receipt/hash를 검증해 Result/Evidence와 완료에 연결한다. 완료 출력 복구는 다시 실행하지 않는다.

## 지원 범위와 제한

- 첫 adapter는 `python-files@1/single-node`: 고정된 모델 파일을 읽는 CPU 프로그램 입력 경로다. PyTorch/vLLM/GPU 기능을 설치하거나 보증한 것이 아니다.
- 기존 Go Node의 content32KiB/snapshot64KiB 한도를 유지한다. metadata도 content 한도에 포함한다. 큰 모델을 조용히 자르거나 호스트 경로 mount로 우회하지 않는다.
- 경로는 `model/0000.bin` 등 shard 번호와 `model/manifest.json`으로 생성한다. 사용자가 준 절대 경로를 mount하지 않는다. frozen source는 불변이며 container 작업 사본은 기존 Workspace 정책을 따른다.
- 원본 파일이 freeze 이후 바뀌어도 승인받은 bytes를 실행한다. 반대로 contribution/Location 버전, 권한, Node 상태가 달라지면 새 admission을 거부한다. License/classification 필드는 선언이며 별도 정책·운영 검토를 대체하지 않는다.
- 실제 GPU/offload/collective/network prefetch provider가 없는 모드는 거부한다. 여러 Node RAM/VRAM을 하나의 프로세스 메모리처럼 더하지 않는다.

## 제한된 대체 실행

`ModelRetryStore.prepare`는 **failed** Run과 모든 Lease의 물리적 해제가 확인된 뒤 같은 모델 ID/version/hash로 새 Run을 만든다. cancelled는 재시도하지 않는다. 기존 Run을 되살리거나 old permit을 다른 Node에 전송하지 않는다.

root Run 잠금과 immutable lineage의 parent/child/generation 유일성으로 한 parent에 하나의 child만 허용한다. 최초 포함3세대가 한도다. child 생성·현재 측정 기반 placement·Lease·model input·lineage/outbox는 같은 트랜잭션이며 배치 실패 시 모두 rollback한다. child는 다시 freeze/정책/독립 승인을 받아야 실행할 수 있다. 오래된 epoch는 operator reconciliation 없이 재사용하지 않는다.

이는 single-node 작업의 대체 Node 복구다. 여러 GPU가 동시에 수행하는 tensor/collective 학습 복구와는 별개다. 실제 두 Go Node 시험은 서로 다른 키/journal/mTLS endpoint를 쓰지만 하나의 격리 Docker host에 있으며 실제 두 PC 또는5대 인수가 아니다.

## Migration 및 인계

0041은 bounded frozen bytes/workload/원래 Catalog snapshot을, 0042는 retry lineage를 추가한다. 둘 다 FORCE RLS, kernel SELECT/INSERT만, immutable trigger와 기존 FK를 사용한다. 0040 이전 이력을 수정하지 않는다. 기존 definer hash/grant 정책을 완화하지 않는다.

Claude: registry/import API는 이 커널 prepare 결과를 사용하고 모델 실행 입력을 별도 JSON 계약으로 다시 만들지 않는다. 0041/0042 RLS·원자성·권한 재검증과 prepared input의 승인 연결을 독립 검토한다. 서비스 엔드포인트/업무 권한 binding은 담당 영역에서 연결한다.

Gemini: freeze 완료, 승인 대기, 예약, 실행, 결과 복구, 대체 Run lineage를 서로 다른 상태로 표시한다. `requiresFrozenInputAndApproval=true`를 실행 가능으로 표시하지 않는다. 모델 지원 범위를 bytes 한도/adapter/mode 그대로 표시한다.

Codex: 실제5대/운영 계정·PITR·GPU/네트워크 provider 증거를 수집한 뒤 지원 모드를 확장한다. 구현·로컬·CI·독립 검토·운영 인수 상태를 분리한다.
