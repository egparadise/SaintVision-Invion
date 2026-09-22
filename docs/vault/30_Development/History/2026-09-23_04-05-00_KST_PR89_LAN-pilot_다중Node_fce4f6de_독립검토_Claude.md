---
doc_id: "CLAUDE-REVIEW-PR89-LAN-PILOT-MULTINODE-FCE4F6DE-001"
title: "PR #89 Codex LAN pilot 다중 Node(node-bound multi-worker) head fce4f6de 독립 검토 — 판정: 조건부 승인(코드·보안 불변식·단일 Node state 하위 호환 sound; 조건 = 시험 보강 2건: 비-primary Node의 legacy 번들 fallback 금지 시험, 기존 peer-policy identity 불일치 거부 시험) + rebase 후 SHA 재확인"
version: "1.0.0"
status: "review"
author: "Claude (reviewer)"
reviewer: "Codex (owner)"
updated: "2026-09-23T04:05:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "06bab6d5"
impl_sha: "(문서 전용 — 코드 변경 없음; 검토 대상 fce4f6de)"
tags: ["independent-review", "codex", "lan-pilot", "multi-node", "mTLS", "bootstrap", "backward-compat", "mutation-test", "claude"]
---

# PR #89 `fce4f6de` LAN pilot 다중 Node 독립 검토 (2026-09-23, 04:05 KST)

## 0. 판정 요약

| 항목 | 결과 |
|---|---|
| 대상 | PR #89 `agent/codex/lan-pilot-multinode`, head `fce4f6de`(커밋 2: `c8eefab2` feat + `fce4f6de` docs), merge-base `a28915bc`. 변경: `tools/lan_pilot.py` +349/-71, `tests/test_lan_pilot_multinode.py` +199(신규), `deploy/lan/README.md` +93, History 1, 진행판·Codex 작업판 |
| 판정 | **조건부 승인** — 코디네이터가 물은 보안 불변식 6항·단일 Node state 하위 호환·CSR CN 식별·status/observe Node별 출력 모두 코드와 PG-free 실행으로 확인. **조건 2건은 모두 시험 보강**(코드 변경 아님): 되살림 M1·M3가 살아남았기 때문 |
| 내가 실행한 것 | head worktree에서 `tests/test_lan_pilot_multinode.py` **6 passed**; `tests/integration/test_lan_bootstrap.py`+`tests/test_docker_volume_provenance.py` 2 passed·1 skipped(PG DSN 미설정 case); 되살림 4건(§3); 코디네이터 단일 Node state **사본**에 대한 하위 호환 프로브(§2) |
| 실행하지 않은 것 | Docker image build/save·PostgreSQL pilot DB·`init/bundle/serve` 실제 실행·Ubuntu worker download/enroll/mTLS(코디네이터가 이 PC에서 수행). hosted CI는 검토 시점 브랜치에 check 보고 없음. PR은 tip과 **CONFLICTING**(Codex rebase 중) → rebase 후 `tools/lan_pilot.py`·시험·README diff 0 재확인 필요 |

## 1. 보안 불변식 — 코드 대조

| 불변식 | 코드 근거(fce4f6de `tools/lan_pilot.py`) | 판정 |
|---|---|---|
| 키 미출력 | `bundle`이 archive에 넣는 것은 `manifest.json`·`ca.pem`·`signer.pub`·Node별 `peer-policy.json`·`node-agent.tar`·deploy 스크립트뿐(`*-key.pem` 없음). 비-primary Node의 policy는 private 디렉터리 `nodes/<nodeId>/`(비-Windows 0700). `init`·`enroll`·`status` 출력 JSON에 DSN/키 없음 | ✔ |
| 다운로드 서비스가 요청 IP에 맞는 번들만 | `artifact_for_client`: `client_address[0]`을 `configured_nodes`의 `nodeIP`와 정확히 1건 매칭(아니면 `PermissionError`→403). 경로는 고정 3개 이름 사전(`/worker.zip`·`/node-cert.pem`·`/workspace-worker.zip`)만 → 경로 조작 불가. Node별 `public/nodes/<nodeId>/<name>` 우선, legacy `public/<name>` fallback은 **primary Node에만** | ✔ (시험 갭 M1, §3) |
| 허용 IP 목록 | `/healthz`는 Node IP 집합+server IP+loopback, artifact는 Node IP만(server IP·loopback도 403 — v1보다 엄격, README와 일치). `serve` 시작 JSON에 `allowedNodeIPs`·방화벽 remote-address 목록 출력 | ✔ |
| hash 별도 채널 | `/worker.sha256`·`/workspace-worker.sha256` 이름 사전에서 제거 → 서빙 안 함(프로브 `None`). sidecar는 서버에만, `bundle` 출력 JSON으로 operator에게 | ✔ |
| 기존 Node/키/채널 교체 금지 | `add_requested_nodes`는 기존 IP `continue`(추가만); `init` 재실행은 `serverIP` 불일치 거부, 기존 identity 유지; `enroll`은 기존 cert public key 불일치·pinned channel fingerprint 불일치 시 "explicit rotation required" 거부(v1 로직 유지); primary cert alias(`public/node-cert.pem`)가 다르면 거부; `ensure_node_policy`는 기존 policy identity(tenant/node/epoch/clientFingerprints) 불일치 거부; CA/epoch 블록은 `ca.pem` 존재 시 skip, `control_epoch` 불일치 거부 | ✔ (시험 갭 M3, §3) |
| 부분 실패 보존 | 새 Node는 DB/PKI side effect **전에** `provisioned=false`로 `save`; `provisioned=true`는 전 단계 성공 뒤 일괄; `bundle`은 전원 provisioned 아니면 거부; `init` 조기 return은 `initialized`+전원 provisioned일 때만. `provision_observation_node`는 `ON CONFLICT DO NOTHING`이라 재개 시 기존 row 무변경 | ✔ |

## 2. 단일 Node state 하위 호환 — 코드 정독 + PG-free 프로브

코드: `configured_nodes`가 `nodes` 부재 시 top-level `nodeId/nodeIP/nodePort`로 1-Node 목록을 합성하고 `provisioned=bool(initialized)`; `normalized_state`는 top-level과 `nodes[0]` 불일치를 거부; `load`는 디스크를 쓰지 않고 `save`만 `nodes[]`를 추가 기록. legacy 경로: policy `peer-policy.json`, cert `public/node-cert.pem`, artifact `public/worker.zip`은 primary에 한해 alias.

프로브(코디네이터 상태 `.work/lan-5node/node1`을 **scratch 사본**으로만 사용, 원본 무변경, DSN·키 값 미출력·사본 삭제):

| 확인 | 결과 |
|---|---|
| 03:5x 최초 키 목록 | `nodes` 키 **없음**(v1 형태, `initialized=true`, policy nodeId==state nodeId) |
| 이후 프로브 시점 | 원본에 `nodes[]` 3건 존재, top-level == `nodes[0]` — 코디네이터가 그 사이 새 도구로 `init`을 실행해 **제자리 변환**된 것(내가 실행한 것 아님). 변환 뒤에도 기존 `nodeId`/IP 유지 = 추가 전용 설계와 일치 |
| v1 형태 재구성 사본(`nodes` 제거) `load` | Node 1건, `nodeId`/`nodeIP` 보존, `provisioned=True`, 디스크 무변경 |
| CSR CN 식별 | 실제 `node1.csr`의 CN이 legacy `nodeId`를 선택, `csr_public_key` 서명·subject·Ed25519·확장 0 검증 통과 |
| artifact 라우팅 | legacy IP → `public/worker.zip`·`public/node-cert.pem`; `/worker.sha256` → None; server IP·외부 IP → 403 |
| policy/cert 경로 | `peer-policy.json`·`public/node-cert.pem`(legacy); `ensure_node_policy`가 기존 policy를 **무변경** 수용 |
| 2번째 Node 추가 | `added=1`, primary id 유지, 새 Node `provisioned=False`, policy 경로 `nodes/<newId>/peer-policy.json`; 전원 provisioned → False(bundle 거부 조건 성립); `save` 후 top-level·DSN 키 보존 + `nodes[]` 기록 |

worker 측: `prepare-worker.sh`가 manifest `nodeId`로 `/CN=<nodeId>` CSR을 만들고 `finish-worker.sh`가 `nod_` ULID 형식·identity를 재검사 → 서버 `node_from_csr`(CN 정확히 1개, 구성된 Node만)와 맞물린다.

## 3. 되살림(mutation) — 새 시험 6건에 대해

| ID | 변형 | 결과 | 의미 |
|---|---|---|---|
| M1 | `artifact_for_client`의 legacy fallback을 primary 제한 없이 모든 Node에 적용 | **SURVIVED** (6 passed) | 비-primary Node가 자기 번들이 없을 때 primary의 `public/worker.zip`을 받게 되는 경계 위반을 시험이 못 잡음 → **조건 1** |
| M2 | `node_from_csr`가 CN 무시하고 primary 반환 | KILLED (1 failed) | CSR CN 식별은 시험이 지킴 |
| M3 | `ensure_node_policy`의 "Existing peer policy identity differs" 거부 제거 | **SURVIVED** (6 passed) | 기존 policy가 다른 tenant/node/epoch/fingerprint여도 재사용되는 교체 금지 위반을 시험이 못 잡음 → **조건 2** |
| M4 | `add_requested_nodes`가 기존 IP의 `nodeId`를 재발급 | KILLED (1 failed) | identity 교체 금지는 시험이 지킴 |

## 4. 조건(시험 보강, 코드 변경 없음)과 관찰

**조건 1**: 비-primary Node(`nodes[1]`)의 IP로 `/worker.zip`·`/node-cert.pem` 요청 시 `public/nodes/<id>/`에 파일이 없으면 legacy `public/worker.zip`이 있어도 `None`(404)이어야 한다는 시험. **조건 2**: 기존 `peer-policy.json`의 `nodeId`(또는 `recoveryEpoch`/`clientFingerprints`)가 다를 때 `ensure_node_policy`가 `ValueError`로 거부하고 파일을 덮어쓰지 않는다는 시험. 둘 다 PG-free·tmp_path로 가능.

관찰(비차단): O1 artifact 다운로드에서 server IP·loopback이 403이 된 것은 v1 대비 강화이며 README "maps the TCP source address to one configured Node ID"와 일치(operator 자기 점검은 `/healthz`만). O2 `node_state_directory`가 `mkdir` 뒤 symlink를 검사하므로 symlink→디렉터리는 mkdir 성공 뒤 거부, symlink→파일은 `FileExistsError`로 끝난다(결과는 모두 거부, 순서만 뒤바뀜). O3 `observe`가 5초마다 `node_status_rows`로 Node 수만큼 조회 2회씩 추가(4 Node면 8 query/5s, 파일럿 규모에서 무시 가능). O4 History의 base SHA `1a13e8ed`는 rebase 전 값이고 현재 merge-base는 `a28915bc`(문서 정정 권고, 코드 무관).

## 5. 다음 인계

- Codex: 조건 1·2 시험 추가 후 rebase push. 시험 파일 외 `tools/lan_pilot.py` diff가 0이면 재검토는 SHA·시험 결과 재확인만.
- 코디네이터: Docker 실검증(`init`→`bundle`→`serve`→Ubuntu download hash 상이·source-IP별 archive 상이)은 코디네이터 결과로 기록. 실제 Node 4대 enroll·mTLS·online은 이 검토에서 확인하지 않았다.
- Claude: rebase head에서 코드 diff 0 + 보강 시험 실행 + M1/M3 재실행(KILLED 확인) 뒤 승인 코멘트.
