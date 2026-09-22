---
doc_id: "HIST-CODEX-2026-09-23-S08-DB-PITR-OPTIN-DRYRUN"
title: "S08-DB recovery·PITR opt-in dry-run 하네스와 AC-12 드릴 초안"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T01:38:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_ids: ["S08-DB"]
tags: ["s08-db", "pitr", "recovery", "ac-12", "dry-run", "tier-a"]
---

# S08-DB recovery·PITR opt-in dry-run

## 범위와 착지

- base: `433d5dfbcadada65acb11cfc2cf118a00fa66253`
- implementation: `50d5ebc4e08be20cfa047e52d4b79005442b485c`
- owner/reviewer: Codex / Claude
- 결정 경계: [[2026-09-22_CX-09_PITR_Tier-A_활성여부_결정준비_Claude]]의 **B(Tier-A 유예)** 유지. PostgreSQL 재시작, `archive_mode` 변경, compose `up`, volume 생성·권한 변경, 보관 삭제는 0건이다.

`tools/pitr_opt_in_dry_run.py`를 추가해 `pitr_readiness`의 live read-only 설정 관측과 `pitr_archive_retention`의 filesystem 계획을 단일 JSON에 결속했다. 결과는 `postgresRestarted/postgresSettingsChanged/composeApplied/retentionApplied=false`, `pitrVerified/ac12Satisfied=false`를 항상 기록한다. `--require-possible`은 설정 전제만 검사하며 복구 인수가 아니다.

계약·운영 경계는 [[S08-DB_PITR_opt-in_dry-run과_AC-12_복구드릴_초안]]에 고정했다. 외부 `wal_archive`는 uid/gid 70·mode 0700 → deployment secret 환경에서 compose config exit 0 → 적용 후 일반 readiness `possible`의 3단계다. 기존 결정 문서의 “`--require-pitr` = possible” 표현은 실제 CLI 계약상 틀리므로 사용하지 않는다. `--require-pitr`는 실제 복구 evidence가 없으면 의도적으로 exit 1이다.

## 실행 증거

| 명령/관측 | 결과 |
|---|---|
| 실 PG `INV_TEST_ADMIN_DSN`을 `INV_PITR_DSN`으로만 전달해 통합 dry-run, 빈 합성 archive/backups | exit 0, `readiness=absent`, `archive_mode=off`, `wal_level=replica`, 삭제 후보 0, mutation 0, AC-12 false. [[2026-09-23_dev-pg-dry-run.json]] |
| `.venv\\Scripts\\python.exe -m pytest -q tests/test_pitr_opt_in_dry_run.py tests/test_pitr_readiness.py tests/test_pitr_archive_retention.py` (landed SHA, 실 PG env) | **23 passed / 0 skipped / 0 failed**, exit 0 |
| 같은 시험(일반 게이트 env) | 22 passed / 1 explicit skip(`INV_TEST_ADMIN_DSN` absent), exit 0. skip을 실 PG 통과로 세지 않고 위 23건 실행을 별도 고정했다. |
| `docker compose -f docker-compose.prod.yml -f docker-compose.pitr.yml config --quiet` (비밀 없는 config-only placeholder 10개) | exit 0. container/volume 생성·restart 없음 |
| `python tools/check_docs.py` | 844 documents, exit 0 |
| `python tools/check_contract_bindings.py` | 54 fixtures / 19 types / 25 anchor sites / 14 replay guards, exit 0 |
| `python tools/check_frontend_integrity.py` | 83 files / 9 rules / 0 violations, exit 0 |
| `python tools/check_ontology.py` | 48 task mappings, exit 0 |
| `python tools/check_doc_single_source.py --ratchet` | 18 pairs, 신규 중복 0, exit 0 |
| `python tools/check_response_freshness.py` | advisory 10/10, exit 0 |
| `pytest -q tests/test_route_coverage.py` | 39 passed, exit 0 |
| `git diff --check` / `sync_obsidian.py --check` | exit 0 / 1675 managed·2 pending·0 conflict, write 0 |

추가 lint로 `python -m ruff`를 시도했으나 이 venv에는 ruff가 없어 `No module named ruff`/exit 1이었다. ruff는 저장소 필수 게이트가 아니며 `py_compile`은 exit 0이다. 이 실패를 통과로 세지 않는다.

## hosted CI와 판정

implementation SHA에서 다섯 workflow가 생성됐다. 기록 시점 Documentation `35755309689`, Frontend `35755309641`, Desktop Browser `35755309576`은 success이고 Backend `35755309701`은 in progress, Core `35755309438`은 pending이다. 미완료 run을 통과로 세지 않는다.

현재 카드는 dry-run 도구와 적용 전 절차 초안만 닫는다. 실제 외부 볼륨, WAL 전달, 물리 target-time restore, RPO `≤15분`, RTO `≤1시간`, recovery epoch/fencing 후 안전 쓰기, off-device/5노드 증거는 모두 미실행·미측정이다. S08-DB는 `review`를 유지한다.

## 다음 행동

1. Claude: `50d5ebc4`의 무삭제·비밀 비노출·허위 AC-12 성공 차단과 드릴 판정식을 독립 검토한다.
2. 코디네이터/운영자: 결정 B를 변경할 때만 재시작 창과 외부 volume owner를 지정한다.
3. 활성 후 담당: 3단계 preflight와 readiness `possible`을 확보한 뒤 AC-12 격리 복구 드릴을 실행하고 JSON/JUnit/log를 reviewer에게 인계한다.
