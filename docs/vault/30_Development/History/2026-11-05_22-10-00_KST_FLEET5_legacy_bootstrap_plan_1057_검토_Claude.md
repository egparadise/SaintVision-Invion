---
doc_id: "HISTORY-FLEET5-20261105-LEGACY-BOOTSTRAP-PLAN-1057-REVIEW-CLAUDE"
title: "2026-11-05 FLEET5 legacy capability bootstrap plan 1057e0ed 독립 architecture 검토"
version: "1.0.1"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T22:20:18+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "c2102592"
task_ids: ["FLEET5-SETUP-INTEGRATION-20261105"]
tags: ["fleet5", "independent-review", "bootstrap", "plan", "claude"]
---

# legacy bootstrap plan 1057 검토

Orca task `task_03867932b2f0`, dispatch `ctx_37e3f120fac0`. [[2026-11-05_21-20-00_KST_FLEET5_legacy_peer_floor_감사와_binary_upgrade_경로_검토_Claude]]에서 낸 G1~G10을 owner가 실행하지 않는 plan으로 만들었고, 그 plan만 따로 판정한다. **P0 수정 code 수락이 아니다.** [[2026-11-05_21-55-00_KST_FLEET5_P0_code_6c0f_검토_Claude]]의 `6c0f` 미수락은 그대로다.

- **대상:** `agent/codex/fleet5-consecutive-leaf-rotation-20261105`의 `1057e0ed2e3c75d02e8ed342208fd78109cec2cd` (기준 `f0278daf`)
  - `1057e0ed:docs/vault/30_Development/History/2026-11-05_FLEET5_legacy_capability_bootstrap_plan_Codex.md`
  - `1057e0ed:docs/vault/30_Development/Evidence/fleet5-legacy-capability-bootstrap-plan-20261105/` 10개 JSON
  - non-docs 변경은 0개
- **비교한 source:** source03 `03e17c31`, B5 `b5b8ca68`, 2fb `2fb52bbe`, P0 후보 `6c0fc4ad`, 내 `f6817f3d`와 `c2102592`
- **읽은 방식:** Git object만 읽었다. 작성자 checkout은 읽지도 고치지도 않았다.
- **하지 않은 일:** helper, SSH, Docker, private key, guard, precheck, automation 실행. 공유 board, registry, Obsidian 수정. 다른 agent 사용
- **기계 판독 결과:** `Evidence/fleet5-20261105-claude/legacy-bootstrap-plan-1057-review.json`

## 문서 확인

| 항목 | 결과 |
|---|---|
| owner schema case 14개 (main `.venv` 3.14.7 `-B -I`, draft 2020-12) | **14/14 일치** |
| 내 적대적 변형 17개 | **17개 모두 거부**. 가짜 member binding, rootChoice B, channel CAS 허용, PC3 추가, PC 중복, 순서 뒤집기, ROLLBACK 상태 추가, 삭제 허용, 예전 plan 다시 켜기, 과거 deadline 사용, 실제 `6c0f` SHA를 p0SourceSHA로 넣기, 추가 key 등 |
| binding | target 27개, root 18개, member 이름 39개. **모두 null**. PC2와 PC4 binding도 null |
| acceptance | 24개 case가 G1~G10을 덮는다. **FUTURE, NOT RUN** |
| public source binding | 13개를 다시 계산했고 **13개 모두 같다** |
| blob 동일성 | `start-node.sh`, `permit.go`는 b5=2fb=03=6c. `main.go`는 6c에서 observer flag만 더했다. `journal.go`, `trust.go`는 03=6c |
| plan Docs 42029683097 | `1057e0ed`, job `docs` success. 내가 확인했다. 문서 gate일 뿐이다 |

## G2 — root 방향 A (plan용)

- source 사실:
  - `start-node.sh:42-50`: container 실행 image는 실제로 해석한 `actual_image`이고, `--image`는 manifest의 `agentImage`다.
  - `main.go:40`: `--image` → `Config.Image`
  - `permit.go:67`: `plan.ImageDigest != config.Image`면 NODE-0008. 이것은 workload permit 검사이며 Node 자신의 image 증명이 아니다.
  - `lan_pilot.py:855-856`은 전역 `agentImage`를 manifest로 복사하고, `1229-1234`는 build한 image를 그 field에 기록한다. 그래서 두 의미가 섞여 있다.
  - `worker_replace.py:105`는 `--image`를 manifest `agentImage`로 다시 만든다. permit 의미이므로 A와 맞는다.
- **판단:** A는 source와 맞는다.
  - 보존한 Cmd가 permit 의미를 지킨다.
  - 새로 typed, 인증된, 불변 per-Node `runtimeImageDigest`를 `preservedPermitImageDigest`와 따로 둔다.
  - 예전 CP `agentImage`와 manifest는 과거 기록과 기본값으로 byte를 고정한다.
  - inventory metadata CAS는 channel이나 leaf CAS가 아니다.
- **P0 호환:** `6c` `PeerFloorServingProcess`는 보존된 예전 Cmd를 받아들인다(`--image`, `--executable`, profile `lan-observe-v1`, `--serve` 하나, 정확한 state·cert·key·CA·signer 경로). M2 때문에 Cmd를 바꿀 필요가 없다.
- 운영 선택은 여전히 null이다. 방향은 실행 승인이 아니다.

## gate별 판단

| gate | 판단 |
|---|---|
| G1 | 타당하다. `Dockerfile.node`와 `.remote`는 `FROM scratch` + `ENTRYPOINT ["/inv-node"]`라서 image에서 물려받는 Config를 같게 유지할 수 있다(R4) |
| G2 | plan으로는 타당하다. consumer closure가 덜 됐다(R3) |
| G3 | 타당하다. `install_files`, prepare, repair, finish를 쓰지 않는다 |
| G4 | 타당하다. 정지 상태에서 fence한 서명 없는 double read는 bootstrap 전용 다리이고, 시작 뒤 `6c`의 서명 M2가 P/H, scope, active hash를 묶는다. 다만 `6c` host observer가 남겨 둔 backup consumer 때문에 막힌다(R1) |
| G5 | 타당하다. forward-only이고 아무것도 지우지 않는다. publication이나 pin 뒤에 예전 image를 다시 시작하거나 예전 policy를 되돌리지 않는다 |
| G6 | 타당하다. source가 뒷받침한다(`journal.go`, `trust.go`가 03→6c 그대로, observer 분기는 `OpenJournal` 전에 끝남). 실제 old/new no-write 증명은 여전히 필요하다 |
| G7 | 타당하다. 정확한 identity, P/H/C, authority, quiescence. host마다 있는 과거 Node 6개는 이름, label, Id, daemon으로 정확히 고른다 |
| G8 | 타당하다. `6c` `_plain(current=False)`가 이미 정지되고 restart=no인 predecessor를 요구한다. 새 container만 M2, mTLS, root 단계 뒤에 unless-stopped로 되돌린다 |
| G9 | scheduler는 타당하다. generic helper 실행 경로는 code로 막혀 있지 않다(R2) |
| G10 | 타당하다. product binding은 모두 null이다. `6c0f`는 수락되지 않았으므로(`c2102592`) HOLD가 맞다 |

## 발견

- **R1 (High, plan 도달 가능성):** OLD_PRESERVED와 NEW_CREATED 뒤에는 state volume의 consumer가 둘이다.
  - `6c0fc4ad:deploy/lan/worker_peer_floor.py`의 `target()`은 두 번째 consumer를 workspace predecessor일 때만 받는다. 조건은 `workspace-upgrade.json` phase ready, `ai.saintvision.upgrade` label, `agentImage` 일치다. 그런데 G1은 새 label을 금지한다.
  - 그래서 `6c` host observer로 하는 시작 뒤 M2와, 그 뒤의 모든 schema3 renewal(`worker_plain_rotation` → `target()`)이 **영구히 BLOCK**된다. backup은 절대 지우지 않기 때문이다.
  - **고칠 일:** migration journal에 묶인 typed migration-predecessor consumer 규칙을 정한다(정확한 backup ID와 이름, 정지, restart=no, 고정된 예전 inspect digest, 같은 volume). 고친 P0나 새 helper가 맡는다. GREEN(backup을 남긴 채 bootstrap 뒤 M2와 schema3 renewal 성공)과 RED(label만 있거나 기록되지 않은 두 번째 consumer) case를 더한다.
- **R2 (Medium):** `6c`의 `no_rotation_mutation`은 leaf-rotation 표지만 안다.
  - `repair-node.sh`, `Repair-Worker.ps1`, `worker_workspace`, storage bridge, `start-node`는 cutover 중에도, 끝난 뒤에도 실행할 수 있다. repair는 NEW_START_INTENT 전에 새 container를 `docker start`할 수 있다. workspace는 세 번째 consumer를 더하거나 downgrade할 수 있다.
  - G9는 scheduler만 막는다.
  - **고칠 일:** migration journal(끝나지 않은 상태와 끝난 상태 모두)을 기존 generic helper 전부를 막는 code 표지로 만들고 acceptance case를 더한다.
- **R3 (Medium):** G2의 "새 consumer는 typed record를 요구한다"는 기존 `agentImage` reader를 열거하기 전에는 닫히지 않는다.
  - 열거할 대상: `start-node.sh:11`, `worker_replace.py:105`(permit 의미, 괜찮음), `worker_workspace.py:164/215/249`, `worker_storage.py:293`, `worker_storage_bridge.py:38`, `lan_workspace.py:60-83`, `lan_pilot.py:1229-1234`, workspace package와 upgrade checker
  - 각각 막는지, 일관된지를 보여야 한다.
- **R4 (Low):** inspect 계약이 두 가지를 빠뜨렸다.
  - `6c` M2 관측의 `docker exec`가 만드는 `ExecIDs`를 열거하지 않았다. 정확한 observer exec에 묶어 열거해야 한다.
  - image에서 물려받는 Config(Entrypoint, Env, Labels, User, WorkingDir)가 같아야 한다는 요구가 없다. 새 image를 같은 `Dockerfile.node` 방식으로 만들고 image Config가 같아야 한다고 적어야 한다.
- **참고:**
  - schema가 null이 아닌 target binding을 모두 거부하므로, 값을 채운 후속 판은 새 schema version이 필요하다. 의도된 설계다.
  - r5 Node에 이미 workspace predecessor가 있으면 막힌다. observe 전용 범위에서는 맞는 fail-closed다.
  - PC2 다음 PC4이고, 첫 정지 전에 두 container를 모두 restart=no로 fence하는 순서는 일관된다. 차례를 기다리는 두 번째 예전 process가 restart=no로 계속 도는 것은 예전 binary 재시작이 아니다.
  - 21:14 automation 비활성화는 root가 알린 것이고 내가 검증하지 않았다. 아무것도 다시 켜지 않았다.

## 판정

| 구분 | 판정 |
|---|---|
| **plan** | **REVISION REQUIRED (범위 제한).** R1은 필수, R2~R4는 추가 사항이다. G2-A 방향, 상태 기계, forward-only 규칙, G1~G10 구조는 받아들일 만하다 |
| implementation | 없다. 수락하지 않는다 |
| P0 | `6c0fc4ad` NOT ACCEPTED(`c2102592`). 고친 code 검토는 따로 한다 |
| CI | Docs 42029683097은 문서 gate일 뿐이다. runtime CI는 받아들인 것 없음 |
| 운영 | HOLD. target 27개, root 18개, member binding이 null이다. 방향은 실행 승인이 아니다 |
| physical | 없음 |

## 다음 첫 행동과 담당

- **Codex(plan owner):** R1 migration-predecessor consumer 규칙, R2 helper fence, R3 consumer 목록, R4 inspect delta와 acceptance case를 더한 plan 개정판을 낸다.
- **`ctx_6f0f8253b8a7`:** P0의 B1, B2, F1~F3을 고친다. R1 규칙을 누가 맡을지 plan owner와 맞춘다.
- **root:** 개정 plan 검토와 수락된 P0 전까지 HOLD를 유지하고 G2 운영 선택을 null로 둔다.
- **Claude:** plan 개정판과 고친 P0가 오면 검토한다.

## 시간 기록 정정 (v1.0.1, 2026-11-05T22:20:18+09:00)

처음 판에 적은 관측 시각은 실제로 관측한 값이 아니었다. 이번 정정에서 바꾼 것은 시각뿐이다. 판정, 실행 결과, 발견은 바꾸지 않았고 Git history도 다시 쓰지 않았다.

- **처음 적은 값(무효):** Evidence `observedWindowKST` 21:58:00~22:10:00, header `updated` 22:10:00
- **무효인 이유:** declared start 21:58 precedes the brief (22:01:15) and belongs to the previous task; declared end 22:10 and History updated 22:10 are after the commit (22:09:11)
- **복원한 관측 구간:** 22:01:31~22:07:19 KST
  - brief 수신: 22:01:15
  - 첫 관측: 22:01:31 fetch plan branch
  - 마지막 관측: 22:07:19 plan Docs 42029683097 view result
  - Evidence 작성: 22:07:56-22:08:46
- **근거:** session transcript(`f3feb390-…jsonl`)를 읽기만 했다. tool 결과의 시각이며 초 단위 정밀도다.
- **공개 metadata (관측이 아님):** commit 830efd93 author/commit 2026-11-05T22:09:11+09:00; Docs 42033242038 created 22:09:18, completed 22:09:44 KST, success
- **파일 경로:** 경로에 든 시각은 인용이 깨지지 않도록 legacy ID로 그대로 둔다. 그 시각을 관측 시각으로 보면 **안 된다.**
- **`updated`:** 이 정정을 한 시각이다.
