---
doc_id: "HIST-CODEX-2026-09-22-S06-S08-DB-OWNER-REVIEW"
title: "S06-DB·S08-DB owner 판정 — review 진입, done 차단 조건 유지"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-22T21:13:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "e31ce3f317d529142527c7e7e9f14f89551f3765"
task_ids: ["S06-DB", "S08-DB"]
tags: ["owner-review", "task-registry", "ontology", "real-pg", "hosted-core"]
---

# S06-DB·S08-DB owner 판정

## 결론

Codex는 AC-06/08, 선행 카드 상태, 기존 실제 PostgreSQL·Linux Docker 증거와 hosted Core JUnit을 다시 대조했다. 두 카드 모두 DB 구현과 실패 경계가 독립 reviewer에게 넘어갈 수준이므로 **`planned`에서 `review`로 진입**한다. 이는 acceptance 또는 outcome 완료 판정이 아니며, 아래 선행 카드·물리 환경·제품 결속 조건이 남아 있으므로 **`done` 전환은 금지**한다.

## AC와 증거 대조

| 카드 | review 진입을 지지하는 증거 | owner 판독 |
|---|---|---|
| S06-DB | Workspace resume 구현 `4f7d5d5b`는 실제 PostgreSQL·mTLS·Go/Docker/Git을 사용한 Core CI [34423762992](https://github.com/egparadise/SaintVision-Invion/actions/runs/34423762992)에서 846 passed·0 skip/fail이었다. 최신 hosted Core [35706465645](https://github.com/egparadise/SaintVision-Invion/actions/runs/35706465645)의 `saintvision-core-evidence`를 직접 판독해 `workspace-tests.xml` **22 passed·0 skipped/failed**, 전체 JUnit의 `test_workspace_resume` 11, `test_workspace_api` 11, `test_workspace_recovery` 12, `test_snapshots` 15가 모두 실행됐음을 확인했다. | 허용 파일 편집·실 Git commit, 응답 유실/CP 재시작 뒤 재실행 0, checkpoint/복원 hash·stale epoch·foreign scope 거부가 review 수준으로 연결된다. |
| S08-DB | Permission snapshot 구현 `9755c608`의 격리 PostgreSQL/Linux 증거는 permission observation 11 + operational readiness 10 + pilot 35 + 실제 복원 18 = **74 passed·0 skipped**다. hosted Core `35706465645` 전체 **2948 passed·58 skipped·0 failed**에서 permission observation 11, readiness 10, pilot 35, containment 28, audit 41이 모두 0 skip/fail이었다. Node runtime의 실제 제한 컨테이너는 Docker socket 부재를 확인했고, 복원 계열은 저장 bytes/hash·RLS·권한·definer 판정을 포함한다. | RLS·불변 감사·권한 snapshot·복원 판정의 DB 면은 reviewer가 검토할 수 있다. 다만 hosted `test_recovery_drill`은 1 passed·19 environment-gated skips였고, GPU 8건은 capability/placement 계약이지 물리 GPU 실행 증거가 아니다. |

hosted 수치는 artifact의 JUnit XML을 읽기 전용으로 파싱해 classname별 `testcase`와 `skipped`/`failure`/`error` 노드를 집계했다. 이 작업에서 제품 시험을 새로 실행하거나 과거 증거를 이번 실행으로 바꾸지 않았다.

## 선행 조건과 done 차단

- **S06-DB 선행:** S05-FE·S05-DB는 `review`, S05-BE·S05-ST는 `planned`다. 완료되지 않은 선행을 건너뛰어 S06을 done으로 만들 수 없다.
- **S06-DB 물리/제품:** 실제 원격 장비에서 WS/PTY·remote Git·CP/Node 재시작·복원 hash를 한 여정으로 인수하지 않았다. `WorkspaceRecovery`의 snapshot reader/checkout writer가 제품 route·worker에 연결되지 않은 상태도 남는다.
- **S08-DB 선행:** S07-FE·S07-DB는 `review`, S07-BE·S07-ST는 `planned`다.
- **S08-DB 물리/운영:** 실제 GPU workload 성공, 운영 승인 우회 0의 종단 인수, off-device/PITR·보존 기간·독립 역할 복원은 미완료다. hosted 복원 19건은 환경 전제 미충족으로 skip되어 과거 격리 Linux 18건을 hosted 재실행으로 확대하지 않는다.
- 두 카드의 registry 상태만 `review`로 바꾸며 outcome/acceptance 상태와 전체 진행률은 올리지 않는다.

## 적용 및 검증

- `docs/task-registry.json`: S06-DB·S08-DB의 `status`만 `planned` → `review`로 변경했다.
- `tools/generate_ontology.py`: 공용 Python에는 `rdflib`가 없어 최초 exit 1이었고, 정본 checkout의 `.venv` Python으로 재실행해 **405 schema triples / 916 data triples / exit 0**으로 네 ontology 산출물을 갱신했다.
- 착지 전 게이트: `check_docs.py` **804 documents / exit 0**, `check_ontology.py` **48 task mappings / exit 0**, `check_ontology_generation.py` **4 artifacts graph-equivalent / exit 0**, `check_doc_single_source.py --ratchet` **18 pairs / exit 0**, `git diff --check` **exit 0**.
- `sync_obsidian.py --check`는 이 Orca worktree의 네 파일(전체 진행판·Codex 작업판·ontology mirror 2개)이 destination과 `both-diverged`이고 신뢰할 baseline이 없어 **exit 3**이었다. 코디네이터 지침대로 `--apply`하지 않았으며, 정본 checkout에서 integration 착지 SHA 기준으로 동기화한다.
- 제품 시험은 재실행하지 않았고, 최종 R1 착지 SHA는 착지 후 이 문서에 기록한다.

## 다음 행동

Claude는 두 카드의 독립 reviewer로서 transaction·권한/RLS·복원 판정과 위 미충족 경계가 정확히 분리됐는지 검토한다. Codex는 실제 원격 Workspace reader 결속과 물리 GPU/독립 복원 환경이 준비될 때 차단 항목만 이어서 측정하며, 그 전에는 `review`를 유지한다.
