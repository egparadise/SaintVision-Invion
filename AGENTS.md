# SaintVision 개발 Agent 공통 지침

## 먼저 읽기

0. `docs/vault/00_Index/전체 개발 진행 현황.md`와 자신의 `docs/vault/30_Development/Agent별 작업/{Codex|Claude|Gemini|Orca} 작업 현황.md`를 읽고 진행판 버전·작업 카드·다음 행동을 확인한다.
0-1. `docs/vault/00_Index/2026-09-15 단일 가상 컴퓨터 보강 설계 인덱스.md`, `docs/vault/30_Development/57.81퍼센트 이후 단일 가상 컴퓨터 보강 로드맵.md`, `docs/vault/40_Governance/Agent 연속 실행과 최종 보고 정책.md`를 읽는다.
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
- 승인된 범위에서는 `ready 선택 → 구현 → 내부 검증 → Evidence/인계 → 다음 ready`를 반복한다. routine 중간 사용자 확인을 요구하지 않으며, 권한·자격증명·비용·공개 배포·파괴적 변경처럼 새 승인이 필요한 경계에서만 멈춘다.

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
- 연속 실행은 test, CI, 독립 review, 운영 인수를 생략한다는 뜻이 아니다. 한 카드가 외부 요인으로 막히면 이유를 기록하고 다른 ready 카드를 진행한다.
- 실제 실행 기록은 docs/vault/30_Development/History; 오류·해결은 별도 페이지.
- KST 시각·명령·exit code·코드 SHA·CI ID·sync 결과·다음 담당자를 남긴다.
- 문서 정본은 docs/vault, Obsidian은 동기화 사본. 외부 편집은 제안으로 반영한다.
- 원문 docs/sources를 수정하지 않는다. 수정 설계는 ADR로 구분한다.

## 지속 개발 기록

- 매 작업 시작 시 공통 진행판과 자기 작업판을 확인한다. 카드 하나를 선택해 owner/reviewer·branch/base SHA·KST·읽은 문서 버전을 기록하고 착수 상태를 갱신한다.
- 매 작업 종료·인계·중단 전에 **작업한 것 → 확인한 것(명령·exit code·환경·Evidence) → 이어서 할 첫 행동과 담당**을 자기 작업판과 History에 남긴다. 공통 진행판에는 한 줄 요약을 반영한다.
- 구현·로컬 검증·CI·독립 검토·운영 인수 상태를 따로 기록한다. 미확인/차단을 완료로 바꾸지 않고, 차단된 카드 외의 ready 작업은 계속한다.
- 집계 owner는 Orca 관리 역할이며 실제 관리 세션이 없으면 Codex가 맡는다. 다른 Agent의 수신·착수·검토를 대신 완료 처리하지 않는다.
- 오래된 worktree는 공유 Obsidian의 `C:\Users\egpar\OneDrive - Inviz\15.Vibe Cording\Obsidian\SaintVision-Invion\00_Index\전체 개발 진행 현황.md`에서 최신 배포본과 Git source를 확인한다. 최신 페이지가 없는 branch는 최초 전달 branch `agent/codex/workspace-bridge`의 진행 문서를 확인한다. 오래된 vault 전체를 최신 공유본 위에 export하지 않는다.
- 상세 규칙은 `docs/vault/40_Governance/Agent 지속 개발 운영 규칙.md`다. 긴 로그는 History/Evidence에 보존하고 진행판은 현재 상태·다음 담당을 유지한다.

## 검증

`python tools/check_docs.py`

`python tools/check_ontology.py` (requirements-docs.txt 환경)

`python tools/sync_obsidian.py --check` 후 실제 권한 내 `--apply`.

오늘(2026-09-22) 추가된 검사 다섯 — 등급이 실패 시 CI를 막는지 말해준다:
- `python tools/check_contract_bindings.py` — 계약 fixture·서빙앵커 커버리지. **게이트**(실패=CI 막힘).
- `python tools/check_frontend_integrity.py` — 프런트 무결성(가짜 id·조기성공·tri-state). **게이트**.
- `pytest tests/core/test_serving_anchors.py`(backend/core 스위트가 수집) — 커널 응답 서빙앵커 무게. **게이트**.
- `python tools/check_doc_single_source.py --ratchet` — 살아있는 문서 간 중복(rule5 분기). **ratchet**(새 중복만 막고 기존 백로그는 통과; 기본 실행은 report-only).
- `python tools/check_response_freshness.py` — 신선도-중요 응답의 관측시각 필드 유무. **report-only**(안 막음 → `$GITHUB_STEP_SUMMARY`로 봄).

검증 검사 도구 **전체 목록**(무엇을·게이트등급·실행법·실패 시 대응)은 `docs/vault/40_Governance/검증검사도구_목록.md`. 검증 규칙·축 정본은 `docs/vault/40_Governance/검증규칙과_세축_canon.md`.

제품 코드와 로컬 실행 검증 기록이 있다. 현재 범위는 공통 진행판의 고정 SHA 증거를 확인한다. 문서 검사 통과를 제품 build·장비 시험 성공이라고 쓰지 않는다.
