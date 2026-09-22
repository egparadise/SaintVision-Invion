---
doc_id: "HIST-CODEX-PC-MIGRATION-5NODE-20260922"
title: "다른 PC 이전·5대 Node 준비 후 가능해지는 검증"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-09-22T10:25:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
---

# 1. 현재 worktree와 브랜치 보존 판정

기준: `origin/integration/all-agents-unified` (`0a02ada1` 관측 시점), `git worktree list --porcelain`, 각 worktree의 `git status --porcelain`, `git rev-list --count origin/integration/all-agents-unified..HEAD`를 사용했다. Codex worktree 51개 중 45개는 integration의 조상이고 clean이다. 이 45개는 clone 후 다시 만들 필요가 없는 오래된 작업 껍데기다.

## 이전해야 하는 것

| 분류 | 브랜치 | 상태 | 이전 조치 |
|---|---|---|---|
| 통합되지 않은 기능 | `agent/codex/alarm-coverage-summary` (`311adb68`) | integration에 1 commit 앞섬 | 브랜치 ref와 commit을 보존하고, 새 PC에서 최신 integration에 재검토 후 반영. 알람 도구·시험·기록 포함 |
| 통합되지 않은 기능 | `agent/codex/s07-replica-wiring` (`f9aac9ee`) | integration에 1 commit 앞섬 | `src/saintvision/services/nodes.py`와 replica/lost 시험을 보존. 실제 Node 인수 후 재검증 대상 |
| 통합되지 않은 환경 가드 | `agent/codex/dev-environment` (`4da131fa`) | integration에 1 commit 앞섬 | `tests/conftest.py`와 역할 fixture 시험을 보존. 새 PC 의존성 설치 뒤 재실행 |
| 미통합 VF evidence | `agent/codex/vf-cx-01` (`bf3e510d`), `agent/codex/vf-cx-04` (`4a06f56f`) | 각각 integration에 1 commit 앞섬 | 코드 브랜치로 보기보다 Evidence JSON과 보고서를 보존. 최신 SHA에 대한 귀속을 새 PC에서 다시 확인 |
| 미커밋 변경 | `agent/codex/write-response-contract` | 12 files dirty | 폐기 금지. 현재 변경을 patch/archive로 먼저 보존하고, 별도 commit 후 review. 생성 schema·fixtures·`result_view.py`·`shards.py`가 섞여 있어 다른 작업자의 미완료 변경일 가능성도 같이 기록 |

`codex/integration-merge`의 커밋은 integration에 반영된 상태다. 위 목록 외 branch는 현재 integration에 이미 도달했거나 오래된 조상이다. 새 PC에서는 57개 worktree를 복제하지 말고 integration tip과 위 보존 목록만 가져온다. dirty worktree는 `git diff > migration/<branch>.patch` 또는 별도 archive를 만든 뒤에만 정리한다.

# 2. 새 PC 직후의 순서

1. integration의 최신 SHA를 clone하고 `git status --porcelain`이 비어 있는지 확인한다.
2. Python 의존성, Node/npm, PostgreSQL client, Docker, Go toolchain을 설치하고 버전을 기록한다.
3. `python tools/check_docs.py`, `python tools/check_contract_bindings.py`, 프런트 `npm test`, Python core를 새 SHA에서 먼저 실행한다.
4. Go 검증을 처음 실행한다. 이전 Windows PC에는 Go가 없어 제품 Go 전체를 검증하지 못했다.
5. 실제 5대 Node를 등록하기 전에 합성 CA/테스트 DB로 실패 경계를 확인하고, 운영 CA·IdP·비밀은 새 PC에 복사하지 않는다.

## Go T1~T3 첫 실행

정확한 기대치는 “성공”이 아니라 첫 실행의 증거다. 각 명령의 SHA·Go 버전·OS·exit code·top-level/leaf 수·skip/error/failure를 저장한다.

| 단계 | 명령 | 처음 확인하는 것 | 실패 소유자 |
|---|---|---|---|
| T1 | `go test -race ./...` in `services/node-agent` | wire 계약, discovery, runtime/storage, transport의 Linux/동시성 단위 시험 | 코드/계약이면 Codex, OS·Docker 전제면 새 PC 환경 담당 |
| T2 | `go test -race ./...` 및 Linux build tags/실행 패키지 | Linux-only filesystem, PTY, Docker/lock 경로와 race | Codex의 Go 런타임 또는 Linux 환경 담당. Windows skip은 실패로 오인하지 않음 |
| T3 | `go build ./...` 및 `go build -trimpath`로 `inv-node`·`inv-supervisor`·`inv-discover` 산출 | 실제 바이너리 컴파일·생성 계약·플랫폼 build | 컴파일/생성 계약은 Codex, toolchain·플랫폼은 환경 담당 |

Go가 통과해도 실제 물리 Node나 운영 CA/mTLS 인수를 뜻하지 않는다. 반대로 Linux/Docker가 없어서 skip이면 제품 합격으로 세지 않는다.

# 3. 5대 Node 인수 준비

## 설치·등록 체크리스트

1. 각 장비의 OS, hostname, MAC/설치 식별자, 디스크 경로, CPU/RAM/GPU를 inventory에 기록한다.
2. `inv-node`와 supervisor를 설치하고 허용 storage root, Docker 정책, 로그 보존을 설정한다.
3. 운영자가 발급한 tenant-bound discovery credential 또는 enrollment token을 승인된 전달 경로로 주입한다. 원문은 저장소·로그에 남기지 않고 digest와 발급/만료/폐기 이벤트만 남긴다.
4. 운영 CA 체인, node 인증서의 SAN/EKU/URI, private-key 권한, CP endpoint DNS를 설치한다. 잘못된 tenant·CA·hostname·폐기 인증서가 거부되는지 먼저 확인한다.
5. Node를 등록하고 mTLS handshake, heartbeat, `heartbeatSequence` 증가, `lastHeartbeatAt`, capability/offer 값, tenant 격리를 실제 API에서 확인한다.
6. CP의 Node 목록과 상세에서 `enrolled/online` 상태가 실제 장비와 일치하는지 확인하고, Node 중지 후 stale/lost 전이와 오래된 token 쓰기 거부를 기록한다.
7. 복구 후 재등록·재연결, replica stale 처리, 승인된 실행의 resource reclaim까지 증거 ID로 묶는다.

## 5대가 있어야 닫히는 항목

- **S01-ST/S02-BE/S02-FE**: 장비 inventory, mTLS 등록, 실제 heartbeat와 브라우저 Node 관측.
- **S04/S07**: DB 행을 `lost`로 바꾼 기존 시험은 상태 로직 증거일 뿐이다. 실제 Node 중단·네트워크 분할·late result·재연결이 필요하다.
- **S07 replica wiring**: 같은 트랜잭션에서 Node loss와 replica stale을 묶는 코드는 실 PG에서 확인했지만, 실제 Node가 사라지는 원인부터 CP가 감지하는 경로는 아직 미검증이다.
- **S05**: 5대 자원 경합·fencing·allocation의 실제 snapshot/weight와 동시 예약 결과.
- **S08/S11/S12**: GPU capability, 보안 격리, 5대 내부망 smoke/rollback/운영 인수.

# 4. 5대 토폴로지 결정

현재 설계와 registry는 “5대 Node” 여정을 전제로 한다. 따라서 권고는 **5대를 모두 worker Node로 유지하고 Control Plane은 별도 호스트·VM·관리 환경에 둔다**는 것이다. 한 대를 Control Plane으로 예약하면 worker는 4대가 되어 5-node acceptance와 수치가 달라진다.

이는 사용자 결정이다. 선택지는 다음과 같다.

- 5대 모두 Node + 별도 CP: 기존 5-node 기준을 보존한다(권고).
- 1대 CP 겸 Node + 4대 worker: 비용은 줄지만 S02/S05/S12의 “5대” 기준과 inventory를 4 worker로 다시 정의해야 한다.
- CP를 5대 중 한 대에 두되 worker 역할도 유지: 장애 격리와 자원 산정이 달라지므로 운영 인수 전에 별도 ADR이 필요하다.

이 문서는 토폴로지를 결정하지 않는다. 사용자가 선택한 뒤 Node 설치·mTLS 발급·S02 인수 증거의 대상 수를 고정한다.

# 5. 검증 경계

현재 관측은 worktree/branch 실측과 기존 코드·시험·Evidence 문서 대조다. Go T1~T3와 실제 5대 Node 인수는 새 PC에서 실행해야 하며, 이전 자체가 성공했다고 주장하지 않는다.

