---
doc_id: "HIST-PTY-INTENT-REPORT-20260912"
title: "2026-09-12 PTY-INTENT Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T00:24:11+09:00"
source_of_truth: "Git"
---

# 2026-09-12 PTY-INTENT Codex 검증보고

CX-01 / owner Codex / reviewer Claude pending. base fd32eda → 구현/clean Linux 검증 **146063417af071aca838578b4ad81c3eae533a03**, branch agent/codex/workspace-bridge, PR19 draft. [[2026-09-12_PTY-INTENT_Codex_착수]], [[Codex Workspace 편집과 PTY 및 원격 Git 계약]] v1.2.0 / ADR-074.

## 작업한 것

서버가 PTY 입력을 보내기 전에 의도를 durable commit한다. 새 `inv.terminal_frame_intents`는 command+sequence의 digest만 보관하며, 원문 입력/nonce/출력을 남기지 않는다. 현재 권한·attachment 검사와 같은 Run 잠금 안에서 insert/event를 원자 처리한다. 같은 순번의 다른 내용은 Node 호출 전에 거부한다.

intent는 실행 완료가 아니다. 검증된 Node 응답과 현재 권한·채널을 확인한 다음에만 기존 `terminal_frame_audit`와 완료 이벤트를 남긴다. 응답 유실/오류에는 intent만 남고, 미확정 순번 뒤 새 입력은 거부한다. 정확히 같은 frame 재확인 또는 poll/종료를 허용하며 poll 관측을 완료 증거로 만들지 않는다. Node의 기존 sequence/hash replay 및 부분 write 보호는 유지한다.

0034는 FORCE RLS, tenant 복합 FK, SELECT/INSERT 최소 권한, 불변 trigger를 적용한 일반 표 추가다. 0033까지 공개 이력과 기존 완료 audit를 보존한다. 기존 9개 definer 정의/권한 hash는 그대로이고 정책 head만 0034로 갱신한다. 운영 DB/Node에는 적용하지 않았다.

## 확인한 증거

| 검증 | 환경/결과 |
|---|---|
| `python tools/check_kernel_docker.py --prepared .work/sv-kernel-d0a636e96273/prepared.json --tests tests/integration/test_workspace_terminal.py tests/integration/test_definer_audit.py tests/integration/test_recovery_drill.py tests/test_migrations.py` | clean1460634 / 실제 Linux PTY·mTLS·일회용 PostgreSQL / **61 passed, 0 skipped, exit0** |
| `python -m pytest tests/core/test_workspace_api_boundary.py tests/core/test_recovery_verdict.py -q` | Windows / **25 passed, exit0** |
| `python .work/cx01_local.py upgrade` → `tools/check_migration_upgrade.py` | 독립 PostgreSQL / **21개 prior→head→replay 경로 exit0**, runtime grant·definer 정책·기존 sentinel 보존 |
| `git push origin agent/codex/workspace-bridge` | 1460634 / exit0 |
| 같은 SHA GitHub Actions | 6개 workflow 모두 계정 결제/한도 때문에 job 시작 전 failure. CI 성공 아님 |

61개는 실제 PTY7(기존3+새4), definer22, 복원12, offline migration20이다. 25개는 그래프3+복원 판정22다. 21개 upgrade는 별도 경로 수이며 일반 시험 개수와 합치지 않는다. 업그레이드 실행 중 문서 Evidence 2개를 추가해 종료 시 harness dirty=true였지만, 제품/시험/migration 소스는1460634 그대로임을 확인했다. Linux61은 clean SHA다.

새 PTY 시험은 (1) 전송 전 오류, (2) Node가 입력을 받은 뒤 응답 유실, (3) 잘못된 nonce 응답에서 intent의 선행 commit과 완료 부재를 확인한다. 새 TerminalService 인스턴스에서도 다른 내용/후속 순번이 Node 호출 전에 거부되고, 동일 frame 재확인 후 `ACK:intent-once`가 정확히 한 번 발생한다. 별도 tenant는 intent를 읽지 못하며 소유자 DELETE도 immutable trigger가 거부한다. (4) intent event 실패를 주입하면 전체 transaction rollback 및 Node 미호출을 확인한다.

[Linux61·source/binary hashes·cleanup](../Evidence/pty-intent-1460634-linux.json), [21개 upgrade](../Evidence/pty-intent-1460634-upgrade.json), [CI ID/annotation](../Evidence/pty-intent-1460634-ci.json). 기존 운영 2-PC/5대 인수, 장시간/부하, 모든 장애 종류를 통과한 결과가 아니다.

## 다음 첫 행동 / 담당

- Codex CX-02: 운영 credential 참조·회수·로그 경계, Storage 정본 및 운영 설정 계약을 구체화한다. CX-01의 F1/F2 독립 검토는 계속 추적한다.
- Claude CL-01: F1의 기존 잠금 재검증29c810f와 F2의1460634/ADR-074를 독립 검토한다. 작성자의 새 시험 성공을 독립 승인으로 바꾸지 않는다.
- Gemini GM-03: 미확정 입력에서 poll을 완료로 간주하지 않고 원 frame의 동일 재확인 또는 종료 안내를 연결한다. 새 nonce/후속 입력으로 우회하지 않는다. 실제 원격 브라우저 여정은 실행 profile 선행이다.
- CX-03 원격 profile 및 실제 7개 시험, CI 계정 제한, 운영 인수는 미완료. PR19 draft 유지, 검토 순서21→22→19.

이번 보강은 기존 S06/S08 부분 구현의 신뢰성 강화다. 전체48 task의 점수를 임의로 올리지 않는다. **전체 추정57.29% 완료 / 42.71% 잔여(표시55%/45%) 유지**. 전체 카드 done/최종 운영 합격 아님.

문서 검사·Obsidian 실제 전달은 아래 영수증에 기록한다.

## 전달 검사

- 2026-09-12T00:24:51+09:00: `python tools/check_docs.py` exit0(24 원본 hash, 274 versioned docs, 48 tasks), `python tools/check_ontology.py` exit0, 변경 Python4개 `black --check` exit0, `git diff --check` exit0.
- Obsidian 사전 check exit0: 관리444개, 변경11개, 충돌0. 실제 export는 다음 영수증으로 기록한다.
