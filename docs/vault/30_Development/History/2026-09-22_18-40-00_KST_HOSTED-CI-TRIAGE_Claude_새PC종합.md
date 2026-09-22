---
doc_id: "CLAUDE-HOSTED-CI-TRIAGE-NEWPC-SUMMARY-001"
title: "hosted CI 결과 triage(오늘 착지 SHA별 5 workflow) + 새 PC 첫날 종합 검증 상태 — Core Build 첫 완주 3d1892c0(2948/58/0), Backend 3회 완주(2668/45/0), 브라우저 실패 케이스 특정"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T18:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "9b6b967b"
impl_sha: "(문서 전용)"
tags: ["hosted-ci", "triage", "new-pc", "verification", "claude"]
---

# hosted CI triage + 새 PC 첫날 종합 (2026-09-22, 18:40 KST)

읽기 도구: `gh run list --branch integration/all-agents-unified`, `gh run view <id> --log/--json jobs`, 아티팩트 다운로드(`desktop-browser-safe-evidence`). 판독 시각 18:38 KST(tip `9b6b967b`). 분류 어휘는 [[CI_첫실행_분류귀속조율_규율]](A 새로 드러남 / B1 회귀 / B2 환경차 / 인프라·machinery).

## 1. SHA × workflow 결과 표 (오늘 integration push, KST)

| SHA | 착지 | 시각 | Docs | Backend | Core | Browser Acceptance | Frontend* |
|---|---|---|---|---|---|---|---|
| `33283867` | Codex fix(security) | 17:37 | success | cancelled | cancelled | failure | — |
| `7dce1737` | merge PR #42(Claude review PR36) | 17:39 | success | **success 35705983790** | cancelled | failure | — |
| `9f1c0fcc` | Codex fix(lan) | 17:40 | success | cancelled | cancelled | failure | — |
| `ddf149e9` | merge PR #39(attribution) | 17:42 | success | cancelled | cancelled | failure | — |
| **`3d1892c0`** | **Claude 카드 3(resource-usage 라우트)** | 17:44 | success | **success 35706465869** | **success 35706465645 — 첫 완주** | failure 35706465844 | — |
| `9cfd8a8e` | docs(review) PR #41 | 18:02 | success | **success 35708110679** | cancelled | failure | — |
| `7e1949ce` | merge PR #45(route_coverage) | 18:06 | success | cancelled | cancelled | failure | — |
| `10516f02` | (merge) | 18:11 | success | cancelled | cancelled | failure | — |
| `30b8b6b5` | Claude 카드 4 | 18:13 | success | cancelled | **in_progress** | failure | — |
| `7168d573` | merge PR(결정 #7 알람, Codex) | 18:16 | success | **in_progress** | cancelled | failure | — |
| `9b6b967b` | Claude 카드 5 | 18:18 | success | pending | pending | in_progress | — |

\*Frontend Build는 `apps/web/**` 경로 필터라 오늘 integration에선 `7b251bd6`(17:25, Gemini locale 수정 merge) success 1회뿐; 이후 agent 브랜치(claude/node-usage-ui·gemini/fix-desktop-studio-browser)에서 success 5회. 규율의 "다섯 전부 같은 SHA" 조건은 integration에서 아직 미충족(경로 필터 구멍, 규율 §frontend.yml 항목).

## 2. 확정 수치와 ratchet 대조

- **Core Build 첫 완주(`3d1892c0`, run 35706465645, 30 step 전부 success)**: 계약 재생성·drift 0 → 발행 head 마이그레이션 → Linux Node 동시성/crash 경계 → **Node 이미지·Python 워크로드 이미지·LAN installer 이미지·production API 이미지 빌드** → Docker API 협상·bounded 실행 → workspace 복구(28+22)·containment 21·business handoff 17·**shard replacement on two real Nodes 15**(225s)·LAN installer 인수 → **full pytest 2948 passed / 58 skipped / 2 deselected / 0 failed(11m28s)** → hygiene → **"Require executed evidence and declared platform skips" PASS(ratchet 11사유 일치)** → build → `go test ./...` → contracts-ts tsc. **어제까지 "Go 0 컴파일·node-dependent 24파일 not_run"이던 자리가 hosted에서 전부 실행·통과했다.** 이 PC에서 못 돌린 24파일(카드 4)의 검증 자리가 실제로 채워짐.
- **Backend Build 완주 3회**(`7dce1737`·`3d1892c0`·`9cfd8a8e`): 3.12·3.14 각 **2668 passed / 45 skipped / 2 deselected / 0 failed**, declared skip ratchet(10사유 45건) **일치** — 이 PC 전수(2523/142, Windows)와의 차이는 Linux 전용 게이트 깨어남(+145 passed)과 Windows 전용 skip(-97)으로 설명됨.
- **Browser Acceptance 전 SHA failure**: 5 passed / 1 failed, 케이스가 이제 **특정됨**(Codex가 카드 2 F-B를 해소해 `failedCaseIds` 노출): `tests.integration.test_desktop_browser::test_browser_real_catalogue_owner_scope_and_revocation`. Gemini 브랜치 `agent/gemini/fix-desktop-studio-browser`(frontend success 2회)가 진행 중.

## 3. 귀속 표 (원인으로 센다)

| 원인 | 분류 | 딸린 결과 | 레인 | 상태 |
|---|---|---|---|---|
| Backend/Core **cancelled** 다수(SHA 8개) | **인프라·machinery** — concurrency 그룹: `4b2204d7`가 integration의 `cancel-in-progress`를 껐지만 GitHub은 같은 그룹에서 **pending run을 하나만** 유지하므로 연속 push(17:37~18:18에 11회, 5분 간격 미준수)가 대기 중 run을 계속 대체함. 코드 실패 0 | 8 SHA × 1~2 workflow | Codex(machinery) + 전 레인(push 간격) | **완주 SHA로 판정 가능**: 3d1892c0가 Backend·Core 둘 다 green이라 그 트리의 상태는 확정. 이후 SHA는 docs/도구 변경 위주 |
| Browser `test_browser_real_catalogue_owner_scope_and_revocation` | **A 새로 드러남**(옛 PC not_run·hosted Chromium 전용) | Browser 11/11 failure | Gemini(화면)·Codex(런너) | Gemini 수정 브랜치 진행 중; 케이스 노출은 Codex 착지로 해소 |
| Frontend 경로 필터 | 규율 §frontend.yml 구멍 | integration에서 frontend 1회만 | Codex(workflow) | 미해결(규율에 기록됨) |
| 코드 회귀(B1)·환경차(B2) | — | **0** (완주한 Backend 3회·Core 1회 모두 0 failed) | — | — |

## 4. 새 PC 첫날 종합 — not_run → 실행 전환 표

| 항목 | 옛 PC 기준선(47b0d2de) | 오늘 새 PC / hosted | 증거 |
|---|---|---|---|
| CI-스코프 pytest 실 PG | 1650 passed / 1039 skip(PG 없음) | **2523 passed / 142 skipped / 2 failed**(d01c931a, 로컬) · hosted Backend **2668 / 45 / 0**(3d1892c0) | [[2026-09-22_17-02-56_KST_REALPG-FULLRUN_Claude_실측]] · run 35706465869 |
| 인수 증거 6세트(S02/S03/S09/S10/S04-05/S07) | 일회용 PG로 개별 | **762 passed / 88 skipped / 0 failed** | [[2026-09-22_17-12-01_KST_REALPG-EVIDENCE_Claude_인수증거]] |
| Docker-only 게이트(role guard·후보 이미지·config volume) | not_run | **23건 passed**(business-kernel-role 포함) | [[2026-09-22_17-52-00_KST_NODE-DEPENDENT-NOTRUN_Claude_실측]] |
| Go 컴파일·테스트 | 0(Go 없음) | 로컬 `go build/vet` 0(contracts-go·node-agent) · hosted `go test ./...`·`-race` success | 카드 2 · run 35706465645 |
| node-dependent 24파일 | ignore | 로컬 **not_run**(Unix 소켓 호스트 부재) · **hosted Core 실행·통과**(workspace/containment/handoff/shard/LAN) | 카드 4 · run 35706465645 |
| PITR runbook | 옛 PC 리허설 | readiness absent(dev-pg) + 물리 리허설 6회 재현, 보관 7일 | [[2026-09-22_17-14-47_KST_PITR-RUNBOOK_Claude_실측]] |
| Codex 착지 독립 검토 | — | 10건 sound, finding 2(F-A 대기, F-B 해소됨) | [[2026-09-22_17-35-00_KST_CODEX-LANDINGS_Claude_독립검토]] |
| 노드 자원 사용량 라우트 | 계약만(404) | 서빙 + 실 PG 앵커 6 passed·변이 KILLED | [[2026-09-22_18-05-00_KST_NODE-RESOURCE-USAGE-ROUTE_Claude_구현]] |
| S02-DB·S03-DB 인계 | — | 검토 패키지 착지(planned→review 제안) | [[2026-09-22_18-25-00_KST_S02-DB_S03-DB_검토인계패키지_Claude]] |

**남은 not_run(정직)**: node-dependent 24파일 로컬(WSL2 Ubuntu 사용자 결정; hosted가 자리) · Linux 전용 skip(파일 백엔드 48·자격증명 20·private-dir 15·publication 13 — hosted에서 실행됨) · CX01 19(보호 컨테이너 옛 PC) · 물리 노드 5대·실 IdP(외부 대기) · 브라우저 인수 1건(Gemini 진행) · symlink 권한 1·CLI 도구 4.

## 다음 첫 행동 / 담당
- 코디네이터/전 레인: **push 간격 5분** 준수(대기 run 대체 방지). 완주 필요한 SHA는 slot으로.
- Gemini: 브라우저 케이스 수정 착지 → Browser Acceptance green이 "다섯 전부" 조건의 마지막 조각(+frontend 경로 필터는 Codex).
- Claude: S02-DB/S03-DB 판정 finding 보완 대기; 다음 완주 SHA(30b8b6b5 Core·7168d573 Backend·9b6b967b) 결과는 다음 사이클에 이 표 갱신.
