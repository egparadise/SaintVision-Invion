---
doc_id: "REPORT-WORKSPACE-RESUME-001"
title: "2026-09-10_10-09-50_KST_WORKSPACE-RESUME_Codex_검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T10:09:50+09:00"
source_of_truth: "Git"
---

# WORKSPACE-RESUME 검증보고

Owner Codex, reviewer Claude pending. Task WORKSPACE-RESUME, S06-BE/DB/ST 및 S03-BE 후속, OUT-03/06/07·AC-03/06/07. base `92934d19213f4bda5bccfe1760373f59522ddccd`, 코드 SHA `4f7d5d5bcea6cd0879d93b56b2972d1adfb80b1a`, branch `agent/codex/workspace-resume`. [PR #12](https://github.com/egparadise/SaintVision-Invion/pull/12)는 PR #11을 base로 한 초안이다. main merge·운영 배포·독립 검토는 수행하지 않았다.

계약은 [[Codex Workspace 실행 재개와 결과 체크포인트 계약]] v1.0.0/ADR-044~045, 실행 기록은 [[2026-09-10_09-29-08_KST_WORKSPACE-RESUME_Codex_개발과정]]이다. Skill agent-delivery/core-reliability v1.0.0, 공통 지침 GUIDE-001/GOV-GIT-001/GOV-AGENT-001 v1.0.0을 사용했다. Prompt/Context/Graph/Harness의 실제 입력은 시작 기록과 코드 SHA에 연결하며 별도 모델/Agent/ROOF 버전을 추정하지 않는다.

## 구현과 확인

1. 현재 checkout의 고정 파일과 이전/다음 Step·checkpoint attempt·recovery attempt를 새 승인에 연결한다. Run version별 승인 이력을 유지하고 오래된 승인/입력 변경을 거부한다.
2. 새 lease·claim·서명 queue를 같은 transaction에 생성한다. admission 실패는 새 예약까지 rollback하며 실행 전 취소는 Node tombstone/정지 증명 뒤 반환한다.
3. Node의 private tmpfs에 실제 파일을 복원하고 UID 65532의 제한된 프로세스로 작업한다. 합성 CI 이미지 안의 실제 Git으로 init/add/commit/rev-parse를 수행하고 출력 commit SHA와 저장된 `.git/refs/heads/main`이 일치함을 확인했다. CP 원본 checkout의 이후 편집도 보존된다.
4. descendants를 종료/reap한 뒤 수정 파일을 수집하고, 실제 receipt/launch/input hash를 재검증한다. modified checkpoint·pin·Evidence·RunAttempt 완료를 원자 확정한다. CP 재시작 후 결과 확정은 프로세스를 다시 실행하지 않는다.
5. 새 checkpoint가 없는 중단 attempt도 이전 검증 checkpoint로 새 승인 기반 재개할 수 있다. 총 3 attempt(최초+최대 2회 재실행) 이후는 거부한다. 샤드 member/parent가 단독 Workspace 재개로 부모 연결을 벗어나는 경로도 거부한다.
6. Docker cleanup의 일시적인 transport/5xx/absence는 기존 4초 안에서 최대 3회 관측한다. 소유권·응답 형식 오류 또는 지속 장애는 receipt 없이 보류한다. 7개 결정론적 Go 경우로 확인했으며 create/start 재시도는 추가하지 않았다.

## 실제 검증

| 명령/검사 | 결과 | 코드·증거 |
|---|---|---|
| 로컬 Windows `python -m pytest tests/core -q` | exit 0, 195 passed | Linux/DB 실행으로 집계하지 않음 |
| 로컬 `python -m pytest tests/test_migrations.py -q` | exit 0, 17 passed | 0018 포함 offline migration |
| 로컬 Linux 대상 Go cross build 및 Windows Go test | exit 0 | 실장비 Windows 격리 driver 검증 아님 |
| CI focused Workspace recovery | 11개 통과 | 전체 시험에도 포함되므로 중복 합산하지 않음 |
| CI `python -m pytest --junitxml=dist/core-tests.xml` | exit 0, 846 passed, failure/error/skip 0 | [Core 34423762992](https://github.com/egparadise/SaintVision-Invion/actions/runs/34423762992) |
| CI `go test -race -json ./...` | 39 top-level / 93 leaf cases, skip/fail 0 | 실제 Linux Node 동시성·filesystem 시험 |
| 계약 재생성/Go·Python build/TS 계약 컴파일 | CI success | 같은 코드 SHA의 Core workflow |
| Docs/Ontology/source 원문 hash 검사 | success | [Docs 34423762963](https://github.com/egparadise/SaintVision-Invion/actions/runs/34423762963) |

실제 PostgreSQL/mTLS/Go/Docker/Git을 사용한 합성 시험이다. 5대 운영 장비·외부 IdP/PKI·브라우저 여정·모델 품질/SLO 인수 결과가 아니다. product execution 성공과 문서 검사 성공을 구별한다.

Artifact `10131988493`, archive SHA-256 `4352d474ea20d7304b59161ce441d214a7feebf766a92ded10fdaeb79c580783`, 검증 시각 `2026-09-10T10:09:35+09:00`. 저장 증거: `Evidence/resumecode-4f7d5d5-provenance.json`, `Evidence/resumecode-4f7d5d5-tests.xml`, `Evidence/resumecode-4f7d5d5-workspace-tests.xml`, `Evidence/resumecode-4f7d5d5-unit.jsonl`. 초기 승인 제약 및 중간 cleanup 관측 실패/해결은 [[ERR-WORKSPACE-001 복구 승인 유일 제약과 체크포인트 attempt]], [[RES-WORKSPACE-001 새 승인 버전과 이전 checkpoint 복구 정합화]] v1.0.1이다. 실패 CI를 통과로 집계하지 않았다.

## 보고서 전달과 남은 범위

보고서 후속 commit도 동일 SHA의 push/PR Core·Backend·Docs CI를 확인하고 PR 본문에 CI ID/Artifact 검증을 남긴다. 자기 SHA를 본문에 넣고 재커밋하는 루프는 만들지 않는다. Obsidian은 기존 export state와 외부 변경 충돌을 검사한 뒤 실제 동기화하고 PR 본문에 파일 수·hash 일치 결과를 기록한다. OneDrive cloud 업로드 자체를 확인했다는 뜻은 아니다.

현재 실행 한도는 파일 합 32 KiB/manifest 64 KiB, 기존 sandbox timeout/profile/lease 상한이다. 대용량 Workspace 전송·파일 수명, 인터랙티브 PTY·remote Git 인증/push·브라우저 통합, 샤드 재실행/다중 Node/collective, kill/drain·Windows/GPU/BuildKit·Context/RO·5대 장비 검증은 남는다. terminal failed/cancelled Run을 자동 부활시키지 않으며 coordinator는 물리 종료 후 recovering 상태를 선택해야 한다. 후속 owner Codex, 업무 Adapter/독립 review Claude, 화면·브라우저 검증 Gemini/Antigravity다. 실제 외부 메시지 전달·독립 검토는 pending이고 task-registry의 Sprint 완료 상태는 변경하지 않았다.
