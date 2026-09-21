---
doc_id: "CLAUDE-FINAL-FULL-INTEGRATION-VERIFY-20260922"
title: "오늘 밤 마무리 — tip 전수 검증(내 것만이 아니라 전부) + 조각-사이 회귀 1건 발견(EvidenceViewer 가짜 PASS, Gemini)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
verified_at_sha: "8090330c7b59bf0de47b04d30f1d8c8da2f731a0"
working_tree_clean: "YES"
worktree: "C:/vw (Claude 전용, detached, 고정 tip)"
interpreter: ".venv/Scripts/python.exe 3.14.6; Node v24.17.0(apps/web node_modules junction)"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["final-verify", "integration", "seam-break", "attribution", "provenance", "green-vs-reached"]
---

# 오늘 밤 마무리 — 마지막 tip에서 전수 검증

세 agent가 오늘 82건(문서 포함, 코드 30여건) 착지했으나 **각자 자기 조각만 검증**했다(나=내 파일 게이트, Codex=자기 시험, Gemini=프런트). **아무도 마지막 상태에서 전부를 안 돌렸다.** 조각 사이 깨짐은 조각 검증에 안 보인다(오늘 이미 봄: Gemini 646통과·게이트통과 순간 integration tsc가 깨져 있었음). 그래서 전수로 돌렸다.

**provenance**: 내 clean 전용 워크트리 `C:/vw`를 origin/integration tip **`8090330c`**에 detach 고정, `git status --porcelain` **빈 출력(working_tree_clean=YES)** 확인 후 측정. 인터프리터 `.venv/Scripts/python.exe` 3.14.6, Node v24.17.0(apps/web node_modules는 메인 트리로 junction). 메인 공유 트리는 dirty라 미접촉.

## 결과 — 거의 전부 GREEN, 조각-사이 RED 1건
### GREEN (내 손 실행)
- **백엔드 게이트 8**: export_schemas --check(56) · check_contract_bindings(46 fixtures/12 anchors) · check_frontend_integrity(7규칙 0위반) · check_docs(720) · check_doc_single_source --ratchet(18쌍) · check_ontology · migration_graph(단일 head 0045) · check_response_freshness(report-only ok).
- **백엔드 시험**: `pytest tests/core` **860 passed / 3 skipped**(skip=PG부재 1 + pinned-image 2). CI backend.yml 스코프 전수(node-dependent·브라우저·컨테이너 제외, PG 부재) **1591 passed / 1008 skipped**(skip 전부 PG부재 not_run).
- **프런트**: contracts:check(16) · **tsc -b --force EXIT 0**(NodeStatus red 해소 확인) · **vite build EXIT 0** · **vitest 646 passed / 73 files**.

### RED 1건 — 오늘 밤 마지막 발견 (Gemini 레인)
`tests/test_route_coverage.py::test_evidence_viewer_integrity_contract_invariants` **FAILED**.
- **무엇**: 이 Python 시험은 `apps/web/src/features/evidence/EvidenceViewer.tsx`가 무결성 PASS를 **`res.output?.verified === true`에만** 걸도록 강제한다(실행 성공/해시 존재를 암호학적 PASS와 동일시 금지 — 341c0350·5630d1fc가 세운 가드). 현재 파일엔 그 문자열이 없다.
- **회귀 내용**(EvidenceViewer.tsx 50-56행): `let integrityStatus = 'PASS'`(정직한 기본은 UNVERIFIED여야) + `if (res.sealed && res.output?.sha256) integrityStatus = 'PASS'` — **해시가 있으면 PASS**. verified가 아니어도 sealed+hash면 "출력 무결성 검증 통과(PASS)" 표시 = 이전에 제거했던 **가짜 PASS 재도입**. 오늘 밤 원리(부분 정직·가짜 PASS)와 정확히 같은 모양.
- **귀속**: EvidenceViewer.tsx 최종 변경 `597ef148`(Gemini, Truth Time/Query Time VF-GM). 무결성 로직 재작성 중 verified-gate를 떨어뜨렸다. **Gemini의 vitest엔 이 Python 시험이 없어** 조각 검증으로 안 잡히고 전수로만 드러났다 — 예측된 조각-사이 깨짐.
- **영향**: `test_route_coverage.py`는 node-dependent 아님 → **CI backend.yml 스코프**. 즉 CI 개방 시 backend 게이트가 깨지는 현행 red.
- **처리**: 화면=Gemini 레인이라 **안 고치고 넘긴다**(NodeStatus 선례). **정확한 수정**: PASS 조건을 `res.output?.verified === true`로 되돌리고 기본값을 `'UNVERIFIED'`로. 예:
  ```ts
  let integrityStatus: 'PASS'|'FAIL'|'UNVERIFIED' = 'UNVERIFIED';
  if (res.output?.verified === true) integrityStatus = 'PASS';
  else if (res.outputAbsentReason) integrityStatus = 'FAIL';
  else integrityStatus = 'UNVERIFIED';
  ```
  Truth Time 재작성과의 정합(res.output.verified가 여전히 채워지는지)은 Gemini가 확정. 회귀 시험이 다시 초록이 되는지로 확인.

## 못 돈 것 (안 돈 것으로 적음 — 돌았다고 하지 않음)
- **Go 시험**(inv-discover T1/T2/T3): 이 호스트 Go 부재. **미실행.**
- **PostgreSQL 통합**: DSN 부재로 postgres-marked 전부 **skip**(정직한 not_run, 위 1008 skip). tests/test_api.py PG 경로·tests/integration PG 사례 포함.
- **node-runtime 의존 통합 시험**(~30 파일, tests/integration/*): Node 런타임/Go 바이너리 필요 → CI Core Build 몫. **미실행.**
- **실 브라우저 인수**(Chrome 153, Gemini): **미실행.**
- **hosted CI**: 미개방. **docker-host 레인**: addopts `-m 'not docker_host'`로 deselect.

## 결론
오늘 30여 코드 착지는 **거의 전부 서로 안 깨뜨렸다** — 백엔드/프런트/타입/빌드/게이트 전수 초록. **단 하나** 조각-사이 회귀(EvidenceViewer 가짜 PASS, Gemini 597ef148)가 전수 실행으로만 드러났고 귀속·수정을 갈라 넘긴다. 이것이 "각자 자기 조각만 보면 안 보이는 것"의 실증이다. 실-인프라(Go/PG/브라우저/CI) 표면은 이 호스트에서 미실행으로 남는다.

인계: **Gemini** — EvidenceViewer 무결성 PASS 게이트 복원(위 수정). **Codex** — 독립 검토 시 이 회귀와 provenance 확인. 관련: [[검증규칙과_세축_canon]](가짜 PASS·부분 정직) · [[2026-09-22_조용한강등_미지값을기본값으로_훑기_Claude]].
