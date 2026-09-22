---
doc_id: "HIST-CLAUDE-ROUTE-COVERAGE-DOCS-GATE-001"
title: "route_coverage CLI를 docs.yml에 report-only로 배선 — exit 기록·job 미실패·step-summary·artifact, 승격 조건 명시"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T20:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["route-coverage", "ci", "docs.yml", "report-only", "wiring", "handoff-codex"]
---

# route_coverage CLI docs.yml report-only 배선

코디네이터 카드(2026-09-22): 신설 검사는 **report-only → 1주 green 후 ratchet 승격**([[검증규칙과_세축_canon]] 검사 등급). 브랜치 `agent/claude/route-coverage-docs-gate`, **PR #45(스캐너 사각 수정) 위 stack** — CLI가 수정된 도구로 돌아야 의미가 있다. `.github/workflows/*.yml`은 **Codex 소유**이므로 PR에서 Codex 검토를 요청하고 integration에 직접 push하지 않는다.

## 1. 배선 (docs.yml, `test_sync` 앞)

- step `Report client route coverage (report-only; …)`: `continue-on-error: true` + 스크립트 마지막 `exit 0` — **job은 절대 안 막는다**. 실제 exit는 `rc`로 잡아 (a) step-summary 제목 `exit=$rc`, (b) 로그 한 줄 `route_coverage exit=… (0=all served, 1=unserved, 2=no client paths)`에 남긴다.
- 서빙 트리는 `--served src --served services/control-plane/src`(`.` 대신) — `tests/`의 데코레이터 예시(`@app.websocket(...)` 등)가 서빙으로 세어져 unserved를 가리는 것을 막는다. 두 방식 모두 현재 43/0(측정, 아래).
- 출력: `route-coverage.json`(기계)·`route-coverage.txt`(사람) → `$GITHUB_STEP_SUMMARY`에 txt 전문, artifact `route-coverage-report`(30일, `if: always()`).
- 의존성: 도구는 stdlib만(argparse/json/re/pathlib) — docs job의 `requirements-docs.txt` 환경으로 충분. `--configured-surface`(fastapi 필요)는 쓰지 않는다.

## 2. 등급·승격 조건 ([[검증검사도구_목록]] v1.4.0에 기재)

- 지금: **report-only**.
- **ratchet 승격**: docs.yml에서 **1주 연속 exit 0** ∧ unserved 백로그 0 ∧ 인공물 오탐 0 → baseline=unserved **이름 집합**(수 아님)으로 새 unserved만 실패. 그 뒤 게이트는 [[검사_게이트승격_기준과_5검사_분류_Claude]] 기준.
- 실패 시 대응: unserved=라우트 카드(백엔드 레인) 또는 죽은 화면 경로 제거(Gemini); exit 2=스캔 입력 오류(경로/체크아웃).

## 3. 실측 (실제 수행)

| 검증 | 결과 |
|---|---|
| YAML 파싱(`yaml.safe_load`) | ok, docs job 14 steps |
| step 스크립트를 로컬 bash로 그대로 실행(`GITHUB_STEP_SUMMARY`=임시 파일) | **step exit 0**, summary에 `## Client route coverage (report-only, exit=0)` + 표 전문, `route-coverage.json` 파싱 ok(unserved []) |
| `--served .` vs `--served src --served services/control-plane/src` (수정 도구, 이 브랜치=#45 head 트리) | 둘 다 clientPaths 43 / unserved 0 (served 137 vs 36+60; tip `3d1892c0`는 resource-usage 라우트가 더해져 61) |
| hosted 실행 | **미실행** — PR이 뜨면 docs workflow가 `pull_request`로 돈다(경로 필터 없음). 첫 summary가 이 배선의 첫 증거. |

## 4. 인계

- **Codex(워크플로 소유)**: step 위치(test_sync 앞)·`continue-on-error`+`exit 0` 이중화가 과한지·artifact 이름·`--served` 트리 선택 검토. 승인 시 코디네이터 병합(#45 먼저).
- **Claude**: 1주 후 summary 이력으로 승격 판단 근거 수집(exit 0 연속 여부).
