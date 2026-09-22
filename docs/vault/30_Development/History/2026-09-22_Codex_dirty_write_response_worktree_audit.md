# 2026-09-22 Codex dirty write-response worktree audit

## 판정

`C:\Project\SaintVision-Invion\.worktrees\codex-write-response-contract`의 미커밋 12개는 보존할 새 작업이 아니라, 통합에 이미 들어간 신선도 응답 변경의 이전 작업본이다. **삭제는 하지 않았다.** 사용자 확인 뒤 해당 worktree를 정리해도 되는 상태로 분류한다.

- dirty branch: `agent/codex/write-response-contract`
- dirty HEAD: `afe8b71ee9c9ecd9de4094a1bbcc97b90ee94b7a` (`docs: complete write response PostgreSQL evidence`)
- dirty 파일 최종 수정 시각: 2026-09-22 00:50 KST 전후
- 비교 대상: `origin/integration/all-agents-unified` at `0d7a6f54eb4ff2483419d8601e270cf710f78ac5` (2026-09-22 10:18:34 KST)
- 관련 통합 기능 커밋: `f1d95466` (`feat(api): expose durable run freshness times`, 2026-09-22 01:13:13 KST)
- 조사자: Codex / 이 기록은 dirty worktree를 변경하지 않는 read-only 조사에서 작성함

시간 순서와 내용이 일치한다. dirty 파일은 `f1d95466` 직전의 작업본이고, 그 커밋과 이후 통합 tip에서 이미 같은 기능이 더 완전한 설명 및 후속 변경과 함께 제공된다. 따라서 이것을 새 PC로 옮길 고유 코드로 세지 않는다.

## 12개 파일 대조

| 파일 | dirty 내용 | 통합 tip 대조 | 판정 |
|---|---|---|---|
| `contracts/fixtures/run-artifact-list.json` | `completedAt` fixture | 바이트 동일 | 중복, 버려도 됨 |
| `contracts/fixtures/run-log-view.json` | `completedAt` fixture | 바이트 동일 | 중복, 버려도 됨 |
| `contracts/fixtures/run-result-view.json` | `stateUpdatedAt`/`completedAt` fixture | 바이트 동일 | 중복, 버려도 됨 |
| `contracts/fixtures/shard-observation-response.json` | `stateAsOf` fixture | 바이트 동일 | 중복, 버려도 됨 |
| `contracts/v1alpha1/core.schema.json` | 네 freshness 필드와 required 추가 | 통합에 존재하며 dirty보다 설명이 완전함 | 오래된 생성물, 버려도 됨 |
| `packages/contracts-go/contracts.go` | 생성 Go 타입 네 필드 | 통합에 존재 | 중복된 이전 생성물, 버려도 됨 |
| `packages/contracts-ts/src/index.ts` | 생성 TS 타입 네 필드 | 통합에 존재 | 중복된 이전 생성물, 버려도 됨 |
| `services/control-plane/src/inv/generated/core.schema.json` | 생성 Python 서비스 스키마 | 통합에 존재하며 설명이 완전함 | 오래된 생성물, 버려도 됨 |
| `services/control-plane/src/inv/generated/models.py` | 생성 Pydantic 네 필드 | 통합에 존재하며 설명이 완전함 | 오래된 생성물, 버려도 됨 |
| `services/control-plane/src/inv/result_view.py` | `stateUpdatedAt`, artifact/log `completedAt` 서빙 | 통합에 동일 기능 + 후속 변경 | 기능 중복, 버려도 됨 |
| `services/control-plane/src/inv/shards.py` | `stateAsOf` 계산 및 `updated_at` 조회 | 통합에 동일 기능 + 후속 주석/변경 | 기능 중복, 버려도 됨 |
| `services/node-agent/internal/wire/core.schema.json` | 생성 wire 스키마 네 필드 | 통합에 존재하며 설명이 완전함 | 오래된 생성물, 버려도 됨 |

## result_view.py와 다운로드 정본 결정의 관계

dirty `result_view.py` 변경은 실행 결과의 durable freshness 시각만 추가한다.

- `RunResultView.stateUpdatedAt`: `inv.runs.updated_at`
- `RunArtifactList.completedAt` 및 `RunLogView.completedAt`: 결과 완료 시각
- 다운로드 본문을 DB 영수증에서 읽을지 저장 snapshot에서 읽을지 결정하는 코드는 변경하지 않는다.
- 따라서 이 12개를 보존한다고 다운로드 정본 결정이 보존되는 것이 아니며, 버린다고 그 결정의 작업이 사라지는 것도 아니다. 다운로드 정본은 사용자 결정 대기로 별도 유지한다.

## 보존/폐기 조치

이번 조사에서는 사용자 자산인 dirty worktree의 파일을 삭제하거나 reset하지 않았다. 사용자가 확인한 뒤 폐기하면 된다. 보존할 고유 코드가 발견되지 않았으므로 새 PC에서는 통합 tip을 clone하고 이 worktree의 12개를 옮기지 않는 것이 권고다. 폐기 전 마지막 안전 확인은 다음 두 조건이다.

1. `git -C .worktrees/codex-write-response-contract diff --name-only`가 위 12개뿐이다.
2. 새 PC clone의 통합 tip에서 `stateUpdatedAt`, `stateAsOf`, `completedAt`와 두 서빙 경로가 존재한다.

## 실행 근거

- `git status --short`로 dirty 파일 12개를 직접 열거했다.
- dirty branch HEAD와 수정 시각을 확인했다.
- `git fetch origin integration/all-agents-unified` 후 통합 SHA를 고정했다.
- 12개 각각의 dirty 파일을 통합 tip과 바이트/내용 대조했다.
- `git log -S`로 해당 기능의 통합 커밋 `f1d95466`을 확인했다.
- 이 기록은 제품 실행·PostgreSQL·브라우저·CI 검증이 아니다. 파일 보존 판단을 위한 정적 Git 대조다.
