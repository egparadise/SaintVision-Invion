---
doc_id: "HISTORY-S11-AC11-SECURITY-SCAN-20260929"
title: "AC-11 security critical/high hosted scan과 fail-closed 집계"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-29T00:53:49+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
task_id: "S11-BE"
acceptance_id: "AC-11"
tags: ["S11", "AC-11", "security", "SAST", "dependency-audit", "hosted"]
---

# AC-11 security critical/high hosted scan과 fail-closed 집계

## 범위와 결정

- branch `agent/codex/ac11-security-hosted-scan`, base #217 승인 head `35c5b207682c19cdc2be3e05df22e91bd4f4475f`, owner Codex·reviewer Claude다. 기존 registry target과 blob `be99a506…`는 바꾸지 않는다.
- `pip-audit 2.10.1`은 `requirements-core.txt`의 취약점 전부를 안정 severity 부재 때문에 high로 보수 분류한다. `bandit 1.9.4`는 `services/control-plane/src`와 `src/saintvision`의 HIGH만 critical/high 분모에 넣는다. JavaScript·Go·container·운영 credential/network 검사는 이 카드가 측정했다고 주장하지 않는다.
- `s11-security-dependency-sast-allowlist-v1.json`은 scanner 버전·scope·severity policy·producer/workflow/importer Git blob을 고정한다. 예외는 exact finding ID, 사유, timezone-aware 만료를 모두 요구한다. 초기 allowlist는 빈 목록이다.
- 보고서에는 dependency 설명, Bandit source snippet, URL, credential 값을 싣지 않고 scanner/rule/component/location의 안정 식별자만 남긴다. scanner exit 2 이상은 zero finding이 아니라 `NOT_OBSERVED`다.

## fail-closed 결속

- 집계기의 security 축은 `SEC-DEF-001`, `SEC-RLS-001`, `SEC-VF-001`, `SEC-SCAN-001` 네 report exact set을 요구한다. raw scan report는 직접 소비하지 않고 importer가 canonical repository의 run/artifact metadata·zip SHA-256·source head·workflow·expiry를 결속한 결과만 받는다.
- allowlist 밖 critical/high, 만료 예외, stale allowlist, severity mismatch는 `MEASURED_FAIL`이다. producer verdict가 재계산과 다르면 `INVALID_RUN`이다.
- source head/tree·clean checkout·source run ID·hosted environment·started/finishedAt(30일 freshness)·artifact digest 중 하나가 결속되지 않으면 `NOT_OBSERVED` 또는 `INVALID_RUN`이다. Bandit `errors[]`, direct pin 누락, production Python file inventory 불일치, scanner exit/count 모순은 fail-closed다. 기본 CI에는 새 repo-wide scan을 넣지 않고 `run-ac11-security` label 또는 `workflow_dispatch`로만 실행한다.

## 현재 검증

- `python -m pytest -q tests/test_ac11_security_scan.py tests/test_import_ac11_security_scan.py tests/test_aggregate_ac11_evidence.py` → **101 passed**, exit 0. provenance/digest/expiry/head/run/workflow, Bandit parse error·source inventory, pip-audit 빈 목록·direct pin 누락, freshness 부정 시험을 포함한다.
- `python -m py_compile tools/run_ac11_security_scan.py tools/import_ac11_security_scan.py tools/aggregate_ac11_evidence.py`, workflow YAML safe-load, `git diff --check` → 모두 exit 0.
- 검토 반영 blob은 producer `87d142e0…0f32`, workflow `84dea5d4…996`, importer `86617533…819`, allowlist `7e78403a…3ba`고 집계기 상수와 일치한다.
- `check_docs`(935 versioned documents), `check_contract_bindings`(55 fixtures·20 response types·14 replay guards), `check_ontology`, `check_doc_single_source --ratchet` → 모두 exit 0.
- 최초 push run `36441818573`은 job 0으로 workflow validation 실패했다. job-level `env`에서 step 실행 전에는 사용할 수 없는 `runner.temp` context를 쓴 것이 원인이므로 raw scanner 경로를 `/tmp`로 고정하고 workflow·allowlist blob pin을 함께 갱신했다. 보안 scan이 실행된 결과가 아니며 PASS 또는 finding 0 증거로 세지 않는다.
- 첫 실제 scan run `36442219055`(head `7e8d765c`)은 `pip-audit` finding 0, Bandit LOW 13·MEDIUM 4·HIGH 1로 artifact를 보존한 뒤 gate가 실패했다. 유일한 HIGH는 `remote_git.py`의 Git wire object ID 계산 `B324`였고, 예외 등록 없이 제품 코드에 `usedforsecurity=False`를 명시했다.
- Claude r1 F1~F7에서 raw report의 run/artifact/source SHA 미결속, Bandit `errors[]` 무시, freshness·direct pin 검증 부재, `externalServicesRequired` 오표기가 확인됐다. importer 추가와 집계 재검증으로 전부 fail-closed로 닫았다. `pip-audit`는 PyPI/vulnerability database를 쓰므로 외부 서비스 0이 아니며 credential 0이다.
- 첫 remediation run `36446508539`(head `d187abbf`)은 정상 파일 `src/saintvision/identity/tokens.py`의 `token` 부분 문자열을 비밀로 잘못 판정한 workflow redaction 오탐으로 실패했다. JSON 전체 문자열이 아닌 금지된 필드 키를 재귀 검사하도록 고치고 회귀 시험으로 고정했다.
- head `ac374c4951e3e9e1ca3aa0a66bcffe2402eee3c5`의 opt-in run `36446788145`는 **success**다. artifact `10980753683`, GitHub digest와 직접 zip SHA-256은 모두 `335d0398aed350d82d1210a4de8d05805f42b86fc028929555852a873d9d98de`다. importer 결과를 집계기에 넣어 `MEASURED_PASS`를 재확인했다. payload `00c7c9e8…56dd`, dependency 41·취약점 0, Python file 179, Bandit HIGH 0, critical/high 0이다.
- 제품 경로 단일 파일 `tests/core/test_workspace_bridge.py`는 로컬 기본 Python 3.10에 `enum.StrEnum`이 없어 수집 전 차단됐고, 설치된 Python 3.14에는 pytest가 없었다. 이를 통과로 세지 않으며 최종 제품 회귀 근거는 hosted Backend 결과로 보완한다.

## 남은 일

- PR #226에서 Claude 재검토와 최종 docs head hosted Backend를 확인한다. 전체 AC-11은 다른 필수 축 때문에 계속 미완료다.

관련 문서: [[S11-BE_DB_AC-11_통합_인수_설계]], [[Codex 작업 현황]].
