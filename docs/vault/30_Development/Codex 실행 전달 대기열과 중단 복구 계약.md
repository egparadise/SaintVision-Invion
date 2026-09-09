---
doc_id: "DURABLE-DISPATCH-CONTRACT-001"
title: "Codex 실행 전달 대기열과 중단 복구 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T02:42:14+09:00"
source_of_truth: "Git"
---

# Codex 실행 전달 대기열과 중단 복구 계약

Task durable-dispatch / owner Codex / reviewer Claude(pending). base 7d657602d3f48122c20207cfff0919755e97f959 (draft #6). OUT-04/06/07의 전송 중단·불확실한 실행·취소 경계를 다룬다. 기존 업무 API/실제 운영 환경/독립 검토 완료를 대신하지 않는다.

## ADR-033 원자 permit 저장과 단 한 번 전송 예약

ToolGateway.claim의 명시적 queue_signing_key 경로는 권한·실제 Lease·policy·runtime 확인 뒤 같은 DB transaction에서 claim, signed permit envelope, enqueue outbox를 저장한다. signer/INSERT/event 실패면 전부 rollback한다. 반환 ClaimResult는 may_start=False/launch=None이며 임시 direct launch 권한을 동시에 주지 않는다. 기존 transient claim을 잃은 뒤 queue로 다시 seal하는 요청은 NODE-0061로 거절한다. queue를 사용하지 않는 legacy trusted caller는 기존 동작을 유지하므로 운영 workflow는 queue 경로로 명시적으로 연결해야 한다.

execution_deliveries의 envelope 및 scope는 불변이며 tenant RLS를 강제한다. 큐는 argv가 포함된 서명 permit을 서버 DB에 보관한다. 공개 route·SSE·로그에서 원시 내용을 제공하지 않으며 DB runtime role은 trusted service만 소유한다. envelope는 암호화된 값이 아니므로 운영 DB/backup 암호화와 secret provider의 참조만 전달하는 정책은 별도 적용 대상이다. signing private key 자체는 큐에 저장하지 않는다.

queued → uncertain → stopped만 허용한다. Run → queue → approval → Node/resources → sorted grants의 잠금을 따른다. 첫 예약 시 현재 Run/승인/quorum/grant/epoch/Lease/deadline을 다시 검사한다. 허가된 경우에만 execute를 예약하고 commit한 후 I/O한다. 이 commit이 start 권한의 선형화 지점이다. 이후 권한 변경과 이미 진행 중인 네트워크 실행 사이에는 물리 취소/Node policy 폐기의 기존 경계가 필요하다.

uncertain을 queued로 되돌리거나 다른 worker에게 execute 권한을 다시 주지 않는다. worker token/45초 lease로 다른 worker의 늦은 완료를 구분한다. 40초 최대 mTLS 호출이 끝나거나 worker lease가 만료되면 observe만 수행한다. 최초 전송 전 crash도 불확실로 취급하므로 미실행일 수 있는 작업을 자동 재시작하지 않는다. trusted operator의 새 승인/Run 또는 후속 정지 확인이 필요하다.

Run이 cancelled이면 execute 작업의 worker lease를 기다리지 않고 cancel 제어 작업이 한 번 인수할 수 있다. 이후 중복 cancel은 제어 lease/재시도 기한을 따른다. 오래된 execute worker의 완료는 새 token을 덮어쓰지 못한다. 취소보다 늦게 Node에 도달하는 기존 execute 요청은 Node permit deadline/관찰 계약을 따르며 proof 없이 반환하지 않는다.

NodeDelivery가 현재 mTLS channel에서 검증한 stop receipt를 resource 반환과 함께 commit한 후 queue를 stopped로 닫는다. 이 두 transaction 사이 crash는 receipt 존재를 확인해 queue만 닫는다. transport의 success dict, 예외, expiry, Node unknown-intent는 물리 증거가 아니다. DB trigger는 receipt 없는 stopped 및 terminal 상태/permit 변경을 거절한다. API Run succeeded는 별도 application Evidence이며 이 worker가 만들지 않는다.

실패는 generic code만 저장하고 2~30초 bounded backoff를 적용한다. 두 worker thread와 요청별 40초 mTLS 제한으로 메모리·동시 호출을 제한한다. 총 queue backlog/보존 GC/운영 경보·event collector는 별도이다. 자동 retry는 observe/cancel 전용이고 execute 재시도는 금지한다.

## 실행 구성

설치된 entry point: inv-delivery-worker 또는 python -m inv.worker. --once는 한 번 처리하고 stopped/uncertain/idle을 출력한다. 기본은 두 worker가 SIGINT/SIGTERM까지 대기열을 소비하며 활성 bounded 호출 종료를 기다린다.

필수 환경: INV_WORKER_CONFIG(운영자 JSON 파일 경로), INV_RUNTIME_DSN(최소권한 runtime DSN), INV_RECOVERY_EPOCH(설치된 UUID). config는 tenantId 및 tls만 가진다. tls는 ca_file/certificate_file/key_file과 선택적 timeout(최대 40초)을 사용한다. 서버가 생성한 기존 Node channel/pin/epoch를 그대로 확인한다. 운영 비밀·CA·장비 주소를 개발자가 임의로 채우지 않는다. 사용자 장비에서 service를 등록하거나 시작하지 않았다.

## 검증 및 다음 담당자

로컬 일반 Python 147 passed, 기존 PostgreSQL/Linux 136 skipped. 초기 신규 fixture dependency 누락으로 16 setup errors를 확인해 approval/node_runtime import를 추가했고 이후 신규 17개는 DB 미설정으로 정상 skip을 확인했다. 전체 301개(실제 DB·Linux Node 포함)의 합격 숫자는 원격 CI 후 별도 기록한다. 정상 실행·8 worker 경합·원자 rollback·grant 철회·취소 선점·RLS/불변 guard·응답 유실·실행 전 crash·실제 worker CLI를 검증한다.

Claude: 이 계약의 독립 검토 및 업무 workflow가 queue_signing_key 경로를 사용하는 adapter. Gemini: authenticated API의 resourceReleasePending 및 서버 관측 상태 반영. Codex: 원본 CI Evidence·보고·Obsidian 동기화, checkpoint/storage 불변 조건 후속. 아직 모르는 intent의 취소에서 자동 자원 반환을 구현했다고 주장하지 않는다.

Node의 단일 execution slot과 맞추어 최초 예약은 Node 행 잠금 아래 같은 Node의 활성 execute worker를 검사한다. 다른 Run이 슬롯을 보유하면 queued를 유지하고 기다린다. 이후 2개 Run의 동시 slot 예약 방지 시나리오를 추가해 신규 통합은 18개다. 이 대기는 실행 여부 불확실 상태로 잘못 전이하지 않는다.
