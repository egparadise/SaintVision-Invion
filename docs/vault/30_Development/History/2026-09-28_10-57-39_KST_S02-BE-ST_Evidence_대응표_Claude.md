---
doc_id: "HIST-CLAUDE-2026-09-28-S02-BE-ST-EVIDENCE-MAP"
title: "S02-BE·S02-ST Evidence 대응표 — OIDC·mTLS 등록·Heartbeat·인증 실패 기록·제공 폴더·DataLocation 카탈로그 대응, 외부 U2~U6 BLOCKED_EXTERNAL 5·audit_events RLS F-S02-01 = PR #128 승인·병합 대기, 구현 추가 0 (카드 ba, docs-only)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T10:58:33+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S02-BE", "S02-ST"]
tags: ["S02-BE", "S02-ST", "AC-02", "evidence", "claude", "docs-only"]
---

# S02-BE·S02-ST Evidence 대응표 (2026-09-28, 카드 ba)

산출물: [[S02-BE·S02-ST Evidence 대응표]]. 이미 있는 것을 대응시키고 공백만 골라냈다. 구현·시험 추가 0.

## 1. 확인 방법(실제 수행한 것만)

`grep`/`sed`/`ls`로 `services/control-plane/src/inv/identity.py`·`node_channels.py`·`business_auth.py`·`app.py`(route 268-297·382-401·561-565), `src/saintvision/api/v1/nodes.py`·`storage.py` route, `src/saintvision/services/audit.py`, `tools/discovery_credential.py`·`lan_pilot.py`, 체크리스트 §0~§5 절 제목, 시험 파일별 `def test_` 수·이름을 읽었다. #120 collector 결과(run 36351674808)·#125/#138·#134·S02-FE Chrome 실측 History·VF-CL-01 History를 참조했다. run ID는 이 세션에서 관찰한 것만(Backend 36351202242·36351674808, desktop-browser 36364528322, Core 36353272311). 메모리 규칙에 따라 가벼운 명령만.

## 2. 결과

- 대응: OIDC 4·mTLS/Heartbeat 7·인증 실패 기록 2·제공 폴더 4·DataLocation 카탈로그 4 항목을 file:line + run ID/실측 기록에 대응하고 U1~U6에 연결(U1 결정됨).
- 공백: E1~E5 실 IdP·운영 CA·DNS·물리 5노드·Storage 제품 값 → BLOCKED_EXTERNAL(U2~U6); G1 `public.audit_events` RLS → F-S02-01 = PR #128(head 4c78afc6, 0047_audit_events_isolation) 승인·병합 대기(base 미착지; #159 선행 의존).
- 작은 PG-free 시험으로 메울 행동 공백 없음 → docs-only. 판정 논리 복제 없음.

## 3. 게이트·인계

check_docs·single_source·ontology 2·bindings·freshness·export_schemas --check·diff --check exit 0. 코드 변경 0. owner Claude / reviewer Codex / 병합 금지. worktree 재사용. 다음 첫 행동: Codex 검토.
