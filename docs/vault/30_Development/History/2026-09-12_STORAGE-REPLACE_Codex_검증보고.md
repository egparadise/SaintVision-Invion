---
doc_id: "HIST-STORAGE-REPLACE-20260912"
title: "2026-09-12_STORAGE-REPLACE_Codex_검증보고"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-12T16:12:16+09:00"
source_of_truth: "Git"
---

# 저장소 Node 교체 실행과 재개

Product `f766146f348d1190d25115a570f63e36956d0c25`, base d1366f7, agent/codex/workspace-bridge. CX-02/S12-ST Codex owner, Claude reviewer pending. GUIDE/GOV-AGENT/GOV-GIT1.1.0, agent-delivery1.1.0/core-reliability1.0.0, ADR-095. [[2026-09-12_STORAGE-REPLACE_Codex_착수]].

## 작업한 것

worker_replace.py는 현재 preflight receipt와 명시적 storage plan을 받아 정지된 정상 관측 Node를 교체한다. private 설치 디렉터리의 flock/0600 파일과 fsync→rename→directory fsync로 단계 기록을 보존한다. 기존 컨테이너의 자동 재시작을 끄고 고유 이름으로 보존한다. 기존 image/config와 이전 정책 exact bytes를 private 기록에 남기며 키/전체 journal 원문은 복제 기록하지 않는다. 같은 소유 상태 volume에 새 readonly/nonrecursive contribution mount 컨테이너를 만들고 정책만 설치한다. 기존 컨테이너나 volume을 삭제하는 명령은 없다.

prepared/fenced/renamed/created/installed/starting/ready 단계를 기록하며 Docker 작업 후 기록 전에 중단돼도 ID/소유 label/실제 설정을 대조해 재개한다. 생성 후 currentId를 고정한다. 시작 전 starting을 먼저 durable 저장한다. journal floor가 올라간 뒤 이전 컨테이너나 정책으로 자동 복귀하지 않는다. 재시도는 같은 plan과 원래 receipt를 사용한다. 계획 변경·기록 손상·알 수 없는 교체 컨테이너·기존 컨테이너 손실은 거부하고 보존한다.

키/인증서/identity 및 기존 journal 파일 내용·권한 해시를 교체 전후 대조한다. 변경 허용은 /state/storage-policy.json과 해당 contribution의 .storage 버전 기록뿐이다. 다른 contribution floor도 보존한다. 새 컨테이너 image/identity/명령/port/mount/권한 및 CPU·RAM·pids 제한을 확인한다. 완료 결과는 JSON이며 기존 컨테이너 보존/새 ID/로컬 정책 수락을 반환한다. 이전 시작 로그가 섞이지 않도록 현재 StartedAt 이후 기록만 대조한다.

**restartPolicy=no, operationalAcceptanceAssessed=false**로 반환한다. phase 이름 fenced는 로컬 자동 재시작 차단이며 분산 Lease/daemon fencing을 구현했다는 뜻이 아니다. 같은 private 디렉터리의 프로세스만 flock으로 조율한다. Docker 관리자·다른 설치 디렉터리·호스트 전원 장애까지 원자적으로 제어하지 않는다.

## 실제 확인

- clean 동일 SHA Windows 경계 **111 passed/exit0**: `python -m pytest -q tests/core/test_lan_replace.py tests/core/test_lan_replacement.py tests/core/test_lan_storage.py tests/core/test_lan_worker_config.py tests/core/test_lan_workspace_upgrade.py --junitxml=.work/storage-replace-windows.xml`. Docker 모사 시험과 Linux 실제 시험을 구분한다.
- 동일 SHA 실제 Linux Docker/Go 설치·교체 **11 passed/0 skipped/exit0**: `python tools/check_storage_bundle.py --prepared .work/sv-kernel-6a9f62c3c81c/prepared.json`. 기존 설치/사전 점검3개와 정상+7단계 중단/재개8개. [case·image/hash·코드 SHA](../Evidence/storage-replace-linux-f766146.json). source/hash가 같은 f9d69a8 Go 바이너리 재사용, runtimeCodeSHA 분리 기록.
- 실제 Go root_version1→2, 기존 컨테이너 정지/자동 재시작 off 유지, 새 컨테이너 ID 유지 재시도, 나중에 정상 정지한 새 Node의 forward 재시작, 키/journal 보호 해시, 이전 policy bytes 보존, private record0600, 동시에 같은 디렉터리 잠금 거부, 다른 receipt 거부를 확인했다. 중단은 Python fault seam으로 작업 후/기록 전 예외를 주입한 시험이다. OS 강제 종료·물리 전원 장애 시험으로 과장하지 않는다.
- git push exit0. [같은 SHA CI6개](../Evidence/storage-replace-f766146-ci.json)는 계정 결제/한도 때문에 job 시작 전 실패. CI 통과/독립 검토/원격 운영 인수는 아니다. PR19 draft, #21→#22→#19 검토 순서 유지.

## 오류와 한계

[[2026-09-12_STORAGE-REPLACE_오류와해결]]: 유지된 volume에 정책을 쓴 뒤 CreatedAt이 달라져 첫 교체 성공 후 재개가 거부됐다. 원본 preflight volume hash는 그대로 검증하고, 교체 중 CreatedAt만 신원 판정에서 제외한다. 나머지 metadata·보존 컨테이너의 정확한 ID와 mount·volume 단독 소유 집합을 확인한다. Windows 포트 예약 범위 충돌은 시험용 포트를 호스트에서 선택하도록 수정했다.

이 설치는 Linux Docker용 CLI다. Windows launcher/WSL 실제 호출·원격 .225 배포를 완료하지 않았다. 새 정책 자체가 잘못되어 Go에서 거부되면 같은 계획 재시도가 자동으로 고쳐주지는 않는다. 다른 forward 정책으로 전환하는 운영 절차는 별도 조율이 필요하며 기존 record 삭제/옛 policy 복귀로 우회하지 않는다. backup은 shared state volume의 이전 컨테이너이지 독립 데이터 백업이 아니다.

## 다음 담당과 첫 행동

Codex: Windows/WSL 교체 진입점과 명시적 source/policy/receipt 전달·출력 검증을 연결한다. 이후 실제 .225 허용 폴더/정책을 적용하고 서버 mTLS→서명 sample→Evidence/StorageCheck→인증 GET을 확인한다. 원격 workload7개/5대/GPU/장시간·전원 장애 인수는 별도다. Claude: ADR-095/기록 원자성·old/new ID·변경 허용 파일·재개 경계를 독립 검토. Gemini: 로컬 교체 완료와 서버 운영 인수/스케줄링 가능 상태를 분리한다.

전체 **2775/4800=57.81% 완료 /42.19% 잔여 유지**. 내부 교체 시험만으로 운영 인수 행을 올리지 않는다. 전달/Obsidian 동기화 결과는 아래 추가한다.


전달 검사: check_docs exit0(문서337/작업48), check_ontology exit0, git diff --check의 문서 EOF 빈 줄2개 수정 후 exit0. PR19 갱신/draft 유지. 보고7e5d029 push exit0. Obsidian 첫 check는 외부3개 변경으로 exit1/쓰기0. 원문/hash를 보존하고 별도 브랜치의 인증 보고를 작성자 주장으로 인계했다. Codex factory 진입점은 직접 확인해 정본 유지 결정을 남겼다.

최종 전달: 352a075 push exit0. 2026-09-12T16:13:47+09:00 로컬 Obsidian640개 전체 hash 일치/pending0/conflict0, check→apply→check exit0. [동기화 영수증](../Evidence/storage-replace-obsidian-20260912.json). 영수증 포함 후속 commit도 push/동기화한다. OneDrive cloud 업로드 미검증. 다음 Codex Windows/WSL 교체 진입점·서버 검증 연결, Claude 독립 검토 pending.
