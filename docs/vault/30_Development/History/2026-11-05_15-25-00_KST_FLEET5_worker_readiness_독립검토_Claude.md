---
doc_id: "HISTORY-FLEET5-20261105-WORKER-REVIEW-CLAUDE"
title: "2026-11-05 FLEET5 Codex worker readiness 6ba9ee46 독립 검토와 CP 오프라인 계획 보정"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T15:25:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "138ece54"
task_ids: ["FLEET5-20261105-CP-AND-INVENTORY", "FLEET5-20261105-WORKER-READINESS"]
tags: ["fleet5", "independent-review", "five-node", "control-plane", "docker", "claude"]
---

# Codex worker readiness 독립 검토

Orca task `task_e1b499632366`. 이 문서는 Claude가 Codex의 `6ba9ee4686ab2ec1b2e566b13edef016fa4f8d4e`(보고 `e1afa49c`)를 독립 검토한 결과다. Codex가 아직 commit하지 않은 Docker 하한 문구 수정도 함께 검토했다. 이 검토는 실제로 수행한 정적 검토와 읽기 전용 관측만 적는다. 시험이나 live health는 다시 실행하지 않았다. Codex의 첫 wave 요약은 검토 시점(15:06~15:25 KST)에 아직 게시되지 않아 검토하지 못했다. 기계 판독 결과는 `Evidence/fleet5-20261105-claude/worker-readiness-review.json`에 있다. 앞선 CP 기록은 [[2026-11-05_15-05-00_KST_FLEET5_CP겸Node와_inventory_대조_Claude]], Codex 원문은 `agent/codex/fleet5-worker-readiness-20261105`의 `History/2026-11-05_FLEET5_worker_readiness_Codex.md`다.

## 무결성 확인

- proposal이 고정한 source 파일 10개의 sha256을 `59f0a3c2` Git blob에서 다시 계산했고 10개 모두 일치했다. 해당 installer와 도구 파일은 `59f0a3c2`와 base `9b9061ed` 사이에 차이가 없다(diff 0행).
- receipt의 Evidence 6개와 History blob sha256도 모두 일치했다. Docs CI는 `e1afa49c`가 run 41977201244 success, `6ba9ee46`이 run 41977391990 success다.
- Codex가 적은 inventory lint 값(5 nodes, 74 missing, 0 invalid)은 내 측정과 같다. Codex는 CLI 판정을 exit 1로 적었고 나는 함수 호출 script를 exit 0으로 적었다. 두 값은 측정 방식이 달라서 생긴 차이이며 서로 모순되지 않는다.

## 발견

| ID | 심각도 | 판정 | 내용 | 필요한 조치 |
|---|---|---|---|---|
| R1 | High | 확인 | 후보 port가 과거 pilot port와 겹친다. bootstrap 18085는 r3의 downloadPort, overview 18086은 r4의 downloadPort, nodeTLS 18447은 r4의 nodePort다. r2/r3/r4의 state·키·저널·volume은 보존 대상인데 worker 쪽 container와 port는 측정되지 않았다. CP에서는 15:07:27 KST에 다섯 후보 모두 비어 있었다(18105는 r5 serve). | 과거 download/node/db port 집합 밖에서 고르고, init 전에 CP와 대상 worker 전부에서 비어 있음을 측정한다. 정지된 container가 게시하는 port도 포함한다. |
| R2 | Medium | 확인 | 관리 `workspaces` 폴더를 쓰는 shipped code가 없다. `lan-workspace-v1` 실행은 16 MiB tmpfs `/workspace`(`snapshot-tmpfs-v1`)를 쓴다. workspace upgrade는 state volume과 Docker socket만 mount한다. host 폴더를 쓰는 유일한 경로는 `worker_storage`의 `/contribution`(read-only, container를 처음 만들 때만)이다. | 폴더를 선택적 read-only storage contribution 원본으로 기술하거나 제안에서 뺀다. storage 20 GiB는 이를 강제하는 코드가 없는 정책 상한이다. |
| R3 | Medium | 가능성 | 사람 계정 UID가 소유한 0700 폴더는 Node container가 읽지 못할 가능성이 크다. container는 root로 실행되지만 `--cap-drop ALL`이라 DAC override가 없다. README의 NODE-0005(signer.pub)와 같은 종류의 실패다. | 소유자와 mode는 검토에서 정하고, 사용 가능하다고 말하기 전에 일회용 probe로 읽힘을 증명한다. |
| R4 | Medium | 가능성 | `worker_workspace.install`은 기존 Cmd를 유지한다. storage를 설정했다면 Cmd에 `--storage-policy`가 남는다. 그런데 mount는 `/contribution` 없이 다시 만든다. 한 Node에서 storage contribution과 workspace를 같이 쓰는 경로는 검토된 적이 없다. | Codex가 검토하거나 시험하기 전에는 같은 Node에서 둘을 결합하지 않는다. |
| R5 | Low | 확인 | 2000m/2 GiB/20 GiB/GPU0 계산은 맞다. 1~3번의 기록된 상한과 측정된 여유보다 모두 작다. 다만 shipped container 한도는 고정값이다(agent 0.5 CPU/256 MiB, workload 1 CPU/512 MiB/30초/network none). 2 CPU/2 GiB는 정책 상한일 뿐 강제 quota가 아니다. | 문구로 구분한다. |
| R6 | Info | 확인 | `lan_workspace.py`는 state의 최상위 nodeId만 패키징하며 `--node-id` 옵션이 없다. Codex의 보고와 같다. | 다섯 대상용 경로는 별도로 구현하고 검토한다. |
| R7 | Info | 확인 | 아직 commit하지 않은 문구 수정은 메시지와 그에 맞춘 시험 문자열만 바꾼다. `>= (1,45)` guard는 그대로다. 단, 고친 `prepare-worker.sh`로 만든 bundle은 `59f0a3c2` bundle과 bytes가 다르다. | namespace마다 source를 하나로 고정한다. |

resource 상한과 GPU0 제안은 R2·R3·R5 문구를 보정한다는 조건으로 수락한다. folder 제안은 R2·R3가 해결될 때까지 `approved:false`를 유지한다. 이 값은 독립 정책 검토가 남아 있다는 뜻이며, 프로젝트 승인을 다시 받아야 한다는 뜻은 아니다.

## 11-10 전 worker1·2 첫 wave 조건

날짜만으로 막을 이유는 없다. 그러나 r5 guard가 매 slot에서 검사하는 입력은 그대로 유지돼야 한다. r5 `private-state.json`의 hash, source03와 executor의 tracked-clean HEAD, cycle plan의 입력 pin 106개, 고정 실행 파일(python/ssh/scp/powershell/node/git), overview 18082의 구성원이 정확히 r5 Node 2개이고 fresh일 것, owner SID·session 1·interactive, 그리고 receipt root에 completion-unknown이나 결과 없는 intent가 없을 것이다.

새 namespace는 구조상 이 입력들을 건드리지 않는다. container·volume 이름과 Node 폴더는 새 nodeId에서 나오고, image tag `saintvision-lan-node:<epoch8>`은 새 epoch에서 나오며, 방화벽 규칙은 manifest의 nodePort를 쓴다. 그래서 다음 조건을 **모두** 지킬 때만 수락한다.

1. R1에 따라 측정으로 비어 있음을 확인한 port만 쓴다.
2. source03 worktree나 그 venv가 아닌, 정확한 source의 별도 checkout과 interpreter에서 실행한다.
3. 모든 후속이 정산될 때까지 CP의 Python, Git, OpenSSH, Node, PowerShell을 바꾸지 않는다.
4. 별도 DB instance와 role을 쓰고, r5를 서비스하는 PostgreSQL은 재시작하거나 설정을 바꾸지 않는다.
5. 14:45 표본의 host free RAM은 0.55 GB였다. 새 serve/observe를 띄우기 전에 실제 메모리 여유를 측정한다.
6. 후속 실행 구간에는 새 f5 process를 띄우거나, 등록 단계를 진행하거나, worker1·2에 부하를 주지 않는다. 구간은 slot 시각부터 slot+10분 grace+14520초까지다: 11-08 14:20~18:32, 11-09 12:15~16:27, 11-10 08:00~12:12 KST.
7. 결과는 새 2-node 관측 namespace로 표기한다. 같은 host의 r5 Node와 f5 Node를 합산하지 않는다.

구성원은 다음과 같다. worker1·2는 후보다. worker3는 socket 접근과 API 측정이 남아 차단, worker4는 endpoint를 몰라 차단, CP는 API 1.41과 Ubuntu WSL 부재로 차단이다. 따라서 다섯 대 구성은 아직 부분 상태다.

## CP Docker 업그레이드: 상태 기반 해제 조건

`138ece54`의 "11-10 08:00 이후"를 다음 상태 조건으로 **대체한다**. 아래를 모두 만족해야 해제한다.

- 각 후속 run에 최종 결과(renewed 또는 기록된 skip)가 automation run history에 남아 있다.
- canonical run의 attempt latch가 없거나 phase가 `completed`다.
- lock과 lock.guard가 없다.
- 어떤 receipt root에도 `*.completion-unknown.json`이나 결과 없는 `*.intent.json`이 없다.
- 살아 있는 Cycle controller child process가 없다.
- config(`ca684b45…`), release parameters(`d46ddd2a…`), guard(`acf8b4f6…`) pin 세 개가 그대로다.
- r5 overview가 200이고, pin된 2 Node가 online/fresh이며, 가장 이른 leaf notAfter가 계획한 margin을 넘는다.

영향이 없다는 증명으로 이 조건을 대신할 수는 없다. Docker는 고정 실행 파일 목록에 없고 r5 DB도 외부에 있다. 하지만 설치기가 logoff, 재부팅 또는 session 변경을 일으키면 18082/3000/55448이 멈추고 session/interactive gate가 깨진다. 이 가능성은 pin한 target 버전의 release note로만 배제할 수 있다. 08:00 자체는 해제 시각이 아니다. 마지막 slot의 결과가 기록된 뒤에 해제하며, 그 slot이 실제 Cycle을 돌리면 최대 11-10 12:12 KST까지 걸린다.

## 권한 문구 정정

`138ece54`의 "새 사용자 권한 필요"는 다음과 같이 정정한다. **기존 프로젝트 승인은 유지되며 일반 동의를 다시 묻지 않는다.** 실제 경계는 네 가지다.

- 설치기와 방화벽 규칙에 OS 관리자 권한이 필요한데, 이 session에는 그 능력이 없다.
- Docker Desktop을 종료하면 running 8개가 멈춘다. 그중 7개는 다른 제품(coco-annotator 2, saint-control 5)이고 나머지 1개는 옛 node1 pilot DB다. 따라서 유지보수 시간과 영향을 조율해야 한다.
- data distro migration 전에 WSL data vhdx를 백업해 데이터를 보존해야 한다.
- 진료 stack container는 열지 않는다.

## rollback 자산 (읽기 전용 탐색)

다음 경로만 범위를 정해 찾았다: Downloads/Desktop/Documents, `C:/Program Files/Docker/Docker`, `C:/ProgramData/DockerDesktop`, `%LOCALAPPDATA%`·`%APPDATA%` Docker, `C:/ProgramData/Package Cache`, D:의 installer/backup 후보 폴더(모두 없음). 찾은 것은 설치 폴더 안의 `Docker Desktop Installer.exe` 하나다. 버전 4.16.3.96739, 7,408,976 bytes, sha256 `991dc4bc…5cdc`이고, Authenticode는 Valid(CN=Docker Inc, timestamp 있음; 서명 인증서 notAfter 2023-10-04)다. 그러나 이 파일은 업그레이드가 교체하는 폴더 안에 있고, 전체 설치 파일보다 훨씬 작아 오프라인 재설치가 되는지 증명되지 않았다. 전체 오프라인 설치 파일과 vhdx 백업이나 manifest는 **없다**. 결론적으로 쓸 수 있는 rollback 자산은 아직 없다.

업그레이드 전 필요한 준비는 다음과 같다. 공식 4.16.3 설치 파일을 게시된 checksum과 함께 보관하고, vhdx 백업 manifest를 만든다. target 버전은 공식 release note로 고정한다. 그 release note에서 Engine 버전, server API 최대가 1.45 이상이고 MinAPIVersion이 1.45 이하인지(node-agent 협상 상한), data-distro migration 내용, 설치 파일 checksum을 확인한다. 다운로드·실행·정지·export는 하지 않았다.

## root 통합 문서 delta `70dcb699..8585b61b` 범위 검토

root가 요청한 범위의 검토다. 대상은 `agent/codex/fleet-five-orchestration-20261105`의 5개 파일이며 모든 local check를 다시 돌리지는 않았다.

- **통합 정확성**: 통합 branch에 들어간 Claude History/Evidence와 Codex History/receipt의 blob이 각각 `138ece54`·`6ba9ee46`의 blob과 같다. 인용한 Docs CI 41977218989(`939e6dae`)와 41978843474(`8585b61b`)는 모두 completed/success다.
- **사실 수락과 계획 정정의 구분**: 올바르다. 측정 결과는 수락했고, 배치 제안은 실행 수락하지 않았다. port 충돌, 날짜만 보는 지연, 포괄적 재승인, 정산 조건(grace 10분과 4시간+120초)을 정정으로 분리했다. 4시간+120초는 guard config의 `maximumWaitSeconds` 14520과 같다. inventory exit 0/1 차이에 대한 설명도 내 측정과 일치한다.
- **가짜 완료 주장 없음**: Claude 작업판 절은 root의 수신 기록이라고 명시했고 Claude 검토 완료를 대신 주장하지 않는다. `fiveNodeOperationalAcceptance=false`, `remoteMutationExecuted=false`이며 원래 48-task와 VF-CL은 그대로다.
- **Low**: Index·착수 History의 "CPU2000m/RAM2GiB/storage20GiB/GPU0은 상한과 여유 안"이라는 문장은 계산상 맞다. 다만 위 R2·R5(폴더를 쓰는 코드 없음, storage 상한을 강제하는 코드 없음)를 함께 적어야 정책 수락으로 오해되지 않는다.

판정: 범위 delta는 수락하며 Low 1건이 있다. 이 판정은 게시·운영 인수와 별개다.

## 인계

- **Codex**: R1(측정된 port), R2~R4(폴더 성격·소유자/mode·storage와 workspace 결합), R7(source 고정)를 첫 wave의 hash packet에 반영한다. 위 조건 1~7의 측정 결과를 붙여 root에 제출한다.
- **root**: CP는 해제 조건과 OS 관리자·유지보수 조율이 갖춰지기 전까지 차단으로 유지하고, worker4 endpoint를 받는다.
- **Claude**: Codex의 실제 첫 wave packet이 게시되면 독립 검토한다.

원래 48-task 상태와 VF-CL 0/5는 바꾸지 않았다. 공통 진행판, registry, Obsidian apply도 바꾸지 않았다.
