# Gemini / Antigravity 진입 지침

매 작업은 `docs/vault/00_Index/전체 개발 진행 현황.md`와 `docs/vault/30_Development/Agent별 작업/Gemini 작업 현황.md` 확인으로 시작한다. 오래된 branch에서는 AGENTS.md의 공유 Obsidian 경로로 최신 진행판을 확인한다. 끝날 때 작업·브라우저/API 검증 증거·남은 문제·다음 첫 행동/담당을 갱신한다. 예시 화면과 실제 운영 인수는 별도로 기록한다.

AGENTS.md를 먼저 읽는다. Gemini는 Antigravity에서 디자인·Frontend·웹 배포를 소유한다. `skills/frontend-delivery/SKILL.md`와 공통 `skills/agent-delivery/SKILL.md`를 따른다.

Frontend는 계약 타입과 실제 API를 사용하고 정상·빈 상태·오류·권한·부분 실패를 검증한다. 인증·SSE·WS·승인 코어는 Codex와 계약을 합의한다. 내부망 HTTPS 배포·웹 rollback·브라우저 smoke·접근성 증거를 기록한다. Backend·DB·Storage의 정본 계약을 UI 편의로 바꾸지 않는다.
Frontend 변경 착지 전에는 단위 테스트(Vitest) 통과에만 의존하지 않고 반드시 `cd apps/web && npx tsc -b` 및 `npm run build`를 직접 실행하여 타입 에러 0건과 프로덕션 번들 생성을 실측한다 (Vitest는 타입을 strip하므로 타입 오류를 검출하지 못함).

Antigravity 세션에 이 파일과 AGENTS.md를 Context로 명시적으로 제공하고 읽은 버전을 시작 기록에 남긴다. 규칙 파일 자동 로드 여부는 실행 도구에서 확인한다.

2026-09-15 보강 트랙은 `docs/vault/30_Development/57.81퍼센트 이후 단일 가상 컴퓨터 보강 로드맵.md`의 VF-GM 카드를 우선한다. Web Desktop Shell, My Computer/Resource Explorer, File Explorer, Model Studio, Terminal/IDE, 외부 HTTPS와 브라우저 인수 순으로 준비된 카드를 중간 사용자 확인 없이 이어간다. 실제 API·권한·부분 실패·접근성 E2E 전에는 done으로 표시하지 않는다.
