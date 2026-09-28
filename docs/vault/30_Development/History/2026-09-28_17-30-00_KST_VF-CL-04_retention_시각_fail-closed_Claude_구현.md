---
doc_id: "HIST-CLAUDE-2026-09-28-VFCL04-RETENTION-FAIL-CLOSED"
title: "VF-CL-04 archive retention 도구 결함 수정 — F-VFCL04-01(시각 파싱 실패의 조용한 mtime fallback) fail-closed, F-VFCL04-02(%Z 서버 timezone 오파싱) 숫자 offset/UTC만 수용·명명 약어 거부, 되살림·속성 시험 19건 (카드 al)"
version: "1.2.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T17:50:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["VF-CL-04"]
tags: ["VF-CL-04", "pitr", "retention", "fail-closed", "timezone", "claude"]
---

# VF-CL-04 retention 도구 결함 수정 (2026-09-28, 카드 al)

근거: PR #147 Codex 검토 F-VFCL04-01과 Claude owner 확인 §7·§9(신규 F-VFCL04-02). 대상 `tools/pitr_archive_retention.py`(`3e267b05`, 통합 tip `1e8baf04`에 포함) — `parse_backup_label`·`load_backups`·`plan`·CLI. migration·계약·제품 라우트 무변경, 기본 dry-run 유지.

## 1. 결함과 수정

| # | 결함(옛 동작, 옛 코드로 재현) | 수정 |
|---|---|---|
| F-VFCL04-01 | `START TIME`이 세 strptime 형식 모두 실패하면 **디렉터리 mtime**이 나이가 됨 → 재현: 손상 label + 30일 전 mtime ⇒ `delete_backups=['bad']`, 오류 없음. `newest = max(taken_at)`도 오염 | **파싱 실패 = `ValueError`**(같은 함수의 `START WAL LOCATION` 누락 정책과 동일). `load_backups`는 `<backup>/backup_label: <이유>`로 다시 raise, CLI는 계획 없이 `mode=refused`·`error` JSON 출력·**exit 3**(`--apply`여도 아무것도 삭제 안 함). `START TIME` **부재**는 mtime 대체 없이 **unknown age**: `BaseBackup.taken_at=None` → 항상 retained, 절대 삭제 후보 아님, newest 선택에서 제외(known 중에서만), start segment는 boundary `min`에 포함(WAL 보존). `Plan.unknown_age_backups`·reason에 명시 |
| F-VFCL04-02 | `%Z`는 CPython에서 UTC·GMT·로컬 tzname만 수용, PostgreSQL은 서버 timezone 약어(KST 등)로 씀 → 재현: `KST` label ⇒ fallback(30일 전 mtime), `+0900`(공백) ⇒ 파싱 실패 fallback, naive ⇒ 조용히 UTC | `parse_start_time`: `<date> <time> <zone>`만 받고, zone이 `UTC`/`GMT`/`Z`면 UTC, 숫자 offset(`+0900`·`+09:00`·공백 유무)이면 offset 적용 후 UTC 환산, **명명 비-UTC 약어(KST·EST·CET…)는 거부**, zone 없는 naive는 **거부**(UTC 가정 안 함), ISO `T…Z` 등 다른 형은 거부. 결과가 runner 로컬 zone에 의존하지 않음 |

## 2. 시험 (PG-free, `tests/test_pitr_archive_retention.py` 9 → **37 passed**, 하네스 시험 +1)

- 되살림 F01 3: 손상 `START TIME` → `load_backups` ValueError(경로 포함) / CLI `--apply`가 exit 3·`mode=refused`·파일 무삭제 / `START TIME` 부재 → unknown age retained·newest는 known 중에서·boundary 미전진·reason 표기. + unknown만 있을 때 전부 retained.
- 되살림 F02 8+6: UTC·GMT·`+0900`·`+09:00`·`-0500`·붙여쓴 `+0900`이 정확한 UTC instant / KST·EST·CET·naive·ISO-Z·쓰레기 거부(`parse_backup_label`도 raise) / `time.tzname`을 KST로 바꿔도 결과 동일.
- 속성 시험 신규 1(300 반복): unknown-age backup은 항상 retained·절대 삭제 후보 아님, newest는 known 중에서만(known 없으면 삭제 0), boundary = 모든 retained의 최소 start이며 unknown의 start ≥ boundary, 삭제 WAL은 전부 boundary 이전. 기존 속성 시험은 그대로 통과.
- Codex 검토(#150) 반영 1: filesystem seam 되살림 — 실제 temp backup 디렉터리에 START TIME 없는 label을 쓰고 디렉터리·label mtime을 400일 전으로 둔 뒤 `load_backups()`가 `taken_at is None`을 돌려주고, 그 결과를 `plan()`에 넣어 retained·삭제 후보 아님·known newest 비오염·boundary 미전진을 단언. 변이(`UnknownAge` → `child.stat().st_mtime`) 적용 시 이 시험만 실패(1 failed / 28 passed), 복원 시 29 passed.
- hosted Backend red 1회(run 36362748049, head 29a2b131: `tests/test_pitr_opt_in_dry_run.py` 4건이 `+00` 형식 label에서 실패) → **내 결함**: PostgreSQL은 이름 없는 zone을 `+HH`/`-HH`로 약칭하고 timestamptz 텍스트도 `+00`/`+05:30`이므로 이는 숫자 offset이지 명명 약어가 아니다. `_NUMERIC_OFFSET`을 `[+-]HH(:?MM)?`로 넓히고 `+HH`는 `+HH00`으로 정규화. 시험 5(`+00`·` +00`·`+09`·`+05:30`·`-05`) + 잘못된 offset 거부 3 추가. `pitr_opt_in_dry_run` 하네스는 기존 `ValueError → parser.error(exit 2)` 경로가 이 fail-closed도 덮음을 시험 1건으로 고정(보고서 미작성·stderr에 label 경로·zone). 총 43 passed(retention 37 + 하네스 6).
- 옛 코드 되살림(별도 스크립트, 위 표의 재현 값): F01 `delete_backups=['bad']` 무오류, F02 KST → mtime fallback, `+0900` → fallback, naive → UTC 도장. 새 시험 파일은 옛 코드에서 import 단계부터 실패(신규 심볼).

## 3. 게이트·경계·인계

check_docs·single_source·ontology 2·bindings·freshness·export_schemas --check·diff --check exit 0. 실 PG·Docker 없음(도구는 파일시스템 전용). VF-CL-04의 다른 두 blocker(#126 drill skip 전환, retention·readiness 운영 gate 미배선)는 건드리지 않음. registry의 blocker id 2개(`archive-retention-…` fail-closed / `…-start-time-timezone-misparsed`)는 #147(Codex) 쪽 문서 작업이며, 이 PR 병합 뒤 해제 근거가 된다. runbook에 label 시각 규칙 한 줄 추가. owner Claude / reviewer Codex / 병합 금지. 다음 첫 행동: Codex 검토 → hosted Backend(`tests/test_pitr_archive_retention.py` 28건 포함) 확인.
