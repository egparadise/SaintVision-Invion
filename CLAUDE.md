# Claude 진입 지침

매 작업은 `docs/vault/00_Index/전체 개발 진행 현황.md`와 `docs/vault/30_Development/Agent별 작업/Claude 작업 현황.md` 확인으로 시작한다. 오래된 branch에서는 AGENTS.md의 공유 Obsidian 경로로 최신 진행판을 확인한다. 끝날 때 작업·검증 증거·다음 첫 행동/담당을 갱신하며, Codex 작성 코드의 독립 검토는 실제 수행한 결과만 기록한다.

먼저 AGENTS.md를 읽는다. Claude는 중간 난도 Backend·DB·Context·Adapter·테스트·운영 문서의 owner다. 고난도 동시성·보안·분산 복구 변경은 Codex 계약을 받아 구현하고 Codex에게 검토를 인계한다. Codex가 작성한 설계·코드는 Claude가 독립 검토한다.

`skills/service-integration/SKILL.md`, `skills/agent-delivery/SKILL.md`를 따른다. 디자인·Frontend·웹 배포는 Gemini(Antigravity)의 책임이다. 배정되지 않은 코어·화면을 임의로 대체하지 않는다. task-registry의 owner·reviewer·선행 작업과 실제 결과를 확인하고 진행한다.
