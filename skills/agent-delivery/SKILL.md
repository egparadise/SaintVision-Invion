---
name: agent-delivery
description: Every SaintVision task delivery
version: 1.1.0
---

# agent-delivery

입력: TaskCard·지침 버전·base SHA. 작업 init 후 scope를 확인한다. 구현·관련 검증 → commit → origin push → 동일 SHA CI → Git 보고서 → Obsidian 동기화 → reviewer 인계. 실패는 오류 페이지·다음 행동으로 남기고 done 처리하지 않는다. 예측값과 실제 결과를 구분한다.

매 작업 시작에 공통 진행판 `docs/vault/00_Index/전체 개발 진행 현황.md`와 자기 Agent 작업판을 읽고 카드·owner/reviewer·branch/base·문서 버전을 기록한다. 종료·인계·중단 전에 작업한 것, 확인한 명령/exit code/환경/Evidence, CI/독립 검토/운영 인수의 각 상태, 남은 문제와 다음 카드/첫 행동/담당을 남긴다. 상세 이력은 History, 현재 요약은 공통 진행판으로 연결한다. 오래된 branch의 전체 vault로 최신 공유본을 덮어쓰지 않는다. 상세 절차는 `docs/vault/40_Governance/Agent 지속 개발 운영 규칙.md`다.

권한: 현재 사용자 지시와 실행 환경 권한 범위 안에서 동작한다. 이미 승인된 작업의 반복 확인을 요구하지 않는다. 공통 지침은 AGENTS.md다.
