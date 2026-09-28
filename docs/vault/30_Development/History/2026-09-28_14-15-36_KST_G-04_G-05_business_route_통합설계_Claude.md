---
doc_id: "HIST-CLAUDE-2026-09-28-G04-G05-BUSINESS-ROUTES-DESIGN"
title: "G-04·G-05 남은 business lane route 통합 설계 v1.0 (docs-only) — 7 route 등급·정본 오류·IDEM·tx/lock·Codex 계약 지점(seal·pin)·eval suite project 결속 migration 번호 요청·계약/FE·PR 분할 8 (카드 58)"
version: "1.2.2"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-28T17:29:11+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1e8baf04"
task_ids: ["S09-BE", "S10-BE"]
tags: ["G-04", "G-05", "design", "claude"]
---

# G-04·G-05 통합 설계 (2026-09-28, 카드 58)

설계 본문: [[G-04_G-05 business lane route 통합 설계 v1.0]]. 요지:

- 재사용 표(§1): #174 index `ix_dataset_versions_tenant_id_content_sha256`, #175 `lineage_query.py` helper(`_membership`·`_version_in_project`·`TRANSLATION`·cursor), #167 `model_release.py`(`_require_approval` canApprove·`_locked_version`·`_rebind_identity`)와 `api/problem.py`, 서비스 함수 7(변경 0), 멱등 원장 `idempotency_records` + `deps.replay_or_reserve`, `adapter_for`.
- 등급(§2): 읽기 3 = membership(#158 §6), 쓰기 5 = canApprove(#152 §3의 승격류 확장; 코디네이터 승인 요청). project 결속은 부모 join(run→workload·model); **eval suite는 결속 불가**.
- 정본 오류·strict·path→row·404(§3): 새 code 0. IDEM 5 규칙(§4).
- tx/lock(§5): W4 pin 경합·W1 seal 동시 봉인/TOCTOU는 **Codex 계약 지점**으로 표시, 구현 보류. **W5는 migration 필요**(`eval_suites.project_id`) → 번호 요청(0051까지 배정).
- 계약/FE(§6): Strict 파생 → `export_schemas`; 화면 없음(Gemini 인계). 부정 시험 목록(§7), PR 분할 8(§8).

docs-only. 게이트 통과. owner Claude / reviewer Codex / 병합 금지.

## v1.1 (2026-09-28T14:22:04+09:00) — 코디네이터 결정 반영

W5 migration **0052** 예약(down 0051, #176 위 stack); W1~W5 canApprove 통일 잠정 승인(최종은 Codex 설계 검토, W5 충분성·W1/W4 경합 계약과 함께). PR 1(R1 + `_run_in_project`)은 #175 위 draft로 선착수, W1·W4는 Codex 계약 전 착수 금지.

## v1.2 (2026-09-28T15:11:46+09:00) — Codex 설계 판정 F1~F4 고정

F1 등급: W2·W4·W5 canApprove 최종, W1은 필요조건 + integrity 값 서버 파생, **W3 보류**(trusted-worker 측정 seam 전). F2 W1 seal 계약(§5-2: READ COMMITTED+명시 잠금, 6단계, canonical intent 비교 멱등/409, IntegrityError 500 금지, lock timeout SYS-0001/503, 시험 a~d). F3 W4 계약(§5-3: 직렬화 → canApprove → parent → ModelVersion 한 행 FOR UPDATE → 재확인 → max → ledger; release/W3 같은 `_locked_version`; 역순·verify↔pin·release↔pin·shorter 시험). F4 IDEM-6: helper는 예약 없음 → advisory lock 직렬화점을 resource row보다 앞에, unique violation 비정상. PR 순서: W3 보류, W1·W4 계약 고정으로 착수 가능.

## v1.2.1 (2026-09-28T15:16:34+09:00) — Codex 조건부 승인 조건 반영

W1 문구 모순 정리: 봉인 artifact 집합은 **서버가 run 정본에서 완전하게 파생**(active + checksum 있는 행 전부), request는 role 매핑만(누락·추가 불가, 미매핑은 `other`, 집합 밖 매핑은 409), canonical intent도 서버 파생 집합 기준. §9의 옛 '잠정 승인'·'착수 금지' 문장을 최종 상태(W2·W4·W5 확정, W4 해제, W1 조건 충족, W3 보류)로 교체. 추가 설계 라운드 없음.

## v1.2.2 (2026-09-28T17:29:11+09:00) — W5 migration 번호 0052 → 0053 (코디네이터 #191 결정)

§5-1·§9의 W5 migration 번호를 `0053`(`down_revision = 0052_model_version_digest_scope`, #197)으로 정정. 0052는 #191 F1 유일성 migration. 문구만; 설계 내용 변경 없음. 선행 migration PR은 `agent/claude/g04-w5-migration-0053`.
