---
doc_id: "HIST-VF-CL-05-005"
title: "VF-CL-05 finding #1 철회와 finding #2(model 개념 결속) 제안 (Claude)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-18T09:30:00+09:00"
base_sha: "b30a723"
reviewed_sha: "origin/agent/codex/vf-deployment-guard (d6d9d87 계약)"
branch: "agent/claude/vf-cl"
task: "VF-CL-05"
source_of_truth: "Git"
tags: ["saintvision", "vf-cl-05", "vf-cx-02", "model-manifest", "finding", "correction"]
---

# VF-CL-05 finding #1 철회와 finding #2 제안 (Claude)

## finding #1 철회 (내 오류)

이전 VF-CX-02 검토에서 "shard 수 상한이 `manifest_copy`에 없어 >1024 shard가 `model_shard_locations` INSERT의 CHECK에서 늦게·불명확하게 거부된다"고 finding #1을 냈다. **이는 틀렸다.** ModelManifest 계약 스키마(`generated/models.py:1464`)가 `shards: max_length=1024`, `replicas: max_length=4096`을 이미 강제하고, `manifest_copy`(model_manifest.py:27)는 **첫 줄에서** `validate_contract("ModelManifest", value)`로 그 JSON Schema(Draft202012)를 검증한다. 따라서 >1024 shard는 manual 검사·DB INSERT 이전에 **조기·명확하게** 거부된다(VAL 계약 오류). 나는 스키마 검증 단계를 간과했다. finding #1은 유효하지 않으므로 철회한다. (원문은 오류 기록으로 보존: `2026-09-15_15-00-00_KST_VF-CL-05_Claude_VF-CX-02독립검토.md`의 finding 1.)

## finding #2 (유효) — 두 model 개념의 결속 제안

두 model 개념이 별개로 존재하고, VF-CL-03의 license/classification 요구가 여기에 걸린다. 실측 대조:

| | 커널 `inv.model_manifests` (VF-CX-02) | S10 `public.model_versions` (내 VF-CL-03) |
|---|---|---|
| 스키마 | inv (kernel), inv_kernel만 GRANT | public, app-role 접근 |
| 키 | (tenant,project,model,version) | (tenant, model_version_id); unique (model_id,version) |
| 내용 | manifest JSONB: shards/replicas/**licensePolicy**/**classification**/encryption/keyRef/runtimeCompatibility, `data_locations` FK | content_sha256·uri·stage·verified_at·retention, lineage graph, deployment |
| 성격 | 저장 **commitment**(bytes 어디에·어떻게, 배포 라이선스) | **registry**(무엇을·왜, provenance·release·deploy) |
| license/classification | **있음**(licensePolicy str, classification enum) | **없음** |

핵심: `model_versions`엔 license/classification 필드가 없고, 그 정보는 커널 manifest(inv_kernel 전용)에만 있다. VF-CL-03의 "import/version/**license** tests"를 채우려면 이 결속을 Codex가 정해야 한다.

### 제안 옵션 (Codex 결정 = finding #2)

- **옵션 A — 값-키 연결, 스키마 유지(권장 기본)**: 둘을 (project, model, version) 자연키로 값 연결한다. `model_versions.uri`(`inv://models/<name>@<version>`)와 manifest의 (model_id,version)이 대응. FK는 없다(inv는 kernel-only, cross-schema FK 불가). license/classification은 **커널 API read-through**로 노출: Model Studio가 license를 보이려면 커널이 `get(manifest).licensePolicy/classification`을 제공하고 app은 그것을 표시. `model_versions`엔 필드 추가 없음. **장점**: 두 관심사 분리 유지, 중복 없음, 커널이 license 단일 진실. **단점**: app이 license를 직접 못 읽고 커널 경유.
- **옵션 B — model_versions에 파생 license/classification 캐시**: `model_versions`에 `license_policy`·`classification` 컬럼을 추가하고, manifest commit 시 커널이 그 값을 model_versions에 기록(파생·불변). **장점**: app이 직접 read. **단점**: 두 곳에 저장→동기화·진실원 이슈, classification 하향 금지 규칙(ADR-013)을 두 곳에서 지켜야.
- **옵션 C — 통합(비권장)**: 한 테이블로 합침. inv_kernel 전용성과 app registry 접근이 상충해 RLS/grant 설계가 복잡. 배포 admission(run이 commit)과 registry lifecycle(승인 흐름)의 트랜잭션 경계도 다름.

**권장**: 옵션 A. license/classification의 단일 진실은 커널 manifest(배포 admission이 강제)이고, registry(model_versions)는 그것을 참조/표시만. VF-CL-03 license 시험은 "release된 model_version에 대응하는 committed manifest의 licensePolicy/classification을 커널 API로 조회·검증"으로 구성하면 된다. classification 하향 금지(ADR-013)는 manifest 측에서 강제.

## 상태 / 다음

- finding #1: **철회(내 오류)**. finding #2: 위 3옵션으로 Codex 결정 대기.
- Codex가 옵션 결정 시 Claude가 VF-CL-03 license 결속(옵션 A면 커널 read-through 시험, B면 파생 컬럼 migration+시험)을 구현.
- VF-CX-02 검토의 finding 3(migration 번호 발산)은 CX-01 통합 시 조정으로 유효.

## 내-side 결정 (2026-09-18, 사용자 승인 위임)

사용자가 내 영역의 승인을 위임했으므로, **옵션 A를 내 side 결정으로 채택**한다 — 커널/코어 계약을 바꾸지 않고 additive이므로 내가 결정할 수 있는 범위다(Codex가 옵션 B를 선호하면 개정 가능). 귀결: `model_versions`에 license 컬럼을 추가하지 않고, license/classification의 단일 진실은 커널 manifest로 둔다. registry는 (model_id, version) join key로 manifest에 대응하고, app이 license를 보일 때는 커널 `ModelManifestStore.get`의 read-through를 쓴다. **VF-CL-03 app-side는 이로써 완결**(join key 시험 `test_a_version_carries_the_join_key_...`로 앵커). 커널-served license 자체의 end-to-end 검증은 CX-01 병합으로 커널 manifest 테이블이 base에 온 뒤 수행한다.
