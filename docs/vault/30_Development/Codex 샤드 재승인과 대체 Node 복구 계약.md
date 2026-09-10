---
doc_id: "CODEX-SHARD-RECOVERY-001"
title: "Codex 샤드 재승인과 대체 Node 복구 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T12:47:00+09:00"
source_of_truth: "Git"
---

# 샤드 재승인과 대체 Node 복구

Task SHARD-RECOVERY, owner Codex, independent reviewer Claude pending. S03-BE·S05-DB·S07-BE/DB 및 OUT-03/05/07 후속이다. base `a70aff43262b7457098d68c0d5b8a662aad4742a`의 Workspace API와 실행 커널을 유지한다. [[2026-09-10_12-38-00_KST_SHARD-RECOVERY_Codex_개발과정]]에서 시작했다.

## ADR-048: 물리적 종료와 새 승인에 기반한 독립 샤드 복구

`ShardRecovery.prepare(principal, project, source_plan_id, plan_id, intents, key=...)`는 실패 또는 취소된 부모와 모든 자식의 실제 stop receipt·미반환 lease 부재를 확인한다. 원본의 shard index 순서와 WorkloadSpec action digest가 모두 같아야 한다. 모든 샤드를 다시 실행하며 성공한 자식의 결과를 부분 재사용하지 않는다. Node는 바꿀 수 있지만, 다른 명령이나 다른 입력은 새 작업으로 계획해야 한다. Workspace resume의 Node 파일 전달은 별도 계약이므로 이 경로에서 거부한다.

prepare는 새 자식 Run·새 Approval만 원자적으로 만든다. 각 자식은 operator가 설치한 제한 L2 정책에 따른 서로 다른 2명 승인이 필요하다. 이전 승인은 재사용할 수 없다. 사용자에게 단계마다 개발 승인을 다시 받는 절차가 아니라 제품이 실행 권한을 검증하는 프로토콜이다. 준비한 결과에는 새 runId·approvalId·nodeId·generation이 포함된다. 준비만으로 lease·claim·queue·부모 Run을 만들지 않는다. 같은 key의 재요청은 기존 준비를 반환한다.

`enqueue(principal, project, plan_id, key=...)`는 서버에 설치된 Node runtime으로 mTLS nonce 관찰과 새 정책 평가를 수행한다. 네트워크 I/O 이후 DB에서 원본 물리적 종료, 현재 requester/voter 권한, target project membership, 승인/Run/version/epoch를 다시 확인한다. 모든 승인 소비·새 lease/fence·claim·queue·부모 Run·복구 계보·event가 한 트랜잭션으로 확정된다. 중간 거부나 예외가 있으면 전체 rollback이다. 복구용 자식은 일반 dispatch/reserve/claim을 통해 개별 실행할 수 없다.

`RestrictedWorkspaceRuntime`의 operator 설정을 재사용한다. target별 CPU/memory resource와 signing key가 있고 동일한 제한 profile을 사용한다. 브라우저 입력으로 정책·capability·NodePrincipal·key를 받지 않는다. 이 변경은 서버 서비스 경계와 공통 Schema이며 공개 recovery HTTP route·설정 UI는 별도 통합 작업이다. 기존 실제 승인 challenge/decision 경로로 반환된 approvalId에 투표할 수 있다.

## ADR-049: 불변 계보와 최대 3개 실행 세대

최초 계획은 generation 1이며 복구 계획은 2, 3까지 허용한다. 실패·취소한 원본 부모/자식의 terminal 상태와 기존 Evidence를 바꾸지 않고 새 parentRunId로 연결한다. 원본 계획에 최대 하나의 실행된 후속 계획만 허용한다. root plan 잠금과 DB의 source unique·root/generation unique·generation CHECK가 분기를 막는다. migration `0020_shard_recovery`는 양쪽 history를 합친 `0019` 위에 추가하며 과거 migration을 수정하지 않는다.

승인 만료 또는 취소 때문에 실행하지 않은 준비 요청은 실행 세대 수에 포함하지 않는다. 새 planId로 다시 준비할 수 있다. 여러 준비 요청이 경합해도 실제 enqueue는 하나만 성공한다. 이미 성공한 enqueue의 같은 key 재요청은 새 Node 실행 없이 같은 응답을 반환하되 현재 requester 권한은 다시 확인한다. Node 응답 유실·offline은 물리적 정지의 증거가 아니므로 복구로 우회하지 않는다. 다른 epoch의 실행은 운영 reconciliation이 먼저다.

잠금 순서는 operation ledger → root plan → source plan → 정렬된 원본 자식 Run → 원본 부모 → 정렬된 새 자식 Run → 정렬된 Approval → project/limit → 전체 Node → 전체 Resource → project Node membership와 정렬된 subject grant다. 전달 worker와 결과 집계는 기존 provider → plan → child → parent 순서를 유지한다. 데이터베이스 runtime 역할은 RLS를 우회하지 않고 새 3개 테이블은 불변이다.

## 합격 증거와 인계

전용 통합 시험은 2개 Go Node 프로세스·서로 다른 인증서/서명 키/저널·실제 Docker 출력/해시/Evidence·부모 집계, 새 승인 누락, 권한 철회, 중간 등록 오류, 취소, 경합, epoch/project 차단, 총 3세대 상한을 확인한다. 두 Node는 같은 CI 호스트에서 실행한다. 5대 PC·원격 네트워크 분할·MPI/NCCL collective·GPU/Windows/BuildKit·성능 SLO 검증으로 확대 해석하지 않는다.

Codex는 실행·계보·DB·보안 계약 및 실제 검증 증거를 전달한다. Claude는 독립 코드 검토, 서비스 route와 운영 설정, 준비 요청 보존/정리 정책, 기존 업무 데이터 연결을 맡는다. Gemini는 새 승인 표시·세대별 부모/자식·대체 Node·실행 대기/종료 미확인/상한/실패 표시와 실제 브라우저 검증을 맡는다. peer 검토는 아직 수행되지 않았다. 다음 Codex 영역은 kill switch/drain·주기 reconciliation, PTY/원격 Git·대용량/Workspace Node 이전, Windows/GPU/BuildKit 및 Context/RO/5대 검증이다.
