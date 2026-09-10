---
doc_id: "CODEX-RUNTIME-COMPLETION-001"
title: "Codex 실행 완료와 자원 회수 통합 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T09:02:10+09:00"
source_of_truth: "Git"
---

# Codex 실행 완료와 자원 회수 통합 계약

Owner Codex, 독립 reviewer Claude pending. Task RUNTIME-COMPLETION, S03/S04/S05/S06/S07 후속. 기준 base `720b8ee`, 최신 Codex `39bd9e9`를 별도 worktree에서 병합했다. [[2026-09-10_08-38-33_KST_RUNTIME-COMPLETION_Codex_개발과정]]의 실행 기록과 연결한다.

## ADR-040: 미발급 예약과 미수신 명령의 취소

Control의 Run 취소는 Run→Node/resource→project grant 순서로 잠근다. tool claim과 attempt가 전혀 없고 현재 epoch인 취소 Run의 예약만 별도 immutable `reservation_aborts` 증명으로 반환한다. SQL FK와 배타적 release-proof 제약으로 Node receipt와 구분한다. 발급된 claim은 아직 전송하지 않았더라도 이 경로를 쓰지 않는다.

Node의 미수신 cancel은 동일 command의 durable tombstone과 allocation high-water를 fsync한 뒤 `not_started` receipt를 반환한다. 이때만 containerId는 빈 문자열, processStarted는 false, exitCode는 -1이다. 지연 Execute와 재시작 Recover는 실행하지 않고 그 증명을 재사용한다. 이미 create intent가 있는 불확실한 명령은 실제 동일 container 정지/삭제 확인이 필요하다. 샤드 admission savepoint 실패는 커밋되지 않은 claim을 롤백한 뒤 같은 바깥 transaction에서 정확한 proof를 가진 미발급 예약을 취소·회수한다. 형식/tenant/project 자체가 잘못된 요청으로 다른 예약을 반환하지 않는다.

## ADR-041: 실제 출력 및 정지 후보의 보존

신뢰된 pinned 이미지의 supervisor는 `ai.saintvision.output=bounded-streams-v1` 라벨과 일치해야 한다. stdout/stderr 각각 64 KiB만 보존하고 전체 쓰기는 소비한다. 한도를 넘으면 exit 122, 성공 Evidence는 생성하지 않는다. PID 1이 단일 JSON artifact를 쓰며 Docker local log는 512 KiB/1개/압축 없음으로 제한한다. Node는 소유한 정지 container의 frame을 읽어 `NodeStopReceipt.output={data,sha256,sizeBytes}`에 실제 바이트를 연결한다. 이 출력은 민감 데이터를 포함할 수 있으므로 UI·console·진단 로그에 원문을 출력하지 않는다. 저장 위치는 private journal·tenant RLS receipt·private object다. 별도 redaction이 완료됐다고 주장하지 않는다.

정지 후보와 출력은 container 삭제 전에 fsync된다. 후보 자체는 외부 정지 receipt가 아니다. 삭제 ACK 유실이나 Node 재시작 시 후보에 기록된 동일 container ID의 부재까지 확인한 뒤 receipt를 확정한다. create intent만 남은 불확실성은 이 증명으로 바꿀 수 없다.

## ADR-042: 결과만 재시도하고 부모 Run을 확정

worker의 `outputRoot`는 사전 생성된 절대 경로의 Linux 서비스 소유 private directory다. project storage budget도 미리 설정되어야 한다. 설정된 경우 실제 stdout/stderr artifact 해시, 크기, JSON 구조, exit 및 receipt를 검증한다. object publication→result commitment→Evidence/Run succeeded로 이어진다. receipt가 현재 epoch의 현재 attempt에 대해 만료 전에 고정한 동일 출력은 lease 반환 후에도 publish할 수 있다. 새로운 출력이나 복구된 불확실한 실행의 성공을 인정하는 예외가 아니다.

`output_ingestions`는 30초 작업 예약과 최대 3회 결과 확정 시도를 기록한다. provider/commit 장애는 같은 object와 Evidence ID를 재사용한다. 3회 후 failed로 종료한다. 실제 프로세스를 재시작하는 기능이 아니며, 새로운 실행은 별도 최신 승인·명령·lease가 필요하다. 실패 물리 receipt는 worker가 Run failed에 자동 반영한다.

신규 샤드 계획에는 별도 parent Run이 있다. parent의 직접 claim/lease와 aggregate Evidence 없는 succeeded는 DB에서 거부한다. 모든 child의 현재 attempt completion과 ready object 바이트를 재검증하여 순서가 고정된 manifest를 DB에 보존한다. 실제 결정 ID와 `shard-completion:v1` 정책 버전, parent Evidence, parent succeeded를 원자적으로 기록한다. 정책은 모든 child의 검증된 성공을 요구하며 수치 reducer·모델 품질·SLO 합격을 평가하지 않는다.

child failed/cancelled는 parent failed와 남은 child 취소를 자동 요청한다. 남은 자원은 실제 Node receipt 전까지 유지한다. parent 브라우저 취소는 child 전체를 원자적으로 취소하고 child 자원 반환 대기를 응답한다. worker가 부모 확정 전에 죽으면 다음 idle sweep가 확정한다. lock 순서는 provider→plan→정렬된 child Runs→parent다.

## ADR-043: 수정 가능한 작업 사본

기존 readonly restore와 별개의 private root에 `WorkingGenerations`를 만든다. 일반 파일 0600, 실행 파일 0700, 원본 restore 0400/0500은 보존된다. checkpoint hash·workspace·source attempt·step ID·epoch와 실제 directory inode를 immutable `workspace_checkouts` receipt에 연결한다. DB commit 전 재시도는 원본 바이트와 일치해야 한다. commit 후 재시도는 metadata와 directory identity를 검증하며 작업 중 변경된 파일을 초기화하지 않는다.

checkout은 현재 recovering Run과 반환된 모든 lease를 요구한다. 파일 준비로 OS 실행 권한을 부여하지 않으며 Run은 recovering에 남는다. Node mount·새 Step 실행 승인·PTY·Git 프로세스 연결은 후속 구현이다. 기존 epoch 정보가 없는 restore 행은 재개용 checkout에 사용하지 않고 현재 epoch에서 새 restore를 만든다.

## 실제 남은 범위와 담당

| 담당 | 남은 범위 | 합격 증거 |
|---|---|---|
| Codex | writable checkout의 Node 전달·격리 mount, 새 실행 승인과 Step 재개, PTY/Git 프로세스·fence 연결 | 복구 후 실제 파일 수정/명령·세션/Git 작업, 오래된 epoch 및 취소 writer 차단 |
| Codex | fresh approval을 전제로 한 제한된 샤드 재실행 정책, 다중 Node 물리 통신·collective/reducer | 중복 실행 0, Node 간 장애/분할·재시도 한도, 실제 통신 결과 |
| Codex | kill/drain, Windows/GPU/BuildKit, Context/RO 안전성 평가, 5대 부하·장애·복구 | 실제 장비/운영 설정과 조건별 측정 기록 |
| Claude | private worker/outputRoot·storage budget의 업무 API Adapter, 통합 DB migration 운영 절차, pool/placement 계약 매핑, Codex 독립 검토 | public 업무 여정과 실제 kernel의 연결·검토 보고 |
| Gemini / Antigravity | parent/child 상태, resourceReleasePending, 실제 output Evidence/aggregate 표시와 복구 UX | 인증된 업무 API 기반 실제 브라우저 종단 시험 |

기존 인계 문서의 과거 수치는 해당 고정 SHA 증거다. 최신 검증보고와 동일 SHA CI가 우선한다. 원문 docs/sources와 task registry의 Sprint 완료 상태를 임의 변경하지 않는다.
