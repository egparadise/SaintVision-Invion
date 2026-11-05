---
doc_id: "HISTORY-FLEET5-20261105-DB-READINESS-864B-REVIEW-CLAUDE"
title: "2026-11-05 FLEET5 Codex DB readiness follow-up 84bb..864b 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T17:35:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "822da5bc"
task_ids: ["FLEET5-DATABASE-READINESS-20261105"]
tags: ["fleet5", "independent-review", "postgresql", "card150", "claude"]
---

# DB readiness follow-up 84bb..864b 검토

Orca task `task_ba13424828e2`, dispatch `ctx_0141888e33d0`. Codex branch `agent/codex/fleet5-database-readiness-20261105`의 `84bbec6b..864b49076c5aa4daa52419e04cb0e883e4df2163`(commit 1개)을 17:25~17:35 KST에 검토했다.

- 범위: 작은 의미 변경과 source binding만 본다. 앞서 ACCEPT한 84bb 기능 코드는 다시 검토하지 않았다.
- 한 일: diff 정독, hash 재계산, JSON 구조 비교, 임시 detached worktree에서 focused test 2개 파일 실행(끝난 뒤 제거)
- 하지 않은 일: 넓은 재실행, Docker, 원격·장치·runtime·admin 작업
- 기계 판독 결과: `Evidence/fleet5-20261105-claude/db-readiness-864b-followup-review.json`
- 앞선 기록: [[2026-11-05_16-36-00_KST_FLEET5_DB_readiness_84bb_source검토_Claude]]

## 바뀐 것

non-docs는 test 파일 1개, 1행이다. 나머지는 Evidence와 Codex History다.

1. `tests/test_core_workflow_cx01.py`: workflow 문자열 기대값 `assert len(cases) == 1` → `== 2`
2. `Evidence/card150-intranet-pki-lan-pilot.json`: `source.toolSHA256`과 `source.toolGitBlobSHA1`의 `deploy/lan/prepare-pilot-database.sh` 두 값
3. 새 Evidence: `authorized-tooling-metadata-extension.json`(승인 `msg_a1cf4c1ac80b`, 바뀐 field 2개), Core 실패 분류, 실행 경계 검증, hosted 사본, 로컬 gate 기록, 내 84bb 검토 사본

## 확인 결과

- **기능 bytes 불변:** 864b에서 `prepare-pilot-database.sh` blob은 `a5695cab0a955d0aeeedf40f6459458ccef6210a`이고, real-PG test blob은 `232528b317af817462811d21f4249358ba378480`이다. 84bb와 같다. `.github`, `deploy`, `services`, `tools`에는 변경이 없다.
- **두 hash 값이 맞다:** 864b의 script를 내가 다시 계산하면 sha256 `60bebe1164e60242b56578b6afda468ca0ff3565662fce644a86472e41cd2266`이다. 예전 값 `200c49a9…`/`0a5572cb…`는 `59f0a3c2`와 `5caa60df`의 script와 일치한다. 즉 바뀐 것은 정확히 "84bb repair 전 → 후" 한 쌍이다.
- **역사 값 보존:** 84bb와 864b의 Card150 JSON을 구조적으로 비교했다. 다른 경로는 위 두 field뿐이다. `observedAt`, `controlPlaneToolingCommit`, `agentImageSourceCommit`, 관측 상태, 다른 hash는 그대로다.
- **이 map은 "현재 tooling" binding이다:** `tests/test_intranet_pki.py:219-235`는 각 `toolSHA256`이 `toolGitBlobSHA1` blob의 hash와 같은지, 그리고 그 blob이 `HEAD:<path>`와 같은지 확인한다. 역사적 관측 시점의 tooling commit(`dea0a2b3`)의 script blob은 `bd418274…`로 예전 값과도 다르다. 그래서 이 map은 원래부터 관측 시점이 아니라 현재 HEAD에 묶여 있었다. 앞선 tooling 수정 `18dbea2e`, `6af107b8`도 같은 map을 고쳤다. 이번 두 field 수정은 그 뜻에 맞고 역사 관측을 바꾸지 않는다.
- **gate가 약해지지 않았다:** 864b의 `core.yml`(300~302행)은 case 2개, `skipped` 0, `failure`/`error` 0을 그대로 요구한다. unit test의 1→2는 84bb에서 이미 workflow를 2로 바꾼 것을 따라간 것이다. 그때 이 unit literal을 함께 고치지 않은 것이 repaired Core 실패 2건 중 하나였다.
- **내 검토 사본:** Codex가 보관한 `independent-review-84bb-claude.json` blob `fd0ac85d`는 내 branch의 `db-readiness-84bb-review.json`과 byte까지 같다.
- **내 실행:** 864b detached worktree, main `.venv` Python 3.14.7, `-B`, cache 없음. `tests/test_core_workflow_cx01.py tests/test_intranet_pki.py`가 **11 passed in 1.81s**였다. root가 잰 11 pass와 같다. worktree는 제거했다.

## hosted (17:33:54 KST 확인)

| run | head | 상태 |
|---|---|---|
| Docs 41993283674 | `864b4907` | completed **success** |
| Core 41993280120 | `864b4907` | **in_progress**. 성공으로 세지 않는다 |
| repaired Core 41987450905 | `84bbec6b` | completed **failure**(8875 pass / 2 fail / 46 skip / 2 deselect). 실패 2건은 위 unit literal과 현재 tooling pin이었다. 기록으로 남는다 |

## 판정

**`84bb..864b` follow-up ACCEPT(source와 binding).** 기능 bytes는 그대로이고, 바뀐 두 hash는 실제 bytes와 맞으며, 역사 관측 값은 보존됐다. gate도 약해지지 않았다. 다만 이 판정에 Core 41993280120의 성공은 들어 있지 않다. 새 Core가 success로 끝나야 84bb repair 전체를 받아들일 수 있다.

**Low(설계, 이번 수정과 무관):** Card150 test는 현재 HEAD tooling을 역사적 관측 Evidence 안에 묶어 둔다. 그래서 pin된 tool을 고칠 때마다 역사 파일을 손대야 하고, 오늘처럼 별도 승인이 필요해진다. 나중에 "관측 당시 tooling"과 "현재 tooling binding"을 다른 파일로 나누면 이 일이 반복되지 않는다. 지금 바꿀 필요는 없다.

## 기록만 한 relay (판정하지 않음)

- CP plan `822da5bc`와 guard `17447988`의 33 pass는 root가 받아들였다. guard 최종 `e62a` 보고 완료, Core(1744) success.
- S1: source worker `ctx_4194506d5037`가 실제 2회 rotation(7→8, 8→9)에서 `finalized installed=True` 해석 때문에 막힌다고 따로 확인했다. live 변경은 없었다. source fix는 root가 relay한다.
- 물리 mapping은 사용자가 CP SSH로 정리했다(legacy worker1 = PC2, worker2 = PC4, worker3 = PC3). NewPC1은 CP 공개 key와 Docker가 없다. root가 기존 coordinator 공개 key를 사용자에게 보냈다. 나는 계정이나 key를 추정하지 않았다.
- root는 PC4에 project별 새 storage 폴더와 cap-drop read probe만 준비한다. active r5는 유지한다. Node enroll과 init은 새 source pin과 operator 날짜·P2를 기다린다.

## 다음 첫 행동과 담당

- **root:** Core 41993280120의 최종 결과를 확인한다. success이면 84bb repair를 받아들이고 새 source pin과 archive revision을 계획한다(59f는 고치지 않는다).
- **Codex:** Core가 실패하면 실패 case만 분류해 다시 보낸다. Low는 선택 사항이다.
- **Claude:** 새 archive와 packet hash, S1 source fix가 오면 검토한다.
