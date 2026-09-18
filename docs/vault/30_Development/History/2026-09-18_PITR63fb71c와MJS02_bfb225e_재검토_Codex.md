---
doc_id: "HIST-CODEX-PITR-MJS02-REVIEW-001"
title: "PITR63fb71c와MJS02 bfb225e 재검토 Codex"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-18T15:45:06+09:00"
source_of_truth: "Git"
---

# PITR63fb71c와MJS02 bfb225e 재검토 Codex

owner 구현 Claude(PITR)/Gemini(MJS), 계약 reviewer Codex. 기준 integration120a8a0, 고정 대상63fb71cb9eeed77d7c1cb015b932c5f14af6d8d9/bfb225ed596649288c5c8507b6b641afed42f534. agent-delivery1.1.0/core-reliability1.0.0 적용. 사용자 입력은 소스 확인이며 이번 실행과 구분한다. 기존 finding 수정본 검토만 수행; 새 전수 감사·실제Docker/PG/image/운영 인수 실행 없음.

## PITR-R2-02 판정: 코드 보류 사유 해소

무작위128-bit run nonce를 NAME/label에 결속, 실패한 ps를 query-error로 구분, rm 실패/재조회 잔존은 rm-error, 확인된 clean만 변경 재시도 허용. 본문 PASS와 trap cleanup 경고는 별개이며 cleanup 불확정을 물리복원 실패나 확인된 정리로 바꾸지 않는다. final trap의 본문 종료코드 보존은 이번에는 소스 검토 범위다.

고정SHA에서 git show로 추출한 원본 tools/pitr_rehearsal.sh와 tests/test_pitr_rehearsal_ownership.sh를 Git Bash로 실행: **13 checks PASS, exit0**. 실제 Docker 대신 가짜 CLI. 다음 범위를 구분한다.

| 조건 | 원본 시험 | Codex 보강 |
|---|---|---|
| 정상/확인된 부재 | clean/삭제0/owned ID 삭제 | timeout 후 실제 대역 owned 삭제와 재조회 clean 뒤 run2/exit0 |
| 다른 owner/과거 run | 빈 ps를 가정하므로 필터 자체 검증은 약함 | 매 ps의 정확한 nonce label 인자를 검사; foreign/past 표식 유지. 실제 Docker의 filtering 구현 시험은 아님 |
| ps 실패 | query-error, run1/exit1 | 동일 대조 및 삭제 후 재조회 실패에도 run1/exit1 |
| rm 실패 | rm-error, run1/exit1 | 동일 대조 |
| timeout 후 확정/미확정 | clean 뒤run2,query/rm-error 뒤run1 | rm 성공이어도 재조회에 남으면 run1/exit1 |

보강 **5 scenarios PASS, exit0**: clean/query/rmfail/postquery/retained. 원본13과 합쳐 독립 제품시험18개라고 세지 않는다. Evidence의 pitr-63fb71c-review-harness.sh는 Git Bash용이다. 재현 시 작업 디렉터리에 tools/pitr_rehearsal.sh를 `git show 63fb71c:tools/pitr_rehearsal.sh`로 추출해 두고 해당 harness를 같은 작업 디렉터리에 복사해 실행한다. fake-docker/state만 사용한다. 원본13의 외부owner 검증 약점은 제품 결함 실증이 아니며 이번 정확한 필터 대조로 보완했다.

### 전체 Claude 브랜치 착지와 구분

**PITR cleanup 코드 hold는 해제**한다. 그러나 전체 브랜치의 문서 정정 요청은 아직 충족되지 않았다. 63fb71c의 `2026-09-19_Claude영역_검증상태지도.md` §1에 fixture11을 여전히 '사용자 실 PG 11 passed', 1eaf285/75초를 'Codex 실행'으로 표기한다. 실제로 전자는 대역 시험, 후자는 사용자 보고다. PITR 제안의 기존 R1-04 잔여인 idle floor/`wal_keep_size` 설명도 남았다. 이는 새 cleanup blocker가 아니라 앞서 전달한 문서 정정 잔여다. 전체 branch는 이번에 병합하지 않았다. 실제 운영 RPO/off-host 인수와 이 문서 정정을 혼동하지 않는다. 다음 Claude: 해당 정정 diff 제출 → Codex 최종 전체 착지 확인. 물리 rehearsal 재실행을 요구하지 않는다.

## MJS-02 지정 세 항목: 해소 확인

원본 recordUnverified 함수와 UI3항목~summary 구간을 변경 없이 추출해 VM에서 실행했다. 기존 집계 2/2,1/2,0/0을 주입한 **3 시나리오 PASS(exit0)**: 모두 unverified3, passed/total 증가0. 전체 성공일 때만exit0, 실패/0수집exit1. 요약은 API Contract Smoke이며 UI는 browser lane 미검증으로 표시한다. 0/0의 NaN%는 표시상 잔여지만 성공으로 통과하지 않는다. 이 시험은 전체 runner199/199나 실제 화면 인수 증거가 아니다. Evidence mjs-bfb225e-summary-review.mjs/json에 원본 고정SHA와 결과 보존.

### MJS02-R1 / P2: 신규 회귀 시험의 실행 환경 경계

`tests/test_browser_smoke_boundary.py` 41~53: Node 존재만으로 실제 전체 smoke를 호출하고 exit0을 요구한다. 기본 not docker_host 선택에서 빠지지 않고 tests/integration 밖이다. backend 준비/격리 fixture나 명시적 opt-in이 없다. runner는 조회뿐 아니라 run/approval/drain/resume 등의 POST를 한다.

고정SHA 파일을 격리 경로에 추출하고 TEST_BASE_URL/TEST_BACKEND_URL을 `http://127.0.0.1:0`으로 설정해 두 시험 실행: **1 passed/1 failed, exit1, 0.22초**. 실패는 첫 fetch의 연결 오류(EADDRNOTAVAIL)이며 UI 단언에 도달하지 않았다. 실제 backend에 접속하거나 POST하지 않았다. 이는 제품 UI 실패가 아니라 backend 없는 기본 회귀 경계의 재현이다. 사용자1254통과 기록은6feccd8이며 bfb225e에도 적용되지 않는다.

Gemini 해소조건: 기본 시험은 원본 함수/runner의 격리 대역으로 집계 계약을 확인. 실제 full smoke 실행은 명시적 통합 lane과 소유 격리 backend로 옮겨 자동 기본 선택에서 제외. 단순 Node skip이나 살아 있는 아무 localhost에 접속하는 가드로 해결하지 않는다. backend 없는 기본 실행 성공, 명시 lane의 선행조건 미충족 표기, mutation의 격리 대상을 대조한다. 199 고정값을 다른 전체개수의 영구계약으로 만들 필요는 없다.

### MJS02-R2 / P2: 인접 상수 UI 단언 잔여

동일 bfb225e 914~915에 `const hasDesktopShell = true`와 bidirectional Desktop/Portal switcher PASS가 남았다. 지정 세 이름 제거는 맞지만 summary의 observed checks 전체가 실제 UI 관측이라는 뜻은 아니다. Gemini는 이 한 항목도 미검증/PASS제외 또는 실제 UI 관측으로 결속해야 한다. 기존 MJS02 잔여로 추적하며 별도의 감사 전체분모를 새로 부풀리지 않는다. 전체 smoke 상단 E2E 표제도 실제 범위와 맞출 필요가 있다. 과거 모든 실행이 가짜였다는 판정은 하지 않는다.

## 전달과 다음 행동

bfb225e는 이미 integration에 들어와 있어 원격 변경을 fast-forward로 수신했다. 신규 기본시험 문제를 숨긴 채 전체회귀 통과로 보고하지 않는다. Gemini R1/R2 수정본, Claude 문서 정정본을 고정SHA로 재검토한다. 현재 세 UI항목과 PITR cleanup이 해소된 사실은 잔여와 별도로 유지한다. 외부5조건/운영인수0/5/image4pass2fail2skip은 변동없음.

검증: check_docs 552문서 PASS/exit0, check_ontology PASS/exit0. 보존된 MJS 원본구간 harness 재실행 exit0, PITR 보강 재실행 exit0. 이 재실행을 새 독립시험으로 합산하지 않는다. CI는 기존 외부대기로 미실행.
