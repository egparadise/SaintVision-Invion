# 2026-09-19 00:35:00 KST 인트라넷 사전 배포 파이프라인 외부 TLS 인증서 주입 및 회귀 검증보고

## 1. 개요
- **목적**: 공개 저장소 전환에 따른 개발 TLS 인증서 외부 주입 아키텍처 전환 수용. `tools/deploy_intranet.ps1`의 환경변수(`SAINTVISION_DEV_CERT_DIR`) 기반 동적 경로 탐색, 미지정 시 `deploy/certs` 클린 폴백, 비어있지 않은 파일 존재 및 Leaf 타입 검증, `tools/verify_tls_cert_pair.py`를 통한 인증서-개인키 암호학적 공개키 쌍 검증, 사전 점검 요약 테이블의 실제 대상 경로 명시, 그리고 `tests/test_deploy_intranet_preflight.py`에 3종의 전용 회귀 시험을 추가하여 총 17개 시험 완결.
- **담당 Agent**: Gemini (Frontend & Intranet Web Delivery Owner)
- **대상 브랜치**: `integration/all-agents-unified`
- **검증 환경**: Windows 11, PowerShell, Node.js v22.14.0, Python 3.14.6 (.venv, cryptography 50.0.1), Vitest v3.2.7, Pytest v9.1.1

---

## 2. 세부 구현 및 정합 내역

### A. 환경변수 기반 인증서 경로 탐색 및 안전한 폴백 (`tools/deploy_intranet.ps1`)
- **경로 결정**:
  ```powershell
  $certDir = if ([string]::IsNullOrWhiteSpace($env:SAINTVISION_DEV_CERT_DIR)) { "deploy/certs" } else { $env:SAINTVISION_DEV_CERT_DIR }
  Write-Host " Certificate target directory: $certDir" -ForegroundColor DarkGray
  $certFile = Join-Path $certDir "saintvision.crt"
  $keyFile = Join-Path $certDir "saintvision.key"
  ```
- **기존 환경 보존**: `SAINTVISION_DEV_CERT_DIR`가 설정되지 않거나 공백일 경우 기존 `deploy/certs`로 투명하게 폴백하여 기존 개발 환경이 즉시 깨지지 않음.

### B. stale 디렉터리 청소 및 파일 존재/크기/Leaf 타입 검사
- Docker 볼륨 바인드 마운트 실패 등으로 인해 타깃 경로에 생성될 수 있는 stale 디렉터리(`PathType Container`)를 선제적으로 감지하여 제거(`Remove-Item -LiteralPath $tlsPath -Recurse -Force`).
- 대상 경로의 `saintvision.crt` 및 `saintvision.key`에 대해 `Test-Path -LiteralPath ... -PathType Leaf` 검사를 동일하게 적용.
- 파일 부재 또는 0바이트 크기 감지 시 `tools/generate_tls_cert.py --output-dir $certDir`를 호출하여 지정된 디렉터리에 신규 생성.

### C. 암호학적 공개키 쌍 정합성 검증 연동
- Step 1 검증 단계에 `tools/verify_tls_cert_pair.py --certificate $certFile --private-key $keyFile`를 연동.
- 인증서의 공개키(`SubjectPublicKeyInfo`)와 개인키의 공개키가 암호학적으로 일치하지 않거나 PEM 파싱에 실패할 경우 즉시 exit 1로 파이프라인 중단.

### D. 사전 점검 요약 테이블의 정직한 경로 표면화
- 사전 점검 요약 테이블의 Step 1 행에서 `$certFile`과 `$keyFile` 변수를 동적으로 참조하여, 외부 주입 경로 사용 시 외부 경로를, 미지정 시 `deploy/certs` 경로를 정확하게 출력:
  ```powershell
  Write-Host " [1/5] TLS Certificate Files:       PRESENT & NON-EMPTY ($($certFile): $($certItem.Length)B, $($keyFile): $($keyItem.Length)B; cryptographic validity & TLS negotiation unverified)" -ForegroundColor Green
  ```
- 기존 스코프 경계(`Scope Assurance Boundary`) 정의를 충실히 보존하여, 로컬 디스크 상의 파일 존재 및 키 페어 일치 검증이 브라우저 간 실시간 TLS 1.3 협상이나 CA 신뢰 체인 검증을 보증하는 것이 아님을 명시.

---

## 3. 신규 영구 회귀 시험 (`tests/test_deploy_intranet_preflight.py`)

기존 14개 테스트에 더해 다음 3개 회귀 시험을 신설하여 총 17개 시험으로 확장:

1. **`test_default_certificate_fallback_when_env_unset`**:
   - `SAINTVISION_DEV_CERT_DIR`가 공백(`""`)으로 전달되었을 때 `deploy/certs` 디렉터리로 정상 폴백하는지 검증.
   - `deploy/certs/saintvision.crt` 및 `key`가 생성되고 콘솔 출력에 `deploy/certs`가 명시되는지 실측.
2. **`test_external_certificate_directory_summary_reporting`**:
   - `SAINTVISION_DEV_CERT_DIR`에 외부 경로(`injected_ext_certs`)가 지정되었을 때, 사전 점검 요약 테이블의 `[1/5] TLS Certificate Files:` 라인이 외부 경로를 정확히 표기하고 `deploy/certs`를 표기하지 않음을 검증.
   - 기본 경로 `deploy/certs`가 전혀 생성되지 않음을 단언.
3. **`test_external_cert_directory_collisions_are_removed_before_generation`**:
   - 외부 지정 디렉터리 내에 stale 디렉터리가 미리 존재할 때, 이를 안전하게 제거하고 파일 형태로 인증서가 재발급되는지 검증.

---

## 4. 검증 결과 및 증거 (Actual Verification Evidence)

1. **사전 배포 파이프라인 회귀 시험 (Pytest)**:
   - 명령: `.venv\Scripts\pytest.exe tests/test_deploy_intranet_preflight.py`
   - 결과: **17 passed in 21.33s** (100% 무오류 통과)
2. **자격증명 및 배포 설정 회귀 시험 (Pytest)**:
   - 명령: `.venv\Scripts\pytest.exe tests/core/test_deployment_credentials.py`
   - 결과: **13 passed in 5.35s** (100% 무오류 통과)
3. **스모크 경계 단위 시험 (Pytest)**:
   - 명령: `.venv\Scripts\pytest.exe tests/test_browser_smoke_boundary.py tests/integration/test_browser_smoke_integration.py`
   - 결과: **3 passed, 1 skipped in 4.21s** (격리 옵트인 레인 준수)
4. **프론트엔드 전체 스위트 (Vitest)**:
   - 명령: `npm --prefix apps/web test -- --run`
   - 결과: **31 passed (31 files), 307 passed (307 tests)**
5. **문서 및 온톨로지 무결성 검증**:
   - 명령: `.venv\Scripts\python.exe tools/check_docs.py`
   - 결과: `PASS: 24 original hashes, 565 versioned documents, wiki links, 48 tasks, 12 outcomes, owner/reviewer/skills, dependency DAG.`
   - 명령: `.venv\Scripts\python.exe tools/check_ontology.py`
   - 결과: `PASS: RDF parsing, defined terms, TTL/JSON-LD equivalence, 48 task mappings, positive SHACL, 4 rejected invalid fixtures, 4 competency queries, Obsidian mirrors.`

---

## 5. 보안 및 거버넌스 준수
- `deploy/certs/saintvision.key` 및 `.crt` 파일은 아직 삭제하지 않았으며, `.gitignore`에도 추가하지 않음 (사용자 승인 대기).
- 개인키 본문이나 민감한 자격증명 값은 본 문서, 로그, 커밋 메시지 어디에도 노출하지 않고 파일 경로와 상태 특성(크기, 모드)만 취급함.
