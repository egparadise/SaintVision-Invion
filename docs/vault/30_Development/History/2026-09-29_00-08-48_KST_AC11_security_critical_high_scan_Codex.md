---
doc_id: "HISTORY-S11-AC11-SECURITY-SCAN-20260929"
title: "AC-11 security critical/high hosted scan과 fail-closed 집계"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-29T00:11:42+09:00"
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

- `python -m pytest -q tests/test_ac11_security_scan.py` → **6 passed**, exit 0.
- `python -m pytest -q tests/test_aggregate_ac11_evidence.py` → **63 passed**, exit 0.
- `python -m py_compile tools/run_ac11_security_scan.py tools/aggregate_ac11_evidence.py` → exit 0.
- workflow YAML safe-load와 `git diff --check` → exit 0. producer blob `de439f28…4c5b`, workflow blob `942316a4…3b2`, allowlist blob `7b931231…b665`를 서로 대조했다.
- `check_docs`(935 versioned documents), `check_contract_bindings`(55 fixtures·20 response types·14 replay guards), `check_ontology`, `check_doc_single_source --ratchet` → 모두 exit 0.
- hosted opt-in run은 PR 생성 뒤 exact head에서 실행한다. 실행 전 상태를 PASS로 기록하지 않는다.

## 남은 일

- branch를 push하고 PR을 만든 뒤 `run-ac11-security` label로 hosted lane을 실행한다. 실제 finding이 나오면 자동 예외로 숨기지 않고 제품 수정 또는 사유·만료가 있는 독립 검토 대상 allowlist 변경으로 처리한다.
- hosted report·JUnit·artifact 식별자와 최종 게이트 결과를 이 문서와 작업판에 기록하고 Claude 독립 검토를 요청한다. 전체 AC-11은 다른 필수 축 때문에 계속 미완료다.

관련 문서: [[S11-BE_DB_AC-11_통합_인수_설계]], [[Codex 작업 현황]].
