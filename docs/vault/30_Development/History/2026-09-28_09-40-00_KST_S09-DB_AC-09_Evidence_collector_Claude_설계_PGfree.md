---
doc_id: "HIST-CLAUDE-2026-09-28-S09-DB-AC09-EVIDENCE-COLLECTOR"
title: "S09-DB/ST AC-09 acceptance Evidence collector — 설계 1쪽 + collector + PG-free 자기 시험 98 passed (실 PG 단일 invocation은 가용 메모리 ≥1.5GB 조건 미충족으로 UNMEASURED, hosted Backend self-test 근거)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T09:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S09-DB", "S09-ST"]
tags: ["S09-DB", "S09-ST", "AC-09", "evidence", "collector", "context", "runrecord", "eval", "claude"]
---

# S09-DB/ST AC-09 acceptance Evidence collector (2026-09-28, 카드 ww)

근거: [[2026-09-22_계보모델불변_컨텍스트eval_교차증거_실PG_S09_S10_Claude]]의 S09 세트(76 passed / 21 skipped, 5파일, `5f0b4cd2`; skip 21 = Linux 사설 스토리지 게이트). 설계 [[S09-DB AC-09 acceptance Evidence collector 설계]]. #127 S10 collector와 같은 형태이며 #120·#121·#127에서 Codex가 잡은 결함 부류 (a)~(g)를 처음부터 적용했다.

## 1. 만든 것

| 파일 | 내용 |
|---|---|
| `tools/collect_s09_acceptance_evidence.py` | 5파일을 **파일 하나당 pytest 프로세스 하나**로 JUnit 실행 → 73 케이스(5파일 test **전수**)를 AC-09 8조항(불변 Context 10 · RunRecord 봉인 4 · eval golden gate 8 · eval executor 적합성 14 · Artifact 역할 pin 3 · tenant 격리 2 · 제한된 승인 루프 18 · RunRecord 완료 파이프라인 14[Linux 게이트])에 매핑 → redacted JSON+MD. **(a)** 어떤 suite든 failed/error·exit≠0·status≠complete → FAIL, 검사 순서 fail-closed 먼저(failed+unavailable = FAIL). **(b)** unavailable suite `counts=null`·totals는 관측분만, 조항 not_run은 항상 reason; 게이트 사유는 suite 완주·실행 0·전부 skipped일 때만(missing 1건이면 일반 not_run). **(c)** dirty 기본 거부·`--allow-dirty-tree` 기록, provenance repo 루트 cwd + collector sha256. **(d)** label `<sha12>-<UTC 시각>`, 기존 파일 있으면 삭제 없이 exit 2. **(e)** prefix 무관 ULID·UUID·disposable·host:port 치환, `--note` 동일. **(f)** `evidence_ref()` placeholder. 외부 대기 4(AC-09 세 지표·CX-02) UNMEASURED·값 없음. `acceptanceClaim=false`. verdict PASS / PASS_MEASURED_PARTIAL(게이트 not_run만 남을 때, `passScope`) / FAIL / UNAVAILABLE / NOT_RUN, exit 0/0/1/2/3 |
| `tests/test_collect_s09_acceptance_evidence.py` | PG-free **98 passed**: 매핑 = 5파일 test 전체(AST)·유일·파일당 1프로세스, 게이트 파일의 skipif 선언 ↔ collector 게이트명, JUnit worst-outcome·실패 문구 미보존, 조항 규칙 5(reason), 게이트 사유 조건 3, verdict 표 9, PASS_MEASURED_PARTIAL 범위·게이트 suite skipped 14 보존(pass도 0도 아님), 되살림(매핑 밖 실패 → FAIL), incomplete 2, failed>unavailable 양방향+not_run 안 error, unavailable=null, 외부 대기 값 없음, sanitizer 부정 시험 6+prefix 전수(core ∪ kernel 21), S09 prefix ⊂ core, sha/count/case명 보존, 비밀 guard, evidence_ref placeholder, 기존 산출물 거부·미삭제, dirty 기본 거부·opt-out 기록, DSN 없음 → 미기록, label 형식, repo 루트 provenance, stub end-to-end(게이트 호스트). postgres 1(전체 파이프라인; 로컬 skip, CI fail, hosted Backend 수집 — ubuntu라 test_results.py도 실행) |

## 2. 실 PG — UNMEASURED(정직)

코디네이터 규칙 "가용 메모리 ≥1.5GB일 때만 실 PG"에 대해 이 시점 가용 메모리는 **약 1.0GB**였다. 따라서 실 PG 단일 invocation(5 프로세스 순차, 이전 실측 110.88s)은 **미실행**이며 로컬 Evidence 파일은 없다(UNMEASURED). 근거는 hosted Backend의 postgres 마커 1건(`test_real_pg_collector_bundle`: collector 전체 파이프라인 1회, verdict-exit 일치·acceptanceClaim=false·DSN 미포함 단언; PR 본문에 run id)이다. 조건이 되면 커밋된 clean head에서 `python tools/collect_s09_acceptance_evidence.py --executor Claude` 1회 → `Evidence/s09-db-acceptance/s09-acceptance-<sha12>-<utc>.{json,md}` 생성 후 이 페이지 v1.1로 결과를 붙인다(이 Windows PC에서는 `runrecord-completion-pipeline`이 게이트 not_run → 기대 verdict PASS_MEASURED_PARTIAL). 전체 suite·브라우저·Docker 기동 없음.

## 3. 게이트·경계

check_docs·single_source·ontology 2·bindings·freshness·export_schemas --check·diff --check exit 0(PR 본문). 공개 계약·registry·ontology 변경 0. S09-DB/S09-ST는 `planned` 유지(인수 판정은 실 PG evidence + Codex 검토 뒤). AC-09 제품 지표 3건은 이 collector 밖(S09-BE/FE). 다음 첫 행동: Codex 설계·코드 검토 → 메모리 조건 충족 시 실 PG 1회 → History v1.1·검증지도 갱신.
