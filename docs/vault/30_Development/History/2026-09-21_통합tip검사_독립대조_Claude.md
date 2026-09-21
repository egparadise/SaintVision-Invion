---
doc_id: "INTEGRATION-TIP-CROSSCHECK-CLAUDE-001"
title: "통합 tip 검사 독립 대조 — Codex 감사 재실행. 같은 tip 같은 결과 + 재현성 규칙 판단"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-21T23:59:00+09:00"
timezone: "Asia/Seoul"
tip_compared: "cb505f6697beffe78a1cbdaee027f415003c55d3"
source_of_truth: "Git"
tags: ["verification", "reproducibility", "cross-check", "provenance", "integration-tip"]
---

# 통합 tip 검사 독립 대조 (Codex 감사 재실행)

Codex가 통합 tip에서 모든 검사를 돌려 종료코드를 기록했다([[2026-09-21_integration-tip-verification_Codex]]). 하루 종일 "각자 브랜치에선 통과, 통합에선 깨짐"(check_docs)이 아무도 모르게 지속됐기에, 그 결과를 독립 재현으로 대조했다. **목적은 숫자 재확인이 아니라, 무엇을 명시해야 통과 보고가 재현 가능해지고 통합 상태를 보증하는가를 확정하는 것이다.**

## 실행 정체성 (provenance)
- **대조 tip**: `cb505f6697beffe78a1cbdaee027f415003c55d3`(Codex가 고정한 것과 동일). 현재 통합 tip은 `3b2617b`(Codex 감사 doc + progress 손상문장 ASCII 교정)이나, Codex 감사가 `cb505f6`을 고정했으므로 대조도 거기서 했다.
- **내 실행**: worktree `.worktrees/int-checks`(Codex는 `codex-public-dsn-integration` — **다른 worktree**), `working_tree_clean=YES`(`git status --porcelain` 빈값), 인터프리터 `C:\Project\SaintVision-Invion\.venv\Scripts\python.exe`(py 3.14.6), Node(frontend). 파이프로 exit 가리지 않음.

## 대조표 — 같은 tip, 두 독립 worktree
| 검사 | Codex exit | 내 재실행 exit | 일치 |
|---|---:|---:|:--:|
| check_docs.py | 0 (602 docs) | 0 (602 docs) | ✓ |
| check_ontology.py | 0 | 0 | ✓ |
| export_schemas.py --check | 0 (22) | 0 (22) | ✓ |
| contracts:check (apps/web) | 1→0 | 0 | ✓* |
| npm test (vitest) | 0 (34/332) | 0 (34/332) | ✓ |
| route_coverage.py CLI | 1 | 1 | ✓ |
| route_coverage 시험 | 0 (28) | 0 (28) | ✓ |
| sync_obsidian.py --check | 0 (1394/1/0) | 0 (1394/1/0) | ✓ |
| **전체 pytest -q tests** | **1338 P / 1315 S / 2 desel / 0 F** | **1338 P / 1315 S / 2 desel / 0 F** | ✓ |

`*` contracts:check의 Codex "1→0"은 **checkout 직후 의존성 미설치**로 첫 실행이 실패한 것(계약 불일치 아님) — `npm ci` 후 0. 나는 먼저 `npm ci`를 해서 0. **결과 차이 아니라 setup 순서 차이.**

**추가로 내가 돌린 것(Codex 표 밖, 전부 통합과 정합)**: `generate_contracts.py`+`git diff --exit-code`(core.yml 드리프트 게이트) → **0**, 단 `git status`는 `models.py`를 M으로 표시(**Windows CRLF 산물** — `git diff`는 eol=lf 정규화로 빈 diff, 실 드리프트 아님); `npx tsc --noEmit` contracts-ts → 0; `test_sync.py` → 0; `build_docs.py` → 0.

**결론: 같은 tip에서 두 독립 worktree가 모든 겹치는 검사에 동일 종료코드.** 유일한 표면 차이(contracts:check 1→0)는 setup 순서, 결과 아님. 전체 pytest 1338/1315/2/0까지 정확 일치.

## 차이가 어디서 오나 (실행위치·환경·시점)
오늘의 혼란은 셋 다였다:
- **시점**: check_docs가 `5c7ce9d`(merge) 직후엔 wiki link 4건이 memory-only 대상이라 **exit 1**, `b728ad0`이 그것을 `memory:` slug으로 바꿔 **exit 0** 복원. 내가 앞서 관측한 exit 1은 `b728ad0` 이전 시점이었다(사용자 지적). **같은 파일, 다른 SHA, 다른 결과.**
- **환경**: 이 Windows 호스트는 PG/Docker/Go/browser 게이트를 못 돌린다 → pytest의 1315 skip이 그것(`INV_TEST_ADMIN_DSN` 부재 등). `generate_contracts`의 CRLF 오탐도 환경. **같은 검사, 다른 OS/toolchain, 다른 표면.**
- **실행위치**: `.venv`(프로젝트) vs 시스템 `python`이 "실행 가능"을 "collection 불가"로 뒤집었던 것, `/c/` MSYS 경로 vs 상대경로가 스크립트를 실패시킨 것. **같은 명령, 다른 cwd/interpreter, 다른 결과.**

## 재현성 규칙 판단 — Codex 9항 + 빠진 것

Codex가 제안한 규칙(9항)은 강하고 "SHA+위치"보다 훨씬 낫다: (1) full SHA+branch (2) worktree 경로 (3) 정확한 명령+작업 디렉터리 (4) 인터프리터/런타임 버전 (5) KST 시작·종료 (6) 직접 종료코드 (7) pass/fail/skip/deselected 수+skip 사유 (8) artifact 경로 (9) **실행자와 검토자가 동일인인지**. 그리고 "변경 후 결과 SHA에서 영향 검사 재실행 후에만 verified". 특히 (9) 독립성 명시는 내가 못 넣은 좋은 항목이다 — 이 문서의 대조 자체가 그 원칙(Codex 실행, Claude 독립 재실행)의 실천이다.

**그러나 부족하다. 빠진 것을 더한다:**
- **(A) 워킹트리 clean 상태 — Codex 9항에 없다(사용자가 짚은 핵심).** SHA X에 dirty tree면 그 SHA는 거짓이다. **측정법까지 명시**해야 한다: `git status --porcelain`가 빈값인가. 그리고 **EOL 드리프트 게이트는 `git diff --exit-code`로**(Windows에서 `git status`는 CRLF를 M으로 오탐 — 오늘 `models.py`가 실증). 즉 "clean"은 어느 명령으로 쟀는지가 결과를 바꾼다.
- **(B) 환경 지문 + "안 돌린/skip한 검사와 그 이유"를 1급 항목으로.** (7)의 per-test skip 사유로 부분 커버되나, "이 호스트는 PG/Docker/Go/browser를 못 돌려 그 게이트를 통째로 생략했다"는 메타 사실이 표면에 있어야 한다 — 그래야 Windows "전부 통과"가 CI 통과와 다름을 읽는이가 안다.
- **(C) 계측 자체의 신뢰성을 규칙으로.** Codex는 실천했다(파이프 없이 `$LASTEXITCODE` 즉시 출력)지만 규칙 항목이어야 한다: 손수 파싱 말고 종료코드, `| tail`이 exit 가리는 PIPESTATUS 함정 회피. 오늘 내 clean-체크(escaped-quote 버그)·loose-regex(16/32)·PIPESTATUS(exit=0 오기)가 전부 계측 오류였다.

**최종 규칙(합의 제안)** = Codex 9항 + (A) clean 상태(측정법 명시) + (B) 환경 지문·생략목록 + (C) 신뢰 가능한 계측. 사용자가 짚은 네 가지(인터프리터 절대경로·실행 디렉터리·SHA·clean)는 이 규칙의 핵심 골격이며, **오늘 우리가 틀린 경우가 전부 그중 하나(대개 clean 또는 SHA 또는 인터프리터)가 빠져서였다.**

## 소감 — 세 agent + 사용자가 상호 정정하며 일한 방식
효과적이었던 것: 독립 검토를 **재읽기가 아니라 변형·실측·재실행으로** 한 것이 진짜 결함을 잡았다(공허 시험, 타임아웃 누수, guard 실포착, 부하 전제 뒤집기, 그리고 이 대조). 사용자가 매번 **기준을 못 박은 것**("현재 저장소", "어느 tip", "clean인가")이 경계 미끄러짐을 반복 차단했고, 발견을 **증거 딸린 문서로 남긴 것**이 다음 정정의 출발점이 됐다. 비효율적이었던 것: **같은 경계·귀속 오류가 셋 모두에게서 여러 번 재발**해(수치 재계산, 올바른 tip 재검토, 브랜치/통합 혼동) 매번 한 왕복씩 소모됐다. 특히 **아무도 pass-report에 tip을 안 박아 브랜치-통합 괴리를 하루 종일 못 봤다**(check_docs). 상호 정정 루프는 오류를 **잡는 데는 탁월**했으나, **같은 유형이 재발한 이유는 인스턴스만 고치고 convention을 안 고쳤기 때문**이다. 다음에 같은 방식으로 일한다면: 상호 독립 검토(특히 실행자≠검토자)는 유지하되, **첫날부터 provenance 헤더를 강제**해 사후 정정을 예방으로 바꾸는 것 — 그것이 오늘 하루의 진짜 산출물이다.

## 인계
Codex 감사 재현 완료(같은 tip 같은 결과). 재현성 규칙은 Codex 9항 + clean 상태 + 환경/생략목록 + 신뢰 계측으로 합의 권고. reviewer: Codex(내가 더한 A/B/C가 충분한지 경계 재검토). 환경 게이트(PG/Docker/Go/browser)의 실제 실행은 여전히 격리 Linux/PG/CI에서의 별도 확인이 필요하다 — 이 Windows 대조는 그 게이트들을 생략했다.
