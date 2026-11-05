---
doc_id: "HISTORY-FLEET5-20261105-FIRST-WAVE-22FA-REVIEW-CLAUDE"
title: "2026-11-05 FLEET5 Codex first-wave 22fa3628 독립 검토와 CP Docker Desktop target 조사"
version: "1.0.0"
status: "review"
author: "Claude"
reviewer: "Codex"
audience: "agent"
updated: "2026-11-05T15:33:00+09:00"
timezone: "Asia/Seoul"
source_of_truth: "Git"
base_sha: "53f5722f"
task_ids: ["FLEET5-20261105-CP-AND-INVENTORY", "FLEET5-FIRST-WAVE-PLAN-20261105"]
tags: ["fleet5", "independent-review", "five-node", "control-plane", "docker", "claude"]
---

# Codex first-wave 22fa3628 독립 검토와 CP Docker target

Orca task `task_bab09fcf8dc7`, dispatch `ctx_88febf51813a`. 이 문서는 coordinator relay로 받은 요청을 처리한 결과다. 검토 대상은 Codex `22fa3628248280801281779b6a934fa6ff83e8f0`(branch `agent/codex/fleet5-first-wave-plan-20261105`, base `6ba9ee46`)의 History, Docker 문구·assertion 3개 파일 변경, 공개 plan `846a5b5c…`, 비공개 vector `a9c6d1e3…`이다. 작업은 15:27~15:33 KST에 했다. 정적 검토, hash 재계산, 공식 문서 읽기, 설치 파일 HTTP HEAD 확인만 했다. 설치 파일 본문 download, 설치, 중지, export, backup, 업무 payload 열람, 인증 시도는 하지 않았다. r5, pin, automation, registry, 공통 board도 바꾸지 않았다. 기계 판독 결과는 `Evidence/fleet5-20261105-claude/first-wave-22fa-review.json`에 있다. 앞선 기록은 [[2026-11-05_15-25-00_KST_FLEET5_worker_readiness_독립검토_Claude]]다.

## 앞선 보고서의 provenance 보정 (추가 기록)

앞선 보고서 `53f5722f`의 서두와 JSON `firstWaveSummaryAvailable: false`는 **처음 검토 단계(15:06~15:15 KST)**의 상태를 적은 값이다. 그 뒤 Codex packet `b1bacdd3`는 실제로 받았고, 같은 History의 exact-vector 절에서 실제로 검토했다. 따라서 그 값을 "현재 packet을 검토하지 못했다"는 뜻으로 읽으면 안 된다. 원래 날짜가 붙은 evidence와 원래 판정은 덮어쓰지 않았다. root가 받아들인 것은 관측값과 검토 발견이며, 실행 승인이 아니다.

## 무결성

- 공개 plan blob sha256은 `846a5b5c14049048a63cdfa062330d9ac7b27f6b4ad5410cf1c667617e19182c`로 일치했다.
- 비공개 `execution-vectors.private.json`은 24,740B, sha256 `a9c6d1e353f1e42fe80423f614625fe8f6ab97ac78722c0c3b71f85a91008c4f`로 일치했다.
- `parameters.private.json`은 `629584cc…`, source archive는 757,760B `a9f0a3b8…`로, 둘 다 `packet-digests.json`과 일치했다.
- vector가 참조하는 tool tree `supervision-final-integration-20261104`는 HEAD `59f0a3c2`이고 tracked 변경은 0이다.
- 이 commit의 hosted Docs CI는 run 41980284535 success다.
- vector 12단계는 모두 `executed: false`다.

## 3개 파일 Docker 문구 변경

변경은 정확하다.

- `deploy/lan/prepare-worker.sh`의 수치 guard `>= (1,45)`는 그대로이고, 오류 메시지만 `Docker Engine 26+ / Docker Desktop 4.29+`로 바뀌었다.
- 시험 assertion도 같은 문자열로 맞췄다.
- README는 Engine 26 / Desktop 4.29를 "역사적 기능 하한이며 지금 설치할 version이 아니다"라고 적는다. 이 내용은 공식 release note 실측과도 맞는다. 4.29.0(2024-04-08)이 Engine v26.0.0을 포함하고, 4.28.0은 v25.0.3이다.
- 문구에 대해 추가로 고칠 것은 없다.

## P1~P8 반영 여부 (가정하지 않고 실제로 확인)

| ID | 상태 at `846a5b5c`/`a9c6d1e3` | 근거 |
|---|---|---|
| P1 CA 수명·회전 | **OPEN, root 결정과 충돌** | plan `newCAPolicy`는 "fresh development pilot self-signed"다. step 05 init vector에는 external CA 옵션이 없다. root는 첫 init에서 새 f5 external intermediate를 쓰기로 정했다(이전 r5 CA는 절대 쓰지 않음). init 뒤에는 CA를 바꿀 수 없으므로 이 packet을 그대로 쓰면 그 결정을 되돌릴 수 없게 된다. **init 전에 다시 만들어야 한다.** |
| P2 ingress 규칙 | **OPEN** | vector에 DOCKER-USER/conntrack 규칙이 없다. History도 "authorized-operator network gate"로만 적는다. root가 지시한 w1/w2 `sudo -n` 읽기 전용 능력 분류 vector도 없다. |
| P3 build 자원 상한 | 부분 반영 | step 07에 `DOCKER_BUILDKIT=0`과 "legacy builder가 없으면 abort"가 들어갔다. Go module은 go.sum으로 고정되지만 여전히 network에서 가져온다. 이 부분은 실행 gate로 남는다. |
| P4 PG16 major | **OPEN** | image는 digest `1a6ab3f5…`로 고정했다. 그러나 major 16임을 보이는 증거(PG_MAJOR/`server_version`)는 plan과 vector 어디에도 없다. |
| P5 r5 실행 환경 공유 | **OPEN** | Windows 단계 6개가 `supervision-codex-20261104/.work/r5-reviewed-source-03e17c31/.venv` python을 쓴다. SSH도 r5의 `known_hosts.pinned`를 읽는다. 읽기만 하므로 bytes는 바뀌지 않는다. 그래도 r5 guard가 고정한 실행 파일과 결합되고, `-B`/`PYTHONDONTWRITEBYTECODE`가 없다. 별도 venv나 hash로 고정한 복사본을 쓰라고 권고한다. |
| R2 workspaces 폴더 | Low, OPEN | step 02가 workspaces 폴더를 만든다. mount하지 않는다는 점은 명시돼 있다. 아직 이 폴더를 쓰는 곳이 없다. |
| R5 quota 표현 | 해결 | History가 "hard filesystem quota is not configured"라고 정확히 적는다. |
| P6~P8 | 별도 확인 대상 아님 | 이번 relay 범위에서는 위 항목을 우선했다. |

gate를 돌리는 동안 Codex message `msg_e0847905db9f`가 도착했다. 내용은 P1~P8 수정 초안이며, 공개 plan은 `efb418758504f84e46269bb311ca0e730d77d4da8d81d4f5769238c781fe3faf`, 비공개 vector는 `f01fc3b1c722722ba6aa92cbb54a0ceae6ccd603a2e12b07660cb24ffbce5813`이다. receipt `c23e33c8`의 수정 commit은 이 시점에 아직 게시되지 않았다. 이 초안은 **받기만 했고 검토하지 않았다**. 아래 판정은 `22fa3628`/`846a5b5c`/`a9c6d1e3`에만 해당한다. Codex가 적은 P2 실제 상태(w1/w2 `sudo -n` 읽기 전용 query가 auth-required로 1 반환, BLOCKED)도 내가 직접 확인하지 않았다.

정리하면 22fa3628은 **문구 변경으로는 통과**다. **실행 packet으로는 P1·P2·P4·P5 때문에 아직 통과가 아니다**. root가 지시한 수정(external intermediate, sudo 분류)을 반영한 다음 hash를 다시 검토해야 한다.

## CP Docker Desktop target (공식 1차 출처, 15:30~15:32 KST)

**권고 target: Docker Desktop 4.98.0 (2026-11-03, Windows amd64 build 245422).** 실행할 때 그 시점의 최신 release를 다시 확인해야 한다. release는 매주 나오고, Pro/Team 지원 범위는 최신 version뿐이다.

- 설치 파일: `https://desktop.docker.com/win/main/amd64/245422/Docker%20Desktop%20Installer.exe`. HEAD 결과는 200, Content-Length 623,748,528, Last-Modified 2026-11-02 17:15:08 GMT다.
- checksum: `https://desktop.docker.com/win/main/amd64/245422/checksums.txt`의 SHA256 `cd6273d9eaa4f07fa7593fc6813d37e1004381cebc3f26047a2554fa5db24388`.
- Authenticode 서명은 파일 본문을 받지 않았으므로 **확인하지 못했다**. 설치 전에 hash와 서명자(Docker Inc)를 확인하는 gate가 필요하다.
- Engine/API: release note에 Desktop이 올린 Engine version으로 마지막에 적힌 값은 v29.9.2(4.96.1)이다. 4.97/4.98 note에는 Engine 줄이 없다. Engine 29.3.0이 최소 API를 v1.44에서 v1.40으로 낮췄다(moby/moby#52067). 공식 API 문서의 예시는 Engine 29.9.3 `API version 1.56 (minimum version 1.40)`이다. 그러면 node-agent는 `min(56,45)=45`를 고르고, 이 값은 server min 1.40 이상이므로 **호환된다**. 29.0~29.2의 min 1.44도 1.45 이하다. 설치한 뒤 `docker version`의 server API와 MinAPIVersion을 실제로 측정하는 것이 권위 gate다.
- Windows: 필요 조건은 Windows 11 Pro/Enterprise/Education 23H2(build 22631) 이상이다. CP는 26300이므로 충족한다. 추가 조건으로 **LanmanServer service가 Automatic**이어야 하며, 이 값은 아직 측정하지 않았다.
- WSL: 설치 최소는 2.1.5다. CP의 2.4.12는 충족한다. 그러나 4.98.0의 CVE-2026-112917(AF_VSOCK 우회) 수정은 **WSL 3.0.3 이상이 필요**하다. 그러려면 관리자 권한으로 `wsl --update`를 해야 하고, 재시작 요구가 나올 수 있다.
- data distro 이전과 재부팅 고려사항:
  - CP는 4.16.3의 두 distro 구조(`docker-desktop` + `docker-desktop-data`)다. 4.30에서 data distro를 쓰지 않는 provisioning이 실험 기능으로 도입됐다.
  - 4.31.0의 known issue로, 4.8.0 이하에서 만든 container·image·volume은 업그레이드 뒤 보이지 않게 된다(docker/for-win#14118).
  - 4.16.3에서 약 80개 minor version을 건너뛰는 업그레이드다. 공식 backup 문서는 업그레이드 실패에 대비해 `docker_data.vhdx`를 backup하라고 안내한다. 그러나 이번 범위에서 backup은 금지됐다.
  - 업그레이드하면 engine이 재시작되어 다른 제품의 container 7개(임상 Saintview 포함)가 멈춘다. 그래서 **그 제품 owner와 정한 작업 창, 그리고 별도로 승인된 backup이 선행 조건**이다.
  - per-machine에서 per-user로 설치 방식을 바꾸지 않는다. docker-users 그룹, sign-out, WSL 재시작 가능성을 계획에 넣는다.
  - host 여유 RAM은 0.55~1.13GB였고 `.wslconfig` 메모리는 6GB다. 이 값은 업그레이드 뒤 기동 여유를 따로 측정해야 한다.
- **4.16.3 rollback 가용성 (정직한 판정):**
  - 공식 FAQ는 최신 release보다 6개월 넘게 오래된 version은 download할 수 없다고 한다.
  - 4.16.3 release-note 항목에는 Download 링크가 없다.
  - 그런데 15:31:34 KST에 build 96739(CP 설치본과 같은 4.16.3.96739) 설치 파일 URL에 HEAD를 보내니 **HTTP 200**이 왔다(Content-Length 623,223,120, Last-Modified 2023-01-30). `checksums.txt`의 SHA256은 `5f6db3cf5a2084fc7c584c90792f38a0caac91c4eed4f8653dde7bb8148517f1`이었다.
  - 따라서 "지금은 접근되지만 정책상 보장되지 않는다"로 판정한다. 서명은 확인하지 못했다.
  - 더 중요한 점이 있다. 하향 설치는 newer 버전을 uninstall해야 하고, Engine 29가 다룬 data를 Engine 20.10으로 되돌리는 것은 지원되지 않는다. 그래서 실제로 쓸 수 있는 rollback은 **업그레이드 전에 승인받아 만든 vhdx backup과 4.16.3 재설치**뿐이다. 그런 backup은 없으므로 **full rollback은 현재 가용하지 않다**.

## 다음 첫 행동과 담당

1. **Codex(owner):** packet을 다시 만든다. 첫 init에 f5 external intermediate를 쓰고(P1), w1/w2 `sudo -n` 읽기 전용 분류 vector를 넣는다(P2). PG major 증거(P4)와 r5와 분리된 venv/known_hosts 사용(P5)도 넣는다. 그다음 새 hash를 root나 활성 dispatch로 보낸다.
2. **Claude:** 새 hash를 받으면 exact-vector를 다시 검토한다.
3. **root coordinator:** CP 업그레이드는 다음이 정해진 뒤에만 다른 승인 단계로 둔다.
   - 다른 제품 owner와 정한 작업 창
   - 승인된 vhdx backup
   - WSL 3.0.3 이상 업데이트
   - LanmanServer 확인
   - 설치 파일 hash와 서명 gate
   - 설치 뒤 API 측정

   policy와 quota를 구분하지 못한 Low 문제는 root가 자기 문서에서 고친다.

출처:
- [Docker Desktop release notes](https://docs.docker.com/desktop/release-notes/)
- [Install Docker Desktop on Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
- [FAQs on Docker Desktop releases](https://docs.docker.com/desktop/troubleshoot-and-support/faqs/releases/)
- [Docker Engine 29 release notes](https://docs.docker.com/engine/release-notes/29/)
- [Docker Engine API](https://docs.docker.com/reference/api/engine/)
- [Back up and restore Docker Desktop data](https://docs.docker.com/desktop/settings-and-maintenance/backup-and-restore/)
