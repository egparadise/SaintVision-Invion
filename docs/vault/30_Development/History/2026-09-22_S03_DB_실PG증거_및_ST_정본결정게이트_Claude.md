---
doc_id: "CLAUDE-S03-DB-REALPG-AND-ST-GATED-001"
title: "S03-DB 실 PostgreSQL 증거(192) + S03-ST는 다운로드-정본 결정(#5)에 게이트 (owner Claude)"
status: "in_progress-evidence-added(DB) / blocked-on-user-decision(ST)"
version: "1.0.0"
author: "Claude (owner)"
reviewer: "Codex"
verified_at_sha: "9f43c59d (origin/integration; 측정 중 tip 이동 가능)"
working_tree: "코드 clean; 문서 1건(R2-a 커밋규칙, 이미 edb068b6로 착지)만 HEAD-lag dirty — pytest 무영향"
db_method: "disposable pgvector/pgvector:pg16 via Docker 20.10.22, per-test DB, 제거 후"
handoff_priority: "LOW — Codex 큐(S01-FE 검토·S02 인계)보다 뒤. 증거 기록됨·블로커 없음"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["S03", "real-pg", "evidence", "download-canonical-gate", "owner"]
---

# S03-DB 실PG 증거 + S03-ST 정본 결정 게이트

S03-DB/ST는 owner Claude·reviewer Codex·planned·depends_on S02(전부). 요구 증거 = **허용·거부 로그·exit code·증거 ID**(AC-03 실행/샌드박스). S02 방법대로 갈라, 진행 가능분(DB) 실PG 실측, ST는 게이트 확인.

## S03-ST — 다운로드-정본 결정(#5)에 **게이트됨** (사용자 caution대로 확인)
S03-ST scope = 볼륨·**Artifact 기본 전송**. 만지기 전에 오늘의 다운로드-정본 결정(브리프 #5)이 걸리는지 봤다. **걸린다:**
- **확인**: `services/control-plane/src/inv/result_view.py`의 download는 아티팩트 바이트를 **DB 영수증 envelope**에서 낸다(`raw = output_bytes(row["receipt"])`). content_hash·size는 `inv.storage_objects`(볼륨 메타)와 대조하나 **바이트 자체는 저장 볼륨 파일이 아니라 DB 영수증**이다. 사용자가 짚은 "다운로드가 저장 파일을 안 읽고 DB 영수증을 읽는다"가 소스로 확인됨.
- **게이트 이유**: 정본 전송이 **볼륨(storage_objects 실 객체)을 읽을지 DB 영수증을 읽을지**가 미결(#5 사용자 결정; 레거시 `X-Checksum-SHA256` vs 현 `X-Content-SHA256`도 그 결정에 포함). Artifact 전송의 정본 계약이 확정되기 전엔 S03-ST의 전송 반절을 **닫을 수 없다.**
- **처리(지시대로)**: S03-ST 전송은 **만지지 않았다.** 정본 결정이 나면 착수. (볼륨/storage_objects 소프트웨어는 존재하나 전송 정본이 게이트라 전체 닫기는 #5 대기.) → 브리프 #5에 "S03-ST 착수가 이 결정에 걸림" 표시.

## S03-DB — 게이트 없음, 실PG 증거 생성 (Workspace·Workload·Run·Evidence)
S03-DB는 물리·정본 의존 없음(S02-DB처럼). 테이블 built(`workspaces·workloads·runs` + evidence 참조, 0001/0002_s03_execution). 밤새 PG 부재로 not_run이던 S03-DB 실행/증거 시험을 일회용 PG로 **실 PostgreSQL 실측**:

**provenance**: SHA `9f43c59d`, 코드 clean(문서 1건 HEAD-lag만), `.venv` 3.14.6, Docker 20.10.22. 내 라벨/전용포트, 끝나고 제거, Codex/보호 컨테이너 미접촉.
- **S03-DB 세트 → 192 passed / 0 skip** (실PG). 파일: `test_run_state`·`core/test_run_result_contract`·`core/test_run_attempt_contract`·`core/test_run_log_contract`·`core/test_run_approval_observation_contract`·`core/test_run_state_alignment`·`core/test_workspace_api_boundary`·`core/test_workspace_response_contract`·`core/test_workspace_manifest`·`test_execution`·`test_execution_readiness`·`test_vf_evidence`·`test_evidence_case_inventories`.
- **요구 증거(허용/거부·exit·증거ID) 실측**: `test_execution::test_the_database_refuses_a_success_without_evidence`(DB가 **증거 없는 성공을 거부** = 거부 로그·증거 ID 강제), run_state/state_alignment(상태·exit 전이), run_result/attempt/log 계약(증거 ID·결과), workspace_api_boundary(Workspace 경계·허용).
- 실행이 **실DB 상태기계·불변식을 관통**하므로 배선·강제가 실측 확인(오늘 lesson).

## 못 한 것 (not_run)
- **전체 CI-스코프 실PG**·node-runtime 의존 실행 시험(integration/*: workspace_api·checkout·resume·start·shards·results 등 = Go/Node 필요) → CI 첫 실행/Codex 몫.
- **S03-ST 전송**: #5 결정 대기(위).
- 실 브라우저 여정(Gemini).

## 상태·인계 (우선순위 표시)
- S03-DB: 소프트웨어 built + **192건 실PG 실측**으로 허용/거부·exit·증거ID 증거 섰다(사용자 입력 없이). **self-close 안 함**, reviewer(Codex) 인계.
- S03-ST: **#5 결정 대기로 착수 보류**(전송 정본 미결). DB만 진행.
- **Codex 큐 우선순위**: 지금 Codex 앞에 S01-FE 검토 + 내 S02 인계가 있다. **이 S03은 셋째, 비긴급** — S03은 planned·depends_on S02(미완)이라 지금 검토 급하지 않다. **S01-FE·S02 먼저 보고 S03은 나중에.** 검토자가 순서 정하도록.

관련: [[2026-09-22_S02_split_및_실PG증거생성_Claude]] · [[사용자_결정대기_브리프_2026-09-22]](#5 다운로드 정본) · [[2026-09-22_artifact_content_header_path_audit_Codex]] · [[검증규칙과_세축_canon]].
