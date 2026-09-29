---
title: "G-04 W5 선행 migration 0053 — eval_suites.project_id"
version: "1.0"
status: "review"
author: "Claude"
updated: "2026-09-28T17:29:11+09:00"
---

# G-04 W5 선행 migration 0053 — eval_suites.project_id

branch `agent/claude/g04-w5-migration-0053`, base #197 head `977faf90`(0052) + #183 설계 branch merge(문구 정정을 같은 PR에 두기 위해). 설계 G-04·G-05 business lane route 통합 설계 §5-1 최소안.

## 한 것

- `migrations/versions/0053_eval_suite_project_scope.py` (`down_revision = 0052_model_version_digest_scope`): `eval_suites.project_id` nullable `CHAR(30)`(InvId) + composite FK `fk_eval_suites_tenant_id_project_id (tenant_id, project_id) → projects` + index `ix_eval_suites_tenant_id_project_id`. 기존 suite는 NULL(W5 route는 NULL suite를 404). `eval_runs`는 suite로 전이(컬럼 없음).
- upgrade는 0052 방식대로 **catalogue를 읽고 수렴**: 없음 → 셋 추가 / column 정상(resume) → 데이터 검사(고아 project 참조 fail-closed) 뒤 없는 것만 추가 / column·FK 이름이 다른 모양 → 거부 / offline(`--sql`)은 전부 렌더. downgrade는 scoped suite가 하나라도 있으면 거부(조용한 손실 방지), 없으면 index·FK·column `IF EXISTS` drop.
- ORM `EvalSuite`에 같은 column·FK·index. `tools/definer-policy.json` revision·head-pin 시험 → 0053. `migration_graph --head` = `0053_eval_suite_project_scope`(단일 head).
- 설계 문구 정정(v1.2.2): §5-1·§9의 W5 번호 `0052` → `0053`, 순서 `…→0052(#191 F1)→0053(W5)`.

## 검증

- PG-free `tests/core/test_eval_suite_project_scope_migration.py`: 로컬 실행(아래 PR 코멘트 수치). stand-in catalogue로 upgrade/downgrade 경로 전부, graph head, ORM 선언 일치.
- 실 PG `tests/integration/test_eval_suite_project_scope_real_pg.py`(hosted): catalogue 모양, legacy NULL·scoped 결속, 타 tenant project·없는 project FK 거부, **resume**(column만 있는 상태에서 alembic 재실행 → FK·index만 추가·0053 기록), **고아 참조가 있는 resume은 FK 추가 전 거부**.
- NOT_OBSERVED: downgrade 실행은 실 PG에서 하지 않았다(PG-free 문장 단언만).

## 다음

Codex 검토 → hosted 인용. W5 route PR(8)은 #191 승인 뒤 그 위에 stack.
