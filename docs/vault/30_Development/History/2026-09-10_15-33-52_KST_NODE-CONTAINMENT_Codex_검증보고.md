---
doc_id: "HIST-NODE-CONTAINMENT-VERIFY-001"
title: "2026-09-10_15-33-52_KST_NODE-CONTAINMENT_Codex_검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T15:33:52+09:00"
source_of_truth: "Git"
---

# NODE-CONTAINMENT 검증·인계

task NODE-CONTAINMENT / S07-BE·DB, S08-BE·DB 부분 범위. owner Codex, reviewer Claude pending. base `990f3f3a89cef6f6e8c7dd1236d8f2518041fc4f`, 구현 `091b8e52306305b91655baf762e5ba142f0585f1`, branch `agent/codex/node-containment`, [draft PR17](https://github.com/egparadise/SaintVision-Invion/pull/17). 시작 Context·범위·명령은 [[2026-09-10_14-47-19_KST_NODE-CONTAINMENT_Codex_개발과정]], 확정 계약은 [[Codex kill switch와 Node drain 및 정리 계약]]의 ADR-053/054/055/056이다.

tenant kill switch는 신규 실행과 늦은 성공을 차단하고 기존 Run의 취소를 지속한다. Node drain은 새 예약/claim/전송을 막고 이미 시작한 실행의 종료를 기다린다. 현재 operator grant와 별도 resume 권한, 요청자를 제외한 검증된 두 사람의 L2 승인, tenant gate/Node 잠금, control version·멱등 감사, 물리 정리·현재 Node 관측 후 재개를 실제로 검증했다. 제어 응답과 물리적 종료는 구분한다.

기존 worker에 Run 단위 정리를 연결하고 취소 전용 5개 처리 경로를 실행 처리 2개와 분리했다. 미발급·만료·취소 예약만 비실행 증명으로 회수하며, claim 이후에는 Node 영수증을 기다린다. 전송 전 preflight 거부는 같은 command의 취소 tombstone으로 정리한다. old epoch 예약과 불확실한 실행은 반환하지 않는다. 이 thread 수만으로 운영 취소 지연을 보장하지 않는다.

## 실제 검증

초기 operator 권한만 확인한 구현에서 L2 승인 누락을 코드/설계 대조로 발견했다. [[NODE-CONTAINMENT 승인 경계 검토 오류]], [[NODE-CONTAINMENT 승인 경계 검토 해결]]에 원인과 forward migration 0023을 기록했다. 앞선 18/21개 통과는 누락된 승인 경계의 증거가 아니며, 이번 검증에서 0/1인 거부·2인 승인·현재 권한 철회·요청 만료·gate 변경·내용/nonce/동일인 중복·적용 시 원자적 소비를 확인했다. 실제 운영 침해가 발견됐다는 의미는 아니다.

- 전체 `python -m pytest --junitxml=dist/core-tests.xml -o faulthandler_timeout=45`: **990 passed**, failure/error/skipped **0**, exit 0.
- 전용 `pytest tests/integration/test_containment.py -x -q`: **28 passed**, exit 0. 업무 binding 16개, Workspace 20개, 샤드 복구 21개도 통과했다. 각 전용 수는 전체의 부분집합이며 합산하지 않는다.
- 실제 PostgreSQL의 operator/RLS·멱등 감사·동시 제어·rollback, 예약/kill barrier, 늦은 성공 거부, 미발급/만료/기취소 예약·old epoch 보존을 검증했다.
- 실제 Go/mTLS/Docker에서 queued 취소 tombstone, 전송 예약 직후 kill/drain, 실제 running container kill과 자원 반환, 진행 중 실행을 보존하는 drain/현재 resource probe 뒤 resume, operator 철회 뒤 worker 재시작, Node 단절 동안 pending 유지·재시작 후 실제 receipt를 검증했다.
- `go test -race -json ./...`: **40 top-level / 94 leaf**, 실패/skip 0. Go binaries·production API image·Python package·생성 계약 drift·TypeScript/Go compile exit 0.
- `tools/check_migration_upgrade.py`: 기존 canonical 0018·0010·0019·0020·0021·0022 → 0023 upgrade/replay exit 0. 빈 DB upgrade와 runtime 비owner/NOLOGIN 그룹도 통합 시험에 포함됐다. operator grant·epoch·LOGIN credential 자동 발급은 하지 않는다.
- Backend Python 3.12/3.14, check_docs·check_ontology 통과. 로컬 core/migration **221 passed**, worker 보완 후 core **201 passed**, 승인 migration/API 경계 **23 passed**, exit 0. 로컬 collect-only는 실행 성공으로 세지 않는다. 실제 Node 시험은 Linux CI 호스트의 합성 실행이며 5대 운영 PC 시험이 아니다.

| Workflow | Trigger | 구현 SHA 결과 |
|---|---|---|
| Core Build | push | [success 34445015092](https://github.com/egparadise/SaintVision-Invion/actions/runs/34445015092) |
| Core Build | pull_request | [success 34445018982](https://github.com/egparadise/SaintVision-Invion/actions/runs/34445018982) |
| Backend Build | push | [success 34445015121](https://github.com/egparadise/SaintVision-Invion/actions/runs/34445015121) |
| Backend Build | pull_request | [success 34445018943](https://github.com/egparadise/SaintVision-Invion/actions/runs/34445018943) |
| Documentation Build | push | [success 34445015096](https://github.com/egparadise/SaintVision-Invion/actions/runs/34445015096) |
| Documentation Build | pull_request | [success 34445018961](https://github.com/egparadise/SaintVision-Invion/actions/runs/34445018961) |

Artifact `10139513227`, archive SHA-256 `6b6a68071e8ea143668f16667866ca15e64366c87eb605a709f974f3df90cb66`, 검증 시각 `2026-09-10T15:32:47+09:00`. `Evidence/containcode-091b8e5-*` 7개 원본 XML/JSONL/provenance를 보존했다. 기존 SHA에서 실행되거나 대체된 CI를 최종 SHA 성공으로 대신하지 않는다.

이전 `18e2d23` 전체 CI 34443537621의 983개 중 1개 실패도 추적했다. 후속 `20ff0d4` CI 34444531780도 전체 990개 중 같은 1개가 실패했고 새 전용 28개는 통과했다. 미등록 임의 tenant로 RLS 조회를 시도한 기존 fixture를 수정해 미등록 tenant 거부와 등록된 다른 tenant 격리를 각각 검증했다. [[NODE-CONTAINMENT tenant 격리 시험 오류]], [[NODE-CONTAINMENT tenant 격리 시험 해결]]을 따르며 barrier를 완화하거나 시험을 skip하지 않았다. 위 최종 구현 SHA의 전체 통과와 구분한다.

## 전달 상태·남은 범위

이 보고서를 포함한 후속 commit도 CI를 확인하고 `tools/sync_obsidian.py --check → --apply → --check`를 수행한다. 최종 SHA/CI ID·실제 sync 파일 수/hash/시각은 PR17의 마지막 인계 영수증으로 고정해 자기 SHA 재기록 루프를 피한다. 아직 실행하지 않은 후속 CI/sync는 이 문서에서 완료로 표시하지 않는다. sync는 로컬 Obsidian 사본이며 OneDrive cloud upload는 별도다.

Claude: 독립 review, 신뢰 operator/person provisioning·운영 서비스 설치/감사 조회/알림, 영구 단절·old epoch·기존 transient claim의 운영 reconciliation. Gemini: 모의 kill 토글을 요청/별도 2인 승인/실제 적용 API에 연결하고 접수/물리 종료 대기/정리 완료/재개를 구분, 권한·버전 충돌·브라우저 검증. 실제 메시지나 독립 인수는 아직 받지 않았다.

Codex 후속: editor/PTY/remote Git·Workspace Node 이전, Windows/GPU/BuildKit 격리, Context/RO 및 실제 5대 부하·장애·복구 검증. OS 전체 방화벽/사용자 프로세스 차단·전체 ROOF·전체 Sprint·운영 배포 완료를 주장하지 않으며 baseline 48 tasks를 done으로 올리지 않는다.
