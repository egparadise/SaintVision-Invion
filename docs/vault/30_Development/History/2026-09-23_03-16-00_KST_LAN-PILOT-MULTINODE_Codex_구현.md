---
doc_id: "HISTORY-2026-09-23-LAN-PILOT-MULTINODE-CODEX"
title: "LAN pilot 다중 Node state·번들·등록 경계 구현"
version: "1.0.2"
status: "review"
author: "Codex"
updated: "2026-09-23T04:55:00+09:00"
source_of_truth: "Git"
---

# LAN pilot 다중 Node state·번들·등록 경계 구현

## 카드와 provenance

- 카드: coordinator 카드 12, LAN 파일럿 다중 노드화. 관련 outcome은 VF-CX-05와 AC-01/AC-12의 물리 5대 인수 선행이다.
- owner/reviewer: Codex / Claude.
- 읽은 진행판: `INDEX-PROGRESS-001` v1.0.256, `WORKBOARD-CODEX-001` v1.0.185.
- branch/worktree: `agent/codex/lan-pilot-multinode` / `D:\Project\SaintVisionI-Invion\.work\codex-lan-pilot-multinode`.
- original base SHA: `1a13e8edfc309ad3a7ad4484fdbebca26d6ecbc2`; final rebase base SHA: `65ef557e77a67d98670771ea45417d88e540f2c8`.
- implementation SHA after final rebase: `e7a37b0addc82d48512b13c542b5c4dce068892b`.

## 구현

`tools/lan_pilot.py`의 기존 단일 Node private state를 깨지 않고 `nodes[]`를 추가했다. 첫 Node의 `nodeId/nodeIP/nodePort`는 이전 도구가 계속 읽는 호환 alias다. `init --node-ip`를 반복할 수 있고, 기존 state에 다시 실행하면 새 주소만 새 Node ID로 추가한다. 새 ID는 DB/PKI 작업 전에 `provisioned=false`로 저장되므로 중간 실패 뒤 같은 ID로 재개하며 기존 Node·키·certificate channel·CA·epoch를 삭제하거나 교체하지 않는다.

`bundle`은 공통 image와 CA 아래 Node별 manifest, peer policy, `worker.zip`, SHA-256 sidecar를 만든다. HTTP bootstrap은 TCP 요청 source IP를 허용 목록의 정확히 한 Node에 매핑해 그 Node의 archive/certificate만 반환한다. hash endpoint는 제공하지 않고 operator 출력·server sidecar로만 남겨 신뢰 채널을 분리했다. 첫 Node의 기존 `public/worker.zip`, `worker.sha256`, `node-cert.pem` 경로도 보존한다.

`enroll --csr`는 CSR의 단일 CN에서 미리 배정된 Node ID를 선택하고, 기존 Ed25519 signature·subject·extension 검증을 그대로 수행한다. 이미 등록된 다른 public key 또는 pinned channel은 계속 명시적 rotation 없이는 거부한다. `status`와 `observe`는 구성된 모든 Node의 ID·IP·DB row·snapshot을 `nodes` 배열로 출력하되 첫 Node의 기존 top-level 출력도 유지한다. `serve` 시작 JSON에는 TCP 18081 Windows 방화벽 remote-address 허용 목록을 출력한다.

`deploy/lan/README.md`에는 Windows server + Ubuntu worker 4대의 반복 `--node-ip`, Node별 out-of-band hash, `prepare-worker.sh` → CSR → `enroll` → certificate hash → `finish-worker.sh` → `start-node.sh` 순서와 Docker 25+/server API 1.45+, NTP, TCP 18443 server-only inbound 조건을 추가했다.

## 검증

환경은 Windows, Python 3.14.7 `.venv`, `PYTHONPATH=src;services/control-plane/src`, `PYTHONUTF8=1`이다.

| 명령 | 결과 |
|---|---|
| `python -m pytest -q tests/test_lan_pilot_multinode.py` | 6 passed, 0 skipped/failed, exit 0. legacy state, additive identity, IP validation, CSR CN 선택, Node별 archive·IP download, hash 비서빙, partial status를 PG-free로 검증 |
| LAN core 11파일 + `tests/test_workspace_package.py` + `tests/test_docker_volume_provenance.py` | 186 passed, 1 skipped, 0 failed, exit 0. skip 1은 `INV_TEST_ADMIN_DSN` 미설정 PostgreSQL case이며 통과로 세지 않음 |
| 첫 재기반 뒤 위 두 범위를 한 lane으로 재실행 (`040cae5b`, code `c8eefab2`) | 192 passed, 1 skipped, 0 failed, exit 0. skip 사유 동일 |
| 최신 tip `06bab6d5` 재기반 뒤 `tests/test_lan_pilot_multinode.py` (`b5571034`, code `6da99baf`) | 6 passed, 0 skipped/failed, exit 0 |
| `python -m py_compile tools/lan_pilot.py tests/test_lan_pilot_multinode.py` | exit 0 |
| `python tools/lan_pilot.py --state .work/unused init --help` | 반복 가능한 `--node-ip` 도움말, exit 0 |
| `python tools/check_docs.py` | final rebase 859 versioned documents, exit 0 |
| `python tools/check_ontology.py` | 48 task mappings, 4 rejected invalid fixtures, exit 0 |
| `python tools/check_doc_single_source.py --ratchet` | baseline 18 pairs, new/stale 0, exit 0 |
| `python tools/sync_obsidian.py --check` | final pre-push 1687 managed, 5 pending exports, 0 conflicts, no writes, exit 0 |
| `git diff --cached --check` | exit 0 |

03:15 KST 메모리 경보 전에 관련 회귀 실행을 마쳤다. 경보 뒤에는 전체 pytest/build/browser/Docker를 시작하지 않았고 단일 PG-free 파일과 문서·코드 정리만 수행했다.

## Ubuntu 24.04 실기 F1 보정

Coordinator의 실제 Ubuntu 24.04 worker `192.168.45.143`에서 `finish-worker.sh`가 `Loaded image execution configuration differs: User`로 멈췄다. bundle manifest의 scratch image `imageConfig.User`는 빈 문자열이지만 최신 Docker Engine의 `image inspect`는 같은 기본값을 `null` 또는 key 누락으로 직렬화할 수 있었다.

Hotfix `10b0fc03d470e6a67fbb13ecb0250e4e6caaebe0`는 문자열 키 `User`와 `WorkingDir`에만 `None`과 `''` 동치를 적용한다. `1000:1000` 또는 `/workspace`처럼 비어 있지 않은 기대값과 누락값의 불일치는 계속 `ValueError`로 거부한다. `Env`와 다른 실행 구성의 비교는 넓히지 않았다. `tests/core/test_lan_worker_config.py`는 User 누락 양성, WorkingDir 누락 양성, 두 non-empty mismatch 음성을 추가했고 전체 **23 passed / 0 skipped/failed / exit 0**이다.

Ubuntu 절은 `finish-worker.sh`가 identity/certificate 확인 뒤 `start-node.sh`를 내부 호출하므로 operator가 직접 호출할 필요가 없고, 직접 선호출하면 의도한 설치 순서를 우회한다는 점을 명시했다.

## 실 Ubuntu 인수와 Claude 조건 보강

Coordinator는 PR head `ebb60155`의 hotfix bundle을 실제 Ubuntu 24.04 worker `192.168.45.143`(Docker API 1.52, NTP synchronized)에 적용했다. 수정 전 `User` mismatch를 재현한 뒤 수정 bundle에서 credential owner/mode 검증, container `Up`, TCP 18443 publish, `observe --once`의 mTLS `online`·`observed=true`·resource snapshot을 확인했다. 기존 단일 Node state의 primary ID를 보존하면서 같은 state에 Node 2/3 주소를 추가하고 Node별 archive와 source-IP별 download를 확인했다. Node 2/3은 CSR 미등록이라 offline이며 성공으로 세지 않는다. Evidence: [PR #89 coordinator 실검증](https://github.com/egparadise/SaintVision-Invion/pull/89#issuecomment-5781996978).

Claude 카드 dd는 M1(secondary가 primary legacy artifact를 fallback)과 M3(peer policy identity/fingerprint 검사를 제거)의 생존을 조건으로 남겼다. `619a45dbb4b7164263acfd1fa3383e38cbff66ce`에서 다음 PG-free 시험을 추가했다.

- secondary IP의 `worker.zip`/`node-cert.pem`은 Node별 파일이 없으면 primary legacy 파일이 있어도 `None`이다.
- 기존 policy의 `nodeId`, `recoveryEpoch`, `clientFingerprints` 각 mismatch는 `ValueError`이고 bytes는 변하지 않는다.
- `65ef557e` 최종 rebase 복원본 `tests/test_lan_pilot_multinode.py`: 10 passed/exit 0.
- M1 되살림: 해당 targeted case 1 failed/exit 1로 KILLED. M3 되살림: 세 parameter case 3 failed/exit 1로 KILLED. 각 mutation은 즉시 원복하고 복원본 10 passed를 재확인했다.

Claude의 조건부 승인 원문은 [PR #89 카드 dd](https://github.com/egparadise/SaintVision-Invion/pull/89#issuecomment-5781789477)다. 보강 head의 최종 reviewer 전환과 hosted checks는 pending이다.

## 정직한 경계와 인계

- Windows server와 Ubuntu Node 1대의 init/bundle/serve/download/enroll/mTLS/18443/NTP는 위 evidence에서 실행됐다. Node 2/3 실제 enroll, Ubuntu 4대 전체, CP 겸임 Windows Node, 장애/부하/AC-12는 미실행이다.
- hosted CI와 보강 head의 Claude 최종 독립 검토는 pending이다. 작성자가 카드를 self-close하지 않는다.
- coordinator가 나머지 Node와 CP 겸임 Windows worker를 등록하고, Claude가 보강 head에서 두 mutation kill을 재확인한다.
- 운영 인수 중 한 Node가 실패하면 state를 보존하고 그 Node만 재시도한다. 기존 key/channel을 자동 교체하는 복구는 이 카드 범위가 아니다.
