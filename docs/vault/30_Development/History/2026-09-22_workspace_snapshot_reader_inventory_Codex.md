---
doc_id: "HISTORY-2026-09-22-WORKSPACE-SNAPSHOT-READERS-CODEX"
title: "Workspace snapshot 파일 reader 인벤토리"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-22T03:25:00+09:00"
source_of_truth: "Git"
---

# Workspace snapshot 파일 reader 인벤토리

## 판정

저장된 Workspace snapshot은 코드상 읽는 경로가 있지만, 현재 tracked product tree에서 운영 경로가 그 reader에 도달하지 않는다. 복구·재개 용도의 reader 구현과 시험은 있지만 product composition은 연결되지 않았다.

1. `output_ingestion.py`는 승인된 Node receipt에서 workspace snapshot을 추출하고 `inv.workspace-output:<tenant>:<command>` ID로 `SnapshotStore`에 저장한다. 이어 `workspace_resume.py::commit_workspace_output`가 동일 ID를 찾아 `files.read(object_key(...))`로 물리 객체를 receipt snapshot과 대조하고, `inv.checkpoints`와 `inv.checkpoint_objects`에 체크포인트를 pin한다. 이 첫 read는 ingestion/commit 시점의 검증이다.
2. 이후 reader 구현은 `SnapshotStore.restore` (`snapshots.py`)와 `WorkspaceRecovery.restore` 및 `WorkspaceRecovery.checkout` (`workspace_recovery.py`)다. 둘 다 `checkpoint_objects`에서 object ID를 찾고 provider의 `files.read`로 저장 파일을 읽는다. `WorkspaceRecovery.restore`는 복구 generation에 게시하고, `checkout`은 같은 checkpoint bytes를 복구 generation과 writable checkout generation으로 게시한다. 이는 물리 snapshot이 쓰기 직후 검증만 하고 버려지는 데이터는 아니라는 코드 근거다.
3. 산출물 GET은 다른 경로다. `ResultView._files`는 실행 receipt의 output bytes에서 workspace snapshot을 재구성한다. 이 경로는 저장된 `inv.workspace-output` 객체를 열지 않는다. 그러므로 앞선 부정 대조(저장 파일 변조에도 HTTP 200 receipt bytes)는 artifact download의 원본 선택을 말하며, recovery reader의 부재를 뜻하지 않는다.

## 제품 호출 연결 조사

시험 파일을 제외한 tracked product source에서 `WorkspaceRecovery`는 클래스 정의 한 건만 있고 import/생성·`recovery.restore`·`recovery.checkout` 호출은 없다. `configured_workspace`는 `WorkspaceAPI`와 `WorkingGenerations`만 조립한다. FastAPI에는 resume prepare/enqueue/status 라우트가 있지만 restore/checkout 라우트는 없다. `WorkspaceAPI.prepare`는 `WorkspaceResume._prepare`를 통해 `inv.workspace_checkouts` 행을 요구하며, 이 행을 쓰는 코드는 `WorkspaceRecovery.checkout`뿐이다. 현재 product composition에는 그 연결이 없다. queue/outbox/event consumer에서도 WorkspaceRecovery 호출이나 checkpoint object read가 발견되지 않았다.

`SnapshotStore.restore`는 integration tests와 `tools/remote_workspace_entry.py`에서만 호출되며, 그 도구의 모듈 설명은 private container entry 및 isolated test database라고 명시한다. WorkspaceRecovery 인스턴스도 integration tests에서만 생성된다. 따라서 “reader 구현이 있다”와 “시험/격리 도구가 읽는다”는 참이고, “제품 운영 흐름이 읽는다”는 현재 tracked tree 기준으로 거짓이다. 외부의 미추적 배포 wrapper가 클래스를 직접 조립하는지까지는 이 저장소만으로 단정하지 않는다.

결과적으로 workspace-output은 completion 트랜잭션에서 receipt와 일치함을 검사하는 제품 read 외에는 현재 제품 후속 consumer가 없다. checkpoint pin은 저장 객체를 GC 보호하므로 복구 wiring이 연결되지 않은 동안에도 저장 공간을 차지한다. 저장/pin 기능을 운영 복구에 연결할지, 미착지 상태에서 어떻게 보존할지는 제품·운영 결정으로 남긴다.

## 부재 주장과 방법

범위는 tracked control-plane Python, FastAPI route/composition, tools, apps, migrations, queue/outbox/event consumer 및 tests다. `git grep`로 `WorkspaceRecovery`, `workspace_recovery`, `recovery.restore`, `recovery.checkout`, `workspace_checkouts`, `checkpoint_objects`, `SnapshotStore.restore`, `workspace-output`, 관련 event names, `object_key`/`files.read`를 조사했다. 이어 `app.py`, `workspace_config.py`, `workspace_api.py`, `workspace_resume.py`, `workspace_recovery.py`의 조립→route→필수 checkout row→유일 writer 관계를 읽었다. 따라서 부재 판정은 이름 검색만이 아니라 설정·route·데이터 선행조건·writer까지 맞춘 정적 호출 그래프 근거다. 부재 범위는 저장소의 tracked product tree이며 외부 runtime wrapper는 미확인이다.

## Provenance와 검증 경계

- SHA: `993cfaf068f3da1df09f402399e75ea3aa55711d`; branch/worktree: `integration/all-agents-unified`, `C:\Project\SaintVision-Invion`.
- `git status --short`는 dirty였다(동시 작업 중인 `.gitignore`, Gemini frontend test/fixture 및 진행판 파일, 앞선 artifact-download History/JUnit 포함). 이 감사는 제품 코드나 테스트를 수정·실행하지 않았다.
- 읽기 전용 소스/호출자 인벤토리다. 실제 복구 API, 배포 composition, physical-node 재개는 실행하지 않았다. 테스트 파일의 물리 복원 단언은 기존 증거이지 이번 실행 결과가 아니다.
- 문서 사후 확인(03:25 KST, 같은 SHA/worktree): `C:\Python314\python.exe tools/check_docs.py` exit 0 (24 original hashes, 707 versioned documents); `C:\Python314\python.exe tools/sync_obsidian.py --check` exit 0, 1508 managed / 4 pending exports / 0 conflicts, read-only. Pending export는 적용하지 않았다.
- 검사 시 origin integration ref가 `b1b97d13`으로 한 커밋 앞서 있었고, `git diff --name-only HEAD..origin/integration/all-agents-unified`상 그 커밋은 History 문서만 바꿨다. 따라서 제품 소스 감사 범위에는 영향을 주지 않지만 이 결과는 local SHA `993cfaf`에 귀속한다.
- provider 연결/정본 선택은 변경하지 않았다. `.work` 잔여도 삭제하지 않았다.

## 다음 행동

제품/운영 owner가 (A) recovery/checkout composition과 운영 route/worker를 연결할지, (B) 연결 전까지 저장·pin을 유지할 근거 및 용량 정책을 어떻게 할지 결정한다. artifact GET의 receipt/provider 정본 선택은 별도 사용자 결정이다. 이번 조사에서 어느 설계도 구현하지 않았다.
