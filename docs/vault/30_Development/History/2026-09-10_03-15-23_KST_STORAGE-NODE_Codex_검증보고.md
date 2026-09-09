---
doc_id: "REPORT-STORAGE-NODE-001"
title: "Codex 저장 복원과 Node 실행 후속 검증 보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T03:15:23+09:00"
source_of_truth: "Git"
---

# Codex 저장 복원과 Node 실행 후속 검증 보고

Task storage-node-runtime / OUT-04·05·06·07 / owner Codex / reviewer Claude(pending). Branch `agent/codex/storage-node-runtime`, base `6c4f8a937c399d7e79bf49d2538e0bce53f24af4`. GUIDE/GOV/Backend·DB·Storage/task registry v1.0.0, agent-delivery/core-reliability v1.0.0, ADR-INDEX v1.9.0, STORAGE-NODE-CONTRACT-001 v1.1.0. 사용자 요청에 따라 기존 Storage/Checkpoint 경계를 먼저 구현·push한 후 Node/독립 샤드 연결을 구현했다. CI 대기 중 후속 구현을 병행했으며 Storage CI 성공 확인과 Node 후속 CI 결과를 구분한다.

## 구현과 실제 증거

| 단계 | 구현 SHA | 검증 결과 | CI |
|---|---|---|---|
| 저장/복원 | `f4e33b958379e058196135d737539a3cee9d0a85` | Python 316, 실패·오류·skip 0 / Go race 57 leaf | [Core #34386900927](https://github.com/egparadise/SaintVision-Invion/actions/runs/34386900927), [Docs #34386900905](https://github.com/egparadise/SaintVision-Invion/actions/runs/34386900905) |
| Node/독립 샤드 포함 전체 | `bd20b6888723322f84defe18f93b52bde0c6cc51` | Python 328, 실패·오류·skip 0 / Go race 62 leaf | [Core #34387490708](https://github.com/egparadise/SaintVision-Invion/actions/runs/34387490708), [Docs #34387490833](https://github.com/egparadise/SaintVision-Invion/actions/runs/34387490833) |

동일 SHA의 Linux/PostgreSQL 16/Docker 합성 시험, package 빌드, JSON Schema 생성 drift·Go/TypeScript 검증을 포함한다. 원본 [[storage-f4e33b9-tests.xml]], [[storage-f4e33b9-unit.jsonl]], [[storage-f4e33b9-provenance.json]], [[runtime-bd20b68-tests.xml]], [[runtime-bd20b68-unit.jsonl]], [[runtime-bd20b68-provenance.json]]. Artifact #10118158719 / #10118385550를 내려받아 실패/skip 및 archive/file hash를 검사했다. 수신 시각 2026-09-10T03:09:59+09:00 / 2026-09-10T03:15:12+09:00.

- Storage: 실제 byte part 재전송/재시작·동시 finalize·잘못된 checksum·publication 후 DB commit 전 crash·fenced checkpoint/pin/outbox·복원 시 재해시·symlink/hardlink/FIFO 차단·quota 경합·삭제 중단/재개·pin/GC 경합·빈 객체를 검증했다. 16MiB part/64MiB local Provider이며 S3 제품 도입의 대체물이 아니다.
- Go 공지: 명시적 TLS 서버/CA로 Claude wire shape를 보내는 실제 HTTPS client와 redirect/신뢰 실패를 시험했다. 공지는 미검증 후보이며 실제 Claude 서버의 등록/인증서 발급과 통합한 시험은 아니다.
- Node snapshot/observer: 실제 mTLS Go `/proc` CPU·RAM 관측, nonce replay/폐기된 channel 거절, 자동 poll/sweep 및 세 용량 숫자의 future/revocation/project 권한 경계를 검증했다. 관측값을 Offer 또는 GPU capability로 승격하지 않는다.
- Transfer: 실제 mTLS chunk 수신 중 응답 유실·재시도·재해시·재요청, part commit 직전 channel 폐기 및 source link 거절을 검증했다. 측정값의 경로는 Node→CP이며 Node→Node locality 성능 수치가 아니다.
- Shards: 2개의 별도 승인 Run/Lease를 한 plan/queue transaction에 넣고 기존 worker→mTLS→Go→Docker로 실제 실행, 개별 receipt 및 물리 자원 반환을 확인했다. 두 번째 admission 실패 시 첫 queue/claim도 rollback되고, 동시 제출은 한 세트만 생긴다. implicit split/MPI/NCCL은 실행 전에 거절한다. 같은 합성 Node에서 순차 실행한 시험이며 5대 분산 동시 실행을 주장하지 않는다.

## 실행 기록과 오류

- 로컬 `python -m pytest -q -r fE`: exit 0, 147 passed/181 skipped, Windows에 없는 Linux/격리 DB 시험은 CI에서 실행했다.
- `go test ./...`(Windows 실행 가능한 패키지), Linux target `go build ./...`: exit 0. Linux race 및 실제 Node/DB 결과는 위 CI 원본이다.
- `python tools/check_docs.py`, `python tools/check_ontology.py`, `python tools/test_sync.py`, `git diff --check`: exit 0. 문서 검증을 제품/실장비 시험으로 대신하지 않는다.
- `git commit` 및 지정 origin branch `git push`: 위 구현 SHA push 성공. 최종 보고서 commit의 동일 SHA CI는 Actions 및 PR 인계에 별도로 남긴다.
- 최초 db7eae70188d17b59d5eb12fafe4425ff1a0561b의 Core #34386461632는 migration 실행 단계 실패, Docs #34386461839 success. 실행 경로를 수정한 f4e33b9에서 전체 316개를 재검증했다. [[ERR-STORAGE-NODE-001 Migration과 기록 인코딩 실패]] / [[RES-STORAGE-NODE-001 Migration 실행과 UTF8 기록 복구]].

## 인계와 남은 작업

계약 [[Codex 저장 복원과 Node 실행 후속 계약]], 안내 [[Codex Node와 저장소 Adapter 실행 안내]]. baseline 48 task/12 Outcome의 선행·독립 검토·실장비 조건 없이 done으로 올리지 않는다.

| 담당 | 다음 행동과 완료 조건 |
|---|---|
| Codex | Run 결과 Artifact의 pin/Evidence/물리 receipt 순서, Workspace 실제 restore/Step 복구, collective 통신 격리·샤드 간 데이터 교환/reducer·parent Run 결과, 실측 locality/프로젝트 pool 예약 연결, S3·Windows/GPU 및 5대 SLO 후속 |
| Claude | 후보/풀 CRUD·업무 API를 위 정본 단위/상태/인증/nonce/queue 계약에 Adapter로 연결, S02/S05/S07 계획 차이 문서화, 기존 heartbeat 인증/경합·backup hash 검토 지적 수정 및 이 코드 독립 검토 |
| Gemini | 실제 후보 목록과 totalOffered/largestSingleNode/spareNow, 배치 Explain 연결, 시뮬레이션과 운영 Evidence 구분 |

Claude 고정 SHA `6db4a5f376be68fcd687b2e1be8de649633b36e4`를 읽었다. 누락 capability를 used=0으로 간주하는 node_spare, 미래 snapshot/link 시각, 문자열 hash만 받는 replica-ready 호출의 trusted byte 검증 경계, idle-first와 정본 가중치 Scheduler의 조율을 계약에 기록했다. 이전 인증 P1은 최신 Node heartbeat route에서도 미해결을 확인했다. 실제 peer 수신/수정/검토 완료를 대신 기록하지 않는다.

실제 IdP/CA/DNS/5대 접속·Storage 제품 정보는 아직 확인되지 않았다. 운영 배포·서비스 기동·인증서 발급·사용자 데이터 삭제·main merge를 수행하지 않았다. 기존 승인 범위에서 구현/검증/push/report를 완료하고 draft PR로 검토에 넘긴다. 인계 수신은 pending이다.

Obsidian 외부 관리 파일 13개와 새 Gemini 보고서 1개를 raw hash로 검토했다. 최신 Codex 기록을 제거하는 이전 사본은 반영하지 않고, 새 보고는 작성자 제안으로 보존했다. [[외부 인계 제안 수신과 정본 동기화 복구]]에 대상 hash와 판단을 기록했다.

## Obsidian 실제 동기화

- 2026-09-10T03:15:28+09:00 `python tools/sync_obsidian.py --check --state .work/storage-obsidian-sync-state.json`: exit 0; `CHECK: 181 managed files, 27 pending exports, 0 conflicts. No writes.`.
- 2026-09-10T03:15:29+09:00 `python tools/sync_obsidian.py --apply --state .work/storage-obsidian-sync-state.json`: exit 0; `EXPORTED: 27 files; all 181 destination hashes match. Unmanaged files untouched.`.

이 실제 결과를 포함한 보고서도 다시 export하고 전체 파일 hash 일치를 확인한다. 최종 보고서 SHA-256은 PR 인계에 기록한다. 작업별 state로 확인 이후 발생한 다른 Agent 편집을 보호하며 공유 state를 무조건 덮어쓰지 않는다.
