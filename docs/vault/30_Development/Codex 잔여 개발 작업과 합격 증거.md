---
doc_id: "CODEX-REMAINING-001"
title: "Codex 잔여 개발 작업과 합격 증거"
version: "1.10.0"
status: "review"
author: "Codex"
updated: "2026-09-11T09:32:53+09:00"
source_of_truth: "Git"
---

# Codex 잔여 개발 작업과 합격 증거

2026-09-11 실제 개발 환경 후속: [[2026-09-11_DEV-ENV_Codex_로컬개발환경구성과검증]]의 프로젝트/도구/CPU Studio를 구성했고 [[2026-09-11_NODE-COMPAT_Codex_검증보고]]에서 서버 서비스 재기동 및 실제 Docker API 1.41 Node 시험을 검증했다. 현재 다른 PC는 mTLS 관측 전용이다. 다음은 원격 시험 프로필 설치 후 실제 실행·복구, Studio와 제품 사용자/권한/Run/Lease/Evidence 연결이다. GPU·다중 Node 업무·5대 인수 및 독립 검토는 미완료다. 아래 과거 기록의 시험 미수행 문구와 통과 수는 해당 코드 SHA/범위에 한정한다.

2026-09-10 Workspace bridge 후속: 편집 revision/동결 입력, 명시적 대체 Node, 제한 PTY/ticket, 고정 GitHub 원격 Git/2인 승인/불확실 dispatch 보존 코드를 추가했다. [[Codex Workspace 편집과 PTY 및 원격 Git 계약]]과 [[2026-09-10_16-32-13_KST_WORKSPACE-BRIDGE_Codex_개발과정]]을 따른다. **사용자 지시로 실제 테스트는 미수행**이며 구현과 정적 build 전달 단계다. Codex의 즉시 다음 작업은 새 코드 전체 실제 회귀·DB/PTY/대체 Node/Git crash/CAS/권한 검증과 고정 SHA Evidence다. 독립 검토(Claude)·실제 API 화면/브라우저(Gemini), 대용량/장시간 PTY/다른 Git provider·Windows/GPU/BuildKit·Context/RO·물리 5대 인수는 남는다. 아래 과거 통과 수와 미구현 목록은 각 SHA 당시 기록이다.

2026-09-10 containment 후속: `091b8e5`에서 tenant kill switch·Node drain·고정 내용/만료/nonce/별도 2인 승인·현재 operator/별도 resume 권한·전송 전 거부 정리·독립 취소 처리·주기 예약 정리를 구현했다. 전체 990개 및 전용 28개가 통과했다. [[2026-09-10_15-33-52_KST_NODE-CONTAINMENT_Codex_검증보고]], [[Codex kill switch와 Node drain 및 정리 계약]]을 따른다. 다음 Codex 범위는 editor/PTY/remote Git·Workspace Node 이전, Windows/GPU/BuildKit·Context/RO와 실제 5대 검증이다. Claude 독립 검토/provisioning/운영 및 Gemini 실제 화면 연결은 남는다. 아래 kill/drain 미구현 문구는 이전 SHA 기준 기록이다.

2026-09-10 업무 kernel 연결 후속: `255b29e`에서 현재 public/kernel 권한 교집합, 실제 입력·새 승인·원자 큐·receipt/Evidence 기반 binding·자동 lock 해제를 구현했다. 전체 962개, 업무 전용 16개와 샤드 21개가 통과했다. [[2026-09-10_13-57-52_KST_BUSINESS-KERNEL_Codex_검증보고]], [[Codex 업무 binding과 실행 커널 연결 계약]]을 따른다. Codex 다음은 kill switch/drain·주기 reconciliation이다. public provisioning/첫 Run·checkout·editor/PTY·업무 router production 조합, PR14 실험 DB 이관, 실제 화면·독립 검토·5대 인수는 남는다. 아래 이전 PR14 통합 예정 문구는 해당 SHA 당시 기록이다.

2026-09-10 샤드 복구 후속: `3835b19`에서 새 승인·물리적 종료·원자 예약/큐·새 부모와 불변 계보·최대 3세대를 구현했다. 실제 두 Go/mTLS Node와 Docker로 전용 19개 및 전체 941개가 통과했다. [[2026-09-10_13-05-06_KST_SHARD-RECOVERY_Codex_검증보고]], [[Codex 샤드 재승인과 대체 Node 복구 계약]]을 따른다. Node는 한 CI 호스트의 별도 프로세스다. 공개 recovery route·운영/업무 연결(Claude), 실제 화면/브라우저(Gemini), 독립 검토와 5대 인수는 남는다. 다음 Codex 우선순위는 PR14 업무 연결과 migration/권한/실제 Evidence 통합, kill switch/drain·주기 reconciliation이며 PTY/remote Git·대용량/Workspace Node 이전·Windows/GPU/BuildKit·Context/RO 검증도 남는다. 아래의 재실행 미구현 문구는 과거 SHA 기준 기록이다.

2026-09-10 공개 API 후속: `e9dd341`에서 JWT 기반 prepare·새 승인·원자 예약/큐·실제 Node/Git/Evidence 연결, production 모의 서버 분리 및 양쪽 migration/제한 DB 역할을 검증했다. 전체 922개와 Go race 94 leaf case가 통과했다. [[2026-09-10_12-24-16_KST_WORKSPACE-API_Codex_검증보고]], [[Codex Workspace 공개 API와 실행 커널 통합 계약]]을 따른다. 아직 public 데이터/업무 이관·첫 Run/checkout/editor 연결·실제 화면·독립 review는 남는다. 다음 Codex 우선순위는 샤드 재실행·대체 Node·다중 Node 복구다. 이전 아래 표는 당시 고정 SHA 기록이다.

2026-09-10 Workspace 후속: `4f7d5d5`에서 새 승인 기반 Node 파일 실행·실제 로컬 Git·수정 checkpoint/Evidence·최대 3 attempt 복구를 검증했다. 통합 846개/Go race 93 leaf case 모두 통과했다. [[2026-09-10_10-09-50_KST_WORKSPACE-RESUME_Codex_검증보고]], [[Codex Workspace 실행 재개와 결과 체크포인트 계약]]을 따른다. 대용량/PTY/remote Git·샤드 재실행·다중 Node/실장비·업무/브라우저 통합과 독립 검토는 남는다. PR #12는 초안이며 아래 이전 기록과 그 미구현 문구는 당시 고정 SHA 기준이다.

## 2026-09-10 실행 완료 후속

현재 후속 정본은 [[Codex 실행 완료와 자원 회수 통합 계약]]이다. 실행 전 취소/등록 실패 회수, 실제 Node 출력/Evidence, 샤드 부모 완료·실패/취소 전파, 결과 확정 3회 재시도, writable checkout을 구현했다. 이하 기존 표의 출력/parent/파일 사본 미구현 문구는 과거 고정 SHA 기록이다. 실제 남은 것은 Node mount·새 Step 실행·PTY/Git, 최신 승인을 전제로 한 샤드 재실행, 다중 Node/collective, kill/drain·Windows/GPU/BuildKit·Context/RO·5대 운영 검증과 Claude/Gemini 업무 Adapter·화면 및 독립 검토다. PR #11에서 인계한다.


현재 제품은 5대 PC의 자원을 내부망 웹에서 안전하게 사용하는 개발·실행 환경을 목표로 한다. 코드/CI가 존재하는 kernel과 제품 전체 합격을 구분한다. baseline registry v1.0.0의 48 task와 12 Outcome은 선행·실장비·독립 검토 조건 없이 done으로 올리지 않는다. 이 표는 미구현을 숨기거나 다음 세션에 작업 승인을 다시 받기 위한 목록이 아니다.

owner Codex / reviewer Claude / task control-integration follow-up. 입력 GUIDE-001, PLAN-BACKEND/DB/STORAGE-001 v1.0.0, ADR-INDEX-001 v1.6.0. 현재 구현 HEAD는 이 문서와 연결한 History 검증 보고서로 고정한다. 작성자 자기 검증과 peer review를 혼동하지 않는다.

| 배정 task | 현재 확보한 kernel/증거 | 남은 구현 또는 합격 증거 |
|---|---|---|
| S01-BE/DB/ST | 정본 Schema, migrations 0001~0006, 강제 RLS, ID/권한/오류·trace 계약, package/CI/ontology | 실장비 5대·허용 폴더/자원·IdP/CA/DNS·Storage 제품 선택 및 운영 연결, peer review |
| S03-BE | 사전 승인 policy, 일회 ToolGateway, signed permit, Linux Docker 격리·정지 receipt | 업무 Workspace adapter, Windows driver/ACL, 운영 profile 및 실제 사용자 여정 |
| S04-BE/DB | 권한 있는 승인 challenge/decision·cancel API, 원자 ledger/outbox, bounded SSE/cursor, Node control cancel | workflow plan/approval request/dispatch daemon과 UI 통합, 오류·취소의 종단 자동 진행 |
| S04-ST | checksum/path 검증 함수, 합성 bytes 시험 | 제품 object storage의 resumable multipart, 중단/재개/동시 finalize/실제 checksum 검증 |
| S05-BE/DB/ST | deterministic ranking, locked Lease/Allocation/fencing, scope 검증 | quota/프로젝트 pool/실제 locality·전송비용 연결, 5노드 50동시 요청과 P95 실측 |
| S06-BE/DB/ST | Run 상태·attempt 경계와 Node durable intent/관찰 재개 | Git/PTY 권한·backpressure, durable Step/session/checkpoint, object snapshot 원자 publication과 실제 복원 |
| S07-BE/DB/ST | 현재 epoch/channel 검사, cancel/observation, heartbeat nonce·순서·timeout, Lease 물리 반환 | 자동 poll/sweep/reconcile/재스케줄 worker, drain 여정, 복제/cache pin/quota/GC 경합 |
| S08-BE/DB/ST | CPU sandbox와 독립 PID1 deadline, RLS, immutable audit/outbox, 기본 secret redaction | ROOF kill switch control·BuildKit·GPU/Windows 실측, secret provider, 안전한 retention GC, off-site backup/restore |
| S09-BE | bounded repair/policy·버전 및 RO 추적 kernel | 실제 Context/LLM adapter 연결, 100 Prompt/30 coding task의 근거 있는 eval·누출 시험 |
| S11-BE/DB/ST | Linux/PostgreSQL/Docker 합성 concurrency·crash·mTLS·권한 시험 | 장시간/부하/분할·스토리지 손상/용량·운영 migration/restore/rollback과 조건별 SLO 집계 |
| S12-BE | 설치 가능한 Python package, portable Node 빌드, 명시적 시작 config | 실제 설치·upgrade·rollback·5대 종단 여정·운영자 교육/인수 및 모든 선행 reviewer 승인 |

## 이어서 실행할 순서

1. 현재 control-integration을 같은 SHA의 CI·원본 Evidence·Obsidian 보고·draft PR로 전달한다. [[Codex 교차 코드 검토 - 인증과 실측 Evidence 정합성]]의 P1은 원 owner 수정 대상으로 유지한다.
2. Codex는 durable dispatch queue와 crash 뒤 observation 전환, 자동 cancel/reconcile의 권한·무결성 경계를 구현한다. 원격 실행 여부가 불확실하면 자동 재실행하거나 Lease를 반환하지 않는다.
3. Storage publication/pin/GC 및 Step/checkpoint 복원 계약을 확장한다. backend product 선택과 업무 adapter는 owner와 명시적으로 연결한다.
4. Claude/Gemini는 검토 오류 수정과 실제 API 연결을 각각 소유한다. UI의 고정 SLO·교육·Smoke·인수 flag는 개발 fixture이며 합격 Evidence로 승격하지 않는다.
5. 실제 IdP/CA/DNS/장비/저장소 값이 확인되면 실장비 검증을 실행한다. 현재 조회하지 못한 값을 임의 CA·IP·GPU 정보로 대체하지 않는다.

운영 정보와 타 Agent 독립 검토 없이 모든 Sprint done을 선언할 수 없다. 기존 사용자 승인 아래 로컬 구현·시험·commit/push/report는 계속 수행 가능하다. 운영 배포·자격 증명 변경·기존 데이터 파괴 작업은 실제 대상과 영향이 확정됐을 때 별도 critical 경계로 판단한다.


## Durable dispatch 후속 반영

[[2026-09-10_02-47-29_KST_DURABLE-DISPATCH_Codex_검증보고]]에서 claim/permit 원자 queue와 자동 전달·취소·관찰 worker를 구현/CI 검증했다. 위 S04/S06/S07의 dispatch daemon 항목 중 이 경계는 확보했으며 workflow enqueue adapter·heartbeat poll/sweep·Storage/Checkpoint·실장비 및 독립 검토는 남아 있다. 실제 운영 구성에 필요한 5대 PC 접속/IdP/CA/DNS/Storage 정보는 사용자에게 비밀을 제외한 값으로 요청했다. 답변 전 임의 운영 값을 만들지 않는다.

## Storage/Node 후속 반영

[[2026-09-10_03-15-23_KST_STORAGE-NODE_Codex_검증보고]]에서 local object publication/part 재개/checkpoint pin과 bytes 복원·GC 경합, Go 공지/실측 snapshot/자동 observer/제한된 전송, 독립 shard plan의 원자 queue와 실제 컨테이너 실행을 검증했다. S3 50GiB/제품 presign, 실제 Workspace 파일 복원/PTY, Artifact Evidence publication, MPI/NCCL·reducer·parent 결과, 5대 운영/Windows/GPU·실측 locality/peer Adapter/검토는 여전히 미완료다. 현재 구현만으로 S04/S05/S06/S07 전체를 done으로 올리지 않는다. 담당 분담과 구체 Adapter 입력은 [[Codex Node와 저장소 Adapter 실행 안내]]를 따른다.

## Execution recovery 후속 반영

[[Codex 전체 후속 구현 실행표]]와 [[Codex 결과 확정과 Workspace 복구 및 배치 계약]]에서 첫 네 영역을 이어 구현했다. 위 표의 역사적 미완료 항목 중 managed attempt/output commitment/Evidence 완료·새 generation의 실제 파일 복원·샤드 결과 manifest/전체 취소/실패 반영·실측 CPU/RAM/project 상한 예약은 내부 구현으로 확보했다. 실제 Node 출력 자동 publication과 업무 verifier, writable Workspace/PTY·Step/Git 재개, parent/collective/reducer, Claude pool/DB 통합과 실제 locality·대형 S3·cache·Windows/GPU·kill switch·운영/5대/Eval·독립 검토는 남는다. 이전 checkpoint 바이트 복원과 이번 실제 파일 복원을 혼동하지 않는다.
