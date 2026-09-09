---
doc_id: "ERR-DISPATCH-001"
title: "ERR-DISPATCH-001 Fixture 의존성과 Node 실행 슬롯 경계"
version: "1.0.0"
status: "review"
author: "Codex"
updated: "2026-09-10T02:47:29+09:00"
source_of_truth: "Git"
---

# ERR-DISPATCH-001 Fixture 의존성과 Node 실행 슬롯 경계

초기 로컬 pytest는 147 passed / 136 skipped / 16 setup errors였다. 새 통합 모듈이 approval 및 node_runtime fixture를 명시적으로 가져오지 않아 발견한 테스트 수집/준비 오류이며 제품 API 실패가 아니다. fixture import를 추가해 해당 모듈이 실제 DB 사전조건까지 도달하는 것을 확인했다.

전송 큐 코드 자체 검토에서 다른 Run 두 개가 같은 Node의 단일 실행 슬롯을 동시에 예약할 수 있는 경계를 확인했다. busy 응답을 불확실 실행으로 남기기 전에 Node 잠금 아래 활성 execute reservation을 검사하도록 보완했다. 운영 장애 또는 수정 전 실장비 race 재현이라고 주장하지 않는다. [[RES-DISPATCH-001 명시적 fixture 및 Node 예약 직렬화]]를 따른다.
