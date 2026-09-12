---
doc_id: "HISTORY-20260912-200500-GEMINI"
title: "Gemini Nginx Reverse Proxy 정본 Workspace WebSocket 프록시 강화 검증보고"
version: "1.0.0"
status: "review"
author: "Gemini"
created: "2026-09-12T20:05:00+09:00"
updated: "2026-09-12T20:05:00+09:00"
source_of_truth: "Git"
---

# Gemini Nginx Reverse Proxy 정본 Workspace WebSocket 프록시 강화 검증보고

- **작업 일시**: 2026-09-12 20:05:00 KST
- **작업자**: Gemini (Antigravity)
- **독립 검토자**: Claude (인증·보안 경계는 Codex)
- **작업 브랜치**: `integration/all-agents-unified`
- **대상 작업 카드**: `GM-03`, `GM-06` (부모 Task: `S06-FE`, `S08-FE`, `S11-FE`, `S12-FE`)

---

## 1. 작업 배경 및 목적

1. **내부망 Nginx 단일 Origin 리버스 프록시 WebSocket 업그레이드 누락 방지**:
   - `src/saintvision/server.py`에 등록된 정본 터미널 웹소켓 엔드포인트는 `@app.websocket("/v1/workspaces/{workspace_id}/terminals/{session_id}")` 형태입니다.
   - 기존 `apps/web/nginx.conf`의 고정 접두사 `location /v1/workspaces/terminals`는 중간에 `{workspace_id}` 세그먼트가 포함된 정본 URL 패턴을 매칭하지 못하고 일반 REST `location /v1/`로 폴백되어, `Upgrade` 및 `Connection` 헤더 누락으로 인해 WebSocket 핸드셰이크가 실패할 잠재 위험이 있었습니다.
2. **Nginx 정규식 위치 블록 및 배포 엔진 규칙 완결 (ADR-038)**:
   - `apps/web/nginx.conf` 및 `deploymentEngine.ts`에 `location ~ ^/v1/workspaces/[^/]+/terminals/` 정규식 라우팅 규칙을 추가하여, 임의의 `workspace_id`와 `session_id`를 가진 PTY WebSocket 연결이 Nginx 단일 오리진을 통과할 때 정확하게 HTTP/1.1 Upgrade 헤더와 3600s/86400s 타임아웃을 보장받도록 프록시 구성을 강화했습니다.

---

## 2. 세부 구현 내역

- **`apps/web/nginx.conf`**:
  - `location ~ ^/v1/workspaces/[^/]+/terminals/` 블록 추가: `proxy_http_version 1.1`, `Upgrade $http_upgrade`, `Connection "Upgrade"`, `proxy_read_timeout 3600s` 명시.
  - 레거시 호환용 `location /v1/workspaces/terminals`도 함께 유지.
- **`apps/web/src/features/deployment/deploymentEngine.ts`**:
  - `nginxRules`에 `/v1/workspaces/{id}/terminals/{sessionId}` 규칙 추가.
  - `generateNginxConfig()`에 `location ~ ^/v1/workspaces/[^/]+/terminals/` 블록 추가.
- **`apps/web/tests/intranet-deployment.test.ts`**:
  - 정본 워크스페이스 터미널 웹소켓 라우팅 규칙 및 생성된 `nginx.conf` 내 정규식 블록 검증 어설션 추가.
  - Vitest 테스트 스위트: **19개 파일 115개 테스트 100% 통과**.
- **Route Coverage 재실측**:
  - `tools/route_coverage.py`: 클라이언트 요청 34개 경로 중 미제공 0개 (**70 routes 제공, 0 unserved, 100% 커버리지**).

---

## 3. 검증 결과 실측 기록 (Zero-Mock Conformance)

| 검증 항목 | 실행 명령 | 결과 / 증거 | 상태 |
|---|---|---|---|
| Vitest 단위 테스트 | `npm --prefix apps/web test -- --run` | 19개 파일 115개 테스트 통과 (2.67s) | **PASS (100%)** |
| Vite 프로덕션 빌드 | `npm --prefix apps/web run build` | dist 번들 클린 생성 (0 error, 0 warning, 5.29s) | **PASS (100%)** |
| E2E 브라우저 스모크 | `node tools/run_browser_smoke.mjs` | 14개 트랙 174/174 검사 통과 (100%) | **PASS (100%)** |
| 2-PC 분산 실행 검증 | `node tools/verify_two_pc_distributed_execution.mjs` | 5개 협동 단계 67/67 검사 통과 (100%) | **PASS (100%)** |
| API 라우트 커버리지 | `python tools/route_coverage.py --served src/saintvision --client apps/web/src` | 70 routes 제공, 34 paths 요청, **0 unserved** | **PASS (100%)** |
| 내부망 배포 사전점검 | `powershell -File tools/deploy_intranet.ps1` | 5/5 전 배포 파이프라인 무오류 통과, Gateway Healthy | **PASS (100%)** |
| 거버넌스 문서 검사 | `python tools/check_docs.py` | 264개 버전 문서, 48개 태스크, 12개 outcome 무오류 | **PASS (100%)** |
| 온톨로지 지식그래프 | `.venv\Scripts\python.exe tools/check_ontology.py` | 48개 태스크 매핑, SHACL 검사, 4개 질의 통과 | **PASS (100%)** |

---

## 4. 진척도 및 인계 상태

1. **진척도 (AUDIT-DEVELOPMENT-20260911 기준 투명 산정)**:
   - **총점**: 48개 태스크 × 100점 = 4,800점.
   - **Codex 공통 기준선 (독립 승인 및 실장비 미인수 기준)**: **57.81%** (2,775 / 4,800점) (약 58% 또는 약 55%).
   - **Gemini 프론트엔드 영역 구현 성숙도**: **75.0%** (900 / 1,200점, `S01-FE` ~ `S12-FE` 전 12개 태스크 최고 구현 상태 도달, review 대기).
   - **Claude 독립 검토 통과 및 통합 승인 시 잠재 진척도**: 2,775점 + 375점 = **3,150 / 4,800점 = 65.63% (약 65% 진척 / 잔여 약 35%)**.
2. **독립 검토 및 협업 인계**:
   - 인계서: `HO-GEMINI-CLAUDE-002` (v1.0.16).
   - Claude(`CL-01`): 독립 검토 진행 가능.
   - Codex(`CX-01` ~ `CX-03`): `deploy/Dockerfile.backend` 팩토리 엔트리포인트 복원 및 `.225` 원격 PC 프로필 설치 대기.
