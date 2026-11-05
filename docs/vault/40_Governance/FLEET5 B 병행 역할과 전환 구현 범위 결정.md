---
doc_id: "GOV-FLEET5-B-BOOTSTRAP-SCOPE-20261106"
title: "FLEET5 B 병행 역할과 전환 구현 범위 결정"
version: "1.1.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-06T05:22:48+09:00"
source_of_truth: "Git"
---

# 실제 검토 이후의 범위 결정

통합72028은 실제255cfa37 source/packet ACCEPT와8개CI/12job 성공을 받았다. 배포 전 C-L1 검토시각 정정 문서를 포함한 최종 납품·작은 독립 검토가 필요하며 별도 시험 보완을72028CI로 차용하지 않는다. 제품 전체·운영 인수는 아니다.

전환5d0753은 실제a81f7330에서 이전 Low/Info를 닫았고 V3-L1~L3의 cohort target·nonproof join·복원 head/epoch 정합성 조건을 남겼다. 기존 Codex를 이후 계약·고난도 구현 owner로 지정하되 현재 작업은 v4 문서/schema/fixture 보완이다. 실제 보완 검토 전 canonical 등록·helper/API/runtime 구현은 허용하지 않는다.

BroadB100f는 실제2bb959a3에서 B1 High/B2~B5 Medium 수정 필요다. Root는 B-FRESH1과 B-MIG1 DESIGN-FIRST를 선택했다. 새5Node 동일 병행 역할을 유지하며 Windows 물리CP의 새 역할은 Linux-native 파일시스템·지원 Docker Engine/default socket을 가진 별도 CP-colocated Linux context를 설계 대상으로 한다. 관리 Linux VM/WSL2 guest의 identity·실행 adapter·소스 containment·독립 kernel 측정·API·접속 capability를 계약으로 닫는다. 실제 guest가 준비됐거나 설치됐다는 뜻이 아니다. Windows drive mapping 또는 mixed cohort로 자동 대체하지 않는다. CP 겸임5번의 S05/S07 독립 장애 영역 제외는 그대로다.

D2는 operator-only role-admission 증거 ABI와 현재(C,R,policy,exe/root/instance) join 무효화·전체caller 분류, D3는 pin전 side-effect-free 검증과 부분 pin exact-config forward replay, D4는 intent부터 전cohort final 증거까지 격리, 당시 D5는 fence→sorted nodes→sorted contributions→sorted channels→admission/nonce/evidence의 B lock순서 제안, D6는 Codex owner/별도 Claude 실제 검토다. policyB 승인·revoke 변화·추가 floor·workload mount검사와 A1~A16 증거를 revised contract로 닫는다.

이 문서 1.0.0의 당시 B 승인 범위는 revised DOCS였다. 코드·ABI/ADR 등록·장비 작업은 실제 수정 검토 뒤 gate에 따라 진행한다. guest/context의 물리 준비는 검토 가능한 구체 계획과 실제 권한·환경 증거가 필요하다. 기존 WindowsDocker/파일럿/업무 컨테이너를 변경하거나 키를 이동하지 않았다. 이미 받은 프로젝트 승인을 반복 요청하지 않는다.

정확한 Root 지시·원본 review refs·reply ID는 implementation-scope-decision-root.json Evidence에 보존했다. 모든 실제 binding NULL/HOLD, B/전환 실제 Go·crypto·Engine·장비 검증0, future40case NOTRUN이며 원래48-task/VFCL 집계는 바꾸지 않는다.


## 실제 rev2 검토 후 rev3 결정

실제 ac9182c3e3d606ec027c0be2e90e049ff50d54f1의 R1~R7 Medium과 Low를 읽었다. Docs42095556156과 Portal42095515359의 exact head·ref·전체 job 성공을 Root가 대조했다. 02cfd260은 수정 필요이고 부분 동결도 하지 않는다. Root reply msg_f7caf4c96b16의 구체 rev3는 DOCS/schema/static fixture 범위이며 B 코드·운영 등록 권한이 아니다.

D1을 관리되는 별도 커널 Linux VM과 자체 Engine으로 좁힌다. WSL2는 Desktop과 커널을 공유하므로 별도 검토되지 않은 대안이며 자동 fallback을 허용하지 않는다. 게스트 CPU·메모리·디스크와 호스트 여유 자원은 원시 측정값·관측 시각·장비 identity·계획 예산으로 확인한다. 계획 기본값 2 vCPU/4 GiB/20 GiB와 호스트 여유 2 GiB/10 GiB는 실제 확보 증거가 아니다. 현재 자원 부족은 RESOURCE_UNAVAILABLE이고 실제 budget·binding은 NULL/HOLD다.

D5는 mandatory Database.transaction의 epoch guard를 존중하여 control_epoch를 첫 잠금으로 정정한다. 이후 routing/fence, 정렬된 inv.nodes, 정렬된 public node/contribution, channels, role/current, 명시된 business/run/grant/nonce/evidence/ledger 순서다. 실제 모든 callsite·FK·RLS·외부 transaction의 잠금 모드를 조사하고 discovery 뒤 재검증한다. DB row lock을 잡은 채 Node I/O를 하지 않으며 bounded timeout/abort와 실제 PG 검증을 별도로 요구한다.

rev3는 protected operator-release authority와 제한된 online use key 분리, Node-visible release/delegation chain, 별도 authenticated observe/reconcile/safety lane, released steady-state per-Node READMIT_SAME_CONFIG, named DB principals/grants, 부분 변경 중 revoke/epoch/expiry의 QUARANTINE, generation-bound memory replay와 닫힌 HostConfig allowlist를 명시해야 한다. 자세한 원문과 실제 reply는 b-rev2-root-revision3-decision.json이다. 기존 승인 재요청은 하지 않는다.

전환 v5의 실제 6b12d3ab 독립 검토와 별도 Root 설계 등록은 [[FLEET5 전환 v5 계약 동결과 구현 범위]]에 기록한다. B 미수락 범위와 전환 K1 구현 범위를 구분하며 실제 장비·전체 제품 인수는 여전히 미완료다.
