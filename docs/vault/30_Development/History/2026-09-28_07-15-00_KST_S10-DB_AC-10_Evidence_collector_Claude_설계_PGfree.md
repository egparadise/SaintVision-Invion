---
doc_id: "HIST-CLAUDE-2026-09-28-S10-DB-AC10-EVIDENCE-COLLECTOR"
title: "S10-DB/ST AC-10 acceptance Evidence collector — 설계 1쪽 + collector + PG-free 자기 시험 32 passed (실 PG 단일 invocation은 가용 메모리 ≥1.5GB 조건 미충족으로 보류)"
version: "1.1.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T08:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S10-DB", "S10-ST"]
tags: ["S10-DB", "S10-ST", "AC-10", "evidence", "collector", "lineage", "model-registry", "claude"]
---

# S10-DB/ST AC-10 acceptance Evidence collector (2026-09-28, 카드 ss)

근거: [[2026-09-22_계보모델불변_컨텍스트eval_교차증거_실PG_S09_S10_Claude]]의 S10 실 PG 세트(228 passed, 14파일, `f0f0c790`). 설계 [[S10-DB AC-10 acceptance Evidence collector 설계]]. #120 S02 collector와 같은 형태이며 Codex가 #120에서 잡은 세 가지를 처음부터 적용했다.

## 1. 만든 것

| 파일 | 내용 |
|---|---|
| `tools/collect_s10_acceptance_evidence.py` | 14파일을 **파일 하나당 pytest 프로세스 하나**(PG-free core 3파일만 한 프로세스)로 JUnit 실행 → 36 케이스를 AC-10 5조항(계보 역추적 8 · 모델 버전 append-only 6 · 보존 pin/release gate 8 · 배포 digest/승인 12 · tenant 격리 2)에 매핑 → redacted JSON+MD. **fail-closed**: 어떤 suite든 failed/error·exit≠0·status≠complete → FAIL(매핑 밖 실패 포함); 조항 pass는 매핑 케이스 전부 passed일 때만. **provenance**: `tools.provenance.collect` + collector sha256, repo 루트 cwd로 계산, dirty tree 기본 거부(exit 2)·`--allow-dirty-tree`는 기록되는 opt-out, label `<sha12>-<UTC 시각>`이고 같은 label 산출물이 있으면 거부(삭제·덮어쓰기 없음). **redaction**: DSN/password 거부, disposable DB 이름·UUID·커널 ULID(실제 S10 prefix `dst_/dsv_/cmt_/img_/mdl_/mdv_/dpl_` + `apv_/usr_/wsp_/wkl_/evs_/evr_` + 커널 `run_/evd_/nod_/prj_/res_/lse_` 등 **prefix 무관 `<3~4 소문자>_<Crockford ULID 26>` 전부**(`saintvision.ids.PREFIXES` 값 전수 + 커널 prefix 세트로 부정 시험))·IPv4:port placeholder, `--note` 동일 치환, 실패 문구 미보존. 외부 대기 CX-02 Provider·MLflow = UNMEASURED·값 없음. `acceptanceClaim=false`. exit 0/1/2/3 |
| `tests/test_collect_s10_acceptance_evidence.py` | PG-free **84 passed**(v1.1; 초판 32): 매핑 36 케이스 실재·유일(AST, BOM 허용), 14파일 커버·postgres 파일당 1프로세스, JUnit worst-outcome·실패 문구 미보존, 조항 규칙 4, verdict 표 5, 되살림(매핑 밖 실패 1 → FAIL)·incomplete suite 2, 외부 대기 값 없음, sanitizer 부정 시험 5 + prefix 전수(core 44 ∪ kernel 21), failed+unavailable → FAIL, 기존 산출물 거부·미삭제, dirty 기본 거부·opt-out 기록, label 시각 형식, repo 루트 provenance, git sha/count 보존, 비밀 guard, stub end-to-end(note 치환). postgres 1(전체 파이프라인; 로컬 skip, CI fail, hosted Backend 수집) |

## 2. 실 PG — 보류(정직)

코디네이터 규칙 "가용 메모리 ≥1.5GB일 때만 실 PG"에 대해 이 시점 가용 메모리는 **547MB**였다. 따라서 실 PG 단일 invocation(14 프로세스 순차, 이전 실측 225s)은 **미실행**이며 Evidence 파일도 없다. 실행 조건이 되면 커밋된 clean head에서 `python tools/collect_s10_acceptance_evidence.py --executor Claude`(clean head 기본 강제) 1회 → `Evidence/s10-db-acceptance/s10-acceptance-<sha12>-<utc>.{json,md}` 생성 후 이 페이지 v1.1로 결과를 붙인다. 전체 suite·브라우저·Docker 기동 없음.

## 2b. Codex 1차 검토(#127) 4건 반영 (v1.1)

| # | 지적 | 반영 |
|---|---|---|
| 1 | sanitizer가 실제 S10 prefix(mdv/dpl/dst/dsv/apv/usr/wsp/wkl/evs/evr)를 놓치고 문서는 존재하지 않는 mv/dep/ds를 적음 | `src/saintvision/ids.py` `PREFIXES`와 커널 `inv.ids.new_id` 형식(3~4 소문자 + Crockford 26)에서 전수 확인 → 정규식을 prefix 무관 `\b[a-z]{3,4}_[0-9A-HJKMNP-TV-Z]{26}\b`로 교체, `PREFIXES.values()` 전수 + 커널 prefix 21개를 parametrize한 부정 시험. 문서 정정 |
| 2 | clean head가 opt-in, provenance가 cwd 의존 | dirty 기본 거부 + `--allow-dirty-tree`(기록) / `collect_provenance_at_repo_root` |
| 3 | 같은 날 재실행이 이전 산출물을 덮어씀 | label에 UTC 시각, 기존 파일 있으면 exit 2·미삭제(`remove_stale_outputs` 제거) |
| 4 | failed+unavailable → UNAVAILABLE | fail-closed 검사를 먼저 수행, `test_failed_outranks_unavailable` |

같은 (2)~(4) 패턴이 #120(S02)·#121(S03)에도 있어 동일하게 고쳤다(S03은 (1)의 prefix 무관 정규식도 적용). S02 30 passed / S03 96 passed.

## 3. 게이트·경계

check_docs·ratchet·ontology·diff --check exit 0(PR 본문). 공개 계약·registry·ontology 변경 0. S10-DB/S10-ST는 `planned` 유지(인수 판정은 실 PG evidence + Codex 검토 뒤). 다음 첫 행동: Codex 설계·코드 검토 → 메모리 조건 충족 시 실 PG 1회 → History v1.1·검증지도 갱신.
