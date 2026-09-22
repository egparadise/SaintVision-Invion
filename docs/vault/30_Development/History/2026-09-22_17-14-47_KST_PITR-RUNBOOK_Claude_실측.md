---
doc_id: "CLAUDE-NEWPC-PITR-RUNBOOK-MEASURE-001"
title: "VF-CL-04 PITR runbook 새 PC 실측 — dev-pg readiness=absent(비파괴) + 물리 PITR 리허설 6회(정상 PASS·결함주입 5 FAIL·잔재 0), 보관 주기 7일(파일럿)"
version: "1.0.0"
status: "evidence-contributed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T17:14:47+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "d01c931a"
impl_sha: "(문서 전용 — 코드 변경 없음)"
tags: ["pitr", "runbook", "vf-cl-04", "new-pc", "operations", "claude"]
---

# VF-CL-04 PITR runbook 실측 (2026-09-22, 17:14 KST)

[[VF-CL-04 replica 복구와 PITR 운영 runbook]] §4(readiness)와 PITR-R2-01/02(물리 리허설·엄격 게이트·owned cleanup)를 **새 PC에서 비파괴로 실측**했다. 원칙: 개발 PG 컨테이너 `saintvision-invion-dev-pg`는 **읽기 전용 + disposable DB 생성/삭제만**(설정·재시작·원본 DB 변경 없음). 물리 리허설은 코디네이터 승인(ask 회신) 하에 `tools/pitr_rehearsal.sh`가 만드는 **owned-label 일회용 probe**(postgres:16-alpine, tmpfs 512MB, 종료 시 자동 제거)로 수행 — dev-pg 미접촉, probe 동시 1개, 다른 대형 시험과 겹치지 않게 순차. 측정 트리 `D:\Project\sv-measure-claude`, SHA `d01c931a`, clean.

## 1. readiness — dev-pg (비파괴)

- 절차: admin DSN으로 `CREATE DATABASE pitr_probe_69597f98a888` → `INV_PITR_DSN`을 그 DB로 지정 → `python tools/pitr_readiness.py --dsn-env INV_PITR_DSN --json` / `--require-pitr` → `DROP DATABASE`. 컨테이너·설정·`invdev` 무변경(readiness는 `pg_settings` 읽기만).
- 결과: **verdict `absent`**, exit 2(json) · **`--require-pitr` exit 1**. settings: `archive_mode=off`, `archive_command=disabled`, `archive_library=unset`, `wal_level=replica`. `pitrVerified:false`, `requiresEvidence=[base-backup, continuous-archived-wal, target-time-recovery, retention-and-media]`.
- 해석: 이 PC의 개발 PG는 **PITR 불가(설정 부재)** — runbook §4 "기본 배포(archive_mode off)는 absent" 그대로. RPO는 논리 dump 주기. 도구 판정이 실 클러스터에서 옳게 나온다는 실측이지, 복구 능력 증명이 아니다(runbook Codex 정정 문단과 일치). 증거: `.work/evidence-claude-d01c931a/pitr_readiness_devpg.json`.

## 2. 물리 PITR 리허설 — owned probe (runbook 절차의 실행 증명)

`tools/pitr_rehearsal.sh`를 FAULT 없음 1회 + 결함 주입 5회, 순차 실행(17:12:30~17:14:47, 2m17s). 각 실행 후 `docker ps -aq --filter label=ai.saintvision.pitr-rehearsal.run` = **0**(R2-02 owned cleanup, 6회 모두 잔재 0). 종료 후 dev-pg 컨테이너 상태 Up 유지 확인.

| 실행 | exit | 소요 | 게이트가 잡은 것 |
|---|---|---|---|
| normal | **0 PASS** | 21s | archive_mode=on·archive_timeout=300·wal_level=replica → base backup → before INSERT → T1=`2026-09-22 08:12:39.326474+00` → after INSERT(source에 확인) → 별도 클러스터(5433) 복원 → **promote** → `restoredRows=[before]`(after 제외). `INNER-PASS` |
| before-insert | 1 FAIL | 11s | `ASSERT-FAIL: 'before' not committed in source` |
| after-insert | 1 FAIL | 14s | `ASSERT-FAIL: 'after' is not present in the SOURCE -> an exclusion result would be vacuous` |
| basebackup | 1 FAIL | 5s | `pg_basebackup: error: could not create directory "/proc/nonexistent"` (set -e) |
| restore-start | 1 FAIL | 17s | 잘못된 port → `pg_ctl start` 실패(ON_ERROR_STOP/set -e) |
| promotion | 1 FAIL | 65s | `recovery_target_action=pause` → `ASSERT-FAIL: restore did not promote / target time not reached (state=t)` |

옛 PC 증거(`Evidence/pitr-rehearsal/2026-09-19_physical-pitr-rehearsal.txt`)와 **같은 매트릭스, 같은 판정**(정상만 PASS, 결함 5종은 각기 다른 게이트로 FAIL). 새 PC Docker에서 재현됨 = 절차가 환경을 넘어 성립. 증거: `Evidence/pitr-rehearsal/2026-09-22_newpc_physical-pitr-rehearsal.txt`, 로그 `.work/evidence-claude-d01c931a/pitr_*.log`.

## 3. 보관 주기 결정 (코디네이터 `ask` 회신, 사용자 위임)

- **WAL 아카이브·base backup 보관 주기 = 7일** — 5대 PC 파일럿 단계 값. **운영 전환 시 운영자가 재결정**한다(이 값은 파일럿 한정이며 AC-12 인수값이 아니다).
- 적용 위치(문서만, 미활성): `docker-compose.pitr.yml`은 opt-in이며 이 PC에선 **적용하지 않았다**(dev-pg 재시작 금지). 활성 시 필요한 것 = 외부 `wal_archive` 볼륨(uid 70, 0700) 사전 준비 + 7일 초과 세그먼트/베이스백업 정리 절차(미작성) + 활성 후 복구 drill로 실 RPO 측정. runbook 갱신은 §4에 "파일럿 보관 7일(운영 재결정)" 한 줄 — 별도 커밋(runbook status가 review라 Codex 검토 대상).

## 4. 하지 않은 것 (정직)
- dev-pg에 archive 설정 적용·재시작 없음(금지 조건). 따라서 **이 PC 개발 DB의 PITR은 여전히 absent**이며 리허설 PASS는 "절차가 성립한다"이지 "dev-pg가 복구 가능하다"가 아니다.
- 별도 장애 도메인(오프호스트 아카이브, Tier B)·보관 매체·7일 정리 자동화는 미실측.

## 다음 첫 행동 / 담당
- Claude: runbook §4에 보관 주기 문구 반영(작은 문서 수정, 다음 사이클) · 이 페이지·Evidence 착지.
- 운영자/사용자: Tier-A 활성 여부(compose override 적용은 재시작 수반) 결정. Codex: 검토.
