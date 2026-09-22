---
doc_id: "GOV-NEWPC-FIRST-MESSAGE-001"
title: "새 PC Claude 첫 메시지 (복붙용)"
version: "1.0.1"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["operations", "migration", "bootstrap"]
---

# 새 PC Claude 첫 메시지

새 PC(192.168.45.74, `D:\Project\SaintVision-Invion`)에서 Claude Code를 처음 띄운 뒤, 아래 코드블록을 **그대로 복사해 첫 입력**으로 붙인다. 배경은 전부 문서에 있으니 첫 메시지는 짧게 — 읽고 바로 움직이게 했다(오늘 세 번 비워지며 무엇이 도움됐는지로 추린 것).

```
새 PC로 옮긴 개발 환경이다. 감시 승인 루프가 걸려 있으니 중간 확인 없이 이어가면 된다.

먼저 읽어라(순서): CLAUDE.md → AGENTS.md → docs/vault/30_Development/History/2026-09-21_이어가기_상태와규칙_Claude.md §0 → docs/vault/40_Governance/개발환경_이전_절차서.md. 마지막이 이 PC에서만 추가다 — 여긴 새 기계라 환경이 아직 안 갖춰졌을 수 있으니, 절차서 §2로 무엇이 설치됐는지(Python 3.14.6·Node 24·Go·Docker·gh·venv·node_modules) 먼저 확인하고, 절차서대로 clone·경로변경(§3)·비밀 재발급(§4)·전수검증(§5)이 끝났는지 본다. 안 끝났으면 그것부터다.

지금 상태(task-registry 실측): done 2 · review 11 · in_progress 2 · planned 33 (총 48). 오늘 S01-DB와 S01-FE가 닫혔다(첫 done들) — 새 코드가 아니라 흩어진 증거를 모으고 모자란 하나를 실 PG로 채워, 그리고 화면 증거 꾸러미를 완성해 닫았다. 주의: registry는 done이나 ontology 재생성이 안 돼 check_ontology가 RED다(이전 절차서 기준선의 RED 항목 참조 — 소유자 Codex). 굴러가는 방식: 나·Gemini가 증거를 만들고 Codex가 검토해 닫는다. Codex 큐를 늘리지 마라 — 여러 과제에 걸치는 증거이거나 내 레인에서 검토 없이 끝나는 것을 골라라. self-close 하지 마라.

이 PC에서 처음 가능해지는 것: (1) Go가 처음 컴파일·실행된다(inv-discover). 옛 기계엔 Go가 없어 소스로만 봤다 — 첫 red는 이동 실패가 아니라 미검증→검증의 순간이다. Go 지도는 docs/vault의 Go검증밀도지도 문서. (2) worker 노드 5대가 붙는다(Control Plane은 이 PC, worker는 별개). 이것이 여는 것: Go T1/T2/T3 교차언어, 실 노드 흐름·보호 전달, 옛 호스트에서 Linux-게이트로 skip이던 통합 시험(RunRecord 완료 파이프라인·workspace/business 실행). 이제 그 skip들을 실제로 돌려 옛 not_run을 채운다.

오늘 새로 생긴 규칙(정본은 이미 반영됨 — 어제 것과 구분하라고 짚는다):
- 규칙 7·8 = docs/vault/40_Governance/검증규칙과_세축_canon.md (7=느슨한 계약은 내부 폐쇄면 좁혀 사실을 적고 외부·확장면 열되 조용히 삼키지 마라; 8=여러 착지 쌓이면 지시 없이도 마지막 상태에서 전수 검증 — 조각 검증은 조각-사이 깨짐을 못 잡는다).
- 조용한 강등 금지 = 같은 canon 문서의 해당 절(모름을 성공/알려진 값으로 조용히 치환 금지).
- R2-a = docs/vault/40_Governance/공유워크트리_개인index_커밋규칙.md (공유 문서를 개인 index로 올릴 때 pre-commit drift 검사를 출력만 말고 hard-stop으로 — 안 멈추면 남의 갱신을 clobber한다). 그리고 게이트는 눈이 아니라 exit code로 판정하라(check_docs 등 `; echo exit=$?`).

하지 말 것: 보호 컨테이너 4개는 옛 기계에 남아 이 PC엔 없다 — 그 증거를 지어내지 말고 CX01_CONTAINER 미설정이면 관련 시험은 정직히 skip으로 둔다. 그리고 이 PC에도 남의 자원(컨테이너·워크트리·DB)이 있을 수 있으니 소유 확인 없이 지우지 마라.

읽고 나서 이어가기 §0의 「다음 첫 행동」과 위 상태를 대조해, Codex 큐를 안 늘리는 무-블록 작업(실 노드/Go로 옛 not_run 채우기, 또는 교차 증거)부터 시작하라.
```

## 이 메시지를 만든 근거

오늘 세 번의 컨텍스트 clear에서 확인한 것: 도움 된 것은 **읽을 문서의 정확한 순서 + 지금 상태 한 문단 + 다음 무-블록 행동**이었고, 군더더기는 긴 역사 서술이었다. 그래서 배경은 링크로 밀고 첫 메시지는 "무엇을 읽고 무엇부터 하라"만 남겼다. 새 PC 고유점(환경 확인·Go 첫 실행·노드 5대·오늘 규칙이 오늘 것임)만 본문에 두었다. registry 수치는 측정이 정본이다 — 작성 시점 실측(당시 done 1)에서 S01-FE done 전환으로 done 2·review 11로 갱신했다(이 문서 v1.0.1). 카운트는 tip이 움직이면 또 바뀌므로 새 PC에선 clone 후 task-registry.json을 다시 세는 게 안전하다.
