---
doc_id: "CODEX-WORKSPACE-RESUME-001"
title: "Codex Workspace 실행 재개와 결과 체크포인트 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T09:40:15+09:00"
source_of_truth: "Git"
---

# Codex Workspace 실행 재개와 결과 체크포인트 계약

Owner Codex, reviewer Claude pending. WORKSPACE-RESUME는 S06-BE/DB/ST, S03-BE와 OUT-03/06/07의 후속이다. base `92934d1`, [PR #12](https://github.com/egparadise/SaintVision-Invion/pull/12)는 PR #11 위에 쌓은 초안이다. [[2026-09-10_09-29-08_KST_WORKSPACE-RESUME_Codex_개발과정]]과 실제 CI 증거를 함께 읽는다.

## ADR-044: 고정된 다음 Step의 새 승인과 원자 admission

`WorkspaceResume.prepare`는 recovering Run의 현재 version/attempt/epoch, 동일 project/workspace checkout, 모든 물리 lease 반환을 확인한다. 편집 Adapter는 writer를 먼저 정지시키고 private tree lock을 준수해야 한다. checkout의 directory identity를 재검증한 뒤 현재 파일을 불변 manifest로 고정한다. 같은 attempt와 epoch에 후속 Step 하나만 허용하며 이전 Step과 다른 ID를 요구한다. 잘못 준비한 내용은 임의 덮어쓰기/기존 승인 재사용으로 수정하지 않는다. 후속 실행을 취소하고 새 논리 작업으로 계획해야 한다.

WorkloadSpec.workspaceResume는 resume/checkout/source attempt/source Step/next Step/input hash/size를 포함하며 승인 actionDigest에 포함된다. 원본 파일의 이후 편집은 보존되고 실행 입력을 변경하지 않는다. frozen snapshot은 tenant RLS와 immutable DB 행에 저장한다. 현재 manifest 상한은 64 KiB, 실제 파일 합은 32 KiB다. 기존 16 MiB snapshot 보관 기능과 이 실행 입력 상한은 구별한다.

`sourceAttempt`는 재개 직전 RunAttempt, `checkpointAttempt`는 실제 복원 원본을 만든 RunAttempt다. 새 checkpoint 없이 중단된 attempt에서도 더 이전의 검증 checkpoint를 사용하여 새 checkout을 만들 수 있다. 두 값과 hash/Step을 모두 새 승인에 고정한다. 총 RunAttempt는 3회까지이며 최초 실행을 포함하므로 이 경로의 최대 재실행은 2회다. 상한 이후 prepare/admission은 거부한다. 자동으로 승인하거나 terminal failed/cancelled Run을 되살리지 않는다. 장애 coordinator는 물리 종료를 확인하고 아직 진행 중인 Run을 recovering으로 전이한 뒤 이 경로를 호출해야 한다.

Run의 기존 11상태는 유지한다. `recovering → awaiting_approval → scheduled → running`을 추가하며 새 running에서 RunAttempt가 증가한다. CP Python과 업무 서비스의 상태 그래프를 동일하게 유지하고 교차 시험한다. DB는 frozen Step/이전 물리 종료 없는 recovery approval 및 결과 checkpoint 없는 resumed success를 거부한다. 업무 서비스의 상태 전이 가능 표시만으로 실행 권한이 생기지 않는다.

`WorkspaceResume.enqueue`는 새 승인 dispatch를 입력으로 받아 새 lease·ToolGateway claim·서명 permit queue를 단일 transaction에 저장한다. admission 실패/commit 실패는 전체 rollback한다. 따라서 과거 attempt가 있는 Run에 새 미발급 예약만 남지 않는다. ToolGateway에서 이 원자 경로를 우회한 Workspace claim은 거부한다. 이전 승인·늦은 command·변경된 내용·stale epoch는 권한을 갱신할 수 없다. 동일 enqueue key의 재요청은 원래 command를 관찰하며 추가 실행을 만들지 않는다.

승인 이력의 UNIQUE는 Run 전체가 아닌 `(tenant_id,run_id,bound_run_version)`이다. 과거 승인/nonce/vote/dispatch는 불변 이력으로 유지한다. 샤드 child/parent Run은 이 단독 Workspace 재개 경로에서 거부한다. 기존 샤드 계획의 command와 부모 집계 연결을 분리하는 우회를 허용하지 않으며 샤드 재실행은 별도 조정 계약으로 구현한다.

## ADR-045: Node private tmpfs와 수정 결과의 원자 확정

추가 supervisor label은 `ai.saintvision.workspace=snapshot-tmpfs-v1`다. 고정 이미지의 trusted PID 1은 서명 launch의 hash/size와 manifest 전체를 검증하고, 비어 있는 `/workspace` tmpfs에 파일을 생성한다. 실제 Docker tmpfs 구성·이미지·launch를 확인하며 호스트 경로나 socket을 전달하지 않는다. 권한은 UID 65532, 파일 0600/0700, umask 077, network none 및 기존 자원/시간 상한이다.

입력은 Docker private config의 supervisor 전용 환경 변수로 전달한다. 명령 인자/이벤트/콘솔에는 입력 원문을 추가하지 않고 child 환경에서도 제거한다. daemon 관리자 및 신뢰된 이미지 supervisor는 이 입력을 읽을 수 있는 기존 신뢰 경계 안에 있다. 별도의 비밀 데이터 redaction을 완료했다고 주장하지 않는다.

supervisor watchdog은 복원·프로세스 실행·최종 파일 수집 전체에 적용된다. 성공한 child가 종료되면 private PID namespace의 나머지 descendants를 종료·reap한 뒤 수정 파일을 수집한다. symlink, hardlink, FIFO/device, 경로 탈출, casefold 충돌, 비정상 parent, hash/size/한도 불일치는 성공 결과로 수락하지 않는다. tmpfs는 명령마다 새로 생성되므로 오래된 writer가 다른 attempt나 CP checkout을 변경할 수 없다.

stdout/stderr와 수정 snapshot을 단일 bounded 출력 artifact에 연결한다. Node는 정지 container에서 실제 bytes를 해시하고 durable stop 후보를 fsync한 후 삭제/정지 증명을 확정한다. CP는 실제 receipt, 해당 command의 서명 launch, resume ID/Step/input hash를 대조한다. 수정 snapshot을 독립 immutable object로 게시하고, checkpoint·보존 pin·Evidence·현재 attempt 완료를 같은 DB transaction에 저장한다. 결과 확정 재시도는 기존 최대 3회 정책이며 프로세스를 다시 실행하지 않는다. 출력 artifact 상한은 300,000 bytes다.

취소·timeout·비정상 exit·손상/초과 파일은 성공 checkpoint를 만들지 않는다. 작업 도중 죽었을 때의 마지막 수정 파일 보존까지 보장하지 않으며 이전 검증 checkpoint를 복구 기준으로 사용한다. `SnapshotStore.restore`로 새 Step의 실제 파일을 읽고 새 generation에 복원할 수 있다.

## 인계와 남은 작업

- Claude: 프로젝트 권한 확인·editor quiesce를 수행하는 업무 Adapter에서 prepare → 새 승인 → enqueue → worker/outputRoot를 연결한다. Kernel의 identity/epoch와 서비스 모델 UUID의 매핑, migration 0018, 다중 worker lock 순서와 독립 보안 검토가 필요하다. 실제 전달/검토는 pending이다.
- Gemini / Antigravity: frozen 입력과 이후 편집을 구분하고, 새 Step/attempt·현재 승인·결과 checkpoint·자원 반환 대기 상태를 보여준다. 커널과 연결한 실제 브라우저 검증은 pending이다.
- Codex: 대용량 Node 전송/작업 파일 수명, 인터랙티브 PTY ticket·stream·fence, 더 긴 실행과 checkpoint 정책, 샤드 재실행·다중 Node 통신, kill/drain·Windows/GPU/BuildKit·Context/RO 및 5대 장비 검증이 남는다. 로컬 Git init/add/commit 결과 시험은 원격 Git 인증/push 또는 브라우저 Git 전체 통합을 뜻하지 않는다.
