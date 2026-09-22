---
doc_id: "CLAUDE-HOSTED-CORE-SKIP58-MAP-001"
title: "hosted Core 첫 완주(3d1892c0, 2948 passed / 58 skipped / 0 failed) — skip 58건 사유 분류표(Linux 전용/CX01/물리 노드/브라우저/도구 부재) + 이 PC 로컬 skip 142 대조 (1쪽)"
version: "1.0.0"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T23:20:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["hosted-ci", "core", "skip", "not_run", "verification-map", "new-pc"]
---

# hosted Core 첫 완주 — skip 58건 분류표

[[2026-09-19_Claude영역_검증상태지도]] 형식(ran-passed / 미검증-정직기록 / 외부 대기)으로, hosted **Core Build run 35706465645**(tip `3d1892c0`, 2026-09-22 08:44 UTC, 30 step 전부 success)의 `core-tests.xml`을 읽어 **3006 수집 / 2948 passed / 58 skipped / 0 failed / 0 error**의 skip 58건을 사유·모듈·분류로 갈랐다. 이 58은 `core.yml`의 **선언 ratchet**(사유별 정확 카운트, 합 58)과 일치한다 — 즉 hosted에서 "조용히 늘어난 skip"은 0이다. 이어 이 PC 로컬 실 PG 전수([[2026-09-22_17-02-56_KST_REALPG-FULLRUN_Claude_실측]], backend.yml 스코프 2667건, skip 142)와 대조한다.

## 1. hosted skip 58 — 사유별 분류

| 건수 | pytest skip 사유(원문) | 모듈 | 분류 | 무엇이 있어야 도는가 | 소유 |
|---|---|---|---|---|---|
| 19 | `CX01_CONTAINER is unset; container identity/ownership cannot be verified` | `test_recovery_drill` | **보호 컨테이너(CX01)** | 옛 PC에 남긴 보호 컨테이너 4개(이전 절차서 §6) — hosted 러너·이 PC 모두 없음. 새 컨테이너가 생기기 전까지 정직 skip | 운영자/Codex(CX-01 정본) |
| 13 | `Explicit local PostgreSQL image required; ambient databases are never used` | `test_migration_role_guard` | **컨테이너 레인 opt-in(이미지)** | `INV_TEST_ROLE_GUARD_IMAGE` — **backend.yml은 `postgres:16`으로 설정해 그 job에선 13건이 돈다**(backend 45 skip 목록에 없음); core.yml만 미설정 | Codex(machinery) — core에도 설정하면 즉시 13건 실행 전환 가능 |
| 10 | `Actual Windows PowerShell launcher` | `test_storage_windows_launcher` | **Windows 전용** | 실제 PowerShell — Linux 러너 불가. **이 PC(Windows)에선 돈다** | — (플랫폼 상보) |
| 8 | `Explicit candidate image and disposable container DB address required` | `test_server_container` | **컨테이너 레인 opt-in(이미지)** | `INV_TEST_SERVER_IMAGE` + 컨테이너 DB 주소 — core는 후보 이미지를 빌드하지만 이 lane 변수는 미주입 | Codex(machinery) |
| 2 | `Explicit pinned local candidate image required` | `test_server_config_volume` | **컨테이너 레인 opt-in(이미지)** | `INV_TEST_CONFIG_IMAGE` 고정 이미지 | Codex(machinery) |
| 1 | `PowerShell and csc.exe shim require Windows` | `test_launcher_failure_boundaries` | **Windows 전용** | Windows + csc.exe | — |
| 1 | `Explicit browser smoke integration lane required (INV_BROWSER_SMOKE_INTEGRATION=1)` | `test_browser_smoke_integration` | **브라우저 opt-in** | 별도 브라우저 레인(desktop-browser.yml이 담당; core에선 의도적 제외) | Gemini/Codex |
| 4 | `claude/codex/gemini/antigravity is not installed on this machine` | `test_cli_adapters` | **도구 부재** | 러너에 에이전트 CLI 4종 — 설치 의도 없음(로컬 사람 CLI 탐지 시험) | — |

분류 합계: 보호 컨테이너 19 · 컨테이너 레인 opt-in 23(13+8+2) · Windows 전용 11 · 브라우저 1 · 도구 부재 4 = **58**. **"물리 노드" 분류는 0** — core.yml은 node-dependent 레인(workspace 22·containment 28·business handoff 17·shard recovery 21·LAN installer 15)을 **실제 Node 컨테이너로 실행**해 0 실패였고, 물리 5대가 필요한 시험은 pytest skip이 아니라 **registry 인수 조건**(S01-ST/S02)으로 남아 있다.

## 2. 이 PC 로컬 skip 142와 대조 (같은 사유는 한 줄로)

| 사유 | hosted core (Linux 러너) | 로컬 (Windows, 실 PG, backend.yml 스코프) | 해석 |
|---|---|---|---|
| Linux 파일 백엔드/자격증명/private dir/publication | **0** (Linux라 실행됨) | **96** (48+20+15+13) | **플랫폼 상보** — 로컬 not_run이 hosted에서 ran-passed로 채워짐. 이 96은 이 PC에서 영원히 skip(WSL2 결정 전) |
| CX01_CONTAINER | 19 | 19 | **양쪽 동일** — 환경이 아니라 보호 컨테이너 부재. 유일하게 어디서도 안 도는 덩어리 |
| 컨테이너 레인 opt-in(role guard 13 / server 8 / config 2) | 23 | 23 | 양쪽 동일. 단 **backend.yml은 role guard 13을 돌린다** → core.yml에도 같은 변수를 주면 hosted 23→10 |
| Windows 전용(PowerShell launcher 10 + csc 1) | 11 | **0** (로컬은 Windows라 실행됨) | **플랫폼 상보(반대 방향)** |
| 브라우저 smoke opt-in | 1 | 1 | 양쪽 동일(별도 레인) |
| 도구 부재(CLI 4종) | 4 | 1 (antigravity만) | 로컬엔 claude/codex/gemini CLI가 있어 3건 실행됨 |
| 측정 트리 특유(launcher prerequisites) / symlink 권한 | 0 | 2 | 로컬 워크트리·Windows 권한 문제 — 주 트리/권한 부여 시 소멸 |
| **합** | **58** | **142** | 겹치는 것 43(CX01 19·opt-in 23·브라우저 1), 나머지는 서로 채워 줌 |

**핵심**: 두 실행을 합치면 **어디서도 안 도는 skip은 CX01 19 + 컨테이너 레인 opt-in 10(server 8·config 2) + 브라우저 smoke 1 + antigravity 1 = 31건**뿐이다. 나머지는 Linux↔Windows 상보 또는 backend job에서 이미 실행 중이다.

## 3. 검증 상태 지도 형식 요약

- **ran-passed(hosted)**: 2948 — node-dependent 레인 포함, Linux 전용 96 포함.
- **미검증이나 정직히 기록됨**: 58(hosted) — 위 표. 전부 ratchet에 선언되어 늘면 CI가 막는다.
- **외부 대기**: CX01 보호 컨테이너(운영자), 물리 노드 5대(registry 인수), WSL2 결정(이 PC Linux 전용 96을 로컬에서도 돌릴지).
- **machinery로 줄일 수 있는 것(Codex)**: core.yml에 `INV_TEST_ROLE_GUARD_IMAGE: postgres:16`(backend와 동일) → 13건 실행; `INV_TEST_SERVER_IMAGE`/`INV_TEST_CONFIG_IMAGE` 주입 → 10건 실행(후보 이미지는 이미 core가 빌드하므로 변수만). ratchet 갱신 필요(합 58→35).

## 4. 하지 않은 것 (정직)
- hosted 로그의 skip 사유는 junit `message`만 읽었다(케이스별 코드 경로는 미추적, 모듈 단위로만 귀속).
- 로컬 142는 [[2026-09-22_17-02-56_KST_REALPG-FULLRUN_Claude_실측]]의 표를 그대로 썼다(재실행 안 함). 내 별도 측정(core.yml 스코프, skip 408)은 스코프가 달라 여기 대조에 쓰지 않았다.
