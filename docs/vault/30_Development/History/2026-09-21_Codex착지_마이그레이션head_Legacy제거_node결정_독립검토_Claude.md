---
doc_id: "CLAUDE-INDEP-REVIEW-MIGRATION-LEGACY-NODE-001"
title: "독립 검토 — Codex 착지(aed446e): 마이그레이션 head 유도 · LegacyProjectCatalog 제거 · node telemetry 결정"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex(피검토)"
reviewed_at_sha: "a25b0e2"
code_commit: "aed446e"
updated: "2026-09-21"
source_of_truth: "Git"
tags: ["independent-review", "migration", "contract", "node-telemetry", "revival", "fixed-sha"]
---

# 독립 검토 — Codex 착지(aed446e)

사용자 지적: 재검증에서 본 **숫자 일관성**(fixture·TS·vitest·python 각 1 감소, dead-contract WARN 소멸, tsc exit 0)은 *제거가 깔끔했다는 증거*이지 *변경을 검토한 것*이 아니다. 둘은 다르다. 이 문서는 세 변경을 **되살림·소스추적**으로 직접 검토한다.

## 검토 트리 못 박기
- **origin tip `a25b0e2`에서 검토**(내 마지막 커밋). 코드 커밋 **`aed446e`**("remove dead legacy response contract and derive migration head", 부모 `cd2b8b1`)는 a25b0e2의 **조상(병합됨)** — `git merge-base --is-ancestor aed446e a25b0e2` = YES. 문서 커밋 `a1833e3`("record migration head fix and contract decisions").
- 인터프리터 `.venv/Scripts/python.exe` 3.14.6. **PG 없음** — 단, 마이그레이션 head 시험은 **파일만 읽는다**(alembic `ScriptDirectory`는 스크립트 파일 파싱, DB 불요) → 이 검토는 PG 없이 완전 실행 가능.
- 되살림은 실 마이그레이션 파일을 건드리지 않고 `migration_graph` 모듈을 import해 `load()`한 실 revision 집합에 **합성 revision을 더해** `chain()`/`downgrade_target()`을 호출하는 방식(공유 워크트리 무접촉).

---

## ① 마이그레이션 head 시험 — 무엇을 지키게 됐고, 무엇이 공허해졌나

**변경**: `assert ordered[-1].revision == "0044_model_registry_binding"`(하드코딩) → `alembic get_current_head()` 유도 대조 + `expected_downgrade_target` 인라인 계산 + 합성 `future` revision 2단언 추가.

### 직접 확인 (되살림, 내 손)
실 head = `0045_discovery_machine_cred`, alembic head 일치(True). 합성 주입 결과:

| 되살림 | 결과 | 판정 |
|---|---|---|
| R1 두 head(내부 노드에 자식 추가로 미참조 노드 2개) | `chain()` **RAISE** "unmerged migration branches: expected exactly one head" | 두-head **잡힘** |
| R2 dangling parent(존재하지 않는 down_revision) | `chain()` **RAISE** "unknown revision parent" | 체인 끊김 **잡힘** |
| R3 중간 노드를 head로 재배선(도달불가 생성) | `chain()` **RAISE** "unreachable revisions" | 재배선 **잡힘** |
| 합성 reversible future → downgrade_target | 불변(0045) | — |
| 합성 **irreversible** future → downgrade_target | **이동**(future_irrev) | 판별력 있음 |

**핵심 재판정 (사용자 우려에 대한 답)**:
- 사용자 우려 = "`ordered[-1]`와 `alembic_head`가 같은 소스에서 나오면 항상 참 → 유도로 바꾸며 공허해졌다." **부분적으로 옳다.** `ordered[-1] == alembic_head` 그 한 줄은, **유효한 단일-head 저장소에선 두 파서가 같은 파일을 읽어 항상 일치** → 사실상 tautology에 가깝다. 그 줄의 독립적 포착은 (a) migration_graph의 ast 파서와 alembic 파서의 **불일치**, (b) 다중-head 뿐인데 (b)는 **바로 윗줄 `ordered = module.chain(revisions)`가 이미 RAISE**하므로 중복이다.
- **그러나 소프트웨어의 "한 head·비순환·도달가능·단일 root" 보호는 공허해지지 않았다.** 그 보호는 `chain()` 내부 RAISE에 **원래부터** 있었고, 시험이 alembic 줄 **이전에** `chain(revisions)`를 호출하므로 실 파일이 두-head면 거기서 먼저 깨진다(R1 실증). 즉 **하드코딩 제거로 사라진 실체 보호는 없다** — 브리틀한 리터럴(정당한 신규 마이그레이션마다 깨지던, 아침 RED의 원인)이 구조 검사(chain)+합성 행위검사(future)로 **이전·증강**됐다.

### 공허한 줄 하나 특정
- `assert module.downgrade_target(revisions) == expected_downgrade_target`: 시험의 `expected_downgrade_target`은 `[r for r in ordered if r.irreversible or isinstance(r.down_revision, tuple)][-1]`로 **`downgrade_target()`의 술어를 그대로 재구현**한다. 되살림에서 둘이 동일(identical logic: True). → **f(x)==f(x)**, 공허. 다만 바로 아래 **합성 future 2단언이 이를 구제**한다: reversible 추가 시 target 불변 / irreversible 추가 시 target 이동을 실제로 판별함(위 표). 그래서 `downgrade_target`의 "가역 꼬리 추가는 안전 롤백지점을 옮기지 않는다"는 행위는 **비공허하게** 검증된다.

### 옛 하드코딩이 잡던 것 중 지금 사라진 것
- head가 예상외 단일값이 되는 경우 중 **단일-head·비순환·도달가능을 모두 만족하는 down_revision 오타**(정확히 다른 유효 노드로 재배선): 옛 리터럴은 문자열 불일치로 잡았고, 지금은 chain 통과+alembic 동의로 **통과한다**. 매우 좁은 케이스(대부분의 오타는 chain의 RAISE에 걸림)라 실질 손실은 작다. 옛 시험이 잡던 나머지("head가 리터럴 X")는 정당한 신규 마이그레이션과 구별 불가였던 **브리틀함 자체**라 손실 아님.

**판정 ①**: 소프트 보호는 chain()에 살아 있고 되살림으로 무게 확증. de-hardcoding은 **정당한 개선**(브리틀 리터럴 제거 + 구조·행위 검사 이전). 단 `downgrade_target==expected` 한 줄은 tautology(future 단언이 구제). **권고(비차단)**: 그 줄을 독립 소스와 대조(예: 마이그레이션 파일의 `irreversible` 주석/PLAN-DB-001 목록을 손으로 나열)하면 재구현 대조의 공허를 없앨 수 있다.

---

## ② LegacyProjectCatalog 제거 — 남은 소비자와 거부의 가시성

**변경**: legacy Pydantic 모델·생성 schema/TS·fixture·provider fixture·어댑터 fallback 분기 제거, 그 봉투를 **거부**하는 회귀 시험 추가.

### 직접 확인 (소스추적)
- **저장소 내 producer 부재 확증**: `LegacyProjectCatalog`/`legacy-project-catalog`/`legacy_project_catalog`를 코드·schema·fixture·mjs 전수 검색 → **문서(md) 6건에만** 잔존, 코드/계약/생성물 **0건**. Codex의 "저장소에 producer 없음"과 일치.
- **프런트가 그 봉투를 만들 경로 없음**: 유일 경로는 `apiClient<ProjectListResponse>('/v1/projects')`가 **백엔드로부터** 받는 것뿐. 프런트 자체가 legacy 봉투를 합성하지 않음.
- **거부가 조용한 빈 목록이 아니라 시끄러운 오류로 표면화**(사용자 최대 우려):
  - `fetchProjects`: legacy `{items}` 봉투는 `projects` 필드 부재 → `!Array.isArray(page.projects)`(undefined) → **`throw new Error('프로젝트 응답 형식 불일치')`**. (빈 목록으로 삼키지 않음.)
  - 유일 호출부 `App.tsx:73` `.catch(() => setProjectError('프로젝트 목록을 확인하지 못했습니다.'))` → `App.tsx:238` `{projectError && <span role="alert">{projectError}</span>}`로 **렌더**. `role="alert"`이라 스크린리더에도 고지. → **아침류(조용한 빈 목록) 아님. 시끄러운 실패 = 옳은 패턴.**

### 잔여(Codex 캐비엇과 일치)
- **[행위 변화]** legacy 봉투는 이전엔 **수용·매핑**(`page.items.map`)됐다. 지금은 거부. 저장소 밖 미문서화 서버가 아직 `{items}`를 보낸다면, **전엔 프로젝트가 보이던 사용자가 이제 오류를 본다**. fail-loud라 방향은 옳으나 그런 producer엔 행위 변화다 — Codex의 "외부 서버 배제 안 함, 발견 시 소비자-호환 계약으로 재개봉" 결론이 이를 정확히 덮는다. 범위 제한 옳음.
- **[사소]** throw 메시지 '프로젝트 응답 형식 불일치'가 사용자에겐 일반 '프로젝트 목록을 확인하지 못했습니다.'로 접힘 → **계약 불일치와 네트워크 오류가 사용자에게 구별 안 됨**. 가시성은 확보되나 원인 구별은 로그 몫.

**판정 ②**: 제거 깔끔(producer 0), 거부는 **시끄럽게** 표면화(role=alert 확증). Codex의 범위 결정 타당. 잔여는 외부-producer 행위변화 1건(캐비엇이 덮음)뿐.

---

## ③ node telemetry 결정 — 전제를 소스로 검증 (백엔드 소관은 나)

**Codex 결정(문서 line 73)**: "telemetry 필드를 계약에 넣지 마라 — 현재 `/v1/nodes` producer가 안 내보내고 `nodeObservation`이 부재를 사용불가/비스케줄로 다룬다. fixture가 telemetry 합성하지 말고 화면 행위 바꾸지 마라."

### 직접 확인 (소스추적, 백엔드)
- **list producer가 telemetry를 안 낸다 — 확증(단, 정밀화 필요)**: `/v1/nodes` → `_node_body(node)` → `schemas.NodeResponse`(=`Strict`, `extra="forbid"`)가 내는 필드는 **nodeId·hostname·osType·osVersion·agentVersion·status·enrolledAt·lastHeartbeatAt·heartbeatSequence·labels 뿐**. `observedNode`가 `valid`에 요구하는 metrics(cpuCores·cpuUsagePercent·memoryTotal/Used·gpuCount·storageTotal/Used)는 **하나도 없다** → 프런트는 **모든 노드를 `telemetryUnavailable=true`(자원 미관측·비스케줄)로 렌더**. Codex 전제 참.
- **프런트가 기대하는 동적 metrics는 백엔드 어디에도 없다**: `cpu_usage/memory_used/memory_total/storage_used/gpu_vram/usage_percent/allocatable`를 `db/models` 전수 검색 → **0건**(telemetry 컬럼 자체가 없음). schemas엔 **enrollment 시 자기신고** `cpu_cores/ram_bytes/gpu_count`(정적 용량)와 discovery `claimed_*`만 있고, **동적 사용률은 부재**. → 이 프런트 필드들은 **producer가 없는 프런트-전용 계약**이다.
- **그러나 백엔드가 telemetry-free는 아니다 (전제 정밀화)**: heartbeat(`POST /v1/nodes/{id}/heartbeats`)가 `ObservationPayload{capabilityId, usedQuantity, unit}`를 **수집**하고 `record_observations`가 기록하며 주석은 "placement reads these"라 명시. 즉 **capability-스코프 사용률 모델**(capability별 totalQuantity/usedQuantity)이 실재하고 `/v1/nodes/{id}`의 capabilities로 노출된다. 이는 프런트의 **평면 노드-metrics 모델**(cpu%/mem-bytes/gpuVram)과 **다른 형태·다른 엔드포인트**다.

### 의도 vs 미구현 (사용자 질문 핵심)
- 프런트가 기대하는 **평면 동적 telemetry(cpuUsagePercent 등)**: DB 컬럼도 schema 필드도 없음 → **미구현**(구현이 없어 안 나가는 것). 사용자 규칙대로 **나중에 추가되면 계약도 함께 가야 한다**.
- 백엔드의 **capability/observation 사용률**: **구현됨·의도적**(cert 인증·`extra=forbid`·"placement reads"). heartbeat 도크스트링은 과거 무인증 라우트가 "utilisation 수치를 주입해 placement를 조종"당한 것을 고친 이력까지 서술 → 사용률을 **capability 관측으로 다루는 것이 설계 의도**.
- 결론: "producer가 telemetry를 안 낸다"는 **list 엔드포인트엔 참**이나, 전체로는 부정확 — **두 자원 모델이 미조정 상태**다(프런트 평면 metrics = 미구현 / 백엔드 capability 관측 = 구현·의도).

**판정 ③**: Codex 결정(지금 telemetry를 계약/ fixture에 넣지 않음)은 **타당·옳다** — list producer가 실제로 안 내고 프런트가 fail-safe(부재→비스케줄, 확증)하기 때문. 다만 근거 문구는 정밀화 필요: 사용률은 **capability/observation 형태로 이미 모델·수집**된다. **권고(node 슬라이스 바인딩 시)**: 평면 telemetry는 지금 계약에서 빼되, 향후 telemetry 표면화 시 **기존 capability/observation 모델과 재조정**(프런트 평면 모델 ↔ 백엔드 capability 모델 중 하나로 수렴)을 열어둘 것. 두 모델을 각자 굳히면 나중에 또 "계약 있으나 producer 다름"이 된다.

---

## 직접 확인 vs 보고 수용 (경계)
- **직접 확인(내 손)**: ① 되살림 R1/R2/R3 + tautology + future 판별 (실행). ② producer 전수검색·`fetchProjects` throw 경로·`role=alert` 렌더 (소스). ③ `_node_body`/`NodeResponse`/DB 모델 telemetry 부재·heartbeat observation 수집 (소스).
- **보고 수용(실행 아님)**: 저장소 밖 미문서화 서버의 부재(불가지 — Codex 범위 제한 수용). 실 PG 마이그레이션 upgrade/downgrade 왕복(이 시험은 파일만 읽으므로 애초 DB 불요 — 실 DB 적용 semantics는 별도 integration 몫). node 슬라이스는 **아직 미구현**(Codex 예정) — 바인딩 후 재검토 대상.

## 종합 판정
1. **마이그레이션 head**: 소프트 보호 chain()에 살아 있음(되살림 확증), de-hardcoding은 개선. `downgrade_target==expected` 한 줄만 tautology(future 단언이 구제). 비차단 권고 1.
2. **Legacy 제거**: producer 0, 거부는 시끄럽게 표면화(role=alert). 타당. 잔여 = 외부-producer 행위변화(캐비엇이 덮음).
3. **node telemetry**: 결정 옳음(list producer 무-telemetry·프런트 fail-safe 확증). 근거 문구 정밀화 + 향후 capability 모델과 재조정 권고.

관련: [[2026-09-21_운영자자격증명발급_독립검토_Claude]] · [[2026-09-21_서빙앵커_감사_3갈래_Claude]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
