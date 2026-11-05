---
doc_id: "HISTORY-FLEET5-20261106-B-PROPOSAL-100F-ARCH-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 Broad B proposal 100f6f13 독립 아키텍처 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T02:45:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "60bfc722"
task_ids: ["FLEET5-COMPUTE-STORAGE-CONTRACT-20261105"]
tags: ["fleet5", "independent-review", "architecture", "storage", "renewal", "claude"]
---

# Broad B proposal 100f 독립 아키텍처 검토

Orca task `task_3516267fa05f`, dispatch `ctx_42a6dd5132c6`. owner는 Codex `task_a8fd2969f0b3 / ctx_6f0f8253b8a7`이다. 대상은 owner branch `agent/codex/fleet5-compute-storage-contract-20261105`의 `History/2026-11-06_FLEET5_B_role_storage_contract_proposal_Codex.md`(100f, 이 base에는 아직 없음)와 `Evidence/fleet5-compute-storage-contract-20261105-codex/b-after-p0-proposal/`다. Root 추가 질문 `msg_be023606185f`(Windows CP daemon source)에도 답한다.

- **판정: REVISION REQUIRED.** 방향은 맞다. 같은 C·ChannelProof 재사용, 두 번째 storage counter 없음, 별도 role floor :3·leaf :4, plain :2/:3과 R4 기본 거부 유지는 4f source와 일치한다. 다만 아래 B1–B5는 Root가 ABI를 확정하기 전에 proposal에서 닫아야 한다.
- **관측 시각:** probe 02:31:59–02:32:00 KST, pytest 02:36:01–02:36:04 KST, hash snapshot 02:38:18 KST. 이 host의 Git Bash는 `TZ=Asia/Seoul`을 반영하지 않으므로 UTC `date` 값에 +9h를 했다.
- **기계 판독 결과:** `Evidence/fleet5-20261105-claude/b-proposal-100f-review.json`

## 대상과 범위

- **대상:** `100f6f132132199d1204a76190f04712dd82de00`. 부모는 `3af3334e`이다. 13개 파일, 모두 docs/vault이며 +2230이다. runtime 기준은 4f97ba71이다.
- **source Docs:** run `42074468349`, job `127410856859` docs success. head는 정확히 100f, 02:25:26–02:25:59 KST다. 이 검토자가 `gh run view`로 직접 확인했고 Root `msg_e8d9e76e8ede`와 일치한다.
- **맥락으로만 읽은 것:** 4f CODE ACCEPT 2736, 4f Core/Backend/Docs와 3af Docs 성공. 선택적 f0af/ACCEPT 70f는 4f/B에 포함되지 않는다.
- **읽은 진행판:** Index 1.0.413.
- **하지 않은 것:** B 구현·계약 등록·ADR·board/registry 변경, live Docker/PKI/SSH/Node/CP 접근. B의 Go·crypto·OS lock·Engine·hardware 실행은 0건이다.

## 독립 확인

| 확인 | 명령·방법 | exit | 결과 |
|---|---|---|---|
| source surface 46개 | 4f/100f/60bf의 git blob을 SHA256으로 비교하고 anchor 행을 대조 | 0 | 46/46 bytes가 4f와 같고 100f에서도 그대로다. anchor 341개 중 329개는 정확히, 12개는 들여쓰기만 다르고 내용이 같다. 틀린 anchor는 0개다. |
| 기본 probe | `.venv` Python 3.14.7 `-B tests/proofs/fleet5_compute_storage_contract_probe.py` | 0 (기대 0) | owner fixture와 JSON이 같다. bytes 차이는 Windows stdout의 CRLF뿐이다. |
| coexistence probe | 위 명령에 `--require-coexistence` | 1 (기대 1) | owner log와 byte 단위로 같다(sha256 `26901da1…`). |
| unit | `pytest -q tests/core/test_fleet5_compute_storage_contract_proof.py` | 0 | 1 passed |

probe는 `git archive 100f6f13`을 scratch에 푼 사본에서 실행했다. Docker·PKI·DB는 쓰지 않았다. 이 결과는 R4가 coexistence를 거부한다는 gap 증거일 뿐이며 Linux mount 강제나 active storage를 증명하지 않는다.

60bfc722(Root board 계보)는 4f를 포함하지 않는다. 46개 surface 중 16개가 60bf와 다르다. 따라서 구현 anchor는 최종 결합 SHA에서 다시 고정해야 한다(Info).

source 대조로 proposal 표의 주장 다음을 확인했다.

- `worker_workspace.py:72` R4 storage flag 거부. `worker_storage.py:197` mount 2개.
- `peer_floor_linux.go:142,192` storage-policy 인자·`/contribution` mount 거부. `peer_policy_phase.py:149` plainServingProcess.
- `storage/sample.go:102` 정책 `certificate_sha256` = 활성 leaf DER(`cert.Raw`) SHA256. `transport/storage.go:48` pin `rootSha256`는 root 문자열(`/contribution`)의 hash이며 파일시스템 identity가 아니다.
- `storage_policy.go:44-47` 단조 규칙: 같은 C에서 hash가 다르면 거부, C+1은 허용, 같은 bytes는 replay.
- `storage_sampling.py:101-102` C/R ≤ 2^31−1. `storage_policy.go:26` Go pin ≤ 2^53−1. 실효 상한은 2^31−1이다.
- `sample.go:128` challenge.Channel 전체가 시작 시 정책과 같아야 한다. `storage_commit.py:79-86` 같은 `inv.node_channels` 행을 `assert_channel`로 다시 확인한다.

## 차단 사항

### B1 (High, 결정) — CP 겸임 Node의 contribution source namespace가 정의되지 않았다

`msg_be023606185f`에 대한 답이다.

- **문제:** B-FRESH1은 "homogeneous five-Node, Node마다 승인된 readonly contribution 하나"를 요구한다(proposal 69행). 그런데 ADR-100 토폴로지의 다섯 번째 Node는 Windows CP 위의 Docker Desktop Linux VM이다. proposal은 "Linux daemon-side source namespace를 요구하고 불확실한 Windows/VM mapping은 거부"(158행)한다고만 쓴다. Docker Desktop에서 무엇이 지원되는 namespace인지, 그 source의 identity·권한을 무엇으로 독립 측정하는지는 정의하지 않는다. manifest의 "co-location metadata"(90행)도 내용이 없다.
- **현재 source:**
  - 기존 storage 경로는 Windows drive를 `/run/desktop/mnt/host/<drive>/…` mapping으로 bind한다(`tools/check_storage_bundle.py:43-45`, `Replace-Storage.ps1` → WSL).
  - 이 mapping의 dev/inode는 Docker Desktop 파일 공유 계층의 값이며 Windows 파일 identity가 아니다. 그래서 proposal 4항의 "관측 root identity ↔ 승인 daemon-side source 일치"를 host validator가 독립 측정할 방법이 없다.
- **mixed cohort로 바꿀 수 없다:** 다섯 번째 Node만 plain으로 두는 방법은 쓸 수 없다. `lan_pilot.py:3546-3547`은 batch가 활성 Node 전체와 같아야 하고, `:3716`은 Node가 여럿이면 단일 commit을 거부한다. 그러면 proposal이 범위에서 뺀 mixed plain/coexist CP control-leaf 계약(247-249행)이 필요해진다.
- **구분:**
  - **설계 gap:** 지원 namespace를 정해야 한다. 예를 들어 Windows drive mapping은 금지하고 VM 내부 Linux 파일시스템만 허용하는 식이다. 그 source의 소유 UID·mode·dev/inode·mount를 daemon 쪽에서 무엇으로 측정하고 서명된 :3 kernel 관측과 무엇으로 맞추는지도 정해야 한다.
  - **구현 전제:** 그 측정을 수행하는 조건부 capability preflight가 필요하다. 미지원이면 BLOCK이며 대체 경로는 없다.
  - **물리 차단:** Index 413 기준 Windows CP Docker API 1.41 차단이 계속된다.
  - 어느 경우에도 Windows bind/hostpath grant를 새로 만들거나 다섯 개의 독립 장애 영역을 주장하지 않는다. 다섯 번째 Node의 S05/S07 제외도 그대로다.

### B2 (Medium) — CP role-admission 기록의 ABI가 없다

- **문제:** proposal은 실행·storage issue/commit을 "검증되고 기록된" role attestation 전까지 격리한다고 한다. 하지만 기록 위치(table/column·migration), 작성 권한, key, 무효화 규칙이 없다. 작성 권한은 operator 전용 grant인지 정해야 한다(node_channels.py:1 "Runtime can read/lock, never provision"과 같은 수준인지). key는 (node, epoch, C, R, policySHA256, executable/CID)여야 한다. C나 R이 바뀌면 자동으로 stale이 되어야 한다.
- **caller 목록도 닫혀 있지 않다.** `inv.node_channels`를 읽는 CP caller가 적어도 다음과 같다. 각각 gate를 적용하는지 제외하는지 명시해야 한다.
  - `placement.py:380`, `capacity.py:22`, `gpu.py:81`, `node_resource_usage.py:77`
  - `containment.py:175`, `observer_worker.py:24`, `node_execution.py:93`, `node_transfer.py`, `terminal.py`
  - `model_source.py`/`model_runtime.py`, `storage_commit.py`, `storage_check_collect.py`
  - `tools/check_lan_storage_readiness.py`, `tools/five_node_lab_preflight.py`
- **policy B의 출처:** 승인 기록이 무엇인지 함께 정해야 한다(L4 참고).

### B3 (Medium) — 두 durable pin의 순서와 부분 상태

- **문제:** Node 시작 시 `main.go:104` `NewAuthority`가 peer floor를 먼저 pin한다(`transport/trust.go:85`). 그 다음에야 `main.go:115` `NewStorageSampler`가 DER을 확인하고(`CheckCertificate`, `transport/storage.go:50-52`) `PinStoragePolicy`를 실행한다. 두 파일은 원자적으로 함께 바뀌지 않는다.
- **결과:** overlap 재시작에서 storage 검증이 실패하면 상태가 (P+1, storage C)로 남는다. 실패 원인은 DER B의 NotBefore·시계 차이, 잘못된 policy B 등이다. peer floor가 단조이므로 이전 config로 재시작할 수도 없다.
- **proposal에 없는 것:** phase 표는 이 중간 상태와 허용 전이를 다루지 않는다.
- **필요한 것:** 아래 둘 중 하나를 계약해야 한다.
  - role-aware runtime이 peer pin 전에 storage config/DER을 먼저 검증한다.
  - 부분 상태를 "같은 exact config replay만 허용, 그 외 BLOCK"으로 닫는다.

  preflight에는 DER B NotBefore ≤ now−skew 조건도 넣어야 한다.

### B4 (Medium) — batch 경로에서의 storage 재승인

- **문제:** 다섯 Node 갱신은 batch 경로다. `stage_leaf_rotation_batch`(`lan_pilot.py:3540-3590`)는 CP leaf를 그대로 둔 채 Node별 C→C+1 CAS를 staging 시점에 수행한다. proposal의 renewal 표는 단일 Node "CP commit" 한 줄뿐이다.
- **필요한 것:**
  - Node별 storage/실행 재승인을 staging/staged/switched/finalized 중 어디서 하는지 정한다.
  - 일부만 staged된 batch가 실패했을 때 Node별 상태(C+1/DER B와 C/DER A가 섞인 상태)를 정의한다.
  - 그 상태에서 storage가 격리를 유지하는지 정한다.

### B5 (Medium) — DB lock 순서

- **현재 lock 순서가 반대다:**
  - 갱신 CAS: `inv.node_channels FOR UPDATE`(`lan_pilot.py:1538-1541`) → `provision_channel` 안의 `inv.nodes FOR UPDATE`(`node_channels.py:169`).
  - storage issue `_scope`: `inv.nodes FOR UPDATE`(`storage_commit.py:56-58`) → `public.storage_contributions FOR UPDATE` → `node_channels FOR SHARE`(`assert_channel`).
- **결과:** 두 transaction이 동시에 돌면 PostgreSQL deadlock abort가 날 수 있다. 안전성 위반은 아니다(fail closed). 다만 CAS의 lost/abort 처리가 필요하다.
- **proposal의 R 재확인 요구:** "commit tx 안에서 storage_contributions status/R 재확인"은 lock을 하나 더 추가한다. 전역 lock 순서를 명시해야 하고, 아니면 quiesce를 DB 수준에서 보장해야 한다.
- **증거 수준:** source 순서 분석이며 재현하지 않았다.

## Low / Info

- **L1:** workload inspection struct(`docker.go:292-315`)는 `HostConfig.Binds/Devices/PortBindings`만 본다. `HostConfig.Mounts`, `VolumesFrom`, 최상위 `Mounts`는 보지 않는다. Node가 config를 직접 만드므로 현재 악용 경로는 없다. 그래도 B의 "workload가 contribution에 접근 불가" 수락 조건에는 inspected 빈 Mounts 확인과 실제 Linux Docker 시험을 추가한다.
- **L2:** `PinStoragePolicy`는 이전 `.storage-<cid>` floor를 지우지 않는다(`storage_policy.go:29-35`). :3 observer는 승인 cid 외 floor 파일이 있을 때의 규칙(거부 또는 무시)을 정해야 한다.
- **L3:** 갱신이 key를 유지하므로 DER A와 B가 같은 Ed25519 key를 쓴다. 따라서 이전 challenge 거부는 key 분리가 아니라 다음에 의존한다.
  - challenge의 channel 결속(`sample.go:128`)
  - nonce 소비
  - `assert_channel` 재확인

  같은 key로 서명된 (C, DER A) sample이 CAS 뒤 거부되는지를 명시적으로 시험해야 한다.
- **L4:** `revoke_channel`도 C를 +1한다(`node_channels.py:217-219`). 갱신 도중 revoke되면 pin된 C+1 정책은 영구히 쓸 수 없고, 더 높은 C의 새 정책이 필요하다. policy B bytes를 누가 생성·승인하는지는 proposal에 없다. fresh install은 "policy authority를 만들지 않는다"고 했는데, renewal은 새 policy hash를 만든다.
- **Info:**
  - Node 프로세스는 Docker socket을 가지므로 host root와 동등하다. 따라서 readonly contribution은 Node 코드의 오기록을 막는 무결성 장치이며, 손상된 Node에 대한 보안 경계가 아니다. threat model에 이 점을 명시한다.
  - 기본 probe stdout이 CRLF로 다른 것은 정상화로 덮지 않고 그대로 기록했다.

## 닫힌 ABI 상태·phase·counter 표 (검토자 제안, 미등록)

counter는 다음 셋뿐이다. 추가 storage counter·table은 없다.

- **P:** Node-local peer floor. 1..2^53−1이며 갱신 1회에 +2다.
- **C:** `inv.node_channels.version`. 실행과 storage가 공유한다. sampling v1에서 1..2^31−1이다. 갱신 CAS에 +1, revoke에도 +1이다.
- **R:** `public.storage_contributions.version`. 1..2^31−1이며 갱신 중에는 바뀌지 않는다. 제품 재등록으로 R이 바뀌면 새 정책과 재시작이 필요하고, 이는 B 갱신 범위 밖이다.

| Phase | Node peer | Node storage pin | CP row | 승인 | 허용 전이 / 실패 |
|---|---|---|---|---|---|
| S0 현재 | P | (R,C,policy A↔DER A) | C,DER A,enabled | role 기록(C,R,A,exe) 유효 → OPEN | → S1 |
| S1 preflight(쓰기 없음) | P | 같음 | 같음 | OPEN | 전원 검증. C+1·P+2 overflow, DER B 유효기간·NotBefore, R/status, policy B bytes 고정. 실패하면 S0 그대로 |
| S2 서명된 intent 기록 | P | 같음 | 같음 | **QUARANTINE**(노출 전) | 이후 forward-only |
| S3 overlap 파일 복사 | P | 같음 | 같음 | QUARANTINE | 부분 복사·복사 전·재시작 복구 = BLOCK |
| S4a 재시작 중 부분 상태 | P+1 | (R,C) | C | QUARANTINE | 같은 exact config replay만 허용, 그 외 BLOCK (B3) |
| S4b overlap | P+1 | (R,C+1,B↔DER B) | C | QUARANTINE | 서명 :3 관측(P+1,C+1,R,DER B) → S5 |
| S5 Node별 CAS(batch staging) | P+1 | 같음 | C+1,DER B | QUARANTINE | 하나의 tx·명시 lock 순서. row=(C,A)이면 CAS, (C+1,B)이면 replay, 그 외 BLOCK (B4/B5) |
| S6 batch switched | P+1 | 같음 | 같음 | QUARANTINE | CP leaf 전환 |
| S7 final | P+2 | (R,C+1,B) exact replay | C+1,DER B | role 기록(C+1,R,B,exe) → OPEN | 완료. 이전 policy/P 복원 금지 |

## 구현 owner 수락 matrix

| # | 수락 조건 | 증거 형태 |
|---|---|---|
| A1 | R4·plain :2/:3·legacy history 시험 무변경 green | 기존 suite exact SHA |
| A2 | manifest 4 닫힌 schema. unknown field·alias·equal 형식·단일 대시·중복 flag 거부 | 생성 schema와 negative fixture |
| A3 | 정확히 mount 3개(state RW·기본 socket·contribution RO/nonrecursive/rprivate). 추가·RW·잘못된 socket 거부 | fixture와 실제 Linux Docker |
| A4 | readonly 쓰기 거부, 하위 mount 제외, propagation 격리 | 실제 Linux Docker (mock 불가) |
| A5 | workload가 contribution·state·socket·host path에 접근 불가. inspected 빈 Mounts/VolumesFrom (L1) | 실제 Docker |
| A6 | :3 observer가 PID·raw argv·실행 파일·root fd identity, peer·storage floor, 추가 floor 파일 규칙(L2)을 확인 | 실제 Go |
| A7 | Go/Python canonical vector(Unicode, 2^31−1 / 2^53−1 경계) | 양 언어 vector |
| A8 | 같은 C에 다른 hash 거부, C/P 역행 거부, R bump 우회 거부 | Go 단위와 CP 시험 |
| A9 | 시작 pin 순서·부분 상태 S4a 처리 (B3) | 실제 Go crash 주입 |
| A10 | 실제 Go와 PostgreSQL로 완전한 :4 갱신 두 번. 같은 C의 CAS, 이전 challenge·같은 key 서명 거부 (L3) | 실제 Go와 PG |
| A11 | batch 부분 staged와 실패 시 Node별 격리 유지 (B4) | PG fixture |
| A12 | 갱신 CAS와 storage issue/commit 동시 실행 시 deadlock/abort 처리, 전역 lock 순서 (B5) | PG 동시성 시험 |
| A13 | role-admission gate가 B2의 닫힌 caller 목록 전체에 적용되고, stale·누락이면 거부 | CP 시험 |
| A14 | CP 겸임 Node source capability preflight. 미지원이면 BLOCK (B1) | preflight fixture(장비 수락은 별도) |
| A15 | 모든 create/copy/start/ack/CAS 지점의 crash·lost response 처리. consumer 둘 동시 금지, 이전 restore 금지 | 주입 시험 |
| A16 | closed package/runtime/schema 재생성, 전체 CI, 실제 독립 검토 | exact SHA CI |

## Root의 구현 전 결정 사항

- **D1:** CP 겸임 Node의 contribution namespace·측정 방법(B1)을 정한다. 아니면 B-FRESH1의 homogeneous 범위를 다시 정한다. 그 경우 mixed cohort CP-leaf 계약이 별도 gate가 된다.
- **D2:** role-admission 기록 ABI와 closed caller 목록(B2). policy B 생성·승인 주체(L4).
- **D3:** pin 순서 계약 또는 S4a 닫힘 규칙(B3).
- **D4:** batch phase별 Node 재승인 규칙(B4).
- **D5:** 전역 DB lock 순서(B5).
- **D6:** 구현 ownership. renewal·CP admission·동시성은 고난도이므로 Codex 계약 영역이다. manifest·fixture·시험은 그 계약 아래에서 나눌 수 있다. Root가 결정한다.

B-MIG1과 legacy 이전은 계속 별도 gate다. 실제 식별자·lease·image·source path·배포 hash는 NULL/HOLD다. 장비 차단은 별도로 유지된다.

## 다음 첫 행동

- **Codex(owner):** B1–B5를 proposal 개정으로 닫는다.
- **Root:** 개정본 수신 후 D1–D6를 결정한다.
- **Claude:** 개정본의 delta만 다시 검토한다.
