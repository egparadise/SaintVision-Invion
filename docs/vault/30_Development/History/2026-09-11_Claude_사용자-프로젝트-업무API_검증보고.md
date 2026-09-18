---
doc_id: "REPORT-CLAUDE-PROJECT-API-20260911"
title: "Claude 사용자 프로젝트 업무 API 검증보고"
version: "1.0.0"
status: "review"
author: "Claude"
updated: "2026-09-11T10:44:51+09:00"
source_of_truth: "Git"
---

# Claude — 사용자·프로젝트·업무 API 검증 보고

- **작성자**: Claude
- **검토자**: **미지정 (Codex 인계 필요)** — 작성자와 검토자는 분리되어야 하므로 이 문서는 검증 보고이지 승인이 아닙니다.
- **브랜치**: `review/claude-pr13-pr17`
- **HEAD SHA**: `001fbeeaa8e3815ae9f36d4076cf804331bade15`
- **base SHA**: `6bc890349297d9a16b66f71e199ab9a440250c4f` (`agent/codex/node-containment`)
- **작성 커밋 3건**:
  - `ad71868` settings API
  - `ece6fea` agent CLI adapters
  - `001fbee` projects/workspaces API

## 검증 환경 — CI가 아닙니다

**GitHub Actions는 저장소 전체에서 중단 상태입니다.** 지시대로 계정 문제는 건드리지 않았고, 대신 로컬 실PostgreSQL로 검증했습니다. 이것은 CI 통과와 **동등하지 않으며**, 그렇게 보고하지 않습니다.

관측된 사실:

```
2026-09-11T00:58:40Z Backend Build  failure  3s  review/claude-pr13-pr17
2026-09-11T00:56:40Z Backend Build  failure  3s  integration/all-agents-unified
```

- 모든 브랜치·모든 워크플로가 **2~5초**에 실패
- job의 `steps: 0` — **단계가 하나도 실행되지 않음**
- 로그 아카이브가 **22바이트(빈 zip)**

즉 코드에 도달하기 전에 실행이 거부된 것입니다.

**검증에 쓴 데이터베이스**: `postgres:16` 컨테이너 `saintvision-lan-db-bff1a31d`, `127.0.0.1:55440`.

## 실행한 명령과 결과

| 명령 | 결과 |
|---|---|
| `pytest tests/test_projects.py -q -p no:randomly` | **19 passed** |
| `pytest tests/test_settings.py -q -p no:randomly` | **16 passed** |
| `pytest tests/test_cli_adapters.py -q -p no:randomly` | **22 passed, 1 skipped** (antigravity 미설치) |
| `pytest tests/test_projects.py test_settings.py test_pools.py test_api.py test_cli_adapters.py test_contracts.py` | **147 passed, 1 skipped** |
| `pytest tests/test_migrations.py` | **20 passed** |
| `python tools/export_schemas.py --check` | **PASS: 18 contract schemas** |
| `python tools/migration_graph.py --head` | `0024_project_kernel_link` |

`tools/node_dependent_tests.py` 기준 node 런타임 의존 17개 suite는 Go 에이전트와 컨테이너 이미지가 필요하여 이 기계에서 실행하지 않았습니다. **미실행이며 통과가 아닙니다.**

## 완료 기준 대비

> 실제 계정으로 만든 프로젝트가 실행 커널까지 연결되고, 권한 없는 요청은 거부됨

### 연결됨 — 다만 정확히 어디까지인지 밝힙니다

`public.project_members.role_code`가 **곧 커널의 권한 판정**입니다. `inv.business_auth.permission()`이 실행 직전에 그 행과 `public.users.status`, `public.projects.status`를 직접 읽습니다. 사본도 동기화도 없습니다. `tests/test_settings.py::test_the_kernel_reads_the_same_vocabulary`가 양쪽 상수를 import해 일치를 단언합니다 — **어긋나면 값은 저장되고 화면은 보여주고 커널은 거부하는데, 어느 쪽도 자기 기준으로는 틀리지 않습니다.**

**아직 연결되지 않은 지점**: 새로 만든 프로젝트는 `inv.business_projects`에 링크되기 전까지 실행할 수 없습니다. 이건 결함이 아니라 의도된 분리입니다 — 프로젝트 생성이 곧 남의 기계에서 코드를 돌릴 권한이 되어선 안 됩니다. 다만 그 상태가 보고되지 않으면 화면에 프로젝트·Workspace·실행 버튼이 다 보이고 실행만 실패합니다. migration `0024`의 definer 함수가 `kernelLinked`/`kernelEnabled`로 답하고, 링크 전에는 문장으로 설명합니다.

OIDC 주체↔업무 user 매핑(`inv.business_subjects`)도 운영자 소유입니다. **`inv_app`은 두 테이블 어느 쪽도 읽을 수 없고**, 그게 맞습니다 — 웹 프로세스가 "어떤 프로젝트가 실행 가능한가"를 열거하거나 바꿀 수 있어선 안 됩니다. `test_the_application_cannot_read_the_link_table_directly`가 그걸 단언합니다.

### 권한 없는 요청 거부 — 스냅샷 결함을 먼저 고쳤습니다

`Principal.project_ids`는 **자격증명 검증 시점에 고정된 집합**이었습니다. 양방향으로 깨집니다:

- 로그인 이후 만든 프로젝트는 그 집합에 없어서 **만든 본인이 열 수 없습니다.**
- 토큰 발급 이후 회수된 멤버십은 **토큰이 만료될 때까지 계속 유효합니다** — 회수가 의미를 갖는 바로 그 구간 내내.

이제 매 요청마다 `project_members`를 읽습니다. 기존 호출처(pools) 한 곳을 옮겼습니다.

거부는 **"없는 프로젝트"와 "내 것이 아닌 프로젝트"를 구분하지 않습니다.** 구분하면 접근 권한 없는 사람에게 식별자의 존재를 확인해 주는 셈입니다. 테스트가 두 경로의 code·message 동일성을 단언합니다.

## 제공한 API

```
GET    /v1/projects                              내가 멤버인 프로젝트 (실시간)
POST   /v1/projects                              생성 — 생성자가 같은 트랜잭션에서 owner
GET    /v1/projects/{id}                         + permission + kernelLinked
GET    /v1/projects/{id}/workspaces              deleted 제외
POST   /v1/projects/{id}/workspaces              provisioning으로 시작
GET    /v1/projects/{id}/permissions/me          화면이 컨트롤을 정할 근거
GET    /v1/projects/{id}/members                 + 유효 권한 + 선택 가능한 role 목록
PUT    /v1/projects/{id}/members/{user}          변경 후 유효 권한을 반환
DELETE /v1/projects/{id}/members/{user}
PUT    /v1/users/{id}/status                     정지 — 즉시 커널에 반영
PUT    /v1/projects/{id}/status                  보관
PUT    /v1/workspaces/{id}/status                합법 전이만
GET    /v1/nodes/{id}/offers                     제공량 + 실제 보유량
PUT    /v1/capabilities/{id}/offer               단위 변환, 이전 offer는 닫고 새로 엶
GET    /v1/adapters                              4개 CLI 설치·로그인·구동 가능 여부
GET    /v1/adapters/{name}
```

계약 JSON Schema 18개 생성 — Gemini가 3단계에서 붙일 대상입니다.

## Adapter 실측 (이 기계)

| adapter | installed | version | login | headless |
|---|---|---|---|---|
| claude-code | ✓ | 2.1.247 | `logged_in` (claude.ai) | ✓ |
| codex-cli | ✓ | 0.153.4 | `logged_in` | ✓ |
| gemini-cli | ✓ | 0.56.0 | `logged_in` (credential file 근거) | ✓ |
| antigravity | ✗ PATH에 없음 | — | `unknown` | ✗ |

Antigravity는 `%LOCALAPPDATA%/Programs/antigravity`에 **설치되어 있으나 PATH에 없습니다.** `which`만 보는 코드에겐 "미설치"와 구분되지 않고 **정반대 조치**가 필요해서, 어댑터가 경로를 찾아 "재설치 말고 PATH에 추가"라고 답합니다. 헤드리스 모드가 없어 구동 불가로 보고하며 **호출을 추측하지 않습니다** — 틀린 추측은 창을 띄우고 영원히 기다립니다.

취소는 `STOPPED`가 아니라 **`UNKNOWN`** 을 반환합니다. 프로세스 종료는 프로세스가 사라졌다는 뜻이지 에이전트가 그 전에 무엇을 했는지는 말하지 않습니다 — 파일 수정, 커밋, 아직 저쪽에서 돌며 과금 중인 요청. `STOPPED`는 프로세스 경계 반대편의 상태를 주장하는 것이고, **오케스트레이터가 아직 돌고 있는 작업을 재시도하게 만드는 주장**입니다.

## 다음 담당자에게

- **Codex**: 이 3개 커밋의 독립 검토가 필요합니다(작성자=Claude). 특히 migration `0024`의 definer 함수 범위와 `project_members` 실시간 읽기가 커널 잠금 순서와 충돌하지 않는지.
- **Gemini**: 위 18개 계약으로 화면을 붙일 수 있습니다. `kernelLinked=false`는 오류가 아니라 **설명해야 할 상태**입니다.
- **운영**: 192.168.45.225의 실행 프로필 설치 전까지 원격 제출은 비활성입니다. 프로젝트를 실행 가능하게 하려면 `inv.business_projects`·`inv.business_subjects` 등록이 필요하며, 이는 스키마 소유자만 가능합니다.

## 미완 / 하지 않은 것

- **실행 준비·승인·제출 API**는 Codex의 `inv.workspace_api`가 이미 구현했습니다. PR #18 검토에서 제 중복 구현(`handoff.py`·`core_gateway.py`)을 철회했고, 다시 만들지 않았습니다.
- **결과·로그·복구 API**는 아직 없습니다. 다음 작업입니다.
- **운영 절차 문서**(서비스 시작·재시작·복구)도 아직입니다.
- node 런타임 의존 17개 suite는 이 기계에서 실행하지 않았습니다.
