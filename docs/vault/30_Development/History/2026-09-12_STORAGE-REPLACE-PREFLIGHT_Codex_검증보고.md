---
doc_id: "HIST-STORAGE-REPLACE-PREFLIGHT-20260912"
title: "2026-09-12_STORAGE-REPLACE-PREFLIGHT_Codex_검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T15:52:13+09:00"
source_of_truth: "Git"
---

# 교체 사전 점검 검증

Product `823b4b83f9b0fe5a7a89416b96db21a7219113af`, base c9dcb09, agent/codex/workspace-bridge. CX-02/S12-ST Codex owner, Claude reviewer pending, agent-delivery1.1.0/core-reliability1.0.0. [[2026-09-12_STORAGE-REPLACE-PREFLIGHT_Codex_착수]], ADR-094.

## 작업한 것

worker_replacement.py의 preflight/recheck는 읽기 전용이다. 정지·정상 종료된 lan-observe-v1 컨테이너와 현재 Node identity/epoch, root-user, 읽기 전용 rootfs, 소유 Node 라벨의 단독 사용 상태 볼륨을 확인한다. 실행 중·비정상 종료·OOM·workspace 프로필·알 수 없는 mount·쓰기 contribution mount·공유 volume을 거부한다. 새 storage plan의 source/policy hash도 다시 확인한다.

/state tar는 최대16MiB/30초로 메모리에서 읽고 링크·경로 이탈·중복·특수 파일을 거부한다. 필수 키·인증 파일 및 journal identity의 0:0/0600·정체성을 확인한다. 전체 파일 내용과 소유권/권한을 해시로 묶어 반환하며 키/정책/경로 원문은 출력하지 않는다. 컨테이너/volume/계획의 해시 및 ID에 결합한다. mtime/atime은 상태 내용 해시에서 제외한다. 두 번 상태를 읽고 전후 inspect를 비교한다. recheck는 현재 기록과 exact receipt가 같아야 통과한다.

Docker mount 목록 순서는 비결정적이므로 Destination 순으로 정규화하되 모든 속성은 보존·비교한다. Docker tar의 type 비트를 권한으로 오인하지 않도록 07777 마스크로 권한만 비교한다. [[2026-09-12_STORAGE-REPLACE-PREFLIGHT_오류와해결]]에 최초 실패와 수정을 기록했다.

**컨테이너 삭제/재생성 executor와 실패 후 forward 재개는 아직 구현하지 않았다.** 이 단계는 그 선행 점검이다. receipt는 서명된 승인/분산 lock/daemon fencing/원자적 교체가 아니며 replacementAuthorized=false, operationalAcceptanceAssessed=false다. 마지막 점검 이후의 관리자 변경·ABA·전체 journal rollback까지 막는다고 주장하지 않는다. 운영 Node를 정지/교체하지 않았다.

## 확인한 증거

- 동일 clean SHA `python -m pytest -q tests/core/test_lan_replacement.py tests/core/test_lan_storage.py tests/core/test_lan_worker_config.py tests/core/test_lan_workspace_upgrade.py --junitxml=.work/storage-replace-preflight-windows.xml`: **90 passed/exit0**. 모사 Docker 경계 시험이며 실장비 인수와 구분한다.
- 동일 SHA `python tools/check_storage_bundle.py --prepared .work/sv-kernel-6a9f62c3c81c/prepared.json`: **실제 Linux Docker3 passed/0 skipped/exit0**. 이전 설치2개+신규 교체 점검1개. 신규 시험은 실행 중 거부/비정지, 명시적으로 정지한 합성 Node의 반복 점검과 내용/권한 보존, 재시작 후 stale 거부 및 새 점검 성공을 확인했다. [case/image/hash/두 코드 SHA](../Evidence/storage-replace-preflight-linux-823b4b8.json). Go source/hash가 같은 f9d69a8 바이너리를 재사용했으며 Windows WSL/.225 운영 시험은 아니다.
- git push exit0. [동일 SHA CI6개](../Evidence/storage-replace-preflight-823b4b8-ci.json)는 결제/한도 때문에 job 시작 전 실패. 반복 rerun/merge 없음. PR19 draft, Claude 독립 검토 pending.

## 다음 담당과 첫 행동

Codex: 이 점검의 해시를 전제로 로컬 lock·durable 교체 단계 기록·기존 image/config 보존·볼륨 재사용·중단 지점별 재개를 구현한다. 기존 Node를 제거한 뒤에도 재개할 수 있어야 하며 새 journal floor 기록 후 이전 정책으로 자동 downgrade하지 않는다. 그 뒤 운영 .225 허용 폴더/정책 적용과 서버 mTLS/Evidence/조회 인수, 원격7개 시험을 수행한다. Claude: ADR-094와 archive/동시 변경/권한 검사를 독립 검토. Gemini: preflight 결과를 운영 준비·물리 시험 완료로 표시하지 않는다.

전체 **2775/4800=57.81% 완료,42.19% 잔여 유지**. 교체 전체 또는 운영 인수가 완료됐다고 올리지 않는다. 전달 검사/Obsidian 동기화 결과는 아래 추가한다.

