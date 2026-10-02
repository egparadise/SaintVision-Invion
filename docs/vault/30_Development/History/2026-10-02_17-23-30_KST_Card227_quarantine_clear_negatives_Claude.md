---
doc_id: "HISTORY-CARD227-QUARANTINE-CLEAR-NEGATIVES-20261002"
title: "카드 227 — 격리 해제 경로의 부정 시험. 제품은 그대로 두고, 변이로 어느 검사가 실제로 작동하는지 측정했다"
version: "1.0.0"
status: "proposed"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-10-02T17:23:30+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "693dc09a"
task_ids: ["S08-BE"]
tags: ["s08-be", "containment", "quarantine", "approvals", "tests", "claude"]
---

# 카드 227 — 격리 해제 경로의 부정 시험

## 0. 한 줄

`#318`(Codex 카드 222) r4가 남긴 후속: 해제 경로의 부정 시험이 `kill`/`drain`용 **generic**이라 **quarantine 전용이 없었다.** 시험만 **열다섯** 추가했고 **제품 코드 변경은 0건**이다. 변이를 걸어 보니 내가 처음 쓴 시험 중 **셋은 다른 검사에 가려** 해당 제품 검사를 실제로 지키지 못했고, 그 셋을 위조 상태를 심는 시험으로 바꿨다.

## 1. 측정 대상 상태를 제품이 만들게 했다

격리는 이 파일이 쓴 `UPDATE`가 아니라 **제품의 fence**(`BuildExecutionService._mark_node_quarantined`)로 만든다. 그래서 시험이 보는 상태는 빌드가 경쟁에서 진 뒤 **실제로 남는 상태**다: `inv.nodes.status='quarantined'` + 원인을 적는 `inv.build.node_quarantined` outbox 레코드.

`resume`의 readiness query가 요구하는 **fresh authenticated observation**(채널·스냅샷·heartbeat)은 시험이 직접 쓴다. 이 파일은 상태 변경 **앞의 승인·감사 게이트**에 관한 것이고, 실제 probe 경로는 Docker 기반 `test_drain_preserves_inflight_execution_and_resume_needs_fresh_probe`가 이미 측정한다 — 모듈 docstring에 적었다.

## 2. 무엇을 거부하는지 (각각 단독)

| 시험 | 거부 |
|---|---|
| 승인 1인만 | `AUTH-0063`, node는 quarantined, 감사 행 0 |
| **approved인데 투표 1건**(위조 행) | 승인 **수** 검사가 유일한 거부가 되는 상태 |
| **투표 2건인데 pending**(위조 행) | status가 투표의 결과임 |
| **요청자가 자기 요청에 투표**(위조 행) | 같은 사람은 두 사람이 아니다 |
| 같은 승인자 재투표 | `IDEM-0001`, 투표 수는 1 |
| `can_resume` 없는 actor 셋 | `AUTH-0062` |
| 만료 승인 · 없는 id · 무투표 approved · 위조 person | `AUTH-0063` · `RES-0004` |
| 다른 node 승인 · tenant 게이트(`clear`) 승인 | `AUTH-0063` |
| **다른 tenant의 승인(양방향)** | `RES-0004` "unavailable" |
| 키 없는(또는 201자) 호출 | `VAL-0003` |

## 3. 성공 경로가 고정하는 것

- 감사 행 **정확히 1건**(subject·reason·node·operation·`response.approvalId`), 소비된 승인이 그 `requestId`에 묶인다
- **원래 원인 보존**: `inv.build.node_quarantined` 레코드가 해제 뒤에도 그대로다(비교를 전후로 한다)
- 재시도 **멱등**(같은 키 → 같은 응답, 행 1건, `node_controls.version` 불변), 소비된 승인은 **다음 격리에 재사용 불가**
- 감사 행은 app role이 `UPDATE`·`DELETE` 불가

## 4. 일시 오류와 증명된 위반의 구분

`_record_preflight_unavailable`(RES-0006) 경로는 node를 **online으로 남기고** 다른 event를 적는다 → 해제할 것이 없고 `resume`은 `LEASE-0003`로 거부된다. 같은 시험이 그 뒤 제품 fence를 걸면 전체 ceremony가 다시 필요함을 확인한다. **변이로 전이 경로가 node를 fence하게 만들면 이 시험이 깨진다** — 그것이 이 구분을 지키는 방식이다.

## 5. 변이 — 내 시험의 세 구멍을 변이가 찾아냈다

제품을 **한 번에 하나씩** 변이시켜 해당 시험이 깨지는지 보았다. 처음 돌렸을 때 **7건 중 3건이 살아남았다**:

| 변이 | 처음 | 왜 가려졌나 | 지금 |
|---|---|---|---|
| 승인 수 `!= 2` → `< 1` | **살아남음** | 평범한 경로에서 투표 1건이면 status가 `pending`이라 **status 검사가 먼저** 거부한다 | `approved`인데 투표 1건인 행을 심어 사살 |
| 같은 사람 검사 삭제 | **살아남음** | 두 번째 투표가 애초에 기록되지 않아(challenge·IDEM 거부) `people` 집합이 쓰이지 않는다 | 요청자의 투표 행을 심어 사살 |
| status 검사 삭제 | **살아남음** | 투표 2건이 없으므로 **수 검사가 먼저** 거부한다 | 투표 2건을 `pending` 행에 심어 사살 |
| 다른 node 검사 삭제 | 사살 | | |
| `can_resume` 요구 삭제 | 사살 | | |
| 키 검사 삭제 | 사살 | | |
| 전이 경로가 fence하게 | 사살 | | |

**7/7 사살**이 된 것은 변이를 돌린 뒤다. 이것이 이 카드에서 가장 쓸모 있었던 측정이다 — 거부 코드가 같으면 시험은 통과하지만, **어느 검사가 그 거부를 냈는지**는 다르다.

## 6. 측정하다 알게 된 두 가지

1. **`inv.containment_votes`는 요청 이력과 같은 immutability 트리거를 쓴다.** 기록된 투표의 `person_id`를 소유자 권한으로도 **UPDATE할 수 없다**(`CheckViolation: Containment request history is immutable`). 그래서 위조는 INSERT로만 가능하고 응용이 다시 거부한다 — 시험이 두 사실을 모두 적는다.
2. **tenant 경계는 두 겹이다.** `inv.containment_approvals`의 RLS를 **끄고** 같은 호출을 다시 했더니 거부 사유가 `Containment approval unavailable` → **`Node control unavailable`** 로 바뀌었다: 승인이 보이게 되어도, 그 승인이 가리키는 **다른 tenant의 node**가 이 tenant의 범위에서 보이지 않아 다시 거부된다. 즉 시험은 load-bearing이고(정책을 없애면 사유가 바뀐다) 경계에는 두 번째 겹이 있다. (probe는 측정 후 지웠다. 제품·시험 변경 아님.)

## 7. 하지 않은 것

- **제품 코드를 고치지 않았다.** 변이는 전부 되돌렸다(`git checkout --`).
- 결함을 발견하면 고치지 않고 보고한다는 카드 규칙대로, §6의 두 관찰은 **보고**이고 변경이 아니다.
- `resume`의 실제 mTLS probe 경로는 다루지 않았다(§1).

## 8. 검증

| 항목 | 결과 |
|---|---|
| `tests/integration/test_quarantine_clear.py` | 실 PG **15 passed**(83s) |
| 제품 단독 변이 | **7/7 사살**(§5) |
| base | train 20 후보 위에서 시작해 **착지한 train 20(`364f73b0`)을 merge**(작업판 충돌은 최신 쪽으로) |

## 9. 다음 첫 행동

1. **Codex**: `#326` 검토 — 특히 §5의 "가려진 검사" 관점이 다른 ceremony(`kill`/`drain`)에도 적용되는지.
2. **Claude**: 검토 반영.
