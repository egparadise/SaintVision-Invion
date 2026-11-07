---
doc_id: "HISTORY-FLEET5-20261107-THREE-CPU-PILOT-EVIDENCE-REVIEW-CLAUDE"
title: "2026-11-07 FLEET5 3대 CPU 관측 pilot 운영 증거 독립 검토"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-07T17:35:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "1efea494f026e932360c35ae811b6423d874a2e7"
task_ids: ["FLEET5-THREE-CPU-PILOT-EVIDENCE-REVIEW-R1-20261107"]
tags: ["fleet5", "independent-review", "cpu", "observation", "claude"]
---

# 3대 CPU 관측 pilot 운영 증거 독립 검토

Orca `task_682a17fab13c` / dispatch `ctx_9dcd414de698`의 독립 검토다. 검토자는 Claude 하나뿐이고 helper·subagent는 쓰지 않았다. 검토 대상은 Root가 실제로 수행한 운영의 공개 증거이며, 자기 검토나 소스 구현이 아니다.

- branch `agent/claude/fleet5-three-cpu-pilot-review-r1-20261107`를 17:30:26 KST에 `1efea494`(제품 source이자 delivery base)에서 만들었다.
- Root 증거는 정확한 commit `baaa8ea9`(원격 ref와 Root HEAD가 같음)에서 `git show`로만 읽었다. [Root Evidence @baaa8ea9](https://github.com/egparadise/SaintVision-Invion/tree/baaa8ea99919a7fec40f8f853a648f4067d7248d/docs/vault/30_Development/Evidence/fleet5-20261105-root).
- 읽은 Root 보드 버전: Index 1.0.510, Codex 1.0.471, Claude 1.2.130, History 1.0.119. 지시된 공개 파일 49개와 Root History의 현재 절만 읽었다. Root `.work`·config·credential·PKI 비밀·transcript는 읽지 않았다.
- runtime recipe `5ba7cfb7`과 1efea의 소스는 로컬에 있어 추가 fetch가 필요 없었다. 읽은 소스: CLI, library, `services/control-plane/src/inv/observer_worker.py`, `services/control-plane/src/inv/node_channels.py`.

## 판정: ACCEPT_THREE_NODE_CPU_OBSERVATION_EVIDENCE_KEEP_REMAINING_LIVE_HOLDS

필수 결함은 0건이다. HIGH 0, MEDIUM 0, LOW 4(Root 운영상 조건부 의무, 비차단), INFO 8이다. 상세는 [review.json](../Evidence/fleet5-three-cpu-pilot-review-r1-20261107-claude/review.json)에 있다.

Root는 PC2·PC3·PC4의 새 현재 프로젝트 Node 3개를 관측 pilot으로 수락할 수 있다. 각 Node의 선택 기여량은 CPU 500m / 64MiB이고, 합계는 1500m / 201326592B다. 이 수락은 물리 자원 전체 공유, workload·Run·출력·audit·GPU·storage, browser, 5대, 전체 프로그램 완료를 뜻하지 않는다.

### 검토자가 직접 다시 계산·대조한 것 (DATA probe)

- **식별·서명 체계 (3대 모두).** 인증서 DER 구조를 직접 읽어 확인했다.
  - CN은 nodeId이고, URI SAN은 정확한 node URI 하나, IP SAN은 endpoint와 같은 주소 하나다.
  - EKU는 serverAuth뿐이고, CA=false(critical), Ed25519다.
  - AKI가 CA SKI와 같고, leaf 만료 11-09가 CA 만료 11-14보다 앞선다.
  - CA PEM·launch signer(32B raw)·CP client fingerprint는 세 대 모두 동일하며, 설치된 공개 파일 hash와도 같다.
  - PC2/PC4는 CSR hash가 일치하고, 인증서 공개키가 CSR 공개키와 같다. 즉 개인키는 대상 호스트에서 생성돼 그곳에 남았다.
  - peer policy는 정확히 6개 key이고, SHA를 다시 계산하면 pin 및 설치 파일 값과 같다.
- **APPLY 결속.**
  - 공개 요청과 DER을 1efea의 plan_body 공식에 넣어 계산한 plan digest(PC3 `95a6d6b5…`, PC2 `afc7af4a…`, PC4 `b8fafc2c…`)가 PLAN 값, APPLY 값과 모두 같다.
  - 요청 hash도 다시 계산해 일치했다.
  - 각 APPLY의 결과: 이전 0, 이후 node1·resources2·project link1·channel1·audit1·control1, offline, snapshot 0이다. channel cert는 DER hash와 같다. tenant control은 그대로이고, apply 1회·reconcile 0회다.
  - APPLY 래퍼는 CLI `8129ab5a…`(1efea와 일치)와 entry `42e89b61…`를 pin한다.
- **이미지·sandbox.**
  - bundle 하나(`7f7b9d3b…`)가 세 대에 같은 Node·workload image ID로 적재됐다.
  - Node container 설정: 500m/256MiB, pids 64, RO rootfs, CapDrop ALL, no-new-privileges. 포트는 호스트 LAN IP(leaf IP SAN)에만 열렸다. mount는 config RO, 빈 state RW, docker.sock 셋뿐이다.
  - argv는 node id를 빼고 세 대가 같다.
  - Node service 256MiB는 container 한도다. offer 64MiB는 DB metadata이자 profile의 workload 상한이다. 따라서 산술 모순이 아니다.
- **관측.**
  - source observer는 enabled current-epoch channel을 최대 5개까지만 받는다. 실제 enabled channel은 승인된 3개와 같은 집합이다.
  - 표본 주기는 약 7.6초(`stop.wait(5)` + 작업)다. probe 수와 수동 호출 0이 표준 loop의 자동 관측과 맞는다.
  - 기존 미연결 Node의 offline 전환은 Root가 승인한 범위다(tenant 한정, stale 60초 초과 정리).
- **실패 보존.** 다음 최초 실패를 성공으로 바꾸지 않고 원본대로 보존했음을 확인했다: workload/observer image r1, observer 시작 AssertionError, readiness probe r1, PC2 key 준비 r1, PC2 trust stderr 153B.
  - observer AssertionError의 정확한 원인은 확정되지 않았다.
  - PC2 공개 plan은 r1과 r2가 바이트까지 같다.
  - 알려진 원인의 복구는 운영 script 수정이며 제품 수정을 요구하지 않는다.

### Root 증거로만 인정하는 것 (검토자 실측 아님)

다음 두 기록은 내부 일관성(노드 집합, ID, 합계, 나이 < 15초)만 대조했다. 검토자가 장비나 런타임을 직접 시험한 결과가 아니다.

- Root 17:13:46 읽기 전용 8초 표본: 3대 모두 online이고 heartbeat·snapshot·probe가 증가했으며, 최대 나이는 2.10초다.
- Root 17:14:39 새 관리자 PKCE 세션의 nodes·capacity·usage 응답: 모두 200, 익명 요청은 401, 정확히 3대, 1500m / 201326592B.

browser 선택 프로젝트·깜빡임은 NOT_OBSERVED, 실제 workload는 NOT_RUN이다.

### 발견 (Root 운영상 조건부 의무, 필수 결함 아님)

- **FT-L1.** PC3 inventory의 tunnel 시작 receipt pin이 커밋된 blob과 다르다(pin 735B/`ecd66dca…`, blob 720B). blob의 줄바꿈을 CRLF로 바꾸면 pin과 정확히 같아진다. 즉 저장소의 eol=lf 정규화 때문이고 내용은 같다. 나머지 40개 항목은 바이트까지 일치한다. 다음 checkpoint에서 이 사실을 기록하거나 다시 pin하면 된다.
- **FT-L2.** 공개된 node-start 프로그램은 template이고, PC3 주소 `192.168.45.222`가 두 번 들어 있다. PC2/PC4에서 실제 실행된 바이트는 공개되지 않았고 hash도 없다. 치환 규칙과 렌더링된 바이트의 SHA를 기록할 것.
- **FT-L3.** observer bootstrap(`8cccc5a1…`)과 Dockerfile r2(`260f52d7…`)의 바이트가 비공개다. 그래서 "표준 observer, custom loop 없음"은 Root의 진술로만 남는다. 관측 주기가 source와 맞는다는 것까지만 확인했다. 비밀이 없는 바이트나 AST 요약을 공개할 것.
- **FT-L4.** CLI([CLI source line 24](https://github.com/egparadise/SaintVision-Invion/blob/1efea494f026e932360c35ae811b6423d874a2e7/tools/fresh_cpu_admission.py#L24))는 `<share>/services/control-plane/src`를 sys.path 맨 앞에 넣는다. 래퍼가 검증하는 것은 venv에 있는 library의 SHA이고, CLI가 실제로 import한 파일이 아니다. digest와 1efea 전용 receipt 필드는 검증된 library와 맞으므로 모순은 없다. 다만 다음에 CLI를 쓰기 전에 그 경로가 없다는 것을 읽기 전용으로 기록할 것.
- **INFO.**
  - I1: image load receipt의 tagOverwrite/oldContainerMutation 값은 측정값이 아니라 상수다. 기존 container 7개의 보존은 구성상(파괴 동사가 없음)으로만 뒷받침된다.
  - I2: admission은 PC3 operator 환경에서 실행됐다.
  - I3: PLAN 래퍼는 CLI를 pin하지 않는다.
  - I4: PC3 측 프로그램과 policy 본문은 비공개다.
  - I5: Node의 docker.sock은 호스트 root와 동등한 권한이다(설계상).
  - I6: 서명과 TLS handshake는 검토자가 다시 검증하지 않았다.
  - I7: freshness 여유가 충분하다.
  - I8: Windows 기본 trust로는 IdP TLS가 실패한다(HOLD 유지).

## 증거 귀속과 실행하지 않은 것

- [pilot_evidence_probe.py.txt](../Evidence/fleet5-three-cpu-pilot-review-r1-20261107-claude/pilot_evidence_probe.py.txt)(`9bf50a02…`)를 `.venv` Python `-I -B`로 scratch에서 실행했다.
  - 1차 실행은 exit 1이었다. 검토자 probe의 DER 외곽 SEQUENCE 처리 버그 때문이며, probe 두 줄만 고쳤다.
  - 2차 실행은 exit 0이고 출력은 [pilot-evidence-probe.json](../Evidence/fleet5-three-cpu-pilot-review-r1-20261107-claude/pilot-evidence-probe.json)(`b408dbf2…`)이다. 입력 49개 파일의 hash가 이 출력에 들어 있다.
  - probe는 bytes/JSON/AST/hashlib만 사용하며, 제품 import·crypto library·서명 검증은 하지 않는다.
- 실행하지 않은 것: SSH, DB, HTTP, browser, app, crypto, container, pytest, Go, Core/Backend CI. 검토자는 실장비도 검증하지 않았다.

## 남은 것과 다음 담당

다음 HOLD는 그대로 유지한다.

- PC1: SSH 255 / 이전 공개키 거부
- PC5: Docker API 1.41 < 1.45, main 자원 제약
- CP workspace 미구성
- 추가 실제 승인자 identity와 요청자가 아닌 서로 다른 두 사람의 실제 투표
- 실제 Run·출력·audit·GPU·storage·5대 인수
- Windows 기본 IdP TLS
- pilot policy 만료 11-08T07:15:30Z, leaf 만료 11-09T07:15:30Z, 갱신
- tunnel 자동 재연결·재부팅 복구
- Original19 HOLD, discharges 0, runtime B0, A1–A16 PENDING, H1–H7/H3EA/RD NULL_HOLD, raw7 UNREGISTERED, A01–A40 NOT_RUN

identity나 투표를 만들지 않았고 정책도 완화하지 않았다. 다음 첫 행동은 Root/Codex 집계자가 맡는다: 이 판정을 받고, FT-L1~L4를 자기 기록에서 처분한 뒤 남은 live gate를 진행한다. 로컬 gate와 sync CHECK 결과는 [local-doc-gates.txt](../Evidence/fleet5-three-cpu-pilot-review-r1-20261107-claude/local-doc-gates.txt)에 있다. 검토 SHA와 Docs run은 push 뒤 worker_done으로 보고한다.
