---
doc_id: "HIST-CODEX-2026-09-22-CORE-CONTAINER-OPTIN"
title: "hosted Core 컨테이너 레인 opt-in 검증"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-22T20:41:00+09:00"
source_of_truth: "Git"
---

# hosted Core 컨테이너 레인 opt-in 검증

- owner: Codex
- 독립 reviewer: Claude
- 기준 integration: `8bd53c70`
- PR 최신 동기화 기준: `4f77e6d5`
- 워크플로 구현: `0d02f343048f74d856bc1c7bf5a2bffadaa39493`
- PR: [#59](https://github.com/egparadise/SaintVision-Invion/pull/59)
- 선행 분류: Claude PR #50, Core run `35706465645`, artifact `saintvision-core-evidence`

## 1. 변경

`core.yml`의 기존 전체 pytest 컬렉션 안에서 컨테이너 의존 시험을 한 번만 실행하도록 세 opt-in 입력을 제공했다.

1. `INV_TEST_ROLE_GUARD_IMAGE=postgres:16`: Backend와 같은 명시적 PostgreSQL 이미지 입력이다. 별도 focused step을 만들지 않아 Core 컬렉션에서 13건을 중복 없이 한 번 실행한다.
2. `INV_TEST_SERVER_IMAGE`와 `INV_TEST_CONFIG_IMAGE`: Core가 직접 빌드하고 non-root 설정을 확인한 production API 이미지의 immutable `sha256:` ID를 사용한다.
3. `INV_CONTAINER_TEST_DB_HOST`: candidate 컨테이너가 Docker 기본 bridge에서 host에 publish된 PostgreSQL 5432로 접근하도록 bridge gateway를 계산한다. runner별 service container IP를 가정하지 않으며, pytest 전에 `pg_isready`로 연결을 확인한다.

이에 따라 skip ratchet에서 다음 세 사유만 제거했다.

| 제거한 skip 사유 | 기존 수 | 실행 전환 |
|---|---:|---:|
| `Explicit local PostgreSQL image required; ambient databases are never used` | 13 | role guard 13/13 |
| `Explicit candidate image and disposable container DB address required` | 8 | server container 8/8 |
| `Explicit pinned local candidate image required` | 2 | config container 2/2 |
| 합계 | **23** | **23/23** |

## 2. hosted 실측

- run: [Core Build 35720205341](https://github.com/egparadise/SaintVision-Invion/actions/runs/35720205341)
- job: `106721077307`
- trigger/ref: `workflow_dispatch` / `agent/codex/core-container-optin`
- exact head: `0d02f343048f74d856bc1c7bf5a2bffadaa39493`
- 결과: `success`, 22분 9초
- artifact: `saintvision-core-evidence`
- JUnit `core-tests.xml`: **3100 tests / 3065 passed / 35 skipped / 0 failures / 0 errors**, 2 deselected, 170 warnings, 735.83초

artifact를 읽기 전용으로 대조했다. `tests.test_migration_role_guard`는 13/13 실행·통과, `tests.integration.test_server_container`는 8/8 실행·통과했다. `tests.core.test_server_config_volume`은 7/7 실행·통과했으며, 그중 선행 run에서 이미지 미지정으로 skip이었던 `test_real_volume_copy_or_failure_cleanup[False|True]` 2건이 실행 전환 대상이다.

선행 run `35706465645`의 JUnit은 3006 tests / 2948 passed / 58 skipped / 0 failures / 0 errors였다. 그 artifact에서 위 세 모듈은 각각 `0 executed + 13 skipped`, `0 + 8`, `5 + 2`였고, 이번 run에서는 정확히 23개 skip이 사라졌다.

남은 35 skip의 실제 분포는 ratchet과 일치한다.

- CX01 container identity/ownership: 19
- Windows 전용: PowerShell launcher 10 + PowerShell/csc shim 1 = 11
- browser smoke opt-in: 1
- 외부 agent CLI 미설치: Claude/Codex/Gemini/Antigravity 각 1 = 4

## 3. 로컬 검증과 경계

- PyYAML parse + workflow policy assertions: PASS, exit 0
- `python tools/check_docs.py`: 워크플로 구현 커밋 전 796 documents PASS, 문서 추가 뒤 797, 최신 integration 동기화 뒤 800 versioned documents PASS, 모두 exit 0
- `git diff --check`: exit 0
- `actionlint`: 설치되지 않아 not run
- 사용자 메모리 경보 당시 지침에 따라 로컬 pytest/build는 실행하지 않았다. 실행 증거는 위 hosted exact-head run이다.

문서 추가 뒤 같은 YAML 정책 검사, `check_docs`, `git diff --check`를 다시 실행해 모두 exit 0임을 확인했다. 병합과 integration 재실행은 코디네이터 소관이며, Claude 독립 검토를 기다린다.
