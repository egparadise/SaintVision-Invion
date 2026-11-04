---
doc_id: "HIST-GEMINI-FE-ESLINT-20261028-001"
title: "2026-10-28 Frontend ESLint lane 정상화"
version: "1.0.0"
status: "implemented"
author: "Gemini"
updated: "2026-10-28T13:12:31+09:00"
source_of_truth: "Git"
tags: ["saintvision", "frontend", "eslint", "verification", "gemini"]
---

# 2026-10-28 Frontend ESLint lane 정상화

## 작업 Context와 경계

- branch: `agent/codex/c301-standalone-worker-modules`.
- base exact HEAD: `f2936ae5e91787b3dbba0d069a85ccaef020c984`.
- owner: Gemini. 독립 reviewer: Claude. 계약/통합 reviewer: Codex.
- 범위: `apps/web`의 package manifest·lockfile·flat lint config와 lint가 직접 지적한 최소 제품 소스 수정.
- 비범위: 공통 진행판, registry, backend, contracts, `.github` workflow. 상태 승격·독립 검토·CI·실브라우저/운영 인수는 수행하지 않았다.

## 버전 선택 근거

- npm registry 실측 최신 조합: `eslint@10.13.0`, `@eslint/js@10.0.1`, `typescript-eslint@8.72.1`, `globals@17.13.0`.
- ESLint 10.13.0 Node engine은 `^20.19.0 || ^22.13.0 || >=24`이다. Frontend hosted workflow의 `setup-node`는 major `22`를 사용하며 최신 22.x는 이 하한을 충족한다. 로컬 실행은 Node.js `v24.10.0`이었다.
- `typescript-eslint@8.72.1`의 peer 범위는 ESLint `^8.57.0 || ^9.0.0 || ^10.0.0`, TypeScript `>=4.8.4 <6.1.0`으로 현재 TypeScript 5.7과 호환된다.
- ESLint 9+의 기본 구성 형식과 typescript-eslint 공식 quickstart에 맞춰 `eslint.config.js` flat config를 사용했다.
- 근거: [ESLint npm metadata](https://www.npmjs.com/package/eslint), [ESLint flat config migration](https://eslint.org/docs/latest/use/configure/migration-guide), [typescript-eslint Getting Started](https://typescript-eslint.io/getting-started/).

## exact 변경 11경로

1. `apps/web/package.json`
2. `apps/web/package-lock.json`
3. `apps/web/eslint.config.js`
4. `apps/web/src/features/admin/AdminSecurityConsole.tsx`
5. `apps/web/src/features/auth/session.ts`
6. `apps/web/src/features/evidence/EvidenceViewer.tsx`
7. `apps/web/src/features/runs/RunDetail.tsx`
8. `apps/web/src/features/studio/DeveloperStudio.tsx`
9. `apps/web/src/shared/api/client.ts`
10. `apps/web/src/shared/realtime/sse-client.ts`
11. `apps/web/src/shared/realtime/ws-terminal.ts`

## 구현

- 네 lint package를 exact dev dependency로 고정하고 lockfile을 갱신했다.
- `eslint.config.js`에 JS·TypeScript 권장 규칙, browser/Node/service-worker globals, `dist`·`coverage` ignore를 구성했다.
- `npm run lint`를 `eslint . --max-warnings 0`으로 강화해 warning도 lane 실패로 처리한다.
- 테스트는 정적 소스 문자열·mutation fixture 때문에 의도적으로 미사용 import/변수와 `@ts-ignore`를 포함한다. 해당 완화는 `tests/**/*.{ts,tsx}` override에만 격리했다.
- G-07 평가 러너는 source blob OID를 Evidence에 봉인한다. `agentEngine.ts`와 `evalRunner.ts`의 lint-only 변경으로 focused test 1건이 drift를 탐지했으므로 두 파일을 원복하고 해당 파일에만 `prefer-const`, `preserve-caught-error`, CommonJS import 규칙 예외를 두어 기존 provenance를 보존했다.
- 제품 소스 최소 수정:
  - `AdminSecurityConsole`: cache 유지/폐기 분기를 동일 의미의 boolean 식으로 정리.
  - OIDC session과 EvidenceViewer: 모든 분기에서 즉시 덮어쓰던 불필요 초기 할당 제거.
  - RunDetail·SSE·terminal WS: 사용하지 않는 catch binding 제거.
  - DeveloperStudio: optional chain 뒤 non-null assertion을 기존 truthiness 의미를 보존하는 `|| ... || ''` fallback으로 교체. Codex F1에서 빈 문자열일 때 `??`가 artifact fallback을 건너뛰는 의미 변경을 찾아 즉시 정정했다.
  - API client: ESLint 10에서 불필요해진 `no-var` disable 주석 제거.

## 실행과 직접 관측 결과

| 명령/단계 | exit | 결과 |
|---|---:|---|
| `npm view eslint@latest ...`, `npm view typescript-eslint@latest ...`, `npm view @eslint/js@latest ...`, `npm view globals@latest ...` | 0 | 최신 version, Node engine, peer dependency 직접 확인. |
| `npm install --save-dev --save-exact eslint@10.13.0 @eslint/js@10.0.1 typescript-eslint@8.72.1 globals@17.13.0` | 0 | 138 packages 추가. 전체 dev audit 경고 6건. |
| 최초 `npm run lint` | 1 | 110 problems: 108 errors, 2 warnings. |
| 제품 최소 수정 후 `npm run lint` | 0 | 오류 0, 경고 0. |
| focused Vitest 13 files 최초 실행 | 1 | 12 files pass, 1 fail; 161 pass, 1 fail. G-07 source blob drift가 원인. |
| G-07 원복 후 focused Vitest 13 files | 0 | 13 files, 162 tests 전부 통과. |
| `npm ci` | 0 | lockfile 기반 265 packages 설치. |
| `npm run lint` after clean `npm ci` | 0 | `--max-warnings 0`, 오류·경고 0. |
| `tsc -b apps/web/tsconfig.json` | 0 | TypeScript 오류 0. |
| `npm run build` | 0 | Vite 108 modules. main JS 1,036.27 kB chunk warning은 유지. |
| full `npm test` | 0 | 99 files, 1,157 tests 전부 통과. localhost:3000 연결 거절 로그는 실제 API 미기동이며 실 API 인수 증거가 아니다. |
| Codex F1 정정 후 DeveloperStudio focused Vitest | 0 | 4 files, 37 tests 전부 통과. 빈 `stateUpdatedAt`에서 artifact 시각으로 fallback하는 기존 truthiness 의미 보존. |
| Codex F1 정정 후 full `npm test` 재실행 | 0 | 99 files, 1,157 tests 전부 통과. |
| Codex F1 정정 후 `npm run lint` / `tsc -b apps/web/tsconfig.json` | 0 / 0 | warning 0, TypeScript 오류 0. |
| `PYTHONUTF8=1 python tools/check_frontend_integrity.py` | 0 | 93 production files, 9 rules, 0 violations. |
| `npm run contracts:check` | 0 | 41 API response types PASS. |
| `PYTHONUTF8=1 python -m pytest tests/test_route_coverage.py -q` | 0 | 41 passed. |
| `npm audit --omit=dev` | 0 | production dependency vulnerabilities 0. |
| `npm audit --json` | 1 | dev-only 총 6건: 3 moderate, 3 high. Vitest/Vite/happy-dom 및 전이 패키지. |
| `npm ls eslint @eslint/js typescript-eslint globals --depth=0` | 0 | 의도한 exact 네 버전 설치 확인. |
| `git diff --check` | 0 | whitespace 오류 0. |

## audit와 CI 잔여 경계

- 전체 audit 6건은 dev-tool chain에만 있고 production audit은 0이다. Vitest 4.1.12 patch, happy-dom 21.0.4 major, Vite의 현 major 바깥 수정 등이 제시되지만 lint 복구 범위를 dependency security migration으로 확대하거나 `audit fix --force`를 실행하지 않았다.
- `.github/workflows/frontend.yml`은 현재 `npm ci`, Vitest, contract check, build만 실행하며 lint step은 없다. 이번 수정 허용 경로가 `apps/web`로 한정됐으므로 workflow를 임의 변경하지 않았다. CI owner가 `npm run lint` step을 추가하고 동일 SHA hosted 결과를 연결해야 한다.
- build의 1,000 kB 초과 chunk warning은 lint lane 실패가 아니며 별도 code-splitting 카드 후보다.

## 인계

- 작업한 것: 로컬과 clean `npm ci` 환경에서 재현 가능한 warning-zero ESLint lane을 만들었다.
- 확인한 것: 기존 집중/전체 시험, 타입, build, 계약, 화면-라우트, Frontend integrity가 모두 유지됐다.
- 다음 첫 행동: CI owner가 Frontend workflow에 lint step을 배선하고 동일 SHA hosted 결과를 확인한다. dependency owner는 dev audit 6건을 별도 카드에서 patch/major 영향과 함께 처리한다.
- 다음 담당: Codex(CI/통합), Claude(독립 리뷰), Gemini(후속 Frontend 수정).
