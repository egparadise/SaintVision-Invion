---
doc_id: "REVIEW-CLAUDE-001"
title: "2026-09-09 HO-DOC-CLAUDE-001 Claude 교차 검토 보고"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-09-09T15:45:31+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# HO-DOC-CLAUDE-001 교차 검토 보고

수신: Claude / 발신: Codex / 검토일: 2026-09-09 KST
base_sha: `5d23bd6ac103dde0288e7a9f4998338844d6fcad`
branch: `agent/claude/HO-DOC-CLAUDE-001`

읽은 문서와 버전: `CLAUDE.md`, `AGENTS.md`, GUIDE-001 v1.0.0, ADR-INDEX-001 v1.0.0, GOV-AGENT-001 v1.0.0, GOV-GIT-001 v1.0.0, PLAN-BACKEND-001 v1.0.0, PLAN-DB-001 v1.0.0, PLAN-STORAGE-001 v1.0.0, PLAN-S01 v1.0.0, PLAN-S02 v1.0.0, ONTO-TRACE-001 v1.0.0, HANDOFF-BASELINE-001 v1.0.0, ERR/RES-DESIGN-001~003, ERR/RES-ENV-001~004, TEMPLATE-01, skills `agent-delivery` v1.0.0 / `service-integration` v1.0.0.

범위: 계약·동시성·운영 누락 검토. **Frontend 계획은 Gemini 수신분이므로 검토 대상에서 제외했다.**

---

## 1. 요약

Codex 통합안은 Claude 보완안의 실제 결함을 정확히 지적했고, 그 지적을 **전부 수용한다**(§2). 통합안 자체에서는 **차단급 3건, 파일럿급 8건, 낮음 3건**을 발견했다. 차단급은 별도 오류 페이지로 기록했다.

차단급 3건은 공통점이 있다. **DB 계층의 정합성은 정의됐으나, DB 밖의 물리 세계(Node의 프로세스, Node의 기억, 각 기계의 시계)와의 경계가 정의되지 않았다.** 세 건 모두 DB 단위 시험은 통과하면서 실장비에서 깨질 수 있다.

## 2. Claude 원문에 대한 지적 — 전부 수용

| ADR | 지적 | 판단 |
|---|---|---|
| ADR-005 | 조건부 INSERT만으로 Lease 원자성 주장 | **수용.** READ COMMITTED에서 두 트랜잭션이 같은 합계를 읽으므로 초과 예약을 막지 못한다. 60_Gaps DB §3의 SQL은 결함이다. |
| ADR-004 | ContextPack/Bundle 혼용, `X-Trace-Id`, run/step ID를 span으로 서술 | **수용.** 60_Gaps Backend §10에서 `traceId → runId → stepId → toolCallId → evidenceId`를 "span 부모-자식 계층"이라 적은 것은 틀렸다. runId·stepId는 업무 연결 키이며 span ID가 아니다. 헤더도 `traceparent`가 맞다. |
| ADR-009 | item ID 배열만으로 ContextBundle 불변성 주장, `vector(1024)` 선고정, PostgreSQL FTS를 BM25로 지칭 | **수용.** 세 가지 모두 오류다. 특히 PostgreSQL 전문 검색은 `ts_rank`/`ts_rank_cd`이며 BM25가 아니다. 차원은 임베딩 모델 선정 후 결정해야 한다. |
| ADR-015 | Promtail 도입 | **수용.** EOL 2026-03-02. Alloy로 교체. |
| ADR-010 | inv URI 문법과 artifact 예제 충돌 | **수용.** 60_Gaps Storage §3에서 공통 문법 `<name>[@<version>]`을 정의하고 artifact 예제만 `runId/artifactId`를 쓴 것은 자기모순이다. namespace별 문법 분리가 맞다. |
| ADR-012 | Artifact 90일과 Evidence 1년 충돌 | **수용.** 두 보존 기간을 각각 제시하면서 참조 관계를 확인하지 않았다. |
| ADR-018 | 단일 서버 99.5% 서술 | **부분 수용, 아래 §4-L2 참조.** |

ADR-004, ADR-009, ADR-015는 책임이 Claude로 배정되어 있다. 구현 시 반영하며, ADR-009의 운영 귀결 하나를 §4-P7에 추가한다.

## 3. 차단급 지적 3건

구현 착수 전 owner 판단이 필요하다. 상세는 각 오류 페이지에 있다.

### B1. Lease 만료와 실제 자원 반환을 동일시함
→ [[ERR-DESIGN-005 Lease 만료와 실제 자원 반환 동일시]]

ADR-005와 [[DB 최종 개발 계획]]이 "활성 예약을 다시 읽고"라고 하면서 **"활성 예약"을 정의하지 않는다.** `expires_at > now()`를 포함하면 Node에서 아직 살아 있는 워크로드의 자원이 재예약되어 물리적 과예약이 발생한다. ADR-005는 DB 내부 경합만 해결한다.

제안: 활성 예약 = `released_at IS NULL`(만료 무관). 만료는 회수를 **시작할 조건**이지 가용량 증가 사건이 아니다.

### B2. 백업 복원이 fencing 단조성을 파괴함
→ [[ERR-DESIGN-006 백업 복원이 fencing 단조성을 파괴]]

PITR로 15분 전으로 복원하면 fencing sequence가 되돌아가지만 Node Agent의 기억은 되돌아가지 않는다. 정상 명령을 stale로 거부하거나(자원 있는데 배치 실패), 반대로 오래된 명령을 재수락한다(fencing 목적 무효화). ADR-006과 백업 계획이 교차 검증되지 않았다.

제안: 복원 runbook에 `setval` 전진을 필수 단계로 넣거나 토큰에 epoch를 포함한다. **Node Agent가 마지막 수락 토큰을 재시작 후에도 보존**해야 한다는 요구가 현재 없다. AC-07과 AC-08을 잇는 복합 시험을 추가한다.

### B3. 시각 동기화 요구가 없음
→ [[ERR-DESIGN-007 시각 동기화 요구 부재]]

Lease 만료, 이탈 감지 60초, 승인 만료, presigned URL 만료, 이벤트 지연 측정, Evidence 순서가 모두 서로 다른 기계의 시계에 의존하는데 NTP·스큐 한도·위반 시 동작이 어디에도 없다. 전제가 "사용자 소유 PC 5대"이므로 시계 관리가 보장되지 않는다.

제안: NTP를 등록 전제조건으로, 허용 스큐 ±5초(초기값), 초과 시 스케줄 제외, Node는 절대 시각이 아닌 **로컬 monotonic clock**으로 잔여 TTL을 판단, `node_clock_skew_seconds` 관측, S01 조사표에 시각 동기화 항목 추가.

## 4. 파일럿급 지적 8건

계약·계획 보완으로 처리 가능하며 별도 오류 페이지를 만들지 않았다.

**P1. Idempotency ledger의 계약이 불완전하다 (ADR-007)**
세 가지가 정해지지 않았다. (a) **응답 본문을 저장하는가** — 저장하지 않으면 재요청에 같은 응답을 돌려줄 수 없다. 저장한다면 크기 상한이 필요하다. (b) **보존 기간** — 무한 증가한다. 최소 클라이언트 최대 재시도 창보다 길어야 하고, 너무 짧으면 중복 창이 다시 열린다. (c) **동시 in-flight 중복** — 같은 키의 두 요청이 동시에 오면 UNIQUE로 하나가 지지만, 진 쪽이 이긴 쪽 결과를 기다릴지 즉시 409를 줄지 정의가 없다.

**P2. "신뢰된 worker"의 위치·시점·SLA가 없다 (ADR-011)**
"신뢰된 worker가 실제 bytes SHA-256 검증"이 맞는 방향이나, 업로드한 Node가 신뢰 주체일 수 없으므로 검증자는 객체를 **다시 읽어야** 한다. 최대 50GiB에 대한 재읽기 시간·대역폭 예산이 없다. 검증 지연 중 상태(staging → active) 전이 규칙과, 검증 대기가 쌓일 때의 백프레셔가 필요하다.

**P3. Evidence partition 고갈이 완료 보류로 연쇄된다 (ADR-008)**
[[DB 최종 개발 계획]]은 월간 partition 자동 생성과 알람을 정했다. 그러나 partition이 없으면 Evidence INSERT가 실패하고, ADR 상 성공 전이는 Evidence와 같은 트랜잭션이므로 **모든 Run이 완료되지 못한다.** 자동화 실패 하나가 제품 전면 정지가 된다. 최소 3개월 선행 생성과 잔여 2개월 미만 시 경고, 그리고 partition 부재를 기동 시 검사에 포함할 것을 제안한다.

**P4. Artifact 보존 pin의 해제 주체가 없다 (ADR-012)**
"Evidence가 참조한 필수 Artifact는 1년 이상 보존 pin"까지는 정해졌으나, 1년 뒤 Evidence가 삭제될 때 **누가 pin을 푸는지**가 없다. 풀지 않으면 저장소가 단조 증가한다. pin을 별도 가변 플래그로 두면 Evidence와 drift가 생기므로, **Evidence 행에서 파생되는 질의**로 정의하고 GC가 그 질의를 참조하도록 할 것을 제안한다. 법적 hold의 해제 절차도 함께 필요하다.

**P5. redaction 실패 시 동작이 없다 (ADR-014)**
"application/CLI 출력 전 1차, 수집기 2차"는 옳다. 그러나 1차 redactor가 예외를 던지면 로그를 버리는지, 원문으로 내보내는지가 정의되지 않았다. **fail-closed(격리 또는 폐기)** 를 명시해야 한다. 합격 기준의 "원문 비밀 노출 0건"이 여기에 걸린다.

**P6. lock_timeout·statement_timeout 정책이 없다 (ADR-005 운영)**
ADR-005가 `SELECT FOR UPDATE`를 도입하면서 경합 시 대기가 생긴다. 타임아웃 정책이 없으면 한 트랜잭션이 막혔을 때 스케줄러 전체가 정지하고 **P95 2초 SLO를 만족할 수 없다.** 예약 트랜잭션에 `lock_timeout`을 걸고, 초과 시 `RES-*`로 다음 후보를 시도하도록 정의할 것을 제안한다.

**P7. ContextBundle redacted snapshot의 저장 증가 (ADR-009, Claude 소유)**
ADR-009의 "redacted content snapshot 보존"을 그대로 구현하면 같은 원문이 bundle마다 중복 저장된다. content hash 기준 dedup 테이블과, RunRecord 보존 기간(프로젝트 수명)에 맞춘 정리 규칙을 함께 설계하겠다. 이는 지적이 아니라 **Claude가 구현 시 처리할 항목**으로 기록한다.

**P8. 알람 라우팅과 대응 주체가 없다**
[[Backend 최종 개발 계획]]은 측정 대상과 임계를 정했고 [[DB 최종 개발 계획]]은 "실패·용량 알람"을 정했다. 그러나 알람이 **누구에게 어떻게 가는지**가 없다. 파일럿은 소수 인원이므로 온콜 조직은 과하지만, 최소한 알람 채널과 심각도별 1차 수신자를 S01에서 확정해야 [[보안 평가 운영 가이드]]의 사고 대응 1단계(탐지)가 성립한다.

## 5. 낮음 3건

**L1. Gang scheduling의 다중 Node 잠금 순서**
ADR-005는 "Node→Resource ID 순서"를 정했다. 여러 Node에 걸친 gang 예약에서는 **Node 사이의 순서**도 고정해야 데드락이 없다. `node_id` 오름차순임을 명시할 것을 제안한다. 또한 점수 계산 단계는 잠금을 잡지 않고 **선택된 후보에 대해서만** 예약 트랜잭션에서 잠근다는 점을 계약에 적어두면 구현자가 전체 직렬화를 만들지 않는다.

**L2. 99.5% SLO 서술 (ADR-018)**
"99.5%는 측정 SLO이며 HA 제공이 아니다"는 정확하고 Claude 원문보다 낫다. 다만 파일럿 보고 시 **월 3.6시간이라는 예산 규모**와 계획 재시작이 그중 얼마를 쓰는지를 함께 적어야 사용자가 수치를 오해하지 않는다. 반박이 아니라 보고 양식 제안이다.

**L3. RLS와 향후 connection pooler**
transaction-local tenant scope는 `SET LOCAL`을 전제한다. 이후 PgBouncer를 transaction 모드로 도입하면 `SET LOCAL`은 안전하나 세션 수준 `SET`은 깨진다. 지금 결정할 사항은 아니고 **제약으로 문서화**만 해두면 나중에 사고를 막는다.

## 6. 확인했고 문제 없는 항목

과잉 지적을 피하기 위해 확인 후 문제 없다고 판단한 것을 남긴다.

- ADR-001의 11상태와 RunAttempt 분리, `timeout/lost`를 종료 사유로 강등한 처리
- ADR-002의 일정(S)·릴리스(R)·품질 게이트(G) 축 분리
- ADR-003의 Protobuf 제거와 JSON Schema 단일 원본
- ADR-013의 실제 의료 원본 초기 제외, 자동 등급 하향 금지
- ADR-016의 TBox/ABox 분리와 SHACL 도입 — Release-0.2.0에 shapes.ttl과 4개 SPARQL이 실제로 존재함을 확인
- ADR-017의 L0~L3 정본화
- [[Storage 최종 개발 계획]]의 MinIO 재검증 판단 — Claude 원문의 제품 선정을 archive 상태 근거로 보류한 것은 타당하다
- 업로드 계약(part 16MiB / 50GiB / 4 동시 / 1시간·15분)과 URL 미로깅
- Evidence app role의 UPDATE/DELETE 불가, 그리고 "superuser까지 완전 WORM이라고 주장하지 않는다"는 정직한 한계 서술

## 7. 수정 요구 정리

| ID | 대상 | 요구 | 제안 owner |
|---|---|---|---|
| CR-01 | ADR-005 / PLAN-DB-001 | "활성 예약" 정의를 `released_at IS NULL`로 고정 | Codex |
| CR-02 | ADR-006 / PLAN-DB-001 | 복원 시 fencing 단조성 보장 절차, Node 토큰 durable 저장 | Codex |
| CR-03 | S01 계약 | NTP·스큐 한도·monotonic TTL·스큐 관측 추가 | Codex |
| CR-04 | ADR-007 | ledger 응답 저장·보존 기간·동시 중복 규칙 명시 | Codex |
| CR-05 | ADR-011 / PLAN-STORAGE-001 | 검증자 위치·시점·SLA·백프레셔 명시 | Codex |
| CR-06 | ADR-008 / PLAN-DB-001 | partition 선행 생성 개월 수와 고갈 경고 | Claude(구현 시 반영) |
| CR-07 | ADR-012 | pin을 Evidence 파생 질의로 정의, 해제 절차 | Codex |
| CR-08 | ADR-014 | redaction 실패 fail-closed 명시 | Codex |
| CR-09 | PLAN-BACKEND-001 | 예약 트랜잭션 lock_timeout 정책 | Codex |
| CR-10 | PLAN-BACKEND-001 | 알람 채널과 심각도별 1차 수신자 | Claude(운영 문서) |
| CR-11 | ADR-005 | 다중 Node gang 잠금 순서, 점수 단계 무잠금 명시 | Codex |
| CR-12 | PLAN-DB-001 | RLS와 pooler 제약 주석 | Claude(구현 시 반영) |

CR-06, CR-10, CR-12, 그리고 §4-P7은 Claude가 자기 영역 작업에서 처리한다. 나머지는 owner 판단이 필요하다.

## 8. 검증

이 보고서는 문서 검토 결과다. **제품 코드·실장비 시험은 수행하지 않았다.** 수행한 검증은 다음과 같다.

| 명령 | 결과 |
|---|---|
| `python tools/check_docs.py` | 아래 개발 과정 기록 참조 |
| `python tools/check_ontology.py` | 아래 개발 과정 기록 참조 |
| `python tools/sync_obsidian.py --check` | 아래 개발 과정 기록 참조 |

ADR-005의 동시성 결함(§2)은 **논증으로 확인**했으며 실제 PostgreSQL 경합 재현은 하지 않았다. 재현 시험은 AC-05의 50 connection 시험에 포함되며 S05에서 수행한다.

## 9. 다음 행동

- 수신 확인: HO-DOC-CLAUDE-001 receipt를 `received`로 갱신
- Codex: CR-01~05, CR-07~09, CR-11 판단 후 ADR 개정 여부 결정. S01-BE/DB/ST 진행 시 반영
- Claude: S02 착수는 S01 완료 후. 그 전까지 CR-06/10/12·P7을 구현 계약 초안으로 준비
- Gemini: 본 보고서에 Frontend 지적 없음. HO-DOC-GEMINI-001은 별도 진행

실행 기록은 [[2026-09-09_15-45-31_KST_HO-DOC-CLAUDE-001_Claude_개발과정]].
