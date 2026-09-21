---
doc_id: "GOV-PRECI-CROSS-LANE-VERIFY-TEMP-001"
title: "CI 개방 전 임시 교차 레인 검증 절차 (수용본; Codex 제안 3f61d76a 기반, Claude 수정 수용)"
status: "active-temporary"
version: "1.0.0"
author: "Claude (governance owner)"
origin_proposal: "Codex 3f61d76a"
retire_when: "종료 조건 4항 충족 시 (아래)"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["governance", "verification", "ci", "cross-lane", "temporary"]
---

# CI 개방 전 임시 교차 레인 검증 절차

> **임시.** hosted CI(GitHub Actions)가 결제로 미개방인 동안만. CI가 실제로 도는 것이 확인되면 **이 문서 전체를 삭제**한다(종료 조건·담당 아래). 워크플로 YAML 배선을 실행 결과로 치지 않는다.

## 핵심 한 줄 (이것만 지켜도 오늘 밤 사고는 안 났다)
**네 레인을 고쳤으면 다른 레인의 가드도 돌려라.** 한 레인 초록은 다른 레인 초록의 증거가 아니다.
- 프런트(`apps/web`) 변경 → vitest **와** Python UI guard `tests/test_route_coverage.py`를 **둘 다**. (오늘 EvidenceViewer 가짜 PASS가 vitest만 돌려 놓친 그 자리.)
- 계약/스키마/fixture 변경 → **양쪽 consumer**(Python 계약시험 + 프런트 contracts:check/vitest).
- 매번 전부는 안 돌린다 — 변경 범위가 실행 레인을 정한다(표).

## 변경 범위 → 최소 실행 (동일 최종 SHA·clean tree, `tools/provenance.py --`로 기록)
| 변경 | 최소 실행 | 조건부 추가 |
|---|---|---|
| 문서만 | `check_docs.py`; task/ontology 매핑 바뀌면 `check_ontology.py` | Obsidian 내보내기 전 `sync_obsidian.py --check` |
| 화면·상태·API 경로(`apps/web/src`) | `npm run test`(vitest) + `npx tsc -b` + `npm run build` + **`tests/test_route_coverage.py`** | endpoint/요청 경로 바뀌면 `tests/integration/test_vf_canonical.py`(PG) |
| 계약·공유 fixture·생성 타입·adapter | `export_schemas.py --check` + `check_contract_bindings.py` + 프런트 `contracts:check` + vitest 전체 + 해당 `tests/core/*contract*` | producer 서비스/route도 바뀌면 PG API integration; 권한·RLS·mutation은 real PG 필수 |
| backend route·상태·authorization·DB/migration | 해당 focused pytest + 관련 core/API contract 시험 | DB state/role/RLS/migration이면 disposable PG; public route/프런트 client 집합 바뀌면 `test_vf_canonical.py` |
| 로그인·주요 여정·브라우저 전용/다운로드·proxy/TLS·DOM | 위 해당 레인 vitest/pytest | `desktop-browser.yml` Chromium+HTTP+DB; proxy/TLS면 web-container |
| **여러 agent 통합·대량 migration·release/handoff 전** | → **[[검증규칙과_세축_canon]] 규칙 8**(마지막 상태 전수 검증)을 따른다. 여기 다시 쓰지 않음(단일 소스). | — |

## 결과 보고 (짧게)
- 레인마다 정확한 command·cwd·exit·pass/fail/error/skip 수와 **skip 사유**를 따로. 다른 interpreter/SHA 숫자를 합치지 않는다.
- provenance: full SHA·worktree·clean 여부·절대 interpreter 경로·KST·실행자·PG/Docker/Go/Node/browser 게이트.
- **한 레인 성공 ≠ 전체 완료.** prerequisite 없어 못 돈 것은 `unverified`+사유(= not_run), **skip을 pass에 더하지 않는다.**

## 종료 조건 (배선 아닌 실행 기준)
다음 **모두** 충족 시 이 임시 절차를 내린다:
1. GitHub Actions 결제/계정 blocker 해소.
2. **같은 integration SHA**에서 `docs·backend·core·frontend·desktop-browser` **다섯 workflow가 실제 시작·완료**(YAML 존재·job 존재는 불충분).
3. 각 workflow가 의도한 시험을 실제 실행했고 금지된 skip/error/failure **0**(opt-in 레인은 기대 testcase 집합+no-skip gate 통과).
4. 그 run URL/SHA와 JUnit/evidence를 History에 남기고 **사용자가 CI 복구 확인**.

## 누가·언제 지우나 (임시가 임시로 지켜지게 — Claude 수정 추가)
- **트리거**: 위 4항이 어느 integration SHA에서 최초로 모두 성립하는 순간(조건 4의 사용자 확인이 시작 신호).
- **담당**: governance/집계 owner(Orca; 세션 없으면 Codex)가 수행.
- **행동(한 커밋)**: (a) 종료 근거(run URL·SHA·JUnit)를 History에 기록, (b) **이 문서를 삭제**, (c) [[검증규칙과_세축_canon]] 규칙 8에 걸린 이 문서 포인터 제거. 셋을 안 하면 "임시"가 영구가 된다 — 조건 충족 후에도 남아 있으면 그 자체가 규칙 위반.
- 부분 실패(어느 workflow 비활성/필수 시험 skip) 시엔 해당 레인만 다시 임시 수동으로 요구하고 문서는 유지.

## 근거·경계
왜 필요한가·상세 실례는 원제안 [[2026-09-22_CI개방전_조건부_수동검증절차_제안_Codex]]와 [[2026-09-22_통합_전수검증_마무리_및_EvidenceViewer_가짜PASS_회귀_Claude]]. 이 절차는 CI 전체 품질 보장 선언이 아니라 **다섯 레인 자동 실행 확인까지의 공백을 메우는 임시 운용**이다. 구조적 근본 수정(정직성 스캐너를 파일지정→모양지정)은 [[2026-09-22_되돌아오는결함_구조가막나_주의에기대나_Claude]].
