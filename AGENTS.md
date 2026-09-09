# SaintVision 개발 Agent 공통 지침

## 먼저 읽기

1. `docs/vault/00_Index/최종 개발 계획 - 모든 개발의 지침.md`
2. `docs/vault/40_Governance/설계 충돌 정정 및 ADR.md`
3. `docs/vault/40_Governance/Agent 역할과 인계 계약.md`
4. `docs/vault/40_Governance/Git Build Obsidian 운영 절차.md`
5. 자신의 영역 계획과 `docs/task-registry.json`의 배정 작업.

## 역할

- Codex: 최고 난도, 아키텍처·공통 계약·분산 상태·동시성·보안·무결성·Reverse-Ontology.
- Claude: 중간 난도 서비스·CRUD·일반 migration·Context·Adapter·테스트·운영 문서.
- Gemini: Antigravity에서 디자인·Frontend·접근성·브라우저 검증·내부망 웹 배포.
- 작업당 owner 하나, 작성자와 reviewer 분리. 다른 Agent 검토를 수행했다고 꾸미지 않는다.
- 사용자 지시·이미 부여된 승인을 우선하며 반복 승인 요구로 승인된 작업을 중단하지 않는다.

## 작업 계약

- 완성 목표 → 합격 증거 → 기능·계약 → 작업 → owner를 역산한다.
- Prompt/Context/Harness/Skill/ROOF/Graph/Agent 버전과 실제 Evidence를 연결한다.
- 시작 시 doc ID·version·base SHA·task ID·scope를 기록한다.
- `skills/agent-delivery/SKILL.md`와 역할별 Skill을 읽는다.
- init → 구현·로컬 검증 → commit → push → CI build → Obsidian report → 검토·인계.
- 최초만 Git init, 이후 init은 작업 준비다. 이미 있는 저장소를 재초기화하지 않는다.
- origin: https://github.com/egparadise/SaintVision-Invion.git
- 작업 브랜치: agent/{codex|claude|gemini}/{task-id}; 별도 worktree 권장.
- 선행 미완료·검증 실패·push/build/report 미완료는 done이 아니다.
- 실제 실행 기록은 docs/vault/30_Development/History; 오류·해결은 별도 페이지.
- KST 시각·명령·exit code·코드 SHA·CI ID·sync 결과·다음 담당자를 남긴다.
- 문서 정본은 docs/vault, Obsidian은 동기화 사본. 외부 편집은 제안으로 반영한다.
- 원문 docs/sources를 수정하지 않는다. 수정 설계는 ADR로 구분한다.

## 검증

`python tools/check_docs.py`

`python tools/check_ontology.py` (requirements-docs.txt 환경)

`python tools/sync_obsidian.py --check` 후 실제 권한 내 `--apply`.

제품 코드는 아직 없다. 문서 검사 통과를 제품 build·장비 시험 성공이라고 쓰지 않는다.
