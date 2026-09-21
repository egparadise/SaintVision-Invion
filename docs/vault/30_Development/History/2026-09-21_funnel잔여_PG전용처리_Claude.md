---
doc_id: "FUNNEL-REMAINDER-PG-ONLY-CLAUDE-001"
title: "파라미터 funnel 잔여 — PG 전용 항목 처리(ZZPROBE 실측). Linux 필요 항목 분리·인계"
version: "1.1.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-21T16:00:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["verification-boundary", "funnel", "pytest-raises-match", "real-pg", "zzprobe", "mutation-testing"]
---

# 파라미터 funnel 잔여 — PG 전용 항목 처리

마감 기록의 내 소관 미완 중 "파라미터 funnel 잔여"를 처리했다. 핵심 구분: **실 PG만 있으면 되는 것(지금 처리)과 Linux 전용 경로까지 필요한 것(남김)**. 이 Windows 호스트에서 Docker로 일회용 PG16을 띄울 수 있으므로 — Linux가 필요한 것은 Linux 전용 backend 경로이지 PG 자체가 아니다 — PG 게이트 funnel은 지금 처리 가능하다.

## 실행 정체성 (provenance — 규칙 첫 실사용)
```
commit_sha:          b23431538eaa4944e7386529923a6031865c6e30 (편집 기준; 아래 참고)
worktree_path:       C:/Project/SaintVision-Invion/.worktrees/claude-cx01
interpreter:         C:\Project\SaintVision-Invion\.venv\Scripts\python.exe  (python 3.14.6)
runtime_node:        v24.17.0
executor:            Claude  (검토자는 다른 사람이라야 독립 검증 — reviewer: Codex)
```
- **PG**: 내 라벨 일회용 PG16 컨테이너 `svcx01-funnelpg`(label `owner=claude-b234315-funnel`, `127.0.0.1:55433`), `INV_TEST_ADMIN_DSN`로 시험 실행. 종료 후 `docker rm -f -v`로 제거, **Docker baseline 48/79/11 복원**. 보호 대상 `saintvision-lan-db*`·`saintview-orthanc*`(4개) 미접촉, 익명 볼륨 69개 보존.
- **provenance env_gates 주의**: 보고 생성 시점 스냅샷은 철거 후라 `postgres_dsn=absent`로 보이나, **funnel 시험 실행 중에는 위 일회용 PG DSN이 설정돼 있었다**(env_gate는 실행-시점이 아니라 스냅샷-시점을 반영 — 도구의 정직한 한계, 규칙에 명시된 라벨링). 종료코드는 파이프 없이 측정.

## PG-only vs Linux 분류 (추측 아니라 실측)
일회용 PG로 funnel 후보 파일을 실행해 실제로 도는지로 분류했다:
| 파일 | 결과 | 분류 |
|---|---|---|
| `test_model_registry_binding.py` | 16 passed | **PG-only** |
| `test_model_registry_runtime.py` | 22 passed | **PG-only** |
| `test_model_registry_revalidation.py` | 7 passed | **PG-only** |
| `test_model_commit.py` | 17 passed | **PG-only** |
| `test_model_locality.py` | 26 passed | **PG-only** |
| `test_model_execution_registry.py` | exit 4(usage/collection) | 미확정 — 조사 필요(Linux 아님으로 보이나 실행 안 됨) |

즉 model-registry/commit/locality 계열 funnel은 **PG만으로 충분**(Windows에서 실 PG로 전부 실행). Linux가 필요한 것은 이 funnel들이 아니라 **node-agent(Go)·컨테이너/네임스페이스 격리·browser(playwright)·`linux_file` 계열**이며, 그것은 funnel match 작업과 별개다. 그러니 funnel match 잔여는 지금 PG로 처리 가능한 항목이다.

## 처리한 것 (ZZPROBE 실측 — 추측 금지)
방법: 각 bare `pytest.raises(DomainError)`(match 없음 = form ④ funnel)에 임시 `match="ZZPROBE"`를 넣어 pytest가 뱉는 **실제 예외 문자열**을 수집하고, 그 코드로 match를 확정, 재실행 통과 확인. 추측으로 넣으면 실제 통과를 거짓 실패로 바꿀 수 있다는 판단이 오늘도 증명됐다(아래 binding L87).

**`test_model_registry_binding.py`** (4 funnel → 16 passed):
| 위치 | funnel | 실측 코드 | 적용 match |
|---|---|---|---|
| L79 | revoked project permission | `AUTH-0030` | `match="AUTH-0030"` |
| L87 (loop 3) | wrong version_id / manifest_hash / **foreign principal** | version_id·hash → `MODEL-0001`, **principal → `AUTH-0030`** | **per-case** `match=expected` (loop를 `(kwargs, expected)`로 재구성) |
| L102 | deny policy | `MODEL-0001` | `match="MODEL-0001"` |
| L153 | retirement invalidates | `MODEL-0001` | `match="MODEL-0001"` |

**최고 가치 발견 = L87**: bare `raises(DomainError)`가 **권한 거부(AUTH-0030)와 manifest 불가(MODEL-0001)를 한 funnel로 뭉갰다**. 실측하니 principal 케이스만 AUTH-0030이고 나머지는 MODEL-0001 — 즉 인가 회귀가 manifest 거부로(또는 그 반대로) 위장 통과할 수 있었다. per-case로 못 박아 그 혼동을 닫았다. (추측대로 uniform을 붙였으면 principal 케이스가 거짓 실패했을 것 — "실행으로 확정"의 이유.)

**`test_model_registry_runtime.py`** (4 funnel → 22 passed):
| 위치 | funnel | 실측 코드 | 적용 |
|---|---|---|---|
| L99 | retirement during read prevents commit | `MODEL-0001` | `match="MODEL-0001"` |
| L133 | policy change after approval prevents claim (removed/changed) | 둘 다 `MODEL-0008`(detail만 상이) | `match="MODEL-0008"` |
| L138 | configured policy requires registry identity | `MODEL-0008` | `match="MODEL-0008"` |
| L147 | enabling policy cannot replay legacy freeze | `MODEL-0008` | `match="MODEL-0008"` |

**검증**: 두 파일 `py_compile` OK, 실 PG 재실행 **16 passed / 22 passed**, bare DomainError funnel 잔여 0. ZZPROBE(틀린 match)→실패 + 실측 match→통과가 곧 비공허성의 구성적 증명. `.venv` 인터프리터, 파이프 없이 exit 측정.

## 남은 것 (같은 방법, PG-only, follow-up)
이번 세션은 rigor를 위해 **binding·runtime 2파일로 한정**했다. 같은 PG-only 계열의 다른 bare `DomainError`/`ValueError` funnel(예: `test_model_commit.py`·`test_model_locality.py`·`test_model_registry_revalidation.py`·`test_provisioning_integrity.py`·`test_control_api.py`·`test_approvals.py`·`test_containment.py` 등)이 남아 있고, **동일 ZZPROBE 방법으로 처리 가능**하다(전부 실 PG로 실행됨을 위에서 확인). 특정 psycopg 예외 타입(`CheckViolation`/`InsufficientPrivilege`/`UniqueViolation`/`LockNotAvailable`)의 raises는 이미 좁아 funnel 아님 — 제외. `test_model_execution_registry.py`의 exit 4는 별도 조사(수집/usage 오류) 필요.

**남기는 것(Linux 필요)**: node-agent(Go race/concurrency), 컨테이너/네임스페이스 격리, playwright browser, `linux_file` 계열 — 이들은 PG가 아니라 Linux 실행 환경이 선행조건이다. 다음 사람이 격리 Linux를 준비할 때 이 목록이 대상이다.

## v1.1.0 정정 — `test_model_execution_registry.py` exit 4의 정체 (조사 완료)
v1.0.0에서 "exit 4 = 수집/usage 오류, 별도 조사 필요, Linux 아님으로 보이나 실행 안 됨"으로 남겼다. **조사 결과: category 미확정이 아니라 내 배치 루프의 경로 오기였다.** 파일은 `tests/integration/`가 아니라 **`tests/core/test_model_execution_registry.py`**에 있고, 내가 `tests/integration/$f.py`로 돌려 pytest가 `ERROR: file or directory not found` → **exit 4**(usage error)를 냈다. "실행되지 않은 것을 어느 범주에 넣을지는 왜 실행되지 않았는지부터 알아야 한다"는 원칙 그대로 — 원인은 파일 부재(잘못된 경로)였다.

실제 파일은 **PG 불필요**(postgres 마커·psycopg 없음, core 테스트). provenance 래핑 모드로 실행해 확인: `env_gates postgres_dsn=absent / as-of at check invocation`, **7 passed exit 0**. parametrized 5-case(`missing→MODEL-0008`, 그 외→`MODEL-0001`)는 이미 per-case match가 있었고, **bare funnel은 L48 하나**(`test_registered_input_does_not_survive_missing_operator_policy`)뿐이었다. ZZPROBE로 실제 코드 `MODEL-0008: Configured policy and exact registry binding required` 확정 → `match="MODEL-0008"` 적용, 재실행 7 passed. bare raises 잔여 0.

**분류 정정**: 이 항목은 "미확정/조사 필요"가 아니라 **PG-free core, 처리 완료**다. Linux 필요 아님. (실행 시점 환경이 보고에 자동 기록됨 — 오늘 고친 wrap 모드의 첫 실사용.)

## 인계
tests/는 Claude 소유라 직접 처리. reviewer: Codex — 특히 binding L87 per-case 분할의 코드 매핑(AUTH-0030 vs MODEL-0001)이 소스와 정합하는지, 남은 PG-only funnel을 같은 방법으로 이어갈지 경계 검토. apps/web 미접촉.
