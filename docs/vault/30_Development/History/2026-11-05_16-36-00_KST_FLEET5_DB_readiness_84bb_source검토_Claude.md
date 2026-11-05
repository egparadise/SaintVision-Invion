---
doc_id: "HISTORY-FLEET5-20261105-DB-READINESS-84BB-REVIEW-CLAUDE"
title: "2026-11-05 FLEET5 Codex DB readiness repair 84bbec6b 독립 source 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T16:36:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "d254fc6a"
task_ids: ["FLEET5-DATABASE-READINESS-20261105"]
tags: ["fleet5", "independent-review", "postgresql", "readiness", "claude"]
---

# DB readiness repair 84bbec6b source 검토

같은 Orca dispatch `ctx_5301317b669b` 안에서 받은 `msg_e22a2ee142c0` 요청을 처리했다. 판정은 앞선 Low-closure 검토 [[2026-11-05_16-32-00_KST_FLEET5_Low_closure_af5b_검토_Claude]]와 **따로** 적는다.

- 검토 대상: Codex `84bbec6bcf06f88a2f226972982bfad68fef5848`, branch `agent/codex/fleet5-database-readiness-20261105`, 부모 `5caa60df`(test-first), 그 부모 `59f0a3c2`
- 검토 시각: 16:33~16:36 KST
- 한 일: 정적 검토와 hosted 상태 조회
- 하지 않은 일: Docker나 test 실행, runtime 변경

## 무결성과 범위

- `deploy/lan/prepare-pilot-database.sh` blob은 `a5695cab0a955d0aeeedf40f6459458ccef6210a`로, relay 값과 일치한다.
- 통제된 회귀 test `tests/integration/test_lan_pilot_database_real_pg.py` blob은 `232528b317af817462811d21f4249358ba378480`이다. `5caa60df`와 `84bbec6b`에서 **같다**. 즉 test를 먼저 넣었고, fix가 그 test를 바꾸지 않았다.
- 59f 기준으로 docs 밖에서 바뀐 파일은 세 개뿐이다.
  - 위 script: `5caa→84bb` 변경은 readiness loop 한 줄에 `-h 127.0.0.1` 추가와 주석 2행
  - test 파일(신규)
  - `.github/workflows/core.yml`: LAN DB real-PG case 개수 assertion 1→2. skip, failure, error 0 조건은 그대로다.

## 판정: ACCEPT (source와 통제 증명), hosted Core는 pending

- **원인 모델이 맞다.** 공식 postgres image entrypoint는 init 중에 Unix socket 전용 임시 server(`listen_addresses=''`)를 띄우고 `POSTGRES_DB`를 만든 뒤 그 server를 멈춘다. 최종 server는 image 기본값 `listen_addresses='*'`로 TCP를 연다.
  - 수정 전: readiness가 Unix `SELECT 1`이었으므로 init 단계에서 통과할 수 있었다. 그러면 뒤의 role·권한 단계가 임시 server가 내려가는 시점과 경쟁했다.
  - 수정 후: 컨테이너 안 `127.0.0.1` TCP와 scram 인증(`--auth-host=scram-sha-256`)이 성공해야만 진행한다. 그러니 최종 server가 떠야만 지나간다.
- **나머지 경로도 일관된다.** 기존 container의 credential 확인(같은 script 99행 근처)과 `verify-pilot-database.sh`의 인증 확인은 이미 `-h 127.0.0.1`을 쓴다. readiness 뒤의 Unix socket 명령은 최종 server가 뜬 다음에만 실행되므로 문제없다.
- **통제 증명 설계가 올바르다.**
  - test는 실제 image entrypoint를 source하고 `docker_setup_db`를 gate로 붙잡아, 임시 Unix server가 떠 있고 DB를 만들기 전인 상태를 재현한다.
  - 그 상태에서 다음을 모두 확인한다.
    - `temporaryUnixSql`
    - `temporaryTcpRejected`
    - `targetDatabaseAbsent`
    - prepare가 아직 끝나지 않음(`pendingBeforeRelease`)
  - gate를 풀면 prepare가 성공하고 다음도 확인한다.
    - 최종 TCP SQL
    - 틀린 credential과 credential 없음이 거부됨
    - `hostAuthentication=scram-sha-256`
  - image ID와 entrypoint sha256을 기록한다.
  - real docker를 감싸는 shim은 PATH 앞에 둘 뿐 판정을 위조하지 않는다.
- **hosted 결과:**
  - baseline Core 41985493178(`5caa60df`)은 **failure**다. root가 "예상된 red"라고 측정한 값과 일치한다(새 case fail, 원래 case pass, skip 0).
  - repaired Docs 41987455119(`84bbec6b`)는 **success**다.
  - repaired Core 41987450905(`84bbec6b`)는 16:34:44 KST에 **in_progress**였다. 이 판정은 Core success를 포함하지 않는다.
- **범위 판단:** root의 표현대로 이것은 "일반 결함 증명"이다. 원래 Core 41982378091 guard 실패의 원인이 이것이었다는 증명은 아니다. 나도 그 원인을 판정하지 않았다.

## Low와 운영상 주의

- **Low(진단성):** readiness가 이제 password 인증까지 요구한다. 그래서 password 파일이 틀리면 원인 대신 "readiness timed out"으로 끝난다. 동작은 안전한 방향이다. 원하면 timeout 메시지에 "credential 또는 최종 server 미기동"을 적어 두면 된다.
- **59f archive 영향:** 이 script는 F5 source archive(`deploy/lan`, `a9f0a3b8…`)에 들어 있다. 59f archive를 몰래 고치지 않는다는 원칙대로, stage03을 이 수정과 함께 하려면 **새 source pin과 archive를 별도 revision으로 만들고 독립 검토**를 다시 받아야 한다. namespace와 artifact version도 함께 정한다. 기존 59f archive로 stage03을 하면 이 race가 그대로 남는다.
- 사용자가 "모든 PC가 설정되었다"고 확인했다는 root의 전달은 기록만 했다. 나는 원격 상태를 확인하지 않았다. 권한과 runtime도 바꾸지 않았다.

## 다음 첫 행동과 담당

- **root:** repaired Core 41987450905의 최종 결과를 확인한다. success이면 `84bbec6b` source를 받아들이고, 새 source pin과 archive revision(namespace와 artifact version 포함)을 계획한다. stage03은 그 revision으로만 한다.
- **Codex:** timeout 메시지 Low를 선택적으로 반영한다.
- **Claude:** 새 archive와 packet hash가 오면 검토한다.
