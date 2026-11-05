---
doc_id: "HISTORY-FLEET5-20261105-CONSECUTIVE-ROTATION-8B53-REVIEW-CLAUDE"
title: "2026-11-05 FLEET5 Codex 연속 leaf rotation과 batch successor 8b53fbfe 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T18:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "8ad8f6d9"
task_ids: ["FLEET5-CONSECUTIVE-LEAF-ROTATION-20261105"]
tags: ["fleet5", "independent-review", "leaf-rotation", "batch", "claude"]
---

# 연속 leaf rotation과 batch successor 8b53fbfe 검토

Orca task `task_2aba347fdf39`, dispatch `ctx_7b3724557215`. 내가 앞서 낸 S1 발견([[2026-11-05_16-32-00_KST_FLEET5_Low_closure_af5b_검토_Claude]])에 대한 Codex의 source 수정을 검토했다.

- 대상: `agent/codex/fleet5-consecutive-leaf-rotation-20261105`의 `8b53fbfef107837602b1b2f700e1f8e7bae28638`. base는 `59f0a3c2`이고 commit은 3개다: `a93ec9f1`(Node), `c540e484`(CP batch), `8b53fbfe`(Card150 tooling 한 쌍).
- 검토 시각: 18:00~18:40 KST
- 한 일: diff 정독, hash 재계산, 새 test 2개 파일 실행, 임시 probe 5개 실행. 임시 worktree는 끝난 뒤 제거했다.
- 하지 않은 일: live, private r5, executor, clock, claim, admin, auth 변경. 전체 suite 재실행. 다른 agent 사용.
- 기계 판독 결과: `Evidence/fleet5-20261105-claude/consecutive-rotation-8b53-review.json`

## 무결성

- `deploy/lan/worker_leaf_rotation.py` sha256 `3411ba485aad6ee0cc356191759584aecfca76ce1421aef68d138fabb7ef603f`. relay 값과 같다. standalone launcher의 `WORKER_MODULES` pin도 같은 값이다.
- `tools/lan_pilot.py` sha256 `b282767fbb3d71bb07ae94ea2c80ea26262f32485d4c6575f9553484563fe4e9`, blob `502edf7b85582ad40fee1c48703787d7b87ce421`. 둘 다 같다.
- Card150 Evidence는 `tools/lan_pilot.py`의 hash 두 field만 바뀌었다. 59f preparation 값은 그대로이므로, DB864의 preparation 값과 합치는 일은 root의 integrator가 맡는다. 두 변경은 서로 다른 key라 충돌하지 않는다.
- **의존성:** worker와 standalone runtime의 import 목록이 59f와 같다(`stat`, `os`, `re`은 원래 있었다). runtime `LOCK_SHA256 06710d85…`(cryptography 50.0.1, cffi 2.0.0, pycparser)도 바뀌지 않았다. 새 package는 없다. `lan_pilot.py`는 `import worker_leaf_rotation as worker_rotation` 한 줄만 늘었고, 같은 module의 다른 이름을 이미 import하고 있었다.

## Node 쪽 (`attest-finalized`, finalize, successor install)

- **finalize** 순서는 이렇다.
  1. finalized journal bytes로 증거를 만든다.
  2. archive 충돌을 먼저 확인한다(publish 안 함).
  3. 처음 finalize하는 경우에만 final policy를 쓰고 restart한다.
  4. 증거를 `os.link`로 덮어쓰지 않게 publish한다.
  5. 마지막에 journal을 `finalized`로 쓴다.

  어느 지점에서 죽어도 다시 실행하면 같은 bytes가 나온다(canonical JSON, Ed25519는 결정적이다). 이미 finalized인 legacy journal을 replay하면 restart하지 않고, 원래 journal bytes를 그대로 archive에 넣는다. 현재 policy가 final policy와 다르면 거부한다.
- **attest-finalized**는 다음이 모두 맞을 때만 서명한다.
  - `validate_bundle(installed=True, finalized=True)`(certificate NotAfter까지 허용)
  - archive 증거 전체를 다시 검증(Node install receipt 서명과 CP commit receipt 서명)
  - active journal bytes가 archive의 `journalRaw`와 같음
  - 현재 `peer-policy.json`이 final policy와 같음

  서명 본문은 schema `saintvision-node-finalized-attestation:1`이다. 그래서 install receipt 서명과 다른 domain이다.
- **successor install**은 finalized journal이고 `rotationId`가 다를 때만 `_finalized_successor`를 탄다. 확인 내용:
  - archive 모양과 bytes
  - 같은 tenant, Node, epoch, IP, CA bundle
  - old target 버전 = new current 버전
  - old next 인증서 = new current 인증서(Node와 CP 모두)
  - 현재 node-cert와 policy 파일이 archive와 같음
  - archive에 든 leaf가 지금도 유효함
  - Node key가 같음
  - createdAt이 증가함
  - 새 archive 이름이 비어 있음

  통과하면 active slot은 기존 durable `installing` 경계에서만 바뀐다. backup 충돌도 거부한다. 알 수 없는 journal 모양(`None`, `{}`, `[]`, 문자열, 다른 phase)은 install 전에 거부한다.

## CP 쪽 (`retire-leaf-rotation-batch`, prepare, commit)

- **retire**는 `switched` 또는 `finalized` journal에서만 시작한다. `switched`만으로는 끝나지 않는다. 확인 내용:
  - 모든 member가 각자의 서명된 attestation을 정확히 한 번 냄(중복, 누락, 외부 Node는 거부)
  - 각 attestation을 이 batch의 `rotation.json`과 public file에 대해 검증
  - `_current_finalized_batch`: tenant, epoch, CA pin, member 집합(= 현재 active Node), 발급 chain의 유효성, 현재 CP leaf와 key, 각 Node의 현재 leaf와 final policy, credential 미폐기, IP, DB channel row(lock을 잡고 version·hash·expiry·enabled·endpoint)
  - 위가 모두 맞으면 CP가 서명한 archive(switched journal, terminal journal, batch, 모든 proof)를 덮어쓰지 않게 publish한 뒤, journal을 원자적으로 `finalized`로 쓴다.
  - unlink나 reset은 없다.
- **같은 batch의 terminal replay:** 다시 retire하면 archive를 검증하고, 받은 proof bytes가 같은지 확인한다. 같은 batch로 prepare하거나 commit해도 phase는 `finalized`로 남는다. stage는 거부된다.
- **successor prepare**는 `_finalized_predecessor`로 archive와 현재 authority를 다시 검증한다. 그리고 다음을 요구한다.
  - 같은 member 집합, tenant, epoch, CA
  - 새 batch의 current CP = old next CP
  - 각 Node에서 버전과 인증서가 이어짐
  - Node key와 CP key가 같음
  - lifetime = min(Node, CP)
  - overlap과 final policy가 맞음

  새 batch를 publish한 다음에만 journal을 `prepared`로 바꾼다. 그 사이에 죽어도 다시 검증해서 이어 간다.
- offline recovery 경로는 여전히 `staging`/`staged`만 받는다. `finalized`에서는 시작할 수 없다.

## 내 실행

**새 test 2개 파일** (8b53 detached worktree, main `.venv` Python 3.14.7, `-B`, cache 없음): **79 passed, 10 skipped**, 48.9초.

skip 10개는 모두 Windows 한계다. symlink 생성 불가(OS 1314)가 9개, POSIX 소유권·mode가 1개다. 이 경우들은 hosted Linux Core에서만 실행된다. 그러니 symlink 거부는 **내가 실행해서 확인하지 못했다.** code만 읽었다(`_regular`의 `lstat`와 `S_ISREG`, 디렉터리의 symlink·junction 검사).

**probe** (임시 test 파일, commit 안 함, sha256 `72a0c6c4…`): 5개 모두 pass.

| probe | 결과 |
|---|---|
| P1 2-Node batch를 **세 번** 연속(prepare→complete→retire) | 버전 `[8,12]→[9,13]→[10,14]`. archive 3개. 두 번을 넘어도 이어진다 |
| P2 이전 batch의 유효 proof를 현재 batch proof와 섞음 | `Node finalized attestation differs from the exact batch`. 같은 proof 두 번도 거부. state snapshot 불변 |
| P3 archive publish 뒤 crash, 그 다음 같은 proof를 다른 직렬화(indent와 개행)로 replay | `Finalized rotation archive collision`. journal은 `switched`로 남음. 원래 파일로는 성공 |
| P4 Node archive 옆에 같은 bytes의 `.next`(link와 unlink 사이 crash) | finalize replay와 successor 뒤에도 `.next`가 **남는다** |
| P7 successor install이 시작된 뒤 이전 rotation을 attest | 거부(`Current Node leaf does not match the rotation base`) |

## 발견 (모두 Low, 차단 아님)

- **L1 `.next` 잔여물:** `_immutable`은 destination이 이미 있으면 바로 return한다. 그래서 link와 unlink 사이에 죽으면 같은 bytes의 `.next`가 영원히 남는다(Node, CP 둘 다). code는 이를 받아들인다. 하지만 Low-closure 분류기는 `.next`를 orphan으로 보고 BLOCK한다. 둘 중 하나가 필요하다.
  - exists 경로에서 bytes가 같은 temp를 unlink하고 디렉터리를 fsync한다.
  - 분류기가 "같은 bytes의 archive `.next`"를 허용한다.
- **L2 retire replay의 byte 의존:** 받은 receipt 파일의 원문 bytes를 archive에 넣는다. 그래서 crash 뒤 replay할 때 의미가 같아도 직렬화가 다르면 충돌하고, batch는 `switched`에 머문다. 안전한 쪽으로 실패하고, README도 receipt를 보관하라고 한다. 그래도 받은 proof를 `_canonical_json(json.loads(raw))`로 정규화해서 넣으면 운영 실수에 덜 민감해진다.
- **L3 문서 범위:** README는 successor가 "현재 authority에 대해 검증된다"고만 쓴다. 다음을 명시하지 않는다.
  - successor는 **같은 member 집합, 같은 Node와 CP key, 같은 tenant·epoch·CA·IP**에서만 가능하다.
  - Node를 추가, 제거, 폐기하거나 IP·epoch·CA를 바꾸면 retire와 successor가 **모두 막힌다.**
  - 이 source에는 그런 cohort 변경 경로가 없다.

  Codex History도 "fixture, hardware acceptance 아님"이라고 바르게 쓴다. 하지만 cohort 변경이 막힌다는 점은 README에 한 문단 있어야 한다.
- **계약 영향(root에게):** 59f 기준의 F5 append 분류기와 snapshot registry는 batch phase를 `{prepared, staging, staged, switched}` 넷으로 알고 있다. 이제 terminal `finalized`, `leaf-rotation-finalized/<batchId>.json` CP archive, Node `leaf-rotation-finalized/<rotationId>.json`, `.next`(L1)를 분류에 넣어야 한다.

## hosted (18:34:41 KST)

| run | head | 상태 |
|---|---|---|
| Docs 42001888497 | `8b53fbfe` | completed **success** |
| Core 42001883513 | `8b53fbfe` | **in_progress**. 성공으로 세지 않는다 |
| a93 Core 41995694509 / Docs 41995699334 | `a93ec9f1` | success(root·Codex 보고). Node만 있던 milestone이므로 8b53의 증거가 아니다 |

## 판정

**`8b53fbfe` ACCEPT (source).**

- Node finalized proof와 CP batch retirement가 brief의 요구를 모두 지킨다.
  - `switched`만으로는 끝나지 않는다.
  - 모든 member의 서명이 필요하다.
  - 현재 authority와 DB channel에 묶인다.
  - archive를 덮어쓰지 않는다.
  - unlink나 reset이 없다.
  - crash와 terminal replay가 된다.
  - legacy migration은 원래 입력의 replay로만 한다.
  - partial, unknown, stale, tampered, 충돌은 거부한다.
- 의존성은 그대로다. 내 probe로 세 번 연속 batch가 되는 것도 확인했다.

판정 범위:

- hosted Core 42001883513은 pending이다. symlink와 POSIX case는 Linux Core에서만 증명된다.
- fixture에서는 member가 고정이다. live hardware, 임의의 append, cohort 변경, 실제 renewal 운영을 받아들인 것은 아니다.
- L1~L3는 Low다. 통합 전에 고치면 좋지만 차단은 아니다.

## 기록만 한 relay (판정하지 않음)

- root는 R4 `1744`/`e62`, DB `864`/`d18`과 이번 source를 합친다. source pin과 archive는 다시 만든다. 59f는 고치지 않는다.
- 진행률은 100%가 아니다(root 판단).
  - PC2와 PC4: r5 두 대 online
  - PC1 `.13`: key와 Docker pending
  - PC3 `.222`: Docker group pending
  - Windows CP `.74`: 예전 API 1.41
- root가 보고한 확인:
  - PC4의 share 폴더 cap-drop read-only 증명 통과
  - 새 Ed25519 외부 issuer의 암호화, 서명, CRL 확인. 예전 CA 24개와 다름. ACL은 operator, SYSTEM, Admin
  - leaf는 발급하지 않음
- 나는 원격·장치 작업을 하지 않았다.

## 다음 첫 행동과 담당

- **root:** Core 42001883513 최종 결과(특히 Linux symlink/POSIX case)를 확인한다. L1~L3를 반영할지 정한다. F5 분류기와 registry 계약에 `finalized`와 archive를 추가하는 일을 배정한다. 그다음 통합 source pin과 archive를 다시 만든다.
- **Codex:** 원하면 L1(같은 bytes의 `.next` 정리)과 L2(proof 정규화)를 고치고, L3 README 문단을 추가한다.
- **Claude:** 통합 source pin, archive, 분류기 계약 delta가 오면 검토한다.
