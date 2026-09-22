---
doc_id: "HIST-CODEX-2026-09-23-LAN-PILOT-CP-COLOCATED"
title: "LAN pilot Windows CP 호스트 겸임 Node 경로 구현"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T06:15:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
original_base_sha: "ed200c33c530de75c1fdee62cc21c976ca336841"
base_sha: "4143f375a2198572455a442cf2d80086d70f5b6b"
implementation_sha: "8007ae124422c5fbe48a8f72d8bceece96d35146"
tags: ["LAN-pilot", "Windows", "Docker-Desktop", "ADR-100", "co-location", "security"]
---

# LAN pilot Windows CP 호스트 겸임 Node 경로 구현

## 범위와 결론

PR #89의 다중 Node state를 그대로 사용해 Windows Control Plane 호스트의 Docker Desktop Linux container를 별도 Node identity로 등록하는 경로를 구현했다. 일반 Node는 계속 `serverIP != nodeIP`여야 하며, 동일 주소는 `init --allow-server-node-colocation`을 명시한 경우에만 허용하고 그 결정을 `serverNodeColocationAllowed=true`로 private state에 영속한다. 기존 Node ID·키·certificate channel·CA·DB·recovery epoch는 제거하거나 교체하지 않는다.

최종 rebase base는 `4143f375a2198572455a442cf2d80086d70f5b6b`, 구현 SHA는 `8007ae124422c5fbe48a8f72d8bceece96d35146`이다.

co-located Node의 schema-v3 manifest는 주소에서 `coLocatedWithControlPlane=true`를 재도출하고 `measurementEligible.s05=false`, `measurementEligible.s07=false`, `exclusionReason=cp-host-colocation`을 고정한다. 독립 Node는 이 bootstrap이 적격을 추정하지 않도록 두 eligibility를 `null`로 둔다. `worker_config.py`, `prepare-worker.sh`, `finish-worker.sh`, `Start-Worker.ps1`은 주소와 선언 또는 ADR-100 제외가 어긋나면 방화벽·credential copy·container 시작 전에 fail closed한다.

`Prepare-Worker.ps1`와 `Start-Worker.ps1`의 기존 Windows→WSL Ubuntu→Docker Desktop 경로는 유지한다. CP 겸임 Node도 자기 Node ID·CSR·private key·certificate·peer policy·journal·container/volume을 가지며, source-IP가 server/Node 공통 주소인 경우 bootstrap HTTP는 그 주소에 배정된 archive와 certificate만 반환한다.

## PG-free 검증

환경은 Windows, Python 3.14.7 `.venv`, `PYTHONPATH=src;services/control-plane/src`, `PYTHONUTF8=1`이다.

| 명령 | 결과 |
|---|---|
| `pytest -q tests/test_lan_pilot_multinode.py` | 13 passed, 0 skipped/failed, exit 0 |
| `pytest -q tests/core/test_lan_worker_config.py` | 30 passed, 0 skipped/failed, exit 0 |
| `python tools/lan_pilot.py --state .work/unused init --help` | opt-in flag 노출, exit 0 |
| PowerShell parser: `Start-Worker.ps1` | parse error 0 |
| `bash -n prepare-worker.sh finish-worker.sh` | exit 0 |
| `python tools/check_docs.py` | 864 versioned documents, exit 0 |
| `python tools/check_contract_bindings.py` | fixtures 54, response types 19, replay guards 14, exit 0 |
| `python tools/check_frontend_integrity.py` | 9 rules, 0 violations, exit 0 |
| `python tools/check_ontology.py` | RDF/SHACL/48 task mappings, exit 0 |
| `python tools/check_doc_single_source.py --ratchet` | 18 baseline pairs, stale 0, exit 0 |
| `git diff --check` | exit 0 |

시험은 동일 주소의 기본 거부, 명시 opt-in 허용, private-state opt-in 누락/위조 거부, 주소에서 co-location 재도출, schema-v3 제외 필드, 설치 측 topology tamper 거부, 독립 Node의 eligibility 미판정을 고정한다. PostgreSQL·Docker container·실제 CSR/등록은 이 로컬 시험에 포함하지 않는다.

## 실제 Windows 호스트 read-only preflight

비밀 DSN·키·token을 출력하지 않고 `.work/lan-5node/node1`의 공개 가능한 상태와 로컬 runtime만 확인했다.

- server IP `192.168.45.74`, 기존 Ubuntu Node identity 3개(`.143`, `.222`, `.210`), 모두 state에서 provisioned다.
- Windows `이더넷 2`에 `192.168.45.74`가 있고 TCP 18443 listener는 없다.
- 기존 `saintvision-lan-node:<epoch-prefix>` image tag가 있으며 local content ID는 state의 recorded image와 일치한다.
- Docker Desktop Engine은 **20.10.22 / API 1.41**로 installer 최소 기준 **API 1.45**보다 낮다.
- WSL distribution은 `docker-desktop`, `docker-desktop-data`뿐이고 스크립트가 요구하는 `Ubuntu`가 없다.

따라서 실제 `Prepare-Worker.ps1`/`Start-Worker.ps1` 실행은 현재 **BLOCKED**다. 기준을 API 1.41로 낮추거나 Docker 내부 distribution을 일반 Ubuntu 대신 사용하는 우회는 하지 않는다. 코디네이터가 Docker Desktop/Engine 25+·server API 1.45+와 WSL `Ubuntu` integration을 준비한 뒤 실제 등록을 수행한다.

현재 코디네이터 관측에서 `.143`과 `.210`은 mTLS online이고 `.222`는 Docker group 대기다. 등록된 Ubuntu identity가 현재 3개이므로 Windows identity 추가만으로 5 Node가 되지는 않는다. 네 번째 Ubuntu identity까지 별도로 등록·관측되어야 ADR-100의 registeredNodeCount 5를 주장할 수 있다.

## 실제 등록 인계

선행 조건 충족 후 같은 state에서 다음 명령으로 겸임 identity만 추가한다.

```powershell
python tools/lan_pilot.py --state .work/lan-5node/node1 init `
  --server-ip 192.168.45.74 --node-ip 192.168.45.74 `
  --allow-server-node-colocation
python tools/lan_pilot.py --state .work/lan-5node/node1 bundle --reuse-image
```

그 다음 `serve`를 재시작해 state를 다시 읽고, same-host HTTP download의 out-of-band SHA-256을 대조한 뒤 `Prepare-Worker.ps1` → CSR enroll → `Start-Worker.ps1` 순서로 실행한다. 완료 판정은 `status`와 `observe --once`의 별도 Node ID, mTLS online, current resource snapshot이며 container 실행이나 certificate 발급만으로 성공 처리하지 않는다.

ADR-100에 따라 이 Node는 all-five topology smoke에는 참여할 수 있지만 S05 timed P95와 S07 independent-host 복구율 분모에서는 사전 제외한다. `colocated-node-process-loss`는 별도 scenario이며 Windows 전체 장애는 외부 monotonic observer가 없으면 `correlated-cp-node-host-loss`/`UNMEASURED`다.

## 다음 행동

Claude가 명시 opt-in·state 영속 승인·manifest/installer fail-closed·기존 단일/다중 Node 하위 호환을 독립 검토한다. 코디네이터는 prerequisite를 충족한 뒤 실제 Windows CSR/enroll/start/observe 결과를 별도 운영 Evidence로 추가한다. 이 카드는 self-close하지 않으며 실제 등록·5 Node 충족·S05/S07 측정을 완료로 주장하지 않는다.
