---
doc_id: "CLAUDE-INDEP-REVIEW-HARDCODE-AUDIT-001"
title: "독립 검토 — Codex 하드코딩 감사: 유도 3건 무게(같은-개수 교체)·원천 비순환·고정 판정(prior 목록 위험)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex(피검토)"
reviewed_at_tip: "f14f4c07"
code_commit: "81a6e577"
updated: "2026-09-22"
source_of_truth: "Git"
tags: ["independent-review", "hardcode-audit", "derive-vs-fixed", "revival", "fixed-sha"]
---

# 독립 검토 — Codex 하드코딩 감사

[[2026-09-21_하드코딩_변경연동값_감사_Codex]]의 독립 검토. 보고를 읽지 않고 **되살렸다**. 검토 tip **`f14f4c07`**, 코드-수정 커밋 `81a6e577`, 인터프리터 `.venv` 3.14. clean 워크트리 `C:/vw`를 tip에 고정해 측정(공유 트리 리셋 회피, R6).

## ① 유도 3건이 무게를 지는가 — 같은-개수 교체가 잡히는가 (직접 되살림, 확증)
핵심: 옛 `len==N` 검사가 못 잡던 **같은 개수 교체·중복**을 새 집합 대조가 잡는가.
- **check_ontology (48행)**: 48은 registry `sum(len outcome_ids)`에서 유도되나, **핵심 가드는 per-task 집합 대조**(`set(realizes)=={outcome_ids}`). 되살림: registry에서 task `S01-FE`의 outcome를 `OUT-01→OUT-02`로 **교체**(둘 다 유효, 총 48 불변, 온톨로지 미변경) → **line 52에서 FAIL(EXIT 1)**. 복원 시 PASS. → 같은-개수 내용 교체를 per-task 집합이 잡는다(48 count만으론 못 잡음). **확증.**
- **check_node_docker_compat (4)**: `case_mode_drift`(집합 대조). 되살림(순수 함수): 모드 `sleep→snooze`(여전히 4개) → `{missing:[sleep], unexpected:[snooze]}` → 잡힘. clean 4개 → 무drift. checker(line 62-79)는 drift≠빈집합이면 `raise SystemExit(1)`. **확증.**
- **check_remote_workspace (7)**: `case_name_drift`. 되살림: `timeout→stall`(여전히 7) → `{missing:[timeout], unexpected:[stall]}` 잡힘; `ai→python` **중복**(7항목 유지) → `{missing:[ai], duplicates:[python]}` 잡힘. **확증.**
- **판정**: 세 건 모두 같은-개수 교체를 잡는다. 옛 count-only가 놓치던 바로 그 형태. 무게 확증.
- **보고 수용(내 실행 아님)**: docker/remote checker의 **전체 실행**은 Docker/Go acceptance 증거가 필요(Codex도 미실행). 나는 drift **순수 함수 + fail 분기**를 확증했고 실 Docker acceptance는 안 돌림.

## ② 유도 원천이 안전한가 — 비순환 (확증)
- **check_ontology 원천 = `docs/task-registry.json`**(source of truth), 검사 **대상 = 온톨로지 ttl/jsonld**. 서로 다르다. registry가 검사 대상이면 순환이겠으나, 이 검사는 온톨로지가 registry를 미러하는지 본다.
- **registry 자체의 스코프 변경은 독립 가드가 잡는다**: `check_docs.py` line 81 `if len(tasks)!=48 or len(outcomes)!=12`가 **하드코딩 리터럴**(주석: "Deliberate governance baseline, not a derived count"). task/outcome 추가·삭제 시 즉시 실패. → registry는 검사 대상 밖 + 독립 baseline이 지킴. **비순환.**
- **잔여(내가 짚음)**: registry+온톨로지를 **함께** 같은-개수로 바꾸면(예: 한 task의 outcome 교체) check_docs(count 동일)·check_ontology(일관) 둘 다 통과. 그러나 이는 **사람이 registry(정본)를 편집하는 의도적 행위**이지 기계적 조용한 드리프트가 아니다. 정본 편집은 허용되고, per-task 집합이 온톨로지 일관성을 보장. 수용.
- **docker/remote 원천 = `acceptance_evidence.py`의 pinned 목록**(주석: "Do not derive from the tests or report being checked"). 검사 대상(증거) 밖. **비순환.** 확증.

## ③ 고정 유지 판정이 옳은가 (내 시각)
- **11 run states (test_run_state.py)**: ADR-001 상태기계 불변식 표현. 고정 맞음(구현에서 유도하면 상태 추가·누락을 함께 따라가 가드 상실). **위험 낮음**: 상태 집합이 바뀌면 단위시험이 **즉시·시끄럽게** 실패. 동의.
- **정본 여정 5개 (browser)**: "브라우저에서 반드시 실행돼야 할 여정" 표현. 이름-집합 대조라 rename/추가/삭제 감지. **위험 낮-중**: CI 증거 게이트에서 시끄럽게 불일치. 동의(Gemini 소관이나 판정 타당).
- **마이그레이션 prior 목록 (check_migration_upgrade.py) — 고정은 맞으나 잔여 위험이 Codex 서술보다 크다**:
  - `expected_head=chain()[-1]`은 **유도**(맞음, 계산값). `priors` 매트릭스는 **큐레이션 고정**(주석: "a migration does not make it a supported external starting state by itself"). 그래프에서 유도하면 모든 revision이 prior가 되어 "지원하는 외부 시작점"이라는 **의미가 소멸**(공허) → 고정이 맞다. 저장소에 파생할 **권위적 supported-versions 선언이 없다**(grep 확인) → 유도할 원천 자체가 없음. **고정 판정 동의.**
  - **그러나 위험이 비대칭·조용하다**: 새 지원 prior를 **목록에 안 넣으면** 그 경로만 **조용히 미검증**으로 남고 **아무것도 실패하지 않는다**(기존 prior는 통과). 이는 11-state/여정 케이스(변경 시 시끄럽게 실패)와 **반대** — 오늘 하루 경계한 "초록인데 도달 안 함"의 전형.
  - **"릴리스 체크리스트"는 단독 가드로 불충분**(사용자 지적에 동의): 실패가 조용한데 가드가 **사람의 기억**이다. "사람이 기억해야 하는 것은 결국 잊힌다."
  - **권고(Codex+운영 소관, 코드 일방 변경 아님)**: (a) 언젠가 **권위적 supported-versions 선언**(태그된 릴리스↔schema head 등)이 생기면 prior를 **그것에서 유도**(그래프 아님) — 새 지원 릴리스가 자동으로 시험을 요구. (b) 그 전까지 체크리스트 항목을 **릴리스-태깅 행위에 묶어 구체화**("릴리스를 지원 업그레이드 원천으로 태그하면 그 head를 priors에 추가"), 가능하면 "태그된 릴리스 head가 전부 priors에 있는지" 경량 교차검사. (c) 최소한 이 **조용한 미검증 위험**을 릴리스 문서에 고정 위험으로 명시. Codex의 잔여-위험 명시는 옳으나 "체크리스트"의 강도가 실패의 조용함에 못 미친다.

## 판정
- ① 유도 3건: **무게 확증**(같은-개수 교체·중복 모두 잡힘, 되살림). docker/remote 전체 Docker 실행은 미검증(순수 함수+fail 분기는 확증).
- ② 원천: **비순환 확증**(registry는 대상 밖+check_docs 독립 baseline; acceptance 목록은 대상 밖 pinned).
- ③ 고정: 11-state·여정·prior 모두 **고정 판정 옳음**. **단 prior 목록의 잔여 위험(조용한 미검증)이 크고 체크리스트는 불충분** → 권위 선언 유도 또는 릴리스-태깅 결속 권고.

## 직접 확인 vs 보고 수용
- **직접(되살림·실행)**: ontology per-task 집합 FAIL, docker/remote drift 함수+fail 분기, check_docs 48/12 리터럴, acceptance pinned 목록, prior head 유도·목록 큐레이션·외부 원천 부재(전부 소스/실행).
- **보고 수용(미실행)**: docker/Go acceptance 전체 실행, 실-PG migration prior 업그레이드 경로(Codex의 실행 결과 수용, 로직은 소스 확증).

관련: [[2026-09-21_하드코딩_변경연동값_감사_Codex]] · [[2026-09-21_유도처방_한계_내산출물_재점검_Claude]] · [[계약검증_자동화대판단_검사목록]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
