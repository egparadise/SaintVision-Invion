---
doc_id: "GOV-FLEET5-B-BOOTSTRAP-SCOPE-20261106"
title: "FLEET5 B 병행 역할과 전환 구현 범위 결정"
version: "1.0.0"
status: "review"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-06T03:03:02+09:00"
source_of_truth: "Git"
---

# 실제 검토 이후의 범위 결정

통합72028은 실제255cfa37 source/packet ACCEPT와8개CI/12job 성공을 받았다. 배포 전 C-L1 검토시각 정정 문서를 포함한 최종 납품·작은 독립 검토가 필요하며 별도 시험 보완을72028CI로 차용하지 않는다. 제품 전체·운영 인수는 아니다.

전환5d0753은 실제a81f7330에서 이전 Low/Info를 닫았고 V3-L1~L3의 cohort target·nonproof join·복원 head/epoch 정합성 조건을 남겼다. 기존 Codex를 이후 계약·고난도 구현 owner로 지정하되 현재 작업은 v4 문서/schema/fixture 보완이다. 실제 보완 검토 전 canonical 등록·helper/API/runtime 구현은 허용하지 않는다.

BroadB100f는 실제2bb959a3에서 B1 High/B2~B5 Medium 수정 필요다. Root는 B-FRESH1과 B-MIG1 DESIGN-FIRST를 선택했다. 새5Node 동일 병행 역할을 유지하며 Windows 물리CP의 새 역할은 Linux-native 파일시스템·지원 Docker Engine/default socket을 가진 별도 CP-colocated Linux context를 설계 대상으로 한다. 관리 Linux VM/WSL2 guest의 identity·실행 adapter·소스 containment·독립 kernel 측정·API·접속 capability를 계약으로 닫는다. 실제 guest가 준비됐거나 설치됐다는 뜻이 아니다. Windows drive mapping 또는 mixed cohort로 자동 대체하지 않는다. CP 겸임5번의 S05/S07 독립 장애 영역 제외는 그대로다.

D2는 operator-only role-admission 증거 ABI와 현재(C,R,policy,exe/root/instance) join 무효화·전체caller 분류, D3는 pin전 side-effect-free 검증과 부분 pin exact-config forward replay, D4는 intent부터 전cohort final 증거까지 격리, D5는 fence→sorted nodes→sorted contributions→sorted channels→admission/nonce/evidence의 일관된 B lock순서, D6는 Codex owner/별도 Claude 실제 검토다. policyB 승인·revoke 변화·추가 floor·workload mount검사와 A1~A16 증거를 revised contract로 닫는다.

현재 승인 범위는 revised DOCS다. 코드·ABI/ADR 등록·장비 작업은 실제 수정 검토 뒤 gate에 따라 진행한다. guest/context의 물리 준비는 검토 가능한 구체 계획과 실제 권한·환경 증거가 필요하다. 기존 WindowsDocker/파일럿/업무 컨테이너를 변경하거나 키를 이동하지 않았다. 이미 받은 프로젝트 승인을 반복 요청하지 않는다.

정확한 Root 지시·원본 review refs·reply ID는 implementation-scope-decision-root.json Evidence에 보존했다. 모든 실제 binding NULL/HOLD, B/전환 실제 Go·crypto·Engine·장비 검증0, future40case NOTRUN이며 원래48-task/VFCL 집계는 바꾸지 않는다.
