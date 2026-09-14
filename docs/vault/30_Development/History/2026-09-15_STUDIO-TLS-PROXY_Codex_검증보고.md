---
doc_id: "HIST-STUDIO-TLS-PROXY-REPORT-20260915"
title: "2026-09-15 STUDIO-TLS-PROXY Codex 검증보고"
version: "1.0.1"
status: "review"
author: "Codex"
updated: "2026-09-15T01:08:36+09:00"
source_of_truth: "Git"
---

# 2026-09-15 STUDIO-TLS-PROXY Codex 검증보고

[[2026-09-15_STUDIO-TLS-PROXY_Codex_착수]]에서 이어 진행했다. CX-01 후속, owner Codex, reviewer Claude 대기. 제품 SHA `89a405a98e21f54feb84bc8799a441f971026a6b`, agent/codex/approval-browser로 commit/push 완료. 문서 정본은 workspace-bridge다.

## 실제 결함과 수정

Nginx 정적 location에 Cache-Control을 추가하면 상위 보안 add_header가 상속되지 않아 `/studio` 응답에 nosniff 등의 헤더가 없었다. security-headers.conf를 해당 location마다 포함하고 Referrer-Policy는 no-referrer로 통일했다. 근거는 [공식 Nginx add_header 상속 규칙](https://nginx.org/en/docs/http/ngx_http_headers_module.html#add_header)이다.

기존 access log는 `$request`와 Referer를 기록해 HTTP redirect query와 같은 origin Referer 안의 OAuth code/state를 남겼다. query/Referer를 제외한 method·URI·status 로그로 교체했다. callback은 기존 access_log off도 유지한다.

실제 커널 `/v1/projects/{project}/runs/{run}/events`에 proxy buffering off가 없어 첫 이벤트를 upstream 종료까지 모았다. 정본 경로를 추가하고 첫 이벤트가 두 번째 이벤트보다 먼저 도착하는지 실제 소켓으로 검증했다. backend가 사라졌을 때 기본 연결 대기로 브라우저 timeout이 먼저 발생하던 문제는 proxy_connect_timeout 2s로 제한했다.

healthcheck는 인증서 검증을 끄는 HTTPS 호출을 제거하고 컨테이너 내부 HTTP liveness로 구분한다. `/readyz`는 backend 실패 상태를 그대로 반환한다. Compose는 기존 public OAuth 설정 파일을 `INV_WEB_AUTH_CONFIG`로 명시하도록 하고 단일 파일 readonly mount/create_host_path=false를 적용했다. 인증서는 기존 별도 mount를 유지한다. Docker build context에서 node_modules/dist/.env/.work를 제외했다. Frontend CI에 실제 image build·TLS/Edge/Compose 시험을 추가했다.

## 재현과 합격 증거

- 정본 Dockerfile `docker build --tag saintvision-web-candidate:studio-tls apps/web` exit 0. 최종 이미지 `sha256:7215cd99b0f4081e17091c4a28bc52d5f497dc610496df5cf4de49b1a7bb0143`. Linux 내부 TypeScript/Vite build 통과, 최종 Vite 8.73초. 실제 Nginx 1.27.5를 실행했다.
- 이전33d63d5 nginx.conf만 같은 이미지에 readonly override하여 실행: 헤더·SSE·로그 3개 시험 모두 실패/11.26초, exit 1. 임의 broken model이 아닌 이전 정본 설정으로 재현했다.
- 최종 `INV_WEB_IMAGE=... python -m pytest -q tests/integration/test_web_container.py`: **7개 통과/19.35초, exit 0**. CA 미신뢰 거부, 명시 CA 신뢰 TLS 성공, 정적/설정/asset 보안 헤더, HTTP/HTTPS query·Referer 로그 비노출, Bearer/status 전달, readiness 실패, SSE 첫 이벤트 지연 방지, backend 중단 시502/504·동일 container 재시작 후 재연결을 확인했다.
- 이 중 실제 Edge는 빌드된 `/studio`를 HTTPS로 열고 readonly config를 확인했다. 테스트용 ephemeral SPKI만 허용하며 전역 ignore HTTPS errors를 사용하지 않는다. Service Worker 활성화·새로고침 후 auth-config/API/callback이 캐시에 없고 local/sessionStorage도 비어 있음을 확인했다. 이 시험에서 로그인 자체는 수행하지 않았다.
- `python -m pytest -q tests/core/test_deployment_credentials.py`: **11개 통과/9.19초, exit 0**. 새 public 설정 누락 거부와 readonly mount를 포함한다. 이 검사는 Compose 모델이며 전체 운영 stack 기동이 아니다.
- 시험 container와 network는 label 확인 후 제거했고, `ai.saintvision.web-test` 잔여 개수0을 확인했다. 임시 private key 파일도 해당 단일 경로만 삭제했다.

Evidence: `../Evidence/studio-tls-89a405a.json`, 실제 built 화면 `../Evidence/studio-tls-89a405a.png`. 이번 upstream은 **transport fixture**다. 실제 kernel/JWT/PG 권한·PKCE 로그인 검증은 앞선 [[2026-09-15_STUDIO-AUTH-ENTRY_Codex_검증보고]]이며 두 환경이 하나의 운영 통합 시험인 것처럼 합산하지 않는다.

## CI와 미완료

동일 SHA Frontend34866485315, Backend34866485266, Docs34866485271, Core34866485273은 전부 결제/한도 제한으로 job 미시작. CI Evidence `../Evidence/studio-tls-ci-89a405a.json`. CI에 새 시험을 연결했지만 실제 CI 통과를 주장하지 않는다.

Npm 이미지 build가 moderate 의존성 경고2개를 냈으며 이번에 버전을 변경하거나 audit 해소를 하지 않았다. 기존 Nginx listen http2 구문은 deprecated 경고가 있으나 시작 실패는 아니었다. 운영 IdP·인증서·Node·DB·서비스는 변경하지 않았다. 새 hostname/IP로 교체되는 backend DNS 재탐색, 실제 configured kernel과 이 HTTPS proxy를 통한 PKCE 전체 여정, operational SSO, remote7시험은 별도 미완료다.

## 인계와 다음 행동

Codex: 다음은 HTTPS proxy+configured kernel+합성 PKCE 전체 여정을 하나의 격리 환경으로 묶고, business 프로젝트/Workspace 생성·편집·실행·결과 흐름을 연결한다. tools/deploy_intranet.ps1의 고정 성공 문구·exit 확인 누락과 simulation 인수 주장은 정리 전 운영 완료 근거로 쓰지 않는다.

Claude:89a405a proxy/timeout/cache/log/Compose 계약 독립 검토, 운영 IdP와 계정 설정, dependencies 점검. Gemini:이 후보와 공유 branch 변경을 검토·통합하고 실제 배포 화면/스크립트 인수를 수행한다. 최신 외부 Gemini6b32c5a의 EvidenceViewer project API·flat fallback·ResultView 합성 변경은 원문 보존했으며 별도 검토 대상이다. 137tests/186smoke/26경로 완료 보고를 이번 커널 통합 증거로 인정하지 않는다.

전체 공식 완료율 **57.8125%(2775/4800), 남은42.1875%** 유지. 로컬 후보의 transport/배포 검증 범위가 진전됐으나 독립 검토·운영 인수 단계는 남아 있다. 문서 검사·Obsidian export 결과는 후속 기록한다.

## 문서와 Obsidian 반영

check_docs는413 versioned 문서/48task 통과, check_ontology도 통과(각 exit0). 문서8e7e2c6 commit/push 후 보존 원문·Git blob·외부 mirror hash를 비교하여3파일을 동일 내용으로만 adoption(대상 쓰기0개)했다. sync --check→--apply→--check exit0, 2026-09-15 01:08:24 KST 929파일 hash 일치·pending0·conflict0. Evidence는 `../Evidence/studio-tls-sync-8e7e2c6.json`. 로컬 Obsidian 사본 확인이며 OneDrive cloud 확인은 아니다. 이 receipt도 commit/push 후 다시 동기화한다.
