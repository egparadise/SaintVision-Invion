---
doc_id: "HIST-CLAUDE-2026-09-28-S12-DB-AC12-EVIDENCE-COLLECTOR"
title: "S12-DB AC-12 acceptance Evidence collector — 설계 1쪽 + collector + PG-free 자기 시험 111 passed (기존 operational_readiness·pitr_readiness·pitr_opt_in_dry_run·browser proof 재사용, 판정 복제 없음, 카드 aq)"
version: "1.2.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T10:23:47+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S12-DB"]
tags: ["S12-DB", "AC-12", "evidence", "collector", "claude"]
---

# S12-DB AC-12 acceptance Evidence collector (2026-09-28, 카드 aq)

설계 [[S12-DB AC-12 acceptance Evidence collector 설계]]. #127(S10)·#131(S09)과 같은 형식이되 시험을 돌리는 대신 **기존 인수 도구의 출력을 읽는다**.

## 1. 만든 것

| 파일 | 내용 |
|---|---|
| `tools/collect_s12_acceptance_evidence.py` | `operational_readiness.py --acceptance-evidence [--release] --json`(권한·offer·admission + `pilot_readiness` catalog: `acceptanceAssessed`·`catalogComplete`·`blockers`), `pitr_readiness.py --json`, `pitr_opt_in_dry_run.py`, desktop-browser proof를 subprocess/파일로 읽어 AC-12 항목 13 + 외부 4를 PASS/FAIL/NOT_OBSERVED/BLOCKED_EXTERNAL로 분류. 판정 논리 복제 0(SQL·설정 평가·drill 규칙 없음, 시험이 소스로 고정). 미관측 = NOT_OBSERVED+reason(0·PASS 아님), 사용자 입력·외부 = BLOCKED_EXTERNAL+reason·value null. verdict FAIL 우선 → NOT_OBSERVED(exit 3) → PASS_MEASURED_PARTIAL(exit 0; 외부 4건 때문에 PASS 불가). provenance repo 루트·dirty 기본 거부·label 시각·기존 파일 거부·`<outside-repo>` placeholder. redaction: 명령행 값(모양 무관)·UUID·prefix 비의존 ULID·disposable·host:port, 이 실행의 DSN env 비밀 guard. `acceptanceClaim=false` |
| `tests/test_collect_s12_acceptance_evidence.py` | PG-free **147 passed**(설계 §4 목록 + §1b 되살림 22 + §1c 13) + postgres 마커 1(hosted Backend: 마이그레이션된 disposable DB·새 tenant에 실제 세 도구 실행 → readiness complete, backup·drill FAIL, release BLOCKED_EXTERNAL, 리허설·web NOT_OBSERVED, verdict FAIL, DSN·tenant 미포함) |

## 1b. Codex 검토 4건 반영(#153 코멘트, 10:12 KST)

F1 구조화 값 redaction + raw/escaped 검사(부정 시험 7 + walker 1), F2 미분류 blocker → NOT_OBSERVED·자기모순 catalog → FAIL(되살림 4 + pilot_readiness blocker 전수 분류 시험), F3 `browserOptIn` 필수·codeSha 결속(`--web-smoke-sha`/proof `codeSha`, 되살림 1 + 결속 6), F4 remote 도달성(`--reachable-ref` ancestry 또는 remote containment, `--allow-unpushed-head` 기록; 되살림 3). PG-free **134 passed**. hosted Backend(head 30f5ca83) run 36364528281: 3041 passed / 47 skipped / 0 failed = base 2929 + 112(PG-free 111 + **postgres 케이스 1 실행**), skip 분포 base와 동일(47). 수정 head의 run은 PR 코멘트. 실PG 시험은 hosted 병합 head가 remote ref에 없을 수 있어 `--allow-unpushed-head`를 **기록하며** 넘긴다(숨기지 않음).

## 1c. Codex 재검토 잔여 2건 반영(head 663aad65 → 다음 head)

F3' `sha_binding` 소문자 hex 12~40 + 접두 일치(부정 시험: 1자·11자·비hex·41자·다른 40자·대문자 정규화·번들 sha 검증), F4' `resolve_remote_tracking_ref`(HEAD·local·tag·refs/heads·미설정 remote 거부, `ls-remote` stale 구분, invalid-ref는 opt-out으로도 불가; 시험 3). PG-free **147 passed**.

## 2. 검증·경계

PG-free 111 passed / 1 postgres skipped(로컬 DSN 없음). 실 PG·Docker·전체 suite 로컬 미실행(메모리); hosted Backend run id는 PR 코멘트. 게이트 check_docs·single_source·ontology 2·bindings·freshness·export_schemas --check·diff --check exit 0. 공개 계약·registry·ontology·migration 변경 0. worktree 재사용(새 worktree 없음). 실 evidence 파일은 사용자가 파일럿 tenant/release/PITR 경로/browser proof를 지정해 실행할 때 생긴다. 다음 첫 행동: Codex 검토 → hosted 결과 → 파일럿 실행은 코디네이터 결정.
