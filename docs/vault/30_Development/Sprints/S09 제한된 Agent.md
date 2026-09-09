---
doc_id: "PLAN-S09"
title: "S09 제한된 Agent"
version: "1.0.0"
status: "planned"
author: "Codex"
updated: "2026-09-09T15:10:54+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# S09 제한된 Agent


기간: 착수 후 17–18주 / 릴리스 R3 / 품질 게이트 G1/G2/G6 기초. **planned**. 실제 시작·종료 시각과 실행 페이지는 수행 시 생성한다.

## 목표와 선행 조건

OUT-09: Agent가 근거 있는 Context와 제한된 수정 루프로 일한다

선행: S08의 4영역 검증 결과와 공유 계약. 아래 작업은 준비가 된 범위에서 병행하되 선행 완료를 거짓 표시하지 않는다.

## 작업

| ID | 영역 | owner | reviewer | 산출물 |
|---|---|---|---|---|
| S09-FE | Frontend | Gemini | Codex | 자연어 요청·예산·diff 검토 |
| S09-BE | Backend | Codex | Claude | Prompt·Context·Skill·bounded repair |
| S09-DB | DB | Claude | Codex | 불변 Context/RunRecord·eval |
| S09-ST | Storage | Claude | Codex | diff·테스트·trace Artifact 연결 |

## 계약·검증

각 영역의 [[Frontend 최종 개발 계획]], [[Backend 최종 개발 계획]], [[DB 최종 개발 계획]], [[Storage 최종 개발 계획]]과 [[설계 충돌 정정 및 ADR]]을 입력으로 사용한다. 생성 계약은 소비자 검토 후 구현한다.

AC-09: Prompt 100건 유효율 99%, 코딩 과제 30건 성공률 70% 목표, 누출 0

필수 증거: golden eval·분류별 성적·금지 행동 시험. 성공 수·전체 수·실제 명령·종료 코드·측정 환경을 기록한다. 실패가 있으면 [[오류 및 해결 인덱스]]에 재현과 해결을 연결한다.

## 공통 완료·인계

모든 작업에 init → 구현·검증 → commit → push → CI build → Obsidian report → reviewer 인계를 적용한다. API/상태/저장소 변경은 영향받는 Agent가 같은 계약 버전을 읽었는지 확인한다. 날짜별 기록은 [[개발 과정 기록 템플릿]]을 사용한다. 제품 기능 검증 전에는 이 계획의 checkbox나 task status를 done으로 바꾸지 않는다.
