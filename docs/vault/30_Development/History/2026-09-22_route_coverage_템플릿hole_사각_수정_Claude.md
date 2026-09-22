---
doc_id: "HIST-CLAUDE-ROUTE-COVERAGE-TEMPLATE-HOLE-FIX-001"
title: "route_coverage 스캐너 사각 수정 — 템플릿 hole 안의 함수 호출이 경로를 지웠다 (30/0 거짓 초록 → 43 경로, PR #36 트리 unserved 2 노출)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T19:15:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["route-coverage", "scanner", "false-green", "regression-test", "mutation-killed", "tooling"]
---

# route_coverage 스캐너 사각 수정

[[2026-09-22_PR36_NodeResourceUsage_UI_독립검토_Claude]] F3의 후속(코디네이터 카드 a). 브랜치 `agent/claude/route-coverage-template-holes`(PR #42 위에 stack — 검토 문서 정정을 같이 담기 위해).

## 1. 무엇이 잘못됐나 (원인 정정 포함)

- **증상**: PR #36 트리에서 `route_coverage.py --served . --client apps/web/src`가 **clientPaths 30 / unserved 0**을 냈지만 어댑터의 `/v1/nodes/{n}/resource-usage`는 어느 트리도 서빙하지 않았다(검토 F1). 도구가 그 경로를 **아예 못 본** 것.
- **원인(정정)**: 검토 v1.0.0에는 "변수에 조립한 URL"로 적었으나 틀렸다 — 스캐너는 파일 텍스트를 통째로 훑으므로 조립 여부와 무관하다. 진짜 원인은 **`${…}` hole 안의 함수 호출**: `_CLIENT`의 허용 문자 `[A-Za-z0-9_\-/{}$:.]`에 `(`·`)`가 없어 `\`/v1/nodes/${encodeURIComponent(nodeId)}/resource-usage\``가 통째로 불일치하고, 대체 경로 `_CLIENT_HEAD`의 head `/v1/nodes/`는 `/`로 끝나 prefix로 버려진다. 결과 = 경로 소멸.
- **범위**: 같은 모양이 `apps/web/src`에 **15곳(13 경로)** — `projects/{}/approvals/{}/review`, `runs/{}/result`, `runs/{}/logs`, `runs/{}/shards`, `runs/{}/artifacts/content`, `workspaces/{}/terminals/{}` 등 핵심 화면 경로. 즉 "30/0"은 SPA 경로의 약 1/3을 못 본 채 낸 숫자였다. **부류**: "검사는 했으나 대상 밖"(스캐너 모양지정 — [[2026-09-22_되돌아오는결함_구조가막나_주의에기대나_Claude]]의 route_coverage판).

## 2. 수정 (tools/route_coverage.py)

- `_flatten_template_holes(text)`: 백틱 리터럴을 걸어가며 `${…}`를 **중괄호 균형**으로 소비(중첩 `{}`·hole 안의 중첩 템플릿 포함)하고 `${x}`로 치환. `/v1/` 리터럴은 첫 `?` 이후(쿼리)를 자른다. `client_paths()`는 이 평탄화 텍스트에 기존 정규식을 그대로 적용 → 기존 판정은 유지되고 못 보던 것만 보인다.
- `_TRAILING_GLUED_HOLE`: 꼬리에 붙은 hole(`resolve${query}` → `resolve{}`)은 쿼리/접미 splice이므로 앞 endpoint로 귀속(`resolve`). 평탄화가 새로 드러낸 4개 인공물(`resolve{}`·`locations{}`·`replica-status{}`·`attempts{}`)을 unserved로 오보하지 않기 위함.

## 3. 회귀 시험 (tests/test_route_coverage.py) — 거짓 초록 재현 후 KILLED

| 시험 | 원본 도구 | 수정 도구 |
|---|---|---|
| `test_a_hole_containing_a_call_is_still_a_path` (`${encodeURIComponent(nodeId)}`) | **FAILED**(∅) | passed |
| `test_two_call_holes_and_a_url_built_in_a_variable` (PR #36 어댑터 모양 그대로) | **FAILED** | passed |
| `test_nested_braces_and_a_nested_template_inside_a_hole_are_consumed` | **FAILED** | passed |
| `test_a_query_string_after_a_v1_template_does_not_hide_the_route` | **FAILED** | passed |
| `test_a_hole_glued_to_the_end_is_a_suffix_splice_not_a_segment` | **FAILED** | passed |
| 기존 31 | 31 passed | 31 passed |

실행: `.venv/Scripts/python.exe -m pytest tests/test_route_coverage.py -q` — 원본 `tools/route_coverage.py`(HEAD)로 바꿔 돌리면 **5 failed / 31 passed**, 수정본으로 **36 passed**(1.33s). `test_flattening_does_not_change_what_was_already_found`가 기존 답 불변을 고정.

## 4. 제품 재측정 (수정 도구, 같은 명령)

| 트리 | 원본 도구 | 수정 도구 |
|---|---|---|
| integration tip `cf65a126` | 30 / unserved 0 | **43 / unserved 0** (새로 보인 13 경로 전부 서빙됨 — 거짓 초록이었으나 결과적으로 구멍은 없었다) |
| PR #36 트리 `96fa3ec6` | 30 / unserved 0 | **45 / unserved 2** = `/v1/nodes/{}/resource-usage`, `/v1/projects/{}/nodes/{}/resource-usage` |

즉 도구가 이제 F1을 **스스로** 잡는다. exit 1(unserved 있음)이 PR #36 트리에서 나온다 — 라우트 카드(오케스트레이션 Claude 워커 카드 3)가 착지하면 0으로 돌아와야 한다.

## 5. 남은 한계 (정직)

- 스캐너는 여전히 **정적 모양**만 본다(HTTP 메서드·인증·payload·live 가용성 미검증 — 도구 docstring의 한계 그대로). `/v1/` 리터럴이 아예 없는 호출(베이스 URL 상수 + 상대경로 결합)은 못 본다.
- 이 수정은 docs.yml/backend.yml에 CLI 배선을 추가하지 않는다(현재도 미배선; 시험만 pytest 수집). CLI를 게이트로 올릴지는 별도 결정(검증검사도구_목록 등급).

## 6. 인계

- **Codex(reviewer)**: 평탄화 워커의 이스케이프(`\\``)·중첩 처리 검토, `_TRAILING_GLUED_HOLE`가 실제 경로를 지우지 않는지(문자 뒤 `{}`가 진짜 매개변수인 경우 = 없음, `/` 뒤 hole만 매개변수).
- PR #36 검토 문서는 이 PR에서 v1.1.0으로 원인 정정(같은 브랜치에 포함).
