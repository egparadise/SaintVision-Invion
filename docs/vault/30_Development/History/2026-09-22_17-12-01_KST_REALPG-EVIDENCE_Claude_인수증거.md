---
doc_id: "CLAUDE-NEWPC-REALPG-EVIDENCE-001"
title: "새 PC 실 PG 인수 증거 재실행 — S02·S03·S09·S10·S04/05 경합·S07 복구 762 passed / 88 skipped / 0 failed (SHA d01c931a)"
version: "1.0.0"
status: "evidence-contributed"
author: "Claude (evidence contributor)"
reviewer: "Codex"
feeds_tasks: "S02-DB/BE/ST · S03-DB · S09-DB/ST · S10-DB/ST/BE · S04-DB/BE · S05-DB/BE · S07-DB/BE (owner Codex; self-close 아님)"
updated: "2026-09-22T17:12:01+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "d01c931a"
impl_sha: "(문서 전용 — 코드 변경 없음)"
tags: ["real-pg", "evidence", "new-pc", "S02", "S03", "S09", "S10", "S04", "S05", "S07", "claude"]
---

# 새 PC 실 PG 인수 증거 재실행 (2026-09-22, 17:12 KST)

옛 PC에서 일회용 PG 컨테이너로 만든 인수 증거(S02 `a8c979d0`·S03·S09/S10 `f0f0c790/5f0b4cd2`·경합/복구 `9f43c59d`)를 **새 PC의 실 PostgreSQL로 같은 파일 집합을 재실행**해 재사용 가능한 증거로 갱신했다. provenance: **SHA `d01c931acf2127377a7cdc665ef3eee5f0402fe9`**, Claude 전용 detached 측정 워크트리 `D:\Project\sv-measure-claude`, `git status --porcelain` 시작·종료 모두 **0줄(working_tree_clean=YES)**, 인터프리터 `.venv\Scripts\python`(3.14.7, pytest 9.1.1), DB `saintvision-invion-dev-pg`(PG 16.15, 127.0.0.1:55432, disposable DB만). 실행 스크립트는 덩어리마다 `pytest -q --strict-markers -p no:cacheprovider -rs --junitxml`, 순차(동시 실행 0), `CI` 미설정. 총 소요 9분 21초(17:02:40~17:12:01).

## 결과 (skip은 통과로 세지 않는다)

| 세트 | 파일 | passed | skipped | failed | exit | 소요 | 옛 PC 증거 대비 |
|---|---|---|---|---|---|---|---|
| S02 (Node 등록·인증실패·제공폴더 카탈로그) | test_api · test_storage_api · test_storage_catalog · core/test_storage_list_response_contract · core/test_storage_observation_contract · test_node_auth · core/test_node_page_detail_response_contract | **91** | 0 | 0 | 0 | 86s | 91 = 동일 |
| S03-DB (Workspace·Workload·Run·Evidence) | test_run_state · core/test_run_{result,attempt,log,approval_observation}_contract · core/test_run_state_alignment · core/test_workspace_{api_boundary,response_contract,manifest} · test_execution · test_execution_readiness · test_vf_evidence · test_evidence_case_inventories | **201** | 0 | 0 | 0 | 52s | 192 → 201 (+9: 그 사이 착지한 시험, 회귀 아님) |
| S09 (불변 Context·RunRecord 봉인·eval) | test_context_eval · test_eval_execution · integration/test_approvals · integration/test_approval_review · integration/test_results | **76** | 21 | 0 | 0 | 92s | 76/21 = 동일 |
| S10 (계보·모델 불변·배포 digest) | test_lineage · test_model_registry · test_deployment_guard · integration/test_model_{commit,registry_binding,registry_revalidation,locality,view,runtime,retry,license_readthrough} · core/test_model_{manifest,execution_registry,remote} | **228** | 0 | 0 | 0 | 216s | 228/0 = 동일 |
| S04/S05 경합 (승인 idempotency·lease/예약 abort·provisioning 충돌·PG 경합·자격증명 발급 경합) | integration/test_approvals · test_reservation_aborts · test_provisioning_integrity · test_postgres · test_discovery_machine_credentials · test_credential_backend · test_control_api | **74** | 48 | 0 | 0 | 97s | 74/48 = 동일 |
| S07 복구 (drill·capability·verdict·PITR 경계·readiness·no-skip 가드) | integration/test_recovery_drill · core/test_recovery_capability · core/test_recovery_verdict · test_pitr_boundary · test_pitr_readiness · test_recovery_drill_prerequisites | **92** | 19 | 0 | 0 | 8s | 92/19 = 동일 |
| **합계** | 6세트 | **762** | **88** | **0** | 전부 0 | 9m21s | |

**skip 88 사유 = 옛 PC와 동일한 정직 게이팅, 새 PC §4 미설정과 일치**: Actual Linux file backend 48(credential 파일 백엔드, Windows) · Linux private storage 21(`integration/test_results.py` 전부 — RunRecord 완료 파이프라인 실출력 바이트) · CX01_CONTAINER is unset 19(물리 컨테이너 복원 리허설 대상; 보호 컨테이너는 옛 PC 잔류). **늘어난 skip 없음.**

## 재사용 가능한 증거 목록 (Codex가 카드 닫을 때 인용)

- provenance: `docs/vault/30_Development/Evidence/claude-newpc-realpg-d01c931a/evidence-provenance.json` (SHA·clean·명령·세트별 수치·junit sha256).
- junit·로그(untracked): `.work/evidence-claude-d01c931a/evidence/{S02,S03,S09,S10,S04_S05_contention,S07_recovery}.{xml,log}` + `evidence_meta.txt`. junit sha256 앞 16자: S02 `3d04ffecf39da26f` · S03 `bf0ee66fbbe039bb` · S09 `25ec19dc6f0a854f` · S10 `27a190b3a0dcb959` · S04/05 `3be68ed92cd1fcad` · S07 `d0a5462bed6a5a96`.
- 각 세트가 채우는 요구증거의 대표 단언은 옛 PC 문서 그대로(소스 불변 확인: d01c931a까지 해당 시험 파일 diff는 S03 +9건뿐) — [[2026-09-22_S02_split_및_실PG증거생성_Claude]] · [[2026-09-22_S03_DB_실PG증거_및_ST_정본결정게이트_Claude]] · [[2026-09-22_계보모델불변_컨텍스트eval_교차증거_실PG_S09_S10_Claude]] · [[2026-09-22_경합복구_교차증거_실PG_S04_S05_S07_Claude]].

## not_run (정직)
- `integration/test_results.py` 21건(Linux 사설 스토리지) · 자격증명 파일 백엔드 48건(Linux) · 컨테이너 복원 리허설 19건(CX01) — 이 호스트 자원 부재. hosted CI(Linux+PG)가 앞 둘의 첫 관측 자리이며, 현재 CI backend는 export_schemas stale로 pytest 미도달([[2026-09-22_17-02-56_KST_REALPG-FULLRUN_Claude_실측]] §4).

## 다음 첫 행동 / 담당
- Codex: 위 증거를 S02·S03·S09·S10·S04·S05·S07 카드 판정에 인용(self-close 아님, 내 카드 상태 미변경).
- Claude: 작업 3 PITR runbook 실측(readiness=dev-pg absent 실측 완료, 물리 리허설 probe 진행 중) → 별도 History.
