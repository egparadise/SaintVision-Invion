---
doc_id: "HIST-WORKSPACE-BRIDGE-DELIVERY-001"
title: "2026-09-10_17-18-33_KST_WORKSPACE-BRIDGE_Codex_구현인계"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T17:18:33+09:00"
source_of_truth: "Git"
---

# Workspace 후속 구현 인계 — 실제 시험 미수행

**사용자 지시로 실제 테스트는 다음 단계로 미뤘다. 이번 증거는 구현·정적 검사·컴파일·문서 전달이다. AC-06/S06 완료·실제 장비 합격·독립 검토 완료를 뜻하지 않는다.**

task WORKSPACE-BRIDGE / S06-BE/DB/ST 부분 / OUT-06·AC-06. owner Codex / reviewer Claude pending. base `dac25591adfb61a4a81382f737c4d1eed34c07d5` / PR17. branch `agent/codex/workspace-bridge`, 구현 코드 SHA `20b488f64521fb9993bf2a6d310e3988130fd1d6`. [초안 PR #19](https://github.com/egparadise/SaintVision-Invion/pull/19), merge/deploy 없음. root integration worktree는 보존했다.

입력 문서/skill/base/task/scope는 [[2026-09-10_16-32-13_KST_WORKSPACE-BRIDGE_Codex_개발과정]], 새 계약은 [[Codex Workspace 편집과 PTY 및 원격 Git 계약]] v1.0.0 / ADR-057~060 / ADR index v1.18.0이다. 수정 이력은 [[2026-09-10_WORKSPACE-BRIDGE_정적검사_오류와해결]]에 분리했다.

## 구현된 범위

- 파일별/전체 hash와 revision CAS를 적용한 immutable editor, 현재 권한·동결 lock·물리 자원 반환 경계, 다음 승인/Node 입력과 동일 snapshot.
- 명시적 신뢰 대상 Node 선택과 새 승인, Node별 probe/resource/profile/key/claim/queue 연결.
- 제한 Linux PTY, 일회 browser ticket·Origin/session/epoch/권한 재검사, durable 단일 connection lease, 입력 순번·부분 write 차단·출력 redaction·backpressure.
- 고정 GitHub repo/branch/commit/snapshot, 현재 서로 다른 2인 승인, 원격 expectedHeadOid 조건, 불확실 dispatch의 재전송/중복 publication 차단과 읽기 전용 reconciliation.
- 0024 forward migration과 Python/Go/TS 정본 계약 생성, 테스트 보류를 명시하는 branch 한정 build-only CI.

## 실제 수행한 정적 검사·build

| KST 시작 | 명령 | exit code |
|---|---|---|
| 2026-09-10T17:11:04+09:00 | `python -m compileall -q services/control-plane/src src tests migrations` | 0 |
| 2026-09-10T17:11:04+09:00 | `python tools/export_schemas.py --check` | 0 |
| 2026-09-10T17:11:05+09:00 | `python tools/migration_graph.py` | 0 |
| 2026-09-10T17:11:05+09:00 | `python -m alembic upgrade head --sql` | 0 |
| 2026-09-10T17:11:07+09:00 | `python -m build services/control-plane --outdir WORKTREE\.work\build-only\dist` | 0 |
| 2026-09-10T17:11:04+09:00 | `go build ./...` | 0 |
| 2026-09-10T17:11:06+09:00 | `go build -trimpath -o WORKTREE\.work\build-only\inv-node-linux ./cmd/inv-node` | 0 |
| 2026-09-10T17:11:26+09:00 | `go build ./...` | 0 |
| 2026-09-10T17:11:31+09:00 | `go build -trimpath -o WORKTREE\.work\build-only\inv-node-windows.exe ./cmd/inv-node` | 0 |
| 2026-09-10T17:11:48+09:00 | `go build -trimpath -o WORKTREE\.work\build-only\inv-supervisor-linux ./cmd/inv-supervisor` | 0 |
| 2026-09-10T17:11:49+09:00 | `go build ./...` | 0 |
| 2026-09-10T17:11:04+09:00 | `npx --yes --package typescript@5.9.3 tsc --noEmit --strict packages/contracts-ts/src/index.ts` | 0 |
| 2026-09-10T17:13:12+09:00 | `python tools/check_docs.py` | 0 |
| 2026-09-10T17:13:12+09:00 | `python tools/check_ontology.py` | 0 |
| 2026-09-10T17:13:15+09:00 | `python tools/build_docs.py` | 0 |

Python 3.14 로컬 compile/package와 Go 1.27.1 Linux·Windows 교차 컴파일을 수행했다. CI는 Python 3.12다. Go binary를 실행하지 않았다. Alembic은 localhost:1의 가짜 offline URL을 사용한 `--sql` 출력이며 DB 연결/적용이 아니다.

추가 `python -m pyflakes`의 새/수정 핵심 Python 파일 검사, `git diff --check`, 계약 생성은 최종 exit 0. pyflakes의 미사용 import 3개를 제거했고 다시 검사했다. 마지막 header 제한/import 변경 뒤 compileall exit 0이며 같은 코드 SHA의 CI에서 package를 다시 생성했다. 실제 경합/보안 속성은 정적 분석만으로 확정하지 않는다.

`git commit` 및 `git push -u origin agent/codex/workspace-bridge` exit 0, GitHub API draft PR 생성 성공. 코드 커밋은 `20b488f`다.

## 코드 SHA의 CI 및 원본 artifact

| run ID | workflow/event | 결과 |
|---|---|---|
| [34454146614](https://github.com/egparadise/SaintVision-Invion/actions/runs/34454146614) | Backend Build / pull_request | skipped |
| [34454146367](https://github.com/egparadise/SaintVision-Invion/actions/runs/34454146367) | Frontend Build & Test / pull_request | skipped |
| [34454146505](https://github.com/egparadise/SaintVision-Invion/actions/runs/34454146505) | Documentation Build / pull_request | success |
| [34454146448](https://github.com/egparadise/SaintVision-Invion/actions/runs/34454146448) | Core Build / pull_request | success |
| [34454130630](https://github.com/egparadise/SaintVision-Invion/actions/runs/34454130630) | Backend Build / push | skipped |
| [34454130644](https://github.com/egparadise/SaintVision-Invion/actions/runs/34454130644) | Frontend Build & Test / push | skipped |
| [34454130696](https://github.com/egparadise/SaintVision-Invion/actions/runs/34454130696) | Documentation Build / push | success |
| [34454130748](https://github.com/egparadise/SaintVision-Invion/actions/runs/34454130748) | Core Build / push | success |

Core의 실행 test job, Backend·Frontend job, docs sync unit test는 사용자 요청으로 **skipped**다. 성공한 Core는 build_only이며 문서 workflow도 정적 검사/bundle만 수행했다. skipped를 시험 통과로 세지 않는다.

- run 34454146448 artifact 10142796058 `saintvision-build-only`: archive SHA-256 `848a6ecead48cea9f9ed4a0543b406d63e067ebaae92ff7c7d9fdde0f64da87d`. 다운로드한 validation-mode.json의 source SHA가 `20b488f64521fb9993bf2a6d310e3988130fd1d6`와 일치하고 mode=build-only, executionTests=deferred-by-user, hardwareTests=not-run, acceptance=pending임을 확인했다.
- run 34454130748 artifact 10142788934 `saintvision-build-only`: archive SHA-256 `5ae4ad317554a1d873551b4c35a2ad924402eeb90ddc71cda4479d3bf90809e7`. 다운로드한 validation-mode.json의 source SHA가 `20b488f64521fb9993bf2a6d310e3988130fd1d6`와 일치하고 mode=build-only, executionTests=deferred-by-user, hardwareTests=not-run, acceptance=pending임을 확인했다.

## Obsidian과 후속 책임

코드 SHA의 Obsidian 확인 시각 2026-09-10T17:15:34+09:00. `python tools/sync_obsidian.py --check` → `--apply` → `--check` 모두 exit 0, 285개 관리 파일 hash 일치, pending 0, conflict 0. 외부 편집/관리하지 않는 파일은 보존했고 OneDrive cloud 업로드 완료는 확인하지 않았다. 이 보고서가 추가된 최종 commit의 CI와 동기화 영수증은 PR 본문과 최종 인계에 기록한다.

**미수행:** pytest·Go test·실제 migration/restore·Node/container·원격 Git repository 조작·브라우저·물리 장비 시험. 회귀 시험 소스는 작성했으나 실행하지 않았다. 이전 PR17의 990 passes는 이번 변경의 근거가 아니다.

다음 Codex 작업은 branch의 테스트 제외 조건을 제거한 뒤 전체 실제 회귀, 0023→0024/기존 경로 upgrade·RLS·불변 이력, PTY/ticket/취소/부분 write, Node 이전/해시/Evidence, Git CAS/2인 승인/권한 회수/crash/응답 유실을 검증하는 것이다. Claude는 독립 코드/DB 검토·첫 Run/checkout/검증된 person 및 운영 provisioning·Git reconciliation 절차를 맡는다. Gemini는 실제 editor/Node 선택/PTY/Git 승인·불확실 상태 화면과 브라우저 여정을 맡는다. 타 Agent가 검토했다고 꾸미지 않는다.

현재 제한은 32 KiB 파일 내용·64 KiB manifest, 최대 30초/완성 줄 출력 PTY, GitHub regular files와 전체 snapshot pull이다. 원격에 이미 보낸 Git write는 kill로 회수되지 않으며 미확정 dispatch는 수동 검토가 필요할 수 있다. 대용량·다른 Git provider·장시간/ANSI terminal·Windows/GPU/BuildKit·Context/RO·5대 부하/장애/복구 인수는 후속 범위다.
