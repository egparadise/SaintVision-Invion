---
doc_id: "HISTORY-CODEX-LAN-PILOT-CP-REVOCATION-EVIDENCE-20260923"
title: "LAN pilot CP 겸임 철회 증거와 재활성 경계"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T09:15:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["LAN", "pilot", "revocation", "PostgreSQL", "audit", "ADR-100"]
---

# LAN pilot CP 겸임 철회 증거와 재활성 경계

## 범위와 SHA

- 카드: Codex 카드 16, PR #103 Claude 관찰 O1~O3 후속.
- 최초 base: `1ac992f1`; 최종 rebase parent: `abf9240f`.
- 구현 SHA: `6230b06f` (rebase 전 동일 blob `b22ae780`).
- branch/PR: `agent/codex/lan-pilot-cp-reactivation`, PR #105.
- 제품 코드·공유 계약·migration 변경 없음. README 경계와 실 PostgreSQL 단일 시험만 추가했다.

## 경계 명문화

철회에는 암묵적 역경로가 없다. `init --allow-server-node-colocation`을 다시 실행해도 disabled marker를 지우거나 revoked channel을 활성화하지 않는다. operator가 private state를 직접 편집하거나 기존 certificate를 재등록하거나 대체 Node를 만들어 우회하는 것도 금지한다. 재활성에는 preserved Node/key identity 재검증, 현재 channel version CAS, 새 audit entry, 마지막 disabled marker 해제를 하나의 별도 검토된 operator command로 구현해야 하며 현재 버전에는 그 명령이 없다.

겸임 Node가 존재하기 전에 `revoke-server-node-colocation`을 실행하는 것은 무해한 idempotent opt-out이다. `serverNodeColocationAllowed=false`와 빈 `disabledNodes/channels`를 남기고 독립 Node에는 손대지 않는다. 이 결과는 겸임 identity/channel이 과거 존재했다는 증거가 아니다.

## 실 PostgreSQL 증거

전용 단일 시험은 `tests/integration`의 기존 `postgres` fixture로 매 실행 고유 database와 난수 `inv_app_*` login role을 만들고 migration head를 적용한다. operator CLI는 그 disposable DB의 owner DSN으로 실제 `revoke_channel`을 호출하며 공용 role 속성을 변경하지 않는다. 종료 시 fixture가 고유 DB와 role을 정리한다.

시험 결과는 다음을 고정했다.

- CP 겸임 channel: version 1/enabled true → version 2/enabled false.
- audit: 기존 `provision` v1을 보존하고 같은 fingerprint의 `revoke` v2를 추가.
- 독립 Node channel: version 1/enabled true 불변.
- 두 Node row 모두 보존, CP Node state는 disabled marker만 추가.
- CP Node key, journal, certificate 파일 bytes 보존.
- CLI public JSON에 DSN 없음.

## 검증

| 명령 | 결과 |
|---|---|
| `pytest -q tests/integration/test_lan_pilot_colocation_revocation.py` | final rebase SHA 1 passed / 8.77s / exit 0; rebase 전 1 passed / 5.70s / exit 0 |
| 같은 실 PG 시험 rebase 전 | 1 passed / 7.00s / exit 0 |
| `pytest -q tests/test_lan_pilot_multinode.py tests/core/test_lan_worker_config.py` | 47 passed / exit 0 |
| docs / contract bindings / frontend integrity / ontology / single-source ratchet | 모두 exit 0; final rebase `check_docs.py` 874 documents |
| response freshness | advisory 10/10 present / exit 0 |
| `python tools/sync_obsidian.py --check` | 1710 managed / 2 pending exports / 0 conflicts / exit 0; `--apply`는 coordinator 담당 |

실 파일럿 `.work/lan-5node/node1`의 state/channel은 변경하지 않았다. Docker API 1.41·Ubuntu WSL 부재 blocker와 실제 CP 겸임 미등록 상태도 유지한다. 따라서 이 시험은 철회 코드의 DB 불변식 증거이지 실제 운영 철회 receipt가 아니다.

## 다음 행동

Claude가 PR #105에서 실제 channel CAS/audit와 보존 단언, disposable DB/role cleanup, 재활성 금지 문구를 독립 검토한다. 향후 재활성 요구가 생기면 별도 카드에서 versioned/audited command를 설계·승인하며, 현재 state를 수동 편집하지 않는다.
