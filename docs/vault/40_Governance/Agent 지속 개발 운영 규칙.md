---
doc_id: "GOV-CONTINUITY-001"
title: "Agent 지속 개발 운영 규칙"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-21T14:05:43+09:00"
source_of_truth: "Git"
---

# Agent 지속 개발 운영 규칙

사용자의 2026-09-11 지시를 적용한다. **매 작업에서 읽기 → 작업 → 확인 → 다음 진행 기록**을 반복한다. [[전체 개발 진행 현황]]이 공통 현재 요약, [[Codex 작업 현황]]·[[Claude 작업 현황]]·[[Gemini 작업 현황]]·[[Orca 작업 현황]]이 현재 후속 카드다. 최초 설계/48개 task/ADR은 범위·합격 조건 정본이며 진행판이 이를 임의 변경하지 않는다.

## 1. 작업을 시작할 때

1. AGENTS.md, 자신의 진입 지침, 공통 진행판과 자기 작업판, 관련 계약/최근 History를 읽는다. doc ID/version·KST·git status·branch/base SHA를 기록한다.
2. 작업 branch가 오래됐으면 다른 Agent 파일을 덮어쓰기 전에 최신 문서 revision을 확인한다. Obsidian의 `00_Index/전체 개발 진행 현황.md`에서 최신 배포본을 읽고 Git source commit과 비교한다. 오래된 worktree의 vault 전체를 새 vault 위에 export하지 않는다.
3. 자기 ready 카드 하나를 선택하고 수신 확인과 in_progress 전환을 기록한다. owner/reviewer/부모 task·선행·합격 증거·변경 경로를 고정한다. 다른 Agent가 하고 있다고 추정하여 상태를 바꾸지 않는다.
4. 사용자에게 이미 승인받은 구현/로컬 검증/일반 전달을 반복 확인하지 않는다. 차단 항목의 이유와 해소 담당을 기록하고 가능한 다른 ready 카드를 진행한다. 계정/키/운영 권한/실장비 조치는 실제 승인·환경 범위를 확인한다.

## 2. 작업하고 확인할 때

구현 → 관련 로컬 검증 → commit → push → 동일 코드 SHA CI → Git 보고서 → Obsidian → 독립 검토/인계를 따른다. 아래 상태를 각각 남긴다.

| 구분 | 남길 값 |
|---|---|
| 구현 | 코드 SHA·scope·변경 계약 버전 |
| 로컬 검증 | 명령·exit code·case/환경·실제 Evidence, skip/한계 |
| CI | run ID/URL·head SHA·실제 시작/성공/실패 이유 |
| 독립 검토 | 작성자와 다른 reviewer, finding·해결 SHA·판정 또는 pending |
| 운영 인수 | 실제 대상 Node/계정/이미지/기간·표본·결과 또는 미수행 |
| 전달 | push 결과·보고서 ID·Obsidian check/apply/check·hash·next owner |

planned/ready/in_progress/review/blocked/done은 작업 상태다. done은 그 카드에 요구된 구현·선행·검증·push·CI·보고서·교차 검토·운영 인수를 모두 충족한 경우만 쓴다. 환경 제약이 있는 카드는 어떤 단계만 끝났는지 쓴다. HTTP accepted/Node online/문서 검사/파일 존재를 실행 완료로 올리지 않는다.

## 3. 작업 후 반드시 남길 기록

자기 작업판의 최신 기록을 갱신하고 상세 내용을 `30_Development/History`에 새 기록으로 추가한다. 오류는 별도 페이지와 오류 인덱스에 연결한다. 공통 진행판에는 한 줄 요약·상태·다음 담당을 반영한다.

```text
task/card ID / 부모 task / owner / reviewer:
KST / 읽은 진행판 doc ID·version:
branch / base SHA / implementation SHA / report SHA:
작업한 것:
확인한 것: 명령, exit code, 실제 환경, Evidence 링크
CI: run ID·head SHA·시작/결과·차단 사유
독립 검토 / 운영 인수:
남은 문제 / 차단 해소 담당:
이어서 할 카드 / 실행 가능한 첫 행동 / 다음 담당:
PR / History / 오류 링크:
Obsidian: check → apply → check, pending/conflict·파일 hash 확인
```

관측하지 않은 결과는 unknown/미수행, 연락하지 않은 인계는 수신 확인 대기다. 실제 자동 실행 서비스/예약 작업을 만들지 않았다면 자동으로 Agent가 실행 중이라고 쓰지 않는다. 이 규칙은 각 세션의 지속 재개 절차다.

## 4. 공통 페이지 충돌과 집계

- 각 Agent는 자기 작업판·자기 History를 소유한다. 다른 Agent의 완료/검토 상태를 대신 확정하지 않는다.
- 공통 진행판 집계 owner는 Orca 역할이며 실제 관리 세션이 없으면 Codex가 맡는다. 사용자 전체 개발 확인 요청 시 교차 소스를 대조해 초기 배정/집계를 갱신할 수 있으나 작성자의 실제 수신/착수와 구분한다.
- 동시에 바뀐 공통 행은 최신 Git commit을 확인해 병합한다. 통째로 덮어쓰기·과거 기록 삭제·Obsidian 충돌 강제 해제는 금지한다.
- 오래된 branch에서 자기 작업을 끝낸 Agent는 최신 진척을 History/자기 작업판 commit으로 제출한다. 집계 담당이 최신 문서 기준에 합친 뒤 전체 vault를 export한다. Obsidian 외부 편집은 제안으로 보존하여 Git에 반영한다.
- 각 작업 종료·인계·중단 직전 갱신한다. 오랜 작업은 중간 검증 단위에서 갱신한다. 정기 자동 감시가 이미 실행 중이라는 의미는 아니다.
- 새 기능의 정본을 바꾸기 전에 기존 계약/reader/DB 표현을 확인한다. ResultView·binding·handoff 같은 개념을 별도 구현으로 다시 만들지 않는다.

## 5. 문서가 오래된 branch에서의 진입

공유 조회 경로는 `C:\Users\egpar\OneDrive - Inviz\15.Vibe Cording\Obsidian\SaintVision-Invion\00_Index\전체 개발 진행 현황.md`다. 파일이 없다면 Git의 최신 진행 문서 commit을 찾아 읽는다. 이 초기 진행판은 `agent/codex/workspace-bridge`에 전달하며 이후 병합 위치는 최신 인계 기록을 따른다. 최신 문서를 읽었다는 사실과 제품 코드를 통합했다는 사실은 다르다.

## External memory references

Obsidian-style wiki links are reserved for pages stored under `docs/vault`. Agent memory files outside the repository are not vault pages: refer to them as inline-code literals with the `memory:<slug>` prefix, and label them as external. Do not use wiki-link syntax for those references; `check_docs.py` validates wiki links against repository files only.

For PowerShell-generated documentation, do not pipe non-ASCII source literals into a native process while `$OutputEncoding` is `us-ascii`. Resolve page paths/stems from Git or filesystem metadata, or use an explicitly UTF-8-safe file/API path, then run `tools/check_docs.py` to validate the resulting target.
