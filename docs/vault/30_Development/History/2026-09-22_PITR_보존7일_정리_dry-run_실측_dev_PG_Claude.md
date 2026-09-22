---
doc_id: "HIST-CLAUDE-PITR-RETENTION-MEASURE-001"
title: "PITR 보존 7일 정리(tools/pitr_archive_retention.py) 실측 — dev PG 실제 base backup 라벨·실제 WAL 이름으로 dry-run/+8일/사본 apply, 불변식 확인 (PR #49 우리 몫 3)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T20:45:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["pitr", "retention", "vf-cl-04", "dev-pg", "dry-run", "evidence", "S01-ST"]
---

# PITR 보존 7일 정리 실측 (dev PG, 비파괴)

[[2026-09-22_S01-BE_S01-ST_잔여_합격조건표_Claude]] "우리 몫 3"(보존 정리 실측). 도구 `tools/pitr_archive_retention.py`(VF-CL-04, 보관 7일 파일럿 결정)는 **파일시스템 전용**(DSN을 읽지 않음)이므로 "dev PG에 실측"의 정직한 형태는: **dev 클러스터에서 실제로 만든 base backup 라벨 2개와 실제 WAL 세그먼트 이름**을 아카이브 레이아웃으로 구성해 도구를 돌리는 것이다. dev PG 자체는 `archive_mode=off`·`/wal_archive` 없음(PITR absent, [[2026-09-22_17-14-47_KST_PITR-RUNBOOK_Claude_실측]])이라 **정리할 실제 아카이브가 없다** — 이 실측은 "정리 도구가 실물 라벨/이름에서 옳게 계획·삭제한다"를 증명하지, dev PG가 정리되고 있다는 뜻이 아니다.

## 1. Provenance
- 코드 tip `b877c601`(트리 `.worktrees/claude-ret`, clean). 인터프리터 `.venv` py3.14.7. 실행 2026-09-22 20:19 KST.
- dev PG `saintvision-invion-dev-pg`(PostgreSQL 16, `wal_level=replica`, `archive_mode=off`). **DB 변경 없음**: `pg_basebackup -X none -c fast` 2회(컨테이너 `/tmp`에 생성 → 라벨만 복사 → 삭제), `pg_switch_wal()` 2회(세그먼트 경계만 이동), `pg_ls_waldir()` 읽기.
- 실물: bb1 라벨 `START WAL LOCATION 0/BB000028 (file …BB)`, bb2 `0/BD000028 (file …BD)`, timeline 1; `pg_wal` 실제 이름 `…BD …BE …BF …C0 …C1`(5개). **`…BB`·`…BC`는 bb1 시점에 실제 존재했던 세그먼트 이름**이나 archive_mode off라 이미 재활용됨 — 아카이브가 있었다면 남았을 파일이므로 이름만 추가(빈 파일). 증거: `Evidence/pitr-retention/2026-09-22_devpg_labels_and_waldir.txt`.
- 비밀: 라벨·JSON에 DSN/비밀번호/호스트 0건(grep 확인).

## 2. 결과

| 실행 | 명령(요지) | 관측 | 불변식 |
|---|---|---|---|
| ① dry-run, 실 클록 | `--archive A --backups B` (기본 7일) | exit 0. `retainedBackups=[bb1,bb2]`, `oldestRetainedStartSegment=…BB`, **delete 0/0**, kept 7. reason: "retain backups newer than 2026-09-15… plus the newest; keep WAL from …BB onward" | 두 백업 모두 7일 이내 → 아무것도 후보 아님(#2) |
| ② dry-run, 클록 +8일 | `--now 2026-09-30T12:00:00+00:00` | `retained=[bb2]`, oldest start `…BD`, **deleteBackups=[bb1]**, **deleteArchive=[…BB, …BC]**, kept 5 | 최신 bb2는 나이와 무관하게 보존(#1); bb2 START(…BD) 이후 세그먼트 전부 보존(#3); 그 앞 BB·BC만 후보 |
| ③ `--apply` (사본) | ② + `--apply` on 복사본 | exit 0. 삭제 = 정확히 bb1 + BB·BC. 남은 archive `BD BE BF C0 C1`, backups `bb2`. **원본 디렉터리 무변경(7/2)** | 계획과 삭제 집합 일치; 삭제는 `--apply`에서만 |
| ④ 자기시험 | `pytest tests/test_pitr_archive_retention.py` | **9 passed**(속성 시험 포함: 보존 창의 WAL은 절대 후보가 아님) | 불변식 1~5 회귀 |

증거: `Evidence/pitr-retention/2026-09-22_dryrun_realclock.json` · `…_dryrun_plus8d.json` · `…_apply_on_copy_plus8d.json`.

## 3. 해석 (정직)
- 도구는 **실물 라벨·실물 세그먼트 이름**에서 결정 7일 규칙을 옳게 적용하며, 삭제 후에도 최신 base backup부터 "지금"까지의 WAL이 완전하다(복구 가능성 보존). 삭제는 dry-run에서 절대 일어나지 않았다.
- **dev PG는 정리 대상이 없다**(아카이브 부재). 이 결과로 "보존 정리가 운영 중"이라고 적을 수 없다. 결정 B([[2026-09-22_CX-09_PITR_Tier-A_활성여부_결정준비_Claude]])대로 Tier-A 활성 후 실제 `/wal_archive`에 같은 명령을 돌린 것이 운영 증거가 된다.
- `.backup` 라벨 파일·`.history`는 이번 입력에 없었다(archive_mode off라 archive_command가 쓰지 않음) — 그 분기는 자기시험 ④가 덮는다.

## 4. 남은 것
- Tier-A 활성 후: 실제 아카이브에 ① 실행 → 주기(예: 일 1회) 결정·자동화(운영자). 이 도구를 cron/compose sidecar로 배선하는 것은 별도 카드.
- S01-ST 표에서 "보존 정리 실측"은 이 문서로 **부분 충족**(도구 검증 완료, 실 아카이브 실행은 활성 대기)으로 갱신.

관련: [[VF-CL-04 replica 복구와 PITR 운영 runbook]] §4 · [[S02_선행입력_체크리스트_2026-09-22]] §5
