---
doc_id: "CLAUDE-ALARM-CHECK-RECOVERY-001"
title: "GOV-ALERT-001 알람 평가 도구 복구 — 규격·스키마 재확인, 소비 경로 정의, 양방향 시험"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
recovered_at_tip: "0979fe6"
updated: "2026-09-21"
source_of_truth: "Git"
tags: ["alarm", "GOV-ALERT-001", "recovery", "ops", "revival"]
---

# GOV-ALERT-001 알람 평가 도구 복구

미병합 점검([[2026-09-21_미병합브랜치_44커밋_유실점검_Claude]])이 찾은 유일한 (2a) 기능 유실 = 알람 평가 도구. **LegacyProjectCatalog의 정확한 거울상**: 그쪽은 계약이 있고 서빙이 없었고, 이쪽은 **규격(GOV-ALERT-001)이 있고 평가 도구가 없다.** 둘 다 "있다≠작동한다"인데 방향만 반대. **옛 커밋을 그대로 가져오지 않고** 지금 규격·스키마에 맞춰 복구했다.

## 복구 전 확인 (요청한 3가지)
### ① 규격이 지금 요구하는 것 vs 그때 도구가 평가하려던 것 — 대체로 일치
현재 [[알람 라우팅과 대응 주체]](GOV-ALERT-001 v1.0.0 draft)의 알람 20개 중 **DB가 답할 수 있는 것**을 옛 도구(00b1159)가 평가하려던 것과 대조: partition 잔여·체크섬 불일치·백업/복원 실패·Node 이탈 지연 = 일치. 나머지(비밀 노출·정책 우회·Evidence 기록 실패·OPA·중복 부수효과·Control Plane 오류율·지연 P95·추세)는 라이브 트래픽/메트릭이 필요해 DB 불가 → 도구가 **평가 불가 목록으로 명시**(정직성 유지).

### ② 스키마가 움직였나 — 움직였고, 하마터면 정상 코드를 "고칠" 뻔함
- **테이블 실재 확인**: `public.storage_checks`(mismatch_count·checked_at)·`public.backup_records`(verified)·`public.recovery_drills`(outcome) 전부 실재(0005 + 0036/0037 진화). `db.partitions.partition_status`도 실재.
- **노드 테이블이 둘**: saintvision `public.nodes`(status `active…`, `last_heartbeat_at`)와 커널 `inv.nodes`(status `online/offline`, `heartbeat_at`, `clock_skew_seconds`; `services/control-plane/src/inv/migrations/0001_core.sql`). **옛 도구는 `inv.nodes`를 `status='online'`·`heartbeat_at`·`clock_skew_seconds`로 조회 — 커널 테이블에 대해 정확했다.**
- **내 초기 오판과 정정**: 처음엔 grep 범위를 `migrations/`·`src/saintvision/db/models/`로만 잡아 `clock_skew_seconds`가 "없다"고 봤고 옛 도구를 버그라 결론낼 뻔했다. **범위가 커널 `inv/`를 뺀 것** → 빈 grep은 계측 고장이지 발견이 아님(`memory:empty-output-is-not-evidence`). 전 저장소 재검색으로 커널 `inv.nodes`에 세 컬럼 다 있음을 확인, **정상 코드를 "고치는" 오류를 회피**.
- **실제 필요한 정정 1건**: `recovery_drills` 실패 판정. 0036이 `CHECK(NOT met_targets OR outcome='passed')`를 걸었으므로 실패/중단 드릴은 `outcome<>'passed'`. 옛 도구의 `='failed'`는 'aborted'를 놓친다 → **`<>'passed'`로 교정**.

### ③ 소비 경로가 있나 — 없다 → (2번째 갈래) 도구 복구 + 누가·언제 정의
- CI/워크플로에 이 도구류(alarm/recovery_drill/operational_readiness/deployment_surface) 참조 **0건**. `operational_readiness.py`도 알람 미포함, `records.py`는 주석 1줄뿐. **아무도 안 부름.**
- 그래서 **아무도 안 부르는 도구를 되살리면 또 다른 죽은 계약**이 되므로 소비 경로를 함께 정의(→ [[서비스-시작-재시작-복구-절차]] §6-1): **누가**=DB/Backend/Storage/인프라 운영(항목별 규격 표), **언제**=(a) 릴리스 게이트 운영준비 증거 1회, (b) 운영 중 월 1회+드릴 직후. 자동 스케줄·채널 라우팅은 **CI 개방+채널 값 결정 후**. 그 전까지 수동 경로가 소비 경로이며 `not_run` 아닌 **수동 실행됨**으로 기록.

## 규격 드리프트 1건 — 별도 결정으로 적어만 둠 (3번째 갈래, 부분)
- **Node 시각 스큐 알람**: 규격은 "ERR-DESIGN-007 채택 시 활성화, 채택 전 알람 안 만듦"이라 두었으나, **커널은 이미 `clock_skew_seconds>5`를 scheduler/placement/leases에서 운영 사용** 중. 현실이 규격의 "보류" 문구를 지났다. 도구는 이 알람을 **울리지 않고 `governanceGated`로 기록**한다. **활성화 여부는 규격 개정을 먼저 해야 하는 별도 결정** — 여기선 기록만(요청대로).

## 복구물 + 오늘 기준(양방향) 증명
- `tools/alarm_check.py`: **순수 판정 함수**(`count_alarm`·`partition_alarm`, DB 불요) + 얇은 DB 층(`evaluate`, sqlalchemy는 함수 내부 import라 모듈 import에 PG 불요). 정직성 유지(`coverage`·`notEvaluable`·`governanceGated`·"never healthy").
- `tests/test_alarm_check.py`: **참일 때 울리고 거짓일 때 안 울리는 양쪽**을 각 알람마다 짝지어 시험. `.venv` python 3.14 **10 passed**.
- **되살림(오늘 기준 준수)**: `count_alarm`을 **항상 울리도록** 변이(`firing: True`)한 복사본에 시험을 돌리니 **정확히 조용해야-하는 시험 3건이 FAIL**(`is_quiet_when_zero`·`far_future_is_quiet`·`exactly_sixty_days_is_quiet`), 7 pass. → **한쪽만 보는 시험이 아니다**(항상-울리는 도구는 통과 못 함). 조용한 쪽이 무게를 진다.

## 인계 / 남은 것
- **가드 시험 5건은 Codex 소관**(미병합 점검의 (2b): definer 코드읽기·복구지점·드릴recording·역할shape — 기능은 착지, 회귀보호 시험만 이식). 이 중 알람 시험은 복구와 함께 내가 작성했으니 중복 방지 위해 Codex에 통지.
- **실 PG 검증 미실행**(이 호스트 PG 부재): `evaluate()`의 실제 쿼리 실행은 PG 필요 → 통합 목록의 PG 시점에. 판정 로직은 순수 함수로 PG 없이 확증. `INV_AUDIT_DSN` 필요.
- **규격 드리프트(스큐 알람 활성화)**: 별도 결정 대기(이어가기 §4).

관련: [[2026-09-21_미병합브랜치_44커밋_유실점검_Claude]] · [[알람 라우팅과 대응 주체]] · [[서비스-시작-재시작-복구-절차]] · [[2026-09-21_이어가기_상태와규칙_Claude]]
