# Gemini / Antigravity 진입 지침

AGENTS.md를 먼저 읽는다. Gemini는 Antigravity에서 디자인·Frontend·웹 배포를 소유한다. `skills/frontend-delivery/SKILL.md`와 공통 `skills/agent-delivery/SKILL.md`를 따른다.

Frontend는 계약 타입과 실제 API를 사용하고 정상·빈 상태·오류·권한·부분 실패를 검증한다. 인증·SSE·WS·승인 코어는 Codex와 계약을 합의한다. 내부망 HTTPS 배포·웹 rollback·브라우저 smoke·접근성 증거를 기록한다. Backend·DB·Storage의 정본 계약을 UI 편의로 바꾸지 않는다.

Antigravity 세션에 이 파일과 AGENTS.md를 Context로 명시적으로 제공하고 읽은 버전을 시작 기록에 남긴다. 규칙 파일 자동 로드 여부는 실행 도구에서 확인한다.
