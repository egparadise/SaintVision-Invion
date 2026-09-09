---
doc_id: "HO-IMPL-CLAUDE-001"
title: "Claude 구현 인계 - Codex 검토 요청"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-09-09T23:45:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# Claude 구현 인계 - Codex 검토 요청

발신: Claude / 수신: Codex(reviewer) / 인계 ID: **HO-IMPL-CLAUDE-001**

기준 커밋: `c1516d2` / branch `agent/claude/HO-DOC-CLAUDE-001`
CI: Backend Build **success** — Python 3.12·3.14 양쪽에서 340 tests, **0 skipped**(PostgreSQL 16 의존 152건 포함), 마이그레이션 5개 `upgrade → downgrade base → upgrade` 왕복 성공.

실제 수신 확인 전까지 pending이다. 외부 메시지는 보내지 않았다.

---

## 1. 무엇을 인계하는가

Claude 배정 12건 중 **11건 구현, 1건 부분**. 코드 71 파일 16,253줄.

| task | 상태 | 주요 산출물 |
|---|---|---|
| S02-BE·DB·ST | 구현·CI 검증 | 마이그레이션 0001, 노드 등록·heartbeat API, 경로 안전성 |
| S03-DB·ST | 구현·CI 검증 | 0002, Run 상태 기계, Evidence 불변 조건, outbox/inbox, Artifact 원장 |
| S09-DB·ST | 구현·CI 검증 | 0003, 불변 Context, RunRecord 봉인, golden eval |
| S10-DB·ST | 구현·CI 검증 | 0004, lineage, 배포 digest |
| S10-BE | **부분** | adapter 계약 + conformance 스위트. **실제 Provider adapter·MLflow·승인 배포 미착수** |
| S12-DB·ST | 구현·CI 검증 | 0005, 백업·복구 훈련·릴리스 manifest·인수 |

**어느 task도 `done`으로 올리지 않았다.** 전부 선행(S01~S11)이 미완이고 실제 장비·사용자 증거가 없다. `task-registry.json`은 손대지 않았다.

---

## 2. 검토 순서 — 위험 높은 것부터

시간이 한정돼 있다면 위에서부터 보시면 됩니다. 각 항목에 **제가 판단한 것**과 **확인이 필요한 것**을 구분해 적었습니다.

### 2.1 tenant 격리 — 최우선

- `migrations/versions/0001_s02_baseline.py` `_install_rls()`, `src/saintvision/db/rls.py`, `src/saintvision/db/session.py`
- `tests/test_database.py`

**확인 요청**: `FORCE ROW LEVEL SECURITY`를 모든 tenant 테이블(49개)에 걸었습니다. 빼면 마이그레이션 소유자가 정책을 우회하므로 **소유자로 실행한 테스트는 전부 통과하고 운영만 샙니다.** 그래서 테스트도 비소유자 `inv_app`(NOLOGIN NOBYPASSRLS)으로 실행합니다.

tenant scope는 `SET LOCAL`만 쓰고 **세션 수준 설정 API를 아예 만들지 않았습니다**(CR-12). `NULLIF(...,'')`로 빈 문자열도 미설정으로 취급합니다. 트랜잭션 종료 시 scope가 사라지는 것을 테스트로 고정했습니다.

복합 FK에 `tenant_id`를 포함해 다른 tenant 행을 FK로 연결할 수 없게 했습니다.

### 2.2 Evidence 트랜잭션 불변 조건 (ADR-008)

- `src/saintvision/services/runs.py::complete_run`, `src/saintvision/runs/state.py`
- `tests/test_execution.py`

**확인 요청**: `verifying → succeeded`를 `complete_run` 하나로만 도달하게 하고 세 겹으로 고정했습니다.

1. `assert_transition`이 이 전이를 **거부**합니다 — Evidence 동반 여부를 그 함수는 볼 수 없기 때문입니다.
2. `runs.evidence_id`가 `state='succeeded'`일 때 NOT NULL이어야 하는 CHECK.
3. 서비스 함수가 트랜잭션을 열지도 커밋하지도 않습니다.

검증도 세 방향입니다: 서비스를 우회해 raw SQL로 쓰면 **DB가 거부**하고, 트랜잭션 중간에 예외를 던지면 **Evidence가 run과 함께 롤백**되며, `inv_app`은 Evidence를 UPDATE·DELETE할 수 없습니다.

### 2.3 상태 기계 (ADR-001)

- `src/saintvision/runs/state.py`, `tests/test_run_state.py`

**확인 요청**: 11상태를 한 모듈에 두고 API·서비스·DB CHECK를 같은 목록에서 렌더링했습니다. 간선 판단이 맞는지 봐 주십시오:

- 종료 아닌 모든 상태 → `cancelled`, `failed`
- `recovering → running` **직행 없음**. 재시도는 재배치가 필요하므로 `scheduled`를 거칩니다
- `timeout`·`node_lost`는 상태가 아니라 종료 사유이고, 사유와 종료 상태의 조합을 검사합니다

### 2.4 컬럼 단위 UPDATE 권한 — 새로 도입한 패턴

- `migrations/versions/0004_s10_lineage.py::_install_rls`, `db/models/__init__.py::LIFECYCLE_UPDATE_COLUMNS`

**확인 요청**: `model_versions`를 처음 append-only로 만들었다가 CI가 `permission denied`로 잡았습니다 — 버전은 삽입 뒤 verified → pinned → released로 진행해야 합니다. 불변인 것은 행이 아니라 **정체성**이라고 판단해 컬럼 단위 UPDATE로 바꿨습니다:

```sql
GRANT SELECT, INSERT ON model_versions TO inv_app;
GRANT UPDATE (stage, verified_at, retention_pinned_until) ON model_versions TO inv_app;
```

**이 패턴을 다른 곳(예: S05 allocation)에도 쓸지는 owner 판단입니다.**

### 2.5 Adapter 취소 3-상태 — 계약 판단

- `src/saintvision/adapters/contract.py`, `tests/test_adapters.py`

**확인 요청**: `cancel()`이 boolean이 아니라 `stopped / already_finished / not_supported / unknown`을 반환합니다. 스트리밍 연결을 닫아도 서버는 생성을 계속하고 과금도 계속할 수 있고, 서버측 취소가 없는 provider도 있습니다. **`unknown`이 orchestrator의 자동 재시도를 막는 신호**입니다([[Backend 최종 개발 계획]]의 "외부 부수 효과 확인 불가 시 자동 재시도하지 않는다").

이 신호를 실제로 소비하는 쪽(RunGraph 재시도 판단)은 Codex 영역이므로, **계약이 그쪽에서 쓰기에 맞는지** 봐 주십시오.

### 2.6 lineage 식별자

- `src/saintvision/db/models/lineage.py`, `src/saintvision/services/lineage.py`

**확인 요청**: 이미지는 tag가 아니라 digest가 정체성입니다(`sha256:<64hex>` 제약). commit은 40/64자 hex, **dirty tree는 거부하지 않고 기록**합니다. `trace_model`은 찾은 것과 함께 **빠진 것과 dangling 링크**를 보고합니다.

`model_lineage`가 다형적 subject에 FK를 걸지 않는 것은 의도이고(종류마다 컬럼을 두면 종류가 늘 때 마이그레이션), 그 대가를 dangling 보고가 갚습니다. **이 트레이드오프가 맞는지** 확인 부탁드립니다.

### 2.7 나머지 (낮은 위험)

경로 안전성(`storage/pathsafe.py`), partition 관리(`db/partitions.py`), 파일럿 운영(`services/pilot.py`), Context 중복 제거(`services/context.py`).

---

## 3. 제가 내린 판단 중 owner 확인이 필요한 것

| # | 판단 | 근거 | 확인 요청 |
|---|---|---|---|
| D1 | `context_snapshots` 키를 `(tenant_id, content_hash)`로. **PREP-CLAUDE-001의 전역 해시 키에서 변경** | tenant 간 중복 제거는 은닉 채널이고, 공유 행은 수명도 공유한다 | 변경 수용 여부 |
| D2 | `nodes.certificate_fingerprint`에 `NULLS NOT DISTINCT`를 **쓰지 않음**(부분 unique 인덱스) | NULL은 "등록 미완료"라는 정상 상태이고 여러 노드가 동시에 갖는다. NULLS NOT DISTINCT면 플랫폼 전체에서 미등록 노드가 1대 | PLAN-DB-001의 "NULL 중복까지 막는 제약" 해석이 맞는지 |
| D3 | `node_capabilities(node_id, kind, device_index)`에는 `NULLS NOT DISTINCT` **유지** | NULL device_index는 "전체 호스트 자원"이라 중복 NULL이 진짜 중복 | 동일 |
| D4 | DEFAULT partition을 두지 않음 | 조용한 성공보다 명시적 실패. Evidence 누락이 완료 보류로 이어지는 것이 설계 의도 | CR-06 수용 여부 |
| D5 | 고아 스냅샷 정리를 참조 카운트가 아닌 `NOT EXISTS` 질의로 | 카운터는 drift가 생기고 정합 작업이 또 필요하다. CR-07에 제안한 것과 같은 원칙 | 동일 원칙을 Artifact pin에도 적용할지 |
| D6 | 복구 훈련이 `fencing_verified` 없이 pass 불가 | ERR-DESIGN-006 미결. 미결 질문이 성공 주장을 막아야 한다 | **이 강제가 과한지** — 아래 4절 참조 |

---

## 4. 지금 막혀 있는 것

### 4.1 ERR-DESIGN-006이 AC-12 증거를 막고 있다

제 코드가 데이터베이스 복구 훈련의 `passed` 기록을 거부합니다. 의도한 것이지만, **ADR이 나오지 않으면 AC-12의 복구 Evidence를 만들 수 없습니다.**

선택지별 구현 비용을 측정해 [[설계 미결 3건 구현 영향 분석]]에 정리했습니다. 요약: (A) `setval` 절차는 스키마 변경 0이고 기동 검사 붙일 자리가 이미 있음, (B) epoch는 마이그레이션 1개 + Node 계약 변경.

### 4.2 CR-01~12 중 8건 미회신

CR-01·02·03·04·05·07·08·09·11이 Codex 판단 대기입니다. CR-06·10·12와 §4-P7은 제가 처리해 구현에 반영했습니다.

### 4.3 S01 미완으로 `unknown`인 값들

코드에 추정으로 채우지 않고 `config.S01_PENDING`에 목록으로 두었으며 `/v1/health`가 `unresolvedSettings`로 응답합니다.

- OIDC issuer·audience·JWKS URL
- Node mTLS CA 번들
- S3 호환 object store 제품·endpoint
- partition 잡·liveness sweep의 실행 주체
- 런타임 의존성 최종 버전 lock
- 어느 두 Provider인지(S10-BE 나머지가 여기 걸림)

---

## 5. 검토 시 유용할 것

**CI가 결함 6건을 잡았습니다.** 각 수정과 재발 방지가 History 기록에 있습니다. 특히 재사용 가치가 있는 것:

- `tests/test_migrations.py` — 전체 upgrade를 **오프라인 렌더링**(서버 불필요)해서 처음부터 올릴 때만 드러나는 순서를 검사합니다. 마이그레이션이 모델 테이블 집합과 정확히 일치하는지, 모든 tenant 테이블이 FORCE·정책을 갖는지, append-only에 UPDATE·DELETE가 없는지.
- 마이그레이션이 **가변 모듈 상수를 읽으면 안 된다**는 규칙 — 0001이 `PARTITIONED_TABLES`를 읽었다가 0002가 그 상수를 바꾸자 깨졌습니다.

**실행 기록**: [[2026-09-09_17-50-00_KST_S02_Claude_개발과정]], [[2026-09-09_18-40-00_KST_S03_Claude_개발과정]], [[2026-09-09_22-00-00_KST_S09_Claude_개발과정]], [[2026-09-09_22-40-00_KST_S10-BE_Claude_개발과정]], [[2026-09-09_23-20-00_KST_S10_Claude_개발과정]], [[2026-09-09_23-50-00_KST_S12_Claude_개발과정]]

---

## 6. 완료 조건과 다음 담당자

**이 인계의 완료 조건**: Codex가 위 검토 순서대로 확인하고, 3절의 D1~D6에 수용/수정 판단을 남기며, 4.1의 ADR을 낸다.

- **Codex**: 본 검토 + ERR-DESIGN-005/006/007 ADR + CR-01~12 회신 + S01
- **Claude**: Codex 회신 후 계약 대조·수정. **그 전까지 새로 착수할 배정 작업 없음**
- **사용자**: Docker/WSL 복구([[ERR-ENV-005 Docker 엔진 중단으로 DB 검증 차단]]). CI가 대체 중이라 개발은 막히지 않았으나 로컬 재현 경로가 없다

관련: [[Agent 인계 대기 목록]], [[설계 미결 3건 구현 영향 분석]], [[Agent 역할과 인계 계약]], [[2026-09-09_15-45-31_KST_HO-DOC-CLAUDE-001_Claude_검토보고]]
