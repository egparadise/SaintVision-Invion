---
doc_id: "HIST-CLAUDE-2026-09-28-S03-ST-EVIDENCE-MAP"
title: "S03-ST Evidence 대응표 — 볼륨·Artifact 전송·checksum·허용/거부 기록·exit code/증거 ID 대응, S3는 #149/#159 인용, 공백 G1 Windows 게이트·G2 #159·G3 F-S02-01·외부 1, 구현 추가 0 (카드 az, docs-only)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T10:51:32+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S03-ST"]
tags: ["S03-ST", "AC-03", "evidence", "claude", "docs-only"]
---

# S03-ST Evidence 대응표 (2026-09-28, 카드 az)

산출물: [[S03-ST 볼륨·Artifact 기본 전송 Evidence 대응표]]. 이미 있는 것을 대응시키고 공백만 골라냈다. 구현·시험 추가 0.

## 1. 확인 방법(실제 수행한 것만)

`grep`/`sed`/`ls`로 `services/control-plane/src/inv/`의 `workspace_files.py`·`workspace_start.py`·`output_ingestion.py`·`object_store.py`·`storage.py`·`storage_commit.py`·`sandbox.py`·`policy.py`·`containment.py`·`results.py`·`app.py`(route 470-481), `src/saintvision/services/verification.py`·`audit.py`, `src/saintvision/storage/*`의 정의 행과 시험 파일별 `def test_` 수, `.github/workflows/core.yml`의 JUnit 단계를 읽었다. #149·#159 본문 요약, #121 collector 조항, #120 RLS evidence(E2)를 참조했다. run ID는 이 세션에서 관찰한 Core 36353272311(artifact 8 XML 파싱)·Backend 36351202242·36351646801만 인용. 메모리 0.6GB 규칙에 따라 로컬 실 PG·Docker·전체 suite·무거운 명령 없음.

## 2. 결과

- 대응: Workspace 볼륨 4·Artifact 업로드/다운로드 5·checksum 4·허용/거부 기록 5·exit code/증거 ID 4 항목을 file:line + run ID로 대응.
- 공백: G1 `test_results.py` Windows 게이트 → NOT_OBSERVED(로컬)·hosted 실행; G2 S3 제품 경로 → #159 검토 중(인용만); G3 `public.audit_events` RLS → F-S02-01 별도 카드; E1 실 5노드 전송 → BLOCKED_EXTERNAL.
- 작은 PG-free 시험으로 메울 행동 공백 없음 → docs-only. 판정 논리 복제 없음.

## 3. 게이트·인계

check_docs·single_source·ontology 2·bindings·freshness·export_schemas --check·diff --check exit 0. 코드 변경 0. owner Claude / reviewer Codex / 병합 금지. worktree 재사용. 다음 첫 행동: Codex 검토.
