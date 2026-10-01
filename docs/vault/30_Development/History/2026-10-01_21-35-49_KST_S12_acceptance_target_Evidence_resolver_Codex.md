---
doc_id: "HIST-20261001-CODEX-CARD190"
title: "S12 수락 target·Evidence 정본 resolver 설계와 공개 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-10-01T21:35:49+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["S12-BE", "Card190", "acceptance", "resolver", "Evidence"]
---

# S12 수락 target·Evidence 정본 resolver 설계와 공개 계약

## 선택 근거와 기준

카드 184/#282 v1.3.0은 release decision write를 켜기 위한 두 resolver 중 target/Evidence
resolver가 없다고 명시했다. `input_sha256`은 Evidence envelope identity가 아니며 caller ref끼리
비교하는 fallback도 금지했다. 따라서 fresh-auth 공급 카드 188 다음의 두 번째 prerequisite인
카드 190을 선택했다. 기준 branch는 #282 head
`b96068b6d009cf2d9ea677b9801749a1e6efd9d0`이고, train9c `be6fcf12`의 조상임을 확인했다.

## 만든 것

- `contracts/release-acceptance-target-registry-v1.json`: AC-12 target v1, source commit/path/blob,
  criteria 4개, canonical digest `d5719845…ee9d`를 고정했다.
- `ReleaseAcceptanceTargetRegistryResponse`와
  `ReleaseAcceptanceReferenceResolutionResponse`: strict/nonempty/unique/lowercase digest,
  all-or-nothing literal을 Pydantic source와 generated JSON Schema로 고정했다.
- [[S12-BE_release_acceptance_target_Evidence_resolver_설계]]: target 변경 절차, Evidence row 전체
  digest, `recorded_at` partition key 포함, migration `0058` 요청, legacy NULL fail-closed/backfill
  receipt, release+project binding/RLS, 오류 표면과 변이 표를 정의했다.
- `tests/core/test_release_acceptance_resolver_contract.py`: registry source blob·target digest와
  shape/semantic 변이, partial/unscoped resolution 거부를 고정했다.

## 정직한 경계

이번 카드는 설계+계약뿐이다. resolver service, DB migration `0058`, binding producer, legacy
backfill, hosted real-PG 결과는 `NOT_OBSERVED`다. 따라서 decision write flag는 계속 off이고
`operatorSignOff=true`를 주장하지 않는다. 다음 구현 owner는 Claude, reviewer는 Codex다.

## 실제 검증

- focused contract: `21 passed`.
- schema export: `95`개 생성(신규 2), 이후 `--check` 예정.
- `git diff --check`: exit 0.
- docs·bindings·citation·ontology gate와 hosted CI는 commit 후 실행/인용한다.

다음 첫 행동: focused gate 전체 실행 → commit/push/PR → Claude 독립 설계 검토 → `0058` 번호 확정.
