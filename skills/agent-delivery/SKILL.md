---
name: agent-delivery
description: Every SaintVision task delivery
version: 1.0.0
---

# agent-delivery

입력: TaskCard·지침 버전·base SHA. 작업 init 후 scope를 확인한다. 구현·관련 검증 → commit → origin push → 동일 SHA CI → Git 보고서 → Obsidian 동기화 → reviewer 인계. 실패는 오류 페이지·다음 행동으로 남기고 done 처리하지 않는다. 예측값과 실제 결과를 구분한다.

권한: 현재 사용자 지시와 실행 환경 권한 범위 안에서 동작한다. 이미 승인된 작업의 반복 확인을 요구하지 않는다. 공통 지침은 AGENTS.md다.
