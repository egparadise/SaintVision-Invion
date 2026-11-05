---
doc_id: "HISTORY-FLEET5-20261105-LEGACY-BOOTSTRAP-PLAN-CDEF-REVIEW-CLAUDE"
title: "2026-11-05 FLEET5 legacy bootstrap plan 개정판 cdeffee7 독립 architecture 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T22:25:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "830efd93"
task_ids: ["FLEET5-SETUP-INTEGRATION-20261105"]
tags: ["fleet5", "independent-review", "bootstrap", "plan", "claude"]
---

# legacy bootstrap plan 개정판 cdef 검토

Orca task `task_03867932b2f0`, dispatch `ctx_37e3f120fac0`. root의 `msg_7b5f8be7e2ba`에 따라, `1057`을 대체하는 개정판 `cdeffee7`와 `1057..cde` delta를 같은 task 안에서 판정한다.

- [[2026-11-05_22-10-00_KST_FLEET5_legacy_bootstrap_plan_1057_검토_Claude]](`830efd93`)의 `1057` 판정과 발견 R1~R4는 그대로 둔다. 이 문서는 그것을 다시 쓰지 않고 `cde`에서의 상태만 더한다.
- **plan 판정일 뿐이다.** P0 수정 code, contract, 운영 수락이 아니다.

## 대상과 방식

- **대상:** `agent/codex/fleet5-consecutive-leaf-rotation-20261105`의 `cdeffee72f0480dc2df543bb3b49c87ebc95a570`
  - 13개 파일, +608/−74. non-docs는 0개
  - 새 파일: `cdeffee7:docs/vault/30_Development/Evidence/fleet5-legacy-capability-bootstrap-plan-20261105/legacy-consumer-closure.json`, `root-g2-planning-choice.json`, `runtime-inventory-contract.json`
  - `inspect-comparison-contract.json`은 바뀌지 않았다
- **읽은 방식:** Git object만 읽었다. 작성자 checkout은 읽지도 고치지도 않았다.
- **하지 않은 일:** helper, SSH, Docker, private key, guard, precheck, automation 실행. 공유 board, registry, Obsidian 수정. 다른 agent 사용
- **기계 판독 결과:** `Evidence/fleet5-20261105-claude/legacy-bootstrap-plan-cdef-review.json`

## 문서 확인

| 항목 | 결과 |
|---|---|
| owner schema case (main `.venv` 3.14.7 `-B -I`) | **16/16 일치** |
| 내 적대적 변형 | **20개 모두 거부**. `cde`에서 새로 더한 것: planning message로 `reviewedContractBinding` 채우기, 같은 message로 `rootG2Decision` 채우기, `implementationAuthorizedOnThisCard=true` |
| binding | target 30개, root 18개, member 이름 52개. **모두 null** |
| acceptance | 28개(A25~A28 추가). **FUTURE, NOT RUN** |
| public source binding | 27개를 다시 계산했고 **27개 모두 같다** |
| plan Docs 42032726002 | `cdeffee7`, 모든 job success. 내가 확인했다. 문서 gate일 뿐이다 |

## delta 판단

- **root G2 planning 선택(`msg_f517e89d6a16`):** planning 전용으로 기록됐다. schema가 다음을 지킨다.
  - `operationalAcceptance`와 `implementationAuthorizedOnThisCard`는 false
  - `reviewedContractBinding`과 `rootG2Decision`은 null
  - root 방향 A(plan용)와 맞는다.
- **typed image field:** 다음 항목을 서로 다른 값으로 둔다. 타당하다.
  - Docker image Id, RepoDigest, platform manifest, config digest, 순서 있는 diffID, archive SHA256, executable SHA256, source Git SHA
  - "image Id는 흔히 config digest"라는 설명은 `6c0fc4ad:tools/lan_pilot.py:564-600`이 classic store와 containerd store를 다루는 방식과 맞는다.
  - offline으로 RepoDigest가 없을 때는 인증된 archive와 build mapping을 요구한다.
- **owned inspection join:** M2 전후에 소유한 daemon으로 inspect하고, 그것을 서명된 M2와 공개된 build에 묶는다. process hash만으로는 image를 증명하지 않는다. 타당하다.
- **argv와 authority 동일성:**
  - 정확한 배열과 순서 있는 hash를 쓴다. Entrypoint와 실제 PID1 argv는 따로 본다.
  - typed DER, SPKI, raw hash를 쓴다.
  - private key는 local 보호 tree가 같은지로만 확인한다.
  - 타당하다.
- **legacy consumer closure:** source03의 reader와 producer를 BLOCK, EXCLUDED, PRESERVE로 분류했다. 전역 `agentImage`로 되돌아가는 경로는 없다.

## `1057` 발견의 `cde` 상태

| ID | 상태 | 내용 |
|---|---|---|
| R1 | **OPEN** | `6c0fc4ad:deploy/lan/worker_peer_floor.py`의 `target()`은 여전히 두 번째 consumer를 label이 붙은 workspace predecessor일 때만 받는다. closure는 source03 범위라 `worker_peer_floor`와 `worker_plain_rotation`이 빠졌다. 그래서 남겨 둔 backup 때문에 `6c` observer로 하는 시작 뒤 M2와 이후의 모든 schema3 renewal이 BLOCK된다 |
| R2 | **PARTIAL** | closure가 "reservation부터 legacy mutator를 막는 새 code guard"를 요구한다. 그러나 기존 helper가 실제로 확인하는 장치(`6c` `no_rotation_mutation`은 leaf-rotation 표지만 안다)를 정하지 않았다. JSON에 `repair-node.sh`, `Repair-Worker.ps1`, `prepare-worker.sh`, `finish-worker.sh`도 없다 |
| R3 | **CLOSED** (source03 범위) | `6c`가 더한 consumer는 R1에 합친다 |
| R4 | **OPEN** | inspect 계약이 그대로다. join이 M2 뒤의 안정된 inspect를 요구하는데도 `6c` M2의 `docker exec`가 만드는 `ExecIDs`를 열거하지 않는다. image에서 물려받는 Config는 config digest로 간접적으로만 묶인다 |

## 새 발견

- **N1 (Medium):** join은 "서명된 실제 process executable SHA256이 공개된 executable hash와 같다"를 요구한다. 그러나 `6c0fc4ad`의 M2는 그런 값을 내지 않는다.
  - `peer_policy_phase.py`의 `FLOOR_KEYS`에 있는 `servingProcessSHA256`은 `PeerFloorServingProcess`가 만든 **raw `/proc/<pid>/cmdline`의 sha256**이다.
  - executable 동일성은 `SameFile(/proc/<pid>/exe, /proc/self/exe)`로만 증명한다.
  - executable bytes hash는 어디에도 없다.
  - **고칠 일:** 고친 P0가 `/proc/<pid>/exe` bytes의 sha256을 서명하게 하거나, join을 "SameFile 증명 + 읽기 전용 image rootfs의 `/inv-node`에 대한 owned inspection"으로 정의한다. `m2WireContractSHA`를 묶을 때 명시적으로 mapping한다.
- **N2 (Low):** argv hash 정의가 둘이다.
  - plan: canonical UTF-8 JSON argv 배열의 SHA256
  - `6c`: raw NUL 구분 cmdline의 SHA256
  - 둘을 모두 이름 붙이고 mapping을 적어야 한다. 서로 직접 비교하면 안 된다.

## 판정

| 구분 | 판정 |
|---|---|
| **plan `cdeffee7`** | **REVISION REQUIRED (범위 제한).** 필수: R1, N1 mapping. 추가: R2 부분, R4, N2. R3은 source03 범위에서 해결됐다. G2-A 방향, typed image 의미, owned-inspection join, argv와 authority 동일성, consumer closure 구조, G1~G10은 받아들일 만하다 |
| implementation | 없다. 수락하지 않는다 |
| P0 | `6c0fc4ad` NOT ACCEPTED(`c2102592`) |
| contract | runtime inventory, M2 wire, 인증 계약이 null이다. 수락하지 않는다 |
| CI | Docs 42032726002은 문서 gate일 뿐이다. runtime CI는 받아들인 것 없음 |
| 운영 | HOLD. target 30개, root 18개, member envelope 2개가 null이다. root 방향 A는 planning 전용이다 |
| physical | 없음 |

## 다음 첫 행동과 담당

- **Codex(plan owner):** 다음을 고치고 acceptance case를 더한다.
  - R1: journal에 묶이고 label을 쓰지 않는 typed migration-predecessor consumer 규칙을 `6c` observer와 renewal 범위에 둔다
  - N1: executable 증명 mapping
  - R2: helper fence 장치 이름과 helper 목록
  - R4: `ExecIDs`와 image Config
  - N2: argv hash mapping
- **`ctx_6f0f8253b8a7`:** P0의 B1, B2, F1~F3을 고친다. M2에 executable bytes hash(N1)와 migration-predecessor 규칙(R1)을 넣을지 plan owner와 정한다.
- **root:** HOLD를 유지하고 contract와 운영 G2 binding을 null로 둔다.
- **Claude:** 다음 plan 개정판과 고친 P0가 오면 검토한다.
