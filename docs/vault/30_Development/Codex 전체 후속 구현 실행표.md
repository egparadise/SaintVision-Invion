---
doc_id: "CODEX-EXECUTION-001"
title: "Codex 전체 후속 구현 실행표"
version: "1.1.1"
status: "in_progress"
author: "Codex"
updated: "2026-09-10T04:16:06+09:00"
source_of_truth: "Git"
---

# Codex 전체 후속 구현 실행표

사용자 지시: Codex 구현 담당 부분 모두 착수. owner Codex, reviewer Claude(대기). Task execution-recovery, base `227cd2984a256092f5496d9895060092cbf87145`, branch `agent/codex/execution-recovery`. GUIDE/GOV/Backend·DB·Storage v1.0.0, ADR-INDEX v1.9.0, task registry v1.0.0, agent-delivery/core-reliability v1.0.0을 읽었다. 시작 시각 2026-09-10 03:30:38 KST. 기존 사용자 승인으로 구현·검증·작업 branch push·CI·보고·Obsidian 동기화·draft PR을 진행한다.

## 전체 순서와 합격 증거

| 순서 | Codex 구현 범위 | 합격 증거 | 착수 상태 |
|---|---|---|---|
| 1 | 실제 실행 attempt와 output commitment, pin/Evidence/Run 완료/물리 반환 순서 | 정상·중복·동시·손상·cancel·recover·GC·commit 실패 시험 | 내부 계약 구현·CI 349개 통과; Node 출력 자동 수집과 업무 verifier 연결 후속 |
| 2 | Workspace 실제 파일 snapshot/안전 복원·Step 재개 권한 | 실제 파일 hash, 중단/재시도, 경로·link 탈출 거절 | 새 generation 복원 구현·CI 385개 통과; writable Workspace/Step/PTY 연결 후속 |
| 3 | 샤드 결과 집계·부모 Run·실패/취소, 샤드 통신 격리 | 다중 Node 실행·실제 결과 교환·부분 실패·replay 시험 | 결과 manifest·전체 취소·실패 반영 구현·CI 388개 통과; parent/통신/reducer 후속 |
| 4 | 풀/실측 locality/할당량과 원자 Scheduler 예약 계약 | 미측정·미래값 거절, 경합·Explain 일치 | 실측 CPU/RAM과 project 상한 예약 구현·CI 400개 통과; 실제 pool/locality 후속 |
| 5 | 대형 Storage·Node 복제·cache pin/GC·물리 용량 경계 | 실제 byte/중단 재개/GC 경합·용량 시험 | 대기; 제품 Adapter는 Claude |
| 6 | 인증/등록 공통 계약·kill switch·drain·복구·Windows/GPU/BuildKit 격리 | 정책 우회·late effect 0, 대상 OS/장비 실행 증거 | 대기; 실제 운영 정보 미확인 |
| 7 | Context/RO 검증 연결·SLO/복구·설치/upgrade/rollback | 실제 평가·부하·장애·5대 인수 기록 | 선행 통합 뒤 검증 |

업무 CRUD·서비스 Adapter·일반 migration 및 Claude 오류 수정은 Claude owner, UI·브라우저·웹 배포는 Gemini owner다. 공통 계약과 인계 입력은 Codex가 구현과 함께 제공한다. 모든 작업을 동시에 완료/검증했다고 표기하지 않으며 각 실제 결과는 History에 고정 SHA로 기록한다. 실제 장비·IdP·CA/DNS·Storage 제품이 미확인인 상태에서 운영 성공을 추정하지 않는다.

첫 네 영역의 정확한 구현 경계·호출 순서·잔여 사항은 [[Codex 결과 확정과 Workspace 복구 및 배치 계약]]을 따른다. 5~7 영역을 구현 완료나 실장비 착수로 표시하지 않는다. 전체 Sprint의 선행·독립 검토 조건은 유지한다.

실행 증거: [[2026-09-10_04-01-17_KST_EXECUTION-RECOVERY_Codex_검증보고]]. 같은 SHA Linux CI Python 400개/Go race 62 leaf, 실패·오류·skip 0. reviewer 수신은 대기다.

샤드 현황 재확인: [[샤드 관리 구현 현황과 잔여 범위]], [[2026-09-10_04-16-06_KST_SHARD-STATUS_Codex_확인보고]]. Codex 검토 branch의 구현과 통합 branch 반영 상태를 구분하며 SHARD-I01~I08의 다음 owner·합격 증거를 따른다.
