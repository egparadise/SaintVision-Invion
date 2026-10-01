---
doc_id: "HIST-20261001-CODEX-CARD190"
title: "S12 수락 target·Evidence 정본 resolver 설계와 공개 계약"
version: "1.2.0"
status: "review"
author: "Codex"
updated: "2026-10-01T22:14:13+09:00"
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
  digest, `recorded_at` partition key 포함, migration `0058` 예약 승인, legacy NULL fail-closed/backfill
  receipt, release+project binding/RLS, 오류 표면과 변이 표를 정의했다.
- `tests/core/test_release_acceptance_resolver_contract.py`: registry source blob·target digest와
  shape/semantic 변이, partial/unscoped resolution 거부를 고정했다.

## 정직한 경계

이번 카드는 설계+계약뿐이다. resolver service, DB migration `0058`, binding producer, legacy
backfill, hosted real-PG 결과는 `NOT_OBSERVED`다. 따라서 decision write flag는 계속 off이고
`operatorSignOff=true`를 주장하지 않는다. 다음 구현 owner는 Claude, reviewer는 Codex다.

## Claude r1 반영

- digest 계산은 trigger 본문에 inline해 `inv_app` INSERT가 EXECUTE 회수로 막히지 않게 했고,
  owner-only 검증/backfill helper와 분리했다. PostgreSQL 16 JSONB text·UTC timestamp·cast 규칙과
  real-PG 고정 vector를 명시했다.
- ledger 전에는 설치/pin prerequisite만 보고, ref resolve는 #282의 ledger/lock 뒤 단계 6과 final
  단계 8에서 두 번 수행한다. timeout 표면은 `RES-0007/503/true`로 정렬했다.
- binder owner와 권한 있는 acceptance-evidence discovery route를 정의했다. producer 부재는 per-row
  404가 아닌 `SYS-0003`이고 `observedAt`은 Evidence `recorded_at`이다.
- resolution DTO에 release·criterion·policy registry·target registry Git blob/file digest를 넣었다.
  registry loader는 duplicate key와 implicit whitespace trim을 거부하고 target-level owner, non-NFC,
  uppercase·63자 hash 변이를 고정했다.
- #282 source head는 merge commit으로만 착지해 도달성을 유지한다. resolver·migration·binder·route와
  hosted real-PG는 여전히 `NOT_OBSERVED`다.
- Claude r2 Low 5건도 v1.1.1에서 닫았다. discovery route는 fresh human+live permission을 요구하는
  strict 100-item page 계약이며 caller project를 받지 않는다. hosted 계획은 trigger/helper digest
  exact equality를 단언한다. target owner는 digest 재계산 뒤에도 거부하고, resolution/discovery의
  top-level과 target `acceptanceIdRef`가 같아야 한다. coordination 용어는 #282의 criterion slot으로
  통일했다.

## 실제 검증

- focused resolver contract: `33 passed`; 기존 write contract 포함 `61 passed`.
- schema export/check: `96/96`.
- `git diff --check`: exit 0.
- docs·bindings·citation·ontology gate와 hosted CI는 commit 후 실행/인용한다.

다음 첫 행동: focused gate 전체 실행 → commit/push/PR → Claude 독립 설계 검토 → `0058` 번호 확정.
