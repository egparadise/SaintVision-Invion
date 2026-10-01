---
doc_id: "HISTORY-20261001-CARD162-AC11-SECURITY-LANDING-SHA-CODEX"
title: "CARD-162 AC-11 security critical/high 착지 SHA 실행과 PyJWT 교정"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-10-01T09:15:24+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_id: "S11-BE"
acceptance_id: "AC-11"
tags: ["S11", "AC-11", "security", "landing-sha", "pip-audit", "PyJWT"]
---

# CARD-162 AC-11 security landing SHA 증거

## 선택 근거

기준은 `origin/integration/all-agents-unified`의 `6fc0428b49f28379cb4da17830d92256b55c2eb2`다. #258 v1.6 §4-3-3은 AC-11 security 축의 다음 판정 조건을 **착지 tree SHA에서의 실행 기록 1건**으로 특정한다. producer `tools/run_ac11_security_scan.py`, importer `tools/import_ac11_security_scan.py`, opt-in workflow `.github/workflows/ac11-security-scan.yml`은 이미 기준 tree에 있으므로 추가 PC·CP·hosts·실 PG 없이 실행할 수 있다. 이 이유로 외부 전제 없는 Codex 고난도 후속 중 이 항목을 먼저 선택했다.

## 첫 착지 SHA 실행 — MEASURED_FAIL

- `workflow_dispatch`, ref `integration/all-agents-unified`, run `36794567345`, head `6fc0428b49f28379cb4da17830d92256b55c2eb2`를 실행했다.
- artifact `11132897489`의 이름은 `s11-ac11-security-6fc0428b49f28379cb4da17830d92256b55c2eb2`, GitHub digest는 `sha256:a0ec166d2263df013fd88897228d84cacb5faa906d5f249989dc23d10f950d4b`, 만료는 2026-10-31T00:08:07Z다.
- report는 clean checkout·동일 source SHA·dependency 41개·Python 192파일을 결속했다. Bandit HIGH 0과 달리 `pip-audit`가 PyJWT 2.13.0의 allowlist 밖 HIGH 13건을 검출했다. producer는 `MEASURED_FAIL / UNALLOWLISTED_CRITICAL_HIGH`, JUnit은 4 tests / 1 failure로 보존했고 workflow gate는 exit 1이었다.
- 이 실패는 실행 경로 결함이나 미관측이 아니다. landing tree의 실제 dependency finding이며 PASS로 세지 않는다.

## 교정 결정

- finding 13건을 allowlist에 넣지 않는다. PyPI의 현재 signed release와 upstream security changelog를 대조해 runtime과 scanner 입력의 exact pin을 PyJWT 2.15.1로 함께 올린다.
- `tests/test_ac11_security_scan.py`에 두 pin의 동일성과 2.13.0 잔존 금지를 고정한다. 공개 HTTP·JSON Schema·ProblemDetails·migration 표면은 바뀌지 않는다.
- PR head에서 focused identity/security 시험과 opt-in scan을 통과시켜도 **착지 SHA 조건은 아직 미충족**이다. 이 변경이 integration에 착지한 뒤 그 SHA로 같은 workflow를 다시 dispatch하고 importer로 artifact metadata·zip digest를 결속해야 조건이 닫힌다.

## PR head 교정 증거 — MEASURED_PASS

- PR #260의 exact head는 `d28a1e1d9510dc32da15c06c381207ffa326500a`다. opt-in security run `36795087571`은 이 SHA를 checkout해 성공했다.
- artifact `11133655643`의 GitHub digest는 `sha256:73d0e566bf22b079df2ed041c9f1468d6f2cfd66aa81ada69e3b9a9eeae112c0`, 만료는 2026-10-31T00:14:00Z다.
- 인증된 run/artifact metadata와 다운로드한 ZIP을 `tools/import_ac11_security_scan.py`로 결속한 결과 exit 0, `MEASURED_PASS / NONE`, HIGH 0, CRITICAL 0이었다. scanner와 runtime의 exact pin은 모두 PyJWT 2.15.1이다.
- 로컬 focused `tests/test_ac11_security_scan.py`는 **14 passed**였다. 로컬 시스템 Python 3.10은 제품의 `enum.StrEnum`을 제공하지 않아 `tests/core/test_identity.py`를 collect하지 못했으므로 통과 증거로 세지 않는다. 해당 제품 호환성은 hosted Backend Python 3.12·3.14 결과로만 판정한다.
- 이 성공은 수정 head의 재현성과 artifact 결속을 증명하지만, integration에 실제 착지한 SHA의 실행은 아니다. 따라서 #258 §4-3-3의 최종 조건은 merge/landing 뒤 exact integration SHA 재실행까지 열어 둔다.

## 상태

S11-BE는 75, AC-11 전체는 미완료다. 첫 실패와 후속 성공을 모두 남기며, 운영 또는 landing 증거를 PR head 증거로 소급 대체하지 않는다.
