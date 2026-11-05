---
doc_id: "HISTORY-FLEET5-20261106-P0-CODE-4A92-REVIEW-CLAUDE"
title: "2026-11-06 FLEET5 P0 code 4a928310 독립 검토와 vector delta 50000697"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-06T00:10:02+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "b59a5252"
task_ids: ["FLEET5-SETUP-INTEGRATION-20261105"]
tags: ["fleet5", "independent-review", "p0", "code", "claude"]
---

# P0 code 4a92 검토

Orca task `task_c90b362f7470`, dispatch `ctx_1e0814952956`. [[2026-11-05_21-55-00_KST_FLEET5_P0_code_6c0f_검토_Claude]]에서 NOT ACCEPTED로 판정한 `6c0fc4ad`의 수정본 `4a928310`을 판정한다. root가 요청해서(`msg_272d6847bae2`) test 전용 vector delta `50000697`의 판정도 함께 적는다.

- **관측 시각:** 2026-11-05 23:47:23 ~ 2026-11-06 00:10:02 KST. 처음 fetch할 때와 작성 전 마지막 CI 확인 때 찍은 shell `date` 출력이다.
- plan 판정을 물려받지 않는다. 직접 확인한 code 판정이다.
- **기계 판독 결과:** `Evidence/fleet5-20261105-claude/p0-code-4a92-review.json`

## 대상과 방식

- **대상:** `agent/codex/fleet5-compute-storage-contract-20261105`의 `4a928310e88ac336efb040c1621525fee7133f32`
  - 6c 대비 non-docs 36개, +1852/−943
  - 사이에 `526d48e4`(fixture hex nonce)와 `323baeb5`(docs 전용 F2/F3 제안)가 있다.
- **vector delta:** `5000069744931afb2fb85d24752a9916f7ba0ccc`. 4a 위에 test 파일 3개와 docs만 바꿨다. runtime 파일 변경은 0개다.
- **읽은 방식:** Git object를 내 scratch worktree에 detached로 꺼냈다. 작성자 checkout은 건드리지 않았다. mutation은 끝난 뒤 되돌렸고 clean 상태를 확인했다.
- **실행:** main `.venv` Python 3.14.7 `-B`로 돌렸다. local에 Go가 없어서 Go는 실행하지 않았다.

## native 고정 증명 (Core 42047390811 artifact 13426365088)

내가 직접 받아서 해석했다.

- 결과: `proofValid` true, linux, 정상 cycle 2개.
- floor: P7~P11, schema `:2`. `servingExecutableSHA256`은 끝까지 같은 값이다.
- cycle 1: C8, 7→8→9. cycle 2: C9, 9→10→11. 두 cycle 모두 final을 받아들였고, final 뒤에 옛 CP는 거부됐다.
- 음성 11개가 모두 true다. Go guard test 7개(subtest 포함)도 모두 통과했다.
- Docker ownership, Postgres CAS, 운영 항목은 artifact 자체가 false로 적었다.
- **한계:** 4a의 canonical vector는 의도한 비 ASCII를 담지 못했다(C2-V1). 그래서 이 artifact를 `50000697`의 성공 증거로 쓰지 않는다.

## 항목별 확인

| 항목 | 결과 |
|---|---|
| **M2** | 실행 파일의 hash는 `/proc/<pid>/exe` descriptor bytes에서 구한다. 확인하는 것: `/proc/self/exe`와 SameFile, UID, group/other 쓰기 권한 없음, 128MiB 상한, starttime으로 PID 세대 재확인, descriptor와 이름으로 본 stat의 일치. 관측 앞뒤로 두 번 잰다. cmdline은 비어 있지 않고, NUL로 끝나고, 올바른 UTF-8이어야 한다. Python은 schema `:2`, hex executable field, v2 domain만 받는다. v1 fallback은 없다 |
| **C2 Python** | 803 golden B01~B05가 5/5 같다. B06~B10은 5/5 거부된다. 내 Go `Marshal` emulator와 random 비교 5000개가 모두 같다. 잘못된 입력은 하나도 받아들이지 않는다 |
| **C2 vector (4a)** | **결함(C2-V1).** fixture에 비 ASCII byte가 0개다. 한글과 악센트 문자가 모두 literal `?`로 바뀌었다. supplementary case는 escape로 쓴 U+10FFFF만 남았다. Go는 raw 비 ASCII를 한 번도 처리하지 않았다. owner 보고 `msg_7113bdba916c`와 내 독립 발견이 같다 |
| **B1** | 고정 probe의 heartbeat가 공유 `NodeProbeInput`을 통과하고 nonce는 hex64다. base64 음성 case는 key가 nonce 하나뿐이라 nonce 오류만 확인한다. 바깥 receipt와 CP commit은 newline이 붙은 기존 표준형을 그대로 쓴다 |
| **B2** | 6c→4a에서 test 함수 9개를 지우고 24개를 더했다. 남은 test 중 assert나 raises가 줄어든 것은 **0개**다. 아래 참고 |
| **F1** | `backend.yml`이 lifecycle `:3` dict의 key 11개를 정확히 비교한다. `rolledBack` False, `rollbackRejected` True, cycle 2이고, `is True`와 `type(...) is int`로 확인한다. module은 5개로 고정했다. bd96479b와 field별 대조는 다시 하지 않았다 |
| **F2 (SF1)** | 아래 참고 |
| **F3 (RS1)** | 아래 참고 |
| **local suite** | 10개 파일에서 206 passed. 14개 skip은 Windows platform skip이다(POSIX owner/mode, symlink) |

### B2: `test_lan_leaf_rotation.py`가 줄어든 이유

- 숫자: test 22→19, assert 116→67, raises 36→28.
- **원인:** 줄어든 양 전체가 지운 test 8개(assert 57개, raises 15개)에서 왔다. 지운 test는 4a가 막는 의미를 시험하던 것이다.
  - legacy uncommitted rollback과 installing rollback: 6c에서도 이미 hard-block이었다.
  - expired partial supersession: 4a에서 `_supersede_expired_journal`이 바로 raise한다.
  - fully-expired offline recovery와 abandon: 4a에서 `lan_pilot`이 바로 raise한다.
- **대체:** forward-only 거부 test 5개가 들어왔다. consecutive의 rollback 복원 test도 거부 test로 바뀌었다.
- **그대로인 것:** batch_successor, archive_residue, predecessor_residue의 assert 수는 바뀌지 않았다.
- 판단: assert나 음성 case를 몰래 지운 것은 없다. 다만 expired recovery 경로를 없앤 것은 기능 축소다. root 결정의 "No expired … transition"과 맞는다.

### F2 (SF1)

- `verify_settled`가 확인하는 것:
  - finalized `:3` journal
  - immutable archive: 정확한 key, 원래 bytes, `.next` 없음
  - 서명과 CP commit
  - 현재 credential bytes
  - 실제 Go final floor
- 마지막에 다시 읽어서 그 사이에 바뀐 것이 없는지 확인한다.
- guard는 기존 `leaf-rotation.lock`을 쓰고, stale lock을 빼앗지 않는다. token은 둘 중 하나로 얻는다.
  - in-process 경로: leaf entry
  - 고정 5-module launcher 경로: entry, module, crypto version의 hash를 확인하고, `-I -B`, 30초, 64KiB 엄격한 JSON, 정확한 key로 실행한다
- 허용하는 action은 `idempotent`와 `same-byte-copy`뿐이다. action 뒤에 안정된 identity를 다시 확인한다.
- workspace와 execution의 SF1 분기는 inspect만 한다. image, profile, container 변경과 undo는 거부한다.

### F3 (RS1)

- 전제: lock, durable `:3` intent, 정확한 proposal과 서명된 pre-floor, 시작 전에 만료되지 않은 chain과 policy. final이면 서명된 CP C+1 commit도 있어야 한다.
- phase tuple은 결정 표와 같다.
- 서명되지 않은 stopped read는 시작 자격 판단에만 쓴다. 이 TAR 읽기의 제한:
  - 16MiB, 30초, 2048 entry
  - owner root, 파일 0600, journal 0700
  - regular file만 허용
- host bytes와 volume bytes가 고정된 active tuple과 같아야 한다. 하나뿐인 action인 `docker start <CID>` 직전에 다시 읽는다.
- start 결과가 불확실하면 ownership을 다시 관측하고 앞으로만 간다.
- ack는 phase와 원래 executable에 맞는 새 Go 관측으로만 만든다.

### 내 mutation red control

- **잡힌 것 8개:**
  - TAR owner
  - settled guard action
  - migration marker
  - final floor 재관측(첫 final archive가 retry에도 같다)
  - U+2028 escape
  - HTML escape
  - v1 domain
  - 서명 없는 ack
- **살아남은 것:**
  - RS1: start 뒤 ack의 phase와 executable 확인 제거
  - RS1: start 직전 stopped 재확인 제거
  - RS1: finalizing에서 P/current floor 허용
  - guard: action 뒤 settled 재검증 제거
  - executable hex 확인 제거
- symlink type 검사는 지워도 mode 0600과 size 검사가 같은 입력을 막는다. 이중 방어이며, 빈틈이 아니다.

## 발견

| ID | 심각도 | 내용 |
|---|---|---|
| **C2-V1** | Medium | 4a vector의 비 ASCII가 `?`로 바뀌었다. `50000697`에서 Python 수준은 고쳐졌다. Go 실행은 pending이다 |
| **CI-B1** | Medium | Backend 42047403498이 **FAILED**다. 3.12와 3.14 모두 같은 5개가 실패한다(8717 passed). 아래 참고 |
| **T1** | Medium | RS1과 SF1의 음성 test가 빠졌다. 살아남은 mutant 4개(start 뒤 ack 확인, start 전 재확인, finalizing tuple 확대, action 뒤 settled 재검증)를 잡는 test가 필요하다 |
| T2 | Low | 서명은 됐지만 형식이 틀린 `servingExecutableSHA256`에 대한 음성 test가 없다 |
| T3 | Low | SF1 기본 경로(고정 launcher subprocess)를 시험한 test가 없다. Python test와 Docker integration test 모두 `_settled_verifier`를 바꿔 끼운다. 실제 Go+Docker는 진짜지만, 설치된 고정 runtime 경로를 증명하지는 않는다 |
| I1 | Info | after-stop/no-copy crash는 복구되지 않는다. 막혀 있을(guarded BLOCK) 뿐이다. RS1이 거부하고 같은 CID가 정지 상태로 남는다. after-copy만 앞으로 재개한다. 전체 복구에는 따로 설계가 필요하다(root `msg_af733431a8e1`) |
| I2 | Info | `restarted` phase는 RS1 대상이 아니다. 결정 표와 같다 |
| I3 | Info | `verify-settled` CLI 자신은 lock을 확인하지 않는다. 읽기 전용이고, 앞뒤 변경을 감지한다 |

**CI-B1 상세:**

- 실패 메시지: "Actual Node floor observation is stale or clock-uncertain"
- local 재현 결과:

  | 실행 순서 | 결과 |
  |---|---|
  | `test_lan_leaf_rotation` → `standalone_runtime` → residue | 5 failed |
  | `test_lan_leaf_rotation` → residue (`standalone_runtime` 없음) | 41 passed |

- 원인: launcher `run_worker`가 같은 process 안에서 worker module을 `sys.modules`에서 뺀다. 그러면 4a의 새 `peer_phase_unit_fixtures`가 바꿔 끼운 module은 낡은 객체가 된다. 그 결과 관측은 고정된 시계를 쓰고, 검증은 실제 시계를 쓴다.
- residue code는 바뀌지 않았다.
- 고칠 때 freshness를 넓히거나 test를 skip하면 안 된다.

## vector delta 50000697

- fixture와 Go test가 모두 ASCII뿐이다. `?` literal은 없다.
- 기대 bytes: 내 emulator 7/7, Python 7/7. body newline은 7/7 없다.
- 담긴 문자:
  - 라틴: U+00E9, U+00EF, U+0301
  - 한글
  - U+2028과 U+2029
  - U+1F600, U+1D11E, U+1F9ED, U+10FFFF
- NFC로 정규화하면 key가 합쳐진다. 따라서 이 case로 정규화를 하지 않는다는 것이 증명된다.
- red control: 옛 4a fixture로 돌리면 1 failed, 9 passed. 고친 fixture로는 10 passed.
- Go 실행은 하지 않았다. CI pending이다.

## 판정

| 구분 | 판정 |
|---|---|
| **candidate code `4a928310`** | **NOT ACCEPTED (exact head).** M2, C2, RS1, SF1, B1, B2, F1 source에서 runtime 정확성 결함은 찾지 못했다. 그래도 C2-V1, CI-B1, T1은 고쳐야 한다. T2와 T3는 Low다 |
| **vector delta `50000697`** | **ACCEPT (test 전용, Python과 source 수준).** C2-V1이 닫혔다. Go canonical 실행은 pending이고, C2 native 수락은 없다 |
| full CI | 4a Backend RED. Core 42047390811은 진행 중이다. green이라고 주장한 것은 없다. 내가 Core를 새로 돌리지 않았다 |
| runtime·physical | 수락하지 않는다. Docker ownership, 실제 Postgres CAS, 운영, physical은 평가하지 않았다 |

## 다음 첫 행동과 담당

- **`ctx_6f0f8253b8a7`:** standalone test isolation 수정과 T1 음성 test(T2와 T3도 받아들이면 함께)를 정확한 SHA로 낸다. Backend가 green이어야 하고, freshness를 넓히거나 skip하지 않는다.
- **root:** 4a를 NOT ACCEPTED로 둔다. `50000697`의 Go 결과는 그 commit 자체의 CI로 확인한다. runtime과 physical은 HOLD로 둔다.
- **Claude:** test 전용 delta가 공개되면 그 delta와 CI를 검토한다.
