---
doc_id: "HIST-CLAUDE-2026-09-28-S10-DB-AC10-EVIDENCE-COLLECTOR"
title: "S10-DB/ST AC-10 acceptance Evidence collector — 설계 1쪽 + collector + PG-free 자기 시험 32 passed (실 PG 단일 invocation은 가용 메모리 ≥1.5GB 조건 미충족으로 보류)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T07:15:00+09:00"
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
| `tools/collect_s10_acceptance_evidence.py` | 14파일을 **파일 하나당 pytest 프로세스 하나**(PG-free core 3파일만 한 프로세스)로 JUnit 실행 → 36 케이스를 AC-10 5조항(계보 역추적 8 · 모델 버전 append-only 6 · 보존 pin/release gate 8 · 배포 digest/승인 12 · tenant 격리 2)에 매핑 → redacted JSON+MD. **fail-closed**: 어떤 suite든 failed/error·exit≠0·status≠complete → FAIL(매핑 밖 실패 포함); 조항 pass는 매핑 케이스 전부 passed일 때만. **provenance**: `tools.provenance.collect` + collector sha256, `--require-clean-head`(dirty면 exit 2), label에 sha12(이전 산출물 미덮어쓰기). **redaction**: DSN/password 거부, disposable DB 이름·UUID·커널 ULID(`mdl_/mv_/dep_/ds_/img_/cmt_/run_/evd_/nod_/prj_/res_/tnt_/lse_`)·IPv4:port placeholder, `--note` 동일 치환, 실패 문구 미보존. 외부 대기 CX-02 Provider·MLflow = UNMEASURED·값 없음. `acceptanceClaim=false`. exit 0/1/2/3 |
| `tests/test_collect_s10_acceptance_evidence.py` | PG-free **32 passed**: 매핑 36 케이스 실재·유일(AST, BOM 허용), 14파일 커버·postgres 파일당 1프로세스, JUnit worst-outcome·실패 문구 미보존, 조항 규칙 4, verdict 표 5, 되살림(매핑 밖 실패 1 → FAIL)·incomplete suite 2, 외부 대기 값 없음, sanitizer 부정 시험 12 패턴, git sha/count 보존, 비밀 guard, stale 삭제·dirty head 거부, stub end-to-end(note 치환). postgres 1(전체 파이프라인; 로컬 skip, CI fail, hosted Backend 수집) |

## 2. 실 PG — 보류(정직)

코디네이터 규칙 "가용 메모리 ≥1.5GB일 때만 실 PG"에 대해 이 시점 가용 메모리는 **547MB**였다. 따라서 실 PG 단일 invocation(14 프로세스 순차, 이전 실측 225s)은 **미실행**이며 Evidence 파일도 없다. 실행 조건이 되면 커밋된 clean head에서 `python tools/collect_s10_acceptance_evidence.py --require-clean-head --executor Claude` 1회 → `Evidence/s10-db-acceptance/s10-acceptance-<sha12>-<utc>.{json,md}` 생성 후 이 페이지 v1.1로 결과를 붙인다. 전체 suite·브라우저·Docker 기동 없음.

## 3. 게이트·경계

check_docs·ratchet·ontology·diff --check exit 0(PR 본문). 공개 계약·registry·ontology 변경 0. S10-DB/S10-ST는 `planned` 유지(인수 판정은 실 PG evidence + Codex 검토 뒤). 다음 첫 행동: Codex 설계·코드 검토 → 메모리 조건 충족 시 실 PG 1회 → History v1.1·검증지도 갱신.
