---
doc_id: "CLAUDE-INDEP-REVIEW-GUARD-TESTS-001"
title: "독립 검토 — Codex 가드 시험 복구(7956355): 무게 되살림·role-shape 중복판정·head 수정 공허성"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex(피검토)"
reviewed_at_tip: "a451d69"
code_commit: "7956355"
updated: "2026-09-21"
source_of_truth: "Git"
tags: ["independent-review", "guard-tests", "revival", "migration-head", "role-shape", "fixed-sha"]
---

# 독립 검토 — Codex 가드 시험 복구 (7956355)

미병합 점검이 넘긴 (2b) 가드 시험을 Codex가 착지(`7956355`·기록 `c36a285`). 보고("89 통과, 가드 제거 변형 1 실패")를 **읽지 않고 직접 되살렸다.**

## 검토 트리·환경
- 고정 tip **`a451d69`**(내 알람 커밋; `7956355`·`c36a285` 조상). 인터프리터 `.venv` python 3.14.
- **되살림을 실제 docker PG로 실행**: 이 호스트에 `postgres:16-alpine` 이미지 존재 → `INV_TEST_ROLE_GUARD_IMAGE=postgres:16-alpine`로 격리 컨테이너를 띄워 실 migration을 돌렸다. (R6-b: 측정 tip 못 박음. 공유 워킹트리는 세션 중 리셋되어 stale이므로 신뢰하지 않고 커밋본을 오버레이해 측정, 측정 후 원복.)
- Codex 변경 3파일: `tests/integration/test_recovery_drill.py`(+44, 실패 드릴 가드), `tests/test_migration_role_guard.py`(head 하드코딩→유도, role-shape 판정), `tools/definer-policy.json`(+11, definer 정책 데이터).

## ① 가드가 무게를 지는가 — 직접 되살림 (확증)
- **마이그레이션 역할 가드(핵심)**: 실 docker PG로 baseline **2 passed**(head/role + SUPERUSER-inv_app 거부). 그 뒤 `src/saintvision/db/migration_guard.py::assert_permission_groups`의 `raise`를 **중립화(pass)**한 변이본으로 `test_unsafe_predecessor_refused_before_schema_write[SUPERUSER-inv_app]` 재실행 → **FAIL**: `assert code != 0 and guard` → `assert (0 != 0)`. 즉 가드를 빼면 **불안전 선행 role이 있어도 업그레이드가 거부 안 하고 진행**(exit 0)하고, 시험이 정확히 그것을 잡는다. **무게 확증.** (가드 원복, MUTANT 0.)
- **실패 드릴 가드(순수 되살림, PG 불요)**: `tools/recovery_drill.py::_passed`를 직접 호출 — `integrityVerified:False` 실패 리포트 → `_passed=False`, 같은 리포트에 `integrityVerified:True`면 `_passed=True`. 시험의 `assert not drill._passed(report)`는 `_passed`가 integrity를 무시하면(항상 True) 깨진다 → 무게 있음. (DB 기록부 `outcome='failed', rpo/rto=None`는 PG integration이라 실행은 PG 시점, 로직은 순수 확증.)
- **definer 정책 가드**: `check_definer_functions.py`가 `definer-policy.json`과 라이브 함수를 대조 — 실 DB(그 함수들 존재)+`INV_AUDIT_DSN` 필요. 이번엔 미실행(구조 검토만): 정책에 `consume_discovery_issue_budget` 추가·revision 0044→0045 갱신은 쿼터 함수를 감사 범위에 넣은 것으로 타당. 실행 되살림은 PG 시점.

## ② role-shape 중복 판정이 옳은가 — 옳다 (다른 것을 지키던 게 아님)
Codex는 role-shape를 **중복**으로 보고 이식 대신 기존 `test_migration_role_guard`에 의존 + head 하드코딩만 고쳤다. 검증:
- 미병합 `test_role_shape.py`는 `saintvision.db.rls`의 **`DESIGNED_ROLE_SHAPE`·`shape_deviations`·`WeakerRoleExists`** 와 **`create_app_role`이 약한 선행 role에 `WeakerRoleExists`를 raise**하는 구현을 시험했다. **그런데 integration엔 그 세 심볼이 전무**(git grep: `rls.py`에 `create_app_role`만, 여전히 `IF NOT EXISTS`로 **선행 role에 양보**). → 그 구현은 **채택되지 않았고**, 미병합 unit 시험은 **import 자체가 불가**해 그대로 이식할 수 없다.
- 대신 integration은 같은 **속성**(불안전 선행 role 거부)을 **다른 기제**로 지킨다: 마이그레이션 preflight `migration_guard.assert_permission_groups`(migrations/env.py:80에서 스키마 쓰기 전 호출)가 거부. 이 기제를 ①에서 무게-확증했다.
- 따라서 "중복" 판정은 **옳다**: 속성은 지켜지고, 미병합 unit 시험은 채택 안 된 구현을 시험하던 것이라 무의미. **다른 속성을 지키다 빠뜨린 것 아님.**
- **잔여(결함 아님, 기록)**: integration `create_app_role`은 아직 `IF NOT EXISTS`(양보)다. B-9 보호는 **전적으로 preflight에 의존** — role 생성이 preflight가 도는 마이그레이션 경로로만 일어나는 한 안전하다. 마이그레이션 밖에서 `create_app_role`을 부르는 경로가 생기면 B-9 양보가 재발할 수 있다(현재 그런 호출자 없음).

## ③ head 수정이 또 공허하지 않은가 — 그 한 줄은 근사-공허, 그러나 시험은 공허하지 않다
오늘 마이그레이션-head 시험에서 본 것과 **같은 구조**다:
- `upgrade()`는 실 `alembic upgrade head`를 subprocess로 돌린다. 성공하면 alembic이 **자기가 파일에서 계산한 head로 `alembic_version`을 스탬프**한다 = `get_current_head()`. → `alembic_version == get_current_head()`는 **업그레이드가 exit 0이면 구성상 항상 참**(양쪽 다 같은 파일→alembic). 그 한 줄은 근사-공허(earlier `ordered[-1]==alembic_head`와 동형).
- **차이**: earlier는 아무것도 안 돌리는 순수 static 대조였다. 여기선 **업그레이드가 실제로 돈다.** 시험의 실제 보호는 head-등식이 아니라 **`upgrade()==(0,False)`를 두 번**(fresh 클러스터에 전 migration이 깨끗이 적용+멱등) + **role count==2**(inv_app·inv_kernel 비특권). 이 둘이 무게를 진다(①의 가드 중립화가 거부-시험을 깼고, migration이 깨지면 exit-0 단언이 깨진다).
- **실제 보호가 무엇인지(요청대로)**: (a) 전 migration이 fresh DB에 exit 0로 적용됨, (b) 재실행 멱등, (c) 결과 role이 비특권. head-등식은 (a)의 부산물이라 독립 무게 없음. **de-hardcoding은 옳다**: 옛 `=='0037_storage_sample_commit'` 하드코딩은 이미 stale(내가 실 PG로 돌리니 head는 `0045`라 옛 단언은 FAIL) — 브리틀 리터럴 제거이고, 실제 보호는 리터럴에 있던 적이 없다.

## 규격 드리프트 통지 (Codex에게 — 커널 소관)
내가 찾은 드리프트: **GOV-ALERT-001은 Node 시각 스큐 알람을 ERR-DESIGN-007 채택 시 활성화라 두었으나, 커널은 이미 `clock_skew_seconds>5`를 scheduler/placement/leases에서 운영 사용** 중. 규격과 구현이 갈렸다. 임의 활성화 안 함(도구는 governance-gated 기록). **규격을 고칠지 구현을 되돌릴지는 커널 소관 = Codex 판단.** 기록 위치:
- [[2026-09-21_알람평가_GOV-ALERT-001_복구_Claude]] §"규격 드리프트 1건" + 도구 `tools/alarm_check.py`의 `GOVERNANCE_GATED`.
- [[2026-09-21_이어가기_상태와규칙_Claude]] §4 "[규격 드리프트] Node 시각 스큐 알람 활성화 여부".

## 판정
- ① 가드 무게: **확증**(역할 가드 실 PG 되살림 FAIL 재현, 실패-드릴 순수 되살림). definer 되살림은 PG 시점.
- ② role-shape 중복 판정: **옳음**(미병합은 채택 안 된 구현의 unit 시험, 속성은 preflight가 지킴). 잔여: create_app_role은 아직 양보식 — preflight 의존 명시.
- ③ head 수정: 그 한 줄은 근사-공허(동형)이나 **시험은 공허하지 않다** — 실제 보호는 upgrade-적용+멱등+role-shape. de-hardcoding 옳음.

관련: [[2026-09-21_미병합브랜치_44커밋_유실점검_Claude]] · [[2026-09-21_알람평가_GOV-ALERT-001_복구_Claude]] · [[2026-09-21_Codex착지_마이그레이션head_Legacy제거_node결정_독립검토_Claude]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
