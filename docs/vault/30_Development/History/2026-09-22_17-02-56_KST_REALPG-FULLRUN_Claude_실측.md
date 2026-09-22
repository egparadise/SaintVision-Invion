---
doc_id: "CLAUDE-NEWPC-REALPG-FULLRUN-001"
title: "새 PC 실 PostgreSQL 전수 실행 — CI-스코프 2667건 (2523 passed / 142 skipped / 2 failed), skip 1011→142"
version: "1.0.0"
status: "evidence-contributed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T17:02:56+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "d01c931a"
impl_sha: "(문서 전용 — 코드 변경 없음)"
tags: ["real-pg", "full-run", "new-pc", "verification", "triage", "claude"]
---

# 새 PC 실 PostgreSQL 전수 실행 (2026-09-22, 17:02 KST)

**측정 SHA `d01c931acf2127377a7cdc665ef3eee5f0402fe9`** (origin/integration tip). 측정 트리는 **Claude 전용 detached 워크트리 `D:\Project\sv-measure-claude`**(R6: 주 워크트리 아님, 소유 Claude). 각 덩어리 시작 시 `git status --porcelain` 빈 출력 확인(아래 예외 1건 명시). 인터프리터 `D:\Project\SaintVisionI-Invion\.venv\Scripts\python`(3.14.7, pytest 9.1.1). 실 DB: 컨테이너 `saintvision-invion-dev-pg`, PostgreSQL 16.15, `127.0.0.1:55432`, `.env`의 `INV_TEST_ADMIN_DSN`(conftest가 시험마다 disposable DB `inv_backend_test_*`/`inv_test_*`를 만들고 버림 — `invdev` 무변경).

## 1. 명령과 exit

CI `backend.yml`과 같은 스코프: `tools/node_dependent_tests.py --pytest-args`(node-dependent 24파일 ignore) + 브라우저/컨테이너 6파일 `--ignore`(test_desktop_browser·test_approval_browser·test_studio_browser·test_web_container·test_workspace_upgrade·test_lan_storage_install). `--strict-markers -p no:cacheprovider -rs --junitxml`. `CI` 환경변수 미설정(로컬).

첫 시도(단일 전수, 15:41 시작)는 **64% 지점에서 Claude Code 하네스의 메모리 reaper에 의해 강제 종료**(명령 오류 아님; 같은 PC에서 다른 세션의 pytest가 15:49~16:24 동시에 돌고 있었음). 코디네이터 승인으로 **3덩어리 순차 재실행**(PowerShell `Start-Process`로 분리, 덩어리마다 junit):

| 덩어리 | 명령 대상 | 시작(KST) | 소요 | exit | 결과 |
|---|---|---|---|---|---|
| core | `tests/core` | 16:24:41 | 90s | 0 | 919 passed / 3 skipped / 0 failed |
| root | `tests/test_*.py` (76파일) | 16:26:31 | 1249s | 1 | 1198 passed / 28 skipped / **1 failed** / 2 deselected |
| integration | `tests/integration` | 16:47:38 | 521s | 1 | 406 passed / 111 skipped / **1 failed** |
| **합계** | 2667 collected | | 31분 | | **2523 passed / 142 skipped / 2 failed / 0 errors** |

- porcelain 예외: core 덩어리 시작 시 `?? %SystemDrive%/`(빈 디렉터리 트리 `ProgramData/Microsoft/Windows/Caches`, 16:04 강제종료된 첫 시도 중 어떤 시험이 Windows 환경변수 문자열을 확장하지 않고 상대경로로 만든 것)가 있었고 즉시 제거. root 덩어리 후에도 같은 것이 재생성돼 제거. 코드 트리와 무관(빈 디렉터리), 결과 무영향. 어느 시험이 만드는지는 미특정(추적 후보: 하네스/런처 시험).
- 새 PC 기준선(같은 PC, 13:00 KST, DSN 없음, `.work/newpc-backend-tests.xml`): **2667 collected / 1011 skipped / 0 failed**. 수집 수 동일(2667) → 시험 집합 동일. **skip 1011 → 142**(전부 "INV_TEST_ADMIN_DSN is absent"였던 것이 실 PG로 도달). skip을 통과로 세지 않는다.

## 2. 남은 skip 142 — 사유별 집계 (전부 환경 게이팅, §4 미설정과 일치)

| 건수 | 사유 | 분류 |
|---|---|---|
| 48 | Actual Linux file backend | Linux 파일 스토리지 백엔드 부재(Windows) — 이전 절차서 §4·§5 예상과 일치 |
| 20 | Linux credentials | Linux 자격증명 백엔드 부재 |
| 19 | CX01_CONTAINER is unset | 보호 컨테이너 옛 PC 잔류(§6) — 의도적 미설정과 일치 |
| 15 | Linux private-directory provider | Linux 전용 |
| 13 | Linux publication contract | Linux 전용 |
| 13 | Explicit local PostgreSQL image required; ambient databases are never used | `INV_TEST_ROLE_GUARD_IMAGE` 미설정(컨테이너 레인 opt-in) |
| 8 | Explicit candidate image and disposable container DB address required | 컨테이너 레인 opt-in |
| 2 | Explicit pinned local candidate image required | 컨테이너 레인 opt-in |
| 1 | launcher prerequisites absent (측정 워크트리에 `.venv`/`node_modules` 없음) | **측정 트리 특유** — 주 트리에선 돈다(fresh 워크트리엔 파생물 없음) |
| 1 | antigravity is not installed | 도구 부재 |
| 1 | symlink on Windows needs privilege (INV_TEST_SYMLINKS) | Windows 권한 |
| 1 | browser smoke integration lane (INV_BROWSER_SMOKE_INTEGRATION=1) | opt-in 레인 |

늘어난 skip 없음 — 남은 142는 모두 이전 절차서 §4(CX01_CONTAINER·Linux 스토리지·이미지/브라우저 opt-in)에 해당한다.

## 3. 실패 2건 — 이름 단위 분류와 귀속

### F1 `tests/test_account_integration.py::test_published_migration_heads_upgrade_without_rewriting` — **환경(동시 실행 경합), 회귀 아님. 귀속 Codex(진단 은닉 설계 갭)**
- 실패 메시지: `Disposable migration paths failed; diagnostics withheld` (자식 `tools/check_migration_upgrade.py` returncode 1, stderr 미노출).
- 독립 재현: (a) 같은 측정 트리에서 `tools/check_migration_upgrade.py` 직접 실행 → **exit 0, 30 PASS, 244s**. (b) 같은 시험 단독 재실행 → **1 passed, 266s, exit 0**. 두 번 다 통과.
- 실패 시각(16:26~16:47 root 덩어리) 동안 주 워크트리에서 **다른 세션의 pytest가 동시 실행**됐다(주 트리 `.work/vf-route-gap.json` 16:29 갱신이 증거). 이 도구는 발행 prior마다 disposable DB에 마이그레이션을 재생하며 클러스터 전역 role(`inv_kernel`·`inv_app`)을 만지므로 동시 세션과 경합할 수 있다[추정 — stderr가 은닉돼 확정 불가].
- 귀속: 시험·도구 소유 Codex(542bd04d·79487cb6). **제안**: 실패 시 자식 stderr 마지막 N줄을 assertion 메시지에 포함(`diagnostics withheld`는 분류를 불가능하게 함 — 규칙 2 "빈 결과는 사실 아님").

### F2 `tests/integration/test_vf_canonical.py::test_factory_route_measurement_is_not_fixture_union` — **시험 결함(fresh checkout에서 재현되는 환경 가정). 귀속 Codex**
- 실패: `FileNotFoundError: ... sv-measure-claude\.work\vf-route-gap.json`. 시험이 `root/.work/vf-route-gap.json`에 `write_text`하나 `.work/`(gitignore)를 만들지 않는다. 주 워크트리엔 `.work/`가 이미 있어 통과하고, **fresh worktree/clone에선 반드시 실패**한다.
- 독립 재현: 측정 트리에 `mkdir .work` 후 단독 재실행 → **1 passed, 7.4s**. 원인 확정.
- 귀속: `test_vf_canonical.py`(fc34f37c, storage/Codex). 수정은 한 줄(`(root/'.work').mkdir(parents=True, exist_ok=True)`). CI backend는 `.work/`를 안 만들므로(core.yml만 `.work/node-image` 생성) hosted CI에서도 같은 실패가 예상된다[추정 — 현재 CI는 그 전 단계에서 실패해 미도달].

## 3-1. 답 아는 자리 대조 — 같은 SHA의 독립 2차 측정과 교차 확인

이 측정과 별개로 다른 Claude 세션이 같은 SHA `d01c931a`를 별도 clean 트리(`.worktrees/claude-newpc`)에서 **core.yml 22단계 스코프**(node-dependent 24파일을 ignore하지 않음)로 쟀다: **2549 passed / 2 failed / 408 skip / 2 deselected**([[2026-09-22_새PC_첫날_CI첫실행_triage_및_이전후_전수검증_Claude]], 착지 `c5042322`). 대조:
- **실패 2건이 이름까지 동일**(F1 migration head · F2 vf_canonical `.work`)하고 각각의 단독 재실행 판정도 동일 — 두 측정이 서로 독립이므로 우연이 아니라 그 SHA의 실제 상태다.
- skip 408 vs 142의 차이 266은 **스코프 차이**(node-dependent 24파일이 그쪽 스코프에선 수집돼 "Linux Docker 런타임 140 · Linux Workspace 실행 26+17+11+11 …"로 skip). 내 backend.yml 스코프는 그 파일들을 `--ignore`하므로 skip에 안 잡힌다. 두 표의 공통 사유(Linux 파일 백엔드 48·CX01 19·명시 PG 이미지 13 등)는 건수까지 일치.
- passed 2549 vs 2523 = 26 차이 — 그쪽 스코프에서 node-dependent 파일 중 일부 시험이 skip이 아니라 통과로 도달한 것(파일 단위 ignore 대 시험 단위 게이팅의 차이)[추정 — 두 junit의 이름 집합 차집합으로 확정 가능, 이번엔 미수행].
- **F2는 이미 origin에서 수정됨**: Codex `51d53b7f`(fix(ci): close backend hosted environment gaps)가 `evidence_dir.mkdir(parents=True, exist_ok=True)`를 넣었다. 이 측정 SHA(d01c931a)는 수정 이전이며, 수정 후 tip에선 이 실패가 사라져야 한다(미측정). F1의 진단 은닉은 origin tip에서도 그대로(`tests/test_account_integration.py`·`tools/check_migration_upgrade.py` diff 0).

## 4. hosted CI 현황 (tip d01c931a)

`gh run list --repo egparadise/SaintVision-Invion --limit 5`: Backend Build **35688813798 failure**(1m1s) · Core Build 35688813794 failure · Desktop HTTP Browser Acceptance 35688813838 failure · Documentation Build 35688813795 success. Backend Build 실패 원인(로그 실측): pytest 이전 단계 `python tools/export_schemas.py --check` → `FAIL: 2 schema file(s) out of date: pool-list-item-response.schema.json, pool-list-response.schema.json`. 측정 트리에서 같은 명령 재현 exit 1(생성 후 revert, 착지 안 함). **귀속 Codex**(pool inventory 9425062c; pool/placement 영역). 이것이 해소되기 전엔 CI backend가 pytest에 도달하지 못한다.

## 5. Evidence

- junit 3개 + 로그 + 재실행 junit 2개 + 도구 로그: `.work/evidence-claude-d01c931a/`(core.xml sha256 `16e38c99a7b7473b…`, root.xml `a6a78dbcfb117480…`, integration.xml `07964579b23bf656…`).
- provenance: `docs/vault/30_Development/Evidence/claude-newpc-realpg-d01c931a/provenance.json` (working_tree_clean=YES, SHA, 명령, 집계).
- 검증상태지도 갱신: [[2026-09-19_Claude영역_검증상태지도]] §5(이 문서 착지와 같은 커밋).

## 다음 첫 행동 / 담당
- Codex: F2 한 줄 수정(`.work` mkdir) · F1 진단 노출 · export_schemas pool 스키마 2건 재생성 착지(CI backend 선행).
- Claude(이어서): 작업 2 증거 재실행(S02/S03/S09/S10/S04-05/S07, 별도 History) · 작업 3 PITR 실측.
