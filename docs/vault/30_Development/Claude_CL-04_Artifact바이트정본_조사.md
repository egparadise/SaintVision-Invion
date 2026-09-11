---
doc_id: "REPORT-CLAUDE-CL04-001"
title: "Claude CL-04 Artifact 바이트 정본 조사"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-09-12T10:10:00+09:00"
source_of_truth: "Git"
---

# Claude CL-04 — `public.artifacts` 소비자·이력·보존 참조 조사

카드: [[Claude 작업 현황]] CL-04. owner Claude / reviewer Codex. 부모 task S03-DB, S03-ST, S09-ST, S10-ST.

카드의 첫 행동은 "조사해"이고, 그 다음이 "kernel 실제 object bytes로 연결하거나 보존 가능한 전환 migration을 만든다"이다. **조사 결과가 어느 쪽을 골라야 하는지를 바꾸므로** 조사부터 적는다. 결론은 일방적으로 migration을 만들면 Codex가 `0030`에서 **의도적으로 철회한 것을 되살리게 된다**는 것이다.

검토 SHA: `review/claude-account-results` 5995b8b, 커널 측은 `agent/codex/workspace-bridge` d14db0a.

## 조사한 사실 (전부 직접 확인)

### 1. `public.artifacts`에는 production writer가 없다

Codex가 `0029_run_outputs` 주석에서 "nothing writes it"이라고 적었다. 인용하지 않고 직접 확인했다.

- 저장소 전체에서 `Artifact(` 생성은 model 정의 한 곳뿐이다. 서비스·API·도구 어디에도 행을 만드는 코드가 없다.
- SQL로 직접 넣는 곳은 **시험 fixture 세 군데뿐**이다: `tests/test_context_eval.py:412`, `tests/test_context_eval.py:467`, `tests/test_execution.py:685`.
- 동반 테이블 `public.upload_sessions`도 마찬가지다. `UploadSession(` 생성이 없고, `api/v1/`에 upload endpoint가 하나도 없다.

즉 공개 측의 **artifact 바이트 수집 경로 전체가 모델만 있고 구현이 없다.**

### 2. 그 결과로 소비자들이 production에서 도달 불가다

- `services/records.py::_pin_artifact`는 `public.artifacts`를 **읽어서** `run_record_artifacts` pin을 만든다. 원본 행이 생기지 않으므로 **pin도 생기지 않는다.**
- 따라서 `list_pinned_artifacts`는 운영에서 언제나 비어 있고, RunRecord는 산출물 pin 없이 봉인된다.
- `seal_run_record(artifacts=[...])`는 운영에서 만족될 수 없는 인자를 받아들인다. 시험이 먼저 행을 직접 넣기 때문에 시험에서는 통과한다.

### 3. 보존은 색인만 있고 수거자가 없다

`artifacts.retention_pinned_until`과 `ix_artifacts_retention_pinned_until`이 있고, model 주석은 "GC must honour this and never shorten it"이라고 말한다. 그러나 `src/` 어디에도 이 값을 읽는 GC/수거자가 없다. 커널 측 `services/control-plane/src/inv/`에도 `inv.storage_objects`를 수거하는 lifecycle 코드가 보이지 않는다.

**보존 규칙을 지킬 주체가 아직 없다.** 지금 상태에서 "GC가 보존을 지킨다"는 합격 증거는 만들 수 없다.

### 4. 실제 바이트와 해시는 커널에 있고, 정본 reader도 이미 있다

`inv.result_commitments`가 Run·attempt·`object_id`·`content_hash`·Evidence를 묶고, `inv.storage_objects`가 크기와 상태를 들고 있다. `services/control-plane/src/inv/result_view.py`의 `ResultView`가 `result()`·`artifacts()`·`download()`·`logs()`·`attempts()`를 그 위에서 제공하며, 사용자 확정대로 **이것이 실행 결과의 정본**이다.

## 왜 여기서 migration을 일방적으로 만들면 안 되는가

가장 그럴듯한 전환은 "공개 측이 커널의 확정 산출물을 SQL로 해석해 artifact 행을 채운다"이다. **그것이 정확히 `0029`가 만들고 `0030`이 철회한 것이다.**

- `0029_run_outputs`가 `public.run_committed_outputs(uuid,text)` 정의 함수를 만들고 `inv_app`에 EXECUTE를 부여했다.
- `0030_provisioning_integrity`가 같은 함수를 `PUBLIC, inv_app`에서 REVOKE하며 이유를 적었다: *"Downloads use the canonical kernel HTTP boundary and its current grant, receipt and immutable Evidence checks. Retain the published revision, while retiring its less restrictive alternate resolver."*
- head DB의 `pg_proc.proacl` 실측으로 확인했다: `run_committed_outputs postgres=X/postgres` — 소유자만 실행 가능하다. (CL-01 F3에 남긴 사항이다.)

그러므로 공개 측 SQL resolver를 다시 만드는 것은 **덜 엄격한 경로를 되살리는 것**이고, 카드가 금지한 "ResultView와 중복 결과 reader 재도입"에도 정면으로 걸린다.

남은 다른 길 — `run_record_artifacts`가 커널 object를 직접 가리키게 하는 것 — 도 공개 측에서 `inv.result_commitments`를 읽어야 하므로 같은 벽에 부딪힌다. `run_record_artifacts.artifact_id`에는 `public.artifacts`로 향하는 FK가 있어서, 커널 object를 pin하려면 그 FK를 느슨하게 하는 migration이 필요하고, 그 pin을 채울 값은 결국 커널에서 와야 한다.

## 그래서 결론

이 항목은 **내가 혼자 결정할 수 있는 구현이 아니라 seam 결정**이다. `CLAUDE.md`의 규칙대로 고난도 경계 변경은 Codex 계약을 받아 구현한다. 이전에 같은 seam에서 네 번(권한·handoff·binding·결과) 양측이 같은 개념을 각각 만들었고 **네 번 모두 실행 기록에 가까운 쪽이 옳았다.** 여기서도 실행 기록에 가까운 쪽은 커널이다.

**아무것도 삭제하지 않았다.** 카드가 "테이블/이력을 먼저 삭제하지 않음"을 요구하므로 `public.artifacts`·`upload_sessions`·`run_record_artifacts`와 그 이력을 그대로 두었다.

## Codex에 필요한 계약 질문 (CL-04 진행 조건)

1. RunRecord의 산출물 pin은 어디에 속하는가? 공개 측 `run_record_artifacts`를 유지하고 커널이 pin 값을 넘겨주는가, 아니면 pin 자체가 커널 기록으로 옮겨가는가.
2. `0030`이 철회한 SQL resolver 대신, 공개 측이 봉인 시점에 확정 산출물의 `content_hash`/크기/`evidence_id`를 얻는 **승인된 경로**는 무엇인가(커널 HTTP 경계인가).
3. `public.artifacts`·`upload_sessions`는 유지·보류·폐기 중 무엇인가. 폐기라면 이력 보존 방식과 `run_record_artifacts` FK 완화 migration의 소유자는 누구인가.
4. 보존/GC의 소유자는 누구인가. 현재 `retention_pinned_until`을 읽는 수거자가 양측 어디에도 없다.

## 남은 것과 다음 첫 행동

- 위 4개 질문을 Codex에 인계한다. 답이 오면 전환 migration을 구현하는 것은 Claude다.
- **지금 상태로 만들 수 없는 합격 증거**를 분명히 한다: "다운로드 actual bytes/hash"는 `ResultView`가 이미 제공하므로 내가 다시 만들지 않는다. "GC/보존"은 수거자가 존재하지 않으므로 증거를 만들 수 없고, 먼저 소유자가 정해져야 한다.
- CI는 세 Agent 공통으로 계정 결제·한도 문제로 차단돼 있다. 위는 전부 소스·로컬 DB 실측이다.
