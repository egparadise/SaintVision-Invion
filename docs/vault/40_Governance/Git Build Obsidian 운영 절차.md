---
doc_id: "GOV-GIT-001"
title: "Git Build Obsidian 운영 절차"
version: "1.1.1"
status: "baseline"
author: "Codex"
updated: "2026-09-11T17:15:06+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["saintvision", "final-plan"]
---

# Git Build Obsidian 운영 절차


## 정본·브랜치

origin은 **https://github.com/egparadise/SaintVision-Invion.git**이다. 최초 원격 refs를 확인해 기존 이력이 있으면 clone하고, 비어 있으면 main을 초기화한다. 최초 문서 기준선 이후 각 작업은 `agent/{codex|claude|gemini}/{task-id}`를 사용한다. main 통합은 교차 검토와 필수 build를 전제로 한다. force push는 기본 금지다.

## 단계 절차와 증거

매 작업은 [[전체 개발 진행 현황]]과 자기 작업판을 읽는 것으로 시작하고, 작업·검증·다음 카드/첫 행동/담당을 갱신한 뒤 끝낸다. 상세 절차와 오래된 branch의 안전한 문서 집계는 [[Agent 지속 개발 운영 규칙]]을 따른다.

| 단계 | 수행 | 증거 |
|---|---|---|
| init | 현재 지침·원격·권한·git status·base SHA·TaskCard 확인 | 시작 시각, Agent, task, branch, 범위 |
| 구현·검증 | 범위 내 수정, 관련 계약·실패·복구 검증 | 명령, 종료 코드, 결과 경로 |
| commit | 변경 파일을 명시해 stage, diff 확인, 커밋 | implementation SHA |
| push | 지정 origin의 작업 브랜치로 push | remote·branch·반환 결과 |
| CI build | 동일 SHA의 문서/제품 pipeline 확인 | run ID·URL·상태·Artifact |
| report | Git 정본 개발 과정·오류/해결·인계 갱신 후 Obsidian 동기화 | report doc ID·SHA-256·실제 동기화 결과 |
| 검토·인계 | reviewer 확인, 다음 담당자 연결 | 검토자·결과·next task |

보고서는 코드 SHA를 참조한다. 보고서 후속 commit은 코드 SHA의 검증 결과를 기록한다. 자기 SHA를 본문에 넣고 다시 커밋하는 무한 루프를 만들지 않는다. 후속 보고서 commit도 CI가 검사하며 CI 자체 기록이 마지막 보고서 커밋의 증거다.

2026-09-18부터 push workflow는 `main`과 `integration/all-agents-unified`에서만 자동 실행된다. 개인 Agent branch push 자체는 CI 증거를 만들지 않으며, 개인 변경은 PR을 열거나 갱신해 동일 SHA의 PR workflow를 실행해야 한다. 따라서 `push → CI build` 절차의 CI 증거 위치만 PR 시점으로 이동했고, 구현 완료·인계 판정에 CI run ID와 상태를 요구하는 규칙은 유지된다. 개인 branch push가 성공했다는 사실을 CI 통과로 기록하지 않는다.

## 현재 사용 가능한 명령

```powershell
python tools/check_docs.py
python tools/check_ontology.py
python tools/sync_obsidian.py --check
python tools/sync_obsidian.py --apply
git status --short
git diff --check
git push -u origin <작업브랜치>
gh run list --repo egparadise/SaintVision-Invion --limit 5
```

`check_ontology.py`는 `requirements-docs.txt` 환경이 필요하다. 현재 CI는 문서·추적표·Ontology 검증을 수행한다. 제품 코드가 없는 상태에서 `product build passed`라고 표시하지 않는다. 향후 Backend pytest, Go test/build, Frontend typecheck/test/build, 통합·보안·장애 시험을 기능 구현과 함께 추가한다.

## Obsidian 동기화

`docs/vault`만 내보내고 `.obsidian` 설정·미관리 파일은 건드리지 않는다. 최초 기존 파일은 캡처한 원문 hash와 일치할 때만 안내문을 추가한 사본으로 갱신한다. 이후 마지막 export hash와 다른 Obsidian 파일을 발견하면 전체 쓰기 전 중단한다. Obsidian의 수정을 변경 제안으로 Git에 수동 반영하고 재검증한다. 충돌 자동 덮어쓰기·폴더 삭제·양방향 자동 병합은 하지 않는다.

동기화 state는 로컬 `.work/obsidian-sync-state.json`에 둔다. 새 환경은 `--adopt-identical`로 현재 Git 사본과 정확히 일치하는 파일만 인수한다. 모든 쓰기는 지정 vault 내부 경로를 확인하고 파일별 임시 파일 후 원자 교체한다. OneDrive 동시 편집 충돌 시 보존된 원문과 hash로 복구한다.

## 실패·재시도

push, CI, sync 실패 시 완료 상태를 내리지 않는다. 네트워크 제한은 필요한 환경 승인을 요청하고, 자격 증명이 없으면 민감값을 출력하지 않고 해당 단계만 blocked로 기록한다. 외부 호출의 성공 여부가 불명확하면 원격 refs/run을 먼저 조회해 중복 실행을 막는다.
