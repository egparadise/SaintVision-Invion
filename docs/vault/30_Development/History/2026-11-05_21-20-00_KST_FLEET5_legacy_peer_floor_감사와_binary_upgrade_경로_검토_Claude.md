---
doc_id: "HISTORY-FLEET5-20261105-LEGACY-PEER-FLOOR-AUDIT-REVIEW-CLAUDE"
title: "2026-11-05 FLEET5 Codex legacy peer-floor 호환 감사 f0278daf 독립 검토와 binary-only upgrade 경로 평가"
version: "1.0.1"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T22:26:17+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "f012b206"
task_ids: ["FLEET5-LEGACY-PEER-FLOOR-COMPAT-20261105"]
tags: ["fleet5", "independent-review", "node-agent", "leaf-rotation", "bootstrap", "claude"]
---

# legacy peer-floor 감사 f0278daf 검토와 binary-only upgrade 경로

Orca task `task_cfafb7eac65c`, dispatch `ctx_a2e0601680de`.

**판정은 둘로 나눈다.**

1. Codex 감사 보고서에 대한 source 판정
2. 지금 공개된 source에 binary-only upgrade 경로가 있는지에 대한 architecture 입력. 이것은 **승인도 구현도 아니다.**

- **대상:** `agent/codex/fleet5-consecutive-leaf-rotation-20261105`의 최신 `f0278daffa616cae4485e4b1d4c07671715892dc`
  - 이전 commit: `83ec7b84`, `b57e4e38`, `9ec6d6bf`
  - 감사 보고서: `f0278daf:docs/vault/30_Development/History/2026-11-05_FLEET5_legacy_peer_floor_compat_Codex.md` v1.0.2
- **읽은 방식:** Git object만 읽었다. hash는 내 독립 script로 다시 계산했다. 이 script는 commit하지 않았고 sha256은 `eb29d6f3…`이다. Codex의 `audit_public_sources.py`는 실행하지 않았다.
- **root 문서:** 공유 Obsidian의 root Index 1.0.406과 Codex board 1.0.367(둘 다 20:43:53 KST)을 읽기만 했다.
- **하지 않은 일:**
  - production이나 source 수정
  - private config, key, PKI, SSH, host Docker, WSL, runtime 접근
  - schedule, guard, claim, clock 변경
  - B5 plan과 command 본문, task 정의, 실행 기록 열람
  - 공유 board, registry, Obsidian apply
  - 다른 agent 사용
- **기계 판독 결과:** `Evidence/fleet5-20261105-claude/legacy-peer-floor-audit-f027-review.json`

## 1. 보고서와 artifact의 결속

- **non-docs 변경 0건:** `2fb52bbe..f0278daf`의 변경 13개 파일은 모두 `docs/` 아래다. 받아들여진 2fb source는 그대로다. Index, Agent board, task registry도 바뀌지 않았다.
- **artifact hash:** 내가 계산한 Git blob sha256이 `validation.json`에 기록된 값과 같다.
  - `audit_public_sources.py`: `c5ca500f…`
  - `public-source-index.json`: `a5d59467…`
  - `findings.json`: `bf5628ae…`
  - `document-gates.log`: `04bfbe95…`
- **root HOLD policy:** `root-technical-hold-20261105.json`의 blob sha256은 **`74560bbda92a3f736105b470c07b4856d12312f5192888fae2297f3e40c2f7ea`**로 brief와 같다. `root-technical-hold-validation.json`의 `policySHA256`도 같다.
- **Docs CI:** run 42023306438은 `headSha=f0278daf`에서 completed **success**였다. 내가 직접 조회했다.
- **gate:** 기록된 gate는 freeze diff, check_docs, citation ratchet, ontology, sync-check, diff-check이고 모두 exit 0이다. 나는 이 gate를 작성자 worktree에서 다시 돌리지 않았다. 대신 freeze 범위를 Git diff로 직접 확인했다.

## 2. source 동등성 (내가 다시 계산함)

대상 commit은 다섯 개다: source03 `03e17c31`, executorB5 `b5b8ca68`, 2fb `2fb52bbe`, nativeFe7 `fe7ebeff`, 보고 `5023ce7d`. 비교를 위해 감사 commit `f0278daf`도 함께 계산했다.

| 대상 | 결과 |
|---|---|
| `journal.go` `0bf50af7…`, `trust.go` `3b5dd89f…`, `main.go` `e4f88038…`, `worker_config.py` `bb2b750a…` | 여섯 commit 모두 **같은 bytes** |
| Python `_write_rotation_public_material` | 여섯 commit 모두 **`2509bb185dbbc1115af55916df240843f089bdfc9c872a127143f9fc732cd99f`** |
| `prepare_leaf_rotation` `afe9b85e…`, `_policy` `47a27a80…`, `docker_restart` `c9620cea…` | 모두 같다 |
| worker의 `rollback` slice | 여섯 commit 모두 `77f335c9…`로 같다. 보고서에는 없는 항목이고 내가 추가로 확인했다 |
| Go `PinPeerPolicy` `64016481…`(341행), `Authority.policy` `ced012c7…`(67행) | 같다. 보고서의 끝 공백 제거 규칙을 따라 재현했다 |
| source03/B5 helper `bca76df8…`, `install` `c8aef68a…`, `finalize` `4b1fa4f8…`, CP `1a8ccbc5…` | 같다. 2fb부터는 lifecycle code가 바뀌었지만 위의 producer, validator, rollback slice는 같다 |
| `observe-peer-policy-floor` 문자열 | 여섯 commit 모두 `services/` 어디에도 없다 |

**call graph** (source03 기준):

- `lan_pilot.py:2670`: batch가 Node마다 `prepare_leaf_rotation(child)`를 부른다.
- `2840` 함수의 2991~3006행: `final_policy = {**overlap_policy, expiresAt, clientFingerprints}`이다. 따라서 final의 version은 overlap과 같은 `C+1`이다.
- worker: `_policy` 199행, `install` 508행, `finalize` 621행, `rollback` 678행, `docker_restart` 743행
- Go: flag 집합에 observer가 없다(`main.go:26` `run()`).

보고서의 "line2590"은 batch 함수가 시작하는 행이다(2588행). 실제 호출은 2670행에 있다. 의미에는 영향이 없다.

**B5 executor** (`b5b8ca68:tools/scheduled_leaf_renewal.py:483-616`): 순서는 보고서와 같다. currentStatus → runtimePreflight → attempt intent → prepare → install·stage → commit → transition → observe → finalize 각각 → finalObserve → 새 leaf 확인. 실패하면 latch가 `failed`가 되고, 그 뒤 실행은 `recovery-required`(exit 2)로 멈춘다. 자동 rollback 호출은 없다. 단, 설정된 command 본문은 읽지 않았다.

## 3. 감사 판정

**`f0278daf` 감사: ACCEPT (source 판정, 아래 주의 포함).**

- 받아들이는 주장:
  - 공개된 03/B5 normal v1 경로가 그대로 실행되면, 확인된 native 실패(같은 `C+1`, 다른 raw hash, NODE-0041)를 물려받는다.
  - 예전 main에는 observer가 없다.
  - side-load한 observer, host 사본, 서명 없는 JSON은 M2가 될 수 없다.
  - 실제 private 실행이나 live 실패는 추론하지 않는다.
  - root의 20:34 snapshot은 범위가 제한된 현재 metadata일 뿐이다.
- root HOLD 기록(`msg_996ef241a877`)의 범위도 정확하다.
  - 예전 callback은 read, evaluate, report HOLD만 한다.
  - RunNow와 legacy phase 실행은 없다.
  - 저장된 schedule 3개는 **바뀌지 않았다**. "disabled"라고 주장하지 않는다.

## 4. source에서 나온 주의 (보고서를 보강함)

- **C1 (Medium, 운영 판단): HOLD는 문서와 callback 차원의 gate일 뿐이고 실행 코드에는 걸려 있지 않다.**
  - B5 executor와 `Invoke-ScheduledLeafRenewal.ps1`에는 hold나 disable을 읽는 경로가 없다.
  - 막는 장치는 renewal window(`renewAt` 이전이면 `outside-window`, 변경 없음), 이전 실패 latch, lock뿐이다.
  - 저장된 schedule이 이 executor를 **직접** 호출한다면, window가 열린 뒤에는 HOLD가 실행을 막지 못한다. HOLD 문서를 읽는 agent callback을 거칠 때만 막힌다.
  - 나는 schedule 정의를 보지 않았다. root는 읽기만으로 다음 두 가지를 확인해야 한다. (a) 저장된 3개가 무엇을 호출하는가. (b) 각 window가 언제 열리는가.
- **C2:** 03/B5 worker의 `rollback()`은 2fb와 같은 slice다(`installing`·`installed`·`restarted` phase에서 version P backup을 복원한다). legacy 경로에서도 overlap pin 뒤에 rollback하면 Node가 시작하지 못한다. 앞선 M5와 같은 결함이다. HOLD와 "예전 policy 복원 금지"가 이 위험을 덮는다.
- **C3:** 예전 container는 `--restart unless-stopped`로 만들어졌다(`f0278daf:deploy/lan/start-node.sh`). 그래서 host나 daemon이 재시작하면 예전 binary가 자동으로 다시 시작된다. 이것은 HOLD로 막을 수 없다.
  - source상으로는 active policy bytes가 floor hash와 같으면 같은 bytes replay라서 받아들여진다. 그래서 floor 위험은 없다.
  - root snapshot(floor1, hash == active)이 맞다면 지금은 무해하다. 하지만 서명된 보장은 아니다.
- **C4:** "예전 binary restart 금지"는 보수적인 정책이다. source상 위험은 active ≠ floor일 때만 생긴다. 이 정책을 약하게 하자는 뜻은 아니다.

## 5. 지금 공개된 binary-only upgrade 경로 평가 (architecture 입력)

**결론: 지금 공개된 source에는 정확한 observe profile을 유지한 채 Go image만 바꾸는 경로가 없다.** 아래 helper는 어느 것도 이 목적에 쓸 수 없다.

| helper (`f0278daf:deploy/lan/…`, 1e64도 같은 결론) | 하는 일 | 쓸 수 없는 이유 |
|---|---|---|
| `start-node.sh` / `finish-worker.sh` | 새로 설치 | container가 있으면 거부한다. 새 CSR, bundle policy 복사, install-files를 한다 |
| `prepare-worker.sh` | 설치 준비 | bundle의 `peer-policy.json`을 host worker_root에 **덮어쓰고** 새 CSR을 만든다. credential rotation에 해당한다 |
| `repair-node.sh` / `Repair-Worker.ps1` | 같은 container를 다시 시작 | image를 바꾸지 않는다. host 사본 5개를 `/state`에 **다시 복사**하므로 active policy를 바꿀 수 있다. **예전 binary를 restart**한다 |
| `worker_workspace.py` (R4) | agent image 교체 | profile이 `lan-workspace-v1`으로 바뀐다. `--image`는 workload로, `--executable`은 python3로 바뀐다. docker.sock bind가 붙는다. install_files로 다시 복사한다. **실패하면 자동으로 예전 container로 되돌린다.** 정확한 observe 유지와 "자동 downgrade 금지"를 모두 어긴다 |
| `worker_replace.py` + `worker_replacement.py` (Replace-Storage) | 정지된 observe Node를 앞으로만 교체 | **storage가 필수다**(`--storage-policy`, storage mount, `storage.install`, `storage.current(plan)`). plain 경로에서는 금지된 B 범위다 |

`worker_replace.py`에는 **그대로 가져다 쓸 통제**가 있다.

- `restart=no` 펜스, backup 이름 변경, 같은 volume, consumer 정확 일치, volume metadata hash
- 정지 상태에서 `/state` 전체를 두 번 읽어 만든 digest(`journal/identity.json`과 credential 5개의 0:0/0600 포함)
- 앞으로만 가는 phase journal(`prepared`→`fenced`→`renamed`→`created`→`installed`→`starting`→`ready`)
- "Starting may persist a new floor. Never restore the old policy/container"
- credential을 다시 복사하지 않는다

자원 한계와 보안 설정(`--read-only`, cap-drop ALL, no-new-privileges, pids 128, 256m, 0.5 cpu)은 모든 경로에서 같다.

**최소 gap과 필요한 통제** (root가 non-executing bootstrap plan을 쓸 때의 입력):

- **G1 정확한 profile 유지:**
  - 예전 container inspect 전체를 고정한다. 새 container는 Image만 달라야 한다. Cmd, Mounts, Labels, PortBindings, 자원, 보안 설정은 같아야 한다.
  - `--storage-policy`나 `/state` 밖의 mount가 있으면 BLOCK한다. storage Node는 plain 경로에서 제외한다.
  - storage 없는 모드를 `worker_replace`에 덧붙이거나 별도 helper를 만들어야 한다. 지금은 없다.
- **G2 `--image` 인자 결정이 필요하다:**
  - observe profile에서 `--image`는 manifest의 `agentImage`이고, Go `permit.go:67`이 `plan.ImageDigest == config.Image`로 쓴다.
  - 새 image를 넣으면 이 인자가 바뀐다. 그러면 CP state의 `agentImage`(`lan_pilot.py:855`, 1233)도 함께 바뀌어야 한다.
  - 인자를 예전 digest로 두면 실제 실행 image와 맞지 않는다.
  - 어느 쪽이든 명시적으로 검토된 결정이 필요하다. channel CAS가 아니라 CP 기록 갱신이며, 이것도 receipt로 결속해야 한다.
- **G3 credential을 다시 복사하지 않는다:** `install_files`, `repair-node`, prepare/finish를 쓰지 않는다. 기존 volume bytes를 그대로 쓴다. host 사본은 읽어서 대조만 한다.
- **G4 bootstrap 전 floor 증거의 한계:**
  - 예전 binary는 M2를 제공할 수 없다. 그래서 cutover 전 증거는 정지(fence) 상태에서 operator가 volume을 두 번 읽은 것뿐이다(`worker_replacement.capture` 방식). 이것은 **서명되지 않은 operator 관측**이다.
  - 그 (P, H)를 replacement record에 결속한다.
  - 새 binary가 시작한 뒤의 M2 증명(nonce, 같은 실행 파일, UID, PID1, 실제 journal)이 같은 (P, H)와 active hash를 보여야 한다. 아니면 BLOCKED이며, downgrade는 없다.
- **G5 앞으로만 간다:** 예전 container를 자동으로 다시 시작하거나 downgrade하지 않는다. 예전 policy 복원, floor·latch reset, expiry 우회도 없다. 실패하면 두 container와 volume을 보존하고 BLOCKED로 둔다(`worker_replace` 방식).
- **G6 journal 호환성:**
  - 새 binary가 기존 journal 형식을 바꾸지 않고 읽는다는 것을 증명해야 한다. 시작 전과 후의 protected-state digest가 같아야 하고, 같은 bytes replay에서는 아무것도 쓰지 않아야 한다.
  - 형식 migration이 필요하면 별도로 검토한다.
- **G7 범위 고정:**
  - P, H, C, Node key, cert, CA, signer.pub, identity가 바뀌지 않는다.
  - channel CAS도, CP leaf 변경도 없다.
  - idle 확인이 필요하다(owned workload 0).
  - 정확한 r5 container만 대상이다. host마다 과거 container 6개가 있으므로 이름, label, Id로 고정한다.
- **G8 restart policy:** replacement는 `restart=no`로 끝난다. `unless-stopped`로 되돌리는 것은 mTLS 확인과 M2 증명 뒤의 명시적 단계로 둔다.
- **G9 HOLD 실효성:** cutover 동안 저장된 schedule이 executor를 직접 실행할 수 없음을 root가 먼저 확인한다(C1).
- **G10 provenance:**
  - P0 source와 binary의 CI provenance가 필요하다: image layer와 config, `imageLayers`/`imageConfig` manifest, 재현 build.
  - native Go 2 cycle 녹색과 M2 no-write·no-`OpenJournal` test가 이 plan보다 먼저 있어야 한다.

## 판정

| 항목 | 판정 |
|---|---|
| `f0278daf` legacy 감사(source, artifact, gate, HOLD 범위) | **ACCEPT**. 주의 C1~C4 |
| 지금 공개된 binary-only 경로 | **없음 (gap)**. 최소 통제는 G1~G10 |
| CI와 physical acceptance | 없음. Docs 42023306438 success는 문서 gate일 뿐이다. native 증명은 여전히 의도된 red다 |
| 앞선 `f012` P0 architecture 수락 | 이 bootstrap이나 미래 구현을 **포함하지 않는다** |

## 다음 첫 행동과 담당

- **root:**
  - C1에 따라 저장된 3개 schedule이 무엇을 호출하는지와 각 window가 열리는 시각을 읽기만으로 확인한다.
  - P0 binary와 source의 CI provenance, native 녹색이 나온 뒤 G1~G10을 반영한 non-executing bootstrap/replacement plan을 쓴다. 특히 G2(`--image`와 CP `agentImage`)를 결정한다.
  - 그 plan은 독립 검토를 받는다.
- **P0 owner `ctx_6f0f8253b8a7`:** M1~M10을 구현한다. G6(journal 호환, no-write replay)을 test로 증명한다.
- **Codex:** 이 감사에 추가로 할 일은 없다. 선택 사항으로 보고서의 "line2590" 표기를 2670으로 고친다.
- **Claude:** bootstrap plan과 P0 구현이 오면 독립 검토한다.

## 시간 기록 정정 (v1.0.1, 2026-11-05T22:26:17+09:00)

처음 판에 적은 관측 시각은 실제로 관측한 값이 아니었다. 이번 정정에서 바꾼 것은 시각뿐이다. 판정, 독립 test, source 판단은 바꾸지 않았고 Git history도 다시 쓰지 않았다.

- **처음 적은 값(무효):** Evidence `observedWindowKST` 21:00:00~21:20:00, header `updated` 21:20:00
- **무효인 이유:** declared start 21:00 precedes the brief (21:01:32); declared end 21:20 and History updated 21:20 are after the commit (21:10:24) and Docs completion (21:11:10), so they were not observed
- **복원한 관측 구간:** 21:01:40~21:08:44 KST
  - brief 수신: 21:01:32 (task_cfafb7eac65c / ctx_a2e0601680de)
  - 첫 관측: 21:01:40 fetch audit branch (result 21:01:59)
  - 마지막 관측: 21:08:44 worker_replace invocation trace result
  - 작성: History 21:08:23, Evidence 21:09:33-21:09:37
- **근거:** 내 session transcript(`f3feb390-…jsonl`)의 metadata만 읽었다. tool 결과의 시각이며 초 단위 정밀도다.
- **공개 metadata (실행 시각으로 쓰지 않음):** commit f6817f3d author/commit 2026-11-05T21:10:24+09:00; Docs 42024928449 created 21:10:40, completed 21:11:10 KST, success
- **본문의 다른 시각:** '20:43:53 KST' in the body is the read board documents' own version time, not an observation time
- **파일 경로:** 경로에 든 시각은 인용이 깨지지 않도록 legacy ID로 그대로 둔다. 그 시각을 관측 시각으로 보면 **안 된다.**
- **`updated`:** 이 정정을 한 시각이다.
- **범위:** 이 검토와 짝 검토(`f6817f3d`, `45bc23cb`)만 감사했다. 그보다 앞선 검토의 시각은 여전히 검증되지 않았다.
