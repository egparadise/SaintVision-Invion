---
doc_id: "HIST-GEMINI-CARD162-001"
title: "History: Card 162 S02-FE 사내 포털 로그인 여정 관측 하네스 구축 및 증거 생성"
version: "1.0.0"
status: "review"
author: "Gemini"
updated: "2026-09-30T15:40:00+09:00"
source_of_truth: "Git"
---

# History: Card 162 S02-FE 사내 포털 로그인 여정 관측 하네스 구축 및 증거 생성

## 1. 개요 및 배경

- **카드 번호**: Card 162 (Owner: Gemini, Reviewers: Claude, Codex)
- **작업 브랜치**: `agent/gemini/c162-fe-login-journey-harness` (Base: `origin/integration/all-agents-unified` `6fc0428b` 위에 Card 153 `2f93cbba` 결합)
- **배경**:
  - 진척 재산정(Card 161, PR #258)에서 "S02-FE는 #247 로그인이 구현됐어도 이름이 해석되지 않아 여정 관측이 부재하다"고 판정됨.
  - 사내망 환경(`portal.sv.lan`)에서 hosts 파일 미반영, DNS 미해석, 또는 포털 컨테이너 미기동 시 크래시나 우회 꼼수 없이 정직하게 외부 차단(`BLOCKED_EXTERNAL`)으로 기록하고, 정상 환경에서는 전체 5단계 로그인 여정을 관측하여 엄격한 무결성 증거(Evidence JSON)를 산출하는 정식 관측 하네스가 요구됨.
- **목적**:
  1. `apps/web`의 Playwright/브라우저 시험 방식을 준수하여 `https://portal.sv.lan` 대상의 5단계 로그인 여정 관측 도구(`tools/observe_portal_login_journey.py`) 구축.
  2. 사전 검사(Preflight)를 통한 정직한 `BLOCKED_EXTERNAL` 기록: DNS 미해석 또는 TCP 443 포트 거부 시 외부에 의한 차단임을 명확히 기록.
  3. 우회 플래그(`--host-resolver-rules`, `--ignore-certificate-errors`, `ignoreHTTPSErrors`) 전면 금지 및 감지 시 즉각 fail-closed 차단(`SecurityCircumventionError`, exit 2).
  4. 엄격한 비식별화(Redaction) 보증: 토큰(JWT, Bearer, code_verifier, code) 0건, IP 주소 0건, 자격증명/비밀값 0건 엄격 검증 및 스키마 enum `[0]` 강제.
  5. 엄격 JSON 스키마(`tools/portal-login-journey-evidence.schema.json`) 및 자동화 단위 시험 스위트(`tests/test_portal_login_journey_harness.py`, 16 passed) 완비.

---

## 2. 5대 핵심 설계 및 불변식

### 1) 5단계 로그인 여정 파이프라인
하네스는 다음 5개 단계를 순차적으로 관측하고 기록합니다:
1. `portal_tls_reachability`: 사내 CA 번들을 통한 `https://portal.sv.lan/` TLS 정상 접속 및 보안 헤더(HSTS, CSP 등) 검증.
2. `login_initiation`: 로그인 화면에서 "조직 계정으로 로그인" 클릭, `sessionStorage`에 PKCE 트랜잭션(`code_challenge` S256, `state`, `nonce`, `code_verifier`) 저장 및 IdP 인가 엔드포인트 이동 관측.
3. `pkce_callback`: IdP로부터 전달된 인가 코드를 `/callback?code=...&state=...`에서 수신, IdP 토큰 엔드포인트(`/protocol/openid-connect/token`)와 코드 교환, ID 토큰 claims 검증 및 클라이언트 정리 후 `/studio` 이동.
4. `identity_session_display`: 인증 완료 후 UI 마운트, Header의 사용자 신원(이름, 역할 배지) 및 제어 평면 `/v1/session` 조회 결과 표시 관측.
5. `logout`: Header "로그아웃" 클릭, 세션 만료 타이머/인메모리 토큰/세션스토리지 무결 청소, IdP 로그아웃 트리거 및 로그인 화면 복귀 관측.

### 2) 정직한 사전 점검 및 `BLOCKED_EXTERNAL` 기록 (No Bypass)
- 임의의 DNS 스푸핑이나 호스트 우회 없이 표준 OS DNS 조회(`socket.getaddrinfo`)를 수행.
- 호스트명 해석 실패(`socket.gaierror`) 시:
  - 1단계 `portal_tls_reachability`를 즉시 `BLOCKED_EXTERNAL`로 기록 (`blockingReason`: "DNS resolution failed for portal.sv.lan").
  - 이후 2~5단계 역시 종속 단계 차단(`BLOCKED_EXTERNAL`)으로 기록하고 전체 상태를 `BLOCKED_EXTERNAL`로 정직하게 출력.
- TCP 포트 443 연결 실패(`ConnectionRefusedError`, 타임아웃) 시:
  - 포털 서비스 미기동 상태로 판정하여 `BLOCKED_EXTERNAL` 기록.
- **우회 플래그 원천 차단**: `--host-resolver-rules`, `--ignore-certificate-errors`, `ignoreHTTPSErrors` 등 인위적 우회 시도가 포착되면 즉시 `SecurityCircumventionError`를 발생시키고 exit code 2로 fail-closed 종료.

### 3) 0-Token / 0-IP / 0-Credential 비식별화(Redaction) 보증
- `RedactionSanitizer`를 통해 모든 관측 데이터, URL, 상세 메시지를 사전 정제:
  - JWT 패턴: `eyJ...` -> `[REDACTED_JWT]`
  - Bearer 헤더: `Bearer ...` -> `Bearer [REDACTED_TOKEN]`
  - 민감 매개변수: `code_verifier=...`, `code=...`, `password=...`, `client_secret=...` -> `[REDACTED_SECRET]`
  - IP 주소: IPv4 / IPv6 주소 패턴 -> `[REDACTED_IP]` (URL 내 호스트의 경우 RFC 3986 URI 유효성을 유지하기 위해 `redacted-host.sv.lan`으로 정규화)
  - 딕셔너리 키 검사: `password`, `client_secret`, `secret`, `access_token`, `id_token` 등 민감 키의 값은 `[REDACTED_CREDENTIAL]`로 치환.
- **이중 감사(Audit) 가드**:
  - Evidence 생성 전 정제된 전체 객체를 재스캔하여 잔여 민감 데이터 개수를 실측:
    `tokenCount == 0`, `ipCount == 0`, `credentialCount == 0`
  - 단 1건이라도 유출 패턴이 검출되면 `RuntimeError`를 발생시켜 증거 파일 생성을 원천 차단.
  - JSON 스키마에서도 audit 속성의 각 count를 `{"type": "integer", "enum": [0]}`으로 정의하여 0이 아닌 값은 스키마 검증에서 거부됨.

---

## 3. 산출물 및 구현 파일

1. **`tools/observe_portal_login_journey.py`**:
   - 사내 포털 로그인 여정 관측 CLI 및 라이브러리.
   - 옵션: `--target-url`, `--idp-url`, `--ca-bundle`, `--output-evidence`, `--mock-mode`, `--timeout`.
   - 사전 점검, 실 브라우저 실행(Playwright), 모의 모드(Mock Mode), 비식별화 정제기, 스키마 검증기 탑재.
2. **`tools/portal-login-journey-evidence.schema.json`**:
   - `additionalProperties: false` 엄격 JSON 스키마.
   - 5개 필수 단계 정의, `overallStatus`(`PASS`, `FAIL`, `BLOCKED_EXTERNAL`), `audit` 섹션의 `[0]` 열거형 강제.
3. **`tests/test_portal_login_journey_harness.py`**:
   - 16개 자동화 단위 및 통합 행동 검증 시험 (Mock 모드, 사전 점검 DNS 차단, 포트 거부, 6종 우회 플래그 거부, CLI 2종 거부, Redaction 누출 검출, 스키마 부정 시험, 파일 저장 등).
4. **`docs/vault/30_Development/Evidence/s02_fe_login_journey_evidence.json`**:
   - 실제 사내망 도메인(`https://portal.sv.lan`)을 대상으로 관측 하네스를 구동하여 생성한 정식 Evidence 파일.
   - 현재 노드 환경의 미해석 상태를 정직하게 반영한 `BLOCKED_EXTERNAL` 실측 증거 (토큰 0건, IP 0건, 자격증명 0건).

---

## 4. 정량 검증 결과

1. **로그인 여정 관측 하네스 자동화 시험 (`pytest tests/test_portal_login_journey_harness.py`)**:
   - **16 passed in 3.57s (100%)**:
     - `test_schema_file_exists_and_is_valid_draft`: 스키마 정합성 검증 PASS
     - `test_unresolved_domain_honestly_reports_blocked_external`: 미해석 도메인 정직한 `BLOCKED_EXTERNAL` 기록 PASS
     - `test_closed_tcp_port_honestly_reports_blocked_external`: 포트 미개방 정직한 `BLOCKED_EXTERNAL` 기록 PASS
     - `test_circumvention_flags_fail_closed_in_observer`: 6종 우회 플래그 fail-closed 거부 PASS
     - `test_cli_rejects_circumvention_flags_with_exit_code_2`: CLI 우회 시도 exit code 2 종료 PASS
     - `test_redaction_sanitizer_eradicates_all_tokens_ips_and_secrets`: 민감 데이터 전수 비식별화 PASS
     - `test_audit_detects_unredacted_leaks`: 미정제 데이터 누출 감사 검출 PASS
     - `test_mock_journey_produces_fully_passing_valid_evidence`: 5단계 Mock 모드 전수 PASS 및 스키마 검증 PASS
     - `test_schema_enforces_zero_token_and_ip_counts`: 스키마 non-zero 및 미지 필드 거부 PASS
     - `test_cli_execution_with_output_file`: CLI 파일 저장 및 유효성 PASS
2. **화면-백엔드 라우트 커버리지 및 무결성 시험 (`pytest tests/test_route_coverage.py`)**: **40 passed 100% (2.26s)**.
3. **프런트엔드 소스 무결성 점검 (`python -X utf8 tools/check_frontend_integrity.py`)**: 92개 파일 스캔, 9대 규칙 위반 **0건 (exit 0)**.
4. **계약 바인딩 점검 (`python tools/check_contract_bindings.py`)**: 55개 픽스처 전수 커버리지, 14개 리플레이 가드 **PASS (exit 0)**.
5. **문서 정합성 및 인덱스 게이트 (`python tools/check_docs.py`)**: 1036개 문서, 48개 태스크, 12개 결과 **PASS (exit 0)**.
6. **단일 출처 검사 (`python tools/check_doc_single_source.py --ratchet`)**: 19쌍 baseline 일치 **PASS (exit 0)**.
7. **인용 ratchet 점검 (`python tools/check_doc_path_citations.py --ratchet --base-ref origin/integration/all-agents-unified`)**: 290개 baseline 일치 **PASS (exit 0)**.
8. **Git 차분 포맷 점검 (`git diff --check`)**: 포맷 경고 **0건 (exit 0)**.

---

## 5. 인계 및 검토 요청

- **상태**: 구현 및 정량 검증 완료, PR 생성 및 독립 검토 준비 완료.
- **검토 요청**:
  - Claude 검토 (UI·운영 축): Playwright 브라우저 관측 여정 흐름 및 `BLOCKED_EXTERNAL` 정직 표기 검증.
  - Codex 검토 (계약·보안 축): Anti-circumvention fail-closed 정책, zero-token/zero-ip Redaction 무결성 및 엄격 JSON 스키마 계약 검증.
