---
doc_id: "EXECUTION-RECOVERY-CONTRACT-001"
title: "Codex 결과 확정과 Workspace 복구 및 배치 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T03:51:59+09:00"
source_of_truth: "Git"
---

# Codex 결과 확정과 Workspace 복구 및 배치 계약

Task execution-recovery, owner Codex, reviewer Claude(대기), base `227cd2984a256092f5496d9895060092cbf87145`, branch `agent/codex/execution-recovery`. GUIDE/GOV/Backend·DB·Storage/task registry v1.0.0, 입력 ADR-INDEX v1.9.0, agent-delivery/core-reliability v1.0.0. 사용자의 Codex 전체 담당 구현 착수 지시에 따른 첫 실행 묶음이다. 전체 계획과 합격 증거는 [[Codex 전체 후속 구현 실행표]].

## ADR-036: 실행 attempt와 결과 확정

- durable queue의 최초 execute 예약에서 Run을 running으로 전이하고 attempt·command·claim의 정확한 allocation proofs를 같은 transaction에 고정한다. running은 전송이 진행 중인 논리 attempt이며 실제 프로세스 시작은 아직 불확실할 수 있다. observation/replay는 attempt를 증가시키거나 새 실행 권한을 만들지 않는다.
- `ResultStore.prepare(tenant, project, run, command, object, evidence, proofs=...)`는 신뢰된 업무 verifier용이다. caller가 project 접근 권한과 업무 결과의 의미를 검증한다. 서비스는 현재 attempt·epoch·fence·claim 만료·입력 digest·policyDecisionId·미래가 아닌 Evidence 시각 및 실제 object bytes를 검증한다.
- **prepare는 유효한 권한 아래, CP에 stop receipt를 기록하기 전에 수행한다.** Node의 실제 프로세스가 이미 종료됐더라도 이 조건은 유지된다. 현재 NodeDelivery는 receipt를 즉시 기록하므로 업무 Adapter는 출력 수집/검증을 먼저 연결해야 한다. 이번 시험의 출력은 trusted verifier가 제공한 합성 바이트이며 컨테이너 출력 자동 추출 성공을 주장하지 않는다. 미준비 상태로 receipt가 먼저 기록되면 새로운 결과 도입을 거절한다.
- output object·전체 EvidenceEnvelope·command·attempt commitment는 불변이다. 실제 바이트를 다시 해시한 뒤 pin을 저장한다. `prepare` replay는 이전 seal의 관측만 반환하며 다른 결과/Evidence ID는 거절한다.
- `ResultStore.complete(..., expected_version=...)`는 현재 running/verifying attempt와 같은 command의 저장된 receipt를 요구한다. `processStarted=true`, `exitCode=0`, `reason=exited`, 정확한 allocation proofs, 물리 예약 반환, 고정된 object의 실제 바이트를 검사한다. cancel/failed/recovering·새 attempt·이전 epoch·손상·불확실한 종료는 성공할 수 없다.
- Evidence INSERT·result completion·verifying/succeeded 전이·outbox가 한 transaction이다. receipt로 반환된 Lease를 다시 발급하거나 활성으로 되돌리지 않는다. commit 실패 시 Evidence/상태는 rollback되고 고정된 output을 재사용한다. DB trigger도 managed attempt에 result completion 없는 성공을 금지한다.
- prepared output/Evidence object는 GC에서 제외하며 현재 보수적으로 무기한 pin한다. 1년 이후 해제·정책 보존 만료 API는 후속이다. 기존 path 기반 `RunStore.complete`는 새 managed 실행의 완료 경로가 아니다.

## ADR-037: 실제 Workspace 파일 복원

- `PrivateTree`는 Linux의 명시적 private service-owned root만 연다. root inode/device 고정, 모든 단계의 no-follow 열린 handle·owner·권한·regular file·single link 검사, 같은 root flock을 쓰는 협력 writer 규칙을 적용한다. snapshot 전에 업무 Adapter가 실제 writer를 정지/flush해야 한다. 실행 중인 임의 프로세스의 일관성을 자동 보장하지 않는다.
- 포맷 `workspace-snapshot:1`: workspace ID, 빈 directory 목록, 상대 경로·실행 권한·size·SHA256·실제 bytes. 최대 2,048 entries, 깊이 16, 실제 내용 16MiB, 직렬화 24MiB다. NFC·casefold 충돌·drive/UNC/ADS·경로 이동·link·FIFO 등을 거절한다. 일반 tar/zip 자동 추출 API를 노출하지 않는다.
- `WorkspaceRecovery.checkpoint`가 파일 capture→object 실제 publication→fenced checkpoint/pin을 연결한다. 기본 object ID는 scope와 내용으로 결정해 동일 snapshot 재시도를 재사용한다. publication 후 취소/권한 만료가 발생하면 checkpoint를 만들지 않는다.
- `restore(..., expected_version=...)`는 현재 recovering Run, 기존 물리 Lease의 전부 반환, 동일 project/run의 checkpoint와 workspace ID를 확인한다. 고정된 별도 restore root에 새 generation을 만들며 기존 작업 폴더나 사용자 파일을 덮어쓰지 않는다.
- 파일 쓰기/재해시/fsync→generation rename/directory fsync→DB restore receipt/outbox 순서다. DB commit 실패 후 같은 generation을 검증하여 재사용한다. DB receipt가 있는 generation이 사라지거나 변조되면 자동 재생성/수정하지 않는다. 새 복원은 새로운 ID와 현재 권한을 요구한다.
- 복원 파일은 0400/0500, 관리 directory는 private이다. 같은 service 계정/host 관리자는 신뢰 경계이며 WORM이 아니다. 업무 Adapter의 writable 실행 copy·Step/PTY/Git 세션 재개·Node mount·Windows ACL/reparse 구현은 아직 연결되지 않았다. 복원 receipt는 프로세스 재시작 권한이 아니다.

## ADR-038: 샤드 결과와 전체 취소

- `ShardRuntime.status`의 `allPhysicallyStopped`와 `allSucceeded`를 분리한다. 후자는 모든 해당 attempt의 result completion/Evidence와 ready object를 요구한다. 그때만 index 순서의 결과 manifest 및 그 digest를 제공한다. 이는 결과 목록이며 계산 reducer나 parent Run 성공이 아니다.
- `cancel(principal, project, plan, key=...)`는 현재 project 요청 권한과 ledger→plan→정렬된 Run→grant 잠금을 사용해 비종료 샤드 전체를 한 transaction에서 취소한다. worker가 개별 Node 취소를 전달한다. 취소 요청만으로 Lease를 반환하지 않는다.
- `reconcile_failures`는 현재 attempt의 저장된 실패/불확실한 receipt를 failed 상태로 반영한다. 자동 재실행·새 Lease 발급·다른 attempt 결과 채택을 하지 않는다.
- 샤드 간 socket/MPI/NCCL·입력 artifact mount·계산 reducer·parent Run coordinator·여러 물리 Node 동시 실행은 후속이다. 현재 `communication != none`을 계속 거절한다. 미전송 취소의 확정적인 never-start receipt 계약도 별도 후속이며 Node 부재를 물리 해제 증거로 대신하지 않는다.

## ADR-039: 실측 배치와 프로젝트 상한

- `PlacementStore.reserve(principal, project, run, Request, key, policy_version, node_ids, pool_version)`는 현재 project_nodes 안에서 후보를 제한한다. CPU/memory 관측·current channel/epoch·15초 freshness·Node 상태·clock skew·host busy·활성 Lease를 다시 읽어 기존 ADR-005 가중치 Scheduler로 계산한다.
- Explain의 snapshot digest/policy/weight/pool/limit version, 선택 Node와 실제 Lease, outbox와 멱등 응답을 한 transaction에 저장한다. reservation lock 순서는 ledger→Run→project `FOR NO KEY UPDATE`→상한 row→정렬 Node/Resource→grant다. FK의 KEY SHARE와 양립하는 project mutex를 사용한다. 기존 LeaseStore 경로도 동일 project 상한을 검사하므로 Adapter 우회로 초과 예약하지 않는다.
- `project_resource_limits`를 먼저 provision해야 새 배치 Adapter를 쓸 수 있다. 최초 상한 생성은 project mutex로 기존 예약과 직렬화한다. 변경은 동일 상한 row에서 version 증가와 현재 예약량 이상을 DB trigger가 검사하고 삭제를 금지한다. 업무 변경 API는 expected version 조건과 운영 권한을 별도로 확인해야 한다. 기존 미구성 project의 legacy Lease API 동작은 유지한다.
- `node_ids`는 권한 있는 project 목록을 좁히는 필터다. Claude의 pool CRUD/migration을 병합한 것이 아니며 pool membership/version 투영은 Claude Adapter가 구현해야 한다. 현재 상한은 project 단위이며 독립 pool별 상한은 후속이다.
- 최소 권한 runtime role에는 `SELECT`와 함께 `GRANT UPDATE(lock_sentinel) ON inv.project_nodes TO <runtime_role>`이 필요하다. PostgreSQL의 `SELECT FOR SHARE`가 요구하는 잠금용 권한이다. `enabled`·Node identity 변경 및 INSERT/DELETE 권한은 부여하지 않는다. sentinel은 CHECK(true)로 변경을 제한한다. 테스트 role과 실제 배포 role 설정에 같은 규칙을 적용해야 한다.
- GPU/VRAM 또는 `required_bytes > 0`인 요청은 측정 Provider가 연결될 때까지 거절한다. Node→CP 측정을 Node→Node locality로 사용하지 않는다. CPU/memory 외 cache/thermal/reliability/cost는 기존 Scheduler의 고정 기본값이며 새로운 실측으로 표시하지 않는다.
- Linux/PostgreSQL/Docker 합성 시험은 운영 5대·50동시/P95 2초 SLO 증거가 아니다. Windows/GPU/Storage 제품·PKI/IdP·업무 앱과 공통 migration 통합·독립 review는 여전히 남아 있다.

## 다음 담당자

Claude: 이 네 내부 Adapter의 project 권한/업무 의미 검증, 단위·상태·scope 변환, ORM/정본 DB migration 계보 조율, 실제 출력 수집과 검증 순서 연결, 기존 heartbeat/backup/미래 관측 지적 수정 및 독립 검토. Gemini: running/물리 정지/결과 확정/복원 세대를 구분하는 실제 API 화면 연결. Codex: Node 출력 publication, parent/샤드 통신·reducer, writable Workspace/Step/PTY, 실제 pool locality/복제/cache·S3, kill switch/drain 및 Windows/GPU·평가/운영 합격 증거. 인계 수신·검토 승인·main merge는 수행됐다고 기록하지 않는다.
