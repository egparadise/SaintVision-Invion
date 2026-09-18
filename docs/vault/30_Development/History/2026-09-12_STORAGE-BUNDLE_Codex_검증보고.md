---
doc_id: "HIST-STORAGE-BUNDLE-20260912"
title: "2026-09-12 STORAGE-BUNDLE Codex 검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T15:40:43+09:00"
source_of_truth: "Git"
---

# STORAGE-BUNDLE 설치 검증

2026-09-12T15:40:43+09:00, product `9848afb4f17c6f2b589f4a9c894f3532185f7213`, base bc87f7c, agent/codex/workspace-bridge, CX-02 owner Codex / Claude reviewer pending. [[2026-09-12_STORAGE-BUNDLE_Codex_착수]], ADR-093.

## 작업한 것

새 Node 컨테이너를 만드는 LAN bundle에 선택적인 StorageSource/StoragePolicySHA256 입력을 연결했다. exact policy bytes/hash, tenant/node/epoch, endpoint, root/channel 버전과 이미지 ID를 검증한다. 허용 폴더는 /contribution으로 readonly/rprivate/nonrecursive bind하며 실제 Docker inspect와 비교한다. 보호 파일은 /state/storage-policy.json에 root:root 0600으로 복사하고 다시 읽어 bytes와 권한을 확인한다. Node가 시작한 뒤 Go의 storagePolicy receipt와 설치 계획을 대조한다. 시작 전후 컨테이너 ID/StartedAt/재시작 횟수도 확인한다.

기본 설치는 관측 전용으로 유지한다. 기존 컨테이너가 있으면 변경하지 않고 거부한다. 기존 키·journal을 지워 재설치하지 않는다. 이 기능은 기존 Node의 통제된 교체 자동화가 아니다. 설치 중 실패한 생성물은 진단을 위해 보존하며 자동 삭제하지 않는다. 호스트 관리자나 검사와 daemon mount 사이 경로 교체를 원자적으로 막는 보장은 아니며 Go의 실제 파일 읽기 경계는 별도로 유지한다.

## 확인한 것

- clean 동일 SHA 실제 Linux Docker + 합성 PKI 설치 **2 passed/0 skipped/exit0**. 읽기 mount·정책 복사·Go receipt·기존 컨테이너 재설치 거부·journal bytes 보존, 잘못된 hash에서 Node/volume 미생성을 확인했다. [원본 증거](../Evidence/storage-bundle-linux-9848afb.json). Go 소스/hash가 동일한 이전 f9d69a8 바이너리를 재사용했으며 runtimeCodeSHA와 설치 코드 SHA를 분리 기록했다.
- `python -m pytest -q tests/core/test_lan_storage.py tests/core/test_lan_worker_config.py tests/core/test_lan_workspace_upgrade.py --junitxml=.work/storage-bundle-windows.xml` **62 passed/exit0**. Docker 응답을 모사하는 경계 시험으로 실제 Docker 2개와 구분한다.
- PowerShell Parser.ParseFile Start-Worker.ps1 오류0/exit0. 이 PC의 Ubuntu WSL 배포판은 없어 WSL_E_DISTRO_NOT_FOUND였다. Windows→WSL 설치 경로 실행·원격 .225 설치는 미수행이다.
- 초기 Docker 시험은 시험 폴더가 daemon 내부 /var/lib/docker 아래여서 rprivate mount가 거부되었다. 일반 Windows 호스트 시험 폴더로 옮긴 후 통과했다. 제품의 격리 조건은 완화하지 않았다. [[2026-09-12_STORAGE-BUNDLE_시험경로와_CI_오류]] 참조.
- git push exit0. [동일 SHA CI6개](../Evidence/storage-bundle-9848afb-ci.json)는 모두 계정 결제/한도 때문에 job 시작 전 실패. 로컬 시험을 CI 통과로 취급하지 않는다. ruff는 환경에 설치되지 않아 미실행, Black 및 git diff --check로 형식 확인했다.

## 이어서 할 것

Codex: 기존 Node의 image/identity/epoch/journal/config 보존과 새 mount 교체를 위한 사전 점검·통제된 교체·실패 후 forward 재개 구현. 실제 원격 PC의 허용 폴더 및 정책을 확정한 뒤 배포, 서버 mTLS→서명 sample→Evidence/StorageCheck→인증 조회까지 확인한다. 원격 workload7개/5대/GPU/장시간 복구 인수는 별도다.
Claude: ADR-093/설치 입력·파일 경계·기존 volume 보존과 receipt 판정을 독립 검토. Gemini: 로컬 설치 기록과 서버 현재 관측/운영 인수 상태를 분리 표시. 독립 검토를 수행했다고 기록하지 않았다.

전체 개발 성숙도 **2775/4800=57.81% 완료 /42.19% 잔여 유지**. 신규 설치 경로 통과만으로 48행의 운영 합격 조건을 올리지 않는다. PR19 draft / 선행 검토 #21→#22→#19 유지. 전달 후 Obsidian check→apply→check 결과를 추가한다.

전달 검사: check_docs exit0(문서331/작업48), check_ontology exit0, git diff --check exit0. PR19 설명 갱신 및 5cb3349 보고 push exit0. 첫 Obsidian check는 외부 인계 페이지1개 변경으로 exit1/쓰기0. Gemini 신규 정본 수렴 회신의 원문/hash를 보존하고 작성자 주장으로 수신 요약했다. 동일 원문 Git 보존 후 쓰기0 인수·정본 동기화를 진행한다.

최종 전달: 19acdab push exit0. 2026-09-12T15:42:15+09:00 Obsidian622개 전체 hash 일치/pending0/conflict0/check→apply→check exit0. [동기화 영수증](../Evidence/storage-bundle-obsidian-20260912.json). 영수증 포함 후속 commit도 push/재동기화한다. OneDrive cloud 업로드는 미검증. 다음 Codex 통제된 기존 Node 교체와 forward 재개, Claude 독립 검토 pending.
