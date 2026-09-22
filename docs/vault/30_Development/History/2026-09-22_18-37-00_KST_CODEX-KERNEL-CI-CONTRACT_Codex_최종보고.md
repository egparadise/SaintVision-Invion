---
doc_id: "HISTORY-2026-09-22-CODEX-KERNEL-CI-CONTRACT-FINAL"
title: "Codex 커널·계약·CI 레인 최종 보고"
version: "1.0.1"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-22T19:32:44+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "d01c931acf2127377a7cdc665ef3eee5f0402fe9"
tags: ["Codex", "CI", "contracts", "PostgreSQL", "serving-anchor", "model-retry"]
---

# Codex 커널·계약·CI 레인 최종 보고

## 식별과 범위

- Orca task `task_84d2b7804299`, dispatch `ctx_569f7a1e1869`, branch `integration/all-agents-unified`.
- 새 PC Windows 11, Python 3.14.7 `.venv`, PostgreSQL 16 `127.0.0.1:55432`, Node 24.10, Go 1.27.
- 소유 범위: 커널·계약·CI machinery. Gemini/Claude 소유 red는 파일을 고치지 않고 코디네이터에게 귀속했다.
- 코드 착지: `881f2911`, `1312e295`, `eceac8cf`, `dcf2b94`, `51d53b7f`, `2aa80899`, `2e803cd6`, `4b2204d7`, `7509f667`, `33283867`, `9f1c0fcc`, `563c54ce`.
- reviewer 착지: S02-DB/S03-DB를 review로만 승격한 `3882496d`.

## 1. CI 첫 실행과 귀속

기준선 `d01c931a`의 실제 hosted 실행은 Documentation [35688813795](https://github.com/egparadise/SaintVision-Invion/actions/runs/35688813795) success, Backend [35688813798](https://github.com/egparadise/SaintVision-Invion/actions/runs/35688813798) failure, Core [35688813794](https://github.com/egparadise/SaintVision-Invion/actions/runs/35688813794) failure, Desktop Browser [35688813838](https://github.com/egparadise/SaintVision-Invion/actions/runs/35688813838) failure였다. Frontend는 기준선 push가 path filter 밖이라 자동 실행되지 않았고 이후 동일 SHA 수동 dispatch machinery를 확인했다.

- Codex: schema export drift, core dependency·skip ratchet, credential fail-closed/portable fixture, CI concurrency, Docker already-absent cleanup, migration child diagnostics, LAN starting readiness 순서를 수정했다.
- Gemini: Desktop/Studio 브라우저 3건과 Ubuntu locale 2건을 인계받아 수정했다. 보정 descendant `d651a52f`의 Desktop Browser [35710556600](https://github.com/egparadise/SaintVision-Invion/actions/runs/35710556600)과 Frontend [35710556480](https://github.com/egparadise/SaintVision-Invion/actions/runs/35710556480)은 success다.
- Core [35706465645](https://github.com/egparadise/SaintVision-Invion/actions/runs/35706465645)는 `3d1892c0`에서 LAN installer, 전체 core pytest, Docker hygiene, control-plane build, Go, TypeScript 전 단계 success다.
- Backend [35706465869](https://github.com/egparadise/SaintVision-Invion/actions/runs/35706465869)은 `3d1892c0`에서 success다.

## 2. EvidenceEnvelope와 docs gate

실 PostgreSQL에서 `results`, `runs`, `shard_completion`, `storage_commit`, `storage_view` 다섯 site에 invalid `EvidenceEnvelope`를 넣어 실제 서빙 직전 거부를 고정했다. 결과는 5 passed/0 skipped이며 다섯 site가 `no-serving-test`에서 `rejection-tested`로 증가했다. WorkloadSpec은 응답이 아니라 입력 경계이므로 이 수치에 합산하지 않았다.

`docs.yml`에는 `PYTHONUTF8=1`, `check_contract_bindings`, `check_frontend_integrity`를 exit-code gate로 배선했다. fixture reachability는 runtime 10/circular 29/schema-only 11/unreferenced 0을 보고하지만 의미론적 producer reachability를 증명하지 않으므로 report-only를 유지했다.

## 3. 결정 #2와 #5

- #2: capability별 `NodeResourceUsageResponse`; 미측정은 null이며 서로 다른 단위의 평면 합계를 만들지 않는다.
- #5: artifact 다운로드 정본은 storage object bytes와 `X-Content-SHA256`이다.

JSON Schema, Python/TypeScript/Go 생성 타입, fixture와 focused 계약 9건을 `eceac8cf`에 착지했다. Node resource usage route `3d1892c0`의 인가·신선도·`released_at IS NULL` lease 집계·RES-0010/0011을 교차검토했고 finding은 없다.

## 4. 결정 #6a 모델 재시도 HTTP 계약

승인된 경로는 일반 Run retry가 아니라 `POST /v1/projects/{project}/runs/{parent}/model-retries`다. `can_request`, `Idempotency-Key`, failed terminal parent, 새 child/placement/lease/lineage, `requiresFrozenInputAndApproval=true`를 강제한다. 같은 key+payload는 같은 child를 반환하고 다른 payload는 409 `ProblemDetails`; `nodeIds`와 `ttlSeconds`는 선택이며 TTL 기본값은 30초다. 이전 command/permit/frozen input/approval은 재사용하지 않는다.

`563c54ce` clean tree 결과:

| 검증 | 결과 |
|---|---|
| focused contract/config/route pytest | 68 passed, exit 0 |
| 실 PostgreSQL HTTP serving/replay/conflict/invalid-response | 1 passed/0 skipped, exit 0 |
| `check_contract_bindings.py` | 51 fixtures, 16 response types, 19 sites, exit 0 |
| `check_anchor_weight.py --modules app` | 3 rejection-tested, 0 gaps, report-only exit 0 |
| contract regeneration drift | 0, exit 0 |
| Go build/vet/test | exit 0 |
| TypeScript strict | exit 0 |
| docs/frontend/ontology/ratchet | 모두 exit 0 |

Frontend path filter는 현재 실제 의존 뿌리 `apps/web/**`와 `contracts/**`를 모두 덮는다. `563c54ce`가 contracts를 변경해 Frontend [35710325340](https://github.com/egparadise/SaintVision-Invion/actions/runs/35710325340)이 실제 실행·success했으므로 live dependency 구멍은 없고 필터를 제거하지 않았다. 문서-only 최종 SHA의 all-five 측정에는 `workflow_dispatch`를 사용한다.

## 5. 독립 검토와 후속 카드

Claude 독립 검토의 F-A(manifest catch 범위)와 F-B(`failedCaseIds`)는 `33283867`에서 좁은 예외 분류와 비밀 비노출을 유지해 보정했다. S02-DB/S03-DB는 증거 묶음이 독립 검토 가능한 상태여서 `review`만 수용했으며, 실 IdP·물리 Node·실 컨테이너 금지 명령/출력·선행 카드가 남아 `done`과 전체 AC 충족 주장은 금지했다. 상세는 [[2026-09-22_18-27-37_KST_S02-DB_S03-DB_Codex_독립검토]]다.

## 6. 동일 SHA hosted CI 최종 완주

최종 문서 SHA `f2aa2b1485fef76beaa8179537a0900d08a2e34c`를 가리키는 integration 실행과 고정 proof branch 수동 실행을 합쳐 다섯 workflow를 같은 SHA에서 모두 success로 확인했다.

| workflow | run ID | trigger/ref | conclusion |
|---|---:|---|---|
| Backend Build | [35714785554](https://github.com/egparadise/SaintVision-Invion/actions/runs/35714785554) | workflow_dispatch / `agent/codex/f2aa-ci-proof` | success (Python 3.12, 3.14) |
| Core Build | [35714470445](https://github.com/egparadise/SaintVision-Invion/actions/runs/35714470445) | workflow_dispatch / `agent/codex/f2aa-ci-proof` | success |
| Desktop HTTP Browser Acceptance | [35712413553](https://github.com/egparadise/SaintVision-Invion/actions/runs/35712413553) | push / `integration/all-agents-unified` | success |
| Documentation Build | [35712413561](https://github.com/egparadise/SaintVision-Invion/actions/runs/35712413561) | push / `integration/all-agents-unified` | success |
| Frontend Build & Test | [35712428159](https://github.com/egparadise/SaintVision-Invion/actions/runs/35712428159) | workflow_dispatch / `integration/all-agents-unified` | success |

최초 Core [35712413499](https://github.com/egparadise/SaintVision-Invion/actions/runs/35712413499)는 Docker isolation 단일 subcase에서 `NODE-0027`로 failure였고 attempt 2는 후속 integration concurrency 때문에 cancelled됐다. 같은 코드의 후속 integration Core [35713565774](https://github.com/egparadise/SaintVision-Invion/actions/runs/35713565774)와 고정 SHA Core `35714470445`가 모두 해당 Docker 단계와 전체 job을 success해 재현되지 않았으므로 runner Docker inspect transient로 분류했다. 최초 Backend `35712413514`의 Python 3.12 job이 Tests에서 비정상 장기 실행되어, 같은 SHA 고정 proof run `35714785554`의 두 Python job success를 최종 증거로 사용했다.

## 남은 경계와 다음 행동

- 작성자 self-close를 하지 않는다. Claude review·운영 인수·실장비 경계는 별도다.
- 동일 SHA 다섯 hosted workflow 완주는 위 run ID로 고정했다. 작성자 self-close 없이 Claude 독립 검토와 운영 인수를 기다린다.
- 다음 fresh dispatch의 첫 행동은 model-retries 타 tenant 요청이 503 `SYS-0001`로 새는 F1을 정직한 4xx `ProblemDetails`로 보정한 뒤 VF-CL-02(c) project-scoped 커널 라우트를 착지하는 것이다.
