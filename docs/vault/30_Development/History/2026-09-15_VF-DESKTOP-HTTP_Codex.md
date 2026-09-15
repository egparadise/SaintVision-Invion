---
doc_id: "HIST-VF-DESKTOP-HTTP-001"
title: "VF Desktop 실제 HTTP 브라우저 검증"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-15T18:54:05+09:00"
source_of_truth: "Git"
---

# VF Desktop 실제 HTTP 브라우저 검증

- owner Codex, reviewer Gemini·Claude(이번 변경 미수신), task VF-CX-01 통합 후속. base0fcbea4, branch agent/codex/vf-desktop-http. 시작 2026-09-15T18:54:05+09:00.
- 공통판 INDEX-PROGRESS-0011.0.86, Codex1.0.54, VF판1.0.15, 설계인덱스/로드맵1.0.0/연속정책1.0.0 및 agent-delivery1.1.0/core-reliability1.0.0 확인.
- 목표: 실제 Edge→Vite→configured HTTP server→비소유자 PostgreSQL의 파일/모델 조회, 현재 권한 철회, 가짜 성공/과거 데이터 노출 거부를 검증. synthetic JWT/로컬 임시DB이며 운영 SSO/5대 인수와 구분한다.
- Claude b44ea32 저장소 API 시험을 faa70b3으로 수신. b30a723은 기존653aea0의 lineage.py/test_model_registry.py와 diff0이며 승인 시간·잠금 보강에 대한 Claude 실제 검토/13시험 보고다. 해당 배포 보강만 독립 검토 수신, 새 Desktop 검토로 확대하지 않는다.
- 구현→로컬시험→고정SHA push/CI→범위제한 Obsidian 동기화→Gemini·Claude 검토 인계.

## 검증 결과

- 최초26시험: 24pass/2fail/0skip. 파일 브라우저 경로는 통과. 모델 서버 시작 실패는 시험 helper가 business:false를 넣었기 때문이며, 기존 설정 계약은 key 생략 또는 true만 허용한다. optional true만 출력하도록 수정했다. 수신한 Claude 시험은 현재 HTTPBearer의 missing-token 401/WWW-Authenticate: Bearer에 맞춰 고쳤다. 제품 인증 동작 변경 없음.
- 수정 후 관련57시험 pass/0fail/0skip/exit0: 실제 Desktop browser2, canonical storage/model/configured server와 수신 storage API, registry/동시성 회귀. native Windows Uvicorn 실제 HTTP 및 비소유자 PostgreSQL16; synthetic issuer, 실제 운영 SSO 아님.
- 명시적 VF_BROWSER_TEST=1 runner로 최종 browser2 pass/0skip/exit0 재검증. ambient INV 설정은 제거하고 INV_BROWSER_TEST opt-in만 검증된 플래그에서 전달한다.
- Edge/Chromium은 HTTP 응답을 가로채지 않았다. Vite proxy→실서버 인증→PG RLS/현재grant/모델manifest 조회. 파일 owner-only 목록, private URI404, revoke 후 empty, forged token거부, 모델 hash일치/unknown가용성, grant revoke403와 이전결과제거. API 요청은 GET만, pageexception0.
- 전용 Desktop HTTP Browser Acceptance CI를 추가했다. Node22/Python3.12/Playwright1.62.0 Chromium 설치 후 동일 격리 runner 실행, 2pass/0skip/컨테이너제거를 강제한다. backend/core는 이 파일만 전용 job에 맡긴다. CI 실행 결과는 push 후 따로 기록한다.
- `python tools/check_docs.py`481문서 exit0, `python tools/check_ontology.py`exit0. 제품 코드 변경 없음. 프런트엔드 build242시험 증거는 기반81987d3이며 이번 실행으로 재계산하지 않는다.
- 다음 담당: Gemini 실제 Desktop 화면/접근성 독립 검토, Claude 이번 harness/CI와 수정된 HTTPBearer 기대값 검토. 운영 owner는 SSO·5대/PITR·CI billing. 기존57.81%/VF운영0/5 유지.
