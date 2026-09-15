---
doc_id: "HIST-VF-CL-03-001"
title: "VF-CL-03 model 레지스트리/lineage 시험 (Claude)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-15T04:40:00+09:00"
base_sha: "46ab3f7"
branch: "agent/claude/vf-cl"
task: "VF-CL-03"
source_of_truth: "Git"
tags: ["saintvision", "vf-cl-03", "model-registry", "lineage", "tests"]
---

# VF-CL-03 model 레지스트리/lineage 시험 (Claude)

## 목적

VF-CL-03(model registry, MLflow/lineage, import adapter)의 **계약 무관 부분**. 기존 S10-ST model **version** 레지스트리(`Model`·`ModelVersion`·`ModelLineage`·`Deployment` + `services/lineage.py` 11개 함수)가 **완전 untested**였음을 확인하고, VF-CL-03 합격 증거("import/version/license tests")에 해당하는 API/DB 통합 시험을 채운다. 이는 **새 VF-CX-02 ModelManifest/Shard와 별개**(그 계약은 미착지, 건드리지 않음). 별도 worktree `agent/claude/vf-cl`.

## 재사용 경계 (VF-CL-01 storage와 동형)

기존 substrate 재사용: `register_model_version`·`verify_model_version`·`pin_retention`·`release_model_version`·`record_lineage`·`trace_model`·`register_dataset_version`·`register_commit`·`record_deployment`. `ModelVersion`은 append-only(고정 이름에 weight 교체 불가), `content_sha256` tenant별 unique, `stage`(draft/candidate/released/retired) + CHECK `release_requires_verification_and_pin`.

## 검증 (throwaway postgres:16) — `tests/test_model_registry.py` 10 passed

- register → `draft`, non-hex SHA 거부, 없는 model 거부.
- **동일 weight 두 이름 거부**(content_sha256 unique → IntegrityError).
- verify → verified_at 설정, checksum 불일치 거부.
- retention pin 연장-전용.
- **release refusal 사슬**: unverified 거부 → verified/unpinned 거부 → verified+pinned이나 lineage 없음 → "not fully traceable" 거부(AC-10).
- **DB CHECK 실증**: owner가 `UPDATE ... stage='released'` 강제(verified/pin 없이) → IntegrityError(검사 실패 가능 실증).
- record_lineage: 미지 kind 거부, 중복 edge 멱등.
- **trace_model**: bare version은 missing = 전 REQUIRED_KINDS(dataset_version/code_commit/eval_run/approval), fullyTraceable False. dataset_version·code_commit 등록·edge 기록 후 missing이 {eval_run,approval}로 축소, dangling 없음.
- RLS: tenant A의 model_version이 tenant B scope에서 불가시(count=0).
- 회귀 없음.

## 남은 부분 (미착수/blocked)

- **성공 release happy-path**: eval_run·approval subject는 evaluation/execution FK 사슬 seeding 필요 → fixture 후속. 현재는 그 부재가 release를 막는 refusal로 검증됨.
- **import adapter(MLflow/lineage import)·license/classification 정책**: 새 VF-CX-02 ModelManifest 필드(licensePolicy/classification/encryption)와 맞물리는 부분은 계약 대기. S10 ModelVersion엔 아직 license 필드 없음 — 계약이 그 위치를 정한다.

## 상태

- `implemented`: `tests/test_model_registry.py`(제품 코드는 기존 substrate).
- `locally_verified`: throwaway postgres 10 passed. (실 클러스터·CI 아님.)
- `independently_reviewed`: Codex pending.
- `operationally_accepted`: 미완.

## 다음 첫 행동/담당

- Claude: eval_run/approval fixture로 성공 release happy-path 보강, VF-CX-02 착지 시 license/manifest 결속.
- Codex: VF-CX-02 계약(license/classification 위치 포함) 제공, VF-CL-01/02/03/04 독립 검토.
