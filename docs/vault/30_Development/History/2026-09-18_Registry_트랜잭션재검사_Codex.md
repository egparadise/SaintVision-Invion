---
doc_id: "HIST-REGISTRY-REVALIDATION-001"
title: "Registry 실행결속용 트랜잭션 재검사"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T13:09:23+09:00"
source_of_truth: "Git"
---

# Registry 실행결속용 트랜잭션 재검사

VF-CX-02/03, owner Codex, reviewer Claude(미실시). base f2297ae, branch agent/codex/model-registry-binding. agent-delivery1.1.0/core-reliability1.0.0와 공통/개인 진행판을 확인했다. 범위는 현재 registry 권한과 lifecycle 검사를 호출자 트랜잭션에서 재사용하는 선행 구현이다. frozen workload/승인 연결은 아직 완료가 아니다.

## 착수

기존 bind는 자체 트랜잭션을 열어 실행 승인 트랜잭션에 SHARE 잠금을 유지할 수 없다. revalidate는 기존 불변 binding만 허용하며 생성/commit/실행permit 발급을 하지 않는다. 공통 현재 검사로 정책·권한·manifest·registry lifecycle 조건의 분기를 방지한다. 실제 PG에서 미결속 거부, 변경된 권한/정책/내용/identity/retention 거부와 호출자 종료까지 lifecycle 잠금 유지를 검증한다.

## 확인한 것과 다음 행동

사용자 제공 disposable PostgreSQL16/55432, 파일별 순차 실행:

- `python -m pytest tests/integration/test_model_registry_revalidation.py -q --tb=short`: exit0, 7passed/0skip/0failed.
- `python -m pytest tests/integration/test_model_registry_binding.py -q --tb=short`: exit0, 16passed/0skip/0failed.
- 증거: Evidence/model-registry-binding/test_model_registry_revalidation-coord-pg.json 및 test_model_registry_binding-revalidation-regression-pg.json. 기존 e89a415 시험 증거는 덮어쓰지 않았다. base f2297ae 위 수정 소스를 시험했으며 source hash를 각 증거에 기록한다.

합계 23건은 두 파일 범위이며 전체 스위트/운영 인수 결과가 아니다. image lane·Docker/prune 실행 없음. CI 결제 제한은 사용자 조치 대기, CI 통과로 기록하지 않는다. 독립 검토는 Claude 대기. 신규 원격 설치 권한을 사용하지 않았다.

다음 Codex: registry binding을 frozen workload의 승인 digest에 연결하고 승인/delivery/claim에서 현재 policy와 lifecycle을 재검사. 다음 Claude: 본 helper와 e89a415 orchestration 독립 검토, R5-01/02 수정본 제출. 사용자 R5-01 독립 MRO 실증은 기존 Claude816346c 검토 History에 수신 기록했다. 원격 tip816346c 확인, 새 수정본 미도착으로 전체 브랜치 보류 유지.

## 배포 기록

구현 SHA 0a16658. 작업 branch와 integration/all-agents-unified에 일반 fast-forward push exit0. check_docs exit0(517문서), check_ontology exit0, git diff --check exit0. 변경 정본 7파일만 Obsidian check→apply→check: 7 exported, 0 pending, 0 conflicts(원본 SHA 0a16658). 전체 vault export 없음.

`gh run list --repo egparadise/SaintVision-Invion --branch agent/codex/model-registry-binding --limit 3 --json databaseId,headSha,status,conclusion,url` exit1: 현재 CLI 인증 없음. 따라서 동일 SHA CI ID/상태는 미확인이다. 기존 billing 대기와 구분하며 CI 재실행/비용 조치는 하지 않았다. 개발 integration 반영과 CI·독립 검토·운영 인수는 별도 상태다.
