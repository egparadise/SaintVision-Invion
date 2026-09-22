---
doc_id: "HIST-CLAUDE-S03-DB-CONTAINER-EVIDENCE-COLLECTOR-001"
title: "S03-DB 제한 컨테이너 출력·거부·lease 회수 Evidence collector(tools/collect_container_evidence.py) — DB 레인(원장 C1~C4) + 컨테이너 레인(sandbox plan P1~P4 실측), 자기시험 20 실 PG·Docker, 미측정 정직 표기 (카드 s)"
version: "1.1.1"
status: "active"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-23T00:40:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["S03-DB", "container", "sandbox", "lease", "evidence", "collector", "real-postgres", "docker", "codex-review"]
---

# S03-DB 컨테이너 출력·거부·lease 회수 Evidence collector (카드 s)

[[2026-09-22_21-55-00_KST_review_done_차단지도_Codex]] "Claude 몫 2순위". 양식은 `2026-09-22_S02-DB_RLS_인증경계_Evidence_collector_Claude.md`(PR #68, 병합 전)와 동일(JSON+MD, 비밀 0, 재실행 1줄, 자기시험, 일회용 DB, exit code). 브랜치 `agent/claude/s03-container-evidence`, reviewer Codex. 계약 변경 없음, registry 불변(S03-DB `review` 유지).

## 1. 산출물

| 파일 | 내용 |
|---|---|
| `tools/collect_container_evidence.py` | **DB 레인**: `inv.runs`마다 lease(활성/회수·회수 근거 `stop_receipt`/`reservation_abort`), `tool_claims`, `execution_deliveries(last_error_code)`, `node_stop_receipts.content_hash`, `result_commitments`↔`storage_objects(content_hash,size_bytes,state)`, `evidence.envelope.outputSha256/result`, `result_completions`, `output_ingestions.last_error`, `approval_audit` phase 집계를 읽기 전용(READ ONLY 트랜잭션, 롤백)으로 수집. **컨테이너 레인**: `inv.sandbox.compile_launch`의 고정 plan(network none·read-only rootfs·cap-drop ALL·no-new-privileges·uid 65532·pids-limit 64)을 그대로 `docker run` 플래그로 걸고 프로브 4개(P1 출력 바이트/sha256 캡처, P2 rootfs 쓰기 거부, P3 TCP 연결 거부, P4 uid·CapEff) 실행. Docker/이미지 부재 시 `measured:false`+사유(이미지 pull 없음). 두 레인 모두 미측정이면 판정하지 않는다. |
| `tests/test_collect_container_evidence.py` | 순수 15(C1~C4·P1~P4 각각 강제, 미측정 불판정, python3 없는 이미지의 P3 미측정, **sandbox plan 미러가 커널 `compile_launch` 소스와 일치**, 0 runs 미측정 표기, 비밀 가드) + 실 PG 2(합성 원장 + 부정 대조군 + CLI exit code) + Docker 1(로컬 이미지 프로브) + 이미지 부재 1. |
| `docs/vault/30_Development/Evidence/container-boundary/container-disposable-head-20260922.{md,json}` | 이 PC의 표준 실행 산출물(§2). |

기대: C1 종단 run에 활성 lease 0 · C2 succeeded run은 evidence+completion이 있고 `outputSha256 == storage_objects.content_hash == commitment.content_hash` · C3 failed run에 성공 evidence/completion 없음 · C4 회수된 lease는 stop receipt 또는 abort 근거 보유 · P1 출력 바이트 정확 캡처 · P2 rootfs 쓰기 거부 · P3 네트워크 거부 · P4 uid 65532·CapEff 0. 재실행: `python tools/collect_container_evidence.py --disposable --container-image python:3.12-slim --out-dir docs/vault/30_Development/Evidence/container-boundary`(`INV_TEST_ADMIN_DSN`, 값 미기재) / 기존 DB: `INV_AUDIT_DSN=<owner dsn> python tools/collect_container_evidence.py --container-image <image> --out-dir <dir>`.

## 2. 실측 (2026-09-23 00:40 KST, PG 16.15 컨테이너, 일회용 DB, Docker 20.10.22, dev DB·타 프로젝트 컨테이너 무접촉)

| 항목 | 결과 |
|---|---|
| 자기시험 | v1.1.0: **25 passed**(실 PG 2·Docker 2 포함), 분리 1레인 |
| 표준 실행 `--disposable --container-image python:3.12-slim` | v1.1.0: **UNMEASURED exit 3**(위반 0이나 DB 레인 run 0) — 컨테이너 레인 4 프로브 + bridge 대조군 측정 |
| DB 레인 | 일회용 head DB에 run 0 → "**no runs observed** — output/hash/lease facts are unmeasured here". 이유: 실 run을 만드는 Linux private Node provider(`tests/integration/test_output_ingestion.py` 등, `skipif(platform != linux)`)는 이 Windows PC에서 실행되지 않는다. condition 줄에 기록. |
| 컨테이너 레인 | 이미지 `python:3.12-slim`(프로브용, 제품 node 이미지 아님). P1 exit 0, stdout 13B `5ea0daed…`/stderr 13B `043ddd62…`(기대 바이트와 sha 일치) · P2 exit 2 `Read-only file system` · P3 exit 3 `denied ConnectionRefusedError` · P4 `65532` / `CapEff: 0000000000000000` |
| 자기시험 합성 원장(실 PG) | 커널 트리거를 통과하는 합법 경로로만 seed: `guard_run`(draft→validated→planned→scheduled→running→verifying→[evidence]→succeeded; cancelled), `guard_reservation_abort`(cancelled+claim/attempt 없음일 때만 abort), `guard_storage_object`(uploading→ready), `storage_budgets` FK, evidence envelope CHECK(tenantId/runId/evidenceId/result). 결과: C1·C4 통과, **C2 2건 검출**("no completion", "evidence has no commitment") — 합성 원장은 commitment 체인(`result_commitments → execution_attempts → tool_claims → approval_dispatches`)을 실 Node 없이 만들 수 없으므로 이 검출이 **정직한 판정**이며 시험이 그것을 pin한다. 부정 대조군: 종단 run에 미회수 lease 삽입 → **C1 검출**, 삭제 후 사라짐. |
| 관찰(DB 불변식) | `lease_release_proof` CHECK(`released_at IS NULL ⇔ 근거 없음`, 회수 시 근거 정확히 1개)와 `guard_run`의 "success requires evidence"가 C4·C2(존재)를 **DB 층에서 이미 강제**한다 — collector의 C2 해시 대조·C1은 DB가 강제하지 않는 부분. `inv.evidence`는 immutable 트리거라 해시 드리프트는 순수 시험으로만. |

## 3. 정직 범위 / 남은 것 (self-close 없음)
- **실 run 원장 실측은 이 PC에서 미측정**. hosted Core(Linux)에서 `test_output_ingestion.py` 성공 경로 뒤 같은 DB에 collector를 돌리는 것이 다음 단계(`--dsn`), 또는 제품 Node가 붙는 S01/S02 이후 운영 DB 실행.
- 컨테이너 레인은 **sandbox plan 제약이 Docker에서 실제로 성립하는가**를 재는 것이지, 제품 node-agent 이미지의 금지 명령 정책(ToolGateway/`compile_launch`의 executables allowlist)을 재지 않는다 — 그것은 hosted Core container opt-in(`test_server_container`)과 Node runtime 인수 범위.
- Codex 검토 요청 사항: C2 판정이 commitment 부재를 위반으로 보는 것이 옳은지(운영상 succeeded run은 항상 commitment를 갖는가), 프로브 4개 외에 추가할 거부 항목(pids-limit 초과, seccomp).

## 4. Codex 검토 반영 (v1.1.0, PR #73 차단 finding 3건)

| # | Codex finding | 조치 | 검증 |
|---|---|---|---|
| F-73-01 | C2가 completion 존재만 보고 `evidence_id`를 대조하지 않음(false negative) | evidence마다 **같은 `evidence_id`의 completion·commitment**를 요구, 이 run의 evidence가 아닌 id를 가리키는 completion은 위반 | 순수 `test_c2_requires_completion_and_commitment_keyed_to_the_same_evidence`(completion→`evd_other` 2건 검출, commitment id 변경 검출) |
| F-73-02 | P3 loopback 거부는 network=none 증거가 아님(false positive) | 컨테이너 안 `/sys/class/net`==`["lo"]` · `/proc/net/route` 빈 표 · 외부 `192.0.2.1:9` connect==`ENETUNREACH` 세 신호 JSON 관측, 셋 다 성립해야 `isolated`. 같은 실행에서 **bridge 대조군** 자동 실행·기록(`control.isolated=False` 필수, 아니면 "non-discriminating" 위반) | `_isolated()` 단위 시험(ECONNREFUSED만으로 False), Docker 시험에 격리 해제 대조군(`network="bridge"` 전체 프로브 → P3만 FAIL). 실측: none=`{lo, [], ENETUNREACH}`, bridge=`{eth0+lo, route 2, TimeoutError}` |
| F-73-03 | DB run 0인데 JSON/최상단 PASS·exit 0 모순 | `verdict ∈ {PASS, VIOLATIONS, UNMEASURED}` + `unmeasured` 사유 목록(JSON·MD 최상단). run 0 또는 레인/프로브 미측정 → **UNMEASURED, exit 3**(PASS 금지) | 순수 `test_zero_runs_or_unmeasured_lane_is_unmeasured_not_pass`(verdict·JSON·MD 고정), CLI `--no-db` → exit 3. 표준 실행 exit 3 |

재실행(일회용 DB + Docker): 자기시험 **25 passed**, 표준 실행 `UNMEASURED: db=runs 0 container=measured 4 probes` exit 3. 기존 이 PC 한계(실 run 원장 미측정)는 이제 verdict 자체가 말한다.

## 5. hosted Backend 결함 수정 (v1.1.1)

`tests/test_cleanup_owned_docker_label_inventory.py::test_all_repository_docker_labels_have_an_explicit_cleanup_policy`가 collector의 프로브 라벨 `ai.saintvision.evidence`를 unclassified로 잡았다. `tools/cleanup_owned_docker.py` `OWNERSHIP_LABELS`에 등록(정책: 프로브 컨테이너는 `--rm`으로 실행 종료 시 제거되고, 남은 고아는 age-gated 정리 backstop 대상). 단일 파일 시험 통과.
