---
doc_id: "REPORT-RUNTIME-COMPLETION-001"
title: "Runtime completion Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T09:08:59+09:00"
source_of_truth: "Git"
---

# Runtime completion Codex 검증보고

Task RUNTIME-COMPLETION / owner Codex / 독립 reviewer Claude pending.
브랜치 `agent/codex/runtime-completion`, base `720b8ee8f4f53436d6316a138896fc6930617b58`, 통합한 이전 Codex `39bd9e97819deaca66eab0368910a7b446cbd4e1`.
검증한 제품 코드 SHA **`fee45a8e89bac7bf4fd63d19d98b49f791612949`**. [Draft PR #11](https://github.com/egparadise/SaintVision-Invion/pull/11).
GUIDE·Agent 역할·Git 운영·agent-delivery·core-reliability v1.0.0, ADR-040~043의 계약은 [[Codex 실행 완료와 자원 회수 통합 계약]]이다.

## 구현과 실제 검증

| 영역 | 구현한 동작 | 실제 시험 |
|---|---|---|
| 통합 | 최신 실행/저장/샤드 소스와 서비스 DB chain, offline SQL, disposable DB fixtures | 전체 PostgreSQL suite, Backend Python 3.12/3.14, migration forward 및 서비스 reverse |
| 자원 회수 | 미발급 예약은 별도 ledger로 회수, 미수신 명령은 Node tombstone 뒤 receipt 반환 | claim/cancel 경쟁, 실패한 두 번째 shard rollback, committed plan 보호, mTLS 취소, 지연 Execute/Node 재시작 |
| 출력·완료 | 성공 프로세스의 실제 stdout/stderr 바이트와 hash를 Node receipt→object→Evidence→Run에 연결 | 실제 Docker 출력, hash/크기/JSON 변조 거부, overflow 실패, receipt 후 CP 재시작, publication 장애·3회 제한 |
| Node 복구 | 정지 후보와 결과를 삭제 전에 fsync, 삭제 ACK 유실 시 같은 ID 부재로 receipt 복구 | Go race 및 삭제 응답 유실/지연 실행 시험 |
| 샤드 부모 | 현재 child 결과 검증 후 ordered manifest·부모 Evidence·succeeded, 실패/취소 전파 | 실제 child 컨테이너, parent 성공/실패, sibling 미실행 취소·자원 반환, 부모 확정 전 CP 재시작·동시 처리 |
| Workspace 사본 | readonly 복원본에서 별도 0600/0700 작업 사본, Step/attempt/epoch/inode 기록 | 실제 파일 수정 보존, 동시 replay, DB commit 유실, dirty 미커밋 거부, 취소, directory 교체 거부 |

## CI 및 Evidence

2026-09-10 09:08:59 KST에 GitHub artifact를 내려받아 실제 JUnit과 Go JSONL을 검사했다.

- [Core Build 34419653044](https://github.com/egparadise/SaintVision-Invion/actions/runs/34419653044): **Python 817 tests / 0 failures / 0 errors / 0 skipped**, Go **67 leaf cases**, race detector 통과. Python 제품 package·Go Node/discover binary·공통 계약 Go/TypeScript build 포함.
- [Backend Build 34419652983](https://github.com/egparadise/SaintVision-Invion/actions/runs/34419652983): Python 3.12/3.14 모두 성공.
- [Documentation Build 34419653073](https://github.com/egparadise/SaintVision-Invion/actions/runs/34419653073): 문서/ontology 성공.
- artifact ID `10130510423`, archive SHA-256 `d167b8ea8347e8a9b795e7972c1208c12f7b211cd9c80a821370f1c21eb4c25b`.
- Git 증거: `30_Development/Evidence/runtime-fee45a8-provenance.json`, `runtime-fee45a8-tests.xml`, `runtime-fee45a8-unit.jsonl`. JUnit SHA-256 `060cc199d9b9a05c129ad18785154a09ddc3278ff6bd117a540441885e1b4385`.

검증 명령: `python -m pytest --junitxml=dist/core-tests.xml`, `go test -race -json ./...`, `python -m build services/control-plane`, 계약 재생성 drift 검사, Go/TypeScript 검사. 모두 해당 CI에서 exit 0이다. 로컬 `python tools/check_docs.py`, `python tools/check_ontology.py`도 exit 0. Windows 로컬에서 Linux/실DB가 skipped된 결과를 위 제품 합격 수에 포함하지 않았다.

이 보고서 이후 문서/증거만 추가한 최종 PR HEAD의 push 및 pull_request Core/Backend/Documentation 결과는 PR 본문에 정확한 SHA와 CI ID를 고정한다. 코드 변경이 생기면 이 코드 SHA의 합격을 새 코드에 적용하지 않는다.

## Obsidian 동기화 및 인계

이전 전체 동기화 conflict 9개는 개별 원문 hash와 Git baseline을 대조하고 `runtime-sync-reviewed-proposals.json`에 원문 byte를 보존했다. 조정 후 전체 `--check`는 216 managed files / 14 pending exports / 0 conflicts, exit 0이었다. 최종 보고·증거를 추가한 후의 `--apply`와 사후 전체 hash 일치 수는 PR 본문 및 작업별 `.work/runtime-final.json`에 남긴다. 확인은 로컬 Obsidian 사본의 hash 기준이며 OneDrive 원격 업로드 완료를 측정한 것이 아니다.

Claude는 receipt/DB/parent lock 순서의 독립 검토, 실제 서비스 Adapter와 pool/placement 매핑을 이어간다. Gemini는 parent/child·실제 Evidence·자원 반환 대기·복구 화면을 실제 API에 연결한다. 실제 수신·독립 검토는 pending이다. 다른 Agent가 기본 폴더에서 수정 중인 auth/server 파일은 이 worktree에 섞거나 덮어쓰지 않았다.

## 남은 작업

Node mount와 새 Step 실행·PTY/Git 프로세스까지 연결한 Workspace 작업 재개는 미구현이다. writable checkout은 파일/재개 위치 준비까지다. 새 승인을 전제로 한 제한된 샤드 **실행** 재시도, 다중 Node 물리 통신·collective/reducer도 남아 있다. 현재 3회 제한은 결과 **확정** 재시도다.

kill switch/drain, Windows/GPU/BuildKit, 실제 Context/RO 평가, 5대 실장비 부하·분할·장애·복구·운영자 인수는 별도다. kernel CI 통과로 Sprint 전체나 운영 릴리스를 done 처리하지 않았다. main merge·운영 배포는 수행하지 않았다.
