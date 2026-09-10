---
doc_id: "PREP-CLAUDE-001"
title: "Claude 영역 구현 준비"
version: "1.0.0"
status: "draft"
author: "Claude"
updated: "2026-09-09T16:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# Claude 영역 구현 준비

**이 문서는 S01 완료 전 준비 초안이다.** 제품 구현·검증은 시작하지 않았고, 여기의 결정은 S01의 계약이 확정되면 재확인한다. S01 계약은 owner(Codex) 소유이며 본 문서가 이를 대체하지 않는다.

배경: [[2026-09-09_15-45-31_KST_HO-DOC-CLAUDE-001_Claude_검토보고]]에서 Claude가 자기 영역에서 처리하기로 한 CR-06, CR-12와 §4-P7을 구현 가능한 수준으로 미리 정리한다. 나머지 CR은 owner 판단 대기다.

대상 작업: S02-DB, S03-DB, S09-DB, S03-ST, S02-ST (전부 `planned`, 선행 S01 미완료)

---

## 1. CR-06 — Evidence partition 고갈 방지

### 문제

ADR-008과 [[DB 최종 개발 계획]]은 월간 partition 자동 생성과 알람을 정했다. 그러나 partition이 없으면 `evidence_envelopes` INSERT가 실패하고, ADR상 `verifying → succeeded` 전이는 Evidence와 같은 트랜잭션이므로 **모든 Run이 완료되지 못한다.** 자동화 실패 하나가 제품 전면 정지로 번진다.

### 결정

| 항목 | 값 | 근거 |
|---|---|---|
| 선행 생성 개월 수 | **3개월** | 월간 잡이 2회 연속 실패해도 여유가 남는다 |
| 경고 임계 | 잔여 **2개월** 미만 | 다음 정기 잡 이전에 사람이 개입할 시간 확보 |
| 심각 임계 | 잔여 **1개월** 미만 | |
| DEFAULT partition | **두지 않는다** | DEFAULT에 행이 들어가면 해당 범위의 새 partition을 붙일 수 없다. 조용한 성공보다 명시적 실패가 낫다 |
| 기동 시 검사 | 필수 | 잔여 개월 수가 1 미만이면 Control Plane이 기동을 거부하고 사유를 로그에 남긴다 |

DEFAULT partition을 두지 않는 선택은 트레이드오프다. 두면 INSERT가 성공하지만 나중에 분리 작업이 필요하고, 그 사이 조회 성능이 나빠진다. Evidence는 **누락이 완료 보류로 이어지는 것이 설계 의도**이므로(ADR-008), 조용히 받아두는 쪽이 오히려 계약에 어긋난다.

### 적용 대상

`evidence_envelopes`, `resource_snapshots`, `audit_events` — 세 partition 테이블 모두 같은 규칙을 쓴다. 다만 `resource_snapshots`는 보존 90일이므로 선행 생성 3개월이 곧 보존 기간과 겹친다. 생성 잡과 삭제 잡을 **같은 트랜잭션에 넣지 않는다** — 삭제 실패가 생성 실패를 유발하면 안 된다.

### 미확인

- 월간 잡의 실행 주체(cron / pg_cron / 애플리케이션 스케줄러)는 S01-BE의 개발 환경 결정에 의존한다. `unknown`.

---

## 2. CR-12 — RLS와 connection pooler 제약

### 문제

[[DB 최종 개발 계획]]은 tenant 격리를 `ENABLE/FORCE RLS` + `WITH CHECK` + 비owner app role + **transaction-local tenant scope**로 정했다. transaction-local은 `SET LOCAL`을 전제한다.

이후 PgBouncer 같은 pooler를 **transaction 모드**로 도입하면 세션이 트랜잭션 단위로 재배정된다. 이때 `SET LOCAL`은 트랜잭션 안에서만 유효하므로 안전하지만, 세션 수준 `SET`이나 트랜잭션 밖에서 설정한 값은 **다른 tenant의 요청에 새어 들어간다.**

### 결정

1. tenant scope는 **반드시 `SET LOCAL`** 로 설정하고, 트랜잭션 밖에서 설정하지 않는다.
2. 모든 tenant 접근 경로를 **명시적 트랜잭션 안**에서 실행한다. autocommit 단문 조회도 예외를 두지 않는다.
3. 이 제약을 코드 주석이 아니라 **테스트로 고정한다.** 트랜잭션 밖에서 tenant 테이블을 조회하면 실패하도록 하는 회귀 테스트를 둔다.
4. pooler 도입은 현재 계획에 없다. 도입 시점에 이 문서를 근거로 재검토한다.

3번이 핵심이다. 주석은 시간이 지나면 무시되지만 테스트는 깨진다.

### 미확인

- pooler 도입 여부·제품은 결정되지 않았다. `unknown`. 본 결정은 도입하지 않은 현재 상태에서도 지켜야 하는 규약이다.

---

## 3. P7 — ContextBundle redacted snapshot의 저장 증가

### 문제

ADR-009는 "item version/hash와 redacted content snapshot 보존"을 요구한다. 이는 옳다 — 가변 item ID만으로는 재현이 불가능하다. 그러나 그대로 구현하면 **같은 원문이 bundle마다 중복 저장된다.**

한 Run이 수십 개 item을 참조하고, 재시도마다 새 bundle이 생기며, RunRecord는 프로젝트 수명 동안 보존된다. 중복은 선형이 아니라 곱으로 늘어난다.

### 결정

content hash를 키로 하는 **불변 스냅샷 저장소**를 두고, bundle은 참조만 갖는다.

```
context_snapshots(
  content_hash  char(64) PRIMARY KEY,   -- redaction 적용 후 내용의 SHA-256
  content       text NOT NULL,
  byte_size     integer NOT NULL,
  first_seen_at timestamptz NOT NULL
)

context_bundle_items(
  bundle_id     inv_id,
  ordinal       integer,
  item_id       inv_id,                  -- 원본 item (가변)
  item_version  integer NOT NULL,        -- 참조 시점 버전
  content_hash  char(64) NOT NULL REFERENCES context_snapshots(content_hash),
  PRIMARY KEY (bundle_id, ordinal)
)
```

- 같은 내용은 한 번만 저장된다. 동일 문서를 반복 참조하는 것이 정상 사용 패턴이므로 중복 제거율이 높다.
- `content_hash`가 PK이므로 스냅샷은 **정의상 불변**이다. 내용이 바뀌면 다른 행이다.
- bundle의 `content_hash`(전체 묶음 해시)는 구성 항목의 `(ordinal, content_hash)` 순서열에서 계산한다. 재현 검증이 항목 단위로 가능해진다.
- **redaction 적용 후 내용을 해시한다.** 적용 전 해시를 쓰면 원문을 복원할 단서가 남는다.

### 정리 규칙

어떤 bundle도 참조하지 않는 스냅샷만 삭제한다. bundle은 RunRecord 보존 기간(프로젝트 수명)을 따르므로, 스냅샷 삭제는 사실상 **고아 정리**만 남는다. 참조 카운트를 별도 컬럼으로 두지 않고 `NOT EXISTS` 질의로 판정한다 — 카운터는 drift가 생기지만 질의는 생기지 않는다. 이는 CR-07에서 Artifact pin에 제안한 것과 같은 원칙이다.

### 미확인

- `context_snapshots.content`의 크기 상한과, 상한 초과 시 object storage로 넘길지 여부는 실제 문서 크기 분포를 본 뒤 정한다. `unknown`.
- 임베딩 차원은 ADR-009에 따라 **모델 선정 전까지 고정하지 않는다.** `vector(n)` 컬럼은 S09 이전에 만들지 않는다.

---

## 4. 다음 행동

S01 완료 후 위 결정을 S01 계약과 대조해 재확인하고, S02-DB/ST의 첫 Alembic migration에 반영한다. 계약이 달라지면 이 문서를 갱신하고 차이를 기록한다.

관련: [[DB 최종 개발 계획]], [[Storage 최종 개발 계획]], [[설계 충돌 정정 및 ADR]], [[알람 라우팅과 대응 주체]]
