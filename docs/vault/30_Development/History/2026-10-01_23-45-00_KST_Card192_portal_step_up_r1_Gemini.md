# 2026-10-01 23:45:00 KST — Card 192: Portal Step-Up 재인증 OIDC PKCE 결속 r1 조치 (Gemini)

- **문서 ID**: `HIST-GEMINI-CARD192-STEP-UP-R1`
- **작업 branch**: `agent/gemini/c192-portal-step-up`
- **Base commit**: `c41fe2da6b08d4b3eb0b213b29c9df4f71a06716` (Train 10 후보 `coord/train10-ci-2245` 머지 완료 `b6b69648`)
- **KST 시각**: 2026-10-01 23:45:00 KST
- **작업자**: Gemini (Frontend / UI / 웹 배포)
- **독립 검토자 요청**: Codex (보안 계약/서명 검증/무저장 불변식 축), Claude (UI/리다이렉트 경계/원자적 커밋 축)
- **상태**: proposed (검토 전 자가 승인 금지)

---

## 1. r1 리뷰 지적사항 및 조치 대조표

Codex Security (F-R1~F-R4, 22:53) 및 Claude UI (S1~S6, 22:42)의 r1 리뷰 지적사항 10건에 대해 전수 조치 및 단위/변이 시험 사살을 완료하였습니다.

| 번호 | 리뷰어 | 구분 / 등급 | 지적 내용 | 조치 내용 및 사살 증거 |
|---|---|---|---|---|
| **F-R1** | Codex | High / Security | `session.ts:526-567`에서 ID 토큰 서명 미검증(payload 디코드만 수행, mock-signature 허용). 변조 서명, unknown kid, alg 완화 거부 필요 | Web Crypto `crypto.subtle.verify` 기반 `verifyIdTokenSignature()` 구현. RS256/ES256 엄격 검증, 서명 1글자 변조 거절, JWKS에 없는 kid 거절, `none`/`HS256` 완화 시도 즉시 거절 사살 (M7, M8 사살) |
| **F-R2** | Codex | High / Security | `beginStepUp`이 `previousToken`을 `sessionStorage`에 직렬화. Codex 보안 결정 선택지 (b) 적용 요구 (Web Storage 토큰 0건 불변식) | `Transaction` 인터페이스 및 `beginStepUp`에서 `previousToken` 완전 제거. `sessionStorage`에 토큰/비밀/Bearer 문자열 0건 잔류 불변식 강제 (M9 사살). `sanitizeReturnUrl`로 오픈 리다이렉트 원천 차단 |
| **F-R3** | Codex | High / Security | 토큰 엔드포인트 교환 전 step-up 트랜잭션 마커 검증 부재. 일반/Step-Up 교차 호출 차단 필요 | `completeStepUp()`은 `tx.isStepUp === true`가 아니면 네트워크 호출 전 즉시 fail-closed 거부. `completeLogin()`은 step-up 트랜잭션 진입 시 즉시 거부 (M6 사살). `Login.tsx`에서 `isStepUpPending()` 분기 |
| **F-R4** | Codex | Medium / Security | Step-up authorize 요청 시 `openid` 스코프 누락 가능성. fail-closed 강제 필요 | `beginStepUp()` 진입 시 `config.scope.split(/\s+/).includes('openid')` 검사, 누락 시 네트워크/저장소 조작 전 즉시 fail-closed 예외 발생 (M5 사살) |
| **S1** | Claude | Blocker / Security | `sessionStorage`에 bearer 토큰 저장 금지 (선택지 b 적용 요구) | `Transaction.previousToken` 완전 제거, `sessionStorage`에 토큰/비밀 문자열 0건 불변식 강제 (M9 사살), same-origin `returnUrl`만 허용 |
| **S2** | Claude | Major / Boundary | 브라우저 리다이렉트 시 메모리 토큰 휘발 모사 누락 | 콜백 시험 전 `clearAuthToken()` 및 `clearSessionExpiration()`을 호출하여 실제 페이지 언로드/리다이렉트 경계를 충실히 모사 |
| **S3** | Claude | Major / Lifecycle | 실패 시 숨은 토큰과 화면 불일치 방지 및 조기 `setAuthToken` 원자성 훼손 방지 | `completeStepUp` 및 `completeLogin` 내부의 조기 `setAuthToken` 제거. 결과 반환 후 호출자(`Login.tsx`) 컴포넌트 활성 수명주기 내에서 `commitSession(token, expiresAt)`으로 원자적 커밋, 실패 시 `clearAuthToken()` 수행 (M4 사살) |
| **S4** | Claude | Minor / Design | `IntranetDeploymentView.tsx`의 미정의 토큰 `var(--color-status-warning)` 사용 및 래칫 불변식 주의 | 정의된 상태 토큰 `var(--color-status-unknown)`으로 교체. 컨테이너 테두리는 `var(--color-border-strong)`을 적용하여 `borderSubtleCount === 141` 래칫 엄격 준수 (13/13 pass) |
| **S5** | Claude | Minor / UI & A11y | 문구 및 사용자 안내 개선 ("재인증 필요" 및 실패 동작 설명) | "릴리스 수락 전 재인증 필요" 문구 반영, 리다이렉트 전/후 실패 동작 설명 문구 반영 |
| **S6** | Claude | Minor / Doc | 오류 타입(`Error`) 일치, 함수 시그니처(`()`), 무저장/재인증 경계 문서화 | `ContractViolationError` 대신 `Error` 명시, 무인자 시그니처 `()`, 저장소 무저장(선택지 b) 불변식 충실 반영 |

---

## 2. 변이 시험 사살 실측 증거 (Kill Rate 100%)

전용 변이 검증 하네스(`scratch/test_c192_r1_mutations.py`)를 통해 지적된 9개 변이 전수를 사살하였습니다:

```text
Checking baseline...
Baseline passed (34 tests)
KILLED: M1: Extra parameter in beginStepUp
KILLED: M2: Reuse existing state in beginStepUp
KILLED: M3: Omit max_age from authorize params
KILLED: M4: Premature setAuthToken before /v1/session in completeStepUp
KILLED: M5: Omit openid scope requirement check
KILLED: M6: Remove pre-exchange isStepUp check in completeStepUp
KILLED: M7: Skip ID token signature verification in completeStepUp
KILLED: M8: Allow 'none' algorithm in verifyIdTokenSignature
KILLED: M9: Leak token into sessionStorage in beginStepUp

--- Summary ---
KILLED: M1: Extra parameter in beginStepUp
KILLED: M2: Reuse existing state in beginStepUp
KILLED: M3: Omit max_age from authorize params
KILLED: M4: Premature setAuthToken before /v1/session in completeStepUp
KILLED: M5: Omit openid scope requirement check
KILLED: M6: Remove pre-exchange isStepUp check in completeStepUp
KILLED: M7: Skip ID token signature verification in completeStepUp
KILLED: M8: Allow 'none' algorithm in verifyIdTokenSignature
KILLED: M9: Leak token into sessionStorage in beginStepUp

ALL 9 MUTATIONS KILLED! Kill rate: 100%
```

---

## 3. 정량 검증 게이트 실측 결과

| 검증 단계 | 명령 | 결과 | 상세 증거 |
|---|---|---|---|
| 단위/계약/UI 테스트 | `npx vitest run ... --maxWorkers=1` | **PASS (5/5 files, 119/119 tests)** | auth-step-up-contract(34), acc09-contrast(13), auth-step-up-ui(5), auth-oidc(50), auth-session(17) |
| TypeScript 컴파일 | `npx tsc -b` | **PASS (exit 0)** | 타입 에러 0건 |
| 프로덕션 번들 빌드 | `npm run build` | **PASS (exit 0)** | Vite v6.4.3 production bundle built in 10.18s |
| API 계약 스키마 검증 | `npm run contracts:check` | **PASS (exit 0)** | 41개 API 응답 스키마와 TypeScript 생성 타입 100% 일치 |
| 라우트/화면 불변식 | `pytest tests/test_route_coverage.py` | **PASS (41/41 passed)** | 라우트 커버리지 및 UI 불변식 100% 통과 |
| 프런트엔드 무결성 | `python tools/check_frontend_integrity.py` | **PASS (exit 0)** | 93개 소스 파일 9대 무결성 규칙 위반 0건 |
| 계약 바인딩 | `python tools/check_contract_bindings.py` | **PASS (exit 0)** | 55개 fixture 참조 확인, 20개 커널 응답 바인딩 게이트 통과 |
| 문서 정본 검증 | `python tools/check_docs.py` | **PASS (exit 0)** | 1076개 버전 문서, DAG 무결성 통과 |
| 문서 경로 인용 래칫 | `python tools/check_doc_path_citations.py --ratchet --base-ref c41fe2da` | **PASS (exit 0)** | 290개 기준 인용 유지, 신규 깨진 인용 0건 |
| 코드 스타일 및 공백 | `git diff --check` | **PASS (exit 0)** | 공백/줄바꿈 에러 0건 |

---

## 4. 정직한 경계 및 제약 사항

1. **라이브 IdP 관측 경계 (`BLOCKED_EXTERNAL`)**:
   - `idp.saintvision.lan:8443`는 사내 hosts 매핑 미적용 환경에서 외부 차단 상태(`BLOCKED_EXTERNAL`)로 유지됩니다.
   - 본 작업은 계약 스키마 및 암호학적 Web Crypto RS256/JWKS 스텁을 통한 클라이언트-측 엄격 검증을 완결하였으며 라이브 통신 성공을 위조하지 않았습니다.
2. **릴리스 수락 쓰기 라우트 비활성 (`INV_RELEASE_ACCEPTANCE_WRITE_ENABLED=false`)**:
   - 백엔드 쓰기 계약 미개방 상태를 준수하여 화면 UI는 재인증 유도 버튼 및 상태 배지만을 제공하며, 수락 등록 폼이나 변이 API 호출은 일절 포함하지 않았습니다.
3. **Web Storage 무저장 불변식 (Codex Security Decision b)**:
   - 브라우저 `sessionStorage`에는 비밀이 아닌 트랜잭션 복귀 상태(`state`, `nonce`, `verifier`, `createdAt`, `redirectUri`, `returnUrl`)만을 격리 저장하며, 어떤 토큰이나 Bearer 자격증명도 저장소에 잔류시키지 않습니다.
