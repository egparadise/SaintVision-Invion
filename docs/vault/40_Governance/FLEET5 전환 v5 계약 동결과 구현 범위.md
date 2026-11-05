---
doc_id: "GOV-FLEET5-BOOTSTRAP-V5-FREEZE-CODE-SCOPE-20261106"
title: "FLEET5 전환 v5 계약 동결과 구현 범위"
version: "1.0.0"
status: "active"
author: "Codex"
reviewer: "Claude"
updated: "2026-11-06T05:22:48+09:00"
source_of_truth: "Git"
---

Root는 source8874b2dfe0dda9a019bd5f334636668290702e13과 실제 reviewer6b12d3ab0e1f3e3cf623b62c528e0e096ba48af6의 검토 원문을 읽고 Docs42101121186/Portal42101121325의 exact SHA·ref·전체 job 성공을 대조했다. V4-M1/I1/I2/I3는 닫혔고 제안 수준 수락이다. 실제 Go·crypto·Engine·장비 실행은 이 설계 수락에 포함되지 않는다.

17개 schema와 11개 규범·synthetic fixture의 원본 SHA256/크기/source를 bootstrap-v5-design-contract-registration-root.json에 고정해 구현 기준으로 등록한다. $id가 없는 7개 schema는 원본 바이트를 바꾸지 않고 명시한 offline URI로 해석하며 전체 참조를 오프라인에서 닫는다. 거부된 v4 signed aggregate는 제외한다. 이는 설계 등록이며 live CP/worker trust 설치가 아니다. 실제 anchor/key/검토된 verifier artifact/binding은 NULL/HOLD다.

Codex task_38393b5d1865가 FLEET5-BOOTSTRAP-V5-K1-OFFLINE-VERIFIER-20261106의 구현 owner다. reply msg_a21df0511488로 승인된 첫 범위는 e50c148287779add421265868ef16909ed984650을 base로 삼은 새 branch의 독립 Go offline verifier package와 테스트·필요한 read-only 검증 CLI다. 오래된 v5 제품 branch를 구현 base로 사용하지 않으며 frozen e50 ref를 움직이지 않는다. 기존 Node launch·peer floor·transport·rotation·B·DB 구현은 변경 범위가 아니다.

K1은 strict UTF-8/closed schema/C2, 외부 고정 trust/role/scope, 실제 Ed25519 typed proof와 freshness/current binding, dependency 순서의 DAG, graph와 별도 role@scope policy, 두 원본 Node projection과 현재 lease/head/readback의 독립 인증 뒤 unsigned derived digest 재계산을 구현한다. bundle/plan은 trust를 설치하거나 verifier를 고르지 못한다. 115개 dummy signed-shape는 실제 서명 positive가 아니며 새 test key로 재생성한 실제 crypto fixture를 별도 표기한다.

K1은 효과 없는 검증 단계다. host root/journal/lock/Engine adapter·CP DB·SSH·Node/leaf 발급·guest 설치·live trust 등록·물리 운영은 별도 K2와 실제 코드 검토 이후 범위다. 구현자는 실제 Go 테스트·race 가능 여부·기존 Node suite/build·관련 게이트·정확한 CI를 기록하고 별도 Claude의 실제 코드 검토를 요청한다. 40개 future case는 수행한 항목별 증거가 생기기 전까지 NOT RUN이다. 이 지침은 반복 사용자 승인을 요구하지 않으며 이미 승인된 구현을 이어가도록 한다.

검토자의 I-a~I-e를 구현 제약으로 보존한다. 특히 112 proof-key swaps는 graph equality만으로 검증되지 않으므로 role@scope policy가 필수이며 rule-list 순서가 아닌 DAG 순서로 평가한다. 전체 제품 100%·5대 운영 인수·원래48-task/VFCL 완료율은 올리지 않는다. 원본 검토와 실행 기록은 [[2026-11-06_05-15-00_KST_FLEET5_bootstrap_contracts_v5_8874_검토_Claude]], [[2026-11-06_FLEET5_bootstrap_contracts_v5_unsigned_context_Codex]]에 있다.
