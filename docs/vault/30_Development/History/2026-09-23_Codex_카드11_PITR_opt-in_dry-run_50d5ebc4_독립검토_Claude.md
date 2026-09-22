---
doc_id: "HIST-CLAUDE-REVIEW-CODEX-CARD11-PITR-DRYRUN-001"
title: "Codex 카드 11 독립 검토 — 50d5ebc4 PITR non-mutating opt-in 재연습(pitr_opt_in_dry_run.py): 코드 정독 쓰기 0·dev PG 1회 실행 absent 정직 표기·AC-12 드릴 초안 '드릴 전 미달성' 경계 유지·게이트·되살림 2 KILLED → 승인(관찰 2)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-23T02:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["review", "codex", "card11", "pitr", "S08-DB", "AC-12", "dry-run", "mutation"]
---

# Codex 카드 11 독립 검토 (reviewer Claude)

대상: integration `50d5ebc4`(feat(pitr): add non-mutating opt-in rehearsal — `tools/pitr_opt_in_dry_run.py` 134줄, `tests/test_pitr_opt_in_dry_run.py` 5 시험, Evidence `s08-pitr-opt-in/2026-09-23_dev-pg-dry-run.json`, 절차서 [[S08-DB_PITR_opt-in_dry-run과_AC-12_복구드릴_초안]]). 검토 트리 `.worktrees/claude-rev11`(tip). 결정 #8 = [[2026-09-22_CX-09_PITR_Tier-A_활성여부_결정준비_Claude]]의 **B(Tier-A 유예)** 유지가 전제.

## 판정: **승인** (finding 0, 관찰 2)

## (a) 실제로 non-mutating인가 — 코드 정독

| 경로 | 관측 | 쓰기 |
|---|---|---|
| DB | `pitr_readiness.read_settings`: `psycopg.connect(autocommit=True)` + `SELECT current_setting(%s, true)`만 | 0 |
| PostgreSQL 설정·재시작·compose | `ALTER SYSTEM`·`pg_reload_conf`·`docker`·`subprocess` 호출 없음(grep 0) | 0 |
| 아카이브/백업 볼륨 | `pitr_archive_retention.load_archive/load_backups/plan`만 호출; 삭제는 별도 `apply()`(`unlink`/`rmtree`)로 이 도구는 호출하지 않음 | 0 |
| 파일 | `--output` 지정 시 그 경로에만 tmp→replace로 JSON 기록 | 출력 1 |
| 보고 | `mutations{postgresRestarted, postgresSettingsChanged, composeApplied, retentionApplied}` 전부 `False` 고정, `acceptance{pitrVerified, ac12Satisfied}` `False` 고정 + reason | — |

## (b) dev PG 1회 실행 (읽기 전용)

`INV_PITR_DSN`=.env admin DSN(invdev), `--archive/--backups`=레포 밖 빈 디렉터리, `--output` 레포 밖. 결과 exit 0: `decision tier-a-deferred` · `harnessVerdict observed` · readiness **`absent`**(`archive_mode off`, `archive_command disabled`, `archive_library unset`, `wal_level replica`) · mutations 전부 False · acceptance 전부 False · retention "no base backup: nothing is deletable". 커밋 Evidence JSON과 설정·verdict 동일. 실행 후 `SHOW archive_mode` = `off`(무변경). 출력에 DSN/비밀 0건. → 결정 B 상태를 **정직 표기**.

## (c) AC-12 드릴 절차서 초안 경계
- §1 결정 B 유지, `possible`은 "설정 전제만 관측"으로 정의, dry-run은 연속 WAL·목표시각 복구·RPO/RTO·재개를 증명하지 않음 ✔.
- §2 종료 코드 `0/2/3` 명시, `--require-possible`도 복구 인수가 아님 ✔; `--require-pitr`(readiness)는 설정만으로 인수를 막기 위해 계속 exit 1 ✔.
- §4 드릴은 **Tier-A 활성 후**·격리 restore host·marker A/B·LSN/timeline·fencing·recovery epoch·RPO(실제 durable commit 차이, ≤15분)·RTO(≤1시간)·artifact 이름 고정·"reviewer 독립 검토 전 S08-DB/AC-12 done 금지" ✔ — "드릴 전 미달성" 경계 유지.
- 절차서의 `password` 문자열은 "로그에 DSN/password/key를 넣지 않는다"는 정책 문장(값 아님).

## (d) 게이트·되살림
| 항목 | 결과 |
|---|---|
| `pytest tests/test_pitr_opt_in_dry_run.py tests/test_pitr_readiness.py tests/test_pitr_archive_retention.py` | **22 passed, 1 skipped**(5+7+9; Codex 보고 22와 일치) |
| `check_docs` | PASS 844 |
| M1 `acceptance.pitrVerified/ac12Satisfied`를 `readiness == possible`로 유도(고정 False 제거) | **KILLED** — 2 failed(`assert True is False`) |
| M2 `mutations.composeApplied`를 True로 | **KILLED** — 1 failed |

## 관찰 (비차단)
- **O1** `main()`이 `read_settings` 예외를 전부 `settings = {}`로 삼켜 `inconclusive`/exit 2가 되지만 JSON에 **원인**(env 미설정 vs 연결 실패 vs 권한)이 남지 않는다. `readiness.reasons` 또는 `inputs.settingsReadable`+사유 한 줄 권고.
- **O2** 빈 `--archive/--backups`로도 `harnessVerdict observed`가 된다(디렉터리 존재만 검사). 재연습 사본 여부를 알 수 없으므로 `inputs`에 항목 수(`archiveEntries`, `backupEntries`)를 기록해 "비어 있는 관측"을 구분하면 좋다.

## 부수 조치
`.work/dev/orch/codex-worker-status.md`에 `CLAUDE-REVIEW:` 줄. 코드 변경 없음(docs-only PR).
