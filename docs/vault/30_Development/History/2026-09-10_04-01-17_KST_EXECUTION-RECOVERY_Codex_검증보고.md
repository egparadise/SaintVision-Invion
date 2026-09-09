---
doc_id: "REPORT-EXECUTION-RECOVERY-001"
title: "Codex 실행 결과와 파일 복구 및 배치 검증 보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T04:01:17+09:00"
source_of_truth: "Git"
---

# Codex 실행 결과와 파일 복구 및 배치 검증 보고

Task execution-recovery / owner Codex / reviewer Claude(pending). Branch `agent/codex/execution-recovery`, base `227cd2984a256092f5496d9895060092cbf87145`. 시작 2026-09-10T03:30:38+09:00. 사용자의 Codex 전체 담당 구현 착수 요청에 따라 [[Codex 전체 후속 구현 실행표]]를 만들고 실행 순서의 첫 네 영역을 구현했다. 나머지 영역은 의존성과 합격 증거를 기록했으며 구현·실장비 시험에 착수했다고 표기하지 않는다.

읽은 입력은 GUIDE/GOV-Agent/GOV-Git/Backend·DB·Storage/task registry v1.0.0, ADR-INDEX v1.9.0, agent-delivery/core-reliability v1.0.0. 결과 계약은 EXECUTION-RECOVERY-CONTRACT-001 v1.0.0 및 ADR-036~039(ADR-INDEX v1.10.0)이다. S04/S05/S06/S07/S08/S11의 공통 계약·무결성·복구 관련 부분을 다루며 48 Task/12 Outcome의 전체 완료 상태를 올리지 않았다.

## 구현과 동일 SHA 증거

| 범위 | 구현 SHA | 검증 결과 | CI |
|---|---|---|---|
| 실행 결과 확정 | `4bbf76c902a6f146d0b49bb26b99938c728f63a6` | Python 349 / Go race 62 leaf, 실패·오류·skip 0 | [Core #34389992848](https://github.com/egparadise/SaintVision-Invion/actions/runs/34389992848), [Docs #34389992824](https://github.com/egparadise/SaintVision-Invion/actions/runs/34389992824) |
| Workspace 파일 복원 | `210c3d3cd129ba601579acdc06129175cceb20e9` | Python 385 / Go race 62 leaf, 실패·오류·skip 0 | [Core #34390648488](https://github.com/egparadise/SaintVision-Invion/actions/runs/34390648488), [Docs #34390648608](https://github.com/egparadise/SaintVision-Invion/actions/runs/34390648608) |
| 샤드 결과와 전체 취소 | `d06bce47c6cf684f6f624228e755e311e570b0e9` | Python 388 / Go race 62 leaf, 실패·오류·skip 0 | [Core #34390986527](https://github.com/egparadise/SaintVision-Invion/actions/runs/34390986527), [Docs #34390986611](https://github.com/egparadise/SaintVision-Invion/actions/runs/34390986611) |
| 실측 CPU/RAM 배치·권한 수정 포함 전체 | `ee7132cd8e59d264bd81e1cb3d3d96e81f56d63e` | Python 400 / Go race 62 leaf, 실패·오류·skip 0 | [Core #34392036680](https://github.com/egparadise/SaintVision-Invion/actions/runs/34392036680), [Docs #34392036686](https://github.com/egparadise/SaintVision-Invion/actions/runs/34392036686) |

위 수치는 누적 전체 suite 결과이며 영역별 수치를 합산하지 않는다. Linux/PostgreSQL 16/Docker, 실제 Python mTLS→Go Node 전달, DB migration·동시성·실패 경계, Python package 빌드, 생성 계약 drift와 Go/TypeScript 검증을 포함한다. 대상 운영 장비의 성능·보안 인수 증거는 아니다.

- results: [[results-4bbf76c-tests.xml]], [[results-4bbf76c-unit.jsonl]], [[results-4bbf76c-provenance.json]]; artifact #10119379747, 실제 수신 2026-09-10T03:41:30+09:00. archive와 각 file SHA-256을 검사했다.
- workspace: [[workspace-210c3d3-tests.xml]], [[workspace-210c3d3-unit.jsonl]], [[workspace-210c3d3-provenance.json]]; artifact #10119603531, 실제 수신 2026-09-10T03:46:41+09:00. archive와 각 file SHA-256을 검사했다.
- shards: [[shards-d06bce4-tests.xml]], [[shards-d06bce4-unit.jsonl]], [[shards-d06bce4-provenance.json]]; artifact #10119750980, 실제 수신 2026-09-10T03:49:49+09:00. archive와 각 file SHA-256을 검사했다.
- placement: [[placement-ee7132c-tests.xml]], [[placement-ee7132c-unit.jsonl]], [[placement-ee7132c-provenance.json]]; artifact #10120154499, 실제 수신 2026-09-10T04:01:12+09:00. archive와 각 file SHA-256을 검사했다.

- 결과 확정: 최초 execute 예약에서 불변 attempt·allocation proofs를 고정하고, 준비된 결과 bytes/pin·Evidence·현재 Run 성공·outbox를 검증/transaction으로 연결했다. 물리 반환 뒤 Lease를 재발급하지 않고 완료할 수 있다. 취소·복구·다른 epoch·손상·무효 receipt는 거절한다. 출력은 시험용 trusted verifier가 제공했으며 Node의 실제 출력 자동 추출은 후속이다.
- Workspace: 실제 파일과 빈 directory를 snapshot하고 별도 private root의 새 generation으로 복원한다. 경로/대소문자 충돌·link·FIFO·권한/내용 변조·commit 실패/replay를 검증했다. raw 16MiB/직렬화 24MiB 한도이며 기존 폴더 덮어쓰기나 writable 실행·Step/PTY/Git 재개는 구현하지 않았다.
- 샤드: 물리 종료와 결과 성공을 분리하고 모든 결과가 확정된 뒤에만 정렬된 manifest를 반환한다. 전체 취소는 원자적이며 물리 Lease는 실제 receipt 뒤에만 반환한다. 실패 receipt 반영을 추가했다. 두 합성 샤드의 같은 Node 순차 시험이며 parent Run/reducer/MPI/NCCL/다중 물리 Node 통신 시험은 아니다.
- 배치: 현재 권한·유효한 실측 CPU/RAM·clock·활성 Lease에서 가중치 Explain과 실제 reservation을 함께 저장한다. project 상한은 기존 직접 Lease 경로도 검사한다. 8개 동시 혼합 예약·rollback·미래/오래된/폐기 관측·권한 실패를 검증했다. 산술 시험은 mTLS 관측 이후 고정 합성 카운터를 쓰며 실제 host 성능으로 주장하지 않는다. GPU/locality와 독립 pool 상한은 아직 없다.

## 실행 명령과 오류

- 로컬 Python: `C:/Project/SaintVision-Invion/.venv/Scripts/python.exe -m pytest -q -r fE`, exit 0, 171 passed/229 skipped. Windows에 없는 Linux/격리 DB 시험은 위 CI에서 모두 실행했다. 전체 400개 중 CI skip은 0이다.
- `python tools/check_docs.py`, `python tools/check_ontology.py`, `python tools/test_sync.py`, `git diff --check`: 구현 시와 최종 보고서 작성 뒤 exit 0. 131 versioned documents/48 Task/12 Outcome, SHACL 및 동기화 보호 시험 3개를 확인했다. 문서 검사를 제품 build/실장비 시험으로 세지 않는다.
- 네 구현 commit과 권한 수정 commit의 `git commit`/origin 작업 branch `git push`: exit 0. 최종 보고서 commit SHA의 push/PR CI는 PR에 별도로 고정한다. main merge와 운영 배포는 이 인계 범위에 포함하지 않는다.
- 최초 배치 `d4ffcfb4683493889fe8ebadabb581f13bea234b`: [Core #34391576304](https://github.com/egparadise/SaintVision-Invion/actions/runs/34391576304) 실패(8 failed/391 passed/0 skipped), [Docs #34391576386](https://github.com/egparadise/SaintVision-Invion/actions/runs/34391576386) success. `SELECT FOR SHARE`의 권한 누락을 `UPDATE(lock_sentinel)`만 부여하는 최소 권한 설정으로 수정했다. enabled 변경/삭제 거절 및 sentinel CHECK 회귀 시험을 추가하고 위 `ee7132cd8e59d264bd81e1cb3d3d96e81f56d63e`에서 전체 재검증했다. [[ERR-PLACEMENT-001 프로젝트 Node 잠금 권한 누락]], [[RES-PLACEMENT-001 고정 sentinel 권한과 변경 차단 검증]].
- 재개 환경의 기본 Python/gh 인증 설정은 기존 가상환경·저장소 인증으로 처리했다. [[ERR-EXECUTION-001 재개 환경의 Python과 GitHub CLI 설정]], [[RES-EXECUTION-001 기존 가상환경과 저장소 인증으로 검증 재개]]. 인증 자료를 보고서·로그에 기록하지 않았다.

## 다음 담당자와 실제 잔여 작업

정확한 API/권한/호출 순서는 [[Codex 결과 확정과 Workspace 복구 및 배치 계약]]을 따른다. 특히 결과 prepare는 권한이 유효하고 CP가 stop receipt를 기록하기 전에 필요하다. 현재 NodeDelivery는 receipt를 즉시 기록하므로 Node 출력 publication과 trusted 업무 verifier 연결이 완료되어야 실제 결과 수집 여정이 성립한다.

| 담당 | 다음 구현·검토 |
|---|---|
| Codex | Node 출력 publication/검증 순서, writable Workspace/Step 재개, parent Run·통신/reducer·미전송 취소 receipt, 실제 pool/locality·Node 복제/cache pin·대형 S3, kill/drain·Windows/GPU/BuildKit, Context/RO·부하/장애/5대 인수 |
| Claude | 후보/풀/Workspace/Run 업무 API Adapter, project 권한·결과 의미 검증, 일반 migration·DB 계보 통합, S02/S05/S07 차이와 위 최소 잠금 권한의 배포 설정, 기존 heartbeat/backup/미래값 지적 수정, 이 변경 독립 검토 |
| Gemini | 후보 목록·세 용량 숫자·배치 Explain 및 실행/물리 종료/결과 확정/복원 generation을 실제 API에 연결하고 브라우저로 검증 |

현재 source lane의 커널과 Claude 업무 앱/Gemini 화면의 단일 제품 흐름은 통합 미완료다. 운영 IdP/CA/DNS/Storage 제품·실제 5대 정보와 인수 시험도 미확인이다. 독립 reviewer의 수신·승인 또는 다른 Agent의 작업 완료를 대신 기록하지 않는다. reviewer receipt는 pending이다.

## Obsidian 실제 동기화

최종 검사 후 `.work/execution-obsidian-sync-state.json`으로 충돌 검사와 실제 export를 진행하고 명령 결과·KST 시각을 아래에 기록한다. 외부 수정과 미관리 파일은 보호한다. 최종 보고서 SHA-256과 최종 CI는 draft PR 인계에 기록한다.

- 2026-09-10T04:01:42+09:00 `python tools/sync_obsidian.py --check --state .work/execution-obsidian-sync-state.json`: exit 0; `CHECK: 200 managed files, 24 pending exports, 0 conflicts. No writes.`.

- 2026-09-10T04:01:43+09:00 `python tools/sync_obsidian.py --apply --state .work/execution-obsidian-sync-state.json`: exit 0; `EXPORTED: 24 files; all 200 destination hashes match. Unmanaged files untouched.`.

이 실제 결과를 포함한 보고서도 재export하고 전체 hash 일치를 확인한다. 최종 보고서 hash·재export 결과와 최종 commit의 동일 SHA CI는 draft PR에 기록한다.
