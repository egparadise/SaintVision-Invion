---
doc_id: "NODE-RUNTIME-CONTRACT-001"
title: "Codex Node 실행 격리와 정지 영수증 계약"
version: "1.1.0"
status: "review"
author: "Codex"
updated: "2026-09-11T09:27:00+09:00"
source_of_truth: "Git"
---

# Codex Node 실행 격리와 정지 영수증 계약

Task node-runtime / owner Codex / reviewer Claude(pending). Base `85a8747a92efd56d14ed7fdfcba85fe03f60463f`, branch `agent/codex/node-runtime`. OUT-03/AC-03·OUT-04/AC-04의 Go Linux 실행 경계를 구현한다. [[Codex ToolGateway 실행 허가와 Sandbox 계약]]의 claim을 실제 Docker 실행과 물리 정지 확인에 연결한다. S03-BE 및 선행 S01/S02·실장비·독립 검토는 미완료다.

## ADR-027 서명된 단기 실행 허가와 durable inbox

Control Plane의 Ed25519 private key로 `SaintVision.NodePermit.v1\0` domain과 canonical JSON bytes를 서명한다. Node에는 공개키만 고정하며 tenant/Node/recoveryEpoch/profile/image/executable도 운영자가 별도로 고정한다. 서명은 암호화가 아니다. 공개 웹 endpoint나 mTLS bootstrap은 이번 범위에 없다. signer 입력은 신규 ClaimResult만 허용하고 claim replay에는 새 permit을 발급하지 않는다.

JSON Schema v1alpha1에 NodeAllocation·NodeExecutionPermit·SignedNodePermit·NodeStopReceipt를 추가하고 Python/TS/Go 타입과 Node embedded schema를 같은 원본에서 생성한다. Go는 duplicate key·과도한 크기/중첩·unknown field·timestamp 형식을 먼저 거절하고 서명된 launch의 원래 JSON bytes hash를 planDigest와 비교한다. Python canonical JSON의 Unicode escape와 정렬을 유지해 byte binding한다. CPU/memory 전체 lease 증명, tenant/run/Node/epoch/token/만료·로컬 allowlist를 대조한다.

Linux 전용 private 0700 journal과 flock으로 worker를 단일화한다. 개별 0600 entry·fsync·directory fsync, allocation별 token high-water, commandId별 불변 intent가 **Docker create 이전**에 저장된다. journal에는 raw argv를 저장하지 않는다. 재전달은 기존 영수증 조회 또는 정지 reconciliation만 수행하며 재시작하지 않는다. corruption·다른 epoch·상태 불명은 fail closed다. 운영 중 state directory 삭제/교체 및 epoch 자동 초기화는 금지한다.

## ADR-028 독립 PID 1 기한과 제거 후 stop ACK

Docker Engine local Unix socket만 사용한다. ADR-062부터 `/version`의 Linux OS·최소/최대 API를 확인하여 클라이언트 지원 범위 1.41~1.45 안에서 협상한다. 범위가 겹치지 않거나 응답이 잘못되면 실행 요청 전에 거부한다. CgroupnsMode를 위해 1.41보다 낮은 API로 내리지 않는다. 성공한 협상만 캐시하며 create/start/stop/delete를 자동 재전송하지 않는다. 입력 permit/DOCKER_HOST/proxy가 privileged 연결을 바꾸지 않는다. 미리 설치된 image content ID (`sha256:...`)만 허용하며 pull하지 않는다. 이는 registry manifest digest와 구별된다. 추후 registry resolver는 별도 신뢰 경계다. approved image는 이 저장소의 `/inv-supervisor`를 PID 1으로 포함하고 `ai.saintvision.supervisor=deadline-v1` label을 갖는다. label 자체는 attestation이 아니며 image content allowlist가 신뢰 근거다.

컨테이너는 UID/GID 65532, network none, read-only root, 모든 capability 제거, no-new-privileges, PID limit 64, CPU quota, memory/swap hard limit, private IPC/cgroup namespace, host mount/device/port 없음, /workspace와 /tmp의 제한된 noexec tmpfs만 사용한다. daemon이 생성한 실제 설정을 다시 대조한 뒤 start한다. 후속 ADR-041에서 bounded stdout/stderr 수집을 추가했으며 ADR-062부터 Docker `json-file` log 512 KiB/1개로 제한한다. 성공/실패 출력의 확정 조건은 [[Codex 실행 완료와 자원 회수 통합 계약]]을 따른다. GPU·host 명령은 이번 구현에 없다.

API 협상 근거: [Docker Engine API 공식 문서](https://docs.docker.com/reference/api/engine/). 실제 20.10.22/API 1.41의 실행 증거와 최신 daemon의 협상 단위 시험은 [[2026-09-11_NODE-COMPAT_Codex_검증보고]]에서 구분한다.

Node Go monotonic deadline은 claim.notAfter에서 허용 clock skew 5초를 뺀 시간과 workload timeout 중 작은 값이다. intent fsync와 create/start 시간도 포함한다. signed permit TTL 상한은 30초다. PID 1 supervisor는 별도 monotonic timer를 가지므로 Node process가 SIGKILL로 중단되어도 기한에 종료된다. workload는 child process group이며 PID 1 종료는 namespace 내 남은 프로세스를 종료한다. supervisor의 dumpable을 끄고 raw 출력은 보존하지 않는다.

정상 종료·timeout·CLI SIGTERM·재시작 reconciliation은 소유 label과 container ID를 검증하고 running/restarting=false, pid=0, created/exited를 확인한다. 이어 `force=false` 삭제 성공을 확인한다. **삭제 전에 ACK하지 않는다.** 지연된 Docker start 요청은 삭제된 ID를 다시 실행할 수 없다. 정지/삭제/영수증 fsync가 불명확하면 ACK하지 않고 자원을 유지한다. create 응답 유실 후 container 부재도 실행 부재의 증거가 아니므로 자동 재실행하지 않는다. 삭제 후 receipt 저장 직전 crash는 수동 조사 상태로 남을 수 있다.

## Control Plane 반환 트랜잭션

인증된 NodePrincipal adapter에서만 NodeReceiptStore.record를 호출한다. Run 잠금 → 정확한 전체 lease 집합 → Node/Resource 잠금 순서로 현재 claim/tenant/project/run/Node/epoch/plan/fence/amount/kind를 대조한다. 0004 migration의 forced-RLS 불변 node_stop_receipts 삽입, 전체 lease released_at/stop_receipt 갱신, inv.execution.stopped outbox를 한 트랜잭션으로 처리한다. 동일 영수증 재전달은 원본을 반환하고 변경된 영수증은 거절한다. lease 만료 자체는 해제가 아니지만 실제 stop 영수증은 만료 뒤에도 처리한다.

exit code 0은 process stop이며 application success Evidence가 아니다. Run은 scheduled로 유지하며 running/verification/Artifact 연결은 후속 adapter 계약이다. Control Plane cancel을 이 CLI로 전달하는 authenticated transport는 아직 없으므로 UI cancel 즉시 물리 정지를 보장하지 않는다. 현재 지원은 bounded CPU 단일 worker Linux Docker/cgroups v2이며 Windows/GPU/5대 실장비/운영 가용성 증거는 없다.

## 합격 증거와 인계

단위 시험은 서명/내용 바꿔치기·정책 완화·clock/fence·동시 8개 command·lost ACK·unknown create·late start/remove 실패·재시작·journal 오염·timeout/cancel을 검증한다. CI는 FROM scratch로 Go 합성 probe와 supervisor를 빌드해 실제 권한/네트워크/파일시스템/cgroup 제한, Python→Go Unicode permit, Node SIGKILL 후 독립 정지, 실제 stop receipt 반환·DB rollback을 검사한다. 실행 전 작성된 항목은 시험 계획이며 실제 결과는 History 검증보고에 연결한다.

Claude는 transport identity·key provisioning/rotation·current PDP/capability verification·Run/Evidence adapter 및 본 경계의 독립 검토를 담당한다. Gemini는 stop receipt 전 자원 반환과 exit 0 성공 표시를 하지 않는 계약을 수신한다. 리뷰 수행·운영 배포·S03 done으로 표시하지 않는다.

설계 근거: [Docker Engine API 1.45](https://docs.docker.com/reference/api/engine/version/v1.45/), [Go monotonic clocks](https://pkg.go.dev/time#hdr-Monotonic_Clocks), [JSON Schema Go 구현](https://github.com/santhosh-tekuri/jsonschema/blob/v6.0.2/README.md). JSON Schema v6.0.2와 cryptography 50.0.1을 고정한다. 실제 protocol/security 선택은 이 프로젝트 결정이며 외부 문서가 프로젝트 검증 결과를 보증하지 않는다.

실제 구현·CI 증거: [[2026-09-10_01-16-02_KST_NODE-RUNTIME_Codex_검증보고]]. Linux Docker/PostgreSQL 포함 Python 194개와 Go 37 leaf case 통과. 독립 검토·운영 transport·Windows/GPU/실장비는 pending.
