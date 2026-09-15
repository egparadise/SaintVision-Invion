---
doc_id: "HIST-VF-CL-01-001"
title: "VF-CL-01 DataLocation 재사용 경계와 카탈로그 시험 (Claude)"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-15T03:10:00+09:00"
base_sha: "71a9b6a"
branch: "agent/claude/vf-cl"
task: "VF-CL-01"
source_of_truth: "Git"
tags: ["saintvision", "vf-cl-01", "storage", "datalocation", "catalog", "tests"]
---

# VF-CL-01 DataLocation 재사용 경계와 카탈로그 시험 (Claude)

## 목적

로드맵 Now의 "Storage/Model manifest 계약과 기존 `DataLocation`, locality, shard runtime의 **재사용 경계 확정**". VF-CL-01이 이미 있는 substrate를 재구현하지 않고 그 위에 쌓도록, 무엇이 존재하고 무엇이 계약 대기인지 실측으로 확정한다. 별도 Claude worktree(`agent/claude/vf-cl`)에서 진행하며 코어/보안 계약은 변경하지 않는다.

## 재사용 경계 — 이미 존재하는 것 (재구현 금지)

VF-CL-01의 "storage catalog/API, DataLocation 재사용"은 **대부분 S02-ST substrate로 이미 구현**되어 있다:

| 구성 | 위치 | 재사용 가능 내용 |
|---|---|---|
| `DataLocation` 모델 | `src/saintvision/db/models/storage.py:93` (table `data_locations`) | `uri`(tenant별 unique)·`kind`(dataset/model/artifact/workspace)·contribution FK·`checksum_sha256`/`verified_at`/`ready`·`retention_pinned_until`·`version`. CHECK `ready_requires_verification`(ADR-011). |
| `StorageContribution` 모델 | `storage.py:34` | 기여 폴더, `normalized_path` 기준 uniqueness, mode/status/capacity. |
| `DataReplica` + `data_locations` | `db/models/locality.py` | node별 replica 상태(transferring/ready/stale/corrupt/evicted), ready=검증된 checksum, pinning, cache 60% 한계, node당 동시 전송 2. |
| storage service | `src/saintvision/services/storage.py` | `register_contribution`·`activate`·`revoke`·`catalogue_location`·`mark_verified`·`pin_retention`·`list_*`. |
| storage API | `src/saintvision/api/v1/storage.py` (`/v1` prefix) | `POST/GET /storage/contributions`, `{id}/activation`, `DELETE {id}`, `GET /storage/locations`. |
| `inv://` 문법 | `src/saintvision/storage/pathsafe.py:235 build_uri` (ADR-010) | dataset/model=`inv://{plural}/{name}@{version}/{path}`, artifact=`inv://artifacts/{run}/{artifact}`, workspace=`inv://workspaces/{ws}/{path}`. name에 `@`·`/` 금지. |

**결론**: VF-CL-01 스키마·API·service·inv:// 문법·무결성 규칙은 신규 개발이 아니라 재사용 대상이다. 최대 위험은 이 substrate를 모르고 재구현하는 것이며, 이 문서가 그것을 막는다.

## 발견한 갭 — 즉시 채운 것 (계약 무관, 내 lane)

기존 storage **카탈로그 service/API에 직접 통합 시험이 없었다**(`tests/test_locality.py`=replica, `test_pathsafe.py`=build_uri만; `catalogue_location`·`/v1/storage/*`·`data_locations` 참조 시험 0). VF-CL-01 합격 증거가 "API/DB integration tests"이므로 이를 채웠다.

- 신규 `tests/test_storage_catalog.py` — throwaway `postgres:16`에서 **13 passed**:
  - contribution lifecycle(pending→active→revoked), 비활성 contribution에 catalogue 거부.
  - catalogue 후 `ready=False`·checksum None, inv:// URI 정확(`inv://datasets/corpus@1/data.bin`).
  - inv:// 문법 per-kind(dataset/model/workspace) 및 version 누락 거부.
  - `mark_verified` ready=True·checksum 기록, non-hex 거부, **재검증 시 checksum 충돌 거부**(ADR-011 substitution guard).
  - **DB CHECK `ready_requires_verification` 실증**: owner가 서비스 밖에서 `ready=true`+checksum 없이 강제 INSERT → `IntegrityError`(검사가 실패할 수 있음을 실증).
  - retention pin은 연장-전용(더 이른 pin은 무시).
  - **RLS**: tenant A 스코프의 non-owner가 tenant B의 data_location을 보지 못함(count=0).

## 계약 대기 (blocked-on-contract)

- VF-CL-01의 남은 부분과 VF-CL-02/03의 model 경로는 **VF-CX-02 계약(ModelManifest/Shard/Replica)** 미착지로 막혀 있다. 현재 `ModelManifest`는 아키텍처 문서(필드 설명)만 있고 `src/`·`services/`·`migrations/`에 코드/스키마가 없다.
- 구체적으로: `kind='model'` DataLocation을 ModelManifest.shards[]·replicas[]에 어떻게 결속하는가(shard가 별도 엔티티인가, model-kind location의 확장인가)가 계약이다. 이 결정은 Codex(VF-CX-02) 몫이며 임의로 스키마를 만들지 않는다.

## VF-CL-02 준비 정찰

- inv:// **빌더** `build_uri`는 있으나 **역방향 `parse_uri`/resolver는 없다**(`resolve_within`은 파일시스템 경로용). VF-CL-02(`inv://` resolver, workspace materialization/write-back)의 신규 작업은 `parse_uri`(uri→kind/name/version/path) + resolver(uri→data_locations→ready DataReplica 선택) + materialization/write-back이다. VF-CL-01(catalog) 선행 위에서 진행 가능.

## 상태

- `implemented`: `tests/test_storage_catalog.py`(신규 시험만; 제품 코드는 기존 substrate).
- `locally_verified`: throwaway postgres:16 13 passed. (실 클러스터·CI 아님.)
- `independently_reviewed`: reviewer Codex 미확인(pending).
- `operationally_accepted`: 미완.

## 다음 첫 행동/담당

- Claude: VF-CX-02 계약 착지 시 model-kind location↔manifest 결속 구현·시험. 그 전까지 VF-CL-02 `parse_uri`/resolver 골격(계약 무관 부분) 착수 가능.
- Codex: VF-CX-02(ModelManifest/Shard/Replica) 계약 제공. VF-CL-05 배포 경계 finding(별도 History) 수용.
