---
doc_id: "HISTORY-S08-BE-BUILDKIT-CONTRACT-20261001"
title: "S08-BE BuildKit 계약 경계 구현"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-10-01T13:40:45+09:00"
source_of_truth: "Git"
---

# S08-BE BuildKit 계약 경계 구현

## 선택 근거

- owner가 Codex인 S08-BE의 범위 중 외부 GPU·LAN builder 없이 닫을 수 있는 첫 구현은
  BuildKit 계약 경계다. Claude가 승인한 PR #265 설계 v1.1.0
  (`ecb43d4d86362de6209d0c2d169810d2f5681bed`)의 구현 순서 1을 따른다.
- 기준은 `origin/coord/train5-ci-1243`의
  `8e6c68c64c32940fc95ea1f89614a053a42bfaa9`다. 공개 route, daemon 실행,
  ROOF 실행 결속, GPU provider, migration은 이 카드의 완료 주장에 포함하지 않는다.

## 구현 경계

- 정본 `contracts/v1alpha1/core.schema.json`에 `BuildRequest`, `BuildPlan`,
  `BuildReceipt`와 하위 strict 타입을 추가했다. 세 계약은 기존 `WorkloadSpec`과
  분리되며 모두 알 수 없는 필드를 거부한다.
- `BuildPlan`의 `rootless=true`, `privileged=false`, `hostAccess=false`, 빈
  `devices`·`binds`는 literal이다. network mode와 policy ID를 결속하고 CPU·memory·
  storage budget, lease/fencing, builder profile/epoch, cache·secret-ref digest,
  immutable base digest를 필수로 둔다.
- request는 clean commit/tree SHA와 canonical relative context·Dockerfile 경로,
  opaque secret reference만 받는다. branch/tag, mutable base tag, literal secret,
  arbitrary env/build args, caller output digest는 계약 표면에 없다.
- receipt는 plan/source/output/SBOM/scan/cache/network digest, trace가 있는 audit
  event, cleanup receipt를 필수로 한다. 성공 receipt는 lease·builder claim·cgroup
  정리 확인과 non-quarantine cache disposition 없이는 거부된다.
- 실패·취소 receipt는 생성되지 않은 output image/config, SBOM, scan, cache output을
  `null`로 기록할 수 있다. 성공일 때는 다섯 digest가 모두 유효해야 하므로 실패에서
  값을 합성하거나 성공에서 증거 부재를 숨길 수 없다.

## 검증

- `python -m pytest tests/core/test_buildkit_contracts.py -q` → **44 passed**.
- `python tools/generate_contracts.py` → 생성 완료; 생성 직후 정본 schema와 Python·
  TypeScript·Go·Node mirror가 동일 입력에서 재생성됐다.
- `npx --yes --package typescript@5.9.3 tsc --noEmit --strict packages/contracts-ts/src/index.ts`
  → exit 0.
- `python tools/check_docs.py` → exit 0.
- `python tools/check_contract_bindings.py` → exit 0.
- `python tools/check_doc_path_citations.py --ratchet --base-ref origin/coord/train5-ci-1243`
  → exit 0, 기존 baseline 외 신규·stale 결함 0.
- `python tools/check_frontend_integrity.py` → exit 0, 0 violations.
- `tests/core/test_core.py`는 로컬 Python 3.10에 `enum.StrEnum`이 없어 collection 전에
  중단됐고 제품 실패로 세지 않는다. 이 저장소의 Python 3.12/3.14 hosted Backend 결과로
  별도 확인한다.
- hosted CI 결과는 PR 생성 뒤 이 문서에 추가한다.

첫 exact-head Core run `36817019372`는 contract regeneration까지 통과한 뒤 Node Go
validator가 Build path/network 정규식의 lookahead·noncapturing group을 컴파일하지 못해
`NODE-0004: schema unavailable`로 실패했다. ECMA 전용 표현을 제거하고 Go RE2와 공통인
capturing group 및 schema `not` 조합으로 바꿨다. Build 계약 pattern에 `(?`가 다시
들어오면 실패하는 회귀 시험을 추가했으며, 교정 head의 hosted Core를 재실행한다.

## 정직성 경계

- 이번 결과는 strict schema와 generated binding의 PG-free 증거다. rootless BuildKit
  daemon, socket 격리, secret canary, cache 격리, cancel·cleanup 실행은 아직
  `NOT_OBSERVED`이며 후속 BuildKit adapter 카드에서만 판정한다.
- receipt와 audit event에 trace를 각각 요구하지만 두 값의 동등성, event 순서와 필수
  event 집합은 JSON Schema가 비교하지 않는다. 이 결속은 adapter 카드의 runtime validator와
  되살림 시험에서 닫는다.
- S08-BE registry 상태와 점수는 변경하지 않는다.
