---
doc_id: "CORE-CONTRACT-001"
title: "Codex 핵심 기반 계약과 검토 회신"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-09T17:03:45+09:00"
source_of_truth: "Git"
---

# Codex 핵심 기반 계약과 검토 회신

사용자가 지정한 Obsidian 계획을 2026-09-09에 읽고 Git 정본과 비교했다. 차이 3개는 Claude 후속 보고 커밋 `3c53e90`의 내용이며 Codex 브랜치에 fast-forward 반영했다. 공통 지침과 영역 계획은 동일했다.

## TaskCard와 단계

- task_id `core-foundation`; owner Codex; reviewer Claude; status review 준비. branch `agent/codex/core-foundation`.
- base `3c53e90`(전체 SHA는 개발 보고 참조). OUT-01 → AC-01 → 계약·개발환경·검토 증거 → S01-BE/DB/ST.
- scope JSON Schema와 Python/TS/Go 생성 타입, PostgreSQL 핵심 migration, Scheduler/Lease/Run/Evidence/outbox 라이브러리, 정책·Storage 검증, CI.
- 선행 계약 GUIDE-001/ADR-INDEX-001/PLAN-BACKEND-001/PLAN-DB-001/PLAN-STORAGE-001 v1.0.0; Skill agent-delivery/core-reliability v1.0.0.
- 이 카드는 S01의 계약을 실행 가능한 시험으로 검증하는 조기 기반 작업이다. S05~S08 제품 작업은 선행 통합·장비 Evidence가 없으므로 planned를 유지한다.
- 합격 증거: 생성물 무변경 재생성, 단위 시험, 실제 PostgreSQL migration/50 connection 경합/RLS/rollback/복구 epoch, Python package와 Go/TS 타입 검사, 문서·Ontology 검사.
- 다음 담당 Claude: 본 계약과 migration의 독립 검토. Gemini: v1alpha1 타입 소비자 검토. 실제 인계 수신은 pending.

## 실행 경계

서비스 라이브러리를 신뢰된 Control Plane 내부에서만 사용한다. 브라우저에 SQL·DSN·정책 결정·정지 receipt 권한을 주지 않는다. OIDC/project ACL, Node mTLS·등록·실제 실행, One-time 승인 소비, SSE/WS, secret redaction 파이프라인은 후속 통합이다. `/healthz`만 생존을 응답하고 `/readyz`는 503을 유지한다. 이 패키지를 운영 서비스 완성으로 취급하지 않는다.

`Database`는 비owner·비superuser·비RLS bypass role, transaction-local tenant, READ COMMITTED를 사용한다. 권한은 tenant 격리이며 project ACL은 서비스 adapter의 별도 필수 조건이다. 핵심 migration은 Lease/Run 불변 조건 시험용 기반이며 Claude의 전체 업무 스키마 migration을 대체하지 않는다. 현재 Evidence는 비partition 테이블이다.

## Claude CR 회신과 ADR-019~023

| 항목 | owner 결정 | 구현·검증 범위 |
|---|---|---|
| CR-01 / B1 | ADR-019: 활성 예약은 `released_at IS NULL`, 만료·cancel·recovering·success는 자원 반환 사건이 아님 | 현재 합계·Offer·복구 전이 수정. Node adapter가 모든 관련 프로세스 정지를 확인하고 lease/token/node에 묶인 durable stop receipt를 제공해야 release 가능. Node 실장비 구현은 후속 |
| CR-02 / B2 | ADR-020: 토큰은 `recovery-epoch UUID:sequence`; epoch는 DB 백업 밖 운영 설정에 보존 | 현재 DB epoch·service epoch·Node enrollment epoch·Lease epoch 일치 검사. Node 영속 fence ledger와 실제 PITR 복합 시험은 S07/08 미완료 |
| CR-03 / B3 | ADR-021: 등록 전 NTP/시간 동기화 확인; 측정 스큐 ±5초 이내, 미측정도 배치 제외 | DB 예약 시 Node 스큐 확인. Node는 request 송신 monotonic 기준에서 RTT/안전 여유를 차감한 TTL을 사용하며 재부팅 시 과거 TTL 실행 금지. Node heartbeat·monotonic 집행은 후속 |
| CR-04 | ADR-022: project/operation/key에 request hash와 성공 응답 저장, 최대 1MiB; 예약 최대 128개 slice | 동시 동일 키는 unique 잠금 후 같은 응답, 다른 hash는 409. lock 초과는 RES-0007/503와 같은 키 재시도. 최소 24시간 재시도 창; 현 버전은 자동 삭제 없음. 향후 본문 정리 후 키/hash tombstone을 프로젝트 수명 보존해 재사용 금지 |
| CR-05 | 수용: Control Plane 관리 검증 worker가 업로더와 별개로 immutable object version을 스트리밍 재읽기 | 현재 로컬 trusted path bytes 검증만 구현. object staging→verifying→active, hash 실패 quarantine, durable bounded queue와 포화 시 init 429를 Storage adapter에 요구. 50GiB 처리 SLA/queue 용량은 제품·대역폭 실측 전 unknown |
| CR-06 | Claude 준비안 수용: 현재 월+이후 3개월 선행 생성, 잔여 2개월 경고·1개월 심각, 기동 가용 범위 검사, DEFAULT 없음 | partition 도입 migration은 Claude 담당. 현재 비partition substrate에 이미 구현됐다고 표기하지 않음 |
| CR-07 | 수용: Evidence 참조·진행 upload·active lease·MLflow·legal hold에서 pin을 파생 | GC는 같은 객체 잠금/트랜잭션에서 eligibility 재확인. Evidence 보존 종료와 참조 제거 후에만 대상; hold는 별도 권한·감사 기록으로 해제. object GC 구현 후속 |
| CR-08 | ADR-023: redactor 예외·형식 실패 시 원문 출력 금지, 고정 오류 코드만 기록 | 정책/스키마 오류에 payload 값 미포함. 애플리케이션/CLI redaction 파이프라인은 후속, 격리 실패 시 폐기 |
| CR-09 | 수용: 예약 lock_timeout 500ms, statement_timeout 2s 초기값, timeout/deadlock rollback 후 RES-0007 | 다음 후보/같은 키 재시도는 남은 전체 예산 안에서 수행. P95 2초 보장은 실측 전 주장하지 않음 |
| CR-10 | 알람 라우팅 초안 수용, 실제 채널/수신자 unknown | Claude 문서 유지, 사용자 운영 환경 확인 필요 |
| CR-11 | 수용: Run → 전체 Node ID 정렬 → 전체 Resource ID 정렬, lock 이후 별도 statement 합계 | 모든 writer 준수, score 단계 무잠금. 여러 Run을 한 txn에서 잠그는 확장도 Run ID 정렬 필요 |
| CR-12 | SET LOCAL/명시적 txn 수용 | 현재 RLS 시험 포함. tenant 미설정 SELECT는 0행, INSERT는 거부. 항상 SQL 예외여야 한다는 초안 표현은 수정 필요. pooler 실측은 미도입 |

P7 초안 추가 검토: content_hash PK만으로 UPDATE 불변성이 생기지는 않는다. `(tenant_id, content_hash)` 복합 키·권한/RLS·hash 검증·UPDATE 거부가 필요하다. bundle hash에는 ordinal/content hash뿐 아니라 sourceId/item version/TTL 등 실행 의미가 있는 metadata도 canonical serialization으로 포함해야 한다. 이 보완 요청은 Claude에게 전달 대기다. L2 SLO 보고는 실제 월 길이와 계획 중단 포함 여부를 함께 기록한다.

## 복원 절차와 Node 인계 조건

1. Scheduler·mutation·Node 신규 명령 중지 후 DB 복원. 기존 Control Plane 및 Node 연결 격리.
2. 이전 백업과 별도로 새 UUID epoch 생성·운영 설정 보존. 운영 권한으로 `inv.control_epoch` 행을 배타 잠금해 교체한다. 서비스는 동일 행 공유 잠금으로 실행 중 교체와 직렬화한다.
3. Node의 과거 실행 전부 중지·검증, durable fence ledger에 새 epoch 등록. 미연결 Node는 quarantined 유지. 임의 명령에서 새 epoch를 자동 학습하지 않는다.
4. 과거 lease는 실제 정지 확인 후 receipt로 정리. sequence 값이 돌아가도 epoch가 다르므로 과거 proof는 checkpoint/result 경계에서 거부한다.
5. Node enrollment epoch·스큐·허용 Offer 검증과 restore smoke 후 서비스 재개. runtime role은 epoch 변경 권한이 없다.

현재 시험은 DB epoch 변경·서비스 재연결·stale proof 거절이다. 실제 backup/PITR·Node 프로세스 종료·재부팅 ledger 시험은 수행 전이다.

## 보안·운영 제한

Storage `resolve_scoped`는 preflight다. 실제 파일 open handle/reparse point 교체 차단은 Node 구현에서 수행해야 한다. `complete`는 trusted verifier가 준 immutable snapshot 경로만 받으며 사용자 mutable 파일을 직접 전달하지 않는다. Evidence 참조 object pin은 아직 통합되지 않았다.

`Outbox`는 at-least-once다. consumer effect는 같은 DB connection을 사용해야 원자적이며 외부 부수 효과에는 별도 멱등성 키가 필요하다. broker callback은 deadline을 갖는 adapter여야 한다. 현재 코드가 네트워크 무한 대기를 자동 해결하지 않는다.

## 장비·배포 인벤토리

| 대상 | OS/CPU/GPU/RAM | 허용 폴더·사용량 | NTP/스큐 | 등록/mTLS |
|---|---|---|---|---|
| Node 1 | unknown | unknown | unknown | unknown |
| Node 2 | unknown | unknown | unknown | unknown |
| Node 3 | unknown | unknown | unknown | unknown |
| Node 4 | unknown | unknown | unknown | unknown |
| Node 5 | unknown | unknown | unknown | unknown |

IdP·내부 DNS/TLS·Storage 제품/라이선스·backup 장애 영역·알람 수신자는 unknown. 개발 PC를 제품 Node로 임의 등록하지 않는다. 이 값과 소비자 검토가 필요한 S01 작업은 done으로 표시하지 않는다.


## Gemini FR-01~07 계약 검토 회신

SPEC-FRONTEND-001 / REVIEW-GEMINI-001 v1.0.0은 Obsidian에서 제안으로 가져왔다. 문서 내 완료 주장은 작성자의 보고이며 Codex가 브라우저/배포 검증 완료로 승인한 것이 아니다. 다음 수정 후 S01-FE 재검토가 필요하다.

| 항목 | Codex 판단과 다음 계약 |
|---|---|
| FR-01 | sequence 재연결 수용. 5,000줄 외 byte/TTL 상한·session epoch·retention gap 응답·resize frame 검증 필요. PTY 실행은 재연결 때문에 재시작하지 않음 |
| FR-02 | ETag/If-Match 수용. 누락 428, stale 412. backend가 동일 파일의 compare-and-write를 atomic하게 수행해야 하며 read 후 별도 write로 검사하면 race가 남음 |
| FR-03 | 연결 제한 대응 수용. fetch Authorization SSE와 polling fallback, 탭 간 연결 예산 필요. 브라우저/프록시의 HTTP 버전을 무조건 정확히 감지한다고 가정하지 않음 |
| FR-04 | UI 비활성화는 안내다. 서버가 actor distinct·digest/scope·expiry·nonce를 같은 txn에서 검사해야 함. 현 core는 L3를 차단한다. L2의 2인 요구만 PolicyDecision에서 검증하며 승인 소비 adapter는 후속. 경로는 `/decision`, 초안의 `/decide` 정정 |
| FR-05 | UI 마스킹은 추가 방어로 수용. 서버가 이미 전송한 비밀 노출을 복구하지 못함. 메모리 토큰도 XSS에 안전하다는 보장은 없으며 XSS 방어와 출력 전 redaction 필수 |
| FR-06 | GRAPH/VERIFY와 LEASE도 오류 UI 매핑에 포함. 새로운 LEASE 코드군은 자원/복구 계열로 취급. 서버 retryable·현재 실행 상태에 따라 재시도 제한 |
| FR-07 | 프록시 location을 실제 `/v1/runs/{id}/events`, `/v1/workspaces/{id}/terminals/{sid}`에 매칭해야 함. 초안의 ID 없는 location은 해당 요청에 적용되지 않음. WS ticket은 URL 로그에서도 삭제. chunked off를 일괄 필수로 하지 말고 buffering/flush/heartbeat를 실제 proxy로 시험 |

Nginx는 buffering을 끄면 upstream에서 받은 응답을 즉시 전달한다([공식 문서](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering)). 실제 경로에 설정이 적용돼야 한다는 점은 현재 프로젝트 라우팅과 대조한 판단이다.

초안의 `compose stop`→동일 설정 `up`은 이전 digest로 변경하는 단계가 없으며 중단 구간이 생긴다. 이전 digest를 명시한 manifest 적용·기동/health·라우팅 전환·smoke 및 실제 시간 측정이 필요하다. Compose up은 설정/이미지 변경에 따라 컨테이너를 재생성한다([공식 문서](https://docs.docker.com/reference/cli/docker/compose/up/)). 10초·무중단은 실측 전 목표로만 표기한다. 구현 owner Gemini, 계약/인증 경계 reviewer Codex.

HIST-GEMINI-002의 하드웨어 사양은 합성 화면 데이터로만 취급하며 실제 Node 인벤토리를 채우는 근거가 아니다. WCAG/승인 검증 완료 서술은 별도 실행 로그·browser Evidence가 연결될 때까지 Codex 검증 미확인이다. 이 브랜치에는 해당 프론트엔드 구현 코드를 가져오지 않았다.
