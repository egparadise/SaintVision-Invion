---
doc_id: "ERR-NODE-CONTAINMENT-L2-001"
title: "NODE-CONTAINMENT 승인 경계 검토 오류"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T15:13:00+09:00"
source_of_truth: "Git"
---

# 제어 변경의 승인 요구 누락

NODE-CONTAINMENT의 초기 `5eccc84`/`fb42f8f`/`18e2d23`은 현재 operator 권한과 제어 version·멱등 감사를 검사했지만 별도 내용 고정·만료·2인 승인이 없었다. 2026-09-10 15:08 KST, [[20_Backend 보완 설계]]의 drain L2 분류, [[보안 평가 운영 가이드]]와 기존 ADR-024/L2 승인 하한을 대조해 이 공백을 확인했다. CI의 초기 18/21개 시험 통과는 이 누락된 승인 요구를 검증한 증거가 아니다. 실제 운영 침해나 제어 실행이 관측됐다는 뜻은 아니다.

runtime 자체가 신뢰된 운영자 권한을 사용하더라도 일반 역할 보유와 특정 작업의 승인·만료는 다르다. kill/drain/clear/resume에 승인 대상과 소비 경계를 추가하고, 원래 0022 migration을 수정하지 않는 0023을 작성한다. 해결은 [[NODE-CONTAINMENT 승인 경계 검토 해결]]이다. 독립 reviewer Claude pending.
