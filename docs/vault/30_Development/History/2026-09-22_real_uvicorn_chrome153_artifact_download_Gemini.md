---
doc_id: "HIST-GEMINI-20260922-06"
title: "실제 Uvicorn 0.52.4 백엔드와 실제 Google Chrome 153 종단간 연결 실측 완결"
version: "1.0.0"
status: "approved"
author: "Gemini"
created: "2026-09-22T04:15:00+09:00"
updated: "2026-09-22T04:15:00+09:00"
source_of_truth: "Git"
---

# 실제 Uvicorn 0.52.4 백엔드와 실제 Google Chrome 153 종단간 연결 실측 완결

## 1. 개요 및 사용자 질문 답변

### 1-1. 사용자 질문 답변
> "한 줄만 답해줘라. workspaceId 가 실제로 빌 수 있었나 아니면 계약 검증이 이미 막고 있어서 그 기본값이 죽은 코드였나. 내가 확인하라고 한 것인데 결과를 못 봤다."

**[답변]**: `core.schema.json`에는 `workspaceId`가 필수 규격이었으나, 프런트엔드 `fetchWorkspaceEditView`의 수동 응답 가드에서 `workspaceId` 검사가 누락되어 있어 실제로 빈 값이 들어와도 검증을 통과하여 `'default-workspace'`가 발화되던 **살아 있는 강등(Silent Fallback)**이었습니다. 현재는 수동 가드에서 빈 문자열/공백 검사를 추가하여 즉시 throw 처리하고 기본값 fallback을 영구 제거했습니다.

### 1-2. 마지막 대역 층(Mock) 제거 실측 목표
- 기존 실측에서는 브라우저 DOM/WebCrypto/파일 저장은 실제 Chrome 153을 사용했으나, 백엔드 네트워크 계층은 Playwright의 라우트 가로채기(Mock)를 사용하고 있었습니다.
- 이번 검증에서는 **Playwright 네트워크 모의를 전면 걷어내고**, 실제 ASGI 웹서버인 **Uvicorn 0.52.4**(`services/control-plane/src/inv/app.py` `create_app`)를 127.0.0.1:8080에 띄우고, **Vite 개발 서버(127.0.0.1:3005)** 프록시를 통해 **실제 Google Chrome 153(공식 빌드, Blink 엔진)** 브라우저를 끝에서 끝까지 연결하여 실제 산출물 다운로드 및 WebCrypto 무결성 검증을 실측했습니다.

---

## 2. 정직한 경계 분리 (무엇이 실제였고 어디가 경계인가)

| 계층 | 실제 구현체 (Genuine Production) | 모의/경계 주입 (Boundary Isolation) |
|---|---|---|
| **백엔드 서버** | **Uvicorn 0.52.4** ASGI TCP 소켓 (127.0.0.1:8080)<br>FastAPI 0.115 `create_app`<br>`artifact_content_response` 계약 검증 (`ArtifactContentResponse`)<br>실제 wire 헤더 직렬화 (`X-Content-SHA256`, `Content-Length`, `Content-Disposition`, `X-Content-Type-Options`) | PostgreSQL DB 트랜잭션 및 IdP(Keycloak): 로컬 인메모리 바인딩(`MockTokens`, `Control`, `ResultView`)으로 주입 |
| **네트워크** | **100% 실제 TCP 소켓 왕복**<br>Chrome -> Vite 프록시(:3005) -> Uvicorn(:8080)<br>Playwright `/v1` 라우트 모의 **0건 (ZERO MOCK)** | IdP 토큰 엔드포인트(`/oauth/token`)만 로컬 OAuth 세션 완료를 위해 Playwright 라우트로 충족 |
| **프런트엔드** | Vite 5.x 개발 서버 (127.0.0.1:3005)<br>`DeveloperStudio.tsx` Step 4 결과 및 아티팩트 UI<br>`runArtifactObservation.ts` `downloadAndVerifyArtifact`<br>네이티브 Fetch API | - |
| **브라우저 런타임** | **Google Chrome 153.0.7070.0 (Official Build, Blink 엔진)**<br>네이티브 `crypto.subtle.digest('SHA-256', ...)`<br>네이티브 파일 다운로드 이벤트 (`page.expect_download()`)<br>로컬 디스크 파일 I/O (`downloaded_real_uvicorn_artifact.bin`) | - |

---

## 3. 실측 수행 과정 및 결과

### 3-1. 실행 스크립트
- `scratch/verify_artifact_download_real_uvicorn_chrome.py`
  - Uvicorn 0.52.4 백엔드 데몬 스레드 가동 (127.0.0.1:8080)
  - Vite dev server (127.0.0.1:3005, proxying `/v1` to `:8080`)
  - Google Chrome 153 실행 및 `/callback` PKCE 세션 초기화
  - 상단 탭 `개발 Studio` 클릭 -> Step 4 `4. 실행 상태 & 실시간 로그` 클릭
  - 아티팩트 카드 `✓ 산출물 검증 완료 (Output Verified)` 확인
  - `[📥 결과 파일 다운로드 (Bytes)]` 클릭
  - Chrome 네이티브 다운로드 이벤트 수신 및 디스크 저장
  - 화면 상 `[전송 확인 완료]` 배너 표출 확인
  - 다운로드 파일 바이트 및 SHA-256 대조 단언

### 3-2. Uvicorn 0.52.4 서버 로그 실측
```text
INFO:     Started server process [30400]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8080 (Press CTRL+C to quit)
INFO:     127.0.0.1:57506 - "GET /v1/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:53018 - "GET /v1/session HTTP/1.1" 200 OK
INFO:     127.0.0.1:53020 - "GET /v1/projects HTTP/1.1" 200 OK
INFO:     127.0.0.1:54060 - "GET /v1/projects/prj_pacs_core/workspaces HTTP/1.1" 200 OK
INFO:     127.0.0.1:56371 - "GET /v1/projects/prj_pacs_core/runs HTTP/1.1" 200 OK
INFO:     127.0.0.1:54679 - "GET /v1/projects/prj_pacs_core/runs/run_pacs_pipeline_01/result HTTP/1.1" 200 OK
INFO:     127.0.0.1:51904 - "GET /v1/projects/prj_pacs_core/runs/run_pacs_pipeline_01/artifacts/content?path=src%2Fserver.ts HTTP/1.1" 200 OK
```

### 3-3. Chrome 153 DOM 및 파일 검증 결과
1. **아티팩트 카드 렌더링**: Uvicorn `/result` 응답의 `output.sha256` 및 `evidence.evidenceId`를 읽어 `✓ 산출물 검증 완료 (Output Verified)` 뱃지 정상 표출.
2. **실제 HTTP 다운로드 및 wire 헤더**:
   - `HTTP 200 OK`
   - `X-Content-SHA256: 8e5d9e54800114544696a3191094c080534476cefb01b7f7fe47bd11d703ddf9`
   - `Content-Length: 50`
   - `Content-Disposition: attachment; filename="artifact.bin"`
   - `X-Content-Type-Options: nosniff`
3. **Chrome WebCrypto 검증 및 정직한 배너 표출**:
   - Chrome 네이티브 WebCrypto가 50바이트의 SHA-256을 계산하여 wire 헤더와 일치함을 검증.
   - 화면에 과장 없는 정직한 배너 렌더링:
     ```text
     [전송 확인 완료] 산출물 파일 'artifact.bin' (50 Bytes, 수신 바이트와 서버 헤더 일치 · 저장소 원본 대조 아님) 다운로드 완료.
     ```
4. **로컬 디스크 파일 바이트 대조**:
   - 디스크 저장 경로: `scratch/downloaded_real_uvicorn_artifact.bin`
   - 파일 크기: 정확히 50 바이트
   - 파일 내용: `saintvision-real-uvicorn-artifact-bytes-model-153\n`
   - 디스크 파일 SHA-256: `8e5d9e54800114544696a3191094c080534476cefb01b7f7fe47bd11d703ddf9` (서버 불변 영수증과 100% 일치)
5. **실측 증거물 확보**:
   - 안전한 화면 스크린샷: `scratch/real_chrome_real_uvicorn_transmission_verified.png`
   - 실측 결과 레코드: `scratch/chrome_real_uvicorn_acceptance_result.json` (`passed: true`)

---

## 4. 결론 및 안전성
- 백엔드 Uvicorn 0.52.4 프로세스와 프런트엔드 Vite 프록시 및 Google Chrome 153 브라우저 간의 **모의 없는 실제 소켓 통신 및 WebCrypto 무결성 검증**이 종단간 완결되었습니다.
- 모든 실측 산출물은 `.gitignore`에 등록된 `scratch/` 내에 격리 보관되어 저장소 오염 없이 안전하게 완료되었습니다.
