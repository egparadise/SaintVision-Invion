---
doc_id: "HIST-VF-DESKTOP-INTEGRATION-001"
title: "VF Desktop 실조회 계약 통합"
version: "1.0.0"
status: "in_progress"
author: "Codex"
updated: "2026-09-15T18:39:34+09:00"
source_of_truth: "Git"
---

# VF Desktop 실조회 계약 통합

- VF-CX-01 통합후속, owner Codex/reviewer Gemini·Claude pending. base7d18b62/agent/codex/vf-desktop-integration, 시작2026-09-15T18:39:34+09:00.
- INDEX-PROGRESS-0011.0.85/WORKBOARD-CODEX-0011.0.53및기존지침/ADR/역할/운영/로드맵/연속정책, agent-delivery/core-reliability 적용.
- Gemini5ef0f1a cherry-pick시진행판충돌은최신판유지. frontend-mutations ab8b645 merge시App은검증된프로젝트/승인관측판선택.
- 발견:샘플파일·모델/실요청없는복구·등록성공alert/고정5대정상알림/고정terminal identity. 실제기능으로승격금지.
- 범위:로그인·프로젝트경계유지,Desktop read-only실조회,미연결mutation/terminal차단. 독립검토/실브라우저/운영인수별도.

## 구현과 검증

- Gemini Desktop UI를 backend 후보와 통합했다. App은 기존 frontend-mutations의 로그인·프로젝트·승인 digest 보호를 유지한다. 로그인 사용자와 선택 프로젝트가 있어야 Desktop 진입이 가능하며 tenant/user/project 키로 재마운트한다.
- 파일 목록·URI 해석·복제본 관측, 정확한 프로젝트/model/version의 Manifest commitment를 기존 GET API로 조회한다. 샘플 파일/모델과 요청 없는 복구·dispatch 성공 표시를 제거했다. URI/모델 범위 및 복제본 집계 불일치를 거부한다.
- 현재 가용성은 unknown, 실행 시 재검증 필요로 표시한다. 입력 변경·프로젝트 전환·unmount에서 요청을 취소하고 이전 응답을 무시한다. Resource Explorer 대신 기존 검증된 NodeList를 표시한다.
- Desktop terminal/studio/approval/settings는 포털로 돌아가는 안내로 제한했다. DesktopSessionView의 샘플 identity는 실행 경로에서 제외했다. 기존 포털의 모든 시제품 기능을 실서비스로 승격했다는 의미가 아니다.
- Windows Node/Vite: `npm ci --ignore-scripts` exit0; `npm run build` exit0; `npm test` 최종242 pass/0 skip, exit0. 추가20개는 실제 client 호출 mock + SSR; live backend 검증은 아니다.
- 최초 추가시험4실패는 beforeEach가 mock 함수를 반환해 cleanup으로 재실행된 시험 fixture 오류였다. void callback으로 수정 후242통과. 최초 headless 실행은 Playwright bundled Chromium 미설치로 exit1; 설치된 Edge Chromium channel로 실행해 통과했다.
- `python tools/verify_desktop_observation_browser.py`: 실제 headless Edge Chromium에서 HTTP fixture 응답으로 empty/관측/입력 race/project race/403/GET-only/browser exception/비로그인 진입 경계를 검증한다. 실제 backend·SSO·5대 장비 검증과 구분한다. 결과는 Evidence/vf-desktop-integration/browser.json.
- `python tools/check_docs.py` exit0 (480문서), `python tools/check_ontology.py` exit0. 최종 보고 후 재검사한다.
- 독립 검토: Gemini/Claude 미수신. CI: push 후 동일 코드 SHA 확인 예정. 운영 인수/실장비/SSO 미완료; 57.81%와 VF 운영 0/5 유지.
- 다음 첫 행동: Gemini는 Desktop 진입·창 동작·접근성·실제 API 연결 독립 검토, Claude는 조회 경로 권한 계약 검토. Codex는 CI 접수와 범위 제한 Obsidian sync를 마무리한다.
