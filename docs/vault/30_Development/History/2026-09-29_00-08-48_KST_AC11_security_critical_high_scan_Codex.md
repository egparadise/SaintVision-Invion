---
doc_id: "HISTORY-S11-AC11-SECURITY-SCAN-20260929"
title: "AC-11 security critical/high hosted scan과 fail-closed 집계"
version: "1.0.3"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-29T00:18:59+09:00"
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
- `s11-security-dependency-sast-allowlist-v1.json`은 scanner 버전·scope·severity policy·producer/workflow Git blob을 고정한다. 예외는 exact finding ID, 사유, timezone-aware 만료를 모두 요구한다. 초기 allowlist는 빈 목록이다.
- 보고서에는 dependency 설명, Bandit source snippet, URL, credential 값을 싣지 않고 scanner/rule/component/location의 안정 식별자만 남긴다. scanner exit 2 이상은 zero finding이 아니라 `NOT_OBSERVED`다.

## fail-closed 결속

- 집계기의 security 축은 `SEC-DEF-001`, `SEC-RLS-001`, `SEC-VF-001`, `SEC-SCAN-001` 네 report exact set을 요구한다. 새 report 누락 또는 canonical payload SHA 불일치는 `NOT_OBSERVED`다.
- allowlist 밖 critical/high, 만료 예외, stale allowlist, severity mismatch는 `MEASURED_FAIL`이다. producer verdict가 재계산과 다르면 `INVALID_RUN`이다.
- scanner 버전, registered scope Git object, producer/workflow blob, allowlist blob 중 하나가 source tree와 다르면 `INVALID_RUN`이다. 기본 CI에는 새 repo-wide scan을 넣지 않고 `run-ac11-security` label 또는 `workflow_dispatch`로만 실행한다.

## 현재 검증

- `python -m pytest -q tests/test_ac11_security_scan.py` → **7 passed**, exit 0. Git object ID용 SHA-1에 `usedforsecurity=False`가 없으면 실패하는 AST 회귀 시험을 포함한다.
- `python -m pytest -q tests/test_aggregate_ac11_evidence.py` → **63 passed**, exit 0.
- `python -m py_compile tools/run_ac11_security_scan.py tools/aggregate_ac11_evidence.py` → exit 0.
- workflow YAML safe-load와 `git diff --check` → exit 0. producer blob `de439f28…4c5b`, 수정 workflow blob `aabc8270…288a`, allowlist blob `74dde5cb…2f70`을 서로 대조했다.
- `check_docs`(935 versioned documents), `check_contract_bindings`(55 fixtures·20 response types·14 replay guards), `check_ontology`, `check_doc_single_source --ratchet` → 모두 exit 0.
- 최초 push run `36441818573`은 job 0으로 workflow validation 실패했다. job-level `env`에서 step 실행 전에는 사용할 수 없는 `runner.temp` context를 쓴 것이 원인이므로 raw scanner 경로를 `/tmp`로 고정하고 workflow·allowlist blob pin을 함께 갱신했다. 보안 scan이 실행된 결과가 아니며 PASS 또는 finding 0 증거로 세지 않는다.
- 첫 실제 scan run `36442219055`(head `7e8d765c`)은 `pip-audit` finding 0, Bandit LOW 13·MEDIUM 4·HIGH 1로 artifact를 보존한 뒤 gate가 실패했다. 유일한 HIGH는 `remote_git.py`의 Git wire object ID 계산 `B324`였고, 예외 등록 없이 제품 코드에 `usedforsecurity=False`를 명시했다.
- 수정 exact head `d64dd7fdd84bd6749e3998c1bd3d76d69cd4ecfa`의 opt-in run `36442706696`은 **success**다. `pip-audit` 41 dependencies·finding 0, Bandit LOW 13·MEDIUM 4·HIGH 0, critical/high 0, verdict `MEASURED_PASS`, JUnit 4/0/0/0이다. artifact `10979282713`, digest `sha256:01cb09e5da2a865e7780da99569bc218b5f69402720338170ed59c06f9b14f0c`, payload SHA-256 `f0a8425e483fad3898de8604a3d561495140fb2f0ba73517dafccf6bc4d965a4`, 만료 `2026-10-28T15:19:58Z`를 직접 내려받아 대조했다.
- 제품 경로 단일 파일 `tests/core/test_workspace_bridge.py`는 로컬 기본 Python 3.10에 `enum.StrEnum`이 없어 수집 전 차단됐고, 설치된 Python 3.14에는 pytest가 없었다. 이를 통과로 세지 않으며 최종 제품 회귀 근거는 hosted Backend 결과로 보완한다.

## 남은 일

- PR #226에서 Claude 독립 검토와 hosted Backend green을 확인한다. 전체 AC-11은 다른 필수 축 때문에 계속 미완료다.

관련 문서: [[S11-BE_DB_AC-11_통합_인수_설계]], [[Codex 작업 현황]].
