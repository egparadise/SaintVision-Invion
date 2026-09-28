---
doc_id: "HIST-CLAUDE-2026-09-28-S10-BE-EVIDENCE-MAP"
title: "S10-BE Evidence 대응표 — Provider adapter contract/conformance/CLI 4종·승인 배포·commitment route·lineage query(#158)·S10-FE(#144/#146) 대응, MLflow 코드 부재(공백+BLOCKED_EXTERNAL), 실 Provider BLOCKED_EXTERNAL, 구현 추가 0 (카드 bc, docs-only)"
version: "1.2.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T11:12:21+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S10-BE"]
tags: ["S10-BE", "AC-10", "evidence", "claude", "docs-only"]
---

# S10-BE Evidence 대응표 (2026-09-28, 카드 bc)

산출물: [[S10-BE Evidence 대응표]]. 이미 있는 것을 대응시키고 공백만 골라냈다. 구현·시험 추가 0.

## 1. 확인 방법(실제 수행한 것만)

`grep`/`sed`/`ls`로 `src/saintvision/adapters/`(contract·reference·conformance·agents·cli·process_output·model_import)의 정의 행, `src/saintvision/api/v1/adapters.py` route, `src/saintvision/services/lineage.py:454~534`, `services/control-plane/src/inv/app.py:449`, 시험 파일별 `def test_` 이름·수, `tests/test_cli_adapters.py:382`의 skip 사유를 읽었다. MLflow는 `git grep -i mlflow -- src services tools tests requirements*.txt pyproject.toml`로 0건임을 확인했다(문서 7건만). #158·#144·#146 파일 목록과 본문 요약을 참조했다. run ID는 이 세션에서 관찰한 Backend 36351202242(head a0dab579b188, 2929/47/2/0)·Core 36353272311(head bc27588d2139, main 3236/17/2/0)·desktop-browser 36364528322(head 30f5ca839923)만 인용 — SHA는 `gh run view --json headSha`, 합계는 passed·skipped·deselected·failed 분리(#164 Codex 기준). 메모리 0.9GB 규칙에 따라 가벼운 명령만.

## 2. 결과

- 대응: adapter contract/conformance/CLI 9항목·MLflow 1·승인 배포 5·commitment/lineage 3을 file:line + run ID로 대응(#127 collector `deployment-digest-and-approval` 12 케이스·#160 S10-ST 대응표와 정합).
- 공백(v1.2 정정): G1a MLflow adapter·계약·설정·시험 부재 → 내부 IMPLEMENTATION/DESIGN GAP(owner 결정) · G1b 구현 뒤 실제 endpoint·credential 실측 → BLOCKED_EXTERNAL; G5 CLI 4종 실바이너리 적합성 hosted skip(shutil.which 부재) → CI_LANE_GAP/NOT_OBSERVED(바이너리 provision으로 메움) · E1 실 계정·CX-02 운영 인수만 BLOCKED_EXTERNAL; G2 `/v1/adapters` HTTP 레벨 시험 없음 → NOT_OBSERVED(후속 소카드); G3 conformance API 노출 없음(#146 FE "미측정") → 설계 대상; G4 승인 배포·lineage query business route → #158·카드 ar·#152 lane; (원칙: 우리가 코드로 만들 수 있는 것은 BLOCKED_EXTERNAL로 강등하지 않음.)
- 작은 PG-free 시험으로 메울 행동 공백 없음 → docs-only. 판정 논리 복제 없음.

## 2b. Codex 검토(#166) 반영

(1) run SHA·합계 4항 분리(v1.1). (2) MLflow 코드 부재를 BLOCKED_EXTERNAL로 강등했던 것을 G1a 내부 구현/설계 공백 + G1b 구현 뒤 운영 실측(외부)으로 분리. (3) CLI 4종 skip을 CI_LANE_GAP/NOT_OBSERVED(G5)로, 실 계정·CX-02 운영 인수만 E1 BLOCKED_EXTERNAL로 분리; 'install 미실행'을 '제품 adapter가 install을 수행하지 않음'으로 좁힘(v1.2). 같은 강등 점검: #161 E2 '실 Provider adapter → BLOCKED_EXTERNAL'이 같은 부류(CLI 미provision은 CI 공백, credential만 외부), #161 E1 AC-09 제품 지표는 내부 측정 러너 부재가 섞여 있음(#113 S09-FE 러너 설계) → 코디네이터 보고; #163 E1(물리 5노드)·#164 E1~E5(U2~U6 사용자 입력)는 진짜 외부.

## 3. 게이트·인계

check_docs·single_source·ontology 2·bindings·freshness·export_schemas --check·diff --check exit 0. 코드 변경 0. owner Claude / reviewer Codex / 병합 금지. worktree 재사용. 다음 첫 행동: Codex 검토 → G1 MLflow 결정은 코디네이터.
