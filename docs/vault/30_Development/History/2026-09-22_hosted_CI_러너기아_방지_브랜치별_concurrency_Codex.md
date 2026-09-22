---
doc_id: "HIST-CODEX-HOSTED-CI-RUNNER-STARVATION-001"
title: "hosted CI 러너 기아 방지 — 브랜치별 concurrency와 Core opt-in 정책"
version: "1.0.1"
status: "active"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-22T19:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["ci", "github-actions", "concurrency", "core-build", "runner", "governance"]
---

# hosted CI 러너 기아 방지 — 브랜치별 concurrency와 Core opt-in 정책

## 관측과 원인

2026-09-22 integration tip `3d1892c0`의 Core Build가 20분 이상 `pending`이며 jobs 0으로 머물렀다. 같은 시간 PR/Agent branch 네 곳의 Core Build가 hosted runner를 사용하고 있었고, 코디네이터가 이미 병합된 branch run을 취소하자 integration Core가 즉시 시작했다. integration 내부의 `cancel-in-progress: false`는 증거 보존에는 맞지만, 무거운 Core를 모든 PR update에서 자동 실행하면 공유 branch가 러너를 얻지 못한다.

## 변경

- 다섯 workflow(Backend, Core, Frontend, Desktop Browser, Documentation)의 concurrency group은 `github.workflow + github.ref`다.
- `main`과 `integration/all-agents-unified`는 진행 중 증거를 취소하지 않는다. PR merge ref와 수동 실행한 Agent branch는 같은 ref의 새 run이 오래된 run을 취소한다.
- Core PR event는 `opened`, `synchronize`, `reopened`, `labeled`를 받되, job은 `run-core` label이 있을 때만 실행한다. label 없는 PR의 workflow/job skip은 Core 통과 증거가 아니다.
- Core는 `workflow_dispatch`와 `main`/`integration/all-agents-unified` push에서 항상 실행한다. Backend·Documentation·Frontend·Desktop Browser의 PR 자동 실행은 유지한다.
- GitHub repository에 `run-core` label을 만들었다. 개인 branch push 자체는 CI 증거로 세지 않고 PR 또는 공유 branch run ID·SHA·결론을 기록한다.

정본 운영 절차는 [[Git Build Obsidian 운영 절차]] v1.1.3의 `hosted runner 기아 방지와 브랜치별 concurrency` 절이다.

## 검증

| 검증 | 결과 |
|---|---|
| `actionlint` 발견 여부 | 이 호스트 PATH에 없음. 실행했다고 주장하지 않는다 |
| YAML 파싱 + 정책 불변식 | PyYAML `BaseLoader`로 5 workflow 파싱, group/cancel 식, Core push branch·PR event·label 식, Backend/Docs/Frontend PR trigger 대조 — **exit 0** |
| `python tools/check_docs.py` | 최종 R1 후보에서 **exit 0** |
| `python tools/check_ontology.py` | **exit 0**, 48 task mappings·SHACL/competency query 통과 |
| `git diff --check` | **exit 0** |

대형 pytest/Vitest/Docker build는 workflow 트리거 정책 변경의 직접 검증이 아니고 메모리 여유도 낮아 실행하지 않았다. 실제 GitHub 문법·스케줄링 증거는 개인 branch push를 통과로 오인하지 않고, integration R1 착지 뒤 생성되는 workflow run으로 확인한다.

## 교차 검토 선처리

카드 진행 중 코디네이터 신호에 따라 PR #41 재검토, PR #46 docs report-only 배선, PR #44 보안 헤더를 먼저 검토했다. PR #41은 수정 반영 뒤 승인했고, PR #46은 hosted docs run과 artifact까지 확인해 승인했으며 `docs.yml` 충돌을 피하려고 PR #46 선병합 뒤 이 카드 재기반을 요청했다. PR #44는 실제 browser/container hosted 결과를 근거로 승인했으나 최신 integration rebase가 필요하다. 각 판정 URL과 세부 근거는 coordinator escalation에 남겼다.

## 착지 후 acceptance 관측

- 정책 본체는 integration `a7f2ecf2`에 착지했다. 이 push의 Core run [35711782206](https://github.com/egparadise/SaintVision-Invion/actions/runs/35711782206)은 jobs 0 pending 상태에서 다음 integration push `f2aa2b14`가 같은 group의 pending 슬롯을 교체해 `09:47:54Z`에 취소됐다. 코디네이터가 취소한 run이 아니며, GitHub concurrency가 같은 group에 pending run 하나만 유지하는 동작이다.
- 그때 이미 실행 중이던 이전 integration Core [35711291031](https://github.com/egparadise/SaintVision-Invion/actions/runs/35711291031)은 취소되지 않고 `09:36:41Z`부터 `09:57:54Z`까지 완주해 success했다. 즉 새 정책이 요구한 `main`/integration의 **in-progress 증거 보호**는 실제로 확인됐다.
- acceptance 대상 `f2aa2b14` Core run은 [35712413499](https://github.com/egparadise/SaintVision-Invion/actions/runs/35712413499)다. `09:47:53Z`에 생성되어 이전 integration Core가 끝난 3초 뒤인 `09:57:57Z`에 core job이 시작했다. 대기는 다른 PR Core가 러너를 점유해 생긴 기아가 아니라 공유 integration run의 의도적 직렬화였으며, 선행 run 해제 직후 jobs 0에서 실제 job으로 전환됐다.
- 이 acceptance run은 스케줄링 목적은 충족했지만 `10:03:33Z`에 **failure**로 종료했다. 실패 지점은 `Verify Docker API negotiation and actual bounded execution`의 `TestDockerLiveCompatibility/isolation`이며 `NODE-0027: execution uncertain; no stop receipt or automatic retry`였다. concurrency/트리거 문법 실패가 아니므로 본 카드의 스케줄링 판정과 분리해 후속 Core 소유 triage로 넘긴다.
- 이 문서 후속 push도 Core를 다시 촉발하지만 문서 기록을 위한 정상 비용이다. 후속 run이 pending 슬롯 교체로 취소되더라도 위 `f2aa2b14` run의 시작 증거에는 영향이 없다.
