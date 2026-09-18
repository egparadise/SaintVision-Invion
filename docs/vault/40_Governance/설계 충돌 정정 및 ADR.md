---
doc_id: "ADR-INDEX-001"
title: "설계 충돌 정정 및 ADR"
version: "1.35.15"
status: "baseline"
author: "Codex"
updated: "2026-09-15T15:14:17+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# 설계 충돌 정정 및 ADR


기존 문서를 덮어 해석하지 않고 정정 목록을 통해 구현 기준을 고정한다. 아래 결정은 Codex 통합 설계다. 원문 작성자의 동의나 제품 검증 완료를 뜻하지 않는다.

| ADR | 원문 문제 | 확정 기준·조치 | 책임 |
|---|---|---|---|
| ADR-001 | Run 상태 3종, Job 혼용 | 11상태 `draft, validated, planned, awaiting_approval, scheduled, running, verifying, recovering, succeeded, failed, cancelled`; Run은 논리 실행, retry는 별도 RunAttempt | Codex |
| ADR-002 | G0~G10 일정과 G0~G6 성숙도 충돌 | S01~S12 일정, R0~R4 릴리스, G0~G6 품질 게이트 분리; 첫 30일= S01~S02 | Codex |
| ADR-003 | Go/Python Control Plane, Protobuf 원본 중복 | FastAPI 모듈러 모놀리스·Go Node·TS Gateway; JSON Schema 원본, 생성 타입·검증·OpenAPI 정합화 | Codex |
| ADR-004 | ContextPack/Bundle, X-Trace-Id, 이벤트 이름 혼용 | ContextBundle, W3C traceparent, inv.* eventType; run/step ID는 span ID가 아닌 속성·연결 키 | Claude |
| ADR-005 | 조건부 INSERT만으로 Lease 원자성 주장 | 모든 관련 writer가 Node→Resource ID 순서로 잠금; 별도 다음 statement에서 최신 예약 합계 재조회; 트랜잭션 내 검사·예약; 실패 전체 rollback | Codex |
| ADR-006 | 노드 전역 최대 토큰이 타 정상 실행을 무효화 | fencing은 allocation/resource slice 범위; DB sequence는 table보다 먼저 생성; stale command를 실제 실행/결과 저장 경계에서 차단 | Codex |
| ADR-007 | Redis TTL만으로 쓰기 멱등성·outbox 무중복 주장 | durable PostgreSQL idempotency ledger, Redis 보조; outbox 재발행 가능, consumer inbox eventId UNIQUE | Codex |
| ADR-008 | SQL 예시 미완성 | FK 생성 순서, NULL 포함 unique, 모든 tenant 테이블 RLS·WITH CHECK·비owner app role, partition 키·Evidence 참조 검증 | Codex |
| ADR-009 | Context item ID 배열만으로 불변성 주장 | item version/hash와 redacted content snapshot 보존; 모델 정하기 전 vector(1024) 고정 금지; PostgreSQL FTS를 BM25라고 부르지 않음 | Claude |
| ADR-010 | inv URI 문법이 artifact 예제와 충돌 | namespace별 문법, artifact는 runId/artifactId; 최신 버전을 실행 계획에서 고정 | Codex |
| ADR-011 | checksum 메타데이터 신뢰, bytes/bps 혼용 | 신뢰된 worker가 실제 bytes SHA-256 검증; 전송 시간=bytes×8/bits-per-second; 빈 Dataset locality=0 | Codex |
| ADR-012 | Artifact 90일 삭제와 Evidence 1년 보존 충돌 | Evidence가 참조한 필수 Artifact는 1년 이상 보존 pin; 업로드·Lease·MLflow 참조·법적 hold는 GC 제외 | Codex |
| ADR-013 | raw 데이터 비식별화 후 자동 등급 하향 | 실제 의료 원본은 초기 시험 제외; 검증·소유자 판단 없이 등급 자동 하향 금지 | Codex |
| ADR-014 | Collector에서만 비밀 마스킹 | application/CLI 출력 전 1차, 수집기 2차; presigned URL·토큰·raw prompt 로그 금지 | Codex |
| ADR-015 | Promtail 도입 | EOL 확인: Grafana Alloy로 교체 | Claude |
| ADR-016 | 기존 Ontology의 namespace·예제·클래스 누락 | 원문 archive 유지, 새 TBox/ABox 분리, SHACL·SPARQL 검사, JSON-LD 동일 graph에서 생성 | Codex |
| ADR-017 | 명령 위험 등급 문서별 차이 | 거버넌스 L0~L3를 정본으로 하고 문자열이 아닌 실제 동작·범위·사전 승인으로 평가 | Codex |
| ADR-018 | 단일 서버=99.5% 불가능 주장·synchronous_commit=무손실 주장 | 99.5%는 측정 SLO; 로컬 durable write와 장애 영역 밖 복구 보장은 구분 | Codex |

## 상태 전이 추가 정리

위 11상태만 유지한다. 종료 전 모든 상태에서 `cancelled`로 가는 경로를 제공하고, 검증 불가·정책 거절·예산 소진은 현재 상태에서 `failed`로 종료 가능하게 계약 표에 명시한다. timeout/lost는 새 상태가 아닌 종료 사유다. `verifying → succeeded`는 결과와 Evidence 저장이 같은 트랜잭션에서 성공해야 한다. 자원 회수와 Run 전이는 상태 확인 후 멱등 처리한다.

## 인증·승인 예외 없는 실행 계약

Browser SSE는 Authorization 헤더를 지원하는 fetch 기반 스트림을 사용한다. 재연결 cursor·유실·중복 제거를 직접 시험한다. WebSocket은 TTL 30초 일회용 ticket과 Origin 검사를 사용한다. Node bootstrap·heartbeat·OIDC는 일반 사용자 mutation과 인증 맥락이 다르므로 계약별 멱등성 키/sequence 규약을 명시한다. 승인에는 내용 digest·actor·scope·만료가 묶이며 변경된 요청에는 이전 승인을 재사용하지 않는다.

## 공식 근거

- [PostgreSQL explicit locking](https://www.postgresql.org/docs/current/explicit-locking.html): 잠금은 트랜잭션 안에서 경합 writer의 순서를 제어한다. ADR-005는 이를 이용한 프로젝트 설계다.
- [Grafana Promtail → Alloy](https://grafana.com/docs/grafana-cloud/observe-and-act/send-data/alloy/set-up/migrate/from-promtail/): Promtail EOL 2026-03-02 확인.
- [W3C SHACL](https://www.w3.org/TR/shacl/): RDF 제약 검사 기준.
- [MinIO 공식 저장소](https://github.com/minio/minio): 2026-09-09 확인 시 archive 및 source-only 상태. [[Storage 최종 개발 계획]]의 제품 검증 과제에 반영한다.

외부 정보 확인일은 2026-09-09다. 원문의 최신 모델명·미검증 링크 전체가 검증됐다고 주장하지 않는다. 변동 기술 버전과 라이선스는 도입 Sprint에서 해당 공식 출처를 다시 확인한다.

## 2026-09-09 Codex 후속 결정

ADR-019(물리 자원 반환), ADR-020(복원 epoch), ADR-021(시계 스큐), ADR-022(멱등 응답/보존), ADR-023(redaction fail-closed)의 결정과 구현 범위는 [[Codex 핵심 기반 계약과 검토 회신]]을 따른다. ADR-005/006/007/014의 해당 문구를 이 결정으로 보완한다. Claude 독립 재검토는 pending이며 Node·운영 시험 완료를 뜻하지 않는다.

ADR-024(승인 내용 고정·distinct actor·nonce 원자 소비·dispatch/outbox/Run transaction)는 [[Codex 승인 경계 계약과 인계]]를 따른다. 서버 내부 계약의 사전 검증이며 공개 인증 adapter·실제 명령 실행 및 S04 완료를 뜻하지 않는다. 독립 reviewer Claude 검토 pending.

ADR-025(일회 실행 허가·불확실한 실행의 자동 재시도 금지), ADR-026(고정 Sandbox launch 계약)은 [[Codex ToolGateway 실행 허가와 Sandbox 계약]]을 따른다. OS 격리 driver·실장비 검증·교차 검토는 별도다.

ADR-027(서명된 Node permit·durable inbox·allocation high-water), ADR-028(독립 PID 1 deadline·삭제 확인 뒤 정지 영수증)의 계약은 [[Codex Node 실행 격리와 정지 영수증 계약]]이다. Linux 합성 컨테이너 검증과 운영 실장비/transport 검증을 구별한다.

ADR-029(mTLS peer 검증·기존 실행 observation) 및 ADR-030(인증서 CAS/폐기·영수증 commit 시 현재 권한)은 [[Codex Node mTLS 전달과 인증서 권한 계약]]을 따른다. 실제 운영 PKI/IdP·전체 등록/Heartbeat API 및 실장비 승인은 별도다.

ADR-031(resource-server 인증·현재 project grant)과 ADR-032(Run별 commit 순서 이벤트·mTLS 관측·원격 취소)는 [[Codex Control API 인증과 Node 관측 계약]]을 따른다. 실제 IdP/PKI·업무 adapter·운영 실장비 검증과 독립 검토는 별도다.

ADR-033(원자 permit queue·일회 전송 예약·중단 후 관찰/취소·receipt 후 종료)은 [[Codex 실행 전달 대기열과 중단 복구 계약]]을 따른다. 운영 worker 설정과 전체 업무/실장비 인수는 별도다.

ADR-034(제한된 local object publication·checkpoint pin·GC 중단 복구)은 [[Codex 저장 복원과 Node 실행 후속 계약]]을 따른다. S3 제품 및 실제 운영 복원/독립 검토는 별도다.

ADR-035(미검증 공지·mTLS 실측 snapshot·명시적 content 전송·독립 샤드 원자 admission)은 [[Codex 저장 복원과 Node 실행 후속 계약]]을 따른다. collective 통신/GPU 및 peer 업무 앱 연결 완료를 의미하지 않는다.

ADR-036(실행 attempt·fenced output commitment·receipt 후 Evidence 원자 확정), ADR-037(실제 Workspace snapshot과 새 generation 복원), ADR-038(샤드 결과 manifest·권한 있는 전체 취소·실패 반영), ADR-039(실측 CPU/RAM 배치·Explain/Lease와 project 상한 잠금)은 [[Codex 결과 확정과 Workspace 복구 및 배치 계약]]을 따른다. 업무 verifier/출력 수집·live Workspace/PTY·parent/collective·pool locality·운영 장비 연결과 독립 review는 별도다.

ADR-040(미발급 예약 회수·Node 미수신 취소 tombstone), ADR-041(실제 bounded 출력·정지 후보 보존), ADR-042(receipt 기반 결과 재시도와 샤드 부모 완료), ADR-043(writable checkout·변경 파일 보존)은 [[Codex 실행 완료와 자원 회수 통합 계약]]을 따른다. Node mount·PTY/Git·샤드 재실행/collective·실장비 및 독립 reviewer 인수는 별도다.

ADR-044(고정 Workspace 입력·새 승인·원자 예약/admission·총 3 attempt 상한), ADR-045(Node private tmpfs 실행·수정 파일/Git 결과 checkpoint의 원자 확정)는 [[Codex Workspace 실행 재개와 결과 체크포인트 계약]]을 따른다. 기존 11상태에 `recovering → awaiting_approval` 간선을 추가하고 업무 서비스/실행 코어/DB 정합성을 검증한다. checkpoint를 만든 attempt와 재개 직전 attempt를 구분하여 이전 checkpoint 재사용을 지원한다. PTY·대용량 전송·원격 Git·다중 Node/실장비 및 독립 검토는 별도다.

ADR-046(실행 kernel을 권위로 하는 공개 Workspace API·승인/예약/큐의 원자 등록), ADR-047(명시적 production 설정·모의 서버 분리·기존 양쪽 migration history의 merge 및 제한 runtime 그룹)은 [[Codex Workspace 공개 API와 실행 커널 통합 계약]]을 따른다. 현재 project grant와 새 distinct 승인을 실제 Node 경로에 연결하며 `accepted`와 실행 시작을 구분한다. public 데이터 이관·전체 업무/화면 연결·실장비·독립 review는 별도다.

ADR-048(물리적 종료·동일 작업·새 승인에 따른 독립 샤드 대체 Node 실행), ADR-049(불변 부모/자식 계보·최대 3개 실행 세대·하나의 후속 계획·원자 admission)은 [[Codex 샤드 재승인과 대체 Node 복구 계약]]을 따른다. 공개 recovery route/UI·Workspace Node 파일 이전·collective·5대 PC·독립 검토는 별도다.

ADR-050(실제 kernel 기록에서 계산하는 불변 업무 binding·물리적 완료 후 자동 편집 lock 해제), ADR-051(명시적 OIDC/업무 identity 연결·현재 권한 교집합·기존 revision 보존), ADR-052(최초 전송 전 권한 상실의 취소 tombstone 및 관측 전용 bounded 재시도)는 [[Codex 업무 binding과 실행 커널 연결 계약]]을 따른다. 일반 CRUD/provisioning/editor/PTY·PR14 실험 DB 이관·5대 인수와 독립 검토는 별도다.

ADR-053(tenant 실행 barrier·별도 현재 operator 권한·불변 제어 감사), ADR-054(Node drain·전송 전 거부의 취소 tombstone·물리 정리 후 명시적 재개), ADR-055(bounded reconciliation·독립 취소 처리·old epoch 예약 보존)는 [[Codex kill switch와 Node drain 및 정리 계약]]을 따른다. 운영 PKI/서비스·UI·5대 SLO·독립 인수 및 전체 ROOF/Windows/GPU/BuildKit 검증은 별도다.

ADR-056(제어 변경의 현재 2인 L2 승인·검증된 서로 다른 사람·고정 내용/epoch/version/만료/nonce·승인 소비와 제어의 원자 확정)은 [[Codex kill switch와 Node drain 및 정리 계약]] v1.1.0을 따른다. 초기 operator-only 경계의 정정이며 자동 비상 예외를 만들지 않는다. 0022 뒤에 0023 forward migration을 추가하고 과거 기록은 보존한다.

ADR-057(불변 editor revision과 승인 snapshot 일치), ADR-058(명시적 목적지 Node와 새 승인), ADR-059(제한 PTY·일회 ticket·현재 권한·bounded 입력/출력), ADR-060(고정 Git provider·현재 2인 승인·expected head publication·불확실 dispatch 재전송 금지)은 [[Codex Workspace 편집과 PTY 및 원격 Git 계약]]을 따른다. 2026-09-10 build-only 기록은 보존한다. 후속 실제 시험과 통합은 ADR-071을 따른다. 0024는 forward only다.

ADR-061(Windows 사용자 전용 개발 Studio·개발 도구와 제품 실행 권한 분리)은 [[Codex 개발 Studio와 제품 실행 경계]]를 따른다. 프로젝트·도구·로컬 CPU 개발 컨테이너를 제공하며 PostgreSQL Run/승인/Node permit/Evidence를 대체하지 않는다. 다중 사용자·원격 업무·GPU 기능은 별도 검증 전까지 비활성이다.

ADR-062(Linux Docker API 1.41~1.45 범위 협상·실제 격리 설정 재검증·512 KiB/1개 json-file 출력 로그)은 [[Codex Node 실행 격리와 정지 영수증 계약]] v1.1.0을 따른다. 성공한 협상만 캐시하고 실행 변경 요청의 자동 재전송은 금지한다. DB/permit/승인 계약은 유지한다. 기존 local logging driver 설정은 서버 20.10 호환성 문제에 따라 정정하며 실제 장비 검증 범위는 [[2026-09-11_NODE-COMPAT_Codex_검증보고]]에 기록한다.

ADR-063(실행 이력이 없는 draft Run의 불변 첫 입력·명시적 Node/자원/버전 고정·원자 승인 소비/예약/queue·attempt 1 및 결과 checkpoint)은 [[Codex Workspace 첫 실행과 승인 입력 계약]]을 따른다. 첫 실행은 startId/initialized, 복구는 resumeId/restored로 구분한다. 0025 forward migration을 현재 실제 head 0023 뒤에 추가한다. 운영 사용자/프로젝트 provisioning·화면·원격 PC 설치와 독립 검토는 별도다.

ADR-064(같은 JWT 검증·명시적 업무 route 조합·분리된 inv_app/inv_kernel DB 계정), ADR-065(별도 운영자 관리 grant·현재 tenant definer·Project/Node writer 직렬화)는 [[Codex 계정과 실행 커널 통합 계약]]을 따른다. 0026에서 두 공개 0025 이력을 보존해 합치고 0027로 권한을 보강한다. 운영 IdP/provisioning·원격 Node·UI·독립 재검토는 별도다.

ADR-066(현재 커널 Run/attempt/receipt/Evidence 조회와 검증된 파일 다운로드), ADR-067(실제 권한을 확인하는 준비 상태·원격 도구 미관측 시 unknown)은 [[Codex 실제 실행 결과 조회 계약]]을 따른다. public Run 기록과 실제 커널 실행 상태를 혼동하지 않는다. 0028에서 새 subject lookup 이력과 기존 권한 이력을 보존해 병합하고 tenant guard를 적용한다.

ADR-068(명시적 계정/요청·승인 권한의 insert-only 원자 준비·현재 계정 잠금·불변 감사·공개 migration 이력 보존)은 [[Codex 계정 준비와 실행 권한 계약]]을 따른다. 계정 연결이 Node/Workspace 실행 가능을 뜻하지 않는다. 0030에서 두 결과 이력을 합치고 subject guard와 canonical 다운로드 경계를 유지한다.

ADR-069(현재 관리자 권한·capability 전체 제공량을 모든 kernel slice에 원자 배분·Node→Resource 직렬화·GPU device 미매핑의 명시적 pending)은 [[Codex 자원 제공량과 예약 원자 반영 계약]]을 따른다. 0031은 두 공개 0030 이력을 보존한다. 결과 정본 및 다음 담당은 [[Codex 실제 실행 결과 조회 계약]] v1.1.0과 [[3 Agent 원격 실행과 운영 인수 확정]]이다.

ADR-070(과거 migration 원본과 현재 적용 함수의 검증 구분·공개 이력 보존·현재 epoch/동일 project/대기 Run의 입력 진단)은 [[2026-09-11_Claude_잔여보고_Codex_독립검토]]를 따른다. 0032는 두 0031을 보존해 병합한다. 결과 URL은 kernel ResultView만 제공하고 업무 surface는 별도 readiness router를 사용한다. 로컬 회귀·CI·독립 검토·실제 운영 인수 상태는 분리한다.

ADR-071(공개 0024/0032 이력의 0033 병합·첫 실행과 복구의 명시적 PTY 허용·협상된 Docker helper API·Git replay의 현재 public 권한 재검사)은 [[Codex Workspace 편집과 PTY 및 원격 Git 계약]] v1.1.0을 따른다. branch별 build-only 유예를 제거하며 로컬 실제 실행·CI·독립 검토·물리 장비 운영 인수는 각각 기록한다.

ADR-072(정확한 definer 정의/시그니처/EXECUTE 정책·필수 inventory·read-only snapshot·관측 실패 거부)은 [[Codex DB 함수 감사와 복원 판정 검토]]를 따른다. catalog 일치와 전체 tenant/복원 안전을 구분하며 실제 mutation/권한 시험·독립 검토를 별도로 요구한다.

ADR-073(복원 nonzero/누락/불확실 관측 거부·정본 definer 정책·양쪽 tenant probe·실측 구간·다음 fencing 값·DB 기록 정합성)은 [[Codex DB 함수 감사와 복원 판정 검토]] v1.1.0을 따른다. DB 리허설과 객체/Node/별도 클러스터/실제 서비스의 운영 복구 합격은 구분한다.

ADR-074(PTY 전송 전 불변 intent commit·확인된 응답 audit 분리·미확정 입력의 digest 고정과 후속 순번 거부·기존 이력 보존)은 [[Codex Workspace 편집과 PTY 및 원격 Git 계약]] v1.2.0을 따른다. 0034는 일반 표 추가이며 definer 정의/권한 정책은 그대로이고 정책 head만 갱신한다.

ADR-075(opaque immutable credential reference·Linux service-owned file backend 구현 기준·현재 scope/회수/목적지 검사·기존 CLI 로그인 관측과 hosted provider 분리)와 ADR-076(제한된 LocalObjects 파일럿·운영 S3 합격 조건·기존 보존 기간·객체/DB/키의 복원 책임 분리)은 [[Codex 운영 자격증명과 Storage 계약]]을 따른다. [[운영 환경 입력과 Agent 인계]]에 미확정 운영 값과 담당자를 둔다. 실제 resolver/운영 배포·제품 선택·독립 인수 완료가 아니다.

ADR-077(Linux descriptor/hash-bound credential backend·PostgreSQL 현재 scope/epoch/회수·runtime SELECT-only·최종 확인 admission과 callback 분리)는 [[Codex 운영 자격증명과 Storage 계약]] v1.2.0을 따른다. 0035는 private version/grant metadata를 추가하며 실제 secret/provider/운영 인수를 대신하지 않는다.

ADR-078(Context metadata 저장 전 비밀 패턴 거부·오류 입력 비반사·운영 CLI 진단과 kernel 인가 분리·DSN 보호 환경/고정 오류·읽기 전용 일관 snapshot)은 [[2026-09-12_CREDENTIAL-BACKEND_Codex_검증보고]]를 따른다. 공개 readiness API 변경·운영 인수 완료가 아니다.

ADR-079(보호 운영자 register/grant 분리·current epoch/scope·Run 범위 원자 회전·폐기 권한 비재활성화·감사 rollback·기본 check/명시 apply)은 [[Codex 자격증명 등록 회전 회수 운영 절차]]와 [[Codex 운영 자격증명과 Storage 계약]] v1.3.0을 따른다. 공개 관리 API·운영 secret 등록·독립 인수 완료가 아니다.

ADR-080(archive 설정과 운영 RPO 분리·command/library marker·공통 CLI/DB acceptance·실패/중단 목표 달성 거부·0036 과거 기록 보존/신규 쓰기 제약)은 [[Codex DB 함수 감사와 복원 판정 검토]] v1.2.0과 [[2026-09-12_RPO-CAPABILITY_Codex_검증보고]]를 따른다. 운영 PITR·전수 과거 기록 검증 완료가 아니다.


ADR-081(private Linux 백업 비파괴 게시·file/directory sync·저장 바이트/identity 재검사·BackupRecord/drill 원자 기록·실패 후 파일 보존)은 [[2026-09-12_BACKUP-LEDGER_Codex_검증보고]]와 [[Codex DB 함수 감사와 복원 판정 검토]]를 따른다. 운영 RPO·별도 장애 영역·Windows 네이티브 저장 지원을 뜻하지 않는다.


ADR-082(tenant/project/user/contract별 관측 비교·lock 이후 일관 transaction·관측시각 보존·owner 전용 명시 기록·현재 인가 unknown)과 ADR-083(AC-12 기록 목록과 운영 인수 증거 분리·만료/목표/criterion 검사·공통CLIexit)는 [[Codex 권한 관측과 운영 인수 집계 계약]]과 [[2026-09-12_PERMISSION-SNAPSHOT_Codex_검증보고]]를 따른다. 운영 Evidence 평가 수집기·실장비·독립 인수 완료가 아니다.


ADR-084(백업 bytes 검증 전 tenant/row잠금·기존checksum 불변 비교·검증 성공 savepoint·항목별 sweep 실패 격리·과거 관측과 현재 정상 분리)는 [[2026-09-12_BACKUP-VERIFY_Codex_검증보고]]를 따른다. open-time 경로 보호·durable 실패 관측/Evidence 연결·운영 인수 완료가 아니다.


ADR-085(명시적 worker ReadRoot·root identity pin·Linux descriptor/Windows reparse handle 경계·N+1 bounded unbuffered 두 번의 hash 관측·같은 timestamp의 덮어쓰기 방어)는 [[Codex 허용 저장소 파일 검증 계약]]과 [[2026-09-12_BACKUP-ROOT_Codex_검증보고]]를 따른다. node identity·snapshot·운영 RPO 인수의 대체물이 아니다.


ADR-086(local-storage-sample-v1:명시적 root·READ ONLY sample/size 검증·--node는 선언·운영 기록0·빈/검증불가 sample 정상 판정 거부·과거 boolean 재평가)는 [[Codex 로컬 폴더 점검과 Node 증명 계약]]과 [[2026-09-12_STORAGE-CHECK_Codex_검증보고]]를 따른다. 인증된 Node 관측의 기록/Evidence 연결은 후속이다.


ADR-087(ASGI client_cert_error 최종 거부·잘못된 direct chain의 proxy fallback 금지·inbound 관측 기록 transaction의 현재 tenant/node/certificate/status row lock)은 [[2026-09-12_NODE-AUTH-COMMIT_Codex_검증보고]]를 따른다. storage challenge·kernel epoch 증명·Evidence 쓰기는 후속이다.


ADR-088(내부 Run/ChannelProof/root/catalog/nonce-bound Ed25519 sample·공유 ReadRoot sampler·사전 byte budget·검증과 durable nonce/Evidence 기록 분리)는 [[Codex 로컬 폴더 점검과 Node 증명 계약]] v1.1.0 및 [[2026-09-12_STORAGE-SIGNED-SAMPLE_Codex_검증보고]]를 따른다. Go endpoint/실제 장비·운영 DB 기록 완료가 아니다.


ADR-089(공통 Schema·Go opt-in 보호 폴더/mTLS 서명 sample·Linux descriptor 경계·실제 TLS peer certificate 반환·운영 기록 분리)는 [[Codex 로컬 폴더 점검과 Node 증명 계약]] v1.2.0 및 [[2026-09-12_STORAGE-NODE-TRANSPORT_Codex_검증보고]]를 따른다. durable nonce/Evidence commit·운영 .225 인수는 후속이다.


ADR-090(현재 프로젝트 요청 권한+폴더 등록 소유자·durable challenge/nonce·기존 Evidence/StorageCheck 원자 쓰기·같은 응답 replay·최소권한/RLS/불변 기록)는 [[Codex 로컬 폴더 점검과 Node 증명 계약]] v1.3.0과 [[2026-09-12_STORAGE-COMMIT_Codex_검증보고]]를 따른다. 공개 API/운영 설치·실장비 인수/Run 완료와 구분한다.


ADR-091(현재 원 요청자/등록 소유자의 과거 storage observation 조회·당시 서명 및 기존 Evidence 연결 재검증·UTC 시각 의미·pending/expired/recorded·currentHealth unknown·정보 최소화)는 [[Codex 로컬 폴더 점검과 Node 증명 계약]] v1.4.0과 [[2026-09-12_STORAGE-VIEW_Codex_검증보고]]를 따른다. 운영 현재 health/Run 완료·수집 시작·배포 완료와 구분한다.


ADR-092(contribution별 root/channel 독립 최소 버전·hash의 기존 journal 영속화·같은 버전 변경 거부·현재 인증서/root 검증 후 pin·로컬 시작 기록과 운영 인수 분리)는 [[Codex 로컬 폴더 점검과 Node 증명 계약]] v1.5.0, [[Codex Node 저장소 설정 설치와 교체 절차]], [[2026-09-12_STORAGE-POLICY_Codex_검증보고]]를 따른다. 전체 journal 삭제/backup rollback·실장비 전원 장애 인수까지 보장하지 않는다.


ADR-093(명시적 source/policy hash·새 컨테이너 읽기 mount·보호 파일 재검증·Go 시작 기록 대조·기존 Node 자동 교체 금지)는 [[Codex 로컬 폴더 점검과 Node 증명 계약]] v1.6.0과 [[2026-09-12_STORAGE-BUNDLE_Codex_검증보고]]를 따른다. 원격 Windows/WSL 배포·운영 인수는 후속이다.


ADR-094(정지 관측 Node 교체 전 비변경 점검·bounded state digest·현재 container/volume/plan 결합·stale 거부·교체 승인과 분리)는 [[Codex 로컬 폴더 점검과 Node 증명 계약]] v1.7.0과 [[2026-09-12_STORAGE-REPLACE-PREFLIGHT_Codex_검증보고]]를 따른다.


ADR-095(기존 container/정책 보존·private durable 단계·same-plan forward 재개·변경 허용 파일 제한·ID 고정·로컬 설치와 운영 인수 분리)는 [[Codex 로컬 폴더 점검과 Node 증명 계약]] v1.8.0과 [[2026-09-12_STORAGE-REPLACE_Codex_검증보고]]를 따른다.

ADR-096(Windows 입력·WSL 고정 private 준비·request SHA 지정 apply·같은 요청 재개·운영 인수 분리)는 [[Codex 로컬 폴더 점검과 Node 증명 계약]] v1.9.0과 [[2026-09-12_STORAGE-WINDOWS_Codex_검증보고]]를 따른다.


## VF 서비스 통합 정정 — 복제본 가용성과 보존 분리

ADR-012를 보강한다. Node 이탈은 복제본을 stale로 만들지만 기존 pinned_until을 삭제하지 않는다. ready/stale에 retention pin을 허용하는 0043 forward migration을 사용하며 stale는 실행·복사 source·eviction 후보가 아니다. 아직 회수되지 않은 stale/corrupt 바이트도 cache 용량에 포함한다. URI version과 식별자에는 경로 구분 slash를 허용하지 않고 parse/build 왕복이 불가능한 빈 suffix는 거부한다. [[2026-09-15_VF-SERVICE-REVIEW_Codex]]의 실제 재현/수정 증거 참조. Codex 수정의 Claude 재검토와 운영 적용은 pending이다.


## VF 모델 업무 등록과 실행 manifest 경계

ADR-010을 보강한다. [[모델 레지스트리와 실행 Manifest 권한 경계]]에 따라 S10 registry와 kernel manifest를 명시적 결속 전까지 구분한다. 이름/URI/hash의 일치가 결속·정책승인·실행 permit을 만들지 않는다. inv_app 직접 kernel 접근을 허용하지 않고 현재 프로젝트 권한을 검사하는 API를 후속 구현한다. [[2026-09-15_VF-MODEL-REVIEW_Codex]]의 독립 finding 판정과 회귀시험을 따른다.
