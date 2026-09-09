---
doc_id: "CODEX-EXECUTION-001"
title: "Codex 전체 후속 구현 실행표"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-10T03:30:38+09:00"
source_of_truth: "Git"
---

# Codex 전체 후속 구현 실행표

사용자 지시: Codex 구현 담당 부분 모두 착수. owner Codex, reviewer Claude(대기). Task execution-recovery, base `227cd2984a256092f5496d9895060092cbf87145`, branch `agent/codex/execution-recovery`. GUIDE/GOV/Backend·DB·Storage v1.0.0, ADR-INDEX v1.9.0, task registry v1.0.0, agent-delivery/core-reliability v1.0.0을 읽었다. 시작 시각 2026-09-10 03:30:38 KST. 기존 사용자 승인으로 구현·검증·작업 branch push·CI·보고·Obsidian 동기화·draft PR을 진행한다.

## 전체 순서와 합격 증거

| 순서 | Codex 구현 범위 | 합격 증거 | 착수 상태 |
|---|---|---|---|
| 1 | 실제 실행 attempt와 output commitment, pin/Evidence/Run 완료/물리 반환 순서 | 정상·중복·동시·손상·cancel·recover·GC·commit 실패 시험 | 구현 중 |
| 2 | Workspace 실제 파일 snapshot/안전 복원·Step 재개 권한 | 실제 파일 hash, 중단/재시도, 경로·link 탈출 거절 | 설계 중 |
| 3 | 샤드 결과 집계·부모 Run·실패/취소, 샤드 통신 격리 | 다중 Node 실행·실제 결과 교환·부분 실패·replay 시험 | 선행 1/2 뒤 구현 |
| 4 | 풀/실측 locality/할당량과 원자 Scheduler 예약 계약 | 미측정·미래값 거절, 경합·Explain 일치 | 대기 |
| 5 | 대형 Storage·Node 복제·cache pin/GC·물리 용량 경계 | 실제 byte/중단 재개/GC 경합·용량 시험 | 대기; 제품 Adapter는 Claude |
| 6 | 인증/등록 공통 계약·kill switch·drain·복구·Windows/GPU/BuildKit 격리 | 정책 우회·late effect 0, 대상 OS/장비 실행 증거 | 대기; 실제 운영 정보 미확인 |
| 7 | Context/RO 검증 연결·SLO/복구·설치/upgrade/rollback | 실제 평가·부하·장애·5대 인수 기록 | 선행 통합 뒤 검증 |

업무 CRUD·서비스 Adapter·일반 migration 및 Claude 오류 수정은 Claude owner, UI·브라우저·웹 배포는 Gemini owner다. 공통 계약과 인계 입력은 Codex가 구현과 함께 제공한다. 모든 작업을 동시에 완료/검증했다고 표기하지 않으며 각 실제 결과는 History에 고정 SHA로 기록한다. 실제 장비·IdP·CA/DNS·Storage 제품이 미확인인 상태에서 운영 성공을 추정하지 않는다.
