---
doc_id: "HIST-STORAGE-POLICY-20260912"
title: "2026-09-12 STORAGE-POLICY Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T15:25:11+09:00"
source_of_truth: "Git"
---

# 2026-09-12 STORAGE-POLICY Codex 검증보고

2026-09-12T15:25:11+09:00 / product `f9d69a8ed3fde2bc99096b5f551c3e6a5bc386b4` / base0c1a4cf / agent/codex/workspace-bridge / CX-02 owner Codex, Claude reviewer pending / PR19 draft. [[2026-09-12_STORAGE-POLICY_Codex_착수]], [[Codex 로컬 폴더 점검과 Node 증명 계약]] v1.5.0/ADR-092, [[Codex Node 저장소 설정 설치와 교체 절차]].

## 작업한 것

기존 Go --storage-policy는 살아 있는 프로세스 동안 hash 변경을 거부했지만 재시작하면 옛 버전의 설정을 다시 받아들일 수 있었다. 기존 identity/epoch journal의 process lock 아래 contribution별 `.storage-<contributionId>`에 rootVersion/channelVersion 및 root/channel/exact policy hash를 보존하도록 구현했다. root와 channel은 각각 역행할 수 없고 같은 버전의 경로·채널 변경도 거부한다. 두 버전 모두 같으면 정확한 policy bytes까지 같아야 한다. 한 버전만 올려 다른 버전을 낮추는 교체는 차단한다.

현재 TLS 인증서/키/SAN/EKU/시간/pin 및 안전한 root/config를 확인한 뒤 floor를 기록한다. pin callback이 없는 sampler는 생성하지 않는다. 처음 기록은 기존 exclusive create/file sync/directory sync, 갱신은 private temp/file sync/rename/directory sync이며 동일 설정 재시작도 directory sync를 확인한다. 실패한 교체는 floor를 낮추지 않는다. 손상된 journal을 새 것으로 초기화하지 않고 거부하며 Node identity/key/기존 작업 journal을 보존한다. startup 전용 함수로서 기존 process lock을 전제로 한다.

실제 listener가 만들어진 후 출력하는 시작 JSON에 tenantId/nodeId/recoveryEpoch, contributionId, 두 버전과 hash를 넣었다. raw root/키/인증서 bytes는 없다. `operationalAcceptanceAssessed=false`다. 이는 **서명되지 않은 로컬 설정 수락 기록**이며 원격 서버의 mTLS 확인이나 현재 건강/작업 완료가 아니다.

## 확인한 것

- clean f9d69a8 Linux 실제 Go daemon/mTLS/파일/PostgreSQL **85 passed/0 skipped/exit0**. 신규 재시작7개를 포함한 Node storage27, 기존 commit22/view18/delivery18. [SHA·개별 case·image/hash·cleanup](../Evidence/storage-policy-linux-f9d69a8.json).
- 실제 프로세스 종료/재시작에서 같은 설정의 시작 기록 유지/서명 sample 성공, root/channel 각각 rollback, 한 축 증가를 이용한 다른 축 rollback, 같은 버전의 경로/채널 변경, 같은 버전의 exact bytes 변경, 손상된 floor 거부/identity 보존을 확인했다. 거부 후 마지막 수락 설정 재시작도 성공했다. 시험용 forward channel2는 운영 DB의 채널을 갱신한 것이 아니므로 운영 인수로 해석하지 않는다.
- Windows `go test ./transport ./storage ./runtime` exit0. transport/runtime의 Windows 가능 시험이며 storage Linux root 시험은 Windows에서 no test files다. 제품 commit 전 작업본 확인으로 구분하며 Linux85와 합산하지 않는다.
- git push origin agent/codex/workspace-bridge exit0. [같은 SHA CI6개](../Evidence/storage-policy-f9d69a8-ci.json)는 결제/한도 제한으로 job 시작 전 failure. 반복 rerun/병합/운영 DB 변경 없음.

## 한계와 다음 행동

설치 절차에 현재 DB root/channel 버전·허용된 실제 폴더·컨테이너 읽기 mount 대응을 고정하고, floor 기록 뒤 listen 실패 시 옛 버전으로 돌아가지 않는 forward 복구 원칙을 기록했다. 전체 journal 삭제/backup 롤백/호스트 관리자 변조를 탐지하는 hardware counter는 아니다. 전원 차단이나 물리 디스크 장애는 시험하지 않았다. 다른 contribution 선택은 원래 contribution의 floor를 지우지 않는다.

**기존 LAN Start-Worker/start-node bundle의 자동 mount/설정 전달·교체는 아직 연결하지 않았다.** 실제 .225 설치 완료도 아니다. 다음 Codex 첫 행동은 bundle에 명시적 읽기 mount·policy 전달과 시작 receipt 대조를 연결하되 기존 journal/키/volume을 보존하는 것이다. 원격 운영자는 실제 허용 폴더 경로를 제공하고 설치 수신 결과를 반환해야 한다. Claude는 f9d69a8/ADR-092/영속 쓰기와 읽기 경계를 독립 검토, Gemini는 로컬 설정 수락과 서버 운영 인수를 분리한다. 운영 원격7개/5대/GPU는 별도다.

전체 개발 성숙도 **2775/4800=57.81% 완료 /42.19% 잔여 유지**. 기존48행의 운영 인수 조건은 아직 충족하지 못했다. PR19 draft/선행 #21→#22→#19 검토 순서 유지.



전달 전 검사: check_docs.py exit0(원문24/문서328/작업48), check_ontology.py exit0, git diff --check exit0. PR19 설명 갱신/draft 유지. 보고 commit/push 후 Obsidian check→apply→check 및 모든 파일 hash 대조를 진행한다.


동기화 최초 check exit1/쓰기0: 외부3개 변경을 발견해 [원문/hash](../Evidence/obsidian-proposals-20260912-storage-policy/manifest.json)를 보존하고 수신 요약만 추가했다. Gemini Vitest109 등은 작성자 보고/독립 검토 pending. 동일 bytes Git 보존을 확인한 뒤 쓰기0 인수하여 정본과 동기화한다.
