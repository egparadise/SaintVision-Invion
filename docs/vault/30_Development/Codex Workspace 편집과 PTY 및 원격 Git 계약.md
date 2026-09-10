---
doc_id: "CODEX-WORKSPACE-BRIDGE-001"
title: "Codex Workspace 편집과 PTY 및 원격 Git 계약"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T17:07:26+09:00"
source_of_truth: "Git"
---

# Workspace 편집·PTY·원격 Git 후속 계약

WORKSPACE-BRIDGE / S06-BE/DB/ST 부분 / OUT-06·AC-06. owner Codex, 독립 reviewer Claude pending. base PR17 `dac25591adfb61a4a81382f737c4d1eed34c07d5`, branch `agent/codex/workspace-bridge`. GUIDE/PLAN-BACKEND/DB/STORAGE/GOV-AGENT/GOV-GIT v1.0.0와 ADR-056을 잇는다. **사용자 요청으로 이번에는 실제 시험을 수행하지 않는다. 구현·정적 검사·컴파일 성공은 AC-06 합격 증거가 아니다.** 이전 PR17 990개 통과를 새 코드의 시험 증거로 재사용하지 않는다.

## ADR-057 — 편집 revision과 다음 Node 입력의 일치

`GET/POST /v1/projects/{project}/runs/{run}/checkouts/{checkout}/files`는 현재 JWT와 프로젝트 권한, 업무 Run이면 public/kernel 권한 교집합을 검사한다. POST는 Idempotency-Key, expectedRevision, 전체 expectedSha256와 파일별 expectedSha256를 요구한다. null expectedSha256는 생성, null dataBase64는 삭제다. 파일 bytes는 canonical Base64와 실제 SHA-256으로 검증한다. 경로 탈출·대소문자 충돌·파일/디렉터리 충돌을 거부한다.

편집은 원본 generation을 덮어쓰지 않고 `inv.workspace_edits`에 불변 snapshot revision을 추가한다. filesystem 원본과 marker/identity를 계속 검사하고, UI 파일 조회·business edit-stop·Workspace prepare가 같은 최신 revision을 사용한다. 작업이 recovering이고 checkout attempt/epoch가 현재이며, 실제 자원 반환 완료·업무 Workspace ready·편집 lock/동결 Step 없음 조건에서만 쓴다. root → tenant gate → Run 순서로 serialize한다. 같은 key의 정확한 재요청은 현재 권한을 재검사한 뒤 기존 결과를 반환한다.

다음 Step은 고정한 snapshot bytes를 서명된 launch에 넣고 Node private tmpfs에서 쓰기 가능한 파일로 만든다. host 공유 폴더를 노출하지 않는다. 현재 상한은 파일 내용 합계 32 KiB, manifest 64 KiB이며 대용량 편집/전송은 별도다. 편집 revision 증가와 이벤트는 같은 transaction이다.

## ADR-058 — 명시적 대체 Node

WorkloadSpec.targetNodeId는 optional NodeId이며 지정하지 않으면 설정된 기본 Node를 사용한다. 지정한 Node는 운영 설정의 destinations에 있어야 하고 tenant·프로젝트 membership·현재 epoch·실제 관측·자원/격리 profile을 통과해야 한다. Node 선택은 workload digest와 새 2인 승인에 포함된다. 변경할 때 새 prepare/승인이 필요하다.

설정은 기본 Node 포함 최대 5개이고, 같은 authoritative workingRoot를 사용한다. 각 목적지는 기존 nodeId/resources/profile/policyVersion/signingKeyFile/tls의 완전한 신뢰 설정이다. HTTP가 endpoint·key·policy를 공급하지 않는다. 대체 Node runtime으로 probe/예약/claim/서명/queue를 일치시키고 ToolGateway가 targetNodeId와 인증된 Node를 비교한다. 이전 Node 물리 정리와 최대 attempt 경계는 기존 Workspace 계약을 따른다. 5대 실제 이동·장애 복구 성공은 아직 측정하지 않았다.

## ADR-059 — 제한된 실제 PTY와 브라우저 ticket

WorkloadSpec.terminal은 sessionId/rows/columns/maxInputBytes/maxOutputBytes다. operator profile.allow_terminal=true, 고정 Workspace 입력, 이미지 label `ai.saintvision.terminal=pty-v1`를 모두 요구한다. 기본은 비활성이다. Linux PID1 supervisor가 /dev/ptmx를 열고 승인된 child에 controlling terminal을 붙인다. 기존 non-root·network none·read-only root·cap drop·pids/cpu/memory와 최대 30초 제한은 그대로 적용한다. Windows PTY provider는 없다.

Node `POST /v1/terminals/frame`은 현재 실행 중인 원래 signed permit에만 접근하며 workload를 재실행하지 않는다. Docker exec는 image-owned `/inv-supervisor --terminal-frame`으로 고정하고 사용자는 65532다. helper는 private Unix socket으로 PID1 PTY에만 전달한다. 취소/heartbeat 처리 lane과 분리한다. 명령 종료·Node 재시작 뒤 입력을 복원하거나 자동 재실행하지 않는다.

브라우저 계약:

1. JWT Authorization과 정확한 Origin으로 `POST /v1/workspaces/{workspace}/terminal-tickets`, body commandId를 보낸다. 현재 원 요청자·Run running·attempt·Node/lease/epoch·프로젝트 권한을 확인한다. ticket은 최대 30초이고 JWT·명령 만료보다 짧다. DB에는 SHA-256만 보관한다.
2. 응답 websocketPath로 subprotocol `inv-terminal-v1`을 사용한다. URL query는 금지한다. 최초 5초 안에 `{"ticket":"..."}` 단일 JSON frame을 보낸다. Origin/session/Workspace 일치 및 ticket의 원자 1회 소비를 확인한다.
3. command당 durable connection lease 하나, 서버당 attachment 최대 32개다. lease는 최대 5초씩 원 ticket 만료 이내로 갱신한다. 매 frame 전후 현재 권한·kill switch·Run·Node/채널·자원을 재확인한다. disconnect의 해제는 connection ID CAS로 처리한다.
4. TerminalFrameInput의 operation은 poll/input/resize다. poll은 sequence=0, 빈 dataBase64를 사용하고 입력 순번을 소비하지 않는다. input/resize는 현재 sequence+1이다. 성공한 마지막 frame의 동일 nonce/내용 재전송만 결과를 재사용한다. 부분 write/불확실한 입력은 session을 중지 상태로 두고 재전송하지 않는다. 입력은 frame당 1 KiB, 합계 승인 상한 이내, mutation sequence 최대 4096이다.
5. Node 출력은 frame당 최대 4096 bytes, transcript 최대 승인 상한 64 KiB다. 브라우저는 매 attachment에서 cursor 0부터 읽으며 서버 응답 cursor를 다음 입력에 사용한다. 입력 응답을 잃으면 재접속 후 poll로 현재 sequence를 확인한다. 이미 확인된 순번을 새로운 nonce로 재사용하지 않는다.
6. TerminalBrowserOutput은 sessionId/sequence/cursor/text/outputMode다. UTF-8 완성 줄에만 redaction을 적용하여 전달하고 ANSI/control sequence와 알려진 token·비밀키 패턴을 걸러낸다. **줄바꿈 없는 prompt는 보이지 않으며 전체 ANSI 터미널 에뮬레이터가 아니다.** 모든 형태의 secret 비누출은 별도 평가가 필요하다. UI는 text로 렌더링하고 HTML로 해석하지 않는다.
7. production 시작점은 WebSocket message 8192 bytes·queue 1·압축 해제 설정을 고정한다. pinned uvicorn/websockets 구현에서 이를 확인한다. ticket/키입력/출력 원문을 감사 이벤트에 쓰지 않는다. frame 감사는 command+sequence당 한 번이고 digest/메타데이터만 보관한다.

## ADR-060 — 고정 원격 Git과 불확실한 publication

현재 provider는 GitHub.com의 REST Git object 읽기와 GraphQL createCommitOnBranch다. Node sandbox의 network 정책을 열거나 host git/hooks/shell을 실행하지 않는다. workspace.gitRepositories 운영 설정에 alias/projectId/repository/branch/tokenFile을 명시한다. alias는 프로젝트에 고정되고 credential은 권한 제한 파일에서 읽는다. HTTP는 URL·repo·branch·credential을 변경할 수 없다. 기본 repository 목록은 비어 있다. 설정/키 발급과 실제 원격 쓰기는 이번 개발에서 수행하지 않았다.

`POST /v1/projects/{project}/runs/{run}/checkouts/{checkout}/git`은 Idempotency-Key와 RemoteGitProposalInput(alias, mode pull/push, 정확한 commit SHA-1, expectedRevision/expectedSha256)를 받는다. 원격 고정 commit/tree/blob을 읽고 bounded snapshot을 만든 후 현재 편집본/권한을 다시 확인하여 intent를 기록한다. 파일별 Git blob SHA-1과 실제 SHA-256을 계산한다. commit/tree 관계는 TLS로 인증한 GitHub 응답을 신뢰하며 독립 서명/전체 Git Merkle 검증을 수행했다고 주장하지 않는다.

파일 수 최대 128, 트리 항목 최대 256, 내용 32 KiB이며 정규 비실행 파일만 지원한다. symlink/submodule/executable/빈 디렉터리의 묵시적 손실을 거부한다. push는 로컬 `.git` metadata를 제외한 snapshot을 승인 대상으로 만든다. 그 외 모든 파일의 추가/변경/삭제가 제안에 표시된다. pull은 **전체 편집 snapshot 교체**이며 merge/conflict resolution이나 로컬 `.git` 유지가 아니다. 새 snapshot을 별도 revision으로 추가하므로 이전 revision은 보존된다.

`GET /v1/projects/{project}/git/{operation}`으로 snapshot·changes·대상·내용 digest·만료·phase·votes·result를 검토한다. `/votes`는 contentDigest와 approve/reject를 받는다. 요청자는 현재 operator can_git 및 프로젝트 can_request, 승인자는 operator can_approve 및 프로젝트 can_approve를 가져야 한다. 신원은 운영자가 검증한 immutable person_id이며 서로 다른 두 사람이어야 하고 요청자와 같으면 안 된다. can_git는 migration에서 false가 기본이고 runtime role은 operator 권한을 발급할 수 없다. 같은 투표만 replay하며 바꾸지 못한다. 요청 최대 5분, gate version·epoch·편집 revision·현재 권한을 apply 직전에 다시 확인한다.

`/apply`의 pull은 DB 안에서 새 revision과 완료 이벤트를 원자 확정한다. push는 먼저 durable phase=dispatched를 commit한 단 하나의 호출자가 네트워크 밖에서 1회 mutation을 보낸다. `expectedHeadOid`는 원격 branch 변경과 commit 생성을 비교 조건으로 묶는다. 임의 force update는 없다. 생성 commit의 parent/operation marker/실제 파일 snapshot을 다시 읽어 확인한 후 완료한다. 이 기록은 Git operation/event이며 Node 실행 receipt나 Run 성공으로 위장하지 않는다.

응답 유실·CP crash·provider 거부로 결과가 확정되지 않으면 phase=dispatched를 유지한다. 이 상태의 apply는 **네트워크 쓰기를 재시도하지 않는다**. 같은 tenant/repository/branch의 다른 미확정 push도 partial unique index로 차단한다. `/reconcile`은 현재 head의 parent·operation marker·내용을 읽어 일치할 때만 완료한다. head가 바뀌었거나 CP가 dispatch commit 직후 중단되어 전송하지 않은 경우 등은 수동 검토/forward fix가 필요하며 자동 해제하지 않는다. 정책 해제 없이 모호한 이력을 지우지 않는다.

DB/working-root lock 안에서 네트워크를 호출하지 않는다. **kill/권한 회수는 새 Git dispatch를 막지만 이미 GitHub에 보낸 publication을 회수할 수 없다.** 이후 read-only reconciliation은 허용한다. 원격 응답/credential/파일 원문을 예외나 감사 이벤트에 노출하지 않는다. 인증 호스트는 api.github.com으로 고정하며 proxy/redirect/자동 retry를 쓰지 않는다.

## DB·배포 및 후속 검증

0023 뒤 0024_workspace_bridge forward migration은 workspace_edits, terminal_tickets/connections/frame_audit, git_operations/votes, operator.can_git를 추가한다. 모두 tenant FORCE RLS와 최소 column grant를 적용한다. immutable intent/vote/revision과 일회 ticket/dispatch 상태 전이를 보존한다. 기존 migration을 수정하지 않는다. 실제 DB 적용·upgrade/restore/rollback은 아직 수행하지 않았다. downgrade 대신 검토된 forward fix 또는 검증된 backup restore가 필요하다.

이번 branch에 한해 Core의 build_only job을 실행하고 기존 runtime/DB 시험 job 및 docs sync 시험을 제외한다. 정상 branch는 기존 전체 시험을 유지한다. build-only artifact의 validation-mode.json은 executionTests=deferred-by-user, acceptance=pending이다. PR을 merge하지 않은 채 후속 시험 단계에서 이 branch 조건을 제거하고 같은 코드에 대해 전체 CI를 실행해야 한다. 문서 check_docs/check_ontology·컴파일·offline SQL render는 허용된 정적 확인이다.

작성한 회귀 시험 소스도 이번에는 실행하지 않는다. 실제 인수 순서는 다음과 같다.

| 담당 | 다음 작업과 합격 증거 |
|---|---|
| Codex | editor CAS/동결/권한회수/경합, 0023→0024/전체 경로·RLS·immutable trigger, Go PTY 입력 중복/부분 write/timeout·취소·출력 budget, ticket 중복·교차 Origin/session·재접속·expiry·Node 재시작, 실제 대체 Node/해시/Evidence, Git 실제 sandbox repo의 CAS/2인승인/권한회수/crash·lost response/불확실 dispatch 격리. 전체 회귀와 고정 SHA 증거 필요 |
| Claude | 독립 코드/DB 계약 검토, 첫 Run/checkout 및 verified person/project/Node provisioning, 실제 IdP/PKI/Node·Git 설정, worker 운영/관측·DB 이관과 검토된 수동 Git reconciliation 절차 |
| Gemini | editor revision conflict, 목적지 Node 선택, 만료 ticket과 text-only PTY/줄 단위 제한, Git diff/전체 pull 교체/2인 승인/불확실 상태 화면을 실제 API와 연결하고 접근성·브라우저 여정 검증 |

대용량 Git/Workspace, 일반 SSH/다른 Git provider, 장시간/full-screen terminal, Windows/GPU/BuildKit 격리, 전체 Context/RO secret 평가와 물리 5대 부하·장애·복구/운영 인수는 후속 범위다. peer review를 수행한 것으로 표시하지 않는다.

외부 계약 참고: [GitHub createCommitOnBranch](https://docs.github.com/en/enterprise-cloud%40latest/graphql/reference/commits), [Git file changes](https://docs.github.com/en/graphql/reference/git), [Go SysProcAttr](https://pkg.go.dev/syscall#SysProcAttr), [Docker Engine API v1.45](https://docs.docker.com/reference/api/engine/version/v1.45/), [websockets package](https://pypi.org/project/websockets/).
