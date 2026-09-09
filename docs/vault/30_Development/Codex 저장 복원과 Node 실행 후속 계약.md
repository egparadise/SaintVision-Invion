---
doc_id: "STORAGE-NODE-CONTRACT-001"
title: "Codex 저장 복원과 Node 실행 후속 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T03:03:00+09:00"
source_of_truth: "Git"
---

# Codex 저장 복원과 Node 실행 후속 계약

Task storage-node-runtime / OUT-04·05·06·07 / owner Codex / reviewer Claude(pending). Base `6c4f8a937c399d7e79bf49d2538e0bce53f24af4`, branch `agent/codex/storage-node-runtime`. GUIDE-001·GOV-AGENT-001·GOV-GIT-001·PLAN-BACKEND/DB/STORAGE-001 및 task registry v1.0.0, ADR-INDEX v1.7.0, agent-delivery/core-reliability v1.0.0을 읽었다. 시작 메타데이터는 `.work/storage-delivery.json`에 작성했으며 문서 작성 시각을 최초 shell 실행 시각으로 소급하지 않는다.

사용자 순서: 기존 Storage/Checkpoint 잔여 경계 구현·검증 후 Claude의 Control Plane 후속 Node/실행 연결. Claude 고정 SHA `6db4a5f376be68fcd687b2e1be8de649633b36e4`는 풀·지역성 계산/metadata이며 실행 권한 또는 실제 hash 측정의 대체물이 아니다.

## ADR-034: 실제 byte publication과 체크포인트 pin

- 기존 Storage 계획의 S3 object/DB metadata 분리는 유지한다. 본 구현은 명시적으로 설정한 Linux 단일 service 계정의 private 0700 directory Provider다. binary는 DB에 넣지 않는다. 16 MiB part, 64 MiB object의 제한된 복원 kernel이며 S3 presigned/50 GiB 제품 구현으로 표시하지 않는다.
- 객체 ID는 UUID이며 project+tenant로 조회한다. 사용자 경로/아카이브 추출은 받지 않는다. root inode 고정, independent descriptor flock, openat/O_NOFOLLOW, regular file·owner·nlink=1·읽기 전용 모드·실제 size/hash를 확인한다. 모든 participating process는 같은 Provider/lock 규칙을 사용한다. root 상위 경로와 service 계정 및 host 관리자는 신뢰 경계다.
- upload identity/hash/size 고정, part 재전송은 같은 bytes만 허용한다. 재시작 후 part metadata에서 재개한다. 모든 part의 실제 byte를 읽어 전체 SHA-256을 검사하고 fsync→rename→directory fsync 후 ready metadata를 commit한다. metadata 전에 중단되면 동일 객체를 재검증하여 finalize한다.
- project budget을 잠그고 uploading/ready/deleting의 **논리 object size**를 예약한다. 실제 staging+final 파일은 최대 약 2배와 crash 임시 파일 공간을 사용하므로 quota를 물리 디스크 여유 보장으로 해석하지 않는다. 임시 orphan/원본 사용자 파일 자동 스캔·삭제는 하지 않는다. 운영 disk headroom/유예 GC/S3 multipart는 후속이다.
- Run→fences→object 순서와 현재 running attempt를 검증한다. 파일 재해시, immutable checkpoint, checkpoint object pin, outbox를 함께 commit한다. 같은 step의 다른 내용은 거절한다. 복원은 해당 project의 고정 attempt/step pin을 조회해 실제 byte 재검증 후 trusted Workspace adapter에 반환한다. 자동 실행/Lease 재발급이 아니다.
- GC는 checkpoint pin을 검사하고 deleting tombstone commit→unlink+fsync→deleted commit 순서를 따른다. 중단 시 삭제를 재개한다. pin은 현재 무기한 보존한다. 만료·회수 API를 도입하기 전에는 체크포인트 객체를 해제하지 않는다.
- RunStore.complete의 기존 path 기반 helper는 이 Provider로 아직 연결되지 않았다. Node stop receipt가 Lease를 반환하는 시점과 application Evidence publication의 순서를 별도 조율해야 하며, checkpoint 복원 검증을 Run 성공으로 승격하지 않는다.

## 담당과 인계

| owner | 구현/후속 |
|---|---|
| Codex | 저장 무결성·pin/GC, Node mTLS 자동 관측·실측 snapshot·bounded transfer, 결정론적 배치·Lease 및 샤드 승인/실행 경계 |
| Claude | discovery 후보/풀 CRUD·업무 API, 확정 계약 adapter, 실행 기록, S02/S05/S07 차이 정리와 Codex 검토 회신; 본 계약 독립 검토 |
| Gemini | 후보 목록, totalOffered/largestSingleNode/spareNow 세 숫자, Explain와 실제 API 연결 |

Claude의 idle-first 계산은 ADR-005 가중치 Scheduler를 대신할 수 없다. float CPU core→integer cpuMillis, ram→memoryBytes, node active→online 등의 변환은 명시적이어야 한다. 한 capability snapshot만으로 다른 자원의 미측정 used를 0이라고 간주하거나 미래 snapshot을 여유로 인정하지 않는다. 계획 placement는 Lease/승인/Node 실행 증거가 없으면 실행된 것으로 표시하지 않는다. 신규 migration 번호는 각 branch 내 이력으로, Claude 0007과 Codex 0007/0008을 그대로 하나의 Alembic head로 합치지 않는다.

## 검증 상태

로컬 pytest 147 passed / 169 skipped / 실패 0. Linux private directory/PostgreSQL/Docker 검증은 동일 SHA CI에서 실행 후 History에 원본 Evidence로 기록한다. peer review, 실장비 5대·IdP/CA/DNS·Storage 제품 선택은 pending이다.
