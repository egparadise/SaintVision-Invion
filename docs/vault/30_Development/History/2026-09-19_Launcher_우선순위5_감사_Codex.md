---
doc_id: "LAUNCHER-PRIORITY5-AUDIT-20260919-CODEX"
title: "Launcher 우선순위 5 실패 경계 감사"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-19T01:00:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
---

# Launcher 우선순위 5 실패 경계 감사

## 확인 범위

원본 `deploy/lan/Start-LiveConsole.ps1`, `deploy/studio/Open-Tool.ps1`, `deploy/studio/Agent-Shell.ps1`, `Start-Environment.ps1`와 worker shell launcher를 읽고, 실패를 성공으로 바꾸거나 도달하지 않은 health·rollback 조건을 성공으로 읽는 경계를 표본 점검했다. CI/실장비/Agent GUI 세션은 실행하지 않았다.

## 결과

### LiveConsole Docker start 실패

`Start-LiveConsole.ps1`는 소유 pilot DB가 stopped일 때 `docker.exe start`를 호출했지만 native exit code를 검사하지 않았다. start가 실패해도 직접 launcher가 listener 시작 단계로 진행할 수 있는 경계였다. 이 경로에 즉시 `LASTEXITCODE` 검사와 “No listeners were started” 예외를 추가했다.

### Agent-Shell / NoExit

`Open-Tool.ps1`의 `-NoExit`는 의도된 대화형 세션 전달이며 자식 도구의 완료·성공을 보고하는 경로가 아니다. 따라서 이를 작업 성공으로 집계하지 않고, GUI를 연 사실만 반환하는 경계로 유지한다. 실제 Agent 도구의 종료 결과는 해당 세션/도구가 별도 기록해야 한다.

### Shell 조건식·치환 실패

PowerShell launcher의 `ErrorActionPreference=Stop`, `Test-Path -LiteralPath`, `LASTEXITCODE` 검사와 Bash launcher의 `set -euo pipefail` 및 명시적 파일·identity 검사는 표본에서 확인됐다. 추가로 “모든 launcher가 안전하다”는 결론은 내리지 않으며, WSL/실장비에서의 native command·환경 치환 실행은 미검증이다.

### 오래된 패키지·rollback·health 의미

`Start-Environment.ps1`의 HTTP health는 서비스 준비 확인이지 image/package freshness나 운영 인수 증명이 아니다. `Enable-Workspace.ps1`의 rollback은 child exit code를 전달하지만 실제 장비·journal 보존은 별도 인수다. 이 감사에서 health/rollback을 제품 완료로 승격하지 않았다.

## 회귀 확인

`tests/core/test_launcher_failure_boundaries.py`는 C# `docker.exe` shim을 컴파일해 `PATH` 앞에 주입하고, 원본 PowerShell launcher가 실제로 `inspect`와 `start`를 호출했는지 먼저 확인한 뒤 start exit 7 경로를 실행한다. 호출 전제가 성립하지 않으면 `ASSERT-FAIL`로 종료하므로 단순 문자열 검사가 아니다. Agent-Shell의 `NoExit`는 interactive 경계로 문서화하며 완료 신호로 세지 않는다. 이 시험은 실제 Docker daemon·WSL·GUI 운영 인수를 대체하지 않는다.

## 다음 범위

Docker start 실패 주입은 daemon 없이 shim으로 행동 검증을 완료했다. WSL native exit 전달, Agent GUI 자식 도구 실패, package rollback과 health의 운영 의미는 Docker/WSL/사용자 세션이 필요한 별도 운영 검증으로 남긴다.

## 후속 정정 및 검증

독립 검토에서 launcher 선행 파일(`.venv/Scripts/python.exe`, `apps/web/node_modules/vite/bin/vite.js`)이 없는 fresh checkout에서는 Docker shim까지 도달할 수 없다는 점을 확인했다. 행동 시험은 이 조건을 명시적 사유가 포함된 `pytest.skip`으로 처리하고, 두 파일이 존재하는데 shim 호출이 없을 때만 `ASSERT-FAIL`로 남긴다. 따라서 환경 미설치와 제품 동작 실패를 구분한다.

또한 `tools/deploy_intranet.ps1`은 Step 1에서 선택한 `$certDir`을 `$env:SAINTVISION_DEV_CERT_DIR`에 반영한다. 인증서 경로를 `deploy/certs`로 폴백한 경우에도 Step 5의 Compose required-variable 검증이 같은 경로를 사용한다. 외부 경로 시험은 Compose 단계에서 환경변수 전달을 확인하도록 고정했다.

검증: `python -m pytest -q tests/core/test_launcher_failure_boundaries.py tests/test_deploy_intranet_preflight.py` → **18 passed**; `git diff --check` → **PASS**.

## 감사 정정 — 인터프리터·되돌림 근거

위 첫 검증 명령은 bare `python`이라 어느 인터프리터가 실행됐는지 이 문서만으로 확정할 수 없다. 이 결과를 프로젝트 venv 실행으로 소급 표기하지 않는다. 2026-09-19 감사자가 명시적으로 `.venv\Scripts\python.exe -m pytest -q tests/core/test_launcher_failure_boundaries.py tests/test_deploy_intranet_preflight.py`를 재실행해 **exit 0, 18 passed in 21.61s**를 확인했다. 이는 현재 통합 코드의 재검증이다.

처음 Docker start 실패 주입을 실장비 필요/미검증으로 분류한 기록은 정정한다. 제품 Docker daemon은 필요하지 않다. C# `docker.exe` shim을 PATH 앞에 두고 원본 PowerShell launcher를 실행하는 격리 주입이 가능하며, 시험은 실제 `inspect`/`start` shim 호출 marker를 확인한다. 사용자는 LASTEXITCODE guard를 제거한 되돌림에서 시험 실패, 선행 Vite 파일을 숨긴 상태에서 사유가 출력되는 skip을 독립 재현했다. 따라서 shim 실패 주입은 확인됨, 실제 Docker·WSL·GUI 인수는 미검증이다. 작성자 Codex의 실행과 사용자 독립 재현은 별도 근거다.
