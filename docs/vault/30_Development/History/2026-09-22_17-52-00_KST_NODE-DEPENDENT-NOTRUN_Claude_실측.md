---
doc_id: "CLAUDE-NEWPC-NODE-DEPENDENT-NOTRUN-001"
title: "카드 4 — 노드 의존 24파일 not_run 원인 확정(Windows 호스트: Unix Docker 소켓 부재) + Docker만으로 가능한 skip 23건 실행 전환(role guard 13·후보 이미지 8·config volume 2, 전부 passed)"
version: "1.0.0"
status: "evidence-contributed"
author: "Claude"
reviewer: "Codex"
updated: "2026-09-22T17:52:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "3d1892c0"
impl_sha: "(문서 전용 — 코드 변경 없음)"
tags: ["node-dependent", "not-run", "docker", "image-lane", "new-pc", "claude"]
---

# 카드 4 — 노드 의존 시험 not_run 채우기 (2026-09-22, 17:52 KST)

목표는 CI-스코프에서 `--ignore`된 node-dependent 24파일과 §4 환경 게이트 skip 142건 중 **이 PC의 Docker로 실행 가능한 부분**을 실제 실행으로 바꾸는 것이다. 측정 트리 `D:\Project\sv-measure-claude`, **SHA `3d1892c0`**(porcelain 0), 실 PG `saintvision-invion-dev-pg`(.env DSN, disposable DB), 각 파일 PowerShell `Start-Process` 분리·순차·동시 1개. 이미지 빌드는 코디네이터 `ask` 승인(플랜 C) 후 1회.

## 1. node-dependent 24파일 — not_run 원인 확정 (실행 불가, 이 호스트)

CI `core.yml` 레시피는 Linux 러너에서 `inv-node`를 **호스트 프로세스**로 띄우고(`INV_NODE_BINARY`를 `subprocess.run`) 그 프로세스가 `/var/run/docker.sock`로 컨테이너를 만든다. 이 PC에서 재현을 시도하기 전에 전제를 확인했다:

- `services/node-agent/runtime/docker.go` `NewDocker`: `filepath.IsAbs(socket)` + `net.Dialer.DialContext(ctx, "unix", socket)` — **Unix 소켓만 허용**(`NODE-0021: absolute local Docker socket required`), `DOCKER_HOST`/npipe 경로 없음(의도된 보안 경계: 상속 자격증명으로 특권 연결이 우회되지 않게).
- 이 호스트의 Docker 엔드포인트: `docker context ls` → `npipe:////./pipe/docker_engine`, `npipe:////./pipe/dockerDesktopLinuxEngine`뿐. `wsl -l -v` → `docker-desktop`·`docker-desktop-data` 내부 배포판만, 사용자 Linux 배포판 없음(`/var/run/docker.sock` 없음).
- 픽스처 `tests/integration/test_node_runtime.py::node_runtime`은 24파일 전부가 전이적으로 도달하며(`tools/node_dependent_tests.py`가 유도), `Path(binary).is_file()`·호스트 tmp 경로(`--state`, `--permit`, `--public-key`)·이후 호스트 `state/` 디렉터리 읽기를 전제한다.

따라서 **24파일은 이 Windows 호스트에서 정직한 not_run**이다. 원인은 코드 결함이 아니라 "Linux Docker 소켓 호스트 부재". 실행하려면 **WSL2 Ubuntu 배포판 + Docker Desktop WSL 통합 + Linux venv**(CI와 동일 조건)가 필요하며 이는 사용자 결정 항목(코디네이터가 올림). 컨테이너 래퍼로 `INV_NODE_BINARY`를 대체하는 편법(플랜 B)은 경로 변환·환경 편차로 CI와 비교 불가라 택하지 않았다. 참고: hosted Core CI는 이미 이 24파일 중 workspace 22·containment 28·business handoff 17·shard recovery 21·LAN installer 15를 **0 실패로 실행**했다([[2026-09-22_새PC_첫날_CI첫실행_triage_및_이전후_전수검증_Claude]]) — 그 자리가 이 파일들의 검증 자리다.

## 2. skip 142 중 Docker만으로 가능한 것 → 실행 전환 (23건, 전부 passed)

| 레인 | 게이트 | 환경 | 파일 | 결과 | 소요 | 잔재 |
|---|---|---|---|---|---|---|
| 마이그레이션 role guard | "Explicit local PostgreSQL image required" 13 | `INV_TEST_ROLE_GUARD_IMAGE=postgres:16`(이미 로컬에 있던 이미지, 시험이 라벨 `ai.saintvision.guard=*` 컨테이너를 만들고 제거) | `tests/test_migration_role_guard.py` | **13 passed / 0 skipped**, exit 0 | 28s | guard 컨테이너 0 |
| 후보 서버 컨테이너(이미지 레인 보안 단언) | "Explicit candidate image and disposable container DB address required" 8 | `deploy/Dockerfile.backend`를 측정 트리에서 1회 빌드 → `inv-api-test:local-3d1892c0` = **`sha256:0886bab93368d372e070ea50c2b533a8b9fb39ce62c0382f5c585a16b8f29358`**(라벨 `ai.saintvision.owner=claude`, 36s, 캐시); `INV_TEST_SERVER_IMAGE=<그 ID>`, `INV_CONTAINER_TEST_DB_HOST=172.17.0.2`(dev-pg의 브리지 IP; 시험이 포트를 5432로 고정하므로 호스트 55432 대신 컨테이너 내부 주소) | `tests/integration/test_server_container.py` | **8 passed / 0 skipped**, exit 0 — healthy·workspace·unreadable·writable·public-signing-key·business·business-workspace·**business-kernel-role** | 69s | `ai.saintvision.test` 컨테이너 0·볼륨 0 |
| 설정 볼륨 복사/실패 정리 | "Explicit pinned local candidate image required" 2 | `INV_TEST_CONFIG_IMAGE=<같은 ID>` | `tests/core/test_server_config_volume.py` | **7 passed**(기존 5 + 이미지 게이트 2), exit 0 | 8s | 0 |

**검증상태지도 §2.1/§2.2의 잔여 미검증 1건(business-kernel-role: kernel DB role을 `INV_BUSINESS_DSN`으로 쓰면 DB가 거부)이 이 PC에서 도달·통과했다.** 옛 PC에서는 host-init/timeout 계층에 막혀 4차례 미도달이던 것이다(메모리 여유 2.3GB, 조용한 구간, 동시 컨테이너 없음). public-signing-key·business-workspace(옛 PC daemon i/o timeout)도 통과. 이미지 레인 8/8 = **제품 보안 단언 실패 0**.

정리: 시험 후 `docker ps -a --filter label=ai.saintvision.test`·`docker volume ls --filter label=ai.saintvision.test`·`label=ai.saintvision.guard` 모두 0. 빌드한 이미지 `inv-api-test:local-3d1892c0`는 ID를 기록한 뒤 제거(다른 프로젝트 이미지·컨테이너 무접촉).

## 3. 남는 skip (이 PC에서 계속 not_run, 사유별)

| 건수 | 사유 | 왜 남는가 |
|---|---|---|
| 48 | Actual Linux file backend | Linux 자격증명 파일 백엔드(소유권·모드·O_NOFOLLOW) — Windows 파일시스템에선 검증 불가; hosted Core가 자리 |
| 20 | Linux credentials | 동상 |
| 19 | CX01_CONTAINER is unset | 보호 컨테이너 옛 PC 잔류(이전 절차서 §6) |
| 15+13 | Linux private-directory provider · Linux publication contract | Linux 전용 |
| 1 | browser smoke integration lane | Chromium 실측 레인(Gemini) |
| 1 | symlink on Windows needs privilege | 개발자 모드/관리자 권한 필요 |
| 1+1 | antigravity·(CLI) not installed / launcher prerequisites(측정 트리 파생물 부재) | 도구·트리 조건 |
| **24파일** | node-dependent (ignore) | §1 — Linux Docker 소켓 호스트 부재 |

## 3-1. hosted Backend Build 첫 완주 (SHA 3d1892c0, run 35706465869) — PG no-skip 첫 관측

착지 대기 중 확인: **Backend Build success** — 3.12·3.14 둘 다 **2668 passed / 45 skipped / 2 deselected / 0 failed**(8~9분), "Require executed evidence and declared platform skips" 단계 통과 = `2aa80899`의 skip ratchet(10사유 정확 건수)이 실 실행과 **일치**. 어제·오늘 "hosted backend PG no-skip 결과 0 관측"이던 자리가 처음 채워졌다. 이 PC 전수(2523/142, node-dependent ignore)와 대조하면 hosted는 Linux라 Linux 전용 게이트가 깨어나 passed가 145 많고 skip이 97 적다 — 남은 45 skip은 Windows PowerShell 런처 11·CX01 19·이미지/브라우저 opt-in 11·CLI 도구 4(ratchet 목록 그대로). Documentation success, Browser Acceptance failure(카드 2 F-B와 동일 케이스 미상, 브라우저 레인), Core Build 진행 중(착지 시점).

## 4. Evidence
- junit·로그: `.work/evidence-claude-d01c931a/card4/{roleguard,server_container,config_volume}.{xml,log}`, `build.log`, 각 `.meta`(SHA·env·exit·소요).
- provenance: `docs/vault/30_Development/Evidence/claude-newpc-realpg-d01c931a/card4-docker-lanes-provenance.json`.
- 검증상태지도 §7 갱신(같은 커밋).

## 다음 첫 행동 / 담당
- 사용자/코디네이터: node-dependent 24파일을 이 PC에서 돌릴지(WSL2 Ubuntu + Docker 통합) 결정. 결정 전까지 hosted Core CI가 검증 자리.
- Claude: 결정 시 WSL2 레인 구축 카드. 그 외 Docker-only 전환은 끝(남은 skip은 Linux/CX01/브라우저/권한).
