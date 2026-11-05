---
doc_id: "HISTORY-FLEET5-20261105-LEGACY-BOOTSTRAP-PLAN-9E8E-REVIEW-CLAUDE"
title: "2026-11-05 FLEET5 legacy bootstrap plan 개정판 9e8e8c2f 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T23:03:41+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "dcff213a"
task_ids: ["FLEET5-SETUP-INTEGRATION-20261105"]
tags: ["fleet5", "independent-review", "bootstrap", "plan", "claude"]
---

# legacy bootstrap plan 개정판 9e8e 검토

Orca task `task_3c24efc159b8`, dispatch `ctx_9fe3a9741db8`. [[2026-11-05_22-25-00_KST_FLEET5_legacy_bootstrap_plan_cdef_검토_Claude]]에서 낸 R1, R2, R4, N1, N2에 답한 개정판 `9e8e8c2f`를 판정한다.

- **실행하지 않는 plan의 판정일 뿐이다.** P0 code, contract, runtime CI, 운영 수락이 아니다.
- f027 판정, architecture 판정, code 판정은 물려받지 않는다.
- **관측 시각:** 23:00:43~23:03:41 KST. 첫 fetch 호출과, 작성 전 마지막 source 확인의 shell `date` 출력이다. 이 파일 이름과 `updated`도 그 마지막 관측 시각이다.

## 대상과 방식

- **대상:** `agent/codex/fleet5-consecutive-leaf-rotation-20261105`의 `9e8e8c2f160c1b6cccc5ffec87d8917010a7df6a`
  - `cdeffee7..9e8e`: 20개 문서, +1236/−79. non-docs는 0개. plan History는 v1.0.2
  - `9e8e8c2f:docs/vault/30_Development/Evidence/fleet5-legacy-capability-bootstrap-plan-20261105/`
- **읽은 방식:** Git object만 읽었다. 작성자 checkout은 건드리지 않았다.
- **하지 않은 일:** product, helper, SSH, Docker, private, guard, precheck, scheduler, physical 작업. board, registry, Obsidian 수정. 다른 agent 사용
- **기계 판독 결과:** `Evidence/fleet5-20261105-claude/legacy-bootstrap-plan-9e8e-review.json`

## 문서 확인 (main `.venv` 3.14.7 `-B -I`)

| 항목 | 결과 |
|---|---|
| artifact hash | 주장 20개, **20/20 일치** |
| owner schema case | **26/26 일치** |
| 내 변형 | bool leaf 뒤집기 39개, null leaf에 digest 채우기 53개, 추가 key 6개. **98개 모두 거부** |
| binding | target 30개, root 18개, member 이름 60개. member envelope 2개는 null |
| encoding | E01~E03의 JSON hex, raw NUL hex, 두 SHA256, 엄격한 왕복, hash 영역 분리를 모두 재현했다 |
| encoding 음성 case | owner의 E04~E07은 receipt만 있고 입력이 공개되지 않아 fixture로 재현할 수 없다. 대신 내 음성 case를 돌렸다. lone surrogate, argv 안의 NUL, 잘못된 UTF-8, terminator 없음, overlong UTF-8은 거부된다. 마지막 빈 인자는 보존되고 NFC 정규화는 하지 않는다 |
| source case 9개 | 내가 `6c`에서 직접 확인했다(아래) |
| future product case | 36개. **NOT RUN** |
| plan Docs 42040204454 | root가 확인했다고 알려 왔다. 내가 다시 확인하지는 않았다 |

`6c0fc4ad`에서 확인한 source 사실:

- `FLOOR_KEYS`에 `servingExecutableSHA256`이 없다. domain은 v1이다(`peer_policy_phase.py:29`, `transport/peer_floor.go:18`).
- `PeerFloorServingProcess`는 SameFile을 확인한 뒤 raw cmdline의 sha256을 돌려준다.
- `worker_peer_floor.target`은 두 번째 consumer를 workspace 표지와 label이 있을 때만 받는다.
- `worker_leaf_rotation.py:90/94/1042/1087`이 `worker_peer_floor`의 observe, context, target에 닿는다.
- `no_rotation_mutation`과 `rotation_mutation_guard`는 leaf-rotation 표지만 안다.
- shell과 PowerShell wrapper는 guard를 직접 부르지 않는다.

## 앞선 발견의 처리

| ID | 상태 | 판단 |
|---|---|---|
| R1 | **plan 수준에서 해결** | 아래 참고 |
| R2 | **plan 수준에서 해결**, Low 잔여 C1 | 아래 참고 |
| R3 | 해결 | source03 범위에서 앞서 해결됐다. `6c` consumer는 R1에 포함됐다 |
| R4 | **plan 수준에서 해결** | 아래 참고 |
| N1 | **plan 수준에서 해결** | 아래 참고 |
| N2 | **plan 수준에서 해결**, Low 잔여 C2 | 아래 참고 |

- **R1:** journal에 묶인 typed predecessor다.
  - backup의 정확한 ID와 이름, 정지, restart=no, 정지·이름 변경 뒤에 고정한 inspect, 같은 volume을 묶는다.
  - current + predecessor 하나만 허용한다. label만 있거나, workspace만 있거나, 기록되지 않았거나, 세 번째인 consumer는 BLOCK이다.
  - bootstrap M2는 아직 쥐고 있는 migration lease와 start intent 아래에서 한다.
  - 이후의 normal:3는 terminal seal과 **새** common-fence lease 아래에서 한다.
  - backup의 정적 binding은 고정한다. 현재 cert, policy, P/H/C는 새로 서명된 M2와 현재 normal:3 세대와 비교하며, migration 기준값과는 절대 비교하지 않는다.
  - GREEN은 backup을 남긴 채 normal:3를 두 번 완료해야 한다.
- **R2:** 이름 있는 `agent_mutation_fence` API와 지속되는 표지를 둔다.
  - 끝나지 않은 상태와 끝난 상태 모두 generic mutator를 막는다.
  - 작업 전체에 걸쳐 logical 소유와 OS 소유를 쥔다.
  - raw, 패치하지 않은, 특권 호출은 관리 interface 밖이라 이 표지로 막을 수 없다고 정직하게 적었다. 그런 경로가 남아 있으면 G9는 HOLD다.
- **R4:**
  - 시작 전에 실제 ExecCreate ID를 기록한다. 처음 `ExecIDs`는 비어 있어야 하고, 이후에는 그 ID만 허용한다.
  - 물려받는 Entrypoint, Env, Labels, User, WorkingDir와 나머지 image Config가 모두 같아야 한다. container override로 차이를 가릴 수 없다.
- **N1:** schema `:2`와 domain v2에서 `/proc/<pid>/exe` bytes의 서명 hash를 필수로 한다. v1의 의미는 그대로 두며 새 증명을 대신할 수 없다. field가 없을 때 fallback도 없다.
- **N2:**
  - hash를 영역별로 따로 둔다: Cmd JSON, Entrypoint JSON, 전체 argv JSON, raw NUL cmdline.
  - terminator를 정확히 하나만 떼는 mapping과 엄격한 UTF-8을 쓰고, 정규화는 하지 않는다.
  - 서로 다른 hash 영역은 직접 비교하지 않는다.

**P0 호환 답변 `msg_03604b3e6bed`:** root가 전달했고, 내가 검증하지 않았다. `9e8` 공개 뒤에 왔으므로, `9e8`의 closure가 이 값을 null로 적은 것이 맞다. 답변 내용은 v2 executable field는 작업 중이고 R1과 fence는 앞으로의 구현에서만 호환된다는 것이다. 공개된 code는 없다.

## 남은 수정 (모두 Low, 다음 단계로 넘김)

- **C1:** fence 필수 entrypoint 목록에 legacy scheduler 경로가 빠졌다.
  - 빠진 것: `deploy/lan/Register-LeafRenewalTask.ps1`(`:102`에서 `Register-ScheduledTask`), `deploy/lan/Invoke-ScheduledLeafRenewal.ps1`, `tools/scheduled_leaf_renewal.py`. `b5b8ca68`과 `6c0fc4ad` 모두에 있다.
  - 이것으로 task를 다시 등록하면 비활성화된 ID 3개 밖에 새 실행 경로가 생긴다.
  - fence matrix와 G9 실행 경로 목록에 DENIED로 적어야 한다.
- **C2:** v2가 "기존의 정렬된 compact ASCII-escape JSON 규칙"을 그대로 쓴다고 했지만, 지금 두 쪽의 bytes가 같지 않다.
  - Go: `json.Marshal(map)`(`transport/peer_floor.go:72-73`)은 key를 정렬하지만 `<>&`를 HTML escape하고 비 ASCII는 raw UTF-8로 낸다.
  - Python: `json.dumps(sort_keys, ensure_ascii=True)`(`peer_policy_phase.py:34`)로 검증한다.
  - 지금은 fail-closed다. v2는 producer와 verifier가 같은 bytes를 만드는 표준형 하나를 정하거나, 두 방식이 겹치는 문자 집합으로 field를 제한하고, 언어 간 fixture를 둬야 한다.
- **C3:** 재진입이 적혀 있지 않다. predecessor는 하나만 허용되고 지우지 않으므로, seal된 Node에서 두 번째 binary migration을 할 길이 없다. 두 번째 migration은 따로 검토한 설계가 나올 때까지 BLOCK이고, predecessor 교체나 회전도 없다고 적어야 한다.
- **참고:**
  - R4의 "처음 `ExecIDs`는 비어 있다"는, 끝난 exec를 container 목록에서 빼고 ExecInspect는 남기는 Engine과 맞는다. plan이 이를 고정된 Engine version fixture로 미룬 것은 맞다. 나는 이것을 검증하지 않았다.
  - root의 RS1/SF1 방향(`msg_87edde1811d5`)은 별개다. `9e8`은 그 방향에 migration consumer 종류를 더하지 않았다.
  - G2-A는 planning 전용이다. 예전 `--image` permit과 전역 CP `agentImage`의 의미는 그대로다.

## 판정

| 구분 | 판정 |
|---|---|
| **plan `9e8e8c2f`** | **ACCEPT (실행하지 않는 plan).** R1, R2, R4, N1, N2는 plan 수준에서 해결됐다. C1~C3은 구현 contract로 넘길 Low 조건이다 |
| implementation | 없다(root가 전달한 P0 답변도 그렇다). 수락하지 않는다 |
| contract | M2 v2 wire, migration journal, common fence, runtime inventory는 binding이 null인 제안이다. 수락하지 않는다 |
| P0 | `6c0fc4ad` NOT ACCEPTED. 고친 P0 검토는 따로 한다 |
| runtime CI | 받아들인 것 없음. future case 36개는 NOT RUN이다 |
| 운영 | HOLD. 모든 binding이 null이다 |
| physical | 없음 |

## 다음 첫 행동과 담당

- **root:** C1~C3을 조건으로 붙여 plan ACCEPT를 반영한다. binding은 null로, 운영은 HOLD로 둔다.
- **Codex(plan owner):** C1~C3을 다음 contract 개정이나 구현 card에 넣는다.
- **`ctx_6f0f8253b8a7`:** 고친 P0를 낸다(B1, B2, F1~F3, v2 executable field, C2 표준형).
- **Claude:** 고친 P0가 오면 검토한다.
