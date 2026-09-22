---
doc_id: "HISTORY-CODEX-LAN-PILOT-CP-OBSERVATIONS-20260923"
title: "LAN pilot CP 겸임 관찰 보강"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-23T08:10:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
tags: ["LAN", "pilot", "ADR-100", "Docker", "revocation", "fail-closed"]
---

# LAN pilot CP 겸임 관찰 보강

## 범위와 SHA

- 카드: Codex 카드 15 O1/O2/O4/O5.
- branch: `agent/codex/lan-pilot-cp-observations`.
- 최종 base: `76f4528d25c609680c26fc3d0623c48be0591696`.
- 구현 SHA: `791c7332738a360933e9b25e5fbaed724a1360a0`.
- reviewer: Claude. 실제 Windows 겸임 등록·철회 명령 실행은 하지 않았다.

## 구현

`revoke-server-node-colocation` 서브커맨드는 CP 겸임 opt-in을 철회할 때 Node ID, address, 파일, private key, journal, DB Node row를 삭제하거나 교체하지 않는다. 먼저 private state에 `serverNodeColocationAllowed=false`, `disabled=true`, `disabledReason=server-node-colocation-revoked`를 저장해 부분 실패에서도 재서빙·재등록이 fail closed되게 한다. 등록 channel이 있으면 기존 `revoke_channel`의 version CAS와 audit를 사용해 비활성화하고, 아직 등록 전이면 `not-enrolled`로 기록한다. disabled Node는 status에 계속 보이지만 active bundle, CSR enrollment, source-IP artifact serve에서 제외된다.

worker installer는 schema-v3가 아니면 topology 검사 첫 단계에서 거부한다. 새 v3 script를 옛 v2 압축 해제 디렉터리에 섞는 경로는 fail closed이며 기존 Ubuntu 3대의 key/journal/container/channel 재설치는 요구하지 않는다. README는 co-located bootstrap 요청이 loopback 또는 WSL NAT source로 도착하면 HTTP 403인 것이 정상이고 allowlist/portproxy로 우회하지 말아야 함을 고정했다. Docker preflight 오류는 최소 Docker API 1.45 = Engine 25+ / Docker Desktop 4.27+를 `BLOCKED` 메시지로 직접 표시한다.

## 검증

| 명령 | 결과 |
|---|---|
| `pytest -q tests/test_lan_pilot_multinode.py tests/core/test_lan_worker_config.py` | 47 passed, exit 0 |
| `python -m py_compile tools/lan_pilot.py deploy/lan/worker_config.py` | exit 0 |
| `bash -n deploy/lan/prepare-worker.sh deploy/lan/finish-worker.sh` | exit 0 |
| `python tools/lan_pilot.py --help` | revoke subcommand 노출, exit 0 |
| `python tools/check_docs.py` | 보고 포함 871 docs, exit 0 |
| contract bindings / frontend integrity / ontology / single-source ratchet | 모두 exit 0 |
| response freshness | advisory 10/10 present, exit 0 |
| `python tools/sync_obsidian.py --check` | 1708 managed, pending export 2, conflict 0, exit 0; apply는 코디네이터 담당 |

시험은 state 저장이 channel revoke보다 먼저 일어나는 순서, identity 보존, disabled Node의 active 집합/HTTP 제거, v2 manifest 거부, 최소 Docker 버전 메시지를 고정한다. 실제 state에는 아직 CP 겸임 Node가 없고 Docker API 1.41·WSL Ubuntu 부재가 유지되므로 운영 명령을 실행하지 않았다. O5는 `BLOCKED`이며 5노드 등록·S05/S07 승격 주장은 없다.

## 다음 행동

Claude가 state preservation, channel audit, disabled boundary와 기존 Ubuntu/단일 Node 호환성을 독립 검토한다. 사용자 또는 코디네이터가 Docker Desktop 4.27+/Engine 25+와 Ubuntu WSL을 준비한 뒤에만 CP 겸임 등록을 다시 수행한다. opt-in 철회가 필요할 때 운영자가 새 subcommand를 명시적으로 실행하며, 실행 전후 state·channel·status 증거는 별도 History로 남긴다.
