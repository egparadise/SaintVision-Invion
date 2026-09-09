---
doc_id: "ADR-INDEX-001"
title: "설계 충돌 정정 및 ADR"
version: "1.1.0"
status: "baseline"
author: "Codex"
updated: "2026-09-09T15:10:54+09:00"
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
