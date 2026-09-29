---
doc_id: "HIST-CLAUDE-2026-09-28-S12-ST-EVIDENCE-MAP"
title: "S12-ST Evidence 대응표 — 운영 점검·제공 폴더·복구 훈련의 기존 도구·시험·hosted run 대응, 공백 5(NOT_OBSERVED 1·BLOCKED_EXTERNAL 4), 구현 추가 0 (카드 as, docs-only)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T10:17:17+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S12-ST"]
tags: ["S12-ST", "AC-12", "evidence", "claude", "docs-only"]
---

# S12-ST Evidence 대응표 (2026-09-28, 카드 as)

산출물: [[S12-ST 운영 점검·제공 폴더·복구 훈련 Evidence 대응표]]. 코디네이터 지시대로 **이미 있는 것을 대응시키고 공백만 골라냈다**. 세 범위 모두 도구·시험·hosted lane이 있어 새 구현은 넣지 않았다.

## 1. 확인 방법(실제 수행한 것만)

`grep`/`sed`로 `tools/operational_readiness.py`·`alarm_check.py`·`storage_check.py`·`check_storage_bundle.py`·`check_lan_storage_readiness.py`·`recovery_drill.py`·`pitr_*.py`·`src/saintvision/services/pilot.py`의 함수 위치와 시험 파일별 `def test_` 수를 읽었고, `.github/workflows/core.yml`·`backend.yml`·`desktop-browser.yml`의 lane 정의를 대조했다. run ID는 이 세션에서 직접 관찰한 hosted run(Core 36353272311 artifact 8 XML 파싱, Backend 36351202242·36363486696 요약행, desktop-browser 36364528322 pass)만 인용했다. 로컬 실 PG·Docker·전체 suite 없음.

## 2. 결과

- 운영 점검 6항목·제공 폴더 6항목·복구 훈련 7항목·registry evidence 4종을 file:line + run ID로 대응(대응표 §1).
- 공백 5: G1 live archiver 2 케이스가 hosted에서 항상 skip → **NOT_OBSERVED(hosted)**(시험 접속 경로 변경 필요, #126 검토에서 별도 검토 항목 → Codex 판단, 이 카드에서 구현 안 함); G2 파일럿 실제 제공 폴더(U5) · G3 off-site backup 선언(ADR-018) · G4 실 PITR/운영 RPO·RTO(CX-09 Tier-A 유예) · G5 release manifest·사용자 인수·물리 Node 브라우저 인수 → **BLOCKED_EXTERNAL** + 이유.
- 판정 논리 복제 없음, 도구 verdict 의미 불변.

## 3. 게이트·인계

check_docs·single_source·ontology 2·bindings·freshness·export_schemas --check·diff --check exit 0. 코드 변경 0. owner Claude / reviewer Codex / 병합 금지. worktree 재사용. 다음 첫 행동: Codex 검토(G1 판단 포함).
