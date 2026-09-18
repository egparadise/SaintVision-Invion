---
doc_id: "HIST-GEMINI-20260918-06"
title: "2026-09-18 15:15 KST 배포 런처 감사 지적 조치 (VB-LAUNCH-01) 및 사전검증 종료가드 Gemini 검증보고"
version: "1.0.0"
status: "approved"
author: "Gemini"
created: "2026-09-18T15:15:00+09:00"
updated: "2026-09-18T15:15:00+09:00"
timezone: "Asia/Seoul"
base_sha: "9082567"
source_of_truth: "Git"
---

# 배포 런처 감사 지적 조치 (VB-LAUNCH-01) 및 사전검증 종료가드 Gemini 검증보고 (2026-09-18 15:15 KST)

## 1. 개요 및 배경

- **실행 주체**: Gemini (Antigravity)
- **독립 감사/검토자**: Codex, Claude
- **기준 Commit**: `9082567`
- **감사 지적 수용 및 조치 (`VB-LAUNCH-01`, P2)**:
  - Codex의 배포 런처(`tools/deploy_intranet.ps1`) 감사에서 발견된 심각한 오류 은폐 결함 완전 해결:
    1. **PowerShell 네이티브 프로그램 종료 코드 무시**:
       - `deploy_intranet.ps1`의 인증서 부재 분기에서 `python tools/generate_tls_cert.py`를 호출한 직후 `$LASTEXITCODE` 검사가 누락됨.
       - PowerShell의 `$ErrorActionPreference = "Stop"`은 PowerShell cmdlet에만 적용되고 외부 네이티브 실행 파일(`.exe`, `.cmd`)의 비정상 종료를 catch하지 않음.
       - 이로 인해 인증서 생성이 실패(exit code 23)해도 후속 `npm test`, `npm run build`, `run_browser_smoke.mjs`가 성공하면 종료 코드가 0으로 덮어써져 최종적으로 "ZERO Errors (All Exit Codes 0)" 성공 배너가 출력되는 결함 확인.
    2. **인증서 및 빌드 산출물 무결성 실측 부재**:
       - 인증서 생성 스크립트 실행 후 `deploy/certs/saintvision.crt`, `saintvision.key`가 실제로 디스크에 존재하고 0 바이트 초과인지 검증하지 않음.
       - `npm run build` 후 `apps/web/dist/index.html`이 실제로 생성되었는지 검증하지 않음.
    3. **정직하지 못한 요약 및 스코프 혼동**:
       - Docker CLI가 없는 환경에서도 건너뜀 여부를 투명하게 분리하지 않고 일괄 성공 배너 출력.
       - 로컬 개발/CI 사전검증(preflight)과 온프레미스 5-노드 물리 장비 인수 시험의 경계 미표시.
    4. **음성 대조군(회귀 시험) 부재**:
       - 인증서 생성 실패 주입 시 스크립트가 Step 1에서 즉시 exit 1로 중단되고 Step 2(Vitest)로 진행하지 않는다는 회귀 시험 부재.

---

## 2. 주요 조치 내역

### 1) `tools/deploy_intranet.ps1` 가드 보강 및 정직한 스코프 개편
- **Python 네이티브 실행 직후 `$LASTEXITCODE` 검사 및 즉시 terminating throw**:
  - `& $pythonCmd tools/generate_tls_cert.py`
  - `if ($LASTEXITCODE -ne 0) { throw "TLS certificate generation failed with exit code $LASTEXITCODE" }`
- **인증서 파일 실존 및 >0 바이트 단언**:
  - `saintvision.crt`, `saintvision.key`의 `Test-Path` 및 `Length -eq 0` 검사.
  - 0바이트 인증서 발견 시 자동 재생성 트리거 및 사후 엄격 단언.
- **프로덕션 빌드 산출물 단언**:
  - `npm run build` 직후 `apps/web/dist/index.html`의 파일 실존 및 `Length -eq 0` 단언.
- **Docker Compose 사전검증 환경변수 자동 보정 및 정직한 상태 분기**:
  - `${INV_WEB_AUTH_CONFIG}`를 Windows 역슬래시가 치환된 정규 슬래시 경로로 바인딩.
  - `INV_CONFIG_VOLUME`, `INV_BUSINESS_DSN` 등 필수 변수 보충.
  - Docker CLI 미검출 시 `SKIPPED (Docker CLI not detected on host)`로 투명하게 표시.
  - 게이트웨이 라이브 프로브 결과를 `[OPT] Live Gateway Probe: ACTIVE` vs `OFFLINE`으로 분리.
- **파이프라인 전체 `try ... catch { throw $_ }` 가드**:
  - 어느 단계에서든 실패 시 오류 메시지를 출력하고 `throw $_`로 상위 프로세스에 즉시 종료 코드 1 전파.
- **정직한 스코프 요약 배너 (Honest Preflight Summary)**:
  - `[1/5] TLS 1.3 Certificates: VERIFIED`
  - `[2/5] Frontend & Protocol Tests: VERIFIED`
  - `[3/5] Production Asset Build: VERIFIED`
  - `[4/5] E2E Browser Smoke Suite: VERIFIED`
  - `[5/5] Compose Production Graph: VERIFIED / SKIPPED`
  - `[OPT] Live Gateway Probe: ACTIVE / OFFLINE`
  - `Scope Assurance Boundary` 명시: 로컬 사전검증 파이프라인이며 물리 5-노드 하드웨어 인수 및 베어메탈 클러스터 배포를 대체하지 않음.

### 2) 회귀 시험 스위트 작성 (`tests/test_deploy_intranet_preflight.py`)
Codex의 합성 대역 주입 실험에 대응하는 영구 회귀 시험 5건 작성:
1. `test_cert_generation_native_failure_halts_immediately`: 인증서 생성 실패(exit 23) 주입 시 Step 1에서 즉시 exit 1로 중단, Step 2 마커 미생성 단언.
2. `test_cert_generation_empty_file_halts_immediately`: 0바이트 인증서 생성 시 Step 1에서 즉시 exit 1로 중단.
3. `test_missing_cert_file_after_generation_halts_immediately`: 인증서 파일 미생성 시 Step 1에서 즉시 exit 1로 중단.
4. `test_missing_build_dist_index_halts_at_step3`: 빌드 후 `dist/index.html` 부재 시 Step 3에서 즉시 exit 1로 중단, Step 4 스모크 미실행 단언.
5. `test_honest_summary_table_format`: 모든 사전검증 성공 시 정직한 단계별 요약 및 Scope Boundary 출력 단언.

### 3) 독립 감사 대응 검증 러너 및 증거 파일 저장
- `docs/vault/30_Development/Evidence/verification-boundary-audit/launcher-fix-runner.py`
- `docs/vault/30_Development/Evidence/verification-boundary-audit/launcher-fix-results.json`
- Codex의 `launcher-results.json`과 동일한 5가지 케이스(tls-failure, tests-failure, smoke-failure, compose-failure, success)를 실측하여, 실패 케이스 4종 모두 processExit 1로 즉시 중단됨을 증명.

---

## 3. 실측 검증 결과 (Verification Evidence)

| 시험 항목 | 실행 명령 | 실측 결과 | 비고 |
|---|---|---|---|
| 배포 런처 회귀 시험 | `pytest tests/test_deploy_intranet_preflight.py -v` | **5 passed** (2.49s) | 음성 대조군 4건 + 요약 검증 1건 |
| 런처 대역 주입 실측 | `python docs/vault/.../launcher-fix-runner.py` | **5/5 PASS** (exit 1 x 4, exit 0 x 1) | `launcher-fix-results.json` |
| 실제 배포 사전검증 파이프라인 | `powershell -ExecutionPolicy Bypass -File tools/deploy_intranet.ps1` | **Exit Code 0** (모든 단계 검증) | 1~5단계 전수 통과 및 라이브 게이트웨이 정상 |
| 2PC 분산 실행 러너 | `node tools/verify_two_pc_distributed_execution.mjs` | **79/79 checks PASS** (3.42s) | VB-MJS-03 조치 상태 완결 유지 |
| 5화면 영수증 대조 러너 | `node tools/reconcile_receipts_evidence.mjs` | **64/64 checks PASS** (0.83s) | VB-MJS-04 조치 상태 완결 유지 |
| Frontend 단위/프로토콜 시험 | `npm --prefix apps/web test -- --run` | **31 파일 300 passed** (3.62s) | 회귀 0건 |
| 문서 및 온톨로지 무결성 | `check_docs.py` / `check_ontology.py` | **PASS / PASS** | 545개 문서, SHACL 무결 |

---

## 4. 결론 및 다음 행동

- Codex의 감사 지적 `VB-LAUNCH-01`이 완전 조치되었으며, 음성 대조군 5종이 `tests/test_deploy_intranet_preflight.py`에 영구 안착되었습니다.
- 이전 세션의 `VB-MJS-03`, `VB-MJS-04`, `VB-MJS-05` 조치와 결합되어, Gemini 영역의 모든 검증 러너 및 배포 런처의 종료가드·다이제스트 결속·정직한 스코프 표기가 완결되었습니다.
- 다음 단계: 사용자 승인에 따라 잔여 제어 평면 UI 미노출 라우트 연동(Storage Contributions/Locations, Pool Capacity/Placement-Preview, Node Liveness/Heartbeat, Discovery Candidates)을 지속 진행합니다.
